package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"stzbHelper/global"
	"stzbHelper/model"
	"syscall"
	"time"

	"golang.org/x/sys/windows"
)

// App struct
type App struct {
	ctx context.Context
}

type AdbProfile struct {
	ID        string `json:"id"`
	Name      string `json:"name"`
	AdbPath   string `json:"adb_path"`
	AdbSerial string `json:"adb_serial"`
}

type ScannedAdbDevice struct {
	Serial string `json:"serial"`
	Status string `json:"status"`
	Name   string `json:"name"`
}

type DiscoveredAdbPath struct {
	Path   string `json:"path"`
	Source string `json:"source"`
}

type CaptureModeStatus struct {
	Mode      string `json:"mode"`
	Running   bool   `json:"running"`
	ReportPos int    `json:"report_pos"`
	Message   string `json:"message"`
}

func currentCaptureModeStatus() CaptureModeStatus {
	mode := getCmd92CaptureMode()
	status := CaptureModeStatus{
		Mode:      mode,
		Running:   mode != "none",
		ReportPos: 0,
	}

	switch mode {
	case "battle_detail":
		status.Message = "当前处于详细战报采集模式"
	case "attendance_report":
		status.ReportPos = global.ExVar.NeededReportPos
		status.Message = "当前处于考勤守军采集模式"
	default:
		status.Message = "当前未开启战报采集"
	}

	return status
}

func setCaptureMode(mode string, reportPos int) CaptureModeStatus {
	global.ExVar.NeedGetBattleData = false
	global.ExVar.NeedGetReport = false
	global.ExVar.NeededReportPos = 0

	switch mode {
	case "battle_detail":
		global.ExVar.NeedGetBattleData = true
	case "attendance_report":
		global.ExVar.NeedGetReport = true
		global.ExVar.NeededReportPos = reportPos
	}

	return currentCaptureModeStatus()
}

// NewApp creates a new App application struct
func NewApp() *App {
	return &App{}
}

// startup is called when the app starts. The context is saved
// so we can call the runtime methods
func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
	global.AppCtx = ctx
	global.LogW.SetContext(ctx)
	log.SetOutput(appLogOutput(os.Stdout))
	log.Println("日志系统已连接到前端")
	startWriteQueue()
	initQueryCache(&teamWinRateQueryCache)
	initPlayerTeamQueryCache()
}

func appLogOutput(stdout io.Writer) io.Writer {
	if stdout == nil {
		return global.LogW
	}
	return io.MultiWriter(global.LogW, stdout)
}

func validateAttendanceRule(disMaxLevel int, atkMinLevel int) error {
	if disMaxLevel <= 0 || atkMinLevel <= 0 {
		return fmt.Errorf("主力/拆迁等级规则不能为空")
	}
	if disMaxLevel >= atkMinLevel {
		return fmt.Errorf("拆迁最高等级必须小于主力最低等级")
	}
	return nil
}

func hasAttendanceRule(task model.Task) bool {
	return task.DisMaxLevel > 0 && task.AtkMinLevel > 0
}

func taskHasReports(pos int) bool {
	var count int64
	model.Conn.Model(&model.Report{}).Where("wid = ?", pos).Count(&count)
	return count > 0
}

func buildTaskUserListForTargets(target []string) (map[int]*model.TaskUserList, int, error) {
	var teamUsers []model.TeamUser
	if len(target) > 0 {
		if err := model.Conn.Where("`group` IN ?", target).Find(&teamUsers).Error; err != nil {
			return nil, 0, err
		}
	}
	return model.TeamUserListToTaskUserList(teamUsers), len(teamUsers), nil
}

// Greet returns a greeting for the given name
func (a *App) Greet(name string) string {
	return fmt.Sprintf("Hello %s, It's show time!", name)
}

func (a *App) GetTeamUser() string {
	var teamUsers []model.TeamUser
	query := model.Conn
	query.Find(&teamUsers)
	if teamUsers == nil {
		teamUsers = []model.TeamUser{}
	}

	return global.Response{Data: teamUsers}.Success()
}

// GetTeamGroup 获取所有不重复的分组名称
func (a *App) GetTeamGroup() string {
	var groups []string
	model.Conn.Model(&model.TeamUser{}).Distinct("group").Pluck("group", &groups)
	return global.Response{Data: groups}.Success()
}

// CreateTask 创建攻城任务
func (a *App) CreateTask(name string, tasktime int, target []string, taskpos []string, disMaxLevel int, atkMinLevel int) string {
	if err := validateAttendanceRule(disMaxLevel, atkMinLevel); err != nil {
		return global.Response{Message: err.Error()}.Error()
	}

	userList, targetUserNum, err := buildTaskUserListForTargets(target)
	if err != nil {
		return global.Response{Message: "获取目标分组成员失败: " + err.Error()}.Error()
	}

	task := model.Task{
		Name:          name,
		Time:          tasktime,
		Pos:           model.ToTaskPos(taskpos),
		DisMaxLevel:   disMaxLevel,
		AtkMinLevel:   atkMinLevel,
		Target:        target,
		TargetUserNum: targetUserNum,
		UserList:      userList,
		Status:        0,
	}

	result := model.Conn.Create(&task)
	if result.Error != nil {
		return global.Response{Message: "创建任务失败: " + result.Error.Error()}.Error()
	}

	return global.Response{Data: task, Message: "创建任务成功"}.Success()
}

func (a *App) UpdateTaskAttendanceRule(id int, disMaxLevel int, atkMinLevel int) string {
	if err := validateAttendanceRule(disMaxLevel, atkMinLevel); err != nil {
		return global.Response{Message: err.Error()}.Error()
	}

	var task model.Task
	model.Conn.First(&task, id)
	if task.Id == 0 {
		return global.Response{Message: "任务不存在"}.Error()
	}

	task.DisMaxLevel = disMaxLevel
	task.AtkMinLevel = atkMinLevel
	if err := model.Conn.Save(&task).Error; err != nil {
		return global.Response{Message: "保存考勤等级规则失败: " + err.Error()}.Error()
	}

	return global.Response{Data: task, Message: "考勤等级规则保存成功"}.Success()
}

func (a *App) UpdateTask(id int, name string, tasktime int, target []string, taskpos []string, disMaxLevel int, atkMinLevel int) string {
	if err := validateAttendanceRule(disMaxLevel, atkMinLevel); err != nil {
		return global.Response{Message: err.Error()}.Error()
	}

	var task model.Task
	model.Conn.First(&task, id)
	if task.Id == 0 {
		return global.Response{Message: "任务不存在"}.Error()
	}

	newPos := model.ToTaskPos(taskpos)
	activeCapture := currentCaptureModeStatus()
	if activeCapture.Mode == "attendance_report" && activeCapture.ReportPos == task.Pos {
		return global.Response{Message: "当前任务正在考勤采集中，请先停止当前考勤模式再编辑任务"}.Error()
	}

	targetChanged := !sameStringSlice(task.Target, target)
	posChanged := task.Pos != newPos
	rebuildRoster := targetChanged || posChanged
	hadReports := taskHasReports(task.Pos)

	task.Name = name
	task.Time = tasktime
	task.Pos = newPos
	task.DisMaxLevel = disMaxLevel
	task.AtkMinLevel = atkMinLevel
	task.Target = target

	message := "任务更新成功"
	if rebuildRoster {
		userList, targetUserNum, err := buildTaskUserListForTargets(target)
		if err != nil {
			return global.Response{Message: "重建任务成员失败: " + err.Error()}.Error()
		}
		task.UserList = userList
		task.TargetUserNum = targetUserNum
		task.CompleteUserNum = 0
		task.Status = 0
		if hadReports {
			message = "任务更新成功，检测到旧战报数据，建议先清理旧战报再重新采集/统计"
		}
	}

	if err := model.Conn.Save(&task).Error; err != nil {
		return global.Response{Message: "更新任务失败: " + err.Error()}.Error()
	}

	return global.Response{Data: task, Message: message}.Success()
}

// GetTaskList 获取任务列表
func (a *App) GetTaskList() string {
	var tasks []model.Task
	model.Conn.Order("time desc, id desc").Find(&tasks)
	if tasks == nil {
		tasks = []model.Task{}
	}
	return global.Response{Data: tasks}.Success()
}

// GetGroupWu 获取分组武勋统计
func (a *App) GetGroupWu() string {
	type GroupWu struct {
		Group        string  `json:"group"`
		MemberCount  int     `json:"member_count"`
		TotalWu      int     `json:"total_wu"`
		AverageWu    float64 `json:"average_wu"`
		AveragePower float64 `json:"average_power"`
		ZeroWuCount  int     `json:"zero_wu_count"`
	}

	var results []GroupWu
	model.Conn.Model(&model.TeamUser{}).
		Select("`group`, count(*) as member_count, sum(wu) as total_wu, avg(wu) as average_wu, avg(power) as average_power, sum(case when wu = 0 then 1 else 0 end) as zero_wu_count").
		Group("`group`").
		Scan(&results)
	if results == nil {
		results = []GroupWu{}
	}

	return global.Response{Data: results}.Success()
}

// ExportTeamUser 导出同盟成员到CSV
func (a *App) ExportTeamUser() string {
	var users []model.TeamUser
	model.Conn.Find(&users)

	if len(users) == 0 {
		return global.Response{Message: "没有数据可导出"}.Error()
	}

	// 生成CSV内容
	csv := "ID,名称,总贡献,周贡献,坐标,势力值,武勋,分组,加入时间\n"
	for _, u := range users {
		csv += fmt.Sprintf("%d,%s,%d,%d,%d,%d,%d,%s,%d\n",
			u.Id, u.Name, u.ContributeTotal, u.ContributeWeek,
			u.Pos, u.Power, u.Wu, u.Group, u.JoinTime)
	}

	// 保存到exe同目录
	exePath, _ := os.Executable()
	dir := filepath.Dir(exePath)
	outputPath := filepath.Join(dir, "team_user_export.csv")

	if err := os.WriteFile(outputPath, []byte(csv), 0644); err != nil {
		return global.Response{Message: "导出失败: " + err.Error()}.Error()
	}

	log.Printf("已导出 %d 条成员数据到: %s", len(users), outputPath)
	return global.Response{Data: map[string]interface{}{
		"path":  outputPath,
		"count": len(users),
	}}.Success()
}

