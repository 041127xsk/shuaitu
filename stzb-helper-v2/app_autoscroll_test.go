package main

import (
	"errors"
	"strings"
	"stzbHelper/global"
	"stzbHelper/model"
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
	autoScrollInsertedCount = 3
	autoScrollDuplicateCount = 5
	autoScrollLastBattleId = 9988
	model.CurrentDatabasePath = `E:\openclaw\openclaw-main\stzb-helper-v2\demo.db`

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
	if status.InsertedCount != 3 {
		t.Fatalf("InsertedCount = %d, want 3", status.InsertedCount)
	}
	if status.DuplicateCount != 5 {
		t.Fatalf("DuplicateCount = %d, want 5", status.DuplicateCount)
	}
	if status.LastBattleID != 9988 {
		t.Fatalf("LastBattleID = %d, want 9988", status.LastBattleID)
	}
	if status.ActiveDatabasePath != model.CurrentDatabasePath {
		t.Fatalf("ActiveDatabasePath = %q, want %q", status.ActiveDatabasePath, model.CurrentDatabasePath)
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
	autoScrollInsertedCount = 0
	autoScrollDuplicateCount = 0

	markAutoScrollInserted(1001)
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
	if autoScrollInsertedCount != 1 {
		t.Fatalf("autoScrollInsertedCount = %d, want 1", autoScrollInsertedCount)
	}
	if autoScrollDuplicateCount != 1 {
		t.Fatalf("autoScrollDuplicateCount = %d, want 1", autoScrollDuplicateCount)
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
	if autoScrollDuplicateCount != 2 {
		t.Fatalf("autoScrollDuplicateCount = %d, want 2", autoScrollDuplicateCount)
	}
}
