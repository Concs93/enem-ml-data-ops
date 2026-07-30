"""
Exporta os dados do site a partir dos marts (Volume 9, Secao 3).

v1: o pacote da FACE DO ALUNO (motor.json) -- calibracao nota->theta, perfil
por nivel, distribuicao de acertos e a Matriz. Sao os marts pequenos; a
geografia entra na v2.

Regras da fronteira (as mesmas do pipeline):
- le SO de marts (nunca de camada interna);
- valida contagens contra o banco e FALHA ALTO antes de gravar parcial;
- grava atomico: escreve em .tmp e renomeia no fim.

Uso:
    python -m export.export_site            # grava webapp/dados/motor.json
"""

import json
import os
import sys

import psycopg2
from dotenv import load_dotenv

DESTINO = os.path.join("webapp", "dados", "motor.json")

# na chave composta, lingua nula vira "_" (JSON nao tem chave nula)
def k(*partes):
    return "|".join("_" if p is None else str(p) for p in partes)


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
    pacote = {"edicao": 2025, "areas": ["CH", "CN", "LC", "MT"]}

    # ---------------------------------------------------- calibracao
    # acertos_medio viaja como TERCEIRO elemento por causa do piso saturado:
    # as faixas 310-360 tem todas theta_efetivo = -3,00 (regiao de prova em
    # branco), entao a curva nota->acertos derivada do THETA e plana ali -- e
    # inverter curva plana foi o que produziu "+40 pontos" fantasma no site
    # (auditoria adversarial, 2026-07-27). A serie OBSERVADA e estritamente
    # crescente (4,11 -> 7,28 no piso de MT) e e o que o site deve inverter.
    cur.execute("""
        select area, cod_lingua, nota_faixa, theta_efetivo, n, acertos_medio,
               nota_minima_area,
               nota_maxima_area
        from marts.mart_calibracao_nota
    """)
    cal, minn, maxn = {}, {}, {}
    for area, lingua, faixa, theta, n, ac_medio, nmin, nmax in cur.fetchall():
        cal[k(area, lingua, faixa)] = [float(theta), int(n), float(ac_medio)]
        if nmin is not None:
            minn[k(area, lingua)] = float(nmin)
        if nmax is not None:
            maxn[k(area, lingua)] = float(nmax)
    pacote["calibracao"] = cal
    # os extremos FISICOS da escala por area: a curva calibravel comeca e
    # termina onde acaba a amostra (n >= 100 por faixa), mas notas fora dela
    # existem -- CH vai a 856,4 com a curva terminando em ~770. O site limita
    # o "ou mais" pelo maximo e RECUSA nota fora da faixa pelos dois
    pacote["minNota"] = minn
    pacote["maxNota"] = maxn

    # ------------------------------------------------------- perfil
    # so o necessario para a tela: hab, acerto esperado, informacao,
    # prioridade, n_itens -- ordenado por prioridade
    cur.execute("""
        select area, cod_lingua, theta, habilidade,
               acerto_esperado, informacao_total, prioridade, n_itens
        from marts.mart_perfil_habilidade
        order by area, cod_lingua, theta,
                 prioridade nulls last, habilidade
    """)
    perfil, info_area = {}, {}
    for area, lingua, theta, hab, esp, info, pri, n_itens in cur.fetchall():
        chave = k(area, lingua, theta)
        # esp e pri sao NULOS na habilidade nao mediavel (MT 21 na edicao;
        # LC 8 para quem fez ingles) -- o vazio declarado viaja como null,
        # e o site o mostra como "nao mediavel", nunca omite
        perfil.setdefault(chave, []).append([
            int(hab),
            float(esp) if esp is not None else None,
            round(float(info), 3),
            int(pri) if pri is not None else None,
            int(n_itens),
        ])
        info_area[chave] = round(info_area.get(chave, 0.0) + float(info), 3)
    pacote["perfil"] = perfil
    pacote["info_area"] = info_area

    # -------------------------------------------------- distribuicao
    # percentil acumulado por (area, lingua, faixa): arrays paralelos
    cur.execute("""
        select area, cod_lingua, nota_faixa, acertos, percentil_ate, n_faixa
        from marts.mart_distribuicao_acertos
        order by area, cod_lingua, nota_faixa, acertos
    """)
    dist = {}
    for area, lingua, faixa, acertos, pct, n_faixa in cur.fetchall():
        d = dist.setdefault(k(area, lingua, faixa),
                            {"acertos": [], "pct": [], "n": int(n_faixa)})
        d["acertos"].append(int(acertos))
        d["pct"].append(float(pct))
    pacote["distribuicao"] = dist

    # ------------------------------------------------- perfil de estudo
    # o banco de SEIS edicoes (2020-2025): "o que costuma render no seu
    # nivel", contra o perfil de 2025 que diz "o que rendia naquela prova".
    # Sao os dois cartoes do site -- perguntas diferentes, nao versoes
    cur.execute("""
        select area, cod_lingua, theta, habilidade,
               acerto_esperado, ganho_passo, prioridade,
               itens_por_prova, n_itens_banco
        from marts.mart_perfil_estudo
        order by area, cod_lingua, theta, prioridade nulls last, habilidade
    """)
    estudo = {}
    for area, lingua, theta, hab, esp, ganho, pri, ipp, nbanco in cur.fetchall():
        estudo.setdefault(k(area, lingua, theta), []).append([
            int(hab),
            float(esp) if esp is not None else None,
            round(float(ganho), 4),
            int(pri) if pri is not None else None,
            round(float(ipp), 2),
            int(nbanco),
        ])
    pacote["estudo"] = estudo

    # -------------------------------------------------------- provas
    # o caderno de cada prova regular (nivel 3): com ele o site corrige o
    # cartao do participante no proprio navegador. Parametros so viajam no
    # item valido -- o invalido aparece (posicao, gabarito) mas nao pontua
    cur.execute("""
        select co_prova, area, cor, posicao, cod_lingua, gabarito,
               habilidade, param_discriminacao, param_dificuldade,
               param_acerto_casual, item_valido, motivo_fora
        from marts.mart_item_prova
        order by co_prova, posicao
    """)
    provas = {}
    for cp, area, cor, pos, lin, gab, hab, pa, pb, pc, ok, fora in cur.fetchall():
        p = provas.setdefault(str(cp), {"area": area, "cor": cor, "itens": []})
        p["itens"].append([
            int(pos),
            int(lin) if lin is not None else None,
            gab,
            int(hab) if hab is not None else None,
            float(pa) if ok and pa is not None else None,
            float(pb) if ok and pb is not None else None,
            float(pc) if ok and pc is not None else None,
            fora,   # null quando vale ponto; 'anulada' ou 'sem_calibracao'
        ])
    pacote["provas"] = provas

    # ------------------------------------------------------- matriz
    cur.execute("""
        select area, habilidade, competencia,
               descricao_habilidade, descricao_competencia
        from staging.matriz_referencia
    """)
    matriz = {}
    for area, hab, comp, dhab, dcomp in cur.fetchall():
        matriz[k(area, hab)] = {"comp": int(comp), "hab": dhab, "compdesc": dcomp}
    pacote["matriz"] = matriz

    return pacote


