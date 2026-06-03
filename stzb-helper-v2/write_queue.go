package main

import (
	"fmt"
	"log"
	"stzbHelper/model"
	"sync"

	"gorm.io/gorm/clause"
)

type writeRequest struct {
	report model.BattleReport
}

var (
	writeQueue chan writeRequest
	writeOnce  sync.Once
)

func startWriteQueue() {
	writeOnce.Do(func() {
		writeQueue = make(chan writeRequest, 256)
		go writeQueueWorker()
	})
}

func writeQueueWorker() {
	log.Println("写入队列已启动")
	for req := range writeQueue {
		processBattleWrite(req.report)
	}
}

func processBattleWrite(report model.BattleReport) {
	result := model.Conn.Clauses(clause.OnConflict{DoNothing: true}).Create(&report)
	if result.Error != nil {
		log.Printf("保存战斗报告失败: %v", result.Error)
		return
	}
	if result.RowsAffected == 0 {
		log.Printf("检测到重复战报 (battle_id=%d)", report.BattleId)
		markAutoScrollDuplicate(report.BattleId)
		return
	}

	recordAutoScrollBattleID(report.BattleId)
	if err := applyBattleReportToMaterializedStats(report); err != nil {
		log.Printf("更新统计索引失败，已保留原始战报 battle_id=%d: %v", report.BattleId, err)
	}
	invalidatePlayerTeamQueryCache()
	invalidateQueryCache(&teamWinRateQueryCache)
	fmt.Printf("成功保存战斗报告, ID: %d\n", report.BattleId)
}

func enqueueBattleReport(report model.BattleReport) {
	if writeQueue == nil {
		startWriteQueue()
	}
	writeQueue <- writeRequest{report: report}
}
