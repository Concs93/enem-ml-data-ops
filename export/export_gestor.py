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

# 'Todas' precisa existir em TODA UF x area -- e o padrao da tela. As outras
# passam pelo gate de publicacao por conta propria: a rede municipal tem 205
# escolas no pais e so publica em 8 UFs, o que e a regra funcionando
REDE_PADRAO = "Todas"


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
        select codigo, area, rede, n_presentes, n_escolas, publicavel
        from marts.mart_geografia_area
        where nivel = 'uf' and publicavel
    """)
    area = {}
    for cod, ar, rede, n, escolas, pub in cur.fetchall():
        area[f"{cod}|{ar}|{rede}"] = [int(n), int(escolas)]
    pacote["area"] = area

    # ------------------------------------------------------------- o mapa
    # [competencia, perfil, diferenca, taxa, taxa_nacional, n_itens]
    # o gate do N minimo e o filtro, nao um enfeite: no nivel UF todas as 27
    # passam com folga, mas o mesmo codigo vai servir municipio -- onde 1.942
    # de 5.570 publicam --, e ali a omissao seria silenciosa
    # n_respostas viaja porque a PRECISAO da medida varia 10x entre as redes:
    # o erro-padrao medio da taxa e 0,13 pp em 'Todas' e 1,47 pp na municipal
    # -- que e MAIOR que o desvio-padrao do proprio perfil entre UFs (1,14).
    # Sem esse numero a tela ordenaria ruido como se fosse conselho.
    cur.execute("""
        select codigo, area, rede, competencia,
               perfil, diferenca, taxa_acerto, taxa_acerto_nacional,
               n_itens_validos, n_respostas, diferenca_area, status
        from marts.mart_geografia_competencia
        where nivel = 'uf' and publicavel
        order by codigo, area, rede, competencia
    """)
    dados, patamar = {}, {}
    for (cod, ar, rede, comp, perf, dif, taxa, taxa_nac,
         n_itens, n_resp, dif_area, status) in cur.fetchall():
        if status != "ok":
            continue
        ch = f"{cod}|{ar}|{rede}"
        dados.setdefault(ch, []).append([
            int(comp), float(perf), float(dif),
            float(taxa), float(taxa_nac), int(n_itens), int(n_resp),
        ])
        # a distancia da unidade ate o nacional na area inteira: e o que o
        # perfil desconta, e a tela mostra para nao esconder o nivel
        patamar[ch] = round(float(dif_area), 2)
    pacote["mapa"] = dados
    pacote["patamar"] = patamar

    # as redes que existem, na ordem em que a tela as oferece
    cur.execute("""
        select distinct rede from marts.mart_geografia_competencia
        where nivel = 'uf' and publicavel
    """)
    achadas = {r[0] for r in cur.fetchall()}
    ordem = ["Todas", "Estadual", "Privada", "Federal", "Municipal"]
    pacote["redes"] = [r for r in ordem if r in achadas]
    if achadas - set(ordem):
        raise SystemExit(f"  ERRO: rede desconhecida no mart: {achadas - set(ordem)}")

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

    # 'Todas' tem de existir em TODA UF x area -- e o estado inicial da tela.
    # Sem isso o mapa mostra um buraco cinza que parece "sem dado" quando na
    # verdade e o export que perdeu a linha
    for cod in pacote["ufs"]:
        for ar in COMP_POR_AREA:
            ch = f"{cod}|{ar}|{REDE_PADRAO}"
            if ch not in pacote["mapa"]:
                erros.append(f"mapa: falta {ch}")
            if ch not in pacote["area"]:
                erros.append(f"area: falta contexto de {ch}")

    # toda celula que EXISTE precisa estar completa. Uma rede pode nao
    # publicar numa UF (a municipal so passa o gate em 8) -- isso e a regra
    # funcionando --, mas rede que publica com meia lista e linha perdida
    for ch, linhas in pacote["mapa"].items():
        _cod, ar, _rede = ch.split("|")
        if len(linhas) != COMP_POR_AREA[ar]:
            erros.append(f"mapa: {ch} com {len(linhas)} competencias, "
                         f"esperadas {COMP_POR_AREA[ar]}")
        if ch not in pacote["area"]:
            erros.append(f"area: falta contexto de {ch}")

    # o invariante do perfil: ponderado pelas respostas ele zera dentro de
    # cada UF x area x rede. Aqui nao temos n_respostas por competencia, entao
    # a checagem e mais fraca de proposito -- media simples com folga larga.
    # O `dbt test geografia_perfil_soma_zero` e quem trava isso de verdade;
    # esta guarda so pega o pacote montado ao contrario (sinal trocado,
    # coluna errada), que deslocaria a media em unidades
    for ch, linhas in pacote["mapa"].items():
        media = sum(l[1] for l in linhas) / len(linhas)
        if abs(media) > 1.5:
            erros.append(f"perfil: media {media:.2f} em {ch} -- o patamar "
                         f"nao foi descontado")

    # conservacao: as 27 UFs cobrem os presentes do pais, na rede 'Todas'.
    # Somar sem filtrar rede daria o DOBRO nos dois lados e passaria verde
    cur.execute("""
        select area, n_presentes from marts.mart_geografia_area
        where nivel = 'pais' and rede = %s
    """, (REDE_PADRAO,))
    for ar, n_pais in cur.fetchall():
        soma = sum(v[0] for k, v in pacote["area"].items()
                   if k.endswith(f"|{ar}|{REDE_PADRAO}"))
        if soma != int(n_pais):
            erros.append(f"area: as UFs somam {soma:,} presentes em {ar}, "
                         f"o pais tem {int(n_pais):,}")

    # e as redes somam a 'Todas' dentro de cada UF x area
    for cod in pacote["ufs"]:
        for ar in COMP_POR_AREA:
            todas = pacote["area"].get(f"{cod}|{ar}|{REDE_PADRAO}")
            if not todas:
                continue
            soma = sum(v[0] for r in pacote["redes"] if r != REDE_PADRAO
                       for v in [pacote["area"].get(f"{cod}|{ar}|{r}")] if v)
            # menor e esperado: rede que nao publica fica de fora do pacote
            if soma > todas[0]:
                erros.append(f"area: as redes de {cod}|{ar} somam {soma:,}, "
                             f"acima dos {todas[0]:,} de 'Todas'")

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
              f"competencias | {len(pacote['redes'])} redes | "
              f"{medidas} medidas")

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
