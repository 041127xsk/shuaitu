# PROJECT_MEMORY.md

## 项目背景
这个仓库在做一个"配将助手"最小可运行系统。目标是先把官网武将志数据抓下来，提取主战法和武将基础属性，整理成结构化数据，后续再扩展为：

- SQLite 持久化 ✅ 已完成
- 阵容构建（待开发）
- 阵容评分（P0 任务）
- 模拟对战（待开发）
- 批量评估新阵容对基准阵容的胜率（待开发）

当前面向的使用场景不是 Web 产品，而是一个供后续规则引擎和 AI 推荐继续开发的数据底座。

## 技术栈
- 语言：Python
- HTTP：`requests`
- HTML 解析：`beautifulsoup4`
- AI 客户端：`openai`（调用通义千问 dashscope OpenAI 兼容接口）
- 测试：`pytest`
- 数据库：SQLite（`data/heroes.db`）
- 环境变量加载：`python-dotenv`
- 调度：当前没有 cron、队列或任务调度框架
- 浏览器自动化：当前没有使用 `playwright`、`selenium` 或 `puppeteer`

## 仓库结构
```
.
├── .env                          # 本地环境变量（含真实 API key，请勿提交）
├── .env.example                   # 环境变量示例（假值）
├── apikey.txt                    # ⚠️ 疑似真实 API key，不要提交到 git
├── requirements.txt               # Python 依赖
│
├── src/
│   ├── __init__.py
│   ├── ai_extract.py             # AI 结构化抽取（通义千问 dashscope）
│   ├── article_extractor.py      # feed 抽取、分段、主战法解析
│   ├── data_fetcher.py           # hero article bundle 封装
│   ├── database.py               # SQLite 持久化层（三表：heroes/primary_skills/crawl_state）
│   └── hero_catalog.py           # 武将目录抓取和链接解析
│
├── scripts/
│   ├── fetch_targets.py          # 批量抓取主入口，已接入 AI 抽取
│   ├── preview_extract.py         # 单条文章预览 / smoke test
│   ├── resolve_targets.py         # 目录页目标解析辅助脚本（UTF-8 清洁版待整理）
│   ├── load_to_sqlite.py         # JSON → SQLite 幂等导入脚本
│   ├── export_heroes.py          # 统一导出（JSON / CSV，含阵营/星级过滤）
│   └── _*.py                     # 调试/临时脚本（不要混入主流程）
│
├── data/
│   ├── heroes.db                 # SQLite 数据库（生成产物）
│   ├── fetched_heroes.json       # 抓取结果 JSON（生成产物）
│   ├── fetched_heroes_all.json   # 全量抓取备份
│   ├── export_all.json           # 统一导出 JSON
│   ├── export_魏国.csv           # 魏国 CSV 导出示例
│   └── directory_anchors.json   # 目录锚点数据
│
└── tests/
    ├── test_ai_extract.py        # AI 抽取单测（mock 验证）
    ├── test_article_extractor.py  # 文章解析单测
    ├── test_data_fetcher.py       # data_fetcher 单测
    └── test_hero_catalog.py       # 目录解析单测
```

## 核心模块说明

### 抓取入口
- `scripts/fetch_targets.py`
  - 当前批量抓取的主入口。
  - 会先抓目录文章 `636268ee74424700010125d5`，再抓 `wujiangInfo.json`，最后对目标武将逐个请求文章 feed。
  - **已接入 AI 抽取**：在抓取主循环里调用 `ai_extract.enrich_skill()`，结果写入 `primary_skills` 表 AI 字段。
  - 输出到 `data/fetched_heroes.json`。
  - 支持 `--limit N` 限制抓取数量。
- `scripts/preview_extract.py`
  - 单条 feed 的预览调试入口。
  - 适合检查 `primary_skill` 是否抓对。
- `scripts/resolve_targets.py`
  - 目录页目标解析辅助脚本。
  - 当前在仓库里是辅助性质，不是主流水线。
  - ⚠️ 有 UTF-8 编码污染迹象（P1 待整理）。

### 数据源配置
- `src/hero_catalog.py`
  - 固定使用 `https://s.166.net/config/sh_stzb/wujiangInfo.json?_t=1648539610183`
  - 用于拿武将基础目录、星级、阵营、兵种和头像信息。
- `src/article_extractor.py`
  - 固定使用 `https://inf.ds.163.com/v1/web/feed/basic/facade`
  - 用于从文章 feed 中解析正文和图片，并抽取主战法。

### 请求 / 解析层
- `src/article_extractor.py`
  - `fetch_feed()`：请求 feed API。
  - `parse_feed_content()`：解析 feed JSON 里的 `content.body`。
  - `iter_blocks()`：把 `longText` 拆成文本块和图片块。
  - `split_sections()`：按标题把文章拆成段落。
  - `extract_primary_skill_info()`：只保留主战法，不抓拆解战法。
  - `find_skill_text()`：只挑主战法相关的段落。
  - `_extract_four_dimensions_image()`：从 blocks 中提取四维属性图 URL。
  - `_trim_skill_paragraphs()`：清洗主战法段落，去除广告和水印。
