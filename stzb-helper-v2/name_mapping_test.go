package main

import (
	"encoding/json"
	"testing"

	"stzbHelper/model"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

func setupNameMappingTestDB(t *testing.T) {
	t.Helper()
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("open sqlite memory db: %v", err)
	}
	if err := db.AutoMigrate(&model.NameMapping{}); err != nil {
		t.Fatalf("migrate name mapping: %v", err)
	}
	model.Conn = db
}

func TestSaveNameMappingUpsertsSameKindAndID(t *testing.T) {
	setupNameMappingTestDB(t)
	app := &App{}

	first := app.SaveNameMapping(`{"kind":"hero","id":130001,"name":"新武将"}`)
	var firstResp struct {
		Code int `json:"code"`
	}
	if err := json.Unmarshal([]byte(first), &firstResp); err != nil || firstResp.Code != 200 {
		t.Fatalf("first SaveNameMapping response = %s, err = %v", first, err)
	}

	second := app.SaveNameMapping(`{"kind":"武将","id":130001,"name":"新武将改名"}`)
	var secondResp struct {
		Code int `json:"code"`
	}
	if err := json.Unmarshal([]byte(second), &secondResp); err != nil || secondResp.Code != 200 {
		t.Fatalf("second SaveNameMapping response = %s, err = %v", second, err)
	}

	var rows []model.NameMapping
	if err := model.Conn.Find(&rows).Error; err != nil {
		t.Fatalf("query name mappings: %v", err)
	}
	if len(rows) != 1 {
		t.Fatalf("len(rows) = %d, want 1", len(rows))
	}
	if rows[0].Kind != "hero" || rows[0].RefID != 130001 || rows[0].Name != "新武将改名" {
		t.Fatalf("row = %#v, want updated hero mapping", rows[0])
	}
}

func TestValidateNameMappingRejectsBadInput(t *testing.T) {
	if msg := validateNameMapping(model.NameMapping{Kind: "hero", RefID: 1, Name: "名"}); msg != "" {
		t.Fatalf("valid mapping rejected: %s", msg)
	}
	if msg := validateNameMapping(model.NameMapping{Kind: "bad", RefID: 1, Name: "名"}); msg == "" {
		t.Fatal("bad kind was accepted")
	}
	if msg := validateNameMapping(model.NameMapping{Kind: "hero", RefID: 0, Name: "名"}); msg == "" {
		t.Fatal("zero id was accepted")
	}
	if msg := validateNameMapping(model.NameMapping{Kind: "hero", RefID: 1, Name: ""}); msg == "" {
		t.Fatal("empty name was accepted")
	}
}
