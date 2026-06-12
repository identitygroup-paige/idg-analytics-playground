import os
import pandas as pd
import pyodbc
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()

TARGET_SCHEMA = "RAW_SQLSERVER"
CHUNK_SIZE = 100_000

TABLES = [
    "ARTransactionLine",
    "ARTransaction",
    "OrderHeader",
    "Customer",
    "Shipment",
]

EXCLUDE_COLUMNS = {
    "CC_Number",
    "CC_NameOnCard",
    "CC_Expiration",
    "CC_Exp_Month",
    "CC_Exp_Year",
    "MNotes",
    "MJobDetailDescription",
    "MScheduleNotes",
    "Notes",
    "ProofComments",
    "BindInstructions",
}

sql_conn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={os.getenv('SQL_SERVER')};"
    f"DATABASE={os.getenv('SQL_DATABASE')};"
    f"UID={os.getenv('SQL_USERNAME')};"
    f"PWD={os.getenv('SQL_PASSWORD')};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

sf_conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    role=os.getenv("SNOWFLAKE_ROLE"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    schema=TARGET_SCHEMA,
)

sf_cur = sf_conn.cursor()


def get_columns(table):
    query = f"""
    SELECT COLUMN_NAME
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo'
      AND TABLE_NAME = '{table}'
    ORDER BY ORDINAL_POSITION;
    """
    df = pd.read_sql(query, sql_conn)

    return [
        col for col in df["COLUMN_NAME"].tolist()
        if col not in EXCLUDE_COLUMNS
    ]


def clean_dates(df):
    for col in df.columns:
        col_upper = col.upper()
        if (
            "DATE" in col_upper
            or "DATIM" in col_upper
            or col_upper.endswith("TIME")
        ):
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                df.loc[df[col] <= pd.Timestamp("1900-01-01"), col] = pd.NaT
                df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
    return df


def prep(df):
    df = clean_dates(df)
    df.columns = [c.upper() for c in df.columns]
    return df


def load_table(table):
    target_table = table.upper()

    print(f"\n=== Loading {table} → {TARGET_SCHEMA}.{target_table} ===")

    cols = get_columns(table)
    column_sql = ",\n        ".join(f"[{c}]" for c in cols)

    source_query = f"""
    SELECT
        {column_sql}
    FROM dbo.[{table}];
    """

    first_chunk = True
    total_rows = 0

    for chunk in pd.read_sql(source_query, sql_conn, chunksize=CHUNK_SIZE):
        chunk = prep(chunk)

        success, nchunks, nrows, _ = write_pandas(
            conn=sf_conn,
            df=chunk,
            table_name=target_table,
            schema=TARGET_SCHEMA,
            auto_create_table=True,
            overwrite=first_chunk,
        )

        total_rows += nrows

        print(
            f"{target_table}: chunk rows={nrows:,}, "
            f"total loaded={total_rows:,}, success={success}"
        )

        first_chunk = False

    print(f"Finished {target_table}: {total_rows:,} rows loaded.")


try:
    sf_cur.execute(f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA}")
    sf_cur.execute(f"USE SCHEMA {TARGET_SCHEMA}")

    for table in TABLES:
        load_table(table)

finally:
    sf_cur.close()
    sf_conn.close()
    sql_conn.close()