import os
from datetime import datetime, timezone

import pandas as pd
import pyodbc
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()

SOURCE_SCHEMA = "dbo"
TARGET_DATABASE = "DATA_VALIDATION"
TARGET_SCHEMA = "RAW_SQL_SERVER"
DQ_TABLE = "SQLSERVER_SNOWFLAKE_ROWCOUNT_CHECKS"


def clean_name(name: str) -> str:
    return (
        str(name)
        .upper()
        .replace(" ", "_")
        .replace(".", "_")
        .replace("-", "_")
        .replace("/", "_")
    )


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


def get_sql_server_tables():
    query = f"""
    SELECT
        TABLE_SCHEMA,
        TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE = 'BASE TABLE'
      AND TABLE_SCHEMA = '{SOURCE_SCHEMA}'
    ORDER BY TABLE_NAME
    """

    return pd.read_sql(query, sql_server_conn)


def get_sql_server_row_count(source_schema, source_table):
    query = f"""
    SELECT COUNT(*) AS ROW_COUNT
    FROM [{source_schema}].[{source_table}]
    """

    return int(pd.read_sql(query, sql_server_conn).iloc[0]["ROW_COUNT"])


def get_snowflake_row_count(target_table):
    cur = snowflake_conn.cursor()

    try:
        cur.execute(f"""
        SELECT COUNT(*) AS ROW_COUNT
        FROM {TARGET_DATABASE}.{TARGET_SCHEMA}.{target_table}
        """)

        return int(cur.fetchone()[0])

    except Exception:
        return None

    finally:
        cur.close()


def main():
    run_started_at = datetime.now(timezone.utc)

    tables_df = get_sql_server_tables()

    print(f"Found {len(tables_df):,} SQL Server tables in schema {SOURCE_SCHEMA}")

    results = []

    for _, row in tables_df.iterrows():
        source_schema = row["TABLE_SCHEMA"]
        source_table = row["TABLE_NAME"]
        target_table = clean_name(source_table)

        print(f"Checking {source_schema}.{source_table} → {target_table}")

        sql_server_rows = None
        snowflake_rows = None
        status = "UNKNOWN"
        error_message = None

        try:
            sql_server_rows = get_sql_server_row_count(source_schema, source_table)
            snowflake_rows = get_snowflake_row_count(target_table)

            if snowflake_rows is None:
                status = "MISSING_IN_SNOWFLAKE"
            elif sql_server_rows == snowflake_rows:
                status = "PASS"
            elif snowflake_rows == 0 and sql_server_rows > 0:
                status = "SNOWFLAKE_EMPTY_SOURCE_HAS_ROWS"
            else:
                status = "ROW_COUNT_MISMATCH"

        except Exception as e:
            status = "ERROR"
            error_message = str(e)

        results.append(
            {
                "RUN_STARTED_AT_UTC": run_started_at,
                "SOURCE_SCHEMA": source_schema,
                "SOURCE_TABLE": source_table,
                "TARGET_DATABASE": TARGET_DATABASE,
                "TARGET_SCHEMA": TARGET_SCHEMA,
                "TARGET_TABLE": target_table,
                "SQL_SERVER_ROWS": sql_server_rows,
                "SNOWFLAKE_ROWS": snowflake_rows,
                "ROW_COUNT_DIFFERENCE": (
                    None
                    if sql_server_rows is None or snowflake_rows is None
                    else snowflake_rows - sql_server_rows
                ),
                "CHECK_STATUS": status,
                "ERROR_MESSAGE": error_message,
            }
        )

    results_df = pd.DataFrame(results)

    print("\nSummary:")
    print(results_df["CHECK_STATUS"].value_counts(dropna=False))

    write_pandas(
        conn=snowflake_conn,
        df=results_df,
        table_name=DQ_TABLE,
        database=TARGET_DATABASE,
        schema=TARGET_SCHEMA,
        auto_create_table=True,
        overwrite=True,
    )

    print(
        f"\nWrote results to "
        f"{TARGET_DATABASE}.{TARGET_SCHEMA}.{DQ_TABLE}"
    )

    failed_df = results_df[results_df["CHECK_STATUS"] != "PASS"]

    if not failed_df.empty:
        print("\nTables requiring attention:")
        print(
            failed_df[
                [
                    "SOURCE_TABLE",
                    "SQL_SERVER_ROWS",
                    "SNOWFLAKE_ROWS",
                    "ROW_COUNT_DIFFERENCE",
                    "CHECK_STATUS",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    try:
        main()
    finally:
        snowflake_conn.close()
        sql_server_conn.close()