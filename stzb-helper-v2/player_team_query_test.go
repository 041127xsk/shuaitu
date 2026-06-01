package main

import "testing"

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
