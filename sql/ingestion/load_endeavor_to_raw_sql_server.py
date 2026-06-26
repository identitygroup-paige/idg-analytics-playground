import os
import re
from datetime import datetime, UTC

datetime.now(UTC)

import pandas as pd
import pyodbc
import snowflake.connector
from dotenv import load_dotenv
from snowflake.connector.pandas_tools import write_pandas
from cryptography.hazmat.primitives import serialization


load_dotenv()


# ----------------------------
# Config
# ----------------------------

SOURCE_SCHEMA = os.getenv("ENDEAVOR_SOURCE_SCHEMA", "dbo")
TARGET_DATABASE = os.getenv("SNOWFLAKE_DATABASE", "DATA_VALIDATION")
TARGET_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "RAW_SQL_SERVER")
TABLE_SUFFIX = "_ENDEAV"
CHUNK_SIZE = int(os.getenv("ENDEAVOR_CHUNK_SIZE", "50000"))

# Optional: comma-separated list, e.g. Customer,OrderHeader,Shipment
INCLUDE_TABLES = os.getenv("ENDEAVOR_INCLUDE_TABLES", "").strip()


# ----------------------------
# Connections
# ----------------------------

def get_sql_server_connection():
    server = os.getenv("ENDEAVOR_SQL_SERVER")
    database = os.getenv("ENDEAVOR_SQL_DATABASE")
    user = os.getenv("ENDEAVOR_SQL_USER")
    password = os.getenv("ENDEAVOR_SQL_PASSWORD")

    if not all([server, database, user, password]):
        raise ValueError("Missing one or more Endeavor SQL Server environment variables.")

    conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )

    return pyodbc.connect(conn_str)


def get_snowflake_connection():
    private_key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    private_key_passphrase = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")

    with open(private_key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=private_key_passphrase.encode(),
        )

    private_key_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        private_key=private_key_der,
        role=os.getenv("SNOWFLAKE_ROLE"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=TARGET_DATABASE,
        schema=TARGET_SCHEMA,
    )

# ----------------------------
# Helpers
# ----------------------------

SNOWFLAKE_RESERVED_WORDS = {
    "START", "END", "TEXT", "DATE", "TIME", "TIMESTAMP",
    "USER", "CURRENT", "GROUP", "ORDER", "BY", "SELECT",
    "FROM", "WHERE", "TABLE", "COLUMN", "VALUE", "VALUES"
}

def clean_identifier(name: str) -> str:
    name = str(name).upper()
    name = re.sub(r"[^A-Z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")

    if not name:
        name = "UNNAMED_COL"

    if name[0].isdigit():
        name = f"COL_{name}"

    if name in SNOWFLAKE_RESERVED_WORDS:
        name = f"{name}_COL"

    return name

def clean_blank_strings(chunk):
    object_cols = chunk.select_dtypes(include=["object"]).columns

    for col in object_cols:
        chunk[col] = chunk[col].replace(r"^\s*$", None, regex=True)

    return chunk

def get_datetime_columns(sql_conn, table_name):
    query = """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ?
          AND TABLE_NAME = ?
          AND DATA_TYPE IN (
              'date',
              'datetime',
              'datetime2',
              'smalldatetime',
              'datetimeoffset',
              'time'
          );
    """
    df = pd.read_sql(query, sql_conn, params=[SOURCE_SCHEMA, table_name])
    return {clean_identifier(c) for c in df["COLUMN_NAME"].tolist()}

def get_source_tables(sql_conn):
    if INCLUDE_TABLES:
        tables = [t.strip() for t in INCLUDE_TABLES.split(",") if t.strip()]
        return tables

    query = """
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = ?
          AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME;
    """

    df = pd.read_sql(query, sql_conn, params=[SOURCE_SCHEMA])
    return df["TABLE_NAME"].tolist()


def create_target_schema(sf_conn):
    with sf_conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {TARGET_DATABASE}.{TARGET_SCHEMA}")
        cur.execute(f"USE DATABASE {TARGET_DATABASE}")
        cur.execute(f"USE SCHEMA {TARGET_SCHEMA}")


