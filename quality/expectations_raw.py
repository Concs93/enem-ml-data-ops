"""
Valida a camada raw logo apos a ingestao -- a fronteira do pipeline.

Estas expectations nao testam o nosso SQL (isso e trabalho do dbt test). Elas
testam os PRESSUPOSTOS que o pipeline inteiro faz sobre o arquivo do INEP:
que o vetor de resposta tem 45 posicoes, que o gabarito e A-E ou X, que a
presenca e 0/1/2, que a habilidade vai de 1 a 30. Cada um desses pressupostos
estava espalhado por macros e modelos, e escrito em lugar nenhum de forma
verificavel.

Se uma delas falhar numa edicao futura, foi o DADO que mudou -- e e melhor
descobrir aqui do que num diagnostico de escola errado.

Nota sobre tipos: a camada raw e toda TEXT por decisao de projeto. Por isso o
que e forma (comprimento, conjunto, padrao) usa expectations de texto, e o que
e numero passa por um query asset que converte. Comparar "9" com 30 como texto
daria ordem lexicografica e a expectation passaria pelo motivo errado.

Contexto efemero (em memoria): cada execucao comeca limpa, entao o script e
idempotente e nao deixa estado no repositorio.

Uso:
    pip install great_expectations
    . .\\load_env.ps1
    python -m quality.expectations_raw
"""

import os

import great_expectations as gx
from dotenv import load_dotenv

AREAS = ["CN", "CH", "LC", "MT"]


def conexao():
    load_dotenv()
    u = os.environ["POSTGRES_USER"]
    p = os.environ["POSTGRES_PASSWORD"]
    h = os.environ.get("POSTGRES_HOST", "localhost")
    porta = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ["POSTGRES_DB"]
    return f"postgresql+psycopg2://{u}:{p}@{h}:{porta}/{db}"


def main():
    context = gx.get_context(mode="ephemeral")
    fonte = context.data_sources.add_postgres(
        "enem_postgres", connection_string=conexao()
    )

    definicoes = []

    def registra(nome, batch, suite):
        definicoes.append(
            context.validation_definitions.add(
                gx.ValidationDefinition(name=nome, data=batch, suite=suite)
            )
        )

    # -------------------------------------- itens: estrutura e dominio
    itens = fonte.add_table_asset(
        name="itens_prova", table_name="itens_prova_2025", schema_name="raw"
    )
    suite_itens = context.suites.add(gx.ExpectationSuite(name="raw_itens_prova"))

    for coluna in ["CO_ITEM", "CO_PROVA", "CO_POSICAO", "SG_AREA",
                   "CO_HABILIDADE", "TX_GABARITO"]:
        suite_itens.add_expectation(
            gx.expectations.ExpectColumnValuesToNotBeNull(column=coluna)
        )

    # as quatro areas, exatamente estas
    suite_itens.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="SG_AREA", value_set=["CH", "CN", "LC", "MT"]
        )
    )

    # gabarito e A-E ou X (anulado). Um valor novo aqui quebraria o calculo
    # de acerto em silencio
    suite_itens.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="TX_GABARITO", value_set=["A", "B", "C", "D", "E", "X"]
        )
    )

    # habilidade de 1 a 30, como TEXTO: regex em vez de faixa numerica.
    # E o que sustenta o join com o seed da Matriz de Referencia
    suite_itens.add_expectation(
        gx.expectations.ExpectColumnValuesToMatchRegex(
            column="CO_HABILIDADE", regex=r"^([1-9]|[12][0-9]|30)$"
        )
    )

    registra("itens", itens.add_batch_definition_whole_table("tudo"), suite_itens)

    # ------------------------------- resultados: forma dos vetores
    resultados = fonte.add_table_asset(
        name="resultados", table_name="resultados_2025", schema_name="raw"
    )
    suite_res = context.suites.add(gx.ExpectationSuite(name="raw_resultados"))

    # TODA a Etapa 3 depende destes tamanhos: o generate_series(1, 45) e o
    # substring por posicao assumem 45, e um vetor mais curto produziria nulos
    # silenciosos. LC e o caso especial: resposta 45, gabarito 50.
    # Os ausentes tem vetor nulo, e expectation de valor ignora nulo.
    for area in AREAS:
        suite_res.add_expectation(
            gx.expectations.ExpectColumnValueLengthsToEqual(
                column=f"TX_RESPOSTAS_{area}", value=45
            )
        )
    suite_res.add_expectation(
        gx.expectations.ExpectColumnValueLengthsToEqual(
            column="TX_GABARITO_LC", value=50
        )
    )

    # presenca: 0 faltou, 1 presente, 2 eliminado. So o 1 entra na analise
    for area in AREAS:
        suite_res.add_expectation(
            gx.expectations.ExpectColumnValuesToBeInSet(
                column=f"TP_PRESENCA_{area}", value_set=["0", "1", "2"]
            )
        )

    registra("resultados",
             resultados.add_batch_definition_whole_table("tudo"), suite_res)

    # ------------------------- notas: o sentinela, virado expectation
    # Query asset porque a raw e texto e aqui a pergunta e numerica. O filtro
    # tira os zeros de proposito: a afirmacao a verificar e "entre as notas que
    # NAO sao o sentinela, todas estao na escala da TRI". Se um dia aparecer
    # nota 120, o zero deixou de ser sentinela -- e e melhor saber.
    colunas = ", ".join(
        f"nullif(\"NU_NOTA_{a}\", '')::numeric as nota_{a.lower()}"
        for a in AREAS
    )
    notas = fonte.add_query_asset(
        name="notas",
        query=f"select {colunas} from raw.resultados_2025",
    )
    suite_notas = context.suites.add(gx.ExpectationSuite(name="raw_notas_escala"))

    for area in AREAS:
        coluna = f"nota_{area.lower()}"
        suite_notas.add_expectation(
            gx.expectations.ExpectColumnValuesToBeBetween(
                column=coluna,
                min_value=250, max_value=1000,
                row_condition=f'col("{coluna}") != 0',
                condition_parser="great_expectations",
            )
        )

    registra("notas", notas.add_batch_definition_whole_table("tudo"), suite_notas)

    # ------------------------------------------------------- executa
    resultado = context.checkpoints.add(
        gx.Checkpoint(name="raw_pos_ingestao", validation_definitions=definicoes)
    ).run()

    print(resultado.describe())
    raise SystemExit(0 if resultado.success else 1)


if __name__ == "__main__":
    main()
