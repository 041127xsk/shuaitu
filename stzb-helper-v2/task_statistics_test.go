package main

import (
	"encoding/json"
	"path/filepath"
	"testing"

	"stzbHelper/model"
)

func TestStatisticsReportReturnsUpdatedTaskData(t *testing.T) {
	defer closeModelConn(t)

	dbPath := filepath.Join(t.TempDir(), "stats.db")
	model.InitDB(dbPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create database")
	}

	task := model.Task{
		Name:            "测试攻城",
		Pos:             10010001,
		Status:          0,
		DisMaxLevel:     20,
		AtkMinLevel:     25,
		Target:          []string{"一队"},
		TargetUserNum:   2,
		CompleteUserNum: 0,
		UserList: map[int]*model.TaskUserList{
			1: {Id: 1, Name: "张三", Group: "一队"},
			2: {Id: 2, Name: "李四", Group: "一队"},
		},
	}
	if err := model.Conn.Create(&task).Error; err != nil {
		t.Fatalf("create task: %v", err)
	}

	reports := []model.Report{
		{BattleID: 1, Wid: 10010001, AttackName: "张三", AttackBaseLevel: 35, AttackHp: 12000},
		{BattleID: 2, Wid: 10010001, AttackName: "张三", AttackBaseLevel: 18, AttackHp: 8000},
		{BattleID: 3, Wid: 10010001, AttackName: "李四", AttackBaseLevel: 25, AttackHp: 9000},
	}
	if err := model.Conn.Create(&reports).Error; err != nil {
		t.Fatalf("create reports: %v", err)
	}

	app := &App{}
	resp := decodeAppResponse(t, app.StatisticsReport(task.Id))
	if resp.Code != 200 {
		t.Fatalf("StatisticsReport response = %+v", resp)
	}

	var updated model.Task
	if err := json.Unmarshal(resp.Data, &updated); err != nil {
		t.Fatalf("unmarshal updated task: %v", err)
	}

	if updated.Id != task.Id {
		t.Fatalf("updated.Id = %d, want %d", updated.Id, task.Id)
	}
	if updated.CompleteUserNum != 2 {
		t.Fatalf("updated.CompleteUserNum = %d, want 2", updated.CompleteUserNum)
	}
	if updated.Status != 1 {
		t.Fatalf("updated.Status = %d, want 1", updated.Status)
	}
	if updated.UserList[1].AtkNum != 1 {
		t.Fatalf("updated.UserList[1].AtkNum = %d, want 1", updated.UserList[1].AtkNum)
	}
	if updated.UserList[1].AtkTeamNum != 1 {
		t.Fatalf("updated.UserList[1].AtkTeamNum = %d, want 1", updated.UserList[1].AtkTeamNum)
	}
	if updated.UserList[1].DisNum != 1 {
		t.Fatalf("updated.UserList[1].DisNum = %d, want 1", updated.UserList[1].DisNum)
	}
	if updated.UserList[1].DisTeamNum != 1 {
		t.Fatalf("updated.UserList[1].DisTeamNum = %d, want 1", updated.UserList[1].DisTeamNum)
	}
	if updated.UserList[2].AtkNum != 1 {
		t.Fatalf("updated.UserList[2].AtkNum = %d, want 1", updated.UserList[2].AtkNum)
	}
	if updated.UserList[2].DisNum != 0 {
		t.Fatalf("updated.UserList[2].DisNum = %d, want 0", updated.UserList[2].DisNum)
	}
	if updated.UserList[2].AtkTeamNum != 1 {
		t.Fatalf("updated.UserList[2].AtkTeamNum = %d, want 1", updated.UserList[2].AtkTeamNum)
	}
}

