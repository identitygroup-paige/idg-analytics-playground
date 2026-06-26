from dotenv import load_dotenv
import os
import pandas as pd
import redshift_connector
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

load_dotenv()

REDSHIFT_TABLES = [
    "idg_campus_reference",
    "idg_contact",
    "idg_estimate",
    "idg_invoice",
    "idg_order",
    "idg_sarasota_estimate_line",
]


def get_redshift_connection():
    return redshift_connector.connect(
        iam=True,
        database=os.getenv("REDSHIFT_DATABASE"),
        db_user=os.getenv("REDSHIFT_DB_USER"),
        cluster_identifier=os.getenv("REDSHIFT_CLUSTER_IDENTIFIER"),
        region=os.getenv("REDSHIFT_REGION"),
    )


def get_snowflake_connection():
    conn = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        role=os.getenv("SNOWFLAKE_ROLE"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    )

    cur = conn.cursor()
    cur.execute(f"USE DATABASE {os.getenv('SNOWFLAKE_DATABASE')}")
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {os.getenv('SNOWFLAKE_DATABASE')}.{os.getenv('SNOWFLAKE_SCHEMA')}")
    cur.execute(f"USE SCHEMA {os.getenv('SNOWFLAKE_DATABASE')}.{os.getenv('SNOWFLAKE_SCHEMA')}")
    cur.close()

    return conn


def read_redshift_table(conn, table_name):
    query = f"""
        SELECT *
        FROM public.{table_name}
    """
    return pd.read_sql(query, conn)


def clean_column_names(df):
    df.columns = [c.upper() for c in df.columns]
    return df


def load_to_snowflake(sf_conn, df, table_name):
    table_name = table_name.upper()

    print(f"DataFrame shape for {table_name}: {df.shape}")

    if df.empty:
        print(f"Skipping {table_name}: dataframe is empty")
        return

    success, nchunks, nrows, output = write_pandas(
        conn=sf_conn,
        df=df,
        table_name=table_name,
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
        auto_create_table=True,
        overwrite=True,
        quote_identifiers=False,
    )

    print(f"{table_name}: success={success}, chunks={nchunks}, rows_loaded={nrows}")
    print(output)

    if not success:
        raise RuntimeError(f"Snowflake load failed for {table_name}")


def main():
    redshift_conn = get_redshift_connection()
    snowflake_conn = get_snowflake_connection()

    for table in REDSHIFT_TABLES:
        print(f"Reading Redshift table: public.{table}")
        df = read_redshift_table(redshift_conn, table)
        df = clean_column_names(df)

        print(f"Loading to Snowflake: RAW_REDSHIFT.{table.upper()}")
        load_to_snowflake(snowflake_conn, df, table)

    redshift_conn.close()
    snowflake_conn.close()

    print("Done loading Redshift public tables to Snowflake RAW_REDSHIFT.")


if __name__ == "__main__":
    main()