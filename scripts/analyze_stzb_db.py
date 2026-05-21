"""Analyze stzbHelper database schema and sample data."""
import sqlite3, os, glob, json

db_files = glob.glob(r"E:\openclaw\openclaw-main\*.db")
if not db_files:
    print("No .db files found")
    exit()

db_path = db_files[0]
print(f"Database: {os.path.basename(db_path)}")
print(f"Size: {os.path.getsize(db_path) / 1024:.1f} KB")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [t[0] for t in cursor.fetchall()]
print(f"\nTables: {tables}")

# For each table, show schema and stats
for table in tables:
    if table == "sqlite_sequence":
        continue
    
    print(f"\n{'='*60}")
    print(f"Table: {table}")
    
    # Schema
    cursor.execute(f"PRAGMA table_info([{table}])")
    columns = cursor.fetchall()
    print(f"Columns ({len(columns)}):")
    for col in columns:
        cid, name, dtype, notnull, default, pk = col
        pk_str = " [PK]" if pk else ""
        null_str = " NOT NULL" if notnull else ""
        default_str = f" DEFAULT {default}" if default else ""
        print(f"  {name}: {dtype}{pk_str}{null_str}{default_str}")
    
    # Count
    cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
    count = cursor.fetchone()[0]
    print(f"Records: {count}")
    
    # Sample data (first 2 rows)
    if count > 0:
        cursor.execute(f"SELECT * FROM [{table}] LIMIT 2")
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]
        print(f"Sample data:")
        for i, row in enumerate(rows):
            print(f"  Row {i+1}:")
            for k, v in zip(col_names, row):
                if isinstance(v, str) and len(v) > 100:
                    v = v[:100] + "..."
                print(f"    {k}: {v}")

# Focus on battle_report - show all column names and sample with hero info
print(f"\n{'='*60}")
print("BATTLE REPORT - Detailed Analysis")
cursor.execute("SELECT * FROM battle_report LIMIT 1")
row = cursor.fetchone()
col_names = [desc[0] for desc in cursor.description]
if row:
    for k, v in zip(col_names, row):
        if isinstance(v, str) and len(v) > 200:
            v = v[:200] + "..."
        print(f"  {k}: {v}")

conn.close()
