package main

import (
	"fmt"
	"path/filepath"
	"sort"
	"stzbHelper/model"
	"testing"

	"gorm.io/gorm"
)

const equivSkill = "1,10,10,11,10,12,10;2,20,10,21,10,22,10;3,30,10,31,10,32,10"

// equivReports 构造覆盖各种组合的战报：
// Npc=0 与 Npc!=0、攻击方命中与防守方命中、同一条战报两边都命中（去重）、完全无关。
// 目的是证明「查询加了 npc = 0 并拆成两次」之后，产出的快照与改动前完全一致。
func equivReports() []model.BattleReport {
	mk := func(id int64, npc int64, atk, def string, h1 int64) model.BattleReport {
		return model.BattleReport{
			BattleId: id, Time: id * 10, Npc: npc,
			AttackName: atk, AttackUnionName: "盟A", AttackIdu: fmt.Sprintf("A%d", id),
			AttackHero1Id: h1, AttackHero2Id: 2, AttackHero3Id: 3,
			AttackHero1Level: 45, AttackHero2Level: 45, AttackHero3Level: 45,
			AttackHp: 25000,
			DefendName: def, DefendUnionName: "盟B", DefendIdu: fmt.Sprintf("D%d", id),
			DefendHero1Id: 4, DefendHero2Id: 5, DefendHero3Id: 6,
			DefendHero1Level: 45, DefendHero2Level: 45, DefendHero3Level: 45,
			DefendHp:     24000,
			AllSkillInfo: equivSkill,
		}
	}
	return []model.BattleReport{
		mk(1, 0, "甲", "乙", 1), // Npc=0，甲为攻击方
		mk(2, 0, "乙", "甲", 7), // Npc=0，甲为防守方
		mk(3, 1, "甲", "丙", 1), // Npc!=0，应被新查询过滤，且对快照无贡献
		mk(4, 0, "甲", "甲", 9), // 同一条战报两边都命中 → 验证去重
		mk(5, 0, "丁", "戊", 1), // 完全无关
		mk(6, 2, "甲", "己", 1), // Npc!=0 再一条
	}
}

// legacyQuerySnapshots 复刻改动前的查询逻辑：不带 npc 条件、OR 合并、ORDER BY battle_id。
func legacyQuerySnapshots(t *testing.T, tx *gorm.DB, players []string) []model.PlayerTeamSnapshot {
	var reports []model.BattleReport
	if err := tx.Where("attack_name IN ? OR defend_name IN ?", players, players).
		Order("battle_id ASC").Find(&reports).Error; err != nil {
		t.Fatal(err)
	}
	playerSet := map[string]bool{}
	for _, p := range players {
		playerSet[p] = true
	}
	all := buildMaterializedPlayerTeamSnapshots(reports)
	out := make([]model.PlayerTeamSnapshot, 0, len(all))
	for _, s := range all {
		if playerSet[s.PlayerName] {
			out = append(out, s)
		}
	}
	return out
}

// snapshotKey 提取除 ID（自增）与 SourceUpdatedAt（当前时间戳）之外的全部业务字段。
func snapshotKey(s model.PlayerTeamSnapshot) string {
	return fmt.Sprintf("%s|%s|%s|%s|%d,%d,%d|%d,%d,%d|%d,%d,%d|%d|%d|%s|%s|%s|%d|%d|%s|%s",
		s.PlayerName, s.UnionName, s.Role, s.Idu,
		s.Hero1ID, s.Hero2ID, s.Hero3ID,
		s.Hero1Level, s.Hero2Level, s.Hero3Level,
		s.Hero1Star, s.Hero2Star, s.Hero3Star,
		s.TotalStar, s.Hp, s.AllSkillInfo, s.Gear, s.HeroType,
		s.LastTime, s.LastBattleID, s.LineupKey, s.NormalizedSkillKey)
}

func snapshotKeys(list []model.PlayerTeamSnapshot) []string {
	out := make([]string, 0, len(list))
	for _, s := range list {
		out = append(out, snapshotKey(s))
	}
	sort.Strings(out)
	return out
}

// TestRefreshSnapshotsForPlayersMatchesLegacyQuery 是查询优化的安全网：
// 只要这个测试通过，就说明「加 npc=0 + 拆两次查询」没有改变任何业务结果。
func TestRefreshSnapshotsForPlayersMatchesLegacyQuery(t *testing.T) {
	model.InitDB(filepath.Join(t.TempDir(), "equiv.db"))
	if model.Conn == nil {
		t.Fatal("数据库未初始化")
	}
	// 关闭连接，否则 t.TempDir() 清理时数据库文件仍被占用、删不掉
	if sqlDB, err := model.Conn.DB(); err == nil {
		defer sqlDB.Close()
	}

	if err := model.Conn.CreateInBatches(equivReports(), 50).Error; err != nil {
		t.Fatal(err)
	}

	players := []string{"甲", "乙"}

	// 改动前的逻辑
	legacy := snapshotKeys(legacyQuerySnapshots(t, model.Conn, players))

	// 改动后的逻辑（会写库）
	if err := model.Conn.Transaction(func(tx *gorm.DB) error {
		return refreshSnapshotsForPlayers(tx, players)
	}); err != nil {
		t.Fatal(err)
	}
	var got []model.PlayerTeamSnapshot
	if err := model.Conn.Where("player_name IN ?", players).Find(&got).Error; err != nil {
		t.Fatal(err)
	}
	current := snapshotKeys(got)

	if len(legacy) != len(current) {
		t.Fatalf("快照条数不一致：改动前 %d 条，改动后 %d 条\n改动前: %v\n改动后: %v",
			len(legacy), len(current), legacy, current)
	}
	for i := range legacy {
		if legacy[i] != current[i] {
			t.Fatalf("第 %d 条快照不一致\n改动前: %s\n改动后: %s", i, legacy[i], current[i])
		}
	}
	t.Logf("等价性验证通过：%d 条快照与改动前逐字段完全一致", len(current))
}
