package main

import (
	"os"
	"path/filepath"
	"stzbHelper/model"
	"testing"
	"time"
)

func TestBuildMaterializedPlayerTeamSnapshotsKeepsLatestEffectiveTeams(t *testing.T) {
	reports := []model.BattleReport{
		{
			BattleId: 100, Time: 1000, Npc: 0,
			AttackName: "甲", AttackUnionName: "盟", AttackIdu: "A1",
			AttackHero1Id: 1, AttackHero2Id: 2, AttackHero3Id: 3,
			AttackHero1Level: 45, AttackHero2Level: 45, AttackHero3Level: 45,
			AttackHero1Star: 1, AttackHero2Star: 2, AttackHero3Star: 3, AttackTotalStar: 6,
			AttackHp: 25000, AllSkillInfo: "1,10,10,11,10,12,10;2,20,10,21,10,22,10;3,30,10,31,10,32,10",
		},
		{
			BattleId: 90, Time: 900, Npc: 0,
			AttackName: "甲", AttackUnionName: "盟", AttackIdu: "A2",
			AttackHero1Id: 1, AttackHero2Id: 2, AttackHero3Id: 4,
			AttackHero1Level: 40, AttackHero2Level: 40, AttackHero3Level: 40,
			AttackHp: 23000, AllSkillInfo: "1,10,10,11,10,12,10;2,20,10,21,10,22,10;3,40,10,41,10,42,10",
		},
		{
			BattleId: 80, Time: 800, Npc: 0,
			DefendName: "甲", DefendUnionName: "盟", DefendIdu: "D1",
			DefendHero1Id: 5, DefendHero2Id: 6, DefendHero3Id: 7,
			DefendHero1Level: 41, DefendHero2Level: 42, DefendHero3Level: 43,
			DefendHero1Star: 2, DefendHero2Star: 2, DefendHero3Star: 2, DefendTotalStar: 6,
			DefendHp: 24000, AllSkillInfo: "4,50,10,51,10,52,10;5,60,10,61,10,62,10;6,70,10,71,10,72,10",
		},
	}

	snapshots := buildMaterializedPlayerTeamSnapshots(reports)

	if len(snapshots) != 2 {
		t.Fatalf("len(snapshots) = %d, want 2", len(snapshots))
	}
	for _, snapshot := range snapshots {
		if snapshot.PlayerName == "甲" && snapshot.LastBattleID == 90 {
			t.Fatal("older same-player team sharing two heroes was kept")
		}
	}
}

