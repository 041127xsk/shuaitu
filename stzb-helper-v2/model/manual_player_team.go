package model

type ManualPlayerTeam struct {
	ID             int64  `json:"id" gorm:"primaryKey"`
	PlayerName     string `json:"player_name" gorm:"index"`
	UnionName      string `json:"union_name" gorm:"index"`
	Idu            string `json:"idu" gorm:"index"`
	Role           string `json:"role"`
	Time           int64  `json:"time" gorm:"index"`
	BattleID       int64  `json:"battle_id"`
	Hero1ID        int64  `json:"hero1_id"`
	Hero2ID        int64  `json:"hero2_id"`
	Hero3ID        int64  `json:"hero3_id"`
	Hero1Level     int64  `json:"hero1_level"`
	Hero2Level     int64  `json:"hero2_level"`
	Hero3Level     int64  `json:"hero3_level"`
	Hero1Star      int64  `json:"hero1_star"`
	Hero2Star      int64  `json:"hero2_star"`
	Hero3Star      int64  `json:"hero3_star"`
	TotalStar      int64  `json:"total_star"`
	Hp             int64  `json:"hp"`
	AllSkillInfo   string `json:"all_skill_info"`
	Gear           string `json:"gear"`
	HeroType       string `json:"hero_type"`
	Note           string `json:"note"`
	SourceBattleID int64  `json:"source_battle_id"`
	SourceRole     string `json:"source_role"`
	Enabled        int64  `json:"enabled" gorm:"default:1;index"`
	CreatedAt      int64  `json:"created_at"`
	UpdatedAt      int64  `json:"updated_at"`
}

func (*ManualPlayerTeam) TableName() string {
	return "manual_player_team"
}

type HiddenPlayerTeam struct {
	ID         int64  `json:"id" gorm:"primaryKey"`
	SourceType string `json:"source_type" gorm:"index:idx_hidden_player_team_source,unique"`
	SourceID   int64  `json:"source_id" gorm:"index:idx_hidden_player_team_source,unique"`
	Role       string `json:"role" gorm:"index:idx_hidden_player_team_source,unique"`
	PlayerName string `json:"player_name"`
	Idu        string `json:"idu"`
	Note       string `json:"note"`
	CreatedAt  int64  `json:"created_at"`
}

func (*HiddenPlayerTeam) TableName() string {
	return "hidden_player_team"
}
