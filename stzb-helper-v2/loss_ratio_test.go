package main

import (
	"math"
	"testing"
)

// parseHeroLossInfo 解析 "ID,等级,开战兵力,剩余兵力,死兵;..." 格式。
//
// 字段语义（全库 21549 场验证）：
//
//	第3位 = 开战兵力，第4位 = 战后剩余，第5位 = 死兵
//	伤兵 = 开战 - 剩余 - 死兵（报文无独立字段，需算出）
//	战损 = 伤兵 + 死兵 = 开战 - 剩余
func TestParseHeroLossInfo(t *testing.T) {
	cases := []struct {
		name      string
		info      string
		wantTotal int64
		wantRemain int64
		wantWounded int64
		wantKilled  int64
		wantLost    int64 // 战损 = 伤 + 死 = 开战 - 剩余
		wantValid   bool
	}{
		{
			name:        "用户截图里的吕蒙：开战9100 剩余7750 死842",
			info:        "100002,41,9100,7750,842;",
			wantTotal:   9100,
			wantRemain:  7750,
			wantWounded: 9100 - 7750 - 842, // 508
			wantKilled:  842,
			wantLost:    1350,
			wantValid:   true,
		},
		{
			name:        "零损失：剩余等于开战，死兵为0",
			info:        "100683,40,7623,7623,0;",
			wantTotal:   7623,
			wantRemain:  7623,
			wantWounded: 0,
			wantKilled:  0,
			wantLost:    0,
			wantValid:   true,
		},
		{
			name:        "被打光：剩余0，死兵占一部分",
			info:        "100477,41,9247,0,3829;",
			wantTotal:   9247,
			wantRemain:  0,
			wantWounded: 9247 - 3829,
			wantKilled:  3829,
			wantLost:    9247,
			wantValid:   true,
		},
		{
			name:        "三武将相加",
			info:        "100029,40,8100,4033,2328;100030,40,8100,2845,1316;",
			wantTotal:   8100 * 2,
			wantRemain:  4033 + 2845,
			wantWounded: (8100 - 4033 - 2328) + (8100 - 2845 - 1316),
			wantKilled:  2328 + 1316,
			wantLost:    (8100 - 4033) + (8100 - 2845),
			wantValid:   true,
		},
		{
			name:      "NPC 全零数据视为不可用",
			info:      "0,0,0,0,0;0,0,0,0,0;0,0,0,0,0;",
			wantValid: false,
		},
		{
			name:      "空字符串",
			info:      "",
			wantValid: false,
		},
		{
			name:        "部分武将ID为0（只统计有效武将）",
			info:        "100619,39,3097,1500,1000;0,0,0,0,0;",
			wantTotal:   3097,
			wantRemain:  1500,
			wantWounded: 3097 - 1500 - 1000, // 597
			wantKilled:  1000,
			wantLost:    1597,
			wantValid:   true,
		},
		{
			name:      "字段不足的记录被跳过",
			info:      "100619,39,3097;100741,34,2168,1000,500;",
			wantTotal:   2168,
			wantRemain:  1000,
			wantWounded: 2168 - 1000 - 500, // 668
			wantKilled:  500,
			wantLost:    1168,
			wantValid:   true,
		},
	}

	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := parseHeroLossInfo(c.info)
			if got.Valid != c.wantValid {
				t.Fatalf("Valid = %v, want %v", got.Valid, c.wantValid)
			}
			if !c.wantValid {
				return
			}
			if got.TotalHp != c.wantTotal {
				t.Fatalf("TotalHp(开战) = %d, want %d", got.TotalHp, c.wantTotal)
			}
			if got.RemainHp != c.wantRemain {
				t.Fatalf("RemainHp(剩余) = %d, want %d", got.RemainHp, c.wantRemain)
			}
			if got.Wounded != c.wantWounded {
				t.Fatalf("Wounded(伤兵) = %d, want %d", got.Wounded, c.wantWounded)
			}
			if got.Killed != c.wantKilled {
				t.Fatalf("Killed(死兵) = %d, want %d", got.Killed, c.wantKilled)
			}
			if got.LostHp != c.wantLost {
				t.Fatalf("LostHp(战损) = %d, want %d", got.LostHp, c.wantLost)
			}
			// 恒等式：剩余 + 伤兵 + 死兵 == 开战
			if got.RemainHp+got.Wounded+got.Killed != got.TotalHp {
				t.Fatalf("剩余(%d)+伤(%d)+死(%d) != 开战(%d)",
					got.RemainHp, got.Wounded, got.Killed, got.TotalHp)
			}
			if got.LostHp != got.TotalHp-got.RemainHp {
				t.Fatalf("战损(%d) != 开战-剩余(%d)", got.LostHp, got.TotalHp-got.RemainHp)
			}
			if got.Anomaly {
				t.Fatalf("正常数据被误判为异常")
			}
		})
	}
}