func TestBuildMaterializedWinRateStatsUsesRawResultRules(t *testing.T) {
	reports := []model.BattleReport{
		{
			BattleId: 1, Time: 100, Npc: 0, Result: 1,
			AttackName: "甲", AttackIdu: "A",
			AttackHero1Id: 1, AttackHero2Id: 2, AttackHero3Id: 3,
			AttackHero1Level: 30, AttackHero2Level: 30, AttackHero3Level: 30,
			AttackHp:   20000,
			DefendName: "乙", DefendIdu: "D",
			DefendHero1Id: 4, DefendHero2Id: 5, DefendHero3Id: 6,
			DefendHero1Level: 30, DefendHero2Level: 30, DefendHero3Level: 30,
			DefendHp:     20000,
			AllSkillInfo: "1,10,10,11,10,12,10;2,20,10,21,10,22,10;3,30,10,31,10,32,10;4,40,10,41,10,42,10;5,50,10,51,10,52,10;6,60,10,61,10,62,10",
		},
		{
			BattleId: 2, Time: 200, Npc: 0, Result: 0,
			AttackName: "甲", AttackIdu: "A",
			AttackHero1Id: 1, AttackHero2Id: 2, AttackHero3Id: 3,
			AttackHero1Level: 31, AttackHero2Level: 31, AttackHero3Level: 31,
			AttackHp:   21000,
			DefendName: "乙", DefendIdu: "D",
			DefendHero1Id: 4, DefendHero2Id: 5, DefendHero3Id: 6,
			DefendHero1Level: 31, DefendHero2Level: 31, DefendHero3Level: 31,
			DefendHp:     21000,
			AllSkillInfo: "1,10,10,11,10,12,10;2,20,10,21,10,22,10;3,30,10,31,10,32,10;4,40,10,41,10,42,10;5,50,10,51,10,52,10;6,60,10,61,10,62,10",
		},
		{
			BattleId: 3, Time: 300, Npc: 0, Result: 6,
			AttackName: "甲", AttackIdu: "A",
			AttackHero1Id: 1, AttackHero2Id: 2, AttackHero3Id: 3,
			AttackHero1Level: 32, AttackHero2Level: 32, AttackHero3Level: 32,
			AttackHp:   22000,
			DefendName: "乙", DefendIdu: "D",
			DefendHero1Id: 4, DefendHero2Id: 5, DefendHero3Id: 6,
			DefendHero1Level: 32, DefendHero2Level: 32, DefendHero3Level: 32,
			DefendHp:     22000,
			AllSkillInfo: "1,10,10,11,10,12,10;2,20,10,21,10,22,10;3,30,10,31,10,32,10;4,40,10,41,10,42,10;5,50,10,51,10,52,10;6,60,10,61,10,62,10",
		},
	}

	stats := buildMaterializedWinRateStats(reports, "player")

	attack := findWinRateStat(stats, "甲", "attack")
	if attack == nil {
		t.Fatal("attack stat for 甲 not found")
	}
	if attack.TotalBattles != 3 || attack.WinCount != 1 || attack.LossCount != 1 || attack.DrawCount != 1 {
		t.Fatalf("attack stat = %+v, want 1 win, 1 loss, 1 draw over 3 battles", *attack)
	}
	if attack.WinRate != 33.3 {
		t.Fatalf("attack WinRate = %.1f, want 33.3", attack.WinRate)
	}

	defend := findWinRateStat(stats, "乙", "defend")
	if defend == nil {
		t.Fatal("defend stat for 乙 not found")
	}
	if defend.TotalBattles != 3 || defend.WinCount != 1 || defend.LossCount != 1 || defend.DrawCount != 1 {
		t.Fatalf("defend stat = %+v, want 1 win, 1 loss, 1 draw over 3 battles", *defend)
	}
}

