# TODO.md

## P0 必做

## ~~P0-1 建立 SQLite 持久化层~~ ✅ 已完成 (2026-04-25)
- `src/database.py`：三张表（heroes / primary_skills / crawl_state）、upsert、查询函数。
- `scripts/load_to_sqlite.py`：幂等导入脚本，支持 `--report` 统计模式。
- 当前已导入 16 条武将，成功率 100%，数据库文件 `data/heroes.db`。

## ~~P0-2 接入 AI 抽取封装~~ ✅ 已完成 (2026-04-26)
- `src/ai_extract.py`：定义 SkillExtraction schema（skill_type/trigger_rate/targets/effects等），
  使用通义千问 dashscope OpenAI 兼容接口，含指数退避重试（最多3次）和无 API_KEY 降级。
- `tests/test_ai_extract.py`：mock 单测，验证抽取逻辑、fallback、降级路径。
- `src/database.py`：`primary_skills` 表新增9个 AI 字段（skill_type/trigger_rate/targets/effects_json 等），
  新增 `upsert_skill_extraction()` 和 `migrate_ai_fields()`，幂等迁移老 DB。
- `scripts/fetch_targets.py`：在抓取主循环里调用 `enrich_skill()`，结果写入 `ai_extraction` 字段。
- `scripts/load_to_sqlite.py`：入库时同步写入 AI 抽取字段。
- 专注战斗类战法（主动/被动/指挥/典藏/兵种/阵法/追击），忽略内政。
- ⚠️ 注意：`skill_type` 为空字符串是正常行为（战法描述未明确说明类型时正确留空），不是 bug。

## ~~工程能力增强~~ ✅ 已完成 (2026-04-27)
- `intel-helper/backend/logger_config.py`：统一日志配置，支持日志轮转
- `intel-helper/backend/main.py`：集成日志系统，关键 API 增加 try/except 日志记录
- `intel-helper/scripts/start_dev.py`：一键启动脚本，自动检查环境和依赖
- `intel-helper/scripts/backup_data.py`：一键备份脚本，支持数据库和日志备份
- `intel-helper/scripts/export_all.py`：一键导出脚本，导出所有表为 JSON/CSV
- `intel-helper/start.bat`：双击启动批处理
- `intel-helper/backup.bat`：双击备份批处理
- `intel-helper/export.bat`：双击导出批处理

## ~~P0-3 补上评分与模拟对战~~ 🔄 进行中
背景：
项目目标里最核心的业务能力之一是阵容评分和对战评估，但当前仓库还没有任何评分代码。

涉及文件：
- `src/scoring.py`（新建）
- `scripts/evaluate_team.py`（新建）
- `src/database.py`

推荐实现：
- 先实现最小版评分：`attack * 0.5 + defense * 0.3 + speed * 0.2`（当前四维属性只有图，需要从图片 OCR 或手动补数据）。
- 给控制、同阵营等加成做一个规则层，不要把规则塞进 SQL 里。
- 提供 `simulate_battle(teamA, teamB)` 和 `evaluate_team(team, baseline_teams)` 两个纯函数。

验收标准：
- 输入一组英雄能得到稳定分数。
- 两支阵容能输出胜负结果。
- 新阵容能对多个基准阵容算出胜率和综合评分。

风险：
- 评分规则一旦写进数据库或抽取层，后续改动会很痛，建议保持纯规则模块化。
- 当前缺少四维属性的结构化数据（只有图片 URL），需要先解决数据来源。

## P1 重要

## P1-1 修复并规范目标解析辅助脚本
背景：
`scripts/resolve_targets.py` 当前在终端里显示出编码污染迹象，虽然不一定完全不可用，但不适合长期维护。

涉及文件：
- `scripts/resolve_targets.py`
- `tests/test_hero_catalog.py`

推荐实现：
- 用 UTF-8 重新整理脚本。
- 把 target 映射改成可读的中文字符串。
- 给解析逻辑补一个最小 smoke test。

验收标准：
- 脚本内容可直接读懂，不再依赖终端乱码猜测。
- 运行输出和 `scripts/fetch_targets.py` 的解析结果一致。

风险：
- 这个脚本本质上依赖目录页文本匹配，改错字符串就会导致链接解析失败。

## P1-2 加上限速、重试和失败退避
背景：
当前抓取流程没有显式限速和退避，适合手工小规模跑，不适合高频批量跑。

涉及文件：
- `src/article_extractor.py`
- `src/hero_catalog.py`
- `scripts/fetch_targets.py`
- `src/ai_extract.py`（已有部分重试逻辑，可复用扩展）

推荐实现：
- 增加统一请求封装，加入超时、重试、指数退避和可配置 sleep。
- 把 User-Agent、超时、最大重试次数放到环境变量里。
- 429 / 403 / 网络超时要有清晰的失败分支。

验收标准：
- 遇到临时网络失败不会整批崩掉。
- 连续失败时能留下明确错误信息。

风险：
- 重试过猛会放大目标站压力，也会提高被限流的概率。

