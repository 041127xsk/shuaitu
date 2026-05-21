"""
report_parser.py - 率土之滨战报解析器
=====================================
从 OCR 结果中提取战报数据：玩家名、武将阵容、胜负结果。
支持同盟战报列表页（多条战报）和单条战报详情页。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from src.ocr_paddle import OCRResult, TextBlock


# 已知武将名
KNOWN_HEROES = {
    # 魏
    "曹操", "司马懿", "曹丕", "曹仁", "夏侯惇", "夏侯渊", "张辽", "徐晃", "许褚", "典韦",
    "张郃", "于禁", "乐进", "李典", "荀彧", "荀攸", "郭嘉", "贾诩", "程昱", "刘晔",
    "满宠", "蒋济", "陈群", "华歆", "王朗", "钟繇", "张春华", "王异", "曹彰", "曹植",
    # 蜀
    "刘备", "关羽", "张飞", "赵云", "马超", "黄忠", "诸葛亮", "庞统", "魏延", "姜维",
    "关平", "关兴", "张苞", "周仓", "廖化", "马谡", "王平", "马岱", "法正", "黄月英",
    # 吴
    "孙权", "孙策", "孙坚", "周瑜", "陆逊", "鲁肃", "吕蒙", "甘宁", "太史慈", "黄盖",
    "程普", "韩当", "周泰", "蒋钦", "凌统", "大乔", "小乔", "步练师", "丁奉", "徐盛",
    # 群
    "吕布", "貂蝉", "董卓", "李儒", "袁绍", "袁术", "颜良", "文丑", "张角", "张宝",
    "张梁", "孟获", "祝融", "兀突骨", "木鹿大王", "公孙瓒", "马腾", "庞德",
    "高顺", "陈宫", "田丰", "沮授", "审配", "许攸",
    # 晋
    "司马昭", "司马师", "司马炎", "邓艾", "钟会", "王基",
    # 特殊/SP
    "关银屏", "马云禄", "甄洛", "蔡文姬", "灵帝", "何太后", "刘禅",
    "群吕布", "群貂蝉", "吴孙权", "SP赵云", "SP关羽", "SP曹操",
    # 补充
    "夏侯霸", "文聘", "曹叡", "诸葛恪", "诸葛瑾",
    "严颜", "黄舞蝶", "花鬘", "袁姬", "张奂", "朱偽", "刘虞", "曹豹",
    "陆抗", "潘璋", "朱桓", "荀谌", "逢纪", "郭图", "张机",
    "关兴张苞", "赵统", "严颜", "颜良",
}

# 胜负关键词
WIN_KEYWORDS = ("胜利", "战胜", "获胜", "胜")
LOSS_KEYWORDS = ("失败", "战败", "失去领地", "败")
DRAW_KEYWORDS = ("平局", "战平")

# 需要跳过的非玩家名文本
SKIP_TEXTS = {
    "同盟战报", "个人", "同盟", "收藏", "筛选", "战报详情",
    "失去领地", "攻占领地", "胜利", "失败", "平局",
    "大营", "中军", "前锋", "武将", "战法",
}


@dataclass
class BattleReport:
    """一条战报数据。"""
    player_a: str = ""              # 攻方玩家名
    player_b: str = ""              # 守方玩家名
    heroes_a: List[str] = field(default_factory=list)   # 攻方武将
    heroes_b: List[str] = field(default_factory=list)   # 守方武将
    result: str = "unknown"         # win / loss / draw / unknown
    season: str = ""                # 赛季标识
    timestamp: str = ""             # 时间戳
    location: str = ""              # 战斗地点
    raw_text: str = ""              # 原始 OCR 文本
    confidence: float = 0.0         # 平均置信度

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_a": self.player_a,
            "player_b": self.player_b,
            "heroes_a": self.heroes_a,
            "heroes_b": self.heroes_b,
            "result": self.result,
            "season": self.season,
            "timestamp": self.timestamp,
            "location": self.location,
            "confidence": self.confidence,
        }


class BattleReportParser:
    """战报解析器。"""

    def __init__(self, known_heroes: Optional[set] = None, season: str = ""):
        self.known_heroes = known_heroes or KNOWN_HEROES
        self.season = season
        self._sorted_heroes = sorted(self.known_heroes, key=len, reverse=True)
        # 单字武将映射：姓 → 全名（用于 OCR 只截取到一个字时匹配）
        # 有歧义时放优先匹配的在前面
        self._single_char_map: Dict[str, List[str]] = {}
        for h in self.known_heroes:
            if len(h) >= 2:
                self._single_char_map.setdefault(h[0], []).append(h)
        # 歧义消解：颜 → 严颜（而非颜良）
        if "颜" in self._single_char_map:
            self._single_char_map["颜"].sort(key=lambda n: (n != "严颜", n))

    def parse(self, ocr: OCRResult) -> List[BattleReport]:
        """
        解析同盟战报列表页截图。
        每条战报由"同盟信息行"标记开头，往下直到下一条"同盟信息行"之前结束。
        """
        if not ocr.blocks:
            return []

        # 按 Y 排序所有块
        sorted_blocks = sorted(ocr.blocks, key=lambda b: b.center_y)

        # 找出所有"同盟信息行"的 Y 坐标（包含国家简写 + 同盟名的行）
        report_starts: List[int] = []
        for i, block in enumerate(sorted_blocks):
            # 同盟行特征：x≈436 处有"夏/唐/秦/汉/周/宋"等国家简写
            if block.center_x > 400 and block.center_x < 500 and block.text in ("夏", "唐", "秦", "汉", "周", "宋", "商", "楚", "赵", "魏", "吴", "蜀", "齐", "燕", "韩"):
                # 前面应该还有"如|来"之类的同盟标识
                # 检查附近有没有同盟名
                nearby = [b for b in sorted_blocks
                          if abs(b.center_y - block.center_y) < 30 and b.center_x > 600]
                if nearby:
                    report_starts.append(i)

        if not report_starts:
            # 没找到同盟行标记，fallback 到简单聚类
            return self._fallback_parse(sorted_blocks)

        # 按同盟行分割战报
        reports = []
        for idx, start_i in enumerate(report_starts):
            # 结束位置：下一条战报的同盟行之前，或文本块末尾
            if idx + 1 < len(report_starts):
                end_i = report_starts[idx + 1]
            else:
                end_i = len(sorted_blocks)

            # 向上扩展一点，把同盟标识行（如|来）也包含进来
            start_y = sorted_blocks[start_i].center_y - 40
            # 向下扩展，包含武将行和等级行（约 +320 像素）
            end_y = sorted_blocks[min(end_i - 1, len(sorted_blocks) - 1)].center_y + 40

            cluster_blocks = [b for b in sorted_blocks if start_y <= b.center_y <= end_y]
            if cluster_blocks:
                report = self._parse_cluster(cluster_blocks)
                if report and (report.heroes_a or report.heroes_b or report.player_a):
                    reports.append(report)

        return reports

    def _fallback_parse(self, sorted_blocks: List[TextBlock]) -> List[BattleReport]:
        """找不到同盟行标记时的 fallback：按武将名聚类。"""
        # 找包含武将名的行
        hero_lines_y = set()
        for block in sorted_blocks:
            for hero_name in self._sorted_heroes:
                if hero_name in block.text:
                    hero_lines_y.add(round(block.center_y / 40) * 40)
                    break

        if not hero_lines_y:
            return []

        # 每个武将行 ±200 像素为一条战报
        reports = []
        used_y = set()
        for hy in sorted(hero_lines_y):
            if any(abs(hy - uy) < 200 for uy in used_y):
                continue
            cluster_blocks = [b for b in sorted_blocks if hy - 200 <= b.center_y <= hy + 200]
            report = self._parse_cluster(cluster_blocks)
            if report and (report.heroes_a or report.heroes_b):
                reports.append(report)
                used_y.add(hy)

        return reports

    def _parse_cluster(self, blocks: List[TextBlock]) -> Optional[BattleReport]:
        """解析一个文本块聚类为一条战报。"""
        texts = [b.text for b in blocks]
        full_text = " ".join(texts)

        # 提取武将名
        heroes = []
        for text in texts:
            for hero_name in self._sorted_heroes:
                if hero_name in text and hero_name not in heroes:
                    heroes.append(hero_name)

        # 提取玩家名（x > 800 的非武将、非关键词、非数字文本）
        players = []
        for block in blocks:
            text = block.text.strip()
            if len(text) < 2 or len(text) > 12:
                continue
            # 跳过纯数字、等级、兵力比
            if text.isdigit() or "/" in text or "Lv" in text or "LV" in text:
                continue
            if text in SKIP_TEXTS or text in self.known_heroes:
                continue
            # 跳过国家简写
            if text in ("夏", "唐", "秦", "汉", "周", "宋", "商", "楚", "赵", "魏", "吴", "蜀", "齐", "燕", "韩"):
                continue
            # 跳过同盟标识（如|来、如来）
            if "来" in text and len(text) <= 3:
                continue
            if any(c.islower() for c in text):
                continue
            if "%" in text:
                continue
            # 跳过星级标识
            if "★" in text or "★" in text:
                continue
            # 玩家名通常在右侧 (x > 1000)
            if block.center_x > 1000:
                players.append(text)

        # 提取胜负
        result = "unknown"
        for text in texts:
            text_clean = text.replace(" ", "")
            for kw in LOSS_KEYWORDS:
                if kw in text_clean:
                    result = "loss"
                    break
            if result != "unknown":
                break
            for kw in WIN_KEYWORDS:
                if kw in text_clean:
                    result = "win"
                    break
            if result != "unknown":
                break
            for kw in DRAW_KEYWORDS:
                if kw in text_clean:
                    result = "draw"
                    break

        # 提取时间戳
        timestamp = ""
        ts_pattern = re.compile(r"\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}")
        for text in texts:
            m = ts_pattern.search(text)
            if m:
                timestamp = m.group()
                break

        # 提取地点
        location = ""
        for text in texts:
            text_clean = text.replace(" ", "")
            if "之战" in text_clean or "战斗" in text_clean:
                location = text_clean
                break

        # 区分攻守双方：x < 700 的武将是攻方，x > 1000 的武将是守方
        # 国家简写不参与武将匹配
        faction_chars = {"夏", "唐", "秦", "汉", "周", "宋", "商", "楚", "赵", "魏", "吴", "蜀", "齐", "燕", "韩"}
        heroes_a = []
        heroes_b = []
        for block in blocks:
            text = block.text.strip()
            matched = False
            # 跳过单个国家简写字符
            if text in faction_chars:
                continue
            # 单字走专用映射（避免 "颜" 误匹配 "颜良"）
            if len(text) == 1 and text in self._single_char_map:
                candidates = self._single_char_map[text]
                hero_name = candidates[0]
                for c in candidates:
                    if block.center_x < 700 and c not in heroes_b:
                        hero_name = c
                        break
                    elif block.center_x >= 700 and c not in heroes_a:
                        hero_name = c
                        break
                if block.center_x < 700:
                    if hero_name not in heroes_a:
                        heroes_a.append(hero_name)
                else:
                    if hero_name not in heroes_b:
                        heroes_b.append(hero_name)
                continue
            for hero_name in self._sorted_heroes:
                if hero_name in text:
                    if block.center_x < 700:
                        if hero_name not in heroes_a:
                            heroes_a.append(hero_name)
                    else:
                        if hero_name not in heroes_b:
                            heroes_b.append(hero_name)
                    matched = True
                    break

        player_a = players[0] if len(players) > 0 else ""
        player_b = players[1] if len(players) > 1 else ""

        if not heroes_a and not heroes_b and heroes:
            heroes_a = heroes[:3]

        avg_conf = sum(b.confidence for b in blocks) / len(blocks) if blocks else 0

        return BattleReport(
            player_a=player_a,
            player_b=player_b,
            heroes_a=heroes_a[:3],
            heroes_b=heroes_b[:3],
            result=result,
            season=self.season,
            timestamp=timestamp,
            location=location,
            raw_text=full_text,
            confidence=avg_conf,
        )

    def parse_single_report(self, ocr: OCRResult) -> Optional[BattleReport]:
        """解析单条战报详情页。"""
        reports = self.parse(ocr)
        return reports[0] if reports else None

    @staticmethod
    def _mean_confidence(ocr: OCRResult) -> float:
        if not ocr.blocks:
            return 0.0
        return sum(b.confidence for b in ocr.blocks) / len(ocr.blocks)
