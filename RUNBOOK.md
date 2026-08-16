# RUNBOOK.md

## 本地启动

### 安装依赖
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 初始化环境
```powershell
# 复制环境变量模板
copy .env.example .env

# 编辑 .env，填入真实 API key（不要提交到 git）
# DASHSCOPE_API_KEY=sk-your-real-key-here
```

⚠️ **注意**：
- `src/ai_extract.py` 会自动从项目根目录加载 `.env`（`load_dotenv(override=True)`）。
- `override=True` 会强制覆盖系统环境变量，确保 Windows 本地其他 KEY 不会干扰。
- `.env` 包含真实 API key，**请勿提交到 git**。
- 如果 git 中已存在敏感信息，需要用 `git filter-branch` 或 `BFG Repo-Cleaner` 清理。

## 启动抓取

### 单条文章预览
用于检查某个 feed 的正文和主战法抽取结果。

```powershell
python scripts/preview_extract.py <feed_id>
```

示例：
```powershell
python scripts/preview_extract.py 6358dcb9744247000199baa9
```

### 批量抓取目标武将
当前主入口会抓目录页、武将目录 JSON，并生成 `data/fetched_heroes.json`。

```powershell
python scripts/fetch_targets.py
```

限制抓取数量（用于测试）：
```powershell
python scripts/fetch_targets.py --limit 3
```

### 目标解析辅助
用于排查目录页里某个名字能解析到哪些链接。

```powershell
python scripts/resolve_targets.py
```

⚠️ 注意：
- 这个脚本是辅助工具，不要把它当成唯一的主数据入口。
- 如果终端显示乱码，优先确认 PowerShell 编码和文件本身的 UTF-8 状态。

## AI 抽取

AI 抽取已集成到 `scripts/fetch_targets.py` 主流程中，无需单独运行。

- 无 `DASHSCOPE_API_KEY` 时自动跳过 AI 抽取，不影响主流程。
- 有 API_KEY 时，每个武将抓取后自动调用 `enrich_skill()` 并写入 SQLite AI 字段。

## SQLite 数据库

### 初始化并导入数据
```powershell
# 从 JSON 导入到 SQLite
python -X utf8 scripts/load_to_sqlite.py

# 指定路径
python -X utf8 scripts/load_to_sqlite.py --db data/heroes.db --json data/fetched_heroes.json
```

### 查看统计（不导入）
```powershell
python -X utf8 scripts/load_to_sqlite.py --report
```

### 统一导出
```powershell
# 默认 JSON，含 summary + heroes 列表
python -X utf8 scripts/export_heroes.py

# JSON 美化输出
python -X utf8 scripts/export_heroes.py --pretty -o data/export.json

# CSV 导出（所有字段，无 paragraphs）
python -X utf8 scripts/export_heroes.py --format csv -o data/export.csv

# 按阵营过滤
python -X utf8 scripts/export_heroes.py --faction 魏 --format csv -o data/魏国.csv

# 按星级过滤
python -X utf8 scripts/export_heroes.py --star 5 --format json -o data/5星.json

# 含主战法段落全文（JSON 模式）
python -X utf8 scripts/export_heroes.py --with-paragraphs -o data/export_full.json

# 组合过滤
python -X utf8 scripts/export_heroes.py --faction 晋 --star 5 --pretty -o data/晋国5星.json
```

### 注意
- 运行 SQLite 相关脚本时加 `-X utf8`，避免 Windows GBK 终端编码问题。
- `data/heroes.db` 是生成产物，不应提交到仓库。

## 测试方式

### 单元测试
```powershell
pytest
```

如果本地没有 `pytest` 命令，也可以：
```powershell
python -m pytest
```

运行特定测试文件：
```powershell
pytest tests/test_ai_extract.py -v
```

### 抓取脚本 smoke test
```powershell
# 单条预览
python scripts/preview_extract.py 6358dcb9744247000199baa9

# 批量抓取（限制3个）
python scripts/fetch_targets.py --limit 3
```

### 不访问真实目标站的测试方式
- `tests/test_ai_extract.py` 使用 mock HTTP 响应，不打真实 API。
- `tests/test_article_extractor.py` 主要覆盖字符串处理，不需要浏览器。
- 如果后续加 SQLite 或评分层，优先给纯函数写测试，避免每次都打真实站点。

## 日志查看
- 当前脚本主要把结果直接打印到标准输出。
- `src/ai_extract.py` 使用标准 `logging` 模块，默认输出到 stderr。
- 如果需要留档，建议把 stdout 重定向到文件：

