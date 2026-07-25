"""
Pipeline ENEM 2025, de ponta a ponta: raw -> staging -> intermediate -> marts.

A restricao que molda todo o desenho: os modelos pesados NAO podem rodar em
paralelo. Cada worker paralelo do Postgres recebe sua propria fatia de
memoria, e e isso que derruba o servidor -- foi o que motivou a regra
"NUNCA rodar dbt run sem --select" desde a Etapa 3.

A traducao disso para o Airflow nao e desligar o paralelismo global, que
serializaria tambem as tasks leves. E declarar QUAL e o recurso escasso: o
pool 'banco_pesado', de um slot, deixa uma varredura grande por vez e nao
atrapalha o resto.

O pool precisa existir ANTES do primeiro disparo:
    docker compose exec airflow airflow pools set \\
        banco_pesado 1 "Uma varredura grande do Postgres por vez"
"""

from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import chain, dag, task_group

PROJETO = "/opt/projeto"
VENV = "/home/airflow/projeto-venv/bin"

DBT = f"cd {PROJETO}/dbt && {VENV}/dbt"
PY = f"cd {PROJETO} && {VENV}/python"

AREAS = ["mt", "ch", "cn", "lc"]

# nome da base na ingestao -> prefixo do arquivo do INEP
BASES = {
    "itens_prova": "ITENS_PROVA",
    "resultados": "RESULTADOS",
    "participantes": "PARTICIPANTES",
}

# so o que dispara varredura grande do banco entra no pool
PESADO = {"pool": "banco_pesado"}


def dbt_run(modelo, **kwargs):
    """Uma task por modelo -- nunca 'dbt run' solto (ver docstring do modulo)."""
    return BashOperator(
        task_id=modelo,
        bash_command=f"{DBT} run --select {modelo}",
        **kwargs,
    )


@dag(
    dag_id="enem_pipeline",
    description="Microdados do ENEM 2025: raw -> staging -> marts",
    start_date=pendulum.datetime(2025, 1, 1, tz="America/Sao_Paulo"),
    # Os microdados saem uma vez por ano. Agendar isto diariamente
    # reprocessaria 4,8 milhoes de linhas identicas as de ontem -- teatro de
    # automacao. Roda por disparo manual.
    schedule=None,
    # protecao explicita: se um dia alguem puser um cron acima, o Airflow nao
    # vai tentar executar retroativamente tudo desde o start_date
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["enem", "dbt"],
)
def enem_pipeline():

    # ------------------------------------------------------------ ingestao
    @task_group(group_id="ingestao")
    def ingestao():
        # as tres bases sao independentes entre si, mas todas varrem arquivo
        # grande (resultados tem 2,1 GB), entao vao para o pool
        for base, arquivo in BASES.items():
            BashOperator(
                task_id=f"carrega_{base}",
                bash_command=(
                    f"{PY} -m ingestion.load_raw "
                    f"--base {base} --path data/raw/{arquivo}_2025.csv"
                ),
                **PESADO,
            )

    # -------------------------------------------------- fronteira, fail fast
    # Antes de qualquer transformacao: se o arquivo do INEP mudou de forma,
    # nao faz sentido gastar 40 minutos construindo modelos em cima dele.
    valida_fronteira = BashOperator(
        task_id="valida_fronteira",
        bash_command=f"{PY} -m quality.expectations_raw",
        # sem retry: se o dado veio fora do esperado, tentar de novo encontra
        # o mesmo dado. Falha de dado pede pessoa, nao repeticao.
        retries=0,
        **PESADO,
    )

    # --------------------------------------------------------------- seeds
    # Os seeds sao versionados no Git justamente para nao dependerem dos
    # artefatos de origem (2,6 GB de microdados e o PDF da Matriz). Quem
    # quiser regerar roda build_seeds.py / build_matriz.py a mao.
    seeds = BashOperator(
        task_id="seeds",
        bash_command=f"{DBT} deps && {DBT} seed",
    )

    # ------------------------------------------------------------- staging
    @task_group(group_id="staging")
    def staging():
        # os tres leem a raw de forma independente: sem dependencia entre eles
        dbt_run("stg_itens")
        dbt_run("stg_participantes")
        # table sobre 4,8 milhoes de linhas
        dbt_run("stg_resultados", **PESADO)

    # -------------------------------------------------------- intermediate
    @task_group(group_id="intermediate")
    def intermediate():
        # os consolidados unem as quatro areas: dependem de todas
        escola = dbt_run("int_acerto_item_escola", **PESADO)
        nacional = dbt_run("int_acerto_item_nacional", **PESADO)

        for area in AREAS:
            # view: segundos, e as quatro podem ir juntas
            respostas = dbt_run(f"int_respostas_{area}")
            # table: minutos. O pool garante uma por vez mesmo que o
            # scheduler queira disparar as quatro
            acerto = dbt_run(f"int_acerto_item_{area}", **PESADO)
            chain(respostas, acerto, [escola, nacional])

    # --------------------------------------------------------------- marts
    @task_group(group_id="marts")
    def marts():
        # ramo paralelo: nenhum fato depende da dimensao, quem a consome e a
        # aplicacao (ver Volume 4)
        dbt_run("dim_escola", **PESADO)

        area = dbt_run("mart_escola_area", **PESADO)
        # os dois diagnosticos herdam o flag publicavel do mart_escola_area
        chain(area, [
            dbt_run("mart_diagnostico_habilidade", **PESADO),
            dbt_run("mart_diagnostico_competencia", **PESADO),
        ])

    testes = BashOperator(
        task_id="dbt_test",
        bash_command=f"{DBT} test",
        **PESADO,
    )

    chain(
        ingestao(),
        valida_fronteira,
        seeds,
        staging(),
        intermediate(),
        marts(),
        testes,
    )


enem_pipeline()