// ExportPlayerTeam 导出敌对队伍到CSV
func (a *App) ExportPlayerTeam(name string, uname string, idu string) string {
	type PlayerTeam struct {
		PlayerName   string `json:"player_name"`
		Hero1ID      int    `json:"hero1_id"`
		Hero2ID      int    `json:"hero2_id"`
		Hero3ID      int    `json:"hero3_id"`
		Hero1Level   int    `json:"hero1_level"`
		Hero2Level   int    `json:"hero2_level"`
		Hero3Level   int    `json:"hero3_level"`
		Hero1Star    int    `json:"hero1_star"`
		Hero2Star    int    `json:"hero2_star"`
		Hero3Star    int    `json:"hero3_star"`
		TotalStar    int    `json:"total_star"`
		Hp           int    `json:"hp"`
		AllSkillInfo string `json:"all_skill_info"`
		Role         string `json:"role"`
		Time         int    `json:"time"`
		Gear         string `json:"gear"`
		HeroType     string `json:"hero_type"`
		Idu          string `json:"idu"`
	}

	namePattern := "%" + name + "%"
	unamePattern := "%" + uname + "%"
	iduPattern := "%" + idu + "%"

	baseQuery := `WITH ranked_data AS (
		SELECT
			attack_name AS player_name,
			attack_hero1_id AS hero1_id,
			attack_hero2_id AS hero2_id,
			attack_hero3_id AS hero3_id,
			attack_hero1_level AS hero1_level,
			attack_hero2_level AS hero2_level,
			attack_hero3_level AS hero3_level,
			attack_hero1_star AS hero1_star,
			attack_hero2_star AS hero2_star,
			attack_hero3_star AS hero3_star,
			attack_total_star AS total_star,
			attack_hp AS hp,
			attacker_gear_info AS gear,
			attack_hero_type AS hero_type,
			attack_idu AS idu,
			time,
			all_skill_info,
			'attack' AS role,
			ROW_NUMBER() OVER (
				PARTITION BY attack_name, attack_hero1_id
				ORDER BY attack_hero1_level DESC, time DESC
			) AS rn
		FROM battle_report
		WHERE attack_hero1_id != 0 AND attack_hero2_id != 0 AND attack_hero3_id != 0
			AND attack_hero1_level >= 15 AND attack_hero2_level >= 15 AND attack_hero3_level >= 15
			AND attack_hp >= 10000
			AND attack_name LIKE ? AND attack_union_name LIKE ? AND attack_idu LIKE ?
			AND npc = 0 AND all_skill_info != "" AND all_skill_info IS NOT NULL
		UNION ALL
		SELECT
			defend_name AS player_name,
			defend_hero1_id AS hero1_id,
			defend_hero2_id AS hero2_id,
			defend_hero3_id AS hero3_id,
			defend_hero1_level AS hero1_level,
			defend_hero2_level AS hero2_level,
			defend_hero3_level AS hero3_level,
			defend_hero1_star AS hero1_star,
			defend_hero2_star AS hero2_star,
			defend_hero3_star AS hero3_star,
			defend_total_star AS total_star,
			defend_hp AS hp,
			defender_gear_info AS gear,
			defend_hero_type AS hero_type,
			defend_idu AS idu,
			time,
			all_skill_info,
			'defend' AS role,
			ROW_NUMBER() OVER (
				PARTITION BY defend_name, defend_hero1_id
				ORDER BY defend_hero1_level DESC, time DESC
			) AS rn
		FROM battle_report
		WHERE defend_hero1_id != 0 AND defend_hero2_id != 0 AND defend_hero3_id != 0
			AND defend_hero1_level >= 15 AND defend_hero2_level >= 15 AND defend_hero3_level >= 15
			AND defend_hp >= 10000
			AND defend_name LIKE ? AND defend_union_name LIKE ? AND defend_idu LIKE ?
			AND npc = 0 AND all_skill_info != "" AND all_skill_info IS NOT NULL
	)
	SELECT * FROM ranked_data WHERE rn = 1`

	var results []PlayerTeam
	model.Conn.Raw(baseQuery,
		namePattern, unamePattern, iduPattern,
		namePattern, unamePattern, iduPattern,
	).Scan(&results)

	if len(results) == 0 {
		return global.Response{Message: "没有数据可导出"}.Error()
	}

	// 生成CSV内容
	csv := "玩家,大营ID,中军ID,前锋ID,大营等级,中军等级,前锋等级,大营红度,中军红度,前锋红度,总红度,兵力,战法,角色,时间,宝物,兵种,队伍ID\n"
	for _, r := range results {
		csv += fmt.Sprintf("%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s,%s,%d,%s,%s,%s\n",
			r.PlayerName, r.Hero1ID, r.Hero2ID, r.Hero3ID,
			r.Hero1Level, r.Hero2Level, r.Hero3Level,
			r.Hero1Star, r.Hero2Star, r.Hero3Star, r.TotalStar,
			r.Hp, r.AllSkillInfo, r.Role, r.Time, r.Gear, r.HeroType, r.Idu)
	}

	// 保存到exe同目录
	exePath, _ := os.Executable()
	dir := filepath.Dir(exePath)
	outputPath := filepath.Join(dir, "player_team_export.csv")

	if err := os.WriteFile(outputPath, []byte("\xEF\xBB\xBF"+csv), 0644); err != nil {
		return global.Response{Message: "导出失败: " + err.Error()}.Error()
	}

	log.Printf("已导出 %d 条队伍数据到: %s", len(results), outputPath)
	return global.Response{Data: map[string]interface{}{
		"path":  outputPath,
		"count": len(results),
	}}.Success()
}

// DeleteTask 删除任务
func (a *App) DeleteTask(id int) string {
	result := model.Conn.Delete(&model.Task{}, id)
	if result.Error != nil {
		return global.Response{Message: "删除任务失败: " + result.Error.Error()}.Error()
	}
	return global.Response{Message: "删除任务成功"}.Success()
}

// EnableGetReport 开启战报获取
func (a *App) EnableGetReport(pos int) string {
	status := setCaptureMode("attendance_report", pos)
	return global.Response{Data: status, Message: "已切换到考勤守军模式"}.Success()
}

func (a *App) DisableGetReport() string {
	status := setCaptureMode("none", 0)
	return global.Response{Data: status, Message: "已关闭战报采集"}.Success()
}

// GetReportNumByTaskId 获取某任务的战报数量
func (a *App) GetReportNumByTaskId(id int) string {
	var task model.Task
	model.Conn.First(&task, id)
	if task.Id == 0 {
		return global.Response{Message: "任务不存在"}.Error()
	}

	var count int64
	model.Conn.Model(&model.Report{}).Where("wid = ?", task.Pos).Count(&count)

	return global.Response{Data: map[string]int64{"count": count}}.Success()
}

// normalizeName 归一化玩家名：去除首尾空格、统一全半角、统一大小写。
// 用于统计时匹配战报进攻方与名单成员，避免因格式差异漏人。
func normalizeName(name string) string {
	name = strings.TrimSpace(name)
	// 全角转半角
	var b strings.Builder
	for _, r := range name {
		switch {
		case r == '\u3000': // 全角空格
			b.WriteRune(' ')
		case r >= '\uFF01' && r <= '\uFF5E': // 全角字符转半角
			b.WriteRune(r - 0xFEE0)
		default:
			b.WriteRune(r)
		}
	}
	return strings.ToLower(b.String())
}

// StatisticsReport 统计考勤
func (a *App) StatisticsReport(id int) string {
	var task model.Task
	model.Conn.First(&task, id)
	if task.Id == 0 {
		return global.Response{Message: "任务不存在"}.Error()
	}
	if !hasAttendanceRule(task) {
		return global.Response{Message: "请先配置主力/拆迁等级规则"}.Error()
	}

	// 获取该坐标的所有战报
	var reports []model.Report
	model.Conn.Where("wid = ?", task.Pos).Find(&reports)

	log.Printf("统计任务[%s]的考勤, 坐标%d, 共%d条战报", task.Name, task.Pos, len(reports))

	if task.UserList == nil {
		task.UserList = map[int]*model.TaskUserList{}
	}

	// 每次统计前先重置计数，避免重复点击统计导致结果累加。
	for _, user := range task.UserList {
		user.AtkNum = 0
		user.DisNum = 0
		user.AtkTeamNum = 0
		user.DisTeamNum = 0
	}

	// 预构建名单索引：归一化名 -> 成员，支持名字格式差异匹配
	userByName := make(map[string]*model.TaskUserList, len(task.UserList))
	for _, user := range task.UserList {
		userByName[normalizeName(user.Name)] = user
	}

	// 统计每个成员的出勤
	gapCount := 0
	autoAdded := 0
	unmatchedNames := map[string]int{}
	nextID := 1000000 // 自动补入成员使用的临时ID（避开真实ID范围）

	for _, report := range reports {
		user := userByName[normalizeName(report.AttackName)]
		if user == nil {
			// 战报中出现但名单没有：自动补入（改善：名单同步）
			user = &model.TaskUserList{
				Id:    nextID,
				Name:  report.AttackName,
				Group: "未分组",
			}
			nextID++
			userByName[normalizeName(report.AttackName)] = user
			task.UserList[user.Id] = user
			autoAdded++
		}

		// 考勤口径:
		// - 拆迁: 等级 <= 任务拆迁最高等级
		// - 主力: 等级 >= 任务主力最低等级
		// - 断层区间(拆迁最高<等级<主力最低): 归入主力，避免静默丢弃（改善：等级断层兜底）
		level := report.AttackBaseLevel
		switch {
		case level <= task.DisMaxLevel:
			user.DisNum++
			user.DisTeamNum++
		case level >= task.AtkMinLevel:
			user.AtkNum++
			user.AtkTeamNum++
		case level > task.DisMaxLevel && level < task.AtkMinLevel:
			user.AtkNum++
			user.AtkTeamNum++
			gapCount++
		default:
			// level <= 0 等异常情况：按主力兜底计一次，并记录
			user.AtkNum++
			user.AtkTeamNum++
			unmatchedNames[report.AttackName]++
		}
	}

	// 计算实际到的人数
	completeNum := 0
	for _, user := range task.UserList {
		if user.AtkNum > 0 || user.DisNum > 0 {
			completeNum++
		}
	}
	task.CompleteUserNum = completeNum
	task.Status = 1

	model.Conn.Save(&task)

	// 漏人告警日志（改善：可观测性）
	if gapCount > 0 {
		log.Printf("统计完成：%d 条战报等级落在断层区间(拆<=%d<等级<%d=主)，已按主力兜底计入", gapCount, task.DisMaxLevel, task.AtkMinLevel)
	}
	if autoAdded > 0 {
		log.Printf("统计完成：战报中发现 %d 个名单外成员，已自动补入并计入出勤", autoAdded)
	}
	if len(unmatchedNames) > 0 {
		log.Printf("统计完成：%d 条战报进攻方无法匹配名单且等级异常(<=0)，已按主力兜底: %v", len(unmatchedNames), unmatchedNames)
	}
	log.Printf("统计完成：任务[%s] 出勤 %d/%d 人", task.Name, completeNum, len(task.UserList))

	return global.Response{Data: task, Message: "统计完成"}.Success()
}

// GetTask 获取任务详情
func (a *App) GetTask(id int) string {
	var task model.Task
	model.Conn.First(&task, id)
	if task.Id == 0 {
		return global.Response{Message: "任务不存在"}.Error()
	}
	return global.Response{Data: task}.Success()
}

// DeleteTaskReport 清理任务战报
func (a *App) DeleteTaskReport(id int) string {
	var task model.Task
	model.Conn.First(&task, id)
	if task.Id == 0 {
		return global.Response{Message: "任务不存在"}.Error()
	}

	// 删除该坐标相关的战报
	model.Conn.Where("wid = ?", task.Pos).Delete(&model.Report{})

	// 重置任务的考勤数据
	task.CompleteUserNum = 0
	task.Status = 0
	for _, user := range task.UserList {
		user.AtkNum = 0
		user.DisNum = 0
		user.AtkTeamNum = 0
		user.DisTeamNum = 0
	}
	model.Conn.Save(&task)

	return global.Response{Message: "清理战报成功"}.Success()
}

// EnableGetBattleReport 开启详细战报获取
func (a *App) EnableGetBattleReport() string {
	status := setCaptureMode("battle_detail", 0)
	return global.Response{Data: status, Message: "已切换到详细战报模式"}.Success()
}

// DisableGetBattleReport 关闭详细战报获取
func (a *App) DisableGetBattleReport() string {
	status := setCaptureMode("none", 0)
	return global.Response{Data: status, Message: "已关闭战报采集"}.Success()
}

func (a *App) GetCaptureModeStatus() string {
	return global.Response{Data: currentCaptureModeStatus()}.Success()
}

// AutoScrollConfig 自动翻页配置
type AutoScrollConfig struct {
	Count           int    `json:"count"`
	Delay           int    `json:"delay"`
	Duration        int    `json:"duration"`
	AdbPath         string `json:"adb_path"`
	AdbSerial       string `json:"adb_serial"`
	StopOnDuplicate bool   `json:"stop_on_duplicate"`
}

// AutoScrollStatus 自动翻页状态
type AutoScrollStatus struct {
	Running            bool   `json:"running"`
	Current            int    `json:"current"`
	Total              int    `json:"total"`
	ScreenWidth        int    `json:"screen_width"`
	ScreenHeight       int    `json:"screen_height"`
	StopReason         string `json:"stop_reason"`
	DuplicateFound     bool   `json:"duplicate_found"`
	StopOnDuplicate    bool   `json:"stop_on_duplicate"`
	InsertedCount      int    `json:"inserted_count"`
	DuplicateCount     int    `json:"duplicate_count"`
	LastBattleID       int64  `json:"last_battle_id"`
	ActiveDatabasePath string `json:"active_database_path"`
}

