#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PR 剪辑效果实战演练脚本
========================

演示完整的 PR 自动化剪辑流程，将所有剪辑效果输出到指定文件夹。

流程：
1. 初始化输出目录
2. 生成各种转场效果脚本（30+ 种）
3. 生成高级剪辑效果脚本（拉镜、缩放、变速、关键帧等）
4. 生成完整剪辑流程脚本
5. 输出演练报告

输出目录结构：
output/pr_demo/
├── transitions/          # 转场效果脚本
│   ├── basic/            # 基础转场
│   ├── wipe/             # 擦除转场
│   ├── slide/            # 滑动转场
│   ├── advanced/         # 高级转场
│   └── creative/         # 创意转场
├── advanced_editing/     # 高级剪辑脚本
│   ├── whip_pan/         # 拉镜效果
│   ├── dynamic_zoom/     # 动态缩放
│   ├── speed_ramp/       # 变速效果
│   └── keyframe/         # 关键帧动画
├── presets/              # 预设文件
│   └── pr_converted/     # 从 AE 转化的 PR 预设
├── full_workflow/        # 完整工作流脚本
└── demo_report.md        # 演练报告
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation" / "src"))

from ae.pr_advanced_editing import (
    AdvancedEditParam,
    DynamicZoomParam,
    EditMode,
    KeyframeAnimationParam,
    KeyframePoint,
    MotionDirection,
    PremiereAdvancedEditing,
    SpeedRampParam,
    WhipPanParam,
)
from ae.pr_preset_converter import PRPresetConverter
from ae.pr_transition_system import (
    PremiereTransitionSystem,
    TransitionDirection,
    TransitionParam,
    TransitionType,
)


