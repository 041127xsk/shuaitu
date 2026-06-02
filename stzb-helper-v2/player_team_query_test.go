package main

import (
	"testing"
	"time"
)

func TestBuildEffectivePlayerTeamsReplacesOlderSharedHeroes(t *testing.T) {
	rows := []playerTeam{
		{PlayerName: "甲", BattleID: 100, Hero1ID: 1, Hero2ID: 2, Hero3ID: 3, Time: 1000},
		{PlayerName: "甲", BattleID: 90, Hero1ID: 1, Hero2ID: 2, Hero3ID: 4, Time: 900},
		{PlayerName: "甲", BattleID: 80, Hero1ID: 1, Hero2ID: 5, Hero3ID: 6, Time: 800},
		{PlayerName: "乙", BattleID: 70, Hero1ID: 1, Hero2ID: 2, Hero3ID: 4, Time: 700},
	}

	teams := buildEffectivePlayerTeams(rows)

	if len(teams) != 3 {
		t.Fatalf("len(teams) = %d, want 3", len(teams))
	}
	if teams[0].BattleID != 100 {
		t.Fatalf("first team battle id = %d, want 100", teams[0].BattleID)
	}
	for _, team := range teams {
		if team.PlayerName == "甲" && team.BattleID == 90 {
			t.Fatal("older same-player team sharing two heroes was not replaced")
		}
	}
}

func TestBuildEffectivePlayerTeamsKeepsLatestExactLineup(t *testing.T) {
	rows := []playerTeam{
		{PlayerName: "甲", BattleID: 11, Hero1ID: 1, Hero2ID: 2, Hero3ID: 3, Time: 100},
		{PlayerName: "甲", BattleID: 12, Hero1ID: 1, Hero2ID: 2, Hero3ID: 3, Time: 100},
		{PlayerName: "甲", BattleID: 10, Hero1ID: 1, Hero2ID: 2, Hero3ID: 3, Time: 90},
	}

	teams := buildEffectivePlayerTeams(rows)

	if len(teams) != 1 {
		t.Fatalf("len(teams) = %d, want 1", len(teams))
	}
	if teams[0].BattleID != 12 {
		t.Fatalf("kept battle id = %d, want newest stable battle id 12", teams[0].BattleID)
	}
}

func TestPaginatePlayerTeamsUsesFilteredTotal(t *testing.T) {
	teams := []playerTeam{
		{BattleID: 5},
		{BattleID: 4},
		{BattleID: 3},
		{BattleID: 2},
		{BattleID: 1},
	}

	page, total := paginatePlayerTeams(teams, 2, 2)

	if total != 5 {
		t.Fatalf("total = %d, want 5", total)
	}
	if len(page) != 2 || page[0].BattleID != 3 || page[1].BattleID != 2 {
		t.Fatalf("page = %+v, want battle ids 3 and 2", page)
	}
}

func TestPaginatePlayerTeamsCanReturnAllForExport(t *testing.T) {
	teams := []playerTeam{{BattleID: 3}, {BattleID: 2}, {BattleID: 1}}

	page, total := paginatePlayerTeams(teams, 1, 0)

	if total != 3 {
		t.Fatalf("total = %d, want 3", total)
	}
	if len(page) != 3 {
		t.Fatalf("len(page) = %d, want all 3 teams", len(page))
	}
}

func TestPlayerTeamCacheReportsHit(t *testing.T) {
	invalidatePlayerTeamQueryCache()
	key := playerTeamQueryCacheKey("甲", "盟", "1")
	setCachedPlayerTeams(key, []playerTeam{{BattleID: 100}})

	teams, ok := getCachedPlayerTeams(key)

	if !ok {
		t.Fatal("cache hit = false, want true")
	}
	if len(teams) != 1 || teams[0].BattleID != 100 {
		t.Fatalf("teams = %+v, want cached battle id 100", teams)
	}
}

func TestNewPlayerTeamQueryMetaIncludesElapsedAndCacheHit(t *testing.T) {
	meta := newPlayerTeamQueryMeta(time.Now().Add(-1500*time.Millisecond), true)

	if !meta.CacheHit {
		t.Fatal("CacheHit = false, want true")
	}
	if meta.QueryMS < 1000 {
		t.Fatalf("QueryMS = %d, want at least 1000", meta.QueryMS)
	}
}

func TestBuildEffectivePlayerTeamsPrefersManualCorrection(t *testing.T) {
	rows := []playerTeam{
		{PlayerName: "甲", BattleID: 9, SourceType: "battle_report", SourceID: 9, Time: 300, Hero1ID: 1001, Hero2ID: 1002, Hero3ID: 1003},
		{PlayerName: "甲", BattleID: 101, SourceType: "manual", SourceID: 101, Manual: true, Time: 100, Hero1ID: 1001, Hero2ID: 1002, Hero3ID: 1004},
	}

	got := buildEffectivePlayerTeams(rows)

	if len(got) != 1 {
		t.Fatalf("len(buildEffectivePlayerTeams()) = %d, want 1", len(got))
	}
	if !got[0].Manual || got[0].SourceID != 101 {
		t.Fatalf("kept team = %#v, want manual correction source_id 101", got[0])
	}
}

func TestFilterHiddenPlayerTeamsHidesOnlyMatchingSourceAndRole(t *testing.T) {
	rows := []playerTeam{
		{BattleID: 1, SourceType: "battle_report", SourceID: 1, Role: "attack"},
		{BattleID: 1, SourceType: "battle_report", SourceID: 1, Role: "defend"},
		{BattleID: 2, SourceType: "manual", SourceID: 2, Role: "attack", Manual: true},
	}
	hidden := map[string]bool{
		hiddenPlayerTeamKey("battle_report", 1, "attack"): true,
	}

	got := filterHiddenPlayerTeams(rows, hidden)

	if len(got) != 2 {
		t.Fatalf("len(filterHiddenPlayerTeams()) = %d, want 2", len(got))
	}
	if got[0].Role != "defend" || got[1].SourceType != "manual" {
		t.Fatalf("remaining teams = %#v, want defend battle row and manual row", got)
	}
}
