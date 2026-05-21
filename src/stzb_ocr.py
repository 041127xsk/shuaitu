"""
stzb-ocr.py - 率土之滨战报分层 OCR 引擎
========================================
分层架构：
- 基础层 (RapidOCR)：快速处理结构化数据，~50ms/张
- 增强层 (Qwen VL)：低置信度样本补全，~2s/张

置信度阈值：avg < 0.85 或单字 < 0.7 时触发 VL

用法：
    from src.stzb_ocr import StzbOCR
    ocr = StzbOCR()
    result = ocr.recognize("battle_report.png")
"""
from __future__ import annotations

import os
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# 置信度阈值
CONF_THRESHOLD_AVG = 0.85   # 平均置信度低于此值触发 VL
CONF_THRESHOLD_LOW = 0.70   # 单块置信度低于此值标记为低置信度

# 结构化校验权重
WEIGHT_NUMERICAL = 0.4      # 数值置信度权重
WEIGHT_STRUCTURAL = 0.6     # 结构化校验权重
HYBRID_THRESHOLD = 0.75     # 混合评分低于此值触发 VL


@dataclass
class ConfidenceScore:
    """混合置信度评分"""
    numerical: float = 0.0      # 数值置信度 (0-1)
    structural: float = 0.0     # 结构化校验分数 (0-1)
    hybrid: float = 0.0         # 混合评分 (0-1)
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}

    def should_trigger_vl(self, threshold: float = HYBRID_THRESHOLD) -> bool:
        """是否应该触发 VL"""
        return self.hybrid < threshold


@dataclass
class TextBlock:
    """OCR 识别的文本块"""
    text: str
    confidence: float
    box: Any = None

    @property
    def center_x(self) -> float:
        if self.box and hasattr(self.box, '__len__') and len(self.box) >= 4:
            return sum(p[0] for p in self.box) / 4
        return 0

    @property
    def center_y(self) -> float:
        if self.box and hasattr(self.box, '__len__') and len(self.box) >= 4:
            return sum(p[1] for p in self.box) / 4
        return 0


@dataclass
class OCRResult:
    """OCR 识别结果"""
    raw_text: str
    confidence: float
    blocks: List[TextBlock] = field(default_factory=list)
    reports: List[Dict[str, Any]] = field(default_factory=list)
    engine: str = "rapid"        # rapid / vl / layered
    vl_triggered: bool = False   # 是否触发了 VL 增强

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "confidence": self.confidence,
            "engine": self.engine,
            "vl_triggered": self.vl_triggered,
            "reports": self.reports,
        }