- `src/hero_catalog.py`
  - `fetch_hero_catalog()`：抓武将基础目录。
  - `to_hero_records()`：把原始 JSON 转成 `HeroRecord` dataclass。
  - `filter_high_star_heroes()`：只保留 `star >= 4` 或 `quality` 以 `SR` 结尾的武将。
  - `resolve_hero_links_from_directory()`：从目录文章里按文本精确匹配链接。

### AI 抽取层
- `src/ai_extract.py`（已建立，2026-04-26）
  - **使用通义千问 dashscope**（OpenAI 兼容接口），默认模型 `qwen/qwen3.5-flash`。
  - `SkillExtraction` dataclass：战法结构化 schema（skill_type / trigger_rate / targets / effects 等）。
  - `extract_skill_details(paragraphs, skill_name_hint)`：主函数，返回 `SkillExtraction`。
  - `enrich_skill(paragraphs, skill_name_hint)`：返回适合塞 SQLite 的扁平 dict。
  - 指数退避重试（默认3次），无 API_KEY 时降级返回空结构不抛异常。
  - 专注战斗类战法（主动/被动/指挥/典藏/兵种/阵法/追击），忽略内政。
  - **自动从项目根目录加载 `.env`**（`load_dotenv(override=True)` 强制覆盖系统环境变量）。
  - **已验证可用**：群吕布（4 effects，skill_type 为空）、张机（2 effects，完整数据）、赵云（3 effects，skill_type 为空）。
  - ⚠️ `skill_type` 为空字符串是正常行为——当战法描述未明确说明"主动"或"被动"时，LLM 正确留空，不是 bug。

### 数据存储层
- `src/database.py`（已建立）
  - 三张表：`heroes`（武将元信息）、`primary_skills`（主战法详情 + AI 抽取字段）、`crawl_state`（抓取状态追踪）。
  - `init_db()`：建库建表，幂等可重复执行。
  - `upsert_hero()`：以 `feed_id` 唯一约束插入或更新武将元信息。
  - `upsert_primary_skill()`：替换主战法（每英雄一条）。
  - `upsert_skill_extraction()`：更新 AI 抽取字段（skill_type / trigger_rate / targets / effects_json 等），不删原记录。
  - `upsert_crawl_state()`：记录抓取状态（pending/done/error），支持断点续跑。
  - `migrate_ai_fields()`：幂等字段迁移，向已有 DB 补充新列。
  - `query_heroes()`：按 `name/faction/star` 组合查询。
  - `get_pending_crawl_targets()`：获取待抓/失败条目，用于增量重跑。
  - `export_heroes()`：从 SQLite 导出武将列表，支持阵营/星级过滤。
  - `export_summary()`：返回导出的统计摘要。
- `scripts/load_to_sqlite.py`（已建立）
  - 从 `data/fetched_heroes.json` 导入全部武将到 SQLite。
  - 支持 `--report` 模式只查看统计，不导入。
  - 幂等，失败条目会写入 `crawl_state` 不中断整批。
- 数据库文件：`data/heroes.db`（生成产物，不提交到仓库）
- 当前已导入：16 条武将记录，16 条主战法，16 条 crawl_state（均 done）。

### 统一导出层
- `scripts/export_heroes.py`（已建立，2026-04-26）
  - 支持 JSON / CSV 两种格式，可按阵营/星级过滤。
  - `--faction 魏 --star 5` 按阵营和星级过滤。
  - `--with-paragraphs` 含主战法段落全文。
  - `--pretty` JSON 美化输出。
  - `--output -o` 指定输出文件。
- 已有导出产物：`data/export_all.json`、`data/export_魏国.csv`。

### 调度 / 任务队列
- 当前没有调度系统、队列、定时任务或后台 worker。
- 所有任务都要手动运行脚本。

### 日志系统
- 当前没有统一日志框架。
- `src/ai_extract.py` 使用标准 `logging` 模块。
- 主要脚本直接把 JSON 或错误信息打印到标准输出。

### 测试
- `tests/test_article_extractor.py`
  - 覆盖文章分段、标题识别、主战法提取、旧格式 fallback、链接提取。
- `tests/test_hero_catalog.py`
  - 覆盖目录过滤、字段映射、目录页链接解析。
- `tests/test_data_fetcher.py`
  - 覆盖 feed id 去重和 bundle 导出。
- `tests/test_ai_extract.py`
  - 覆盖抽取逻辑、mock 验证、无 API_KEY 降级。

### 前端或后台管理界面
- 当前没有前端，也没有后台管理界面。

