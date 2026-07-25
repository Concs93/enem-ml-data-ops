import argparse
import io
import os
import time

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

from ingestion.config import CSV_SEP, CSV_ENCODING, CHUNKSIZE, BASES


def get_engine():
    load_dotenv()
    user = os.environ["POSTGRES_USER"]
    pwd = os.environ["POSTGRES_PASSWORD"]
    db = os.environ["POSTGRES_DB"]
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    return create_engine(f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}")


def load(base, year, path):
    colunas = BASES[base]
    table = f"{base}_{year}"
    engine = get_engine()

    reader = pd.read_csv(
        path,
        sep=CSV_SEP,
        encoding=CSV_ENCODING,
        usecols=lambda c: c in colunas,
        chunksize=CHUNKSIZE,
        dtype=str,          # raw fica cru; a tipagem vem no staging
        low_memory=False,
    )

    conn = engine.raw_connection()
    total, t0, criada = 0, time.time(), False
    try:
        cur = conn.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS raw;")
        # CASCADE porque, a partir da Etapa 2, existem views do staging
        # apoiadas nestas tabelas (stg_itens, stg_participantes). Sem ele, o
        # Postgres recusa o DROP -- "cannot drop table because other objects
        # depend on it" -- e a reingestao so funciona num banco virgem, o que
        # quebra a idempotencia justamente quando o pipeline vira rotina.
        #
        # E seguro: tudo acima da raw e derivado e reconstruido pelo dbt, que
        # no DAG roda logo em seguida. Derrubar a view e recria-la em minutos
        # e o comportamento correto; manter uma view apontando para uma tabela
        # que sera recriada do zero e que seria perigoso.
        cur.execute(f'DROP TABLE IF EXISTS raw.{table} CASCADE;')
        conn.commit()

        for i, chunk in enumerate(reader):
            if not criada:
                # todas as colunas como TEXT: a camada raw nao interpreta nada
                cols_sql = ", ".join(f'"{c}" TEXT' for c in chunk.columns)
                cur.execute(f"CREATE TABLE raw.{table} ({cols_sql});")
                conn.commit()
                print(f"  tabela raw.{table} criada com {len(chunk.columns)} colunas")
                criada = True

            # serializa o bloco em memoria e entrega ao COPY
            buf = io.StringIO()
            chunk.to_csv(buf, index=False, header=False, na_rep="")
            buf.seek(0)
            cur.copy_expert(
                f"COPY raw.{table} FROM STDIN WITH (FORMAT csv)", buf
            )
            conn.commit()   # commit por bloco: progresso duravel, memoria estavel
            buf.close()

            total += len(chunk)
            print(f"  bloco {i + 1}: +{len(chunk):,} linhas (total {total:,})")

        print(f"OK: {total:,} linhas em raw.{table} em {time.time() - t0:.0f}s")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, choices=list(BASES))
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--path", required=True)
    args = ap.parse_args()
    load(args.base, args.year, args.path)


if __name__ == "__main__":
    main()
