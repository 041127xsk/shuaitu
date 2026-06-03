package main

import (
	"fmt"
	"sort"
	"strings"
	"stzbHelper/model"
	"sync"
	"time"

	"gorm.io/gorm"
)

const (
	materializedStatsVersion = 1
	defaultWinRateMinLevel   = 30
	defaultWinRateMinHp      = 20000
)

type materializedRebuildRunner func(progress func(int64) error) error

var materializedRebuildState = struct {
	sync.Mutex
	running bool
}{}

type winRateMaterializedAcc struct {
	stat      model.TeamWinRateStat
	playerSet map[string]bool
}

type materializedStatsAccumulator struct {
	teamCandidates []playerTeam
	playerStats    map[string]*winRateMaterializedAcc
	teamStats      map[string]*winRateMaterializedAcc
	lastBattleID   int64
	processed      int64
}

func newMaterializedStatsAccumulator() *materializedStatsAccumulator {
	return &materializedStatsAccumulator{
		playerStats: map[string]*winRateMaterializedAcc{},
		teamStats:   map[string]*winRateMaterializedAcc{},
	}
}

func (acc *materializedStatsAccumulator) Add(report model.BattleReport) {
	acc.processed++
	if report.BattleId > acc.lastBattleID {
		acc.lastBattleID = report.BattleId
	}

	acc.teamCandidates = append(acc.teamCandidates, battleReportTeamCandidates(report)...)
	if !isWinRateEligibleBattle(report, defaultWinRateMinLevel, defaultWinRateMinHp) {
		return
	}
	for _, side := range battleReportWinRateSides(report) {
		acc.addWinRateSide(side, "player")
		acc.addWinRateSide(side, "team")
	}
}

func (acc *materializedStatsAccumulator) ProcessedReportCount() int64 {
	return acc.processed
}

func (acc *materializedStatsAccumulator) LastBattleID() int64 {
	return acc.lastBattleID
}

func (acc *materializedStatsAccumulator) BuildSnapshots() []model.PlayerTeamSnapshot {
	teams := buildEffectivePlayerTeams(acc.teamCandidates)
	snapshots := make([]model.PlayerTeamSnapshot, 0, len(teams))
	now := time.Now().Unix()
	for _, team := range teams {
		snapshots = append(snapshots, playerTeamToSnapshot(team, now))
	}
	return snapshots
}

func (acc *materializedStatsAccumulator) BuildWinRateStats(mode string) []model.TeamWinRateStat {
	if mode == "team" {
		return buildWinRateStatsFromAcc(acc.teamStats, mode)
	}
	return buildWinRateStatsFromAcc(acc.playerStats, mode)
}

func (acc *materializedStatsAccumulator) addWinRateSide(side model.TeamWinRateStat, mode string) {
	key := winRateMaterializedKey(side, mode)
	stats := acc.playerStats
	if mode == "team" {
		stats = acc.teamStats
	}

	entry, ok := stats[key]
	if !ok {
		base := side
		base.TotalBattles = 0
		base.WinCount = 0
		base.LossCount = 0
		base.DrawCount = 0
		entry = &winRateMaterializedAcc{
			stat:      base,
			playerSet: map[string]bool{},
		}
		stats[key] = entry
	}
	entry.stat.TotalBattles++
	entry.stat.WinCount += side.WinCount
	entry.stat.LossCount += side.LossCount
	entry.stat.DrawCount += side.DrawCount
	if side.LastTime > entry.stat.LastTime || (side.LastTime == entry.stat.LastTime && side.LastBattleID > entry.stat.LastBattleID) {
		side.TotalBattles = entry.stat.TotalBattles
		side.WinCount = entry.stat.WinCount
		side.LossCount = entry.stat.LossCount
		side.DrawCount = entry.stat.DrawCount
		entry.stat = side
	}
	if side.PlayerName != "" {
		entry.playerSet[side.PlayerName] = true
	}
}

