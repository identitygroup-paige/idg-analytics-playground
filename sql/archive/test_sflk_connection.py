import os
from dotenv import load_dotenv
import snowflake.connector

load_dotenv()

print("Account:", os.getenv("SNOWFLAKE_ACCOUNT"))
print("User:", os.getenv("SNOWFLAKE_USER"))
print("Role:", os.getenv("SNOWFLAKE_ROLE"))
print("Warehouse:", os.getenv("SNOWFLAKE_WAREHOUSE"))
print("Database:", os.getenv("SNOWFLAKE_DATABASE"))
print("Schema:", os.getenv("SNOWFLAKE_SCHEMA"))

conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    role=os.getenv("SNOWFLAKE_ROLE"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
)

cur = conn.cursor()

cur.execute("""
SELECT
    CURRENT_ACCOUNT(),
    CURRENT_USER(),
    CURRENT_ROLE(),
    CURRENT_WAREHOUSE(),
    CURRENT_DATABASE(),
    CURRENT_SCHEMA()
""")

print(cur.fetchone())

cur.execute("CREATE SCHEMA IF NOT EXISTS DATA_VALIDATION_DEV")
print("Schema created or already exists.")

cur.close()
conn.close()



