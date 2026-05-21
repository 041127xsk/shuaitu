import sqlite3
import shutil
import os
import glob

db1 = r'E:\openclaw\openclaw-main\tools\歌丨池上#7191611_X5602.db'
db2 = r'E:\openclaw\openclaw-main\stzb-helper-v2\build\bin\game.db'
output = r'E:\openclaw\openclaw-main\战报助手\数据库\歌丨池上#7191611_X5602.db'

print("=== Database Merge Tool ===")
print(f"Source 1: {db1}")
print(f"Source 2: {db2}")
print(f"Output: {output}")

# Check file sizes
print(f"\nSource 1 size: {os.path.getsize(db1)} bytes")
print(f"Source 2 size: {os.path.getsize(db2)} bytes")

# Step 1: Copy db1 to output (as base)
print("\n[1/3] Copying first database to output...")
shutil.copy2(db1, output)
print("Done!")

# Step 2: Merge db2 into output
print("\n[2/3] Merging second database...")
conn_out = sqlite3.connect(output)
conn_in = sqlite3.connect(db2)

cursor_out = conn_out.cursor()
cursor_in = conn_in.cursor()

# Get tables
cursor_in.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor_in.fetchall()

print(f"Tables to process: {len(tables)}")

for table in tables:
    table_name = table[0]
    if table_name == 'sqlite_sequence':
        continue

    # Get row count from source
    cursor_in.execute(f"SELECT COUNT(*) FROM [{table_name}]")
    src_count = cursor_in.fetchone()[0]

    # Get columns
    cursor_in.execute(f"PRAGMA table_info([{table_name}])")
    columns_info = cursor_in.fetchall()
    columns = [col[1] for col in columns_info]
    col_str = ', '.join([f'[{c}]' for c in columns])
    placeholders = ', '.join(['?' for _ in columns])

    # Copy with INSERT OR IGNORE (dedup by primary key)
    cursor_in.execute(f"SELECT * FROM [{table_name}]")
    rows = cursor_in.fetchall()

    if rows:
        insert_sql = f"INSERT OR IGNORE INTO [{table_name}] ({col_str}) VALUES ({placeholders})"
        cursor_out.executemany(insert_sql, rows)

        # Get count after insert
        cursor_out.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        dest_count = cursor_out.fetchone()[0]

        print(f"  {table_name}: {src_count} rows -> {dest_count} total (merged {len(rows)})")

conn_out.commit()
conn_out.close()
conn_in.close()

# Step 3: Verify
print("\n[3/3] Verifying output database...")
conn = sqlite3.connect(output)
cursor = cursor
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("Final table counts:")
total = 0
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM [{table[0]}]")
    count = cursor.fetchone()[0]
    print(f"  {table[0]}: {count}")
    total += count

conn.close()

print(f"\n=== Merge Complete! ===")
print(f"Output size: {os.path.getsize(output)} bytes")
print(f"Total records: {total}")