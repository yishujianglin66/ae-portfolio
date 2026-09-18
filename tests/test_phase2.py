"""
Phase2 模块单元测试
覆盖: ae_ts_compiler_client.py, keyframe_animation_generator.py, beat_keyframe_mapper.py
"""
import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 将项目根目录加入 sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ae_ts_compiler_client import (
    AETSCompilerClient,
    _format_jsx_value,
    _iso_now,
    _json_str,
    _map_easing_type,
)
from beat_keyframe_mapper import (
    Beat,
    BeatKeyframeMapper,
    KeyframeMapping,
    MappingResult,
    parse_beats_from_features,
)
from keyframe_animation_generator import (
    EASE_PRESETS,
    AnimationTemplate,
    KeyframeAnimationGenerator,
    KeyframePoint,
)

# ============================================================
# 夹具
# ============================================================


@pytest.fixture
def ts_client():
    """创建一个使用不存在路径的 AETSCompilerClient，确保 _run_compiler 走降级分支"""
    return AETSCompilerClient(compiler_dir=os.path.join(PROJECT_ROOT, "_nonexistent_compiler_"))


@pytest.fixture
def ts_client_no_node():
    """创建一个 _run_compiler 必定失败的客户端（用于降级测试）"""
    client = AETSCompilerClient(compiler_dir=os.path.join(PROJECT_ROOT, "_nonexistent_compiler_"))
    return client


@pytest.fixture
def anim_gen():
    """关键帧动画生成器"""
    return KeyframeAnimationGenerator()


@pytest.fixture
def mapper():
    """节拍-关键帧映射器"""
    return BeatKeyframeMapper(precision_ms=10.0)


@pytest.fixture
def sample_beats():
    """示例节拍列表（4/4拍, 120BPM, 共8拍）"""
    beats = []
    for i in range(8):
        beats.append(Beat(
            time=0.5 * i,  # 每0.5秒一拍
            strength=0.9 if i % 4 == 0 else 0.5,
            is_downbeat=(i % 4 == 0),
            beat_number=i + 1,
            measure=i // 4 + 1,
        ))
    return beats


@pytest.fixture
def sample_targets():
    """示例目标事件列表"""
    return [
        {"time": 0.0, "property": "Scale", "value": 110, "ease": "ease_out"},
        {"time": 1.0, "property": "Scale", "value": 115, "ease": "ease_out"},
        {"time": 2.0, "property": "Opacity", "value": 80, "ease": "ease_in"},
        {"time": 3.0, "property": "Position", "value": [960, 540], "ease": "linear"},
    ]


@pytest.fixture
def sample_audio_features():
    """示例音频特征数据"""
    return {
        "features": {
            "beats": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
            "downbeats": [0.0, 2.0],
            "bpm": 120.0,
            "duration": 4.0,
            "energy_curve": {
                "times": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
                "values": [0.9, 0.4, 0.5, 0.3, 0.8, 0.4, 0.6, 0.35],
            },
        }
    }


# ============================================================
# AETSCompilerClient 测试
# ============================================================


