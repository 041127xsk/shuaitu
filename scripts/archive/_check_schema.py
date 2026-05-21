import sqlite3
conn = sqlite3.connect('data/heroes.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('表列表:', [t[0] for t in tables])
print()
for t in tables:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t[0]})")]
    print(f'{t[0]:30s}: {cols}')
print()
row = conn.execute('SELECT * FROM heroes LIMIT 1').fetchone()
print('heroes 样本 (tuple):', row)
