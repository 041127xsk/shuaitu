package main

import (
	"fmt"
	"log"
	"os"
	"path/filepath"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func main() {
	db1 := "E:/openclaw/openclaw-main/tools/歌丨池上#7191611_X5602.db"
	db2 := "E:/openclaw/openclaw-main/stzb-helper-v2/build/bin/game.db"
	output := "E:/openclaw/openclaw-main/战报助手/数据库/歌丨池上#7191611_X5602.db"

	log.Println("Starting database merge...")
	log.Printf("Source 1: %s", db1)
	log.Printf("Source 2: %s", db2)
	log.Printf("Output: %s", output)

	// First, copy db1 to output
	if err := copyFile(db1, output); err != nil {
		log.Fatalf("Failed to copy db1: %v", err)
	}
	log.Println("Copied first database")

	// Open output database
	db, err := gorm.Open(sqlite.Open(output+"?cache=shared&mode=rwc"), &gorm.Config{})
	if err != nil {
		log.Fatalf("Failed to open output db: %v", err)
	}
	defer func() {
		sqlDB, _ := db.DB()
		sqlDB.Close()
	}()

	// Get tables
	var tables []string
	db.Raw("SELECT name FROM sqlite_master WHERE type='table'").Scan(&tables)
	log.Printf("Tables: %v", tables)

	// Open db2
	db2Conn, err := gorm.Open(sqlite.Open(db2+"?cache=shared&mode=ro"), &gorm.Config{})
	if err != nil {
		log.Fatalf("Failed to open db2: %v", err)
	}
	defer func() {
		sqlDB, _ := db2Conn.DB()
		sqlDB.Close()
	}()

	// Copy each table with INSERT OR IGNORE (dedup)
	for _, table := range tables {
		if table == "sqlite_sequence" {
			continue
		}

		log.Printf("Processing table: %s", table)

		// Get column names
		var columns []string
		db.Raw(fmt.Sprintf("PRAGMA table_info(%s)", table)).Scan(&struct {
			Name string
		}{})
		// Get columns properly
		rows, _ := db.Raw(fmt.Sprintf("PRAGMA table_info(%s)", table)).Rows()
		defer rows.Close()
		for rows.Next() {
			var col struct {
				Cid   int
				Name  string
				Type  string
				Notnull int
				Dflt_value interface{}
				Pk int
			}
			rows.Scan(&col.Cid, &col.Name, &col.Type, &col.Notnull, &col.Dflt_value, &col.Pk)
			columns = append(columns, col.Name)
		}

		if len(columns) == 0 {
			continue
		}

		// Get all rows from db2
		rows2, err := db2Conn.Raw(fmt.Sprintf("SELECT * FROM %s", table)).Rows()
		if err != nil {
			log.Printf("  Skip table %s: %v", table, err)
			continue
		}

		// Get column types
		columns2, _ := rows2.Columns()
		
		count := 0
		for rows2.Next() {
			values, _ := rows2.ScanSlice()
			
			// Build INSERT OR IGNORE query
			placeholders := make([]string, len(columns2))
			args := make([]interface{}, len(columns2))
			for i := range columns2 {
				placeholders[i] = "?"
				if i < len(values) {
					args[i] = values[i]
				}
			}
			
			colStr := ""
			for i, c := range columns2 {
				if i > 0 {
					colStr += ","
				}
				colStr += fmt.Sprintf(`"%s"`, c)
			}
			
			sql := fmt.Sprintf("INSERT OR IGNORE INTO %s (%s) VALUES (%s)", table, colStr, placeholders[0])
			if len(placeholders) > 1 {
				sql = fmt.Sprintf("INSERT OR IGNORE INTO %s (%s) VALUES (%s)", table, colStr, "")
			}
			
			// Use raw insert
			tx := db.Exec("INSERT OR IGNORE INTO "+table+" ("+colStr+") SELECT "+colStr+" FROM (SELECT "+colStr+") WHERE 1=0", args)
			if tx.Error == nil && tx.RowsAffected > 0 {
				count++
			}
		}
		rows2.Close()
		log.Printf("  %s: %d rows merged", table, count)
	}

	log.Println("Merge completed!")
}

func copyFile(src, dst string) error {
	data, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	return os.WriteFile(dst, data, 0644)
}