func buildMaterializedPlayerTeamSnapshots(reports []model.BattleReport) []model.PlayerTeamSnapshot {
	candidates := make([]playerTeam, 0, len(reports)*2)
	for _, report := range reports {
		candidates = append(candidates, battleReportTeamCandidates(report)...)
	}

	teams := buildEffectivePlayerTeams(candidates)
	snapshots := make([]model.PlayerTeamSnapshot, 0, len(teams))
	now := time.Now().Unix()
	for _, team := range teams {
		snapshots = append(snapshots, playerTeamToSnapshot(team, now))
	}
	return snapshots
}

func battleReportTeamCandidates(report model.BattleReport) []playerTeam {
	if report.Npc != 0 || strings.TrimSpace(report.AllSkillInfo) == "" {
		return nil
	}

	var candidates []playerTeam
	if isValidTeamSide(report.AttackHero1Id, report.AttackHero2Id, report.AttackHero3Id, report.AttackHero1Level, report.AttackHero2Level, report.AttackHero3Level, report.AttackHp, 15, 10000) {
		candidates = append(candidates, playerTeam{
			PlayerName:   report.AttackName,
			UnionName:    report.AttackUnionName,
			BattleID:     int(report.BattleId),
			Hero1ID:      int(report.AttackHero1Id),
			Hero2ID:      int(report.AttackHero2Id),
			Hero3ID:      int(report.AttackHero3Id),
			Hero1Level:   int(report.AttackHero1Level),
			Hero2Level:   int(report.AttackHero2Level),
			Hero3Level:   int(report.AttackHero3Level),
			Hero1Star:    int(report.AttackHero1Star),
			Hero2Star:    int(report.AttackHero2Star),
			Hero3Star:    int(report.AttackHero3Star),
			TotalStar:    int(report.AttackTotalStar),
			Hp:           int(report.AttackHp),
			AllSkillInfo: report.AllSkillInfo,
			Role:         "attack",
			Time:         int(report.Time),
			Gear:         report.AttackerGearInfo,
			HeroType:     report.AttackHeroType,
			Idu:          report.AttackIdu,
		})
	}

	if isValidTeamSide(report.DefendHero1Id, report.DefendHero2Id, report.DefendHero3Id, report.DefendHero1Level, report.DefendHero2Level, report.DefendHero3Level, report.DefendHp, 15, 10000) {
		candidates = append(candidates, playerTeam{
			PlayerName:   report.DefendName,
			UnionName:    report.DefendUnionName,
			BattleID:     int(report.BattleId),
			Hero1ID:      int(report.DefendHero1Id),
			Hero2ID:      int(report.DefendHero2Id),
			Hero3ID:      int(report.DefendHero3Id),
			Hero1Level:   int(report.DefendHero1Level),
			Hero2Level:   int(report.DefendHero2Level),
			Hero3Level:   int(report.DefendHero3Level),
			Hero1Star:    int(report.DefendHero1Star),
			Hero2Star:    int(report.DefendHero2Star),
			Hero3Star:    int(report.DefendHero3Star),
			TotalStar:    int(report.DefendTotalStar),
			Hp:           int(report.DefendHp),
			AllSkillInfo: report.AllSkillInfo,
			Role:         "defend",
			Time:         int(report.Time),
			Gear:         report.DefenderGearInfo,
			HeroType:     report.DefendHeroType,
			Idu:          report.DefendIdu,
		})
	}

	return candidates
}

