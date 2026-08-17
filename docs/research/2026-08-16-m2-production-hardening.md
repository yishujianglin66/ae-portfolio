# M2 生产级打磨 — 特写评分 + 缓存修复 + 收敛实证

> 日期：2026-08-16 · 模式：真机 + 真实 API 多轮闭环 · 产物：output/m2_iteration/

## 一、本轮修复的核心缺陷

**缓存 key 截断 bug（假收敛根因）**
- 旧实现：缓存 key 只取 `frames_b64[:2000]`（base64 前 2000 字符）
- 问题：粒子在画面中部，图像前部（背景）在迭代中不变 → base64 前缀碰撞 → **3 轮评分命中同一旧缓存，分数完全一致（假收敛）**
- 证据：3 个渲染文件 md5 都不同（迭代确实生效），但评分一字不差
- 修复：缓存 key 用完整 base64 哈希 → 实测第 2 轮评分真实变化（color_harmony 7→8）

## 二、M2a 特写评分（解决 texture 振荡）

- **问题**：全帧评分里粒子只占 5%，AI 看不清细节只会猜"加大粒子"→ 与 composition"挡脸"矛盾，振荡
- **方案**：`score_closeup()` 裁剪中央区域放大评分 texture 细节
- **实测**：特写后 AI 建议从"加大粒子"变为"透明度渐变+动态变化"（能看清细节才给可执行建议）

## 三、M2b 振荡抑制

- texture 维度走特写评分 + 阈值保护（特写达标则跳过自动迭代）
- 每轮只调最低分维度（v2 已修）→ 消除"第1轮加大/第2轮缩小"震荡

## 四、M2c 生产级加固

- 评分缓存（完整哈希 key，省 API 计费）
- API 调用重试 3 次（指数退避）
- 结果 JSON 持久化到 cache/visual_scores/

## 五、诚实记录的边界

1. **维度权衡冲突**：AI 对 texture 建议"加大粒子"，对 composition 建议"缩小粒子"——这是真实的审美权衡（粒子丰富度 vs 不挡脸），闭环用"每轮最低分优先"策略轮流逼近，但不会同时满足两者。生产上需要人工设权重或按目标段落侧重。
2. **特写评分仍受单帧局限**：pacing 等时序维度靠多帧推理，可信度有限。

## 六、闭环现状（全部真机实证）

```
渲染 → qwen-vl 6帧评分 → 最低分维度:
   texture → 特写评分(裁剪放大) → 语义驱动动作
   其他    → 语义驱动动作(advice→结构化调参)
→ 单维度迭代 → AE真机重渲染 → 复评
```

## 七、产物

- `core/visual_scorer.py`：score_video / score_closeup / iterate_parameters（语义驱动 v2）/ 缓存重试
- `scripts/m2_auto_iterate.py`：无人值守多轮闭环
- `output/m2_iteration/`：多轮成片 + 评分记录
- 回归 43/43 + 19/19 全绿

---

# M2 打磨续篇（2026-08-16 第二轮）

## M2e 维度优先级权重
- `STYLE_DIM_WEIGHTS`: 风格卡 → 维度权重（amv/edit 偏 dynamism+pacing, ambient/vintage 偏 texture+color）
- `pick_target_dim`: 按"低分×高权重"选迭代维度 —— 解决 texture(加大粒子) vs composition(缩小粒子) 冲突: 同分时 edit 风格先攻 dynamism, vintage 先攻 texture
- 验证: 3 组用例全通过

## M2f 时序评分
- `score_sequence(t_start, t_end)`: 抽节拍窗口连续帧 + 时间标注 + 帧间差异统计
- 实测 drop 段(2.4-3.9s): pacing=8, diff_mean=13.4（节拍段画面持续活跃的客观证据）
- 解决旧 score_video 均匀抽帧导致 pacing 只能靠模型推理的问题

## M2g 调参器（数据积累 → GBDT）
- m2_auto_iterate 每轮落盘 `_param_snapshot`（9 参数特征）→ train_samples.jsonl
- `train_param_tuner.py`: 7 个 GBDT 单目标回归器, 特征重要性输出, 模型存 models/output/param_tuner.pkl
- 现状: 3 样本已训出（chromatic_amount 被识别为主要特征）, 数据随迭代累积精度提升
- 诚实边界: 当前样本数过少特征重要性不可靠, 属管线就绪阶段

## 本轮产物
- core/visual_scorer.py: +pick_target_dim +score_sequence +STYLE_DIM_WEIGHTS
- scripts/m2_auto_iterate.py: +参数快照 +训练样本落盘
- scripts/train_param_tuner.py: GBDT 调参器训练
- models/output/param_tuner.pkl: 首个调参器
- 回归 43/43 + 19/19 全绿

---

# M2 调参器数据采集（2026-08-16 第三轮）

## 核心成果：发现并修复"死参数"数据缺陷

**缺陷**：`_glow_mult`/`_pps_mult` 在调参器样本里被记录（0.6/1.0 等），但
`particular_jsx` 从不读取——**记录了的参数不影响渲染 = 噪声特征**。样本记录了
"Glow 倍率 0.6"但渲染用的恒是 4.5，调参器学到的是假映射。

**修复**：`particular_jsx` 新增 `glow_mult`/`pps_mult` 参数，orchestrator 传入，
验证：`glow_mult=2.0 → Glow 强度 9.0`、`pps_mult=2.0 → 粒子 10000/s` 真实进 JSX。

## 批量采集管线

- `scripts/collect_tuning_data.py`: 参数网格随机采样（psize/色差/punch/shake/glow/text_size
  各 3-5 档）× 2 秒短段渲染 × qwen 评分 → 落盘 train_samples.jsonl
- 首轮采集 6 样本: 参数多样（psize 3档/glow 3档/色差 4档/text_size 3档）
- 约 100s/组合（2 秒短段, 比 5 秒快 2.5x）

## 调参器现状（诚实）

- 6 样本重训完成, 但 text_size 被 6 目标全识别为主特征(0.735) = **小样本过拟合**
- 特征重要性在 6 样本量级不可靠, 需 30-50 样本
- 价值: 采集管线已就绪且**数据质量已确保**（死参数修复 = 每个样本特征都真实作用于渲染）
- 继续跑采集即可（无人值守, 一晚上 30-50 样本）

## 回归
- 43/43 + 19/19 全绿
