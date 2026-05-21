"""
test_ai_extract.py - AI 抽取模块单测
不访问真实 API，用 unittest.mock 模拟 LLM 响应。
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
import json

from src.ai_extract import (
    extract_skill_details,
    enrich_skill,
    SkillExtraction,
    SkillEffect,
    _call_llm,
)


# ---------------------------------------------------------------------------
# Mock LLM 响应（真实数据样例）
# ---------------------------------------------------------------------------

MOCK_LLM_RESPONSE = {
    "skill_name": "闭月",
    "skill_type": "主动",
    "trigger_type": "瞬发",
    "trigger_rate": 45,
    "trigger_condition": "战斗中，友军造成伤害后",
    "targets": "敌军群体(2人)",
    "effects": [
        {"description": "使敌军群体陷入暴走状态，持续3回合", "category": "控制效果"},
        {"description": "降低目标防御属性", "category": "属性变化"},
    ],
    "duration": "3回合",
    "notes": "受谋略属性影响",
}


MOCK_LLM_RESPONSE_NO_KEY = {}


def _mock_response(*args, **kwargs) -> dict:
    return MOCK_LLM_RESPONSE


def _mock_response_no_key(*args, **kwargs) -> dict:
    return MOCK_LLM_RESPONSE_NO_KEY


# ---------------------------------------------------------------------------
# 测试 extract_skill_details
# ---------------------------------------------------------------------------

class TestExtractSkillDetails:
    def test_basic_extraction(self):
        """正常调用 LLM，返回正确字段"""
        with patch("src.ai_extract._call_llm", _mock_response):
            result = extract_skill_details(
                ["貂蝉的战法【闭月】，对得起这个形容貂蝉的这个名号，【闭月】能让对方群体暴走3回合，3回合！"],
                skill_name_hint="闭月",
            )
        assert result.skill_name == "闭月"
        assert result.skill_type == "主动"
        assert result.trigger_type == "瞬发"
        assert result.trigger_rate == 45
        assert result.targets == "敌军群体(2人)"
        assert len(result.effects) == 2
        assert result.effects[0].description == "使敌军群体陷入暴走状态，持续3回合"
        assert result.effects[0].category == "控制效果"

    def test_hints_used_as_fallback(self):
        """LLM 没返回 skill_name 时，fallback 到 hint"""
        with patch("src.ai_extract._call_llm", return_value={"skill_type": "主动"}):
            result = extract_skill_details(
                ["战法描述"],
                skill_name_hint="闭月",
            )
        assert result.skill_name == "闭月"

    def test_empty_paragraphs_returns_empty(self):
        """空 paragraphs 返回 skill_name=空字符串"""
        result = extract_skill_details([])
        assert result.skill_name == ""
        assert result.skill_type == ""

    def test_empty_paragraphs_with_hint(self):
        """空 paragraphs 但有 hint，返回 hint 名称"""
        result = extract_skill_details([], skill_name_hint="天下无双")
        assert result.skill_name == "天下无双"
        assert result.is_empty() is False

    def test_llm_returns_empty_dict(self):
        """LLM 返回空 dict 时降级处理"""
        with patch("src.ai_extract._call_llm", return_value={}):
            result = extract_skill_details(
                ["战法描述"],
                skill_name_hint="闭月",
            )
        assert result.skill_name == "闭月"
        assert result.trigger_rate is None

    def test_effects_parsed_correctly(self):
        """effects 字段可以接受 dict 或 str"""
        with patch("src.ai_extract._call_llm", return_value={
            "skill_name": "测试",
            "skill_type": "主动",
            "effects": [
                {"description": "效果1", "category": "伤害"},
                "纯字符串效果",
            ],
        }):
            result = extract_skill_details(["描述"])
        assert len(result.effects) == 2
        assert result.effects[0].description == "效果1"
        assert result.effects[1].description == "纯字符串效果"

    def test_raw_paragraphs_sample_set(self):
        """raw_paragraphs_sample 取前3段"""
        with patch("src.ai_extract._call_llm", _mock_response):
            paragraphs = ["第1段", "第2段", "第3段", "第4段", "第5段"]
            result = extract_skill_details(paragraphs)
        # 前3段
        assert "第1段" in result.raw_paragraphs_sample
        assert "第3段" in result.raw_paragraphs_sample
        assert "第4段" not in result.raw_paragraphs_sample

    def test_to_dict_serialization(self):
        """to_dict 能正确序列化"""
        with patch("src.ai_extract._call_llm", _mock_response):
            result = extract_skill_details(["战法描述"], skill_name_hint="闭月")
        d = result.to_dict()
        assert "skill_name" in d
        assert "effects" in d
        assert isinstance(d["effects"], list)


# ---------------------------------------------------------------------------
# 测试 enrich_skill
# ---------------------------------------------------------------------------

class TestEnrichSkill:
    def test_enrich_skill_returns_dict(self):
        """enrich_skill 返回扁平 dict，适合直接塞 SQLite"""
        with patch("src.ai_extract._call_llm", _mock_response):
            result = enrich_skill(
                ["貂蝉的战法【闭月】，..."],
                skill_name_hint="闭月",
            )
        assert result["skill_name"] == "闭月"  # LLM 返回值优先于 hint
        assert result["skill_type"] == "主动"
        assert result["trigger_rate"] == 45
        assert result["targets"] == "敌军群体(2人)"
        assert result["effects"] == [
            "使敌军群体陷入暴走状态，持续3回合",
            "降低目标防御属性",
        ]
        assert result["ai_extracted"] is True

    def test_enrich_skill_no_api_key(self):
        """无 API_KEY 时返回兜底结构，不抛异常"""
        with patch("src.ai_extract.API_KEY", ""):
            result = enrich_skill(["战法描述"], skill_name_hint="测试")
        assert result["skill_name"] == "测试"
        assert result["ai_extracted"] is True
        assert result["skill_type"] == ""


# ---------------------------------------------------------------------------
# 测试 _call_llm 重试逻辑
# ---------------------------------------------------------------------------

def _make_mock_response(data: dict):
    """构造一个模拟 OpenAI chat completion 响应对象"""
    mock_message = MagicMock()
    mock_message.content = json.dumps(data)
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


class TestCallLlmRetry:
    def test_retry_on_failure(self):
        """失败时指数退避重试，最终返回成功结果"""
        call_count = 0

        def flaky_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("模拟网络错误")
            return _make_mock_response({"skill_name": "测试", "skill_type": "主动"})

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = flaky_create

        with patch("src.ai_extract._build_client", return_value=mock_client):
            with patch("src.ai_extract.MAX_RETRIES", 2):
                with patch("src.ai_extract.TIMEOUT", 1):
                    result = _call_llm("test")
        # 2次失败后第3次成功
        assert result["skill_name"] == "测试"
        assert call_count == 3

    def test_max_retries_exceeded(self):
        """超过最大重试次数后返回空 dict，不抛异常"""
        call_count = 0

        def always_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("持续失败")

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = always_fail

        with patch("src.ai_extract._build_client", return_value=mock_client):
            with patch("src.ai_extract.MAX_RETRIES", 2):
                with patch("src.ai_extract.TIMEOUT", 0):
                    result = _call_llm("test")

        assert result == {}
        assert call_count == 3  # 初始1次 + 2次重试


# ---------------------------------------------------------------------------
# 测试 SkillExtraction dataclass
# ---------------------------------------------------------------------------

class TestSkillExtractionDataclass:
    def test_is_empty_true(self):
        e = SkillExtraction(skill_name="", skill_type="")
        assert e.is_empty() is True

    def test_is_empty_false_with_name(self):
        e = SkillExtraction(skill_name="闭月", skill_type="主动")
        assert e.is_empty() is False

    def test_default_effects_list(self):
        e = SkillExtraction(skill_name="测试", skill_type="主动")
        assert isinstance(e.effects, list)
        assert len(e.effects) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
