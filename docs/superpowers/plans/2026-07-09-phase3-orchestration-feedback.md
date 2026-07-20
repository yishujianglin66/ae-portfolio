# Phase 3: 智能编排与反馈闭环 - 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现智能场景编排、音乐节拍联动、效果组合推荐和完整反馈闭环，打通"输入描述→AE执行→结果反馈→学习优化"的全流程闭环。

**Architecture:** 在现有五层Pipeline基础上，新增场景编排层（Layer 3.5）和反馈闭环层（Layer 5增强）。Python端负责编排逻辑，通过TS编译器生成JSX，通过MCP Bridge执行并回传结果。TS Phase5模块的验证/学习/恢复能力被封装为Python可用的反馈管理器。

**Tech Stack:** Python 3.11, TypeScript (compiler/build), ExtendScript (AE 2026), JSON文件通信

---

## 整体架构升级

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AE AI Agent - Phase 3 架构                       │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 5: Feedback Loop (反馈闭环层)                               │
│  ├── 结果验证 (ResultVerifier - TS Phase5)                        │
│  ├── 学习优化 (LearningLoop - TS Phase5)                          │
│  ├── 失败恢复 (FailureRecovery - TS Phase5)                       │
│  └── 置信度校准 (ConfidenceCalibrator - 新增)                     │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 4: Execution (执行层)                                       │
│  ├── TS编译器 (phase4 生成器 + codegen)                            │
│  ├── AE执行引擎 (MCP Bridge)                                       │
│  └── 渲染与输出                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 3.5: Orchestration (编排层) ← Phase 3 新增                  │
│  ├── 场景编排引擎 (SceneOrchestrator) - 多场景切换+转场            │
│  ├── 节拍编排器 (BeatOrchestrator) - 音乐驱动的效果/动画编排       │
│  ├── 效果组合器 (EffectComposer) - 效果搭配+风格模板库             │
│  └── 镜头语言引擎 (CameraLanguageEngine) - 推/拉/摇/移/跟          │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 3: Planning (规划层)                                        │
│  ├── 任务分解                                                      │
│  └── 资源调度                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 2: Understanding (理解层)                                    │
│  ├── 语义理解 (NLU Parser - TS Phase4)                            │
│  ├── 情绪识别                                                      │
│  └── 意图推理                                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 1: Perception (感知层)                                       │
│  ├── 视频帧分析 (video_analyzer_enhanced.py)                       │
│  ├── 音频分析 (audio_analyzer_enhanced.py - BPM/节拍/能量)        │
│  └── 素材检索                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 文件结构规划

| 文件 | 职责 | 状态 |
|------|------|------|
| `scene_orchestrator.py` | 场景编排引擎 - 多场景切换、转场效果、镜头语言 | 待创建 |
| `beat_orchestrator.py` | 节拍编排器 - 音乐驱动的效果和动画编排 | 待创建 |
| `effect_composer.py` | 效果组合器 - 效果搭配推荐、风格模板库 | 待创建 |
| `feedback_loop_manager.py` | 反馈闭环管理器 - 整合TS Phase5到Python | 待创建 |
| `ae_agent_pipeline.py` | 端到端流程管理器 - 新增编排层和反馈层集成 | 待修改 |
| `style_template_library.py` | 风格模板库 - 20+种视频风格的效果组合预设 | 待创建 |
| `tests/test_phase3_scene.py` | 场景编排引擎测试 | 待创建 |
| `tests/test_phase3_beat.py` | 节拍编排器测试 | 待创建 |
| `tests/test_phase3_composer.py` | 效果组合器测试 | 待创建 |
| `tests/test_phase3_feedback.py` | 反馈闭环测试 | 待创建 |
| `tests/test_phase3_integration.py` | Phase 3集成测试 | 待创建 |
| `tests/test_phase3_real_ae.py` | Phase 3 AE实机验证脚本 | 待创建 |

---

## Task 1: 场景编排引擎 (SceneOrchestrator)

**Files:**
- Create: `scene_orchestrator.py`
- Test: `tests/test_phase3_scene.py`

**核心功能：**
1. 多场景管理 - 创建、排序、合并场景
2. 转场效果库 - 10种常见转场（淡入淡出、滑动、缩放、擦除、溶解、闪白、模糊转场等）
3. 镜头语言引擎 - 推、拉、摇、移、跟、升降、震镜 7种镜头运动
4. 场景时序计算 - 自动计算每个场景的起止时间和转场重叠

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_phase3_scene.py
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scene_orchestrator import SceneOrchestrator, Scene, Transition, CameraMove


class TestSceneOrchestrator:
    def test_initialization(self):
        orch = SceneOrchestrator()
        assert orch.scenes == []
        assert orch.total_duration == 0

    def test_add_scene(self):
        orch = SceneOrchestrator()
        scene = Scene(name="开场", duration=3.0, layer_name="scene_1")
        orch.add_scene(scene)
        assert len(orch.scenes) == 1
        assert orch.total_duration == 3.0

    def test_add_multiple_scenes(self):
        orch = SceneOrchestrator()
        orch.add_scene(Scene(name="开场", duration=3.0))
        orch.add_scene(Scene(name="主体", duration=5.0))
        orch.add_scene(Scene(name="结尾", duration=2.0))
        assert len(orch.scenes) == 3
        assert orch.total_duration == 10.0

    def test_generate_transitions_default(self):
        orch = SceneOrchestrator()
        orch.add_scene(Scene(name="s1", duration=3.0))
        orch.add_scene(Scene(name="s2", duration=3.0))
        transitions = orch.generate_transitions("crossfade")
        assert len(transitions) == 1
        assert transitions[0].type == "crossfade"
        assert transitions[0].duration == 0.5

    def test_generate_all_transition_types(self):
        types = ["crossfade", "slide_left", "slide_right", "zoom_in", 
                 "wipe_left", "dissolve", "flash_white", "blur", "scale_up", "page_turn"]
        orch = SceneOrchestrator()
        orch.add_scene(Scene(name="s1", duration=2.0))
        orch.add_scene(Scene(name="s2", duration=2.0))
        for t in types:
            transitions = orch.generate_transitions(t)
            assert len(transitions) == 1
            assert transitions[0].type == t

    def test_camera_move_push(self):
        move = CameraMove(type="push", start_scale=1.0, end_scale=1.3, duration=2.0)
        assert move.type == "push"
        assert move.start_scale == 1.0
        assert move.end_scale == 1.3

    def test_camera_move_pan(self):
        move = CameraMove(type="pan_left", start_x=0, end_x=-200, duration=3.0)
        assert move.type == "pan_left"

    def test_apply_camera_to_scene(self):
        orch = SceneOrchestrator()
        scene = Scene(name="test", duration=4.0)
        move = CameraMove(type="push", start_scale=1.0, end_scale=1.2, duration=4.0)
        keyframes = orch.apply_camera_move(scene, move)
        assert len(keyframes) > 0
        assert keyframes[0]["propertyName"] == "Scale"

    def test_generate_scene_timeline(self):
        orch = SceneOrchestrator()
        orch.add_scene(Scene(name="s1", duration=3.0))
        orch.add_scene(Scene(name="s2", duration=3.0))
        timeline = orch.generate_timeline()
        assert len(timeline) == 2
        assert timeline[0]["start"] == 0
        assert timeline[0]["end"] == 3.0
        assert timeline[1]["start"] == 3.0

    def test_generate_timeline_with_transitions(self):
        orch = SceneOrchestrator()
        orch.add_scene(Scene(name="s1", duration=3.0))
        orch.add_scene(Scene(name="s2", duration=3.0))
        orch.generate_transitions("crossfade", duration=0.5)
        timeline = orch.generate_timeline()
        # 转场重叠后总时长应减少
        assert timeline[-1]["end"] < 6.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_phase3_scene.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'scene_orchestrator'"

- [ ] **Step 3: 实现 SceneOrchestrator**

