# ENVIRONMENT.md

## 必需环境变量

| 变量名 | 用途 | 示例值（假值） | 是否必填 | 来源 | 相关文件 |
|---|---|---:|---|---|---|---|
| `DASHSCOPE_API_KEY` | 通义千问 dashscope API 密钥 | `sk-your-key-here` | **是**（AI 抽取需要） | 阿里云 dashscope 控制台 | `src/ai_extract.py` |
| `DASHSCOPE_BASE_URL` | dashscope API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 否（已有默认值） | 固定 | `src/ai_extract.py` |
| `DASHSCOPE_MODEL` | 使用的模型名 | `qwen/qwen3.5-flash` | 否（已有默认值） | 固定 | `src/ai_extract.py` |
| `DASHSCOPE_TIMEOUT` | API 超时秒数 | `30` | 否（已有默认值） | 固定 | `src/ai_extract.py` |
| `DASHSCOPE_MAX_RETRIES` | 最大重试次数 | `3` | 否（已有默认值） | 固定 | `src/ai_extract.py` |

⚠️ **注意**：`src/ai_extract.py` 在导入时会自动从项目根目录 `.env` 加载环境变量（`load_dotenv(override=True)`），`override=True` 会强制覆盖系统环境变量，确保 Windows 本地其他 KEY 不会干扰。

## 可选环境变量

| 变量名 | 用途 | 示例值（假值） | 是否必填 | 来源 | 相关文件 |
|---|---|---:|---|---|---|---|
| `SCRAPER_USER_AGENT` | 抓取时使用的 UA | `Mozilla/5.0 (Windows NT 10.0; Win64; x64)` | 否（已有默认值） | 本地环境 | `src/article_extractor.py`、`src/hero_catalog.py` |
| `SCRAPER_SLEEP_SECONDS` | 抓取间隔 | `1.5` | 否 | 本地环境 | `scripts/fetch_targets.py`（待接入） |
| `SCRAPER_TIMEOUT_SECONDS` | 请求超时 | `20` | 否（已有默认值） | 本地环境 | `src/article_extractor.py`、`src/hero_catalog.py` |
| `SCRAPER_MAX_RETRIES` | 最大重试次数 | `3` | 否 | 本地环境 | 待实现 |
| `SQLITE_PATH` | SQLite 数据库文件路径 | `data/heroes.db` | 否（已有默认值） | 本地环境 | `src/database.py` |
| `OUTPUT_PATH` | 导出文件路径 | `data/fetched_heroes.json` | 否 | 本地环境 | `scripts/fetch_targets.py` |
| `LOG_LEVEL` | 日志级别 | `INFO` | 否 | 本地环境 | `src/ai_extract.py` |
| `HTTP_PROXY` | HTTP 代理 | `http://127.0.0.1:7890` | 否 | 系统环境 / 本地环境 | 待实现 |
| `HTTPS_PROXY` | HTTPS 代理 | `http://127.0.0.1:7890` | 否 | 系统环境 / 本地环境 | 待实现 |

## 配置文件

- `.env.example`
  - 已在仓库中生成，只有假值和注释，可安全提交。
- `.env`
  - 本地使用文件，**请勿提交到 git**。
  - 包含真实 `DASHSCOPE_API_KEY`。
  - ⚠️ 如果 `.gitignore` 中还没有 `.env`，请添加。
- ⚠️ `apikey.txt`
  - 根目录存在该文件，疑似包含真实 API key。
  - 建议在 `.gitignore` 中加入 `apikey.txt`，并从 git 历史中清理。
- 配置文件
  - 当前仓库没有独立的 `config.yaml` 或 `settings.toml`。
- credentials 文件
  - 当前仓库没有这类文件。
- 本地配置
  - 可以用环境变量或 `.env` 保存。
- 生产配置
  - 后续如果上云或上 CI，要和本地配置分开。

## 不应该提交的文件

- `.env`（包含真实 API key）
- `apikey.txt`（疑似包含真实 API key）
- 任何真实 Cookie、Token、API key
- 任何真实账号密码
- 私钥文件
- 带真实密钥的调试日志
- `data/heroes.db`（生成产物）
- `data/fetched_heroes.json`（生成产物）
- `data/fetched_heroes_all.json`（生成产物）

## 依赖版本

### Python
- 建议 3.11+；当前工作区里有 `cpython-312` 的字节码痕迹，说明本地曾用过 3.12。

### Python 包
```
requests>=2.31.0      # HTTP 请求
beautifulsoup4>=4.12.3 # HTML 解析
openai>=1.40.0        # AI 客户端（兼容 dashscope）
pytest>=8.2.0         # 测试
python-dotenv>=1.0.0  # 环境变量加载（ai_extract.py 依赖）
```

⚠️ 注意：`python-dotenv` 已作为 `src/ai_extract.py` 的隐式依赖，但 `requirements.txt` 中可能未显式列出。如有 ImportError，请运行 `pip install python-dotenv`。

### 当前没有以下依赖
- Node.js / pnpm / npm / yarn
- 浏览器驱动
- 数据库迁移工具
- 队列系统

## 安全注意事项

- **不要提交 `.env`**。
- **不要提交 `apikey.txt`**，请在 `.gitignore` 中排除。
- 不要把真实 Cookie 写进 markdown。
- 不要把真实账号写进 markdown。
- 日志里不要打印密钥、Cookie 或完整授权头。
- 生产配置和测试配置要分开。
- 如果后续接入代理，代理地址也不一定算敏感，但认证信息要单独保护。
- `load_dotenv(override=True)` 会覆盖同名系统环境变量，确保本地其他 API key 不会污染本项目。
