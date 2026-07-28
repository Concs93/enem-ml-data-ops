"""
Gera o seed que classifica CADA versao de prova de CADA edicao do banco.

Por que existe: o `ITENS_PROVA` traz o `TX_COR` -- so a cor ("AZUL"), sem o
qualificador. O que distingue prova regular de reaplicacao, acessibilidade e
BAM e o ROTULO do CO_PROVA, que mora no dicionario da edicao (e nos scripts
INPUT_R que o INEP publica junto). Sem esse rotulo, o banco de itens multi-
edicao mistura as quatro aplicacoes sem saber.

O seed `co_prova.csv` ja resolvia isso -- so para 2025. Este script estende a
mesma regra as seis edicoes, baixando de cada ZIP APENAS o script do R
(~20 KB de um pacote de 500 MB), pelo mesmo truque de range do baixa_itens.py.

A regra de classificacao e a mesma e vem de build_seeds.py (classifica_prova):
e regular quando o rotulo e so o nome da cor, sem qualificador. Nao ha
transcricao aqui -- se o INEP mudar a nomenclatura, o script erra alto em vez
de gravar um seed plausivel e errado.

CO_PROVA e unico entre edicoes (2020: 567-699 ... 2025: 1447-1573, zero
sobreposicao -- verificado), entao o seed nao precisa de chave composta; a
coluna `edicao` fica para leitura e teste.

Uso:
    python -m ingestion.build_co_prova_banco
    python -m ingestion.build_co_prova_banco --anos 2024 2025
"""

import argparse
import csv
import os
import re
import sys

from ingestion.baixa_itens import pesca
from ingestion.build_seeds import _extrai_c, _split_args, classifica_prova
from ingestion.config import EDICOES_ITENS

DESTINO = os.path.join("dbt", "seeds", "co_prova_banco.csv")

# O script do R que traz os niveis e rotulos de CO_PROVA_CN/CH/LC/MT. Ate 2023
# ha um arquivo unico (INPUT_R_MICRODADOS_ENEM_AAAA.R); de 2024 em diante o
# INEP separou em RESULTADOS e PARTICIPANTES, e as colunas CO_PROVA_* ficam no
# de RESULTADOS. O de ITENS_PROVA nunca serve.
#
# Nomear o arquivo certo por exclusao (nao e ITENS_PROVA, nao e PARTICIPANTES)
# em vez de fixar o nome: a nomenclatura ja mudou uma vez e vai mudar de novo.
def _e_o_script_certo(nome):
    n = os.path.basename(nome).upper()
    return (n.endswith(".R")
            and "INPUT_R" in n
            and "ITENS_PROVA" not in n
            and "PARTICIPANTES" not in n)


def provas_da_edicao(ano):
    """Devolve [(edicao, co_prova, area, cor, rotulo, tipo, is_regular)]."""
    txt = pesca(ano, _e_o_script_certo, rotulo="script do R").decode(
        "latin-1", "replace").replace("\r", "")

    # O script inteiro vem COMENTADO, e quando um `labels = c(...)` quebra de
    # linha o `#` fica no meio da expressao -- em 2022 isso fazia a busca por
    # "labels" pular para a variavel seguinte e devolver os rotulos de
    # TP_LINGUA ('Ingles','Espanhol') no lugar das cores. Tirar o marcador
    # antes de qualquer parse e a mesma solucao do build_seeds.
    txt = "\n".join(re.sub(r"^\s*#", "", ln) for ln in txt.splitlines())

    # E delimitar o bloco contando parenteses, em vez de uma janela de N
    # caracteres: o bloco de uma variavel acaba onde o factor( fecha
    blocos = {}
    for m in re.finditer(r"\$([A-Z0-9_]+)\s*<-\s*factor\(", txt):
        i, prof = m.end(), 1
        while i < len(txt) and prof:
            if txt[i] == "(":
                prof += 1
            elif txt[i] == ")":
                prof -= 1
            i += 1
        blocos[m.group(1)] = txt[m.end(): i - 1]

    linhas = []
    for area in ("CN", "CH", "LC", "MT"):
        var = f"CO_PROVA_{area}"
        corpo = blocos.get(var)
        if corpo is None:
            continue
        niveis = _extrai_c(corpo, "levels")
        rotulos = _extrai_c(corpo, "labels")
        if not (niveis and rotulos):
            continue
        niveis, rotulos = _split_args(niveis), _split_args(rotulos)
        if len(niveis) != len(rotulos):
            raise RuntimeError(
                f"{ano}/{var}: {len(niveis)} niveis para {len(rotulos)} "
                f"rotulos - o layout do script mudou")
        for cod, rot in zip(niveis, rotulos):
            if not str(cod).strip().isdigit():
                continue
            tipo = classifica_prova(rot)
            cor = rot.split(" - ")[0].split(" (")[0].strip()
            linhas.append([ano, int(cod), area, cor, rot, tipo,
                           "true" if tipo == "regular" else "false"])
    return linhas


