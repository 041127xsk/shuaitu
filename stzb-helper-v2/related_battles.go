package main

import (
	"fmt"
	"strings"
	"stzbHelper/model"
)

type relatedBattle struct {
	BattleID          int64  `json:"battle_id"`
	Time              int64  `json:"time"`
	Role              string `json:"role"`
	ResultLabel       string `json:"result_label"`
	OpponentName      string `json:"opponent_name"`
	OpponentUnionName string `json:"opponent_union_name"`
	AttackHp          int64  `json:"attack_hp"`
	DefendHp          int64  `json:"defend_hp"`
	AllSkillInfo      string `json:"all_skill_info"`
}

func queryRelatedBattles(playerName, role, idu string, hero1ID, hero2ID, hero3ID, page, pageSize int) ([]relatedBattle, int64, error) {
	if model.Conn == nil {
		return nil, 0, fmt.Errorf("请先选择数据库")
	}
	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}

	query := model.Conn.Model(&model.BattleReport{}).Where("npc = 0")
	if role == "defend" {
		query = query.Where("defend_name = ? AND defend_hero1_id = ? AND defend_hero2_id = ? AND defend_hero3_id = ?", playerName, hero1ID, hero2ID, hero3ID)
		if strings.TrimSpace(idu) != "" {
			query = query.Where("defend_idu = ?", idu)
		}
	} else {
		role = "attack"
		query = query.Where("attack_name = ? AND attack_hero1_id = ? AND attack_hero2_id = ? AND attack_hero3_id = ?", playerName, hero1ID, hero2ID, hero3ID)
		if strings.TrimSpace(idu) != "" {
			query = query.Where("attack_idu = ?", idu)
		}
	}

	var total int64
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	var reports []model.BattleReport
	if err := query.Order("time DESC, battle_id DESC").Limit(pageSize).Offset((page - 1) * pageSize).Find(&reports).Error; err != nil {
		return nil, 0, err
	}

	rows := make([]relatedBattle, 0, len(reports))
	for _, report := range reports {
		row := relatedBattle{
			BattleID:     report.BattleId,
			Time:         report.Time,
			Role:         role,
			ResultLabel:  battleResultLabel(report.Result, role),
			AttackHp:     report.AttackHp,
			DefendHp:     report.DefendHp,
			AllSkillInfo: report.AllSkillInfo,
		}
		if role == "defend" {
			row.OpponentName = report.AttackName
			row.OpponentUnionName = report.AttackUnionName
		} else {
			row.OpponentName = report.DefendName
			row.OpponentUnionName = report.DefendUnionName
		}
		rows = append(rows, row)
	}
	return rows, total, nil
}

func battleResultLabel(result int64, role string) string {
	win, loss, draw := resultCounts(result, role)
	if draw > 0 {
		return "平"
	}
	if win > 0 {
		return "胜"
	}
	if loss > 0 {
		return "负"
	}
	return "未知"
}