type AttendanceSummaryTask struct {
	ID   int    `json:"id"`
	Name string `json:"name"`
	Time int    `json:"time"`
	Pos  int    `json:"pos"`
}

type AttendanceSummaryCell struct {
	InRoster   bool `json:"in_roster"`
	Attended   bool `json:"attended"`
	AtkNum     int  `json:"atk_num"`
	DisNum     int  `json:"dis_num"`
	AtkTeamNum int  `json:"atk_team_num"`
	DisTeamNum int  `json:"dis_team_num"`
}

type AttendanceSummaryMember struct {
	Name              string                        `json:"name"`
	Group             string                        `json:"group"`
	TaskAttendedCount int                           `json:"task_attended_count"`
	TaskAbsentCount   int                           `json:"task_absent_count"`
	AtkTeamTotal      int                           `json:"atk_team_total"`
	DisTeamTotal      int                           `json:"dis_team_total"`
	AtkNumTotal       int                           `json:"atk_num_total"`
	DisNumTotal       int                           `json:"dis_num_total"`
	TaskMap           map[int]AttendanceSummaryCell `json:"task_map"`
}

type AttendanceSummary struct {
	Tasks   []AttendanceSummaryTask   `json:"tasks"`
	Members []AttendanceSummaryMember `json:"members"`
}

var (
	autoScrollRunning         bool
	autoScrollCurrent         int
	autoScrollTotal           int
	autoScrollCancel          chan bool
	autoScrollDuplicateFound  bool
	autoScrollLastBattleId    int64
	autoScrollStopOnDuplicate bool
	autoScrollStopReason      string
	autoScrollInsertedCount   int
	autoScrollDuplicateCount  int
)

var commandRunner = func(name string, arg ...string) (string, error) {
	cmd := exec.Command(name, arg...)
	cmd.SysProcAttr = &syscall.SysProcAttr{
		CreationFlags: 0x08000000, // CREATE_NO_WINDOW
	}
	output, err := cmd.CombinedOutput()
	if err != nil {
		log.Printf("执行命令失败: %v, args: %v, output: %s", err, arg, string(output))
		return string(output), err
	}
	return string(output), nil
}

const (
	DefaultAdbSerial = "127.0.0.1:16384"
)

// GetAutoScrollStatus 获取自动翻页状态
func (a *App) GetAutoScrollStatus() string {
	w, h := getScreenSize()
	return global.Response{Data: newAutoScrollStatus(w, h)}.Success()
}

func newAutoScrollStatus(w, h int) AutoScrollStatus {
	return AutoScrollStatus{
		Running:            autoScrollRunning,
		Current:            autoScrollCurrent,
		Total:              autoScrollTotal,
		ScreenWidth:        w,
		ScreenHeight:       h,
		StopReason:         autoScrollStopReason,
		DuplicateFound:     autoScrollDuplicateFound,
		StopOnDuplicate:    autoScrollStopOnDuplicate,
		InsertedCount:      autoScrollInsertedCount,
		DuplicateCount:     autoScrollDuplicateCount,
		LastBattleID:       autoScrollLastBattleId,
		ActiveDatabasePath: model.CurrentDatabasePath,
	}
}

func recordAutoScrollBattleID(battleID int64) {
	if battleID > 0 {
		autoScrollLastBattleId = battleID
	}
}

func markAutoScrollInserted(battleID int64) {
	recordAutoScrollBattleID(battleID)
	autoScrollInsertedCount++
}

func markAutoScrollDuplicate(battleID int64) {
	recordAutoScrollBattleID(battleID)
	autoScrollDuplicateFound = true
	autoScrollDuplicateCount++
	if autoScrollStopOnDuplicate {
		autoScrollStopReason = fmt.Sprintf("检测到重复战报 battle_id=%d，自动翻页已停止", battleID)
		return
	}
	autoScrollStopReason = fmt.Sprintf("检测到重复战报 battle_id=%d，已记录并继续翻页", battleID)
}

func shouldStopOnDuplicate() bool {
	return autoScrollDuplicateFound && autoScrollStopOnDuplicate
}

func getAdbPath(v interface{}) string {
	config := loadAppConfigStruct()
	if v == nil {
		return config.AdbPath
	}
	if s, ok := v.(string); ok {
		if s == "" {
			return config.AdbPath
		}
		return s
	}
	return config.AdbPath
}

func getAdbSerial(v interface{}) string {
	config := loadAppConfigStruct()
	if v == nil {
		return config.AdbSerial
	}
	if s, ok := v.(string); ok {
		if s == "" {
			return config.AdbSerial
		}
		return s
	}
	return config.AdbSerial
}

// StartAutoScroll 开始自动翻页
func (a *App) StartAutoScroll(jsonStr string) string {
	if autoScrollRunning {
		return global.Response{Message: "自动翻页已在运行中"}.Error()
	}

	var args struct {
		AdbPath         string `json:"adb_path"`
		AdbSerial       string `json:"adb_serial"`
		Count           int    `json:"count"`
		Delay           int    `json:"delay"`
		Duration        int    `json:"duration"`
		StopOnDuplicate bool   `json:"stop_on_duplicate"`
	}
	if jsonStr != "" {
		json.Unmarshal([]byte(jsonStr), &args)
	}

	adbPath := args.AdbPath
	adbSerial := args.AdbSerial
	count := args.Count
	delay := args.Delay
	duration := args.Duration
	stopOnDuplicate := args.StopOnDuplicate
	config := loadAppConfigStruct()

	if adbPath == "" {
		adbPath = config.AdbPath
	}
	if adbSerial == "" {
		adbSerial = config.AdbSerial
	}
	if count <= 0 {
		count = config.ScrollCount
	}
	if delay <= 0 {
		delay = config.ScrollDelay
	}
	if duration <= 0 {
		duration = config.ScrollDuration
	}

	log.Printf("StartAutoScroll: adbPath=%s, adbSerial=%s, count=%d, delay=%d, duration=%d, stopOnDuplicate=%v", adbPath, adbSerial, count, delay, duration, stopOnDuplicate)

	autoScrollRunning = true
	autoScrollCurrent = 0
	autoScrollTotal = count
	autoScrollDuplicateFound = false
	autoScrollLastBattleId = 0
	autoScrollStopOnDuplicate = stopOnDuplicate
	autoScrollStopReason = ""
	autoScrollInsertedCount = 0
	autoScrollDuplicateCount = 0
	autoScrollCancel = make(chan bool, 1)

	if lastId := readLastBattleId(); lastId > 0 {
		duplicateStrategy := "发现重复后继续"
		if stopOnDuplicate {
			duplicateStrategy = "发现重复后停止"
		}
		log.Printf("检测到上次最后战斗ID=%d；当前重复策略：%s", lastId, duplicateStrategy)
	}

	go func() {
		defer func() {
			saveLastBattleId()
			autoScrollRunning = false
			log.Printf("本轮结束：新增%d条，重复%d条，最后battle_id=%d，原因：%s",
				autoScrollInsertedCount, autoScrollDuplicateCount, autoScrollLastBattleId, autoScrollStopReason)
		}()

		w, h := getScreenSizeWithAdb(adbPath, adbSerial)
		cx := w / 2
		yStart := int(float64(h) * 0.4)
		yEnd := int(float64(h) * 0.15)

		log.Printf("自动翻页开始: ADB=%s, Serial=%s, 屏幕 %dx%d, 滑动 %d 次, 间隔 %dms",
			adbPath, adbSerial, w, h, count, delay)

		consecutiveFailures := 0
		const maxConsecutiveFailures = 5

		// 动态翻页策略：
		// - 滑动间隔保持用户配置（可短，如 100ms），快速翻页
		// - 但监测「连续多滑未新增战报」：说明可能滑到未加载区域或列表底部，
		//   此时暂停等待加载（pauseWaitMs），避免漏采中部战报
		// - 每 20 滑额外做一次深呼吸等待，兜底懒加载延迟
		noNewThreshold := 5               // 连续多少滑未新增战报则暂停等待
		noNewCount := 0                   // 当前连续无新增计数
		lastInserted := autoScrollInsertedCount
		const pauseWaitMs = 800           // 暂停等待加载时长
		const loadBreatheInterval = 20    // 深呼吸周期
		const loadBreatheExtraMs = 500    // 深呼吸额外时长

		for i := 0; i < count; i++ {
			select {
			case <-autoScrollCancel:
				autoScrollStopReason = fmt.Sprintf("手动停止，已滑动 %d/%d 次", autoScrollCurrent, count)
				log.Printf("自动翻页已停止，已滑动 %d/%d 次", autoScrollCurrent, count)
				return
			default:
			}

			if shouldStopOnDuplicate() {
				if autoScrollStopReason == "" {
					autoScrollStopReason = fmt.Sprintf("检测到重复战报，停止翻页，已滑动 %d/%d 次", autoScrollCurrent, count)
				}
				log.Printf("检测到重复战报，停止翻页 (已处理 %d 条)", autoScrollCurrent)
				return
			}

			success := swipeWithAdb(adbPath, adbSerial, cx, yStart, yEnd, duration)
			if success {
				consecutiveFailures = 0
			} else {
				consecutiveFailures++
				log.Printf("[%d/%d] 滑动失败 (连续失败 %d 次)", i+1, count, consecutiveFailures)
				if consecutiveFailures >= maxConsecutiveFailures {
					autoScrollStopReason = fmt.Sprintf("ADB 连续 %d 次滑动失败，已停止在 %d/%d 次", maxConsecutiveFailures, autoScrollCurrent, count)
					log.Printf("连续 %d 次滑动失败，停止翻页", maxConsecutiveFailures)
					autoScrollCurrent = i
					return
				}
				continue
			}

			autoScrollCurrent = i + 1
			if (i+1)%100 == 0 || i == 0 {
				log.Printf("[%d/%d] 滑动完成", autoScrollCurrent, count)
			}

			// 检测连续无新增战报：有新增则重置计数，无新增则累计
			if autoScrollInsertedCount > lastInserted {
				noNewCount = 0
				lastInserted = autoScrollInsertedCount
			} else {
				noNewCount++
			}

			if i < count-1 {
				// 默认按用户配置的短间隔继续
				waitMs := delay
				if waitMs < 50 {
					waitMs = 50
				}
				// 连续多滑无新增：暂停等待游戏懒加载
				if noNewCount >= noNewThreshold {
					noNewCount = 0
					log.Printf("[%d/%d] 连续 %d 滑未新增战报，暂停 %dms 等待加载 (累计已入库 %d 条)",
						autoScrollCurrent, count, noNewThreshold, pauseWaitMs, autoScrollInsertedCount)
					waitMs += pauseWaitMs
				}
				// 周期性深呼吸，兜底加载延迟
				if (i+1)%loadBreatheInterval == 0 {
					waitMs += loadBreatheExtraMs
				}
				time.Sleep(time.Duration(waitMs) * time.Millisecond)
			}
		}

		autoScrollStopReason = fmt.Sprintf("已完成 %d 次自动翻页", count)
		log.Printf("自动翻页完成: 共 %d 次", count)
	}()

	return global.Response{Message: fmt.Sprintf("开始自动翻页: %d 次", count)}.Success()
}

// StopAutoScroll 停止自动翻页
func (a *App) StopAutoScroll() string {
	if !autoScrollRunning {
		return global.Response{Message: "自动翻页未运行"}.Error()
	}

	select {
	case autoScrollCancel <- true:
	default:
	}
	saveLastBattleId()
	autoScrollStopReason = fmt.Sprintf("手动停止，当前已滑动 %d/%d 次", autoScrollCurrent, autoScrollTotal)
	autoScrollRunning = false

	return global.Response{Message: fmt.Sprintf("已停止，当前已滑动 %d 次", autoScrollCurrent)}.Success()
}

