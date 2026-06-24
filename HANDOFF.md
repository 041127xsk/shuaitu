# HANDOFF.md — 项目交接文档

## 一句话概述

这个仓库是一个面向率土之滨的"配将助手"系统：从官网抓取武将志和武将目录数据，提取主战法与武将信息，存入 SQLite；同时通过 ADB + Npcap 抓包采集战报，提供队伍查询、胜率统计和阵容评分。

---

## 仓库总览

```
openclaw-main/
├── src/                          # Python 数据抓取管线
│   ├── ai_extract.py             # AI 结构化抽取（通义千问 dashscope）
│   ├── article_extractor.py      # 文章解析核心
│   ├── database.py               # SQLite 持久化（heroes / primary_skills / crawl_state）
│   ├── hero_catalog.py           # 武将目录抓取
│   └── data_fetcher.py           # hero article bundle 封装
│
├── scripts/
│   ├── fetch_targets.py          # 批量抓取主入口
│   ├── load_to_sqlite.py         # JSON → SQLite 导入
│   ├── export_heroes.py          # 统一导出（JSON / CSV）
│   └── preview_extract.py        # 单条文章预览
│
├── data/
│   ├── heroes.db                 # 武将数据库（生成产物）
│   └── fetched_heroes.json       # 抓取结果 JSON
│
├── stzb-helper-v2/               # Wails v2 桌面应用（Go + Vue 3）
│   ├── app.go                    # Wails 主入口，所有 Go→JS 桥接函数
│   ├── model/                    # GORM 数据模型（7 个文件）
│   ├── write_queue.go            # 写入队列（channel + 单 worker）
│   ├── query_cache.go            # LRU 查询缓存（32 条，TTL 20s）
│   ├── player_team_query.go      # 队伍查询核心逻辑
│   ├── materialized_stats.go     # 物化统计重建
│   ├── name_mapping.go           # 名称映射 CRUD API
│   ├── parse.go                  # 战报解析（ADB + Npcap）
│   ├── npacp.go                  # Npcap 抓包
│   ├── frontend/src/
│   │   ├── pages/                # Vue 页面（12 个）
│   │   └── utils/nameMappings.js # 名称映射前端工具
│   └── build/bin/
│       ├── stzbHelper-wails.exe  # 编译产物
│       └── config.json           # 运行时配置
│
├── intel-helper/                 # 情报助手（独立项目，.gitignore 排除）
├── pcb_analyzer/                 # PCB 分析（独立项目，.gitignore 排除）
└── mimo2codex/                   # 转换工具（独立项目，.gitignore 排除）
```

---

## 环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Go | 1.23+ | Wails 后端编译 |
| Node.js | 18+ | 前端构建 |
| Python | 3.10+ | 数据抓取管线 |
| Wails CLI | v2.12.0 | 桌面应用构建 |
| ADB | 最新 | 手机自动化翻页 |
| Npcap | 1.80+ | 战报抓包 |
| SQLite | 3.35+ | 数据库 |

---

## 构建与运行

### Wails 桌面应用

```powershell
# 安装依赖
cd stzb-helper-v2/frontend && npm install

# 开发模式
cd stzb-helper-v2 && wails dev

# 生产构建
$env:Path = "C:\go\bin;C:\Users\27557\go\bin;$env:Path"
cd stzb-helper-v2
wails build
# 输出: stzb-helper-v2/build/bin/stzbHelper-wails.exe
```

### Python 数据管线

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 批量抓取
python scripts/fetch_targets.py

# 导入 SQLite
python -X utf8 scripts/load_to_sqlite.py

