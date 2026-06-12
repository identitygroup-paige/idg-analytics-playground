import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

server = os.getenv("SQL_SERVER")
database = os.getenv("SQL_DATABASE")
username = os.getenv("SQL_USERNAME")
password = os.getenv("SQL_PASSWORD")

connection_string = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={password};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

print("Attempting connection...")

conn = pyodbc.connect(connection_string)

print("SUCCESS: connected to SQL Server.")

cursor = conn.cursor()

cursor.execute("""
SELECT TOP 10
    TABLE_SCHEMA,
    TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
ORDER BY TABLE_SCHEMA, TABLE_NAME;
""")

rows = cursor.fetchall()

print("\nFirst 10 tables:")
for row in rows:
    print(f"{row.TABLE_SCHEMA}.{row.TABLE_NAME}")

conn.close()