func playerTeamToSnapshot(team playerTeam, sourceUpdatedAt int64) model.PlayerTeamSnapshot {
	return model.PlayerTeamSnapshot{
		PlayerName:         team.PlayerName,
		UnionName:          team.UnionName,
		Role:               team.Role,
		Idu:                team.Idu,
		Hero1ID:            int64(team.Hero1ID),
		Hero2ID:            int64(team.Hero2ID),
		Hero3ID:            int64(team.Hero3ID),
		Hero1Level:         int64(team.Hero1Level),
		Hero2Level:         int64(team.Hero2Level),
		Hero3Level:         int64(team.Hero3Level),
		Hero1Star:          int64(team.Hero1Star),
		Hero2Star:          int64(team.Hero2Star),
		Hero3Star:          int64(team.Hero3Star),
		TotalStar:          int64(team.TotalStar),
		Hp:                 int64(team.Hp),
		AllSkillInfo:       team.AllSkillInfo,
		Gear:               team.Gear,
		HeroType:           team.HeroType,
		LastTime:           int64(team.Time),
		LastBattleID:       int64(team.BattleID),
		LineupKey:          lineupKey(int64(team.Hero1ID), int64(team.Hero2ID), int64(team.Hero3ID)),
		NormalizedSkillKey: normalizedSkillKey(team.AllSkillInfo, team.Role),
		SourceUpdatedAt:    sourceUpdatedAt,
	}
}

func buildMaterializedWinRateStats(reports []model.BattleReport, mode string) []model.TeamWinRateStat {
	acc := newMaterializedStatsAccumulator()
	for _, report := range reports {
		acc.Add(report)
	}
	return acc.BuildWinRateStats(mode)
}

func buildWinRateStatsFromAcc(merged map[string]*winRateMaterializedAcc, mode string) []model.TeamWinRateStat {
	stats := make([]model.TeamWinRateStat, 0, len(merged))
	for _, entry := range merged {
		entry.stat.Mode = mode
		entry.stat.MinLevel = defaultWinRateMinLevel
		entry.stat.MinHp = defaultWinRateMinHp
		entry.stat.WinRate = calculateWinRate(entry.stat.WinCount, entry.stat.TotalBattles)
		if mode == "team" {
			entry.stat.PlayerName = ""
			entry.stat.Players = strings.Join(sortedSetKeys(entry.playerSet), ",")
		}
		stats = append(stats, entry.stat)
	}

	sort.Slice(stats, func(i, j int) bool {
		if stats[i].TotalBattles != stats[j].TotalBattles {
			return stats[i].TotalBattles > stats[j].TotalBattles
		}
		if stats[i].WinRate != stats[j].WinRate {
			return stats[i].WinRate > stats[j].WinRate
		}
		return stats[i].LastBattleID > stats[j].LastBattleID
	})
	return stats
}

func battleReportWinRateSides(report model.BattleReport) []model.TeamWinRateStat {
	attackWin, attackLoss, draw := resultCounts(report.Result, "attack")
	defendWin, defendLoss, defendDraw := resultCounts(report.Result, "defend")
	return []model.TeamWinRateStat{
		{
			PlayerName:         report.AttackName,
			UnionName:          report.AttackUnionName,
			Players:            report.AttackName,
			Role:               "attack",
			Idu:                report.AttackIdu,
			Hero1ID:            report.AttackHero1Id,
			Hero2ID:            report.AttackHero2Id,
			Hero3ID:            report.AttackHero3Id,
			Hero1Level:         report.AttackHero1Level,
			Hero2Level:         report.AttackHero2Level,
			Hero3Level:         report.AttackHero3Level,
			Hero1Star:          report.AttackHero1Star,
			Hero2Star:          report.AttackHero2Star,
			Hero3Star:          report.AttackHero3Star,
			TotalStar:          report.AttackTotalStar,
			AllSkillInfo:       report.AllSkillInfo,
			LineupKey:          lineupKey(report.AttackHero1Id, report.AttackHero2Id, report.AttackHero3Id),
			NormalizedSkillKey: normalizedSkillKey(report.AllSkillInfo, "attack"),
			WinCount:           attackWin,
			LossCount:          attackLoss,
			DrawCount:          draw,
			LastTime:           report.Time,
			LastBattleID:       report.BattleId,
		},
		{
			PlayerName:         report.DefendName,
			UnionName:          report.DefendUnionName,
			Players:            report.DefendName,
			Role:               "defend",
			Idu:                report.DefendIdu,
			Hero1ID:            report.DefendHero1Id,
			Hero2ID:            report.DefendHero2Id,
			Hero3ID:            report.DefendHero3Id,
			Hero1Level:         report.DefendHero1Level,
			Hero2Level:         report.DefendHero2Level,
			Hero3Level:         report.DefendHero3Level,
			Hero1Star:          report.DefendHero1Star,
			Hero2Star:          report.DefendHero2Star,
			Hero3Star:          report.DefendHero3Star,
			TotalStar:          report.DefendTotalStar,
			AllSkillInfo:       report.AllSkillInfo,
			LineupKey:          lineupKey(report.DefendHero1Id, report.DefendHero2Id, report.DefendHero3Id),
			NormalizedSkillKey: normalizedSkillKey(report.AllSkillInfo, "defend"),
			WinCount:           defendWin,
			LossCount:          defendLoss,
			DrawCount:          defendDraw,
			LastTime:           report.Time,
			LastBattleID:       report.BattleId,
		},
	}
}

