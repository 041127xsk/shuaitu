package model

import (
	"encoding/json"
	"fmt"
	"strconv"
)

type TeamUser struct {
	Id              int    `json:"id" gorm:"column:id"`
	Name            string `json:"name" gorm:"column:name"`
	ContributeTotal int    `json:"contribute_total" gorm:"column:contribute_total"`
	ContributeWeek  int    `json:"contribute_week" gorm:"column:contribute_week"`
	Pos             int    `json:"pos" gorm:"column:pos"`
	Power           int    `json:"power" gorm:"column:power"`
	Wu              int    `json:"wu" gorm:"column:wu"`
	Group           string `json:"group" gorm:"column:group"`
	JoinTime        int    `json:"join_time" gorm:"column:join_time"`
}

func (TeamUser) TableName() string {
	return "team_user"
}

/*
		同盟成员信息索引
		[
			//0 id?
	        //1 名称
			//2 总贡献
			//6 坐标
			//7 本周贡献
			//8 势力
			//10 武勋
			//13 分组
			//30 应该是加入时间
		]
*/

func ToTeamUser(data []any) TeamUser {
	teamUser, err := ToTeamUserWithError(data)
	if err != nil {
		return TeamUser{}
	}
	return teamUser
}

func ToTeamUserWithError(data []any) (TeamUser, error) {
	if len(data) < 31 {
		return TeamUser{}, fmt.Errorf("字段数量不足: got %d, want >= 31", len(data))
	}

	group, err := valueAsString(data[13])
	if err != nil {
		return TeamUser{}, fmt.Errorf("分组字段异常: %w", err)
	}
	if group == "" {
		group = "未分组"
	}

	id, err := valueAsInt(data[0])
	if err != nil {
		return TeamUser{}, fmt.Errorf("id字段异常: %w", err)
	}
	name, err := valueAsString(data[1])
	if err != nil {
		return TeamUser{}, fmt.Errorf("名称字段异常: %w", err)
	}
	contributeTotal, err := valueAsInt(data[2])
	if err != nil {
		return TeamUser{}, fmt.Errorf("总贡献字段异常: %w", err)
	}
	pos, err := valueAsInt(data[6])
	if err != nil {
		return TeamUser{}, fmt.Errorf("坐标字段异常: %w", err)
	}
	contributeWeek, err := valueAsInt(data[7])
	if err != nil {
		return TeamUser{}, fmt.Errorf("本周贡献字段异常: %w", err)
	}
	power, err := valueAsInt(data[8])
	if err != nil {
		return TeamUser{}, fmt.Errorf("势力字段异常: %w", err)
	}
	wu, err := valueAsInt(data[10])
	if err != nil {
		return TeamUser{}, fmt.Errorf("武勋字段异常: %w", err)
	}
	joinTime, err := valueAsInt(data[30])
	if err != nil {
		return TeamUser{}, fmt.Errorf("加入时间字段异常: %w", err)
	}

	teamUser := TeamUser{
		Id:              id,
		Name:            name,
		ContributeTotal: contributeTotal,
		ContributeWeek:  contributeWeek,
		Pos:             pos,
		Power:           power,
		Wu:              wu,
		Group:           group,
		JoinTime:        joinTime,
	}

	return teamUser, nil
}

func valueAsInt(value any) (int, error) {
	switch v := value.(type) {
	case float64:
		return int(v), nil
	case int:
		return v, nil
	case int64:
		return int(v), nil
	case json.Number:
		i, err := v.Int64()
		return int(i), err
	case string:
		if v == "" {
			return 0, nil
		}
		i, err := strconv.Atoi(v)
		return i, err
	default:
		return 0, fmt.Errorf("不支持的数字类型 %T", value)
	}
}

func valueAsString(value any) (string, error) {
	switch v := value.(type) {
	case string:
		return v, nil
	case fmt.Stringer:
		return v.String(), nil
	case nil:
		return "", nil
	default:
		return "", fmt.Errorf("不支持的文本类型 %T", value)
	}
}
