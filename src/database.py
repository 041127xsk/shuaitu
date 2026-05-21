"""
database.py - SQLite 持久化层
=============================
提供 heroes / primary_skills / crawl_state 三张表的建表、插入、查询和去重逻辑。

表结构：
  heroes          - 武将元信息 (name, faction, star, ...)
  primary_skills  - 主战法详情 (hero_id FK, skill_name, paragraphs, images, ...)
  crawl_state     - 抓取状态追踪 (feed_id, status, last_error, ...)
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "heroes.db"


# ---------------------------------------------------------------------------
# 连接管理
# ---------------------------------------------------------------------------

def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """返回一个启用外键约束的 SQLite 连接。"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# 建表
# ---------------------------------------------------------------------------

DDL = """
CREATE TABLE IF NOT EXISTS heroes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    hero_id     INTEGER,                      -- 来自 wujiangInfo.json 的原始 id
    name        TEXT    NOT NULL,
    unique_name TEXT,
    quality     TEXT,
    star        INTEGER,
    faction     TEXT,
    cost        REAL,
    unit_type   TEXT,
    image       TEXT,
    feed_id     TEXT    UNIQUE,               -- 文章 feed id，用于去重
    article_url TEXT,
    article_title TEXT,
    four_dimensions_image TEXT,               -- 四维属性图 URL（武将属性面板截图）
    attack      INTEGER,                      -- 攻击属性（来自 intel-helper）
    defense     INTEGER,                      -- 防御属性
    speed       INTEGER,                      -- 速度属性
    tags        TEXT,                         -- 标签（逗号分隔）
    created_at  DATETIME DEFAULT (datetime('now','localtime')),
    updated_at  DATETIME DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS primary_skills (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    hero_id             INTEGER NOT NULL REFERENCES heroes(id) ON DELETE CASCADE,
    title               TEXT,                     -- 章节标题，如"主战法解析"
    name                TEXT,                     -- 战法名称，如"天下无双"
    paragraph_count      INTEGER DEFAULT 0,
    image_count         INTEGER DEFAULT 0,
    paragraphs_json     TEXT,                     -- JSON 数组
    images_json         TEXT,                     -- JSON 数组
    -- AI 结构化抽取字段（nullable，待流水线补充）
    skill_type          TEXT,                     -- 主动/被动/指挥/典藏/兵种/阵法/追击
    trigger_type        TEXT,                     -- 瞬发/准备
    trigger_rate        INTEGER,                  -- 发动概率 0-100
    trigger_condition   TEXT,                     -- 发动条件描述
    targets             TEXT,                     -- 如"敌军群体(2人)"
    effects_json        TEXT,                     -- JSON 数组：每条效果 description
    duration            TEXT,                     -- 持续时间，如"3回合"
    notes               TEXT,                     -- 补充说明
    ai_extracted        INTEGER DEFAULT 0,        -- 0=未抽取 1=已抽取
    created_at          DATETIME DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS crawl_state (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_id     TEXT    NOT NULL UNIQUE,
    hero_name   TEXT,
    article_url TEXT,
    status      TEXT    NOT NULL DEFAULT 'pending',  -- pending / done / error
    last_error  TEXT,
    updated_at  DATETIME DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_heroes_name    ON heroes(name);
CREATE INDEX IF NOT EXISTS idx_heroes_faction ON heroes(faction);
CREATE INDEX IF NOT EXISTS idx_heroes_star    ON heroes(star);
CREATE INDEX IF NOT EXISTS idx_crawl_status   ON crawl_state(status);
"""


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """建库建表，幂等，可重复执行。返回 connection 供后续使用。"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    conn.executescript(DDL)
    # 对已存在的老 DB 补充新字段
    migrate_ai_fields(conn)
    migrate_hero_attribute_fields(conn)
    return conn


# ---------------------------------------------------------------------------
# 写入 - heroes
# ---------------------------------------------------------------------------

def upsert_hero(conn: sqlite3.Connection, hero: dict) -> int:
    """
    插入或更新武将记录。以 feed_id 作为唯一键去重。
    返回 heroes.id（自增主键）。
    """
    meta = hero.get("hero_meta") or {}
    feed_id = hero.get("feed_id") or ""

    sql_insert = """
    INSERT INTO heroes (
        hero_id, name, unique_name, quality, star,
        faction, cost, unit_type, image,
        feed_id, article_url, article_title,
        four_dimensions_image, attack, defense, speed, tags
    ) VALUES (
        :hero_id, :name, :unique_name, :quality, :star,
        :faction, :cost, :unit_type, :image,
        :feed_id, :article_url, :article_title,
        :four_dimensions_image, :attack, :defense, :speed, :tags
    )
    ON CONFLICT(feed_id) DO UPDATE SET
        hero_id       = excluded.hero_id,
        name          = excluded.name,
        unique_name   = excluded.unique_name,
        quality       = excluded.quality,
        star          = excluded.star,
        faction       = excluded.faction,
        cost          = excluded.cost,
        unit_type     = excluded.unit_type,
        image         = excluded.image,
        article_url   = excluded.article_url,
        article_title = excluded.article_title,
        four_dimensions_image = excluded.four_dimensions_image,
        attack        = COALESCE(excluded.attack, attack),
        defense       = COALESCE(excluded.defense, defense),
        speed         = COALESCE(excluded.speed, speed),
        tags          = COALESCE(excluded.tags, tags),
        updated_at    = datetime('now','localtime')
    """

    params = {
        "hero_id":       meta.get("id"),
        "name":          hero.get("hero_name") or meta.get("name") or "",
        "unique_name":   meta.get("unique_name"),
        "quality":       meta.get("quality"),
        "star":          meta.get("star"),
        "faction":       meta.get("faction"),
        "cost":          meta.get("cost"),
        "unit_type":     meta.get("unit_type"),
        "image":         meta.get("image"),
        "feed_id":       feed_id,
        "article_url":   hero.get("article_url"),
        "article_title": hero.get("article_title"),
        "four_dimensions_image": hero.get("four_dimensions_image"),
        "attack":        meta.get("attack"),
        "defense":       meta.get("defense"),
        "speed":         meta.get("speed"),
        "tags":          meta.get("tags"),
    }

    cursor = conn.execute(sql_insert, params)
    conn.commit()

    # 拿到插入/更新后的行 id
    if cursor.lastrowid:
        return cursor.lastrowid
    row = conn.execute("SELECT id FROM heroes WHERE feed_id = ?", (feed_id,)).fetchone()
    return row["id"]


# ---------------------------------------------------------------------------
# 写入 - primary_skills
# ---------------------------------------------------------------------------

def upsert_primary_skill(conn: sqlite3.Connection, hero_row_id: int, skill: dict) -> None:
    """
    插入或替换武将主战法（每个武将只保留一条）。
    以 hero_id 唯一：先删再插，保证数据最新。
    """
    if not skill:
        return

    conn.execute("DELETE FROM primary_skills WHERE hero_id = ?", (hero_row_id,))
    conn.execute(
        """
        INSERT INTO primary_skills (
            hero_id, title, name,
            paragraph_count, image_count,
            paragraphs_json, images_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            hero_row_id,
            skill.get("title"),
            skill.get("name"),
            skill.get("paragraph_count", 0),
            skill.get("image_count", 0),
            json.dumps(skill.get("paragraphs") or [], ensure_ascii=False),
            json.dumps(skill.get("images") or [], ensure_ascii=False),
        ),
    )
    conn.commit()


