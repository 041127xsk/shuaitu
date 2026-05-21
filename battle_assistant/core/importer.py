"""
战报助手 - 数据导入模块
"""
import glob
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


class DataImporter:
    def __init__(self, db_path: str = "data/heroes.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript("""
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
        conn.close()

    def find_stzb_db(self, search_dir: str = ".") -> Optional[str]:
        """查找 stzbHelper 数据库文件"""
        search_path = Path(search_dir)
        db_files = list(search_path.glob("*.db"))
        db_files = [f for f in db_files if "heroes" not in f.name.lower()]
        if db_files:
            return str(db_files[0])
        return None

    def import_data(self, src_path: str, filter_npc: bool = True,
                    filter_incomplete: bool = True) -> Tuple[int, int, int, int, int]:
        """
        导入数据
        返回: (imported, skipped_dup, filtered_npc, filtered_incomplete, members_imported)
        """
        src_conn = sqlite3.connect(src_path)
        dst_conn = sqlite3.connect(str(self.db_path))

        # 导入战报
        cursor = src_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM battle_report")
        total_reports = cursor.fetchone()[0]

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

            # 过滤 NPC
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

        # 导入同盟成员
        members_imported = 0
        cursor.execute("SELECT id, name, contribute_total, contribute_week, pos, power, wu, \"group\", join_time FROM team_user")
        for row in cursor.fetchall():
            member_id, name, contribute_total, contribute_week, pos, power, wu, group_name, join_time = row

            existing = dst_conn.execute(
                "SELECT id FROM stzb_team_members WHERE member_id = ?", (member_id,)
            ).fetchone()

            if existing:
                continue

            join_date = datetime.fromtimestamp(join_time).strftime("%Y-%m-%d %H:%M:%S") if join_time else ""

            dst_conn.execute("""
                INSERT INTO stzb_team_members (
                    member_id, name, contribute_total, contribute_week,
                    pos, power, wu, group_name, join_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (member_id, name, contribute_total, contribute_week,
                  pos, power, wu, group_name, join_date))
            members_imported += 1

        dst_conn.commit()
        src_conn.close()
        dst_conn.close()

        return imported, skipped_dup, filtered_npc, filtered_incomplete, members_imported

    def get_stats(self) -> dict:
        """获取数据库统计"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM stzb_battle_reports")
        reports = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM stzb_team_members")
        members = cursor.fetchone()[0]

        conn.close()

        return {"reports": reports, "members": members}