```python
# scene_orchestrator.py
"""
场景编排引擎 - 多场景切换、转场效果、镜头语言
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import math


@dataclass
class Scene:
    name: str
    duration: float
    layer_name: str = ""
    start_time: float = 0.0
    effects: List[Dict] = field(default_factory=list)
    camera_moves: List = field(default_factory=list)


@dataclass
class Transition:
    type: str
    duration: float
    start_time: float = 0.0
    from_scene: str = ""
    to_scene: str = ""


@dataclass
class CameraMove:
    type: str  # push, pull, pan_left, pan_right, tilt_up, tilt_down, follow, shake
    duration: float
    start_scale: float = 1.0
    end_scale: float = 1.0
    start_x: float = 0.0
    end_x: float = 0.0
    start_y: float = 0.0
    end_y: float = 0.0
    shake_amplitude: float = 0.0
    shake_frequency: float = 0.0


TRANSITION_TYPES = {
    "crossfade": {"name": "交叉淡入淡出", "effect": "ADBE Opacity", "overlap": True},
    "slide_left": {"name": "左滑", "effect": "ADBE Position", "overlap": True},
    "slide_right": {"name": "右滑", "effect": "ADBE Position", "overlap": True},
    "zoom_in": {"name": "放大切入", "effect": "ADBE Scale", "overlap": True},
    "wipe_left": {"name": "左擦除", "effect": "ADBE Linear Wipe", "overlap": False},
    "dissolve": {"name": "溶解", "effect": "ADBE Dissolve", "overlap": True},
    "flash_white": {"name": "闪白", "effect": "ADBE Exposure", "overlap": True},
    "blur": {"name": "模糊转场", "effect": "ADBE Gaussian Blur 2", "overlap": True},
    "scale_up": {"name": "缩放弹出", "effect": "ADBE Scale", "overlap": False},
    "page_turn": {"name": "翻页", "effect": "CC Page Turn", "overlap": True},
}


CAMERA_MOVE_TYPES = {
    "push": {"name": "推镜", "property": "Scale", "direction": "in"},
    "pull": {"name": "拉镜", "property": "Scale", "direction": "out"},
    "pan_left": {"name": "左摇", "property": "Position", "direction": "left"},
    "pan_right": {"name": "右摇", "property": "Position", "direction": "right"},
    "tilt_up": {"name": "上摇", "property": "Position", "direction": "up"},
    "tilt_down": {"name": "下摇", "property": "Position", "direction": "down"},
    "follow": {"name": "跟随", "property": "Position", "direction": "track"},
    "shake": {"name": "震镜", "property": "Position", "direction": "shake"},
    "dolly": {"name": "轨道移动", "property": "Position", "direction": "dolly"},
    "crane": {"name": "升降镜头", "property": "Position", "direction": "crane"},
}


class SceneOrchestrator:
    def __init__(self, fps: int = 30, comp_width: int = 1920, comp_height: int = 1080):
        self.fps = fps
        self.comp_width = comp_width
        self.comp_height = comp_height
        self.scenes: List[Scene] = []
        self.transitions: List[Transition] = []

    def add_scene(self, scene: Scene) -> None:
        if not scene.layer_name:
            scene.layer_name = f"scene_{len(self.scenes) + 1:03d}"
        self.scenes.append(scene)
        self._recalculate_times()

    def _recalculate_times(self) -> None:
        current = 0.0
        for i, scene in enumerate(self.scenes):
            scene.start_time = current
            current += scene.duration

    @property
    def total_duration(self) -> float:
        if not self.scenes:
            return 0.0
        return self.scenes[-1].start_time + self.scenes[-1].duration

    def generate_transitions(
        self,
        transition_type: str = "crossfade",
        duration: float = 0.5,
    ) -> List[Transition]:
        if transition_type not in TRANSITION_TYPES:
            raise ValueError(f"Unknown transition type: {transition_type}")
        
        self.transitions = []
        for i in range(len(self.scenes) - 1):
            from_scene = self.scenes[i]
            to_scene = self.scenes[i + 1]
            trans = Transition(
                type=transition_type,
                duration=duration,
                start_time=from_scene.start_time + from_scene.duration - duration,
                from_scene=from_scene.name,
                to_scene=to_scene.name,
            )
            self.transitions.append(trans)
        
        self._adjust_scene_times_for_transitions()
        return self.transitions

    def _adjust_scene_times_for_transitions(self) -> None:
        if not self.transitions:
            return
        
        overlap = self.transitions[0].duration
        current = 0.0
        for i, scene in enumerate(self.scenes):
            scene.start_time = current
            current += scene.duration
            if i < len(self.scenes) - 1:
                current -= overlap

    def apply_camera_move(
        self,
        scene: Scene,
        move: CameraMove,
        layer_name: str = "",
    ) -> List[Dict[str, Any]]:
        layer = layer_name or scene.layer_name
        keyframes = []
        start_t = scene.start_time
        end_t = start_t + move.duration

        if move.type == "push":
            keyframes.append({
                "layerName": layer,
                "propertyName": "Scale",
                "time": start_t,
                "value": [move.start_scale * 100, move.start_scale * 100],
                "easeType": "ease_out",
            })
            keyframes.append({
                "layerName": layer,
                "propertyName": "Scale",
                "time": end_t,
                "value": [move.end_scale * 100, move.end_scale * 100],
                "easeType": "ease_in",
            })
        elif move.type == "pull":
            keyframes.append({
                "layerName": layer,
                "propertyName": "Scale",
                "time": start_t,
                "value": [move.start_scale * 100, move.start_scale * 100],
                "easeType": "ease_out",
            })
            keyframes.append({
                "layerName": layer,
                "propertyName": "Scale",
                "time": end_t,
                "value": [move.end_scale * 100, move.end_scale * 100],
                "easeType": "ease_in",
            })
        elif move.type in ("pan_left", "pan_right", "tilt_up", "tilt_down"):
            start_x = self.comp_width / 2 + move.start_x
            start_y = self.comp_height / 2 + move.start_y
            end_x = self.comp_width / 2 + move.end_x
            end_y = self.comp_height / 2 + move.end_y
            
            keyframes.append({
                "layerName": layer,
                "propertyName": "Anchor Point",
                "time": start_t,
                "value": [start_x, start_y],
                "easeType": "ease_in_out",
            })
            keyframes.append({
                "layerName": layer,
                "propertyName": "Anchor Point",
                "time": end_t,
                "value": [end_x, end_y],
                "easeType": "ease_in_out",
            })
        elif move.type == "shake":
            n_frames = int(move.duration * self.fps)
            for i in range(n_frames + 1):
                t = start_t + i / self.fps
                progress = i / n_frames
                decay = 1.0 - progress
                offset_x = math.sin(progress * move.shake_frequency * math.pi * 2) * move.shake_amplitude * decay
                offset_y = math.cos(progress * move.shake_frequency * math.pi * 2 * 0.7) * move.shake_amplitude * 0.6 * decay
                keyframes.append({
                    "layerName": layer,
                    "propertyName": "Position",
                    "time": t,
                    "value": [self.comp_width / 2 + offset_x, self.comp_height / 2 + offset_y],
                    "easeType": "linear",
                })

        return keyframes

    def generate_timeline(self) -> List[Dict[str, Any]]:
        timeline = []
        for scene in self.scenes:
            timeline.append({
                "name": scene.name,
                "layer_name": scene.layer_name,
                "start": scene.start_time,
                "end": scene.start_time + scene.duration,
                "duration": scene.duration,
                "effects_count": len(scene.effects),
            })
        return timeline

    def generate_transition_keyframes(self) -> List[Dict[str, Any]]:
        keyframes = []
        for trans in self.transitions:
            if trans.type == "crossfade":
                from_layer = self._find_scene_layer(trans.from_scene)
                to_layer = self._find_scene_layer(trans.to_scene)
                if from_layer and to_layer:
                    keyframes.extend(self._crossfade_keyframes(
                        from_layer, to_layer, trans.start_time, trans.duration
                    ))
            elif trans.type == "blur":
                from_layer = self._find_scene_layer(trans.from_scene)
                to_layer = self._find_scene_layer(trans.to_scene)
                if from_layer and to_layer:
                    keyframes.extend(self._blur_transition_keyframes(
                        from_layer, to_layer, trans.start_time, trans.duration
                    ))
        return keyframes

    def _find_scene_layer(self, scene_name: str) -> str:
        for scene in self.scenes:
            if scene.name == scene_name:
                return scene.layer_name
        return ""

    def _crossfade_keyframes(
        self, from_layer: str, to_layer: str, start_t: float, duration: float
    ) -> List[Dict]:
        return [
            {"layerName": from_layer, "propertyName": "Opacity",
             "time": start_t, "value": 100, "easeType": "linear"},
            {"layerName": from_layer, "propertyName": "Opacity",
             "time": start_t + duration, "value": 0, "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Opacity",
             "time": start_t, "value": 0, "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Opacity",
             "time": start_t + duration, "value": 100, "easeType": "linear"},
        ]

    def _blur_transition_keyframes(
        self, from_layer: str, to_layer: str, start_t: float, duration: float
    ) -> List[Dict]:
        mid_t = start_t + duration / 2
        return [
            {"layerName": from_layer, "propertyName": "Opacity",
             "time": start_t, "value": 100, "easeType": "linear"},
            {"layerName": from_layer, "propertyName": "Opacity",
             "time": mid_t, "value": 0, "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Opacity",
             "time": mid_t, "value": 0, "easeType": "linear"},
            {"layerName": to_layer, "propertyName": "Opacity",
             "time": start_t + duration, "value": 100, "easeType": "linear"},
        ]

    def to_planning_result(self) -> Dict[str, Any]:
        effects = []
        keyframes = []
        layers = []

        for scene in self.scenes:
            layers.append({
                "name": scene.layer_name,
                "type": "footage",
                "startTime": scene.start_time,
                "duration": scene.duration,
            })
            for eff in scene.effects:
                effects.append({
                    "layerName": scene.layer_name,
                    "effectName": eff.get("matchName", ""),
                    "settings": eff.get("settings", {}),
                })
            for move in scene.camera_moves:
                keyframes.extend(self.apply_camera_move(scene, move, scene.layer_name))

        keyframes.extend(self.generate_transition_keyframes())

        return {
            "composition": {
                "name": "Orchestrated_Comp",
                "width": self.comp_width,
                "height": self.comp_height,
                "duration": self.total_duration,
                "frameRate": self.fps,
            },
            "layers": layers,
            "effects": effects,
            "keyframes": keyframes,
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_phase3_scene.py -v`
Expected: 10 passed

---

## Task 2: 节拍编排器 (BeatOrchestrator)

**Files:**
- Create: `beat_orchestrator.py`
- Test: `tests/test_phase3_beat.py`

**核心功能：**
1. 节拍驱动的效果触发 - 在重拍/弱拍触发不同效果
2. 节拍同步动画生成 - 缩放、透明度、位移与节拍同步
3. 音乐结构编排 - 副歌增强、主歌铺垫、间奏过渡
4. 能量曲线映射 - 将音乐能量映射为效果强度

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_phase3_beat.py
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from beat_orchestrator import BeatOrchestrator, BeatSyncConfig


