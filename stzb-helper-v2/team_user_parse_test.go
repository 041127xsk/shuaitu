package main

import (
	"bytes"
	"compress/zlib"
	"testing"

	"stzbHelper/model"
)

func TestParseZlibDataSupportsBestCompressionHeader(t *testing.T) {
	payload := []byte(`[[1,"玩家",10,0,0,0,123,5,999,0,8,0,0,"一团",0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1710000000]]`)
	var buf bytes.Buffer
	writer, err := zlib.NewWriterLevel(&buf, zlib.BestCompression)
	if err != nil {
		t.Fatalf("create zlib writer: %v", err)
	}
	if _, err := writer.Write(payload); err != nil {
		t.Fatalf("write zlib payload: %v", err)
	}
	if err := writer.Close(); err != nil {
		t.Fatalf("close zlib writer: %v", err)
	}

	got := parseZlibData(buf.Bytes())
	if string(got) != string(payload) {
		t.Fatalf("parseZlibData() = %q, want %q", got, payload)
	}
}

func TestToTeamUserWithErrorHandlesStringNumbersAndDefaultGroup(t *testing.T) {
	row := make([]any, 31)
	row[0] = "1001"
	row[1] = "樱丨月檬远"
	row[2] = "300"
	row[6] = "123456"
	row[7] = "22"
	row[8] = "9000"
	row[10] = "88"
	row[13] = ""
	row[30] = "1710000000"

	user, err := model.ToTeamUserWithError(row)
	if err != nil {
		t.Fatalf("ToTeamUserWithError() error = %v", err)
	}
	if user.Id != 1001 || user.Name != "樱丨月檬远" || user.Group != "未分组" {
		t.Fatalf("unexpected user: %+v", user)
	}
}

func TestToTeamUserWithErrorRejectsShortRows(t *testing.T) {
	if _, err := model.ToTeamUserWithError([]any{1, "玩家"}); err == nil {
		t.Fatal("ToTeamUserWithError() error = nil, want short row error")
	}
}
