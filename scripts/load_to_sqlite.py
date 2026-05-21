"""
load_to_sqlite.py - 将 data/fetched_heroes.json 导入 SQLite
=============================================================
用法：
    python scripts/load_to_sqlite.py
    python scripts/load_to_sqlite.py --db data/heroes.db --json data/fetched_heroes.json
    python scripts/load_to_sqlite.py --report        # 只打印统计，不导入

说明：
- 可重复执行（幂等），以 feed_id 作唯一键，不会产生重复记录。
- 每个武将导入失败不会中断整批，错误会写入 crawl_state 表并打印到标准输出。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保能找到 src 包
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import (
    count_by_faction,
    count_heroes,
    init_db,
    upsert_crawl_state,
    upsert_hero,
    upsert_primary_skill,
    upsert_skill_extraction,
    query_heroes,
    get_primary_skill,
)

DEFAULT_JSON = Path(__file__).parent.parent / "data" / "fetched_heroes.json"
DEFAULT_DB   = Path(__file__).parent.parent / "data" / "heroes.db"


def load_json(json_path: Path) -> dict:
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def import_heroes(data: dict, conn) -> tuple[int, int]:
    """
    遍历 heroes 列表，逐条 upsert。
    返回 (成功数, 失败数)。
    """
    heroes = data.get("heroes", [])
    ok, fail = 0, 0

    for hero in heroes:
        hero_name = hero.get("hero_name", "?")
        feed_id   = hero.get("feed_id", "")

        try:
            row_id = upsert_hero(conn, hero)

            skill = hero.get("primary_skill") or {}
            upsert_primary_skill(conn, row_id, skill)

            # AI 结构化抽取字段入库（可选，失败不中断）
            ai_extraction = hero.get("ai_extraction") or {}
            if ai_extraction.get("ai_extracted"):
                try:
                    upsert_skill_extraction(conn, row_id, ai_extraction)
                except Exception as e:
                    print(f"    [WARN] AI抽取字段写入失败: {e}", file=sys.stderr)

            upsert_crawl_state(
                conn,
                feed_id    = feed_id,
                hero_name  = hero_name,
                article_url= hero.get("article_url", ""),
                status     = "done",
            )
            print(f"  [OK]  {hero_name} (feed_id={feed_id})")
            ok += 1

        except Exception as e:
            err_msg = str(e)
            print(f"  [ERR] {hero_name} (feed_id={feed_id}): {err_msg}", file=sys.stderr)
            if feed_id:
                upsert_crawl_state(
                    conn,
                    feed_id    = feed_id,
                    hero_name  = hero_name,
                    article_url= hero.get("article_url", ""),
                    status     = "error",
                    last_error = err_msg,
                )
            fail += 1

    return ok, fail


def print_report(conn) -> None:
    total = count_heroes(conn)
    print(f"\n{'='*40}")
    print(f"  数据库共 {total} 条武将记录")
    print(f"{'='*40}")
    print("  阵营分布：")
    for row in count_by_faction(conn):
        print(f"    {row['faction'] or '未知':>6}  {row['cnt']} 人")
    print()

    print("  高星武将列表（star >= 4）：")
    rows = query_heroes(conn, star=4)
    for row in rows:
        print(f"    [{row['star']}★] {row['name']:6}  {row['faction'] or '':4}  {row['unit_type'] or ''}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="把 fetched_heroes.json 导入 SQLite")
    parser.add_argument("--db",     default=str(DEFAULT_DB),   help="SQLite 数据库路径")
    parser.add_argument("--json",   default=str(DEFAULT_JSON), help="输入 JSON 文件路径")
    parser.add_argument("--report", action="store_true",       help="只打印统计，不导入")
    args = parser.parse_args()

    db_path   = Path(args.db)
    json_path = Path(args.json)

    print(f"数据库: {db_path}")
    print(f"数据源: {json_path}")
    print()

    conn = init_db(db_path)

    if args.report:
        print_report(conn)
        conn.close()
        return

    if not json_path.exists():
        print(f"[ERROR] 找不到 JSON 文件: {json_path}", file=sys.stderr)
        sys.exit(1)

    data = load_json(json_path)
    total_in_file = len(data.get("heroes", []))
    print(f"JSON 中共 {total_in_file} 条武将，开始导入...\n")

    ok, fail = import_heroes(data, conn)

    print(f"\n导入完成：成功 {ok} / 失败 {fail}")
    print_report(conn)
    conn.close()


if __name__ == "__main__":
    main()
