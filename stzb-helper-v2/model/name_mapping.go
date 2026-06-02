package model

type NameMapping struct {
	ID        int64  `json:"row_id" gorm:"primaryKey"`
	Kind      string `json:"kind" gorm:"column:kind;uniqueIndex:idx_name_mapping_kind_ref"`
	RefID     int64  `json:"id" gorm:"column:ref_id;uniqueIndex:idx_name_mapping_kind_ref"`
	Name      string `json:"name"`
	Note      string `json:"note"`
	CreatedAt int64  `json:"created_at"`
	UpdatedAt int64  `json:"updated_at"`
}

func (*NameMapping) TableName() string {
	return "name_mapping"
}
