package model

import (
	"log"
	"os"
	"path/filepath"
	"strings"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

var Conn *gorm.DB

// InitDB 初始化数据库连接
// databasePath 可以是绝对路径或相对路径，不带 .db 后缀
func InitDB(databasePath string) {
	// 如果设置了数据库目录，使用该目录
	if dbDir != "" {
		// 确保目录存在
		if err := os.MkdirAll(dbDir, 0755); err != nil {
			log.Println("创建数据库目录失败:", err)
			return
		}
		// 提取文件名
		filename := filepath.Base(databasePath)
		databasePath = filepath.Join(dbDir, filename)
	}

	dsn := databasePath + ".db?cache=shared&mode=rwc"
	// SQLite 需要正斜杠
	dsn = strings.ReplaceAll(dsn, "\\", "/")
	log.Println("正在连接数据库:", dsn)

	// 检查数据库是否已存在
	dbFile := databasePath + ".db"
	if _, err := os.Stat(dbFile); err == nil {
		log.Printf("检测到已存在数据库: %s，自动继承", dbFile)
	} else {
		log.Printf("创建新数据库: %s", dbFile)
	}

	db, err := gorm.Open(sqlite.Open(dsn), &gorm.Config{})
	if err != nil {
		log.Println("连接数据库失败:", err)
		return
	}

	err = db.AutoMigrate(&TeamUser{}, &Task{}, &Report{}, &BattleReport{})
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
	}
	for _, sql := range indexes {
		if err := db.Exec(sql).Error; err != nil {
			log.Println("创建索引失败:", err)
		}
	}

	Conn = db
	log.Println("数据库连接成功")
}

// SetDbDir 设置数据库存储目录
func SetDbDir(dir string) {
	dbDir = dir
	log.Println("数据库目录设置为:", dir)
}

// GetDbDir 获取数据库存储目录
func GetDbDir() string {
	return dbDir
}

var dbDir string = ""
