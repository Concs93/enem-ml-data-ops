"""
Cria a camada raw VAZIA -- so a estrutura, zero linhas.

Serve a Faixa 2 da CI: o Postgres precisa das tabelas para julgar coluna,
tipo e juncao, mas nao precisa de uma linha sequer. Com elas de pe, o
`dbt build --empty` executa o SQL de todos os modelos contra um banco de
verdade sem processar dado nenhum.

A lista de colunas vem de ingestion/config.py -- a mesma que a ingestao usa.
Escrever um .sql a parte criaria uma segunda fonte de verdade, que diverge em
silencio no dia em que alguem acrescentar uma coluna. E a mesma regra dos
seeds: derivar de artefato, nunca transcrever.

Uso (da raiz do projeto):
    python -m ci.cria_raw_vazia
"""

import os

import psycopg2

from ingestion.config import (BASES, CENSO_ESCOLAR, EDICOES_ITENS,
                              ITENS_PROVA, ANO_CORRENTE)

ANO = ANO_CORRENTE
ANO_CENSO = 2024


def main():
    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )
    cur = conn.cursor()
    cur.execute("create schema if not exists raw;")

    # as tres bases do ENEM (ano da edicao) + o cadastro do Censo, que tem
    # ano proprio: o Censo do ano do ENEM nao existe quando os microdados
    # saem, entao a fonte real e censo_escolar_2024 (ver load_censo.py)
    tabelas = {f"{base}_{ANO}": colunas for base, colunas in BASES.items()}
    tabelas[f"censo_escolar_{ANO_CENSO}"] = CENSO_ESCOLAR
    # o banco de itens tem uma tabela por edicao; a lista mora no config,
    # entao acrescentar uma edicao nao exige tocar na CI
    for ano in EDICOES_ITENS:
        tabelas[f"itens_prova_{ano}"] = ITENS_PROVA

    for nome, colunas in tabelas.items():
        tabela = f"raw.{nome}"
        # tudo TEXT, igual a ingestao de verdade (decisao da Etapa 1:
        # a camada raw nao interpreta nada)
        cols = ", ".join(f'"{c}" text' for c in colunas)
        cur.execute(f"drop table if exists {tabela} cascade;")
        cur.execute(f"create table {tabela} ({cols});")
        print(f"  {tabela}: {len(colunas)} colunas, 0 linhas")

    conn.commit()
    conn.close()
    print(f"ok: {len(tabelas)} tabelas criadas em raw")


if __name__ == "__main__":
    main()
