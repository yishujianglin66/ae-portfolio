#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Premiere Pro 高级剪辑系统
==============================

验证高级剪辑系统的类型定义、参数配置和脚本生成功能。
"""

import pytest
from ae.pr_advanced_editing import (
    EditMode,
    MotionDirection,
    WhipPanParam,
    DynamicZoomParam,
    SpeedRampParam,
    KeyframePoint,
    KeyframeAnimationParam,
    AdvancedEditParam,
    PremiereAdvancedEditing,
)


class TestEditMode:
    """测试编辑模式枚举。"""

    def test_edit_modes_count(self):
        """验证编辑模式数量。"""
        assert len(list(EditMode)) >= 10

    def test_common_edit_modes_exist(self):
        """验证常用编辑模式存在。"""
        assert EditMode.WHIP_PAN.value == "whip_pan"
        assert EditMode.DYNAMIC_ZOOM.value == "dynamic_zoom"
        assert EditMode.SPEED_RAMP.value == "speed_ramp"
        assert EditMode.KEYFRAME_ANIMATION.value == "keyframe_animation"


class TestMotionDirection:
    """测试运动方向枚举。"""

    def test_directions(self):
        """验证运动方向定义。"""
        assert MotionDirection.LEFT.value == "left"
        assert MotionDirection.RIGHT.value == "right"
        assert MotionDirection.UP.value == "up"
        assert MotionDirection.DOWN.value == "down"


class TestWhipPanParam:
    """测试拉镜效果参数。"""

    def test_default_params(self):
        """验证默认参数。"""
        params = WhipPanParam()
        assert params.direction == MotionDirection.RIGHT
        assert params.speed == 2.0
        assert params.blur_amount == 25.0
        assert params.duration == 0.5
        assert params.overlap == 0.3

    def test_custom_params(self):
        """验证自定义参数。"""
        params = WhipPanParam(
            direction=MotionDirection.LEFT,
            speed=3.0,
            blur_amount=35.0,
            duration=0.7,
            overlap=0.4,
        )
        assert params.direction == MotionDirection.LEFT
        assert params.speed == 3.0
        assert params.blur_amount == 35.0


class TestDynamicZoomParam:
    """测试动态缩放参数。"""

    def test_default_params(self):
        """验证默认参数。"""
        params = DynamicZoomParam()
        assert params.start_scale == 100.0
        assert params.end_scale == 150.0
        assert params.duration == 2.0
        assert params.ease_type == "ease_in_out"
        assert params.focus_point is None
        assert params.blur_amount == 0.0

    def test_custom_params(self):
        """验证自定义参数。"""
        params = DynamicZoomParam(
            start_scale=80.0,
            end_scale=200.0,
            duration=3.0,
            ease_type="ease_out",
            focus_point=[0.3, 0.7],
            blur_amount=10.0,
        )
        assert params.start_scale == 80.0
        assert params.end_scale == 200.0
        assert params.focus_point == [0.3, 0.7]


class TestSpeedRampParam:
    """测试速度调整参数。"""

    def test_default_params(self):
        """验证默认参数。"""
        params = SpeedRampParam()
        assert params.start_speed == 100.0
        assert params.end_speed == 200.0
        assert params.ramp_duration == 1.0
        assert params.ease_type == "ease_in_out"
        assert params.frame_blending is True
        assert params.preserve_audio is False

    def test_custom_params(self):
        """验证自定义参数。"""
        params = SpeedRampParam(
            start_speed=50.0,
            end_speed=100.0,
            ramp_duration=2.0,
            ease_type="ease_in",
            frame_blending=False,
            preserve_audio=True,
        )
        assert params.start_speed == 50.0
        assert params.end_speed == 100.0
        assert params.preserve_audio is True


class TestKeyframePoint:
    """测试关键帧点。"""

    def test_keyframe_point(self):
        """验证关键帧点定义。"""
        kf = KeyframePoint(time=1.0, value=[100, 100], interpolation="bezier")
        assert kf.time == 1.0
        assert kf.value == [100, 100]
        assert kf.interpolation == "bezier"

    def test_default_interpolation(self):
        """验证默认插值类型。"""
        kf = KeyframePoint(time=0.5, value=50.0)
        assert kf.interpolation == "linear"


class TestKeyframeAnimationParam:
    """测试关键帧动画参数。"""

    def test_keyframe_animation_param(self):
        """验证关键帧动画参数。"""
        keyframes = [
            KeyframePoint(time=0.0, value=[0, 0]),
            KeyframePoint(time=2.0, value=[100, 50], interpolation="bezier"),
        ]
        params = KeyframeAnimationParam(
            property_name="Position",
            keyframes=keyframes,
            easing="ease_in_out",
        )
        assert params.property_name == "Position"
        assert len(params.keyframes) == 2
        assert params.easing == "ease_in_out"


class TestAdvancedEditParam:
    """测试高级编辑参数。"""

    def test_default_params(self):
        """验证默认参数。"""
        params = AdvancedEditParam()
        assert params.edit_mode == EditMode.WHIP_PAN
        assert isinstance(params.whip_pan, WhipPanParam)
        assert isinstance(params.dynamic_zoom, DynamicZoomParam)
        assert isinstance(params.speed_ramp, SpeedRampParam)

    def test_custom_params(self):
        """验证自定义参数。"""
        whip_params = WhipPanParam(direction=MotionDirection.LEFT)
        params = AdvancedEditParam(
            edit_mode=EditMode.WHIP_PAN,
            whip_pan=whip_params,
            track_index=1,
            clip_index=2,
        )
        assert params.edit_mode == EditMode.WHIP_PAN
        assert params.whip_pan.direction == MotionDirection.LEFT
        assert params.track_index == 1
        assert params.clip_index == 2

    def test_to_dict(self):
        """验证参数序列化。"""
        whip_params = WhipPanParam(direction=MotionDirection.RIGHT)
        params = AdvancedEditParam(
            edit_mode=EditMode.WHIP_PAN,
            whip_pan=whip_params,
        )
        result = params.to_dict()
        assert result["edit_mode"] == "whip_pan"
        assert result["whip_pan"]["direction"] == "right"


class TestPremiereAdvancedEditing:
    """测试高级剪辑系统核心功能。"""

    def test_list_edit_modes(self):
        """验证列出编辑模式。"""
        system = PremiereAdvancedEditing()
        modes = system.list_edit_modes()
        assert len(modes) >= 10
        assert all("mode" in m for m in modes)
        assert all("name" in m for m in modes)

    def test_get_edit_mode_info(self):
        """验证获取编辑模式信息。"""
        system = PremiereAdvancedEditing()
        info = system.get_edit_mode_info(EditMode.WHIP_PAN)
        assert info["name"] == "拉镜效果"
        assert info["category"] == "高级转场"

    def test_generate_whip_pan_script(self):
        """验证生成拉镜脚本。"""
        system = PremiereAdvancedEditing()
        whip_params = WhipPanParam(direction=MotionDirection.RIGHT, speed=2.0)
        params = AdvancedEditParam(edit_mode=EditMode.WHIP_PAN, whip_pan=whip_params)
        script = system.generate_whip_pan_script(0, 0, whip_params)
        assert isinstance(script, str)
        assert "whip_pan" in script.lower()
        assert "Transform" in script
        assert "Directional Blur" in script

    def test_generate_dynamic_zoom_script(self):
        """验证生成动态缩放脚本。"""
        system = PremiereAdvancedEditing()
        zoom_params = DynamicZoomParam(
            start_scale=100.0,
            end_scale=150.0,
            duration=2.0,
        )
        script = system.generate_dynamic_zoom_script(0, 0, zoom_params)
        assert isinstance(script, str)
        assert "dynamic_zoom" in script.lower()
        assert "Transform" in script
        assert "Scale" in script

    def test_generate_speed_ramp_script(self):
        """验证生成速度调整脚本。"""
        system = PremiereAdvancedEditing()
        speed_params = SpeedRampParam(
            start_speed=100.0,
            end_speed=200.0,
            ramp_duration=1.0,
        )
        script = system.generate_speed_ramp_script(0, 0, speed_params)
        assert isinstance(script, str)
        assert "speed_ramp" in script.lower()
        assert "Speed" in script

    def test_generate_keyframe_animation_script(self):
        """验证生成关键帧动画脚本。"""
        system = PremiereAdvancedEditing()
        keyframes = [
            KeyframePoint(time=0.0, value=[100, 100]),
            KeyframePoint(time=1.0, value=[150, 150]),
        ]
        kf_params = KeyframeAnimationParam(
            property_name="Scale",
            keyframes=keyframes,
        )
        script = system.generate_keyframe_animation_script(0, 0, kf_params)
        assert isinstance(script, str)
        assert "keyframe_animation" in script.lower()
        assert "Transform" in script

    def test_apply_editing_dry_run(self):
        """验证编辑应用（dry run 模式）。"""
        system = PremiereAdvancedEditing()
        whip_params = WhipPanParam(direction=MotionDirection.RIGHT)
        params = AdvancedEditParam(edit_mode=EditMode.WHIP_PAN, whip_pan=whip_params)
        result = system.apply_editing(0, 0, params)
        assert result["success"] is True
        assert result["status"] == "dry_run"
        assert result["edit_mode"] == "whip_pan"
