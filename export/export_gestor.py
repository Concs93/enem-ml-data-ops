"""
Exporta o pacote da FACE DO GESTOR: Brasil e as 27 UFs, por competencia e
por rede. UMA SAIDA -- webapp/dados/geografia.json.

SIMPLES POR DECISAO (02/08/2026): municipio, regiao imediata e o relatorio
por escola sairam do produto. O grao fino convida ao uso que fez o INEP
descontinuar o "ENEM por Escola"; a analise vive bem por estado e
competencia. O co_municipio segue como grao de COMPUTO nos marts.

O DESENHO DOS NUMEROS (medido antes de decidido):
- A tela mostra COMPARACOES SIMPLES: taxa da UF menos taxa do Brasil, na
  MESMA rede -- subtracao que o leitor confere de cabeca. A ordem e a mesma
  do indicador centrado em 3.464 de 3.480 listas.
- O `perfil` (desvio do padrao da propria unidade) so pinta o MAPA e vira
  anotacao verbal: entre unidades, a diferenca crua e 90%+ ranking (rho
  0,91-0,97 com o nivel; o perfil, 0,03-0,08).
- `tri` e a competencia em que AVANCAR mais rende no nivel medio da celula
  -- contexto, nunca o numero que ordena.
- `esc` guarda o n_escolas das celulas que EXISTEM mas nao publicam: e o
  que separa "tem 1 escola federal, abaixo do minimo" de "nao tem escola
  federal" (so a contagem cadastral viaja; nota de celula fechada, nunca).

Regras da fronteira: le SO de marts; valida conservacao e FALHA ALTO antes
de gravar parcial; grava atomico (tmp + rename). Arredonda UMA vez, para a
casa da tela (o mart guarda 4 casas).

Uso:
    python -m export.export_gestor
"""

import json
import os
import sys
from collections import defaultdict

import psycopg2
from dotenv import load_dotenv

DESTINO = os.path.join("webapp", "dados", "geografia.json")

UFS_ESPERADAS = 27
# LC 9 · MT 7 · CN 8 · CH 6 -- 30 competencias (Matriz de Referencia)
COMP_POR_AREA = {"CH": 6, "CN": 8, "LC": 9, "MT": 7}
REDE_PADRAO = "Todas"
REDES_CONHECIDAS = ["Todas", "Estadual", "Privada", "Federal", "Municipal"]


def conexao():
    load_dotenv()
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def k(*partes):
    return "|".join(str(p) for p in partes)


def curva_acertos_nota(cur):
    """A ponte acertos->nota por area, para converter distancia de acerto em
    pontos NA MEDIA. Vem do acertos_medio da calibracao (estritamente
    crescente -- e a serie que o site do aluno ja inverte). Em LC as duas
    linguas sao fundidas ponderando pelo n de cada faixa; a honestidade de
    +-13 pontos da conversao nivel<->nota ja esta documentada no projeto."""
    cur.execute("""
        select area, nota_faixa + 5 as nota,
               sum(n * acertos_medio) / sum(n) as acertos
        from marts.mart_calibracao_nota
        group by 1, 2 order by 1, 2
    """)
    curvas = {}
    for area, nota, ac in cur.fetchall():
        curvas.setdefault(area, []).append((float(ac), float(nota)))
    # monotonica por construcao no miolo; o piso saturado pode oscilar --
    # colapsa mantendo a maior nota (mesma regra do site do aluno)
    for area, serie in curvas.items():
        limpa = []
        for ac, nota in serie:
            if limpa and ac <= limpa[-1][0]:
                limpa[-1] = (limpa[-1][0], max(limpa[-1][1], nota))
            else:
                limpa.append((ac, nota))
        curvas[area] = limpa
    return curvas


def nota_de_acertos(curva, ac):
    if ac <= curva[0][0]:
        return curva[0][1]
    if ac >= curva[-1][0]:
        return curva[-1][1]
    for i in range(1, len(curva)):
        if ac <= curva[i][0]:
            a0, n0 = curva[i-1]
            a1, n1 = curva[i]
            return n0 + (n1 - n0) * (ac - a0) / (a1 - a0)
    return curva[-1][1]


def tabela_tri(cur):
    """Para cada (area, theta da grade): a competencia em que avancar meio
    nivel mais devolve acertos. Em LC usa a lingua da MAIORIA -- derivada do
    proprio banco, nunca transcrita."""
    cur.execute("""
        select cod_lingua, sum(n) from marts.mart_calibracao_nota
        where area = 'LC' group by 1 order by 2 desc
    """)
    linhas = [(int(l), float(n)) for l, n in cur.fetchall()]
    lingua_maioria = linhas[0][0]
    pct_maioria = round(100.0 * linhas[0][1] / sum(n for _, n in linhas))

    cur.execute("""
        with h as (
            select theta, area, competencia,
                   sum(n_itens)                                   as n_itens,
                   sum(n_itens * acerto_esperado) / sum(n_itens)  as acerto
            from marts.mart_perfil_habilidade
            where cod_lingua is null or cod_lingua = %s
            group by 1, 2, 3
        ),
        ganho as (
            select a.area, a.theta, a.competencia,
                   sum(a.n_itens * (b.acerto - a.acerto)) as g
            from h a
            join h b on b.area = a.area and b.competencia = a.competencia
                    and b.theta = a.theta + 0.5
            group by 1, 2, 3
        )
        select distinct on (area, theta) area, theta, competencia
        from ganho order by area, theta, g desc
    """, (lingua_maioria,))
    tri = {(a, float(t)): int(c) for a, t, c in cur.fetchall()}
    thetas = sorted({t for _, t in tri})
    rotulo_lc = ("inglês" if lingua_maioria == 0 else "espanhol")
    return tri, thetas, f"{rotulo_lc}, a língua de {pct_maioria}% dos participantes"


