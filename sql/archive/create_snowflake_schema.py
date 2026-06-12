import os
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

# Change this to whatever schema you want to create
SCHEMA_NAME = "DATA_VALIDATION_DEV"

conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    role=os.getenv("SNOWFLAKE_ROLE"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE")
)

try:
    cur = conn.cursor()

    print(f"Creating schema: {SCHEMA_NAME}")

    cur.execute(f"""
        CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}
    """)

    print("Success!")

    cur.execute(f"""
        SHOW SCHEMAS LIKE '{SCHEMA_NAME}'
    """)

    results = cur.fetchall()

    print("\nSchema verification:")
    for row in results:
        print(row)

finally:
    cur.close()
    conn.close()