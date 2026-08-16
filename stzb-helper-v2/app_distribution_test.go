package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLoadAppConfigStructUsesPortableDefaultsWhenConfigMissing(t *testing.T) {
	exePath := withTempExecutableDir(t)
	appDir := filepath.Dir(exePath)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()

	got := loadAppConfigStruct()

	wantADB := filepath.Join(appDir, "platform-tools", "adb.exe")
	wantDB := filepath.Join(appDir, "data", "default.db")
	if got.AdbPath != wantADB {
		t.Fatalf("AdbPath = %q, want portable bundled adb %q", got.AdbPath, wantADB)
	}
	if got.DatabasePath != wantDB {
		t.Fatalf("DatabasePath = %q, want portable bundled database %q", got.DatabasePath, wantDB)
	}
	if strings.Contains(got.AdbPath, `.local\bin`) || strings.Contains(strings.ToLower(got.DatabasePath), "openclaw") {
		t.Fatalf("portable defaults leaked developer paths: %+v", got)
	}
	if len(got.AdbProfiles) != 1 || got.AdbProfiles[0].AdbPath != wantADB {
		t.Fatalf("AdbProfiles = %+v, want one bundled adb default profile", got.AdbProfiles)
	}
}

func TestLoadAppConfigStructBackfillsPortablePathsForEmptyInstalledConfig(t *testing.T) {
	exePath := withTempExecutableDir(t)
	appDir := filepath.Dir(exePath)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()

	data, err := json.Marshal(AppConfig{
		ScrollCount:     4000,
		ScrollDelay:     100,
		ScrollDuration:  100,
		StopOnDuplicate: false,
	})
	if err != nil {
		t.Fatalf("marshal config: %v", err)
	}
	if err := os.WriteFile(filepath.Join(appDir, "config.json"), data, 0644); err != nil {
		t.Fatalf("write config: %v", err)
	}

	got := loadAppConfigStruct()

	if got.AdbPath != filepath.Join(appDir, "platform-tools", "adb.exe") {
		t.Fatalf("AdbPath = %q, want installed bundled adb", got.AdbPath)
	}
	if got.DatabasePath != filepath.Join(appDir, "data", "default.db") {
		t.Fatalf("DatabasePath = %q, want installed bundled database", got.DatabasePath)
	}
	if got.AdbSerial != DefaultAdbSerial {
		t.Fatalf("AdbSerial = %q, want %q", got.AdbSerial, DefaultAdbSerial)
	}
}
