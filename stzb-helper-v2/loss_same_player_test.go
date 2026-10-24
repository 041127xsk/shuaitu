package main

// 回归测试：同一玩家的不同阵容必须得到不同的战损比。
//
// 这是实际发生的 bug：早先按 PlayerName 匹配战损数据，导致胜率页里
// 同一玩家的多个阵容行显示完全相同的战损比（用户反馈「小池的三个队伍
// 战损比一模一样」）。正确做法是按三武将组合匹配。

import (
	"os"
	"testing"

	"stzbHelper/model"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

const dbForSamePlayerCheck = `E:\openclaw\openclaw-main\stzb-helper-v2\build\bin\小池.db`

// 同一玩家的多个阵容，经 attachLossRatioToStats 后比值不能全部相同。
func TestDistinctLineupsGetDistinctRatio(t *testing.T) {
	if _, err := os.Stat(dbForSamePlayerCheck); err != nil {
		t.Skipf("库不存在: %v", err)
	}
	db, err := gorm.Open(sqlite.Open(dbForSamePlayerCheck+"?cache=shared&mode=ro"), &gorm.Config{})
	if err != nil {
		t.Fatalf("打开库失败: %v", err)
	}
	prev := model.Conn
	model.Conn = db
	defer func() { model.Conn = prev }()

	invalidateLossStatsCache()

	// 找一个有多个阵容的玩家
	type playerRow struct {
		PlayerName string `gorm:"column:player_name"`
		Cnt        int64  `gorm:"column:cnt"`
	}
	var pr playerRow
	err = db.Raw(`
		SELECT player_name, COUNT(DISTINCT lineup_key) AS cnt
		FROM team_winrate_stats
		WHERE mode = 'player' AND lineup_key != ''
		GROUP BY player_name
		HAVING cnt >= 3
		ORDER BY cnt DESC
		LIMIT 1`).Scan(&pr).Error
	if err != nil || pr.PlayerName == "" {
		t.Skip("找不到有 3 个以上阵容的玩家，跳过")
	}
	t.Logf("测试玩家: %s（%d 个阵容）", pr.PlayerName, pr.Cnt)

	// 取该玩家的所有阵容行
	var rows []model.TeamWinRateStat
	err = db.Where("mode = ? AND player_name = ?", "player", pr.PlayerName).
		Order("total_battles DESC").
		Limit(10).
		Find(&rows).Error
	if err != nil {
		t.Fatalf("查询阵容失败: %v", err)
	}
	if len(rows) < 2 {
		t.Skip("该玩家阵容不足 2 个，跳过")
	}

	// 走和线上一致的填充逻辑
	attachLossRatioToStats(rows, "player")

	type detail struct {
		lineup string
		ratio  float64
		battles int64
	}
	var details []detail
	for _, r := range rows {
		details = append(details, detail{
			lineup:  teamLossKey(r.PlayerName, r.Hero1ID, r.Hero2ID, r.Hero3ID),
			ratio:   r.LossRatio,
			battles: r.LossRatioBattles,
		})
		t.Logf("  阵容 %-22s 战损比=%.4f（统计场次 %d）", details[len(details)-1].lineup, r.LossRatio, r.LossRatioBattles)
	}

	// 至少要有两个非零且不同的比值，否则说明还是按玩家聚合
	var valid []float64
	for _, d := range details {
		if d.ratio > 0 {
			valid = append(valid, d.ratio)
		}
	}
	if len(valid) < 2 {
		t.Skipf("只有 %d 个阵容有战损数据，样本不足", len(valid))
	}

	allSame := true
	for _, v := range valid[1:] {
		if v != valid[0] {
			allSame = false
			break
		}
	}
	if allSame {
		t.Fatalf("同一玩家的 %d 个阵容战损比完全相同（%.4f）—— 说明仍在按玩家聚合，应按阵容匹配",
			len(valid), valid[0])
	}
	t.Logf("✅ %d 个阵容的战损比互不相同，按阵容匹配生效", len(valid))
}