// 脏数据：剩余 + 死兵 > 开战时，伤兵按 0 兜底并标记异常，不能出现负数。
func TestParseHeroLossInfoHandlesDirtyData(t *testing.T) {
	// 剩余 800 + 死兵 900 = 1700 > 开战 1000，伤兵算出来是 -700
	got := parseHeroLossInfo("100001,40,1000,800,900;")
	if got.Wounded != 0 {
		t.Fatalf("Wounded = %d, want 0（负值必须兜底为 0）", got.Wounded)
	}
	if !got.Anomaly {
		t.Fatal("脏数据未被标记为异常")
	}
	if got.LostHp < 0 {
		t.Fatalf("战损出现负数: %d", got.LostHp)
	}

	// 剩余超过开战兵力：按满编剩余处理
	over := parseHeroLossInfo("100001,40,1000,5000,0;")
	if over.RemainHp != 1000 {
		t.Fatalf("RemainHp = %d, want 1000（剩余不得超过开战）", over.RemainHp)
	}
	if !over.Anomaly {
		t.Fatal("剩余超限未被标记为异常")
	}
	if over.LostHp != 0 {
		t.Fatalf("LostHp = %d, want 0", over.LostHp)
	}
}

// 损耗率 = 我方战损 / 我方开战兵力，必须 <= 1。
// 这里把「分子分母颠倒」这个历史 bug 钉死：
// 早先误写成 computeLossRatio(ourLost, ourTotalHp)，得到的是 开战/战损。
func TestComputeDestroyedRate(t *testing.T) {
	cases := []struct {
		name       string
		ourLost    int64
		ourTotalHp int64
		want       float64
	}{
		{"用户截图队伍1：79433/190100", 79433, 190100, 79433.0 / 190100.0},
		{"用户截图队伍2：138338/236570", 138338, 236570, 138338.0 / 236570.0},
		{"零损失", 0, 100000, 0},
		{"打光", 100000, 100000, 1.0},
		{"分母为0（无法计算）", 5000, 0, 0},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := computeDestroyedRate(c.ourLost, c.ourTotalHp)
			if math.Abs(got-c.want) > 1e-9 {
				t.Fatalf("computeDestroyedRate(%d,%d) = %v, want %v", c.ourLost, c.ourTotalHp, got, c.want)
			}
			if got > 1.0 {
				t.Fatalf("损耗率 %v 超过 1", got)
			}
		})
	}

	// 关键回归：两者绝不能被搞混
	ourLost, ourTotalHp := int64(79433), int64(190100)
	destroyed := computeDestroyedRate(ourLost, ourTotalHp)
	if destroyed > 1 {
		t.Fatalf("损耗率 = %v > 1，分子分母颠倒了", destroyed)
	}
	// 颠倒后（错误的旧实现）会得到 2.39
	inverted := computeLossRatio(ourLost, ourTotalHp)
	if inverted <= 1 {
		t.Fatalf("computeLossRatio 参数顺序已变，测试前提失效: %v", inverted)
	}
	t.Logf("正确损耗率=%.1f%%，若误用 computeLossRatio 会得到 %.1f%%（= 开战/战损）",
		destroyed*100, inverted*100)
}

// 战损比 = 对方战损 / 我方战损，> 1 为我方赚。
func TestComputeLossRatio(t *testing.T) {
	cases := []struct {
		name      string
		ourLost   int64
		enemyLost int64
		want      float64
	}{
		{"我方无损（无法计算）", 0, 5000, 0},
		{"标准互损", 1000, 2000, 2.0},
		{"我方吃亏", 3000, 1000, 1.0 / 3.0},
		{"完全压制", 40, 20000, 500.0},
		{"双方相等", 1500, 1500, 1.0},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := computeLossRatio(c.ourLost, c.enemyLost)
			if math.Abs(got-c.want) > 1e-9 {
				t.Fatalf("computeLossRatio(%d,%d) = %v, want %v", c.ourLost, c.enemyLost, got, c.want)
			}
		})
	}
}

// 双方兵力门槛：完美克制时一方可能只带几十兵，必须剔除，否则比值被极端放大。
func TestMinLossRatioHpThresholdValue(t *testing.T) {
	if MinLossRatioHpThreshold != 20000 {
		t.Fatalf("MinLossRatioHpThreshold = %d, want 20000（双方兵力需 > 20000）", MinLossRatioHpThreshold)
	}
}

