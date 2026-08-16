package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestLoadAppConfigStructUsesSavedAdbSettings(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()

	saved := AppConfig{
		AdbPath:         `D:\tools\adb.exe`,
		AdbSerial:       "127.0.0.1:5555",
		ScrollCount:     123,
		ScrollDelay:     456,
		ScrollDuration:  789,
		StopOnDuplicate: true,
		DatabasePath:    filepath.Join(filepath.Dir(exePath), "saved.db"),
	}
	if err := saveAppConfigStruct(saved); err != nil {
		t.Fatalf("saveAppConfigStruct: %v", err)
	}

	got := loadAppConfigStruct()
	if got.AdbPath != saved.AdbPath {
		t.Fatalf("AdbPath = %q, want %q", got.AdbPath, saved.AdbPath)
	}
	if got.AdbSerial != saved.AdbSerial {
		t.Fatalf("AdbSerial = %q, want %q", got.AdbSerial, saved.AdbSerial)
	}
	if got.ScrollCount != saved.ScrollCount {
		t.Fatalf("ScrollCount = %d, want %d", got.ScrollCount, saved.ScrollCount)
	}
	if got.ScrollDelay != saved.ScrollDelay {
		t.Fatalf("ScrollDelay = %d, want %d", got.ScrollDelay, saved.ScrollDelay)
	}
	if got.ScrollDuration != saved.ScrollDuration {
		t.Fatalf("ScrollDuration = %d, want %d", got.ScrollDuration, saved.ScrollDuration)
	}
	if got.StopOnDuplicate != saved.StopOnDuplicate {
		t.Fatalf("StopOnDuplicate = %v, want %v", got.StopOnDuplicate, saved.StopOnDuplicate)
	}
}

func TestLoadConfigReturnsSavedAdbSettings(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()

	saved := AppConfig{
		AdbPath:         `D:\portable\adb.exe`,
		AdbSerial:       "emulator-5554",
		ScrollCount:     321,
		ScrollDelay:     111,
		ScrollDuration:  222,
		StopOnDuplicate: false,
		DatabasePath:    filepath.Join(filepath.Dir(exePath), "saved.db"),
	}
	if err := saveAppConfigStruct(saved); err != nil {
		t.Fatalf("saveAppConfigStruct: %v", err)
	}

	resp := decodeAppResponse(t, (&App{}).LoadConfig())
	if resp.Code != 200 {
		t.Fatalf("LoadConfig response = %+v", resp)
	}

	var got AppConfig
	if err := json.Unmarshal(resp.Data, &got); err != nil {
		t.Fatalf("unmarshal config response: %v", err)
	}
	if got.AdbPath != saved.AdbPath {
		t.Fatalf("AdbPath = %q, want %q", got.AdbPath, saved.AdbPath)
	}
	if got.AdbSerial != saved.AdbSerial {
		t.Fatalf("AdbSerial = %q, want %q", got.AdbSerial, saved.AdbSerial)
	}
}

func TestGetAdbHelpersPreferSavedConfigOverDefaults(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()

	saved := AppConfig{
		AdbPath:         `E:\android\adb.exe`,
		AdbSerial:       "127.0.0.1:62001",
		ScrollCount:     defaultConfig.ScrollCount,
		ScrollDelay:     defaultConfig.ScrollDelay,
		ScrollDuration:  defaultConfig.ScrollDuration,
		StopOnDuplicate: defaultConfig.StopOnDuplicate,
		DatabasePath:    defaultConfig.DatabasePath,
	}
	if err := saveAppConfigStruct(saved); err != nil {
		t.Fatalf("saveAppConfigStruct: %v", err)
	}

	if got := getAdbPath(nil); got != saved.AdbPath {
		t.Fatalf("getAdbPath(nil) = %q, want %q", got, saved.AdbPath)
	}
	if got := getAdbPath(""); got != saved.AdbPath {
		t.Fatalf("getAdbPath(\"\") = %q, want %q", got, saved.AdbPath)
	}
	if got := getAdbSerial(nil); got != saved.AdbSerial {
		t.Fatalf("getAdbSerial(nil) = %q, want %q", got, saved.AdbSerial)
	}
	if got := getAdbSerial(""); got != saved.AdbSerial {
		t.Fatalf("getAdbSerial(\"\") = %q, want %q", got, saved.AdbSerial)
	}
}

