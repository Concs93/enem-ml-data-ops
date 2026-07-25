"""
Carrega o cadastro de escolas do Censo Escolar (INEP) na camada raw.

Por que este script existe: os microdados do ENEM identificam a escola apenas
por CO_ESCOLA, um codigo do INEP que ninguem sabe de cabeca. Sem o cadastro,
nenhuma escola consegue se encontrar num relatorio -- o que inviabiliza
qualquer produto consultavel. O Censo traz o nome, e de quebra a geografia do
IBGE (meso e microrregiao), o porte e a infraestrutura.

Duas diferencas em relacao ao load_raw.py, e as duas sao de proposito:

1. Le o CSV DE DENTRO do zip, sem extrair. O arquivo tem 208 MB descompactado
   contra 32 MB zipado; extrair seria gastar disco para jogar fora depois.

2. Baixa sozinho se o zip nao existir. E artefato publico e versionado por ano
   -- a mesma logica do build_matriz.py, que busca o PDF oficial.

Descasamento conhecido: o Censo do MESMO ano do ENEM costuma nao existir ainda
quando os microdados do ENEM saem (o Censo e coletado em maio e publicado bem
depois). Usa-se o ano anterior, e o script avisa quando isso acontece.

Uso:
    python -m ingestion.load_censo --ano 2024
    python -m ingestion.load_censo --ano 2024 --zip data/raw/censo_escolar_2024.zip
"""

import argparse
import csv
import io
import os
import sys
import time
import urllib.request
import zipfile

import psycopg2
from dotenv import load_dotenv

from ingestion.config import (CENSO_CSV_INTERNO, CENSO_ESCOLAR, CENSO_URL,
                              CHUNKSIZE, CSV_ENCODING, CSV_SEP)

# o cadastro tem ~215 mil escolas; menos que isto e leitura parcial, nao
# uma rede escolar que encolheu
MINIMO_ESPERADO = 150_000


def conexao():
    load_dotenv()
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def baixa(ano, destino):
    """Busca o zip do INEP se ele ainda nao estiver em disco."""
    if os.path.exists(destino):
        print(f"  zip ja existe: {destino} "
              f"({os.path.getsize(destino) / 1048576:.0f} MB)")
        return destino

    url = CENSO_URL.format(ano=ano)
    print(f"  baixando {url}")
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)

    # baixa para um nome temporario e so renomeia no fim. Se a conexao cair no
    # meio, o parcial nao vira "zip ja existe" na proxima execucao -- que seria
    # pior que falhar, porque o erro apareceria como zip corrompido
    parcial = destino + ".parcial"
    try:
        urllib.request.urlretrieve(url, parcial)
        zipfile.ZipFile(parcial).testzip()   # o download veio inteiro?
        os.replace(parcial, destino)
    except Exception as e:
        if os.path.exists(parcial):
            os.remove(parcial)
        raise SystemExit(
            f"\nFALHA ao baixar o Censo {ano}: {e}\n"
            f"Se for 404 ou conexao recusada, o Censo {ano} provavelmente ainda\n"
            f"nao foi publicado -- use o ano anterior. O cadastro de escolas e\n"
            f"estavel entre edicoes, e o script avisa no cruzamento final quanto\n"
            f"disso custou."
        )
    print(f"  ok: {os.path.getsize(destino) / 1048576:.0f} MB")
    return destino


def acha_csv(zf, ano):
    """Localiza o CSV do cadastro dentro do zip.

    O INEP varia o nome da pasta raiz entre edicoes (2024 veio como
    '..._defeso'), entao casamos pelo final do caminho em vez de fixar tudo.
    """
    alvo = CENSO_CSV_INTERNO.format(ano=ano)
    for nome in zf.namelist():
        if nome.replace("\\", "/").endswith(alvo):
            return nome
    raise SystemExit(
        f"\nFALHA: nao achei '{alvo}' dentro do zip.\n"
        f"Arquivos disponiveis:\n  " +
        "\n  ".join(n for n in zf.namelist() if n.endswith(".csv"))
    )


