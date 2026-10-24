package main

// 回归：损耗率必须 <= 100%，且「按玩家」口径要精确到 玩家+阵容。
//
// 历史 bug（已修）：queryTeamLossStats 只按三武将聚合，而同一阵容全库有
// 几十上百个玩家在用。player 模式下战损取自全库 786 场、页面那一行只代表
// 该玩家的 10 场，且攻守两侧都按「本方视角」重复计入 —— 实测 646 支队伍里
// 609 支损耗率超过 100%（最高 287%）。
//
// 现在聚合键是「玩家名 + 三武将」，与派生表「玩家 + 阵容」一行一一对应。

import (
	"os"
	"testing"

	"stzbHelper/model"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

const reproDB = `E:\openclaw\openclaw-main\stzb-helper-v2\build\bin\小池.db`

func openReproDB(t *testing.T) {
	t.Helper()
	if _, err := os.Stat(reproDB); err != nil {
		t.Skipf("库不存在: %v", err)
	}
	db, err := gorm.Open(sqlite.Open(reproDB+"?cache=shared&mode=ro"), &gorm.Config{})
	if err != nil {
		t.Fatalf("打开库失败: %v", err)
	}
	prev := model.Conn
	model.Conn = db
	t.Cleanup(func() { model.Conn = prev })
}

// 截图里那三支队伍：修复前 146.5% / 199.8% / 144.2%
func TestLossRateNeverExceedsOne(t *testing.T) {
	openReproDB(t)

	stats, err := queryTeamLossStats(effectiveMinTeamHeroLevel(defaultWinRateMinLevel))
	if err != nil {
		t.Fatalf("战损统计失败: %v", err)
	}
	if len(stats) == 0 {
		t.Fatal("没有任何战损统计")
	}

	over := 0
	maxRate := 0.0
	var maxKey string
	for key, ls := range stats {
		if ls.OurTotalHp <= 0 {
			continue
		}
		if ls.OurLost > ls.OurTotalHp {
			t.Fatalf("战损(%d) 超过开战兵力(%d)：%s", ls.OurLost, ls.OurTotalHp, key)
		}
		rate := float64(ls.OurLost) / float64(ls.OurTotalHp)
		if rate > maxRate {
			maxRate, maxKey = rate, key
		}
		if rate > 1 {
			over++
			t.Errorf("超过 100%%: %s 场次=%d 战损=%d 开战=%d rate=%.1f%%",
				key, ls.Battles, ls.OurLost, ls.OurTotalHp, rate*100)
		}
	}
	t.Logf("共 %d 条「玩家+阵容」统计，最高损耗率 %.1f%%（%s），超 100%% 的 %d 条",
		len(stats), maxRate*100, maxKey, over)
}

// 同一阵容下，不同玩家必须算出不同的战损（证明 key 带了玩家名）
func TestLossStatsKeyIncludesPlayer(t *testing.T) {
	openReproDB(t)

	stats, err := queryTeamLossStats(effectiveMinTeamHeroLevel(defaultWinRateMinLevel))
	if err != nil {
		t.Fatalf("战损统计失败: %v", err)
	}

	// 找一个被多个玩家使用的热门阵容
	byLineup := map[string][]*teamLossStat{}
	for _, ls := range stats {
		k := teamLossKey("", ls.Hero1ID, ls.Hero2ID, ls.Hero3ID)
		byLineup[k] = append(byLineup[k], ls)
	}

	found := false
	for k, list := range byLineup {
		if len(list) < 3 {
			continue
		}
		found = true
		// 每个元素的 PlayerName 必须非空且互不相同
		seen := map[string]bool{}
		for _, ls := range list {
			if ls.PlayerName == "" {
				t.Fatalf("阵容 %s 的战损统计缺少玩家名", k)
			}
			if seen[ls.PlayerName] {
				t.Fatalf("阵容 %s 出现重复玩家 %s，聚合键可能没带玩家名", k, ls.PlayerName)
			}
			seen[ls.PlayerName] = true
		}
		// 明细战损不应完全相同（若 key 没带玩家名，全库会只有一条）
		distinct := map[int64]bool{}
		for _, ls := range list {
			distinct[ls.OurLost] = true
		}
		if len(distinct) == 1 && len(list) > 5 {
			t.Errorf("阵容 %s 的 %d 个玩家战损完全相同(%d)，聚合口径可疑",
				k, len(list), list[0].OurLost)
		}
		t.Logf("阵容 %s 有 %d 个玩家各自独立的战损统计", k, len(list))
		break
	}
	if !found {
		t.Skip("没有找到被 3 个以上玩家使用的阵容")
	}
}

// 「按队伍」口径跨玩家聚合后，损耗率同样不能超过 100%
func TestAggregateLossByLineupBounded(t *testing.T) {
	openReproDB(t)

	stats, err := queryTeamLossStats(effectiveMinTeamHeroLevel(defaultWinRateMinLevel))
	if err != nil {
		t.Fatalf("战损统计失败: %v", err)
	}

	checked := 0
	for _, ls := range stats {
		agg := aggregateLossByLineup(stats, ls.Hero1ID, ls.Hero2ID, ls.Hero3ID)
		if agg == nil || agg.OurTotalHp <= 0 {
			continue
		}
		if agg.OurLost > agg.OurTotalHp {
			t.Fatalf("阵容聚合后战损(%d) 超过开战(%d)", agg.OurLost, agg.OurTotalHp)
		}
		rate := float64(agg.OurLost) / float64(agg.OurTotalHp)
		if rate > 1 {
			t.Fatalf("阵容 %d_%d_%d 聚合损耗率 %.1f%% 超过 100%%",
				ls.Hero1ID, ls.Hero2ID, ls.Hero3ID, rate*100)
		}
		checked++
		if checked >= 50 {
			break
		}
	}
	t.Logf("校验 %d 个阵容的跨玩家聚合损耗率，全部 <= 100%%", checked)
}

// 打印截图里三支队伍修复后的实际数值
func TestShowFixedValues(t *testing.T) {
	openReproDB(t)
	stats, err := queryTeamLossStats(effectiveMinTeamHeroLevel(defaultWinRateMinLevel))
	if err != nil {
		t.Fatalf("战损统计失败: %v", err)
	}
	targets := []struct {
		h1, h2, h3 int64
		before     string
	}{
		{100035, 100707, 100783, "146.5%"},
		{100794, 100771, 100474, "199.8%"},
		{100683, 100692, 100645, "144.2%"},
	}
	for _, tg := range targets {
		key := teamLossKey("歌丨小池", tg.h1, tg.h2, tg.h3)
		ls, ok := stats[key]
		if !ok {
			t.Logf("阵容 %d_%d_%d: 无统计", tg.h1, tg.h2, tg.h3)
			continue
		}
		rate := computeDestroyedRate(ls.OurLost, ls.OurTotalHp)
		t.Logf("阵容 %d_%d_%d: 场次=%d 战损=%d 开战=%d → 损耗率=%.1f%%  (修复前 %s)",
			tg.h1, tg.h2, tg.h3, ls.Battles, ls.OurLost, ls.OurTotalHp, rate*100, tg.before)
	}
}