def tri_da_media(tri, thetas, area, media_nota):
    if media_nota is None:
        return None
    t = round(((float(media_nota) - 500) / 100.0) / 0.05) * 0.05
    t = min(max(t, thetas[0]), thetas[-1])
    return tri.get((area, round(t, 2)))


def exporta(cur):
    tri_tab, tri_grade, tri_nota_lc = tabela_tri(cur)

    pacote = {"edicao": 2025, "areas": sorted(COMP_POR_AREA),
              "triLC": tri_nota_lc}

    cur.execute("""
        select distinct co_uf, uf, nome_uf, nome_regiao
        from staging.int_municipio_geografia where co_uf is not null
    """)
    pacote["ufs"] = {str(c): [s, n, r] for c, s, n, r in cur.fetchall()}

    cur.execute("""
        select distinct area, competencia, descricao_competencia
        from staging.matriz_referencia
    """)
    pacote["comp"] = {k(a, c): d for a, c, d in cur.fetchall()}

    cur.execute("""
        select distinct area, competencia, n_itens_validos_nacional
        from marts.mart_geografia_competencia where nivel = 'pais'
    """)
    pacote["itens"] = {k(a, c): int(n) for a, c, n in cur.fetchall()}

    # contexto (n, escolas, media) por celula publicavel + tri
    cur.execute("""
        select codigo, area, rede, n_presentes, n_escolas, media_nota
        from marts.mart_geografia_area
        where publicavel and nivel in ('pais', 'uf')
    """)
    ctx, tri_out = {}, {}
    for cod, ar, rede, n, esc, media in cur.fetchall():
        ctx[k(cod, ar, rede)] = [int(n), int(esc), round(float(media))]
        t = tri_da_media(tri_tab, tri_grade, ar, media)
        if t is not None:
            tri_out[k(cod, ar, rede)] = t
    pacote["ctx"] = ctx
    pacote["tri"] = tri_out

    # n_escolas das celulas que existem mas NAO publicam (so cadastral)
    cur.execute("""
        select codigo, area, rede, n_escolas
        from marts.mart_geografia_area
        where not publicavel and nivel in ('pais', 'uf')
    """)
    pacote["esc"] = {k(c, a, r): int(n) for c, a, r, n in cur.fetchall()}

    # [comp, taxa (1 casa), perfil (1 casa), n_respostas]
    cur.execute("""
        select codigo, area, rede, competencia,
               taxa_acerto, perfil, n_respostas
        from marts.mart_geografia_competencia
        where publicavel and status = 'ok' and nivel in ('pais', 'uf')
        order by codigo, area, rede, competencia
    """)
    dados = defaultdict(list)
    for cod, ar, rede, comp, taxa, perfil, n in cur.fetchall():
        dados[k(cod, ar, rede)].append(
            [int(comp), round(float(taxa), 1), round(float(perfil), 1), int(n)])
    pacote["dados"] = dict(dados)

    # ------------------- pontos na media: fechar a distancia para o Brasil
    # Cenario NOMEADO (a melhoria "X%" generica nao existe): se esta rede
    # acertasse, em cada competencia em que esta atras, o que o Brasil da
    # mesma rede acerta, quantos pontos a MEDIA subiria. Convertido pela
    # curva acertos->nota (nao por inclinacao local: o fator varia de ~32 a
    # ~14 pts/acerto ao longo da escala) e PARTICIONADO para as partes
    # somarem o total -- a licao da face do aluno ("somar e exatamente a
    # conferencia que o leitor faz").
    curvas = curva_acertos_nota(cur)
    pacote["pts"] = {}
    for ch, linhas in list(pacote["dados"].items()):
        cod, ar, rede = ch.split("|")
        if cod == "0":
            continue
        br = {l[0]: l[1] for l in pacote["dados"].get(k(0, ar, rede), [])}
        ctx = pacote["ctx"].get(ch)
        if not br or not ctx or not ctx[0]:
            continue
        presentes = ctx[0]
        # questoes POR ALUNO da competencia = respostas / presentes (em LC a
        # C2 tem 10 itens distintos mas cada aluno responde 5 -- e por isso
        # que n_respostas, e nao n_itens, e o divisor certo)
        q_aluno = {l[0]: l[3] / presentes for l in linhas}
        atual = sum(l[1] / 100 * q_aluno[l[0]] for l in linhas)
        delta = {l[0]: max(0.0, (br.get(l[0], 0) - l[1]) / 100) * q_aluno[l[0]]
                 for l in linhas}
        total_delta = sum(delta.values())
        curva = curvas[ar]
        total_pts = (nota_de_acertos(curva, atual + total_delta)
                     - nota_de_acertos(curva, atual)) if total_delta > 1e-9 else 0.0
        total_int = round(total_pts)
        # particao por resto maior: as partes inteiras somam o total exato
        if total_int > 0 and total_delta > 0:
            brutas = {c: total_pts * d / total_delta for c, d in delta.items()}
            partes = {c: int(v) for c, v in brutas.items()}
            sobra = total_int - sum(partes.values())
            for c, _ in sorted(brutas.items(), key=lambda x: -(x[1] % 1)):
                if sobra <= 0:
                    break
                partes[c] += 1
                sobra -= 1
        else:
            partes = {l[0]: 0 for l in linhas}
        for l in linhas:
            l.append(partes.get(l[0], 0))
        pacote["pts"][ch] = total_int

    cur.execute("""
        select distinct rede from marts.mart_geografia_competencia
        where nivel = 'uf' and publicavel
    """)
    achadas = {r[0] for r in cur.fetchall()}
    if achadas - set(REDES_CONHECIDAS):
        raise SystemExit(f"ERRO: rede desconhecida: {achadas - set(REDES_CONHECIDAS)}")
    pacote["redes"] = [r for r in REDES_CONHECIDAS if r in achadas]

    return pacote


