package main

import (
	"encoding/json"
	"testing"

	"stzbHelper/global"
)

type captureModeStatus struct {
	Mode      string `json:"mode"`
	Running   bool   `json:"running"`
	ReportPos int    `json:"report_pos"`
	Message   string `json:"message"`
}

func decodeCaptureModeStatus(t *testing.T, raw string) captureModeStatus {
	t.Helper()
	resp := decodeAppResponse(t, raw)
	if resp.Code != 200 {
		t.Fatalf("capture mode response = %+v", resp)
	}

	var status captureModeStatus
	if err := json.Unmarshal(resp.Data, &status); err != nil {
		t.Fatalf("unmarshal capture mode status: %v", err)
	}
	return status
}

func resetCaptureFlags() {
	global.ExVar.NeedGetBattleData = false
	global.ExVar.NeedGetReport = false
	global.ExVar.NeededReportPos = 0
}

func TestCaptureModeDefaultsToNone(t *testing.T) {
	resetCaptureFlags()
	app := &App{}

	status := decodeCaptureModeStatus(t, app.GetCaptureModeStatus())
	if status.Mode != "none" {
		t.Fatalf("status.Mode = %q, want none", status.Mode)
	}
	if status.Running {
		t.Fatal("status.Running = true, want false")
	}
	if status.ReportPos != 0 {
		t.Fatalf("status.ReportPos = %d, want 0", status.ReportPos)
	}
}

func TestEnableGetBattleReportSwitchesToBattleDetailMode(t *testing.T) {
	resetCaptureFlags()
	app := &App{}

	app.EnableGetReport(12345678)
	resp := decodeAppResponse(t, app.EnableGetBattleReport())
	if resp.Code != 200 {
		t.Fatalf("EnableGetBattleReport response = %+v", resp)
	}

	status := decodeCaptureModeStatus(t, app.GetCaptureModeStatus())
	if status.Mode != "battle_detail" {
		t.Fatalf("status.Mode = %q, want battle_detail", status.Mode)
	}
	if !status.Running {
		t.Fatal("status.Running = false, want true")
	}
	if status.ReportPos != 0 {
		t.Fatalf("status.ReportPos = %d, want 0", status.ReportPos)
	}
}

func TestEnableGetReportSwitchesToAttendanceMode(t *testing.T) {
	resetCaptureFlags()
	app := &App{}

	app.EnableGetBattleReport()
	resp := decodeAppResponse(t, app.EnableGetReport(87654321))
	if resp.Code != 200 {
		t.Fatalf("EnableGetReport response = %+v", resp)
	}

	status := decodeCaptureModeStatus(t, app.GetCaptureModeStatus())
	if status.Mode != "attendance_report" {
		t.Fatalf("status.Mode = %q, want attendance_report", status.Mode)
	}
	if !status.Running {
		t.Fatal("status.Running = false, want true")
	}
	if status.ReportPos != 87654321 {
		t.Fatalf("status.ReportPos = %d, want 87654321", status.ReportPos)
	}
}

func TestDisableGetReportStopsCurrentCaptureMode(t *testing.T) {
	resetCaptureFlags()
	app := &App{}

	app.EnableGetReport(11223344)
	resp := decodeAppResponse(t, app.DisableGetReport())
	if resp.Code != 200 {
		t.Fatalf("DisableGetReport response = %+v", resp)
	}

	status := decodeCaptureModeStatus(t, app.GetCaptureModeStatus())
	if status.Mode != "none" {
		t.Fatalf("status.Mode = %q, want none", status.Mode)
	}
	if status.Running {
		t.Fatal("status.Running = true, want false")
	}
	if status.ReportPos != 0 {
		t.Fatalf("status.ReportPos = %d, want 0", status.ReportPos)
	}
}

func TestDisableGetBattleReportAlsoStopsAttendanceMode(t *testing.T) {
	resetCaptureFlags()
	app := &App{}

	app.EnableGetReport(55667788)
	resp := decodeAppResponse(t, app.DisableGetBattleReport())
	if resp.Code != 200 {
		t.Fatalf("DisableGetBattleReport response = %+v", resp)
	}

	status := decodeCaptureModeStatus(t, app.GetCaptureModeStatus())
	if status.Mode != "none" {
		t.Fatalf("status.Mode = %q, want none", status.Mode)
	}
	if status.Running {
		t.Fatal("status.Running = true, want false")
	}
	if status.ReportPos != 0 {
		t.Fatalf("status.ReportPos = %d, want 0", status.ReportPos)
	}
}

func TestCmd92CaptureModeRouting(t *testing.T) {
	tests := []struct {
		name string
		mode string
		want string
	}{
		{name: "none", mode: "none", want: "none"},
		{name: "battle detail", mode: "battle_detail", want: "battle_detail"},
		{name: "attendance", mode: "attendance_report", want: "attendance_report"},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			resetCaptureFlags()
			switch tc.mode {
			case "battle_detail":
				global.ExVar.NeedGetBattleData = true
			case "attendance_report":
				global.ExVar.NeedGetReport = true
				global.ExVar.NeededReportPos = 10010001
			}

			if got := getCmd92CaptureMode(); got != tc.want {
				t.Fatalf("getCmd92CaptureMode() = %q, want %q", got, tc.want)
			}
		})
	}
}
