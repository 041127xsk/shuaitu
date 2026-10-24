package main

// 回归：损耗率与负率的 JSON 字段名不能撞车。
//
// 历史 bug：损耗率曾用 json:"loss_rate"，而「负率」早已占用 loss_rate
// （loss_count/total_battles）。前端读 row.loss_rate 拿到的是负率，
// 再 ×100 显示，于是负率 3.52% 被显示成「损耗率 3.52」，
// 用户看到的就是「损耗率超过 1（甚至 3.x）」。实际后端算出的损耗率从未超过 1。
//
// 现在损耗率用 destroyed_rate，这里用反射把两个字段钉死。

import (
	"encoding/json"
	"reflect"
	"strings"
	"testing"

	"stzbHelper/model"
)

// 收集结构体上所有 json tag，用于断言字段名唯一性
func jsonTagsOf(t *testing.T, v interface{}) []string {
	t.Helper()
	rt := reflect.TypeOf(v)
	if rt.Kind() == reflect.Ptr {
		rt = rt.Elem()
	}
	tags := make([]string, 0, rt.NumField())
	for i := 0; i < rt.NumField(); i++ {
		tag := rt.Field(i).Tag.Get("json")
		if tag == "" || tag == "-" {
			continue
		}
		name := strings.Split(tag, ",")[0]
		tags = append(tags, name)
	}
	return tags
}

func assertNoDupTags(t *testing.T, name string, tags []string) {
	t.Helper()
	seen := map[string]bool{}
	for _, tag := range tags {
		if seen[tag] {
			t.Fatalf("%s 出现重复 json 字段名 %q（会导致前端读到错误字段）", name, tag)
		}
		seen[tag] = true
	}
}

// 损耗率字段必须叫 destroyed_rate，不能叫 loss_rate
func TestLossRateFieldNameNotConflicting(t *testing.T) {
	// 1. 派生表模型：字段名唯一，且存在 destroyed_rate
	tags := jsonTagsOf(t, model.TeamWinRateStat{})
	assertNoDupTags(t, "model.TeamWinRateStat", tags)
	found := false
	for _, tag := range tags {
		if tag == "destroyed_rate" {
			found = true
		}
	}
	if !found {
		t.Fatal("model.TeamWinRateStat 缺少 destroyed_rate 字段（损耗率）")
	}

	// 2. 实际序列化：损耗率与负率必须落在不同 key 上
	row := model.TeamWinRateStat{
		PlayerName:   "测试玩家",
		TotalBattles: 100,
		LossCount:    352, // 负率异常值，仅用于区分字段
		LossRate:     0.42,
	}
	blob, err := json.Marshal(row)
	if err != nil {
		t.Fatalf("序列化失败: %v", err)
	}
	var decoded map[string]interface{}
	if err := json.Unmarshal(blob, &decoded); err != nil {
		t.Fatalf("反序列化失败: %v", err)
	}
	v, ok := decoded["destroyed_rate"]
	if !ok {
		t.Fatalf("JSON 里没有 destroyed_rate 字段，实际 keys: %v", keysOf(decoded))
	}
	if got, _ := v.(float64); got != 0.42 {
		t.Fatalf("destroyed_rate = %v, want 0.42", v)
	}
	if _, ok := decoded["loss_rate"]; ok {
		t.Fatalf("JSON 里仍存在 loss_rate 字段，与负率撞名：%v", keysOf(decoded))
	}
}

func keysOf(m map[string]interface{}) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}

// 损耗率在数学上不可能超过 1（战损 <= 开战），这里用脏数据也不该放大
func TestLossRateBoundedByParse(t *testing.T) {
	cases := []string{
		"100001,40,1000,0,1000;",   // 打光，死兵等于开战
		"100001,40,1000,0,0;",      // 打光，全伤兵
		"100001,40,1000,1000,0;",   // 零损失
		"100001,40,1000,500,500;",  // 各半
	}
	for _, info := range cases {
		got := parseHeroLossInfo(info)
		if !got.Valid {
			continue
		}
		if got.LostHp > got.TotalHp {
			t.Fatalf("战损(%d) 超过开战(%d)，输入 %q", got.LostHp, got.TotalHp, info)
		}
		// 累计口径同样是 sum(战损)/sum(开战)，单场不越界则累计也不越界
		rate := float64(got.LostHp) / float64(got.TotalHp)
		if rate > 1.0 {
			t.Fatalf("损耗率 %v 超过 1，输入 %q", rate, info)
		}
	}
}
