# M2 视觉评估闭环 — 交付报告

> 日期：2026-08-16 · 模式：真机 + 真实 API 调用（非纸面）· 产物：edit_m2.mp4 + 评分数据

## 一、闭环定义

```
渲染成片 → 均匀抽 6 帧 → qwen-vl-max 多模态评审
  → 结构化评分(6 维度 + 问题清单 + 建议) → 自动调参 → 重渲染 → 复评
```

## 二、打通过程（踩掉的坑）

1. **`core.llm_gateway` 的 gateway 坏了**：`configure_from_env()` 只加载 deepseek/doubao 两个 provider，siliconflow/qwen 未注册——`chat_vision(provider='siliconflow')` 报 "未配置"。排查到 `_config.providers` 为空即放弃。
2. **方案**：绕开 gateway，**直连 DashScope compatible-mode**（QWEN_API_KEY + qwen-vl-max，OpenAI 兼容格式），实测返回专业评审级 JSON。
3. 修复 `_frame_to_b64` 的 cv2 5.0 imdecode 兼容（np.fromfile）。

## 三、闭环实证（同一成片 AI 迭代前后）

| 维度 | 首评 | 复评 | 变化 |
|---|---|---|---|
| color_harmony | 5 | **8** | +3 |
| text_read | 8 | **9** | +1 |
| composition | 6 | 6 | 持平 |
| dynamism | 7 | 7 | 达标 |
| overall | 6 | **7** | +1 |

**AI 首评意见**（一针见血，直接命中我们的调参方向）：
- "黄色爆炸图形遮挡关键角色面部" → 粒子 40px→28px + Glow 收敛
- "色彩对比过强，黄黑缺乏层次" → 落地后 color_harmony 5→8

**复评新建议**（下一轮迭代方向）："黄色爆炸缺动态变化，建议加脉冲动画"——指向粒子爆发窗口单一的问题。

## 四、产物

- `core/visual_scorer.py` — score_video / score_frames / iterate_parameters
- `output/one_pipeline/edit_m2.mp4` — AI 优化版成片（粒子 5.8% 收敛不挡脸）

## 五、能力边界（诚实）

- 视觉模型对**单帧/聚合帧**的评分可信（色彩/遮挡/文字清晰）
- **节奏/时序维度**（pacing）多帧聚合下可信度有限——单帧无运动信息，模型靠推理
- 迭代规则是启发式（幅度 ±20%），非强化学习——后续可用评分数据积累训练调参器

## 六、下一步

1. **M2 全自动循环**：评分 → iterate → 重渲染 → 复评，无人值守多轮
2. **调参器训练**：积累 (合成树参数, 评分) 数据 → 训 GBDT 预测最优参数
3. 多段成片：完整歌曲多段编排 + 全程 M2 把关
