# Phase 3 - 音频驱动自动化

> 基于 Phase 2 实战经验沉淀，实现可配置、可复用、自动化的音频驱动 AE 工作流

---

## 快速开始

### 一键启动

1. 将音频文件命名为 `input.wav` 放在项目根目录
2. 双击运行 `一键启动工具箱.bat`
3. 按提示完成预检 → 分析 → 写入 → 渲染

### 手动步骤

```bash
# 1. 音频分析
py -3.11 phase2_optimized.py --audio input.wav

# 2. AE 预检（在AE中运行）
# 打开 scripts/check_before_run.jsx

# 3. 验证写入
py -3.11 verify_phase2_run.py

# 4. 渲染（在AE中手动渲染）
```

---

## 目录结构

```
Phase3-音频驱动自动化/
├── 一键启动工具箱.bat        # 入口脚本
├── scripts/
│   └── check_before_run.jsx  # AE 预检脚本
├── config/
│   └── beat_config.json      # 参数配置模板
└── index.md                  # 本文件
```

---

## 配置文件说明

`beat_config.json` 核心参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `audio_settings.min_duration_sec` | 音频最短时长（秒） | 8.0 |
| `beat_detection.strong_beat_threshold` | 强拍能量阈值（×均值） | 1.3 |
| `frequency_bands.low.range_hz` | 低频范围（Hz） | [20, 200] |
| `frequency_bands.high.range_hz` | 高频范围（Hz） | [4000, 12000] |
| `keyframe_templates.strong_beat.scale.frames` | 强拍 Scale 关键帧 | 5帧模板 |
| `expression_templates.opacity_driven` | Opacity 表达式模板 | 能量驱动 |

---

## 预检项目

`check_before_run.jsx` 自动检测：

1. ✓ 音频时长 ≥ 8秒
2. ✓ 关键图层存在（MainVideo, Audio Controller）
3. ✓ 表达式绑定完整（Opacity, Rotation, Glow）
4. ✓ 能量滑块控制器存在（4个）
5. ⚠ 分层结构（背景/前景层检测）

---

## 扩展方向

### Phase 3.1: 分层驱动
- 背景层绑定低频能量
- 前景层绑定高频能量
- 实现多层协同动画

### Phase 3.2: 贝塞尔包络
- 调用 `BeatKeyframeMapper.calculate_bezier_envelope()`
- 替换线性关键帧，实现平滑过渡

### Phase 3.3: 风格自适应
- 检测能量密度自动切换 `on_beat`/`double_time`/`half_time`
- 高能段落加速，低能段落放慢

---

## 经验文档

- [Phase 2 实战经验总结](../Phase2实战经验总结.md)
- [V4 深度分析报告](../../reports/v4_phase2_review.md)
- [V4 经验审查建议](../../reports/v4_experience_review.md)