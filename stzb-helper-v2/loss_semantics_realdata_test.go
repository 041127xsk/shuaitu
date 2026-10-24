package main

// 战损口径回归：净战损只算死兵（伤兵可恢复）。
//
// 用真实库验证三件事：
//  1. 单场明细里 净战损 == 死兵，且 总损 == 伤兵 + 死兵
//  2. 明细的 counted_in_loss_ratio 与「双方开战兵力 > 20000」一致
//  3. 累计损耗率 = 我方累计死兵 / 我方累计开战兵力，且不含伤兵

import (
	"os"
	"testing"

	"stzbHelper/model"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

const dbForLossSemantics = `E:\openclaw\openclaw-main\stzb-helper-v2\build\bin\小池.db`

func TestRealDataLossSemantics(t *testing.T) {
	if _, err := os.Stat(dbForLossSemantics); err != nil {
		t.Skipf("库不存在: %v", err)
	}
	db, err := gorm.Open(sqlite.Open(dbForLossSemantics+"?cache=shared&mode=ro"), &gorm.Config{})
	if err != nil {
		t.Fatalf("打开库失败: %v", err)
	}
	prev := model.Conn
	model.Conn = db
	defer func() { model.Conn = prev }()

	teams, _, err := queryEffectivePlayerTeamsWithMeta("", "", "")
	if err != nil {
		t.Fatalf("队伍查询失败: %v", err)
	}

	checkedRows := 0
	withWounded := 0
	counted := 0
	notCounted := 0

	for i, team := range teams {
		if i >= 5 {
			break
		}
		rows, n, err := queryRelatedBattles(team.PlayerName, team.Role, team.Idu,
			team.Hero1ID, team.Hero2ID, team.Hero3ID, 1, 100)
		if err != nil {
			t.Errorf("%s 查询失败: %v", team.PlayerName, err)
			continue
		}
		t.Logf("%s role=%s 阵容=%d_%d_%d → %d 条战报",
			team.PlayerName, team.Role, team.Hero1ID, team.Hero2ID, team.Hero3ID, n)

		for _, row := range rows {
			checkedRows++

			// 1. 明细层恒等式：剩余 + 伤兵 + 死兵 == 开战；战损 == 开战 - 剩余
			for _, side := range [][]heroLossDetail{row.AttackHeroes, row.DefendHeroes} {
				for _, h := range side {
					if h.RemainHp+h.Wounded+h.Killed != h.TotalHp {
						t.Fatalf("剩余(%d)+伤(%d)+死(%d) != 开战(%d)",
							h.RemainHp, h.Wounded, h.Killed, h.TotalHp)
					}
					if h.LostHp != h.TotalHp-h.RemainHp {
						t.Fatalf("战损(%d) != 开战(%d)-剩余(%d)", h.LostHp, h.TotalHp, h.RemainHp)
					}
					if h.Wounded < 0 {
						t.Fatalf("伤兵出现负数: %d", h.Wounded)
					}
					if h.Anomaly {
						t.Fatalf("真实数据出现被标记的异常武将: %+v", h)
					}
				}
			}

			// 2. 汇总层：我方/对方战损应与逐武将战损之和一致，且 = 伤+死
			var atkLost, defLost int64
			for _, h := range row.AttackHeroes {
				atkLost += h.LostHp
			}
			for _, h := range row.DefendHeroes {
				defLost += h.LostHp
			}
			if row.Role == "defend" {
				if row.OurLostHp != defLost || row.EnemyLostHp != atkLost {
					t.Fatalf("守方视角战损错位: our=%d(want %d) enemy=%d(want %d)",
						row.OurLostHp, defLost, row.EnemyLostHp, atkLost)
				}
			} else {
				if row.OurLostHp != atkLost || row.EnemyLostHp != defLost {
					t.Fatalf("攻方视角战损错位: our=%d(want %d) enemy=%d(want %d)",
						row.OurLostHp, atkLost, row.EnemyLostHp, defLost)
				}
			}
			if row.OurLostHp != row.OurWoundedHp+row.OurKilledHp {
				t.Fatalf("我方战损(%d) != 伤(%d)+死(%d)", row.OurLostHp, row.OurWoundedHp, row.OurKilledHp)
			}

			// 3. 门槛标注
			var atkTotal, defTotal int64
			for _, h := range row.AttackHeroes {
				atkTotal += h.TotalHp
			}
			for _, h := range row.DefendHeroes {
				defTotal += h.TotalHp
			}
			wantCounted := atkTotal > MinLossRatioHpThreshold && defTotal > MinLossRatioHpThreshold
			if row.CountedInLossRatio != wantCounted {
				t.Fatalf("counted_in_loss_ratio=%v，但双方兵力 %d/%d，应=%v",
					row.CountedInLossRatio, atkTotal, defTotal, wantCounted)
			}
			if wantCounted {
				counted++
			} else {
				notCounted++
			}

			if row.OurWoundedHp > 0 || row.EnemyWoundedHp > 0 {
				withWounded++
			}
		}
	}

	t.Logf("校验 %d 条战报：计入战损比 %d 条，未计入 %d 条，有伤兵 %d 条",
		checkedRows, counted, notCounted, withWounded)
	if checkedRows == 0 {
		t.Fatal("没有取到任何战报，无法验证")
	}
	if counted == 0 {
		t.Error("没有任何场次被计入战损比，门槛可能失效")
	}
}

// 累计损耗率：分母是累计开战兵力，分子是累计战损（伤+死），因此必然 <= 1。
func TestTeamLossStatsLossRate(t *testing.T) {
	if _, err := os.Stat(dbForLossSemantics); err != nil {
		t.Skipf("库不存在: %v", err)
	}
	db, err := gorm.Open(sqlite.Open(dbForLossSemantics+"?cache=shared&mode=ro"), &gorm.Config{})
	if err != nil {
		t.Fatalf("打开库失败: %v", err)
	}
	prev := model.Conn
	model.Conn = db
	defer func() { model.Conn = prev }()

	stats, err := queryTeamLossStats(effectiveMinTeamHeroLevel(defaultWinRateMinLevel))
	if err != nil {
		t.Fatalf("战损统计失败: %v", err)
	}
	if len(stats) == 0 {
		t.Fatal("没有任何队伍的累计战损")
	}

	overOne := 0
	checked := 0
	maxRate := 0.0
	for _, ls := range stats {
		if ls.Battles == 0 || ls.OurTotalHp == 0 {
			continue
		}
		checked++
		if ls.OurLost > ls.OurTotalHp {
			t.Fatalf("累计战损(%d) 超过累计开战兵力(%d)", ls.OurLost, ls.OurTotalHp)
		}
		if ls.OurLost != ls.OurWounded+ls.OurKilled {
			t.Fatalf("战损(%d) != 伤(%d)+死(%d)", ls.OurLost, ls.OurWounded, ls.OurKilled)
		}
		rate := float64(ls.OurLost) / float64(ls.OurTotalHp)
		if rate > maxRate {
			maxRate = rate
		}
		if rate > 1 {
			overOne++
		}
	}
	if overOne > 0 {
		t.Errorf("%d 支队伍的损耗率超过 100%%，分母口径有误", overOne)
	}
	t.Logf("校验 %d 支队伍，最高累计损耗率 %.1f%%（应为 <= 100%%）", checked, maxRate*100)
	if maxRate <= 0 {
		t.Error("损耗率全为 0，统计可能没跑起来")
	}

	var ourLost, ourWounded, ourKilled, ourHp int64
	for _, ls := range stats {
		ourLost += ls.OurLost
		ourWounded += ls.OurWounded
		ourKilled += ls.OurKilled
		ourHp += ls.OurTotalHp
	}
	t.Logf("全库累计：战损(伤+死)=%d（伤 %d / 死 %d），开战兵力=%d，整体损耗率 %.1f%%",
		ourLost, ourWounded, ourKilled, ourHp, float64(ourLost)/float64(ourHp)*100)
	if ourWounded == 0 {
		t.Error("伤兵累计为 0，伤兵字段可能没被采集")
	}
	if ourLost != ourWounded+ourKilled {
		t.Error("全库战损不等于伤+死，口径不一致")
	}
}