// 队伍键必须与三武将 ID 顺序一致，不能排序（排序会把不同阵容误当同一队）；
// 且必须包含玩家名（同一阵容几十上百个玩家共用，只按阵容会跨玩家混算，
// 曾导致 646 支里 609 支损耗率超过 100%）。
func TestTeamLossKeyOrderSensitive(t *testing.T) {
	a := teamLossKey("张三", 101, 202, 303)
	b := teamLossKey("张三", 303, 202, 101)
	if a == b {
		t.Fatalf("teamLossKey 对顺序不敏感: %s == %s，不同阵容会被错误合并", a, b)
	}
	c := teamLossKey("李四", 101, 202, 303)
	if a == c {
		t.Fatalf("teamLossKey 未区分玩家: %s == %s，不同玩家会被错误合并", a, c)
	}
	if a != "张三|101_202_303" {
		t.Fatalf("teamLossKey = %s, want 张三|101_202_303", a)
	}
}

// 逐武将明细：开战/剩余/死兵 由报文给出，伤兵算出，战损 = 伤+死 = 开战-剩余。
func TestParseHeroLossDetailsFields(t *testing.T) {
	// 用户截图里的吕蒙：开战 9100、剩余 7750、死兵 842
	details := parseHeroLossDetails("100002,41,9100,7750,842;")
	if len(details) != 1 {
		t.Fatalf("解析出 %d 个武将，want 1", len(details))
	}
	d := details[0]
	if d.TotalHp != 9100 {
		t.Fatalf("TotalHp(开战) = %d, want 9100", d.TotalHp)
	}
	if d.RemainHp != 7750 {
		t.Fatalf("RemainHp(剩余) = %d, want 7750", d.RemainHp)
	}
	if d.Killed != 842 {
		t.Fatalf("Killed(死兵) = %d, want 842", d.Killed)
	}
	if d.Wounded != 9100-7750-842 {
		t.Fatalf("Wounded(伤兵) = %d, want %d", d.Wounded, 9100-7750-842)
	}
	if d.LostHp != 1350 {
		t.Fatalf("LostHp(战损) = %d, want 1350", d.LostHp)
	}
	// 恒等式：剩余 + 伤 + 死 = 开战
	if d.RemainHp+d.Wounded+d.Killed != d.TotalHp {
		t.Fatalf("剩余+伤+死 != 开战")
	}
	wantRate := 1350.0 / 9100.0
	if math.Abs(d.LossRatio-wantRate) > 1e-9 {
		t.Fatalf("LossRatio = %v, want %v", d.LossRatio, wantRate)
	}
	if d.Anomaly {
		t.Fatal("正常数据被误判为异常")
	}
}

// 核心证据：同一武将继续两场时，下一场的开战兵力 == 上一场的第4位（剩余）。
// 这直接证明第4位是「剩余兵力」而不是「伤兵」。
func TestHeroFieldSemanticsRemain(t *testing.T) {
	cases := []struct {
		name               string
		prevInfo, nextInfo string
	}{
		{
			name:     "歌丨谣 100683 连续两场",
			prevInfo: "100683,40,9600,8166,1081;",
			nextInfo: "100683,40,8166,8166,0;",
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			prev := parseHeroLossInfo(c.prevInfo)
			next := parseHeroLossInfo(c.nextInfo)
			if next.TotalHp != prev.RemainHp {
				t.Fatalf("下一场开战(%d) != 上一场剩余(%d)", next.TotalHp, prev.RemainHp)
			}
		})
	}
}

// 累计口径自洽性：战损 <= 开战，所以累计损耗率必然 <= 100%。
func TestLossRateCannotExceedOne(t *testing.T) {
	// 极端：被打光（剩余 0）
	info := "100029,40,9700,0,4998;"
	got := parseHeroLossInfo(info)
	if got.LostHp != got.TotalHp {
		t.Fatalf("打光时战损(%d) 应等于开战(%d)", got.LostHp, got.TotalHp)
	}
	rate := float64(got.LostHp) / float64(got.TotalHp)
	if rate > 1.0 {
		t.Fatalf("单场损耗率 %v 超过 100%%", rate)
	}

	// 零损失
	zero := parseHeroLossInfo("100029,40,9700,9700,0;")
	if zero.LostHp != 0 {
		t.Fatalf("零损失时战损 = %d, want 0", zero.LostHp)
	}
}
