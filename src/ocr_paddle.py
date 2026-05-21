"""
ocr_paddle.py - RapidOCR 封装
==============================
使用 RapidOCR (PaddleOCR ONNX 版) 进行中文识别，
替代 Tesseract 以获得更好的游戏截图识别效果。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from rapidocr_onnxruntime import RapidOCR


@dataclass
class TextBlock:
    """一个识别到的文本块。"""
    text: str
    confidence: float
    box: list  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]

    @property
    def center_x(self) -> float:
        return sum(p[0] for p in self.box) / 4

    @property
    def center_y(self) -> float:
        return sum(p[1] for p in self.box) / 4

    @property
    def height(self) -> float:
        return max(p[1] for p in self.box) - min(p[1] for p in self.box)

    @property
    def width(self) -> float:
        return max(p[0] for p in self.box) - min(p[0] for p in self.box)


@dataclass
class OCRResult:
    """OCR 识别结果。"""
    blocks: List[TextBlock] = field(default_factory=list)
    raw_text: str = ""

    @property
    def texts(self) -> List[str]:
        return [b.text for b in self.blocks]

    def find_text(self, keyword: str) -> List[TextBlock]:
        """查找包含关键词的文本块。"""
        return [b for b in self.blocks if keyword in b.text]

    def find_by_y_range(self, y_min: float, y_max: float) -> List[TextBlock]:
        """查找 Y 坐标在指定范围内的文本块。"""
        return [b for b in self.blocks if y_min <= b.center_y <= y_max]


class GameOCR:
    """游戏截图 OCR 引擎。自动选择最优后端：PaddleOCR > RapidOCR。"""

    def __init__(self):
        self._backend = "rapid"
        self._paddle_ocr = None
        self._rapid_ocr = None

        # PaddleOCR 3.x 与 PaddlePaddle 3.3 有兼容问题，直接用 RapidOCR
        self._rapid_ocr = RapidOCR()

    def recognize(self, image_path: str, min_confidence: float = 0.5) -> OCRResult:
        """
        识别图片中的文字。

        参数:
            image_path: 图片路径
            min_confidence: 最低置信度阈值

        返回:
            OCRResult 对象
        """
        return self._recognize_rapid(image_path, min_confidence)
        if self._backend == "paddle":
            return self._recognize_paddle(image_path, min_confidence)
        return self._recognize_rapid(image_path, min_confidence)

    def _recognize_paddle(self, image_path: str, min_confidence: float) -> OCRResult:
        """用 PaddleOCR 识别。"""
        result = self._paddle_ocr.ocr(image_path, cls=True)
        blocks = []
        if result and result[0]:
            for line in result[0]:
                box, (text, conf) = line
                if conf >= min_confidence:
                    blocks.append(TextBlock(
                        text=text.strip(),
                        confidence=conf,
                        box=box
                    ))
        raw_text = "\n".join(b.text for b in blocks)
        return OCRResult(blocks=blocks, raw_text=raw_text)

    def _recognize_rapid(self, image_path: str, min_confidence: float) -> OCRResult:
        """用 RapidOCR 识别。"""
        result = self._rapid_ocr(image_path)
        blocks = []
        if result and result[0]:
            for box, text, conf in result[0]:
                if conf >= min_confidence:
                    blocks.append(TextBlock(
                        text=text.strip(),
                        confidence=conf,
                        box=box
                    ))
        raw_text = "\n".join(b.text for b in blocks)
        return OCRResult(blocks=blocks, raw_text=raw_text)

    def recognize_bytes(self, image_bytes: bytes, min_confidence: float = 0.5) -> OCRResult:
        """从字节流识别。"""
        result = self._engine(image_bytes)

        blocks = []
        if result and result[0]:
            for box, text, conf in result[0]:
                if conf >= min_confidence:
                    blocks.append(TextBlock(
                        text=text.strip(),
                        confidence=conf,
                        box=box
                    ))

        raw_text = "\n".join(b.text for b in blocks)
        return OCRResult(blocks=blocks, raw_text=raw_text)
