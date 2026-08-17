# 精度优化实验记录 (Step 4 A4-A5 冲刺)

> 2026-08-15 | 目标: 动漫运镜分类器精度最大化 (用户要求"效果最好、精度最完美")

## 实验 1: complex 标签 VLM 二次清洗 — ❌ 作废

- 假设: 首轮预标注对风格化推镜有 complex 误判, 用"严格 prompt"(单一方向优先) 重标可修复
- 方法: 60 条 complex 重标 → 59 条被改成单一方向 (表面"成功")
- **对照实验 (关键)**: 用同一严格 prompt 重标 30 条原高置信(≥0.85)单一方向镜头
  → **一致率仅 53.33%** (16/30, pan_left→zoom_in 等错乱)
- **结论**: 严格 prompt 自带"单一方向"偏见, 重标是噪声; `vlm_labels_v2.jsonl` 作废。
  原标签 (conf≥0.7) 是当前最干净的无人工标签。
- 教训: VLM prompt 微调的方向性偏见必须用对照集自检, 不能直接信"改标率"。

## 实验 2: 云端 v2 加权训练 — ❌ 无效 (环境 bug)

- 云端 transformers 4.46.3 + torch 2.1.2 加载 VideoMAE checkpoint 时注意力偏置
  键名不匹配 (q_bias/v_bias 未被识别 → 随机初始化), **基座模型静默损坏**
- 后果: v2 训练 val 0.2405 ≈ 基座水平 (适配器≈零权重); 云端评估 lora == base 22.9%
- 修复: 云端对齐本地版本 **torch 2.6.0 + transformers 5.14.1** 后基座恢复正常
  (验证: 同 300 集 argmax 0.7037 与本地完全一致)
- 教训: 换环境后必须先跑"已知基准集"验证模型加载正确性, 再投入训练

## 实验 3: 逐类阈值调优 — ✅ 有效 (+1.35%)

- v1 LoRA (训练 val 63.65%) 在 300 条 VLM 一致性集上:
  - argmax 基线: **70.37%**
  - 逐类阈值 (Static 0.50 / Motion 0.45 / Pull 0.15 / Push 0.45): **71.72%**
  - **Pull 短板从 4.2% → 45.8%** (阈值 0.15 回收大量低置信 Pull)
- 阈值已存 `models/output/thresholds_tuned.json` (A5 接入用)
- 网格 0.05-0.80 扩展后结果稳定, 无更好组合

## 实验 4: 云端标注提速 — ✅ 最终配置: 三通道 x 9 路

- 坑 1: 12 路并发触发 SiliconFlow 限流卡死 → 降并发
- 坑 2: ModelScope key 在 .env 注释行里 (解析失败, 通道静默缺失) → 正则兜底
- 坑 3: 每镜头 5 次 ffmpeg 调用 → 单次 fps 滤镜调用 (5x 进程开销消除)
- 坑 4 (根因): **nohup 后台进程随 SSH 通道关闭被连带杀死** (进程组随会话消亡,
  日志 0 字节假象) → `setsid` + `</dev/null` + `python -u` 彻底分离
- 终态: 三通道 (SiliconFlow 8B / ModelScope 235B / 百炼 qwen3.8-max) x 9 路,
  ~25-30/分钟, 通道分布 SF 51% / 百炼 26% / MS 23%

## 实验 5: 视觉模型通道调整 (用户反馈 qwen3.8-max 额度耗尽)

- SiliconFlow 通道: Qwen3-VL-8B → **Qwen3-VL-30B-A3B** (MoE, 网关"视觉标注最省"档)
- 百炼通道: qwen3.8-max → **qwen-vl-max** (实测额度可用)
- ModelScope 235B: 保留 (偶尔 429 瞬时限流)
- .env `QWEN_VISION_MODEL` 同步改 qwen-vl-max (全项目网关生效)

## 进行中 / 待办

1. [~] **全量标注**: 云端 4 路并发 (12 路限流卡死已降) ~40-100/分钟, 预计 2-4h
2. [ ] **v3 训练**: fine 10 类细方向头 (摆脱 32% 光流规则细分) + weight-cap 5x + 无 sampler
   — 脚本已升级 `70edd84`, 部署器 `D:\AE-Data\cloud_launch_v3.py` 就绪; **启动前提醒用户 (成本)**
3. [ ] v3 评估: 细 10 类盲评 vs v1 粗4类(71.72%)
4. [ ] 人工盲评集 (100 条分层, `scripts/build_blind_review.py`) → 真实验收
5. [ ] A5 接入 ai/camera_decision.py (分类器模块 `models/anime_camera_classifier.py` 已就绪)