class TestAETSCompilerClient:
    """ae_ts_compiler_client.py - AETSCompilerClient"""

    def test_client_initialization(self, ts_client):
        """初始化参数"""
        assert ts_client.compiler_dir is not None
        assert ts_client.use_ts_node is False
        assert ts_client._cli_js_path.endswith("cli.js")
        assert ts_client._cli_ts_path.endswith("cli.ts")

    def test_client_initialization_custom(self):
        """自定义参数初始化"""
        client = AETSCompilerClient(compiler_dir="/tmp/my_compiler", use_ts_node=True)
        assert client.compiler_dir == "/tmp/my_compiler"
        assert client.use_ts_node is True

    def test_health_check(self, ts_client):
        """健康检查 - 编译器不存在时应返回 False"""
        result = ts_client.health_check()
        assert result is False

    def test_health_check_ts_node(self):
        """ts-node 模式健康检查 - 目录不存在应返回 False"""
        client = AETSCompilerClient(compiler_dir="/nonexistent", use_ts_node=True)
        assert client.health_check() is False

    def test_compile_effect(self, ts_client_no_node):
        """单效果编译（降级JSX生成）"""
        result = ts_client_no_node.compile_effect(
            "ADBE Gaussian Blur 2",
            {"Blurriness": 50, "Repeat": 1},
        )
        assert result["success"] is True
        assert result["matchName"] == "ADBE Gaussian Blur 2"
        assert "jsx_code" in result
        assert isinstance(result["jsx_code"], str)
        assert len(result["jsx_code"]) > 0

    def test_compile_effect_with_context(self, ts_client_no_node):
        """带上下文的效果编译"""
        ctx = {
            "compName": "Test Comp",
            "width": 3840,
            "height": 2160,
            "layerRef": "my_layer",
            "layerType": "text",
        }
        result = ts_client_no_node.compile_effect(
            "ADBE Glow",
            {"Threshold": 128},
            context=ctx,
        )
        assert result["success"] is True

    def test_compile_batch(self, ts_client_no_node):
        """批量编译"""
        effects = [
            {"matchName": "ADBE Gaussian Blur 2", "settings": {"Blurriness": 30}},
            {"matchName": "ADBE Glow", "settings": {"Threshold": 100}},
        ]
        result = ts_client_no_node.compile_batch(effects)
        assert result["success"] is True
        assert len(result["results"]) == 2
        assert result["results"][0]["matchName"] == "ADBE Gaussian Blur 2"
        assert result["results"][1]["matchName"] == "ADBE Glow"
        assert "jsx_code" in result

    def test_compile_from_planning(self, ts_client_no_node):
        """从规划结果编译"""
        planning = {
            "composition": {
                "name": "Music Video",
                "width": 1920,
                "height": 1080,
                "frameRate": 30,
                "duration": 10,
                "bgColor": [0, 0, 0],
            },
            "layers": [
                {
                    "ref": "text_layer",
                    "layerType": "text",
                    "name": "Title",
                    "text": "Hello",
                    "fontSize": 72,
                    "position": [960, 540],
                },
            ],
            "effects": [
                {
                    "matchName": "ADBE Gaussian Blur 2",
                    "layerRef": "text_layer",
                    "settings": {"Blurriness": 20},
                },
            ],
            "keyframes": [
                {
                    "propertyPath": "ADBE Transform/Opacity",
                    "layerRef": "text_layer",
                    "keyframes": [
                        {"time": 0, "value": 0},
                        {"time": 1, "value": 100},
                    ],
                },
            ],
            "transitions": [],
            "timeline": [],
        }
        result = ts_client_no_node.compile_from_planning(planning)
        assert result["success"] is True
        assert "jsx_code" in result
        assert result["command_count"] >= 3  # comp + layer + effect at minimum

    def test_generate_standalone_jsx(self, ts_client_no_node):
        """独立JSX生成，验证语法正确性"""
        effects = [
            {"matchName": "ADBE Gaussian Blur 2", "settings": {"Blurriness": 50}},
        ]
        jsx = ts_client_no_node._generate_standalone_jsx(effects=effects)
        # 基本 IIFE 结构
        assert jsx.startswith("(function() {")
        assert jsx.endswith("})();")
        # 包含 undo group
        assert "beginUndoGroup" in jsx
        assert "endUndoGroup" in jsx
        # 包含 try/catch
        assert "try {" in jsx
        assert "catch (e)" in jsx
        # JSON 输出
        assert "JSON.stringify" in jsx

    def test_standalone_jsx_contains_effect(self, ts_client_no_node):
        """JSX包含效果代码"""
        effects = [
            {"matchName": "ADBE Gaussian Blur 2", "settings": {"Blurriness": 50, "Repeat": 2}},
        ]
        jsx = ts_client_no_node._generate_standalone_jsx(effects=effects)
        assert "ADBE Gaussian Blur 2" in jsx
        assert "Blurriness" in jsx
        assert "Repeat" in jsx
        assert "setValue" in jsx

    def test_standalone_jsx_contains_keyframe(self, ts_client_no_node):
        """JSX包含关键帧代码"""
        effects = [{"matchName": "ADBE Glow", "settings": {}}]
        keyframes = [
            {
                "propertyPath": "ADBE Transform/Opacity",
                "keyframes": [
                    {"time": 0, "value": 0, "easing": {"type": "ease_in_out"}},
                    {"time": 1, "value": 100},
                ],
            }
        ]
        jsx = ts_client_no_node._generate_standalone_jsx(effects=effects, keyframes=keyframes)
        assert "resolveProperty" in jsx
        assert "setValueAtTime" in jsx
        assert "setInterpolationTypeAtKey" in jsx
        assert "KeyframeEase" in jsx


# ============================================================
# 辅助函数测试
# ============================================================


