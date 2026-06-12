import os
import pandas as pd
import pyodbc
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()

TARGET_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "DATA_VALIDATION_DEV")
TARGET_TABLE = "ORDER_HEADER_SAMPLE"

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
    schema=TARGET_SCHEMA,
)

cur = snowflake_conn.cursor()

try:
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA}")
    cur.execute(f"USE SCHEMA {TARGET_SCHEMA}")

    query = """
    SELECT TOP 1000
        JobNumber,
        EstimateNumber,
        CustAccount,
        CustName,
        SalesRepCode,
        CSR,
        Estimator,
        JobDescription,
        PONumber,
        PrevPONumber,
        PrevJobNumber,
        OriginalJobNumber,
        DueDate,
        EstimateDate,
        CompleteDate,
        OrderDate,
        JobStatus,
        EstimateStatus,
        EstTimeFrame,
        OrderType,
        RFQ,
        RFQDate,
        ProofDate,
        PriorityLevel,
        QuickOrder,
        Revision,
        RevisionDate,
        RevisionReason,
        TotalOverride,
        UserDefined1,
        UserDefined2,
        UserDefined3,
        UserDefined4,
        UserDefined5,
        CustUserDefined1,
        CustUserDefined2,
        CustUserDefined3,
        TaxCodeA,
        TaxCodeB,
        TaxCodeC,
        TaxCodeD,
        EntryDate,
        TotalComponents,
        BackOrder,
        Prepayment,
        TotalSellPrice,
        OrderSellPrice,
        InvoiceSellPrice,
        TotalFreightCost,
        InvoicedFreightPrice,
        PlantID,
        RFQFlag,
        CalculatedTotalPrice,
        NoDueDate,
        ReorderDate,
        DeliveryDate,
        CreateOpr,
        CreateDatim,
        UpdateOpr,
        Updatedatim,
        Discount,
        TaxJurisdiction,
        ARJobCloseOut,
        OutsideOrder,
        OutsideOrderID,
        RequestForOrder,
        QuoteDueDate,
        DontChargeFreight,
        ManualCommission,
        OriginatedFromRFQ,
        PaymentMethod,
        BackOrderFrom,
        TemplateCode,
        OriginalPlantID,
        OriginalEstimateNumber,
        Archived,
        PODate,
        TaxOverrideAmount,
        SchedulePriority,
        JobPriority,
        JobRouted,
        ManufacturerItemNumber,
        StatusReasonCode,
        CustomerOvers,
        JobTicketPrintDate,
        CustContactID,
        BillContactID,
        EstimateDueDate,
        ArCloseOutOption,
        ID,
        Status,
        CurrencyCode,
        ExchangeRate,
        FromCopy,
        FromEstimate,
        FromOrder,
        PrevEstimateNumber,
        OpportunityFlag,
        AvaTaxOverride,
        ProofCode,
        MDSFStatus
    FROM dbo.OrderHeader
    ORDER BY OrderDate DESC;
    """

    print("Reading OrderHeader sample from SQL Server...")

    df = pd.read_sql(query, sql_server_conn)

    print(f"Rows read from SQL Server: {len(df):,}")
    print(f"Columns read from SQL Server: {len(df.columns):,}")

    # Snowflake likes uppercase column names.
    df.columns = [c.upper() for c in df.columns]

    print(f"Loading to Snowflake table: {TARGET_SCHEMA}.{TARGET_TABLE}")

    success, nchunks, nrows, _ = write_pandas(
        conn=snowflake_conn,
        df=df,
        table_name=TARGET_TABLE,
        schema=TARGET_SCHEMA,
        auto_create_table=True,
        overwrite=True,
    )

    print(f"Load complete: success={success}, chunks={nchunks}, rows={nrows}")

    cur.execute(f"SELECT COUNT(*) FROM {TARGET_SCHEMA}.{TARGET_TABLE}")
    count = cur.fetchone()[0]

    print(f"Snowflake row count: {count:,}")

finally:
    cur.close()
    snowflake_conn.close()
    sql_server_conn.close()