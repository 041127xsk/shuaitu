package main

import (
	"bytes"
	"encoding/json"
	"log"
	"strings"
	"testing"
)

func TestParseBattleDataLogsProgressEveryThirtyReports(t *testing.T) {
	oldQueue := writeQueue
	writeQueue = make(chan writeRequest, 64)
	defer func() { writeQueue = oldQueue }()

	var logBuf bytes.Buffer
	oldLogWriter := log.Writer()
	log.SetOutput(&logBuf)
	defer log.SetOutput(oldLogWriter)

	parseBattleData(buildBattleDataPayloadForLogTest(30))

	logs := logBuf.String()
	if !strings.Contains(logs, "详细战报采集中：已处理30条，最后battle_id=1030") {
		t.Fatalf("logs = %q, want 30-report progress log", logs)
	}
	if !strings.Contains(logs, "详细战报解析完成：收到30条，有效30条，跳过0条") {
		t.Fatalf("logs = %q, want completion summary", logs)
	}
	if strings.Contains(logs, "处理战斗ID") || strings.Contains(logs, "保存战斗报告") {
		t.Fatalf("logs = %q, should not contain per-report battle logs", logs)
	}
}

func TestParseBattleDataDoesNotLogProgressBeforeThirtyReports(t *testing.T) {
	oldQueue := writeQueue
	writeQueue = make(chan writeRequest, 64)
	defer func() { writeQueue = oldQueue }()

	var logBuf bytes.Buffer
	oldLogWriter := log.Writer()
	log.SetOutput(&logBuf)
	defer log.SetOutput(oldLogWriter)

	parseBattleData(buildBattleDataPayloadForLogTest(29))

	logs := logBuf.String()
	if strings.Contains(logs, "详细战报采集中") {
		t.Fatalf("logs = %q, should not contain progress log before 30 reports", logs)
	}
	if !strings.Contains(logs, "详细战报解析完成：收到29条，有效29条，跳过0条") {
		t.Fatalf("logs = %q, want completion summary", logs)
	}
}

func buildBattleDataPayloadForLogTest(count int) []byte {
	rows := make([]any, 0, count)
	for i := 1; i <= count; i++ {
		rows = append(rows, []any{map[string]any{
			"battle_id":                1000 + i,
			"attack_help_id":           "help",
			"time":                     1710000000 + i,
			"wid":                      "100200",
			"wid_name":                 "测试地块",
			"attack_name":              "进攻方",
			"attack_union_name":        "测试盟",
			"defend_name":              "防守方",
			"defend_union_name":        "测试盟",
			"attack_advance":           "0;1;2;3",
			"defend_advance":           "1;2;3",
			"attack_all_hero_info":     "101,45;102,45;103,45",
			"defend_all_hero_info":     "201,45;202,45;203,45",
			"attack_hp":                25000,
			"defend_hp":                23000,
			"npc":                      0,
			"all_skill_info":           "1,10,10,11,10,12,10;2,20,10,21,10,22,10;3,30,10,31,10,32,10",
			"result":                   1,
			"attack_idu":               "A",
			"defend_idu":               "D",
			"attacker_gear_info":       "301,10,0;302,10,0;303,10,0",
			"defender_gear_info":       "401,10,0;402,10,0;403,10,0",
			"attack_hero_type":         "1;2;3",
			"defend_hero_type":         "4;5;6",
			"attack_hero_type_advance": "",
			"defend_hero_type_advance": "",
		}})
	}
	payload, _ := json.Marshal(rows)
	return payload
}
