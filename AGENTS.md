# AGENTS.md

## 项目一句话概述
这个项目是一个面向策略游戏的"配将助手"MVP：从官网抓取武将志和武将目录数据，提取主战法与武将信息，存入 SQLite，后续扩展阵容评分与模拟对战系统。

## 后续 Agent 工作原则
- 修改代码前，先读 `PROJECT_MEMORY.md`、`RUNBOOK.md`、`SCRAPER_NOTES.md`、`TODO.md`。
- 不要擅自删除抓取脚本、配置模板、数据样本、测试文件或生成产物的说明。
- 不要提交真实 API key、Cookie、Token、账号密码、私钥、数据库密码。
  - ⚠️ 已在 `apikey.txt` 中发现疑似真实 API key，请勿提交到 git。
- 不要在不了解数据来源的情况下修改字段含义，尤其是 `star`、`quality`、`contory`、`type`、`feed_id`、`primary_skill`、`skill_type` 这些字段。
- 修改抓取逻辑后，必须说明对数据结构、抓取频率、失败重试、断点续跑和去重规则的影响。
- 运行高频抓取前，必须先确认目标站规则、限速、代理、登录态和相关环境变量。
- 不要用真实生产账号做测试。
- 不要把临时调试代码留在主流程里，尤其是 `scripts/fetch_targets.py` 和 `src/article_extractor.py` 这种入口路径。
- 不要把生成数据文件当成源码；`data/fetched_heroes.json` 是产物，不是权威定义。
- 所有脚本依赖 `.env` 文件时会自动从项目根目录加载（通过 `dotenv`），`src/ai_extract.py` 强制覆盖系统环境变量以避免 Windows 干扰。

## 推荐工作流程
1. 先读 `PROJECT_MEMORY.md`，确认当前实现状态。
2. 再读 `RUNBOOK.md`，确认已有命令和运行方式。
3. 再读 `SCRAPER_NOTES.md`，确认数据源、字段和限速约束。
4. 再检查 `TODO.md`，找出当前优先级最高的任务。
5. 最后开始改代码。

## 修改完成后的要求
- 更新 `PROJECT_MEMORY.md`，记录本次变更和当前状态。
- 更新 `TODO.md`，把已完成事项标掉，把新问题补进去。
- 更新 `DECISIONS.md`，把关键技术选择写成 ADR。
- 如果改了抓取逻辑，必须同步更新 `SCRAPER_NOTES.md`。
- 如果改了启动方式或环境变量，必须同步更新 `ENVIRONMENT.md` 和 `RUNBOOK.md`。
- 如果新增命令，必须同步更新 `RUNBOOK.md`。
- 如果新增生成产物或数据样本，要在文档里注明它们的用途和生命周期。

## 当前最该关注的文件
- `src/ai_extract.py` — AI 结构化抽取核心，使用通义千问 API
- `src/database.py` — SQLite 持久化层，三表设计
- `src/article_extractor.py` — 文章解析核心，标题识别和主战法判定
- `src/hero_catalog.py` — 武将目录，高星过滤
- `scripts/fetch_targets.py` — 批量抓取主入口，已接入 AI 抽取
- `scripts/load_to_sqlite.py` — SQLite 导入脚本
- `scripts/export_heroes.py` — 统一导出脚本（JSON / CSV）
- `data/heroes.db` — SQLite 数据库文件（生成产物）
- `data/fetched_heroes.json` — 抓取结果 JSON（生成产物）
- `.env` — 本地环境变量（包含真实 dashscope API key，请勿提交）
- `tests/` — 单元测试