func TestStatisticsReportDoesNotAccumulateOnRepeatedRuns(t *testing.T) {
	defer closeModelConn(t)

	dbPath := filepath.Join(t.TempDir(), "stats-repeat.db")
	model.InitDB(dbPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create database")
	}

	task := model.Task{
		Name:            "重复统计测试",
		Pos:             20020002,
		Status:          0,
		DisMaxLevel:     20,
		AtkMinLevel:     25,
		Target:          []string{"二队"},
		TargetUserNum:   1,
		CompleteUserNum: 0,
		UserList: map[int]*model.TaskUserList{
			1: {Id: 1, Name: "樱丨月檬远", Group: "二队"},
		},
	}
	if err := model.Conn.Create(&task).Error; err != nil {
		t.Fatalf("create task: %v", err)
	}

	reports := []model.Report{
		{BattleID: 11, Wid: 20020002, AttackName: "樱丨月檬远", AttackBaseLevel: 8, AttackHp: 7000},
		{BattleID: 12, Wid: 20020002, AttackName: "樱丨月檬远", AttackBaseLevel: 35, AttackHp: 12000},
	}
	if err := model.Conn.Create(&reports).Error; err != nil {
		t.Fatalf("create reports: %v", err)
	}

	app := &App{}
	firstResp := decodeAppResponse(t, app.StatisticsReport(task.Id))
	if firstResp.Code != 200 {
		t.Fatalf("first StatisticsReport response = %+v", firstResp)
	}

	secondResp := decodeAppResponse(t, app.StatisticsReport(task.Id))
	if secondResp.Code != 200 {
		t.Fatalf("second StatisticsReport response = %+v", secondResp)
	}

	var updated model.Task
	if err := json.Unmarshal(secondResp.Data, &updated); err != nil {
		t.Fatalf("unmarshal updated task: %v", err)
	}

	if updated.UserList[1].AtkNum != 1 {
		t.Fatalf("updated.UserList[1].AtkNum = %d, want 1", updated.UserList[1].AtkNum)
	}
	if updated.UserList[1].DisNum != 1 {
		t.Fatalf("updated.UserList[1].DisNum = %d, want 1", updated.UserList[1].DisNum)
	}
	if updated.UserList[1].AtkTeamNum != 1 {
		t.Fatalf("updated.UserList[1].AtkTeamNum = %d, want 1", updated.UserList[1].AtkTeamNum)
	}
	if updated.UserList[1].DisTeamNum != 1 {
		t.Fatalf("updated.UserList[1].DisTeamNum = %d, want 1", updated.UserList[1].DisTeamNum)
	}
}

func TestCreateTaskPersistsAttendanceRule(t *testing.T) {
	defer closeModelConn(t)

	dbPath := filepath.Join(t.TempDir(), "task-create.db")
	model.InitDB(dbPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create database")
	}

	app := &App{}
	resp := decodeAppResponse(t, app.CreateTask("带规则任务", 1234567890, []string{"一队"}, []string{"100", "1001"}, 19, 27))
	if resp.Code != 200 {
		t.Fatalf("CreateTask response = %+v", resp)
	}

	var created model.Task
	if err := json.Unmarshal(resp.Data, &created); err != nil {
		t.Fatalf("unmarshal created task: %v", err)
	}
	if created.DisMaxLevel != 19 {
		t.Fatalf("created.DisMaxLevel = %d, want 19", created.DisMaxLevel)
	}
	if created.AtkMinLevel != 27 {
		t.Fatalf("created.AtkMinLevel = %d, want 27", created.AtkMinLevel)
	}
}

func TestStatisticsReportRejectsTaskWithoutAttendanceRule(t *testing.T) {
	defer closeModelConn(t)

	dbPath := filepath.Join(t.TempDir(), "stats-missing-rule.db")
	model.InitDB(dbPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create database")
	}

	task := model.Task{
		Name:            "老任务",
		Pos:             30030003,
		Status:          0,
		Target:          []string{"三队"},
		TargetUserNum:   1,
		CompleteUserNum: 0,
		UserList: map[int]*model.TaskUserList{
			1: {Id: 1, Name: "王五", Group: "三队"},
		},
	}
	if err := model.Conn.Create(&task).Error; err != nil {
		t.Fatalf("create task: %v", err)
	}

	app := &App{}
	resp := decodeAppResponse(t, app.StatisticsReport(task.Id))
	if resp.Code == 200 {
		t.Fatalf("StatisticsReport response = %+v, want error", resp)
	}
}

