package model

import (
	"log"
	"strings"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

var Conn *gorm.DB

// InitDB 初始化数据库连接
// databasePath 可以是绝对路径或相对路径，可以带或不带 .db 后缀
func InitDB(databasePath string) {
	// 如果路径已经以 .db 结尾，就不再添加
	dsn := databasePath
	if !strings.HasSuffix(dsn, ".db") {
		dsn = dsn + ".db"
	}
	dsn = dsn + "?cache=shared&mode=rwc"
	// SQLite 需要正斜杠
	dsn = strings.ReplaceAll(dsn, "\\", "/")
	log.Println("正在连接数据库:", dsn)

	db, err := gorm.Open(sqlite.Open(dsn), &gorm.Config{})
	if err != nil {
		log.Println("连接数据库失败:", err)
		return
	}
	for _, sql := range []string{
		"PRAGMA busy_timeout = 5000",
		"PRAGMA journal_mode = WAL",
		"PRAGMA synchronous = NORMAL",
		"PRAGMA temp_store = MEMORY",
	} {
		if err := db.Exec(sql).Error; err != nil {
			log.Println("设置 SQLite 参数失败:", err)
		}
	}

	err = db.AutoMigrate(&TeamUser{}, &Task{}, &Report{}, &BattleReport{}, &PlayerTeamSnapshot{}, &TeamWinRateStat{}, &MaterializedState{}, &MaterializedTeamExclusion{})
	if err != nil {
		log.Println("数据库迁移失败:", err)
		return
	}

	// 为 battle_report 创建查询索引
	indexes := []string{
		"CREATE INDEX IF NOT EXISTS idx_br_attack_name ON battle_report(attack_name)",
		"CREATE INDEX IF NOT EXISTS idx_br_defend_name ON battle_report(defend_name)",
		"CREATE INDEX IF NOT EXISTS idx_br_attack_union_name ON battle_report(attack_union_name)",
		"CREATE INDEX IF NOT EXISTS idx_br_defend_union_name ON battle_report(defend_union_name)",
		"CREATE INDEX IF NOT EXISTS idx_br_npc ON battle_report(npc)",
		"CREATE INDEX IF NOT EXISTS idx_br_attack_hero1_id ON battle_report(attack_hero1_id)",
		"CREATE INDEX IF NOT EXISTS idx_br_defend_hero1_id ON battle_report(defend_hero1_id)",
		"CREATE INDEX IF NOT EXISTS idx_br_time_battle_id ON battle_report(time DESC, battle_id DESC)",
		"CREATE INDEX IF NOT EXISTS idx_br_attack_team_query ON battle_report(npc, attack_hp, attack_hero1_level, attack_hero2_level, attack_hero3_level, time DESC, battle_id DESC)",
		"CREATE INDEX IF NOT EXISTS idx_br_defend_team_query ON battle_report(npc, defend_hp, defend_hero1_level, defend_hero2_level, defend_hero3_level, time DESC, battle_id DESC)",
		"CREATE INDEX IF NOT EXISTS idx_br_attack_idu_time ON battle_report(attack_idu, time DESC)",
		"CREATE INDEX IF NOT EXISTS idx_br_defend_idu_time ON battle_report(defend_idu, time DESC)",
		"CREATE INDEX IF NOT EXISTS idx_br_result_time ON battle_report(result, time DESC)",
		"CREATE INDEX IF NOT EXISTS idx_br_attack_winrate ON battle_report(npc, result, attack_hp, defend_hp, attack_hero1_level, attack_hero2_level, attack_hero3_level, defend_hero1_level, defend_hero2_level, defend_hero3_level)",
		"CREATE INDEX IF NOT EXISTS idx_br_defend_winrate ON battle_report(npc, result, defend_hp, attack_hp, defend_hero1_level, defend_hero2_level, defend_hero3_level, attack_hero1_level, attack_hero2_level, attack_hero3_level)",
		"CREATE INDEX IF NOT EXISTS idx_br_attack_related ON battle_report(npc, attack_name, attack_idu, attack_hero1_id, attack_hero2_id, attack_hero3_id, time DESC, battle_id DESC)",
		"CREATE INDEX IF NOT EXISTS idx_br_defend_related ON battle_report(npc, defend_name, defend_idu, defend_hero1_id, defend_hero2_id, defend_hero3_id, time DESC, battle_id DESC)",
		"CREATE INDEX IF NOT EXISTS idx_pts_search ON player_team_snapshot(player_name, union_name, idu, last_time DESC)",
		"CREATE INDEX IF NOT EXISTS idx_twrs_search ON team_winrate_stats(mode, min_level, min_hp, player_name, idu, total_battles DESC, win_rate DESC)",
		"CREATE INDEX IF NOT EXISTS idx_twrs_team_search ON team_winrate_stats(mode, min_level, min_hp, lineup_key, normalized_skill_key, total_battles DESC, win_rate DESC)",
		"CREATE UNIQUE INDEX IF NOT EXISTS idx_mte_unique ON materialized_team_exclusion(player_name, role, idu, lineup_key, normalized_skill_key)",
	}
	for _, sql := range indexes {
		if err := db.Exec(sql).Error; err != nil {
			log.Println("创建索引失败:", err)
		}
	}

	Conn = db
	log.Println("数据库连接成功")
}