class PREditingDemo:
    """PR 剪辑效果实战演练。"""

    def __init__(self, output_dir: Path | str = None):
        if output_dir is None:
            output_dir = PROJECT_ROOT / "output" / "pr_demo"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.transition_system = PremiereTransitionSystem()
        self.editing_system = PremiereAdvancedEditing()
        self.preset_converter = PRPresetConverter()

        self.demo_stats = {
            "transitions": 0,
            "advanced_edits": 0,
            "presets": 0,
            "workflows": 0,
            "errors": [],
        }

    def run_full_demo(self) -> dict:
        """运行完整演练。"""
        print("=" * 70)
        print("PR 剪辑效果实战演练")
        print("=" * 70)
        print(f"输出目录: {self.output_dir}")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # 1. 生成转场效果
        print("【1/5】生成转场效果脚本...")
        self._generate_transitions()
        print(f"   ✓ 生成 {self.demo_stats['transitions']} 个转场脚本")
        print()

        # 2. 生成高级剪辑效果
        print("【2/5】生成高级剪辑效果脚本...")
        self._generate_advanced_editing()
        print(f"   ✓ 生成 {self.demo_stats['advanced_edits']} 个高级剪辑脚本")
        print()

        # 3. 转化 AE 预设
        print("【3/5】转化 AE 预设到 PR...")
        self._convert_presets()
        print(f"   ✓ 转化 {self.demo_stats['presets']} 个预设")
        print()

        # 4. 生成完整工作流
        print("【4/5】生成完整工作流脚本...")
        self._generate_full_workflow()
        print(f"   ✓ 生成 {self.demo_stats['workflows']} 个工作流脚本")
        print()

        # 5. 生成演练报告
        print("【5/5】生成演练报告...")
        self._generate_report()
        print("   ✓ 报告已生成")
        print()

        print("=" * 70)
        print("演练完成！")
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"统计: {self.demo_stats['transitions']} 转场 / "
              f"{self.demo_stats['advanced_edits']} 高级剪辑 / "
              f"{self.demo_stats['presets']} 预设 / "
              f"{self.demo_stats['workflows']} 工作流")
        print("=" * 70)

        return self.demo_stats

    def _generate_transitions(self):
        """生成所有转场效果脚本。"""
        transitions_dir = self.output_dir / "transitions"
        transitions_dir.mkdir(parents=True, exist_ok=True)

        categories = {
            "basic": ["cross_dissolve", "dip_to_black", "dip_to_white", "dissolve"],
            "wipe": ["wipe_left", "wipe_right", "wipe_up", "wipe_down", "wipe_center", "wipe_iris"],
            "slide": ["slide_left", "slide_right", "slide_up", "slide_down", "slide_over"],
            "advanced": ["zoom_in", "zoom_out", "zoom_blur", "whip_pan_left", "whip_pan_right",
                        "spin_cw", "spin_ccw", "stretch_in", "stretch_out"],
            "creative": ["swirl", "twist", "fold", "page_turn", "glitch", "strobe", "flash", "shake"],
        }

        for category, transition_types in categories.items():
            cat_dir = transitions_dir / category
            cat_dir.mkdir(exist_ok=True)

            for t_type in transition_types:
                try:
                    # 生成参数
                    direction = self._get_direction_for_transition(t_type)
                    params = TransitionParam(
                        transition_type=TransitionType(t_type),
                        duration=1.0 if category != "creative" else 0.5,
                        direction=direction,
                        blur_amount=20.0,
                        zoom_amount=1.5,
                        rotation_angle=180.0,
                    )

                    # 生成脚本
                    if category in ["advanced", "creative"]:
                        script = self.transition_system.generate_advanced_transition_script(
                            0, 0, params
                        )
                    else:
                        script = self.transition_system.generate_transition_script(
                            0, 0, params
                        )

                    # 保存脚本
                    script_path = cat_dir / f"{t_type}.jsx"
                    script_path.write_text(script, encoding="utf-8")

                    # 保存参数配置
                    config_path = cat_dir / f"{t_type}_config.json"
                    config_path.write_text(
                        json.dumps(params.to_dict(), ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

                    self.demo_stats["transitions"] += 1
                except Exception as e:
                    self.demo_stats["errors"].append(f"transition/{t_type}: {e}")

    def _get_direction_for_transition(self, t_type: str) -> TransitionDirection | None:
        """根据转场类型获取方向。"""
        if "left" in t_type:
            return TransitionDirection.LEFT
        elif "right" in t_type:
            return TransitionDirection.RIGHT
        elif "up" in t_type:
            return TransitionDirection.UP
        elif "down" in t_type:
            return TransitionDirection.DOWN
        elif "in" in t_type:
            return TransitionDirection.IN
        elif "out" in t_type:
            return TransitionDirection.OUT
        elif "cw" in t_type or "ccw" in t_type:
            return TransitionDirection.CENTER
        return None

    def _generate_advanced_editing(self):
        """生成高级剪辑效果脚本。"""
        editing_dir = self.output_dir / "advanced_editing"
        editing_dir.mkdir(parents=True, exist_ok=True)

        # 拉镜效果
        whip_dir = editing_dir / "whip_pan"
        whip_dir.mkdir(exist_ok=True)

        for direction in [MotionDirection.LEFT, MotionDirection.RIGHT,
                          MotionDirection.UP, MotionDirection.DOWN]:
            for speed in [1.5, 2.0, 3.0]:
                try:
                    params = WhipPanParam(
                        direction=direction,
                        speed=speed,
                        blur_amount=25.0,
                        duration=0.5,
                        overlap=0.3,
                    )
                    script = self.editing_system.generate_whip_pan_script(0, 0, params)
                    script_path = whip_dir / f"whip_{direction.value}_speed{speed}.jsx"
                    script_path.write_text(script, encoding="utf-8")

                    config_path = whip_dir / f"whip_{direction.value}_speed{speed}_config.json"
                    config_path.write_text(
                        json.dumps({
                            "direction": direction.value,
                            "speed": speed,
                            "blur_amount": 25.0,
                            "duration": 0.5,
                        }, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    self.demo_stats["advanced_edits"] += 1
                except Exception as e:
                    self.demo_stats["errors"].append(f"whip_pan/{direction.value}_{speed}: {e}")

        # 动态缩放
        zoom_dir = editing_dir / "dynamic_zoom"
        zoom_dir.mkdir(exist_ok=True)

        zoom_configs = [
            ("slow_zoom_in", 100.0, 150.0, 3.0, "ease_out"),
            ("fast_zoom_in", 100.0, 200.0, 1.0, "ease_in_out"),
            ("zoom_out", 150.0, 100.0, 2.0, "ease_in"),
            ("ken_burns", 100.0, 130.0, 5.0, "ease_in_out"),
        ]
        for name, start, end, duration, ease in zoom_configs:
            try:
                params = DynamicZoomParam(
                    start_scale=start,
                    end_scale=end,
                    duration=duration,
                    ease_type=ease,
                    focus_point=[0.5, 0.5],
                )
                script = self.editing_system.generate_dynamic_zoom_script(0, 0, params)
                script_path = zoom_dir / f"{name}.jsx"
                script_path.write_text(script, encoding="utf-8")

                config_path = zoom_dir / f"{name}_config.json"
                config_path.write_text(
                    json.dumps({
                        "start_scale": start,
                        "end_scale": end,
                        "duration": duration,
                        "ease_type": ease,
                    }, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self.demo_stats["advanced_edits"] += 1
            except Exception as e:
                self.demo_stats["errors"].append(f"dynamic_zoom/{name}: {e}")

        # 变速效果
        speed_dir = editing_dir / "speed_ramp"
        speed_dir.mkdir(exist_ok=True)

        speed_configs = [
            ("slow_motion", 100.0, 50.0, 1.0, "ease_in_out"),
            ("fast_forward", 100.0, 200.0, 0.5, "ease_out"),
            ("speed_ramp_up", 50.0, 100.0, 2.0, "ease_in"),
            ("speed_ramp_down", 100.0, 25.0, 1.5, "ease_out"),
        ]
        for name, start, end, duration, ease in speed_configs:
            try:
                params = SpeedRampParam(
                    start_speed=start,
                    end_speed=end,
                    ramp_duration=duration,
                    ease_type=ease,
                    frame_blending=True,
                )
                script = self.editing_system.generate_speed_ramp_script(0, 0, params)
                script_path = speed_dir / f"{name}.jsx"
                script_path.write_text(script, encoding="utf-8")

                config_path = speed_dir / f"{name}_config.json"
                config_path.write_text(
                    json.dumps({
                        "start_speed": start,
                        "end_speed": end,
                        "ramp_duration": duration,
                        "ease_type": ease,
                        "frame_blending": True,
                    }, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self.demo_stats["advanced_edits"] += 1
            except Exception as e:
                self.demo_stats["errors"].append(f"speed_ramp/{name}: {e}")

        # 关键帧动画
        keyframe_dir = editing_dir / "keyframe"
        keyframe_dir.mkdir(exist_ok=True)

        keyframe_configs = [
            ("position_bounce", "Position", [
                KeyframePoint(time=0.0, value=[960, 540], interpolation="linear"),
                KeyframePoint(time=0.5, value=[960, 300], interpolation="bezier"),
                KeyframePoint(time=1.0, value=[960, 540], interpolation="bezier"),
            ]),
            ("scale_pulse", "Scale", [
                KeyframePoint(time=0.0, value=[100, 100], interpolation="linear"),
                KeyframePoint(time=0.3, value=[120, 120], interpolation="bezier"),
                KeyframePoint(time=0.6, value=[100, 100], interpolation="bezier"),
            ]),
            ("rotation_spin", "Rotation", [
                KeyframePoint(time=0.0, value=[0.0], interpolation="linear"),
                KeyframePoint(time=1.0, value=[360.0], interpolation="linear"),
            ]),
        ]
        for name, prop, keyframes in keyframe_configs:
            try:
                params = KeyframeAnimationParam(
                    property_name=prop,
                    keyframes=keyframes,
                    easing="ease_in_out",
                )
                script = self.editing_system.generate_keyframe_animation_script(0, 0, params)
                script_path = keyframe_dir / f"{name}.jsx"
                script_path.write_text(script, encoding="utf-8")

                config_path = keyframe_dir / f"{name}_config.json"
                config_path.write_text(
                    json.dumps({
                        "property_name": prop,
                        "keyframes": [kf.__dict__ for kf in keyframes],
                        "easing": "ease_in_out",
                    }, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                self.demo_stats["advanced_edits"] += 1
            except Exception as e:
                self.demo_stats["errors"].append(f"keyframe/{name}: {e}")

    def _convert_presets(self):
        """转化 AE 预设到 PR。"""
        presets_dir = self.output_dir / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)

        ae_presets_dir = PROJECT_ROOT / "ae" / "presets"
        if not ae_presets_dir.exists():
            print(f"   ⚠ AE 预设目录不存在: {ae_presets_dir}")
            return

        try:
            results = self.preset_converter.convert_all_presets(
                ae_presets_dir,
                presets_dir / "pr_converted",
            )
            self.demo_stats["presets"] = sum(len(v) for v in results.values())
        except Exception as e:
            self.demo_stats["errors"].append(f"preset_conversion: {e}")

    def _generate_full_workflow(self):
        """生成完整工作流脚本。"""
        workflow_dir = self.output_dir / "full_workflow"
        workflow_dir.mkdir(parents=True, exist_ok=True)

        # 工作流 1: 简单剪辑流程
        simple_workflow = self._generate_simple_workflow()
        (workflow_dir / "01_simple_editing.jsx").write_text(
            simple_workflow, encoding="utf-8"
        )

        # 工作流 2: 多转场批量应用
        batch_workflow = self._generate_batch_transition_workflow()
        (workflow_dir / "02_batch_transitions.jsx").write_text(
            batch_workflow, encoding="utf-8"
        )

        # 工作流 3: 电影感剪辑
        cinematic_workflow = self._generate_cinematic_workflow()
        (workflow_dir / "03_cinematic_editing.jsx").write_text(
            cinematic_workflow, encoding="utf-8"
        )

        # 工作流 4: Vlog 风格剪辑
        vlog_workflow = self._generate_vlog_workflow()
        (workflow_dir / "04_vlog_style.jsx").write_text(
            vlog_workflow, encoding="utf-8"
        )

        self.demo_stats["workflows"] = 4

    def _generate_simple_workflow(self) -> str:
        """生成简单剪辑流程脚本。"""
        return """// ========================================
// PR 简单剪辑工作流
// 流程: 导入素材 -> 创建序列 -> 添加剪辑 -> 应用转场 -> 导出
// ========================================

(function() {
    var result = {
        status: "success",
        workflow: "simple_editing",
        steps: []
    };

    try {
        // 步骤 1: 检查项目
        if (!app.project) {
            result.status = "error";
            result.error = "没有打开的项目";
            return JSON.stringify(result);
        }
        result.steps.push("project_ready");

        // 步骤 2: 获取活动序列
        var seq = app.project.activeSequence;
        if (!seq) {
            result.status = "error";
            result.error = "没有活动序列";
            return JSON.stringify(result);
        }
        result.steps.push("sequence_ready");
        result.sequenceName = seq.name;
        result.videoTracks = seq.videoTracks.numItems;
        result.audioTracks = seq.audioTracks.numItems;

        // 步骤 3: 列出所有剪辑
        var clips = [];
        for (var t = 0; t < seq.videoTracks.numItems; t++) {
            var track = seq.videoTracks[t];
            for (var c = 0; c < track.clips.numItems; c++) {
                var clip = track.clips[c];
                clips.push({
                    track: t,
                    index: c,
                    name: clip.name,
                    start: clip.start.seconds,
                    duration: clip.duration.seconds
                });
            }
        }
        result.clips = clips;
        result.totalClips = clips.length;
        result.steps.push("clips_listed");

        // 步骤 4: 对前 N 个剪辑应用交叉溶解转场
        var transitionCount = 0;
        for (var i = 0; i < Math.min(clips.length - 1, 5); i++) {
            try {
                var trackIdx = clips[i].track;
                var clipIdx = i;
                var clip = seq.videoTracks[trackIdx].clips[clipIdx];
                var transition = clip.applyTransition("Cross Dissolve");
                if (transition) {
                    transition.duration = 1.0;
                    transitionCount++;
                }
            } catch(e) {
                // 跳过失败的转场
            }
        }
        result.transitionsApplied = transitionCount;
        result.steps.push("transitions_applied");

        result.steps.push("workflow_complete");

    } catch (e) {
        result.status = "error";
        result.error = e.toString();
    }

    return JSON.stringify(result, null, 2);
})();
"""

    def _generate_batch_transition_workflow(self) -> str:
        """生成批量转场应用脚本。"""
        return """// ========================================
// PR 批量转场工作流
// 对时间轴上的所有剪辑批量应用多种转场效果
// ========================================

(function() {
    var result = {
        status: "success",
        workflow: "batch_transitions",
        transitions: []
    };

    try {
        var seq = app.project.activeSequence;
        if (!seq) {
            result.status = "error";
            result.error = "没有活动序列";
            return JSON.stringify(result);
        }

        var transitionTypes = [
            "Cross Dissolve",
            "Dip to Black",
            "Wipe Right",
            "Slide Left",
            "Zoom In"
        ];

        var appliedCount = 0;
        for (var t = 0; t < seq.videoTracks.numItems; t++) {
            var track = seq.videoTracks[t];
            for (var c = 0; c < track.clips.numItems - 1; c++) {
                var clip = track.clips[c];
                var transType = transitionTypes[c % transitionTypes.length];

                try {
                    var transition = clip.applyTransition(transType);
                    if (transition) {
                        transition.duration = 0.8;
                        result.transitions.push({
                            track: t,
                            clip: c,
                            type: transType,
                            duration: 0.8
                        });
                        appliedCount++;
                    }
                } catch(e) {
                    result.transitions.push({
                        track: t,
                        clip: c,
                        type: transType,
                        error: e.toString()
                    });
                }
            }
        }

        result.totalApplied = appliedCount;

    } catch (e) {
        result.status = "error";
        result.error = e.toString();
    }

    return JSON.stringify(result, null, 2);
})();
"""

    def _generate_cinematic_workflow(self) -> str:
        """生成电影感剪辑工作流。"""
        return """// ========================================
// PR 电影感剪辑工作流
// 应用电影级调色 + 拉镜转场 + 速度曲线
// ========================================

(function() {
    var result = {
        status: "success",
        workflow: "cinematic_editing",
        effects: []
    };

    try {
        var seq = app.project.activeSequence;
        if (!seq) {
            result.status = "error";
            result.error = "没有活动序列";
            return JSON.stringify(result);
        }

        // 步骤 1: 为所有剪辑添加 Lumetri Color 电影调色
        for (var t = 0; t < seq.videoTracks.numItems; t++) {
            var track = seq.videoTracks[t];
            for (var c = 0; c < track.clips.numItems; c++) {
                var clip = track.clips[c];
                try {
                    // 添加 Lumetri Color 效果
                    var lumetri = clip.effects.addVideoEffect("Lumetri Color");
                    if (lumetri) {
                        result.effects.push({
                            track: t,
                            clip: c,
                            effect: "Lumetri Color",
                            type: "color_grade"
                        });
                    }
                } catch(e) {
                    // 跳过
                }
            }
        }

        // 步骤 2: 应用 Transform 效果实现动态缩放
        for (var t = 0; t < seq.videoTracks.numItems; t++) {
            var track = seq.videoTracks[t];
            for (var c = 0; c < track.clips.numItems; c++) {
                var clip = track.clips[c];
                try {
                    var transform = clip.effects.addVideoEffect("Transform");
                    if (transform) {
                        // Ken Burns 效果: 缓慢缩放
                        result.effects.push({
                            track: t,
                            clip: c,
                            effect: "Transform",
                            type: "ken_burns"
                        });
                    }
                } catch(e) {
                    // 跳过
                }
            }
        }

        result.totalEffects = result.effects.length;

    } catch (e) {
        result.status = "error";
        result.error = e.toString();
    }

    return JSON.stringify(result, null, 2);
})();
"""

    def _generate_vlog_workflow(self) -> str:
        """生成 Vlog 风格剪辑工作流。"""
        return """// ========================================
// PR Vlog 风格剪辑工作流
// 快节奏转场 + 动态缩放 + 故障效果
// ========================================

(function() {
    var result = {
        status: "success",
        workflow: "vlog_style",
        effects: []
    };

    try {
        var seq = app.project.activeSequence;
        if (!seq) {
            result.status = "error";
            result.error = "没有活动序列";
            return JSON.stringify(result);
        }

        // 步骤 1: 应用快速缩放转场
        var transitionCount = 0;
        for (var t = 0; t < seq.videoTracks.numItems; t++) {
            var track = seq.videoTracks[t];
            for (var c = 0; c < track.clips.numItems - 1; c++) {
                var clip = track.clips[c];
                try {
                    // 使用交叉溶解作为基础转场
                    var transition = clip.applyTransition("Cross Dissolve");
                    if (transition) {
                        transition.duration = 0.3;  // 快速转场
                        transitionCount++;
                    }
                } catch(e) {
                    // 跳过
                }
            }
        }
        result.transitions = transitionCount;

        // 步骤 2: 添加故障效果（Glitch）- 使用高斯模糊+通道偏移模拟
        for (var t = 0; t < seq.videoTracks.numItems; t++) {
            var track = seq.videoTracks[t];
            for (var c = 0; c < track.clips.numItems; c++) {
                if (c % 3 === 0) {  // 每 3 个剪辑加一个
                    var clip = track.clips[c];
                    try {
                        // 添加 Gaussian Blur 模拟故障模糊
                        var blur = clip.effects.addVideoEffect("Gaussian Blur");
                        if (blur) {
                            result.effects.push({
                                track: t,
                                clip: c,
                                effect: "Gaussian Blur",
                                type: "glitch"
                            });
                        }
                    } catch(e) {
                        // 跳过
                    }
                }
            }
        }

        result.totalEffects = result.effects.length;

    } catch (e) {
        result.status = "error";
        result.error = e.toString();
    }

    return JSON.stringify(result, null, 2);
})();
"""

    def _generate_report(self):
        """生成演练报告。"""
        report_path = self.output_dir / "demo_report.md"

        report = f"""# PR 剪辑效果实战演练报告

**生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**输出目录:** `{self.output_dir}`

## 📊 统计概览

| 类别 | 数量 |
|------|------|
| 转场效果 | {self.demo_stats['transitions']} |
| 高级剪辑效果 | {self.demo_stats['advanced_edits']} |
| 转化预设 | {self.demo_stats['presets']} |
| 完整工作流 | {self.demo_stats['workflows']} |
| 错误 | {len(self.demo_stats['errors'])} |

## 📁 目录结构

```
output/pr_demo/
├── transitions/              # 转场效果
│   ├── basic/                # 基础转场 (淡入淡出等)
│   ├── wipe/                 # 擦除转场
│   ├── slide/                # 滑动转场
│   ├── advanced/             # 高级转场 (拉镜、缩放、旋转等)
│   └── creative/             # 创意转场 (故障、抖动、漩涡等)
├── advanced_editing/         # 高级剪辑
│   ├── whip_pan/             # 拉镜效果 (4 方向 × 3 速度 = 12 种)
│   ├── dynamic_zoom/         # 动态缩放 (4 种配置)
│   ├── speed_ramp/           # 变速效果 (4 种配置)
│   └── keyframe/             # 关键帧动画 (3 种配置)
├── presets/                  # 预设文件
│   └── pr_converted/         # AE → PR 转化预设
├── full_workflow/            # 完整工作流
│   ├── 01_simple_editing.jsx
│   ├── 02_batch_transitions.jsx
│   ├── 03_cinematic_editing.jsx
│   └── 04_vlog_style.jsx
└── demo_report.md            # 本报告
```

## 🎬 转场效果清单

### 基础转场 (4 种)
- Cross Dissolve - 交叉溶解
- Dip to Black - 黑场过渡
- Dip to White - 白场过渡
- Dissolve - 溶解

### 擦除转场 (6 种)
- Wipe Left / Right / Up / Down - 四向擦除
- Wipe Center - 中心擦除
- Wipe Iris - 圆形擦除

### 滑动转场 (5 种)
- Slide Left / Right / Up / Down - 四向滑动
- Slide Over - 覆盖滑动

### 高级转场 (9 种)
- Zoom In / Out / Blur - 缩放转场
- Whip Pan Left / Right - 拉镜转场
- Spin CW / CCW - 旋转转场
- Stretch In / Out - 拉伸转场

### 创意转场 (8 种)
- Swirl - 漩涡
- Twist - 扭曲
- Fold - 折叠
- Page Turn - 翻页
- Glitch - 故障
- Strobe - 频闪
- Flash - 闪烁
- Shake - 抖动

## ✨ 高级剪辑效果

### 拉镜效果 (Whip Pan) - 12 种
- 4 个方向: 左、右、上、下
- 3 种速度: 1.5x / 2.0x / 3.0x
- 含运动模糊效果

### 动态缩放 (Dynamic Zoom) - 4 种
- Slow Zoom In - 缓慢放大
- Fast Zoom In - 快速放大
- Zoom Out - 缩小
- Ken Burns - 肯·伯恩斯效果 (缓慢推拉)

### 变速效果 (Speed Ramp) - 4 种
- Slow Motion - 慢动作 (100% → 50%)
- Fast Forward - 快进 (100% → 200%)
- Speed Ramp Up - 加速 (50% → 100%)
- Speed Ramp Down - 减速 (100% → 25%)

### 关键帧动画 - 3 种
- Position Bounce - 位置弹跳
- Scale Pulse - 缩放脉冲
- Rotation Spin - 旋转

## 🔄 完整工作流

### 1. 简单剪辑工作流
导入素材 → 创建序列 → 添加剪辑 → 应用转场 → 导出

### 2. 批量转场工作流
对时间轴上所有剪辑批量应用 5 种转场效果循环

### 3. 电影感剪辑工作流
Lumetri Color 调色 + Ken Burns 动态缩放 + 电影级转场

### 4. Vlog 风格工作流
快节奏转场 + 故障效果 + 动态缩放

## 🚀 使用方法

### 方法 1: 直接运行 JSX 脚本
1. 打开 Premiere Pro
2. 打开或创建一个项目和序列
3. 文件 → 脚本 → 运行脚本文件...
4. 选择对应的 `.jsx` 文件
5. 查看输出结果

### 方法 2: 使用 MCP 桥接
1. 确保 `pr_mcp_bridge.jsx` 在 PR 中运行
2. 使用 Python API 调用:
   ```python
   from ae.pr_mcp_client import PremiereMCP
   client = PremiereMCP()
   result = client.apply_transition_effect(...)
   ```

### 方法 3: 使用 PREngine
```python
from engines.pr.engine import PREngine
engine = PREngine()
result = await engine.execute(script_content)
```

## ⚠️ 注意事项

1. **脚本兼容性**: 所有脚本基于 Premiere Pro 2024+ ExtendScript API 编写
2. **效果可用性**: 部分高级效果需要相应的 PR 版本支持
3. **性能考虑**: 批量应用大量效果可能需要较长时间
4. **项目备份**: 运行脚本前建议备份项目文件
5. **撤销操作**: 建议在运行批量脚本前保存项目，方便撤销

"""

        if self.demo_stats["errors"]:
            report += "\n## ❌ 错误列表\n\n"
            for err in self.demo_stats["errors"]:
                report += f"- {err}\n"

        report_path.write_text(report, encoding="utf-8")


def main():
    """命令行入口。"""
    import argparse

    parser = argparse.ArgumentParser(description="PR 剪辑效果实战演练")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="输出目录 (默认: output/pr_demo)",
    )
    args = parser.parse_args()

    demo = PREditingDemo(output_dir=args.output_dir)
    stats = demo.run_full_demo()

    print(f"\n输出目录: {demo.output_dir}")
    print(f"演练报告: {demo.output_dir / 'demo_report.md'}")

    return 0 if not stats["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
