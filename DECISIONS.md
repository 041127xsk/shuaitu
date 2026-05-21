# DECISIONS.md

## ADR-001: 以官网文章 feed 作为主战法抽取来源
日期：2026-04-25
状态：已采用

背景：
武将志首页和目录页能提供武将入口，但真正的主战法、正文段落和图片信息在文章 feed 里更完整。单靠目录页不足以拿到战法详情。

决策：
以 `https://inf.ds.163.com/v1/web/feed/basic/facade?feedId=<id>&squareId=` 作为主战法抽取的主数据源。

原因：
- feed 里能拿到结构化正文。
- 能同时解析文本和图片。
- 比直接爬 HTML 更稳定，也更适合后续抽取主战法。

影响：
- 抓取链路需要先从目录页解析文章链接，再请求 feed。
- 解析逻辑需要兼容不同历史文章格式。

替代方案：
- 直接抓网页 HTML。
- 直接依赖浏览器自动化截取页面渲染结果。

## ADR-002: 使用 `wujiangInfo.json` 作为武将基础目录
日期：2026-04-25
状态：已采用

背景：
官网存在一个公开的武将基础目录 JSON，包含 `id / name / quality / star / contory / cost / type / image` 等元信息。

决策：
用 `wujiangInfo.json` 作为英雄目录、星级过滤和基础元信息来源。

原因：
- 数据比手工维护的 URL 列表更稳定。
- 适合做高星过滤和阵营筛选。
- 字段足够支撑当前 MVP 的元信息需求。

影响：
- 目前四维属性并不在这个 JSON 里，后续若要补四维，需要继续从文章详情或图片里抽。
- 目录里的字段命名沿用了源站字段，如 `contory`，暂时不强行改名，避免下游混淆。

替代方案：
- 手工维护一份英雄清单。
- 从页面 HTML 中临时解析元信息。

## ADR-003: 仅抓高星武将，暂不覆盖全量低星武将
日期：2026-04-25
状态：已采用

背景：
用户已明确后续抓取只保留 5 星 / 高星武将，当前目标先把点名武将和晋阵营高星武将抓完。

决策：
`scripts/fetch_targets.py` 只保留 `star >= 4` 或 `quality` 以 `SR` 结尾的武将。

原因：
- MVP 阶段先控制数据规模。
- 高星武将更符合后续阵容推荐的主要使用场景。
- 可以减少无效抓取和存储成本。

影响：
- 当前导出的 JSON 只覆盖高星英雄（当前约 156 个高星武将中部分有文章链接）。
- 后续如果要做全量库，需要补增量抓取和更完整的目录导入逻辑。

替代方案：
- 全量抓取后再做业务过滤。

## ADR-004: 只保留主战法，不抓拆解战法
日期：2026-04-25
状态：已采用

背景：
武将志文章里除了主战法，还可能包含拆解战法、搭配参考和其他章节，但当前项目的主数据只需要武将四维和主战法。

决策：
抽取流程只保留主战法详情，忽略拆解战法和其它无关章节。

原因：
- 当前项目目标聚焦阵容推荐和评分，拆解战法对主链路帮助不大。
- 减少噪音可以让结构化输出更稳定。
- 以后要扩展时，可以再把参考段落作为附加信息单独存储。

影响：
- 生成文件更轻。
- 解析器必须能区分主战法与其他章节。

替代方案：
- 全部章节都抓下来，后续再筛选。

## ADR-005: 先产出 JSON 快照，再补 SQLite
日期：2026-04-25
状态：已采用

背景：
当前仓库还没有数据库层，但抓取链路已经跑通了一部分，先把结构化结果稳定导出更容易验证解析质量。

决策：
先把批量抓取结果输出为 `data/fetched_heroes.json`，后续再把同样的数据写入 SQLite。

原因：
- JSON 更容易人工检查。
- 适合在 SQLite 层落地前做抽样验证。
- 可以先把抽取规则跑稳，再定数据库 schema。

影响：
- 当前已有 `data/heroes.db` SQLite 数据库（2026-04-25 建立），JSON 快照作为中间产物保留。

替代方案：
- 直接跳过 JSON，马上做 SQLite。

## ADR-006: 用启发式标题识别兼容多种历史文章格式
日期：2026-04-25
状态：已采用

背景：
官网武将志文章存在不同历史格式，有些章节标题是方括号样式，有些是旧式纯文本标题。

决策：
在 `src/article_extractor.py` 中使用启发式标题识别和 fallback 逻辑，兼容多种历史格式。

原因：
- 单一规则容易漏老文章。
- 当前数据源是历史内容，格式并不统一。

影响：
- 解析器能覆盖更多文章。
- 规则变化时需要同步测试，避免误把拆解战法当主战法。

