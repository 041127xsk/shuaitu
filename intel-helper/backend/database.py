"""
数据库模块 - SQLite 持久化层
"""
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Boolean,
    DateTime, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import (
    declarative_base, relationship, sessionmaker, Session
)
from sqlalchemy.ext.declarative import DeclarativeMeta

Base: DeclarativeMeta = declarative_base()

# ============================================================================
# 数据模型
# ============================================================================

class Hero(Base):
    """武将表"""
    __tablename__ = "hero"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, index=True)
    camp = Column(String(50), nullable=True)  # 魏/蜀/吴/群
    troop_type = Column(String(50), nullable=True)  # 步兵/骑兵/弓兵/器械
    attack = Column(Integer, nullable=True)
    defense = Column(Integer, nullable=True)
    speed = Column(Integer, nullable=True)
    tags = Column(String(200), nullable=True)  # 逗号分隔的标签
    # 战法相关字段
    skill_name = Column(String(100), nullable=True)  # 主战法名称
    skill_images_json = Column(Text, nullable=True)  # 战法截图 JSON 数组
    skill_desc = Column(Text, nullable=True)  # 战法描述
    skill_type = Column(String(50), nullable=True)  # 主动/被动/指挥/典藏
    skill_trigger_rate = Column(Integer, nullable=True)  # 发动概率 0-100

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "camp": self.camp,
            "troop_type": self.troop_type,
            "attack": self.attack,
            "defense": self.defense,
            "speed": self.speed,
            "tags": self.tags.split(",") if self.tags else [],
            # 战法字段
            "skill_name": self.skill_name,
            "skill_images": json.loads(self.skill_images_json) if self.skill_images_json else [],
            "skill_desc": self.skill_desc,
            "skill_type": self.skill_type,
            "skill_trigger_rate": self.skill_trigger_rate
        }
        return result


class Player(Base):
    """玩家表"""
    __tablename__ = "player"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    normalized_name = Column(String(100), nullable=False, index=True)
    alliance = Column(String(100), nullable=True)
    server = Column(String(50), nullable=True)
    season = Column(String(50), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    snapshots = relationship("IntelSnapshot", back_populates="player", cascade="all, delete-orphan")
    teams = relationship("ObservedTeam", back_populates="player", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("normalized_name", "season", name="uix_player_normalized_season"),
        Index("idx_player_season", "season"),
    )


class IntelSnapshot(Base):
    """战报快照表"""
    __tablename__ = "intel_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("player.id", ondelete="CASCADE"), nullable=True)
    image_path = Column(String(500), nullable=False)
    image_hash = Column(String(64), nullable=False, index=True)
    source_type = Column(String(50), default="battle_report")
    raw_ocr_text = Column(Text, nullable=True)
    ai_result_json = Column(Text, nullable=True)
    confidence = Column(Integer, nullable=True)  # 0-100
    confirmed = Column(Boolean, default=False)
    captured_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    player = relationship("Player", back_populates="snapshots")
    teams = relationship("ObservedTeam", back_populates="snapshot")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "player_id": self.player_id,
            "image_path": self.image_path,
            "image_hash": self.image_hash,
            "source_type": self.source_type,
            "raw_ocr_text": self.raw_ocr_text,
            "ai_result_json": self.ai_result_json,
            "confidence": self.confidence,
            "confirmed": self.confirmed,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ObservedTeam(Base):
    """观察到的队伍表"""
    __tablename__ = "observed_team"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("player.id", ondelete="CASCADE"), nullable=False)
    snapshot_id = Column(Integer, ForeignKey("intel_snapshot.id", ondelete="SET NULL"), nullable=True)
    team_name = Column(String(100), nullable=True)
    battle_result = Column(String(20), nullable=True)  # win/loss/draw/unknown
    enemy_side = Column(String(20), nullable=True)  # left/right/top/bottom/unknown
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    player = relationship("Player", back_populates="teams")
    snapshot = relationship("IntelSnapshot", back_populates="teams")
    members = relationship("ObservedTeamMember", back_populates="team", cascade="all, delete-orphan")

    def to_dict(self, include_members: bool = True) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "player_id": self.player_id,
            "snapshot_id": self.snapshot_id,
            "team_name": self.team_name,
            "battle_result": self.battle_result,
            "enemy_side": self.enemy_side,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        if include_members:
            result["members"] = [m.to_dict() for m in self.members]
        return result


