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

## 最近一次会话进展（2026-06-01）
- **stzb-helper-v2 自动翻页重复战报开关与日志可读性修复**：
  - 真实项目目录 `E:\openclaw\openclaw-main\stzb-helper-v2` 已补上重复战报处理改动：默认只记录本次处理到的最后一个 `battle_id`，不再强制自动停止。
  - 新增 `stop_on_duplicate` 启动参数和配置字段；自动翻页页与首页自动翻页面板均提供“重复战报自动停”开关，打开后才在重复战报处自动停止。
  - `parse.go` 统一通过 `recordAutoScrollBattleID()` / `markAutoScrollDuplicate()` 记录最后战报 ID，重复战报也会写入最新 ID。
  - `app.go` 将后端标准日志优先写入 `global.LogW`，再写 stdout，避免桌面 exe 中 stdout 不可用导致前端日志空白。
  - 浅色/深色模式日志区新增 `--log-*` 主题变量；`Logs.vue` 和 `AutoScroll.vue` 日志文字使用独立日志文字色，修复浅色模式看不清。
  - 新增 `app_autoscroll_test.go` 覆盖重复战报开关和 stdout 失败时前端日志仍可写入。

## 最近一次会话进展（2026-06-02）
- **stzb-helper-v2 队伍查询性能与前端体积优化**：
  - `GetPlayerTeam` 改为一次查询候选队伍，在 Go 层完成完整三将阵容去重、同玩家共享 2 个武将的旧队伍替换和分页，避免原先总数查询与分页查询各跑一遍大窗口排序。
  - 新增 20 秒短时队伍查询缓存；同一筛选条件下翻页和导出会复用过滤后的有效队伍列表，切换/创建数据库或新增战报时自动失效。
  - `model.InitDB` 新增队伍查询相关索引，覆盖时间、攻守方等级/兵力、队伍 ID 等常用查询路径。
  - 前端路由改为懒加载；`xlsx` 从主包移出，队伍查询、同盟成员、攻城任务仅在点击导出时动态加载。
  - 移除不存在的 Geist 字体引用，改用系统字体栈，`npm run build` 不再出现字体路径警告。

## 最近一次会话进展（2026-06-02 深夜）
- **stzb-helper-v2 查询可观测性与胜率页缓存优化**：
  - 队伍查询新增 `GetPlayerTeamExport`，前端导出 Excel 不再循环分页拉取，直接复用后端一次性有效队伍结果。
  - 队伍查询和队伍胜率查询返回 `query_ms` / `cache_hit`，页面统计区显示本次耗时和是否命中缓存。
  - 队伍胜率页新增 20 秒短时结果缓存；同一筛选、分页和分组模式重复查询直接返回缓存。
  - `model.InitDB` 补充胜率查询相关复合索引，覆盖结果、攻守双方等级/兵力等过滤条件。
  - 新增 `query_cache.go` 作为轻量查询缓存工具，数据库切换/创建和新增战报时同步失效。

## 最近一次会话进展（2026-06-02 更晚）
- **stzb-helper-v2 百万级战报性能方案设计已确定**：
  - 用户确认一赛季数据可能达到几十万到一百多万条，选择物化统计/缓存表路线。
  - 设计新增 `player_team_snapshot`，队伍查询优先读快照，先快速展示队伍结果。
  - 设计新增 `team_winrate_stats`，胜率仍以原始 `battle_report` 为唯一权威来源，但采集时实时/增量维护预计算胜负平统计。
  - 设计新增 `materialized_state` 记录派生表状态、版本、最后处理的 `battle_id` 和重建状态。
  - 队伍查询将支持“先出结果，展开后按需加载相关原始战报”，避免主查询被原始大表拖慢。
  - 设计文档已写入 `stzb-helper-v2/docs/superpowers/specs/2026-06-02-performance-materialized-stats-design.md`。

## 最近一次会话进展（2026-06-02 最晚）
- **stzb-helper-v2 百万级战报物化统计已实现首版**：
  - 新增 `player_team_snapshot`、`team_winrate_stats`、`materialized_state` 三张派生表，随 `model.InitDB` 自动迁移。
  - 新增 `RebuildMaterializedStats()` 和 `GetMaterializedStatsStatus()` Wails API；队伍查询页和胜率页提供“重建索引”入口。
  - `GetPlayerTeam` / `GetPlayerTeamExport` 在 `player_team_snapshot` ready 时优先读取派生快照，否则回退原始查询。
  - `GetTeamWinRate` / `GetTeamWinRateByTeam` 在默认阈值（30 级、20000 兵力）且 `team_winrate_stats` ready 时优先读取派生统计；其他阈值暂时回退原始查询，避免统计口径错误。
  - 新增 `GetPlayerTeamRelatedBattles()`，队伍查询先展示结果，点击“战报”后再从原始 `battle_report` 按需加载该队伍相关战报。
  - 抓包新增战报入库后会调用 `applyBattleReportToMaterializedStats()` 增量刷新受影响玩家快照和胜率统计；失败时保留原始战报并标记/记录索引异常。
  - 新增 `materialized_stats_test.go` 覆盖队伍快照、胜率规则、全量重建和攻守胜负标签。

