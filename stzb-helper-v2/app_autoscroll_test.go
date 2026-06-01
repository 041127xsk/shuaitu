package main

import (
	"errors"
	"strings"
	"stzbHelper/global"
	"testing"
)

type failingWriter struct{}

func (failingWriter) Write([]byte) (int, error) {
	return 0, errors.New("stdout unavailable")
}

func TestNewAutoScrollStatusIncludesStopReason(t *testing.T) {
	autoScrollRunning = false
	autoScrollCurrent = 42
	autoScrollTotal = 8000
	autoScrollDuplicateFound = true
	autoScrollStopOnDuplicate = true
	autoScrollStopReason = "检测到重复战报，停止翻页"

	status := newAutoScrollStatus(1080, 1920)

	if status.StopReason != autoScrollStopReason {
		t.Fatalf("StopReason = %q, want %q", status.StopReason, autoScrollStopReason)
	}
	if !status.DuplicateFound {
		t.Fatal("DuplicateFound = false, want true")
	}
	if !status.StopOnDuplicate {
		t.Fatal("StopOnDuplicate = false, want true")
	}
}

func TestAppLogOutputWritesFrontendLogWhenStdoutFails(t *testing.T) {
	global.LogW.Clear()

	_, _ = appLogOutput(failingWriter{}).Write([]byte("adb log visible\n"))

	entries := global.LogW.GetLogs()
	if len(entries) == 0 {
		t.Fatal("frontend log entries are empty")
	}
	if !strings.Contains(entries[len(entries)-1], "adb log visible") {
		t.Fatalf("last frontend log = %q, want adb log visible", entries[len(entries)-1])
	}
}

func TestDuplicateBattleReportOnlyStopsWhenEnabled(t *testing.T) {
	autoScrollDuplicateFound = false
	autoScrollStopOnDuplicate = false
	autoScrollStopReason = ""
	autoScrollLastBattleId = 0

	recordAutoScrollBattleID(1001)
	markAutoScrollDuplicate(1002)

	if autoScrollLastBattleId != 1002 {
		t.Fatalf("autoScrollLastBattleId = %d, want 1002", autoScrollLastBattleId)
	}
	if shouldStopOnDuplicate() {
		t.Fatal("duplicate report stopped scrolling while stop-on-duplicate is disabled")
	}
	if !strings.Contains(autoScrollStopReason, "继续翻页") {
		t.Fatalf("autoScrollStopReason = %q, want continue message", autoScrollStopReason)
	}

	autoScrollDuplicateFound = false
	autoScrollStopOnDuplicate = true
	autoScrollStopReason = ""
	markAutoScrollDuplicate(1003)

	if !shouldStopOnDuplicate() {
		t.Fatal("duplicate report did not stop scrolling while stop-on-duplicate is enabled")
	}
	if !strings.Contains(autoScrollStopReason, "自动翻页已停止") {
		t.Fatalf("autoScrollStopReason = %q, want stop message", autoScrollStopReason)
	}
}