func resultCounts(result int64, role string) (win int64, loss int64, draw int64) {
	if result == 6 || result == 7 || result == 8 || result == 13 {
		return 0, 0, 1
	}
	attackWon := result == 1 || result == 2 || result == 3 || result == 4 || result == 10 || result == 18 || result == 19
	if role == "attack" {
		if attackWon {
			return 1, 0, 0
		}
		if result == 0 {
			return 0, 1, 0
		}
		return 0, 0, 0
	}
	if attackWon {
		return 0, 1, 0
	}
	if result == 0 {
		return 1, 0, 0
	}
	return 0, 0, 0
}

func isWinRateEligibleBattle(report model.BattleReport, minLevel int64, minHp int64) bool {
	if report.Npc != 0 || !hasCompleteSkillInfo(report.AllSkillInfo) {
		return false
	}
	if !isValidTeamSide(report.AttackHero1Id, report.AttackHero2Id, report.AttackHero3Id, report.AttackHero1Level, report.AttackHero2Level, report.AttackHero3Level, report.AttackHp, minLevel, minHp) {
		return false
	}
	return isValidTeamSide(report.DefendHero1Id, report.DefendHero2Id, report.DefendHero3Id, report.DefendHero1Level, report.DefendHero2Level, report.DefendHero3Level, report.DefendHp, minLevel, minHp)
}

func isValidTeamSide(hero1, hero2, hero3, level1, level2, level3, hp, minLevel, minHp int64) bool {
	return hero1 != 0 && hero2 != 0 && hero3 != 0 &&
		level1 >= minLevel && level2 >= minLevel && level3 >= minLevel &&
		hp >= minHp
}

func hasCompleteSkillInfo(skillInfo string) bool {
	if strings.TrimSpace(skillInfo) == "" {
		return false
	}
	if strings.Count(skillInfo, ";") != 5 && strings.Count(skillInfo, ";") != 6 {
		return false
	}
	return !strings.Contains(skillInfo, ",0,")
}

func winRateMaterializedKey(stat model.TeamWinRateStat, mode string) string {
	if mode == "team" {
		return strings.Join([]string{stat.LineupKey, stat.NormalizedSkillKey}, "|")
	}
	return strings.Join([]string{stat.PlayerName, stat.LineupKey}, "|")
}

func lineupKey(hero1, hero2, hero3 int64) string {
	return fmt.Sprintf("%d_%d_%d", hero1, hero2, hero3)
}

func normalizedSkillKey(skillInfo string, role string) string {
	groups := strings.Split(skillInfo, ";")
	parts := make([]string, 0, 3)
	for _, group := range groups {
		values := strings.Split(group, ",")
		if len(values) < 6 {
			continue
		}
		index := strings.TrimSpace(values[0])
		if role == "attack" && (index < "1" || index > "3") {
			continue
		}
		if role == "defend" && (index < "4" || index > "6") {
			continue
		}
		sub1 := strings.TrimSpace(values[3])
		sub2 := strings.TrimSpace(values[5])
		if sub1 > sub2 {
			sub1, sub2 = sub2, sub1
		}
		parts = append(parts, strings.TrimSpace(values[1])+"_"+sub1+"_"+sub2)
	}
	if role == "defend" {
		sort.Sort(sort.Reverse(sort.StringSlice(parts)))
	} else {
		sort.Strings(parts)
	}
	return strings.Join(parts, "|")
}

