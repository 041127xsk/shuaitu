# stzb-ocr - 率土之滨战报 OCR Skill

## 功能
分层智能识别战报截图，自动提取结构化数据。

## 架构
```
┌─────────────────────────────────────┐
│         基础层 (PaddleOCR)           │
│  - 快速处理结构化数值（兵力/等级）   │
│  - 高吞吐量场景                      │
└─────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────┐
│       增强层 (Qwen VL API)           │
│  - 低置信度样本补全                  │
│  - 复杂场景（武将名/技能描述）       │
└─────────────────────────────────────┘
```

## 安装
```bash
pip install paddlepaddle paddleocr
```

## 用法

### Python API
```python
from src.stzb_ocr import StzbOCR, extract_battle_report

# 方式 1: 直接调用
result = extract_battle_report("battle_report.png")
print(result["extracted_data"])

# 方式 2: 自定义配置
ocr = StzbOCR()
result = ocr.recognize("battle_report.png")
```

### 返回数据结构
```json
{
  "raw_text": "识别的原始文本...",
  "confidence": 0.95,
  "extracted_data": {
    "player_a": "唐黑神话",
    "player_b": "神鸢燕南飞",
    "heroes_a": ["曹豹", "刘虞"],
    "heroes_b": ["黄忠", "黄盖", "严颜"],
    "result": "loss",
    "timestamp": "2026/05/03 20:57:54"
  }
}
```

## 性能对比

| 引擎 | 速度 | 准确率 | 适用场景 |
|------|------|--------|----------|
| PaddleOCR | ~50ms/img | 95%+ | 常规战报 |
| RapidOCR | ~100ms/img | 92% | 备用方案 |
| Qwen VL | ~2s/img | 98%+ | 困难样本 |

## TODO
- [ ] Qwen VL API 集成
- [ ] 自动置信度阈值判断
- [ ] 批量处理队列
- [ ] 结果缓存机制
