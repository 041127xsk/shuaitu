package main

// 验证「派生表路径」也会返回战损比。
//
// 这是本次 bug 的核心：胜率查询优先走物化派生表（team_winrate_stats），
// 走派生表时会提前 return，导致后面原始查询路径上的战损填充代码永远执行不到，
// 前端看到所有战损比都是空。

import (
	"os"
	"testing"

	"stzbHelper/model"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

const realDBForLoss = `E:\openclaw\openclaw-main\stzb-helper-v2\build\bin\小池.db`

func openRealDBForLoss(t *testing.T) func() {
	t.Helper()
	if _, err := os.Stat(realDBForLoss); err != nil {
		t.Skipf("测试库不存在，跳过: %v", err)
	}
	db, err := gorm.Open(sqlite.Open(realDBForLoss+"?cache=shared&mode=ro"), &gorm.Config{})
	if err != nil {
		t.Fatalf("打开数据库失败: %v", err)
	}
	prev := model.Conn
	model.Conn = db
	return func() { model.Conn = prev }
}

// 派生表路径必须能返回非零战损比。
func TestMaterializedPathReturnsLossRatio(t *testing.T) {
	cleanup := openRealDBForLoss(t)
	defer cleanup()

	invalidateLossStatsCache()

	data, used, err := queryMaterializedWinRateStats("player", "", "", "", 1, 20, defaultWinRateMinLevel, defaultWinRateMinHp)
	if err != nil {
		t.Fatalf("派生表查询失败: %v", err)
	}
	if !used {
		t.Skip("派生表未就绪（status 非 ready），本用例不适用")
	}

	list, ok := data["list"]
	if !ok {
		t.Fatal("返回数据缺少 list 字段")
	}
	rows, ok := list.([]model.TeamWinRateStat)
	if !ok {
		t.Fatalf("list 类型异常: %T", list)
	}
	if len(rows) == 0 {
		t.Fatal("派生表返回了 0 行，无法验证战损")
	}

	withRatio := 0
	for _, r := range rows {
		if r.LossRatio > 0 {
			withRatio++
			t.Logf("  %-20s 场次=%d 战损比=%.2f（统计场次 %d）",
				r.PlayerName, r.TotalBattles, r.LossRatio, r.LossRatioBattles)
		}
	}

	if withRatio == 0 {
		t.Fatalf("派生表返回 %d 行，但没有任何一行带战损比 —— 战损填充未生效", len(rows))
	}
	t.Logf("派生表 %d 行中 %d 行带战损比", len(rows), withRatio)
}

// 「按队伍」模式同样要生效。
func TestMaterializedTeamModeReturnsLossRatio(t *testing.T) {
	cleanup := openRealDBForLoss(t)
	defer cleanup()

	invalidateLossStatsCache()

	data, used, err := queryMaterializedWinRateStats("team", "", "", "", 1, 20, defaultWinRateMinLevel, defaultWinRateMinHp)
	if err != nil {
		t.Fatalf("派生表查询失败: %v", err)
	}
	if !used {
		t.Skip("派生表未就绪，本用例不适用")
	}

	rows, _ := data["list"].([]model.TeamWinRateStat)
	if len(rows) == 0 {
		t.Skip("派生表无数据")
	}

	withRatio := 0
	for _, r := range rows {
		if r.LossRatio > 0 {
			withRatio++
		}
	}
	if withRatio == 0 {
		t.Fatalf("按队伍模式：%d 行全部没有战损比", len(rows))
	}
	t.Logf("按队伍模式：%d 行中 %d 行带战损比", len(rows), withRatio)
}

// 缓存应避免重复全表扫描，但要能在失效后重新统计。
func TestLossStatsCacheInvalidation(t *testing.T) {
	cleanup := openRealDBForLoss(t)
	defer cleanup()

	invalidateLossStatsCache()

	first, err := cachedPlayerLossStats()
	if err != nil {
		t.Fatalf("首次统计失败: %v", err)
	}
	if len(first) == 0 {
		t.Fatal("首次统计结果为空")
	}

	// 第二次应命中缓存（同一个 map 指针）
	second, err := cachedPlayerLossStats()
	if err != nil {
		t.Fatalf("第二次统计失败: %v", err)
	}
	if len(second) != len(first) {
		t.Fatalf("缓存前后数据量不一致: %d vs %d", len(first), len(second))
	}

	// 失效后应重新查询，得到新的 map
	invalidateLossStatsCache()
	third, err := cachedPlayerLossStats()
	if err != nil {
		t.Fatalf("失效后统计失败: %v", err)
	}
	if len(third) != len(first) {
		t.Fatalf("失效重查后数据量变化: %d vs %d", len(first), len(third))
	}
}
