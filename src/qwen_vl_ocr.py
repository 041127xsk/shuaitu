"""
qwen_vl_ocr.py - Qwen VL 视觉 OCR 增强层
==========================================
用通义千问 VL 模型识别战报截图，提取结构化数据。
用于 PaddleOCR/RapidOCR 置信度不够时的补全。

用法：
    from src.qwen_vl_ocr import QwenVLOCR
    ocr = QwenVLOCR()
    result = ocr.recognize_battle_report("screenshot.png")
"""
from __future__ import annotations

import os
import base64
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from dotenv import load_dotenv

_dotenv_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_dotenv_path, override=True)

logger = logging.getLogger(__name__)


class QwenVLOCR:
    """Qwen VL 视觉 OCR 引擎"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        self.model = model or os.getenv("DASHSCOPE_VL_MODEL", "qwen-vl-max")
        self.base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.timeout = int(os.getenv("DASHSCOPE_TIMEOUT", "30"))

        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY 未配置")

    def _image_to_base64(self, image_path: str) -> str:
        """将图片转为 base64"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def recognize_battle_report(self, image_path: str) -> Dict[str, Any]:
        """
        识别战报截图，提取结构化数据。

        参数:
            image_path: 截图路径

        返回:
            {
                "raw_text": "原始识别文本",
                "reports": [
                    {
                        "player_a": "攻方玩家",
                        "player_b": "守方玩家",
                        "heroes_a": ["武将1", "武将2", "武将3"],
                        "heroes_b": ["武将4", "武将5", "武将6"],
                        "result": "win/loss/draw",
                        "timestamp": "2026/05/03 20:57:54",
                        "location": "战斗地点"
                    }
                ]
            }
        """
        b64_image = self._image_to_base64(image_path)

        prompt = """请识别这张率土之滨的战报截图，提取以下信息：

1. 所有出现的武将名（注意区分攻方和守方，左侧是攻方，右侧是守方）
2. 玩家名（攻方和守方）
3. 战斗结果（胜利/失败/平局）
4. 时间戳
5. 战斗地点

请以 JSON 格式返回，格式如下：
{
  "reports": [
    {
      "player_a": "攻方玩家名",
      "player_b": "守方玩家名",
      "heroes_a": ["攻方武将1", "攻方武将2", "攻方武将3"],
      "heroes_b": ["守方武将1", "守方武将2", "守方武将3"],
      "result": "win/loss/draw",
      "timestamp": "YYYY/MM/DD HH:MM:SS",
      "location": "战斗地点"
    }
  ]
}

注意：
- 只返回 JSON，不要有其他文字
- 武将名必须是游戏中的完整名字（如：严颜、颜良、黄忠）
- 如果看不清某个字段，留空字符串或空数组
- result: "胜"或"胜利"对应"win"，"败"或"失败"对应"loss"，"平"对应"draw"
"""

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{b64_image}"
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
                temperature=0.1,
                max_tokens=2000,
            )

            content = response.choices[0].message.content.strip()

            # 提取 JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
            return result

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}, 原始响应: {content}")
            return {"raw_text": content, "reports": [], "error": str(e)}
        except Exception as e:
            logger.error(f"Qwen VL 调用失败: {e}")
            return {"reports": [], "error": str(e)}

    def recognize_text(self, image_path: str, prompt: str = "") -> str:
        """
        通用图片文字识别。

        参数:
            image_path: 图片路径
            prompt: 额外提示词

        返回:
            识别的文本
        """
        b64_image = self._image_to_base64(image_path)

        default_prompt = "请识别图片中的所有文字，按原始布局返回。"
        full_prompt = f"{default_prompt}\n{prompt}" if prompt else default_prompt

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{b64_image}"
                                },
                            },
                            {
                                "type": "text",
                                "text": full_prompt,
                            },
                        ],
                    }
                ],
                temperature=0.1,
                max_tokens=2000,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Qwen VL 调用失败: {e}")
            return f"Error: {e}"


# Skill 函数
def extract_battle_report_with_vl(image_path: str) -> Dict[str, Any]:
    """
    用 Qwen VL 提取战报数据

    Args:
        image_path: 战报截图路径

    Returns:
        结构化数据
    """
    ocr = QwenVLOCR()
    return ocr.recognize_battle_report(image_path)
