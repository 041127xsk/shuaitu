# 性能优化设计文档

## 1. 背景与目标

### 1.1 当前瓶颈
- 每条战报触发 10-15 次 DB 操作（INSERT + 物化增量更新 + 缓存清空）
- `GetTeamWinRateByTeam` 全量加载到 Go 内存再分页，数据量大时 OOM
- `GetTeamWinRate` 同一 CTE 执行两遍（COUNT + DATA），查询耗时翻倍
- `GetPlayerTeam` raw 路径 UNION ALL 无 LIMIT，全量扫描
- goroutine 并发写入 SQLite，导致 "database is locked"
- 全局变量 `fullbuf`/`waitbuf` 无锁保护，数据竞争
- battle_report 有 17 个索引，写入放大严重
- 缓存只存最后一条结果，命中率极低

### 1.2 目标
- 消除 SQLite 并发写入问题
- 查询耗时降低 50%+
- 消除 OOM 风险
- 提高缓存命中率

## 2. 优化项清单

### P0: 写入性能

#### P0-1: 写入队列 ✅
- **方案**: 新建 `write_queue.go`，用 buffered channel + 单 worker goroutine 序列化所有 DB 写入
- **改动**: `write_queue.go`(新建), `parse.go`(enqueueBattleReport), `app.go`(startWriteQueue)
- **验证**: 编译通过 + 启动不崩溃

#### P0-2: npacp.go 全局变量加锁 ✅
- **方案**: `fullbuf`/`fullsize`/`waitbuf` 加 `sync.Mutex` 保护
- **改动**: `npacp.go`
- **验证**: 编译通过

#### P0-3: 连接池配置 ✅
- **方案**: `SetMaxOpenConns(1)` + WAL 参数移入 DSN
- **改动**: `model/database.go`
- **验证**: 编译通过

### P0: 查询性能

#### P0-4: GetTeamWinRate CTE 合并 ✅
- **方案**: 用 `COUNT(*) OVER()` 窗口函数，单次查询同时获取总数和分页数据
- **改动**: `app.go` GetTeamWinRate 函数
- **验证**: 编译通过

#### P0-5: GetTeamWinRateByTeam 加 LIMIT ✅
- **方案**: SQL 加 `LIMIT 5000` 防止全量加载 OOM
- **改动**: `app.go` GetTeamWinRateByTeam 函数
- **验证**: 编译通过

#### P0-6: GetPlayerTeam raw 路径加 LIMIT ✅
- **方案**: UNION ALL 查询加 `LIMIT 5000`
- **改动**: `player_team_query.go` queryPlayerTeamCandidates
- **验证**: 编译通过

### P1: 索引优化

#### P1-1: 精简索引 ✅
- **方案**: 删除被复合索引覆盖的单列索引
- **当前**: 15 个索引（从 17 个精简）
- **删除**:
  - `idx_br_attack_name` — 被 `idx_br_attack_related` 覆盖
  - `idx_br_defend_name` — 被 `idx_br_defend_related` 覆盖
  - `idx_br_attack_union_name` — 查询频率低
  - `idx_br_defend_union_name` — 同上
  - `idx_br_attack_hero1_id` — 查询频率低
  - `idx_br_defend_hero1_id` — 同上
- **保留**:
  - `idx_br_npc` — 高选择性过滤
  - `idx_br_time_battle_id` — 排序核心
  - `idx_br_attack_team_query` — 队伍查询核心
  - `idx_br_defend_team_query` — 同上
  - `idx_br_attack_idu_time` — IDU 查询
  - `idx_br_defend_idu_time` — 同上
  - `idx_br_result_time` — 胜率查询
  - `idx_br_attack_winrate` — 胜率统计
  - `idx_br_defend_winrate` — 同上
  - `idx_br_attack_related` — 相关战报
  - `idx_br_defend_related` — 同上
  - 物化表索引 — 保留
- **改动**: `model/database.go`
- **验证**: 编译通过 + 查询性能不下降

### P1: 缓存优化

#### P1-2: 缓存改为 LRU Map ✅
- **方案**: 用 `container/list` + `map` 实现 LRU 缓存
- **当前**: 最多缓存 32 个不同查询结果，TTL 20 秒
- **改动**: `query_cache.go`, `player_team_query.go`
- **验证**: 编译通过 + 重复查询命中缓存

### P2: 前端优化（后续）

#### P2-1: 虚拟滚动
- TeamQuery / TeamWinRate 列表使用虚拟滚动
- 避免大 pageSize 时 DOM 膨胀

#### P2-2: 图片 lazy loading
- 英雄头像使用 `loading="lazy"`

#### P2-3: Excel 导出优化
- 使用流式写入避免大内存占用

## 3. 实施顺序

1. ✅ P0-1: 写入队列
2. ✅ P0-2: 全局变量加锁
3. ✅ P0-3: 连接池配置
4. ✅ P0-4: CTE 合并
5. ✅ P0-5: GetTeamWinRateByTeam LIMIT
6. ✅ P0-6: GetPlayerTeam LIMIT
7. ✅ P1-1: 精简索引
8. ✅ P1-2: 缓存 LRU Map

## 4. 验证标准

每完成一项后检查：
- [ ] `go build` 编译通过
- [ ] `wails build` 构建成功
- [ ] exe 启动不崩溃
- [ ] 数据库列表正常显示
- [ ] 功能正常（队伍查询、胜率统计、考勤等）
