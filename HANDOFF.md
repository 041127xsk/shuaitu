# 率土之滨战报助手 - 项目交接文档

> 文档版本：2026-05-08
> 项目状态：核心功能已完成，可正常使用

---

## 一、项目概述

本项目是一个面向《率土之滨》策略游戏的战报数据采集与分析工具，主要功能：
- 通过 Npcap 被动抓包采集战报数据（不封号）
- 自动翻页采集同盟战报
- 数据导入/导出（支持按同盟分组导出 Excel）
- GUI 桌面应用程序（战报助手.exe）

**GitHub 仓库**：https://github.com/041127xsk/shuaitu

---

## 二、技术栈

| 层级 | 技术 |
|------|------|
| 语言 | Python 3.12 + Go 1.22 |
| GUI | tkinter（战报助手） |
| 抓包 | Npcap + stzbHelper（Go/Wails） |
| 数据库 | SQLite |
| 导出 | openpyxl（Excel） |
| 模拟器控制 | ADB（MuMu 模拟器） |

---

## 三、文件结构

```
E:\openclaw\openclaw-main\
├── 战报助手/                          # 分发包
│   ├── 战报助手.exe                   # 主程序（tkinter GUI）
│   ├── stzbHelper.exe                 # 抓包工具（Go/Wails，支持数据库自动继承）
│   ├── 使用说明.txt
│   └── 数据库/
│       └── 益桤#7191611_X5602.db     # 战报数据库（8150条战报，296条成员）
│
├── battle_assistant/                  # 战报助手源码（Python）
│   ├── core/
│   │   ├── config.py                  # 配置管理
│   │   ├── adb_helper.py              # ADB 工具
│   │   ├── scroller.py                # 自动翻页
│   │   ├── importer.py                # 数据导入
│   │   └── exporter.py                # Excel 导出（支持按同盟分组）
│   ├── gui/
│   │   └── main_window.py             # 主界面（tkinter）
│   └── main.py                        # 入口
│
├── stzbHelper-src/                    # stzbHelper 源码（Go/Wails）
│   ├── parse.go                       # 协议解析（已修改：数据库自动继承）
│   ├── npacp.go                       # Npcap 抓包逻辑
│   ├── app.go                         # API 接口（已添加 SetDbDir/GetDbDir）
│   ├── model/
│   │   └── database.go                # 数据库初始化（已修改：支持目录配置）
│   ├── global/
│   │   └── variable.go                # 全局变量（已添加 DbDir）
│   └── frontend/                      # Vue.js 前端
│
├── scripts/                           # Python 脚本
│   ├── auto_scroll_reports.py         # 自动翻页脚本
│   ├── import_stzb_helper.py          # 数据导入脚本
│   ├── export_excel.py                # Excel 导出脚本
│   └── analyze_all_db.py              # 数据库分析脚本
│
├── tools/
│   ├── stzbHelper.exe                 # stzbHelper 工具
│   └── stzb-capture/                  # 抓包工具文件夹
│       ├── stzbHelper.exe
│       ├── auto_scroll_reports.py
│       ├── import_stzb_helper.py
│       └── start_capture.bat          # 一键启动脚本
│
├── data/
│   ├── heroes.db                      # 项目主数据库
│   └── alliances/                     # 按同盟导出的 Excel 文件
│
└── docs/
    ├── AGENTS.md                      # Agent 工作指南
    ├── PROJECT_MEMORY.md              # 项目记忆
    ├── RUNBOOK.md                     # 运行手册
    ├── SCRAPER_NOTES.md               # 抓取笔记
    ├── TODO.md                        # 任务清单
    ├── DECISIONS.md                   # 技术决策记录
    └── ENVIRONMENT.md                 # 环境变量说明
```

---

## 四、核心模块说明

### 4.1 战报采集系统

**原理**：
- 率土之滨使用自定义二进制协议（TCP 端口 8001），不是 HTTP/HTTPS
- 使用 Npcap 被动抓包，不修改游戏内存，不会封号
- stzbHelper 负责协议解析和数据存储

**协议格式**：
```
[0-3]  包大小 (big endian uint32)
[4-7]  协议号/命令ID (big endian uint32)
[12]   数据类型: 2=明文, 3=zlib压缩, 5=异或加密
[17+]  数据载荷
```

