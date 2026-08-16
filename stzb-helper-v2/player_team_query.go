package main

import (
	"container/list"
	"fmt"
	"log"
	"sort"
	"strings"
	"stzbHelper/model"
	"sync"
	"time"
)

type playerTeam struct {
	PlayerName   string `json:"player_name"`
	UnionName    string `json:"union_name"`
	BattleID     int    `json:"battle_id"`
	Hero1ID      int    `json:"hero1_id"`
	Hero2ID      int    `json:"hero2_id"`
	Hero3ID      int    `json:"hero3_id"`
	Hero1Level   int    `json:"hero1_level"`
	Hero2Level   int    `json:"hero2_level"`
	Hero3Level   int    `json:"hero3_level"`
	Hero1Star    int    `json:"hero1_star"`
	Hero2Star    int    `json:"hero2_star"`
	Hero3Star    int    `json:"hero3_star"`
	TotalStar    int    `json:"total_star"`
	Hp           int    `json:"hp"`
	AllSkillInfo string `json:"all_skill_info"`
	Role         string `json:"role"`
	Time         int    `json:"time"`
	Gear         string `json:"gear"`
	HeroType     string `json:"hero_type"`
	Idu          string `json:"idu"`
	SourceType   string `json:"source_type"`
	SourceID     int    `json:"source_id"`
	Manual       bool   `json:"manual"`
	Note         string `json:"note"`
}

type playerTeamCacheEntry struct {
	key       string
	createdAt time.Time
	teams     []playerTeam
}

type playerTeamQueryMeta struct {
	QueryMS  int64 `json:"query_ms"`
	CacheHit bool  `json:"cache_hit"`
}

type playerTeamLRUCache struct {
	sync.Mutex
	entries map[string]*list.Element
	order   *list.List
}

var playerTeamQueryCache playerTeamLRUCache

const playerTeamQueryCacheTTL = 20 * time.Second
const playerTeamQueryCacheMaxSize = 32

func initPlayerTeamQueryCache() {
	playerTeamQueryCache.entries = make(map[string]*list.Element, playerTeamQueryCacheMaxSize)
	playerTeamQueryCache.order = list.New()
}

func queryEffectivePlayerTeams(name, uname, idu string) ([]playerTeam, error) {
	teams, _, err := queryEffectivePlayerTeamsWithMeta(name, uname, idu)
	return teams, err
}

func queryEffectivePlayerTeamsWithMeta(name, uname, idu string) ([]playerTeam, playerTeamQueryMeta, error) {
	start := time.Now()
	key := playerTeamQueryCacheKey(name, uname, idu)
	if teams, ok := getCachedPlayerTeams(key); ok {
		log.Printf("队伍查询命中缓存: name=%s, union=%s, idu=%s, 有效队伍=%d", name, uname, idu, len(teams))
		return teams, newPlayerTeamQueryMeta(start, true), nil
	}

	rows, err := queryPlayerTeamCandidates(name, uname, idu)
	if err != nil {
		return nil, newPlayerTeamQueryMeta(start, false), err
	}
	manualRows, err := queryManualPlayerTeamCandidates(name, uname, idu)
	if err != nil {
		return nil, newPlayerTeamQueryMeta(start, false), err
	}
	hidden, err := queryHiddenPlayerTeamKeys()
	if err != nil {
		return nil, newPlayerTeamQueryMeta(start, false), err
	}
	rows = append(rows, manualRows...)
	rows = filterHiddenPlayerTeams(rows, hidden)
	teams := buildEffectivePlayerTeams(rows)
	setCachedPlayerTeams(key, teams)
	log.Printf("队伍查询刷新缓存: name=%s, union=%s, idu=%s, 候选=%d, 有效=%d", name, uname, idu, len(rows), len(teams))
	return teams, newPlayerTeamQueryMeta(start, false), nil
}

func newPlayerTeamQueryMeta(start time.Time, cacheHit bool) playerTeamQueryMeta {
	elapsed := time.Since(start).Milliseconds()
	if elapsed < 0 {
		elapsed = 0
	}
	return playerTeamQueryMeta{
		QueryMS:  elapsed,
		CacheHit: cacheHit,
	}
}

