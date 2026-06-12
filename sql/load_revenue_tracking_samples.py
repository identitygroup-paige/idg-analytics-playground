import os
import pandas as pd
import pyodbc
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()

TARGET_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "DATA_VALIDATION_DEV")
SAMPLE_ROWS = 1000

TABLES = [
    "OrderHeader",
    "OrderValue",
    "OrderTotals",
    "ARTransaction",
    "ARTransactionLine",
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

try:
    sf_cur.execute(f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA}")
    sf_cur.execute(f"USE SCHEMA {TARGET_SCHEMA}")

    for table in TABLES:
        print(f"\n--- Loading {table} ---")

        col_query = f"""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo'
          AND TABLE_NAME = '{table}'
        ORDER BY ORDINAL_POSITION;
        """

        cols_df = pd.read_sql(col_query, sql_conn)

        cols = [
            col for col in cols_df["COLUMN_NAME"].tolist()
            if col not in EXCLUDE_COLUMNS
        ]

        if not cols:
            print(f"No columns found for {table}; skipping.")
            continue

        column_sql = ",\n        ".join(f"[{c}]" for c in cols)

        query = f"""
        SELECT TOP {SAMPLE_ROWS}
            {column_sql}
        FROM dbo.[{table}];
        """
        df = pd.read_sql(query, sql_conn)

        date_col_query = f"""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo'
        AND TABLE_NAME = '{table}'
        AND DATA_TYPE IN (
            'date',
            'datetime',
            'datetime2',
            'smalldatetime',
            'datetimeoffset'
        )
        ORDER BY ORDINAL_POSITION;
        """

        date_cols_df = pd.read_sql(date_col_query, sql_conn)
        date_cols = date_cols_df["COLUMN_NAME"].tolist()
        print(f"Date columns for {table}: {date_cols}")

        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                df.loc[df[col] <= pd.Timestamp("1900-01-01"), col] = pd.NaT
                df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")

        df.columns = [c.upper() for c in df.columns]

        target_table = f"{table.upper()}_SAMPLE"

        success, nchunks, nrows, _ = write_pandas(
            conn=sf_conn,
            df=df,
            table_name=target_table,
            schema=TARGET_SCHEMA,
            auto_create_table=True,
            overwrite=True,
        )

        print(f"{target_table}: success={success}, rows={nrows}")

finally:
    sf_cur.close()
    sf_conn.close()
    sql_conn.close()