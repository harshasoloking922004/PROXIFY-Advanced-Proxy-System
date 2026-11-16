import sqlite3

db_path = "database/proxy_history.db"

connection = sqlite3.connect(db_path)
cursor = connection.cursor()

cursor.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
""")

tables = cursor.fetchall()

print("DATABASE TABLES:")
for table in tables:
    print("-", table[0])

for (table_name,) in tables:
    print(f"\nTABLE: {table_name}")

    cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    print("Total records:", cursor.fetchone()[0])

connection.close()