## 最近一次会话进展（2026-06-02 最最后）
- **stzb-helper-v2 统计索引后台重建与进度展示**：
  - `RebuildMaterializedStats()` 从同步阻塞改为启动后台重建任务，立即返回“已开始后台重建”。
  - `materialized_state` 新增 `processed_report_count`，配合 `battle_report_count` 展示重建进度。
  - `GetMaterializedStatsStatus()` 返回 `rebuilding` 状态；队伍查询页和胜率页每秒轮询状态，显示 `重建中 已处理/总数 (%)`。
  - 重建完成后页面自动刷新当前查询；重建期间查询仍可回退原始表或等待索引 ready。
  - 新增测试覆盖后台重建启动、进度写入和完成状态。

## 最近一次会话进展（2026-06-02 隐藏同步）
- **stzb-helper-v2 队伍隐藏同步到胜率查询**：
  - 新增 `materialized_team_exclusion` 表，保存用户在队伍查询中隐藏的队伍标记。
  - `player_team_snapshot` 查询和 `team_winrate_stats` 查询都会按同一隐藏标记过滤，避免队伍查询隐藏后胜率页仍显示。
  - 队伍查询页新增“隐藏”按钮，确认后写入排除标记并清空队伍/胜率短时缓存。
  - 隐藏不会删除原始 `battle_report`，不改变抓取频率、失败重试、断点续跑或战报去重规则；后续重建索引会继续保留隐藏标记。
  - 新增测试覆盖隐藏队伍后队伍查询、玩家胜率查询、按队伍胜率查询同步排除。

## 最近一次会话进展（2026-06-03 页面体验优化）
- **stzb-helper-v2 隐藏恢复与查询页渲染优化**：
  - 新增 `GetHiddenPlayerTeams(page, pageSize)` 和 `RestoreHiddenPlayerTeam(id)` Wails API，用于查看和恢复隐藏队伍。
  - 队伍查询页新增“隐藏管理”弹窗，可分页查看隐藏队伍并恢复；恢复只删除隐藏标记，不删除原始 `battle_report`。
  - 队伍查询页将玩家分组改为 `computed`，当前页战法解析缓存到结果对象，相关战报已加载后折叠/展开不再重复请求。
  - 队伍胜率页把英雄、战法、时间、负率和平局率预处理成展示模型，模板不再反复解析配置和战法字符串。
  - 队伍胜率页移除重复内联 base64 星星图片，改为 CSS 星点，页面 chunk 明显减小。
  - 新增测试覆盖隐藏列表、恢复隐藏后队伍/胜率重新显示，以及恢复不存在记录的错误路径。

## 最近一次会话进展（2026-06-03 大库稳定性）
- **stzb-helper-v2 统计索引重建内存与替换窗口优化**：
  - 全量重建不再把所有 `battle_report` 原始行累积成一个大数组，而是按批读取后直接送入汇总器，边读边累计队伍快照候选和胜率统计。
  - 重建结果先写入 `player_team_snapshot_rebuild` / `team_winrate_stats_rebuild` 临时表，写完后用短事务替换正式表，降低百万级重建期间正式统计表被长时间占用的风险。
  - `model.InitDB` 设置 `busy_timeout`、WAL、`synchronous=NORMAL` 和 `temp_store=MEMORY`，提升 SQLite 长读写共存稳定性。
  - 新增相关战报展开索引和队伍胜率派生查询索引：`idx_br_attack_related`、`idx_br_defend_related`、`idx_twrs_team_search`。
  - 新增测试覆盖分批汇总与旧规则一致、临时表替换后清理、以及大库查询索引自动创建。
  - 本轮不改变抓取频率、失败重试、断点续跑、战报去重规则；`battle_report` 仍是唯一权威数据源。

## 最近一次会话进展（2026-06-03 发布与实测基线）
- **stzb-helper-v2 最新桌面包与统计索引性能基线**：
  - 已执行 `wails build -clean`，新桌面包输出到 `stzb-helper-v2/build/bin/stzbHelper-wails.exe`。
  - `build/bin` 已清理为只保留最新 `stzbHelper-wails.exe`；历史本地 exe 不再留在该目录。
  - 新增默认跳过的 `TestMaterializedStatsPerformanceProbe`；设置 `STZB_PERF_DB` 后可在复制库上复测统计索引重建和查询耗时。
  - 使用 `E:\openclaw\openclaw-main\战报助手\数据库\歌丨池上#7191611_X5602.db` 的临时副本实测：`battle_report_count=74326`，重建 `3.732s`，队伍查询 `16ms`，默认阈值胜率查询 `35ms`，相关战报展开 `1ms`。
  - 该实测库不是百万级，仅作为当前优化后的本机基线；真实一赛季百万级库仍需单独复测。

## 最近一次会话进展（2026-06-02 侧边栏整理）
- **stzb-helper-v2 移除空白自动翻页入口**：
  - 左侧控制栏移除“自动翻页”菜单项，避免点击进入不存在路由后的空白页面。
  - `frontend/src/App.vue` 同步移除该菜单项独占使用的刷新图标导入。
  - 保留后台自动翻页能力和首页已有控制入口，不改变 ADB 配置、抓包逻辑、重复战报处理或数据结构。
  - 新增 `frontend_navigation_test.go`，防止侧边栏再次暴露空白自动翻页入口。

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