class TestCompilerHelpers:
    """ae_ts_compiler_client.py 辅助函数"""

    def test_iso_now(self):
        """_iso_now 返回非空字符串"""
        result = _iso_now()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_json_str(self):
        """_json_str 正确转义字符串"""
        assert _json_str("hello") == '"hello"'
        assert _json_str('say "hi"') == '"say \\"hi\\""'

    def test_format_jsx_value_none(self):
        assert _format_jsx_value(None) == "null"

    def test_format_jsx_value_bool(self):
        assert _format_jsx_value(True) == "true"
        assert _format_jsx_value(False) == "false"

    def test_format_jsx_value_int(self):
        assert _format_jsx_value(42) == "42"

    def test_format_jsx_value_float(self):
        assert _format_jsx_value(3.14) == "3.14"

    def test_format_jsx_value_float_whole(self):
        """浮点整数值应输出整数"""
        assert _format_jsx_value(50.0) == "50"

    def test_format_jsx_value_string(self):
        assert _format_jsx_value("hello") == '"hello"'

    def test_format_jsx_value_list(self):
        assert _format_jsx_value([1, 2, 3]) == "[1, 2, 3]"

    def test_format_jsx_value_nested_list(self):
        assert _format_jsx_value([[1, 2], [3, 4]]) == "[[1, 2], [3, 4]]"

    def test_map_easing_type(self):
        assert _map_easing_type("linear") == "KeyframeInterpolationType.LINEAR"
        assert _map_easing_type("bezier") == "KeyframeInterpolationType.BEZIER"
        assert _map_easing_type("hold") == "KeyframeInterpolationType.HOLD"
        assert _map_easing_type("ease_in") == "KeyframeInterpolationType.BEZIER"
        assert _map_easing_type("ease_out") == "KeyframeInterpolationType.BEZIER"
        assert _map_easing_type("ease_in_out") == "KeyframeInterpolationType.BEZIER"
        # 未知类型默认 BEZIER
        assert _map_easing_type("unknown") == "KeyframeInterpolationType.BEZIER"


# ============================================================
# KeyframeAnimationGenerator 测试
# ============================================================


