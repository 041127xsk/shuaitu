package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"stzbHelper/model"
)

type appTestResponse struct {
	Code    int             `json:"code"`
	Message string          `json:"msg"`
	Data    json.RawMessage `json:"data"`
}

func decodeAppResponse(t *testing.T, raw string) appTestResponse {
	t.Helper()
	var resp appTestResponse
	if err := json.Unmarshal([]byte(raw), &resp); err != nil {
		t.Fatalf("decode response %q: %v", raw, err)
	}
	return resp
}

func withTempExecutableDir(t *testing.T) string {
	t.Helper()
	tmpDir := t.TempDir()
	exePath, err := os.Executable()
	if err != nil {
		t.Fatalf("get executable path: %v", err)
	}
	dstExe := filepath.Join(tmpDir, filepath.Base(exePath))
	data, err := os.ReadFile(exePath)
	if err != nil {
		t.Fatalf("read executable: %v", err)
	}
	if err := os.WriteFile(dstExe, data, 0755); err != nil {
		t.Fatalf("write temp executable: %v", err)
	}
	return dstExe
}

func readTestConfig(t *testing.T, exePath string) AppConfig {
	t.Helper()
	configPath := filepath.Join(filepath.Dir(exePath), "config.json")
	data, err := os.ReadFile(configPath)
	if err != nil {
		t.Fatalf("read config %s: %v", configPath, err)
	}
	var config AppConfig
	if err := json.Unmarshal(data, &config); err != nil {
		t.Fatalf("unmarshal config: %v", err)
	}
	return config
}

func TestCreateDbCreatesNameMappingTableAndPersistsConfig(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()
	defer closeModelConn(t)

	model.Conn = nil
	app := &App{}

	resp := decodeAppResponse(t, app.CreateDb("fresh-db"))
	if resp.Code != 200 {
		t.Fatalf("CreateDb response = %+v", resp)
	}

	if model.Conn == nil {
		t.Fatal("model.Conn is nil after CreateDb")
	}

	config := readTestConfig(t, exePath)
	wantPath := filepath.Join(filepath.Dir(exePath), "fresh-db.db")
	if config.DatabasePath != wantPath {
		t.Fatalf("config.DatabasePath = %q, want %q", config.DatabasePath, wantPath)
	}

	if !strings.HasSuffix(config.DatabasePath, ".db") {
		t.Fatalf("config.DatabasePath = %q, want .db suffix", config.DatabasePath)
	}

	var count int64
	if err := model.Conn.Raw("SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = ?", "name_mapping").Scan(&count).Error; err != nil {
		t.Fatalf("query sqlite_master: %v", err)
	}
	if count != 1 {
		t.Fatalf("name_mapping table count = %d, want 1", count)
	}

	getResp := decodeAppResponse(t, app.GetNameMappings())
	if getResp.Code != 200 {
		t.Fatalf("GetNameMappings response = %+v", getResp)
	}
	if string(getResp.Data) != "[]" {
		t.Fatalf("GetNameMappings data = %s, want []", string(getResp.Data))
	}
}

func TestSelectDbPersistsChosenDatabasePath(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()
	defer closeModelConn(t)

	dir := filepath.Dir(exePath)
	selectedPath := filepath.Join(dir, "picked.db")
	model.InitDB(selectedPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create selectedPath database")
	}
	closeModelConn(t)

	app := &App{}
	resp := decodeAppResponse(t, app.SelectDb("picked"))
	if resp.Code != 200 {
		t.Fatalf("SelectDb response = %+v", resp)
	}

	config := readTestConfig(t, exePath)
	if config.DatabasePath != selectedPath {
		t.Fatalf("config.DatabasePath = %q, want %q", config.DatabasePath, selectedPath)
	}
}