class TestBeatOrchestrator:
    def test_initialization(self):
        orch = BeatOrchestrator(bpm=120, fps=30)
        assert orch.bpm == 120
        assert orch.beat_interval == 0.5  # 60/120

    def test_beat_interval_calculation(self):
        orch = BeatOrchestrator(bpm=100)
        assert abs(orch.beat_interval - 0.6) < 0.001
        orch2 = BeatOrchestrator(bpm=150)
        assert abs(orch2.beat_interval - 0.4) < 0.001

    def test_generate_beat_timeline(self):
        orch = BeatOrchestrator(bpm=120, fps=30)
        beats = orch.generate_beat_timeline(duration=3.0)
        assert len(beats) == 6  # 3s / 0.5s = 6 beats
        assert beats[0] == 0.0
        assert beats[1] == 0.5
        assert beats[-1] == 2.5

    def test_generate_downbeats(self):
        orch = BeatOrchestrator(bpm=120, fps=30, beats_per_measure=4)
        downbeats = orch.generate_downbeats(duration=4.0)
        assert len(downbeats) == 2  # 4s / 2s(measure) = 2
        assert downbeats[0] == 0.0
        assert downbeats[1] == 2.0

    def test_beat_scale_animation(self):
        orch = BeatOrchestrator(bpm=120)
        config = BeatSyncConfig(
            property_type="scale",
            base_value=100,
            beat_value=120,
            attack=0.05,
            decay=0.15,
        )
        keyframes = orch.generate_beat_synced_keyframes(
            layer_name="test_layer",
            beat_times=[0.0, 0.5, 1.0],
            config=config,
        )
        assert len(keyframes) > 0
        assert keyframes[0]["propertyName"] == "Scale"

    def test_beat_opacity_animation(self):
        orch = BeatOrchestrator(bpm=120)
        config = BeatSyncConfig(
            property_type="opacity",
            base_value=50,
            beat_value=100,
            attack=0.03,
            decay=0.1,
        )
        keyframes = orch.generate_beat_synced_keyframes(
            layer_name="test_layer",
            beat_times=[0.0, 0.5],
            config=config,
        )
        assert len(keyframes) > 0
        assert keyframes[0]["propertyName"] == "Opacity"

    def test_effect_on_beat(self):
        orch = BeatOrchestrator(bpm=120)
        effects = orch.generate_beat_effect_triggers(
            layer_name="fx_layer",
            beat_times=[0.0, 1.0, 2.0],
            effect_type="glow_pulse",
            intensity=1.0,
        )
        assert len(effects) > 0

    def test_musical_structure_sections(self):
        orch = BeatOrchestrator(bpm=120)
        sections = orch.generate_musical_structure(duration=20.0)
        assert "intro" in sections
        assert "verse" in sections
        assert "chorus" in sections
        assert "outro" in sections

    def test_energy_to_intensity_mapping(self):
        orch = BeatOrchestrator(bpm=120)
        intensity = orch.energy_to_intensity(0.0)
        assert intensity == 0.0
        intensity = orch.energy_to_intensity(1.0)
        assert intensity == 1.0
        intensity = orch.energy_to_intensity(0.5)
        assert 0.4 < intensity < 0.6

    def test_generate_full_beat_effects(self):
        orch = BeatOrchestrator(bpm=120)
        result = orch.generate_full_beat_show(
            layer_name="main_layer",
            duration=5.0,
            style="energetic",
        )
        assert "effects" in result
        assert "keyframes" in result
        assert len(result["keyframes"]) > 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_phase3_beat.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'beat_orchestrator'"

- [ ] **Step 3: 实现 BeatOrchestrator**

```python
# beat_orchestrator.py
"""
节拍编排器 - 音乐驱动的效果和动画编排
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import math


@dataclass
class BeatSyncConfig:
    property_type: str  # scale, opacity, position, rotation, effect
    base_value: float = 100.0
    beat_value: float = 120.0
    attack: float = 0.05  # 攻击时间(秒)
    decay: float = 0.15   # 衰减时间(秒)
    easing: str = "ease_out"
    sync_mode: str = "every_beat"  # every_beat, downbeat_only, offbeat


@dataclass
class MusicalSection:
    type: str  # intro, verse, pre_chorus, chorus, bridge, outro
    start_time: float
    end_time: float
    energy: float  # 0.0 - 1.0
    intensity_multiplier: float = 1.0


MUSICAL_STRUCTURE_TEMPLATES = {
    "pop_song": [
        {"type": "intro", "duration_ratio": 0.1, "energy": 0.3, "intensity": 0.5},
        {"type": "verse", "duration_ratio": 0.25, "energy": 0.5, "intensity": 0.7},
        {"type": "pre_chorus", "duration_ratio": 0.1, "energy": 0.7, "intensity": 0.85},
        {"type": "chorus", "duration_ratio": 0.25, "energy": 1.0, "intensity": 1.0},
        {"type": "verse", "duration_ratio": 0.1, "energy": 0.5, "intensity": 0.7},
        {"type": "chorus", "duration_ratio": 0.15, "energy": 1.0, "intensity": 1.0},
        {"type": "outro", "duration_ratio": 0.05, "energy": 0.2, "intensity": 0.3},
    ],
    "edm_drop": [
        {"type": "intro", "duration_ratio": 0.1, "energy": 0.2, "intensity": 0.3},
        {"type": "build_up", "duration_ratio": 0.2, "energy": 0.6, "intensity": 0.6},
        {"type": "drop", "duration_ratio": 0.3, "energy": 1.0, "intensity": 1.0},
        {"type": "break", "duration_ratio": 0.2, "energy": 0.4, "intensity": 0.5},
        {"type": "drop", "duration_ratio": 0.15, "energy": 1.0, "intensity": 1.1},
        {"type": "outro", "duration_ratio": 0.05, "energy": 0.1, "intensity": 0.2},
    ],
    "short_hook": [
        {"type": "intro", "duration_ratio": 0.1, "energy": 0.4, "intensity": 0.6},
        {"type": "hook", "duration_ratio": 0.6, "energy": 1.0, "intensity": 1.0},
        {"type": "outro", "duration_ratio": 0.3, "energy": 0.3, "intensity": 0.4},
    ],
}


BEAT_EFFECT_STYLES = {
    "energetic": {
        "scale_pulse": True,
        "opacity_flash": True,
        "glow_boost": True,
        "shake_on_beat": False,
        "intensity": 1.0,
    },
    "chill": {
        "scale_pulse": True,
        "opacity_flash": False,
        "glow_boost": True,
        "shake_on_beat": False,
        "intensity": 0.4,
    },
    "heavy": {
        "scale_pulse": True,
        "opacity_flash": True,
        "glow_boost": True,
        "shake_on_beat": True,
        "intensity": 1.2,
    },
    "subtle": {
        "scale_pulse": True,
        "opacity_flash": False,
        "glow_boost": False,
        "shake_on_beat": False,
        "intensity": 0.25,
    },
}


class BeatOrchestrator:
    def __init__(
        self,
        bpm: float = 120.0,
        fps: int = 30,
        beats_per_measure: int = 4,
    ):
        self.bpm = bpm
        self.fps = fps
        self.beats_per_measure = beats_per_measure
        self.beat_interval = 60.0 / bpm
        self.measure_interval = self.beat_interval * beats_per_measure

    def generate_beat_timeline(self, duration: float, offset: float = 0.0) -> List[float]:
        beats = []
        t = offset
        while t < duration:
            beats.append(round(t, 4))
            t += self.beat_interval
        return beats

    def generate_downbeats(self, duration: float, offset: float = 0.0) -> List[float]:
        beats = []
        t = offset
        while t < duration:
            beats.append(round(t, 4))
            t += self.measure_interval
        return beats

    def generate_offbeats(self, duration: float, offset: float = 0.0) -> List[float]:
        all_beats = self.generate_beat_timeline(duration, offset)
        return [b for i, b in enumerate(all_beats) if i % 2 == 1]

    def generate_beat_synced_keyframes(
        self,
        layer_name: str,
        beat_times: List[float],
        config: BeatSyncConfig,
    ) -> List[Dict[str, Any]]:
        keyframes = []
        prop_name = self._property_name(config.property_type)

        for beat in beat_times:
            attack_end = beat + config.attack
            decay_end = beat + config.attack + config.decay

            if config.property_type == "scale":
                base = [config.base_value, config.base_value]
                peak = [config.beat_value, config.beat_value]
            elif config.property_type == "opacity":
                base = config.base_value
                peak = config.beat_value
            else:
                base = config.base_value
                peak = config.beat_value

            keyframes.append({
                "layerName": layer_name,
                "propertyName": prop_name,
                "time": beat,
                "value": base,
                "easeType": "ease_out",
            })
            keyframes.append({
                "layerName": layer_name,
                "propertyName": prop_name,
                "time": attack_end,
                "value": peak,
                "easeType": "ease_in",
            })
            keyframes.append({
                "layerName": layer_name,
                "propertyName": prop_name,
                "time": decay_end,
                "value": base,
                "easeType": "linear",
            })

        return keyframes

    def _property_name(self, prop_type: str) -> str:
        mapping = {
            "scale": "Scale",
            "opacity": "Opacity",
            "position": "Position",
            "rotation": "Rotation",
        }
        return mapping.get(prop_type, "Opacity")

    def generate_beat_effect_triggers(
        self,
        layer_name: str,
        beat_times: List[float],
        effect_type: str = "glow_pulse",
        intensity: float = 1.0,
    ) -> List[Dict[str, Any]]:
        effects = []
        
        if effect_type == "glow_pulse":
            for beat in beat_times:
                effects.append({
                    "layerName": layer_name,
                    "effectName": "ADBE Glo2",
                    "settings": {
                        "Glow Radius": 20 * intensity,
                        "Glow Intensity": 1.5 * intensity,
                        "Glow Threshold": 50,
                    },
                })
        elif effect_type == "sharpen_pulse":
            for beat in beat_times:
                effects.append({
                    "layerName": layer_name,
                    "effectName": "ADBE Unsharp Mask",
                    "settings": {
                        "Amount": 100 * intensity,
                        "Radius": 2.0,
                    },
                })
        
        return effects

    def generate_musical_structure(
        self,
        duration: float,
        template: str = "pop_song",
    ) -> List[MusicalSection]:
        template_data = MUSICAL_STRUCTURE_TEMPLATES.get(template, MUSICAL_STRUCTURE_TEMPLATES["short_hook"])
        sections = []
        current_time = 0.0

        for section_template in template_data:
            section_duration = duration * section_template["duration_ratio"]
            sections.append(MusicalSection(
                type=section_template["type"],
                start_time=current_time,
                end_time=current_time + section_duration,
                energy=section_template["energy"],
                intensity_multiplier=section_template["intensity"],
            ))
            current_time += section_duration

        return sections

    def energy_to_intensity(self, energy: float) -> float:
        return max(0.0, min(1.0, energy))

    def generate_full_beat_show(
        self,
        layer_name: str,
        duration: float,
        style: str = "energetic",
        structure_template: str = "short_hook",
    ) -> Dict[str, Any]:
        style_config = BEAT_EFFECT_STYLES.get(style, BEAT_EFFECT_STYLES["subtle"])
        sections = self.generate_musical_structure(duration, structure_template)
        all_beats = self.generate_beat_timeline(duration)
        
        keyframes = []
        effects = []

        for section in sections:
            section_beats = [b for b in all_beats if section.start_time <= b < section.end_time]
            intensity = style_config["intensity"] * section.intensity_multiplier

            if style_config.get("scale_pulse"):
                config = BeatSyncConfig(
                    property_type="scale",
                    base_value=100,
                    beat_value=100 + 20 * intensity,
                    attack=0.03,
                    decay=0.12,
                )
                keyframes.extend(self.generate_beat_synced_keyframes(layer_name, section_beats, config))

            if style_config.get("opacity_flash"):
                config = BeatSyncConfig(
                    property_type="opacity",
                    base_value=70,
                    beat_value=100,
                    attack=0.02,
                    decay=0.08,
                )
                keyframes.extend(self.generate_beat_synced_keyframes(layer_name, section_beats, config))

            if style_config.get("glow_boost"):
                effects.append({
                    "layerName": layer_name,
                    "effectName": "ADBE Glo2",
                    "settings": {
                        "Glow Radius": 15 * intensity,
                        "Glow Intensity": 1.0 * intensity,
                        "Glow Threshold": 60,
                    },
                })

        return {
            "layerName": layer_name,
            "duration": duration,
            "style": style,
            "effects": effects,
            "keyframes": keyframes,
            "sections": [s.__dict__ for s in sections],
            "beat_count": len(all_beats),
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_phase3_beat.py -v`
Expected: 10 passed