class TestKeyframeAnimationGenerator:
    """keyframe_animation_generator.py - KeyframeAnimationGenerator"""

    # ---- 入场动画 ----

    def test_entrance_fade_in(self, anim_gen):
        """淡入动画 (Opacity 0→100)"""
        kfs = anim_gen.generate_entrance_animation("fade_in", 1.0)
        assert len(kfs) == 2
        assert kfs[0].value == 0
        assert kfs[1].value == 100
        # 确认属性是 Opacity
        tmpl = next(t for t in anim_gen.templates["entrance"] if t.name == "fade_in")
        assert tmpl.property_name == "Opacity"

    def test_entrance_fade_in_duration_scaling(self, anim_gen):
        """淡入动画时间缩放"""
        kfs = anim_gen.generate_entrance_animation("fade_in", 2.0)
        assert kfs[-1].time == pytest.approx(2.0)

    def test_entrance_slide_left(self, anim_gen):
        """左滑入场 (Position变化)"""
        kfs = anim_gen.generate_entrance_animation("slide_left", 0.8)
        assert len(kfs) == 2
        assert isinstance(kfs[0].value, list)
        # 初始 x 应该是负数（画面左侧外）
        assert kfs[0].value[0] < 0
        # 最终位置 x 应该是 960
        assert kfs[1].value[0] == 960

    def test_entrance_slide_left_custom_y(self, anim_gen):
        """左滑入场自定义 y 坐标"""
        kfs = anim_gen.generate_entrance_animation("slide_left", 0.8, y=300)
        for kf in kfs:
            assert kf.value[1] == 300

    def test_entrance_scale_up(self, anim_gen):
        """放大入场 (Scale 0→100)"""
        kfs = anim_gen.generate_entrance_animation("scale_up", 0.6)
        assert len(kfs) == 2
        assert kfs[0].value == 0
        assert kfs[1].value == 100
        tmpl = next(t for t in anim_gen.templates["entrance"] if t.name == "scale_up")
        assert tmpl.property_name == "Scale"

    def test_entrance_unknown_raises(self, anim_gen):
        """未知入场动画应抛出 ValueError"""
        with pytest.raises(ValueError, match="未知的入场动画类型"):
            anim_gen.generate_entrance_animation("nonexistent", 1.0)

    # ---- 出场动画 ----

    def test_exit_fade_out(self, anim_gen):
        """淡出动画"""
        kfs = anim_gen.generate_exit_animation("fade_out", 0.8)
        assert len(kfs) == 2
        assert kfs[0].value == 100
        assert kfs[1].value == 0
        tmpl = next(t for t in anim_gen.templates["exit"] if t.name == "fade_out")
        assert tmpl.property_name == "Opacity"

    def test_exit_slide_out(self, anim_gen):
        """滑出动画"""
        kfs = anim_gen.generate_exit_animation("slide_left_out", 0.8)
        assert len(kfs) == 2
        assert isinstance(kfs[0].value, list)
        assert kfs[0].value[0] == 960  # 从中心出发
        assert kfs[1].value[0] < 0     # 向左滑出

    def test_exit_unknown_raises(self, anim_gen):
        """未知出场动画应抛出 ValueError"""
        with pytest.raises(ValueError, match="未知的出场动画类型"):
            anim_gen.generate_exit_animation("nonexistent", 1.0)

    # ---- 循环动画 ----

    def test_loop_pulse(self, anim_gen):
        """脉冲循环"""
        kfs = anim_gen.generate_loop_animation("pulse", 1.0)
        assert len(kfs) == 3
        # 脉冲: 100 → 105 → 100
        assert kfs[0].value == 100
        assert kfs[1].value == 105
        assert kfs[2].value == 100
        tmpl = next(t for t in anim_gen.templates["loop"] if t.name == "pulse")
        assert tmpl.property_name == "Scale"

    def test_loop_breathe(self, anim_gen):
        """呼吸循环"""
        kfs = anim_gen.generate_loop_animation("breathe", 3.0)
        assert len(kfs) == 3
        assert kfs[0].value == 100
        assert kfs[1].value == 103
        assert kfs[2].value == 100
        tmpl = next(t for t in anim_gen.templates["loop"] if t.name == "breathe")
        assert tmpl.property_name == "Scale"
        assert tmpl.duration == pytest.approx(3.0)

    def test_loop_unknown_raises(self, anim_gen):
        """未知循环动画应抛出 ValueError"""
        with pytest.raises(ValueError, match="未知的循环动画类型"):
            anim_gen.generate_loop_animation("nonexistent", 1.0)

    # ---- 强调动画 ----

    def test_emphasis_shake(self, anim_gen):
        """抖动强调"""
        kfs = anim_gen.generate_emphasis_animation("shake", 0.6)
        assert len(kfs) == 11  # 5次振荡 + 衰减
        # 首尾应为 0
        assert kfs[0].value == 0
        assert kfs[-1].value == 0
        tmpl = next(t for t in anim_gen.templates["emphasis"] if t.name == "shake")
        assert tmpl.property_name == "Position"

    def test_emphasis_shake_custom_amplitude(self, anim_gen):
        """抖动自定义振幅"""
        kfs = anim_gen.generate_emphasis_animation("shake", 0.6, amplitude=20)
        # 非零值的绝对值应与自定义振幅相关
        nonzero_vals = [kf.value for kf in kfs if isinstance(kf.value, (int, float)) and kf.value != 0]
        if nonzero_vals:
            max_val = max(abs(v) for v in nonzero_vals)
            assert max_val == pytest.approx(20, abs=1)

    def test_emphasis_pop(self, anim_gen):
        """弹出强调"""
        kfs = anim_gen.generate_emphasis_animation("pop", 0.5)
        assert len(kfs) == 3
        assert kfs[0].value == 100    # 起始
        assert kfs[1].value == 120    # 弹出
        assert kfs[2].value == 100    # 回弹
        tmpl = next(t for t in anim_gen.templates["emphasis"] if t.name == "pop")
        assert tmpl.property_name == "Scale"

    def test_emphasis_unknown_raises(self, anim_gen):
        """未知强调动画应抛出 ValueError"""
        with pytest.raises(ValueError, match="未知的强调动画类型"):
            anim_gen.generate_emphasis_animation("nonexistent", 1.0)

    # ---- 节拍同步 ----

    def test_beat_synced_keyframes(self, anim_gen):
        """节拍同步关键帧"""
        beat_times = [0.5, 1.0, 1.5, 2.0]
        kfs = anim_gen.generate_beat_synced_keyframes(
            beat_times=beat_times,
            property_name="Scale",
            base_value=100,
            beat_value=110,
            attack_ms=30,
            decay_ms=200,
        )
        # 每个节拍产生 attack + decay 两帧
        assert len(kfs) == 8
        # 应按时间排序
        times = [kf.time for kf in kfs]
        assert times == sorted(times)
        # 检查 attack 帧
        attack_kfs = [kf for kf in kfs if kf.value == 110]
        assert len(attack_kfs) == 4

    def test_beat_synced_keyframes_timing(self, anim_gen):
        """节拍同步关键帧时间精度"""
        beat_times = [1.0]
        kfs = anim_gen.generate_beat_synced_keyframes(
            beat_times=beat_times,
            property_name="Opacity",
            base_value=100,
            beat_value=70,
            attack_ms=20,
            decay_ms=150,
        )
        assert len(kfs) == 2
        assert kfs[0].time == pytest.approx(1.0)
        assert kfs[1].time == pytest.approx(1.0 + 0.020 + 0.150)

    def test_beat_scale_animation(self, anim_gen):
        """节拍缩放动画"""
        beat_times = [0.5, 1.0]
        cmds = anim_gen.generate_beat_scale_animation(
            beat_times=beat_times,
            base_scale=100,
            beat_scale=115,
        )
        assert len(cmds) > 0
        assert all(c["command"] == "setKeyframe" for c in cmds)
        assert all(c["property"] == "Scale" for c in cmds)

    def test_beat_opacity_animation(self, anim_gen):
        """节拍透明度动画"""
        beat_times = [0.5, 1.0]
        cmds = anim_gen.generate_beat_opacity_animation(
            beat_times=beat_times,
            base_opacity=100,
            beat_opacity=70,
        )
        assert len(cmds) > 0
        assert all(c["command"] == "setKeyframe" for c in cmds)
        assert all(c["property"] == "Opacity" for c in cmds)

    def test_beat_position_animation(self, anim_gen):
        """节拍位移动画"""
        beat_times = [0.5, 1.0]
        cmds = anim_gen.generate_beat_position_animation(
            beat_times=beat_times,
            direction="up",
            distance=20,
        )
        assert len(cmds) > 0
        assert all(c["command"] == "setKeyframe" for c in cmds)
        assert all(c["property"] == "Position" for c in cmds)
        # 检查方向：up → [0, -20]
        attack_cmds = [c for c in cmds if c["value"] != [0, 0]]
        assert any(c["value"] == [0, -20] for c in attack_cmds)

    # ---- AE 命令格式 ----

    def test_to_ae_commands(self, anim_gen):
        """转换为AE命令格式"""
        kfs = [
            KeyframePoint(time=0, value=0, ease_out="ease_out",
                          bezier_out=EASE_PRESETS["ease_out"]),
            KeyframePoint(time=1, value=100, ease_in="ease_in",
                          bezier_in=EASE_PRESETS["ease_in"]),
        ]
        cmds = anim_gen.to_ae_keyframe_commands(kfs, layer_name="Layer 1", property_name="Opacity")
        assert len(cmds) == 2
        assert cmds[0]["command"] == "setKeyframe"
        assert cmds[0]["layer"] == "Layer 1"
        assert cmds[0]["property"] == "Opacity"
        assert cmds[0]["time"] == pytest.approx(0.0)
        assert cmds[0]["value"] == 0
        assert "easing" in cmds[0]
        assert "out" in cmds[0]["easing"]

    def test_to_ae_commands_with_comp(self, anim_gen):
        """AE命令格式带 comp 字段"""
        kfs = [KeyframePoint(time=0, value=100)]
        cmds = anim_gen.to_ae_keyframe_commands(kfs, layer_name="L", property_name="Scale", comp_name="Comp 1")
        assert cmds[0]["comp"] == "Comp 1"

    def test_to_ae_commands_linear_no_easing(self, anim_gen):
        """linear 缓动不输出 easing 字段"""
        kfs = [KeyframePoint(time=0, value=100, ease_in="linear", ease_out="linear")]
        cmds = anim_gen.to_ae_keyframe_commands(kfs, layer_name="L", property_name="Scale")
        assert "easing" not in cmds[0]

    # ---- 缓动预设 ----

    def test_ease_presets(self):
        """缓动预设完整性"""
        required = ["linear", "ease_in", "ease_out", "ease_in_out", "spring", "bounce", "elastic"]
        for name in required:
            assert name in EASE_PRESETS
        # linear 应为 None
        assert EASE_PRESETS["linear"] is None
        # 其他应为4元组
        for name in required[1:]:
            assert isinstance(EASE_PRESETS[name], tuple)
            assert len(EASE_PRESETS[name]) == 4


