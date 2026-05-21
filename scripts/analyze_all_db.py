import sqlite3, os, glob

db_files = glob.glob(r"E:\openclaw\openclaw-main\**\*.db", recursive=True)

for db_path in db_files:
    if not os.path.exists(db_path):
        continue
    size = os.path.getsize(db_path)
    if size < 1000:  # Skip tiny files
        continue
        
    print(f"\n{'='*50}")
    print(f"File: {os.path.basename(db_path)}")
    print(f"Path: {db_path}")
    print(f"Size: {size / 1024:.1f} KB")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        
        for table in tables:
            if table == 'sqlite_sequence':
                continue
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
                count = cursor.fetchone()[0]
                if count > 0:
                    print(f"  {table}: {count} records")
            except Exception as e:
                print(f"  {table}: error - {e}")
        
        conn.close()
    except Exception as e:
        print(f"  Error: {e}")
