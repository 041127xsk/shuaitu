package model

import (
	"log"
	"path/filepath"
	"strings"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

var Conn *gorm.DB
var CurrentDatabasePath string

// InitDB 初始化数据库连接
// databasePath 可以是绝对路径或相对路径，可以带或不带 .db 后缀
func InitDB(databasePath string) {
	var previousSQLDB *gorm.DB
	if Conn != nil {
		previousSQLDB = Conn
	}

	resolvedPath := databasePath
	if !strings.HasSuffix(strings.ToLower(resolvedPath), ".db") {
		resolvedPath = resolvedPath + ".db"
	}
	if absPath, err := filepath.Abs(resolvedPath); err == nil {
		resolvedPath = absPath
	}

	dsn := resolvedPath
	dsn = dsn + "?cache=shared&mode=rwc&_journal_mode=WAL&_busy_timeout=5000&_synchronous=NORMAL&_temp_store=MEMORY"
	// SQLite 需要正斜杠
	dsn = strings.ReplaceAll(dsn, "\\", "/")
	log.Println("正在连接数据库:", dsn)

	db, err := gorm.Open(sqlite.Open(dsn), &gorm.Config{})
	if err != nil {
		log.Println("连接数据库失败:", err)
		return
	}

err = db.AutoMigrate(&TeamUser{}, &Task{}, &Report{}, &BattleReport{}, &PlayerTeamSnapshot{}, &TeamWinRateStat{}, &MaterializedState{}, &MaterializedTeamExclusion{}, &NameMapping{}, &ManualPlayerTeam{}, &HiddenPlayerTeam{})
	if err != nil {
		log.Println("数据库迁移失败:", err)
		return
	}

	// 为 battle_report 创建查询索引（精简版，避免写入放大）
	indexes := []string{
		"CREATE INDEX IF NOT EXISTS idx_br_npc ON battle_report(npc)",
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
		"CREATE INDEX IF NOT EXISTS idx_manual_team_player ON manual_player_team(player_name)",
		"CREATE INDEX IF NOT EXISTS idx_manual_team_union ON manual_player_team(union_name)",
		"CREATE INDEX IF NOT EXISTS idx_manual_team_idu ON manual_player_team(idu)",
		"CREATE INDEX IF NOT EXISTS idx_manual_team_enabled ON manual_player_team(enabled)",
		"CREATE INDEX IF NOT EXISTS idx_name_mapping_kind ON name_mapping(kind)",
	}
	for _, sql := range indexes {
		if err := db.Exec(sql).Error; err != nil {
			log.Println("创建索引失败:", err)
		}
	}

	if previousSQLDB != nil {
		if oldDB, err := previousSQLDB.DB(); err == nil {
			if err := oldDB.Close(); err != nil {
				log.Println("关闭旧数据库连接失败:", err)
			}
		}
	}

	Conn = db
	CurrentDatabasePath = resolvedPath
	log.Println("数据库连接成功")
}
