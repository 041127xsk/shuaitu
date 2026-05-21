package global

import "encoding/json"

type Response struct {
	Code    int    `json:"code"`
	Message string `json:"msg"`
	Data    any    `json:"data"`
}

// Success 成功的返回
func (r Response) Success() string {
	r.Code = 200
	if r.Message == "" {
		r.Message = "ok"
	}

	jsonData, _ := json.Marshal(r)

	return string(jsonData)
}

// Error 发生错误的返回
func (r Response) Error() string {
	if r.Message == "" {
		r.Message = "error"
	}

	if r.Code == 0 {
		r.Code = 500
	}

	jsonData, _ := json.Marshal(r)

	return string(jsonData)
}
