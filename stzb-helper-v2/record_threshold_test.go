package main

import (
	"testing"

	"stzbHelper/model"
)

// 入库门槛：进攻方三名武将等级必须全部 > MinRecordAttackHeroLevel(25)。
// 即 <= 25 丢弃、>= 26 保留。边界值最容易写错，这里逐个钉死。
func TestShouldRecordBattleReportLevelBoundary(t *testing.T) {
	mk := func(l1, l2, l3 int64) model.BattleReport {
		return model.BattleReport{
			AttackHero1Level: l1,
			AttackHero2Level: l2,
			AttackHero3Level: l3,
		}
	}

	cases := []struct {
		name   string
		report model.BattleReport
		want   bool
	}{
		{"三人全 40 级", mk(40, 40, 40), true},
		{"三人全 26 级（刚过线）", mk(26, 26, 26), true},
		{"三人全 25 级（等于阈值，丢弃）", mk(25, 25, 25), false},
		{"三人全 24 级", mk(24, 24, 24), false},
		{"只有一人 25，其余 40（应丢弃）", mk(25, 40, 40), false},
		{"只有一人 25 且在末位（应丢弃）", mk(40, 40, 25), false},
		{"只有一人 26，其余 40（应保留）", mk(26, 40, 40), true},
		{"三人全 0（等级缺失，应丢弃）", mk(0, 0, 0), false},
		{"一人 0 其余 40（数据不完整，应丢弃）", mk(0, 40, 40), false},
		{"混合 40/30/26（应保留）", mk(40, 30, 26), true},
		{"混合 40/30/25（应丢弃）", mk(40, 30, 25), false},
		{"满级 50", mk(50, 50, 50), true},
	}

	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := shouldRecordBattleReport(c.report); got != c.want {
				t.Fatalf("shouldRecordBattleReport(攻方 %d/%d/%d) = %v, want %v",
					c.report.AttackHero1Level, c.report.AttackHero2Level, c.report.AttackHero3Level,
					got, c.want)
			}
		})
	}
}

// 阈值常量本身必须与需求一致：<= 25 丢弃，也就是门槛值 25。
func TestMinRecordAttackHeroLevelValue(t *testing.T) {
	if MinRecordAttackHeroLevel != 25 {
		t.Fatalf("MinRecordAttackHeroLevel = %d, want 25（<= 25 级不入库）", MinRecordAttackHeroLevel)
	}
}

// 查询侧门槛是「严格大于 30」，与入库门槛的「<= 25 丢弃」是两套值，不能混。
func TestMinTeamHeroLevelValue(t *testing.T) {
	if MinTeamHeroLevel != 30 {
		t.Fatalf("MinTeamHeroLevel = %d, want 30（队伍查询要求 > 30 级）", MinTeamHeroLevel)
	}
}

// 查询侧阈值兜底：前端传入低于 30 时抬到 30，高于 30 时尊重原值。
func TestEffectiveMinTeamHeroLevel(t *testing.T) {
	cases := []struct{ in, want int }{
		{0, 30},
		{1, 30},
		{15, 30},
		{29, 30},
		{30, 30},
		{31, 31},
		{40, 40},
	}
	for _, c := range cases {
		if got := effectiveMinTeamHeroLevel(c.in); got != c.want {
			t.Fatalf("effectiveMinTeamHeroLevel(%d) = %d, want %d", c.in, got, c.want)
		}
	}
}
