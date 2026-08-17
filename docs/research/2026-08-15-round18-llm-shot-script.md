# Round 18 — LLM 镜头剧本落地：v6 静态 89.5% / 撞击仅 3 处

> 日期: 2026-08-15 | 分支: feat/project-consolidation-v1

## 用户指令闭环

"调用 api 模型进行辅助" → DeepSeek V4 以剪辑导演身份编排镜头剧本,
已在渲染管线内落地生效 (v6 成品)。

## API 基建修复 (ai/ai_agent.py)

| 问题 | 修复 |
|---|---|
| 渲染子进程看不到密钥 (仅加载不存在的 ai/.env.doubao) | 加载项目根 .env + .env.doubao |
| DuckMiss 中转站已死 → 全部调用 403 | 提供方健康降级链: 原生DeepSeek V4 → ARK → DuckMiss |
| DeepSeek V4 推理链吃满预算 → content 为空 | reasoning_effort="none" (实测 reasoning_tokens=0, content 直出) |
| 结构化 JSON 偶发违规 | 校验失败带原因反馈重试 + 单弧段单撞击硬约束 |

实测: api.deepseek.com 原生 deepseek-v4-pro/flash 全通; LLM 计划生成
从 30s+ 不稳定 → 6-8s 稳定成功 (¥0.01/次)。

## v6 镜头剧本 (DeepSeek V4 Pro 生成, 管线内缓存确定性复用)

- 运动预算: intro/outro = 0 (全静态), build = 1/10, drop = 2/10;
- 撞击点: 64.5s (首次爆发强拍) + 108.0s (二次爆发), 间隔 43.5s;
- 每弧段附镜头思路 notes (如 "爆发强拍，首次撞击" / "单点强撞，余下硬切")。

## v6 成品实测 (D:\output_director\solo_pilot\v23\v23_final_full_v6.mp4)

| 指标 | v4 (旧) | v5 (规则修复) | v6 (LLM剧本) |
|---|---|---|---|
| 静态占比 | 76.4% | 82.1% | **89.5%** |
| intro 段静态 | — | — | **100%** |
| 撞击(拉进-闪回) | 54处+173覆盖 | 2 处 | **3 处 (剧本指定)** |
| 鼓点帧差 MAD (静态镜头) | 0.267 | 0.029 | **0.044 (-84%)** |
| 评估 | 4/5 | 4/5 | 4/5 (仅缺48fps) |

- 运动镜头仅 21 处温和运镜 (pan/diag/zoom_back ≤1.12x) + 3 处剧本撞击;
- 转场: flash 4 / fade 42 / cut 183; 违规 0; taste 9/9/6 全遵守;
- 48fps 增强已排队 (GPU 空闲自动触发, pwsh-103)。

## 提交

- 806a9ef ai_agent 根.env加载+健康降级链
- 877eabc reasoning_effort=none + 校验反馈重试 + pro优先
- f158cc1 shot_design_llm 模块 + production_director T4.55/T4.5/T4.6 接入
- 7646609 onset推拉门控根因修复 (静态镜头真静态)
- 测试: 32+29 项回归全过 (含真实 API 冒烟由管线验证)
