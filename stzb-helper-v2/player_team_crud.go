package main

import (
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"time"

	"stzbHelper/global"
	"stzbHelper/model"
)

type manualPlayerTeamInput struct {
	PlayerName     string `json:"player_name"`
	UnionName      string `json:"union_name"`
	Idu            string `json:"idu"`
	Role           string `json:"role"`
	Time           int64  `json:"time"`
	BattleID       int64  `json:"battle_id"`
	Hero1ID        int64  `json:"hero1_id"`
	Hero2ID        int64  `json:"hero2_id"`
	Hero3ID        int64  `json:"hero3_id"`
	Hero1Level     int64  `json:"hero1_level"`
	Hero2Level     int64  `json:"hero2_level"`
	Hero3Level     int64  `json:"hero3_level"`
	Hero1Star      int64  `json:"hero1_star"`
	Hero2Star      int64  `json:"hero2_star"`
	Hero3Star      int64  `json:"hero3_star"`
	TotalStar      int64  `json:"total_star"`
	Hp             int64  `json:"hp"`
	AllSkillInfo   string `json:"all_skill_info"`
	Gear           string `json:"gear"`
	HeroType       string `json:"hero_type"`
	Note           string `json:"note"`
	SourceBattleID int64  `json:"source_battle_id"`
	SourceRole     string `json:"source_role"`
}

func buildManualPlayerTeam(input manualPlayerTeamInput, existing *model.ManualPlayerTeam) model.ManualPlayerTeam {
	now := time.Now().Unix()
	row := model.ManualPlayerTeam{
		Enabled:   1,
		CreatedAt: now,
		UpdatedAt: now,
	}
	if existing != nil {
		row = *existing
		row.UpdatedAt = now
		if row.CreatedAt == 0 {
			row.CreatedAt = now
		}
	}

	role := normalizePlayerTeamRole(input.Role)
	sourceRole := strings.TrimSpace(input.SourceRole)
	if sourceRole == "" {
		sourceRole = role
	} else {
		sourceRole = normalizePlayerTeamRole(sourceRole)
	}
	if input.Time <= 0 {
		input.Time = now
	}
	totalStar := input.TotalStar
	if totalStar == 0 {
		totalStar = input.Hero1Star + input.Hero2Star + input.Hero3Star
	}

	row.PlayerName = strings.TrimSpace(input.PlayerName)
	row.UnionName = strings.TrimSpace(input.UnionName)
	row.Idu = strings.TrimSpace(input.Idu)
	row.Role = role
	row.Time = input.Time
	row.BattleID = input.BattleID
	row.Hero1ID = input.Hero1ID
	row.Hero2ID = input.Hero2ID
	row.Hero3ID = input.Hero3ID
	row.Hero1Level = input.Hero1Level
	row.Hero2Level = input.Hero2Level
	row.Hero3Level = input.Hero3Level
	row.Hero1Star = input.Hero1Star
	row.Hero2Star = input.Hero2Star
	row.Hero3Star = input.Hero3Star
	row.TotalStar = totalStar
	row.Hp = input.Hp
	row.AllSkillInfo = strings.TrimSpace(input.AllSkillInfo)
	row.Gear = strings.TrimSpace(input.Gear)
	row.HeroType = strings.TrimSpace(input.HeroType)
	row.Note = strings.TrimSpace(input.Note)
	row.SourceBattleID = input.SourceBattleID
	row.SourceRole = sourceRole
	if row.Enabled == 0 {
		row.Enabled = 1
	}
	return row
}

func normalizePlayerTeamRole(role string) string {
	if strings.TrimSpace(role) == "defend" {
		return "defend"
	}
	return "attack"
}

func validateManualPlayerTeam(row model.ManualPlayerTeam) string {
	if row.PlayerName == "" {
		return "玩家名称不能为空"
	}
	if row.Hero1ID == 0 || row.Hero2ID == 0 || row.Hero3ID == 0 {
		return "三名武将 ID 必须填写完整"
	}
	return ""
}

