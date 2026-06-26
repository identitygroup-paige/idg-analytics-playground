from dotenv import load_dotenv
import os

load_dotenv()

print("DB:", os.getenv("REDSHIFT_DATABASE"))
print("Cluster:", os.getenv("REDSHIFT_CLUSTER_IDENTIFIER"))

from dotenv import load_dotenv
import os
import redshift_connector

load_dotenv()

conn = redshift_connector.connect(
    iam=True,
    database=os.getenv("REDSHIFT_DATABASE"),
    cluster_identifier=os.getenv("REDSHIFT_CLUSTER_IDENTIFIER"),
    db_user=os.getenv("REDSHIFT_DB_USER"),
    region=os.getenv("REDSHIFT_REGION"),
)

cursor = conn.cursor()

cursor.execute("""
SELECT
    current_database(),
    current_user,
    current_schema;
""")

print(cursor.fetchall())

cursor.close()
conn.close()