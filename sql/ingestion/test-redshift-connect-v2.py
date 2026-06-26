from dotenv import load_dotenv
import os
import redshift_connector

load_dotenv()

conn = redshift_connector.connect(
    iam=True,
    database=os.getenv("REDSHIFT_DATABASE"),
    db_user=os.getenv("REDSHIFT_DB_USER"),
    cluster_identifier=os.getenv("REDSHIFT_CLUSTER_IDENTIFIER"),
    region=os.getenv("REDSHIFT_REGION"),
)

cursor = conn.cursor()
cursor.execute("""
SELECT
    current_database() AS database_name,
    current_user AS user_name,
    current_schema() AS schema_name;
""")
print(cursor.fetchall())


cursor.close()
conn.close()