func getLastBattleIdPath() string {
	exePath, err := os.Executable()
	if err != nil {
		return filepath.Join(os.TempDir(), "stzb-helper-last-battle-id.txt")
	}
	return filepath.Join(filepath.Dir(exePath), "last_battle_id.txt")
}

func readLastBattleId() int64 {
	data, err := os.ReadFile(getLastBattleIdPath())
	if err != nil {
		return 0
	}
	id, _ := strconv.ParseInt(strings.TrimSpace(string(data)), 10, 64)
	return id
}

func saveLastBattleId() {
	if autoScrollLastBattleId <= 0 {
		return
	}
	path := getLastBattleIdPath()
	os.WriteFile(path, []byte(strconv.FormatInt(autoScrollLastBattleId, 10)), 0644)
	log.Printf("已记录最后战斗ID: %d", autoScrollLastBattleId)
}

// getScreenSize 获取屏幕分辨率（使用默认配置）
func getScreenSize() (int, int) {
	config := loadAppConfigStruct()
	return getScreenSizeWithAdb(config.AdbPath, config.AdbSerial)
}

// getScreenSizeWithAdb 获取屏幕分辨率（指定ADB）
func getScreenSizeWithAdb(adbPath string, adbSerial string) (int, int) {
	result := subprocessRun(adbPath, "-s", adbSerial, "shell", "wm", "size")
	if result == "" {
		log.Println("获取屏幕尺寸失败，返回默认值")
		return 1080, 1920
	}
	output := strings.TrimSpace(result)

	for _, line := range strings.Split(output, "\n") {
		lower := strings.ToLower(line)
		if strings.Contains(lower, "physical") || strings.Contains(lower, "size") {
			parts := strings.Split(line, ":")
			if len(parts) >= 2 {
				sizePart := strings.TrimSpace(parts[len(parts)-1])
				wh := strings.Split(sizePart, "x")
				if len(wh) == 2 {
					w := strings.TrimSpace(wh[0])
					h := strings.TrimSpace(wh[1])
					wi, _ := strconv.Atoi(w)
					hi, _ := strconv.Atoi(h)
					if wi > 0 && hi > 0 {
						return wi, hi
					}
				}
			}
		}
	}
	log.Println("未找到屏幕尺寸信息，返回默认值")
	return 1080, 1920
}

// subprocessRun 执行命令并返回输出
func subprocessRun(name string, arg ...string) string {
	result, _ := subprocessRunWithError(name, arg...)
	return result
}

// subprocessRunWithError 执行命令并返回输出和错误
func subprocessRunWithError(name string, arg ...string) (string, error) {
	return commandRunner(name, arg...)
}

// swipeWithAdb 执行单次滑动，返回是否成功
func swipeWithAdb(adbPath, adbSerial string, cx, yStart, yEnd, duration int) bool {
	output, err := subprocessRunWithError(adbPath, "-s", adbSerial, "shell", "input", "swipe",
		fmt.Sprintf("%d", cx), fmt.Sprintf("%d", yStart),
		fmt.Sprintf("%d", cx), fmt.Sprintf("%d", yEnd),
		fmt.Sprintf("%d", duration))

	output = strings.TrimSpace(output)
	if err != nil && output != "" {
		log.Printf("swipeWithAdb: ADB退出码非0但产生了输出 (可能是ADB版本差异), output: %s", output)
		return true
	}
	if err != nil {
		log.Printf("swipeWithAdb: ADB命令失败, err=%v, output=%s", err, output)
		return false
	}
	return true
}

// CheckAdbConnection 检查 ADB 连接状态
func (a *App) CheckAdbConnection(jsonStr string) string {
	var args struct {
		AdbPath   string `json:"adb_path"`
		AdbSerial string `json:"adb_serial"`
	}
	if jsonStr != "" {
		json.Unmarshal([]byte(jsonStr), &args)
	}

	adbPath := args.AdbPath
	adbSerial := args.AdbSerial
	config := loadAppConfigStruct()
	if adbPath == "" {
		adbPath = config.AdbPath
	}
	if adbSerial == "" {
		adbSerial = config.AdbSerial
	}

	if adbPath == "" {
		return global.Response{Data: map[string]interface{}{
			"connected": false,
			"message":   "ADB路径为空，请在设置中配置ADB路径",
		}}.Error()
	}
	if adbSerial == "" {
		return global.Response{Data: map[string]interface{}{
			"connected": false,
			"message":   "ADB Serial为空，请在设置中配置Serial",
		}}.Error()
	}

	log.Printf("CheckAdbConnection: adbPath=%s, adbSerial=%s", adbPath, adbSerial)

	if _, err := os.Stat(adbPath); os.IsNotExist(err) {
		return global.Response{Data: map[string]interface{}{
			"connected": false,
			"message":   fmt.Sprintf("ADB路径不存在: %s", adbPath),
		}}.Error()
	}

	subprocessRun(adbPath, "connect", adbSerial)
	time.Sleep(500 * time.Millisecond)

	result := subprocessRun(adbPath, "-s", adbSerial, "get-state")
	state := strings.TrimSpace(result)
	if state == "device" {
		w, h := getScreenSizeWithAdb(adbPath, adbSerial)
		return global.Response{Data: map[string]interface{}{
			"connected":  true,
			"screen":     fmt.Sprintf("%dx%d", w, h),
			"adb_path":   adbPath,
			"adb_serial": adbSerial,
		}}.Success()
	}
	return global.Response{Data: map[string]interface{}{
		"connected": false,
		"message":   fmt.Sprintf("设备未连接 (状态: %s)，请检查模拟器和ADB", state),
	}}.Error()
}

// AppConfig 应用配置
type AppConfig struct {
	AdbPath            string       `json:"adb_path"`
	AdbSerial          string       `json:"adb_serial"`
	ScrollCount        int          `json:"scroll_count"`
	ScrollDelay        int          `json:"scroll_delay"`
	ScrollDuration     int          `json:"scroll_duration"`
	StopOnDuplicate    bool         `json:"stop_on_duplicate"`
	DatabasePath       string       `json:"database_path"`
	DefaultDisMaxLevel int          `json:"default_dis_max_level"`
	DefaultAtkMinLevel int          `json:"default_atk_min_level"`
	AdbProfiles        []AdbProfile `json:"adb_profiles"`
	ActiveAdbProfileID string       `json:"active_adb_profile_id"`
}

var executablePathFunc = os.Executable

var defaultConfig = AppConfig{
	AdbSerial:          "127.0.0.1:16384",
	ScrollCount:        4000,
	ScrollDelay:        100,
	ScrollDuration:     100,
	StopOnDuplicate:    false,
	DefaultDisMaxLevel: 19,
	DefaultAtkMinLevel: 25,
}

func portableDefaultPath(parts ...string) string {
	dir, err := getAppDir()
	if err != nil {
		return filepath.Join(parts...)
	}
	all := append([]string{dir}, parts...)
	return filepath.Join(all...)
}

func defaultAdbPath() string {
	return portableDefaultPath("platform-tools", "adb.exe")
}

func defaultDatabasePath() string {
	return portableDefaultPath("data", "default.db")
}

func defaultAppConfig() AppConfig {
	config := defaultConfig
	config.AdbPath = defaultAdbPath()
	config.DatabasePath = defaultDatabasePath()
	config = ensureAdbProfiles(config)
	return config
}

func getAppDir() (string, error) {
	exePath, err := executablePathFunc()
	if err != nil {
		return "", err
	}
	return filepath.Dir(exePath), nil
}

func sameStringSlice(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func getConfigPath() string {
	dir, err := getAppDir()
	if err != nil {
		return "config.json"
	}
	return filepath.Join(dir, "config.json")
}

func mergeConfigWithDefaults(config AppConfig) AppConfig {
	defaults := defaultAppConfig()
	if config.AdbPath == "" {
		config.AdbPath = defaults.AdbPath
	}
	if config.AdbSerial == "" {
		config.AdbSerial = defaults.AdbSerial
	}
	if config.ScrollCount == 0 {
		config.ScrollCount = defaults.ScrollCount
	}
	if config.ScrollDelay == 0 {
		config.ScrollDelay = defaults.ScrollDelay
	}
	if config.ScrollDuration == 0 {
		config.ScrollDuration = defaults.ScrollDuration
	}
	if config.DatabasePath == "" {
		config.DatabasePath = defaults.DatabasePath
	}
	if config.DefaultDisMaxLevel == 0 {
		config.DefaultDisMaxLevel = defaults.DefaultDisMaxLevel
	}
	if config.DefaultAtkMinLevel == 0 {
		config.DefaultAtkMinLevel = defaults.DefaultAtkMinLevel
	}
	config = ensureAdbProfiles(config)
	return config
}

func ensureAdbProfiles(config AppConfig) AppConfig {
	profiles := make([]AdbProfile, 0, len(config.AdbProfiles))
	seen := map[string]bool{}
	for _, profile := range config.AdbProfiles {
		if strings.TrimSpace(profile.ID) == "" {
			profile.ID = fmt.Sprintf("profile-%d", len(profiles)+1)
		}
		if strings.TrimSpace(profile.Name) == "" {
			profile.Name = "模拟器 " + profile.ID
		}
		if strings.TrimSpace(profile.AdbPath) == "" {
			profile.AdbPath = config.AdbPath
		}
		if strings.TrimSpace(profile.AdbSerial) == "" {
			continue
		}
		if seen[profile.ID] {
			continue
		}
		seen[profile.ID] = true
		profiles = append(profiles, profile)
	}

	if len(profiles) == 0 {
		profiles = append(profiles, AdbProfile{
			ID:        "default",
			Name:      "默认模拟器",
			AdbPath:   config.AdbPath,
			AdbSerial: config.AdbSerial,
		})
	}

	activeID := strings.TrimSpace(config.ActiveAdbProfileID)
	var active *AdbProfile
	for i := range profiles {
		if profiles[i].ID == activeID {
			active = &profiles[i]
			break
		}
	}
	if active == nil {
		active = &profiles[0]
		activeID = active.ID
	}

	if strings.TrimSpace(active.AdbPath) == "" {
		active.AdbPath = defaultAdbPath()
	}
	if strings.TrimSpace(active.AdbSerial) == "" {
		active.AdbSerial = defaultConfig.AdbSerial
	}

	config.AdbProfiles = profiles
	config.ActiveAdbProfileID = activeID
	config.AdbPath = active.AdbPath
	config.AdbSerial = active.AdbSerial
	return config
}

func loadAppConfigStruct() AppConfig {
	configPath := getConfigPath()
	data, err := os.ReadFile(configPath)
	if err != nil {
		return defaultAppConfig()
	}

	var config AppConfig
	if err := json.Unmarshal(data, &config); err != nil {
		return defaultAppConfig()
	}

	return mergeConfigWithDefaults(config)
}

func saveAppConfigStruct(config AppConfig) error {
	configPath := getConfigPath()
	config = mergeConfigWithDefaults(config)
	data, err := json.MarshalIndent(config, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(configPath, data, 0644)
}

func currentAdbProfile(config AppConfig) AdbProfile {
	config = ensureAdbProfiles(config)
	for _, profile := range config.AdbProfiles {
		if profile.ID == config.ActiveAdbProfileID {
			return profile
		}
	}
	return config.AdbProfiles[0]
}

func normalizeDatabasePath(dbPath string) string {
	if strings.HasSuffix(strings.ToLower(dbPath), ".db") {
		return dbPath
	}
	return dbPath + ".db"
}

func normalizeDatabaseName(name string) string {
	return strings.TrimSuffix(strings.TrimPrefix(strings.TrimSpace(name), "[配置]"), ".db")
}

func persistSelectedDatabasePath(dbPath string) error {
	config := loadAppConfigStruct()
	config.DatabasePath = normalizeDatabasePath(dbPath)
	return saveAppConfigStruct(config)
}

func resolveDatabasePath(name string) (string, error) {
	config := loadAppConfigStruct()
	dbPath := config.DatabasePath

	if strings.HasPrefix(name, "[配置]") || name == "" || name == "game" {
		return normalizeDatabasePath(dbPath), nil
	}

	dir, err := getAppDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, name+".db"), nil
}

func resolveManagedDatabasePath(name string) (string, error) {
	normalized := normalizeDatabaseName(name)
	if normalized == "" {
		return "", fmt.Errorf("数据库名称不能为空")
	}
	dir, err := getAppDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, normalized+".db"), nil
}