func TestMaterializedStatsAccumulatorMatchesFullBuildersAcrossBatches(t *testing.T) {
	reports := []model.BattleReport{
		{
			BattleId: 1, Time: 100, Npc: 0, Result: 1,
			AttackName: "甲", AttackIdu: "A",
			AttackHero1Id: 1, AttackHero2Id: 2, AttackHero3Id: 3,
			AttackHero1Level: 30, AttackHero2Level: 30, AttackHero3Level: 30,
			AttackHp:   20000,
			DefendName: "乙", DefendIdu: "D",
			DefendHero1Id: 4, DefendHero2Id: 5, DefendHero3Id: 6,
			DefendHero1Level: 30, DefendHero2Level: 30, DefendHero3Level: 30,
			DefendHp:     20000,
			AllSkillInfo: "1,10,10,11,10,12,10;2,20,10,21,10,22,10;3,30,10,31,10,32,10;4,40,10,41,10,42,10;5,50,10,51,10,52,10;6,60,10,61,10,62,10",
		},
		{
			BattleId: 2, Time: 200, Npc: 0, Result: 0,
			AttackName: "甲", AttackIdu: "A",
			AttackHero1Id: 1, AttackHero2Id: 2, AttackHero3Id: 3,
			AttackHero1Level: 31, AttackHero2Level: 31, AttackHero3Level: 31,
			AttackHp:   21000,
			DefendName: "乙", DefendIdu: "D",
			DefendHero1Id: 4, DefendHero2Id: 5, DefendHero3Id: 6,
			DefendHero1Level: 31, DefendHero2Level: 31, DefendHero3Level: 31,
			DefendHp:     21000,
			AllSkillInfo: "1,10,10,11,10,12,10;2,20,10,21,10,22,10;3,30,10,31,10,32,10;4,40,10,41,10,42,10;5,50,10,51,10,52,10;6,60,10,61,10,62,10",
		},
		{
			BattleId: 3, Time: 300, Npc: 0, Result: 6,
			AttackName: "丙", AttackIdu: "C",
			AttackHero1Id: 7, AttackHero2Id: 8, AttackHero3Id: 9,
			AttackHero1Level: 32, AttackHero2Level: 32, AttackHero3Level: 32,
			AttackHp:   22000,
			DefendName: "丁", DefendIdu: "E",
			DefendHero1Id: 10, DefendHero2Id: 11, DefendHero3Id: 12,
			DefendHero1Level: 32, DefendHero2Level: 32, DefendHero3Level: 32,
			DefendHp:     22000,
			AllSkillInfo: "1,70,10,71,10,72,10;2,80,10,81,10,82,10;3,90,10,91,10,92,10;4,100,10,101,10,102,10;5,110,10,111,10,112,10;6,120,10,121,10,122,10",
		},
	}

	acc := newMaterializedStatsAccumulator()
	for _, report := range reports[:1] {
		acc.Add(report)
	}
	for _, report := range reports[1:] {
		acc.Add(report)
	}

	if acc.ProcessedReportCount() != int64(len(reports)) {
		t.Fatalf("ProcessedReportCount = %d, want %d", acc.ProcessedReportCount(), len(reports))
	}
	if acc.LastBattleID() != 3 {
		t.Fatalf("LastBattleID = %d, want 3", acc.LastBattleID())
	}
	if len(acc.BuildSnapshots()) != len(buildMaterializedPlayerTeamSnapshots(reports)) {
		t.Fatalf("incremental snapshot count = %d, want %d", len(acc.BuildSnapshots()), len(buildMaterializedPlayerTeamSnapshots(reports)))
	}
	if len(acc.BuildWinRateStats("player")) != len(buildMaterializedWinRateStats(reports, "player")) {
		t.Fatalf("incremental player stat count = %d, want %d", len(acc.BuildWinRateStats("player")), len(buildMaterializedWinRateStats(reports, "player")))
	}
	if len(acc.BuildWinRateStats("team")) != len(buildMaterializedWinRateStats(reports, "team")) {
		t.Fatalf("incremental team stat count = %d, want %d", len(acc.BuildWinRateStats("team")), len(buildMaterializedWinRateStats(reports, "team")))
	}
}

func findWinRateStat(stats []model.TeamWinRateStat, playerName string, role string) *model.TeamWinRateStat {
	for i := range stats {
		if stats[i].PlayerName == playerName && stats[i].Role == role {
			return &stats[i]
		}
	}
	return nil
}

func TestRebuildMaterializedStatsWritesSnapshotsStatsAndState(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "materialized-test.db")
	model.InitDB(dbPath)
	sqlDB, err := model.Conn.DB()
	if err == nil {
		defer sqlDB.Close()
	}

	report := model.BattleReport{
		BattleId: 1001, Time: 1000, Npc: 0, Result: 1,
		AttackName: "甲", AttackUnionName: "盟A", AttackIdu: "A",
		AttackHero1Id: 1, AttackHero2Id: 2, AttackHero3Id: 3,
		AttackHero1Level: 35, AttackHero2Level: 35, AttackHero3Level: 35,
		AttackHp:   23000,
		DefendName: "乙", DefendUnionName: "盟B", DefendIdu: "D",
		DefendHero1Id: 4, DefendHero2Id: 5, DefendHero3Id: 6,
		DefendHero1Level: 35, DefendHero2Level: 35, DefendHero3Level: 35,
		DefendHp:     23000,
		AllSkillInfo: "1,10,10,11,10,12,10;2,20,10,21,10,22,10;3,30,10,31,10,32,10;4,40,10,41,10,42,10;5,50,10,51,10,52,10;6,60,10,61,10,62,10",
	}
	if err := model.Conn.Create(&report).Error; err != nil {
		t.Fatalf("insert battle report: %v", err)
	}

	if err := rebuildMaterializedStats(); err != nil {
		t.Fatalf("rebuildMaterializedStats() error = %v", err)
	}

	var snapshots int64
	model.Conn.Model(&model.PlayerTeamSnapshot{}).Count(&snapshots)
	if snapshots != 2 {
		t.Fatalf("snapshot count = %d, want 2", snapshots)
	}

	var stats int64
	model.Conn.Model(&model.TeamWinRateStat{}).Count(&stats)
	if stats != 4 {
		t.Fatalf("win-rate stat count = %d, want 4 player/team rows", stats)
	}

	var state model.MaterializedState
	if err := model.Conn.Where("name = ?", "player_team_snapshot").First(&state).Error; err != nil {
		t.Fatalf("state not found: %v", err)
	}
	if state.Status != "ready" || state.LastBattleID != 1001 || state.BattleReportCount != 1 {
		t.Fatalf("state = %+v, want ready through battle 1001 count 1", state)
	}
}