**关键协议号**：
| 协议号 | 数据类型 | 说明 |
|--------|----------|------|
| 92 | 战报 | 同盟战报数据 |
| 103 | 成员 | 同盟成员列表 |
| 3686 | 主簿 | 玩家个人信息 |
| 724 | 叫阵 | 战役叫阵消息 |

### 4.2 自动翻页模块

**文件**：`battle_assistant/core/scroller.py`

**功能**：
- 使用 ADB 模拟滑动操作
- 自适应屏幕分辨率（1080x1920）
- 可配置翻页次数、间隔、滑动时长
- 支持后台运行，不阻塞 GUI

**滑动坐标**：
```python
cx = w // 2           # 水平居中
y_start = int(h * 0.4)  # 起始位置（40%高度）
y_end = int(h * 0.15)   # 结束位置（15%高度）
```

### 4.3 数据导入模块

**文件**：`battle_assistant/core/importer.py`

**功能**：
- 从 stzbHelper 数据库导入数据到项目数据库
- 支持过滤 NPC 战斗
- 支持过滤攻方武将不足 3 名的战报
- 自动去重（基于 battle_id）

### 4.4 Excel 导出模块

**文件**：`battle_assistant/core/exporter.py`

**功能**：
- 自动列宽（中文字符算 2 个宽度）
- 表头样式（蓝底白字，冻结首行）
- 数据样式（居中，带边框）
- 支持按同盟分组导出（每个同盟一个 Excel 文件）

### 4.5 stzbHelper（Go/Wails）

**源码**：`stzbHelper-src/`

**已修改文件**：
- `parse.go` - 协议解析
- `model/database.go` - 数据库初始化（支持目录配置和自动继承）
- `app.go` - API 接口（添加 SetDbDir/GetDbDir）
- `global/variable.go` - 全局变量（添加 DbDir）

**新功能**：
- 数据库自动继承：检测到同名玩家时自动打开已存在的数据库
- 数据库目录配置：可以通过 API 设置数据库存储目录

---

## 五、运行方式

### 5.1 环境初始化

```powershell
# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Npcap
# 下载地址：https://npcap.com/#download

# 安装 Go 环境（如需编译 stzbHelper）
# 下载地址：https://golang.google.cn/dl/

# 安装 Wails（如需编译 stzbHelper）
go install github.com/wailsapp/wails/v2/cmd/wails@latest
```

### 5.2 使用战报助手

```powershell
# 1. 解压 战报助手_v1.0.zip
# 2. 运行 战报助手.exe
# 3. 程序会自动检测 ADB 和游戏版本
# 4. 启动 stzbHelper 进行抓包
# 5. 导入数据到数据库
# 6. 按同盟导出 Excel
```

### 5.3 使用 stzbHelper 单独抓包

```powershell
# 1. 启动 stzbHelper.exe
# 2. 在游戏中打开主公簿激活
# 3. 进入同盟战报页面
# 4. 运行自动翻页脚本
python scripts/auto_scroll_reports.py --count 5000 --delay 0.1 --duration 100

# 5. 导入数据
python scripts/import_stzb_helper.py

# 6. 导出 Excel
python scripts/export_excel.py --all --filter-valid --filter-no-npc
```

### 5.4 编译 stzbHelper

```powershell
cd stzbHelper-src
wails build
```

---

## 六、设计规范

### 6.1 数据模型

#### BattleReport（战报数据）
```python
battle_id: int              # 战斗ID（唯一索引）
battle_time: str            # 战斗时间
wid_name: str               # 战斗地点
attack_name: str            # 进攻方
attack_union_name: str      # 进攻方同盟
defend_name: str            # 防守方
defend_union_name: str      # 防守方同盟
attack_hero1_id: int        # 攻方大营ID
attack_hero2_id: int        # 攻方中军ID
attack_hero3_id: int        # 攻方前锋ID
attack_hero1_level: int     # 攻方大营等级
attack_hero2_level: int     # 攻方中军等级
attack_hero3_level: int     # 攻方前锋等级
attack_hero1_star: int      # 攻方大营红度
attack_hero2_star: int      # 攻方中军红度
attack_hero3_star: int      # 攻方前锋红度
defend_hero1_id: int        # 守方大营ID
defend_hero2_id: int        # 守方中军ID
defend_hero3_id: int        # 守方前锋ID
attack_hp: int              # 攻方兵力
defend_hp: int              # 守方兵力
npc: int                    # 是否NPC战斗（1=是）
result: int                 # 战斗结果（1=胜利）
```

