package main

// 排查并回归「队伍查询 / 胜率查询展开战报」：
// 用和线上完全一致的查询条件跑真实数据，覆盖三种入口
//  1. 队伍查询（玩家 + 攻守角色 + idu + 阵容）
//  2. 胜率查询-按玩家（同上）
//  3. 胜率查询-按队伍组合（只按阵容，跨玩家）
//
// 以及 idu 漂移（玩家重登后 idu 变了）时必须能自动放宽匹配。

import (
	"os"
	"testing"

	"stzbHelper/model"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

const dbForRelated = `E:\openclaw\openclaw-main\stzb-helper-v2\build\bin\小池.db`

func openRelatedTestDB(t *testing.T) {
	t.Helper()
	if _, err := os.Stat(dbForRelated); err != nil {
		t.Skipf("库不存在: %v", err)
	}
	db, err := gorm.Open(sqlite.Open(dbForRelated+"?cache=shared&mode=ro"), &gorm.Config{})
	if err != nil {
		t.Fatalf("打开库失败: %v", err)
	}
	prev := model.Conn
	model.Conn = db
	t.Cleanup(func() { model.Conn = prev })
}

func TestRelatedBattlesRealData(t *testing.T) {
	openRelatedTestDB(t)

	teams, _, err := queryEffectivePlayerTeamsWithMeta("", "", "")
	if err != nil {
		t.Fatalf("队伍查询失败: %v", err)
	}
	t.Logf("队伍查询返回 %d 支", len(teams))
	if len(teams) == 0 {
		t.Fatal("队伍查询一条都查不到")
	}

	withData, without := 0, 0
	for i, team := range teams {
		if i >= 10 {
			break
		}
		list, n, err := queryRelatedBattles(team.PlayerName, team.Role, team.Idu,
			team.Hero1ID, team.Hero2ID, team.Hero3ID, 1, 20)
		if err != nil {
			t.Errorf("  [%d] %s role=%s 查询报错: %v", i, team.PlayerName, team.Role, err)
			continue
		}
		if n > 0 {
			withData++
			if i == 0 {
				t.Logf("  示例队伍: %s role=%s 阵容=%d_%d_%d 战报=%d 条",
					team.PlayerName, team.Role, team.Hero1ID, team.Hero2ID, team.Hero3ID, n)
				if len(list) > 0 {
					b := list[0]
					t.Logf("    最新一条: battle_id=%d 对手=%s 结果=%s",
						b.BattleID, b.OpponentName, b.ResultLabel)
				}
			}
		} else {
			without++
			t.Logf("  [无结果] %s role=%s idu=%q 阵容=%d_%d_%d",
				team.PlayerName, team.Role, team.Idu, team.Hero1ID, team.Hero2ID, team.Hero3ID)
		}
	}
	t.Logf("队伍查询展开战报抽样 10 支: 有数据 %d 支，无数据 %d 支", withData, without)
	if withData == 0 && without > 0 {
		t.Errorf("抽样全部查不到战报，说明展开战报功能存在系统性问题")
	}
}

// 胜率页两种口径都要能展开战报。
func TestRelatedBattlesForWinRateRows(t *testing.T) {
	openRelatedTestDB(t)

	// 按玩家
	playerPage, used, err := queryMaterializedWinRateStats("player", "", "", "", 1, 20, effectiveMinTeamHeroLevel(defaultWinRateMinLevel), defaultWinRateMinHp)
	if err != nil {
		t.Fatalf("按玩家胜率查询失败: %v", err)
	}
	if !used {
		t.Skip("统计索引未就绪，跳过")
	}
	playerRows, _ := playerPage["list"].([]model.TeamWinRateStat)
	if len(playerRows) == 0 {
		t.Fatal("按玩家胜率没有数据")
	}
	miss := 0
	for _, row := range playerRows {
		_, n, err := queryRelatedBattles(row.PlayerName, row.Role, row.Idu,
			int(row.Hero1ID), int(row.Hero2ID), int(row.Hero3ID), 1, 20)
		if err != nil {
			t.Errorf("按玩家 %s 查询报错: %v", row.PlayerName, err)
			continue
		}
		if n == 0 {
			miss++
			t.Logf("  [按玩家无结果] %s role=%s idu=%q 阵容=%d_%d_%d",
				row.PlayerName, row.Role, row.Idu, row.Hero1ID, row.Hero2ID, row.Hero3ID)
		}
	}
	t.Logf("按玩家 %d 行: 查空 %d 行", len(playerRows), miss)
	if miss > 0 {
		t.Errorf("按玩家口径有 %d 行展开战报查空", miss)
	}

	// 按队伍组合：只有一个阵容、没有具体玩家
	teamPage, used, err := queryMaterializedWinRateStats("team", "", "", "", 1, 20, effectiveMinTeamHeroLevel(defaultWinRateMinLevel), defaultWinRateMinHp)
	if err != nil {
		t.Fatalf("按队伍胜率查询失败: %v", err)
	}
	if !used {
		t.Skip("统计索引未就绪，跳过")
	}
	teamRows, _ := teamPage["list"].([]model.TeamWinRateStat)
	if len(teamRows) == 0 {
		t.Fatal("按队伍胜率没有数据")
	}
	miss = 0
	for _, row := range teamRows {
		_, n, err := queryRelatedBattles("", "", "",
			int(row.Hero1ID), int(row.Hero2ID), int(row.Hero3ID), 1, 20)
		if err != nil {
			t.Errorf("按队伍 %d_%d_%d 查询报错: %v", row.Hero1ID, row.Hero2ID, row.Hero3ID, err)
			continue
		}
		if n == 0 {
			miss++
			t.Logf("  [按队伍无结果] 阵容=%d_%d_%d", row.Hero1ID, row.Hero2ID, row.Hero3ID)
		}
	}
	t.Logf("按队伍 %d 行: 查空 %d 行", len(teamRows), miss)
	if miss > 0 {
		t.Errorf("按队伍口径有 %d 行展开战报查空", miss)
	}
}

// idu 漂移（玩家重登后复合 idu 变化）时必须自动放宽匹配，不能返回空。
func TestRelatedBattlesStaleIduFallback(t *testing.T) {
	openRelatedTestDB(t)

	var report model.BattleReport
	if err := model.Conn.Where("npc = 0 AND attack_hero1_id != 0 AND attack_hero2_id != 0 AND attack_hero3_id != 0").
		Order("time DESC").First(&report).Error; err != nil {
		t.Fatalf("取一条战报失败: %v", err)
	}

	// 正常 idu 能查到
	base, n, err := queryRelatedBattles(report.AttackName, "attack", report.AttackIdu,
		int(report.AttackHero1Id), int(report.AttackHero2Id), int(report.AttackHero3Id), 1, 20)
	if err != nil {
		t.Fatalf("正常查询失败: %v", err)
	}
	if n == 0 {
		t.Fatalf("正常 idu 也查不到战报: %s", report.AttackName)
	}
	t.Logf("%s 阵容 %d_%d_%d 正常 idu 查到 %d 条",
		report.AttackName, report.AttackHero1Id, report.AttackHero2Id, report.AttackHero3Id, n)

	// 过期 idu（模拟重登后的旧复合串）必须回退到阵容匹配，而不是返回空
	stale, n2, err := queryRelatedBattles(report.AttackName, "attack", "1,2,3,4,0",
		int(report.AttackHero1Id), int(report.AttackHero2Id), int(report.AttackHero3Id), 1, 20)
	if err != nil {
		t.Fatalf("过期 idu 查询失败: %v", err)
	}
	if n2 == 0 {
		t.Errorf("过期 idu 查空，未回退到阵容匹配（正是「点战报没结果」的根因）")
	}
	if len(stale) > 0 && len(base) > 0 && stale[0].BattleID != base[0].BattleID {
		t.Logf("回退结果最新一条 battle_id=%d，精确匹配最新=%d", stale[0].BattleID, base[0].BattleID)
	}
	t.Logf("过期 idu 回退后查到 %d 条", n2)

	// 角色留空时应能覆盖攻守两侧
	both, nb, err := queryRelatedBattles(report.AttackName, "", report.AttackIdu,
		int(report.AttackHero1Id), int(report.AttackHero2Id), int(report.AttackHero3Id), 1, 20)
	if err != nil {
		t.Fatalf("双方口径查询失败: %v", err)
	}
	if nb < n {
		t.Errorf("角色留空查到 %d 条，少于只查攻方的 %d 条", nb, n)
	}
	for _, row := range both {
		if row.Role != "attack" && row.Role != "defend" {
			t.Errorf("角色推断异常: %q", row.Role)
		}
	}
	t.Logf("角色留空（攻守都查）查到 %d 条", nb)
}
