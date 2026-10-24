package main

import (
	"fmt"
	"log"
	"strings"
	"stzbHelper/model"
	"sync"
	"time"

	"gorm.io/gorm"
)

func materializedStateReady(name string) bool {
	if model.Conn == nil {
		return false
	}
	var state model.MaterializedState
	if err := model.Conn.Where("name = ?", name).First(&state).Error; err != nil {
		return false
	}
	return state.Status == "ready" && state.Version == materializedStatsVersion
}

func getMaterializedStates() ([]model.MaterializedState, error) {
	if model.Conn == nil {
		return nil, fmt.Errorf("请先选择数据库")
	}
	var states []model.MaterializedState
	if err := model.Conn.Order("name ASC").Find(&states).Error; err != nil {
		return nil, err
	}
	return states, nil
}

func queryMaterializedPlayerTeams(name, uname, idu string, page, pageSize int) ([]playerTeam, int, playerTeamQueryMeta, error) {
	start := time.Now()
	if page < 1 {
		page = 1
	}
	pageSize = normalizePlayerTeamPageSize(pageSize)

	query := model.Conn.Model(&model.PlayerTeamSnapshot{})
	query = applySnapshotExclusionFilter(query)
	query = applySnapshotFilters(query, name, uname, idu)

	var total int64
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, newPlayerTeamQueryMeta(start, false), err
	}

	var rows []model.PlayerTeamSnapshot
	err := query.Order("last_time DESC, last_battle_id DESC").
		Limit(pageSize).
		Offset((page - 1) * pageSize).
		Find(&rows).Error
	if err != nil {
		return nil, 0, newPlayerTeamQueryMeta(start, false), err
	}

	return snapshotsToPlayerTeams(rows), int(total), newPlayerTeamQueryMeta(start, false), nil
}

func queryMaterializedPlayerTeamsAll(name, uname, idu string) ([]playerTeam, playerTeamQueryMeta, error) {
	start := time.Now()
	query := model.Conn.Model(&model.PlayerTeamSnapshot{})
	query = applySnapshotExclusionFilter(query)
	query = applySnapshotFilters(query, name, uname, idu)

	var rows []model.PlayerTeamSnapshot
	err := query.Order("last_time DESC, last_battle_id DESC").Find(&rows).Error
	if err != nil {
		return nil, newPlayerTeamQueryMeta(start, false), err
	}
	return snapshotsToPlayerTeams(rows), newPlayerTeamQueryMeta(start, false), nil
}

func applySnapshotFilters(query *gorm.DB, name, uname, idu string) *gorm.DB {
	if strings.TrimSpace(name) != "" {
		query = query.Where("player_name LIKE ?", "%"+strings.TrimSpace(name)+"%")
	}
	if strings.TrimSpace(uname) != "" {
		query = query.Where("union_name LIKE ?", "%"+strings.TrimSpace(uname)+"%")
	}
	if strings.TrimSpace(idu) != "" {
		query = query.Where("idu LIKE ?", "%"+strings.TrimSpace(idu)+"%")
	}
	return query
}

func applySnapshotExclusionFilter(query *gorm.DB) *gorm.DB {
	return query.Where(`NOT EXISTS (
		SELECT 1 FROM materialized_team_exclusion e
		WHERE e.lineup_key = player_team_snapshot.lineup_key
			AND (e.player_name = '' OR e.player_name = player_team_snapshot.player_name)
			AND (e.role = '' OR e.role = player_team_snapshot.role)
			AND (e.idu = '' OR e.idu = player_team_snapshot.idu)
			AND (e.normalized_skill_key = '' OR e.normalized_skill_key = player_team_snapshot.normalized_skill_key)
	)`)
}

func snapshotsToPlayerTeams(rows []model.PlayerTeamSnapshot) []playerTeam {
	teams := make([]playerTeam, 0, len(rows))
	for _, row := range rows {
		teams = append(teams, playerTeam{
			PlayerName:   row.PlayerName,
			UnionName:    row.UnionName,
			BattleID:     int(row.LastBattleID),
			Hero1ID:      int(row.Hero1ID),
			Hero2ID:      int(row.Hero2ID),
			Hero3ID:      int(row.Hero3ID),
			Hero1Level:   int(row.Hero1Level),
			Hero2Level:   int(row.Hero2Level),
			Hero3Level:   int(row.Hero3Level),
			Hero1Star:    int(row.Hero1Star),
			Hero2Star:    int(row.Hero2Star),
			Hero3Star:    int(row.Hero3Star),
			TotalStar:    int(row.TotalStar),
			Hp:           int(row.Hp),
			AllSkillInfo: row.AllSkillInfo,
			Role:         row.Role,
			Time:         int(row.LastTime),
			Gear:         row.Gear,
			HeroType:     row.HeroType,
			Idu:          row.Idu,
		})
	}
	return teams
}

