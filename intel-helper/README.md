# 率土战报情报库 - Intel Helper

> 能够用命令行解决的事情就不要来麻烦我。

个人使用的战报情报管理工具，支持上传战报截图、OCR识别、玩家搜索和克制分析。

## 快速开始

### 1. 安装依赖

```bash
cd intel-helper
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置 OCR provider
```

### 3. 初始化数据库

```bash
python -m backend.seed
```

### 4. 启动服务

```bash
# 开发模式
uvicorn backend.main:app --reload --port 8000

# 或使用 Python 直接运行
python -m backend.main
```

### 5. 访问前端

打开浏览器访问: http://localhost:8000

## 功能模块

### 战报上传 (POST /intel/upload)
- 接收战报截图
- 自动OCR识别
- 返回识别结果供确认

### 情报确认 (POST /intel/confirm)
- 用户确认OCR结果
- 保存玩家、队伍、武将信息
- 保留原始截图

### 玩家搜索 (GET /players/search)
- 按玩家名模糊搜索
- 支持赛季筛选
- 查看历史队伍

### 克制分析 (POST /counter/analyze)
- 根据敌方队伍武将分析
- 输出敌方队伍类型标签
- 推荐克制方向

## OCR 模块

支持多种 OCR 提供者：

### 本地 OCR (默认)
使用 Tesseract，需安装 tesseract-ocr

### 阿里云 OCR (预留)
配置 DASHSCOPE_API_KEY 使用通义千问

## 数据库

SQLite 数据库，包含以下表：
- hero: 武将信息（含战法名称、战法截图等）
- player: 玩家信息
- intel_snapshot: 战报快照
- observed_team: 观察到的队伍
- observed_team_member: 队伍武将成员
- player_alias: 玩家别名 (预留)

## 武将库

武将库支持展示武将的主战法信息和截图：

### 查看武将详情
点击武将卡片可查看：
- 武将基础属性（攻/防/速）
- 武将特点标签
- 主战法名称、类型、发动概率
- 战法截图（可点击放大查看）

### 导入战法数据
从配将助手导入战法数据：

```bash
# 导入战法数据（从 ../data/heroes.db）
python -m backend.import_skills

# 指定源数据库路径
python -m backend.import_skills --source /path/to/heroes.db

# 仅预览不写入
python -m backend.import_skills --dry-run
```

导入前需先运行配将助手的抓取脚本生成武将数据。

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