func TestReplaceMaterializedStatsRowsUsesStagingTables(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "materialized-staging-test.db")
	model.InitDB(dbPath)
	sqlDB, err := model.Conn.DB()
	if err == nil {
		defer sqlDB.Close()
	}

	for _, name := range []string{"player_team_snapshot", "team_winrate_stats"} {
		if err := saveMaterializedState(model.MaterializedState{
			Name:    name,
			Version: materializedStatsVersion,
			Status:  "building",
		}); err != nil {
			t.Fatalf("save state %s: %v", name, err)
		}
	}
	if err := model.Conn.Create(&model.PlayerTeamSnapshot{
		PlayerName: "旧队伍", Role: "attack", Idu: "old",
		Hero1ID: 1, Hero2ID: 2, Hero3ID: 3,
		LineupKey: "1_2_3", NormalizedSkillKey: "old-skill",
	}).Error; err != nil {
		t.Fatalf("insert old snapshot: %v", err)
	}

	snapshots := []model.PlayerTeamSnapshot{
		{
			PlayerName: "新队伍", Role: "defend", Idu: "new",
			Hero1ID: 4, Hero2ID: 5, Hero3ID: 6,
			LineupKey: "4_5_6", NormalizedSkillKey: "new-skill",
			LastBattleID: 99,
		},
	}
	stats := []model.TeamWinRateStat{
		{
			Mode: "player", MinLevel: defaultWinRateMinLevel, MinHp: defaultWinRateMinHp,
			PlayerName: "新队伍", Role: "defend", Idu: "new",
			Hero1ID: 4, Hero2ID: 5, Hero3ID: 6,
			LineupKey: "4_5_6", NormalizedSkillKey: "new-skill",
			TotalBattles: 3, WinCount: 2, WinRate: 66.7, LastBattleID: 99,
		},
	}

	if err := replaceMaterializedStatsRows(snapshots, stats, 12, 99); err != nil {
		t.Fatalf("replaceMaterializedStatsRows() error = %v", err)
	}

	var visible []model.PlayerTeamSnapshot
	if err := model.Conn.Find(&visible).Error; err != nil {
		t.Fatalf("query snapshots: %v", err)
	}
	if len(visible) != 1 || visible[0].PlayerName != "新队伍" {
		t.Fatalf("snapshots = %+v, want only staged new row", visible)
	}

	var state model.MaterializedState
	if err := model.Conn.Where("name = ?", "player_team_snapshot").First(&state).Error; err != nil {
		t.Fatalf("state not found: %v", err)
	}
	if state.ProcessedReportCount != 12 || state.LastBattleID != 99 {
		t.Fatalf("state = %+v, want processed 12 last battle 99", state)
	}

	for _, tableName := range []string{"player_team_snapshot_rebuild", "team_winrate_stats_rebuild"} {
		var count int64
		if err := model.Conn.Raw("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = ?", tableName).Scan(&count).Error; err != nil {
			t.Fatalf("check staging table %s: %v", tableName, err)
		}
		if count != 0 {
			t.Fatalf("staging table %s still exists", tableName)
		}
	}
}