# 导出
python -X utf8 scripts/export_heroes.py --pretty
```

### 运行时配置

`stzb-helper-v2/build/bin/config.json`:
```json
{
  "adb_path": "C:\\Users\\27557\\.local\\bin\\platform-tools\\adb.exe",
  "adb_serial": "127.0.0.1:16384",
  "scroll_count": 8000,
  "scroll_delay": 300,
  "scroll_duration": 500,
  "database_path": "E:\\openclaw\\openclaw-main\\战报助手\\数据库\\歌丨小池.db"
}
```

---

## 数据库架构

### 战报数据库（Wails 应用，GORM AutoMigrate）

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `battle_report` | 原始战报（唯一权威数据源） | battle_id, attack_idu, defend_idu, result, time |
| `player_team_snapshot` | 队伍查询派生快照 | player_name, idu, lineup_key, hero1/2/3_id |
| `team_winrate_stats` | 胜率预聚合统计 | mode, lineup_key, total_battles, win_rate |
| `materialized_state` | 派生表状态追踪 | status, battle_report_count, processed_report_count |
| `materialized_team_exclusion` | 隐藏队伍排除标记 | player_name, role, idu, lineup_key |
| `name_mapping` | 名称映射（hero/skill/gear） | kind, ref_id, name |
| `team_user` | 同盟成员 | — |
| `task` | 攻城任务 | — |
| `report` | 攻城统计 | — |

### 武将数据库（Python 管线，手动建表）

| 表名 | 用途 |
|------|------|
| `heroes` | 武将元信息（feed_id 唯一键） |
| `primary_skills` | 主战法详情 + AI 抽取字段 |
| `crawl_state` | 抓取状态追踪（断点续跑） |

---

## 核心功能

### 1. 自动翻页抓包（ADB + Npcap）
- ADB 连接手机模拟器，自动翻页战斗详情
- Npcap 抓取网络包，解析战报数据
- 写入队列（`write_queue.go`）串行化所有 DB 写入，消除 SQLite locked

### 2. 队伍查询（TeamQuery.vue → player_team_query.go）
- 攻守方独立筛选、战法搜索、星级/兵力阈值过滤
- LRU 缓存（32 条，TTL 20s），切换数据库/新增战报时自动失效
- 宝物（gear）显示：4 位 gear_id × gear_level;gear_refine × 4 槽位
- 名称映射：支持 hero/skill/gear 自定义名称替换
- 隐藏队伍管理：写排除标记，不删除原始战报

### 3. 胜率统计（TeamWinRate.vue → materialized_stats.go）
- 按队伍/按玩家两种视图
- 物化统计层：后台重建，页面显示进度（已处理/总数）
- 默认阈值（30 级、20000 兵力）读派生表，非默认回退原始查询

### 4. 攻城任务（Task.vue）
- 自动统计攻城参与名单和出勤率
- 单任务导出 Excel、大数据库导出（汇总 + 明细）

### 5. 名称映射（name_mapping.go + nameMappings.js）
- 自动检测当前查询结果中不在 cfg 和映射表里的未知 ID
- 点击未知 ID 一键填充表单，输入名称保存
- 支持编辑和删除已有映射

---

## Go→JS 桥接约定

所有暴露给前端的 Go 函数都接受**一个 `jsonStr string` 参数**，Go 内部解析 JSON。这样避免 Wails v2 的位置类型序列化 bug。

```go
// Go 侧
func (a *App) GetTeamWinRate(jsonStr string) string {
    var args struct { Mode string `json:"mode"` ... }
    json.Unmarshal([]byte(jsonStr), &args)
    // ...
    return global.Response{Data: result}.Success()
}
```

```js
// JS 侧
const resp = await GetTeamWinRate(JSON.stringify({ mode, min_level, ... }))
```

---

## 性能优化措施

| 层级 | 措施 | 文件 |
|------|------|------|
| 写入 | channel 写入队列，单 worker 串行化 | `write_queue.go` |
| 查询 | LRU 缓存（32 条，TTL 20s） | `query_cache.go` |
| 数据库 | `SetMaxOpenConns(1)` + WAL + busy_timeout | `model/database.go` |
| 索引 | 15 个复合索引覆盖常用查询 | `model/database.go` |
| 物化 | 队伍快照 + 胜率预聚合，后台重建 | `materialized_stats.go` |
| SQL | GetTeamWinRate CTE 合并单查询 | `app.go` |
| 前端 | 路由懒加载，xlsx 按需加载 | `routes.ts` |

---

## 已知问题

1. **Wails CLI v2.12.0 vs go.mod v2.11.0 警告** — 网络无法下载 v2.12.0 依赖，不影响编译
2. **go.mod 模块名 `stzbHelper`** — 不是目录名 `stzb-helper-v2`，新建 Go 文件时注意 import 路径
3. **`skill_type` 为空是正常行为** — 战法描述未明确说明类型时 LLM 正确留空，不是 bug
4. **`apikey.txt`** — 疑似真实 API key，不要提交到 git
5. **物化统计默认阈值** — 只覆盖 30 级 / 20000 兵力；其他阈值回退原始查询

---

## 当前优先级

### P0（必须做）
- 阵容评分函数 `simulate_battle(teamA, teamB)` — 还没有评分代码

### P1（重要）
- 限速、重试和失败退避
- 增量抓取断点续跑
- 解析脚本 UTF-8 整理

### P2（可选）
- 百万级赛季库性能实测
- GitHub Releases 发布
- README 完善

---

## 提交历史

```
a771e960 feat: name mapping auto-detect unknown IDs, full CRUD UI
acc09963 feat: restore name mapping system (hero/skill/gear custom names)
31fa964e feat: re-add gear display to team query (compact/card/export)
0b41ea46 perf: LRU cache (32 entries), index pruning (17→15)
d2d19cba perf: write queue, CTE merge, query limits, connection pool, mutex
7ca6cc66 feat: add gear display, export attendance, fix TS errors
e75a04d0 docs: design materialized performance stats
27a4fe70 perf: add query metrics and cache win rate results
6f450a58 perf: speed up team query and split frontend chunks
4169c99d feat: add duplicate battle stop toggle and fix light log contrast
b4cc4ed9 Initial commit
```

---

## 安全注意事项

- `.env` 和 `apikey.txt` 包含真实 API key，**绝对不要提交**
- `pcb_analyzer/`、`mimo2codex/`、`intel-helper/` 包含个人信息，已加入 `.gitignore`
- `battle_report` 是唯一权威数据源，隐藏/恢复只是展示层排除
- 物化统计表可随时从原始战报全量重建
