"""Baixa a malha MUNICIPAL do IBGE, um arquivo por UF, para o mapa da face
do gestor no nivel de cidade.

Por que 27 arquivos e nao um: a malha municipal inteira tem ~2,6 MB e a tela
so precisa dos municipios do estado em que a pessoa entrou. Um arquivo por UF
(~30-160 KB) desce ao clicar, e o mapa nacional continua leve.

TRES casas decimais aqui (~110 m), contra duas na malha de UFs: municipio
pequeno tem ~5 km de largura, e a 0,01 grau o poligono degenera. No zoom de
um estado (~5 graus em ~600 px), 0,001 grau fica abaixo de um pixel -- e o
suficiente sem ser gordura.

Uso:
    python -m ingestion.baixa_malha_municipios     # webapp/dados/malha_mun/{uf}.json
"""
from __future__ import annotations

import gzip
import json
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "webapp" / "dados" / "malha_mun"

URL = ("https://servicodados.ibge.gov.br/api/v3/malhas/estados/{uf}"
       "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio")

# codigos oficiais das 27 UFs (faixa 11-53 do IBGE)
UFS = [11, 12, 13, 14, 15, 16, 17,
       21, 22, 23, 24, 25, 26, 27, 28, 29,
       31, 32, 33, 35,
       41, 42, 43,
       50, 51, 52, 53]

CASAS = 3


def arredonda(geom):
    """Corta casas decimais preservando a estrutura (Polygon/MultiPolygon)."""
    def anel(coords):
        saida, ant = [], None
        for x, y in coords:
            p = [round(x, CASAS), round(y, CASAS)]
            if p != ant:
                saida.append(p)
                ant = p
        # anel degenerado pelo arredondamento: volta a precisao original
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


def baixa(uf: int) -> dict:
    req = urllib.request.Request(URL.format(uf=uf),
                                 headers={"Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=180) as r:
        corpo = r.read()
    if corpo[:2] == b"\x1f\x8b":
        corpo = gzip.decompress(corpo)
    return json.loads(corpo.decode("utf-8"))


def main():
    PASTA.mkdir(parents=True, exist_ok=True)
    total_kb, total_mun = 0.0, 0
    print(f"Baixando a malha municipal de {len(UFS)} UFs")
    for uf in UFS:
        bruto = baixa(uf)
        feicoes = bruto.get("features", [])
        # piso por UF: o DF e UM municipio (Brasilia) -- um piso generico de
        # "15" derrubou o script exatamente nele. Fora o DF, a menor UF e
        # Roraima com 15; menos que isso e resposta truncada
        piso = 1 if uf == 53 else 15
        if len(feicoes) < piso:
            raise SystemExit(f"  ERRO: UF {uf} com {len(feicoes)} municipios")

        saida = {"type": "FeatureCollection", "features": []}
        for f in feicoes:
            cod = str(f.get("properties", {}).get("codarea", ""))
            if len(cod) != 7 or not cod.startswith(str(uf)):
                raise SystemExit(f"  ERRO: UF {uf} com codarea estranho: {cod!r}")
            saida["features"].append({
                "type": "Feature",
                "properties": {"m": int(cod)},
                "geometry": arredonda(f["geometry"]),
            })

        destino = PASTA / f"{uf}.json"
        tmp = destino.with_suffix(".tmp")
        tmp.write_text(json.dumps(saida, separators=(",", ":")), encoding="utf-8")
        tmp.replace(destino)
        kb = destino.stat().st_size / 1024
        total_kb += kb
        total_mun += len(feicoes)
        print(f"  UF {uf}: {len(feicoes):4d} municipios · {kb:6.0f} KB")
        time.sleep(0.4)          # cortesia com a API publica

    print(f"\n{total_mun} municipios em {total_kb/1024:.1f} MB "
          f"({total_kb/len(UFS):.0f} KB por UF, na media)")
    # o total do IBGE e 5.570-5.572 conforme a vintage da malha; menos de
    # 5.500 significa UF truncada que passou pelo piso individual
    if total_mun < 5500:
        raise SystemExit(f"ERRO: total de municipios baixo demais ({total_mun})")


if __name__ == "__main__":
    sys.exit(main())