func TestLoadConfigMigratesLegacyAdbConfigToProfiles(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()

	legacy := map[string]any{
		"adb_path":          `D:\legacy\adb.exe`,
		"adb_serial":        "127.0.0.1:16384",
		"scroll_count":      321,
		"scroll_delay":      111,
		"scroll_duration":   222,
		"stop_on_duplicate": true,
		"database_path":     filepath.Join(filepath.Dir(exePath), "legacy.db"),
	}
	data, err := json.Marshal(legacy)
	if err != nil {
		t.Fatalf("marshal legacy config: %v", err)
	}
	if err := os.WriteFile(filepath.Join(filepath.Dir(exePath), "config.json"), data, 0644); err != nil {
		t.Fatalf("write legacy config: %v", err)
	}

	resp := decodeAppResponse(t, (&App{}).LoadConfig())
	if resp.Code != 200 {
		t.Fatalf("LoadConfig response = %+v", resp)
	}

	var got AppConfig
	if err := json.Unmarshal(resp.Data, &got); err != nil {
		t.Fatalf("unmarshal config response: %v", err)
	}
	if len(got.AdbProfiles) != 1 {
		t.Fatalf("len(got.AdbProfiles) = %d, want 1", len(got.AdbProfiles))
	}
	if got.ActiveAdbProfileID == "" {
		t.Fatal("ActiveAdbProfileID = empty, want migrated profile id")
	}
	if got.AdbProfiles[0].AdbPath != legacy["adb_path"] {
		t.Fatalf("AdbProfiles[0].AdbPath = %q, want %q", got.AdbProfiles[0].AdbPath, legacy["adb_path"])
	}
	if got.AdbProfiles[0].AdbSerial != legacy["adb_serial"] {
		t.Fatalf("AdbProfiles[0].AdbSerial = %q, want %q", got.AdbProfiles[0].AdbSerial, legacy["adb_serial"])
	}
}

func TestSetActiveAdbProfilePersistsActiveProfileAndMirrorFields(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()

	config := AppConfig{
		AdbPath:            `D:\adb\one.exe`,
		AdbSerial:          "127.0.0.1:16384",
		ScrollCount:        defaultConfig.ScrollCount,
		ScrollDelay:        defaultConfig.ScrollDelay,
		ScrollDuration:     defaultConfig.ScrollDuration,
		StopOnDuplicate:    defaultConfig.StopOnDuplicate,
		DatabasePath:       filepath.Join(filepath.Dir(exePath), "saved.db"),
		ActiveAdbProfileID: "one",
		AdbProfiles: []AdbProfile{
			{ID: "one", Name: "MuMu-1", AdbPath: `D:\adb\one.exe`, AdbSerial: "127.0.0.1:16384"},
			{ID: "two", Name: "MuMu-2", AdbPath: `D:\adb\two.exe`, AdbSerial: "127.0.0.1:16416"},
		},
	}
	if err := saveAppConfigStruct(config); err != nil {
		t.Fatalf("saveAppConfigStruct: %v", err)
	}

	resp := decodeAppResponse(t, (&App{}).SetActiveAdbProfile("two"))
	if resp.Code != 200 {
		t.Fatalf("SetActiveAdbProfile response = %+v", resp)
	}

	got := loadAppConfigStruct()
	if got.ActiveAdbProfileID != "two" {
		t.Fatalf("ActiveAdbProfileID = %q, want two", got.ActiveAdbProfileID)
	}
	if got.AdbPath != `D:\adb\two.exe` {
		t.Fatalf("AdbPath = %q, want D:\\adb\\two.exe", got.AdbPath)
	}
	if got.AdbSerial != "127.0.0.1:16416" {
		t.Fatalf("AdbSerial = %q, want 127.0.0.1:16416", got.AdbSerial)
	}
}

