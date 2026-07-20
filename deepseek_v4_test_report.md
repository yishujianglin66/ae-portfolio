
============================================================
DeepSeek V4 正式版 API 测试报告
============================================================
测试时间: 2026-07-15 18:26:59
API 端点: https://api.deepseek.com

## 测试汇总
- 总测试数: 5
- 成功数: 5
- 成功率: 100.0%
- 总Token: 输入=7571, 输出=674
- 平均响应时间: 3414ms

## 费用估算
- V4-Flash: ¥0.000168 (输入=20, 输出=74)
- V4-Pro: ¥0.003075 (输入=25, 输出=500)
- 总费用: ¥0.003243

## 测试详情

### ✅ api_connection
- latency_ms: 1159
- error: None
- model: deepseek-v4-flash

### ✅ v4_flash
- latency_ms: 1599
- tokens_input: 20
- tokens_output: 74
- error: None
- content: 遮罩抠像（Roto）是通过逐帧或关键帧手动绘制蒙版，将视频中的特定物体或人物从背景中精确分离出来的技术。
- model: deepseek-v4-flash

### ✅ v4_pro
- latency_ms: 12407
- tokens_input: 25
- tokens_output: 500
- error: None
- content: 
- model: deepseek-v4-pro

### ✅ large_context
- context_size: 10000
- latency_ms: 1905
- tokens_input: 7526
- tokens_output: 100
- error: None
- model: deepseek-v4-flash

### ✅ silhouette_intent
- accuracy: 1.0
- correct: 5
- total: 5