class StzbOCR:
    """
    分层 OCR 引擎

    流程：
    1. RapidOCR 快速扫描（~50ms）
    2. 检查平均置信度
    3. 如果 < 0.85，调用 Qwen VL 补全（~2s）
    4. 合并结果返回
    """

    def __init__(self, vl_threshold: float = CONF_THRESHOLD_AVG):
        self._rapid_ocr = None
        self._vl_ocr = None
        self._vl_threshold = vl_threshold
        self._init_backends()

    def _init_backends(self):
        """初始化 OCR 后端"""
        # RapidOCR（基础层）
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._rapid_ocr = RapidOCR()
            logger.info("RapidOCR initialized")
        except Exception as e:
            logger.error(f"RapidOCR init failed: {e}")

        # Qwen VL（增强层）
        try:
            from src.qwen_vl_ocr import QwenVLOCR
            self._vl_ocr = QwenVLOCR()
            logger.info("Qwen VL OCR initialized")
        except Exception as e:
            logger.warning(f"Qwen VL not available: {e}")

    def recognize(self, image_path: str, force_vl: bool = False) -> OCRResult:
        """
        识别战报截图。

        参数:
            image_path: 截图路径
            force_vl: 强制使用 VL（跳过 RapidOCR）

        返回:
            OCRResult 对象
        """
        if force_vl:
            return self._recognize_vl(image_path)

        # 第一层：RapidOCR 快扫
        rapid_result = self._recognize_rapid(image_path)

        # 混合置信度评估
        score = self._evaluate_confidence(rapid_result)
        rapid_result.confidence = score.hybrid

        logger.info(
            f"Confidence: numerical={score.numerical:.2f}, "
            f"structural={score.structural:.2f}, hybrid={score.hybrid:.2f}"
        )

        # 判断是否需要 VL 增强
        if score.should_trigger_vl(self._vl_threshold) and self._vl_ocr:
            logger.info(f"VL triggered: hybrid_score={score.hybrid:.2f}")
            vl_result = self._recognize_vl(image_path)
            vl_result.vl_triggered = True
            vl_result.engine = "layered"
            return vl_result

        return rapid_result

    def _recognize_rapid(self, image_path: str) -> OCRResult:
        """RapidOCR 识别"""
        if not self._rapid_ocr:
            return OCRResult(raw_text="", confidence=0, engine="rapid")

        result = self._rapid_ocr(image_path)
        blocks = []
        if result and result[0]:
            for box, text, conf in result[0]:
                blocks.append(TextBlock(text=text.strip(), confidence=conf, box=box))

        raw_text = "\n".join(b.text for b in blocks)
        avg_conf = sum(b.confidence for b in blocks) / len(blocks) if blocks else 0

        # 用 report_parser 解析战报
        reports = self._parse_reports(raw_text, blocks)

        return OCRResult(
            raw_text=raw_text,
            confidence=avg_conf,
            blocks=blocks,
            reports=reports,
            engine="rapid",
        )

    def _recognize_vl(self, image_path: str) -> OCRResult:
        """Qwen VL 识别"""
        if not self._vl_ocr:
            return OCRResult(raw_text="", confidence=0, engine="vl")

        vl_result = self._vl_ocr.recognize_battle_report(image_path)

        reports = vl_result.get("reports", [])
        raw_text = "\n".join(
            f"{r.get('player_a','')} vs {r.get('player_b','')}: "
            f"{'、'.join(r.get('heroes_a',[]))} vs {'、'.join(r.get('heroes_b',[]))}"
            for r in reports
        )

        return OCRResult(
            raw_text=raw_text,
            confidence=0.98,  # VL 置信度默认高
            reports=reports,
            engine="vl",
        )

    def _parse_reports(self, raw_text: str, blocks: List[TextBlock]) -> List[Dict[str, Any]]:
        """用 report_parser 解析战报"""
        try:
            from src.report_parser import BattleReportParser
            from src.ocr_paddle import OCRResult as ParserOCRResult, TextBlock as ParserTextBlock

            parser = BattleReportParser(season="5607")
            parser_blocks = [
                ParserTextBlock(text=b.text, confidence=b.confidence, box=b.box or [[0,0],[0,0],[0,0],[0,0]])
                for b in blocks
            ]
            ocr_result = ParserOCRResult(blocks=parser_blocks, raw_text=raw_text)
            reports = parser.parse(ocr_result)

            return [r.to_dict() for r in reports]
        except Exception as e:
            logger.error(f"Report parsing failed: {e}")
            return []

    def _evaluate_confidence(self, result: OCRResult) -> ConfidenceScore:
        """
        混合置信度评估

        数值置信度 (40%): RapidOCR 返回的平均置信度
        结构化校验 (60%): 检查识别结果是否合理

        结构化校验项：
        1. 武将名命中率 - 识别出的武将名有多少在已知列表中
        2. 战报完整性 - 是否有胜负、玩家名、时间戳
        3. 阵容合理性 - 是否有 ≥2 个武将
        """
        from src.report_parser import KNOWN_HEROES

        score = ConfidenceScore()

        # === 数值置信度 ===
        if result.blocks:
            score.numerical = sum(b.confidence for b in result.blocks) / len(result.blocks)
        else:
            score.numerical = 0.0

        # === 结构化校验 ===
        checks = {}
        total_weight = 0
        weighted_sum = 0

        # 1. 武将名命中率 (权重 35)
        hero_hits = 0
        hero_total = 0
        for report in result.reports:
            for hero in (report.get("heroes_a", []) + report.get("heroes_b", [])):
                hero_total += 1
                if hero in KNOWN_HEROES:
                    hero_hits += 1
        hero_rate = hero_hits / max(hero_total, 1)
        checks["hero_hit_rate"] = {"hits": hero_hits, "total": hero_total, "rate": hero_rate}
        weighted_sum += hero_rate * 35
        total_weight += 35

        # 2. 战报完整性 (权重 35)
        completeness = 0
        completeness_details = {}
        for report in result.reports:
            has_result = report.get("result", "") in ("win", "loss", "draw")
            has_players = bool(report.get("player_a", "")) and bool(report.get("player_b", ""))
            has_timestamp = bool(report.get("timestamp", ""))
            has_heroes = len(report.get("heroes_a", []) + report.get("heroes_b", [])) >= 2

            completeness_details = {
                "has_result": has_result,
                "has_players": has_players,
                "has_timestamp": has_timestamp,
                "has_heroes": has_heroes,
            }
            # 只要有任意一条战报完整就算通过
            if has_result and has_heroes:
                completeness = 1.0 if has_players and has_timestamp else 0.8
                break
            elif has_heroes:
                completeness = 0.5
        checks["completeness"] = {**completeness_details, "score": completeness}
        weighted_sum += completeness * 35
        total_weight += 35

        # 3. 阵容合理性 (权重 30)
        has_reports = len(result.reports) > 0
        has_multiple_heroes = any(
            len(r.get("heroes_a", [])) + len(r.get("heroes_b", [])) >= 4
            for r in result.reports
        )
        lineup_score = 0.0
        if has_multiple_heroes:
            lineup_score = 1.0
        elif has_reports:
            lineup_score = 0.5
        checks["lineup"] = {"has_reports": has_reports, "score": lineup_score}
        weighted_sum += lineup_score * 30
        total_weight += 30

        # 结构化总分
        score.structural = weighted_sum / total_weight if total_weight > 0 else 0
        score.details = checks

        # === 混合评分 ===
        score.hybrid = (
            score.numerical * WEIGHT_NUMERICAL
            + score.structural * WEIGHT_STRUCTURAL
        )

        return score


# Skill 封装函数
def extract_battle_report(image_path: str, force_vl: bool = False) -> Dict[str, Any]:
    """
    提取战报数据的 Skill 函数

    Args:
        image_path: 战报截图路径
        force_vl: 强制使用 VL

    Returns:
        结构化 JSON 数据
    """
    ocr = StzbOCR()
    result = ocr.recognize(image_path, force_vl=force_vl)
    return result.to_dict()