// LoadConfig 加载配置
func (a *App) LoadConfig() string {
	configPath := getConfigPath()
	if _, err := os.Stat(configPath); err != nil {
		log.Printf("配置文件不存在，使用默认配置: %v", err)
	} else if _, err := os.ReadFile(configPath); err != nil {
		log.Printf("配置文件读取失败，使用默认配置: %v", err)
	}
	return global.Response{Data: loadAppConfigStruct()}.Success()
}

// SaveConfig 保存配置
func (a *App) SaveConfig(configJson string) string {
	var config AppConfig
	if err := json.Unmarshal([]byte(configJson), &config); err != nil {
		return global.Response{Message: "配置格式错误: " + err.Error()}.Error()
	}

	config = mergeConfigWithDefaults(config)
	if err := validateAttendanceRule(config.DefaultDisMaxLevel, config.DefaultAtkMinLevel); err != nil {
		return global.Response{Message: "全局默认考勤等级规则无效: " + err.Error()}.Error()
	}
	if err := saveAppConfigStruct(config); err != nil {
		return global.Response{Message: "保存配置失败: " + err.Error()}.Error()
	}

	configPath := getConfigPath()
	log.Printf("配置已保存到: %s", configPath)
	return global.Response{Message: "配置保存成功"}.Success()
}

func (a *App) SaveAdbProfiles(configJson string) string {
	var payload AppConfig
	if err := json.Unmarshal([]byte(configJson), &payload); err != nil {
		return global.Response{Message: "配置格式错误: " + err.Error()}.Error()
	}

	current := loadAppConfigStruct()
	current.AdbProfiles = payload.AdbProfiles
	current.ActiveAdbProfileID = payload.ActiveAdbProfileID
	current = mergeConfigWithDefaults(current)
	if err := saveAppConfigStruct(current); err != nil {
		return global.Response{Message: "保存模拟器实例失败: " + err.Error()}.Error()
	}
	return global.Response{Data: current, Message: "模拟器实例保存成功"}.Success()
}

func (a *App) SetActiveAdbProfile(profileID string) string {
	if autoScrollRunning {
		return global.Response{Message: "自动翻页运行中，无法切换模拟器实例"}.Error()
	}

	config := loadAppConfigStruct()
	config.ActiveAdbProfileID = profileID
	config = mergeConfigWithDefaults(config)

	found := false
	for _, profile := range config.AdbProfiles {
		if profile.ID == profileID {
			found = true
			break
		}
	}
	if !found {
		return global.Response{Message: "模拟器实例不存在"}.Error()
	}

	if err := saveAppConfigStruct(config); err != nil {
		return global.Response{Message: "切换模拟器实例失败: " + err.Error()}.Error()
	}
	return global.Response{Data: currentAdbProfile(config), Message: "模拟器实例切换成功"}.Success()
}

func (a *App) ScanAdbDevices() string {
	config := loadAppConfigStruct()
	profile := currentAdbProfile(config)
	adbPath := profile.AdbPath
	if adbPath == "" {
		adbPath = config.AdbPath
	}
	if adbPath == "" {
		return global.Response{Message: "ADB路径为空，请先配置ADB路径"}.Error()
	}
	if _, err := os.Stat(adbPath); os.IsNotExist(err) {
		return global.Response{Message: "ADB路径不存在: " + adbPath}.Error()
	}

	output, err := subprocessRunWithError(adbPath, "devices")
	if err != nil && strings.TrimSpace(output) == "" {
		return global.Response{Message: "扫描ADB设备失败: " + err.Error()}.Error()
	}

	devices := []ScannedAdbDevice{}
	for _, line := range strings.Split(strings.ReplaceAll(output, "\r\n", "\n"), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "List of devices attached") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		devices = append(devices, ScannedAdbDevice{
			Serial: fields[0],
			Status: fields[1],
			Name:   "MuMu " + fields[0],
		})
	}

	return global.Response{Data: devices}.Success()
}

func (a *App) DiscoverAdbPaths() string {
	return global.Response{Data: discoverAdbPaths()}.Success()
}

func discoverAdbPaths() []DiscoveredAdbPath {
	config := loadAppConfigStruct()
	candidates := []DiscoveredAdbPath{
		{Path: defaultAdbPath(), Source: "内置ADB"},
		{Path: config.AdbPath, Source: "当前配置"},
	}
	for _, profile := range config.AdbProfiles {
		if strings.TrimSpace(profile.AdbPath) == "" {
			continue
		}
		source := "模拟器实例"
		if strings.TrimSpace(profile.Name) != "" {
			source = "模拟器实例: " + profile.Name
		}
		candidates = append(candidates, DiscoveredAdbPath{Path: profile.AdbPath, Source: source})
	}

	if path, err := exec.LookPath("adb.exe"); err == nil {
		candidates = append(candidates, DiscoveredAdbPath{Path: path, Source: "系统PATH"})
	} else if path, err := exec.LookPath("adb"); err == nil {
		candidates = append(candidates, DiscoveredAdbPath{Path: path, Source: "系统PATH"})
	}

	for _, envName := range []string{"ANDROID_HOME", "ANDROID_SDK_ROOT", "LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"} {
		value := strings.TrimSpace(os.Getenv(envName))
		if value == "" {
			continue
		}
		switch envName {
		case "ANDROID_HOME", "ANDROID_SDK_ROOT":
			candidates = append(candidates, DiscoveredAdbPath{Path: filepath.Join(value, "platform-tools", "adb.exe"), Source: envName})
		case "LOCALAPPDATA":
			candidates = append(candidates,
				DiscoveredAdbPath{Path: filepath.Join(value, "Android", "Sdk", "platform-tools", "adb.exe"), Source: "Android SDK"},
				DiscoveredAdbPath{Path: filepath.Join(value, "Programs", "stzbHelper", "platform-tools", "adb.exe"), Source: "stzbHelper安装目录"},
			)
		case "ProgramFiles", "ProgramFiles(x86)":
			candidates = append(candidates,
				DiscoveredAdbPath{Path: filepath.Join(value, "Netease", "MuMuPlayer-12.0", "shell", "adb.exe"), Source: "MuMu Player"},
				DiscoveredAdbPath{Path: filepath.Join(value, "Netease", "MuMuPlayerGlobal-12.0", "shell", "adb.exe"), Source: "MuMu Player"},
				DiscoveredAdbPath{Path: filepath.Join(value, "MuMu", "emulator", "nemu", "vmonitor", "bin", "adb_server.exe"), Source: "MuMu Player"},
			)
		}
	}

	seen := map[string]bool{}
	results := []DiscoveredAdbPath{}
	for _, candidate := range candidates {
		path := strings.TrimSpace(candidate.Path)
		if path == "" {
			continue
		}
		absPath, err := filepath.Abs(path)
		if err != nil {
			absPath = path
		}
		if _, err := os.Stat(absPath); err != nil {
			continue
		}
		key := normalizePathForCompare(absPath)
		if seen[key] {
			continue
		}
		seen[key] = true
		results = append(results, DiscoveredAdbPath{Path: absPath, Source: candidate.Source})
	}
	return results
}

func normalizePathForCompare(path string) string {
	return strings.ToLower(filepath.Clean(path))
}

// EnableBookData 开启主公簿数据推送
func (a *App) EnableBookData() string {
	global.ExVar.NeedPushBookData = true
	return global.Response{Message: "开启主公簿数据推送成功"}.Success()
}

// DisableBookData 关闭主公簿数据推送
func (a *App) DisableBookData() string {
	global.ExVar.NeedPushBookData = false
	return global.Response{Message: "关闭主公簿数据推送成功"}.Success()
}

// // EnableBattleCall 开启战役叫阵数据推送
// func (a *App) EnableBattleCall() string {
// 	global.ExVar.NeedPushBattleCallData = true
// 	return global.Response{Message: "开启战役叫阵数据推送成功"}.Success()
// }

// // DisableBattleCall 关闭战役叫阵数据推送
// func (a *App) DisableBattleCall() string {
// 	global.ExVar.NeedPushBattleCallData = false
// 	return global.Response{Message: "关闭战役叫阵数据推送成功"}.Success()
// }

// GetDbList 获取当前目录下的数据库文件列表
func (a *App) GetDbList() string {
	dbList := []string{}

	config := loadAppConfigStruct()
	dbPath := normalizeDatabasePath(config.DatabasePath)
	if _, err := os.Stat(dbPath); err == nil {
		baseName := filepath.Base(dbPath)
		dbList = append(dbList, "[配置]"+strings.TrimSuffix(baseName, ".db"))
	}

	if dir, err := getAppDir(); err == nil {
		entries, _ := os.ReadDir(dir)
		for _, entry := range entries {
			if !entry.IsDir() && strings.HasSuffix(entry.Name(), ".db") {
				name := strings.TrimSuffix(entry.Name(), ".db")
				if "[配置]"+name == "[配置]"+strings.TrimSuffix(filepath.Base(dbPath), ".db") {
					continue
				}
				dbList = append(dbList, name)
			}
		}
	}

	return global.Response{Data: dbList}.Success()
}

// CreateDb 创建新数据库并连接
func (a *App) CreateDb(name string) string {
	name = normalizeDatabaseName(name)
	if name == "" {
		return global.Response{Message: "数据库名称不能为空"}.Error()
	}
	dir, err := getAppDir()
	if err != nil {
		return global.Response{Message: "获取程序路径失败: " + err.Error()}.Error()
	}
	dbPath := filepath.Join(dir, name+".db")

	model.InitDB(dbPath)
	if model.Conn == nil {
		return global.Response{Message: "创建数据库失败，请检查日志"}.Error()
	}
	if err := persistSelectedDatabasePath(dbPath); err != nil {
		return global.Response{Message: "创建数据库成功，但保存默认数据库失败: " + err.Error()}.Error()
	}
	databaseSelected = true
	invalidatePlayerTeamQueryCache()
	invalidateQueryCache(&teamWinRateQueryCache)
	return global.Response{Message: "数据库创建成功"}.Success()
}

func (a *App) RenameDb(oldName string, newName string) string {
	oldPath, err := resolveManagedDatabasePath(oldName)
	if err != nil {
		return global.Response{Message: "获取原数据库路径失败: " + err.Error()}.Error()
	}
	newName = normalizeDatabaseName(newName)
	if newName == "" {
		return global.Response{Message: "新数据库名称不能为空"}.Error()
	}
	newPath, err := resolveManagedDatabasePath(newName)
	if err != nil {
		return global.Response{Message: "获取新数据库路径失败: " + err.Error()}.Error()
	}
	if _, err := os.Stat(oldPath); err != nil {
		return global.Response{Message: "原数据库不存在: " + oldPath}.Error()
	}
	if _, err := os.Stat(newPath); err == nil {
		return global.Response{Message: "目标数据库已存在: " + newPath}.Error()
	}

	config := loadAppConfigStruct()
	selectedPath := normalizeDatabasePath(config.DatabasePath)
	renamingSelected := normalizeDatabasePath(oldPath) == selectedPath

	if model.Conn != nil && renamingSelected {
		if sqlDB, err := model.Conn.DB(); err == nil {
			_ = sqlDB.Close()
		}
		model.Conn = nil
	}

	if err := os.Rename(oldPath, newPath); err != nil {
		return global.Response{Message: "重命名数据库失败: " + err.Error()}.Error()
	}

	if renamingSelected {
		if err := persistSelectedDatabasePath(newPath); err != nil {
			return global.Response{Message: "数据库已重命名，但更新默认数据库失败: " + err.Error()}.Error()
		}
		model.InitDB(newPath)
		if model.Conn == nil {
			return global.Response{Message: "数据库已重命名，但重新连接失败: " + newPath}.Error()
		}
	}

	return global.Response{Message: "数据库重命名成功"}.Success()
}

