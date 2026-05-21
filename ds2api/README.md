# ds2api 项目分析

## 项目概述

**ds2api** 是一个将 DeepSeek Web 对话能力转换为 OpenAI、Claude、Gemini 兼容 API 的中间件项目。

| 属性 | 值 |
|------|-----|
| Stars | 3790 |
| Forks | 1062 |
| 语言 | Go (74.7%), JavaScript (24.2%) |
| 许可证 | AGPL-3.0 |
| 最新版本 | v4.4.3 (2026-05-05) |

## 技术架构

### 后端
- **核心语言**: Go (纯 Go 实现，不依赖 Python)
- **目录**: `cmd/ds2api/`, `api/`, `internal/`
- **特性**:
  - 高并发协议适配
  - 多账号轮询
  - 流式输出支持

### 前端
- **技术**: React 管理后台
- **源码位置**: `webui/`
- **部署时**: 自动构建到 `static/admin`

### 部署方式
- 本地运行 (go run ./cmd/ds2api)
- Docker
- Vercel Serverless
- Linux systemd

## 核心功能

1. **协议转换**: DeepSeek Web → OpenAI / Claude / Gemini 兼容 API
2. **多账号轮询**: 支持多个 DeepSeek 账号轮换使用
3. **高并发**: Go 实现支持高并发请求
4. **WebUI 管理面板**: React 可视化管理界面
5. **流式响应**: 支持 Server-Sent Events 流式输出

## 项目结构 (推测)

```
ds2api/
├── cmd/ds2api/          # 入口
├── api/                 # API 路由
├── internal/            # 内部逻辑
├── webui/               # React 前端源码
├── static/admin/        # 前端构建产物
├── config.example.json  # 配置模板
└── .env.example         # 环境变量模板
```

## 与本项目的关联

该项目与 `openclaw-main` 目标类似：
- ds2api: 将 DeepSeek 网页版转为 API
- openclaw: 将率土之滨官网数据转为结构化数据

可参考其:
- Go 后端代码组织方式
- 多账号轮询机制
- 前端管理面板实现
- Vercel 部署配置

## 参考链接

- 仓库: https://github.com/CJackHwang/ds2api
- 作者博客: https://blog.cjack.top