func calculateWinRate(winCount int64, totalBattles int64) float64 {
	if totalBattles <= 0 {
		return 0
	}
	return float64(int(float64(winCount)/float64(totalBattles)*1000)) / 10
}

func sortedSetKeys(set map[string]bool) []string {
	keys := make([]string, 0, len(set))
	for key := range set {
		if key != "" {
			keys = append(keys, key)
		}
	}
	sort.Strings(keys)
	return keys
}

func rebuildMaterializedStats() error {
	if err := beginMaterializedRebuild(); err != nil {
		return err
	}
	if err := rebuildMaterializedStatsData(updateMaterializedRebuildProgress); err != nil {
		markMaterializedFailed(err)
		return err
	}
	return finishMaterializedRebuildReady()
}

func startMaterializedStatsRebuild() (bool, error) {
	return startMaterializedStatsRebuildWithRunner(rebuildMaterializedStatsData)
}

func startMaterializedStatsRebuildWithRunner(runner materializedRebuildRunner) (bool, error) {
	materializedRebuildState.Lock()
	if materializedRebuildState.running {
		materializedRebuildState.Unlock()
		return false, nil
	}
	materializedRebuildState.running = true
	materializedRebuildState.Unlock()

	if err := beginMaterializedRebuild(); err != nil {
		materializedRebuildState.Lock()
		materializedRebuildState.running = false
		materializedRebuildState.Unlock()
		return false, err
	}

	go func() {
		defer func() {
			materializedRebuildState.Lock()
			materializedRebuildState.running = false
			materializedRebuildState.Unlock()
		}()

		if err := runner(updateMaterializedRebuildProgress); err != nil {
			markMaterializedFailed(err)
			return
		}
		if err := finishMaterializedRebuildReady(); err != nil {
			markMaterializedFailed(err)
		}
	}()

	return true, nil
}

func materializedStatsRebuildRunning() bool {
	materializedRebuildState.Lock()
	defer materializedRebuildState.Unlock()
	return materializedRebuildState.running
}

func beginMaterializedRebuild() error {
	if model.Conn == nil {
		return fmt.Errorf("请先选择数据库")
	}

	var total int64
	if err := model.Conn.Model(&model.BattleReport{}).Count(&total).Error; err != nil {
		return err
	}

	startedAt := time.Now().Unix()
	if err := saveMaterializedState(model.MaterializedState{
		Name:              "player_team_snapshot",
		Version:           materializedStatsVersion,
		Status:            "building",
		BattleReportCount: total,
		StartedAt:         startedAt,
	}); err != nil {
		return err
	}
	if err := saveMaterializedState(model.MaterializedState{
		Name:              "team_winrate_stats",
		Version:           materializedStatsVersion,
		Status:            "building",
		BattleReportCount: total,
		StartedAt:         startedAt,
	}); err != nil {
		return err
	}
	return nil
}

func rebuildMaterializedStatsData(progress func(int64) error) error {
	acc := newMaterializedStatsAccumulator()
	batch := []model.BattleReport{}
	if err := model.Conn.Order("battle_id ASC").FindInBatches(&batch, 5000, func(tx *gorm.DB, batchNum int) error {
		for _, report := range batch {
			acc.Add(report)
		}
		return progress(acc.ProcessedReportCount())
	}).Error; err != nil {
		return err
	}

	snapshots := acc.BuildSnapshots()
	playerStats := acc.BuildWinRateStats("player")
	teamStats := acc.BuildWinRateStats("team")
	allStats := append(playerStats, teamStats...)

	return replaceMaterializedStatsRows(snapshots, allStats, acc.ProcessedReportCount(), acc.LastBattleID())
}