```powershell
python scripts/fetch_targets.py *> run.log
```

## 常用命令
```powershell
# 安装
python -m venv .venv; .\venv\Scripts\Activate; pip install -r requirements.txt

# 单条预览
python scripts/preview_extract.py <feed_id>

# 批量抓取
python scripts/preview_extract.py 6358dcb9744247000199baa9
python scripts/fetch_targets.py
python scripts/fetch_targets.py --limit 3

# SQLite
python -X utf8 scripts/load_to_sqlite.py --report
python -X utf8 scripts/load_to_sqlite.py

# 导出
python -X utf8 scripts/export_heroes.py --faction 魏 --format csv -o data/魏国.csv
python -X utf8 scripts/export_heroes.py --pretty --with-paragraphs -o data/export_full.json

# 测试
pytest

# 调试辅助
python scripts/resolve_targets.py
```

## 常见故障排查

### 401 / 403
- 先检查 `DASHSCOPE_API_KEY` 是否有效，是否已过期。
- 检查网络是否可达 dashscope API 域名。
- 当前仓库抓取的公开接口（feed API）暂时没有显式登录态。
- 如果突然出现 401 / 403，先检查目标站是否改了接口权限、请求头或防护策略。

### 429 限流
- AI 抽取已有指数退避重试（默认3次），遇到 429 会自动等待后重试。
- 抓取流程当前没有显式限速，一旦遇到目标站限流，先停止批量抓取，降低频率。
- 建议在 `.env` 中设置 `SCRAPER_SLEEP_SECONDS=1.5`。

### API Key 无效 / 过期
- 检查 `.env` 中 `DASHSCOPE_API_KEY` 是否正确。
- 无 KEY 时 `enrich_skill()` 返回空结构，不影响主流程。

### Cookie 过期
- 当前主抓取链路不依赖 Cookie。
- 如果后续接入需要登录的页面，Cookie 不要写进仓库，要放到本地环境变量或外部密钥管理里。

### 代理失败
- 当前没有内置代理层。
- 如果后续加入代理，先检查代理可达性、认证方式和时延，再决定是否在批处理里启用。
- 可在 `.env` 中设置 `HTTP_PROXY` / `HTTPS_PROXY`。

### MuMu 模拟器网络错误 / 游戏卡加载
**症状**：游戏卡在加载界面，提示"网络错误"，但 `ping` 和 `curl` 正常。

**根因**：之前设置过 mitmproxy 代理（`http_proxy`），清除后模拟器 DNS 配置丢失，导致游戏无法解析域名。

**修复步骤**：
```powershell
# 1. 重连 ADB
adb disconnect
adb connect 127.0.0.1:16384

# 2. 清除所有代理残留（必须全部删除！）
adb -s 127.0.0.1:16384 shell "settings delete global http_proxy"
adb -s 127.0.0.1:16384 shell "settings delete global global_http_proxy_host"
adb -s 127.0.0.1:16384 shell "settings delete global global_http_proxy_port"
adb -s 127.0.0.1:16384 shell "settings delete global global_http_proxy_exclusion_list"

# 3. 验证全部为 null
adb -s 127.0.0.1:16384 shell "settings get global http_proxy"
adb -s 127.0.0.1:16384 shell "settings get global global_http_proxy_host"
adb -s 127.0.0.1:16384 shell "settings get global global_http_proxy_port"

# 4. 强制停止游戏并重启
adb -s 127.0.0.1:16384 shell "am force-stop com.netease.stzb.uc"
# 等 5 秒
adb -s 127.0.0.1:16384 shell "monkey -p com.netease.stzb.uc -c android.intent.category.LAUNCHER 1"

# 5. 验证网络
adb -s 127.0.0.1:16384 shell "ping -c 1 -W 3 baidu.com"
adb -s 127.0.0.1:16384 shell "curl -s -o /dev/null -w '%{http_code}' http://baidu.com"
```

**注意事项**：
- 模拟器 ADB 端口默认 `16384`，如果连不上先确认 MuMu 是否在运行
- `setprop net.dns1` 等命令对游戏不生效，DNS 由模拟器自动管理
- **必须删除 `global_http_proxy_host` 和 `global_http_proxy_port`**，只删 `http_proxy` 不够！游戏会读取这两个字段
- 如果清除代理后仍报网络错误，`am force-stop` 后重启游戏即可
- logcat 中出现 `Failed to connect to /127.0.0.1:8090` 表示代理残留未清干净

