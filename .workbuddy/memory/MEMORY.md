# 项目长期记忆

## 常用技术栈（技术简报筛选依据）
Python 3.11（.venv）/ Node 22 / ComfyUI / FFmpeg / MCP / After Effects 脚本 / 扩散与视频生成模型。
硬件 RTX 4060（显存敏感，凡是省显存/提速的推理优化都属于高相关）。

## 简报/汇报偏好（2026-09-08 立）
- 要"扫一眼就能看完"：技术热点简报严格控制在 10 行以内，分「新项目」「版本更新」「其他动态」三段。
- 每个条目一句话讲清：做什么 + 为什么突然火 + 和我什么关系。
- **绝对不凑数**，没值得看的就写"本期无"。
- 看项目看**增速**不看总 star 数。
- 默认直接在对话里输出，不生成文件。

## R1 cut_visibility 验收口径铁律（2026-09-10 立）
- **v2 验收口径有幸存者偏差**：ffmpeg 场景检测只给"本来就合格的切点"打分，坏切点被静默丢弃 → v2 永远自我表扬（run61 v2=1.05/frozen 2.94%，实际 72.9% 冻结）。
- **永远用 v3**（`scripts/cut_visibility_v3.py`）：分母 = EDL 声明切点全集（不是场景检测发现的）；frozen_rate = frozen/n_declared。
- v3 必须搭配 EDL 的 `cut_points` 字段，不可缺。
- 任何"切点可见性"报告必须报 v3 数字，否则不算数。

## production_director 漂移钳制铁律（2026-09-10 立）
- `_tl_drift` 累加器在慢放段 (speed<1) 失控：read_dur=duration*speed 输入窗口 < out_frames/fps 输出所需，
  30fps 源经 fps=24 重采样后实际帧数 < out_frames，drift += render_dur-_ad 持续累加无衰减。
- run61 实测 49.62s vs plan 30s（+19.62s 失控），后续 108 段无钳制仿真最终漂移 2.8e34s。
- 钳制 `_TL_DRIFT_LIMIT = 2.0/24.0`（±2 帧 ≈ ±83ms），溢出强制归零。
- 钳制后仿真最大漂移 7.1 帧 ≈ ±295ms（仍受 ±2 帧限制但允许爬升一次）。
- 单测覆盖：`tests/test_rl_drift_clamp.py`（4）+ `tests/test_rl_run61_realistic.py`（3）= 7 用例。
