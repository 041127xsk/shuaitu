package main

import (
	"fmt"
	"strconv"
	"strings"
	"stzbHelper/model"
)

type relatedBattle struct {
	BattleID          int64  `json:"battle_id"`
	Time              int64  `json:"time"`
	Role              string `json:"role"`
	ResultLabel       string `json:"result_label"`
	OpponentName      string `json:"opponent_name"`
	OpponentUnionName string `json:"opponent_union_name"`
	AttackHp          int64  `json:"attack_hp"`
	DefendHp          int64  `json:"defend_hp"`
	AllSkillInfo      string `json:"all_skill_info"`

	// 本场逐武将明细战损
	AttackHeroes []heroLossDetail `json:"attack_heroes"`
	DefendHeroes []heroLossDetail `json:"defend_heroes"`

	// 按 role 折算成本方视角的汇总。LossRatio = 对方战损 / 我方战损，
	// 战损 = 伤兵 + 死兵（当场被打掉的全部兵力）。
	OurLostHp      int64   `json:"our_lost_hp"`
	EnemyLostHp    int64   `json:"enemy_lost_hp"`
	OurWoundedHp   int64   `json:"our_wounded_hp"`
	EnemyWoundedHp int64   `json:"enemy_wounded_hp"`
	OurKilledHp    int64   `json:"our_killed_hp"`
	EnemyKilledHp  int64   `json:"enemy_killed_hp"`
	LossRatio      float64 `json:"loss_ratio"`

	// CountedInLossRatio 表示本场是否满足战损比门槛（双方开战兵力均 > 20000）。
	// 不满足的场次仍然展示，但明确标注「不参与累计战损比统计」，避免用户
	// 拿弹窗里的明细自己加总却对不上表格里的战损比。
	CountedInLossRatio bool `json:"counted_in_loss_ratio"`
}

// heroLossDetail 是单个武将在一场战斗里的兵力变化。
//
// 原始报文 attack_all_hero_info = "武将ID,等级,开战兵力,剩余兵力,死兵;..."
// 伤兵由「开战 - 剩余 - 死兵」算出（报文没有单独字段）。
// 战损 = 开战 - 剩余 = 伤兵 + 死兵，恒 <= 开战兵力。
type heroLossDetail struct {
	HeroID   int64 `json:"hero_id"`
	Level    int64 `json:"level"`
	TotalHp  int64 `json:"total_hp"`  // 开战兵力（第3位）
	RemainHp int64 `json:"remain_hp"` // 战后剩余（第4位）
	Wounded  int64 `json:"wounded"`   // 伤兵 = 开战 - 剩余 - 死兵
	Killed   int64 `json:"killed"`    // 死兵（第5位）
	LostHp   int64 `json:"lost_hp"`   // 战损 = 伤兵 + 死兵 = 开战 - 剩余

	WoundedRate float64 `json:"wounded_rate"` // 伤兵 / 开战兵力
	LossRatio   float64 `json:"loss_ratio"`   // 损耗率 = 战损 / 开战兵力
	Anomaly     bool    `json:"anomaly"`      // 脏数据（开战 < 剩余+死兵），伤兵按 0 兜底
}

// parseHeroLossDetails 逐武将解析 all_hero_info。
// 全 0 的武将（NPC / 空报文）直接跳过，避免明细里出现一堆 0 行。
func parseHeroLossDetails(info string) []heroLossDetail {
	info = strings.TrimSpace(info)
	if info == "" {
		return nil
	}
	details := make([]heroLossDetail, 0, 3)
	for _, chunk := range strings.Split(strings.Trim(info, ";"), ";") {
		fields := strings.Split(strings.TrimSpace(chunk), ",")
		if len(fields) < 5 {
			continue
		}
		heroID, err := strconv.ParseInt(strings.TrimSpace(fields[0]), 10, 64)
		if err != nil || heroID == 0 {
			continue
		}
		level, _ := strconv.ParseInt(strings.TrimSpace(fields[1]), 10, 64)
		total, err1 := strconv.ParseInt(strings.TrimSpace(fields[2]), 10, 64)
		remain, err2 := strconv.ParseInt(strings.TrimSpace(fields[3]), 10, 64)
		killed, err3 := strconv.ParseInt(strings.TrimSpace(fields[4]), 10, 64)
		if err1 != nil || err2 != nil || err3 != nil {
			continue
		}
		if total < 0 || remain < 0 || killed < 0 {
			continue
		}

		anomaly := false
		if remain > total {
			// 剩余不可能超过开战兵力，脏数据按满编处理
			remain = total
			anomaly = true
		}
		wounded := total - remain - killed
		if wounded < 0 {
			// 理论不该发生；按 0 兜底并标记异常，不静默吞掉
			wounded = 0
			anomaly = true
		}
		lost := wounded + killed

		d := heroLossDetail{
			HeroID:   heroID,
			Level:    level,
			TotalHp:  total,
			RemainHp: remain,
			Wounded:  wounded,
			Killed:   killed,
			LostHp:   lost,
			Anomaly:  anomaly,
		}
		if total > 0 {
			d.WoundedRate = float64(wounded) / float64(total)
			d.LossRatio = float64(lost) / float64(total)
		}
		details = append(details, d)
	}
	return details
}

