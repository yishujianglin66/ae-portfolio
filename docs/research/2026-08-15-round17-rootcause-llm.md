# Round 17 — 根因修复 + LLM 镜头剧本 (DeepSeek V4 辅助)

> 日期: 2026-08-15 | 分支: feat/project-consolidation-v1

## 用户反馈链条

1. "每个镜头都是晃动、推拉、闪回" → v4 静态占比 76% 仍无变化;
2. "对比 v22 进行学习" → v22 (8/12, 无逐拍推拉代码) 静态镜头真静态;
3. "调用 api 模型进行辅助" → 接入 DeepSeek V4 编排镜头剧本。

## 根因 (为什么 v4 "还是没变化")

`_extract_clip` 中 onset 逐拍"拉进-闪回"分支优先级高于 zoompan_effect:

```python
if onset_times and len(onset_times) > 0:   # ← 旧: 有鼓点就打 punch
    ...zoompan punch...
elif zoompan_effect:                       # ← static 永远走不到
```

v4 实测: 227/229 段带鼓点 onset, **173 个"静态"镜头全部被鼓点推拉覆盖** —
T4.5 静态化只改了标签, 渲染层无视之。v22 无此分支 → 静态真静态 → 用户认可。

## 修复 (v5)

1. **门控**: onset punch 只作用于剧本派发的撞击镜头 push/zoom_in;
   static/pan/diag/zoom_back 不再被覆盖 (回归测试 tests/test_director_punch_gating.py);
2. **T4.6 撞击预算**: 全片≤6 次、间隔≥20s、仅爆发段强拍;
3. **幅度收敛**: punch 峰值 1.35→1.15, 双鼓点对 0.28→0.12;
4. AE 通道同步门控 (`pulse` 仅限撞击镜头)。

### v5 实测

- 静态 188/229 (82.1%), 撞击仅 2 次 (78.4s / 123.4s, 间隔45s, 均在 drop);
- **MAD 定量验证 PASS**: 鼓点前后帧差中位数 v4=0.1059 → v5=0.0286 (-73%),
  静态镜头像素级真静态;
- assess 4/5 优良 (仅缺 48fps 增强)。

## LLM 镜头剧本 (v6)

### 基建修复 (ai/ai_agent.py, 806a9ef)

- 渲染子进程看不到 User 环境变量 → 原代码只加载不存在的 `ai/.env.doubao`
  → 修复为加载项目根 `.env` + `.env.doubao`;
- DuckMiss 中转站实测已死(连接重置) → 提供方健康降级链
  (原生 DeepSeek V4 → ARK → DuckMiss, 6s 真实对话探测);
- DeepSeek V4 推理模型 content 为空时回退 reasoning_content;
- 实测: api.deepseek.com 原生 deepseek-v4-pro/flash 全通 (200)。

### 镜头剧本模块 (ai/shot_design_llm.py, f158cc1)

DeepSeek V4 以剪辑导演身份, 基于音乐弧段表输出严格 JSON 镜头设计:

| 约束 | 值 |
|---|---|
| intro/outro/break | motion_per_10 = 0 (全静态) |
| build | 1/10 运动, 词表 static+pan |
| drop | 2/10 运动, 撞击点仅强拍 |
| 撞击点 | 64.5s / 107.5s / 128.0s (3处, 间隔≥20s) |
| 全片加权运动 | ≈0.94/10 (~9.4%, v4 为 24%) |
| 输出校验 | 数量/间隔/弧段归属/static首位/加权上限, 失败重试换模型 |

计划缓存 (shot_plan_<bgm>_<sig>.json) → 重复渲染确定性, LLM 失败自动
规则兜底 (T4.5/T4.6), 永不阻塞渲染。

### 管线接入 (production_director)

- Phase 2 弧段表定稿后调用 design_shot_plan;
- T4.55: 剧本撞击点强制 push;
- T4.5: 运动预算优先取剧本分弧段值;
- T4.6: 剧本点放行, 其余仍须强拍+间隔+预算;
- Phase 2 theme 分镜 LLM Agent 恢复 → 叙事角色真实生成。

## 交付物

- v5 (规则修复版): `D:\output_director\solo_pilot\v23\v23_final_full_v5.mp4` (168.5s, 4/5);
- v6 (LLM剧本版): `v23_final_full_v6.mp4` (渲染中);
- 测试: 36+29 项回归全过 (门控/剧本校验/品味契约/运镜决策)。
