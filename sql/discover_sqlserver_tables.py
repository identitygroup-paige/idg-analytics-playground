import pandas as pd

query = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    SUM(p.rows) AS row_count
FROM sys.tables t
JOIN sys.schemas s
    ON t.schema_id = s.schema_id
JOIN sys.partitions p
    ON t.object_id = p.object_id
WHERE p.index_id IN (0,1)
GROUP BY
    s.name,
    t.name
ORDER BY row_count DESC
"""

df = pd.read_sql(query, sql_conn)

print(df.head(20))