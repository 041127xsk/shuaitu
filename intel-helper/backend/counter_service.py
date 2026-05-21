"""
克制分析服务 - 基于规则的队伍克制分析
"""
import os
import json
from typing import Dict, Any, List, Optional
from collections import Counter

from sqlalchemy.orm import Session

from database import Database, Hero, ObservedTeam, ObservedTeamMember


class CounterService:
    """克制分析服务"""

    # 队伍类型标签规则
    HERO_TAG_MAP = {
        # 物理输出型
        "马超": ["物理", "爆发", "追击"],
        "关羽": ["物理", "控制", "爆发"],
        "张飞": ["物理", "爆发", "群攻"],
        "赵云": ["物理", "生存", "全能"],
        "太史慈": ["物理", "连击", "弓兵"],
        "甘宁": ["物理", "爆发", "暴击"],
        "孙策": ["物理", "爆发", "骑兵"],
        "吕布": ["物理", "爆发", "群攻"],
        "黄忠": ["物理", "弓兵", "爆发"],
        "张辽": ["物理", "先手", "骑兵"],
        "魏延": ["物理", "爆发", "战意"],
        "曹彰": ["物理", "爆发", "骑兵"],
        "颜良": ["物理", "爆发", "骑兵"],
        "文丑": ["物理", "爆发", "骑兵"],
        "张郃": ["物理", "控制", "弓兵"],
        "徐晃": ["物理", "爆发", "减伤"],
        "周泰": ["物理", "保护", "肉盾"],
        "凌统": ["物理", "先手", "辅助"],
        "孙坚": ["物理", "肉盾", "反击"],
        "曹仁": ["物理", "肉盾", "控制"],
        "孙武": ["谋略", "控制", "辅助"],

        # 谋略输出型
        "周瑜": ["谋略", "控制", "群攻"],
        "陆逊": ["谋略", "爆发", "火攻"],
        "诸葛亮": ["谋略", "控制", "辅助"],
        "司马懿": ["谋略", "爆发", "持续"],
        "荀彧": ["谋略", "辅助", "控制"],
        "郭嘉": ["谋略", "控制", "先手"],
        "贾诩": ["谋略", "控制", "持续"],
        "庞统": ["谋略", "辅助", "治疗"],
        "法正": ["谋略", "辅助", "治疗"],
        "徐庶": ["谋略", "控制", "辅助"],
        "姜维": ["谋略", "辅助", "控制"],
        "张角": ["谋略", "控制", "爆发"],
        "袁绍": ["谋略", "弓兵", "控制"],
        "公孙瓒": ["谋略", "弓兵", "辅助"],
        "董卓": ["谋略", "控制", "肉盾"],
        "李儒": ["谋略", "控制", "debuff"],
        "陈宫": ["谋略", "辅助", "控制"],
        "鲁肃": ["谋略", "辅助", "治疗"],
        "张昭": ["谋略", "辅助", "buff"],
        "顾雍": ["谋略", "辅助", "治疗"],
        "诸葛恪": ["谋略", "爆发", "辅助"],
        "程昱": ["谋略", "控制", "持续"],
        "刘晔": ["谋略", "器械", "持续"],
        "李严": ["谋略", "控制", "辅助"],

        # 治疗/辅助型
        "刘备": ["治疗", "辅助", "生存"],
        "华佗": ["治疗", "辅助", "解控"],
        "步练师": ["治疗", "辅助", "保护"],
        "王异": ["治疗", "辅助", "控制"],
        "张春华": ["治疗", "辅助", "控制"],
        "貂蝉": ["控制", "辅助", "混乱"],
        "甄氏": ["辅助", "buff", "治疗"],
        "大小乔": ["辅助", "治疗", "保护"],
        "周仓": ["保护", "辅助", "控制"],
        "廖化": ["辅助", "治疗", "保护"],

        # 肉盾/防御型
        "曹操": ["辅助", "buff", "全队"],
        "孙权": ["辅助", "生存", "全能"],
        "孟获": ["肉盾", "反击", "蛮族"],
        "祝融": ["治疗", "辅助", "蛮族"],
        "兀突骨": ["肉盾", "蛮族", "生存"],
        "木鹿大王": ["肉盾", "蛮族", "辅助"],
        "张宝": ["谋略", "控制", "持续"],
        "张梁": ["谋略", "爆发", "控制"],
    }

    # 队伍类型判断规则
    TEAM_TYPE_RULES = {
        "物理队": ["物理"],
        "谋略队": ["谋略"],
        "肉盾队": ["肉盾"],
        "控制队": ["控制"],
        "爆发队": ["爆发"],
        "治疗队": ["治疗", "辅助"],
        "先手队": ["先手"],
        "追击队": ["追击"],
    }

    # 克制关系
    COUNTER_RECOMMENDATIONS = {
        "物理队": {
            "type": "谋略/减伤队",
            "score": 85,
            "reason": "物理队依赖普通攻击和战法伤害，谋略队能有效抵消伤害，减伤战法降低前三回合爆发",
            "suggested_heroes": ["曹操", "刘备", "诸葛亮"],
            "suggested_tags": ["谋略", "减伤", "辅助"]
        },
        "谋略队": {
            "type": "肉盾/反击队",
            "score": 80,
            "reason": "谋略队多为持续伤害，肉盾队能承受伤害并通过反击消耗敌方",
            "suggested_heroes": ["曹操", "周泰", "孙坚"],
            "suggested_tags": ["肉盾", "反击", "减伤"]
        },
        "爆发队": {
            "type": "控制/减伤队",
            "score": 90,
            "reason": "爆发队追求前三回合终结，控制和减伤能有效拖延节奏，降低爆发收益",
            "suggested_heroes": ["诸葛亮", "曹操", "刘备"],
            "suggested_tags": ["控制", "减伤", "解控"]
        },
        "肉盾队": {
            "type": "谋略/持续队",
            "score": 85,
            "reason": "肉盾队防御高但输出慢，谋略持续伤害和百分比伤害能有效突破",
            "suggested_heroes": ["陆逊", "周瑜", "司马懿"],
            "suggested_tags": ["谋略", "持续", "百分比"]
        },
        "控制队": {
            "type": "解控/先手队",
            "score": 88,
            "reason": "控制队依赖封普攻和战法，解控和先手能保证输出环境",
            "suggested_heroes": ["华佗", "张辽", "甘宁"],
            "suggested_tags": ["解控", "先手", "净化"]
        },
        "治疗队": {
            "type": "爆发/禁疗队",
            "score": 82,
            "reason": "治疗队续航强，需要爆发伤害或禁疗来阻止回复",
            "suggested_heroes": ["马超", "吕布", "张飞"],
            "suggested_tags": ["爆发", "禁疗", "重伤"]
        },
        "先手队": {
            "type": "后手/反制队",
            "score": 75,
            "reason": "先手队追求速战，后期反制和稳定队形能应对",
            "suggested_heroes": ["曹操", "刘备", "周泰"],
            "suggested_tags": ["减伤", "保护", "稳定"]
        },
        "追击队": {
            "type": "肉盾/控制队",
            "score": 78,
            "reason": "追击队依赖普攻触发，肉盾和控制能限制其输出",
            "suggested_heroes": ["曹操", "周泰", "诸葛亮"],
            "suggested_tags": ["肉盾", "控制", "减伤"]
        },
        "混兵队": {
            "type": "针对性队伍",
            "score": 70,
            "reason": "混兵队难以针对，根据具体武将组合分析克制",
            "suggested_heroes": [],
            "suggested_tags": ["灵活应变"]
        }
    }

    def __init__(self, db: Database):
        self.db = db

    def analyze_team(self, team_id: int) -> Dict[str, Any]:
        """
        分析队伍并提供克制建议
        """
        with self.db.get_session() as session:
            team = session.query(ObservedTeam).filter(
                ObservedTeam.id == team_id
            ).first()

            if not team:
                return {"error": "队伍不存在"}

            # 获取队伍成员
            members = session.query(ObservedTeamMember).filter(
                ObservedTeamMember.observed_team_id == team_id
            ).order_by(ObservedTeamMember.position).all()

            hero_names = [m.hero_name for m in members]

            # 获取武将详细信息
            heroes_info = []
            for member in members:
                hero = session.query(Hero).filter(Hero.id == member.hero_id).first()
                heroes_info.append({
                    "name": member.hero_name,
                    "level": member.level,
                    "tags": hero.tags.split(",") if hero and hero.tags else self.get_hero_tags(member.hero_name)
                })

            # 分析敌方队伍类型
            enemy_tags = self._analyze_team_tags(hero_names, heroes_info)
            enemy_team_type = self._determine_team_type(enemy_tags)

            # 获取克制建议
            counter = self._get_counter_recommendation(enemy_team_type, enemy_tags)

            # 尝试找已记录的我方队伍
            my_teams = self._find_suggested_teams(enemy_tags)

            return {
                "enemy_team": hero_names,
                "enemy_team_info": heroes_info,
                "enemy_tags": enemy_tags,
                "enemy_type": enemy_team_type,
                "recommendations": [counter] + my_teams
            }

    def _analyze_team_tags(self, hero_names: List[str], heroes_info: List[Dict]) -> List[str]:
        """分析队伍整体标签"""
        all_tags = []

        for hero_name, hero_info in zip(hero_names, heroes_info):
            # 从武将信息获取标签
            if hero_info.get("tags"):
                all_tags.extend(hero_info["tags"])

            # 从标签映射获取
            if hero_name in self.HERO_TAG_MAP:
                all_tags.extend(self.HERO_TAG_MAP[hero_name])

        # 统计标签频率
        tag_counts = Counter(all_tags)
        return [tag for tag, count in tag_counts.most_common(5)]

    def _determine_team_type(self, tags: List[str]) -> str:
        """根据标签判断队伍类型"""
        # 优先匹配更具体的类型
        type_priority = ["爆发队", "控制队", "先手队", "追击队", "治疗队", "肉盾队", "物理队", "谋略队"]

        for team_type in type_priority:
            required_tag = team_type.replace("队", "")
            if required_tag in tags:
                return team_type

        return "混兵队"

    def _get_counter_recommendation(self, team_type: str, enemy_tags: List[str]) -> Dict[str, Any]:
        """获取克制建议"""
        base_counter = self.COUNTER_RECOMMENDATIONS.get(
            team_type,
            self.COUNTER_RECOMMENDATIONS["混兵队"]
        )

        # 根据敌方具体标签微调
        recommendations = {
            "type": base_counter["type"],
            "score": base_counter["score"],
            "reason": base_counter["reason"],
            "suggested_heroes": base_counter["suggested_heroes"],
            "based_on": team_type
        }

        return recommendations

    def _find_suggested_teams(self, enemy_tags: List[str]) -> List[Dict[str, Any]]:
        """查找系统中的克制队伍"""
        with self.db.get_session() as session:
            # 查找所有队伍
            teams = session.query(ObservedTeam).all()

            suggested = []
            for team in teams:
                members = session.query(ObservedTeamMember).filter(
                    ObservedTeamMember.observed_team_id == team.id
                ).all()

                # 获取队伍武将和标签
                team_heroes = [m.hero_name for m in members]
                team_tags = []
                for hero_name in team_heroes:
                    if hero_name in self.HERO_TAG_MAP:
                        team_tags.extend(self.HERO_TAG_MAP[hero_name])

                # 计算克制分数
                counter_tags = {"谋略": "物理", "物理": "谋略", "肉盾": "持续", "爆发": "减伤"}
                score = 0
                for enemy_tag in enemy_tags:
                    if enemy_tag in counter_tags and counter_tags[enemy_tag] in team_tags:
                        score += 20
                    elif enemy_tag in team_tags:
                        score += 10

                if score > 0:
                    suggested.append({
                        "type": f"我方队伍: {','.join(team_heroes[:3])}",
                        "score": min(score, 95),
                        "reason": "系统中已记录的克制队伍",
                        "team_id": team.id,
                        "suggested_heroes": team_heroes
                    })

            # 返回分数最高的3个
            suggested.sort(key=lambda x: x["score"], reverse=True)
            return suggested[:3]

    def get_hero_tags(self, hero_name: str) -> List[str]:
        """获取武将标签"""
        return self.HERO_TAG_MAP.get(hero_name, [])

    def batch_analyze(self, player_id: int) -> Dict[str, Any]:
        """批量分析玩家的所有队伍"""
        with self.db.get_session() as session:
            teams = session.query(ObservedTeam).filter(
                ObservedTeam.player_id == player_id
            ).all()

            results = []
            for team in teams:
                analysis = self.analyze_team(team.id)
                analysis["team_id"] = team.id
                analysis["battle_result"] = team.battle_result
                analysis["created_at"] = team.created_at.isoformat() if team.created_at else None
                results.append(analysis)

            return {
                "player_id": player_id,
                "team_count": len(results),
                "teams": results
            }
