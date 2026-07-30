"""
Exporta o pacote da FACE DO GESTOR (geografia.json) a partir dos marts.

Passo inicial: nivel UF, grao competencia. Sao 27 unidades x 4 areas x 6 a 9
competencias -- ~810 numeros, alguns KB. Regiao imediata (510 unidades) e
municipio (1.942 publicaveis) entram depois, no mesmo formato.

O QUE VIAJA, E POR QUE:
- `perfil` e o numero que o mapa pinta. E a diferenca contra o nacional
  DEPOIS de descontar o patamar da propria UF na area. A diferenca crua e
  80% "este estado vai melhor/pior em tudo" -- pintar com ela seria ranking
  disfarcado (ver mart_geografia_competencia).
- `diferenca` viaja junto porque a tela precisa dizer as duas coisas sem
  esconder nenhuma: onde a rede esta como um todo, e onde ela se distancia
  do proprio patamar.

Regras da fronteira (as mesmas do export do aluno):
- le SO de marts (nunca de camada interna);
- valida conservacao contra o banco e FALHA ALTO antes de gravar parcial;
- grava atomico: escreve em .tmp e renomeia no fim.

Uso:
    python -m export.export_gestor          # grava webapp/dados/geografia.json
"""

import json
import os
import sys

import psycopg2
from dotenv import load_dotenv

DESTINO = os.path.join("webapp", "dados", "geografia.json")

UFS_ESPERADAS = 27
# LC 9 · MT 7 · CN 8 · CH 6 -- 30 competencias no total (Matriz de Referencia)
COMP_POR_AREA = {"CH": 6, "CN": 8, "LC": 9, "MT": 7}


def conexao():
    load_dotenv()
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def exporta(cur):
    pacote = {"edicao": 2025, "nivel": "uf", "areas": sorted(COMP_POR_AREA)}

    # ------------------------------------------------------------- as UFs
    # a sigla sai do proprio cadastro (derivar, nunca transcrever)
    cur.execute("""
        select distinct co_uf, uf, nome_uf, nome_regiao
        from staging.int_municipio_geografia
        where co_uf is not null
    """)
    ufs = {}
    for cod, sigla, nome, regiao in cur.fetchall():
        ufs[str(cod)] = [sigla, nome, regiao]
    pacote["ufs"] = ufs

    # -------------------------------------------------------- competencias
    cur.execute("""
        select distinct area, competencia, descricao_competencia
        from staging.matriz_referencia
    """)
    pacote["comp"] = {f"{a}|{c}": d for a, c, d in cur.fetchall()}

    # ------------------------------------------------------ contexto de area
    # participantes e media da nota por UF x area: e o que da escala humana ao
    # mapa ("estes 145 mil alunos"), nao um ranking -- a ordenacao da tela e
    # sempre por perfil
    cur.execute("""
        select codigo, area, n_presentes, media_nota, publicavel
        from marts.mart_geografia_area
        where nivel = 'uf'
    """)
    area = {}
    for cod, ar, n, media, pub in cur.fetchall():
        area[f"{cod}|{ar}"] = [int(n), round(float(media), 1), bool(pub)]
    pacote["area"] = area

    # ------------------------------------------------------------- o mapa
    # [competencia, perfil, diferenca, taxa, taxa_nacional, n_itens]
    # o gate do N minimo e o filtro, nao um enfeite: no nivel UF todas as 27
    # passam com folga, mas o mesmo codigo vai servir municipio -- onde 1.942
    # de 5.570 publicam --, e ali a omissao seria silenciosa
    cur.execute("""
        select codigo, area, competencia,
               perfil, diferenca, taxa_acerto, taxa_acerto_nacional,
               n_itens_validos, diferenca_area, status
        from marts.mart_geografia_competencia
        where nivel = 'uf' and publicavel
        order by codigo, area, competencia
    """)
    dados, patamar = {}, {}
    for (cod, ar, comp, perf, dif, taxa, taxa_nac,
         n_itens, dif_area, status) in cur.fetchall():
        if status != "ok":
            continue
        ch = f"{cod}|{ar}"
        dados.setdefault(ch, []).append([
            int(comp), float(perf), float(dif),
            float(taxa), float(taxa_nac), int(n_itens),
        ])
        patamar[ch] = round(float(dif_area), 2)
    pacote["mapa"] = dados
    pacote["patamar"] = patamar

    return pacote


def valida(cur, pacote):
    """Um mapa parcial no ar pinta um estado de cinza e ninguem percebe --
    melhor nao gravar."""
    erros = []

    if len(pacote["ufs"]) != UFS_ESPERADAS:
        erros.append(f"ufs: {len(pacote['ufs'])} unidades, esperadas "
                     f"{UFS_ESPERADAS}")

    if len(pacote["comp"]) != 30:
        erros.append(f"comp: {len(pacote['comp'])} competencias, esperadas 30")

    # toda UF tem as quatro areas, e toda area tem TODAS as suas competencias.
    # Sem isso o mapa mostra um buraco cinza que parece "sem dado" quando na
    # verdade e o export que perdeu a linha
    for cod in pacote["ufs"]:
        for ar, n_esp in COMP_POR_AREA.items():
            ch = f"{cod}|{ar}"
            if ch not in pacote["mapa"]:
                erros.append(f"mapa: falta {ch}")
                continue
            if len(pacote["mapa"][ch]) != n_esp:
                erros.append(f"mapa: {ch} com {len(pacote['mapa'][ch])} "
                             f"competencias, esperadas {n_esp}")
            if ch not in pacote["area"]:
                erros.append(f"area: falta contexto de {ch}")

    # o invariante do perfil: ponderado pelas respostas ele zera dentro de
    # cada UF x area. Aqui nao temos n_respostas por competencia, entao a
    # checagem e mais fraca de proposito -- media simples com folga larga.
    # O `dbt test geografia_perfil_soma_zero` e quem trava isso de verdade;
    # esta guarda so pega o pacote montado ao contrario (sinal trocado,
    # coluna errada), que deslocaria a media em unidades
    for ch, linhas in pacote["mapa"].items():
        media = sum(l[1] for l in linhas) / len(linhas)
        if abs(media) > 1.5:
            erros.append(f"perfil: media {media:.2f} em {ch} -- o patamar "
                         f"nao foi descontado")

    # o pais tem de somar: as 27 UFs cobrem os presentes do nivel 'pais'
    cur.execute("""
        select area, n_presentes from marts.mart_geografia_area
        where nivel = 'pais'
    """)
    for ar, n_pais in cur.fetchall():
        soma = sum(v[0] for k, v in pacote["area"].items()
                   if k.endswith(f"|{ar}"))
        if soma != int(n_pais):
            erros.append(f"area: as UFs somam {soma:,} presentes em {ar}, "
                         f"o pais tem {int(n_pais):,}")

    return erros


def main():
    conn = conexao()
    cur = conn.cursor()
    try:
        print("1. Exportando dos marts")
        pacote = exporta(cur)

        print("2. Validando conservacao")
        erros = valida(cur, pacote)
        if erros:
            print("\nFALHA -- nada foi gravado:")
            for e in erros:
                print(f"  ! {e}")
            sys.exit(1)
        medidas = sum(len(v) for v in pacote["mapa"].values())
        print(f"  ok: {len(pacote['ufs'])} UFs | {len(pacote['comp'])} "
              f"competencias | {medidas} medidas")

        print("3. Gravando")
        os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
        tmp = DESTINO + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(pacote, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, DESTINO)
        kb = os.path.getsize(DESTINO) / 1024
        print(f"  {DESTINO}: {kb:.0f} KB")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
