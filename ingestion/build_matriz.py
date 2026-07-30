"""
Gera o seed da Matriz de Referencia do ENEM a partir do PDF oficial do INEP.

Entrada : o PDF da Matriz de Referencia
          (https://download.inep.gov.br/download/enem/matriz_referencia.pdf)
Saida   : dbt/seeds/matriz_referencia.csv

Por que este script existe: os microdados trazem apenas o NUMERO da habilidade
(CO_HABILIDADE), nunca a descricao nem a competencia de area que a agrupa. Sem
esse mapa, o diagnostico diz "habilidade 21" -- que nao significa nada para um
professor -- e nao consegue agregar no nivel de competencia, o unico jeito de
dar lastro as habilidades medidas por um item so.

A Matriz e publica mas nao vem no pacote de microdados. Em vez de transcrever
a mao, derivamos do PDF oficial: a transcricao manual de 120 descricoes
rotularia habilidade errada em todos os relatorios se errasse uma linha, e
ninguem perceberia.

Uso:
    pip install pdfplumber
    python -m ingestion.build_matriz --pdf data/raw/matriz_referencia.pdf
"""

import argparse
import csv
import os
import re
import sys


# A Matriz nomeia as areas por extenso; os microdados usam a sigla de SG_AREA.
# Este e o unico ponto de traducao entre os dois vocabularios.
AREAS = {
    "Linguagens, Códigos e suas Tecnologias":  "LC",
    "Matemática e suas Tecnologias":           "MT",
    "Ciências da Natureza e suas Tecnologias": "CN",
    "Ciências Humanas e suas Tecnologias":     "CH",
}

# o documento tem 30 habilidades por area, numeradas de 1 a 30
HABILIDADES_POR_AREA = 30

# a Matriz usa hifen e travessao como separador, de forma inconsistente
SEP = r"[-–—]"

RE_AREA = re.compile(r"^Matriz de Refer[êe]ncia (?:de )?(.+?)\s*$", re.M)
RE_COMPETENCIA = re.compile(r"^Compet[êe]ncia de [áa]rea\s+(\d+)\s*" + SEP + r"\s*(.*)$")
RE_HABILIDADE = re.compile(r"^H\s*(\d+)\s*" + SEP + r"\s*(.*)$")

# Depois da ultima habilidade (CH H30) o PDF emenda o ANEXO com os objetos de
# conhecimento -- 20 mil caracteres que nao sao habilidade nenhuma. Como
# nenhuma linha dele casa com H\d ou Competencia, o parser os tratava como
# continuacao da H30 e o texto ia inteiro para o relatorio.
RE_FIM = re.compile(r"^\s*ANEXO\b")

# Nenhuma descricao real passa de 250 caracteres (a maior e LC C9, com 341
# na competencia). O teto abaixo e folgado de proposito: nao existe para
# medir estilo, e para denunciar emenda de secao.
MAX_DESCRICAO = 600


def extrai_texto(caminho):
    """Le o PDF preservando as palavras inteiras.

    pdfplumber posiciona caractere a caractere; extratores que inferem o espaco
    pela largura do glifo quebram palavras no meio ('signif icados') porque o
    PDF e justificado. A diferenca so aparece quando alguem le o relatorio.
    """
    try:
        import pdfplumber
    except ImportError:
        raise SystemExit(
            "pdfplumber nao instalado. Rode: pip install pdfplumber\n"
            "(extratores baseados em largura de glifo quebram palavras neste PDF)"
        )

    with pdfplumber.open(caminho) as pdf:
        paginas = [p.extract_text() or "" for p in pdf.pages]
    texto = "\n".join(paginas)

    # corta o ANEXO: a Matriz termina na ultima habilidade
    linhas = texto.splitlines()
    for i, linha in enumerate(linhas):
        if RE_FIM.match(linha):
            print(f"  ANEXO encontrado na linha {i} - cortado "
                  f"({len(linhas) - i} linhas descartadas)")
            return "\n".join(linhas[:i])
    return texto