func TestScanAdbDevicesReturnsParsedDeviceList(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()

	adbPath := filepath.Join(filepath.Dir(exePath), "adb.exe")
	if err := os.WriteFile(adbPath, []byte("stub"), 0644); err != nil {
		t.Fatalf("write adb stub: %v", err)
	}

	originalRunner := commandRunner
	commandRunner = func(name string, arg ...string) (string, error) {
		if len(arg) == 1 && arg[0] == "devices" {
			return "List of devices attached\r\n127.0.0.1:16384\tdevice\r\n127.0.0.1:16416\toffline\r\nemulator-5554\tdevice\r\n\r\n", nil
		}
		return "", nil
	}
	defer func() { commandRunner = originalRunner }()

	config := AppConfig{
		AdbPath:            adbPath,
		AdbSerial:          "127.0.0.1:16384",
		ScrollCount:        defaultConfig.ScrollCount,
		ScrollDelay:        defaultConfig.ScrollDelay,
		ScrollDuration:     defaultConfig.ScrollDuration,
		StopOnDuplicate:    defaultConfig.StopOnDuplicate,
		DatabasePath:       filepath.Join(filepath.Dir(exePath), "saved.db"),
		ActiveAdbProfileID: "one",
		AdbProfiles: []AdbProfile{
			{ID: "one", Name: "MuMu-1", AdbPath: adbPath, AdbSerial: "127.0.0.1:16384"},
		},
	}
	if err := saveAppConfigStruct(config); err != nil {
		t.Fatalf("saveAppConfigStruct: %v", err)
	}

	resp := decodeAppResponse(t, (&App{}).ScanAdbDevices())
	if resp.Code != 200 {
		t.Fatalf("ScanAdbDevices response = %+v", resp)
	}

	var devices []ScannedAdbDevice
	if err := json.Unmarshal(resp.Data, &devices); err != nil {
		t.Fatalf("unmarshal devices: %v", err)
	}
	if len(devices) != 3 {
		t.Fatalf("len(devices) = %d, want 3", len(devices))
	}
	if devices[0].Serial != "127.0.0.1:16384" || devices[0].Status != "device" {
		t.Fatalf("devices[0] = %+v, want serial/status parsed", devices[0])
	}
}

func TestLoadConfigUsesDefaultAttendanceRuleWhenConfigMissingFields(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()

	legacy := AppConfig{
		AdbPath:         `D:\portable\adb.exe`,
		AdbSerial:       "127.0.0.1:16384",
		ScrollCount:     400,
		ScrollDelay:     100,
		ScrollDuration:  100,
		StopOnDuplicate: false,
		DatabasePath:    filepath.Join(filepath.Dir(exePath), "legacy.db"),
	}
	if err := saveAppConfigStruct(legacy); err != nil {
		t.Fatalf("saveAppConfigStruct: %v", err)
	}

	resp := decodeAppResponse(t, (&App{}).LoadConfig())
	if resp.Code != 200 {
		t.Fatalf("LoadConfig response = %+v", resp)
	}

	var got AppConfig
	if err := json.Unmarshal(resp.Data, &got); err != nil {
		t.Fatalf("unmarshal config response: %v", err)
	}
	if got.DefaultDisMaxLevel != 19 {
		t.Fatalf("DefaultDisMaxLevel = %d, want 19", got.DefaultDisMaxLevel)
	}
	if got.DefaultAtkMinLevel != 25 {
		t.Fatalf("DefaultAtkMinLevel = %d, want 25", got.DefaultAtkMinLevel)
	}
}

func TestSaveConfigPersistsAttendanceDefaults(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()

	app := &App{}
	payload := AppConfig{
		AdbPath:            `D:\portable\adb.exe`,
		AdbSerial:          "127.0.0.1:16384",
		ScrollCount:        500,
		ScrollDelay:        200,
		ScrollDuration:     150,
		StopOnDuplicate:    true,
		DatabasePath:       filepath.Join(filepath.Dir(exePath), "saved.db"),
		DefaultDisMaxLevel: 18,
		DefaultAtkMinLevel: 30,
	}
	data, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal payload: %v", err)
	}

	resp := decodeAppResponse(t, app.SaveConfig(string(data)))
	if resp.Code != 200 {
		t.Fatalf("SaveConfig response = %+v", resp)
	}

	got := loadAppConfigStruct()
	if got.DefaultDisMaxLevel != 18 {
		t.Fatalf("DefaultDisMaxLevel = %d, want 18", got.DefaultDisMaxLevel)
	}
	if got.DefaultAtkMinLevel != 30 {
		t.Fatalf("DefaultAtkMinLevel = %d, want 30", got.DefaultAtkMinLevel)
	}
}

func TestSaveConfigRejectsInvalidAttendanceDefaults(t *testing.T) {
	exePath := withTempExecutableDir(t)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()

	app := &App{}
	payload := AppConfig{
		AdbPath:            `D:\portable\adb.exe`,
		AdbSerial:          "127.0.0.1:16384",
		ScrollCount:        500,
		ScrollDelay:        200,
		ScrollDuration:     150,
		StopOnDuplicate:    true,
		DatabasePath:       filepath.Join(filepath.Dir(exePath), "saved.db"),
		DefaultDisMaxLevel: 25,
		DefaultAtkMinLevel: 25,
	}
	data, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal payload: %v", err)
	}

	resp := decodeAppResponse(t, app.SaveConfig(string(data)))
	if resp.Code == 200 {
		t.Fatalf("SaveConfig response = %+v, want error", resp)
	}
}