def carrega(ano, caminho_zip):
    tabela = f"censo_escolar_{ano}"
    zf = zipfile.ZipFile(caminho_zip)
    interno = acha_csv(zf, ano)
    print(f"  lendo {interno}")

    conn = conexao()
    cur = conn.cursor()
    t0, total, blocos = time.time(), 0, 0

    try:
        cur.execute("create schema if not exists raw;")
        # CASCADE pelo mesmo motivo do load_raw.py: assim que existir uma view
        # do staging sobre esta tabela, o DROP simples passa a ser recusado
        cur.execute(f"drop table if exists raw.{tabela} cascade;")
        cols_sql = ", ".join(f'"{c}" text' for c in CENSO_ESCOLAR)
        cur.execute(f"create table raw.{tabela} ({cols_sql});")
        conn.commit()
        print(f"  tabela raw.{tabela} criada com {len(CENSO_ESCOLAR)} colunas")

        with zf.open(interno) as fh:
            texto = io.TextIOWrapper(fh, encoding=CSV_ENCODING, newline="")
            leitor = csv.reader(texto, delimiter=CSV_SEP)
            cabecalho = next(leitor)

            faltando = [c for c in CENSO_ESCOLAR if c not in cabecalho]
            if faltando:
                raise SystemExit(
                    f"\nFALHA: o arquivo do Censo {ano} nao tem estas colunas:\n"
                    f"  {faltando}\n"
                    f"O layout mudou entre edicoes -- ajuste CENSO_ESCOLAR em "
                    f"ingestion/config.py."
                )
            indices = [cabecalho.index(c) for c in CENSO_ESCOLAR]

            buf = io.StringIO()
            escritor = csv.writer(buf)
            no_bloco = 0

            def descarrega():
                nonlocal buf, escritor, no_bloco, total, blocos
                if not no_bloco:
                    return
                buf.seek(0)
                cur.copy_expert(
                    f"copy raw.{tabela} from stdin with (format csv)", buf)
                conn.commit()   # commit por bloco: progresso duravel
                total += no_bloco
                blocos += 1
                print(f"  bloco {blocos}: +{no_bloco:,} linhas "
                      f"(total {total:,})")
                buf = io.StringIO()
                escritor = csv.writer(buf)
                no_bloco = 0

            for linha in leitor:
                if len(linha) <= indices[-1]:
                    continue        # linha truncada: o Censo tem algumas
                escritor.writerow([linha[i] for i in indices])
                no_bloco += 1
                if no_bloco >= CHUNKSIZE:
                    descarrega()
            descarrega()

        print(f"OK: {total:,} linhas em raw.{tabela} "
              f"em {time.time() - t0:.0f}s")
        return conn, cur, tabela, total

    except Exception:
        conn.rollback()
        conn.close()
        raise


def valida(cur, tabela, total):
    """Falha alto. Um cadastro pela metade produz escolas sem nome e ninguem
    percebe -- o relatorio simplesmente mostra menos."""
    erros = []

    if total < MINIMO_ESPERADO:
        erros.append(f"so {total:,} escolas carregadas; esperado "
                     f"{MINIMO_ESPERADO:,}+ (leitura parcial?)")

    cur.execute(f'select count(*) from raw.{tabela} '
                f'where "CO_ENTIDADE" is null or "CO_ENTIDADE" = \'\';')
    if (n := cur.fetchone()[0]):
        erros.append(f"{n:,} linhas sem CO_ENTIDADE (a chave do cruzamento)")

    cur.execute(f'select count(*) - count(distinct "CO_ENTIDADE") '
                f'from raw.{tabela};')
    if (n := cur.fetchone()[0]):
        erros.append(f"{n:,} CO_ENTIDADE duplicados; o grao deveria ser "
                     f"uma linha por escola")

    cur.execute(f'select count(*) from raw.{tabela} '
                f'where "NO_ENTIDADE" is null or "NO_ENTIDADE" = \'\';')
    if (n := cur.fetchone()[0]):
        erros.append(f"{n:,} escolas sem nome -- e justamente o nome que "
                     f"motiva esta ingestao")

    return erros


def relatorio(cur, tabela):
    """Quanto do ENEM este cadastro consegue nomear. Se a tabela do diagnostico
    ainda nao existir, apenas pula -- a ingestao nao depende dela."""
    cur.execute("select to_regclass('marts.mart_escola_area');")
    if cur.fetchone()[0] is None:
        print("\n  (marts.mart_escola_area ainda nao existe; "
              "pulando o cruzamento)")
        return

    cur.execute(f"""
        select count(*)                                          as escolas,
               count(*) filter (where c."CO_ENTIDADE" is null)   as sem_nome,
               sum(m.n_presentes)                                as participantes,
               sum(m.n_presentes) filter (where c."CO_ENTIDADE" is null)
                                                                 as part_sem_nome
        from marts.mart_escola_area m
        left join raw.{tabela} c
               on c."CO_ENTIDADE"::bigint = m.co_escola
        where m.area = 'MT' and m.publicavel;
    """)
    esc, sem, part, part_sem = cur.fetchone()
    print("\nCruzamento com o diagnostico (escolas publicaveis em MT)")
    print(f"  escolas          : {esc:,}")
    print(f"  sem nome         : {sem:,} ({100 * sem / esc:.1f}%)")
    print(f"  participantes    : {part:,}")
    print(f"  sem nome         : {part_sem or 0:,} "
          f"({100 * (part_sem or 0) / part:.1f}%)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, default=2024,
                    help="edicao do Censo Escolar (padrao: 2024)")
    ap.add_argument("--zip", dest="caminho",
                    help="zip ja baixado; sem isto, o script busca no INEP")
    args = ap.parse_args()

    destino = args.caminho or f"data/raw/censo_escolar_{args.ano}.zip"

    print("1. Zip")
    baixa(args.ano, destino)

    print("2. Carga")
    conn, cur, tabela, total = carrega(args.ano, destino)

    try:
        print("3. Validacao")
        erros = valida(cur, tabela, total)
        if erros:
            print("\nFALHA -- a tabela foi criada mas NAO e confiavel:")
            for e in erros:
                print(f"  ! {e}")
            sys.exit(1)
        print("  ok: chave unica, sem nulos, volume esperado")

        relatorio(cur, tabela)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
