CSV_SEP = ";"
CSV_ENCODING = "latin-1"
CHUNKSIZE = 50_000  # linhas por bloco; reduza se faltar RAM

PARTICIPANTES = [
    "NU_INSCRICAO", "NU_ANO",
    "TP_FAIXA_ETARIA", "TP_SEXO", "TP_COR_RACA",
    "TP_ST_CONCLUSAO", "TP_ANO_CONCLUIU", "TP_ENSINO", "IN_TREINEIRO",
    "CO_MUNICIPIO_PROVA", "CO_UF_PROVA", "SG_UF_PROVA",
] + [f"Q{i:03d}" for i in range(1, 24)]

RESULTADOS = [
    "NU_SEQUENCIAL", "NU_ANO",
    # escola — a chave do projeto
    "CO_ESCOLA", "CO_MUNICIPIO_ESC", "NO_MUNICIPIO_ESC",
    "CO_UF_ESC", "SG_UF_ESC",
    "TP_DEPENDENCIA_ADM_ESC", "TP_LOCALIZACAO_ESC", "TP_SIT_FUNC_ESC",
    # aplicação
    "CO_MUNICIPIO_PROVA", "CO_UF_PROVA", "SG_UF_PROVA",
    # presença e prova
    "TP_PRESENCA_CN", "TP_PRESENCA_CH", "TP_PRESENCA_LC", "TP_PRESENCA_MT",
    "CO_PROVA_CN", "CO_PROVA_CH", "CO_PROVA_LC", "CO_PROVA_MT",
    "NU_NOTA_CN", "NU_NOTA_CH", "NU_NOTA_LC", "NU_NOTA_MT",
    # vetores de resposta e gabarito
    "TX_RESPOSTAS_CN", "TX_RESPOSTAS_CH", "TX_RESPOSTAS_LC", "TX_RESPOSTAS_MT",
    "TX_GABARITO_CN", "TX_GABARITO_CH", "TX_GABARITO_LC", "TX_GABARITO_MT",
    "TP_LINGUA",
    # redação
    "TP_STATUS_REDACAO", "NU_NOTA_REDACAO",
    "NU_NOTA_COMP1", "NU_NOTA_COMP2", "NU_NOTA_COMP3",
    "NU_NOTA_COMP4", "NU_NOTA_COMP5",
]

ITENS_PROVA = [
    "CO_PROVA", "TX_COR", "TP_LINGUA",
    "CO_ITEM", "CO_POSICAO", "SG_AREA", "TX_GABARITO",
    "IN_ITEM_ADAPTADO", "IN_ITEM_ABAN", "TX_MOTIVO_ABAN",
    "CO_HABILIDADE", "NU_PARAM_A", "NU_PARAM_B", "NU_PARAM_C",
]

BASES = {
    "participantes": PARTICIPANTES,
    "resultados": RESULTADOS,
    "itens_prova": ITENS_PROVA,
}


# ----------------------------------------------------------------- Censo Escolar
#
# Fonte diferente das tres acima: o Censo Escolar (INEP) traz o CADASTRO das
# escolas, que os microdados do ENEM nao tem. O ENEM so identifica a escola por
# CO_ESCOLA -- um codigo que ninguem sabe de cabeca. Sem este cruzamento,
# nenhuma escola consegue se achar num relatorio.
#
# Sao 426 colunas no arquivo; ficam estas, em quatro grupos. O criterio e o
# mesmo das outras bases: entra o que tem uso previsto, nao o que existe.
CENSO_ESCOLAR = [
    # identidade -- CO_ENTIDADE e a chave que casa com CO_ESCOLA do ENEM
    "NU_ANO_CENSO", "CO_ENTIDADE", "NO_ENTIDADE", "TP_SITUACAO_FUNCIONAMENTO",

    # geografia. MESO e MICRORREGIAO sao a agregacao do IBGE que permite subir
    # de nivel quando o municipio e pequeno demais para publicar sozinho --
    # 45% dos municipios tem uma escola so, e publicar o municipio seria
    # publicar aquela escola com outro rotulo
    "CO_REGIAO", "CO_UF", "SG_UF", "CO_MUNICIPIO", "NO_MUNICIPIO",
    "CO_MESORREGIAO", "CO_MICRORREGIAO", "TP_LOCALIZACAO",

    # rede
    "TP_DEPENDENCIA", "TP_CATEGORIA_ESCOLA_PRIVADA",

    # porte no ensino medio -- o publico do ENEM
    "IN_MED", "QT_MAT_MED", "QT_DOC_MED", "QT_TUR_MED", "QT_SALAS_UTILIZADAS",

    # infraestrutura: contexto para comparar escolas de perfil semelhante
    "IN_INTERNET", "IN_BIBLIOTECA", "IN_LABORATORIO_INFORMATICA",
    "IN_LABORATORIO_CIENCIAS", "IN_QUADRA_ESPORTES", "IN_AGUA_POTAVEL",
    "IN_ENERGIA_REDE_PUBLICA", "IN_ESGOTO_REDE_PUBLICA",
    "IN_ACESSIBILIDADE_INEXISTENTE",
]

# o zip do INEP, e o caminho do CSV dentro dele. O ano vai por formatacao
# porque a estrutura se repete entre edicoes.
CENSO_URL = ("https://download.inep.gov.br/dados_abertos/"
             "microdados_censo_escolar_{ano}.zip")
CENSO_CSV_INTERNO = "dados/microdados_ed_basica_{ano}.csv"