替代方案：
- 只支持一种最新格式。

## ADR-007: 使用通义千问 dashscope 作为 AI 结构化抽取后端
日期：2026-04-26
状态：已采用

背景：
需要从战法散文描述中提取结构化字段（skill_type / trigger_rate / targets / effects 等），需要 LLM 能力。

决策：
使用阿里云通义千问 dashscope OpenAI 兼容接口，模型默认 `qwen/qwen3.5-flash`，API Key 通过 `DASHSCOPE_API_KEY` 环境变量注入。

原因：
- OpenAI 兼容接口方便复用 `openai` Python SDK。
- `qwen/qwen3.5-flash` 速度快、成本低，适合结构化抽取任务。
- dashscope 在国内访问稳定，不需要代理。
- 通过 `load_dotenv(override=True)` 从项目根目录 `.env` 自动加载，避免硬编码。

影响：
- AI 抽取依赖网络和 API 可用性，无 KEY 时降级返回空结构。
- prompt 设计需针对率土之滨游戏术语做专门优化。
- 抽取结果写入 SQLite AI 字段，通过 `upsert_skill_extraction()` 更新。

替代方案：
- 使用 OpenAI GPT-4 系列（成本高，需要代理）。
- 使用本地模型（需要 GPU 资源）。

## ADR-008: AI 抽取专注战斗类战法，忽略内政/政务类
日期：2026-04-26
状态：已采用

背景：
武将志文章中有些是内政武将，其战法是政务类，对阵容推荐无帮助。

决策：
在 `src/ai_extract.py` 的 system prompt 中明确指示：内政/政务类战法直接忽略，`skill_type` 留空。

原因：
- 减少噪音数据入库。
- 专注战斗类战法（主动/被动/指挥/典藏/兵种/阵法/追击）。
- 与 ADR-004 保持一致，主战法解析层已经通过 SECTION_TITLES 白名单过滤了"内政"章节。

影响：
- `skill_type` 为空字符串不代表出错，可能是内政武将或战法描述未明确类型。
- `SkillExtraction.is_empty()` 只检查 skill_name 和 skill_type 是否同时为空。

替代方案：
- 全部战法都抽取，后续在评分层过滤。
- 先通过星级/阵营预判武将类型再决定是否调用 AI。

## ADR-009: SQLite 三表设计（heroes / primary_skills / crawl_state）
日期：2026-04-25
状态：已采用

背景：
需要持久化武将元信息、主战法详情和抓取状态，需要可查询的数据库层。

决策：
使用 SQLite 建三张表：
- `heroes`：武将元信息，`feed_id` 作为唯一键。
- `primary_skills`：主战法详情，每武将一条，`hero_id` 外键引用 heroes。
- `crawl_state`：抓取状态追踪，`feed_id` 唯一键，记录 pending/done/error 状态。

原因：
- 三表分离，元信息、战法和状态解耦，互不影响。
- heroes 和 primary_skills 一对一是合理建模。
- crawl_state 支持断点续跑和失败重试。
- 全部用 `CREATE TABLE IF NOT EXISTS` 和 `ON CONFLICT DO UPDATE`，幂等可重复执行。

影响：
- AI 抽取字段（skill_type / trigger_rate / targets / effects_json 等）作为 nullable 列加到 primary_skills 表。
- `migrate_ai_fields()` 提供幂等字段迁移，向已有 DB 补充新列。

替代方案：
- 只用一张大表（数据冗余、查询不便）。
- 使用 PostgreSQL/MySQL（增加运维复杂度，不适合 MVP 阶段）。

## 发现记录：python-dotenv 缺失
日期：2026-04-26
状态：已修复

背景：
`src/ai_extract.py` 依赖 `python-dotenv` 从 `.env` 加载环境变量，但 `requirements.txt` 中未列出该依赖。

决策：
在 `requirements.txt` 中添加 `python-dotenv>=1.0.0`。

原因：
- `load_dotenv()` 是显式依赖，必须在 requirements.txt 中声明。
- 新环境运行 `pip install -r requirements.txt` 后即可正常使用，无需手动安装。

影响：
- 新环境不会因为 ImportError 报错。

## 发现记录：缺少 .gitignore
日期：2026-04-26
状态：已修复

背景：
仓库中没有 `.gitignore`，`apikey.txt` 和 `.env` 可能被提交到 git。

决策：
创建 `.gitignore`，排除 `.env`、`apikey.txt`、所有 `.db` 文件和 `data/*.json` 等生成产物。

原因：
- 防止真实 API key 泄漏。
- 防止生成产物污染仓库。

影响：
- `.gitignore` 覆盖范围：环境变量文件、API key 文件、数据库文件、抓取结果 JSON/CSV、Python 缓存、测试缓存、IDE 配置等。