func replaceMaterializedStatsRows(snapshots []model.PlayerTeamSnapshot, stats []model.TeamWinRateStat, processed int64, lastBattleID int64) error {
	if model.Conn == nil {
		return fmt.Errorf("请先选择数据库")
	}

	if err := prepareMaterializedRebuildTables(); err != nil {
		return err
	}
	defer dropMaterializedRebuildTables()

	if len(snapshots) > 0 {
		if err := model.Conn.Table("player_team_snapshot_rebuild").CreateInBatches(snapshots, 500).Error; err != nil {
			return err
		}
	}
	if len(stats) > 0 {
		if err := model.Conn.Table("team_winrate_stats_rebuild").CreateInBatches(stats, 500).Error; err != nil {
			return err
		}
	}

	return model.Conn.Transaction(func(tx *gorm.DB) error {
		if err := tx.Exec("DELETE FROM player_team_snapshot").Error; err != nil {
			return err
		}
		if err := tx.Exec(`
INSERT INTO player_team_snapshot (
	player_name, union_name, role, idu,
	hero1_id, hero2_id, hero3_id,
	hero1_level, hero2_level, hero3_level,
	hero1_star, hero2_star, hero3_star, total_star,
	hp, all_skill_info, gear, hero_type,
	last_time, last_battle_id, lineup_key, normalized_skill_key, source_updated_at
)
SELECT
	player_name, union_name, role, idu,
	hero1_id, hero2_id, hero3_id,
	hero1_level, hero2_level, hero3_level,
	hero1_star, hero2_star, hero3_star, total_star,
	hp, all_skill_info, gear, hero_type,
	last_time, last_battle_id, lineup_key, normalized_skill_key, source_updated_at
FROM player_team_snapshot_rebuild`).Error; err != nil {
			return err
		}
		if err := tx.Exec("DELETE FROM team_winrate_stats").Error; err != nil {
			return err
		}
		if err := tx.Exec(`
INSERT INTO team_winrate_stats (
	mode, min_level, min_hp, player_name, union_name, players, role, idu,
	hero1_id, hero2_id, hero3_id,
	hero1_level, hero2_level, hero3_level,
	hero1_star, hero2_star, hero3_star, total_star,
	all_skill_info, lineup_key, normalized_skill_key,
	total_battles, win_count, loss_count, draw_count, win_rate,
	last_time, last_battle_id
)
SELECT
	mode, min_level, min_hp, player_name, union_name, players, role, idu,
	hero1_id, hero2_id, hero3_id,
	hero1_level, hero2_level, hero3_level,
	hero1_star, hero2_star, hero3_star, total_star,
	all_skill_info, lineup_key, normalized_skill_key,
	total_battles, win_count, loss_count, draw_count, win_rate,
	last_time, last_battle_id
FROM team_winrate_stats_rebuild`).Error; err != nil {
			return err
		}

		return updateMaterializedRebuildProgressTx(tx, processed, lastBattleID)
	})
}

func prepareMaterializedRebuildTables() error {
	for _, sql := range []string{
		"DROP TABLE IF EXISTS player_team_snapshot_rebuild",
		"DROP TABLE IF EXISTS team_winrate_stats_rebuild",
		"CREATE TABLE player_team_snapshot_rebuild AS SELECT * FROM player_team_snapshot WHERE 0",
		"CREATE TABLE team_winrate_stats_rebuild AS SELECT * FROM team_winrate_stats WHERE 0",
	} {
		if err := model.Conn.Exec(sql).Error; err != nil {
			return err
		}
	}
	return nil
}

func dropMaterializedRebuildTables() {
	if model.Conn == nil {
		return
	}
	_ = model.Conn.Exec("DROP TABLE IF EXISTS player_team_snapshot_rebuild").Error
	_ = model.Conn.Exec("DROP TABLE IF EXISTS team_winrate_stats_rebuild").Error
}

func updateMaterializedRebuildProgress(processed int64) error {
	return model.Conn.Transaction(func(tx *gorm.DB) error {
		return updateMaterializedRebuildProgressTx(tx, processed, 0)
	})
}