func TestInitDBCreatesLargeBattleQueryIndexes(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "materialized-index-test.db")
	model.InitDB(dbPath)
	sqlDB, err := model.Conn.DB()
	if err == nil {
		defer sqlDB.Close()
	}

	for _, indexName := range []string{
		"idx_br_attack_related",
		"idx_br_defend_related",
		"idx_twrs_team_search",
	} {
		var count int64
		if err := model.Conn.Raw("SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND name = ?", indexName).Scan(&count).Error; err != nil {
			t.Fatalf("check index %s: %v", indexName, err)
		}
		if count != 1 {
			t.Fatalf("index %s exists count = %d, want 1", indexName, count)
		}
	}
}

func TestMaterializedStatsPerformanceProbe(t *testing.T) {
	dbPath := os.Getenv("STZB_PERF_DB")
	if dbPath == "" {
		t.Skip("set STZB_PERF_DB to run the materialized stats performance probe")
	}

	model.InitDB(dbPath)
	sqlDB, err := model.Conn.DB()
	if err == nil {
		defer sqlDB.Close()
	}

	var reportCount int64
	if err := model.Conn.Model(&model.BattleReport{}).Count(&reportCount).Error; err != nil {
		t.Fatalf("count battle reports: %v", err)
	}
	t.Logf("battle_report_count=%d", reportCount)

	rebuildStart := time.Now()
	if err := rebuildMaterializedStats(); err != nil {
		t.Fatalf("rebuildMaterializedStats() error = %v", err)
	}
	t.Logf("rebuild_duration=%s", time.Since(rebuildStart))

	teamStart := time.Now()
	teams, teamTotal, teamMeta, err := queryMaterializedPlayerTeams("", "", "", 1, 20)
	if err != nil {
		t.Fatalf("queryMaterializedPlayerTeams() error = %v", err)
	}
	t.Logf("team_query_duration=%s query_ms=%d cache_hit=%t total=%d page_rows=%d", time.Since(teamStart), teamMeta.QueryMS, teamMeta.CacheHit, teamTotal, len(teams))

	winRateStart := time.Now()
	winRateData, used, err := queryMaterializedWinRateStats("player", "", "", "", 1, 20, defaultWinRateMinLevel, defaultWinRateMinHp)
	if err != nil {
		t.Fatalf("queryMaterializedWinRateStats() error = %v", err)
	}
	if !used {
		t.Fatal("queryMaterializedWinRateStats() did not use materialized stats")
	}
	winRateRows := 0
	if list, ok := winRateData["list"].([]model.TeamWinRateStat); ok {
		winRateRows = len(list)
	}
	t.Logf("win_rate_query_duration=%s query_ms=%v total=%v page_rows=%d", time.Since(winRateStart), winRateData["query_ms"], winRateData["total"], winRateRows)

	if len(teams) == 0 {
		t.Log("related_battles_skipped=no teams")
		return
	}
	team := teams[0]
	relatedStart := time.Now()
	relatedRows, relatedTotal, err := queryRelatedBattles(team.PlayerName, team.Role, team.Idu, team.Hero1ID, team.Hero2ID, team.Hero3ID, 1, 20)
	if err != nil {
		t.Fatalf("queryRelatedBattles() error = %v", err)
	}
	t.Logf("related_battles_duration=%s total=%d page_rows=%d", time.Since(relatedStart), relatedTotal, len(relatedRows))
}

