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

successful_tables = []
failed_tables = []

try:
    cur = snowflake_conn.cursor()

    cur.execute(
        f"CREATE SCHEMA IF NOT EXISTS {TARGET_DATABASE}.{TARGET_SCHEMA}"
    )

    cur.execute(
        f"USE SCHEMA {TARGET_DATABASE}.{TARGET_SCHEMA}"
    )

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

    print(
        f"\nFound {len(tables_df):,} tables in SQL Server schema {SOURCE_SCHEMA}"
    )

    for _, row in tables_df.iterrows():

        source_schema = row["TABLE_SCHEMA"]
        source_table = row["TABLE_NAME"]
        target_table = clean_name(source_table)
        staging_table = f"{target_table}__STAGING"

        try:

            print(
                f"\n{'=' * 80}"
            )
            print(
                f"Loading {source_schema}.{source_table}"
            )
            print(
    f"Final target: {TARGET_DATABASE}.{TARGET_SCHEMA}.{target_table}"
    )
            print(
                f"Staging target: {TARGET_DATABASE}.{TARGET_SCHEMA}.{staging_table}"
)

            source_query = f"""
            SELECT *
            FROM [{source_schema}].[{source_table}]
            """

            first_chunk = True
            total_rows = 0
            cur.execute(f"""
            DROP TABLE IF EXISTS {TARGET_DATABASE}.{TARGET_SCHEMA}.{staging_table}
            """)

            for chunk in pd.read_sql(
                source_query,
                sql_server_conn,
                chunksize=CHUNKSIZE
            ):

                chunk.columns = [
                    clean_name(c)
                    for c in chunk.columns
                ]

                success, nchunks, nrows, _ = write_pandas(
                conn=snowflake_conn,
                df=chunk,
                table_name=staging_table,
                database=TARGET_DATABASE,
                schema=TARGET_SCHEMA,
                auto_create_table=True,
                overwrite=first_chunk,
            )

                total_rows += nrows
                first_chunk = False

                print(
                    f"  Loaded chunk rows: {nrows:,}"
                    f" | Running total: {total_rows:,}"
                )
                cur.execute(f"""
                CREATE OR REPLACE TABLE {TARGET_DATABASE}.{TARGET_SCHEMA}.{target_table} AS
                SELECT *
                FROM {TARGET_DATABASE}.{TARGET_SCHEMA}.{staging_table}
                """)

                cur.execute(f"""
                DROP TABLE IF EXISTS {TARGET_DATABASE}.{TARGET_SCHEMA}.{staging_table}
                """)
                print(
                    f"SUCCESS: {source_schema}.{source_table}"
                    f" ({total_rows:,} rows)"
                )

            successful_tables.append(
                {
                    "table": f"{source_schema}.{source_table}",
                    "rows": total_rows,
                }
            )

        except Exception as table_error:

            print(
                f"\nERROR loading "
                f"{source_schema}.{source_table}"
            )

            print(str(table_error))

            failed_tables.append(
                {
                    "table": f"{source_schema}.{source_table}",
                    "error": str(table_error),
                }
            )
            try:
                cur.execute(f"""
                DROP TABLE IF EXISTS {TARGET_DATABASE}.{TARGET_SCHEMA}.{staging_table}
                """)
            except Exception:
                pass
            continue
    validation_rows = []

    print("\nBuilding validation results...")

    for success in successful_tables:
        full_table_name = success["table"]
        source_schema, source_table = full_table_name.split(".")
        target_table = clean_name(source_table)

        sql_count_query = f"""
        SELECT COUNT(*) AS ROW_COUNT
        FROM [{source_schema}].[{source_table}]
        """

        sf_count_query = f"""
        SELECT COUNT(*) AS ROW_COUNT
        FROM {TARGET_DATABASE}.{TARGET_SCHEMA}.{target_table}
        """

        try:
            sql_server_rows = pd.read_sql(sql_count_query, sql_server_conn).iloc[0]["ROW_COUNT"]

            sf_cur = snowflake_conn.cursor()
            sf_cur.execute(sf_count_query)
            snowflake_rows = sf_cur.fetchone()[0]
            sf_cur.close()

            validation_rows.append({
                "SOURCE_SCHEMA": source_schema,
                "SOURCE_TABLE": source_table,
                "TARGET_DATABASE": TARGET_DATABASE,
                "TARGET_SCHEMA": TARGET_SCHEMA,
                "TARGET_TABLE": target_table,
                "SQL_SERVER_ROWS": int(sql_server_rows),
                "SNOWFLAKE_ROWS": int(snowflake_rows),
                "ROW_COUNT_MATCH": int(sql_server_rows) == int(snowflake_rows),
                "LOAD_STATUS": "SUCCESS",
                "ERROR_MESSAGE": None,
            })

        except Exception as validation_error:
            validation_rows.append({
                "SOURCE_SCHEMA": source_schema,
                "SOURCE_TABLE": source_table,
                "TARGET_DATABASE": TARGET_DATABASE,
                "TARGET_SCHEMA": TARGET_SCHEMA,
                "TARGET_TABLE": target_table,
                "SQL_SERVER_ROWS": None,
                "SNOWFLAKE_ROWS": None,
                "ROW_COUNT_MATCH": False,
                "LOAD_STATUS": "VALIDATION_ERROR",
                "ERROR_MESSAGE": str(validation_error),
            })

    for failure in failed_tables:
        source_schema, source_table = failure["table"].split(".")
        target_table = clean_name(source_table)

        validation_rows.append({
            "SOURCE_SCHEMA": source_schema,
            "SOURCE_TABLE": source_table,
            "TARGET_DATABASE": TARGET_DATABASE,
            "TARGET_SCHEMA": TARGET_SCHEMA,
            "TARGET_TABLE": target_table,
            "SQL_SERVER_ROWS": None,
            "SNOWFLAKE_ROWS": None,
            "ROW_COUNT_MATCH": False,
            "LOAD_STATUS": "FAILED",
            "ERROR_MESSAGE": failure["error"],
        })

    validation_df = pd.DataFrame(validation_rows)

    if not validation_df.empty:
        
        write_pandas(
            conn=snowflake_conn,
            df=validation_df,
            table_name="SQLSERVER_LOAD_VALIDATION",
            database=TARGET_DATABASE,
            schema=TARGET_SCHEMA,
            auto_create_table=True,
            overwrite=True,
        )

        print(
            f"Validation table written to "
            f"{TARGET_DATABASE}.{TARGET_SCHEMA}.SQLSERVER_LOAD_VALIDATION"
        )
        
    print("\n")
    print("=" * 80)
    print("LOAD SUMMARY")
    print("=" * 80)

    print(
        f"Successful tables: {len(successful_tables):,}"
    )

    print(
        f"Failed tables: {len(failed_tables):,}"
    )

    if failed_tables:

        print("\nFAILED TABLES")

        for failure in failed_tables:
            print(
                f"- {failure['table']}"
            )

finally:

    try:
        cur.close()
    except:
        pass

    snowflake_conn.close()
    sql_server_conn.close()