func TestAutoConnectDbUsesLastPersistedDatabase(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()
	defer closeModelConn(t)

	dir := filepath.Dir(exePath)
	firstDB := filepath.Join(dir, "first.db")
	secondDB := filepath.Join(dir, "second.db")

	model.InitDB(firstDB)
	if model.Conn == nil {
		t.Fatal("InitDB did not create first database")
	}
	model.Conn.Exec("INSERT INTO team_user(name, `group`) VALUES (?, ?)", "first-user", "A")

	model.InitDB(secondDB)
	if model.Conn == nil {
		t.Fatal("InitDB did not create second database")
	}
	model.Conn.Exec("INSERT INTO team_user(name, `group`) VALUES (?, ?)", "second-user", "B")
	closeModelConn(t)

	config := AppConfig{
		AdbPath:         defaultConfig.AdbPath,
		AdbSerial:       defaultConfig.AdbSerial,
		ScrollCount:     defaultConfig.ScrollCount,
		ScrollDelay:     defaultConfig.ScrollDelay,
		ScrollDuration:  defaultConfig.ScrollDuration,
		StopOnDuplicate: defaultConfig.StopOnDuplicate,
		DatabasePath:    secondDB,
	}
	configData, err := json.Marshal(config)
	if err != nil {
		t.Fatalf("marshal config: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "config.json"), configData, 0644); err != nil {
		t.Fatalf("write config: %v", err)
	}

	app := &App{}
	resp := decodeAppResponse(t, app.AutoConnectDb())
	if resp.Code != 200 {
		t.Fatalf("AutoConnectDb response = %+v", resp)
	}

	if model.Conn == nil {
		t.Fatal("model.Conn is nil after AutoConnectDb")
	}

	var rows []model.TeamUser
	if err := model.Conn.Find(&rows).Error; err != nil {
		t.Fatalf("query team_user: %v", err)
	}
	if len(rows) != 1 || rows[0].Name != "second-user" {
		t.Fatalf("rows = %#v, want second-user from persisted database", rows)
	}
}

func TestRenameDbRenamesConfiguredDatabaseAndPersistsConfig(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()
	defer closeModelConn(t)

	dir := filepath.Dir(exePath)
	oldPath := filepath.Join(dir, "old-name.db")
	model.InitDB(oldPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create old database")
	}
	if err := persistSelectedDatabasePath(oldPath); err != nil {
		t.Fatalf("persistSelectedDatabasePath: %v", err)
	}

	app := &App{}
	resp := decodeAppResponse(t, app.RenameDb("[配置]old-name", "new-name"))
	if resp.Code != 200 {
		t.Fatalf("RenameDb response = %+v", resp)
	}

	newPath := filepath.Join(dir, "new-name.db")
	if _, err := os.Stat(newPath); err != nil {
		t.Fatalf("renamed database missing: %v", err)
	}
	if _, err := os.Stat(oldPath); !os.IsNotExist(err) {
		t.Fatalf("old database still exists, err=%v", err)
	}

	config := readTestConfig(t, exePath)
	if config.DatabasePath != newPath {
		t.Fatalf("config.DatabasePath = %q, want %q", config.DatabasePath, newPath)
	}
}

func TestDeleteDbRemovesNonConfiguredDatabase(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()
	defer closeModelConn(t)

	dir := filepath.Dir(exePath)
	keepPath := filepath.Join(dir, "keep.db")
	deletePath := filepath.Join(dir, "delete-me.db")

	model.InitDB(keepPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create keep database")
	}
	if err := persistSelectedDatabasePath(keepPath); err != nil {
		t.Fatalf("persistSelectedDatabasePath: %v", err)
	}
	closeModelConn(t)

	model.InitDB(deletePath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create delete database")
	}
	closeModelConn(t)

	app := &App{}
	resp := decodeAppResponse(t, app.DeleteDb("delete-me"))
	if resp.Code != 200 {
		t.Fatalf("DeleteDb response = %+v", resp)
	}

	if _, err := os.Stat(deletePath); !os.IsNotExist(err) {
		t.Fatalf("delete database still exists, err=%v", err)
	}

	config := readTestConfig(t, exePath)
	if config.DatabasePath != keepPath {
		t.Fatalf("config.DatabasePath = %q, want %q", config.DatabasePath, keepPath)
	}
}

func TestDeleteDbRejectsConfiguredDatabase(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()
	defer closeModelConn(t)

	dir := filepath.Dir(exePath)
	selectedPath := filepath.Join(dir, "selected.db")
	model.InitDB(selectedPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create selected database")
	}
	if err := persistSelectedDatabasePath(selectedPath); err != nil {
		t.Fatalf("persistSelectedDatabasePath: %v", err)
	}

	app := &App{}
	resp := decodeAppResponse(t, app.DeleteDb("[配置]selected"))
	if resp.Code == 200 {
		t.Fatalf("DeleteDb response = %+v, want error", resp)
	}

	if _, err := os.Stat(selectedPath); err != nil {
		t.Fatalf("selected database missing: %v", err)
	}
}

func TestDashboardEndpointsReturnEmptyArraysOnFreshDatabase(t *testing.T) {
	defer closeModelConn(t)

	dbPath := filepath.Join(t.TempDir(), "fresh.db")
	model.InitDB(dbPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create fresh database")
	}

	app := &App{}
	tests := []struct {
		name string
		raw  string
	}{
		{name: "GetTaskList", raw: app.GetTaskList()},
		{name: "GetTeamUser", raw: app.GetTeamUser()},
		{name: "GetGroupWu", raw: app.GetGroupWu()},
	}

	for _, tc := range tests {
		resp := decodeAppResponse(t, tc.raw)
		if resp.Code != 200 {
			t.Fatalf("%s response = %+v", tc.name, resp)
		}
		if string(resp.Data) != "[]" {
			t.Fatalf("%s data = %s, want []", tc.name, string(resp.Data))
		}
	}
}

func closeModelConn(t *testing.T) {
	t.Helper()
	if model.Conn == nil {
		return
	}
	sqlDB, err := model.Conn.DB()
	if err == nil {
		_ = sqlDB.Close()
	}
	model.Conn = nil
}