func parseManualPlayerTeamInput(jsonStr string) (manualPlayerTeamInput, error) {
	var input manualPlayerTeamInput
	if err := json.Unmarshal([]byte(jsonStr), &input); err != nil {
		return input, err
	}
	return input, nil
}

func queryManualPlayerTeamCandidates(name string, uname string, idu string) ([]playerTeam, error) {
	if model.Conn == nil {
		return nil, fmt.Errorf("请先选择数据库")
	}
	var manualRows []model.ManualPlayerTeam
	query := model.Conn.Where("enabled = ?", 1)
	if strings.TrimSpace(name) != "" {
		query = query.Where("player_name LIKE ?", "%"+strings.TrimSpace(name)+"%")
	}
	if strings.TrimSpace(uname) != "" {
		query = query.Where("union_name LIKE ?", "%"+strings.TrimSpace(uname)+"%")
	}
	if strings.TrimSpace(idu) != "" {
		query = query.Where("idu LIKE ?", "%"+strings.TrimSpace(idu)+"%")
	}
	if err := query.Find(&manualRows).Error; err != nil {
		return nil, err
	}

	rows := make([]playerTeam, 0, len(manualRows))
	for _, row := range manualRows {
		battleID := int(row.BattleID)
		if battleID == 0 {
			battleID = int(row.ID)
		}
		rows = append(rows, playerTeam{
			PlayerName:   row.PlayerName,
			UnionName:    row.UnionName,
			BattleID:     battleID,
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
			Time:         int(row.Time),
			Gear:         row.Gear,
			HeroType:     row.HeroType,
			Idu:          row.Idu,
			SourceType:   "manual",
			SourceID:     int(row.ID),
			Manual:       true,
			Note:         row.Note,
		})
	}
	return rows, nil
}

func queryHiddenPlayerTeamKeys() (map[string]bool, error) {
	var hiddenRows []model.HiddenPlayerTeam
	if err := model.Conn.Find(&hiddenRows).Error; err != nil {
		return nil, err
	}
	hidden := make(map[string]bool, len(hiddenRows))
	for _, row := range hiddenRows {
		hidden[hiddenPlayerTeamKey(row.SourceType, int(row.SourceID), row.Role)] = true
	}
	return hidden, nil
}

func invalidatePlayerTeamDerivedData() {
	invalidatePlayerTeamQueryCache()
	invalidateQueryCache(&teamWinRateQueryCache)
	log.Println("队伍查询修正层已变更，查询缓存已刷新")
}

func (a *App) CreateManualPlayerTeam(jsonStr string) string {
	if model.Conn == nil {
		return global.Response{Message: "请先选择数据库"}.Error()
	}
	input, err := parseManualPlayerTeamInput(jsonStr)
	if err != nil {
		return global.Response{Message: "队伍数据格式错误: " + err.Error()}.Error()
	}
	row := buildManualPlayerTeam(input, nil)
	if msg := validateManualPlayerTeam(row); msg != "" {
		return global.Response{Message: msg}.Error()
	}
	if err := model.Conn.Create(&row).Error; err != nil {
		return global.Response{Message: "新增队伍失败: " + err.Error()}.Error()
	}
	if row.SourceBattleID > 0 {
		hidePlayerTeamRecord("battle_report", row.SourceBattleID, row.SourceRole, row.PlayerName, row.Idu, "编辑原始队伍后自动隐藏")
	}
	invalidatePlayerTeamDerivedData()
	return global.Response{Data: row, Message: "队伍已新增"}.Success()
}

