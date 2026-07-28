"""
Baixa APENAS o arquivo ITENS_PROVA de cada edicao do ENEM, sem puxar o ZIP
inteiro.

Por que isto existe: os microdados de cada edicao vem num ZIP de 500-620 MB,
mas o ITENS_PROVA e um CSV de ~350 KB -- o resto e RESULTADOS e PARTICIPANTES,
que nao usamos para o motor psicometrico. Baixar 2,5 GB para extrair 1,7 MB
seria desperdicio de banda (e a maquina daqui tem upload ruim e disco curto).

Como: o servidor do INEP responde `Accept-Ranges: bytes`. Entao lemos o fim do
ZIP (diretorio central), localizamos a entrada do ITENS_PROVA, e pedimos por
range so os bytes dela. Custo tipico: ~200 KB por edicao em vez de ~550 MB.

Os parametros de TRI (NU_PARAM_A/B/C) so passaram a ser publicados a partir do
ENEM 2020 -- antes disso o ITENS_PROVA existe mas nao serve para o motor. O
script confere isso no cabecalho e avisa alto quando faltarem.

Uso:
    python -m ingestion.baixa_itens                 # 2020..2024
    python -m ingestion.baixa_itens --anos 2023 2024
"""

import argparse
import io
import os
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib

URL = "https://download.inep.gov.br/microdados/microdados_enem_{ano}.zip"
DESTINO = os.path.join("data", "raw")

# colunas que o motor psicometrico exige; sem elas a edicao nao serve
PARAMS = ["NU_PARAM_A", "NU_PARAM_B", "NU_PARAM_C"]

EOCD_SIG = b"PK\x05\x06"
CD_SIG = b"PK\x01\x02"


def _tenta(fn, tentativas=4):
    """O servidor do INEP derruba conexao quando recebe varias seguidas.
    Como cada arquivo exige 3 requisicoes (cauda, diretorio, dados), sem
    repeticao o script falha no meio e deixa edicao de fora -- que e
    exatamente o tipo de buraco silencioso que este projeto persegue."""
    for i in range(tentativas):
        try:
            return fn()
        except (urllib.error.URLError, ConnectionError, TimeoutError) as ex:
            if i == tentativas - 1:
                raise
            espera = 2 ** i
            print(f"    (rede: {type(ex).__name__}; nova tentativa em {espera}s)")
            time.sleep(espera)


def pega(url, inicio=None, fim=None, timeout=120):
    def _ir():
        req = urllib.request.Request(url, headers={"User-Agent": "enem-ml-data-ops"})
        if inicio is not None:
            req.add_header("Range", f"bytes={inicio}-{'' if fim is None else fim}")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), r.status, dict(r.headers)
    return _tenta(_ir)


def tamanho(url):
    def _ir():
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "enem-ml-data-ops"})
        with urllib.request.urlopen(req, timeout=60) as r:
            if r.headers.get("Accept-Ranges", "").lower() != "bytes":
                raise RuntimeError("servidor nao aceita range; abortando para "
                                   "nao baixar o ZIP inteiro")
            return int(r.headers["Content-Length"])
    return _tenta(_ir)


def entradas_do_zip(url, total):
    """Le o diretorio central pelo fim do arquivo e devolve as entradas."""
    cauda = min(70 * 1024, total)
    dados, _, _ = pega(url, total - cauda, total - 1)

    pos = dados.rfind(EOCD_SIG)
    if pos < 0:
        raise RuntimeError("nao achei o fim do diretorio central (ZIP64?)")
    n_entradas, cd_tam, cd_off = struct.unpack("<H", dados[pos+10:pos+12])[0], \
        struct.unpack("<I", dados[pos+12:pos+16])[0], \
        struct.unpack("<I", dados[pos+16:pos+20])[0]

    cd, _, _ = pega(url, cd_off, cd_off + cd_tam - 1)
    saida, i = [], 0
    for _ in range(n_entradas):
        if cd[i:i+4] != CD_SIG:
            break
        metodo   = struct.unpack("<H", cd[i+10:i+12])[0]
        comp     = struct.unpack("<I", cd[i+20:i+24])[0]
        bruto    = struct.unpack("<I", cd[i+24:i+28])[0]
        n_nome   = struct.unpack("<H", cd[i+28:i+30])[0]
        n_extra  = struct.unpack("<H", cd[i+30:i+32])[0]
        n_coment = struct.unpack("<H", cd[i+32:i+34])[0]
        offset   = struct.unpack("<I", cd[i+42:i+46])[0]
        nome     = cd[i+46:i+46+n_nome].decode("cp437", "replace")
        saida.append(dict(nome=nome, metodo=metodo, comp=comp,
                          bruto=bruto, offset=offset))
        i += 46 + n_nome + n_extra + n_coment
    return saida