def valida(cur, pacote):
    erros = []

    if len(pacote["ufs"]) != UFS_ESPERADAS:
        erros.append(f"ufs: {len(pacote['ufs'])}, esperadas {UFS_ESPERADAS}")
    if len(pacote["comp"]) != 30:
        erros.append(f"comp: {len(pacote['comp'])}, esperadas 30")

    # pais e toda UF com 'Todas' completa em toda area -- o estado inicial
    for cod in ["0"] + list(pacote["ufs"]):
        for ar, n_esp in COMP_POR_AREA.items():
            ch = k(cod, ar, REDE_PADRAO)
            if ch not in pacote["ctx"]:
                erros.append(f"ctx: falta {ch}")
            if len(pacote["dados"].get(ch, [])) != n_esp:
                erros.append(f"dados: {ch} incompleta")
            if ch not in pacote["tri"]:
                erros.append(f"tri: falta {ch}")

    # paridade ctx <-> dados (um sem o outro e painel morto em silencio)
    if set(pacote["ctx"]) != set(pacote["dados"]):
        dif = set(pacote["ctx"]) ^ set(pacote["dados"])
        erros.append(f"paridade: {len(dif)} celulas em so um de ctx/dados "
                     f"(ex.: {sorted(dif)[:3]})")

    # toda celula que existe esta completa
    for ch, linhas in pacote["dados"].items():
        ar = ch.split("|")[1]
        if len(linhas) != COMP_POR_AREA[ar]:
            erros.append(f"dados: {ch} com {len(linhas)} competencias")
            break

    # conservacao: as UFs somam o pais (rede 'Todas', por area)
    for ar in COMP_POR_AREA:
        pais = pacote["ctx"].get(k(0, ar, REDE_PADRAO))
        soma = sum(pacote["ctx"][k(c, ar, REDE_PADRAO)][0]
                   for c in pacote["ufs"]
                   if k(c, ar, REDE_PADRAO) in pacote["ctx"])
        if pais and soma != pais[0]:
            erros.append(f"conservacao: UFs somam {soma:,} em {ar}, "
                         f"pais tem {pais[0]:,}")

    # o perfil zera dentro da celula (guarda frouxa; o dbt test trava exato)
    for ch, linhas in pacote["dados"].items():
        media = sum(l[2] for l in linhas) / len(linhas)
        if abs(media) > 1.5:
            erros.append(f"perfil: media {media:.2f} em {ch}")

    # as partes dos pontos somam o total (a conferencia que o leitor faz)
    for ch, total in pacote["pts"].items():
        soma = sum(l[4] for l in pacote["dados"][ch] if len(l) > 4)
        if soma != total:
            erros.append(f"pts: partes somam {soma} != total {total} em {ch}")
        if total < 0:
            erros.append(f"pts: total negativo em {ch}")

    # o tri aponta competencia que existe na area
    for ch, c in pacote["tri"].items():
        ar = ch.split("|")[1]
        if k(ar, c) not in pacote["comp"]:
            erros.append(f"tri: {ch} aponta C{c}, inexistente em {ar}")

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
        medidas = sum(len(v) for v in pacote["dados"].values())
        print(f"  ok: 27 UFs | {len(pacote['redes'])} redes | "
              f"{medidas} medidas")

        print("3. Gravando")
        os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
        tmp = DESTINO + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(pacote, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, DESTINO)
        print(f"  {DESTINO}: {os.path.getsize(DESTINO)/1024:.0f} KB")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
