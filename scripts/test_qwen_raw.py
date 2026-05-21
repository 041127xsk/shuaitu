import os, json
from dotenv import load_dotenv
load_dotenv(dotenv_path="C:/Users/27557/Documents/New project/.env")

import httpx
from openai import OpenAI

api_key = os.getenv("DASHSCOPE_API_KEY", "")
base_url = os.getenv("DASHSCOPE_BASE_URL", "")
model = os.getenv("DASHSCOPE_MODEL", "")

paragraphs_text = "- 战斗开始后每回合使我军群体2人伤害提升15%，受谋略属性影响，持续3回合\n- 战斗中，每次友军主动攻击后，我军群体2人进行一次追击"

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

http_client = httpx.Client(timeout=httpx.Timeout(30.0), verify=False)
client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)

user_prompt = USER_PROMPT_TEMPLATE.format(paragraphs_text=paragraphs_text)
resp = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ],
    temperature=0.1,
    response_format={"type": "json_object"},
)
raw = resp.choices[0].message.content or "{}"
print("原始返回:")
print(raw)
print()
result = json.loads(raw)
print("解析后:")
print(json.dumps(result, ensure_ascii=False, indent=2))
