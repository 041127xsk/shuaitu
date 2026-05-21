import sqlite3
conn = sqlite3.connect('data/intel.db')
cursor = conn.cursor()

# 检查前5个武将的战法数据
cursor.execute('SELECT id, name, skill_name, skill_images_json FROM hero LIMIT 5')
rows = cursor.fetchall()
print('Database hero data:')
for row in rows:
    print('  ID:', row[0], 'Name:', row[1], 'Skill:', row[2], 'Images:', row[3][:50] if row[3] else 'None')

# 统计有战法数据的武将数量
cursor.execute('SELECT COUNT(*) FROM hero WHERE skill_name IS NOT NULL')
print('Heroes with skill:', cursor.fetchone()[0])

cursor.execute('SELECT COUNT(*) FROM hero WHERE skill_images_json IS NOT NULL')
print('Heroes with images:', cursor.fetchone()[0])

conn.close()