def upsert_skill_extraction(conn: sqlite3.Connection, hero_row_id: int, extraction: dict) -> None:
    """
    更新武将主战法的 AI 抽取字段。
    不删原有记录，只 UPDATE 已有行（以 hero_id 为条件）。
    extraction 来自 ai_extract.enrich_skill() 返回的 dict。
    """
    conn.execute(
        """
        UPDATE primary_skills SET
            skill_type        = :skill_type,
            trigger_type      = :trigger_type,
            trigger_rate      = :trigger_rate,
            trigger_condition = :trigger_condition,
            targets           = :targets,
            effects_json      = :effects_json,
            duration          = :duration,
            notes             = :notes,
            ai_extracted      = :ai_extracted
        WHERE hero_id = :hero_id
        """,
        {
            "hero_id":          hero_row_id,
            "skill_type":       extraction.get("skill_type"),
            "trigger_type":     extraction.get("trigger_type"),
            "trigger_rate":     extraction.get("trigger_rate"),
            "trigger_condition": extraction.get("trigger_condition"),
            "targets":          extraction.get("targets"),
            "effects_json":     json.dumps(extraction.get("effects") or [], ensure_ascii=False),
            "duration":         extraction.get("duration"),
            "notes":            extraction.get("notes"),
            "ai_extracted":     1 if extraction.get("ai_extracted") else 0,
        },
    )
    conn.commit()


