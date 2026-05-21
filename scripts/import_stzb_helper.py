"""
import_stzb_helper.py - 导入 stzbHelper 数据到本项目数据库
=========================================================
从 stzbHelper 的 SQLite 数据库读取战报和同盟成员数据，
导入到本项目的 data/heroes.db 中。

用法：
    python scripts/import_stzb_helper.py                          # 自动查找 stzbHelper 的 .db 文件
    python scripts/import_stzb_helper.py --db path/to/stzb.db    # 指定数据库文件
    python scripts/import_stzb_helper.py --dry-run                # 只预览不导入
"""
from __future__ import annotations

import glob
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import get_connection, init_db


def find_stzb_db() -> str | None:
    """自动查找 stzbHelper 的数据库文件（在项目根目录和 tools 目录下）。"""
    # 查找根目录
    db_files = glob.glob(str(ROOT / "*.db"))
    # 排除我们自己的 heroes.db
    db_files = [f for f in db_files if "heroes" not in os.path.basename(f).lower()]
    if db_files:
        return max(db_files, key=lambda f: os.path.getsize(f))
    
    # 查找 tools 目录
    tools_dir = ROOT / "tools"
    if tools_dir.exists():
        db_files = glob.glob(str(tools_dir / "*.db"))
        if db_files:
            return max(db_files, key=lambda f: os.path.getsize(f))
    
    return None


