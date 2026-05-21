import sqlite3, os, glob

# Find the db file
db_files = glob.glob(r"E:\openclaw\openclaw-main\*.db")
if not db_files:
    print("No .db files found")
    exit()

db_path = db_files[0]
print(f"Database: {os.path.basename(db_path)}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"Tables: {[t[0] for t in tables]}")

# Count records
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM [{table[0]}]")
    count = cursor.fetchone()[0]
    print(f"  {table[0]}: {count} records")

# Show sample battle report
for table in tables:
    tname = table[0]
    if "battle" in tname.lower() or "report" in tname.lower():
        cursor.execute(f"SELECT * FROM [{tname}] LIMIT 3")
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]
        print(f"\nSample {tname} ({len(rows)} rows):")
        for row in rows:
            d = dict(zip(col_names, row))
            # Print key fields only
            for k in ["battle_id", "attack_name", "defend_name", "attack_union_name", "defend_union_name", "wid_name", "result", "time"]:
                if k in d:
                    print(f"  {k}: {d[k]}")
            print("  ---")

conn.close()
