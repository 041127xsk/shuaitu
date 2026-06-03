package main

import (
	"fmt"
	"strings"
	"stzbHelper/model"
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