func queryPlayerTeamCandidates(name, uname, idu string) ([]playerTeam, error) {
	if model.Conn == nil {
		return nil, fmt.Errorf("请先选择数据库")
	}

	attackWhere, attackArgs := buildPlayerTeamWhere("attack", name, uname, idu)
	defendWhere, defendArgs := buildPlayerTeamWhere("defend", name, uname, idu)
	args := append(attackArgs, defendArgs...)

	query := fmt.Sprintf(`
		SELECT
			attack_name AS player_name,
			attack_union_name AS union_name,
			attack_hero1_id AS hero1_id,
			attack_hero2_id AS hero2_id,
			attack_hero3_id AS hero3_id,
			attack_hero1_level AS hero1_level,
			attack_hero2_level AS hero2_level,
			attack_hero3_level AS hero3_level,
			attack_hero1_star AS hero1_star,
			attack_hero2_star AS hero2_star,
			attack_hero3_star AS hero3_star,
			attack_total_star AS total_star,
			attack_hp AS hp,
			attacker_gear_info AS gear,
			attack_hero_type AS hero_type,
			attack_idu AS idu,
			time,
			all_skill_info,
			battle_id,
			'attack' AS role,
			'battle_report' AS source_type,
			battle_id AS source_id,
			0 AS manual,
			'' AS note
		FROM battle_report
		WHERE %s
		UNION ALL
		SELECT
			defend_name AS player_name,
			defend_union_name AS union_name,
			defend_hero1_id AS hero1_id,
			defend_hero2_id AS hero2_id,
			defend_hero3_id AS hero3_id,
			defend_hero1_level AS hero1_level,
			defend_hero2_level AS hero2_level,
			defend_hero3_level AS hero3_level,
			defend_hero1_star AS hero1_star,
			defend_hero2_star AS hero2_star,
			defend_hero3_star AS hero3_star,
			defend_total_star AS total_star,
			defend_hp AS hp,
			defender_gear_info AS gear,
			defend_hero_type AS hero_type,
			defend_idu AS idu,
			time,
			all_skill_info,
			battle_id,
			'defend' AS role,
			'battle_report' AS source_type,
			battle_id AS source_id,
			0 AS manual,
			'' AS note
		FROM battle_report
		WHERE %s
		ORDER BY time DESC, battle_id DESC
		LIMIT 5000`, strings.Join(attackWhere, " AND "), strings.Join(defendWhere, " AND "))

	var rows []playerTeam
	if err := model.Conn.Raw(query, args...).Scan(&rows).Error; err != nil {
		return nil, err
	}
	return rows, nil
}

func buildPlayerTeamWhere(side, name, uname, idu string) ([]string, []interface{}) {
	where := []string{
		fmt.Sprintf("%s_hero1_id != 0", side),
		fmt.Sprintf("%s_hero2_id != 0", side),
		fmt.Sprintf("%s_hero3_id != 0", side),
		fmt.Sprintf("%s_hero1_level >= 15", side),
		fmt.Sprintf("%s_hero2_level >= 15", side),
		fmt.Sprintf("%s_hero3_level >= 15", side),
		fmt.Sprintf("%s_hp >= 10000", side),
		"npc = 0",
		"all_skill_info IS NOT NULL",
		"all_skill_info != ''",
		buildPlayerTeamExclusionWhere(side),
	}
	args := []interface{}{}

	if strings.TrimSpace(name) != "" {
		where = append(where, fmt.Sprintf("%s_name LIKE ?", side))
		args = append(args, "%"+strings.TrimSpace(name)+"%")
	}
	if strings.TrimSpace(uname) != "" {
		where = append(where, fmt.Sprintf("%s_union_name LIKE ?", side))
		args = append(args, "%"+strings.TrimSpace(uname)+"%")
	}
	if strings.TrimSpace(idu) != "" {
		where = append(where, fmt.Sprintf("%s_idu LIKE ?", side))
		args = append(args, "%"+strings.TrimSpace(idu)+"%")
	}

	return where, args
}

func buildPlayerTeamExclusionWhere(side string) string {
	return fmt.Sprintf(`NOT EXISTS (
		SELECT 1 FROM materialized_team_exclusion e
		WHERE e.lineup_key = printf('%%d_%%d_%%d', %[1]s_hero1_id, %[1]s_hero2_id, %[1]s_hero3_id)
			AND (e.player_name = '' OR e.player_name = %[1]s_name)
			AND (e.role = '' OR e.role = '%[1]s')
			AND (e.idu = '' OR e.idu = %[1]s_idu)
	)`, side)
}

func buildEffectivePlayerTeams(rows []playerTeam) []playerTeam {
	sortedRows := append([]playerTeam(nil), rows...)
	sort.SliceStable(sortedRows, func(i, j int) bool {
		if sortedRows[i].Manual != sortedRows[j].Manual {
			return sortedRows[i].Manual
		}
		if sortedRows[i].Time == sortedRows[j].Time {
			return sortedRows[i].BattleID > sortedRows[j].BattleID
		}
		return sortedRows[i].Time > sortedRows[j].Time
	})

	exactSeen := make(map[string]struct{}, len(sortedRows))
	keptByPlayer := make(map[string][]playerTeam)
	teams := make([]playerTeam, 0, len(sortedRows))

	for _, row := range sortedRows {
		exactKey := playerTeamExactKey(row)
		if _, ok := exactSeen[exactKey]; ok {
			continue
		}
		if conflictsWithKeptPlayerTeam(row, keptByPlayer[row.PlayerName]) {
			continue
		}

		exactSeen[exactKey] = struct{}{}
		teams = append(teams, row)
		keptByPlayer[row.PlayerName] = append(keptByPlayer[row.PlayerName], row)
	}

	return teams
}