// sumLostHp 汇总一队三武将的战损（伤+死）。
func sumLostHp(details []heroLossDetail) int64 {
	var lost int64
	for _, d := range details {
		lost += d.LostHp
	}
	return lost
}

// sumHp 汇总三武将的指定字段（开战兵力 / 伤兵 / 死兵）。
func sumHp(details []heroLossDetail, pick func(heroLossDetail) int64) int64 {
	var total int64
	for _, d := range details {
		total += pick(d)
	}
	return total
}

// queryRelatedBattles 查询某支队伍参与过的原始战报。
//
// 匹配口径（三条都必须满足，缺一不可，否则会把同名不同阵容的战报混进来）：
//  1. 三武将 ID 完全一致；
//  2. 玩家名一致（playerName 为空时不限玩家，用于「按队伍组合」这种跨玩家口径）；
//  3. role 为空时攻守两侧都查，否则只查指定一侧。
//
// idu 只是「尽力精确」的条件：idu 是每场战斗都会变的复合串（形如
// "57303482,477588,477552,477543,0"），玩家重新登录后同一支队伍就会换一个 idu。
// 早先把它当成硬条件，只要快照里的 idu 落后于最新战报，整支队伍的战报就查不出来，
// 表现正是「点了战报没有任何结果」。现在先按 idu 精确匹配，查空则自动放宽到只按
// 阵容 + 玩家名匹配，保证历史战报一定能展开。
func queryRelatedBattles(playerName, role, idu string, hero1ID, hero2ID, hero3ID, page, pageSize int) ([]relatedBattle, int64, error) {
	if model.Conn == nil {
		return nil, 0, fmt.Errorf("请先选择数据库")
	}
	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}

	name := strings.TrimSpace(playerName)
	iduTrim := strings.TrimSpace(idu)

	// sideCondition 生成单侧（攻方或守方）的匹配条件。
	sideCondition := func(side string, withIdu bool) (string, []interface{}) {
		sql := fmt.Sprintf("(%[1]s_hero1_id = ? AND %[1]s_hero2_id = ? AND %[1]s_hero3_id = ?)", side)
		args := []interface{}{hero1ID, hero2ID, hero3ID}
		if name != "" {
			sql += fmt.Sprintf(" AND %s_name = ?", side)
			args = append(args, name)
		}
		if withIdu && iduTrim != "" {
			sql += fmt.Sprintf(" AND %s_idu = ?", side)
			args = append(args, iduTrim)
		}
		return sql, args
	}

	buildWhere := func(withIdu bool) (string, []interface{}) {
		switch role {
		case "attack":
			return sideCondition("attack", withIdu)
		case "defend":
			return sideCondition("defend", withIdu)
		default:
			attackSQL, attackArgs := sideCondition("attack", withIdu)
			defendSQL, defendArgs := sideCondition("defend", withIdu)
			return "(" + attackSQL + " OR " + defendSQL + ")", append(attackArgs, defendArgs...)
		}
	}

	fetch := func(where string, args []interface{}) ([]relatedBattle, int64, error) {
		var total int64
		if err := model.Conn.Model(&model.BattleReport{}).Where("npc = 0 AND "+where, args...).Count(&total).Error; err != nil {
			return nil, 0, err
		}
		if total == 0 {
			return []relatedBattle{}, 0, nil
		}
		var reports []model.BattleReport
		if err := model.Conn.Where("npc = 0 AND "+where, args...).
			Order("time DESC, battle_id DESC").
			Limit(pageSize).
			Offset((page - 1) * pageSize).
			Find(&reports).Error; err != nil {
			return nil, 0, err
		}

		rows := make([]relatedBattle, 0, len(reports))
		for _, report := range reports {
			// 未指定 role 时按「这一场里我们站哪边」逐条推断。
			rowRole := role
			if rowRole != "attack" && rowRole != "defend" {
				if report.AttackHero1Id == int64(hero1ID) &&
					report.AttackHero2Id == int64(hero2ID) &&
					report.AttackHero3Id == int64(hero3ID) {
					rowRole = "attack"
				} else {
					rowRole = "defend"
				}
			}
			row := relatedBattle{
				BattleID:     report.BattleId,
				Time:         report.Time,
				Role:         rowRole,
				ResultLabel:  battleResultLabel(report.Result, rowRole),
				AttackHp:     report.AttackHp,
				DefendHp:     report.DefendHp,
				AllSkillInfo: report.AllSkillInfo,
				AttackHeroes: parseHeroLossDetails(report.AttackAllHeroInfo),
				DefendHeroes: parseHeroLossDetails(report.DefendAllHeroInfo),
			}
			if rowRole == "defend" {
				row.OpponentName = report.AttackName
				row.OpponentUnionName = report.AttackUnionName
				row.OurLostHp = sumLostHp(row.DefendHeroes)
				row.EnemyLostHp = sumLostHp(row.AttackHeroes)
				row.OurWoundedHp = sumHp(row.DefendHeroes, func(d heroLossDetail) int64 { return d.Wounded })
				row.EnemyWoundedHp = sumHp(row.AttackHeroes, func(d heroLossDetail) int64 { return d.Wounded })
				row.OurKilledHp = sumHp(row.DefendHeroes, func(d heroLossDetail) int64 { return d.Killed })
				row.EnemyKilledHp = sumHp(row.AttackHeroes, func(d heroLossDetail) int64 { return d.Killed })
			} else {
				row.OpponentName = report.DefendName
				row.OpponentUnionName = report.DefendUnionName
				row.OurLostHp = sumLostHp(row.AttackHeroes)
				row.EnemyLostHp = sumLostHp(row.DefendHeroes)
				row.OurWoundedHp = sumHp(row.AttackHeroes, func(d heroLossDetail) int64 { return d.Wounded })
				row.EnemyWoundedHp = sumHp(row.DefendHeroes, func(d heroLossDetail) int64 { return d.Wounded })
				row.OurKilledHp = sumHp(row.AttackHeroes, func(d heroLossDetail) int64 { return d.Killed })
				row.EnemyKilledHp = sumHp(row.DefendHeroes, func(d heroLossDetail) int64 { return d.Killed })
			}
			row.LossRatio = computeLossRatio(row.OurLostHp, row.EnemyLostHp)
			// 与累计战损比同一口径：双方开战兵力都 > 20000 才计入统计。
			// 明细仍然展示（用户要看全量），但标注清楚哪些场次没被计入。
			ourTotal := sumHp(row.AttackHeroes, func(d heroLossDetail) int64 { return d.TotalHp })
			enemyTotal := sumHp(row.DefendHeroes, func(d heroLossDetail) int64 { return d.TotalHp })
			row.CountedInLossRatio = ourTotal > MinLossRatioHpThreshold && enemyTotal > MinLossRatioHpThreshold
			rows = append(rows, row)
		}
		return rows, total, nil
	}

	where, args := buildWhere(true)
	rows, total, err := fetch(where, args)
	if err != nil {
		return nil, 0, err
	}
	if total == 0 && iduTrim != "" {
		where, args = buildWhere(false)
		rows, total, err = fetch(where, args)
		if err != nil {
			return nil, 0, err
		}
	}
	// 指定了玩家名仍查空时，退一步只按阵容查（玩家改名/名字里带空格等情况）。
	if total == 0 && name != "" {
		name, iduTrim = "", ""
		where, args = buildWhere(false)
		rows, total, err = fetch(where, args)
		if err != nil {
			return nil, 0, err
		}
	}
	return rows, total, nil
}

func battleResultLabel(result int64, role string) string {
	win, loss, draw := resultCounts(result, role)
	if draw > 0 {
		return "平"
	}
	if win > 0 {
		return "胜"
	}
	if loss > 0 {
		return "负"
	}
	return "未知"
}