def migrate_ai_fields(conn: sqlite3.Connection) -> None:
    """
    对已存在的 DB 补充 AI 抽取字段（幂等迁移）。
    多次执行安全。
    """
    new_cols = [
        "skill_type TEXT",
        "trigger_type TEXT",
        "trigger_rate INTEGER",
        "trigger_condition TEXT",
        "targets TEXT",
        "effects_json TEXT",
        "duration TEXT",
        "notes TEXT",
        "ai_extracted INTEGER DEFAULT 0",
    ]
    for col_def in new_cols:
        col_name = col_def.split()[0]
        try:
            conn.execute(f"ALTER TABLE primary_skills ADD COLUMN {col_def}")
            conn.commit()
        except Exception:
            pass  # 列已存在，忽略


def migrate_hero_attribute_fields(conn: sqlite3.Connection) -> None:
    """
    对已存在的 heroes 补充四维属性字段（幂等迁移）。
    多次执行安全。
    """
    new_cols = [
        "attack INTEGER",
        "defense INTEGER",
        "speed INTEGER",
        "tags TEXT",
    ]
    for col_def in new_cols:
        try:
            conn.execute(f"ALTER TABLE heroes ADD COLUMN {col_def}")
            conn.commit()
        except Exception:
            pass  # 列已存在，忽略


# ---------------------------------------------------------------------------
# 写入 - crawl_state
# ---------------------------------------------------------------------------