### 页面结构变化
- `src/article_extractor.py` 依赖标题识别和 section 划分。
- 一旦页面正文结构变了，优先看 `split_sections()`、`_is_section_heading()` 和 `extract_primary_skill_info()`。
- 备选 fallback 逻辑在 `_extract_primary_skill_from_blocks()` 中。

### 字段解析失败
- 先确认 `feed_id` 是否正确。
- 再确认正文是否有 `longText`。
- 最后检查主战法标题是否被误识别成拆解战法或搭配参考。
- 运行 `scripts/preview_extract.py <feed_id>` 检查解析结果。

### 数据库连接失败
- 检查数据库文件路径是否正确（默认 `data/heroes.db`）。
- 检查数据库文件权限。
- 如果数据库 schema 需要迁移（新增列），运行 `scripts/load_to_sqlite.py` 会自动调用 `migrate_ai_fields()`。

### AI 抽取返回空结果
- 检查 `DASHSCOPE_API_KEY` 是否设置且有效。
- 检查网络是否可达 dashscope。
- `skill_type` 为空字符串是正常行为——战法描述未明确说明"主动"或"被动"时正确留空。
- 检查 `src/ai_extract.py` 的日志输出，看是否到达 MAX_RETRIES。

### 编码 / 时区问题
- 当前仓库里有中文字符串和可能的历史文章文本，务必使用 UTF-8。
- Windows PowerShell 下如果输出乱码，优先检查终端编码（`chcp 65001`），不要先怀疑数据源。
- 运行 SQLite 相关脚本时加 `-X utf8`。

### 依赖版本问题
- 先运行 `pip install -r requirements.txt`。
- 如果 `openai` 或 `beautifulsoup4` 出现 API 差异，优先看当前环境里安装的版本。
- 已知 `src/ai_extract.py` 需要 `openai>=1.40.0`。

---

## 战报抓包（stzbHelper 方案）

