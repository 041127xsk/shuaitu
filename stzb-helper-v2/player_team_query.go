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

// MinTeamHeroLevel 是记录一支队伍时每名武将必须达到的最低等级（严格大于）。
//
// 满级武将为 50 级，30 级以上基本代表主力阵容。此前的门槛是 15 级，
// 会把大量练级中/炮灰队伍一起收进来，干扰队伍查询与胜率统计。
// 队伍查询、导出、胜率统计统一使用本常量，避免各处阈值不一致。
const MinTeamHeroLevel = 30

// minTeamHeroLevelCondition 生成某侧（attack/defend）三名武将的等级条件。
// 使用严格大于（> 30），要求三名武将全部达标。
func minTeamHeroLevelCondition(side string) string {
	return fmt.Sprintf(
		"%[1]s_hero1_level > %[2]d AND %[1]s_hero2_level > %[2]d AND %[1]s_hero3_level > %[2]d",
		side, MinTeamHeroLevel,
	)
}

// effectiveMinTeamHeroLevel 把调用方传入的等级阈值抬到不低于 MinTeamHeroLevel。
//
// 胜率查询的阈值来自前端表单，允许用户设置；但低于 30 的取值会把练级/炮灰队伍
// 一并纳入统计，与队伍查询、导出的口径不一致。这里统一兜底。
func effectiveMinTeamHeroLevel(requested int) int {
	if requested < MinTeamHeroLevel {
		return MinTeamHeroLevel
	}
	return requested
}

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

	// 用窗口函数在 SQL 层做去重，取代原来的 LIMIT 5000。
	//
	// 原实现 `ORDER BY time DESC LIMIT 5000` 是按时间硬截断：数据库积累到上万条
	// 战报后，排在 5000 名之后的老玩家虽然确有战报，却完全查不到（实测 909 个
	// 玩家受影响）。而去重逻辑本身（buildEffectivePlayerTeams）只保留每个玩家
	// 每种「三武将组合」的最新一条，所以真正需要的行数约等于玩家数 × 阵容数，
	// 远小于 5000。
	//
	// 这里按 (玩家, 角色, 三武将) 分区取 rn = 1 的最新记录，行数从 26960 降到
	// 约 2500，既消除漏查，又保留原来防 OOM 的意图。后续 Go 层仍会再做一次
	// 完整去重与「同玩家共享 2 武将」淘汰，行为不变。
	query := fmt.Sprintf(`
		WITH attack_pick AS (
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
				'' AS note,
				ROW_NUMBER() OVER (
					PARTITION BY attack_name, attack_hero1_id, attack_hero2_id, attack_hero3_id
					ORDER BY time DESC, battle_id DESC
				) AS rn
			FROM battle_report
			WHERE %s
		),
		defend_pick AS (
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
				'' AS note,
				ROW_NUMBER() OVER (
					PARTITION BY defend_name, defend_hero1_id, defend_hero2_id, defend_hero3_id
					ORDER BY time DESC, battle_id DESC
				) AS rn
			FROM battle_report
			WHERE %s
		)
		SELECT
			player_name, union_name, hero1_id, hero2_id, hero3_id,
			hero1_level, hero2_level, hero3_level,
			hero1_star, hero2_star, hero3_star, total_star,
			hp, gear, hero_type, idu, time, all_skill_info, battle_id,
			role, source_type, source_id, manual, note
		FROM attack_pick WHERE rn = 1
		UNION ALL
		SELECT
			player_name, union_name, hero1_id, hero2_id, hero3_id,
			hero1_level, hero2_level, hero3_level,
			hero1_star, hero2_star, hero3_star, total_star,
			hp, gear, hero_type, idu, time, all_skill_info, battle_id,
			role, source_type, source_id, manual, note
		FROM defend_pick WHERE rn = 1
		ORDER BY time DESC, battle_id DESC`,
		strings.Join(attackWhere, " AND "), strings.Join(defendWhere, " AND "))

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
		// 三名武将等级必须严格大于 MinTeamHeroLevel（> 30，不含 30 级）
		minTeamHeroLevelCondition(side),
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
	// 只有 3 个武将，改用栈上数组：原实现每次调用都在堆上分配 1 个 map + 1 个 slice，
	// 一次全量比对要分配上百万次。语义与原来完全一致（仍遍历 b、仍跳过 id==0）。
	aHeroes := [3]int{a.Hero1ID, a.Hero2ID, a.Hero3ID}
	bHeroes := [3]int{b.Hero1ID, b.Hero2ID, b.Hero3ID}
	count := 0
	for _, id := range bHeroes {
		if id == 0 {
			continue
		}
		if id == aHeroes[0] || id == aHeroes[1] || id == aHeroes[2] {
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
