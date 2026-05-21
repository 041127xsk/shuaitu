"""
import_intel_helper.py - 将 intel-helper 的武将数据导入 heroes.db
================================================================
用法：
    python scripts/import_intel_helper.py
    python scripts/import_intel_helper.py --json intel-helper/exports/2026-04-27_003000/hero.json
    python scripts/import_intel_helper.py --dry-run    # 只预览，不写入

说明：
- 将 intel-helper 的 122 个武将（含 attack/defense/speed）导入 heroes.db
- 以 hero_name 作为匹配键，更新已有记录的属性字段
- 新增 heroes.db 中不存在的武将（无 feed_id，用 name 去重）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.database import get_connection, init_db, migrate_hero_attribute_fields

DEFAULT_JSON = ROOT / "intel-helper" / "exports" / "2026-04-27_003000" / "hero.json"
DEFAULT_DB = ROOT / "data" / "heroes.db"

# intel-helper 阵营名映射到 heroes.db 的阵营名
CAMP_MAP = {
    "魏": "魏",
    "蜀": "蜀",
    "吴": "吴",
    "群": "群",
    "汉": "汉",
    "晋": "晋",
}


def load_intel_heroes(json_path: Path) -> list[dict]:
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def import_intel_heroes(heroes: list[dict], conn, dry_run: bool = False) -> tuple[int, int, int]:
    """
    导入 intel-helper 武将数据。
    返回 (更新数, 新增数, 跳过数)。
    """
    updated, inserted, skipped = 0, 0, 0

    for hero in heroes:
        name = hero.get("name", "").strip()
        if not name:
            skipped += 1
            continue

        attack = hero.get("attack")
        defense = hero.get("defense")
        speed = hero.get("speed")
        camp = CAMP_MAP.get(hero.get("camp", ""), hero.get("camp", ""))
        troop_type = hero.get("troop_type", "")
        tags = ",".join(hero.get("tags", []))

        # 检查是否已有同名武将
        existing = conn.execute(
            "SELECT id, attack, defense, speed FROM heroes WHERE name = ?", (name,)
        ).fetchone()

        if existing:
            # 更新已有记录的属性（仅当现有值为空时）
            if existing["attack"] is None and attack is not None:
                if not dry_run:
                    conn.execute(
                        "UPDATE heroes SET attack=?, defense=?, speed=?, tags=?, updated_at=datetime('now','localtime') WHERE id=?",
                        (attack, defense, speed, tags, existing["id"]),
                    )
                    conn.commit()
                updated += 1
                print(f"  [UPDATE] {name} -> atk={attack} def={defense} spd={speed}")
            else:
                skipped += 1
        else:
            # 新增武将（无 feed_id，用 name 去重）
            if not dry_run:
                conn.execute(
                    """INSERT INTO heroes (name, faction, unit_type, attack, defense, speed, tags, feed_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (name, camp, troop_type, attack, defense, speed, tags, f"intel_{name}"),
                )
                conn.commit()
            inserted += 1
            print(f"  [INSERT] {name} -> atk={attack} def={defense} spd={speed}")

    return updated, inserted, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 intel-helper 武将数据到 heroes.db")
    parser.add_argument("--json", default=str(DEFAULT_JSON), help="intel-helper hero.json 路径")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="heroes.db 路径")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写入")
    args = parser.parse_args()

    json_path = Path(args.json)
    db_path = Path(args.db)

    if not json_path.exists():
        print(f"[ERROR] 找不到 JSON 文件: {json_path}", file=sys.stderr)
        sys.exit(1)

    print(f"数据源: {json_path}")
    print(f"数据库: {db_path}")
    if args.dry_run:
        print("(dry-run 模式，不写入)")
    print()

    heroes = load_intel_heroes(json_path)
    print(f"intel-helper 共 {len(heroes)} 个武将")

    has_attr = [h for h in heroes if h.get("attack") is not None]
    print(f"其中 {len(has_attr)} 个有 attack/defense/speed 属性")
    print()

    conn = init_db(db_path)

    updated, inserted, skipped = import_intel_heroes(heroes, conn, dry_run=args.dry_run)

    print(f"\n{'='*40}")
    print(f"  更新: {updated}  新增: {inserted}  跳过: {skipped}")
    print(f"{'='*40}")

    # 统计
    total = conn.execute("SELECT COUNT(*) FROM heroes").fetchone()[0]
    with_attr = conn.execute(
        "SELECT COUNT(*) FROM heroes WHERE attack IS NOT NULL"
    ).fetchone()[0]
    print(f"  数据库共 {total} 条武将，{with_attr} 条有属性数据")

    conn.close()


if __name__ == "__main__":
    main()
