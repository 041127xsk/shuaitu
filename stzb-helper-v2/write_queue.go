package main

import (
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
	if model.Conn == nil {
		log.Printf("保存战斗报告失败: 数据库未连接 (battle_id=%d)", report.BattleId)
		return
	}

	result := model.Conn.Clauses(clause.OnConflict{DoNothing: true}).Create(&report)
	if result.Error != nil {
		log.Printf("保存战斗报告失败: %v", result.Error)
		return
	}
	if result.RowsAffected == 0 {
		markAutoScrollDuplicate(report.BattleId)
		return
	}

	markAutoScrollInserted(report.BattleId)
	if err := applyBattleReportToMaterializedStats(report); err != nil {
		log.Printf("更新统计索引失败，已保留原始战报 battle_id=%d: %v", report.BattleId, err)
	}
	invalidatePlayerTeamQueryCache()
	invalidateQueryCache(&teamWinRateQueryCache)
	// 新增战报后战损数据也变了，清掉战损缓存，下次查询重新统计
	invalidateLossStatsCache()
}

// MinRecordAttackHeroLevel 是战报入库时进攻方三名武将必须达到的最低等级（含）。
//
// 低于等于该值的战报在入库前直接丢弃，不再写入数据库：这类记录基本是练级、
// 炮灰、铺路队伍，既污染队伍查询，也让库无限膨胀。
// 与查询侧的 MinTeamHeroLevel（> 30）不同，这里是入库硬门槛（<= 25 丢弃），
// 两者配合：库里不存在 <= 25 的残留，查询侧再按 > 30 筛主力。
const MinRecordAttackHeroLevel = 25

// shouldRecordBattleReport 判断一条战报是否值得入库。
//
// 规则：进攻方三名武将等级都已知（> 0）且全部高于 MinRecordAttackHeroLevel 才记录。
// 进攻方等级缺失（0）视为数据不完整，同样不记录，避免脏数据入库。
func shouldRecordBattleReport(report model.BattleReport) bool {
	levels := [3]int64{
		report.AttackHero1Level,
		report.AttackHero2Level,
		report.AttackHero3Level,
	}
	for _, lv := range levels {
		if lv <= MinRecordAttackHeroLevel {
			return false
		}
	}
	return true
}

func enqueueBattleReport(report model.BattleReport) {
	if !shouldRecordBattleReport(report) {
		noteLowLevelSkip(report)
		return
	}
	if writeQueue == nil {
		startWriteQueue()
	}
	writeQueue <- writeRequest{report: report}
}

// 低等级战报的跳过统计：累计到 100 条提示一次，避免逐条刷屏。
var (
	lowLevelSkipMutex sync.Mutex
	lowLevelSkipTotal int64 // 未提示的累计数
	lowLevelSkipAll   int64 // 会话内总跳过数
)

func noteLowLevelSkip(report model.BattleReport) {
	lowLevelSkipMutex.Lock()
	lowLevelSkipTotal++
	lowLevelSkipAll++
	pending := lowLevelSkipTotal
	total := lowLevelSkipAll
	if pending >= 100 {
		lowLevelSkipTotal = 0
	}
	lowLevelSkipMutex.Unlock()

	switch {
	case pending >= 100:
		log.Printf("跳过低等级战报：本批 100 条，累计已跳过 %d 条（攻方武将需全部 > %d 级才入库）",
			total, MinRecordAttackHeroLevel)
	case total == 1:
		// 只提示一次，让用户确认规则已生效
		log.Printf("跳过低等级战报不入库：battle_id=%d 攻方等级=%d/%d/%d（阈值 > %d）",
			report.BattleId, report.AttackHero1Level, report.AttackHero2Level, report.AttackHero3Level,
			MinRecordAttackHeroLevel)
	}
}
