package main

import (
	"encoding/json"
	"path/filepath"
	"testing"

	"stzbHelper/model"
)

type groupWuRow struct {
	Group        string  `json:"group"`
	MemberCount  int     `json:"member_count"`
	TotalWu      int     `json:"total_wu"`
	AverageWu    float64 `json:"average_wu"`
	AveragePower float64 `json:"average_power"`
	ZeroWuCount  int     `json:"zero_wu_count"`
}

func TestGetGroupWuIncludesAveragePower(t *testing.T) {
	defer closeModelConn(t)

	dbPath := filepath.Join(t.TempDir(), "group-wu.db")
	model.InitDB(dbPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create database")
	}

	teamUsers := []model.TeamUser{
		{Id: 1, Name: "张三", Group: "一团", Power: 1000, Wu: 500},
		{Id: 2, Name: "李四", Group: "一团", Power: 2000, Wu: 0},
		{Id: 3, Name: "王五", Group: "二团", Power: 4000, Wu: 900},
	}
	if err := model.Conn.Create(&teamUsers).Error; err != nil {
		t.Fatalf("create team users: %v", err)
	}

	resp := decodeAppResponse(t, (&App{}).GetGroupWu())
	if resp.Code != 200 {
		t.Fatalf("GetGroupWu response = %+v", resp)
	}

	var rows []groupWuRow
	if err := json.Unmarshal(resp.Data, &rows); err != nil {
		t.Fatalf("unmarshal group rows: %v", err)
	}
	if len(rows) != 2 {
		t.Fatalf("len(rows) = %d, want 2", len(rows))
	}

	gotByGroup := map[string]groupWuRow{}
	for _, row := range rows {
		gotByGroup[row.Group] = row
	}

	if gotByGroup["一团"].AveragePower != 1500 {
		t.Fatalf("一团 AveragePower = %v, want 1500", gotByGroup["一团"].AveragePower)
	}
	if gotByGroup["一团"].AverageWu != 250 {
		t.Fatalf("一团 AverageWu = %v, want 250", gotByGroup["一团"].AverageWu)
	}
	if gotByGroup["一团"].ZeroWuCount != 1 {
		t.Fatalf("一团 ZeroWuCount = %d, want 1", gotByGroup["一团"].ZeroWuCount)
	}
	if gotByGroup["二团"].AveragePower != 4000 {
		t.Fatalf("二团 AveragePower = %v, want 4000", gotByGroup["二团"].AveragePower)
	}
}
