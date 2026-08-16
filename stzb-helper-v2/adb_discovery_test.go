package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestDiscoverAdbPathsIncludesPortableAndConfiguredPaths(t *testing.T) {
	exePath := withTempExecutableDir(t)
	appDir := filepath.Dir(exePath)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()

	portableAdb := filepath.Join(appDir, "platform-tools", "adb.exe")
	if err := os.MkdirAll(filepath.Dir(portableAdb), 0755); err != nil {
		t.Fatalf("mkdir portable adb dir: %v", err)
	}
	if err := os.WriteFile(portableAdb, []byte("adb"), 0644); err != nil {
		t.Fatalf("write portable adb: %v", err)
	}

	configuredAdb := filepath.Join(appDir, "custom", "adb.exe")
	if err := os.MkdirAll(filepath.Dir(configuredAdb), 0755); err != nil {
		t.Fatalf("mkdir configured adb dir: %v", err)
	}
	if err := os.WriteFile(configuredAdb, []byte("adb"), 0644); err != nil {
		t.Fatalf("write configured adb: %v", err)
	}

	config := AppConfig{
		AdbPath:            configuredAdb,
		AdbSerial:          DefaultAdbSerial,
		ScrollCount:        defaultConfig.ScrollCount,
		ScrollDelay:        defaultConfig.ScrollDelay,
		ScrollDuration:     defaultConfig.ScrollDuration,
		DatabasePath:       filepath.Join(appDir, "data", "default.db"),
		ActiveAdbProfileID: "custom",
		AdbProfiles: []AdbProfile{
			{ID: "custom", Name: "本机ADB", AdbPath: configuredAdb, AdbSerial: DefaultAdbSerial},
		},
	}
	if err := saveAppConfigStruct(config); err != nil {
		t.Fatalf("save config: %v", err)
	}

	paths := discoverAdbPaths()

	if !containsDiscoveredAdbPath(paths, portableAdb) {
		t.Fatalf("discoverAdbPaths() = %+v, want portable adb %q", paths, portableAdb)
	}
	if !containsDiscoveredAdbPath(paths, configuredAdb) {
		t.Fatalf("discoverAdbPaths() = %+v, want configured adb %q", paths, configuredAdb)
	}
}

func TestDiscoverAdbPathsResponseReturnsCandidates(t *testing.T) {
	exePath := withTempExecutableDir(t)
	appDir := filepath.Dir(exePath)
	originalExecutablePathFunc := executablePathFunc
	executablePathFunc = func() (string, error) { return exePath, nil }
	defer func() { executablePathFunc = originalExecutablePathFunc }()

	adbPath := filepath.Join(appDir, "platform-tools", "adb.exe")
	if err := os.MkdirAll(filepath.Dir(adbPath), 0755); err != nil {
		t.Fatalf("mkdir adb dir: %v", err)
	}
	if err := os.WriteFile(adbPath, []byte("adb"), 0644); err != nil {
		t.Fatalf("write adb: %v", err)
	}

	resp := decodeAppResponse(t, (&App{}).DiscoverAdbPaths())
	if resp.Code != 200 {
		t.Fatalf("DiscoverAdbPaths response = %+v", resp)
	}

	var paths []DiscoveredAdbPath
	if err := json.Unmarshal(resp.Data, &paths); err != nil {
		t.Fatalf("unmarshal discovered adb paths: %v", err)
	}
	if !containsDiscoveredAdbPath(paths, adbPath) {
		t.Fatalf("DiscoverAdbPaths() = %+v, want %q", paths, adbPath)
	}
}

func containsDiscoveredAdbPath(paths []DiscoveredAdbPath, want string) bool {
	want = normalizePathForCompare(want)
	for _, item := range paths {
		if normalizePathForCompare(item.Path) == want {
			return true
		}
	}
	return false
}
