package main

// 独立验证战损比：不信任被测代码，直接读原始报文手算，再与函数结果对比。
//
// 战损比 = 对方战损 / 我方战损（>1 我方赚）
// 战损 = 伤兵 + 死兵 = 开战 - 剩余

import (
	"os"
	"strconv"
	"strings"
	"testing"

	"stzbHelper/model"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

const verifyDB = `E:\openclaw\openclaw-main\stzb-helper-v2\build\bin\小池.db`

// 独立实现：从原始报文手算单侧战损，不复用 parseHeroLossInfo
func manualLost(info string) (total, lost int64, ok bool) {
	info = strings.TrimSpace(info)
	if info == "" {
		return 0, 0, false
	}
	for _, chunk := range strings.Split(strings.Trim(info, ";"), ";") {
		f := strings.Split(strings.TrimSpace(chunk), ",")
		if len(f) < 5 {
			continue
		}
		hid, e1 := strconv.ParseInt(f[0], 10, 64)
		tot, e2 := strconv.ParseInt(f[2], 10, 64)
		rem, e3 := strconv.ParseInt(f[3], 10, 64)
		kil, e4 := strconv.ParseInt(f[4], 10, 64)
		if e1 != nil || e2 != nil || e3 != nil || e4 != nil || hid == 0 {
			continue
		}
		if rem > tot {
			rem = tot
		}
		wounded := tot - rem - kil
		if wounded < 0 {
			wounded = 0
		}
		total += tot
		lost += wounded + kil
		ok = true
	}
	return total, lost, ok
}

func TestVerifyLossRatioAgainstRawData(t *testing.T) {
	if _, err := os.Stat(verifyDB); err != nil {
		t.Skipf("库不存在: %v", err)
	}
	db, err := gorm.Open(sqlite.Open(verifyDB+"?cache=shared&mode=ro"), &gorm.Config{})
	if err != nil {
		t.Fatalf("打开库失败: %v", err)
	}
	prev := model.Conn
	model.Conn = db
	defer func() { model.Conn = prev }()

	// 取一批双方兵力都够大的真实战报
	var reports []model.BattleReport
	if err := db.Where("npc = 0 AND attack_hp > ? AND defend_hp > ? AND attack_all_hero_info != '' AND defend_all_hero_info != ''",
		MinLossRatioHpThreshold, MinLossRatioHpThreshold).
		Order("time DESC").Limit(200).Find(&reports).Error; err != nil {
		t.Fatalf("取战报失败: %v", err)
	}
	if len(reports) == 0 {
		t.Skip("没有可用战报")
	}
	t.Logf("取到 %d 条战报用于核对", len(reports))

	checked := 0
	for _, r := range reports {
		atkTotal, atkLost, atkOK := manualLost(r.AttackAllHeroInfo)
		defTotal, defLost, defOK := manualLost(r.DefendAllHeroInfo)
		if !atkOK || !defOK {
			continue
		}
		_ = atkTotal
		_ = defTotal

		// ---- 攻方视角：我方=攻方 ----
		rows, _, err := queryRelatedBattles(r.AttackName, "attack", r.AttackIdu,
			int(r.AttackHero1Id), int(r.AttackHero2Id), int(r.AttackHero3Id), 1, 5)
		if err != nil {
			continue
		}
		var hit *relatedBattle
		for i := range rows {
			if rows[i].BattleID == r.BattleId {
				hit = &rows[i]
				break
			}
		}
		if hit != nil {
			if hit.OurLostHp != atkLost {
				t.Fatalf("battle %d 攻方视角 OurLostHp=%d, 手算=%d", r.BattleId, hit.OurLostHp, atkLost)
			}
			if hit.EnemyLostHp != defLost {
				t.Fatalf("battle %d 攻方视角 EnemyLostHp=%d, 手算=%d", r.BattleId, hit.EnemyLostHp, defLost)
			}
			// 我方战损为 0 时函数按约定返回 0（表示无法计算），不产生 +Inf
			want := 0.0
			if atkLost > 0 {
				want = float64(defLost) / float64(atkLost)
			}
			if diff(hit.LossRatio, want) > 1e-9 {
				t.Fatalf("battle %d 攻方战损比=%.4f, 手算=%.4f", r.BattleId, hit.LossRatio, want)
			}
			checked++
		}

		// ---- 守方视角：我方=守方，比值应互为倒数 ----
		rowsD, _, err := queryRelatedBattles(r.DefendName, "defend", r.DefendIdu,
			int(r.DefendHero1Id), int(r.DefendHero2Id), int(r.DefendHero3Id), 1, 5)
		if err != nil {
			continue
		}
		var hitD *relatedBattle
		for i := range rowsD {
			if rowsD[i].BattleID == r.BattleId {
				hitD = &rowsD[i]
				break
			}
		}
		if hitD != nil {
			if hitD.OurLostHp != defLost {
				t.Fatalf("battle %d 守方视角 OurLostHp=%d, 手算=%d", r.BattleId, hitD.OurLostHp, defLost)
			}
			if hitD.EnemyLostHp != atkLost {
				t.Fatalf("battle %d 守方视角 EnemyLostHp=%d, 手算=%d", r.BattleId, hitD.EnemyLostHp, atkLost)
			}
			wantD := 0.0
			if defLost > 0 {
				wantD = float64(atkLost) / float64(defLost)
			}
			if diff(hitD.LossRatio, wantD) > 1e-9 {
				t.Fatalf("battle %d 守方战损比=%.4f, 手算=%.4f", r.BattleId, hitD.LossRatio, wantD)
			}
			// 攻守两侧的战损比互为倒数
			if hit != nil && hit.LossRatio > 0 && hitD.LossRatio > 0 {
				if diff(hit.LossRatio*hitD.LossRatio, 1.0) > 1e-6 {
					t.Fatalf("battle %d 攻守战损比不互为倒数: %.4f * %.4f = %.6f",
						r.BattleId, hit.LossRatio, hitD.LossRatio, hit.LossRatio*hitD.LossRatio)
				}
			}
			checked++
		}
	}
	t.Logf("核对 %d 个视角，战损比与手算全部一致（攻守互为倒数）", checked)
	if checked == 0 {
		t.Fatal("没有核对到任何数据")
	}
}

func diff(a, b float64) float64 {
	if a > b {
		return a - b
	}
	return b - a
}

// 累计口径：战损比 = 对方累计战损 / 我方累计战损
func TestVerifyAggregatedLossRatio(t *testing.T) {
	if _, err := os.Stat(verifyDB); err != nil {
		t.Skipf("库不存在: %v", err)
	}
	db, err := gorm.Open(sqlite.Open(verifyDB+"?cache=shared&mode=ro"), &gorm.Config{})
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

	checked := 0
	var sumOur, sumEnemy int64
	for _, ls := range stats {
		if ls.OurLost <= 0 {
			continue
		}
		// 1. 汇总值必须等于「伤+死」
		if ls.OurLost != ls.OurWounded+ls.OurKilled {
			t.Fatalf("%s|%d_%d_%d OurLost(%d) != Wounded(%d)+Killed(%d)",
				ls.PlayerName, ls.Hero1ID, ls.Hero2ID, ls.Hero3ID,
				ls.OurLost, ls.OurWounded, ls.OurKilled)
		}
		// 2. 战损不能超过累计开战兵力
		if ls.OurLost > ls.OurTotalHp {
			t.Fatalf("%s OurLost(%d) > OurTotalHp(%d)", ls.PlayerName, ls.OurLost, ls.OurTotalHp)
		}
		if ls.EnemyLost > ls.EnemyTotalHp {
			t.Fatalf("%s EnemyLost(%d) > EnemyTotalHp(%d)", ls.PlayerName, ls.EnemyLost, ls.EnemyTotalHp)
		}
		// 3. 战损比 = EnemyLost / OurLost
		got := computeLossRatio(ls.OurLost, ls.EnemyLost)
		want := float64(ls.EnemyLost) / float64(ls.OurLost)
		if diff(got, want) > 1e-9 {
			t.Fatalf("%s 战损比=%.6f, want %.6f", ls.PlayerName, got, want)
		}
		sumOur += ls.OurLost
		sumEnemy += ls.EnemyLost
		checked++
	}
	t.Logf("核对 %d 条累计记录；全库累计 我方战损=%d 对方战损=%d 整体战损比=%.4f",
		checked, sumOur, sumEnemy, float64(sumEnemy)/float64(sumOur))

	// 4. 战损比不受「100%」上限约束（它本来就是比值，可以 > 1）
	over := 0
	for _, ls := range stats {
		if ls.OurLost > 0 && computeLossRatio(ls.OurLost, ls.EnemyLost) > 1 {
			over++
		}
	}
	t.Logf("战损比 > 1（我方赚）的记录: %d / %d", over, len(stats))
	if over == 0 {
		t.Log("提示：没有一条 > 1，样本可能偏向吃亏")
	}
}