---

## Task 3: 效果组合推荐器 (EffectComposer)

**Files:**
- Create: `effect_composer.py`
- Create: `style_template_library.py`
- Test: `tests/test_phase3_composer.py`

**核心功能：**
1. 风格模板库 - 20+种视频风格的效果组合预设
2. 效果搭配推荐 - 根据意图推荐效果组合
3. 风格混合 - 多种风格融合
4. 参数联动 - 效果间参数自动协调

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_phase3_composer.py
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from effect_composer import EffectComposer, StyleTemplate
from style_template_library import STYLE_TEMPLATES


class TestEffectComposer:
    def test_initialization(self):
        composer = EffectComposer()
        assert len(composer.templates) > 0

    def test_all_templates_loaded(self):
        composer = EffectComposer()
        template_names = composer.list_templates()
        assert len(template_names) >= 15
        assert "cinematic" in template_names
        assert "cyberpunk" in template_names

    def test_get_template(self):
        composer = EffectComposer()
        template = composer.get_template("cinematic")
        assert template is not None
        assert template.name == "cinematic"
        assert len(template.effects) > 0

    def test_get_template_not_found(self):
        composer = EffectComposer()
        template = composer.get_template("nonexistent")
        assert template is None

    def test_compose_effects_cinematic(self):
        composer = EffectComposer()
        result = composer.compose("cinematic", intensity=1.0)
        assert len(result["effects"]) > 0
        for eff in result["effects"]:
            assert "effectName" in eff
            assert "settings" in eff

    def test_compose_with_intensity(self):
        composer = EffectComposer()
        low = composer.compose("cyberpunk", intensity=0.5)
        high = composer.compose("cyberpunk", intensity=1.5)
        low_total = sum(e["settings"].get("Glow Intensity", 0) for e in low["effects"] if "Glow Intensity" in e["settings"])
        high_total = sum(e["settings"].get("Glow Intensity", 0) for e in high["effects"] if "Glow Intensity" in e["settings"])
        assert high_total > low_total

    def test_compose_with_layer(self):
        composer = EffectComposer()
        result = composer.compose("dreamy", layer_name="my_layer")
        for eff in result["effects"]:
            assert eff["layerName"] == "my_layer"

    def test_recommend_by_keyword(self):
        composer = EffectComposer()
        recs = composer.recommend_by_keywords(["发光", "赛博"])
        assert len(recs) > 0
        assert "cyberpunk" in [r["name"] for r in recs[:5]]

    def test_mix_styles(self):
        composer = EffectComposer()
        result = composer.mix_styles(["cinematic", "cyberpunk"], ratios=[0.6, 0.4])
        assert len(result["effects"]) > 0
        assert result["mixed_from"] == ["cinematic", "cyberpunk"]

    def test_list_categories(self):
        composer = EffectComposer()
        cats = composer.list_categories()
        assert len(cats) > 0
        assert "电影感" in cats or "cinematic" in cats
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_phase3_composer.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'effect_composer'"

- [ ] **Step 3: 实现风格模板库**