def upsert_crawl_state(
    conn: sqlite3.Connection,
    feed_id: str,
    hero_name: str = "",
    article_url: str = "",
    status: str = "done",
    last_error: Optional[str] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO crawl_state (feed_id, hero_name, article_url, status, last_error)
        VALUES (:feed_id, :hero_name, :article_url, :status, :last_error)
        ON CONFLICT(feed_id) DO UPDATE SET
            status     = excluded.status,
            last_error = excluded.last_error,
            updated_at = datetime('now','localtime')
        """,
        {
            "feed_id":     feed_id,
            "hero_name":   hero_name,
            "article_url": article_url,
            "status":      status,
            "last_error":  last_error,
        },
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------

def get_hero_by_name(conn: sqlite3.Connection, name: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM heroes WHERE name = ?", (name,)).fetchone()


def get_hero_by_feed_id(conn: sqlite3.Connection, feed_id: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM heroes WHERE feed_id = ?", (feed_id,)).fetchone()


def get_primary_skill(conn: sqlite3.Connection, hero_row_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM primary_skills WHERE hero_id = ?", (hero_row_id,)
    ).fetchone()


def query_heroes(
    conn: sqlite3.Connection,
    *,
    name: Optional[str] = None,
    faction: Optional[str] = None,
    star: Optional[int] = None,
) -> list[sqlite3.Row]:
    """按 name / faction / star 组合过滤，全部可选。"""
    clauses, params = [], []
    if name:
        clauses.append("name LIKE ?")
        params.append(f"%{name}%")
    if faction:
        clauses.append("faction = ?")
        params.append(faction)
    if star is not None:
        clauses.append("star >= ?")
        params.append(star)

    sql = "SELECT * FROM heroes"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY star DESC, name"
    return conn.execute(sql, params).fetchall()


def get_pending_crawl_targets(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """返回所有 status = 'pending' 或 'error' 的待抓条目（用于断点续跑）。"""
    return conn.execute(
        "SELECT * FROM crawl_state WHERE status IN ('pending','error') ORDER BY id"
    ).fetchall()


def count_heroes(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS cnt FROM heroes").fetchone()
    return row["cnt"]


def count_by_faction(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT faction, COUNT(*) AS cnt FROM heroes GROUP BY faction ORDER BY cnt DESC"
    ).fetchall()


# ---------------------------------------------------------------------------
# 统一导出
# ---------------------------------------------------------------------------

def _hero_skill_row(conn: sqlite3.Connection, hero_row: sqlite3.Row) -> dict:
    """将一条 heroes Row 拼上对应 primary_skill，返回扁平 dict。"""
    skill_row = conn.execute(
        "SELECT * FROM primary_skills WHERE hero_id = ?", (hero_row["id"],)
    ).fetchone()

    row = dict(hero_row)
    # 展开 skill 字段，加 skill_ 前缀避免冲突
    if skill_row:
        for k, v in dict(skill_row).items():
            if k not in ("id", "hero_id", "created_at"):
                row[f"skill_{k}"] = v
    else:
        for k in ("title", "name", "paragraph_count", "image_count",
                  "paragraphs_json", "images_json",
                  "skill_type", "trigger_type", "trigger_rate",
                  "trigger_condition", "targets", "effects_json",
                  "duration", "notes", "ai_extracted"):
            row[f"skill_{k}"] = None
    return row


def export_heroes(
    conn: sqlite3.Connection,
    *,
    faction: Optional[str] = None,
    star: Optional[int] = None,
    with_paragraphs: bool = False,
) -> list[dict]:
    """
    从 SQLite 导出武将列表，可选过滤。

    参数:
        faction:       按阵营过滤（魏/群/吴/蜀/汉/晋）
        star:          最低星级过滤
        with_paragraphs: True 时 paragraphs_json 保持 JSON 字符串，False 时省略

    返回:
        list[dict]，每条是一个武将的扁平 dict（含 skill_* 字段）
    """
    clauses, params = [], []
    if faction:
        clauses.append("faction = ?")
        params.append(faction)
    if star is not None:
        clauses.append("star >= ?")
        params.append(star)

    sql = "SELECT * FROM heroes"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY star DESC, faction, name"

    heroes = conn.execute(sql, params).fetchall()
    rows = [_hero_skill_row(conn, h) for h in heroes]

    if not with_paragraphs:
        for row in rows:
            row.pop("skill_paragraphs_json", None)
            row.pop("skill_images_json", None)

    # 去掉 SQLite 内部 id 列（暴露给外部的用 feed_id）
    for row in rows:
        row.pop("id", None)

    return rows


def export_summary(conn: sqlite3.Connection) -> dict:
    """返回导出的统计摘要。"""
    total = count_heroes(conn)
    factions = count_by_faction(conn)
    with_skill = conn.execute(
        "SELECT COUNT(*) FROM heroes h JOIN primary_skills ps ON ps.hero_id = h.id WHERE ps.name IS NOT NULL AND ps.name != ''"
    ).fetchone()[0]
    with_four_dim = conn.execute(
        "SELECT COUNT(*) FROM heroes WHERE four_dimensions_image IS NOT NULL AND four_dimensions_image != ''"
    ).fetchone()[0]
    return {
        "total": total,
        "with_skill_name": with_skill,
        "with_four_dimensions_image": with_four_dim,
        "by_faction": [{"faction": r["faction"], "count": r["cnt"]} for r in factions],
    }


# =============================================================================
# 玩家队伍数据库 - Player Teams
# =============================================================================

PLAYER_TEAMS_DDL = """
CREATE TABLE IF NOT EXISTS player_teams (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       TEXT    NOT NULL,               -- 玩家ID
    team_name       TEXT    NOT NULL,               -- 队伍名称
    hero_lineup     TEXT,                           -- 武将阵容（JSON数组）
    level           INTEGER DEFAULT 1,              -- 等级
    power           INTEGER DEFAULT 0,              -- 战力值（可选）
    created_at      DATETIME DEFAULT (datetime('now','localtime')),
    updated_at      DATETIME DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_player_teams_player_id ON player_teams(player_id);
"""


def init_player_teams_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """初始化玩家队伍表"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    conn.executescript(PLAYER_TEAMS_DDL)
    return conn


def create_player_team(
    conn: sqlite3.Connection,
    player_id: str,
    team_name: str,
    hero_lineup: list[str],
    level: int = 1,
    power: int = 0,
) -> int:
    """
    创建新的玩家队伍。
    返回新记录的 id。
    """
    cursor = conn.execute(
        """
        INSERT INTO player_teams (player_id, team_name, hero_lineup, level, power)
        VALUES (?, ?, ?, ?, ?)
        """,
        (player_id, team_name, json.dumps(hero_lineup, ensure_ascii=False), level, power),
    )
    conn.commit()
    return cursor.lastrowid


def get_player_team(conn: sqlite3.Connection, team_id: int) -> Optional[sqlite3.Row]:
    """根据 ID 获取单个队伍"""
    row = conn.execute("SELECT * FROM player_teams WHERE id = ?", (team_id,)).fetchone()
    if row:
        return row
    return None


def get_player_teams(
    conn: sqlite3.Connection,
    player_id: Optional[str] = None,
) -> list[sqlite3.Row]:
    """
    获取玩家队伍列表。
    如果提供 player_id，则只返回该玩家的队伍。
    """
    if player_id:
        return conn.execute(
            "SELECT * FROM player_teams WHERE player_id = ? ORDER BY updated_at DESC",
            (player_id,),
        ).fetchall()
    return conn.execute("SELECT * FROM player_teams ORDER BY updated_at DESC").fetchall()


def update_player_team(
    conn: sqlite3.Connection,
    team_id: int,
    *,
    player_id: Optional[str] = None,
    team_name: Optional[str] = None,
    hero_lineup: Optional[list[str]] = None,
    level: Optional[int] = None,
    power: Optional[int] = None,
) -> bool:
    """
    更新玩家队伍信息。
    只更新提供的字段。
    返回是否更新成功。
    """
    updates = []
    params = []
    
    if player_id is not None:
        updates.append("player_id = ?")
        params.append(player_id)
    if team_name is not None:
        updates.append("team_name = ?")
        params.append(team_name)
    if hero_lineup is not None:
        updates.append("hero_lineup = ?")
        params.append(json.dumps(hero_lineup, ensure_ascii=False))
    if level is not None:
        updates.append("level = ?")
        params.append(level)
    if power is not None:
        updates.append("power = ?")
        params.append(power)
    
    if not updates:
        return False
    
    updates.append("updated_at = datetime('now','localtime')")
    params.append(team_id)
    
    sql = f"UPDATE player_teams SET {', '.join(updates)} WHERE id = ?"
    cursor = conn.execute(sql, params)
    conn.commit()
    return cursor.rowcount > 0


def delete_player_team(conn: sqlite3.Connection, team_id: int) -> bool:
    """
    删除玩家队伍。
    返回是否删除成功。
    """
    cursor = conn.execute("DELETE FROM player_teams WHERE id = ?", (team_id,))
    conn.commit()
    return cursor.rowcount > 0


def count_player_teams(conn: sqlite3.Connection, player_id: Optional[str] = None) -> int:
    """统计玩家队伍数量"""
    if player_id:
        row = conn.execute(
            "SELECT COUNT(*) FROM player_teams WHERE player_id = ?", (player_id,)
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM player_teams").fetchone()
    return row[0]


# =============================================================================
# 战报抓包数据库 - Battle Reports (Network Capture)
# =============================================================================

BATTLE_REPORTS_DDL = """
CREATE TABLE IF NOT EXISTS battle_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT    NOT NULL,
    method          TEXT,
    status_code     INTEGER,
    content_type    TEXT,
    data_json       TEXT,                           -- 原始 JSON 响应
    raw_preview     TEXT,                           -- 原始响应前 5000 字符
    digest          TEXT    UNIQUE,                  -- url+timestamp 的 hash，用于去重
    created_at      DATETIME DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_battle_reports_url ON battle_reports(url);
CREATE INDEX IF NOT EXISTS idx_battle_reports_digest ON battle_reports(digest);
"""


def init_battle_reports_db(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """初始化战报抓包表"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    conn.executescript(BATTLE_REPORTS_DDL)
    return conn


def insert_battle_report(
    conn: sqlite3.Connection,
    url: str,
    method: str,
    status_code: int,
    content_type: str,
    data_json: str,
    raw_preview: str,
    digest: str,
) -> Optional[int]:
    """
    插入一条战报抓包记录。
    以 digest 去重，已存在则跳过。
    返回新记录 id，已存在则返回 None。
    """
    try:
        cursor = conn.execute(
            """
            INSERT INTO battle_reports (url, method, status_code, content_type, data_json, raw_preview, digest)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (url, method, status_code, content_type, data_json, raw_preview, digest),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # digest 重复，跳过
        return None


def count_battle_reports(conn: sqlite3.Connection) -> int:
    """统计战报抓包记录数"""
    row = conn.execute("SELECT COUNT(*) FROM battle_reports").fetchone()
    return row[0]


def get_battle_reports(
    conn: sqlite3.Connection,
    limit: int = 100,
    offset: int = 0,
) -> list[sqlite3.Row]:
    """获取战报抓包记录列表"""
    return conn.execute(
        "SELECT * FROM battle_reports ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()


def get_battle_report_by_digest(conn: sqlite3.Connection, digest: str) -> Optional[sqlite3.Row]:
    """根据 digest 获取单条记录"""
    return conn.execute(
        "SELECT * FROM battle_reports WHERE digest = ?", (digest,)
    ).fetchone()