def valida(linhas, anos):
    """Falha alto. Um seed que classifica errado faz o banco de itens misturar
    reaplicacao com regular -- e o erro nao aparece em contagem nenhuma."""
    erros = []
    por_ano = {}
    for l in linhas:
        por_ano.setdefault(l[0], []).append(l)

    for ano, ls in sorted(por_ano.items()):
        regulares = [l for l in ls if l[6] == "true"]
        # 4 areas x 4 cores = 16 provas regulares, o padrao desde 2009
        if len(regulares) != 16:
            erros.append(f"{ano}: {len(regulares)} provas regulares, "
                         f"esperado 16 (4 areas x 4 cores)")
        por_area = {}
        for l in regulares:
            por_area[l[2]] = por_area.get(l[2], 0) + 1
        ruins = {a: n for a, n in por_area.items() if n != 4}
        if ruins:
            erros.append(f"{ano}: areas com numero errado de cores regulares: {ruins}")
        tipos = {l[5] for l in ls}
        if tipos == {"regular"}:
            erros.append(f"{ano}: TODAS as provas vieram como regular - a "
                         f"regra de classificacao nao casou com os rotulos")

    faltando = set(anos) - set(por_ano)
    if faltando:
        erros.append(f"edicoes sem nenhuma prova: {sorted(faltando)}")

    # CO_PROVA precisa ser unico entre edicoes -- o join do banco depende disso
    vistos = {}
    for l in linhas:
        if l[1] in vistos and vistos[l[1]] != l[0]:
            erros.append(f"co_prova {l[1]} aparece em {vistos[l[1]]} e {l[0]}")
        vistos[l[1]] = l[0]

    return erros


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anos", nargs="+", type=int, default=EDICOES_ITENS)
    args = ap.parse_args()

    todas = []
    for ano in args.anos:
        print(f"\n=== ENEM {ano} ===")
        try:
            ls = provas_da_edicao(ano)
        except Exception as ex:
            print(f"  ! {type(ex).__name__}: {ex}")
            continue
        reg = sum(1 for l in ls if l[6] == "true")
        print(f"  {len(ls)} versoes de prova, {reg} regulares")
        todas += ls

    print("\nValidacao")
    erros = valida(todas, args.anos)
    if erros:
        print("FALHA - o seed NAO foi gravado:")
        for e in erros:
            print(f"  ! {e}")
        sys.exit(1)
    print("  ok: 16 provas regulares por edicao, co_prova unico entre edicoes")

    todas.sort(key=lambda l: (l[0], l[2], l[1]))
    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    with open(DESTINO, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["edicao", "co_prova", "sg_area", "cor", "rotulo",
                    "tipo_aplicacao", "is_regular"])
        w.writerows(todas)
    print(f"\n  gravado {DESTINO} ({len(todas)} linhas)")

    print("\nResumo por tipo de aplicacao")
    tipos = {}
    for l in todas:
        tipos[l[5]] = tipos.get(l[5], 0) + 1
    for t, n in sorted(tipos.items(), key=lambda x: -x[1]):
        print(f"  {t:16} {n}")


if __name__ == "__main__":
    main()
