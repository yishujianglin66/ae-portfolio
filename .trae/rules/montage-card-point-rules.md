---
alwaysApply: true
description: 漫剪卡点铁律 - 音乐驱动剪辑的已验证链路（禁止自己单独开发，必须复用）
---

# 漫剪卡点铁律（音乐驱动剪辑）

> 本规则记录 **2026-08-12~13 实测验证成功**的卡点/节奏/变速/运镜全链路。
> 任何漫剪/卡点/AMV/音乐剪辑任务 **必须** 先按此复用已验证资产，
> **禁止自己单独开发新的切点/变速/运镜逻辑**。多次绕弯路教训：
> v23 曾重写切点逻辑 8 次都不如 v22，最终发现答案是"复用已集成的工具"。

---

## 0. 最高铁律：先回忆，再复用，禁止单干

1. **任何剪辑增强任务，第一件事是搜索以下已验证资产**（不要凭记忆造轮子）：
   - `core/music_dynamics.py` — MusicDynamicsAnalyzer（能量分层 high/mid/low，v21c 就有）
   - `core/beat_strength_engine.py` — BeatStrengthEngine（节拍强弱分级 STRONG/MEDIUM/WEAK）
   - `core/style_presets.py` — StylePresetSystem（choose_camera 运镜池）
   - `external/OpenMontage/.agents/skills/music-to-video/scripts/analyze-beatgrid.py` — 鼓类型/网格语义/kick 检测
   - `ai/taste_contract.py` — 品味三旋钮（visual_variance/motion_intensity/information_density）
   - `data/style_cards/*.json` — 风格卡（amv_highenergy 等）
   - `tmp/render_v22.py` — v22 完整编排参考（用户认可的基线）
2. **用 `grep -rn` 全库搜索**，确认资产存在后再动手。
3. 若某个能力已有实现，**只做适配集成，不重写**。

---

## 1. 卡点链路（已验证，顺序固定）

```
BGM → music_dynamics 能量分层(high/mid/low) → 切点密度按能量级
    → kick/strong 强制锚定(beatgrid) → 变速/运镜按 beat_strength 逐镜头
```

- **切点密度**：high 段 onset∪beat 全切(0.18s) / mid 段 beat 逐拍 / low 段仅 downbeat 长镜头(呼吸)
- **用 `_arc_levels`（能量级）决定密度**，不要用 onset 密度（low 段的 hihat 会被误判为高密）
- **边界吸附到拍**：非首尾边界 250ms 内有拍/onset 则吸附，消除"不在拍上的镜头"
- **空档正确性**：200ms 内无拍的边界保留（长镜头跨越空档=正确，不是偏移）

## 2. 变速（已验证）

- **逐镜头动态决策**：`BeatStrengthEngine.classify_beats` → `speed_for_shot(level, beat_strength, energy_norm, is_downbeat)`
  - high+强拍→1.0x pulse / high+普通→1.3-1.5x fast_pan
  - low+强拍→0.55x slowmo / low+普通→0.7x
  - mid+强拍→0.9x zoom_back / mid+普通→1.0x static
- **beat 匹配必须最近回退**：`get_beat_at_time` 失败时取离镜头开始最近的拍（否则 55% 退化 MEDIUM 全原速）
- **e_norm 用 RMS 真实能量分位归一**（P10/P90），不要用段目标均值
- **变速镜头强制硬切**：`_xfade_for` 里 `speed != 1.0` 返回硬切——setpts 与 xfade 预补偿叠加会引入 98% 切点滞后

## 3. 撞拍锚定（beatgrid）

- **kick(低频<150Hz) + strong 拍** 强制并入切点，保证每个重音一刀
- 排除 hihat/riser/glitch 事件（不"撞"）
- 加载器：`ProductionDirector._load_beatgrid()`（缓存 tmp/audiomap_*.json）
- 实测 kick 命中 91%

## 4. 节奏呼吸（information_density 旋钮）

- **information_density 必须接入切点密度**（否则默认值导致一直快切，无呼吸）
- low 段最小间隔 = `max(0.3, 1.5 - 0.12*info_d)`，mid 段 = `max(0.18, 0.8 - 0.06*info_d)`，high 段保持 0.18s
- **加载风格卡**：`ProductionDirector(taste_profile=风格卡dict)`，高燃用 `data/style_cards/amv_highenergy.json`
  （视觉7/运动8/信息密度4 → 低密铺垫长镜呼吸 + 高潮爆发）
- 实测：<0.3s 镜头 76%→33%，自进化评分 68.5→82.3

## 5. 环境铁律

- **Python 必须用 `py -3.12`**（默认 `py` 指向损坏的 Python 3.14，会崩）
- **ffmpeg 在 PATH**：`/c/ffmpeg/bin/ffmpeg`（质量评分/镜头检测依赖）
- PowerShell 用 `;` 不用 `&&`；GBK 控制台勿打印 emoji
- 含中文的 .ps1 必须 UTF-8 BOM

---

## 6. 已验证成果基线（2026-08-13）

| 指标 | v22 | v23(本链路) |
|------|-----|------------|
| onset 对齐 | 60.9% | 72.9% |
| CBE 踩拍误差 | 61ms | 48ms |
| 变速 | 动态4档 | 动态多档(pulse/slowmo/fast_pan) |
| 运镜 | 6种 | 6种 |
| 节奏呼吸 | 有 | 有(<0.3s仅33%) |
| kick 锚定 | — | 91%重音有刀 |
| 自进化评分 | — | 82.3 |

**禁止回退**：任何改动不得让这些指标倒退；新方案必须先对照此基线。
