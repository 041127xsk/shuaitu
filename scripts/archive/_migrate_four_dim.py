import sqlite3, sys
sys.path.insert(0, '.')
from src.database import init_db

conn = init_db()
# 迁移：给已有 DB 补列（幂等）
try:
    conn.execute("ALTER TABLE heroes ADD COLUMN four_dimensions_image TEXT")
    conn.commit()
    print("ALTER TABLE heroes ADD COLUMN four_dimensions_image OK")
except Exception as e:
    print(f"ALTER TABLE: {e}")

# 验证
cols = [r[1] for r in conn.execute("PRAGMA table_info(heroes)")]
print("heroes 列:", cols)