func conflictsWithKeptPlayerTeam(row playerTeam, kept []playerTeam) bool {
	for _, newer := range kept {
		if sharedHeroCount(row, newer) >= 2 {
			return true
		}
	}
	return false
}

func sharedHeroCount(a, b playerTeam) int {
	aHeroes := map[int]struct{}{a.Hero1ID: {}, a.Hero2ID: {}, a.Hero3ID: {}}
	count := 0
	for _, id := range []int{b.Hero1ID, b.Hero2ID, b.Hero3ID} {
		if _, ok := aHeroes[id]; ok && id != 0 {
			count++
		}
	}
	return count
}

func playerTeamExactKey(team playerTeam) string {
	return fmt.Sprintf("%s|%d|%d|%d", team.PlayerName, team.Hero1ID, team.Hero2ID, team.Hero3ID)
}

func hiddenPlayerTeamKey(sourceType string, sourceID int, role string) string {
	return fmt.Sprintf("%s|%d|%s", sourceType, sourceID, role)
}

func normalizePlayerTeamSource(row playerTeam) playerTeam {
	if row.SourceType == "" {
		if row.Manual {
			row.SourceType = "manual"
		} else {
			row.SourceType = "battle_report"
		}
	}
	if row.SourceID == 0 {
		row.SourceID = row.BattleID
	}
	return row
}

func filterHiddenPlayerTeams(rows []playerTeam, hidden map[string]bool) []playerTeam {
	if len(hidden) == 0 {
		return rows
	}
	filtered := make([]playerTeam, 0, len(rows))
	for _, row := range rows {
		row = normalizePlayerTeamSource(row)
		if hidden[hiddenPlayerTeamKey(row.SourceType, row.SourceID, row.Role)] {
			continue
		}
		filtered = append(filtered, row)
	}
	return filtered
}

func paginatePlayerTeams(teams []playerTeam, page, pageSize int) ([]playerTeam, int) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 50
	}
	total := len(teams)
	start := (page - 1) * pageSize
	if start >= total {
		return []playerTeam{}, total
	}
	end := start + pageSize
	if end > total {
		end = total
	}
	return teams[start:end], total
}

func normalizePlayerTeamPageSize(pageSize int) int {
	if pageSize < 1 {
		return 50
	}
	if pageSize > 1000 {
		return 1000
	}
	return pageSize
}

func playerTeamQueryCacheKey(name, uname, idu string) string {
	return strings.Join([]string{strings.TrimSpace(name), strings.TrimSpace(uname), strings.TrimSpace(idu)}, "\x00")
}

func getCachedPlayerTeams(key string) ([]playerTeam, bool) {
	playerTeamQueryCache.Lock()
	defer playerTeamQueryCache.Unlock()

	if playerTeamQueryCache.entries == nil {
		return nil, false
	}

	elem, ok := playerTeamQueryCache.entries[key]
	if !ok {
		return nil, false
	}

	entry := elem.Value.(*playerTeamCacheEntry)
	if len(entry.teams) == 0 || time.Since(entry.createdAt) > playerTeamQueryCacheTTL {
		playerTeamQueryCache.order.Remove(elem)
		delete(playerTeamQueryCache.entries, key)
		return nil, false
	}

	playerTeamQueryCache.order.MoveToFront(elem)
	return append([]playerTeam(nil), entry.teams...), true
}

func setCachedPlayerTeams(key string, teams []playerTeam) {
	playerTeamQueryCache.Lock()
	defer playerTeamQueryCache.Unlock()

	if playerTeamQueryCache.entries == nil {
		playerTeamQueryCache.entries = make(map[string]*list.Element, playerTeamQueryCacheMaxSize)
		playerTeamQueryCache.order = list.New()
	}

	if elem, ok := playerTeamQueryCache.entries[key]; ok {
		playerTeamQueryCache.order.Remove(elem)
		delete(playerTeamQueryCache.entries, key)
	}

	if playerTeamQueryCache.order.Len() >= playerTeamQueryCacheMaxSize {
		oldest := playerTeamQueryCache.order.Back()
		if oldest != nil {
			oldEntry := oldest.Value.(*playerTeamCacheEntry)
			delete(playerTeamQueryCache.entries, oldEntry.key)
			playerTeamQueryCache.order.Remove(oldest)
		}
	}

	entry := &playerTeamCacheEntry{
		key:       key,
		createdAt: time.Now(),
		teams:     append([]playerTeam(nil), teams...),
	}
	elem := playerTeamQueryCache.order.PushFront(entry)
	playerTeamQueryCache.entries[key] = elem
}

func invalidatePlayerTeamQueryCache() {
	playerTeamQueryCache.Lock()
	defer playerTeamQueryCache.Unlock()

	playerTeamQueryCache.entries = make(map[string]*list.Element, playerTeamQueryCacheMaxSize)
	if playerTeamQueryCache.order != nil {
		playerTeamQueryCache.order.Init()
	} else {
		playerTeamQueryCache.order = list.New()
	}
}
