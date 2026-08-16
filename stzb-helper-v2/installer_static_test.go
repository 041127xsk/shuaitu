package main

import (
	"os"
	"strings"
	"testing"
)

func TestInstallerScriptUsesUserWritableInstallDirAndPreservesData(t *testing.T) {
	contentBytes, err := os.ReadFile("installer/stzbHelper.iss")
	if err != nil {
		t.Fatalf("read installer script: %v", err)
	}
	content := string(contentBytes)

	required := []string{
		`DefaultDirName={localappdata}\Programs\{#MyAppName}`,
		`PrivilegesRequired=lowest`,
		`data\default.db`,
		`onlyifdoesntexist`,
		`platform-tools\adb.exe`,
		`MicrosoftEdgeWebView2Setup.exe`,
		`npcap-installer.exe`,
		`使用说明.md`,
		`Name: "{group}\使用说明"`,
	}
	for _, needle := range required {
		if !strings.Contains(content, needle) {
			t.Fatalf("installer script missing %q", needle)
		}
	}

	forbidden := []string{
		`C:\Users\27557`,
		`E:\openclaw`,
		`DefaultDirName={autopf}`,
		`PrivilegesRequired=admin`,
	}
	for _, needle := range forbidden {
		if strings.Contains(content, needle) {
			t.Fatalf("installer script contains forbidden machine-specific or unwritable setting %q", needle)
		}
	}
}
