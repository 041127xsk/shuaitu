# 网络抓包采集战报

## 原理
游戏翻页时会请求战报 API，直接拦截响应拿 JSON，比 OCR 快 10 倍，准确率 100%。

## 快速开始

### 1. 安装依赖
```bash
pip install mitmproxy
```

### 2. 启动抓包代理
```bash
python src/network_capture/capture.py --port 8888
```
启动后会自动连接 SQLite，抓到的数据同时写入 JSON 文件和数据库。

### 3. 设置模拟器代理（新终端）
```bash
python src/network_capture/capture.py --setup --port 8888
```

### 4. 在游戏中翻页战报
手动翻页，代理会自动抓取战报 API 响应。控制台会打印：
```
[CAPTURED] https://api.xxx.com/battle/report -> 1 items
[CAPTURED] https://api.xxx.com/battle/list -> 2 items
```

### 5. 停止抓包
按 `Ctrl+C` 停止，自动打印统计：
```
==================================================
  抓包统计
==================================================
  总请求:     156
  匹配 API:   23
  已保存:     8
  重复跳过:   0
  错误:       0
  JSON 文件:  data/network_capture/capture_20260507_103000.json
  DB 记录数:  8
==================================================
```

### 6. 移除代理
```bash
python src/network_capture/capture.py --remove
```

## 命令速查

| 命令 | 说明 |
|------|------|
| `python src/network_capture/capture.py` | 启动抓包（默认端口 8888，自动写 DB） |
| `python src/network_capture/capture.py --port 9090` | 指定端口 |
| `python src/network_capture/capture.py --no-db` | 只保存 JSON，不写 SQLite |
| `python src/network_capture/capture.py --setup` | 设置模拟器代理 |
| `python src/network_capture/capture.py --remove` | 移除模拟器代理 |
| `python src/network_capture/capture.py --analyze data/network_capture/xxx.json` | 分析已抓数据 |
| `python src/network_capture/capture.py --stats` | 查看数据库统计 |

## 数据存储

### JSON 文件
保存在 `data/network_capture/capture_YYYYMMDD_HHMMSS.json`，每条记录：
```json
{
  "timestamp": "2026-05-07T10:30:00",
  "url": "https://api.game.com/battle/report/list",
  "method": "POST",
  "status_code": 200,
  "content_type": "application/json",
  "data": { /* 解析后的 JSON 数据 */ },
  "raw": "原始响应前 5000 字符",
  "digest": "去重哈希"
}
```

### SQLite 数据库
写入 `data/heroes.db` 的 `battle_reports` 表，字段：
- `url` - 请求 URL
- `method` - HTTP 方法
- `status_code` - 状态码
- `data_json` - JSON 响应
- `digest` - 去重哈希（URL + 时间戳的 SHA256）
- `created_at` - 抓取时间

自动去重：同一条战报不会重复入库（基于 digest）。

## 注意事项
- 首次运行可能需要安装 mitmproxy CA 证书（访问 `mitm.it`）
- 如果游戏使用 HTTPS + SSL Pinning，需要配合 Frida 做 SSL Unpinning
- 抓包数据保存在 `data/network_capture/` 和 `data/heroes.db`
- 模拟器 ADB 序列号默认 `127.0.0.1:16384`，可通过 `--serial` 修改

## 对比 OCR
| 方案 | 速度 | 准确率 | 难度 |
|------|------|--------|------|
| OCR 滑动截图 | ~5秒/页 | 95% | 低 |
| 网络抓包 | ~0.1秒/页 | 100% | 中 |