func (a *App) DeleteDb(name string) string {
	dbPath, err := resolveManagedDatabasePath(name)
	if err != nil {
		return global.Response{Message: "获取数据库路径失败: " + err.Error()}.Error()
	}
	if _, err := os.Stat(dbPath); err != nil {
		return global.Response{Message: "数据库不存在: " + dbPath}.Error()
	}

	selectedPath := normalizeDatabasePath(loadAppConfigStruct().DatabasePath)
	if normalizeDatabasePath(dbPath) == selectedPath {
		return global.Response{Message: "当前默认数据库不可删除，请先切换到其他数据库"}.Error()
	}

	if err := os.Remove(dbPath); err != nil {
		return global.Response{Message: "删除数据库失败: " + err.Error()}.Error()
	}

	return global.Response{Message: "数据库删除成功"}.Success()
}

// SelectDb 选择并初始化数据库
func (a *App) SelectDb(name string) string {
	dbPath, err := resolveDatabasePath(name)
	if err != nil {
		return global.Response{Message: "获取数据库路径失败: " + err.Error()}.Error()
	}

	if _, err := os.Stat(dbPath); err != nil {
		return global.Response{Message: "数据库文件不存在: " + dbPath}.Error()
	}

	model.InitDB(dbPath)
	if model.Conn == nil {
		return global.Response{Message: "数据库连接失败: " + dbPath}.Error()
	}
	if err := persistSelectedDatabasePath(dbPath); err != nil {
		return global.Response{Message: "数据库连接成功，但保存默认数据库失败: " + err.Error()}.Error()
	}
	databaseSelected = true
	invalidatePlayerTeamQueryCache()
	invalidateQueryCache(&teamWinRateQueryCache)
	log.Printf("数据库连接成功: %s", dbPath)
	return global.Response{Message: "数据库连接成功"}.Success()
}

// AutoConnectDb 自动连接配置的数据库
func (a *App) AutoConnectDb() string {
	return a.SelectDb("")
}

func (a *App) GetAttendanceSummary() string {
	var tasks []model.Task
	model.Conn.Where("status = ?", 1).Order("time asc, id asc").Find(&tasks)
	if tasks == nil {
		tasks = []model.Task{}
	}

	summary := AttendanceSummary{
		Tasks:   make([]AttendanceSummaryTask, 0, len(tasks)),
		Members: []AttendanceSummaryMember{},
	}

	memberIndex := map[string]int{}
	for _, task := range tasks {
		summary.Tasks = append(summary.Tasks, AttendanceSummaryTask{
			ID:   task.Id,
			Name: task.Name,
			Time: task.Time,
			Pos:  task.Pos,
		})

		for _, user := range task.UserList {
			key := fmt.Sprintf("%d:%s", user.Id, user.Name)
			memberPos, ok := memberIndex[key]
			if !ok {
				summary.Members = append(summary.Members, AttendanceSummaryMember{
					Name:    user.Name,
					Group:   user.Group,
					TaskMap: map[int]AttendanceSummaryCell{},
				})
				memberPos = len(summary.Members) - 1
				memberIndex[key] = memberPos
			}
			member := &summary.Members[memberPos]

			attended := user.AtkNum > 0 || user.DisNum > 0
			cell := AttendanceSummaryCell{
				InRoster:   true,
				Attended:   attended,
				AtkNum:     user.AtkNum,
				DisNum:     user.DisNum,
				AtkTeamNum: user.AtkTeamNum,
				DisTeamNum: user.DisTeamNum,
			}
			member.TaskMap[task.Id] = cell
			if attended {
				member.TaskAttendedCount++
			} else {
				member.TaskAbsentCount++
			}
			member.AtkNumTotal += user.AtkNum
			member.DisNumTotal += user.DisNum
			member.AtkTeamTotal += user.AtkTeamNum
			member.DisTeamTotal += user.DisTeamNum
		}
	}

	for i := range summary.Members {
		for _, task := range summary.Tasks {
			if _, ok := summary.Members[i].TaskMap[task.ID]; !ok {
				summary.Members[i].TaskMap[task.ID] = AttendanceSummaryCell{}
			}
		}
	}

	sort.Slice(summary.Members, func(i, j int) bool {
		if summary.Members[i].Group == summary.Members[j].Group {
			return summary.Members[i].Name < summary.Members[j].Name
		}
		return summary.Members[i].Group < summary.Members[j].Group
	})

	return global.Response{Data: summary}.Success()
}

// GetMaterializedStatsStatus 获取派生统计状态
func (a *App) GetMaterializedStatsStatus() string {
	states, err := getMaterializedStates()
	if err != nil {
		return global.Response{Message: "获取统计索引状态失败: " + err.Error()}.Error()
	}
	return global.Response{Data: map[string]interface{}{
		"states":            states,
		"team_ready":        materializedStateReady("player_team_snapshot"),
		"winrate_ready":     materializedStateReady("team_winrate_stats"),
		"rebuilding":        materializedStatsRebuildRunning(),
		"version":           materializedStatsVersion,
		"default_min_level": defaultWinRateMinLevel,
		"default_min_hp":    defaultWinRateMinHp,
	}}.Success()
}

// RebuildMaterializedStats 从原始战报重建派生统计
func (a *App) RebuildMaterializedStats() string {
	started, err := startMaterializedStatsRebuild()
	if err != nil {
		return global.Response{Message: "启动统计索引重建失败: " + err.Error()}.Error()
	}
	if !started {
		return global.Response{Data: map[string]interface{}{
			"started": false,
		}, Message: "统计索引正在重建中"}.Success()
	}
	invalidatePlayerTeamQueryCache()
	invalidateQueryCache(&teamWinRateQueryCache)
	return global.Response{Data: map[string]interface{}{
		"started": true,
	}, Message: "统计索引已开始后台重建"}.Success()
}

// GetLogs 获取历史日志
func (a *App) GetLogs() string {
	return global.Response{Data: global.LogW.GetLogs()}.Success()
}

// GetVersion 获取当前版本号
func (a *App) GetVersion() string {
	return global.Response{Data: global.Version}.Success()
}

// CheckNpcap 检测 Npcap 是否已安装
func (a *App) CheckNpcap() string {
	dll := windows.NewLazySystemDLL("wpcap.dll")
	err := dll.Load()
	installed := err == nil
	log.Printf("Npcap installed: %v", installed)
	return global.Response{Data: map[string]bool{"installed": installed}}.Success()
}

