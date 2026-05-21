"""
ai_extract.py - AI 结构化抽取封装
===============================
把战法散文扔给 LLM，吐结构化字段。

依赖：
    openai>=1.40.0（已在 requirements.txt）
    pydantic>=2.0（内置，仅作类型声明用 dataclass）

环境变量（从 .env 读取）：
    DASHSCOPE_API_KEY（阿里云通义千问 API Key）
    DASHSCOPE_BASE_URL（默认 https://dashscope.aliyuncs.com/compatible-mode/v1）
    DASHSCOPE_MODEL    （默认 qwen/qwen3.5-flash）
    DASHSCOPE_TIMEOUT  （默认 30 秒）
    DASHSCOPE_MAX_RETRIES（默认 3 次）
"""
from __future__ import annotations

import os
import time
from pathlib import Path

# 加载 .env，强制覆盖系统环境变量（避免 Windows 系统级 Key 干扰）
_dotenv_path = Path(__file__).resolve().parents[1] / ".env"
from dotenv import load_dotenv
load_dotenv(_dotenv_path, override=True)
import logging
from dataclasses import asdict, dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
MODEL = os.getenv("DASHSCOPE_MODEL", "qwen/qwen3.5-flash")
TIMEOUT = int(os.getenv("DASHSCOPE_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("DASHSCOPE_MAX_RETRIES", "3"))


# ---------------------------------------------------------------------------
# 输出 schema（dataclass，方便序列化）
# ---------------------------------------------------------------------------

@dataclass
class SkillEffect:
    """单个效果，如"暴走2回合"、"谋略降低30%" """
    description: str          # 效果描述原文
    category: Optional[str] = None   # 效果分类：属性变化/特殊状态/伤害/治疗/防御...（可选）


@dataclass
class SkillExtraction:
    """
    战法结构化抽取结果。
    字段尽量和 rate土 战法机制对齐，方便后续评分模块直接使用。
    """
    # 基本信息
    skill_name: str           # 战法名称，如"闭月"
    skill_type: str           # 战法大类：主动/被动/指挥/内政/典藏/兵种/阵法/追击
    trigger_type: Optional[str] = None  # 瞬发 / 准备 / 追击（追击战法有独立分类）

    # 发动条件
    trigger_rate: Optional[int] = None   # 发动概率，0-100 的整数
    trigger_condition: Optional[str] = None  # 发动条件描述，如"战斗中，每次友军主动攻击后"

    # 作用目标
    targets: Optional[str] = None   # 如"敌军群体(2人)"、"己方单体"、"敌军全体"

    # 效果列表
    effects: list[SkillEffect] = field(default_factory=list)

    # 补充
    duration: Optional[str] = None  # 持续时间，如"3回合"、"持续至战斗结束"
    notes: Optional[str] = None    # 其他补充，如"受谋略属性影响"、"无法清除"

    # 元信息
    raw_paragraphs_sample: Optional[str] = None  # 原始段落前3条（方便溯源）

    def to_dict(self) -> dict:
        d = asdict(self)
        # effects 里的 None 也保留，方便 JSON 一致处理
        return d

    def is_empty(self) -> bool:
        return not (self.skill_name or self.skill_type)


# ---------------------------------------------------------------------------
# 提示词
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """你是一个《率土之滨》游戏攻略 AI，负责从武将攻略文章中抽取战法信息。

输出要求：
- 严格按 JSON 格式输出，不要有额外文字。
- 所有字段尽量填，实在不确定的填 null，不要编造。
- 发动概率填整数（0-100），不要填文字描述。
- 效果列表尽量拆成单条，每条填 description 字段。
- 如果战法文本中找不到战法类型，填 null，不要猜测。

    参考分类（只填战斗类战法，內政/政务类战法直接忽略，skill_type 留空）：
- skill_type（战法大类）：主动/被动/指挥/典藏/兵种/阵法/追击
- trigger_type（触发类型）：瞬发/准备
- category（效果分类）：属性变化/控制效果/伤害/治疗/防御/特殊/增益/减益
"""


USER_PROMPT_TEMPLATE = """从以下战法文本中抽取结构化信息。

【战法文本】
{paragraphs_text}

请返回以下 JSON（只返回 JSON，不要其他内容）：
{{
    "skill_name": "战法名称",
    "skill_type": "主动",
    "trigger_type": "瞬发",
    "trigger_rate": 45,
    "trigger_condition": "战斗中，...",
    "targets": "敌军群体(2人)",
    "effects": [
        {{"description": "使目标陷入混乱状态，持续2回合", "category": "控制效果"}},
        {{"description": "每回合损失一定兵力", "category": "伤害"}}
    ],
    "duration": "2回合",
    "notes": "受谋略属性影响",
    "raw_paragraphs_sample": ""
}}"""


# ---------------------------------------------------------------------------
# LLM 调用
# ---------------------------------------------------------------------------

_client: Optional["OpenAI"] = None


def _get_client() -> "OpenAI":
    """构建（并缓存）OpenAI 兼容客户端，按需降级禁用 SSL 验证。"""
    global _client
    if _client is not None:
        return _client

    from openai import OpenAI
    import httpx

    for skip_verify in (False, True):
        try:
            # 强制禁用代理，避免VPN/代理导致的SSL问题
            # httpx通过环境变量或TrustEnv控制代理，这里设置空环境来禁用
            import os
            for _env_key in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"]:
                os.environ[_env_key] = ""
            os.environ["NO_PROXY"] = "*"

            http_client = httpx.Client(
                timeout=httpx.Timeout(float(TIMEOUT)),
                verify=not skip_verify,
                trust_env=False,  # 不从环境变量读取代理
            )
            client_kwargs: dict = {
                "api_key": API_KEY,
                "http_client": http_client,
            }
            if BASE_URL:
                client_kwargs["base_url"] = BASE_URL
            client = OpenAI(**client_kwargs)
            # 发一个轻量请求试探连通性
            client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            _client = client
            if skip_verify:
                logger.warning("SSL 验证已禁用（降级模式），请留意安全提示")
            return client
        except Exception as exc:
            if skip_verify:
                logger.error("AI 客户端构建失败（已尝试禁用SSL）: %s", exc)
                raise
            logger.warning("AI 客户端 SSL 握手失败，降级重试（禁用验证）: %s", exc)

    # 静态分析兜底（永远不会走到）
    raise RuntimeError("AI client init failed")


# 兼容旧名
_build_client = _get_client


def _call_llm(paragraphs_text: str, *, retry_count: int = 0) -> dict:
    """
    调用 LLM，返回解析后的 dict。
    失败时按指数退避重试，MAX_RETRIES 次后返回空 dict。
    """
    if not API_KEY:
        logger.warning("DASHSCOPE_API_KEY 未设置，跳过 AI 抽取")
        return {}

    try:
        client = _build_client()
        user_prompt = USER_PROMPT_TEMPLATE.format(paragraphs_text=paragraphs_text)

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,   # 低随机性，保证抽取稳定性
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        import json
        return json.loads(raw)

    except Exception as exc:
        if retry_count < MAX_RETRIES:
            wait = 2 ** retry_count
            logger.warning("AI 抽取失败，第 %d 次重试，%ds 后重试: %s", retry_count + 1, wait, exc)
            time.sleep(wait)
            return _call_llm(paragraphs_text, retry_count=retry_count + 1)
        else:
            logger.error("AI 抽取失败，已达最大重试次数: %s", exc)
            return {}


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def extract_skill_details(
    paragraphs: list[str],
    *,
    skill_name_hint: str = "",
) -> SkillExtraction:
    """
    把战法段落列表转成结构化 SkillExtraction。

    参数:
        paragraphs:     战法描述段落列表（来自 article_extractor 的 paragraphs）
        skill_name_hint: 战法名称（来自 extract_primary_skill_info 的 name 字段，
                        用于补充抽取不到名称时兜底）

    返回:
        SkillExtraction 对象。失败时返回 skill_name=skill_name_hint 的空结果。

    调用方不需要 try/except，此函数保证不抛异常。
    """
    if not paragraphs:
        return SkillExtraction(skill_name=skill_name_hint, skill_type="")

    # 取前3段作为 LLM 输入，避免 token 浪费
    sample = paragraphs[:3]
    paragraphs_text = "\n".join(f"- {p}" for p in sample)

    result = _call_llm(paragraphs_text)
    if not result:
        return SkillExtraction(skill_name=skill_name_hint, skill_type="")

    # 兜底：LLM 没返回名称时用 hint
    if not result.get("skill_name") and skill_name_hint:
        result["skill_name"] = skill_name_hint

    # 构建 SkillEffect 列表
    effects = []
    for e in (result.get("effects") or []):
        if isinstance(e, dict):
            effects.append(SkillEffect(
                description=e.get("description", ""),
                category=e.get("category"),
            ))
        elif isinstance(e, str):
            effects.append(SkillEffect(description=e))

    return SkillExtraction(
        skill_name=result.get("skill_name") or skill_name_hint,
        skill_type=result.get("skill_type") or "",
        trigger_type=result.get("trigger_type"),
        trigger_rate=result.get("trigger_rate"),
        trigger_condition=result.get("trigger_condition"),
        targets=result.get("targets"),
        effects=effects,
        duration=result.get("duration"),
        notes=result.get("notes"),
        raw_paragraphs_sample=paragraphs_text,
    )


# ---------------------------------------------------------------------------
# 便捷包装（用于 load_to_sqlite 流水线）
# ---------------------------------------------------------------------------

def enrich_skill(
    paragraphs: list[str],
    skill_name_hint: str = "",
) -> dict:
    """
    给定 paragraphs，返回适合直接塞进 SQLite 的 dict。
    字段和 primary_skills 表结构对齐。
    """
    extraction = extract_skill_details(paragraphs, skill_name_hint=skill_name_hint)
    return {
        "skill_name": extraction.skill_name,
        "skill_type": extraction.skill_type,
        "trigger_type": extraction.trigger_type,
        "trigger_rate": extraction.trigger_rate,
        "trigger_condition": extraction.trigger_condition,
        "targets": extraction.targets,
        "effects": [e.description for e in extraction.effects],
        "duration": extraction.duration,
        "notes": extraction.notes,
        "ai_extracted": True,
    }
