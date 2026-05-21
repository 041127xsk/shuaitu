# SCRAPER_NOTES.md

## 数据源列表

### 1) 武将基础目录 JSON
- 名称：武将基础目录
- URL：`https://s.166.net/config/sh_stzb/wujiangInfo.json?_t=1648539610183`
- 入口文件：`src/hero_catalog.py`
- 使用脚本：`scripts/fetch_targets.py`、`scripts/resolve_targets.py`
- 抓取方式：HTTP JSON
- 是否需要登录：否
- 是否需要 Cookie：否
- 是否需要代理：当前不需要
- 是否有验证码风险：低，但接口可能随站点策略变化
- 当前状态：可用

### 2) 武将志目录文章
- 名称：武将目录索引文章
- URL：`https://ds.163.com/article/636268ee74424700010125d5/`
- 入口文件：`src/hero_catalog.py`、`scripts/fetch_targets.py`
- 抓取方式：HTTP 页面内容 + feed 解析
- 是否需要登录：否
- 是否需要 Cookie：否
- 是否需要代理：当前不需要
- 是否有验证码风险：低到中，取决于目标站策略
- 当前状态：可用

### 3) 武将志文章 feed API
- 名称：武将志详情 feed
- URL：`https://inf.ds.163.com/v1/web/feed/basic/facade?feedId=<feed_id>&squareId=`
- 入口文件：`src/article_extractor.py`
- 使用脚本：`scripts/preview_extract.py`、`scripts/fetch_targets.py`
- 抓取方式：HTTP API
- 是否需要登录：否
- 是否需要 Cookie：否
- 是否需要代理：当前不需要
- 是否有验证码风险：低，但有可能被限流
- 当前状态：可用

### 4) 通义千问 AI 抽取（dashscope）
- 名称：AI 结构化抽取
- URL：`https://dashscope.aliyuncs.com/compatible-mode/v1`（OpenAI 兼容）
- 入口文件：`src/ai_extract.py`
- 使用脚本：`scripts/fetch_targets.py`（集成在主流程中）
- 抓取方式：HTTPS API（OpenAI 兼容）
- 是否需要登录：是（API Key）
- 是否需要 Cookie：否
- 是否需要代理：当前不需要（国内直接访问）
- 是否有验证码风险：无
- 当前状态：可用
- 注意：无 `DASHSCOPE_API_KEY` 时自动跳过，不影响主流程

## 数据流
1. 先请求武将基础目录 JSON，得到全部武将元信息。
2. 过滤出高星武将，当前规则是 `star >= 4` 或 `quality` 以 `SR` 结尾。
3. 请求武将目录文章，拿到目录里的锚点和文章链接。
4. 按武将名字在目录文章里做精确文本匹配，解析出对应文章 URL。
5. 由文章 URL 提取 `feed_id`，再请求 feed API。
6. 从 feed 的 `content.body.longText` 中解析 HTML。
7. 按标题和段落规则识别主战法章节。
8. **（可选）AI 结构化抽取**：调用通义千问 dashscope，从战法段落提取结构化字段（skill_type / trigger_rate / targets / effects 等）。
9. 把武将元信息 + 主战法写入 `data/fetched_heroes.json` 和 `data/heroes.db`。

## 如何分页
- 当前这套公开数据源没有做分页循环。
- 目录 JSON 是一次性取全量。
- 文章 feed 是按单篇 feed_id 逐个请求。

## 如何提取详情页
- 先从目录文章 `longText` 里的 `<a href=...>` 锚点提取链接。
- 再按武将名做精确匹配。
- `scripts/fetch_targets.py` 里对"群吕布"做了别名兜底，优先匹配 `群骑吕布`。

## 如何解析字段