def import_battle_reports(src_conn: sqlite3.Connection, dst_conn: sqlite3.Connection, dry_run: bool = False, filter_npc: bool = True, filter_incomplete: bool = True) -> tuple[int, int, int, int]:
    """导入战报数据。返回 (imported, skipped_dup, filtered_npc, filtered_incomplete)。"""
    cursor = src_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM battle_report")
    total = cursor.fetchone()[0]
    print(f"Found {total} battle reports in stzbHelper DB")

    if dry_run:
        print("[DRY RUN] Would import battle reports")
        return 0, 0, 0, 0

    # 读取所有战报
    cursor.execute("""
        SELECT battle_id, time, wid, wid_name,
               attack_name, attack_union_name, attack_clan_name,
               defend_name, defend_union_name, defend_clan_name,
               attack_hero1_id, attack_hero2_id, attack_hero3_id,
               attack_hero1_level, attack_hero2_level, attack_hero3_level,
               attack_hero1_star, attack_hero2_star, attack_hero3_star, attack_total_star,
               defend_hero1_id, defend_hero2_id, defend_hero3_id,
               defend_hero1_level, defend_hero2_level, defend_hero3_level,
               defend_hero1_star, defend_hero2_star, defend_hero3_star, defend_total_star,
               attack_hp, defend_hp, npc, result,
               attack_all_hero_info, defend_all_hero_info,
               attack_advance, defend_advance,
               all_skill_info, attack_idu, defend_idu,
               attacker_gear_info, defender_gear_info,
               attack_hero_type, defend_hero_type
        FROM battle_report
    """)
    rows = cursor.fetchall()

    imported = 0
    skipped_dup = 0
    filtered_npc = 0
    filtered_incomplete = 0

    for row in rows:
        (battle_id, time, wid, wid_name,
         attack_name, attack_union_name, attack_clan_name,
         defend_name, defend_union_name, defend_clan_name,
         attack_hero1_id, attack_hero2_id, attack_hero3_id,
         attack_hero1_level, attack_hero2_level, attack_hero3_level,
         attack_hero1_star, attack_hero2_star, attack_hero3_star, attack_total_star,
         defend_hero1_id, defend_hero2_id, defend_hero3_id,
         defend_hero1_level, defend_hero2_level, defend_hero3_level,
         defend_hero1_star, defend_hero2_star, defend_hero3_star, defend_total_star,
         attack_hp, defend_hp, npc, result,
         attack_all_hero_info, defend_all_hero_info,
         attack_advance, defend_advance,
         all_skill_info, attack_idu, defend_idu,
         attacker_gear_info, defender_gear_info,
         attack_hero_type, defend_hero_type) = row

        # 过滤 NPC 战斗（打城）
        if filter_npc and npc == 1:
            filtered_npc += 1
            continue

        # 过滤攻方武将不足 3 名
        if filter_incomplete and (not attack_hero1_id or not attack_hero2_id or not attack_hero3_id):
            filtered_incomplete += 1
            continue

        # 检查是否已存在
        existing = dst_conn.execute(
            "SELECT id FROM stzb_battle_reports WHERE battle_id = ?", (battle_id,)
        ).fetchone()

        if existing:
            skipped_dup += 1
            continue

        # 转换时间戳
        battle_time = datetime.fromtimestamp(time).strftime("%Y-%m-%d %H:%M:%S") if time else ""

        # 插入数据
        dst_conn.execute("""
            INSERT INTO stzb_battle_reports (
                battle_id, battle_time, wid, wid_name,
                attack_name, attack_union_name, attack_clan_name,
                defend_name, defend_union_name, defend_clan_name,
                attack_hero1_id, attack_hero2_id, attack_hero3_id,
                attack_hero1_level, attack_hero2_level, attack_hero3_level,
                attack_hero1_star, attack_hero2_star, attack_hero3_star, attack_total_star,
                defend_hero1_id, defend_hero2_id, defend_hero3_id,
                defend_hero1_level, defend_hero2_level, defend_hero3_level,
                defend_hero1_star, defend_hero2_star, defend_hero3_star, defend_total_star,
                attack_hp, defend_hp, npc, result,
                attack_all_hero_info, defend_all_hero_info,
                attack_advance, defend_advance,
                all_skill_info, attack_idu, defend_idu,
                attacker_gear_info, defender_gear_info,
                attack_hero_type, defend_hero_type
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?
            )
        """, (
            battle_id, battle_time, wid, wid_name,
            attack_name, attack_union_name, attack_clan_name,
            defend_name, defend_union_name, defend_clan_name,
            attack_hero1_id, attack_hero2_id, attack_hero3_id,
            attack_hero1_level, attack_hero2_level, attack_hero3_level,
            attack_hero1_star, attack_hero2_star, attack_hero3_star, attack_total_star,
            defend_hero1_id, defend_hero2_id, defend_hero3_id,
            defend_hero1_level, defend_hero2_level, defend_hero3_level,
            defend_hero1_star, defend_hero2_star, defend_hero3_star, defend_total_star,
            attack_hp, defend_hp, npc, result,
            attack_all_hero_info, defend_all_hero_info,
            attack_advance, defend_advance,
            all_skill_info, attack_idu, defend_idu,
            attacker_gear_info, defender_gear_info,
            attack_hero_type, defend_hero_type
        ))
        imported += 1

    dst_conn.commit()
    return imported, skipped_dup, filtered_npc, filtered_incomplete


