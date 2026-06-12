import os
import pandas as pd
import pyodbc
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()

TARGET_SCHEMA = "DATA_VALIDATION_DEV"

# -----------------------------
# SQL Server connection
# -----------------------------

sql_server_conn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={os.getenv('SQL_SERVER')};"
    f"DATABASE={os.getenv('SQL_DATABASE')};"
    f"UID={os.getenv('SQL_USERNAME')};"
    f"PWD={os.getenv('SQL_PASSWORD')};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

# -----------------------------
# Snowflake connection
# -----------------------------

snowflake_conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    role=os.getenv("SNOWFLAKE_ROLE"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
)

cur = snowflake_conn.cursor()

try:
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA}")
    cur.execute(f"USE SCHEMA {TARGET_SCHEMA}")

    # -----------------------------
    # Query 1: database dictionary
    # -----------------------------

    database_dictionary_query = """
    SELECT
        TABLE_SCHEMA,
        TABLE_NAME,
        COLUMN_NAME,
        DATA_TYPE,
        CHARACTER_MAXIMUM_LENGTH,
        NUMERIC_PRECISION,
        NUMERIC_SCALE,
        IS_NULLABLE,
        ORDINAL_POSITION
    FROM INFORMATION_SCHEMA.COLUMNS
    ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
    """

    database_dictionary_df = pd.read_sql(
        database_dictionary_query,
        sql_server_conn
    )

    database_dictionary_df.columns = [
        c.upper().replace(" ", "_")
        for c in database_dictionary_df.columns
    ]

    success, nchunks, nrows, _ = write_pandas(
        conn=snowflake_conn,
        df=database_dictionary_df,
        table_name="DATABASE_DICTIONARY",
        schema=TARGET_SCHEMA,
        auto_create_table=True,
        overwrite=True,
    )

    print(f"DATABASE_DICTIONARY loaded: success={success}, rows={nrows}")

    # -----------------------------
    # Query 2: table row counts
    # -----------------------------

    table_row_counts_query = """
    SELECT
        s.name AS TABLE_SCHEMA,
        t.name AS TABLE_NAME,
        SUM(p.rows) AS ROW_COUNT
    FROM sys.tables t
    INNER JOIN sys.schemas s
        ON t.schema_id = s.schema_id
    INNER JOIN sys.partitions p
        ON t.object_id = p.object_id
    WHERE p.index_id IN (0, 1)
    GROUP BY
        s.name,
        t.name
    ORDER BY ROW_COUNT DESC
    """

    table_row_counts_df = pd.read_sql(
        table_row_counts_query,
        sql_server_conn
    )

    table_row_counts_df.columns = [
        c.upper().replace(" ", "_")
        for c in table_row_counts_df.columns
    ]

    success, nchunks, nrows, _ = write_pandas(
        conn=snowflake_conn,
        df=table_row_counts_df,
        table_name="TABLE_ROW_COUNTS",
        schema=TARGET_SCHEMA,
        auto_create_table=True,
        overwrite=True,
    )

    print(f"TABLE_ROW_COUNTS loaded: success={success}, rows={nrows}")

finally:
    cur.close()
    snowflake_conn.close()
    sql_server_conn.close()

import pandas as pd

query = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    SUM(p.rows) AS row_count
FROM sys.tables t
JOIN sys.schemas s
    ON t.schema_id = s.schema_id
JOIN sys.partitions p
    ON t.object_id = p.object_id
WHERE p.index_id IN (0,1)
GROUP BY
    s.name,
    t.name
ORDER BY row_count DESC
"""

df = pd.read_sql(query, sql_conn)

print(df.head(20))