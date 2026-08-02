"""
Exporta o pacote da FACE DO GESTOR: Brasil e as 27 UFs, por competencia e
por rede. UMA SAIDA -- webapp/dados/geografia.json.

SIMPLES POR DECISAO (02/08/2026): municipio, regiao imediata e o relatorio
por escola sairam do produto. O grao fino convida ao uso que fez o INEP
descontinuar o "ENEM por Escola"; a analise vive bem por estado e
competencia. O co_municipio segue como grao de COMPUTO nos marts.

O DESENHO FINAL (02/08/2026, segunda rodada do "simple is best"): a tela
faz UMA pergunta -- quantos pontos a media subiria se a rede acertasse,
onde esta atras, o que o Brasil da mesma rede acerta -- repartidos por
competencia (as partes somam o total). A taxa viaja como recibo; n_respostas
sustenta a guarda de margem; `esc` separa "nao tem escola da rede" de
"abaixo do minimo". Perfil e TRI sairam do pacote junto com o mapa
tematico: o mapa agora e so o seletor de estados.

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


def aplica_pts(dados_cel, ctx_cel, ganhos_cel, curvas):
    """Anexa a parte de cada competencia as linhas e devolve o total da
    celula. A MESMA conta para pais, estado e cidade: passo integrado sobre
    a distribuicao real, curva acertos->nota, particao por resto maior."""
    pts = {}
    for ch, linhas in dados_cel.items():
        ar = ch.split("|")[-2]
        ctx = ctx_cel.get(ch)
        ganho_cel = ganhos_cel.get(ch)
        if not ctx or not ctx[0] or not ganho_cel:
            continue
        presentes = ctx[0]
        q_aluno = {l[0]: l[2] / presentes for l in linhas}
        atual = sum(l[1] / 100 * q_aluno[l[0]] for l in linhas)
        delta = {l[0]: max(0.0, ganho_cel.get(l[0], 0.0)) for l in linhas}
        total_delta = sum(delta.values())
        curva = curvas[ar]
        total_pts = (nota_de_acertos(curva, atual + total_delta)
                     - nota_de_acertos(curva, atual)) if total_delta > 1e-9 else 0.0
        total_int = round(total_pts)
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
        pts[ch] = total_int
    return pts


def exporta(cur):
    pacote = {"edicao": 2025, "areas": sorted(COMP_POR_AREA)}

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
    ctx = {}
    for cod, ar, rede, n, esc, media in cur.fetchall():
        ctx[k(cod, ar, rede)] = [int(n), int(esc), round(float(media))]
    pacote["ctx"] = ctx

    # n_escolas das celulas que existem mas NAO publicam (so cadastral)
    cur.execute("""
        select codigo, area, rede, n_escolas
        from marts.mart_geografia_area
        where not publicavel and nivel in ('pais', 'uf')
    """)
    pacote["esc"] = {k(c, a, r): int(n) for c, a, r, n in cur.fetchall()}

    # [comp, taxa (1 casa -- o recibo), n_respostas (a margem)] + pts no fim
    cur.execute("""
        select codigo, area, rede, competencia, taxa_acerto, n_respostas
        from marts.mart_geografia_competencia
        where publicavel and status = 'ok' and nivel in ('pais', 'uf')
        order by codigo, area, rede, competencia
    """)
    dados = defaultdict(list)
    for cod, ar, rede, comp, taxa, n in cur.fetchall():
        dados[k(cod, ar, rede)].append(
            [int(comp), round(float(taxa), 1), int(n)])
    pacote["dados"] = dict(dados)

    # --------------- pontos na media: o POTENCIAL de um passo de avanco
    # (cenario da face do aluno; ver aplica_pts). Os ganhos por celula saem
    # do join pesos x referencia -- estado E cidade pela mesma conta.
    cur.execute("""
        select coalesce(w.co_uf, 0) as co_uf, w.rede, w.area, r.competencia,
               sum(w.n * r.ganho) / sum(w.n) as ganho
        from staging.int_uf_nivel w
        join staging.int_estudo_referencia r
          on r.area = w.area
         and r.cod_lingua = w.cod_lingua
         and r.theta = w.theta
        group by grouping sets ((w.co_uf, w.rede, w.area, r.competencia),
                                (w.rede, w.area, r.competencia))
    """)
    ganhos = defaultdict(dict)
    for cod, rede, ar, comp, g in cur.fetchall():
        ganhos[k(cod, ar, rede)][int(comp)] = float(g)

    curvas = curva_acertos_nota(cur)
    pacote["pts"] = aplica_pts(pacote["dados"], pacote["ctx"], ganhos, curvas)

    # ---------------- municipios (voltaram em 02/08 com a moeda do passo):
    # mesmos dados, mesmo calculo, empacotados POR UF -- o navegador baixa
    # so o estado aberto. Cidade entra por busca; sem malha municipal.
    cur.execute("""
        select codigo, area, rede, n_presentes, n_escolas, media_nota
        from marts.mart_geografia_area
        where publicavel and nivel = 'municipio'
    """)
    mun_ctx = defaultdict(dict)
    for cod, ar, rede, n, esc, media in cur.fetchall():
        mun_ctx[cod][k(ar, rede)] = [int(n), int(esc), round(float(media))]

    cur.execute("""
        select codigo, area, rede, n_escolas
        from marts.mart_geografia_area
        where not publicavel and nivel = 'municipio'
    """)
    mun_esc = defaultdict(dict)
    for cod, ar, rede, n in cur.fetchall():
        mun_esc[cod][k(ar, rede)] = int(n)

    cur.execute("""
        select codigo, area, rede, competencia, taxa_acerto, n_respostas
        from marts.mart_geografia_competencia
        where publicavel and status = 'ok' and nivel = 'municipio'
        order by codigo, area, rede, competencia
    """)
    mun_dados = defaultdict(lambda: defaultdict(list))
    for cod, ar, rede, comp, taxa, n in cur.fetchall():
        mun_dados[cod][k(ar, rede)].append(
            [int(comp), round(float(taxa), 1), int(n)])

    cur.execute("""
        select w.co_municipio, w.rede, w.area, r.competencia,
               sum(w.n * r.ganho) / sum(w.n) as ganho
        from staging.int_municipio_nivel w
        join staging.int_estudo_referencia r
          on r.area = w.area
         and r.cod_lingua = w.cod_lingua
         and r.theta = w.theta
        group by 1, 2, 3, 4
    """)
    mun_ganhos = defaultdict(lambda: defaultdict(dict))
    for cod, rede, ar, comp, g in cur.fetchall():
        mun_ganhos[cod][k(ar, rede)][int(comp)] = float(g)

    cur.execute("""
        select distinct codigo, nome from marts.mart_geografia_area
        where nivel = 'municipio'
    """)
    nomes = dict(cur.fetchall())

    pacotes = {}
    indice = []
    for cod, nome in nomes.items():
        uf = cod // 100000
        sigla = pacote["ufs"].get(str(uf), ["?"])[0]
        pub = 1 if cod in mun_ctx else 0
        indice.append([cod, nome, sigla, pub])
        pk = pacotes.setdefault(uf, {"uf": uf, "mun": {}})
        entrada = {"nome": nome}
        if pub:
            entrada["ctx"] = mun_ctx[cod]
            entrada["dados"] = mun_dados[cod]
            entrada["pts"] = aplica_pts(mun_dados[cod], mun_ctx[cod],
                                        mun_ganhos[cod], curvas)
        if cod in mun_esc:
            entrada["esc"] = mun_esc[cod]
        pk["mun"][str(cod)] = entrada
    indice.sort(key=lambda l: l[1])
    pacote["_pacotes"] = pacotes
    pacote["_indice"] = indice

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

    # municipios: toda celula publicavel completa, com pts e partes somando
    for uf, pk in pacote["_pacotes"].items():
        for cod, m in pk["mun"].items():
            if "dados" not in m:
                continue
            for ch, linhas in m["dados"].items():
                ar = ch.split("|")[0]
                if len(linhas) != COMP_POR_AREA[ar]:
                    erros.append(f"mun {cod}: {ch} incompleta")
                    break
                if ch not in m["pts"]:
                    erros.append(f"mun {cod}: {ch} sem potencial")
                    break
                soma = sum(l[3] for l in linhas if len(l) > 3)
                if soma != m["pts"][ch]:
                    erros.append(f"mun {cod}: partes {soma} != {m['pts'][ch]} em {ch}")
                    break
            else:
                continue
            break

    # toda celula publicavel tem o potencial calculado -- celula sem pts e
    # painel sem resposta em silencio
    sem = [ch for ch in pacote["ctx"] if ch not in pacote["pts"]]
    if sem:
        erros.append(f"pts: {len(sem)} celulas publicaveis sem potencial "
                     f"(ex.: {sorted(sem)[:3]})")

    # as partes dos pontos somam o total (a conferencia que o leitor faz)
    for ch, total in pacote["pts"].items():
        soma = sum(l[3] for l in pacote["dados"][ch] if len(l) > 3)
        if soma != total:
            erros.append(f"pts: partes somam {soma} != total {total} em {ch}")
        if total < 0:
            erros.append(f"pts: total negativo em {ch}")

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
        pacotes = pacote.pop("_pacotes")
        indice = pacote.pop("_indice")
        os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
        tmp = DESTINO + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(pacote, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, DESTINO)
        print(f"  {DESTINO}: {os.path.getsize(DESTINO)/1024:.0f} KB")

        pasta = os.path.join("webapp", "dados", "geo_mun")
        os.makedirs(pasta, exist_ok=True)
        total = 0
        for uf, pk in sorted(pacotes.items()):
            caminho = os.path.join(pasta, f"{uf}.json")
            with open(caminho + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(pk, fh, ensure_ascii=False, separators=(",", ":"))
            os.replace(caminho + ".tmp", caminho)
            total += os.path.getsize(caminho)
        print(f"  {pasta}/: {len(pacotes)} arquivos, {total/1024:.0f} KB")

        caminho = os.path.join("webapp", "dados", "municipios_indice.json")
        with open(caminho + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(indice, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(caminho + ".tmp", caminho)
        print(f"  {caminho}: {os.path.getsize(caminho)/1024:.0f} KB")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