def import_team_users(src_conn: sqlite3.Connection, dst_conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """导入同盟成员数据。"""
    cursor = src_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM team_user")
    total = cursor.fetchone()[0]
    print(f"Found {total} team members in stzbHelper DB")

    if dry_run:
        print("[DRY RUN] Would import team members")
        return 0

    cursor.execute("SELECT id, name, contribute_total, contribute_week, pos, power, wu, \"group\", join_time FROM team_user")
    rows = cursor.fetchall()

    imported = 0
    skipped = 0
    for row in rows:
        member_id, name, contribute_total, contribute_week, pos, power, wu, group_name, join_time = row

        existing = dst_conn.execute(
            "SELECT id FROM stzb_team_members WHERE member_id = ?", (member_id,)
        ).fetchone()

        if existing:
            skipped += 1
            continue

        join_date = datetime.fromtimestamp(join_time).strftime("%Y-%m-%d %H:%M:%S") if join_time else ""

        dst_conn.execute("""
            INSERT INTO stzb_team_members (
                member_id, name, contribute_total, contribute_week,
                pos, power, wu, group_name, join_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (member_id, name, contribute_total, contribute_week,
              pos, power, wu, group_name, join_date))
        imported += 1

    dst_conn.commit()
    return imported


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import stzbHelper data")
    parser.add_argument("--db", type=str, help="Path to stzbHelper database")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't import")
    parser.add_argument("--keep-npc", action="store_true", help="Keep NPC battles (default: filter out)")
    parser.add_argument("--keep-incomplete", action="store_true", help="Keep reports with < 3 heroes (default: filter out)")
    args = parser.parse_args()

    # Find source database
    src_path = args.db or find_stzb_db()
    if not src_path:
        print("[ERROR] No stzbHelper database found. Use --db to specify.")
        return

    print(f"Source: {src_path}")

    # Initialize our database
    dst_path = ROOT / "data" / "heroes.db"
    dst_conn = init_db(dst_path)
    print(f"Destination: {dst_path}")

    # Create stzb tables if not exist
    dst_conn.executescript("""
        CREATE TABLE IF NOT EXISTS stzb_battle_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            battle_id INTEGER UNIQUE,
            battle_time TEXT,
            wid TEXT,
            wid_name TEXT,
            attack_name TEXT,
            attack_union_name TEXT,
            attack_clan_name TEXT,
            defend_name TEXT,
            defend_union_name TEXT,
            defend_clan_name TEXT,
            attack_hero1_id INTEGER,
            attack_hero2_id INTEGER,
            attack_hero3_id INTEGER,
            attack_hero1_level INTEGER,
            attack_hero2_level INTEGER,
            attack_hero3_level INTEGER,
            attack_hero1_star INTEGER,
            attack_hero2_star INTEGER,
            attack_hero3_star INTEGER,
            attack_total_star INTEGER,
            defend_hero1_id INTEGER,
            defend_hero2_id INTEGER,
            defend_hero3_id INTEGER,
            defend_hero1_level INTEGER,
            defend_hero2_level INTEGER,
            defend_hero3_level INTEGER,
            defend_hero1_star INTEGER,
            defend_hero2_star INTEGER,
            defend_hero3_star INTEGER,
            defend_total_star INTEGER,
            attack_hp INTEGER,
            defend_hp INTEGER,
            npc INTEGER,
            result INTEGER,
            attack_all_hero_info TEXT,
            defend_all_hero_info TEXT,
            attack_advance TEXT,
            defend_advance TEXT,
            all_skill_info TEXT,
            attack_idu TEXT,
            defend_idu TEXT,
            attacker_gear_info TEXT,
            defender_gear_info TEXT,
            attack_hero_type TEXT,
            defend_hero_type TEXT,
            created_at DATETIME DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS stzb_team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER UNIQUE,
            name TEXT,
            contribute_total INTEGER,
            contribute_week INTEGER,
            pos INTEGER,
            power INTEGER,
            wu INTEGER,
            group_name TEXT,
            join_time TEXT,
            created_at DATETIME DEFAULT (datetime('now','localtime'))
        );
    """)

    # Open source database
    src_conn = sqlite3.connect(src_path)

    # Import data
    print("\n--- Importing Battle Reports ---")
    filter_npc = not args.keep_npc
    filter_incomplete = not args.keep_incomplete
    reports_imported, skipped_dup, filtered_npc, filtered_incomplete = import_battle_reports(
        src_conn, dst_conn, args.dry_run, filter_npc, filter_incomplete
    )
    print(f"Imported: {reports_imported}")
    print(f"Skipped (duplicate): {skipped_dup}")
    print(f"Filtered (NPC): {filtered_npc}")
    print(f"Filtered (incomplete heroes): {filtered_incomplete}")

    print("\n--- Importing Team Members ---")
    members_imported = import_team_users(src_conn, dst_conn, args.dry_run)
    print(f"Imported: {members_imported}")

    # Summary
    print("\n" + "=" * 50)
    print("Import Summary")
    print("=" * 50)
    cursor = dst_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM stzb_battle_reports")
    total_reports = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM stzb_team_members")
    total_members = cursor.fetchone()[0]
    print(f"Total battle reports in DB: {total_reports}")
    print(f"Total team members in DB: {total_members}")

    src_conn.close()
    dst_conn.close()


if __name__ == "__main__":
    main()