# ============================================================
# BeatKeyframeMapper 测试
# ============================================================


class TestBeatKeyframeMapper:
    """beat_keyframe_mapper.py - BeatKeyframeMapper"""

    def test_mapper_initialization(self):
        """初始化"""
        mapper = BeatKeyframeMapper(precision_ms=20.0)
        assert mapper.precision_ms == pytest.approx(20.0)

    def test_mapper_initialization_default(self):
        """默认精度"""
        mapper = BeatKeyframeMapper()
        assert mapper.precision_ms == pytest.approx(10.0)

    # ---- 映射策略 ----

    def test_map_nearest(self, mapper, sample_beats, sample_targets):
        """最近邻匹配"""
        result = mapper.map_beats_to_keyframes(sample_beats, sample_targets, strategy="nearest")
        assert isinstance(result, MappingResult)
        assert len(result.mappings) > 0
        for m in result.mappings:
            assert isinstance(m, KeyframeMapping)
            assert abs(m.offset_ms) <= mapper.precision_ms * 5

    def test_map_dynamic_programming(self, mapper, sample_beats, sample_targets):
        """动态规划匹配"""
        result = mapper.map_beats_to_keyframes(
            sample_beats, sample_targets, strategy="dynamic_programming"
        )
        assert isinstance(result, MappingResult)
        assert len(result.mappings) > 0
        assert result.beat_count == len(sample_beats)
        assert result.keyframe_count == len(sample_targets)

    def test_map_downbeat_priority(self, mapper, sample_beats, sample_targets):
        """强拍优先匹配"""
        result = mapper.map_beats_to_keyframes(
            sample_beats, sample_targets, strategy="downbeat_priority"
        )
        assert isinstance(result, MappingResult)
        # 应至少匹配一些事件
        assert len(result.mappings) > 0

    def test_map_energy_based(self, mapper, sample_beats, sample_targets):
        """能量匹配"""
        # 添加能量信息
        for t in sample_targets:
            t["energy"] = 0.8
        result = mapper.map_beats_to_keyframes(
            sample_beats, sample_targets, strategy="energy_based"
        )
        assert isinstance(result, MappingResult)
        assert len(result.mappings) > 0

    def test_map_empty_beats(self, mapper, sample_targets):
        """空节拍列表"""
        result = mapper.map_beats_to_keyframes([], sample_targets)
        assert len(result.mappings) == 0
        assert result.coverage == 0.0

    def test_map_empty_targets(self, mapper, sample_beats):
        """空目标列表"""
        result = mapper.map_beats_to_keyframes(sample_beats, [])
        assert len(result.mappings) == 0
        assert result.coverage == 0.0

    # ---- 时间线生成 ----

    def test_generate_beat_synced_timeline(self, mapper, sample_beats):
        """节拍同步时间线"""
        clip_events = [
            {"type": "cut", "time": 0.0, "intensity": 0.9},
            {"type": "effect", "time": 1.0, "intensity": 0.7},
            {"type": "transition", "time": 2.0, "intensity": 0.5},
        ]
        result = mapper.generate_beat_synced_timeline(
            beats=sample_beats,
            total_duration=4.0,
            clip_events=clip_events,
            style="default",
        )
        assert "timeline" in result
        assert "beat_map" in result
        assert "statistics" in result
        assert result["statistics"]["style"] == "default"
        assert result["statistics"]["total_events"] == 3

    def test_timeline_on_beat_style(self, mapper, sample_beats):
        """on_beat 风格"""
        clip_events = [
            {"type": "cut", "time": 0.0},
            {"type": "cut", "time": 0.5},
        ]
        result = mapper.generate_beat_synced_timeline(
            beats=sample_beats,
            total_duration=4.0,
            clip_events=clip_events,
            style="on_beat",
        )
        assert result["statistics"]["style"] == "on_beat"

    def test_timeline_off_beat_style(self, mapper, sample_beats):
        """off_beat 风格"""
        clip_events = [
            {"type": "cut", "time": 0.25},
            {"type": "cut", "time": 0.75},
        ]
        result = mapper.generate_beat_synced_timeline(
            beats=sample_beats,
            total_duration=4.0,
            clip_events=clip_events,
            style="off_beat",
        )
        assert result["statistics"]["style"] == "off_beat"
        # off_beat 应产生反拍节拍
        assert result["statistics"]["beat_count"] > 0

    # ---- 贝塞尔包络 ----

    def test_calculate_bezier_envelope(self, mapper):
        """贝塞尔包络线"""
        samples = mapper.calculate_bezier_envelope(
            beat_time=1.0,
            attack_ms=50,
            decay_ms=200,
            peak_value=110,
            base_value=100,
            sample_rate=30,
        )
        assert len(samples) > 0
        # 第一个采样点应该在 beat_time 附近
        assert samples[0][0] == pytest.approx(1.0, abs=0.01)
        # 峰值应接近 peak_value
        max_val = max(v for _, v in samples)
        assert max_val >= 100
        # 最终值应接近 base_value
        assert samples[-1][1] == pytest.approx(100, abs=1)

    def test_calculate_bezier_envelope_zero_duration(self, mapper):
        """零持续时间包络"""
        samples = mapper.calculate_bezier_envelope(
            beat_time=1.0, attack_ms=0, decay_ms=0,
            peak_value=110, base_value=100,
        )
        assert len(samples) == 1
        assert samples[0][1] == pytest.approx(100)

    # ---- 密度优化 ----

    def test_optimize_keyframe_density(self, mapper):
        """关键帧密度优化"""
        # 创建间隔很近的关键帧
        kfs = [
            KeyframeMapping(
                time=1.0, beat_time=1.0, offset_ms=0,
                strength=0.9, property_name="Scale", value=110,
                ease_type="ease_out", confidence=0.9,
            ),
            KeyframeMapping(
                time=1.01, beat_time=1.0, offset_ms=10,
                strength=0.5, property_name="Scale", value=115,
                ease_type="ease_out", confidence=0.7,
            ),
            KeyframeMapping(
                time=1.5, beat_time=1.5, offset_ms=0,
                strength=0.8, property_name="Scale", value=105,
                ease_type="ease_out", confidence=0.8,
            ),
        ]
        result = mapper.optimize_keyframe_density(kfs, min_interval_ms=50)
        # 前两个间隔仅10ms，应被合并
        assert len(result) == 2

    def test_optimize_keyframe_density_keeps_higher_confidence(self, mapper):
        """密度优化保留更高置信度"""
        kfs = [
            KeyframeMapping(
                time=1.0, beat_time=1.0, offset_ms=0,
                strength=0.9, property_name="Scale", value=110,
                ease_type="ease_out", confidence=0.5,
            ),
            KeyframeMapping(
                time=1.01, beat_time=1.0, offset_ms=10,
                strength=0.5, property_name="Scale", value=115,
                ease_type="ease_out", confidence=0.9,
            ),
        ]
        result = mapper.optimize_keyframe_density(kfs, min_interval_ms=50)
        # 第二个置信度更高应保留
        assert result[0].confidence == pytest.approx(0.9)

    def test_optimize_keyframe_density_empty(self, mapper):
        """空列表优化"""
        result = mapper.optimize_keyframe_density([])
        assert result == []

    # ---- 映射质量验证 ----

    def test_validate_mapping_good(self, mapper, sample_beats, sample_targets):
        """映射质量验证 - 良好"""
        result = mapper.map_beats_to_keyframes(sample_beats, sample_targets, strategy="dynamic_programming")
        validation = mapper.validate_mapping(result)
        assert "valid" in validation
        assert "score" in validation
        assert "issues" in validation
        assert isinstance(validation["issues"], list)

    def test_validate_mapping_empty(self, mapper):
        """映射质量验证 - 空映射"""
        empty_result = MappingResult(
            mappings=[], beat_count=8, keyframe_count=4,
            average_offset_ms=0.0, max_offset_ms=0.0, coverage=0.0,
        )
        validation = mapper.validate_mapping(empty_result)
        assert validation["valid"] is False
        assert validation["score"] == pytest.approx(0.0)
        assert len(validation["issues"]) > 0

    # ---- 从音频特征解析 ----

    def test_parse_beats_from_features(self, sample_audio_features):
        """从音频特征解析节拍"""
        beats = parse_beats_from_features(sample_audio_features)
        assert len(beats) == 8
        assert all(isinstance(b, Beat) for b in beats)
        # 强拍检测
        downbeats = [b for b in beats if b.is_downbeat]
        assert len(downbeats) >= 2  # 至少0.0和2.0

    def test_parse_beats_from_features_beat_numbers(self, sample_audio_features):
        """节拍编号连续"""
        beats = parse_beats_from_features(sample_audio_features)
        numbers = [b.beat_number for b in beats]
        assert numbers == list(range(1, len(beats) + 1))

    def test_parse_beats_from_features_no_downbeats(self):
        """无强拍信息时自动推算"""
        features = {
            "beats": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
            "downbeats": [],
            "bpm": 120.0,
            "duration": 4.0,
            "energy_curve": {"times": [], "values": []},
        }
        beats = parse_beats_from_features({"features": features})
        # 4/4拍: beat_number 1,5 为强拍 (即索引0,4)
        assert beats[0].is_downbeat is True
        assert beats[4].is_downbeat is True
        # 非强拍
        assert beats[1].is_downbeat is False
        assert beats[2].is_downbeat is False

    def test_parse_beats_from_features_empty(self):
        """空特征"""
        beats = parse_beats_from_features({"features": {"beats": []}})
        assert beats == []

    # ---- DP 最优性 ----

    def test_dp_optimality(self, sample_beats, sample_targets):
        """验证DP比nearest更优（偏移量更小或相等）"""
        mapper_dp = BeatKeyframeMapper(precision_ms=10.0)
        mapper_nn = BeatKeyframeMapper(precision_ms=10.0)

        result_dp = mapper_dp.map_beats_to_keyframes(
            sample_beats, sample_targets, strategy="dynamic_programming"
        )
        result_nn = mapper_nn.map_beats_to_keyframes(
            sample_beats, sample_targets, strategy="nearest"
        )
        # DP 总偏移 <= Nearest 总偏移（或差距很小）
        dp_total = sum(abs(m.offset_ms) for m in result_dp.mappings)
        nn_total = sum(abs(m.offset_ms) for m in result_nn.mappings)
        assert dp_total <= nn_total + 1.0  # 允许微小数值误差

    # ---- 精度约束 ----

    def test_precision_constraint(self):
        """精度约束验证 - 偏移量不超过 precision_ms * 5"""
        mapper = BeatKeyframeMapper(precision_ms=10.0)
        # 精确对齐的节拍和目标
        beats = [Beat(time=1.0, strength=0.9, is_downbeat=True, beat_number=1, measure=1)]
        targets = [{"time": 1.0, "property": "Scale", "value": 110, "ease": "ease_out"}]
        result = mapper.map_beats_to_keyframes(beats, targets, strategy="dynamic_programming")
        for m in result.mappings:
            assert abs(m.offset_ms) <= mapper.precision_ms * 5

    def test_precision_constraint_tight(self):
        """精度约束 - 目标离所有节拍很远时不应匹配"""
        mapper = BeatKeyframeMapper(precision_ms=10.0)
        beats = [Beat(time=0.0, strength=0.9, is_downbeat=True, beat_number=1, measure=1)]
        # 目标时间距节拍 0.1s = 100ms > precision*5 = 50ms
        targets = [{"time": 0.1, "property": "Scale", "value": 110, "ease": "ease_out"}]
        result = mapper.map_beats_to_keyframes(beats, targets, strategy="nearest")
        assert len(result.mappings) == 0

    # ---- 风格预设 ----

    def test_style_presets_exist(self):
        """所有风格预设存在"""
        required_styles = ["default", "on_beat", "off_beat", "double_time", "half_time"]
        for style in required_styles:
            assert style in BeatKeyframeMapper.STYLE_PRESETS

    def test_half_time_only_downbeats(self, mapper, sample_beats):
        """half_time 风格只保留强拍"""
        clip_events = [
            {"type": "cut", "time": 0.0},
            {"type": "cut", "time": 2.0},
        ]
        result = mapper.generate_beat_synced_timeline(
            beats=sample_beats,
            total_duration=4.0,
            clip_events=clip_events,
            style="half_time",
        )
        # beat_map 中的节拍应该只有强拍
        for b in result["beat_map"]:
            assert b["is_downbeat"] is True

    def test_double_time_more_beats(self, mapper, sample_beats):
        """double_time 风格产生更多节拍"""
        clip_events = [{"type": "cut", "time": 0.25}]
        result = mapper.generate_beat_synced_timeline(
            beats=sample_beats,
            total_duration=4.0,
            clip_events=clip_events,
            style="double_time",
        )
        # double_time 的 beat_count 应 > 原始 beat 数
        assert result["statistics"]["beat_count"] > len(sample_beats)
