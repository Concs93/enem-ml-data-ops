"""
Exporta os pacotes da FACE DO GESTOR -- a navegacao por grao:
Brasil > estado > cidade > rede, cada nivel com o diagnostico DELE.

TRES SAIDAS:
  webapp/dados/geografia.json           pais + as 27 UFs (todas as redes)
  webapp/dados/geo_mun/{uf}.json        municipios + regioes imediatas da UF
  webapp/dados/municipios_indice.json   [codigo, nome, sigla, publica] p/ busca

O DESENHO DOS NUMEROS (decisao de 01/08/2026, medida antes de decidida):
- A tela mostra COMPARACOES SIMPLES: taxa da unidade menos taxa do pai
  geografico e menos taxa do Brasil, sempre NA MESMA REDE. Sao subtracoes
  que o leitor confere de cabeca. A ordem da lista e a mesma que a do
  indicador centrado (medido: 3.464 de 3.480 listas identicas), entao a
  simplicidade nao custa o conselho.
- O `perfil` (desvio do padrao da propria unidade) viaja junto, mas so pinta
  o MAPA e vira anotacao verbal -- entre unidades de niveis diferentes, a
  diferenca crua e 90%+ ranking (rho 0,91-0,97 com o nivel; o perfil, 0,03-
  0,08). Cada painel usa a medida que a pergunta dele exige.
- `tri` e a competencia em que AVANCAR mais rende no nivel medio da celula
  (ganho de um passo do mart_perfil_habilidade). E quase um fato nacional
  (1 a 3 respostas distintas entre 27 UFs), por isso e UMA linha de
  contexto, nunca o numero que ordena.

Regras da fronteira (as mesmas do export do aluno):
- le SO de marts;
- valida conservacao contra o banco e FALHA ALTO antes de gravar parcial;
- grava atomico (tmp + rename), e o conjunto so e valido se TODOS os
  arquivos gravarem -- por isso valida tudo antes do primeiro rename.

Uso:
    python -m export.export_gestor
"""

import json
import os
import sys
from collections import defaultdict

import psycopg2
from dotenv import load_dotenv

DESTINO_RAIZ = os.path.join("webapp", "dados", "geografia.json")
PASTA_MUN = os.path.join("webapp", "dados", "geo_mun")
DESTINO_INDICE = os.path.join("webapp", "dados", "municipios_indice.json")

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


# ---------------------------------------------------------------- TRI (contexto)
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
    """media da nota -> theta na grade de 0,05 -> competencia que mais rende."""
    if media_nota is None:
        return None
    t = round(((float(media_nota) - 500) / 100.0) / 0.05) * 0.05
    t = min(max(t, thetas[0]), thetas[-1])
    return tri.get((area, round(t, 2)))


