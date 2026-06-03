package main

import (
	"encoding/json"
	"strings"
	"time"

	"stzbHelper/global"
	"stzbHelper/model"
)

type nameMappingInput struct {
	Kind string `json:"kind"`
	ID   int64  `json:"id"`
	Name string `json:"name"`
	Note string `json:"note"`
}

func normalizeNameMappingKind(kind string) string {
	switch strings.TrimSpace(strings.ToLower(kind)) {
	case "hero", "武将":
		return "hero"
	case "skill", "战法":
		return "skill"
	case "gear", "宝物":
		return "gear"
	default:
		return strings.TrimSpace(strings.ToLower(kind))
	}
}

func buildNameMapping(input nameMappingInput, existing *model.NameMapping) model.NameMapping {
	now := time.Now().Unix()
	row := model.NameMapping{
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
	row.Kind = normalizeNameMappingKind(input.Kind)
	row.RefID = input.ID
	row.Name = strings.TrimSpace(input.Name)
	row.Note = strings.TrimSpace(input.Note)
	return row
}

func validateNameMapping(row model.NameMapping) string {
	if row.Kind != "hero" && row.Kind != "skill" && row.Kind != "gear" {
		return "映射类型只能是武将、战法或宝物"
	}
	if row.RefID <= 0 {
		return "ID 必须大于 0"
	}
	if row.Name == "" {
		return "名称不能为空"
	}
	return ""
}

func parseNameMappingInput(jsonStr string) (nameMappingInput, error) {
	var input nameMappingInput
	err := json.Unmarshal([]byte(jsonStr), &input)
	return input, err
}

func (a *App) GetNameMappings() string {
	if model.Conn == nil {
		return global.Response{Message: "请先选择数据库"}.Error()
	}
	var rows []model.NameMapping
	if err := model.Conn.Order("kind ASC, ref_id ASC").Find(&rows).Error; err != nil {
		return global.Response{Message: "读取名称映射失败: " + err.Error()}.Error()
	}
	return global.Response{Data: rows}.Success()
}

func (a *App) SaveNameMapping(jsonStr string) string {
	if model.Conn == nil {
		return global.Response{Message: "请先选择数据库"}.Error()
	}
	input, err := parseNameMappingInput(jsonStr)
	if err != nil {
		return global.Response{Message: "映射数据格式错误: " + err.Error()}.Error()
	}

	var existing model.NameMapping
	var existingPtr *model.NameMapping
	if err := model.Conn.Where("kind = ? AND ref_id = ?", normalizeNameMappingKind(input.Kind), input.ID).First(&existing).Error; err == nil {
		existingPtr = &existing
	}

	row := buildNameMapping(input, existingPtr)
	if msg := validateNameMapping(row); msg != "" {
		return global.Response{Message: msg}.Error()
	}
	if err := model.Conn.Save(&row).Error; err != nil {
		return global.Response{Message: "保存名称映射失败: " + err.Error()}.Error()
	}
	return global.Response{Data: row, Message: "名称映射已保存"}.Success()
}

func (a *App) DeleteNameMapping(kind string, id int) string {
	if model.Conn == nil {
		return global.Response{Message: "请先选择数据库"}.Error()
	}
	if err := model.Conn.Where("kind = ? AND ref_id = ?", normalizeNameMappingKind(kind), id).Delete(&model.NameMapping{}).Error; err != nil {
		return global.Response{Message: "删除名称映射失败: " + err.Error()}.Error()
	}
	return global.Response{Message: "名称映射已删除"}.Success()
}