### 目录字段
| 字段名 | 来源 | 类型 | 是否必填 | 示例 | 清洗规则 |
|---|---|---|---|---|---|
| `id` | wujiangInfo.json | int | 是 | 1001 | 转整数 |
| `name` | wujiangInfo.json | str | 是 | 群吕布 | 转字符串 |
| `uniqueName` | wujiangInfo.json | str | 否 | 神吕 | 转字符串，可能为空 |
| `quality` | wujiangInfo.json | str | 是 | SSR | 以 `SR`/`SSR` 结尾 |
| `star` | wujiangInfo.json | int | 是 | 5 | 转整数 |
| `faction`（字段名为 contory） | wujiangInfo.json | str | 是 | 群 | 来自 `contory` 字段 |
| `cost` | wujiangInfo.json | float | 否 | 3.5 | 转浮点数 |
| `unit_type`（字段名为 type） | wujiangInfo.json | str | 是 | 骑 | 来自 `type` 字段 |
| `image` | wujiangInfo.json | str | 否 | https://... | 图片 URL |

⚠️ 字段命名说明：`faction` 实际从 `contory` 字段读取，`unit_type` 从 `type` 字段读取。`hero_catalog.py` 在 `to_hero_records()` 中做了字段映射，不要随便改。

### 文章字段
| 字段名 | 来源 | 类型 | 是否必填 | 示例 | 清洗规则 |
|---|---|---|---|---|---|
| `feed_id` | URL path | str | 是 | 639fc0e9c5a3250001d3cb97 | 从 URL 提取 |
| `title` | feed.body.title | str | 是 | 武将解析：群骑吕布 | 转字符串 |
| `subtitle` | feed.body.subTitle | str | 否 | 神吕 | 可为空 |
| `intro` | feed.body.text | str | 否 | 简介文本 | 可为空 |
| `links` | feed.body.longText | list[str] | 否 | [...] | BeautifulSoup 提取锚点 href |
| `sections` | feed.body.longText | list[SkillSection] | 是 | [...] | split_sections() 输出 |
| `blocks` | feed.body.longText | list[ArticleBlock] | 是 | [...] | iter_blocks() 输出 |

### 主战法字段
| 字段名 | 来源 | 类型 | 是否必填 | 示例 | 清洗规则 |
|---|---|---|---|---|---|
| `primary_skill.title` | section.title | str | 是 | 主战法解析 | 从 sections 匹配 |
| `primary_skill.name` | 段落中的【战法名】 | str | 是 | 天下无双 | detect_skill_names() 提取 |
| `primary_skill.paragraph_count` | 段落数量 | int | 是 | 8 | 清洗后段落数 |
| `primary_skill.image_count` | 图片数量 | int | 是 | 21 | section.images 长度 |
| `primary_skill.paragraphs` | 正文段落 | list[str] | 是 | [...] | _trim_skill_paragraphs() 清洗 |
| `primary_skill.images` | 图片 URL 列表 | list[str] | 否 | [...] | 可为空 |

### AI 抽取字段（SQLite primary_skills 表）
| 字段名 | 来源 | 类型 | 是否必填 | 示例 | 清洗规则 |
|---|---|---|---|---|---|
| `skill_type` | AI 抽取 | str | 否 | 主动/被动/指挥/典藏/兵种/阵法/追击 | 来自 LLM，空=未识别或内政 |
| `trigger_type` | AI 抽取 | str | 否 | 瞬发/准备 | 来自 LLM |
| `trigger_rate` | AI 抽取 | int | 否 | 45 | 0-100 整数 |
| `trigger_condition` | AI 抽取 | str | 否 | 战斗中，... | 来自 LLM |
| `targets` | AI 抽取 | str | 否 | 敌军群体(2人) | 来自 LLM |
| `effects_json` | AI 抽取 | str(JSON) | 否 | [{"description":"...", "category":"..."}] | JSON 数组 |
| `duration` | AI 抽取 | str | 否 | 2回合 | 来自 LLM |
| `notes` | AI 抽取 | str | 否 | 受谋略属性影响 | 来自 LLM |
| `ai_extracted` | 标记位 | int | 是 | 0/1 | 0=未抽取 1=已抽取 |