func queryMaterializedWinRateStats(mode, name, uname, idu string, page, pageSize, minLevel, minHp int) (map[string]interface{}, bool, error) {
	start := time.Now()
	if minLevel != defaultWinRateMinLevel || minHp != defaultWinRateMinHp || !materializedStateReady("team_winrate_stats") {
		return nil, false, nil
	}
	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 200 {
		pageSize = 50
	}

	query := model.Conn.Model(&model.TeamWinRateStat{}).
		Where("mode = ? AND min_level = ? AND min_hp = ?", mode, minLevel, minHp)
	query = applyWinRateStatExclusionFilter(query, mode)
	query = applyWinRateStatFilters(query, mode, name, uname, idu)

	var total int64
	if err := query.Count(&total).Error; err != nil {
		return nil, true, err
	}

	var rows []model.TeamWinRateStat
	err := query.Order("total_battles DESC, win_rate DESC, last_time DESC").
		Limit(pageSize).
		Offset((page - 1) * pageSize).
		Find(&rows).Error
	if err != nil {
		return nil, true, err
	}

	// 补战损比。派生表里没有战损字段（无法用 SQL 从 all_hero_info 文本算出来），
	// 这里在返回前实时填充。查询失败不影响主流程，战损比留 0（前端显示 —）。
	attachLossRatioToStats(rows, mode)

	return map[string]interface{}{
		"list":      rows,
		"total":     total,
		"page":      page,
		"pageSize":  pageSize,
		"query_ms":  time.Since(start).Milliseconds(),
		"cache_hit": false,
		"source":    "materialized",
	}, true, nil
}

// attachLossRatioToStats 给派生表查询结果补上战损比与损耗率。
//
// mode = "player"：派生表行是「某个玩家 + 某个阵容」，按 玩家+阵容 精确匹配。
// mode = "team"  ：派生表行是「某个阵容」（跨玩家聚合），按阵容累加所有玩家。
//
// 早先两种模式都只按三武将匹配，导致 player 模式下分子分母跨了全部玩家：
// 战损取自全库 786 场、页面这一行只代表 10 场，且攻守两侧重复计入，
// 实测 646 支队伍里 609 支损耗率超过 100%（最高 287%）。
func attachLossRatioToStats(rows []model.TeamWinRateStat, mode string) {
	if len(rows) == 0 {
		return
	}

	stats, err := cachedTeamLossStats()
	if err != nil {
		log.Printf("战损统计查询失败（派生表 mode=%s），战损比留空: %v", mode, err)
		return
	}
	for i := range rows {
		var ls *teamLossStat
		if mode == "team" {
			ls = aggregateLossByLineup(stats, rows[i].Hero1ID, rows[i].Hero2ID, rows[i].Hero3ID)
		} else if v, ok := stats[teamLossKey(rows[i].PlayerName, rows[i].Hero1ID, rows[i].Hero2ID, rows[i].Hero3ID)]; ok {
			ls = v
		}
		if ls == nil || ls.Battles == 0 {
			continue
		}
		rows[i].OurLostHp = ls.OurLost
		rows[i].EnemyLostHp = ls.EnemyLost
		rows[i].OurWoundedHp = ls.OurWounded
		rows[i].EnemyWoundedHp = ls.EnemyWounded
		rows[i].OurKilledHp = ls.OurKilled
		rows[i].EnemyKilledHp = ls.EnemyKilled
		rows[i].LossRatioBattles = ls.Battles
		rows[i].LossRatio = computeLossRatio(ls.OurLost, ls.EnemyLost)
		rows[i].LossRate = computeDestroyedRate(ls.OurLost, ls.OurTotalHp)
	}
}

// aggregateLossByLineup 按阵容（三武将）跨玩家累加战损。
// 用于「按队伍组合」视图：该视图把同一阵容的所有玩家合成一行。
func aggregateLossByLineup(stats map[string]*teamLossStat, h1, h2, h3 int64) *teamLossStat {
	if len(stats) == 0 {
		return nil
	}
	var out *teamLossStat
	for _, ls := range stats {
		if ls.Hero1ID != h1 || ls.Hero2ID != h2 || ls.Hero3ID != h3 {
			continue
		}
		if out == nil {
			out = &teamLossStat{Hero1ID: h1, Hero2ID: h2, Hero3ID: h3}
		}
		out.OurLost += ls.OurLost
		out.EnemyLost += ls.EnemyLost
		out.OurWounded += ls.OurWounded
		out.EnemyWounded += ls.EnemyWounded
		out.OurKilled += ls.OurKilled
		out.EnemyKilled += ls.EnemyKilled
		out.OurTotalHp += ls.OurTotalHp
		out.EnemyTotalHp += ls.EnemyTotalHp
		out.Battles += ls.Battles
	}
	return out
}