// CheckUpdate 检查是否有新版本
func (a *App) CheckUpdate() string {
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get("https://api.github.com/repos/FlxSNX/stzbHelper/releases/latest")
	if err != nil {
		return global.Response{Message: "检查更新失败: " + err.Error()}.Error()
	}
	defer resp.Body.Close()

	if resp.StatusCode == 404 {
		return global.Response{Data: map[string]interface{}{"hasUpdate": false, "message": "暂无发行版本"}}.Success()
	}

	if resp.StatusCode != 200 {
		return global.Response{Message: "检查更新失败，状态码: " + fmt.Sprint(resp.StatusCode)}.Error()
	}

	var release struct {
		TagName string `json:"tag_name"`
		Body    string `json:"body"`
		HTMLURL string `json:"html_url"`
		Name    string `json:"name"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&release); err != nil {
		return global.Response{Message: "解析更新信息失败: " + err.Error()}.Error()
	}

	hasUpdate := release.TagName != global.Version
	return global.Response{Data: map[string]interface{}{
		"hasUpdate":  hasUpdate,
		"latestVer":  release.TagName,
		"name":       release.Name,
		"body":       release.Body,
		"url":        release.HTMLURL,
		"currentVer": global.Version,
	}}.Success()
}

// GetPlayerTeam 查询玩家队伍
func (a *App) GetPlayerTeam(name string, uname string, idu string, page int, pageSize int) string {
	if page < 1 {
		page = 1
	}
	pageSize = normalizePlayerTeamPageSize(pageSize)

	if materializedStateReady("player_team_snapshot") {
		results, total, meta, err := queryMaterializedPlayerTeams(name, uname, idu, page, pageSize)
		if err != nil {
			return global.Response{Message: "查询统计索引失败: " + err.Error()}.Error()
		}
		log.Printf("查询玩家队伍(派生表): name=%s, union=%s, idu=%s, page=%d, total=%d, 结果=%d条, 耗时=%dms", name, uname, idu, page, total, len(results), meta.QueryMS)
		return global.Response{Data: map[string]interface{}{
			"list":      results,
			"total":     total,
			"page":      page,
			"pageSize":  pageSize,
			"query_ms":  meta.QueryMS,
			"cache_hit": false,
			"source":    "materialized",
		}}.Success()
	}

	teams, meta, err := queryEffectivePlayerTeamsWithMeta(name, uname, idu)
	if err != nil {
		return global.Response{Message: "查询失败: " + err.Error()}.Error()
	}
	results, total := paginatePlayerTeams(teams, page, pageSize)

	log.Printf("查询玩家队伍: name=%s, union=%s, idu=%s, page=%d, total=%d, 结果=%d条, 耗时=%dms, 缓存=%t", name, uname, idu, page, total, len(results), meta.QueryMS, meta.CacheHit)
	return global.Response{Data: map[string]interface{}{
		"list":      results,
		"total":     total,
		"page":      page,
		"pageSize":  pageSize,
		"query_ms":  meta.QueryMS,
		"cache_hit": meta.CacheHit,
		"source":    "raw",
	}}.Success()
}

func (a *App) GetPlayerTeamExport(name string, uname string, idu string) string {
	if materializedStateReady("player_team_snapshot") {
		teams, meta, err := queryMaterializedPlayerTeamsAll(name, uname, idu)
		if err != nil {
			return global.Response{Message: "导出统计索引失败: " + err.Error()}.Error()
		}
		return global.Response{Data: map[string]interface{}{
			"list":      teams,
			"total":     len(teams),
			"query_ms":  meta.QueryMS,
			"cache_hit": false,
			"source":    "materialized",
		}}.Success()
	}

	teams, meta, err := queryEffectivePlayerTeamsWithMeta(name, uname, idu)
	if err != nil {
		return global.Response{Message: "导出查询失败: " + err.Error()}.Error()
	}

	log.Printf("导出玩家队伍: name=%s, union=%s, idu=%s, total=%d, 耗时=%dms, 缓存=%t", name, uname, idu, len(teams), meta.QueryMS, meta.CacheHit)
	return global.Response{Data: map[string]interface{}{
		"list":      teams,
		"total":     len(teams),
		"query_ms":  meta.QueryMS,
		"cache_hit": meta.CacheHit,
		"source":    "raw",
	}}.Success()
}

// GetPlayerTeamRelatedBattles 按需查询某支队伍相关原始战报
func (a *App) GetPlayerTeamRelatedBattles(playerName string, role string, idu string, hero1ID int, hero2ID int, hero3ID int, page int, pageSize int) string {
	rows, total, err := queryRelatedBattles(playerName, role, idu, hero1ID, hero2ID, hero3ID, page, pageSize)
	if err != nil {
		return global.Response{Message: "查询相关战报失败: " + err.Error()}.Error()
	}
	return global.Response{Data: map[string]interface{}{
		"list":     rows,
		"total":    total,
		"page":     page,
		"pageSize": pageSize,
	}}.Success()
}

// HidePlayerTeam 隐藏一支队伍，并同步排除队伍查询和胜率查询
func (a *App) HidePlayerTeam(playerName string, role string, idu string, hero1ID int, hero2ID int, hero3ID int, allSkillInfo string) string {
	err := hideMaterializedPlayerTeam(playerTeam{
		PlayerName:   playerName,
		Role:         role,
		Idu:          idu,
		Hero1ID:      hero1ID,
		Hero2ID:      hero2ID,
		Hero3ID:      hero3ID,
		AllSkillInfo: allSkillInfo,
	})
	if err != nil {
		return global.Response{Message: "隐藏队伍失败: " + err.Error()}.Error()
	}
	return global.Response{Message: "已隐藏该队伍，队伍查询和胜率查询会同步排除"}.Success()
}

// GetHiddenPlayerTeams 查询已隐藏队伍
func (a *App) GetHiddenPlayerTeams(page int, pageSize int) string {
	rows, total, err := queryHiddenMaterializedTeams(page, pageSize)
	if err != nil {
		return global.Response{Message: "查询隐藏队伍失败: " + err.Error()}.Error()
	}
	return global.Response{Data: map[string]interface{}{
		"list":     rows,
		"total":    total,
		"page":     page,
		"pageSize": pageSize,
	}}.Success()
}

// RestoreHiddenPlayerTeam 恢复一支已隐藏队伍
func (a *App) RestoreHiddenPlayerTeam(id int) string {
	if err := restoreHiddenMaterializedTeam(int64(id)); err != nil {
		return global.Response{Message: "恢复隐藏队伍失败: " + err.Error()}.Error()
	}
	return global.Response{Message: "已恢复该队伍，原始战报未被删除"}.Success()
}

// GetTeamWinRate 查询队伍胜率统计
func (a *App) GetTeamWinRate(name string, uname string, idu string, page int, pageSize int, minLevel int, minHp int) string {
	queryStart := time.Now()
	type TeamWinRate struct {
		PlayerName   string  `json:"player_name"`
		Hero1Id      int64   `json:"hero1_id"`
		Hero2Id      int64   `json:"hero2_id"`
		Hero3Id      int64   `json:"hero3_id"`
		Hero1Level   int64   `json:"hero1_level"`
		Hero2Level   int64   `json:"hero2_level"`
		Hero3Level   int64   `json:"hero3_level"`
		Hero1Star    int64   `json:"hero1_star"`
		Hero2Star    int64   `json:"hero2_star"`
		Hero3Star    int64   `json:"hero3_star"`
		TotalStar    int64   `json:"total_star"`
		TotalBattles int64   `json:"total_battles"`
		WinCount     int64   `json:"win_count"`
		LossCount    int64   `json:"loss_count"`
		DrawCount    int64   `json:"draw_count"`
		WinRate      float64 `json:"win_rate"`
		LastTime     int64   `json:"last_time"`
		Idu          string  `json:"idu"`
		AllSkillInfo string  `json:"all_skill_info"`
		Role         string  `json:"role"`
	}

	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 200 {
		pageSize = 50
	}

	if data, used, err := queryMaterializedWinRateStats("player", name, uname, idu, page, pageSize, minLevel, minHp); used {
		if err != nil {
			return global.Response{Message: "查询统计索引失败: " + err.Error()}.Error()
		}
		log.Printf("查询队伍胜率(派生表): name=%s, union=%s, idu=%s, page=%d, total=%v, 耗时=%vms", name, uname, idu, page, data["total"], data["query_ms"])
		return global.Response{Data: data}.Success()
	}

	cacheKey := makeQueryCacheKey("player", name, uname, idu, page, pageSize, minLevel, minHp)
	if data, ok := getCachedQueryData(&teamWinRateQueryCache, cacheKey); ok {
		data["query_ms"] = time.Since(queryStart).Milliseconds()
		data["cache_hit"] = true
		log.Printf("查询队伍胜率命中缓存: name=%s, union=%s, idu=%s, page=%d", name, uname, idu, page)
		return global.Response{Data: data}.Success()
	}

	namePattern := "%" + name + "%"
	unamePattern := "%" + uname + "%"
	iduPattern := "%" + idu + "%"

	// 攻方: result IN (1,2,3,4,10,18,19) 胜, result=0 负, result IN (6,7,8,13) 平
	// 守方: result=0 胜, result IN (1,2,3,4,10,18,19) 负, result IN (6,7,8,13) 平
	baseQuery := `WITH battle_stats AS (
		SELECT
			attack_name AS player_name,
			attack_hero1_id AS hero1_id,
			attack_hero2_id AS hero2_id,
			attack_hero3_id AS hero3_id,
			attack_hero1_level AS hero1_level,
			attack_hero2_level AS hero2_level,
			attack_hero3_level AS hero3_level,
			attack_hero1_star AS hero1_star,
			attack_hero2_star AS hero2_star,
			attack_hero3_star AS hero3_star,
			attack_total_star AS total_star,
			attack_idu AS idu,
			time,
			all_skill_info,
			'attack' AS role,
			CASE WHEN result = 0 THEN 1 ELSE 0 END AS loss,
			CASE WHEN result IN (6,7,8,13) THEN 1 ELSE 0 END AS draw,
			CASE WHEN result IN (1,2,3,4,10,18,19) THEN 1 ELSE 0 END AS win
		FROM battle_report
		WHERE attack_hero1_id != 0 AND attack_hero2_id != 0 AND attack_hero3_id != 0
			AND attack_hero1_level >= ? AND attack_hero2_level >= ? AND attack_hero3_level >= ?
			AND attack_hp >= ?
			AND defend_hero1_level >= ? AND defend_hero2_level >= ? AND defend_hero3_level >= ?
			AND defend_hp >= ?
			AND LENGTH(all_skill_info) - LENGTH(REPLACE(all_skill_info, ';', '')) = 6
			AND LENGTH(REPLACE(all_skill_info, ',0,', ',')) = LENGTH(all_skill_info)
			AND attack_name LIKE ? AND attack_union_name LIKE ? AND attack_idu LIKE ?
			AND npc = 0 AND result IN (0,1,2,3,4,6,7,8,10,13,18,19)
			AND NOT EXISTS (
				SELECT 1 FROM materialized_team_exclusion e
				WHERE e.lineup_key = printf('%d_%d_%d', attack_hero1_id, attack_hero2_id, attack_hero3_id)
					AND (e.player_name = '' OR e.player_name = attack_name)
					AND (e.role = '' OR e.role = 'attack')
					AND (e.idu = '' OR e.idu = attack_idu)
			)
		UNION ALL
		SELECT
			defend_name AS player_name,
			defend_hero1_id AS hero1_id,
			defend_hero2_id AS hero2_id,
			defend_hero3_id AS hero3_id,
			defend_hero1_level AS hero1_level,
			defend_hero2_level AS hero2_level,
			defend_hero3_level AS hero3_level,
			defend_hero1_star AS hero1_star,
			defend_hero2_star AS hero2_star,
			defend_hero3_star AS hero3_star,
			defend_total_star AS total_star,
			defend_idu AS idu,
			time,
			all_skill_info,
			'defend' AS role,
			CASE WHEN result IN (1,2,3,4,10,18,19) THEN 1 ELSE 0 END AS loss,
			CASE WHEN result IN (6,7,8,13) THEN 1 ELSE 0 END AS draw,
			CASE WHEN result = 0 THEN 1 ELSE 0 END AS win
		FROM battle_report
		WHERE defend_hero1_id != 0 AND defend_hero2_id != 0 AND defend_hero3_id != 0
			AND defend_hero1_level >= ? AND defend_hero2_level >= ? AND defend_hero3_level >= ?
			AND defend_hp >= ?
			AND attack_hero1_level >= ? AND attack_hero2_level >= ? AND attack_hero3_level >= ?
			AND attack_hp >= ?
			AND LENGTH(all_skill_info) - LENGTH(REPLACE(all_skill_info, ';', '')) = 6
			AND LENGTH(REPLACE(all_skill_info, ',0,', ',')) = LENGTH(all_skill_info)
			AND defend_name LIKE ? AND defend_union_name LIKE ? AND defend_idu LIKE ?
			AND npc = 0 AND result IN (0,1,2,3,4,6,7,8,10,13,18,19)
			AND NOT EXISTS (
				SELECT 1 FROM materialized_team_exclusion e
				WHERE e.lineup_key = printf('%d_%d_%d', defend_hero1_id, defend_hero2_id, defend_hero3_id)
					AND (e.player_name = '' OR e.player_name = defend_name)
					AND (e.role = '' OR e.role = 'defend')
					AND (e.idu = '' OR e.idu = defend_idu)
			)
	),
	aggregated AS (
		SELECT
			player_name, hero1_id, hero2_id, hero3_id,
			MAX(hero1_level) AS hero1_level,
			MAX(hero2_level) AS hero2_level,
			MAX(hero3_level) AS hero3_level,
			MAX(hero1_star) AS hero1_star,
			MAX(hero2_star) AS hero2_star,
			MAX(hero3_star) AS hero3_star,
			MAX(total_star) AS total_star,
			SUBSTR(MAX(time || '|' || idu), INSTR(MAX(time || '|' || idu), '|') + 1) AS idu,
			MAX(time) AS last_time,
			SUBSTR(MAX(time || '_' || all_skill_info), INSTR(MAX(time || '_' || all_skill_info), '_') + 1) AS all_skill_info,
			SUBSTR(MAX(time || '_' || role), INSTR(MAX(time || '_' || role), '_') + 1) AS role,
			SUM(win) AS win_count,
			SUM(loss) AS loss_count,
			SUM(draw) AS draw_count,
			COUNT(*) AS total_battles
		FROM battle_stats
		GROUP BY player_name, hero1_id, hero2_id, hero3_id
	)`

	args := []interface{}{
		minLevel, minLevel, minLevel, minHp, minLevel, minLevel, minLevel, minHp, namePattern, unamePattern, iduPattern,
		minLevel, minLevel, minLevel, minHp, minLevel, minLevel, minLevel, minHp, namePattern, unamePattern, iduPattern,
	}

	// 单次查询：用窗口函数同时获取总数和分页数据
	offset := (page - 1) * pageSize
	singleQuery := baseQuery + ` SELECT
		player_name, hero1_id, hero2_id, hero3_id,
		hero1_level, hero2_level, hero3_level, hero1_star, hero2_star, hero3_star,
		total_star, idu, last_time, all_skill_info, role,
		win_count, loss_count, draw_count, total_battles,
		ROUND(CAST(win_count AS REAL) / total_battles * 100, 1) AS win_rate,
		COUNT(*) OVER() AS total_count
		FROM aggregated
		ORDER BY total_battles DESC, win_rate DESC
		LIMIT ? OFFSET ?`

	var results []struct {
		TeamWinRate
		TotalCount int64 `json:"total_count" gorm:"column:total_count"`
	}
	if err := model.Conn.Raw(singleQuery, append(args, pageSize, offset)...).Scan(&results).Error; err != nil {
		return global.Response{Message: "查询失败: " + err.Error()}.Error()
	}

	var total int64
	winRateResults := make([]TeamWinRate, 0, len(results))
	for _, r := range results {
		if total == 0 {
			total = r.TotalCount
		}
		winRateResults = append(winRateResults, r.TeamWinRate)
	}

	data := map[string]interface{}{
		"list":      winRateResults,
		"total":     total,
		"page":      page,
		"pageSize":  pageSize,
		"query_ms":  time.Since(queryStart).Milliseconds(),
		"cache_hit": false,
		"source":    "raw",
	}
	setCachedQueryData(&teamWinRateQueryCache, cacheKey, data)
	log.Printf("查询队伍胜率: name=%s, union=%s, idu=%s, page=%d, total=%d, 结果: %d条, 耗时=%dms", name, uname, idu, page, total, len(winRateResults), data["query_ms"])
	return global.Response{Data: data}.Success()
}

func (a *App) GetTeamWinRateByTeam(name string, uname string, idu string, page int, pageSize int, minLevel int, minHp int) string {
	queryStart := time.Now()
	type TeamWinRateByTeam struct {
		Hero1Id      int64   `json:"hero1_id"`
		Hero2Id      int64   `json:"hero2_id"`
		Hero3Id      int64   `json:"hero3_id"`
		Hero1Level   int64   `json:"hero1_level"`
		Hero2Level   int64   `json:"hero2_level"`
		Hero3Level   int64   `json:"hero3_level"`
		Hero1Star    int64   `json:"hero1_star"`
		Hero2Star    int64   `json:"hero2_star"`
		Hero3Star    int64   `json:"hero3_star"`
		TotalStar    int64   `json:"total_star"`
		TotalBattles int64   `json:"total_battles"`
		WinCount     int64   `json:"win_count"`
		LossCount    int64   `json:"loss_count"`
		DrawCount    int64   `json:"draw_count"`
		WinRate      float64 `json:"win_rate"`
		LastTime     int64   `json:"last_time"`
		AllSkillInfo string  `json:"all_skill_info"`
		Role         string  `json:"role"`
		Players      string  `json:"players"`
	}

	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 200 {
		pageSize = 50
	}

	if data, used, err := queryMaterializedWinRateStats("team", name, uname, idu, page, pageSize, minLevel, minHp); used {
		if err != nil {
			return global.Response{Message: "查询统计索引失败: " + err.Error()}.Error()
		}
		log.Printf("查询队伍胜率(按队伍/派生表): name=%s, union=%s, idu=%s, page=%d, total=%v, 耗时=%vms", name, uname, idu, page, data["total"], data["query_ms"])
		return global.Response{Data: data}.Success()
	}

	cacheKey := makeQueryCacheKey("team", name, uname, idu, page, pageSize, minLevel, minHp)
	if data, ok := getCachedQueryData(&teamWinRateQueryCache, cacheKey); ok {
		data["query_ms"] = time.Since(queryStart).Milliseconds()
		data["cache_hit"] = true
		log.Printf("查询队伍胜率(按队伍)命中缓存: name=%s, union=%s, idu=%s, page=%d", name, uname, idu, page)
		return global.Response{Data: data}.Success()
	}

	namePattern := "%" + name + "%"
	unamePattern := "%" + uname + "%"
	iduPattern := "%" + idu + "%"

	baseQuery := `WITH battle_stats AS (
		SELECT
			attack_name AS player_name,
			attack_hero1_id AS hero1_id,
			attack_hero2_id AS hero2_id,
			attack_hero3_id AS hero3_id,
			attack_hero1_level AS hero1_level,
			attack_hero2_level AS hero2_level,
			attack_hero3_level AS hero3_level,
			attack_hero1_star AS hero1_star,
			attack_hero2_star AS hero2_star,
			attack_hero3_star AS hero3_star,
			attack_total_star AS total_star,
			time,
			all_skill_info,
			'attack' AS role,
			CASE WHEN result = 0 THEN 1 ELSE 0 END AS loss,
			CASE WHEN result IN (6,7,8,13) THEN 1 ELSE 0 END AS draw,
			CASE WHEN result IN (1,2,3,4,10,18,19) THEN 1 ELSE 0 END AS win
		FROM battle_report
		WHERE attack_hero1_id != 0 AND attack_hero2_id != 0 AND attack_hero3_id != 0
			AND attack_hero1_level >= ? AND attack_hero2_level >= ? AND attack_hero3_level >= ?
			AND attack_hp >= ?
			AND defend_hero1_level >= ? AND defend_hero2_level >= ? AND defend_hero3_level >= ?
			AND defend_hp >= ?
			AND LENGTH(all_skill_info) - LENGTH(REPLACE(all_skill_info, ';', '')) = 6
			AND LENGTH(REPLACE(all_skill_info, ',0,', ',')) = LENGTH(all_skill_info)
			AND attack_name LIKE ? AND attack_union_name LIKE ? AND attack_idu LIKE ?
			AND npc = 0 AND result IN (0,1,2,3,4,6,7,8,10,13,18,19)
			AND NOT EXISTS (
				SELECT 1 FROM materialized_team_exclusion e
				WHERE e.lineup_key = printf('%d_%d_%d', attack_hero1_id, attack_hero2_id, attack_hero3_id)
					AND (e.player_name = '' OR e.player_name = attack_name)
					AND (e.role = '' OR e.role = 'attack')
					AND (e.idu = '' OR e.idu = attack_idu)
			)
		UNION ALL
		SELECT
			defend_name AS player_name,
			defend_hero1_id AS hero1_id,
			defend_hero2_id AS hero2_id,
			defend_hero3_id AS hero3_id,
			defend_hero1_level AS hero1_level,
			defend_hero2_level AS hero2_level,
			defend_hero3_level AS hero3_level,
			defend_hero1_star AS hero1_star,
			defend_hero2_star AS hero2_star,
			defend_hero3_star AS hero3_star,
			defend_total_star AS total_star,
			time,
			all_skill_info,
			'defend' AS role,
			CASE WHEN result IN (1,2,3,4,10,18,19) THEN 1 ELSE 0 END AS loss,
			CASE WHEN result IN (6,7,8,13) THEN 1 ELSE 0 END AS draw,
			CASE WHEN result = 0 THEN 1 ELSE 0 END AS win
		FROM battle_report
		WHERE defend_hero1_id != 0 AND defend_hero2_id != 0 AND defend_hero3_id != 0
			AND defend_hero1_level >= ? AND defend_hero2_level >= ? AND defend_hero3_level >= ?
			AND defend_hp >= ?
			AND attack_hero1_level >= ? AND attack_hero2_level >= ? AND attack_hero3_level >= ?
			AND attack_hp >= ?
			AND LENGTH(all_skill_info) - LENGTH(REPLACE(all_skill_info, ';', '')) = 6
			AND LENGTH(REPLACE(all_skill_info, ',0,', ',')) = LENGTH(all_skill_info)
			AND defend_name LIKE ? AND defend_union_name LIKE ? AND defend_idu LIKE ?
			AND npc = 0 AND result IN (0,1,2,3,4,6,7,8,10,13,18,19)
			AND NOT EXISTS (
				SELECT 1 FROM materialized_team_exclusion e
				WHERE e.lineup_key = printf('%d_%d_%d', defend_hero1_id, defend_hero2_id, defend_hero3_id)
					AND (e.player_name = '' OR e.player_name = defend_name)
					AND (e.role = '' OR e.role = 'defend')
					AND (e.idu = '' OR e.idu = defend_idu)
			)
	),
	aggregated AS (
		SELECT
			hero1_id, hero2_id, hero3_id,
			GROUP_CONCAT(DISTINCT player_name) AS players,
			MAX(hero1_level) AS hero1_level,
			MAX(hero2_level) AS hero2_level,
			MAX(hero3_level) AS hero3_level,
			MAX(hero1_star) AS hero1_star,
			MAX(hero2_star) AS hero2_star,
			MAX(hero3_star) AS hero3_star,
			MAX(total_star) AS total_star,
			MAX(time) AS last_time,
			SUBSTR(MAX(time || '_' || all_skill_info), INSTR(MAX(time || '_' || all_skill_info), '_') + 1) AS all_skill_info,
			SUBSTR(MAX(time || '_' || role), INSTR(MAX(time || '_' || role), '_') + 1) AS role,
			SUM(win) AS win_count,
			SUM(loss) AS loss_count,
			SUM(draw) AS draw_count,
			COUNT(*) AS total_battles
		FROM battle_stats
		GROUP BY hero1_id, hero2_id, hero3_id
	)`

	args := []interface{}{
		minLevel, minLevel, minLevel, minHp, minLevel, minLevel, minLevel, minHp, namePattern, unamePattern, iduPattern,
		minLevel, minLevel, minLevel, minHp, minLevel, minLevel, minLevel, minHp, namePattern, unamePattern, iduPattern,
	}

	dataQuery := baseQuery + ` SELECT hero1_id, hero2_id, hero3_id,
		hero1_level, hero2_level, hero3_level, hero1_star, hero2_star, hero3_star,
		total_star, last_time, all_skill_info, role, players,
		win_count, loss_count, draw_count, total_battles,
		ROUND(CAST(win_count AS REAL) / total_battles * 100, 1) AS win_rate
		FROM aggregated
		ORDER BY total_battles DESC, win_rate DESC
		LIMIT 5000`

	var rawResults []TeamWinRateByTeam
	if err := model.Conn.Raw(dataQuery, args...).Scan(&rawResults).Error; err != nil {
		return global.Response{Message: "查询失败: " + err.Error()}.Error()
	}

	// Go 层归一化战法并合并相同队伍
	type teamAcc struct {
		TeamWinRateByTeam
		playerSet map[string]bool
	}
	merged := make(map[string]*teamAcc)
	for _, r := range rawResults {
		// 生成归一化 key: heroIDs + 排序后的战法
		groups := strings.Split(r.AllSkillInfo, ";")
		var skillParts []string
		for _, g := range groups {
			parts := strings.Split(g, ",")
			if len(parts) < 6 {
				continue
			}
			mainSkill := parts[1]
			sub1 := parts[3]
			sub2 := parts[5]
			if sub1 > sub2 {
				sub1, sub2 = sub2, sub1
			}
			skillParts = append(skillParts, mainSkill+"_"+sub1+"_"+sub2)
		}
		key := fmt.Sprintf("%d_%d_%d|%s", r.Hero1Id, r.Hero2Id, r.Hero3Id, strings.Join(skillParts, "|"))

		if existing, ok := merged[key]; ok {
			existing.TotalBattles += r.TotalBattles
			existing.WinCount += r.WinCount
			existing.LossCount += r.LossCount
			existing.DrawCount += r.DrawCount
			if r.LastTime > existing.LastTime {
				existing.LastTime = r.LastTime
				existing.AllSkillInfo = r.AllSkillInfo
				existing.Role = r.Role
			}
			if r.Hero1Level > existing.Hero1Level {
				existing.Hero1Level = r.Hero1Level
			}
			if r.Hero2Level > existing.Hero2Level {
				existing.Hero2Level = r.Hero2Level
			}
			if r.Hero3Level > existing.Hero3Level {
				existing.Hero3Level = r.Hero3Level
			}
			for _, p := range strings.Split(r.Players, ",") {
				if p != "" {
					existing.playerSet[p] = true
				}
			}
		} else {
			ps := make(map[string]bool)
			for _, p := range strings.Split(r.Players, ",") {
				if p != "" {
					ps[p] = true
				}
			}
			merged[key] = &teamAcc{
				TeamWinRateByTeam: r,
				playerSet:         ps,
			}
		}
	}

	// 转换为切片并计算胜率、玩家列表
	var allResults []TeamWinRateByTeam
	for _, v := range merged {
		v.Players = ""
		first := true
		for p := range v.playerSet {
			if first {
				v.Players = p
				first = false
			} else {
				v.Players += "," + p
			}
		}
		if v.TotalBattles > 0 {
			v.WinRate = float64(int(float64(v.WinCount)/float64(v.TotalBattles)*1000)) / 10
		}
		allResults = append(allResults, v.TeamWinRateByTeam)
	}

	// 排序
	sort.Slice(allResults, func(i, j int) bool {
		if allResults[i].TotalBattles != allResults[j].TotalBattles {
			return allResults[i].TotalBattles > allResults[j].TotalBattles
		}
		return allResults[i].WinRate > allResults[j].WinRate
	})

	total := len(allResults)

	// 分页
	start := (page - 1) * pageSize
	end := start + pageSize
	if start > total {
		start = total
	}
	if end > total {
		end = total
	}
	pageResults := allResults[start:end]

	data := map[string]interface{}{
		"list":      pageResults,
		"total":     total,
		"page":      page,
		"pageSize":  pageSize,
		"query_ms":  time.Since(queryStart).Milliseconds(),
		"cache_hit": false,
		"source":    "raw",
	}
	setCachedQueryData(&teamWinRateQueryCache, cacheKey, data)
	log.Printf("查询队伍胜率(按队伍): name=%s, union=%s, idu=%s, page=%d, total=%d, 结果: %d条, 耗时=%dms", name, uname, idu, page, total, len(pageResults), data["query_ms"])
	return global.Response{Data: data}.Success()
}
