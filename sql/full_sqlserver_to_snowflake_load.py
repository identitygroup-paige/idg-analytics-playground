import os
import pandas as pd
import pyodbc
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()

SOURCE_SCHEMA = "dbo"
TARGET_DATABASE = "DATA_VALIDATION"
TARGET_SCHEMA = "RAW_SQL_SERVER"
CHUNKSIZE = 100000

sql_server_conn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={os.getenv('SQL_SERVER')};"
    f"DATABASE={os.getenv('SQL_DATABASE')};"
    f"UID={os.getenv('SQL_USERNAME')};"
    f"PWD={os.getenv('SQL_PASSWORD')};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

snowflake_conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    role=os.getenv("SNOWFLAKE_ROLE"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=TARGET_DATABASE,
)

def clean_name(name: str) -> str:
    return (
        str(name)
        .upper()
        .replace(" ", "_")
        .replace(".", "_")
        .replace("-", "_")
        .replace("/", "_")
    )

try:
    cur = snowflake_conn.cursor()
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {TARGET_DATABASE}.{TARGET_SCHEMA}")
    cur.execute(f"USE SCHEMA {TARGET_DATABASE}.{TARGET_SCHEMA}")

    table_query = f"""
    SELECT
        TABLE_SCHEMA,
        TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE = 'BASE TABLE'
      AND TABLE_SCHEMA = '{SOURCE_SCHEMA}'
    ORDER BY TABLE_NAME
    """

    tables_df = pd.read_sql(table_query, sql_server_conn)

    for _, row in tables_df.iterrows():
        source_schema = row["TABLE_SCHEMA"]
        source_table = row["TABLE_NAME"]
        target_table = clean_name(source_table)

        print(f"\nLoading {source_schema}.{source_table} → {TARGET_DATABASE}.{TARGET_SCHEMA}.{target_table}")

        source_query = f"""
        SELECT *
        FROM [{source_schema}].[{source_table}]
        """

        first_chunk = True
        total_rows = 0

        for chunk in pd.read_sql(source_query, sql_server_conn, chunksize=CHUNKSIZE):
            chunk.columns = [clean_name(c) for c in chunk.columns]

            success, nchunks, nrows, _ = write_pandas(
                conn=snowflake_conn,
                df=chunk,
                table_name=target_table,
                database=TARGET_DATABASE,
                schema=TARGET_SCHEMA,
                auto_create_table=True,
                overwrite=first_chunk,
            )

            total_rows += nrows
            first_chunk = False

            print(f"  Loaded chunk rows: {nrows:,} | total: {total_rows:,}")

        print(f"Finished {source_schema}.{source_table}: {total_rows:,} rows")

finally:
    snowflake_conn.close()
    sql_server_conn.close()