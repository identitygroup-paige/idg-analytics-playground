import os
import pandas as pd
import pyodbc
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()

TARGET_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "DATA_VALIDATION_DEV")
SAMPLE_ROWS = 1000

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


def clean_dates(df):
    for col in df.columns:
        if "DATE" in col.upper() or "DATIM" in col.upper() or "TIME" in col.upper():
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


def load_to_snowflake(df, table_name):
    success, nchunks, nrows, _ = write_pandas(
        conn=sf_conn,
        df=df,
        table_name=table_name,
        schema=TARGET_SCHEMA,
        auto_create_table=True,
        overwrite=True,
    )
    print(f"{table_name}: success={success}, rows={nrows}")


try:
    sf_cur.execute(f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA}")
    sf_cur.execute(f"USE SCHEMA {TARGET_SCHEMA}")

    print("Loading driver invoice lines...")

    ar_line_query = f"""
    SELECT TOP {SAMPLE_ROWS}
        *
    FROM dbo.ARTransactionLine
    WHERE JobNumber IS NOT NULL
      AND TransactionNumber IS NOT NULL
    ORDER BY TransactionNumber DESC;
    """

    ar_line_df = pd.read_sql(ar_line_query, sql_conn)
    ar_line_df = prep(ar_line_df)

    load_to_snowflake(ar_line_df, "COORD_ARTRANSACTIONLINE_SAMPLE")

    job_numbers = ar_line_df["JOBNUMBER"].dropna().astype(str).unique().tolist()
    transaction_numbers = ar_line_df["TRANSACTIONNUMBER"].dropna().astype(str).unique().tolist()

    print(f"Distinct job numbers: {len(job_numbers):,}")
    print(f"Distinct transaction numbers: {len(transaction_numbers):,}")

    job_list = ",".join(f"'{j.replace(chr(39), chr(39)+chr(39))}'" for j in job_numbers)
    transaction_list = ",".join(f"'{t.replace(chr(39), chr(39)+chr(39))}'" for t in transaction_numbers)

    print("Loading matching AR transactions...")

    ar_header_query = f"""
    SELECT *
    FROM dbo.ARTransaction
    WHERE CAST(TransactionNumber AS varchar(50)) IN ({transaction_list});
    """

    ar_header_df = pd.read_sql(ar_header_query, sql_conn)
    ar_header_df = prep(ar_header_df)

    load_to_snowflake(ar_header_df, "COORD_ARTRANSACTION_SAMPLE")

    print("Loading matching order headers...")

    order_header_query = f"""
    SELECT *
    FROM dbo.OrderHeader
    WHERE JobNumber IN ({job_list});
    """

    order_header_df = pd.read_sql(order_header_query, sql_conn)
    order_header_df = prep(order_header_df)

    # Drop sensitive payment fields if present
    sensitive_cols = [
        "CC_NUMBER",
        "CC_NAMEONCARD",
        "CC_EXPIRATION",
        "CC_EXP_MONTH",
        "CC_EXP_YEAR",
    ]
    order_header_df = order_header_df.drop(
        columns=[c for c in sensitive_cols if c in order_header_df.columns],
        errors="ignore"
    )

    load_to_snowflake(order_header_df, "COORD_ORDERHEADER_SAMPLE")

    cust_accounts = order_header_df["CUSTACCOUNT"].dropna().astype(str).unique().tolist()

    if cust_accounts:
        cust_list = ",".join(f"'{c.replace(chr(39), chr(39)+chr(39))}'" for c in cust_accounts)

        print("Loading matching customers...")

        customer_key_options = [
            "CustAccount",
            "Account",
            "CustomerAccount",
            "CustomerNumber",
            "CustomerID",
            "CustID",
        ]

        customer_cols_query = """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo'
          AND TABLE_NAME = 'Customer'
        ORDER BY ORDINAL_POSITION;
        """

        customer_cols_df = pd.read_sql(customer_cols_query, sql_conn)
        customer_cols = customer_cols_df["COLUMN_NAME"].tolist()

        customer_key = None

        for candidate in customer_key_options:
            if candidate in customer_cols:
                customer_key = candidate
                break

        if customer_key is None:
            print("Could not find a customer key column. Available Customer columns:")
            print(customer_cols)
        else:
            print(f"Using Customer key column: {customer_key}")

            customer_query = f"""
            SELECT *
            FROM dbo.Customer
            WHERE [{customer_key}] IN ({cust_list});
            """

            customer_df = pd.read_sql(customer_query, sql_conn)
            customer_df = prep(customer_df)

            load_to_snowflake(customer_df, "COORD_CUSTOMER_SAMPLE")

    print("Loading matching shipments...")

    shipment_query = f"""
    SELECT *
    FROM dbo.Shipment
    WHERE JobNumber IN ({job_list});
    """

    shipment_df = pd.read_sql(shipment_query, sql_conn)
    shipment_df = prep(shipment_df)

    load_to_snowflake(shipment_df, "COORD_SHIPMENT_SAMPLE")

finally:
    sf_cur.close()
    sf_conn.close()
    sql_conn.close()