# ------------------------------------------------------------------- extracao
def exporta(cur):
    tri_tab, tri_grade, tri_nota_lc = tabela_tri(cur)

    raiz = {"edicao": 2025, "areas": sorted(COMP_POR_AREA),
            "triLC": tri_nota_lc}

    cur.execute("""
        select distinct co_uf, uf, nome_uf, nome_regiao
        from staging.int_municipio_geografia where co_uf is not null
    """)
    raiz["ufs"] = {str(c): [s, n, r] for c, s, n, r in cur.fetchall()}

    cur.execute("""
        select distinct area, competencia, descricao_competencia
        from staging.matriz_referencia
    """)
    raiz["comp"] = {k(a, c): d for a, c, d in cur.fetchall()}

    cur.execute("""
        select distinct area, competencia, n_itens_validos_nacional
        from marts.mart_geografia_competencia where nivel = 'pais'
    """)
    raiz["itens"] = {k(a, c): int(n) for a, c, n in cur.fetchall()}

    # ---------------- contexto (n, escolas, media) por celula publicavel
    cur.execute("""
        select nivel, codigo, area, rede, n_presentes, n_escolas, media_nota
        from marts.mart_geografia_area
        where publicavel and nivel in ('pais', 'uf', 'municipio', 'regiao_imediata')
    """)
    ctx = {"pais_uf": {}, "mun": defaultdict(dict), "ri": defaultdict(dict)}
    tri_out = {"pais_uf": {}, "mun": defaultdict(dict), "ri": defaultdict(dict)}
    for nivel, cod, ar, rede, n, esc, media in cur.fetchall():
        val = [int(n), int(esc), round(float(media))]
        chave = k(cod, ar, rede)
        t = tri_da_media(tri_tab, tri_grade, ar, media)
        if nivel in ("pais", "uf"):
            ctx["pais_uf"][chave] = val
            if t is not None:
                tri_out["pais_uf"][chave] = t
        elif nivel == "municipio":
            ctx["mun"][cod][k(ar, rede)] = val
            if t is not None:
                tri_out["mun"][cod][k(ar, rede)] = t
        else:
            ctx["ri"][cod][k(ar, rede)] = val
            if t is not None:
                tri_out["ri"][cod][k(ar, rede)] = t

    # ---------------- competencias por celula publicavel (status ok)
    # [comp, taxa (1 casa), perfil (1 casa), n_respostas (a margem sai dele
    #  no navegador)]. O mart guarda 4 casas e AQUI arredonda-se UMA vez,
    #  para a casa que a tela exibe -- arredondar duas vezes trocava o
    #  digito em ~1 de cada 10 celulas (crivo de 01/08/2026)
    cur.execute("""
        select nivel, codigo, area, rede, competencia,
               taxa_acerto, perfil, n_respostas
        from marts.mart_geografia_competencia
        where publicavel and status = 'ok'
          and nivel in ('pais', 'uf', 'municipio', 'regiao_imediata')
        order by nivel, codigo, area, rede, competencia
    """)
    dados = {"pais_uf": defaultdict(list), "mun": defaultdict(lambda: defaultdict(list)),
             "ri": defaultdict(lambda: defaultdict(list))}
    for nivel, cod, ar, rede, comp, taxa, perfil, n in cur.fetchall():
        linha = [int(comp), round(float(taxa), 1), round(float(perfil), 1), int(n)]
        if nivel in ("pais", "uf"):
            dados["pais_uf"][k(cod, ar, rede)].append(linha)
        elif nivel == "municipio":
            dados["mun"][cod][k(ar, rede)].append(linha)
        else:
            dados["ri"][cod][k(ar, rede)].append(linha)

    raiz["ctx"] = ctx["pais_uf"]
    raiz["dados"] = {c: v for c, v in dados["pais_uf"].items()}
    raiz["tri"] = tri_out["pais_uf"]

    cur.execute("""
        select distinct rede from marts.mart_geografia_competencia
        where nivel = 'uf' and publicavel
    """)
    achadas = {r[0] for r in cur.fetchall()}
    if achadas - set(REDES_CONHECIDAS):
        raise SystemExit(f"ERRO: rede desconhecida: {achadas - set(REDES_CONHECIDAS)}")
    raiz["redes"] = [r for r in REDES_CONHECIDAS if r in achadas]

    # ---------------- cadastro municipal: nome, regiao imediata, UF
    # a UF sai do PROPRIO codigo (2 primeiros digitos) e nao do cadastro:
    # Boa Esperanca do Norte/MT existe no ENEM e nao no Censo 2024 -- pelo
    # cadastro ela ficaria sem UF e cairia do pacote
    cur.execute("""
        select a.codigo,
               max(a.nome)                    as nome,
               max(g.co_regiao_imediata)      as ri
        from marts.mart_geografia_area a
        left join staging.int_municipio_geografia g on g.co_municipio = a.codigo
        where a.nivel = 'municipio'
        group by 1
    """)
    municipios = {cod: {"nome": nome, "ri": ri} for cod, nome, ri in cur.fetchall()}

    cur.execute("""
        select distinct codigo, nome from marts.mart_geografia_area
        where nivel = 'regiao_imediata'
    """)
    nomes_ri = dict(cur.fetchall())

    # ---------------- monta os pacotes por UF
    pacotes = {}
    for cod, cad in municipios.items():
        uf = cod // 100000
        p = pacotes.setdefault(uf, {"uf": uf, "mun": {}, "ri": {}})
        entrada = {"nome": cad["nome"]}
        if cad["ri"] is not None:
            entrada["ri"] = int(cad["ri"])
        if cod in ctx["mun"]:
            entrada["ctx"] = ctx["mun"][cod]
            entrada["dados"] = dados["mun"][cod]
            entrada["tri"] = tri_out["mun"][cod]
        p["mun"][str(cod)] = entrada
    for cod, cel in ctx["ri"].items():
        uf = cod // 10000
        p = pacotes.setdefault(uf, {"uf": uf, "mun": {}, "ri": {}})
        p["ri"][str(cod)] = {"nome": nomes_ri.get(cod, str(cod)),
                             "ctx": cel, "dados": dados["ri"][cod],
                             "tri": tri_out["ri"][cod]}

    # ---------------- indice de busca
    indice = sorted(
        [[cod, cad["nome"], raiz["ufs"].get(str(cod // 100000), ["?"])[0],
          1 if cod in ctx["mun"] else 0]
         for cod, cad in municipios.items()],
        key=lambda l: l[1])

    return raiz, pacotes, indice


# ------------------------------------------------------------------ validacao
def valida(cur, raiz, pacotes, indice):
    """Um pacote parcial no ar e um mapa que mente com confianca."""
    erros = []

    if len(raiz["ufs"]) != UFS_ESPERADAS:
        erros.append(f"ufs: {len(raiz['ufs'])}, esperadas {UFS_ESPERADAS}")
    if len(raiz["comp"]) != 30:
        erros.append(f"comp: {len(raiz['comp'])}, esperadas 30")

    # pais e toda UF precisam da rede 'Todas' completa em toda area -- e o
    # estado inicial da tela
    for cod in ["0"] + list(raiz["ufs"]):
        for ar, n_esp in COMP_POR_AREA.items():
            ch = k(cod, ar, REDE_PADRAO)
            if ch not in raiz["ctx"]:
                erros.append(f"ctx: falta {ch}")
            linhas = raiz["dados"].get(ch, [])
            if len(linhas) != n_esp:
                erros.append(f"dados: {ch} com {len(linhas)} competencias, "
                             f"esperadas {n_esp}")
            if ch not in raiz["tri"]:
                erros.append(f"tri: falta {ch}")

    # toda celula que EXISTE esta completa (vale para municipio tambem --
    # conferido no banco: nenhuma celula publicavel tem status != ok)
    def confere_completo(rotulo, dados_cel):
        for ch, linhas in dados_cel.items():
            ar = ch.split("|")[-2] if rotulo != "raiz" else ch.split("|")[1]
            if len(linhas) != COMP_POR_AREA[ar]:
                erros.append(f"{rotulo}: {ch} com {len(linhas)} competencias")
                return  # um exemplo basta; a causa e a mesma
    confere_completo("raiz", raiz["dados"])
    for uf, p in pacotes.items():
        for cod, m in p["mun"].items():
            if "dados" in m:
                confere_completo(f"mun {cod}", m["dados"])
        for cod, r in p["ri"].items():
            confere_completo(f"ri {cod}", r["dados"])

    # paridade ctx <-> dados: o JS espera que toda celula com contexto tenha
    # lista e vice-versa; um lado sem o outro e painel morto em silencio
    if set(raiz["ctx"]) != set(raiz["dados"]):
        dif = set(raiz["ctx"]) ^ set(raiz["dados"])
        erros.append(f"paridade: {len(dif)} celulas em so um de ctx/dados "
                     f"(ex.: {sorted(dif)[:3]})")
    for uf, pacote in pacotes.items():
        for cod, m in list(pacote["mun"].items()) + list(pacote["ri"].items()):
            if ("ctx" in m) != ("dados" in m) or                ("ctx" in m and set(m["ctx"]) != set(m["dados"])):
                erros.append(f"paridade: {cod} (UF {uf}) com ctx e dados "
                             f"divergentes")
                break

    # conservacao 1: as UFs somam o pais (rede 'Todas', por area)
    for ar in COMP_POR_AREA:
        pais = raiz["ctx"].get(k(0, ar, REDE_PADRAO))
        soma = sum(raiz["ctx"][k(c, ar, REDE_PADRAO)][0] for c in raiz["ufs"]
                   if k(c, ar, REDE_PADRAO) in raiz["ctx"])
        if pais and soma != pais[0]:
            erros.append(f"conservacao: UFs somam {soma:,} em {ar}, "
                         f"pais tem {pais[0]:,}")

    # conservacao 2: os municipios de cada UF somam a UF -- CONTRA O BANCO,
    # porque o pacote so carrega os publicaveis (a soma do pacote e menor por
    # construcao, e isso nao e defeito)
    cur.execute("""
        with mun as (
            select codigo / 100000 as uf, area, sum(n_presentes) as n
            from marts.mart_geografia_area
            where nivel = 'municipio' and rede = %s
            group by 1, 2
        )
        select u.codigo, u.area, u.n_presentes, m.n
        from marts.mart_geografia_area u
        join mun m on m.uf = u.codigo and m.area = u.area
        where u.nivel = 'uf' and u.rede = %s
          and u.n_presentes is distinct from m.n
    """, (REDE_PADRAO, REDE_PADRAO))
    vazou = cur.fetchall()
    if vazou:
        erros.append(f"conservacao: {len(vazou)} celulas UF x area em que os "
                     f"municipios nao somam a UF (ex.: {vazou[:2]})")

    # o perfil zera dentro da celula (guarda frouxa; o dbt test
    # geografia_perfil_soma_zero trava com o peso exato)
    for ch, linhas in raiz["dados"].items():
        media = sum(l[2] for l in linhas) / len(linhas)
        if abs(media) > 1.5:
            erros.append(f"perfil: media {media:.2f} em {ch}")

    # o tri aponta competencia que existe na area
    for ch, c in raiz["tri"].items():
        ar = ch.split("|")[1]
        if k(ar, c) not in raiz["comp"]:
            erros.append(f"tri: {ch} aponta C{c}, inexistente em {ar}")

    # indice cobre exatamente os municipios do mart
    cur.execute("select count(distinct codigo) from marts.mart_geografia_area "
                "where nivel = 'municipio'")
    n_mart = cur.fetchone()[0]
    if len(indice) != n_mart:
        erros.append(f"indice: {len(indice)} municipios, mart tem {n_mart}")

    # a malha municipal precisa existir para toda UF do pacote -- um pacote
    # sem malha vira um estado que abre e nao desenha
    for uf in pacotes:
        if not os.path.exists(os.path.join("webapp", "dados", "malha_mun",
                                           f"{uf}.json")):
            erros.append(f"malha: falta webapp/dados/malha_mun/{uf}.json "
                         f"(rodar ingestion.baixa_malha_municipios)")

    return erros


def grava(caminho, obj):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, caminho)
    return os.path.getsize(caminho) / 1024


def main():
    conn = conexao()
    cur = conn.cursor()
    try:
        print("1. Exportando dos marts")
        raiz, pacotes, indice = exporta(cur)

        print("2. Validando conservacao")
        erros = valida(cur, raiz, pacotes, indice)
        if erros:
            print("\nFALHA -- nada foi gravado:")
            for e in erros:
                print(f"  ! {e}")
            sys.exit(1)
        medidas = sum(len(v) for v in raiz["dados"].values())
        pub = sum(1 for l in indice if l[3])
        print(f"  ok: 27 UFs | {medidas} medidas pais+UF | "
              f"{len(pacotes)} pacotes | {len(indice)} municipios no indice "
              f"({pub} publicam)")

        print("3. Gravando")
        kb = grava(DESTINO_RAIZ, raiz)
        print(f"  {DESTINO_RAIZ}: {kb:.0f} KB")
        total = 0.0
        for uf, p in sorted(pacotes.items()):
            total += grava(os.path.join(PASTA_MUN, f"{uf}.json"), p)
        print(f"  {PASTA_MUN}/: {len(pacotes)} arquivos, {total/1024:.1f} MB")
        kb = grava(DESTINO_INDICE, indice)
        print(f"  {DESTINO_INDICE}: {kb:.0f} KB")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