### 原理
率土之滨使用自定义二进制协议（TCP 端口 8001），不是 HTTP/HTTPS。
使用 [stzbHelper](https://github.com/FlxSNX/stzbHelper) 的 Npcap 抓包方案捕获数据。

### 安全性
- **被动抓包**：Npcap 只监听网卡数据，不修改游戏内存
- **无注入**：不需要 Frida，不会触发反作弊
- **不会封号**：和 Wireshark 一样，游戏无法检测

### 前置条件
1. 安装 [Npcap](https://npcap.com/#download)（已安装）
2. 下载 stzbHelper（已下载到 `tools/stzbHelper.exe`）
3. MuMu 模拟器运行中，游戏已登录

### 操作流程
```powershell
# 1. 启动 stzbHelper
.\tools\stzbHelper.exe

# 2. 在游戏中打开主公簿（点击头像 → 主公簿）激活 stzbHelper

# 3. 进入同盟战报页面

# 4. 运行自动翻页脚本
python scripts\auto_scroll_reports.py --count 30 --delay 1.5

# 5. 导入数据到本项目数据库
python scripts\import_stzb_helper.py
```

### 数据结构
stzbHelper 数据库包含 5 个表：
- `battle_report` - 战报数据（49 个字段）
- `team_user` - 同盟成员（370+ 条）
- `reports` - 详细战报（103 个字段，需开启详细战报模式）
- `task` - 攻城任务

### 关键字段
- `battle_id` - 战斗唯一ID
- `attack_name` / `defend_name` - 玩家名
- `attack_union_name` / `defend_union_name` - 同盟名
- `attack_hero1_id/2/3` - 进攻方武将ID
- `attack_hero1_level/2/3` - 武将等级
- `attack_hero1_star/2/3` - 武将红度
- `attack_all_hero_info` - 武将详情（格式：`id,level,stat1,stat2,stat3;...`）
- `all_skill_info` - 战法详情
- `result` - 战斗结果（1=胜利）
- `npc` - 是否 NPC 战斗

### 导入脚本
```powershell
# 自动查找 stzbHelper 的 .db 文件并导入
python scripts\import_stzb_helper.py

# 指定数据库文件
python scripts\import_stzb_helper.py --db path/to/stzb.db

# 只预览不导入
python scripts\import_stzb_helper.py --dry-run
```

### 数据存储
- stzbHelper 数据库：项目根目录下 `*.db` 文件
- 本项目数据库：`data/heroes.db` 中的 `stzb_battle_reports` 和 `stzb_team_members` 表

### 统计索引（stzb-helper-v2）
stzb-helper-v2 会在数据库中维护统计索引相关表：
- `player_team_snapshot`：队伍查询快照。
- `team_winrate_stats`：默认阈值（30 级、20000 兵力）下的胜率预计算统计。
- `materialized_state`：统计索引状态。
- `materialized_team_exclusion`：队伍查询中隐藏的队伍标记。

使用方式：
1. 选择数据库后，进入「队伍查询」或「队伍胜率」。
2. 首次使用或导入大量历史战报后，点击「重建索引」。重建会在后台运行，页面会显示 `重建中 已处理/总数 (%)`。
3. 后续抓包新增战报成功入库后，会自动增量更新统计索引。
4. 队伍查询会先展示快照结果；点击某支队伍的「战报」按钮后，再从原始 `battle_report` 加载相关战报。
5. 在队伍查询中点击「隐藏」后，该队伍会写入 `materialized_team_exclusion`，队伍查询和默认阈值胜率查询都会同步排除。
6. 在队伍查询中点击「隐藏管理」可以查看隐藏队伍并恢复；恢复只删除隐藏标记，不删除原始战报。

注意：
- `battle_report` 仍是唯一权威数据源；派生表只是可重建的加速层。
- 全量重建会按批读取原始战报并先写 `_rebuild` 临时表，最后再替换正式统计表；正常完成或失败后临时表会被清理。
- `stzb-helper-v2` 初始化数据库时会启用 SQLite WAL、busy timeout 等参数，并创建相关战报展开和派生胜率查询索引。
- 隐藏队伍不会删除原始 `battle_report`，重建索引后隐藏标记仍会生效。
- 恢复隐藏队伍后，页面会刷新当前查询；胜率页下一次查询也会同步显示恢复后的队伍。
- 如果页面显示「索引未就绪」，可以点击「重建索引」。
- 胜率页在默认阈值下优先使用统计索引；修改最低等级或最低兵力后会回退原始查询。

性能复测：
```powershell
# 建议先复制数据库，再对副本运行，避免实测过程改动原始库的派生表和索引
Set-Location E:\openclaw\openclaw-main\stzb-helper-v2
$env:STZB_PERF_DB="E:\path\to\copied-season.db"
go test . -run TestMaterializedStatsPerformanceProbe -v -count=1
Remove-Item Env:STZB_PERF_DB
```

当前本机基线（2026-06-03，74,326 条 `battle_report`，非百万级）：
- 统计索引重建：约 3.73 秒。
- 队伍查询：约 16 ms。
- 默认阈值胜率查询：约 35 ms。
- 相关战报展开：约 1 ms。

## stzb-helper-v2 Windows 安装包发布

### 准备完整发布目录
```powershell
Set-Location E:\openclaw\openclaw-main\stzb-helper-v2
.\installer\prepare-release.ps1 -DatabasePath "E:\path\to\your.db"
```

如果不传 `-DatabasePath`，脚本会优先读取 `build\bin\config.json` 的 `database_path`，把该数据库复制为安装包内的 `data\default.db`。

脚本会准备：
- `stzbHelper-wails.exe`
- `data\default.db`
- `platform-tools\adb.exe`
- `deps\MicrosoftEdgeWebView2Setup.exe`
- `deps\npcap-installer.exe`

### 编译一键安装包
运行：

```powershell
.\installer\prepare-release.ps1 -DatabasePath "E:\path\to\your.db" -CompileInstaller
```

如果构建机没有 Inno Setup 6，脚本会自动下载并安装 Inno Setup 6.7.3。也可以通过 `-InnoSetupPath` 指定已有 `ISCC.exe`。

输出：
```text
build\installer-output\stzbHelper-Setup.exe
```

### 分发注意
- 安装目录默认是 `%LOCALAPPDATA%\Programs\stzbHelper`，确保普通用户运行时可写数据库和配置。
- 安装器首次安装会创建 `config.json`，数据库路径指向安装目录的 `data\default.db`，ADB 指向安装目录的 `platform-tools\adb.exe`。
- 升级安装不会覆盖已有 `data\default.db` 和 `config.json`。
- Npcap 是抓包驱动，安装时可能弹出管理员权限提示；MuMu 模拟器和游戏账号仍需要用户自行安装和登录。