#### TeamMember（同盟成员）
```python
member_id: int              # 成员ID
name: str                   # 名称
contribute_total: int       # 总贡献
contribute_week: int        # 周贡献
power: int                  # 势力值
wu: int                     # 武勋
group_name: str             # 分组/同盟名
join_time: str              # 加入时间
```

### 6.2 配置管理

**文件**：`config.json`（程序运行时自动生成）

```json
{
  "adb_path": "C:\\Users\\...\\adb.exe",
  "serial": "127.0.0.1:16384",
  "game_version": "auto",
  "scroll_count": 5000,
  "scroll_delay": 0.1,
  "scroll_duration": 100,
  "filter_npc": true,
  "filter_incomplete": true,
  "last_export_path": "",
  "last_export_dir": ""
}
```

### 6.3 样式规范

- **编码**：全部 UTF-8
- **日志**：使用标准 logging，区分 info/warning/error
- **错误处理**：核心函数保证不抛异常，返回空结构或降级
- **幂等性**：所有写入操作支持重复执行

---

## 七、已知问题与风险

### 7.1 当前问题
1. **stzbHelper 前端**：未修改，需要后续开发数据库管理界面
2. **按同盟导出**：如果同盟名包含特殊字符，文件名会自动替换
3. **ADB 路径**：需要手动配置或自动检测

### 7.2 高风险区域
- `stzbHelper-src/model/database.go`：数据库初始化逻辑
- `stzbHelper-src/parse.go`：协议解析逻辑
- `battle_assistant/core/exporter.py`：Excel 导出逻辑

### 7.3 安全警示
- 本项目仅用于个人学习和数据分析
- 不要利用抓包数据进行自动化操作（可能违反游戏用户协议）
- 不要公开分享抓到的 API 端点或通信协议细节

---

## 八、下一步建议

### 8.1 优先级 P0
1. **测试 stzbHelper 新功能**：验证数据库自动继承是否正常工作
2. **完善 GUI 功能**：添加数据库目录配置界面

### 8.2 优先级 P1
1. **数据分析功能**：胜率统计、热门阵容分析
2. **阵容评分系统**：基于战报数据的武将搭配评分
3. **定时自动抓取**：定时运行 stzbHelper + 翻页 + 导入

### 8.3 优先级 P2
1. **Web 前端**：基于 stzbHelper 的 Vue.js 前端开发数据展示页面
2. **多账号支持**：支持同时采集多个账号的数据
3. **数据同步**：云端数据备份和同步

---

## 九、给下一个 Agent 的第一条建议

> **先运行 `pytest`，确认测试全部通过后再开始改代码。** 不要先重构，不要先加功能，先确认现状是健康的。
>
> 如果测试通过，下一步最值得做的是 **测试 stzbHelper 的数据库自动继承功能**，确保新版本正常工作。
>
> **重要提示**：
> - stzbHelper 源码在 `stzbHelper-src/` 目录
> - 编译需要 Go 环境和 Wails：`cd stzbHelper-src && wails build`
> - Python 依赖在 `requirements.txt`
> - 数据库文件在 `data/heroes.db` 和 `战报助手/数据库/`

---

## 十、关键文件索引

| 文件 | 用途 | 重要程度 |
|------|------|----------|
| `battle_assistant/gui/main_window.py` | GUI 主界面 | 高 |
| `battle_assistant/core/exporter.py` | Excel 导出（含按同盟分组） | 高 |
| `battle_assistant/core/importer.py` | 数据导入 | 高 |
| `battle_assistant/core/scroller.py` | 自动翻页 | 高 |
| `stzbHelper-src/model/database.go` | 数据库初始化（已修改） | 高 |
| `stzbHelper-src/parse.go` | 协议解析 | 高 |
| `stzbHelper-src/app.go` | API 接口（已修改） | 高 |
| `scripts/auto_scroll_reports.py` | 自动翻页脚本 | 中 |
| `scripts/import_stzb_helper.py` | 数据导入脚本 | 中 |
| `scripts/export_excel.py` | Excel 导出脚本 | 中 |

---

**文档维护**：每次会话结束后更新 PROJECT_MEMORY.md、TODO.md 和本 HANDOFF.md。
