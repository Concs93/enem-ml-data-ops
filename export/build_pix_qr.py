"""Gera o QR do PIX da pagina de apoio e o injeta no webapp/apoie.html.

O QR do PIX NAO e a chave codificada: e o "BR Code", o payload EMV MPM
padronizado pelo Banco Central (manual do BR Code, EMVCo MPM). Cada campo e
`ID + tamanho em 2 digitos + valor`, e o ultimo campo e um CRC-16/CCITT-FALSE
calculado sobre tudo o que veio antes -- inclusive sobre o proprio "6304".

Derivar, nunca transcrever: o SVG do QR e gerado aqui e injetado entre os
marcadores no HTML, para que trocar a chave seja rodar este script de novo.

    python export/build_pix_qr.py

Verificacao final que NENHUM script substitui: apontar a camera do banco para
o QR gerado e conferir se o nome que aparece e o certo. Um payload pode estar
formalmente valido e mesmo assim apontar para a chave errada.
"""

import os
import re
import sys

import segno

# ---------------------------------------------------------------- configuracao
CHAVE = "db37d884-2e4d-47db-af3b-6377064f1f18"   # chave aleatoria (EVP)
NOME = "ENEM EM FOCO"       # ate 25 caracteres, sem acento
CIDADE = "BELO HORIZONTE"   # ate 15 caracteres, sem acento
TXID = "***"                # "***" = sem identificador de transacao

HTML = os.path.join("webapp", "apoie.html")
INICIO = "<!-- QR:INICIO (gerado por export/build_pix_qr.py) -->"
FIM = "<!-- QR:FIM -->"


def campo(ident: str, valor: str) -> str:
    """ID + tamanho em 2 digitos + valor."""
    if len(valor) > 99:
        raise ValueError(f"campo {ident} tem {len(valor)} caracteres (max 99)")
    return f"{ident}{len(valor):02d}{valor}"


def crc16(dados: str) -> str:
    """CRC-16/CCITT-FALSE: polinomio 0x1021, valor inicial 0xFFFF."""
    crc = 0xFFFF
    for b in dados.encode("ascii"):
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def payload(chave: str, nome: str, cidade: str, txid: str) -> str:
    conta = campo("00", "br.gov.bcb.pix") + campo("01", chave)
    corpo = (
        campo("00", "01")            # formato do payload
        + campo("26", conta)         # conta do recebedor (GUI + chave)
        + campo("52", "0000")        # categoria do estabelecimento: nao informada
        + campo("53", "986")         # moeda: BRL
        + campo("58", "BR")          # pais
        + campo("59", nome[:25])     # nome do recebedor
        + campo("60", cidade[:15])   # cidade do recebedor
        + campo("62", campo("05", txid))
    )
    # o CRC entra por ultimo e cobre o proprio marcador "6304"
    return corpo + "6304" + crc16(corpo + "6304")


def valida(p: str) -> None:
    """Reabre o payload campo a campo -- se o parser nao fecha, algo esta torto."""
    i, vistos = 0, {}
    while i < len(p):
        ident, tam = p[i:i + 2], int(p[i + 2:i + 4])
        vistos[ident] = p[i + 4:i + 4 + tam]
        i += 4 + tam
    if i != len(p):
        raise SystemExit("ERRO: os tamanhos declarados nao fecham com o total")
    for obrig in ("00", "26", "53", "58", "59", "60", "63"):
        if obrig not in vistos:
            raise SystemExit(f"ERRO: campo obrigatorio {obrig} ausente")
    if crc16(p[:-4]) != vistos["63"]:
        raise SystemExit("ERRO: CRC nao confere")
    if CHAVE not in vistos["26"]:
        raise SystemExit("ERRO: a chave nao esta no payload")
    print(f"  payload valido: {len(p)} caracteres, {len(vistos)} campos, "
          f"CRC {vistos['63']}")


def main() -> None:
    # vetor de teste do CRC-16/CCITT-FALSE: "123456789" -> 0x29B1
    if crc16("123456789") != "29B1":
        raise SystemExit("ERRO: o CRC-16 falhou no vetor de teste padrao")

    p = payload(CHAVE, NOME, CIDADE, TXID)
    valida(p)

    qr = segno.make(p, error="m")
    svg = qr.svg_inline(scale=1, border=2, dark="#20211f", light=None)

    # o segno grava width/height mas NAO grava viewBox -- e sem viewBox o CSS
    # nao escala nada: o QR sai do tamanho natural (53px) dentro da caixa, o
    # que parece funcionar na inspecao do codigo e falha na tela. As dimensoes
    # sao lidas do proprio SVG, nunca transcritas
    m = re.search(r'width="(\d+)"\s+height="(\d+)"', svg)
    if not m:
        raise SystemExit("ERRO: nao achei width/height no SVG do segno")
    w, h = m.group(1), m.group(2)
    svg = svg.replace(
        "<svg ",
        f'<svg role="img" aria-label="QR Code do PIX para doacao" '
        f'viewBox="0 0 {w} {h}" shape-rendering="crispEdges" ', 1)

    with open(HTML, encoding="utf-8") as fh:
        html = fh.read()
    novo = re.sub(
        re.escape(INICIO) + r".*?" + re.escape(FIM),
        INICIO + "\n" + svg + "\n" + FIM,
        html, flags=re.S)
    if novo == html:
        raise SystemExit(f"ERRO: marcadores {INICIO} / {FIM} nao encontrados")
    with open(HTML, "w", encoding="utf-8", newline="") as fh:
        fh.write(novo)

    print(f"  QR: versao {qr.version}, {len(svg)} bytes de SVG")
    print(f"  injetado em {HTML}")
    print("\n  copia e cola (confira no app do banco antes de publicar):")
    print(f"  {p}")


if __name__ == "__main__":
    sys.exit(main())