func TestHiddenMaterializedTeamIsExcludedFromTeamAndWinRateQueries(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "materialized-hidden-test.db")
	model.InitDB(dbPath)
	sqlDB, err := model.Conn.DB()
	if err == nil {
		defer sqlDB.Close()
	}

	for _, name := range []string{"player_team_snapshot", "team_winrate_stats"} {
		if err := saveMaterializedState(model.MaterializedState{
			Name:    name,
			Version: materializedStatsVersion,
			Status:  "ready",
		}); err != nil {
			t.Fatalf("save state %s: %v", name, err)
		}
	}
	hiddenSnapshot := model.PlayerTeamSnapshot{
		PlayerName: "甲", Role: "attack", Idu: "A",
		Hero1ID: 1, Hero2ID: 2, Hero3ID: 3,
		LastTime: 200, LastBattleID: 2,
		LineupKey: "1_2_3", NormalizedSkillKey: "skill-a",
	}
	visibleSnapshot := model.PlayerTeamSnapshot{
		PlayerName: "乙", Role: "attack", Idu: "B",
		Hero1ID: 7, Hero2ID: 8, Hero3ID: 9,
		LastTime: 100, LastBattleID: 1,
		LineupKey: "7_8_9", NormalizedSkillKey: "skill-b",
	}
	if err := model.Conn.Create(&[]model.PlayerTeamSnapshot{hiddenSnapshot, visibleSnapshot}).Error; err != nil {
		t.Fatalf("insert snapshots: %v", err)
	}
	if err := model.Conn.Create(&[]model.TeamWinRateStat{
		{
			Mode: "player", MinLevel: defaultWinRateMinLevel, MinHp: defaultWinRateMinHp,
			PlayerName: "甲", Role: "attack", Idu: "A",
			Hero1ID: 1, Hero2ID: 2, Hero3ID: 3,
			LineupKey: "1_2_3", NormalizedSkillKey: "skill-a",
			TotalBattles: 10, WinRate: 70, LastTime: 200,
		},
		{
			Mode: "team", MinLevel: defaultWinRateMinLevel, MinHp: defaultWinRateMinHp,
			Players: "甲", Role: "attack", Idu: "A",
			Hero1ID: 1, Hero2ID: 2, Hero3ID: 3,
			LineupKey: "1_2_3", NormalizedSkillKey: "skill-a",
			TotalBattles: 10, WinRate: 70, LastTime: 200,
		},
		{
			Mode: "player", MinLevel: defaultWinRateMinLevel, MinHp: defaultWinRateMinHp,
			PlayerName: "乙", Role: "attack", Idu: "B",
			Hero1ID: 7, Hero2ID: 8, Hero3ID: 9,
			LineupKey: "7_8_9", NormalizedSkillKey: "skill-b",
			TotalBattles: 5, WinRate: 60, LastTime: 100,
		},
	}).Error; err != nil {
		t.Fatalf("insert win-rate stats: %v", err)
	}
	if err := model.Conn.Create(&model.MaterializedTeamExclusion{
		PlayerName: "甲", Role: "attack", Idu: "A",
		LineupKey: "1_2_3", NormalizedSkillKey: "skill-a",
		CreatedAt: time.Now().Unix(),
	}).Error; err != nil {
		t.Fatalf("insert exclusion: %v", err)
	}

	teams, total, _, err := queryMaterializedPlayerTeams("", "", "", 1, 20)
	if err != nil {
		t.Fatalf("queryMaterializedPlayerTeams() error = %v", err)
	}
	if total != 1 || len(teams) != 1 || teams[0].PlayerName != "乙" {
		t.Fatalf("visible teams = %+v total=%d, want only 乙", teams, total)
	}

	data, used, err := queryMaterializedWinRateStats("player", "", "", "", 1, 20, defaultWinRateMinLevel, defaultWinRateMinHp)
	if err != nil || !used {
		t.Fatalf("queryMaterializedWinRateStats(player) used=%t error=%v", used, err)
	}
	playerRows := data["list"].([]model.TeamWinRateStat)
	if len(playerRows) != 1 || playerRows[0].PlayerName != "乙" {
		t.Fatalf("player win-rate rows = %+v, want only 乙", playerRows)
	}

	data, used, err = queryMaterializedWinRateStats("team", "", "", "", 1, 20, defaultWinRateMinLevel, defaultWinRateMinHp)
	if err != nil || !used {
		t.Fatalf("queryMaterializedWinRateStats(team) used=%t error=%v", used, err)
	}
	teamRows := data["list"].([]model.TeamWinRateStat)
	if len(teamRows) != 0 {
		t.Fatalf("team win-rate rows = %+v, want hidden lineup excluded", teamRows)
	}
}