def extrai(url, e):
    """Baixa so os bytes da entrada e descomprime."""
    # o cabecalho local tem tamanhos proprios de nome/extra; le 4 KB e resolve
    cab, _, _ = pega(url, e["offset"], e["offset"] + 4095)
    n_nome  = struct.unpack("<H", cab[26:28])[0]
    n_extra = struct.unpack("<H", cab[28:30])[0]
    inicio = e["offset"] + 30 + n_nome + n_extra
    dados, _, _ = pega(url, inicio, inicio + e["comp"] - 1, timeout=300)
    if e["metodo"] == 0:
        return dados
    return zlib.decompress(dados, -zlib.MAX_WBITS)


def pesca(ano, casa, rotulo="arquivo"):
    """Extrai do ZIP remoto a MAIOR entrada que satisfaz `casa(nome)`.

    Reaproveitado por quem precisa de outro arquivo do mesmo pacote -- o
    script do R com os rotulos de CO_PROVA, por exemplo. Devolve os bytes.
    """
    url = URL.format(ano=ano)
    total = tamanho(url)
    entradas = entradas_do_zip(url, total)
    alvo = [e for e in entradas if casa(e["nome"])]
    if not alvo:
        raise RuntimeError(f"{rotulo} nao encontrado no ZIP de {ano} "
                           f"({len(entradas)} entradas)")
    e = max(alvo, key=lambda x: x["bruto"])
    print(f"  {rotulo}: {e['nome'].split('/')[-1]} "
          f"({e['comp']/1024:.0f} KB baixados de um ZIP de {total/1048576:.0f} MB)")
    return extrai(url, e)


def uma_edicao(ano):
    url = URL.format(ano=ano)
    print(f"\n=== ENEM {ano} ===")
    try:
        total = tamanho(url)
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as ex:
        print(f"  ! indisponivel: {ex}")
        return None
    print(f"  ZIP remoto: {total/1048576:.0f} MB")

    entradas = entradas_do_zip(url, total)
    alvo = [e for e in entradas
            if "ITENS_PROVA" in e["nome"].upper() and e["nome"].upper().endswith(".CSV")]
    if not alvo:
        print(f"  ! nenhum ITENS_PROVA no ZIP ({len(entradas)} entradas)")
        return None
    e = max(alvo, key=lambda x: x["bruto"])
    print(f"  entrada: {e['nome']}  ({e['comp']/1024:.0f} KB comprimido, "
          f"{e['bruto']/1024:.0f} KB abertos)")
    print(f"  baixando {e['comp']/1024:.0f} KB em vez de {total/1048576:.0f} MB "
          f"({total/max(e['comp'],1):.0f}x menos)")

    conteudo = extrai(url, e)
    if len(conteudo) != e["bruto"]:
        raise RuntimeError(f"tamanho inesperado: {len(conteudo)} != {e['bruto']}")

    cabecalho = conteudo.split(b"\n", 1)[0].decode("latin-1")
    faltam = [p for p in PARAMS if p not in cabecalho.upper()]
    n_linhas = conteudo.count(b"\n")
    if faltam:
        print(f"  ! SEM parametros de TRI ({', '.join(faltam)}) - nao serve "
              f"para o motor; nao gravado")
        return None

    os.makedirs(DESTINO, exist_ok=True)
    caminho = os.path.join(DESTINO, f"ITENS_PROVA_{ano}.csv")
    tmp = caminho + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(conteudo)
    os.replace(tmp, caminho)
    print(f"  ok: {caminho} ({n_linhas-1} itens, parametros de TRI presentes)")
    return caminho


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anos", nargs="+", type=int,
                    default=[2020, 2021, 2022, 2023, 2024])
    args = ap.parse_args()

    ok, falhou = [], []
    for ano in args.anos:
        try:
            r = uma_edicao(ano)
        except Exception as ex:                       # rede, ZIP64, formato
            print(f"  ! erro em {ano}: {type(ex).__name__}: {ex}")
            r = None
        (ok if r else falhou).append(ano)

    print(f"\nResumo: {len(ok)} edicoes gravadas {ok}")
    if falhou:
        print(f"        {len(falhou)} sem itens utilizaveis {falhou}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
