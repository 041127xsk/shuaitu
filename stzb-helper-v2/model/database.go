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

	err = db.AutoMigrate(&TeamUser{}, &Task{}, &Report{}, &BattleReport{}, &ManualPlayerTeam{}, &HiddenPlayerTeam{}, &NameMapping{})
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

	Conn = db
	log.Println("数据库连接成功")
}