```python
# style_template_library.py
"""
风格模板库 - 20+种视频风格的效果组合预设
"""
from typing import Dict, List, Any


STYLE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "cinematic": {
        "name": "cinematic",
        "display_name": "电影感",
        "category": "电影感",
        "description": "经典电影调色风格，低饱和、高对比、暗角",
        "keywords": ["电影", "cinematic", "胶片", "质感"],
        "intensity_range": [0.3, 1.5],
        "effects": [
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": -10, "Master Lightness": -3},
                "intensity_param": "Master Saturation",
                "intensity_factor": -15,
            },
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {"Brightness": 0, "Contrast": 15},
                "intensity_param": "Contrast",
                "intensity_factor": 20,
            },
            {
                "effectName": "ADBE Glo2",
                "settings": {"Glow Radius": 15, "Glow Intensity": 0.5, "Glow Threshold": 80},
                "intensity_param": "Glow Intensity",
                "intensity_factor": 0.8,
            },
        ],
    },
    "cyberpunk": {
        "name": "cyberpunk",
        "display_name": "赛博朋克",
        "category": "科幻",
        "description": "霓虹灯光、高饱和、蓝紫配色、发光效果",
        "keywords": ["赛博朋克", "cyberpunk", "霓虹", "未来", "科幻"],
        "intensity_range": [0.5, 2.0],
        "effects": [
            {
                "effectName": "ADBE Glo2",
                "settings": {"Glow Radius": 40, "Glow Intensity": 2.0, "Glow Threshold": 30},
                "intensity_param": "Glow Intensity",
                "intensity_factor": 2.5,
            },
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": 20, "Master Hue": -10},
                "intensity_param": "Master Saturation",
                "intensity_factor": 25,
            },
            {
                "effectName": "ADBE Fractal Noise",
                "settings": {"Fractal Type": "Turbulence", "Noise Type": "Soft Linear",
                            "Contrast": 40, "Brightness": 0, "Scale": 200, "Complexity": 3},
                "intensity_param": "Contrast",
                "intensity_factor": 50,
            },
        ],
    },
    "dreamy": {
        "name": "dreamy",
        "display_name": "梦幻",
        "category": "氛围",
        "description": "柔焦、低对比、高光发光、温暖色调",
        "keywords": ["梦幻", "dreamy", "柔美", "仙气", "浪漫"],
        "intensity_range": [0.3, 1.2],
        "effects": [
            {
                "effectName": "ADBE Gaussian Blur 2",
                "settings": {"Blurriness": 3},
                "intensity_param": "Blurriness",
                "intensity_factor": 5,
            },
            {
                "effectName": "ADBE Glo2",
                "settings": {"Glow Radius": 30, "Glow Intensity": 1.2, "Glow Threshold": 50},
                "intensity_param": "Glow Intensity",
                "intensity_factor": 1.5,
            },
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": 5, "Master Lightness": 5},
                "intensity_param": "Master Lightness",
                "intensity_factor": 10,
            },
        ],
    },
    "horror": {
        "name": "horror",
        "display_name": "恐怖",
        "category": "氛围",
        "description": "低亮度、高对比、偏绿偏红、暗部噪点",
        "keywords": ["恐怖", "horror", "惊悚", "悬疑", "黑暗"],
        "intensity_range": [0.5, 1.8],
        "effects": [
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {"Brightness": -15, "Contrast": 25},
                "intensity_param": "Contrast",
                "intensity_factor": 30,
            },
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": -20, "Master Hue": 15},
                "intensity_param": "Master Saturation",
                "intensity_factor": -25,
            },
            {
                "effectName": "ADBE Fractal Noise",
                "settings": {"Fractal Type": "Turbulence", "Noise Type": "Splatter",
                            "Contrast": 60, "Brightness": -20, "Scale": 100, "Complexity": 5},
                "intensity_param": "Contrast",
                "intensity_factor": 70,
            },
        ],
    },
    "vintage": {
        "name": "vintage",
        "display_name": "复古",
        "category": "风格化",
        "description": "褪色、偏黄、低对比、颗粒感",
        "keywords": ["复古", "vintage", "怀旧", "老电影", "胶片"],
        "intensity_range": [0.3, 1.5],
        "effects": [
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": -30, "Master Hue": 10},
                "intensity_param": "Master Saturation",
                "intensity_factor": -35,
            },
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {"Brightness": 5, "Contrast": -10},
                "intensity_param": "Contrast",
                "intensity_factor": -15,
            },
            {
                "effectName": "ADBE Fractal Noise",
                "settings": {"Fractal Type": "Turbulence", "Noise Type": "Soft Linear",
                            "Contrast": 30, "Brightness": -10, "Scale": 50, "Complexity": 2},
                "intensity_param": "Contrast",
                "intensity_factor": 40,
            },
        ],
    },
    "neon": {
        "name": "neon",
        "display_name": "霓虹",
        "category": "科幻",
        "description": "强烈发光、高饱和、电光蓝紫配色",
        "keywords": ["霓虹", "neon", "发光", "灯光", "电光"],
        "intensity_range": [0.5, 2.5],
        "effects": [
            {
                "effectName": "ADBE Glo2",
                "settings": {"Glow Radius": 50, "Glow Intensity": 3.0, "Glow Threshold": 20},
                "intensity_param": "Glow Intensity",
                "intensity_factor": 3.5,
            },
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": 30, "Master Hue": -20},
                "intensity_param": "Master Saturation",
                "intensity_factor": 35,
            },
        ],
    },
    "minimal": {
        "name": "minimal",
        "display_name": "极简",
        "category": "风格化",
        "description": "干净、低饱和、柔和阴影、高曝光",
        "keywords": ["极简", "minimal", "简约", "干净", "ins风"],
        "intensity_range": [0.2, 1.0],
        "effects": [
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {"Brightness": 10, "Contrast": -5},
                "intensity_param": "Brightness",
                "intensity_factor": 15,
            },
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": -15, "Master Lightness": 5},
                "intensity_param": "Master Saturation",
                "intensity_factor": -20,
            },
        ],
    },
    "drama": {
        "name": "drama",
        "display_name": "戏剧性",
        "category": "电影感",
        "description": "高对比、暗部压暗、高光保留、浓郁色彩",
        "keywords": ["戏剧", "drama", "强烈", "对比", "张力"],
        "intensity_range": [0.5, 2.0],
        "effects": [
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {"Brightness": -5, "Contrast": 30},
                "intensity_param": "Contrast",
                "intensity_factor": 40,
            },
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": 10, "Master Lightness": -5},
                "intensity_param": "Master Saturation",
                "intensity_factor": 15,
            },
            {
                "effectName": "ADBE Glo2",
                "settings": {"Glow Radius": 10, "Glow Intensity": 0.3, "Glow Threshold": 90},
                "intensity_param": "Glow Intensity",
                "intensity_factor": 0.5,
            },
        ],
    },
    "warm": {
        "name": "warm",
        "display_name": "暖色调",
        "category": "色彩",
        "description": "偏黄偏橙、温暖、日落感",
        "keywords": ["暖", "warm", "日落", "金色", "阳光"],
        "intensity_range": [0.3, 1.5],
        "effects": [
            {
                "effectName": "ADBE Color Balance",
                "settings": {"Midtone Red Balance": 10, "Midtone Green Balance": 5, "Midtone Blue Balance": -10},
                "intensity_param": "Midtone Red Balance",
                "intensity_factor": 15,
            },
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": 5, "Master Hue": 5},
                "intensity_param": "Master Saturation",
                "intensity_factor": 10,
            },
        ],
    },
    "cool": {
        "name": "cool",
        "display_name": "冷色调",
        "category": "色彩",
        "description": "偏蓝偏青、冷峻、清冷感",
        "keywords": ["冷", "cool", "清冷", "蓝色", "冰"],
        "intensity_range": [0.3, 1.5],
        "effects": [
            {
                "effectName": "ADBE Color Balance",
                "settings": {"Midtone Red Balance": -10, "Midtone Green Balance": 0, "Midtone Blue Balance": 15},
                "intensity_param": "Midtone Blue Balance",
                "intensity_factor": 20,
            },
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": 0, "Master Hue": -10},
                "intensity_param": "Master Hue",
                "intensity_factor": -15,
            },
        ],
    },
    "grunge": {
        "name": "grunge",
        "display_name": "脏污/油渍",
        "category": "风格化",
        "description": "颗粒感、暗部细节丢失、高对比、粗糙",
        "keywords": ["grunge", "脏", "粗糙", "颗粒", "朋克"],
        "intensity_range": [0.5, 2.0],
        "effects": [
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {"Brightness": -10, "Contrast": 40},
                "intensity_param": "Contrast",
                "intensity_factor": 50,
            },
            {
                "effectName": "ADBE Fractal Noise",
                "settings": {"Fractal Type": "Turbulence", "Noise Type": "Splatter",
                            "Contrast": 80, "Brightness": -30, "Scale": 80, "Complexity": 6},
                "intensity_param": "Contrast",
                "intensity_factor": 90,
            },
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": -25, "Master Lightness": -5},
                "intensity_param": "Master Saturation",
                "intensity_factor": -30,
            },
        ],
    },
    "soft_glow": {
        "name": "soft_glow",
        "display_name": "柔光",
        "category": "氛围",
        "description": "柔和发光、低对比、朦胧美",
        "keywords": ["柔光", "soft", "朦胧", "柔焦", "柔和"],
        "intensity_range": [0.2, 1.2],
        "effects": [
            {
                "effectName": "ADBE Gaussian Blur 2",
                "settings": {"Blurriness": 2},
                "intensity_param": "Blurriness",
                "intensity_factor": 4,
            },
            {
                "effectName": "ADBE Glo2",
                "settings": {"Glow Radius": 25, "Glow Intensity": 0.8, "Glow Threshold": 60},
                "intensity_param": "Glow Intensity",
                "intensity_factor": 1.2,
            },
        ],
    },
    "high_energy": {
        "name": "high_energy",
        "display_name": "高能",
        "category": "动感",
        "description": "高饱和、强对比、发光、运动感",
        "keywords": ["高能", "energy", "动感", "活力", "热血"],
        "intensity_range": [0.5, 2.0],
        "effects": [
            {
                "effectName": "ADBE Glo2",
                "settings": {"Glow Radius": 35, "Glow Intensity": 2.5, "Glow Threshold": 25},
                "intensity_param": "Glow Intensity",
                "intensity_factor": 3.0,
            },
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": 25, "Master Lightness": 0},
                "intensity_param": "Master Saturation",
                "intensity_factor": 30,
            },
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {"Brightness": 5, "Contrast": 20},
                "intensity_param": "Contrast",
                "intensity_factor": 25,
            },
        ],
    },
    "noir": {
        "name": "noir",
        "display_name": "黑色电影",
        "category": "电影感",
        "description": "黑白、高对比、暗角、戏剧光影",
        "keywords": ["黑白", "noir", "黑色电影", "黑色", "光影"],
        "intensity_range": [0.5, 1.8],
        "effects": [
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": -100, "Master Lightness": 0},
                "intensity_param": "Master Lightness",
                "intensity_factor": -10,
            },
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {"Brightness": -5, "Contrast": 35},
                "intensity_param": "Contrast",
                "intensity_factor": 45,
            },
        ],
    },
    "pastel": {
        "name": "pastel",
        "display_name": "马卡龙",
        "category": "色彩",
        "description": "低饱和、高明度、柔和粉彩色",
        "keywords": ["马卡龙", "pastel", "粉嫩", "糖果", "少女"],
        "intensity_range": [0.3, 1.2],
        "effects": [
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {"Master Saturation": -10, "Master Lightness": 15},
                "intensity_param": "Master Lightness",
                "intensity_factor": 20,
            },
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {"Brightness": 10, "Contrast": -10},
                "intensity_param": "Brightness",
                "intensity_factor": 15,
            },
            {
                "effectName": "ADBE Glo2",
                "settings": {"Glow Radius": 15, "Glow Intensity": 0.5, "Glow Threshold": 70},
                "intensity_param": "Glow Intensity",
                "intensity_factor": 0.8,
            },
        ],
    },
}
```

- [ ] **Step 4: 实现 EffectComposer**

```python
# effect_composer.py
"""
效果组合推荐器 - 效果搭配推荐、风格模板库、风格混合
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from style_template_library import STYLE_TEMPLATES


@dataclass
class StyleTemplate:
    name: str
    display_name: str
    category: str
    description: str
    keywords: List[str]
    intensity_range: List[float]
    effects: List[Dict[str, Any]]


class EffectComposer:
    def __init__(self):
        self.templates: Dict[str, StyleTemplate] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        for name, data in STYLE_TEMPLATES.items():
            self.templates[name] = StyleTemplate(
                name=data["name"],
                display_name=data["display_name"],
                category=data["category"],
                description=data["description"],
                keywords=data["keywords"],
                intensity_range=data["intensity_range"],
                effects=data["effects"],
            )

    def list_templates(self) -> List[str]:
        return list(self.templates.keys())

    def list_categories(self) -> List[str]:
        return list(set(t.category for t in self.templates.values()))

    def get_template(self, name: str) -> Optional[StyleTemplate]:
        return self.templates.get(name)

    def compose(
        self,
        style_name: str,
        intensity: float = 1.0,
        layer_name: str = "layer_001",
    ) -> Dict[str, Any]:
        template = self.get_template(style_name)
        if not template:
            return {"effects": [], "style": style_name, "intensity": intensity, "error": "Template not found"}

        intensity = max(template.intensity_range[0], min(template.intensity_range[1], intensity))
        effects = []

        for fx_template in template.effects:
            settings = dict(fx_template["settings"])
            if "intensity_param" in fx_template:
                param = fx_template["intensity_param"]
                base_value = settings[param]
                factor = fx_template["intensity_factor"]
                settings[param] = base_value + (factor - base_value) * (intensity - 0.5) * 2
            
            effects.append({
                "layerName": layer_name,
                "effectName": fx_template["effectName"],
                "settings": settings,
            })

        return {
            "style": style_name,
            "display_name": template.display_name,
            "intensity": intensity,
            "effects": effects,
            "effect_count": len(effects),
        }

    def recommend_by_keywords(
        self,
        keywords: List[str],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        scores = []
        for name, template in self.templates.items():
            score = 0.0
            all_keywords_lower = [k.lower() for k in template.keywords]
            for kw in keywords:
                kw_lower = kw.lower()
                for tk in all_keywords_lower:
                    if kw_lower in tk or tk in kw_lower:
                        score += 1.0
                        break
            if score > 0:
                scores.append({
                    "name": name,
                    "display_name": template.display_name,
                    "category": template.category,
                    "score": score,
                    "description": template.description,
                })
        
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:limit]

    def mix_styles(
        self,
        style_names: List[str],
        ratios: List[float] = None,
        layer_name: str = "layer_001",
    ) -> Dict[str, Any]:
        if ratios is None:
            ratios = [1.0 / len(style_names)] * len(style_names)
        
        total_ratio = sum(ratios)
        normalized_ratios = [r / total_ratio for r in ratios]

        all_effects = []
        effect_by_name = {}

        for style_name, ratio in zip(style_names, normalized_ratios):
            result = self.compose(style_name, intensity=ratio, layer_name=layer_name)
            for eff in result["effects"]:
                match_name = eff["effectName"]
                if match_name not in effect_by_name:
                    effect_by_name[match_name] = eff
                else:
                    for k, v in eff["settings"].items():
                        if k in effect_by_name[match_name]["settings"]:
                            existing = effect_by_name[match_name]["settings"][k]
                            if isinstance(existing, (int, float)) and isinstance(v, (int, float)):
                                effect_by_name[match_name]["settings"][k] = existing + v
        
        all_effects = list(effect_by_name.values())

        return {
            "mixed_from": style_names,
            "ratios": normalized_ratios,
            "effects": all_effects,
            "effect_count": len(all_effects),
        }

    def get_style_effect_count(self, style_name: str) -> int:
        template = self.get_template(style_name)
        return len(template.effects) if template else 0
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_phase3_composer.py -v`
Expected: 10 passed

