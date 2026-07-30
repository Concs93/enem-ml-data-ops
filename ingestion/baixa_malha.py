"""Baixa a malha territorial do IBGE para o mapa da face do gestor.

Uma varredura, um arquivo. A malha e geometria estavel -- nao muda com a
edicao do ENEM --, entao ela e baixada uma vez e versionada junto do site.

QUALIDADE "MINIMA" de proposito. O IBGE oferece minima, intermediaria e
maxima; para um mapa do pais renderizado em ~700px, a intermediaria (251 KB)
gasta 2,5x mais bytes para desenhar detalhe abaixo de um pixel. A minima
(98 KB) ja passa do necessario, e o arredondamento abaixo corta mais um terco.

Uso:
    python -m ingestion.baixa_malha            # grava webapp/dados/malha_uf.json
"""
from __future__ import annotations

import gzip
import json
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "webapp" / "dados" / "malha_uf.json"

URL = ("https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
       "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF")

# 27 unidades da federacao: 26 estados + DF. Numero fechado -- se vier outro,
# a API mudou de contrato e e melhor parar do que gravar um mapa incompleto
UFS_ESPERADAS = 27

# 2 casas decimais ~ 1,1 km no equador. Num mapa do Brasil inteiro em 700px,
# um pixel vale ~6 km -- a terceira casa desenha detalhe que nao existe na tela
CASAS = 2


def arredonda(geom):
    """Corta as casas decimais preservando a estrutura (Polygon/MultiPolygon)."""
    def anel(coords):
        saida, ant = [], None
        for x, y in coords:
            p = [round(x, CASAS), round(y, CASAS)]
            if p != ant:                 # colapsa pontos que viraram o mesmo
                saida.append(p)
                ant = p
        # um anel precisa fechar e ter area; se o arredondamento o degenerou,
        # devolve o original em vez de gravar geometria invalida
        if len(saida) < 4:
            return [[round(x, CASAS + 2), round(y, CASAS + 2)] for x, y in coords]
        if saida[0] != saida[-1]:
            saida.append(saida[0])
        return saida

    if geom["type"] == "Polygon":
        geom["coordinates"] = [anel(r) for r in geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        geom["coordinates"] = [[anel(r) for r in poly] for poly in geom["coordinates"]]
    else:
        raise SystemExit(f"geometria inesperada: {geom['type']}")
    return geom


def pontos(geom):
    if geom["type"] == "Polygon":
        return sum(len(r) for r in geom["coordinates"])
    return sum(len(r) for poly in geom["coordinates"] for r in poly)


def main():
    print("1. Baixando a malha do IBGE")
    # o servico responde gzip mesmo sem Accept-Encoding; urllib nao descomprime
    req = urllib.request.Request(URL, headers={"Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=180) as r:
        corpo = r.read()
    if corpo[:2] == b"\x1f\x8b":
        corpo = gzip.decompress(corpo)
    bruto = json.loads(corpo.decode("utf-8"))

    feicoes = bruto.get("features", [])
    if len(feicoes) != UFS_ESPERADAS:
        raise SystemExit(f"  ERRO: {len(feicoes)} feicoes, esperadas {UFS_ESPERADAS}")

    antes = sum(pontos(f["geometry"]) for f in feicoes)

    print("2. Enxugando")
    saida = {"type": "FeatureCollection", "features": []}
    codigos = set()
    for f in feicoes:
        cod = f.get("properties", {}).get("codarea")
        if not cod or not str(cod).isdigit():
            raise SystemExit(f"  ERRO: feicao sem codarea utilizavel: {f.get('properties')}")
        codigos.add(int(cod))
        saida["features"].append({
            "type": "Feature",
            # so o codigo viaja: o nome vem do mart, que e a fonte do projeto
            "properties": {"uf": int(cod)},
            "geometry": arredonda(f["geometry"]),
        })

    if len(codigos) != UFS_ESPERADAS:
        raise SystemExit(f"  ERRO: {len(codigos)} codigos distintos")
    # os codigos de UF do IBGE vao de 11 (RO) a 53 (DF)
    if min(codigos) < 11 or max(codigos) > 53:
        raise SystemExit(f"  ERRO: codigo de UF fora da faixa: {min(codigos)}-{max(codigos)}")

    depois = sum(pontos(f["geometry"]) for f in saida["features"])

    print("3. Gravando")
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    tmp = SAIDA.with_suffix(".tmp")
    tmp.write_text(json.dumps(saida, separators=(",", ":")), encoding="utf-8")
    tmp.replace(SAIDA)
    kb = SAIDA.stat().st_size / 1024
    print(f"  {SAIDA.relative_to(RAIZ)}: {kb:.0f} KB · {len(codigos)} UFs · "
          f"{antes:,} -> {depois:,} pontos")


if __name__ == "__main__":
    sys.exit(main())
