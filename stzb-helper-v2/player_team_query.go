package main

import (
	"container/list"
	"fmt"
	"log"
	"sort"
	"strconv"
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

// MinLossRatioHpThreshold 是参与战损统计的双方兵力下限（严格大于）。
//
// 战损比和损耗率**都**用这个门槛：两者分子分母都取自同一批场次，
// 保证「表格上的战损比」和「表格上的损耗率」是同一口径算出来的，
// 不会出现一个数包含小规模接触、另一个不包含的错位。
//
// 完美克制（兵种/战法压制）下，一方可能只带几十兵打对方两万多兵，此时我方战损
// 极小、比值被极端放大（实测最高 591 倍），会严重稀释真实战力对比。
// 实测：无门槛时胜局平均战损比 2.39，加 20000 门槛后回落到 1.63，
// 且可用场次仍有 35%（10463/29782），样本量足够。
const MinLossRatioHpThreshold = 20000

// 战损相关：all_hero_info 字段格式为
//
//	"武将ID,等级,开战兵力,剩余兵力,死兵;..."
//
// **字段语义（用全库 21549 场 / 114611 个武将实例验证）：**
//
//	第 3 位 = 开战兵力   三名武将之和恒等于该侧 *_hp（39620/39620 = 100%）
//	第 4 位 = 战后剩余兵力
//	第 5 位 = 死兵
//	伤兵   = 开战 - 剩余 - 死兵   （报文里没有单独字段，必须算出来）
//
// 验证依据：
//   - 「剩余(第4) + 死兵(第5) ≤ 开战(第3)」无一条违例，且 82.47% 严格小于
//     （差值就是伤兵；若第4位是伤兵，这个差值就没有对应量了）。
//   - 同一武将继续两场：下一场开战兵力 == 上一场第4位（命中率 32.85%，
//     是所有候选假设里最高的）；上一场剩多少，下一场就带多少。
//   - 第4位 == 开战兵力的「零损失」占 17.53%（剩余等于开战很自然）；
//     第5位 == 开战兵力出现 0 次。
//   - 第4/第5 位从不大于第3位（剩余和死兵都不可能超过开战兵力）。
//
// **损耗口径：战损 = 开战 - 剩余 = 伤兵 + 死兵。**
//
// 打完之后剩下的是剩余兵力，其余全部是本场损耗。伤兵战后虽然能恢复，
// 但这一场确实被打掉了，属于「当场损失」，计入损耗率与战损比。
// 于是恒有 战损 <= 开战，累计损耗率必然 <= 100%。

// heroLossInfo 是单侧（进攻方或防守方）的兵力与战损合计。
type heroLossInfo struct {
	TotalHp  int64 // 开战总兵力
	RemainHp int64 // 战后剩余兵力
	Wounded  int64 // 伤兵 = 开战 - 剩余 - 死兵
	Killed   int64 // 死兵（第5位）
	LostHp   int64 // 战损 = 伤兵 + 死兵 = 开战 - 剩余
	Anomaly  bool  // 出现「开战 < 剩余 + 死兵」的脏数据，已按 0 兜底
	Valid    bool  // 数据是否可用
}

// parseHeroLossInfo 从 all_hero_info 文本解析出该侧的开战兵力、剩余与战损。
//
// 伤兵由「开战 - 剩余 - 死兵」算出。理论上不会为负（全库实测 0 次违例），
// 一旦为负说明报文格式变了或数据脏了：按 0 兜底并置 Anomaly，同时打日志，
// 不静默吞掉，避免数字悄悄算错。
// 全部武将 ID 为 0（NPC 或空数据）时返回 Valid=false，调用方应跳过该场战报。
func parseHeroLossInfo(info string) heroLossInfo {
	info = strings.TrimSpace(info)
	if info == "" {
		return heroLossInfo{}
	}

	var result heroLossInfo
	for _, chunk := range strings.Split(strings.Trim(info, ";"), ";") {
		fields := strings.Split(strings.TrimSpace(chunk), ",")
		if len(fields) < 5 {
			continue
		}
		heroID, err := strconv.ParseInt(strings.TrimSpace(fields[0]), 10, 64)
		if err != nil || heroID == 0 {
			continue
		}
		total, err1 := strconv.ParseInt(strings.TrimSpace(fields[2]), 10, 64)
		remain, err2 := strconv.ParseInt(strings.TrimSpace(fields[3]), 10, 64)
		killed, err3 := strconv.ParseInt(strings.TrimSpace(fields[4]), 10, 64)
		if err1 != nil || err2 != nil || err3 != nil {
			continue
		}
		if total < 0 || remain < 0 || killed < 0 {
			continue
		}
		if remain > total {
			// 剩余不可能超过开战兵力；脏数据按满编剩余处理（本场无损失）
			remain = total
			result.Anomaly = true
		}
		result.TotalHp += total
		result.RemainHp += remain
		result.Killed += killed
		result.Valid = true
	}

	if result.TotalHp <= 0 {
		// 解析出全 0 数据（NPC/空报文），视为不可用
		return heroLossInfo{}
	}

	// 伤兵 = 开战 - 剩余 - 死兵。恒 >= 0 才对，为负说明数据异常。
	wounded := result.TotalHp - result.RemainHp - result.Killed
	if wounded < 0 {
		result.Anomaly = true
		log.Printf("[战损异常] 开战(%d) < 剩余(%d) + 死兵(%d)，伤兵按 0 兜底",
			result.TotalHp, result.RemainHp, result.Killed)
		wounded = 0
	}
	result.Wounded = wounded
	// 战损 = 伤兵 + 死兵 = 开战 - 剩余（两者等价，用前者保证与展示一致）
	result.LostHp = result.Wounded + result.Killed
	return result
}

// LossRatio 按「先累加、后相除」的口径计算战损比 = 对方战损 / 我方战损。
//
// 返回 0 表示无法计算（我方战损为 0 或数据不可用）。比值 > 1 为我方赚。
//
// 注意参数顺序是 (我方, 对方)，返回值是 对方/我方 —— 名字容易看反，
// 计算「损耗率」请用下面的 computeDestroyedRate，不要复用本函数。
func computeLossRatio(ourLost, enemyLost int64) float64 {
	if ourLost <= 0 || enemyLost < 0 {
		return 0
	}
	return float64(enemyLost) / float64(ourLost)
}

// computeDestroyedRate 计算损耗率 = 我方累计战损 / 我方累计开战兵力。
//
// 结果是 0~1 的比值（不是百分数），物理上恒 <= 1：战损不可能超过开战兵力。
// 早先误用 computeLossRatio(ourLost, ourTotalHp)，把分母分子颠倒，
// 得到的是「开战/战损」（例如 2.39 = 239%），这是损耗率超过 100% 的直接原因。
func computeDestroyedRate(ourLost, ourTotalHp int64) float64 {
	if ourTotalHp <= 0 || ourLost < 0 {
		return 0
	}
	rate := float64(ourLost) / float64(ourTotalHp)
	if rate > 1 {
		// 防御性兜底：删数据/脏数据理论上不该出现，真出现也按满损处理
		return 1
	}
	return rate
}

// teamLossStat 是一支队伍的累计战损（按「玩家名 + 三武将」聚合）。
//
// OurLost / EnemyLost 是「当场被打掉」的累计兵力（伤兵 + 死兵），
// 用于战损比与损耗率；OurWounded 单独保留，用于展示其中多少能恢复。
type teamLossStat struct {
	PlayerName   string
	Hero1ID      int64
	Hero2ID      int64
	Hero3ID      int64
	OurLost      int64 // 我方累计战损（伤+死）
	EnemyLost    int64 // 对方累计战损（伤+死）
	OurWounded   int64 // 我方累计伤兵（可恢复部分）
	EnemyWounded int64 // 对方累计伤兵
	OurKilled    int64 // 我方累计死兵（永久损失）
	EnemyKilled  int64 // 对方累计死兵
	OurTotalHp   int64 // 我方累计开战兵力（损耗率分母）
	EnemyTotalHp int64 // 对方累计开战兵力
	Battles      int64
}

// queryTeamLossStats 统计每支队伍在「双方兵力都 > MinLossRatioHpThreshold」场次里的
// 累计战损，用于计算战损比与损耗率。
//
// **聚合键是「玩家名 + 三武将」，不是单独的三武将。**
//
// 这一点极其关键。派生表 team_winrate_stats 的每一行是「某玩家的某个阵容」，
// 而同一个阵容（如 100035_100707_100783）全库有 80+ 个玩家在用。早先只按三武将
// 聚合，导致损耗率的分子分母跨了所有玩家：
//   - 战损取自全库 786 场，但页面这一行只代表该玩家的 10 场；
//   - 更严重的是攻守两侧都按「本方视角」计入，同一批场次被算了两遍。
// 实测 646 支队伍里 609 支损耗率超过 100%（最高 287%），就是重复计入的直接后果。
//
// 单独查询而不并入胜率主查询，原因：
//   - 战损需要解析 all_hero_info 文本，SQLite 不擅长这种拆解，只能在 Go 层做；
//   - 主查询已经聚合过，拿不到逐场明细。这里按队伍键累加后再返回。
func queryTeamLossStats(minLevel int) (map[string]*teamLossStat, error) {
	if model.Conn == nil {
		return nil, fmt.Errorf("请先选择数据库")
	}

	// 攻守两个方向都取，统一成「本方视角」：own_hero_info / enemy_hero_info。
	// 每条战报只在「该玩家实际所处的那一侧」产生一行，不会两侧重复。
	query := `
		SELECT
			attack_name AS player_name,
			attack_hero1_id AS hero1_id,
			attack_hero2_id AS hero2_id,
			attack_hero3_id AS hero3_id,
			attack_all_hero_info AS own_info,
			defend_all_hero_info AS enemy_info
		FROM battle_report
		WHERE attack_hero1_id != 0 AND attack_hero2_id != 0 AND attack_hero3_id != 0
			AND attack_hero1_level > ? AND attack_hero2_level > ? AND attack_hero3_level > ?
			AND defend_hero1_id != 0 AND defend_hero2_id != 0 AND defend_hero3_id != 0
			AND attack_hp > ? AND defend_hp > ?
			AND npc = 0
			AND attack_name != ''
			AND attack_all_hero_info != '' AND defend_all_hero_info != ''
			AND attack_all_hero_info NOT LIKE '0,0,0,0,0%'
			AND defend_all_hero_info NOT LIKE '0,0,0,0,0%'
		UNION ALL
		SELECT
			defend_name AS player_name,
			defend_hero1_id AS hero1_id,
			defend_hero2_id AS hero2_id,
			defend_hero3_id AS hero3_id,
			defend_all_hero_info AS own_info,
			attack_all_hero_info AS enemy_info
		FROM battle_report
		WHERE defend_hero1_id != 0 AND defend_hero2_id != 0 AND defend_hero3_id != 0
			AND defend_hero1_level > ? AND defend_hero2_level > ? AND defend_hero3_level > ?
			AND attack_hero1_id != 0 AND attack_hero2_id != 0 AND attack_hero3_id != 0
			AND defend_hp > ? AND attack_hp > ?
			AND npc = 0
			AND defend_name != ''
			AND defend_all_hero_info != '' AND attack_all_hero_info != ''
			AND defend_all_hero_info NOT LIKE '0,0,0,0,0%'
			AND attack_all_hero_info NOT LIKE '0,0,0,0,0%'`

	thr := MinLossRatioHpThreshold
	args := []interface{}{
		minLevel, minLevel, minLevel, thr, thr,
		minLevel, minLevel, minLevel, thr, thr,
	}

	type rawRow struct {
		PlayerName string
		Hero1ID    int64
		Hero2ID    int64
		Hero3ID    int64
		OwnInfo    string
		EnemyInfo  string
	}
	var rows []rawRow
	if err := model.Conn.Raw(query, args...).Scan(&rows).Error; err != nil {
		return nil, err
	}

	stats := make(map[string]*teamLossStat, len(rows))
	for _, r := range rows {
		if r.PlayerName == "" {
			continue
		}
		// 二次校验：以 hero_info 解析出的兵力为准
		own := parseHeroLossInfo(r.OwnInfo)
		enemy := parseHeroLossInfo(r.EnemyInfo)
		if !own.Valid || !enemy.Valid {
			continue
		}
		if own.TotalHp <= MinLossRatioHpThreshold || enemy.TotalHp <= MinLossRatioHpThreshold {
			continue
		}

		key := teamLossKey(r.PlayerName, r.Hero1ID, r.Hero2ID, r.Hero3ID)
		acc := stats[key]
		if acc == nil {
			acc = &teamLossStat{
				PlayerName: r.PlayerName,
				Hero1ID:    r.Hero1ID,
				Hero2ID:    r.Hero2ID,
				Hero3ID:    r.Hero3ID,
			}
			stats[key] = acc
		}
		acc.OurLost += own.LostHp
		acc.EnemyLost += enemy.LostHp
		acc.OurWounded += own.Wounded
		acc.EnemyWounded += enemy.Wounded
		acc.OurKilled += own.Killed
		acc.EnemyKilled += enemy.Killed
		acc.OurTotalHp += own.TotalHp
		acc.EnemyTotalHp += enemy.TotalHp
		acc.Battles++
	}
	return stats, nil
}

// teamLossKey 生成队伍键：玩家名 + 三武将 ID（顺序固定，不改序）。
//
// 必须带上玩家名：同一个阵容有几十上百个玩家在用，只按三武将聚合会把
// 所有人的战损混在一起，导致单行数据的战损比/损耗率失真（实测 646 支里
// 609 支损耗率 > 100%）。带上玩家名后，与派生表「玩家 + 阵容」一行一一对应。
func teamLossKey(playerName string, h1, h2, h3 int64) string {
	return fmt.Sprintf("%s|%d_%d_%d", playerName, h1, h2, h3)
}

// playerLossStat 是一个玩家在其所有队伍上的累计战损（按玩家名聚合）。
type playerLossStat struct {
	OurLost      int64 // 我方累计战损（伤+死）
	EnemyLost    int64 // 对方累计战损（伤+死）
	OurWounded   int64 // 我方累计伤兵
	EnemyWounded int64 // 对方累计伤兵
	OurKilled    int64 // 我方累计死兵
	EnemyKilled  int64 // 对方累计死兵
	OurTotalHp   int64 // 我方累计开战兵力
	EnemyTotalHp int64 // 对方累计开战兵力
	Battles      int64
}

// queryPlayerLossStats 按玩家名聚合累计战损，口径与 queryTeamLossStats 完全一致：
// 只统计双方兵力都 > MinLossRatioHpThreshold 的场次，先累加后相除。
//
// 「按玩家」视图的分组键是 (player_name, 三武将)，一个玩家可能有多支队伍，
// 因此这里把所有队伍的战损汇总到玩家名下。
func queryPlayerLossStats(minLevel int) (map[string]*playerLossStat, error) {
	if model.Conn == nil {
		return nil, fmt.Errorf("请先选择数据库")
	}

	query := `
		SELECT attack_name AS player_name,
			attack_all_hero_info AS own_info,
			defend_all_hero_info AS enemy_info
		FROM battle_report
		WHERE attack_hero1_id != 0 AND attack_hero2_id != 0 AND attack_hero3_id != 0
			AND attack_hero1_level > ? AND attack_hero2_level > ? AND attack_hero3_level > ?
			AND defend_hero1_id != 0 AND defend_hero2_id != 0 AND defend_hero3_id != 0
			AND attack_hp > ? AND defend_hp > ?
			AND npc = 0
			AND attack_all_hero_info != '' AND defend_all_hero_info != ''
			AND attack_all_hero_info NOT LIKE '0,0,0,0,0%'
			AND defend_all_hero_info NOT LIKE '0,0,0,0,0%'
		UNION ALL
		SELECT defend_name AS player_name,
			defend_all_hero_info AS own_info,
			attack_all_hero_info AS enemy_info
		FROM battle_report
		WHERE defend_hero1_id != 0 AND defend_hero2_id != 0 AND defend_hero3_id != 0
			AND defend_hero1_level > ? AND defend_hero2_level > ? AND defend_hero3_level > ?
			AND attack_hero1_id != 0 AND attack_hero2_id != 0 AND attack_hero3_id != 0
			AND defend_hp > ? AND attack_hp > ?
			AND npc = 0
			AND defend_all_hero_info != '' AND attack_all_hero_info != ''
			AND defend_all_hero_info NOT LIKE '0,0,0,0,0%'
			AND attack_all_hero_info NOT LIKE '0,0,0,0,0%'`

	thr := MinLossRatioHpThreshold
	args := []interface{}{
		minLevel, minLevel, minLevel, thr, thr,
		minLevel, minLevel, minLevel, thr, thr,
	}

	type rawRow struct {
		PlayerName string
		OwnInfo    string
		EnemyInfo  string
	}
	var rows []rawRow
	if err := model.Conn.Raw(query, args...).Scan(&rows).Error; err != nil {
		return nil, err
	}

	stats := make(map[string]*playerLossStat, len(rows))
	for _, r := range rows {
		if r.PlayerName == "" {
			continue
		}
		own := parseHeroLossInfo(r.OwnInfo)
		enemy := parseHeroLossInfo(r.EnemyInfo)
		if !own.Valid || !enemy.Valid {
			continue
		}
		acc := stats[r.PlayerName]
		if acc == nil {
			acc = &playerLossStat{}
			stats[r.PlayerName] = acc
		}
		acc.OurLost += own.LostHp
		acc.EnemyLost += enemy.LostHp
		acc.OurWounded += own.Wounded
		acc.EnemyWounded += enemy.Wounded
		acc.OurKilled += own.Killed
		acc.EnemyKilled += enemy.Killed
		acc.OurTotalHp += own.TotalHp
		acc.EnemyTotalHp += enemy.TotalHp
		acc.Battles++
	}
	return stats, nil
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