---

## Task 4: 反馈闭环管理器 (FeedbackLoopManager)

**Files:**
- Create: `feedback_loop_manager.py`
- Test: `tests/test_phase3_feedback.py`

**核心功能：**
1. 结果验证 - 检查AE执行结果是否符合预期
2. 学习循环 - 从成功/失败案例中学习，更新参数模板
3. 失败恢复 - 自动重试、降级策略、参数调整
4. 置信度校准 - 根据历史表现调整置信度

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_phase3_feedback.py
import os
import sys
import pytest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feedback_loop_manager import FeedbackLoopManager, ExecutionRecord, VerificationResult


class TestFeedbackLoopManager:
    def test_initialization(self):
        fm = FeedbackLoopManager()
        assert fm.records == []
        assert fm.confidence_threshold == 0.6

    def test_record_successful_execution(self):
        fm = FeedbackLoopManager()
        record = fm.record_execution(
            user_input="给图层加一个强发光效果",
            intent_type="add_effect",
            success=True,
            expected={"effectName": "ADBE Glo2", "settings": {"Glow Intensity": 2.0}},
            actual={"effectName": "ADBE Glo2", "settings": {"Glow Intensity": 2.0}},
        )
        assert record.success is True
        assert record.intent_type == "add_effect"
        assert len(fm.records) == 1

    def test_record_failed_execution(self):
        fm = FeedbackLoopManager()
        record = fm.record_execution(
            user_input="加一个不存在的效果",
            intent_type="add_effect",
            success=False,
            error_message="Effect not found",
            error_code="EFFECT_NOT_FOUND",
            expected={"effectName": "NonExistent"},
            actual=None,
        )
        assert record.success is False
        assert record.error_code == "EFFECT_NOT_FOUND"

    def test_verify_parameters_match(self):
        fm = FeedbackLoopManager()
        expected = {"effectName": "ADBE Glo2", "settings": {"Glow Radius": 20, "Glow Intensity": 1.5}}
        actual = {"effectName": "ADBE Glo2", "settings": {"Glow Radius": 20, "Glow Intensity": 1.5}}
        result = fm.verify_parameters(expected, actual)
        assert result.passed is True
        assert len(result.mismatches) == 0

    def test_verify_parameters_mismatch(self):
        fm = FeedbackLoopManager()
        expected = {"effectName": "ADBE Glo2", "settings": {"Glow Radius": 20, "Glow Intensity": 2.0}}
        actual = {"effectName": "ADBE Glo2", "settings": {"Glow Radius": 20, "Glow Intensity": 1.5}}
        result = fm.verify_parameters(expected, actual)
        assert result.passed is False
        assert len(result.mismatches) == 1
        assert result.mismatches[0]["param"] == "Glow Intensity"

    def test_verify_parameters_with_tolerance(self):
        fm = FeedbackLoopManager()
        expected = {"settings": {"Blurriness": 10}}
        actual = {"settings": {"Blurriness": 10.5}}
        result = fm.verify_parameters(expected, actual, tolerance=0.1)
        assert result.passed is True

    def test_get_success_rate(self):
        fm = FeedbackLoopManager()
        for i in range(8):
            fm.record_execution(f"test_{i}", "test", True, {}, {})
        for i in range(2):
            fm.record_execution(f"fail_{i}", "test", False, {}, None, error_code="TEST_ERROR")
        rate = fm.get_success_rate()
        assert abs(rate - 0.8) < 0.01

    def test_get_success_rate_by_intent(self):
        fm = FeedbackLoopManager()
        for i in range(5):
            fm.record_execution(f"glow_{i}", "add_glow", True, {}, {})
        for i in range(2):
            fm.record_execution(f"blur_{i}", "add_blur", True, {}, {})
        fm.record_execution("blur_fail", "add_blur", False, {}, None, error_code="ERR")
        assert fm.get_success_rate("add_glow") == 1.0
        assert abs(fm.get_success_rate("add_blur") - 0.667) < 0.01

    def test_suggest_recovery(self):
        fm = FeedbackLoopManager()
        suggestion = fm.suggest_recovery("EFFECT_NOT_FOUND", {"effectName": "BadEffect"})
        assert suggestion["action"] is not None
        assert "message" in suggestion

    def test_calculate_confidence_adjustment(self):
        fm = FeedbackLoopManager()
        adj = fm.calculate_confidence_adjustment(
            intent_type="add_effect",
            success=True,
            base_confidence=0.8,
        )
        assert adj > 0  # 成功应该提升置信度

        adj_fail = fm.calculate_confidence_adjustment(
            intent_type="add_effect",
            success=False,
            base_confidence=0.8,
        )
        assert adj_fail < 0  # 失败应该降低置信度

    def test_get_learning_summary(self):
        fm = FeedbackLoopManager()
        for i in range(10):
            fm.record_execution(f"t_{i}", "type_a", True, {}, {})
        for i in range(5):
            fm.record_execution(f"f_{i}", "type_b", False, {}, None, error_code="ERR")
        summary = fm.get_learning_summary()
        assert summary["total_executions"] == 15
        assert summary["success_rate"] > 0.5
        assert "by_intent" in summary
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_phase3_feedback.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 实现 FeedbackLoopManager**

```python
# feedback_loop_manager.py
"""
反馈闭环管理器 - 整合结果验证、学习循环、失败恢复、置信度校准
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import uuid
import math


@dataclass
class VerificationResult:
    passed: bool
    mismatches: List[Dict[str, Any]] = field(default_factory=list)
    match_score: float = 0.0
    details: str = ""


@dataclass
class ExecutionRecord:
    id: str
    user_input: str
    intent_type: str
    success: bool
    expected: Dict[str, Any]
    actual: Optional[Dict[str, Any]]
    error_message: str = ""
    error_code: str = ""
    timestamp: str = ""
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    user_adjusted: bool = False
    final_params: Optional[Dict] = None


ERROR_RECOVERY_STRATEGIES = {
    "EFFECT_NOT_FOUND": {
        "actions": [
            {"action": "retry_with_alternative", "description": "尝试使用替代效果"},
            {"action": "retry_with_adjusted_params", "description": "调整参数后重试"},
            {"action": "skip_effect", "description": "跳过该效果继续执行"},
        ],
        "default": "retry_with_alternative",
    },
    "PROPERTY_NOT_FOUND": {
        "actions": [
            {"action": "retry_with_adjusted_params", "description": "调整参数名后重试"},
            {"action": "skip_property", "description": "跳过该属性设置"},
        ],
        "default": "retry_with_adjusted_params",
    },
    "SCRIPT_ERROR": {
        "actions": [
            {"action": "retry_with_simplified_script", "description": "使用简化脚本重试"},
            {"action": "report_error", "description": "报告错误给用户"},
        ],
        "default": "retry_with_simplified_script",
    },
    "TIMEOUT": {
        "actions": [
            {"action": "retry_with_longer_timeout", "description": "延长超时重试"},
            {"action": "retry", "description": "直接重试"},
        ],
        "default": "retry_with_longer_timeout",
    },
    "AE_NOT_RESPONDING": {
        "actions": [
            {"action": "wait_and_retry", "description": "等待后重试"},
            {"action": "report_error", "description": "报告错误"},
        ],
        "default": "wait_and_retry",
    },
}


class FeedbackLoopManager:
    def __init__(self, confidence_threshold: float = 0.6):
        self.records: List[ExecutionRecord] = []
        self.confidence_threshold = confidence_threshold
        self._confidence_adjustments: Dict[str, float] = {}
        self._success_counts: Dict[str, List[bool]] = {}

    def record_execution(
        self,
        user_input: str,
        intent_type: str,
        success: bool,
        expected: Dict[str, Any],
        actual: Optional[Dict[str, Any]],
        error_message: str = "",
        error_code: str = "",
        base_confidence: float = 0.5,
    ) -> ExecutionRecord:
        record_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        confidence_adj = self.calculate_confidence_adjustment(
            intent_type, success, base_confidence
        )
        confidence_after = max(0.0, min(1.0, base_confidence + confidence_adj))

        record = ExecutionRecord(
            id=record_id,
            user_input=user_input,
            intent_type=intent_type,
            success=success,
            expected=expected,
            actual=actual,
            error_message=error_message,
            error_code=error_code,
            timestamp=timestamp,
            confidence_before=base_confidence,
            confidence_after=confidence_after,
        )

        self.records.append(record)

        if intent_type not in self._success_counts:
            self._success_counts[intent_type] = []
        self._success_counts[intent_type].append(success)

        return record

    def verify_parameters(
        self,
        expected: Dict[str, Any],
        actual: Optional[Dict[str, Any]],
        tolerance: float = 0.01,
    ) -> VerificationResult:
        if actual is None:
            return VerificationResult(
                passed=False,
                mismatches=[{"type": "missing", "param": "all", "expected": expected, "actual": None}],
                match_score=0.0,
                details="No actual result provided",
            )

        mismatches = []
        total_params = 0
        matched_params = 0

        exp_settings = expected.get("settings", {})
        act_settings = actual.get("settings", {})

        for param, exp_val in exp_settings.items():
            total_params += 1
            if param not in act_settings:
                mismatches.append({
                    "type": "missing_param",
                    "param": param,
                    "expected": exp_val,
                    "actual": None,
                })
                continue

            act_val = act_settings[param]

            if isinstance(exp_val, (int, float)) and isinstance(act_val, (int, float)):
                diff = abs(exp_val - act_val)
                base = abs(exp_val) if exp_val != 0 else 1.0
                if diff / base > tolerance:
                    mismatches.append({
                        "type": "value_mismatch",
                        "param": param,
                        "expected": exp_val,
                        "actual": act_val,
                        "diff": diff,
                        "diff_percent": diff / base * 100,
                    })
                else:
                    matched_params += 1
            elif exp_val == act_val:
                matched_params += 1
            else:
                mismatches.append({
                    "type": "type_mismatch",
                    "param": param,
                    "expected": exp_val,
                    "actual": act_val,
                })

        match_score = matched_params / total_params if total_params > 0 else 1.0

        return VerificationResult(
            passed=len(mismatches) == 0,
            mismatches=mismatches,
            match_score=match_score,
            details=f"Matched {matched_params}/{total_params} parameters",
        )

    def get_success_rate(self, intent_type: str = None) -> float:
        if intent_type:
            counts = self._success_counts.get(intent_type, [])
            if not counts:
                return 0.0
            return sum(counts) / len(counts)
        else:
            if not self.records:
                return 0.0
            successes = sum(1 for r in self.records if r.success)
            return successes / len(self.records)

    def suggest_recovery(
        self,
        error_code: str,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        strategy = ERROR_RECOVERY_STRATEGIES.get(error_code)
        if not strategy:
            return {
                "action": "report_error",
                "message": f"Unknown error code: {error_code}",
                "alternatives": [],
            }

        return {
            "action": strategy["default"],
            "error_code": error_code,
            "message": f"Error '{error_code}' - recommended action: {strategy['default']}",
            "alternatives": strategy["actions"],
            "context": context or {},
        }

    def calculate_confidence_adjustment(
        self,
        intent_type: str,
        success: bool,
        base_confidence: float,
    ) -> float:
        history_rate = self.get_success_rate(intent_type)
        history_count = len(self._success_counts.get(intent_type, []))

        if success:
            base_adj = 0.05
            if history_count > 0:
                base_adj = max(0.01, 0.05 * (1 - history_rate))
            return min(0.1, base_adj)
        else:
            base_adj = -0.08
            if history_count > 0:
                base_adj = min(-0.02, -0.08 * history_rate)
            return max(-0.15, base_adj)

    def get_learning_summary(self) -> Dict[str, Any]:
        if not self.records:
            return {
                "total_executions": 0,
                "success_rate": 0.0,
                "by_intent": {},
            }

        by_intent = {}
        for intent in self._success_counts:
            by_intent[intent] = {
                "count": len(self._success_counts[intent]),
                "success_rate": self.get_success_rate(intent),
            }

        return {
            "total_executions": len(self.records),
            "successful": sum(1 for r in self.records if r.success),
            "failed": sum(1 for r in self.records if not r.success),
            "success_rate": self.get_success_rate(),
            "by_intent": by_intent,
            "unique_intents": len(self._success_counts),
        }

    def get_recent_records(self, limit: int = 10) -> List[ExecutionRecord]:
        return self.records[-limit:]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_phase3_feedback.py -v`