func TestListHiddenMaterializedTeamsReturnsPagedRows(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "materialized-hidden-list-test.db")
	model.InitDB(dbPath)
	sqlDB, err := model.Conn.DB()
	if err == nil {
		defer sqlDB.Close()
	}

	exclusions := []model.MaterializedTeamExclusion{
		{
			PlayerName: "甲", Role: "attack", Idu: "A",
			LineupKey: "1_2_3", NormalizedSkillKey: "skill-a", CreatedAt: 100,
		},
		{
			PlayerName: "乙", Role: "defend", Idu: "B",
			LineupKey: "4_5_6", NormalizedSkillKey: "skill-b", CreatedAt: 200,
		},
	}
	if err := model.Conn.Create(&exclusions).Error; err != nil {
		t.Fatalf("insert exclusions: %v", err)
	}

	rows, total, err := queryHiddenMaterializedTeams(1, 1)
	if err != nil {
		t.Fatalf("queryHiddenMaterializedTeams() error = %v", err)
	}
	if total != 2 {
		t.Fatalf("total = %d, want 2", total)
	}
	if len(rows) != 1 || rows[0].PlayerName != "乙" || rows[0].Hero1ID != 4 || rows[0].Hero2ID != 5 || rows[0].Hero3ID != 6 {
		t.Fatalf("rows = %+v, want latest hidden 乙 4/5/6", rows)
	}
}

func TestRestoreHiddenMaterializedTeamMakesQueriesVisibleAgain(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "materialized-restore-hidden-test.db")
	model.InitDB(dbPath)
	sqlDB, err := model.Conn.DB()
	if err == nil {
		defer sqlDB.Close()
	}

	for _, name := range []string{"player_team_snapshot", "team_winrate_stats"} {
		if err := saveMaterializedState(model.MaterializedState{
			Name:    name,
			Version: materializedStatsVersion,
			Status:  "ready",
		}); err != nil {
			t.Fatalf("save state %s: %v", name, err)
		}
	}
	if err := model.Conn.Create(&model.PlayerTeamSnapshot{
		PlayerName: "甲", Role: "attack", Idu: "A",
		Hero1ID: 1, Hero2ID: 2, Hero3ID: 3,
		LastTime: 200, LastBattleID: 2,
		LineupKey: "1_2_3", NormalizedSkillKey: "skill-a",
	}).Error; err != nil {
		t.Fatalf("insert snapshot: %v", err)
	}
	if err := model.Conn.Create(&model.TeamWinRateStat{
		Mode: "player", MinLevel: defaultWinRateMinLevel, MinHp: defaultWinRateMinHp,
		PlayerName: "甲", Role: "attack", Idu: "A",
		Hero1ID: 1, Hero2ID: 2, Hero3ID: 3,
		LineupKey: "1_2_3", NormalizedSkillKey: "skill-a",
		TotalBattles: 10, WinRate: 70, LastTime: 200,
	}).Error; err != nil {
		t.Fatalf("insert win-rate stat: %v", err)
	}
	exclusion := model.MaterializedTeamExclusion{
		PlayerName: "甲", Role: "attack", Idu: "A",
		LineupKey: "1_2_3", NormalizedSkillKey: "skill-a",
		CreatedAt: time.Now().Unix(),
	}
	if err := model.Conn.Create(&exclusion).Error; err != nil {
		t.Fatalf("insert exclusion: %v", err)
	}

	if err := restoreHiddenMaterializedTeam(exclusion.ID); err != nil {
		t.Fatalf("restoreHiddenMaterializedTeam() error = %v", err)
	}

	teams, total, _, err := queryMaterializedPlayerTeams("", "", "", 1, 20)
	if err != nil {
		t.Fatalf("queryMaterializedPlayerTeams() error = %v", err)
	}
	if total != 1 || len(teams) != 1 || teams[0].PlayerName != "甲" {
		t.Fatalf("visible teams = %+v total=%d, want restored 甲", teams, total)
	}

	data, used, err := queryMaterializedWinRateStats("player", "", "", "", 1, 20, defaultWinRateMinLevel, defaultWinRateMinHp)
	if err != nil || !used {
		t.Fatalf("queryMaterializedWinRateStats() used=%t error=%v", used, err)
	}
	playerRows := data["list"].([]model.TeamWinRateStat)
	if len(playerRows) != 1 || playerRows[0].PlayerName != "甲" {
		t.Fatalf("player win-rate rows = %+v, want restored 甲", playerRows)
	}
}