func updateMaterializedRebuildProgressTx(tx *gorm.DB, processed int64, lastBattleID int64) error {
	for _, name := range []string{"player_team_snapshot", "team_winrate_stats"} {
		var state model.MaterializedState
		if err := tx.Where("name = ?", name).First(&state).Error; err != nil {
			return err
		}
		if processed > state.ProcessedReportCount {
			state.ProcessedReportCount = processed
		}
		if lastBattleID > state.LastBattleID {
			state.LastBattleID = lastBattleID
		}
		if err := tx.Save(&state).Error; err != nil {
			return err
		}
	}
	return nil
}

func finishMaterializedRebuildReady() error {
	return model.Conn.Transaction(func(tx *gorm.DB) error {
		finishedAt := time.Now().Unix()
		for _, name := range []string{"player_team_snapshot", "team_winrate_stats"} {
			var state model.MaterializedState
			if err := tx.Where("name = ?", name).First(&state).Error; err != nil {
				return err
			}
			state.Status = "ready"
			state.FinishedAt = finishedAt
			state.LastError = ""
			if err := tx.Save(&state).Error; err != nil {
				return err
			}
		}
		return nil
	})
}

func saveMaterializedState(state model.MaterializedState) error {
	if model.Conn == nil {
		return fmt.Errorf("请先选择数据库")
	}
	return model.Conn.Save(&state).Error
}

func markMaterializedFailed(err error) {
	if model.Conn == nil {
		return
	}
	now := time.Now().Unix()
	msg := ""
	if err != nil {
		msg = err.Error()
	}
	for _, name := range []string{"player_team_snapshot", "team_winrate_stats"} {
		_ = model.Conn.Save(&model.MaterializedState{
			Name:       name,
			Version:    materializedStatsVersion,
			Status:     "failed",
			FinishedAt: now,
			LastError:  msg,
		}).Error
	}
}

func applyBattleReportToMaterializedStats(report model.BattleReport) error {
	if model.Conn == nil {
		return fmt.Errorf("请先选择数据库")
	}
	if !materializedStateReady("player_team_snapshot") || !materializedStateReady("team_winrate_stats") {
		return markMaterializedStale(report.BattleId)
	}

	err := model.Conn.Transaction(func(tx *gorm.DB) error {
		if err := refreshSnapshotsForPlayers(tx, affectedBattlePlayers(report)); err != nil {
			return err
		}
		if isWinRateEligibleBattle(report, defaultWinRateMinLevel, defaultWinRateMinHp) {
			for _, side := range battleReportWinRateSides(report) {
				if err := upsertWinRateStat(tx, side, "player"); err != nil {
					return err
				}
				if err := upsertWinRateStat(tx, side, "team"); err != nil {
					return err
				}
			}
		}
		return bumpMaterializedStates(tx, report.BattleId)
	})
	if err != nil {
		markMaterializedFailed(err)
		return err
	}
	return nil
}

func refreshSnapshotsForPlayers(tx *gorm.DB, players []string) error {
	players = compactStrings(players)
	if len(players) == 0 {
		return nil
	}

	var reports []model.BattleReport
	if err := tx.Where("attack_name IN ? OR defend_name IN ?", players, players).Order("battle_id ASC").Find(&reports).Error; err != nil {
		return err
	}
	playerSet := map[string]bool{}
	for _, player := range players {
		playerSet[player] = true
	}

	allSnapshots := buildMaterializedPlayerTeamSnapshots(reports)
	snapshots := make([]model.PlayerTeamSnapshot, 0, len(allSnapshots))
	for _, snapshot := range allSnapshots {
		if playerSet[snapshot.PlayerName] {
			snapshots = append(snapshots, snapshot)
		}
	}

	if err := tx.Where("player_name IN ?", players).Delete(&model.PlayerTeamSnapshot{}).Error; err != nil {
		return err
	}
	if len(snapshots) > 0 {
		return tx.CreateInBatches(snapshots, 100).Error
	}
	return nil
}