Expected: 10 passed

---

## Task 5: Pipeline集成 - 编排层和反馈层

**Files:**
- Modify: `ae_agent_pipeline.py`
- Test: `tests/test_phase3_integration.py`

**核心改动：**
1. `_init_phase3_modules()` - 加载场景编排器、节拍编排器、效果组合器、反馈管理器
2. `orchestrate_scenes()` - 场景编排方法
3. `orchestrate_beat_sync()` - 节拍编排方法
4. `compose_style_effects()` - 风格效果组合方法
5. `run_with_feedback()` - 带反馈闭环的执行

- [ ] **Step 1: 编写失败测试**

```python
# tests/test_phase3_integration.py
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_agent_pipeline import AEAgentPipeline, PlanningResult


class TestPhase3Integration:
    def test_pipeline_phase3_modules_loaded(self):
        pipeline = AEAgentPipeline()
        assert pipeline.scene_orchestrator is not None
        assert pipeline.beat_orchestrator is not None
        assert pipeline.effect_composer is not None
        assert pipeline.feedback_manager is not None

    def test_compose_style_effects(self):
        pipeline = AEAgentPipeline()
        result = pipeline.compose_style_effects(
            style_name="cinematic",
            layer_name="test_layer",
            intensity=1.0,
        )
        assert result["style"] == "cinematic"
        assert len(result["effects"]) > 0
        for eff in result["effects"]:
            assert eff["layerName"] == "test_layer"

    def test_orchestrate_beat_show(self):
        pipeline = AEAgentPipeline()
        result = pipeline.orchestrate_beat_show(
            layer_name="beat_layer",
            bpm=120,
            duration=3.0,
            style="energetic",
        )
        assert "keyframes" in result
        assert len(result["keyframes"]) > 0
        assert result["style"] == "energetic"

    def test_orchestrate_multi_scene(self):
        pipeline = AEAgentPipeline()
        scenes = [
            {"name": "开场", "duration": 2.0},
            {"name": "主体", "duration": 3.0},
            {"name": "结尾", "duration": 1.0},
        ]
        result = pipeline.orchestrate_scenes(
            scenes=scenes,
            transition_type="crossfade",
            transition_duration=0.3,
        )
        assert result["total_duration"] > 0
        assert result["scene_count"] == 3

    def test_run_with_feedback_success(self):
        pipeline = AEAgentPipeline()
        result = pipeline.run_with_feedback(
            user_input="给图层加电影感效果",
            intent_type="add_style",
            execute_fn=lambda: {"success": True, "result": "ok"},
            expected={"style": "cinematic"},
        )
        assert result["record"] is not None
        assert "verification" in result

    def test_recommend_styles(self):
        pipeline = AEAgentPipeline()
        recs = pipeline.recommend_styles(["发光", "赛博"])
        assert len(recs) > 0

    def test_get_feedback_summary(self):
        pipeline = AEAgentPipeline()
        pipeline.feedback_manager.record_execution(
            "test", "test_intent", True, {}, {}, base_confidence=0.7
        )
        summary = pipeline.get_feedback_summary()
        assert summary["total_executions"] >= 1
        assert "success_rate" in summary

    def test_full_pipeline_phase3(self):
        pipeline = AEAgentPipeline()
        perception_data = {"audio": {"bpm": 120, "duration": 5.0}}
        understanding = {"intent": "add_style", "style": "cinematic", "keywords": ["电影感"]}
        
        result = pipeline.orchestrate_full(
            perception=perception_data,
            understanding=understanding,
            layer_name="main_layer",
        )
        assert "effects" in result
        assert "keyframes" in result
        assert len(result["effects"]) > 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_phase3_integration.py -v`
Expected: FAIL

- [ ] **Step 3: 修改 ae_agent_pipeline.py 添加 Phase 3 集成**

在 `__init__` 中添加：
```python
from scene_orchestrator import SceneOrchestrator
from beat_orchestrator import BeatOrchestrator
from effect_composer import EffectComposer
from feedback_loop_manager import FeedbackLoopManager

# 在 __init__ 末尾添加
self._init_phase3_modules()
```

新增方法：
```python
    def _init_phase3_modules(self):
        self.scene_orchestrator = SceneOrchestrator()
        self.beat_orchestrator = BeatOrchestrator()
        self.effect_composer = EffectComposer()
        self.feedback_manager = FeedbackLoopManager()

    def compose_style_effects(self, style_name: str, layer_name: str, intensity: float = 1.0) -> Dict:
        return self.effect_composer.compose(style_name, intensity, layer_name)

    def recommend_styles(self, keywords: List[str], limit: int = 5) -> List[Dict]:
        return self.effect_composer.recommend_by_keywords(keywords, limit)

    def orchestrate_beat_show(self, layer_name: str, bpm: float, duration: float, style: str = "energetic") -> Dict:
        self.beat_orchestrator = BeatOrchestrator(bpm=bpm)
        return self.beat_orchestrator.generate_full_beat_show(layer_name, duration, style)

    def orchestrate_scenes(self, scenes: List[Dict], transition_type: str = "crossfade", transition_duration: float = 0.5) -> Dict:
        from scene_orchestrator import Scene
        orch = SceneOrchestrator()
        for s in scenes:
            orch.add_scene(Scene(
                name=s.get("name", f"scene_{len(orch.scenes)}"),
                duration=s.get("duration", 3.0),
            ))
        orch.generate_transitions(transition_type, transition_duration)
        return {
            "scene_count": len(orch.scenes),
            "total_duration": orch.total_duration,
            "timeline": orch.generate_timeline(),
            "transitions": [t.__dict__ for t in orch.transitions],
        }

    def run_with_feedback(self, user_input: str, intent_type: str, execute_fn, expected: Dict, base_confidence: float = 0.7) -> Dict:
        try:
            actual = execute_fn()
            success = actual.get("success", False)
            actual_result = actual.get("result", actual) if success else None
            error_msg = "" if success else actual.get("error", "Unknown error")
            error_code = "" if success else actual.get("error_code", "EXECUTION_ERROR")
        except Exception as e:
            success = False
            actual_result = None
            error_msg = str(e)
            error_code = "EXCEPTION"

        verification = self.feedback_manager.verify_parameters(expected, actual_result if success else None)
        record = self.feedback_manager.record_execution(
            user_input=user_input,
            intent_type=intent_type,
            success=success,
            expected=expected,
            actual=actual_result,
            error_message=error_msg,
            error_code=error_code,
            base_confidence=base_confidence,
        )

        suggestion = None
        if not success:
            suggestion = self.feedback_manager.suggest_recovery(error_code)

        return {
            "success": success,
            "record": record,
            "verification": verification,
            "suggestion": suggestion,
        }

    def get_feedback_summary(self) -> Dict:
        return self.feedback_manager.get_learning_summary()

    def orchestrate_full(self, perception: Dict, understanding: Dict, layer_name: str = "main_layer") -> Dict:
        style = understanding.get("style", "cinematic")
        bpm = perception.get("audio", {}).get("bpm", 120)
        duration = perception.get("audio", {}).get("duration", 5.0)

        style_result = self.effect_composer.compose(style, layer_name=layer_name)
        
        self.beat_orchestrator = BeatOrchestrator(bpm=bpm)
        beat_result = self.beat_orchestrator.generate_full_beat_show(layer_name, duration, "subtle")

        all_effects = list(style_result["effects"])
        all_keyframes = list(beat_result["keyframes"])

        return {
            "style": style,
            "bpm": bpm,
            "duration": duration,
            "effects": all_effects,
            "keyframes": all_keyframes,
            "effect_count": len(all_effects),
            "keyframe_count": len(all_keyframes),
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_phase3_integration.py -v`
Expected: 8 passed