def limpa(texto):
    """Normaliza espacos, recola palavra composta partida e tira marcador."""
    texto = re.sub(r"\s+", " ", texto).strip()

    # PALAVRA COMPOSTA PARTIDA NA LINHA. O PDF quebra "cientifico-tecnologicas"
    # em "cientifico-" + "tecnologicas", e juntar as linhas com espaco produzia
    # "cientifico- tecnologicas" -- que aparecia assim na tela.
    #
    # Colar e seguro NESTE documento: as 6 linhas que terminam em hifen foram
    # conferidas uma a uma e todas sao compostos (historico-geograficos,
    # cientifico-tecnologicas x3, logico-semanticas). Nao ha hifenizacao de
    # silaba, que exigiria decidir se o hifen fica ou sai. A exigencia de letra
    # dos DOIS lados evita colar o travessao solto do anexo ("- Quimica").
    texto = re.sub(r"(\w)-\s+(\w)", r"\1-\2", texto)

    # MARCADOR DE NOTA DE RODAPE. O rstrip("*") anterior so pegava o asterisco
    # em ULTIMA posicao, e o unico caso do documento tem pontuacao depois
    # ("...grupos sociais*."), entao ele passava direto para o seed e chegava a
    # tela. Pior: o PDF nao traz nota de rodape nenhuma nas 24 paginas -- o
    # marcador nao tem referente, e so levanta uma pergunta sem resposta.
    texto = re.sub(r"\*(?=\W*$)", "", texto)
    texto = texto.strip()

    # PONTO FINAL AUSENTE NA FONTE. Duas entradas das 150 nao terminam em
    # pontuacao no PDF oficial -- CH C1 ("...que constituem as identidades") e
    # CH H7 ("...de poder entre as nacoes"). O texto esta COMPLETO; falta so o
    # ponto, e conferido contra o PDF: a linha seguinte ja e a proxima
    # habilidade. Na tela, ao lado de 148 frases pontuadas, a falta lia como
    # descricao cortada -- foi assim que apareceu.
    #
    # Fechar a frase e normalizacao, nao edicao: nao muda o sentido nem
    # acrescenta palavra. Diferente do asterisco, aqui nao ha o que interpretar.
    if texto and texto[-1] not in ".?!":
        texto += "."

    return texto


def parse(texto):
    """Devolve [(sigla, competencia, habilidade, desc_comp, desc_hab)]."""
    linhas = []
    nao_mapeadas = []

    # divide o documento nos cabecalhos de area; o trecho antes do primeiro
    # cabecalho e a pagina dos eixos cognitivos, que nao entra no seed
    partes = RE_AREA.split(texto)
    for i in range(1, len(partes), 2):
        nome_area, corpo = partes[i].strip(), partes[i + 1]

        sigla = AREAS.get(nome_area)
        if not sigla:
            nao_mapeadas.append(nome_area)
            continue

        competencia = None
        desc_comp = []
        habilidade = None
        desc_hab = []
        registros = []

        def fecha_habilidade():
            if habilidade is not None:
                registros.append([competencia, habilidade,
                                  limpa(" ".join(desc_comp)),
                                  limpa(" ".join(desc_hab))])

        for linha in corpo.splitlines():
            linha = linha.strip()
            if not linha:
                continue

            m = RE_COMPETENCIA.match(linha)
            if m:
                fecha_habilidade()
                habilidade, desc_hab = None, []
                competencia = int(m.group(1))
                desc_comp = [m.group(2)]
                continue

            m = RE_HABILIDADE.match(linha)
            if m:
                fecha_habilidade()
                habilidade = int(m.group(1))
                desc_hab = [m.group(2)]
                continue

            # linha de continuacao: pertence a habilidade aberta ou, se
            # nenhuma esta aberta, ao enunciado da competencia
            if habilidade is not None:
                desc_hab.append(linha)
            elif competencia is not None:
                desc_comp.append(linha)

        fecha_habilidade()

        for comp, hab, dcomp, dhab in registros:
            linhas.append([sigla, comp, hab, dcomp, dhab])

        print(f"  {sigla}: {len({r[0] for r in registros})} competencias, "
              f"{len(registros)} habilidades")

    return linhas, nao_mapeadas


