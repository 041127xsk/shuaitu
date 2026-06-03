package main

import (
	"fmt"
	"strconv"
	"strings"
	"stzbHelper/model"
	"time"

	"gorm.io/gorm"
)

type hiddenMaterializedTeam struct {
	ID                 int64  `json:"id"`
	PlayerName         string `json:"player_name"`
	Role               string `json:"role"`
	Idu                string `json:"idu"`
	Hero1ID            int64  `json:"hero1_id"`
	Hero2ID            int64  `json:"hero2_id"`
	Hero3ID            int64  `json:"hero3_id"`
	LineupKey          string `json:"lineup_key"`
	NormalizedSkillKey string `json:"normalized_skill_key"`
	CreatedAt          int64  `json:"created_at"`
}

func hideMaterializedPlayerTeam(team playerTeam) error {
	if model.Conn == nil {
		return fmt.Errorf("请先选择数据库")
	}

	exclusion := materializedTeamExclusionFromPlayerTeam(team)
	if strings.TrimSpace(exclusion.PlayerName) == "" || exclusion.LineupKey == "0_0_0" {
		return fmt.Errorf("队伍信息不完整，无法隐藏")
	}

	err := model.Conn.Where(
		"player_name = ? AND role = ? AND idu = ? AND lineup_key = ? AND normalized_skill_key = ?",
		exclusion.PlayerName,
		exclusion.Role,
		exclusion.Idu,
		exclusion.LineupKey,
		exclusion.NormalizedSkillKey,
	).FirstOrCreate(&exclusion).Error
	if err != nil {
		return err
	}

	invalidatePlayerTeamQueryCache()
	invalidateQueryCache(&teamWinRateQueryCache)
	return nil
}

func queryHiddenMaterializedTeams(page, pageSize int) ([]hiddenMaterializedTeam, int64, error) {
	if model.Conn == nil {
		return nil, 0, fmt.Errorf("请先选择数据库")
	}
	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}

	query := model.Conn.Model(&model.MaterializedTeamExclusion{})
	var total int64
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	var exclusions []model.MaterializedTeamExclusion
	if err := query.Order("created_at DESC, id DESC").
		Limit(pageSize).
		Offset((page - 1) * pageSize).
		Find(&exclusions).Error; err != nil {
		return nil, 0, err
	}

	rows := make([]hiddenMaterializedTeam, 0, len(exclusions))
	for _, exclusion := range exclusions {
		rows = append(rows, hiddenMaterializedTeamFromExclusion(exclusion))
	}
	return rows, total, nil
}

func restoreHiddenMaterializedTeam(id int64) error {
	if model.Conn == nil {
		return fmt.Errorf("请先选择数据库")
	}
	if id <= 0 {
		return fmt.Errorf("隐藏记录不存在")
	}

	var exclusion model.MaterializedTeamExclusion
	if err := model.Conn.First(&exclusion, id).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return fmt.Errorf("隐藏记录不存在")
		}
		return err
	}
	if err := model.Conn.Delete(&exclusion).Error; err != nil {
		return err
	}

	invalidatePlayerTeamQueryCache()
	invalidateQueryCache(&teamWinRateQueryCache)
	return nil
}

func materializedTeamExclusionFromPlayerTeam(team playerTeam) model.MaterializedTeamExclusion {
	return model.MaterializedTeamExclusion{
		PlayerName:         strings.TrimSpace(team.PlayerName),
		Role:               strings.TrimSpace(team.Role),
		Idu:                strings.TrimSpace(team.Idu),
		LineupKey:          lineupKey(int64(team.Hero1ID), int64(team.Hero2ID), int64(team.Hero3ID)),
		NormalizedSkillKey: normalizedSkillKey(team.AllSkillInfo, team.Role),
		CreatedAt:          time.Now().Unix(),
	}
}

func hiddenMaterializedTeamFromExclusion(exclusion model.MaterializedTeamExclusion) hiddenMaterializedTeam {
	hero1, hero2, hero3 := parseLineupKey(exclusion.LineupKey)
	return hiddenMaterializedTeam{
		ID:                 exclusion.ID,
		PlayerName:         exclusion.PlayerName,
		Role:               exclusion.Role,
		Idu:                exclusion.Idu,
		Hero1ID:            hero1,
		Hero2ID:            hero2,
		Hero3ID:            hero3,
		LineupKey:          exclusion.LineupKey,
		NormalizedSkillKey: exclusion.NormalizedSkillKey,
		CreatedAt:          exclusion.CreatedAt,
	}
}

func parseLineupKey(value string) (int64, int64, int64) {
	parts := strings.Split(value, "_")
	if len(parts) != 3 {
		return 0, 0, 0
	}
	ids := [3]int64{}
	for i, part := range parts {
		id, err := strconv.ParseInt(strings.TrimSpace(part), 10, 64)
		if err != nil {
			return 0, 0, 0
		}
		ids[i] = id
	}
	return ids[0], ids[1], ids[2]
}
