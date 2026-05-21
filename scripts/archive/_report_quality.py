"""数据质量统计报告"""
import sys, json
sys.path.insert(0, '.')
from src.database import init_db

db = init_db('data/heroes.db')

# 总数
total = db.execute("SELECT COUNT(*) FROM heroes").fetchone()[0]
with_skill_name = db.execute(
    "SELECT COUNT(*) FROM primary_skills WHERE name != '' AND name IS NOT NULL"
).fetchone()[0]
no_skill_name = total - with_skill_name

print(f"\n=== 数据质量报告 ===")
print(f"  总武将数: {total}")
print(f"  有战法名: {with_skill_name}")
print(f"  无战法名: {no_skill_name}")
print()

# 按 faction 统计
rows = db.execute(
    "SELECT faction, COUNT(*) as cnt FROM heroes GROUP BY faction ORDER BY cnt DESC"
).fetchall()
print("按阵营分布:")
for r in rows:
    print(f"  {r['faction'] or '未知':6} : {r['cnt']} 人")
print()

# 无战法名的
rows = db.execute("""
    SELECT h.name, ps.name as skill_name 
    FROM heroes h
    LEFT JOIN primary_skills ps ON ps.hero_id = h.id
    WHERE ps.name = '' OR ps.name IS NULL
    ORDER BY h.name
""").fetchall()
if rows:
    print(f"战法名为空的武将 ({len(rows)} 个):")
    for r in rows:
        print(f"  {r['name']}")
print()

# 有战法名的样本
rows = db.execute("""
    SELECT h.name, ps.name as skill_name, ps.paragraph_count
    FROM heroes h
    JOIN primary_skills ps ON ps.hero_id = h.id
    WHERE ps.name != '' AND ps.name IS NOT NULL
    ORDER BY ps.paragraph_count DESC
    LIMIT 10
""").fetchall()
print("段落最多的10个武将:")
for r in rows:
    print(f"  {r['name']:8} [{r['skill_name']}]  {r['paragraph_count']}段")

db.close()