func upsertWinRateStat(tx *gorm.DB, side model.TeamWinRateStat, mode string) error {
	side.Mode = mode
	side.MinLevel = defaultWinRateMinLevel
	side.MinHp = defaultWinRateMinHp
	side.TotalBattles = 1
	side.WinRate = calculateWinRate(side.WinCount, side.TotalBattles)
	if mode == "team" {
		side.Players = side.PlayerName
		side.PlayerName = ""
	}

	query := tx.Where("mode = ? AND min_level = ? AND min_hp = ? AND lineup_key = ?", mode, defaultWinRateMinLevel, defaultWinRateMinHp, side.LineupKey)
	if mode == "team" {
		query = query.Where("normalized_skill_key = ?", side.NormalizedSkillKey)
	} else {
		query = query.Where("player_name = ?", side.PlayerName)
	}

	var existing model.TeamWinRateStat
	if err := query.First(&existing).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return tx.Create(&side).Error
		}
		return err
	}

	existing.TotalBattles += 1
	existing.WinCount += side.WinCount
	existing.LossCount += side.LossCount
	existing.DrawCount += side.DrawCount
	existing.WinRate = calculateWinRate(existing.WinCount, existing.TotalBattles)
	if mode == "team" {
		existing.Players = mergeCSVNames(existing.Players, side.Players)
	}
	if side.LastTime > existing.LastTime || (side.LastTime == existing.LastTime && side.LastBattleID > existing.LastBattleID) {
		existing.UnionName = side.UnionName
		existing.Role = side.Role
		existing.Idu = side.Idu
		existing.Hero1Level = side.Hero1Level
		existing.Hero2Level = side.Hero2Level
		existing.Hero3Level = side.Hero3Level
		existing.Hero1Star = side.Hero1Star
		existing.Hero2Star = side.Hero2Star
		existing.Hero3Star = side.Hero3Star
		existing.TotalStar = side.TotalStar
		existing.AllSkillInfo = side.AllSkillInfo
		existing.LastTime = side.LastTime
		existing.LastBattleID = side.LastBattleID
	}
	return tx.Save(&existing).Error
}

func bumpMaterializedStates(tx *gorm.DB, battleID int64) error {
	for _, name := range []string{"player_team_snapshot", "team_winrate_stats"} {
		var state model.MaterializedState
		if err := tx.Where("name = ?", name).First(&state).Error; err != nil {
			return err
		}
		if battleID > state.LastBattleID {
			state.LastBattleID = battleID
		}
		state.Status = "ready"
		if err := tx.Save(&state).Error; err != nil {
			return err
		}
	}
	return nil
}

func markMaterializedStale(battleID int64) error {
	if model.Conn == nil {
		return fmt.Errorf("请先选择数据库")
	}
	now := time.Now().Unix()
	for _, name := range []string{"player_team_snapshot", "team_winrate_stats"} {
		state := model.MaterializedState{
			Name:         name,
			Version:      materializedStatsVersion,
			Status:       "stale",
			LastBattleID: battleID,
			FinishedAt:   now,
		}
		var existing model.MaterializedState
		if err := model.Conn.Where("name = ?", name).First(&existing).Error; err == nil {
			state.BattleReportCount = existing.BattleReportCount
			state.StartedAt = existing.StartedAt
			if existing.LastBattleID > battleID {
				state.LastBattleID = existing.LastBattleID
			}
		}
		if err := model.Conn.Save(&state).Error; err != nil {
			return err
		}
	}
	return nil
}

func affectedBattlePlayers(report model.BattleReport) []string {
	return []string{report.AttackName, report.DefendName}
}

func compactStrings(values []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value == "" || seen[value] {
			continue
		}
		seen[value] = true
		out = append(out, value)
	}
	return out
}

func mergeCSVNames(existing string, next string) string {
	set := map[string]bool{}
	for _, value := range strings.Split(existing+","+next, ",") {
		value = strings.TrimSpace(value)
		if value != "" {
			set[value] = true
		}
	}
	return strings.Join(sortedSetKeys(set), ",")
}
