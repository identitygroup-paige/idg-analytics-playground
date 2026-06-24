import os
from pathlib import Path

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

DATABASE = "DATA_VALIDATION"
SCHEMA = "MART_REVENUE"
OUTPUT_DIR = Path("exports/view_ddls")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    role=os.getenv("SNOWFLAKE_ROLE"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=DATABASE,
    schema=SCHEMA,
)

try:
    cur = conn.cursor()

    cur.execute(f"""
        SELECT TABLE_NAME
        FROM {DATABASE}.INFORMATION_SCHEMA.VIEWS
        WHERE TABLE_SCHEMA = '{SCHEMA}'
        ORDER BY TABLE_NAME
    """)

    views = [row[0] for row in cur.fetchall()]

    inventory = []

    combined_sql = []

    for view_name in views:
        cur.execute(f"SELECT GET_DDL('VIEW', '{DATABASE}.{SCHEMA}.{view_name}')")
        ddl = cur.fetchone()[0]

        file_path = OUTPUT_DIR / f"{view_name}.sql"
        file_path.write_text(ddl + ";\n", encoding="utf-8")

        combined_sql.append(f"-- {'=' * 80}")
        combined_sql.append(f"-- {DATABASE}.{SCHEMA}.{view_name}")
        combined_sql.append(f"-- {'=' * 80}")
        combined_sql.append(ddl + ";")
        combined_sql.append("")

        inventory.append({
            "DATABASE": DATABASE,
            "SCHEMA": SCHEMA,
            "VIEW_NAME": view_name,
            "SQL_FILE": str(file_path),
        })

    combined_path = OUTPUT_DIR / "all_mart_revenue_view_ddls.sql"
    combined_path.write_text("\n".join(combined_sql), encoding="utf-8")

    inventory_df = pd.DataFrame(inventory)
    inventory_df.to_csv(OUTPUT_DIR / "view_inventory.csv", index=False)

    print(f"Exported {len(views)} views.")
    print(f"Combined SQL: {combined_path}")
    print(f"Inventory CSV: {OUTPUT_DIR / 'view_inventory.csv'}")

finally:
    conn.close()