func TestRestoreHiddenMaterializedTeamMissingReturnsError(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "materialized-restore-missing-test.db")
	model.InitDB(dbPath)
	sqlDB, err := model.Conn.DB()
	if err == nil {
		defer sqlDB.Close()
	}

	if err := restoreHiddenMaterializedTeam(999); err == nil {
		t.Fatal("restoreHiddenMaterializedTeam() error = nil, want missing error")
	}
}

func TestBattleResultLabelRespectsRole(t *testing.T) {
	tests := []struct {
		result int64
		role   string
		want   string
	}{
		{result: 1, role: "attack", want: "胜"},
		{result: 1, role: "defend", want: "负"},
		{result: 0, role: "attack", want: "负"},
		{result: 0, role: "defend", want: "胜"},
		{result: 6, role: "attack", want: "平"},
		{result: 6, role: "defend", want: "平"},
	}

	for _, tt := range tests {
		if got := battleResultLabel(tt.result, tt.role); got != tt.want {
			t.Fatalf("battleResultLabel(%d, %q) = %q, want %q", tt.result, tt.role, got, tt.want)
		}
	}
}

func TestStartMaterializedStatsRebuildRunsInBackgroundAndTracksProgress(t *testing.T) {
	dbPath := filepath.Join(t.TempDir(), "materialized-async-test.db")
	model.InitDB(dbPath)
	sqlDB, err := model.Conn.DB()
	if err == nil {
		defer sqlDB.Close()
	}

	started := make(chan struct{})
	release := make(chan struct{})
	done := make(chan struct{})
	startedOnce := false
	startedOK, err := startMaterializedStatsRebuildWithRunner(func(progress func(int64) error) error {
		if err := progress(3); err != nil {
			return err
		}
		if !startedOnce {
			startedOnce = true
			close(started)
		}
		<-release
		close(done)
		return nil
	})
	if err != nil {
		t.Fatalf("startMaterializedStatsRebuildWithRunner() error = %v", err)
	}
	if !startedOK {
		t.Fatal("startedOK = false, want true")
	}

	select {
	case <-started:
	case <-time.After(time.Second):
		t.Fatal("background rebuild did not start")
	}

	var state model.MaterializedState
	if err := model.Conn.Where("name = ?", "player_team_snapshot").First(&state).Error; err != nil {
		t.Fatalf("state not found: %v", err)
	}
	if state.Status != "building" {
		t.Fatalf("state.Status = %q, want building", state.Status)
	}
	if state.ProcessedReportCount != 3 {
		t.Fatalf("ProcessedReportCount = %d, want 3", state.ProcessedReportCount)
	}

	close(release)
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("background rebuild did not finish")
	}

	waitForState(t, "player_team_snapshot", "ready")
}

func waitForState(t *testing.T, name string, want string) {
	t.Helper()
	deadline := time.Now().Add(time.Second)
	for time.Now().Before(deadline) {
		var state model.MaterializedState
		if err := model.Conn.Where("name = ?", name).First(&state).Error; err == nil && state.Status == want {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("state %s did not become %s", name, want)
}