class ObservedTeamMember(Base):
    """队伍武将成员表"""
    __tablename__ = "observed_team_member"

    id = Column(Integer, primary_key=True, autoincrement=True)
    observed_team_id = Column(Integer, ForeignKey("observed_team.id", ondelete="CASCADE"), nullable=False)
    hero_id = Column(Integer, ForeignKey("hero.id", ondelete="SET NULL"), nullable=True)
    hero_name = Column(String(50), nullable=False)
    position = Column(Integer, nullable=True)  # 1, 2, 3
    level = Column(Integer, nullable=True)
    skill_1 = Column(String(100), nullable=True)
    skill_2 = Column(String(100), nullable=True)
    skill_3 = Column(String(100), nullable=True)

    # 关系
    team = relationship("ObservedTeam", back_populates="members")
    hero = relationship("Hero")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "observed_team_id": self.observed_team_id,
            "hero_id": self.hero_id,
            "hero_name": self.hero_name,
            "position": self.position,
            "level": self.level,
            "skill_1": self.skill_1,
            "skill_2": self.skill_2,
            "skill_3": self.skill_3
        }


class PlayerAlias(Base):
    """玩家别名表 (预留)"""
    __tablename__ = "player_alias"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("player.id", ondelete="CASCADE"), nullable=False)
    alias = Column(String(100), nullable=False)
    normalized_alias = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    player = relationship("Player")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "player_id": self.player_id,
            "alias": self.alias,
            "normalized_alias": self.normalized_alias,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class PlayerTeam(Base):
    """玩家队伍数据库"""
    __tablename__ = "player_team"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String(50), nullable=False, index=True)  # 玩家ID
    team_name = Column(String(100), nullable=False)  # 队伍名称
    hero_lineup = Column(Text, nullable=True)  # 武将阵容（JSON数组）
    level = Column(Integer, default=1)  # 等级
    power = Column(Integer, default=0)  # 战力值
    notes = Column(Text, nullable=True)  # 备注
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "player_id": self.player_id,
            "team_name": self.team_name,
            "hero_lineup": json.loads(self.hero_lineup) if self.hero_lineup else [],
            "level": self.level,
            "power": self.power,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


# ============================================================================
# 数据库管理器
# ============================================================================

class Database:
    """数据库管理器"""

    def __init__(self, db_url: str = "sqlite:///data/intel.db"):
        # 确保目录存在
        db_path = db_url.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        self.engine = create_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

    def create_all(self):
        """创建所有表"""
        Base.metadata.create_all(bind=self.engine)

    def drop_all(self):
        """删除所有表"""
        Base.metadata.drop_all(bind=self.engine)

    @contextmanager
    def get_session(self) -> Session:
        """获取数据库会话的上下文管理器"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session_dependency(self) -> Session:
        """FastAPI 依赖注入"""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()


# ============================================================================
# 全局数据库实例
# ============================================================================

_db_instance: Optional[Database] = None


def get_database(db_url: Optional[str] = None) -> Database:
    """获取数据库实例"""
    global _db_instance
    if _db_instance is None:
        if db_url is None:
            db_url = os.getenv("DATABASE_URL", "sqlite:///data/intel.db")
        _db_instance = Database(db_url)
    return _db_instance


def init_database(db_url: Optional[str] = None) -> Database:
    """初始化数据库"""
    db = get_database(db_url)
    db.create_all()
    return db