---

## Task 6: AE实机验证脚本

**Files:**
- Create: `tests/test_phase3_real_ae.py`

**验证步骤：**
1. 风格效果组合（电影感风格，3个效果）
2. 多场景+转场（3场景 + crossfade转场）
3. 节拍同步动画（BPM=120, 4拍缩放动画）
4. 完整编排（场景+风格+节拍）
5. 反馈闭环模拟（执行→验证→记录）

- [ ] **Step 1: 创建实机验证脚本**

```python
# tests/test_phase3_real_ae.py
"""
Phase 3 AE实机验证脚本
验证：风格组合、场景编排、节拍同步、反馈闭环
"""
import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_agent_pipeline import AEAgentPipeline, PlanningResult
from ae_command_generator import AECommandGenerator


def step1_style_composition():
    """Step 1: 风格效果组合验证"""
    print("\n" + "="*60)
    print("Step 1: 风格效果组合验证 (电影感风格)")
    print("="*60)
    
    pipeline = AEAgentPipeline()
    result = pipeline.compose_style_effects(
        style_name="cinematic",
        layer_name="StyleTestLayer",
        intensity=1.0,
    )
    
    print(f"  风格: {result.get('display_name', result.get('style'))}")
    print(f"  效果数量: {result.get('effect_count', 0)}")
    for eff in result["effects"]:
        print(f"    - {eff['effectName']}")
        for k, v in eff["settings"].items():
            print(f"        {k}: {v}")
    
    # 生成commands
    cmd_gen = AECommandGenerator()
    commands = []
    commands.extend(cmd_gen.generate_create_comp(
        name="Phase3_StyleTest",
        width=1920, height=1080, duration=3.0, frame_rate=30,
    ))
    for eff in result["effects"]:
        commands.extend(cmd_gen.generate_apply_effect(
            layer_name="StyleTestLayer",
            effect_match_name=eff["effectName"],
            settings=eff["settings"],
            comp_name="Phase3_StyleTest",
        ))
    
    print(f"  [OK] 生成 {len(commands)} 条命令")
    return True


def step2_scene_orchestration():
    """Step 2: 场景编排 + 转场验证"""
    print("\n" + "="*60)
    print("Step 2: 场景编排 + 转场验证")
    print("="*60)
    
    pipeline = AEAgentPipeline()
    scenes = [
        {"name": "Scene1", "duration": 2.0},
        {"name": "Scene2", "duration": 2.0},
        {"name": "Scene3", "duration": 1.0},
    ]
    result = pipeline.orchestrate_scenes(
        scenes=scenes,
        transition_type="crossfade",
        transition_duration=0.3,
    )
    
    print(f"  场景数: {result['scene_count']}")
    print(f"  总时长: {result['total_duration']:.2f}s")
    for tl in result["timeline"]:
        print(f"    {tl['name']}: {tl['start']:.2f}s - {tl['end']:.2f}s")
    for t in result["transitions"]:
        print(f"    转场 {t['from_scene']}→{t['to_scene']}: {t['type']} @{t['start_time']:.2f}s")
    
    print(f"  [OK] 场景编排完成")
    return True


def step3_beat_sync():
    """Step 3: 节拍同步动画验证"""
    print("\n" + "="*60)
    print("Step 3: 节拍同步动画验证 (BPM=120)")
    print("="*60)
    
    pipeline = AEAgentPipeline()
    result = pipeline.orchestrate_beat_show(
        layer_name="BeatLayer",
        bpm=120,
        duration=3.0,
        style="energetic",
    )
    
    print(f"  风格: {result['style']}")
    print(f"  节拍数: {result['beat_count']}")
    print(f"  关键帧数: {len(result['keyframes'])}")
    print(f"  效果数: {len(result['effects'])}")
    
    # 显示前6个关键帧
    for i, kf in enumerate(result["keyframes"][:6]):
        print(f"    KF{i}: t={kf['time']:.2f}s {kf['propertyName']}={kf['value']}")
    
    print(f"  [OK] 节拍编排完成")
    return True


def step4_full_orchestration():
    """Step 4: 完整编排（场景+风格+节拍）"""
    print("\n" + "="*60)
    print("Step 4: 完整编排验证")
    print("="*60)
    
    pipeline = AEAgentPipeline()
    perception = {"audio": {"bpm": 120, "duration": 5.0}}
    understanding = {"intent": "add_style", "style": "cyberpunk", "keywords": ["赛博朋克"]}
    
    result = pipeline.orchestrate_full(
        perception=perception,
        understanding=understanding,
        layer_name="MainLayer",
    )
    
    print(f"  风格: {result['style']}")
    print(f"  BPM: {result['bpm']}")
    print(f"  效果数: {result['effect_count']}")
    print(f"  关键帧数: {result['keyframe_count']}")
    
    # 编译为JSX
    planning = PlanningResult(
        composition={"name": "Phase3_FullTest", "width": 1920, "height": 1080, "duration": 5.0, "frameRate": 30},
        layers=[{"name": "MainLayer", "type": "solid", "duration": 5.0, "color": [0.1, 0.2, 0.5]}],
        effects=result["effects"],
        keyframes=result["keyframes"],
    )
    
    compile_result = pipeline.compile_planning_to_jsx(planning)
    print(f"  JSX编译: {'成功' if compile_result['success'] else '失败'}")
    print(f"  方法: {compile_result['method']}")
    print(f"  JSX长度: {len(compile_result.get('jsx_code', ''))}")
    
    # 保存JSX
    if compile_result.get("success"):
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "phase3_e2e_compiled.jsx"
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(compile_result["jsx_code"])
        print(f"  JSX已保存至: {output_path}")
    
    print(f"  [OK] 完整编排完成")
    return True


def step5_feedback_loop():
    """Step 5: 反馈闭环模拟"""
    print("\n" + "="*60)
    print("Step 5: 反馈闭环模拟")
    print("="*60)
    
    pipeline = AEAgentPipeline()
    
    # 模拟成功执行
    def mock_success():
        return {"success": True, "result": {"settings": {"Glow Radius": 20, "Glow Intensity": 1.5}}}
    
    result = pipeline.run_with_feedback(
        user_input="给图层加强发光",
        intent_type="add_style",
        execute_fn=mock_success,
        expected={"style": "cinematic", "settings": {"Glow Radius": 20, "Glow Intensity": 1.5}},
    )
    
    print(f"  执行成功: {result['success']}")
    print(f"  验证通过: {result['verification'].passed}")
    print(f"  匹配分数: {result['verification'].match_score:.2f}")
    
    # 模拟失败执行
    def mock_failure():
        return {"success": False, "error": "Effect not found", "error_code": "EFFECT_NOT_FOUND"}
    
    result2 = pipeline.run_with_feedback(
        user_input="加一个不存在的效果",
        intent_type="add_effect",
        execute_fn=mock_failure,
        expected={"effectName": "NonExistent"},
    )
    
    print(f"  失败执行: success={result2['success']}")
    print(f"  恢复建议: {result2['suggestion']['action'] if result2['suggestion'] else 'None'}")
    
    # 汇总
    summary = pipeline.get_feedback_summary()
    print(f"  总执行数: {summary['total_executions']}")
    print(f"  成功率: {summary['success_rate']:.1%}")
    
    print(f"  [OK] 反馈闭环完成")
    return True


def run_all():
    print("\n" + "="*60)
    print("Phase 3 AE实机验证")
    print("="*60)
    
    steps = [
        ("Step 1: 风格效果组合", step1_style_composition),
        ("Step 2: 场景编排", step2_scene_orchestration),
        ("Step 3: 节拍同步", step3_beat_sync),
        ("Step 4: 完整编排", step4_full_orchestration),
        ("Step 5: 反馈闭环", step5_feedback_loop),
    ]
    
    passed = 0
    for name, fn in steps:
        try:
            if fn():
                passed += 1
                print(f"  [PASS] {name}")
            else:
                print(f"  [FAIL] {name}")
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print(f"结果: {passed}/{len(steps)} 步骤通过")
    print("="*60)
    return passed == len(steps)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", type=int, help="运行指定步骤 (1-5)")
    parser.add_argument("--full", action="store_true", help="运行全部步骤")
    args = parser.parse_args()
    
    if args.step:
        steps = {
            1: step1_style_composition,
            2: step2_scene_orchestration,
            3: step3_beat_sync,
            4: step4_full_orchestration,
            5: step5_feedback_loop,
        }
        if args.step in steps:
            steps[args.step]()
        else:
            print(f"无效的步骤号: {args.step}")
    else:
        run_all()
```

- [ ] **Step 2: 运行实机验证脚本**

Run: `python tests/test_phase3_real_ae.py --full`
Expected: 5/5 通过，并生成 phase3_e2e_compiled.jsx

---

## Task 7: 全量测试回归

- [ ] **Step 1: 运行全量测试**

Run: `pytest tests/ -v --tb=short -q`
Expected: 所有测试通过

- [ ] **Step 2: 修复任何失败的测试**

逐一排查并修复失败测试，确保 0 失败。

---

## 验证与验收标准

### 功能验收
- [ ] 场景编排引擎：10种转场效果、10种镜头运动、场景时序计算
- [ ] 节拍编排器：BPM计算、节拍同步关键帧、音乐结构编排、4种节拍风格
- [ ] 效果组合推荐器：15+种风格模板、关键词推荐、风格混合
- [ ] 反馈闭环管理器：结果验证、学习记录、失败恢复、置信度校准
- [ ] Pipeline集成：所有模块正确加载，方法可调用
- [ ] AE实机验证：5个步骤全部通过，JSX可在AE中执行

### 测试验收
- [ ] 单元测试：场景10 + 节拍10 + 组合10 + 反馈10 = 40个新测试全部通过
- [ ] 集成测试：8个Phase 3集成测试全部通过
- [ ] 全量回归：原有589个测试全部通过
- [ ] 总测试数：589 + 48 = 637+ 全部通过

### 性能验收
- [ ] 场景编排 < 10ms
- [ ] 节拍编排（30秒，120BPM）< 50ms
- [ ] 效果组合 < 5ms
- [ ] 反馈记录 < 2ms