func TestUpdateTaskAttendanceRuleAffectsStatistics(t *testing.T) {
	defer closeModelConn(t)

	dbPath := filepath.Join(t.TempDir(), "stats-update-rule.db")
	model.InitDB(dbPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create database")
	}

	task := model.Task{
		Name:            "改规则任务",
		Pos:             40040004,
		Status:          0,
		DisMaxLevel:     15,
		AtkMinLevel:     30,
		Target:          []string{"四队"},
		TargetUserNum:   1,
		CompleteUserNum: 0,
		UserList: map[int]*model.TaskUserList{
			1: {Id: 1, Name: "赵六", Group: "四队"},
		},
	}
	if err := model.Conn.Create(&task).Error; err != nil {
		t.Fatalf("create task: %v", err)
	}

	reports := []model.Report{
		{BattleID: 21, Wid: 40040004, AttackName: "赵六", AttackBaseLevel: 20, AttackHp: 7000},
		{BattleID: 22, Wid: 40040004, AttackName: "赵六", AttackBaseLevel: 28, AttackHp: 12000},
	}
	if err := model.Conn.Create(&reports).Error; err != nil {
		t.Fatalf("create reports: %v", err)
	}

	app := &App{}
	resp := decodeAppResponse(t, app.UpdateTaskAttendanceRule(task.Id, 20, 28))
	if resp.Code != 200 {
		t.Fatalf("UpdateTaskAttendanceRule response = %+v", resp)
	}

	statsResp := decodeAppResponse(t, app.StatisticsReport(task.Id))
	if statsResp.Code != 200 {
		t.Fatalf("StatisticsReport response = %+v", statsResp)
	}

	var updated model.Task
	if err := json.Unmarshal(statsResp.Data, &updated); err != nil {
		t.Fatalf("unmarshal updated task: %v", err)
	}
	if updated.UserList[1].DisNum != 1 {
		t.Fatalf("updated.UserList[1].DisNum = %d, want 1", updated.UserList[1].DisNum)
	}
	if updated.UserList[1].AtkNum != 1 {
		t.Fatalf("updated.UserList[1].AtkNum = %d, want 1", updated.UserList[1].AtkNum)
	}
}

func TestUpdateTaskRebuildsTargetUsersAndResetsAttendanceState(t *testing.T) {
	defer closeModelConn(t)
	resetCaptureFlags()

	dbPath := filepath.Join(t.TempDir(), "task-update.db")
	model.InitDB(dbPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create database")
	}

	teamUsers := []model.TeamUser{
		{Id: 1, Name: "张三", Group: "一队"},
		{Id: 2, Name: "李四", Group: "二队"},
	}
	if err := model.Conn.Create(&teamUsers).Error; err != nil {
		t.Fatalf("create team users: %v", err)
	}

	task := model.Task{
		Name:            "原任务",
		Time:            123,
		Pos:             model.ToTaskPos([]string{"100", "1001"}),
		Status:          1,
		DisMaxLevel:     19,
		AtkMinLevel:     25,
		Target:          []string{"一队"},
		TargetUserNum:   1,
		CompleteUserNum: 1,
		UserList: map[int]*model.TaskUserList{
			1: {Id: 1, Name: "张三", Group: "一队", AtkNum: 2, AtkTeamNum: 2},
		},
	}
	if err := model.Conn.Create(&task).Error; err != nil {
		t.Fatalf("create task: %v", err)
	}

	reports := []model.Report{
		{BattleID: 31, Wid: task.Pos, AttackName: "张三", AttackBaseLevel: 35},
	}
	if err := model.Conn.Create(&reports).Error; err != nil {
		t.Fatalf("create reports: %v", err)
	}

	app := &App{}
	resp := decodeAppResponse(t, app.UpdateTask(task.Id, "新任务", 456, []string{"二队"}, []string{"100", "1002"}, 18, 30))
	if resp.Code != 200 {
		t.Fatalf("UpdateTask response = %+v", resp)
	}

	var updated model.Task
	if err := json.Unmarshal(resp.Data, &updated); err != nil {
		t.Fatalf("unmarshal updated task: %v", err)
	}
	if updated.Name != "新任务" {
		t.Fatalf("updated.Name = %q, want 新任务", updated.Name)
	}
	if updated.TargetUserNum != 1 {
		t.Fatalf("updated.TargetUserNum = %d, want 1", updated.TargetUserNum)
	}
	if updated.CompleteUserNum != 0 {
		t.Fatalf("updated.CompleteUserNum = %d, want 0", updated.CompleteUserNum)
	}
	if updated.Status != 0 {
		t.Fatalf("updated.Status = %d, want 0", updated.Status)
	}
	if _, ok := updated.UserList[2]; !ok {
		t.Fatalf("updated.UserList missing rebuilt target member: %+v", updated.UserList)
	}
	if _, ok := updated.UserList[1]; ok {
		t.Fatalf("updated.UserList still contains old target member: %+v", updated.UserList)
	}
	if resp.Message == "" {
		t.Fatal("UpdateTask response message empty, want warning about existing reports")
	}
}