// 战损统计的短时缓存。
//
// 战损需要扫描全表并逐条解析 all_hero_info 文本（约 200-400ms），
// 而胜率页每次翻页都会调用，不做缓存会明显拖慢翻页。
// 只有「按玩家」「按队伍」两种口径，用两个槽位即可；新增战报时统一失效。
const lossStatsCacheTTL = 20 * time.Second

var (
	lossStatsCacheMu    sync.Mutex
	lossPlayerCacheAt   time.Time
	lossPlayerCacheData map[string]*playerLossStat
	lossTeamCacheAt     time.Time
	lossTeamCacheData   map[string]*teamLossStat
)

// invalidateLossStatsCache 清空战损缓存（新增/切换数据库时调用）。
func invalidateLossStatsCache() {
	lossStatsCacheMu.Lock()
	lossPlayerCacheData = nil
	lossTeamCacheData = nil
	lossStatsCacheMu.Unlock()
}

func cachedPlayerLossStats() (map[string]*playerLossStat, error) {
	level := effectiveMinTeamHeroLevel(defaultWinRateMinLevel)

	lossStatsCacheMu.Lock()
	if lossPlayerCacheData != nil && time.Since(lossPlayerCacheAt) < lossStatsCacheTTL {
		data := lossPlayerCacheData
		lossStatsCacheMu.Unlock()
		return data, nil
	}
	lossStatsCacheMu.Unlock()

	data, err := queryPlayerLossStats(level)
	if err != nil {
		return nil, err
	}

	lossStatsCacheMu.Lock()
	lossPlayerCacheData = data
	lossPlayerCacheAt = time.Now()
	lossStatsCacheMu.Unlock()
	return data, nil
}

func cachedTeamLossStats() (map[string]*teamLossStat, error) {
	level := effectiveMinTeamHeroLevel(defaultWinRateMinLevel)

	lossStatsCacheMu.Lock()
	if lossTeamCacheData != nil && time.Since(lossTeamCacheAt) < lossStatsCacheTTL {
		data := lossTeamCacheData
		lossStatsCacheMu.Unlock()
		return data, nil
	}
	lossStatsCacheMu.Unlock()

	data, err := queryTeamLossStats(level)
	if err != nil {
		return nil, err
	}

	lossStatsCacheMu.Lock()
	lossTeamCacheData = data
	lossTeamCacheAt = time.Now()
	lossStatsCacheMu.Unlock()
	return data, nil
}

func applyWinRateStatFilters(query *gorm.DB, mode, name, uname, idu string) *gorm.DB {
	if strings.TrimSpace(name) != "" {
		if mode == "team" {
			query = query.Where("players LIKE ?", "%"+strings.TrimSpace(name)+"%")
		} else {
			query = query.Where("player_name LIKE ?", "%"+strings.TrimSpace(name)+"%")
		}
	}
	if strings.TrimSpace(uname) != "" {
		query = query.Where("union_name LIKE ?", "%"+strings.TrimSpace(uname)+"%")
	}
	if strings.TrimSpace(idu) != "" {
		query = query.Where("idu LIKE ?", "%"+strings.TrimSpace(idu)+"%")
	}
	return query
}

func applyWinRateStatExclusionFilter(query *gorm.DB, mode string) *gorm.DB {
	if mode == "team" {
		return query.Where(`NOT EXISTS (
			SELECT 1 FROM materialized_team_exclusion e
			WHERE e.lineup_key = team_winrate_stats.lineup_key
				AND (e.normalized_skill_key = '' OR e.normalized_skill_key = team_winrate_stats.normalized_skill_key)
		)`)
	}
	return query.Where(`NOT EXISTS (
		SELECT 1 FROM materialized_team_exclusion e
		WHERE e.lineup_key = team_winrate_stats.lineup_key
			AND (e.player_name = '' OR e.player_name = team_winrate_stats.player_name)
			AND (e.role = '' OR e.role = team_winrate_stats.role)
			AND (e.idu = '' OR e.idu = team_winrate_stats.idu)
			AND (e.normalized_skill_key = '' OR e.normalized_skill_key = team_winrate_stats.normalized_skill_key)
	)`)
}