⚠️ `skill_type` 为空字符串是**正常行为**，不是错误：战法描述未明确说明"主动"或"被动"时，LLM 按提示词正确留空，不代表没有数据。

## 反爬与限速
- 当前限速策略：没有显式全局 sleep，也没有并发。
- User-Agent：目前脚本里用的是简单的 `Mozilla/5.0`。
- 请求头：当前只显式设置了最小 UA，没有复杂的伪装头。
- 重试策略：AI 抽取有指数退避重试（默认3次），其他请求层暂无统一重试。
- 超时策略：
  - feed API 默认 20 秒
  - 武将目录默认 30 秒
  - AI 抽取默认 30 秒（dashscope timeout 可配置）
- 代理策略：当前没有内置代理逻辑。
- 失败退避策略：AI 抽取有 `_call_llm` 内部退避，其他层暂无。
- 429 / 403 处理方式：目前主要靠抛错和手工重跑。

需要人工确认的地方：
- 目标站是否允许更高频率抓取。
- 如果后续要做批量定时任务，是否需要代理池。
- 是否要把抓取频率写成环境变量（已有 `SCRAPER_SLEEP_SECONDS` 环境变量占位）。

## 登录态与认证
- 当前已确认的公开接口不需要登录。
- AI 抽取需要 `DASHSCOPE_API_KEY`，通过 `.env` 文件加载。
- ⚠️ 当前仓库根目录有 `apikey.txt` 文件，疑似包含真实 API key，请在 `.gitignore` 中排除。
- 如果后续接入需要登录的页面：
  - Cookie 不要提交到仓库。
  - 用本地 `.env` 或外部密钥系统承载。
  - 日志里不要打印完整 Cookie。

## 调度
- 当前没有 cron。
- 当前没有队列。
- 当前没有定时任务。
- 当前所有任务都需要手动运行脚本。

建议的补跑方式：
- 直接重新跑 `python scripts/fetch_targets.py`
- 若后续加状态表，则只重跑失败 feed 或未完成 feed（`crawl_state` 表已建）

避免重复抓取的方法：
- 先按 `feed_id` 去重。
- 目录解析结果用唯一链接列表去重。
- 落库时对 `name` 或 `feed_id` 加唯一约束。

## 数据质量

### 去重规则
- `extract_feed_ids_from_links()` 会对 feed id 去重。
- `scripts/fetch_targets.py` 会对每个英雄的 URL 列表做去重。
- SQLite 层对 `heroes.feed_id` 和 `crawl_state.feed_id` 加了唯一约束。

### 增量抓取规则
- 当前没有正式增量逻辑。
- 现在的做法是手动重跑批量脚本生成快照。

### 断点续跑规则
- `crawl_state` 表已建，记录 `feed_id / status / last_error / updated_at`。
- `fetch_targets.py` 还未全面接入 `crawl_state`，中断后需手动重跑。

### 失败数据如何记录
- `scripts/fetch_targets.py` 会把失败条目写成：
  - `hero_name`
  - `article_url`
  - `feed_id`
  - `error`

### 异常样本如何保存
- 当前保存在控制台输出和生成 JSON 里。
- `crawl_state.last_error` 记录最近一次错误。

### 数据校验方法
- 抽样检查 `primary_skill.name` 是否是目标主战法。
- 检查 `paragraph_count`、`image_count` 是否和页面正文一致。
- 检查导出的 hero 数量是否和目录过滤结果大致匹配。
- 运行 `pytest` 确保单元测试通过。
- 运行 `scripts/load_to_sqlite.py --report` 检查 SQLite 数据完整性。

## 修改抓取逻辑的注意事项
- 改 selectors 要同步更新测试。
- 改字段名要检查下游 JSON、SQLite 和评分逻辑。
- 改频率要注意限流和目标站规则。
- 改代理要注意成本、稳定性和失败退避。
- 改存储结构要写迁移方案，别直接覆盖旧数据。
- AI 抽取 prompt 改动后需要重新验证抽取结果（`scripts/preview_extract.py`）。