def valida(linhas, nao_mapeadas):
    """Falha alto. Um seed silenciosamente incompleto rotularia habilidade
    errada em todo relatorio, e ninguem perceberia."""
    erros = []

    for nome in nao_mapeadas:
        erros.append(f"area do PDF nao reconhecida: {nome!r} "
                     f"(atualize o dicionario AREAS)")

    siglas = {l[0] for l in linhas}
    faltando = set(AREAS.values()) - siglas
    if faltando:
        erros.append(f"areas ausentes no resultado: {sorted(faltando)}")

    for sigla in sorted(siglas):
        habs = sorted(l[2] for l in linhas if l[0] == sigla)
        esperado = list(range(1, HABILIDADES_POR_AREA + 1))
        if habs != esperado:
            faltam = sorted(set(esperado) - set(habs))
            sobram = sorted(set(habs) - set(esperado))
            dup = sorted({h for h in habs if habs.count(h) > 1})
            erros.append(
                f"{sigla}: esperava habilidades 1..{HABILIDADES_POR_AREA}, "
                f"veio {len(habs)}"
                + (f" | faltam {faltam}" if faltam else "")
                + (f" | inesperadas {sobram}" if sobram else "")
                + (f" | duplicadas {dup}" if dup else "")
            )

        comps = sorted({l[1] for l in linhas if l[0] == sigla})
        if comps != list(range(1, len(comps) + 1)):
            erros.append(f"{sigla}: competencias nao contiguas a partir de 1: {comps}")

    vazias = [(l[0], l[2]) for l in linhas if not l[4] or len(l[4]) < 20]
    if vazias:
        erros.append(f"descricoes vazias ou curtas demais: {vazias[:5]}")

    # Descricao gigante nao e descricao: e outra secao do PDF emendada na
    # ultima habilidade aberta. Foi exatamente assim que o ANEXO inteiro
    # (21.710 caracteres) entrou na CH H30 e chegou ao site.
    longas = [(l[0], f"H{l[2]}", len(l[4])) for l in linhas
              if len(l[4]) > MAX_DESCRICAO]
    longas += [(l[0], f"C{l[1]}", len(l[3])) for l in linhas
               if len(l[3]) > MAX_DESCRICAO]
    if longas:
        erros.append(
            f"descricoes longas demais (>{MAX_DESCRICAO} chars) - o PDF "
            f"provavelmente emendou outra secao: {sorted(set(longas))[:5]}")

    # RUIDO DE EXTRACAO QUE SOBREVIVE AO limpa(). Nenhum destes derruba o
    # script, porque nao invalidam o dado -- mas todos ja chegaram a tela, e
    # todos ficaram escondidos enquanto a descricao aparecia truncada. O limpa()
    # trata os tres casos conhecidos; este bloco existe para o caso NOVO, na
    # proxima edicao do PDF.
    suspeitos = []
    for l in linhas:
        for rotulo, txt in ((f"C{l[1]}", l[3]), (f"H{l[2]}", l[4])):
            if not txt:
                continue
            if re.search(r"\w-\s+\w", txt):
                suspeitos.append((l[0], rotulo, "hifen solto"))
            if "*" in txt:
                suspeitos.append((l[0], rotulo, "marcador de nota"))
            if txt[-1] not in ".?!":
                suspeitos.append((l[0], rotulo, "sem pontuacao final"))
    if suspeitos:
        erros.append(
            f"ruido de extracao que o limpa() nao pegou: "
            f"{sorted(set(suspeitos))[:6]}")

    return erros


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True,
                    help="caminho do PDF da Matriz de Referencia")
    ap.add_argument("--saida", default="dbt/seeds",
                    help="pasta de destino do seed (padrao: dbt/seeds)")
    args = ap.parse_args()

    print("1. Lendo o PDF")
    texto = extrai_texto(args.pdf)
    print(f"  {len(texto):,} caracteres")

    print("2. Parse por area")
    linhas, nao_mapeadas = parse(texto)

    print("3. Validacao")
    erros = valida(linhas, nao_mapeadas)
    if erros:
        print("\nFALHA - o seed NAO foi gravado:")
        for e in erros:
            print(f"  ! {e}")
        sys.exit(1)
    print("  ok: 4 areas, 30 habilidades cada, competencias contiguas")

    linhas.sort(key=lambda r: (r[0], r[2]))

    caminho = os.path.join(args.saida, "matriz_referencia.csv")
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["area", "habilidade", "competencia",
                    "descricao_competencia", "descricao_habilidade"])
        for sigla, comp, hab, dcomp, dhab in linhas:
            w.writerow([sigla, hab, comp, dcomp, dhab])

    print(f"\n  gravado {caminho} ({len(linhas)} linhas)")

    print("\nResumo")
    for sigla in sorted({l[0] for l in linhas}):
        da_area = [l for l in linhas if l[0] == sigla]
        n_comp = len({l[1] for l in da_area})
        por_comp = [sum(1 for l in da_area if l[1] == c)
                    for c in sorted({l[1] for l in da_area})]
        print(f"  {sigla}: {n_comp} competencias, habilidades por competencia: "
              f"{por_comp}")


if __name__ == "__main__":
    main()