def get_row_count_sql_server(sql_conn, table_name):
    query = f"SELECT COUNT(*) AS ROW_COUNT FROM [{SOURCE_SCHEMA}].[{table_name}]"
    return int(pd.read_sql(query, sql_conn)["ROW_COUNT"].iloc[0])

def normalize_chunk_for_raw_load(chunk, datetime_cols):
    for col in chunk.columns:
        if col in datetime_cols:
            chunk[col] = pd.to_datetime(chunk[col], errors="coerce")
        else:
            chunk[col] = chunk[col].astype("string")
            chunk[col] = chunk[col].replace(r"^\s*$", pd.NA, regex=True)

    return chunk

def load_table(sql_conn, sf_conn, table_name):
    source_table = f"[{SOURCE_SCHEMA}].[{table_name}]"
    target_table = clean_identifier(f"{table_name}{TABLE_SUFFIX}")

    print(f"\nLoading {source_table} → {TARGET_DATABASE}.{TARGET_SCHEMA}.{target_table}")

    source_count = get_row_count_sql_server(sql_conn, table_name)
    print(f"Source row count: {source_count}")

    if source_count == 0:
        print(f"Skipping {table_name}: source table is empty.")
        return

    # Replace target table on first chunk, append after that
    first_chunk = True
    total_loaded = 0

    query = f"SELECT * FROM {source_table}"

    datetime_cols = get_datetime_columns(sql_conn, table_name)

    for chunk in pd.read_sql(query, sql_conn, chunksize=CHUNK_SIZE):
        chunk.columns = [clean_identifier(c) for c in chunk.columns]

        chunk = normalize_chunk_for_raw_load(chunk, datetime_cols)

        chunk["_SOURCE_SYSTEM"] = "ENDEAVOR"
        chunk["_SOURCE_DATABASE"] = os.getenv("ENDEAVOR_SQL_DATABASE")
        chunk["_SOURCE_SCHEMA"] = SOURCE_SCHEMA
        chunk["_SOURCE_TABLE"] = table_name
        chunk["_INGESTED_AT"] = datetime.now(UTC)

        print(chunk.columns.tolist())

        success, nchunks, nrows, output = write_pandas(
            conn=sf_conn,
            df=chunk,
            table_name=target_table,
            database=TARGET_DATABASE,
            schema=TARGET_SCHEMA,
            auto_create_table=True,
            overwrite=first_chunk,
            quote_identifiers=False,
            use_logical_type=True,
        )

        if not success:
            raise RuntimeError(f"Snowflake write_pandas failed for {target_table}: {output}")

        total_loaded += nrows
        first_chunk = False

        print(f"Loaded chunk rows: {nrows}; total loaded so far: {total_loaded}")

    print(f"Finished {target_table}: {total_loaded} rows loaded.")


def validate_loaded_tables(sf_conn):
    query = f"""
        SELECT
            TABLE_SCHEMA,
            TABLE_NAME,
            ROW_COUNT
        FROM {TARGET_DATABASE}.INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = '{TARGET_SCHEMA}'
          AND TABLE_NAME ILIKE '%{TABLE_SUFFIX}'
        ORDER BY TABLE_NAME;
    """

    with sf_conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    print("\nSnowflake validation:")
    for row in rows:
        print(row)


# ----------------------------
# Main
# ----------------------------

def main():
    sql_conn = get_sql_server_connection()
    sf_conn = get_snowflake_connection()

    try:
        create_target_schema(sf_conn)

        tables = get_source_tables(sql_conn)
        print(f"Found {len(tables)} tables in SQL Server schema {SOURCE_SCHEMA}.")

        for table in tables:
            load_table(sql_conn, sf_conn, table)

        validate_loaded_tables(sf_conn)

    finally:
        sql_conn.close()
        sf_conn.close()


if __name__ == "__main__":
    main()