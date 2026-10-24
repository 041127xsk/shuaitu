package model

type PlayerTeamSnapshot struct {
	ID                 int64  `json:"id" gorm:"primaryKey"`
	PlayerName         string `json:"player_name" gorm:"index:idx_pts_player"`
	UnionName          string `json:"union_name" gorm:"index:idx_pts_union"`
	Role               string `json:"role" gorm:"index:idx_pts_role"`
	Idu                string `json:"idu" gorm:"index:idx_pts_idu"`
	Hero1ID            int64  `json:"hero1_id" gorm:"column:hero1_id;index:idx_pts_lineup"`
	Hero2ID            int64  `json:"hero2_id" gorm:"column:hero2_id;index:idx_pts_lineup"`
	Hero3ID            int64  `json:"hero3_id" gorm:"column:hero3_id;index:idx_pts_lineup"`
	Hero1Level         int64  `json:"hero1_level"`
	Hero2Level         int64  `json:"hero2_level"`
	Hero3Level         int64  `json:"hero3_level"`
	Hero1Star          int64  `json:"hero1_star"`
	Hero2Star          int64  `json:"hero2_star"`
	Hero3Star          int64  `json:"hero3_star"`
	TotalStar          int64  `json:"total_star"`
	Hp                 int64  `json:"hp"`
	AllSkillInfo       string `json:"all_skill_info"`
	Gear               string `json:"gear"`
	HeroType           string `json:"hero_type"`
	LastTime           int64  `json:"last_time" gorm:"index:idx_pts_time"`
	LastBattleID       int64  `json:"last_battle_id" gorm:"column:last_battle_id;index"`
	LineupKey          string `json:"lineup_key" gorm:"index:idx_pts_lineup_key"`
	NormalizedSkillKey string `json:"normalized_skill_key" gorm:"index:idx_pts_skill_key"`
	SourceUpdatedAt    int64  `json:"source_updated_at"`
}

func (*PlayerTeamSnapshot) TableName() string {
	return "player_team_snapshot"
}

type TeamWinRateStat struct {
	ID                 int64   `json:"id" gorm:"primaryKey"`
	Mode               string  `json:"mode" gorm:"index:idx_twrs_mode"`
	MinLevel           int64   `json:"min_level" gorm:"index:idx_twrs_filter"`
	MinHp              int64   `json:"min_hp" gorm:"index:idx_twrs_filter"`
	PlayerName         string  `json:"player_name" gorm:"index:idx_twrs_player"`
	UnionName          string  `json:"union_name" gorm:"index:idx_twrs_union"`
	Players            string  `json:"players"`
	Role               string  `json:"role" gorm:"index:idx_twrs_role"`
	Idu                string  `json:"idu" gorm:"index:idx_twrs_idu"`
	Hero1ID            int64   `json:"hero1_id" gorm:"column:hero1_id;index:idx_twrs_lineup"`
	Hero2ID            int64   `json:"hero2_id" gorm:"column:hero2_id;index:idx_twrs_lineup"`
	Hero3ID            int64   `json:"hero3_id" gorm:"column:hero3_id;index:idx_twrs_lineup"`
	Hero1Level         int64   `json:"hero1_level"`
	Hero2Level         int64   `json:"hero2_level"`
	Hero3Level         int64   `json:"hero3_level"`
	Hero1Star          int64   `json:"hero1_star"`
	Hero2Star          int64   `json:"hero2_star"`
	Hero3Star          int64   `json:"hero3_star"`
	TotalStar          int64   `json:"total_star"`
	AllSkillInfo       string  `json:"all_skill_info"`
	LineupKey          string  `json:"lineup_key" gorm:"index:idx_twrs_lineup_key"`
	NormalizedSkillKey string  `json:"normalized_skill_key" gorm:"index:idx_twrs_skill_key"`
	TotalBattles       int64   `json:"total_battles" gorm:"index:idx_twrs_total"`
	WinCount           int64   `json:"win_count"`
	LossCount          int64   `json:"loss_count"`
	DrawCount          int64   `json:"draw_count"`
	WinRate            float64 `json:"win_rate"`
	LastTime           int64   `json:"last_time" gorm:"index:idx_twrs_time"`
	LastBattleID       int64   `json:"last_battle_id" gorm:"column:last_battle_id"`

	// 战损：不落库（gorm:"-"），查询后由 materialized_queries 侧实时填充。
	// 原因：战损需要解析 all_hero_info 文本，无法在物化表重建时用 SQL 完成；
	// 且战损口径依赖「双方兵力 > 20000」的运行时过滤，属于展示层派生数据。
	// LostHp 只算死兵（永久损失）；伤兵 / 总损仅展示。
	OurLostHp        int64   `json:"our_lost_hp" gorm:"-"`
	EnemyLostHp      int64   `json:"enemy_lost_hp" gorm:"-"`
	OurWoundedHp     int64   `json:"our_wounded_hp" gorm:"-"`
	EnemyWoundedHp   int64   `json:"enemy_wounded_hp" gorm:"-"`
	OurKilledHp      int64   `json:"our_killed_hp" gorm:"-"`
	EnemyKilledHp    int64   `json:"enemy_killed_hp" gorm:"-"`
	LossRatio        float64 `json:"loss_ratio" gorm:"-"`
	LossRatioBattles int64   `json:"loss_ratio_battles" gorm:"-"`
	LossRate         float64 `json:"destroyed_rate" gorm:"-"`
}

func (*TeamWinRateStat) TableName() string {
	return "team_winrate_stats"
}

type MaterializedState struct {
	Name                 string `json:"name" gorm:"primaryKey"`
	Version              int64  `json:"version"`
	Status               string `json:"status"`
	LastBattleID         int64  `json:"last_battle_id" gorm:"column:last_battle_id"`
	BattleReportCount    int64  `json:"battle_report_count"`
	ProcessedReportCount int64  `json:"processed_report_count"`
	StartedAt            int64  `json:"started_at"`
	FinishedAt           int64  `json:"finished_at"`
	LastError            string `json:"last_error"`
}

func (*MaterializedState) TableName() string {
	return "materialized_state"
}

type MaterializedTeamExclusion struct {
	ID                 int64  `json:"id" gorm:"primaryKey"`
	PlayerName         string `json:"player_name" gorm:"index:idx_mte_player"`
	Role               string `json:"role" gorm:"index:idx_mte_role"`
	Idu                string `json:"idu" gorm:"index:idx_mte_idu"`
	LineupKey          string `json:"lineup_key" gorm:"index:idx_mte_lineup_key"`
	NormalizedSkillKey string `json:"normalized_skill_key" gorm:"index:idx_mte_skill_key"`
	CreatedAt          int64  `json:"created_at"`
}

func (*MaterializedTeamExclusion) TableName() string {
	return "materialized_team_exclusion"
}