## 当前实现状态

### ✅ 已完成
- 能从武将目录接口抓到基础武将数据。
- 能从目录文章里解析目标武将文章链接。
- 能从文章 feed 里提取正文、图片、主战法信息。
- 已经能批量抓到一批高星武将，并生成 `data/fetched_heroes.json`（16 个武将）。
- 已明确当前规则：只抓 5 星 / 高星武将，忽略拆解战法。
- **SQLite 持久化层已建立**（`src/database.py` + `scripts/load_to_sqlite.py`），16 条武将全部入库。
- **AI 结构化抽取已建立**（`src/ai_extract.py`），已接入抓取流水线并验证可用。
- **统一导出脚本已建立**（`scripts/export_heroes.py`），支持 JSON / CSV，含阵营/星级过滤。

### 🔄 部分完成
- 文章抽取层已经能处理多种历史文章格式，但仍依赖启发式标题识别。
- `scripts/resolve_targets.py` 有编码问题，P1 待整理。
- 重试、限速、退避策略已写入 TODO，但尚未实现。

### ❌ 还没开始
- 阵容评分函数 `simulate_battle(teamA, teamB)`。
- 批量评估新阵容对基准阵容的胜率。
- 完整的重试、退避、限速、代理与登录态管理。
- 定时任务和增量抓取。

### 只是 demo / mock / 临时代码
- `data/fetched_heroes.json` 是生成样本，不是长期维护的主数据。
- `scripts/preview_extract.py` 主要是 smoke test。
- `scripts/resolve_targets.py` 是辅助脚本，适合排查目录页链接，不应作为唯一数据入口。
- `scripts/_*.py` 调试脚本不要混入主流程。

## 最近一次会话进展（2026-05-03）
- 项目已成功上传至 GitHub：https://github.com/041127xsk/shuaitu
- 提交记录：`f1ca0ef`（率土之滨配将助手数据底座）、`a065183`（合并远程仓库并解决.gitignore冲突）
- `.gitignore` 已合并本地规则与远程 AL 项目规则
- Git 身份已配置：`xieshikun <041127xsk@example.com>`

## 最近一次会话进展（2026-04-26）
- 确认了 AI 抽取使用通义千问 dashscope API（`qwen/qwen3.5-flash`）。
- AI 抽取验证结果：群吕布（4 effects，skill_type 为空）、张机（2 effects，完整数据）、赵云（3 effects，skill_type 为空）。
- 确认 `skill_type` 为空是正常行为——战法描述未明确说明类型时正确留空。
- `check_results.py` 之前有逻辑 bug（把空字符串误判为"无数据"），已修复理解。
- 统一导出脚本 `export_heroes.py` 已完成，支持 JSON / CSV，含阵营/星级过滤。
- **intel-helper 武将库增强**（2026-04-26）：给 intel-helper 的武将表添加了战法字段（skill_name, skill_images_json, skill_desc, skill_type, skill_trigger_rate），前端武将库支持点击查看武将详情和战法截图，添加了 `backend/import_skills.py` 用于从配将助手导入战法数据。
- **武将库完善**（2026-04-26）：从配将助手导入 111 个武将战法数据到 intel-helper，武将库页面默认展示所有武将，支持按阵营、战法筛选，添加武将统计信息（总数、有战法数、有截图数、各阵营数量）。

## 已知问题
- ⚠️ `apikey.txt` 文件中疑似包含真实 API key，不要提交到 git。
- ⚠️ `.env` 文件包含真实 dashscope API key，不应提交。
- `scripts/resolve_targets.py` 在终端显示里有编码污染迹象，建议后续整理成 UTF-8 清洁版。
- `src/article_extractor.py` 依赖标题识别和启发式规则，遇到页面结构变化时容易失配。
- 当前抓取没有断点续跑状态表（`crawl_state` 表已建，但批量抓取脚本还未全面接入）。
- AI 抽取的 `skill_type` 字段为空时，不代表没有数据，是 LLM 按提示词正确留空。

## 高风险区域
- `src/article_extractor.py`
  - 这里是文章解析核心，标题识别和主战法判定都在这里，改动容易影响全部抽取结果。
- `src/ai_extract.py`
  - AI 抽取核心，涉及 API 调用和 prompt 设计，改动可能影响所有战法结构化结果。
- `scripts/fetch_targets.py`
  - 这里决定批量抓取范围、输出结构和生成文件，改错会直接影响产物。
- `src/hero_catalog.py`
  - 这里负责目录链接解析和高星过滤，字段含义不能随便改。
- `src/database.py`
  - SQLite schema 和 upsert 逻辑，一旦改动需要考虑迁移方案。
- `data/fetched_heroes.json` / `data/heroes.db`
  - 这是生成结果，不能当成源码逻辑去手工改字段语义。
