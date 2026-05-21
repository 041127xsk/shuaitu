import sqlite3
conn = sqlite3.connect('data/heroes.db')
total = conn.execute('SELECT COUNT(*) FROM heroes').fetchone()[0]
with_img = conn.execute('SELECT COUNT(*) FROM heroes WHERE four_dimensions_image IS NOT NULL AND four_dimensions_image != ""').fetchone()[0]
print(f'总武将: {total}')
print(f'有四维图: {with_img} ({with_img*100//total}%)')
print(f'无四维图: {total-with_img}')
print()
print('无图武将列表:')
rows = conn.execute('SELECT name FROM heroes WHERE four_dimensions_image IS NULL OR four_dimensions_image = ""').fetchall()
for r in rows:
    print(f'  {r[0]}')