func TestUpdateTaskRejectsEditingTaskInActiveAttendanceMode(t *testing.T) {
	defer closeModelConn(t)
	resetCaptureFlags()

	dbPath := filepath.Join(t.TempDir(), "task-update-active.db")
	model.InitDB(dbPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create database")
	}

	task := model.Task{
		Name:        "进行中任务",
		Time:        123,
		Pos:         model.ToTaskPos([]string{"200", "2002"}),
		DisMaxLevel: 19,
		AtkMinLevel: 25,
		Target:      []string{"一队"},
		UserList:    map[int]*model.TaskUserList{},
	}
	if err := model.Conn.Create(&task).Error; err != nil {
		t.Fatalf("create task: %v", err)
	}

	setCaptureMode("attendance_report", task.Pos)

	app := &App{}
	resp := decodeAppResponse(t, app.UpdateTask(task.Id, "不允许修改", 456, []string{"一队"}, []string{"200", "2002"}, 19, 25))
	if resp.Code == 200 {
		t.Fatalf("UpdateTask response = %+v, want error", resp)
	}
}

func TestGetAttendanceSummaryAggregatesAcrossCompletedTasks(t *testing.T) {
	defer closeModelConn(t)

	dbPath := filepath.Join(t.TempDir(), "attendance-summary.db")
	model.InitDB(dbPath)
	if model.Conn == nil {
		t.Fatal("InitDB did not create database")
	}

	tasks := []model.Task{
		{
			Name:            "任务A",
			Time:            100,
			Pos:             10010001,
			Status:          1,
			DisMaxLevel:     19,
			AtkMinLevel:     25,
			Target:          []string{"一队"},
			TargetUserNum:   2,
			CompleteUserNum: 1,
			UserList: map[int]*model.TaskUserList{
				1: {Id: 1, Name: "张三", Group: "一队", AtkNum: 2, AtkTeamNum: 2},
				2: {Id: 2, Name: "李四", Group: "一队", AtkNum: 0, DisNum: 0},
			},
		},
		{
			Name:            "任务B",
			Time:            200,
			Pos:             10010002,
			Status:          1,
			DisMaxLevel:     19,
			AtkMinLevel:     25,
			Target:          []string{"二队"},
			TargetUserNum:   2,
			CompleteUserNum: 2,
			UserList: map[int]*model.TaskUserList{
				1: {Id: 1, Name: "张三", Group: "一队", DisNum: 1, DisTeamNum: 1},
				3: {Id: 3, Name: "王五", Group: "二队", AtkNum: 1, AtkTeamNum: 1},
			},
		},
		{
			Name:            "未统计任务",
			Time:            300,
			Pos:             10010003,
			Status:          0,
			DisMaxLevel:     19,
			AtkMinLevel:     25,
			Target:          []string{"三队"},
			TargetUserNum:   1,
			CompleteUserNum: 0,
			UserList: map[int]*model.TaskUserList{
				4: {Id: 4, Name: "赵六", Group: "三队"},
			},
		},
	}
	if err := model.Conn.Create(&tasks).Error; err != nil {
		t.Fatalf("create tasks: %v", err)
	}

	app := &App{}
	resp := decodeAppResponse(t, app.GetAttendanceSummary())
	if resp.Code != 200 {
		t.Fatalf("GetAttendanceSummary response = %+v", resp)
	}

	var summary AttendanceSummary
	if err := json.Unmarshal(resp.Data, &summary); err != nil {
		t.Fatalf("unmarshal summary: %v", err)
	}
	if len(summary.Tasks) != 2 {
		t.Fatalf("len(summary.Tasks) = %d, want 2", len(summary.Tasks))
	}
	if len(summary.Members) != 3 {
		t.Fatalf("len(summary.Members) = %d, want 3", len(summary.Members))
	}

	var zhang AttendanceSummaryMember
	for _, member := range summary.Members {
		if member.Name == "张三" {
			zhang = member
			break
		}
	}
	if zhang.Name == "" {
		t.Fatal("missing 张三 in summary")
	}
	if zhang.TaskAttendedCount != 2 {
		t.Fatalf("张三.TaskAttendedCount = %d, want 2", zhang.TaskAttendedCount)
	}
	if zhang.TaskAbsentCount != 0 {
		t.Fatalf("张三.TaskAbsentCount = %d, want 0", zhang.TaskAbsentCount)
	}
	if zhang.AtkNumTotal != 2 || zhang.DisNumTotal != 1 {
		t.Fatalf("张三 totals = %+v, want atk=2 dis=1", zhang)
	}

	var li AttendanceSummaryMember
	for _, member := range summary.Members {
		if member.Name == "李四" {
			li = member
			break
		}
	}
	if li.TaskAbsentCount != 1 {
		t.Fatalf("李四.TaskAbsentCount = %d, want 1", li.TaskAbsentCount)
	}
	if cell, ok := li.TaskMap[tasks[1].Id]; !ok || cell.InRoster {
		t.Fatalf("李四 task B cell = %+v, want not in roster", cell)
	}
}
