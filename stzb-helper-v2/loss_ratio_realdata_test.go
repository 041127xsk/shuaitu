package main

// 真实数据验证：仅在本机存在测试库时运行，否则跳过。
// 用 go test -run TestRealDataLossRatio -v 手动触发。

import (
	"os"
	"sort"
	"testing"

	"stzbHelper/model"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

const realTestDB = `E:\openclaw\openclaw-main\stzb-helper-v2\build\bin\小池.db`

func openRealDB(t *testing.T) func() {
	t.Helper()
	if _, err := os.Stat(realTestDB); err != nil {
		t.Skipf("测试库不存在，跳过真实数据验证: %v", err)
	}
	db, err := gorm.Open(sqlite.Open(realTestDB+"?cache=shared&mode=ro"), &gorm.Config{})
	if err != nil {
		t.Fatalf("打开数据库失败: %v", err)
	}
	prev := model.Conn
	model.Conn = db
	return func() { model.Conn = prev }
}

// 用真实库跑一遍战损统计，检查结果是否符合业务常识。
func TestRealDataLossRatio(t *testing.T) {
	cleanup := openRealDB(t)
	defer cleanup()

	stats, err := queryTeamLossStats(MinTeamHeroLevel)
	if err != nil {
		t.Fatalf("queryTeamLossStats 失败: %v", err)
	}
	if len(stats) == 0 {
		t.Fatal("没有任何队伍参与战损统计，门槛可能过严或数据为空")
	}

	var totalOur, totalEnemy int64
	var zeroBattle, zeroOurLost int
	type entry struct {
		key   string
		our   int64
		enemy int64
		n     int64
		ratio float64
	}
	var entries []entry

	for k, s := range stats {
		if s.Battles == 0 {
			zeroBattle++
			continue
		}
		if s.OurLost == 0 {
			zeroOurLost++
		}
		totalOur += s.OurLost
		totalEnemy += s.EnemyLost
		entries = append(entries, entry{k, s.OurLost, s.EnemyLost, s.Battles,
			computeLossRatio(s.OurLost, s.EnemyLost)})
	}

	t.Logf("参与统计的队伍: %d 支（其中场次为 0 的异常 %d 支，我方无损 %d 支）",
		len(stats), zeroBattle, zeroOurLost)

	if zeroBattle > 0 {
		t.Errorf("存在 %d 支队伍场次为 0，说明聚合逻辑有误", zeroBattle)
	}

	// 每支队伍的战损不应超过其总兵力。这里用「战损比极端值」做间接检查：
	// 门槛已保证双方兵力 > 20000，若比值超过 50 说明门槛没生效。
	over50 := 0
	for _, e := range entries {
		if e.ratio > 50 {
			over50++
			if over50 <= 3 {
				t.Logf("  异常高比值: %s 场次=%d 我方战损=%d 对方战损=%d 比值=%.2f",
					e.key, e.n, e.our, e.enemy, e.ratio)
			}
		}
	}
	if over50 > 0 {
		t.Errorf("有 %d 支队伍战损比 > 50，双方兵力门槛可能未生效", over50)
	}

	if totalOur > 0 {
		weighted := float64(totalEnemy) / float64(totalOur)
		t.Logf("加权战损比（全体队伍累加）: %.2f", weighted)
		if weighted < 0.1 || weighted > 10 {
			t.Errorf("整体加权战损比 %.2f 明显异常，远超合理范围 [0.1, 10]", weighted)
		}
	}

	// 展示场次最多的几支队伍，便于人工核对
	sort.Slice(entries, func(i, j int) bool { return entries[i].n > entries[j].n })
	show := 8
	if len(entries) < show {
		show = len(entries)
	}
	t.Log("场次最多的队伍:")
	for i := 0; i < show; i++ {
		e := entries[i]
		t.Logf("  %-18s 场次=%-5d 我方战损=%-8d 对方战损=%-8d 战损比=%.2f",
			e.key, e.n, e.our, e.enemy, e.ratio)
	}
}