func (a *App) UpdateManualPlayerTeam(id int, jsonStr string) string {
	if model.Conn == nil {
		return global.Response{Message: "请先选择数据库"}.Error()
	}
	var existing model.ManualPlayerTeam
	if err := model.Conn.First(&existing, id).Error; err != nil {
		return global.Response{Message: "手工队伍不存在"}.Error()
	}
	input, err := parseManualPlayerTeamInput(jsonStr)
	if err != nil {
		return global.Response{Message: "队伍数据格式错误: " + err.Error()}.Error()
	}
	row := buildManualPlayerTeam(input, &existing)
	if msg := validateManualPlayerTeam(row); msg != "" {
		return global.Response{Message: msg}.Error()
	}
	if err := model.Conn.Save(&row).Error; err != nil {
		return global.Response{Message: "保存队伍失败: " + err.Error()}.Error()
	}
	invalidatePlayerTeamDerivedData()
	return global.Response{Data: row, Message: "队伍已保存"}.Success()
}

func (a *App) HidePlayerTeamRecord(sourceType string, sourceID int, role string) string {
	if model.Conn == nil {
		return global.Response{Message: "请先选择数据库"}.Error()
	}
	if strings.TrimSpace(sourceType) == "" || sourceID <= 0 {
		return global.Response{Message: "队伍来源无效"}.Error()
	}
	if err := hidePlayerTeamRecord(sourceType, int64(sourceID), normalizePlayerTeamRole(role), "", "", "手动隐藏"); err != nil {
		return global.Response{Message: "隐藏队伍失败: " + err.Error()}.Error()
	}
	invalidatePlayerTeamDerivedData()
	return global.Response{Message: "队伍已隐藏，可在隐藏管理中恢复"}.Success()
}

func hidePlayerTeamRecord(sourceType string, sourceID int64, role string, playerName string, idu string, note string) error {
	var count int64
	if err := model.Conn.Model(&model.HiddenPlayerTeam{}).
		Where("source_type = ? AND source_id = ? AND role = ?", sourceType, sourceID, role).
		Count(&count).Error; err != nil {
		return err
	}
	if count > 0 {
		return nil
	}
	hidden := model.HiddenPlayerTeam{
		SourceType: sourceType,
		SourceID:   sourceID,
		Role:       role,
		PlayerName: playerName,
		Idu:        idu,
		Note:       note,
		CreatedAt:  time.Now().Unix(),
	}
	return model.Conn.Create(&hidden).Error
}

func (a *App) RestoreHiddenPlayerTeamRecord(sourceType string, sourceID int, role string) string {
	if model.Conn == nil {
		return global.Response{Message: "请先选择数据库"}.Error()
	}
	if err := model.Conn.Where("source_type = ? AND source_id = ? AND role = ?", sourceType, sourceID, normalizePlayerTeamRole(role)).Delete(&model.HiddenPlayerTeam{}).Error; err != nil {
		return global.Response{Message: "恢复队伍失败: " + err.Error()}.Error()
	}
	invalidatePlayerTeamDerivedData()
	return global.Response{Message: "队伍已恢复"}.Success()
}

func (a *App) DeleteManualPlayerTeam(id int) string {
	if model.Conn == nil {
		return global.Response{Message: "请先选择数据库"}.Error()
	}
	if err := model.Conn.Delete(&model.ManualPlayerTeam{}, id).Error; err != nil {
		return global.Response{Message: "删除手工队伍失败: " + err.Error()}.Error()
	}
	model.Conn.Where("source_type = ? AND source_id = ?", "manual", id).Delete(&model.HiddenPlayerTeam{})
	invalidatePlayerTeamDerivedData()
	return global.Response{Message: "手工队伍已删除"}.Success()
}

func (a *App) GetHiddenPlayerTeamsBySource() string {
	if model.Conn == nil {
		return global.Response{Message: "请先选择数据库"}.Error()
	}
	var rows []model.HiddenPlayerTeam
	if err := model.Conn.Order("created_at DESC").Find(&rows).Error; err != nil {
		return global.Response{Message: "读取隐藏队伍失败: " + err.Error()}.Error()
	}
	return global.Response{Data: rows}.Success()
}
