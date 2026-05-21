# 率土战报情报库 - 微信小程序

基于 `intel-helper` 后端的微信小程序客户端。

## 功能特性

- **上传战报**: 支持截图上传，OCR智能识别武将信息
- **玩家搜索**: 按玩家名/赛季搜索，查看历史队伍
- **武将库**: 浏览所有武将属性、阵营、标签
- **克制分析**: 分析敌方队伍类型，推荐克制武将

## 项目结构

```
miniprogram/
├── app.js           # 小程序入口
├── app.json         # 全局配置
├── app.wxss         # 全局样式
├── pages/
│   ├── index/        # 首页
│   ├── upload/       # 上传战报页
│   ├── search/      # 搜索玩家页
│   ├── player-detail/# 玩家详情页
│   ├── heroes/       # 武将库页
│   ├── hero-detail/ # 武将详情页
│   └── counter/      # 克制分析页
└── assets/           # 静态资源
```

## 配置说明

### 后端 API 地址

在 `app.js` 中配置后端服务地址：

```javascript
globalData: {
  apiBase: 'http://127.0.0.1:8000',  // 开发环境
  // apiBase: 'https://your-server.com',  // 生产环境
}
```

### 开发者配置

1. 打开微信开发者工具
2. 导入本项目
3. 在 `project.config.json` 中修改 `appid` 为你的小程序 AppID
4. 填写后端服务地址

## API 接口

小程序调用以下后端接口：

| 接口 | 方法 | 功能 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/intel/upload` | POST | 上传战报截图 |
| `/intel/confirm` | POST | 确认保存情报 |
| `/players/search` | GET | 搜索玩家 |
| `/players/{id}` | GET | 获取玩家详情 |
| `/heroes` | GET | 获取武将列表 |
| `/counter/analyze` | POST | 克制分析 |
| `/seasons` | GET | 获取赛季列表 |

## 开发说明

### 页面跳转

- tabBar 页面: `wx.switchTab()`
- 普通页面: `wx.navigateTo()`

### 请求封装

使用 `app.request()` 方法封装请求，自动处理 JSON 解析和错误处理。

### 样式规范

- 使用暗色主题配色
- 卡片式布局
- 圆角设计
- 渐变按钮

## 注意事项

1. 小程序需要在 `app.json` 中配置服务器域名白名单（生产环境）
2. 开发环境可关闭域名校验
3. OCR 识别依赖后端 Tesseract 服务
4. 首次使用需确保后端服务已启动
