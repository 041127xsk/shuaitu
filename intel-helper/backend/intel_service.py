"""
情报服务 - 处理战报上传和确认
"""
import os
import json
import shutil
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from database import (
    Database, Hero, Player, IntelSnapshot, ObservedTeam,
    ObservedTeamMember, PlayerAlias
)
from ocr import OCREngine, OCRResult, normalize_name


class IntelService:
    """情报服务"""

    def __init__(self, db: Database, upload_dir: str = "data/screenshots"):
        self.db = db
        self.upload_dir = upload_dir
        self.ocr_engine = OCREngine()

        # 确保上传目录存在
        os.makedirs(self.upload_dir, exist_ok=True)

    def upload_screenshot(self, file_path: str, season: str) -> Dict[str, Any]:
        """
        上传战报截图
        1. 计算图片哈希
        2. 检查是否有相同的已确认快照
        3. 如果有重复，删除旧的，用新的替换
        4. OCR 识别
        5. 提取数据
        6. 返回结果
        """
        # 计算图片哈希
        image_hash = self._calculate_hash(file_path)

        # 检查是否已存在相同哈希的已确认快照
        with self.db.get_session() as session:
            existing = session.query(IntelSnapshot).filter(
                IntelSnapshot.image_hash == image_hash,
                IntelSnapshot.confirmed == True  # 只比对已确认的
            ).first()

            if existing:
                # 删除旧的快照文件
                old_image_path = existing.image_path
                if old_image_path and os.path.exists(old_image_path):
                    try:
                        os.remove(old_image_path)
                        print(f"已删除重复的旧截图: {old_image_path}")
                    except Exception as e:
                        print(f"删除旧截图失败: {e}")

                # 删除旧的快照记录（同时会删除关联的队伍）
                session.delete(existing)
                session.flush()
                print(f"已删除重复的旧快照记录 ID: {existing.id}")

        # 生成保存路径
        filename = f"{image_hash[:16]}_{Path(file_path).name}"
        saved_path = os.path.join(self.upload_dir, filename)

        # 复制文件到上传目录
        shutil.copy2(file_path, saved_path)

        # OCR 处理
        try:
            ocr_result = self.ocr_engine.process_image(saved_path)
        except Exception as e:
            # OCR 失败也允许继续，返回空结果
            ocr_result = OCRResult(
                raw_text="",
                confidence=0,
                extracted_data={"player_name": None, "alliance": None, "heroes": []}
            )

        # 创建快照记录（未确认状态）
        with self.db.get_session() as session:
            snapshot = IntelSnapshot(
                image_path=saved_path,
                image_hash=image_hash,
                source_type="battle_report",
                raw_ocr_text=ocr_result.raw_text,
                ai_result_json=json.dumps(ocr_result.extracted_data),
                confidence=ocr_result.confidence,
                confirmed=False,
                captured_at=datetime.utcnow()
            )
            session.add(snapshot)
            session.flush()

            return {
                "success": True,
                "snapshot_id": snapshot.id,
                "image_path": saved_path,
                "image_hash": image_hash,
                "raw_ocr_text": ocr_result.raw_text,
                "confidence": ocr_result.confidence,
                "suggested": {
                    "player_name": ocr_result.extracted_data.get("player_name"),
                    "alliance": ocr_result.extracted_data.get("alliance"),
                    "heroes": ocr_result.extracted_data.get("heroes", [])
                }
            }

    def confirm_intel(
        self,
        snapshot_id: int,
        player_name: str,
        season: str,
        alliance: Optional[str] = None,
        server: Optional[str] = None,
        heroes: List[Dict[str, Any]] = None,
        enemy_side: str = "unknown",
        battle_result: str = "unknown",
        notes: Optional[str] = None,
        team_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        确认并保存情报
        - 创建或更新玩家
        - 创建队伍记录
        - 创建武将成员记录
        """
        if not heroes:
            heroes = []

        normalized_name = normalize_name(player_name)

        with self.db.get_session() as session:
            # 获取快照
            snapshot = session.query(IntelSnapshot).filter(
                IntelSnapshot.id == snapshot_id
            ).first()

            if not snapshot:
                return {"success": False, "error": "快照不存在"}

            # 创建或更新玩家
            player = session.query(Player).filter(
                Player.normalized_name == normalized_name,
                Player.season == season
            ).first()

            is_new_player = False
            if player:
                # 更新玩家信息
                if alliance:
                    player.alliance = alliance
                if server:
                    player.server = server
                player.updated_at = datetime.utcnow()
            else:
                # 创建新玩家
                player = Player(
                    name=player_name,
                    normalized_name=normalized_name,
                    alliance=alliance,
                    server=server,
                    season=season,
                    notes=notes
                )
                session.add(player)
                is_new_player = True

            session.flush()

            # 更新快照
            snapshot.player_id = player.id
            snapshot.confirmed = True

            # 创建队伍记录
            team = ObservedTeam(
                player_id=player.id,
                snapshot_id=snapshot.id,
                team_name=team_name,
                battle_result=battle_result,
                enemy_side=enemy_side,
                notes=notes
            )
            session.add(team)
            session.flush()

            # 创建队伍武将成员
            for i, hero_info in enumerate(heroes):
                hero_name = hero_info.get("name") if isinstance(hero_info, dict) else hero_info

                # 尝试查找武将
                hero = session.query(Hero).filter(Hero.name == hero_name).first()

                member = ObservedTeamMember(
                    observed_team_id=team.id,
                    hero_id=hero.id if hero else None,
                    hero_name=hero_name,
                    position=hero_info.get("position", i + 1) if isinstance(hero_info, dict) else i + 1,
                    level=hero_info.get("level") if isinstance(hero_info, dict) else None,
                    skill_1=hero_info.get("skill_1") if isinstance(hero_info, dict) else None,
                    skill_2=hero_info.get("skill_2") if isinstance(hero_info, dict) else None,
                    skill_3=hero_info.get("skill_3") if isinstance(hero_info, dict) else None
                )
                session.add(member)

            return {
                "success": True,
                "player_id": player.id,
                "team_id": team.id,
                "is_new_player": is_new_player,
                "message": "情报保存成功"
            }

    def search_players(
        self,
        query: str,
        season: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        搜索玩家
        """
        with self.db.get_session() as session:
            base_query = session.query(Player)

            # 模糊搜索
            if query:
                normalized_query = normalize_name(query)
                base_query = base_query.filter(
                    or_(
                        Player.name.like(f"%{query}%"),
                        Player.normalized_name.like(f"%{normalized_query}%")
                    )
                )

            # 赛季筛选
            if season:
                base_query = base_query.filter(Player.season == season)

            players = base_query.limit(limit).all()

            results = []
            for player in players:
                # 统计队伍数量
                team_count = session.query(ObservedTeam).filter(
                    ObservedTeam.player_id == player.id
                ).count()

                # 获取最近出现时间
                latest_team = session.query(ObservedTeam).filter(
                    ObservedTeam.player_id == player.id
                ).order_by(ObservedTeam.created_at.desc()).first()

                results.append({
                    "id": player.id,
                    "name": player.name,
                    "normalized_name": player.normalized_name,
                    "alliance": player.alliance,
                    "server": player.server,
                    "season": player.season,
                    "team_count": team_count,
                    "latest_seen": latest_team.created_at.isoformat() if latest_team else None,
                    "updated_at": player.updated_at.isoformat() if player.updated_at else None
                })

            return results

    def get_player_detail(self, player_id: int) -> Optional[Dict[str, Any]]:
        """
        获取玩家详情
        """
        with self.db.get_session() as session:
            player = session.query(Player).filter(Player.id == player_id).first()
            if not player:
                return None

            # 获取所有队伍
            teams = session.query(ObservedTeam).filter(
                ObservedTeam.player_id == player_id
            ).order_by(ObservedTeam.created_at.desc()).all()

            teams_data = []
            for team in teams:
                team_dict = team.to_dict()

                # 获取截图路径
                if team.snapshot:
                    team_dict["image_path"] = team.snapshot.image_path

                # 获取武将信息
                members = session.query(ObservedTeamMember).filter(
                    ObservedTeamMember.observed_team_id == team.id
                ).order_by(ObservedTeamMember.position).all()

                team_dict["members"] = [m.to_dict() for m in members]
                teams_data.append(team_dict)

            return {
                "id": player.id,
                "name": player.name,
                "normalized_name": player.normalized_name,
                "alliance": player.alliance,
                "server": player.server,
                "season": player.season,
                "notes": player.notes,
                "created_at": player.created_at.isoformat() if player.created_at else None,
                "updated_at": player.updated_at.isoformat() if player.updated_at else None,
                "teams": teams_data,
                "team_count": len(teams_data)
            }

    def get_team_detail(self, team_id: int) -> Optional[Dict[str, Any]]:
        """
        获取队伍详情
        """
        with self.db.get_session() as session:
            team = session.query(ObservedTeam).filter(
                ObservedTeam.id == team_id
            ).first()

            if not team:
                return None

            result = team.to_dict()

            # 获取截图路径
            if team.snapshot:
                result["image_path"] = team.snapshot.image_path

            # 获取武将信息
            members = session.query(ObservedTeamMember).filter(
                ObservedTeamMember.observed_team_id == team_id
            ).order_by(ObservedTeamMember.position).all()

            result["members"] = [m.to_dict() for m in members]

            # 获取玩家信息
            if team.player:
                result["player"] = {
                    "id": team.player.id,
                    "name": team.player.name,
                    "alliance": team.player.alliance,
                    "season": team.player.season
                }

            return result

    def get_all_seasons(self) -> List[str]:
        """获取所有赛季"""
        with self.db.get_session() as session:
            seasons = session.query(Player.season).distinct().all()
            return [s[0] for s in seasons if s[0]]

    def get_all_players(self) -> List[Dict[str, Any]]:
        """
        获取所有已统计的玩家列表及其队伍信息
        """
        with self.db.get_session() as session:
            # 获取所有玩家
            players = session.query(Player).order_by(Player.updated_at.desc()).all()

            results = []
            for player in players:
                # 获取所有队伍
                teams = session.query(ObservedTeam).filter(
                    ObservedTeam.player_id == player.id
                ).order_by(ObservedTeam.created_at.desc()).all()

                teams_data = []
                for team in teams:
                    # 获取武将成员
                    members = session.query(ObservedTeamMember).filter(
                        ObservedTeamMember.observed_team_id == team.id
                    ).order_by(ObservedTeamMember.position).all()

                    team_data = {
                        "id": team.id,
                        "team_name": team.team_name,
                        "battle_result": team.battle_result,
                        "created_at": team.created_at.isoformat() if team.created_at else None,
                        "heroes": [m.hero_name for m in members if m.hero_name]
                    }
                    teams_data.append(team_data)

                results.append({
                    "id": player.id,
                    "name": player.name,
                    "alliance": player.alliance,
                    "server": player.server,
                    "season": player.season,
                    "team_count": len(teams_data),
                    "teams": teams_data,
                    "updated_at": player.updated_at.isoformat() if player.updated_at else None
                })

            return results

    def get_hero_by_name(self, hero_name: str) -> Optional[Dict[str, Any]]:
        """根据名称查找武将"""
        with self.db.get_session() as session:
            hero = session.query(Hero).filter(Hero.name == hero_name).first()
            return hero.to_dict() if hero else None

    def get_all_heroes(self) -> List[Dict[str, Any]]:
        """获取所有武将"""
        with self.db.get_session() as session:
            heroes = session.query(Hero).order_by(Hero.name).all()
            return [h.to_dict() for h in heroes]

    def _calculate_hash(self, file_path: str) -> str:
        """计算文件哈希"""
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def cleanup_unconfirmed_snapshots(self, hours: int = 24) -> int:
        """
        清理未确认的快照（识别后未保存的）
        - 删除超过指定时间的未确认快照
        - 同时删除对应的截图文件
        - 返回删除数量
        """
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        with self.db.get_session() as session:
            # 查找未确认且超过时间限制的快照
            unconfirmed = session.query(IntelSnapshot).filter(
                IntelSnapshot.confirmed == False,
                IntelSnapshot.created_at < cutoff_time
            ).all()

            deleted_count = 0
            for snapshot in unconfirmed:
                # 删除截图文件
                if snapshot.image_path and os.path.exists(snapshot.image_path):
                    try:
                        os.remove(snapshot.image_path)
                    except Exception as e:
                        print(f"删除未确认快照文件失败: {e}")

                # 删除数据库记录
                session.delete(snapshot)
                deleted_count += 1

            if deleted_count > 0:
                print(f"已清理 {deleted_count} 个未确认的旧快照")

            return deleted_count