## P1-3 建立增量与断点续跑状态
背景：
当前批量抓取只写一次 JSON，crawl_state 表已建但 fetch_targets.py 还未全面接入，中断后需要人工判断从哪继续。

涉及文件：
- `src/database.py`
- `scripts/fetch_targets.py`
- `scripts/load_to_sqlite.py`

推荐实现：
- `crawl_state` 表已建，重新执行时跳过已完成条目。
- 失败条目可单独重跑。
- 把 fetch_targets.py 的错误处理改为写入 crawl_state 而非直接退出。

验收标准：
- 中断后能从未完成项继续跑。
- 同一 feed 不会被重复处理多次。

风险：
- 状态表设计如果太早定死，后续字段变化会带来迁移成本。

## ~~P1-4 统一结构化导出格式~~ ✅ 已完成 (2026-04-26)
- `src/database.py` 新增 `export_heroes()` / `export_summary()` 函数
- `scripts/export_heroes.py`：统一导出 CLI，支持 JSON / CSV，含阵营过滤、星级过滤、`--with-paragraphs` 等选项
- `data/export_all.json`：全量 JSON 导出（含 summary）
- `data/export_魏国.csv`：魏国 CSV 导出示例

## ~~P1-6 intel-helper 武将库战法展示~~ ✅ 已完成 (2026-04-26)
- `intel-helper/backend/database.py`：Hero 表新增战法字段（skill_name, skill_images_json, skill_desc, skill_type, skill_trigger_rate）
- `intel-helper/frontend/app.js`：武将库支持点击查看武将详情和战法截图
- `intel-helper/frontend/style.css`：添加武将详情弹窗和战法截图样式
- `intel-helper/backend/import_skills.py`：新建导入脚本，支持从配将助手 heroes.db 导入战法数据
- `intel-helper/README.md`：添加武将库和战法导入说明

## ~~P1-5 整理调试脚本目录~~ ✅ 已完成 (2026-05-07)
- 根目录 21 个 Frida 调试脚本（`_capture_*.py`、`_deep_*.py`、`_test_*.py`、`_start_*.sh` 等）已移入 `scripts/archive/`。
- `scripts/` 下 15 个调试/临时脚本（`_battle_proxy.py`、`_debug_*.py`、`_migrate_*.py`、`_ssl_unpin.py`、capture_battle_*.py 等）已移入 `scripts/archive/`。
- 归档脚本共 47 个，不再混入主流程。
- `scripts/` 目录现保留主入口和检查脚本：fetch_targets.py、export_heroes.py、load_to_sqlite.py、preview_extract.py、resolve_targets.py、download_hero_images.py、fetch_all_sr.py、import_intel_helper.py、check_*.py、test_*.py。

## P2 可选优化

## P2-1 增加 README 和示例命令
背景：
当前仓库没有项目总说明，新人上手时只能依赖交接文档。

涉及文件：
- `README.md`（新建）
- `RUNBOOK.md`

推荐实现：
- 放最短的安装、抓取、测试命令。
- 只写真正能跑的命令，不写概念说明。

验收标准：
- 新人只看 README 就能启动最小流程。

风险：
- README 容易过时，建议只放主入口和最常用命令。

## P2-2 增加更细的测试覆盖
背景：
当前测试覆盖了核心解析逻辑，但还没有数据库和评分测试。

涉及文件：
- `tests/`
- `src/database.py`
- `src/scoring.py`（新建后）

推荐实现：
- 给 SQLite 去重、阵容评分、战斗模拟写单测。
- 给批处理函数写一个不访问真实站点的 mock 测试。

验收标准：
- 核心规则变动时，测试能及时报警。

风险：
- 抓取测试如果直接打真实站点，会很慢也不稳定，尽量避免。

## P2-3 改善日志和调试体验
背景：
当前主要靠 stdout 输出 JSON，排查问题时不够方便。

涉及文件：
- `src/article_extractor.py`
- `scripts/fetch_targets.py`
- `scripts/preview_extract.py`

推荐实现：
- 引入标准 `logging`。
- 区分 info / warning / error。
- 给每个 feed 和 hero 名字打上上下文。

验收标准：
- 出错时能快速定位是哪一个 feed 或哪个 hero。

风险：
- 日志太啰嗦会影响批量抓取阅读体验，最好只保留结构化关键信息。

## ~~P2-4 清理 apikey.txt 中的敏感信息~~ 🔄 部分完成 (2026-04-26)
- ✅ 已创建 `.gitignore`，排除 `.env`、`apikey.txt` 和所有生成产物。
- ✅ 已将 `python-dotenv>=1.0.0` 加入 `requirements.txt`。
- ⚠️ `apikey.txt` 文件仍存在于仓库中，如 git 历史已包含需要清理。
- ⚠️ 建议将 `apikey.txt` 内容移入 `.env` 后删除该文件。
- ⚠️ 如果 git 历史已提交过敏感信息，需运行 `git filter-branch` 或 `BFG Repo-Cleaner` 清理。