def valida(cur, pacote):
    """Conservacao contra o banco. Um pacote parcial no ar e um site que
    mente com confianca -- melhor nao gravar."""
    erros = []

    cur.execute("select count(*) from marts.mart_calibracao_nota")
    if len(pacote["calibracao"]) != cur.fetchone()[0]:
        erros.append("calibracao: contagem nao bate com o mart")

    # o acertos_medio e a serie que o site INVERTE; quase-monotonia e o que
    # torna a inversao bem definida. Pequenas oscilacoes nas faixas raras do
    # topo sao toleradas (o site colapsa segmentos degenerados), mas inversao
    # em massa seria dado quebrado
    quebras = 0
    grupos = {}
    for chave, (theta, n, ac) in pacote["calibracao"].items():
        area, lingua, faixa = chave.rsplit("|", 2)
        grupos.setdefault((area, lingua), []).append((int(faixa), ac))
    for serie in grupos.values():
        serie.sort()
        quebras += sum(1 for i in range(1, len(serie))
                       if serie[i][1] <= serie[i-1][1])
    if quebras > 5:
        erros.append(f"calibracao: acertos_medio com {quebras} inversoes de "
                     f"monotonia - a curva do site nao teria inversa")
    elif quebras:
        print(f"  aviso: acertos_medio com {quebras} oscilacao(oes) local(is) "
              f"- o site colapsa esses segmentos")

    # o teto fisico precisa existir para os 5 grupos e nunca ficar ABAIXO da
    # ultima faixa calibravel -- senao o cap cortaria a propria curva
    ultimas = {}
    primeiras = {}
    for chave, (theta, n, ac) in pacote["calibracao"].items():
        area, lingua, faixa = chave.rsplit("|", 2)
        kk = f"{area}|{lingua}"
        ultimas[kk] = max(ultimas.get(kk, 0), int(faixa))
        primeiras[kk] = min(primeiras.get(kk, 9999), int(faixa))
    for kk, topo in ultimas.items():
        nmax = pacote["maxNota"].get(kk)
        if nmax is None:
            erros.append(f"maxNota: falta o teto da escala para {kk}")
        elif nmax < topo:
            erros.append(f"maxNota: teto {nmax} abaixo da ultima faixa "
                         f"calibravel ({topo}) em {kk}")
    # o piso tem de existir, ficar ACIMA de zero (senao o sentinela de prova em
    # branco vazou) e nao pode estar acima da primeira faixa calibravel -- se
    # estiver, a faixa aceita cortaria gente que a propria curva atende
    for kk, base in primeiras.items():
        nmin = pacote["minNota"].get(kk)
        if nmin is None:
            erros.append(f"minNota: falta o piso da escala para {kk}")
        elif nmin <= 0:
            erros.append(f"minNota: piso {nmin} em {kk} -- o zero e sentinela "
                         f"de prova em branco e nao pode entrar")
        elif nmin > base + 10:
            erros.append(f"minNota: piso {nmin} acima da primeira faixa "
                         f"calibravel ({base}) em {kk}")

    cur.execute("""
        select count(distinct (area, cod_lingua, theta))
        from marts.mart_perfil_habilidade
    """)
    if len(pacote["perfil"]) != cur.fetchone()[0]:
        erros.append("perfil: numero de chaves (area,lingua,theta) nao bate")

    # todo nivel do perfil lista todas as habilidades da area (30)
    ruins = [c for c, habs in pacote["perfil"].items() if len(habs) != 30]
    if ruins:
        erros.append(f"perfil: {len(ruins)} chaves sem as 30 habilidades "
                     f"(ex.: {ruins[:3]})")

    # o perfil de estudo tem o MESMO grao do de 2025: as duas listas precisam
    # cobrir os mesmos niveis, senao um cartao aparece e o outro some
    if set(pacote["estudo"]) != set(pacote["perfil"]):
        so_um = set(pacote["perfil"]) ^ set(pacote["estudo"])
        erros.append(f"estudo x perfil: {len(so_um)} chaves em so um dos dois "
                     f"(ex.: {sorted(so_um)[:3]})")
    ruins = [c for c, habs in pacote["estudo"].items() if len(habs) != 30]
    if ruins:
        erros.append(f"estudo: {len(ruins)} chaves sem as 30 habilidades")
    # a escala de uma prova: itens_por_prova soma 45 (tolerancia do
    # arredondamento em 2 casas sobre 30 valores)
    tortos = [c for c, habs in pacote["estudo"].items()
              if abs(sum(h[4] for h in habs) - 45) > 0.25]
    if tortos:
        erros.append(f"estudo: {len(tortos)} chaves fora da escala de uma "
                     f"prova (itens_por_prova nao soma 45)")

    if len(pacote["matriz"]) != 120:
        erros.append(f"matriz: {len(pacote['matriz'])} entradas, esperado 120")

    # 16 cadernos regulares, inteiros, com os validos exatos da edicao
    # (CH 45, CN 42, LC 50, MT 43 -- os cinco nao avaliaveis)
    esperado_prova = {"CH": (45, 45), "CN": (45, 42),
                      "LC": (50, 50), "MT": (45, 43)}
    if len(pacote["provas"]) != 16:
        erros.append(f"provas: {len(pacote['provas'])} cadernos, esperado 16")
    for cp, p in pacote["provas"].items():
        q_esp, v_esp = esperado_prova[p["area"]]
        validos = sum(1 for it in p["itens"] if it[4] is not None)
        if len(p["itens"]) != q_esp or validos != v_esp:
            erros.append(f"provas: caderno {cp} ({p['area']}) tem "
                         f"{len(p['itens'])} questoes / {validos} validas, "
                         f"esperado {q_esp} / {v_esp}")

    # percentil acumulado termina em 100 em toda faixa
    tortas = [c for c, d in pacote["distribuicao"].items()
              if abs(d["pct"][-1] - 100.0) > 0.01]
    if tortas:
        erros.append(f"distribuicao: {len(tortas)} faixas nao acumulam 100%")

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
        print(f"  ok: calibracao {len(pacote['calibracao'])} | "
              f"perfil {len(pacote['perfil'])} chaves | "
              f"estudo {len(pacote['estudo'])} chaves | "
              f"distribuicao {len(pacote['distribuicao'])} faixas | "
              f"matriz {len(pacote['matriz'])} | "
              f"provas {len(pacote['provas'])} cadernos")

        print("3. Gravando")
        os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
        tmp = DESTINO + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(pacote, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, DESTINO)
        mb = os.path.getsize(DESTINO) / 1048576
        print(f"  {DESTINO}: {mb:.1f} MB")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
