import sqlite3
import glob

# Find the largest db file in tools directory
db_files = glob.glob(r'E:\openclaw\openclaw-main\tools\*.db')
if db_files:
    db_path = max(db_files, key=lambda f: __import__('os').path.getsize(f))
    print(f'Using: {db_path}')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f'Tables:')
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM [{table[0]}]")
        count = cursor.fetchone()[0]
        print(f'  {table[0]}: {count} records')
    
    conn.close()
else:
    print('No database files found')
