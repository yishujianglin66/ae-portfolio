#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Premiere Pro 转场效果系统
==============================

验证转场系统的类型定义、参数配置和脚本生成功能。
"""

import pytest

from ae.pr_transition_system import (
    PremiereTransitionSystem,
    TransitionDirection,
    TransitionParam,
    TransitionType,
)


class TestTransitionType:
    """测试转场类型枚举。"""

    def test_transition_types_count(self):
        """验证转场类型数量。"""
        assert len(list(TransitionType)) >= 30

    def test_common_transitions_exist(self):
        """验证常用转场类型存在。"""
        assert TransitionType.CROSS_DISSOLVE.value == "cross_dissolve"
        assert TransitionType.WHIP_PAN.value == "whip_pan"
        assert TransitionType.ZOOM.value == "zoom"
        assert TransitionType.GLITCH.value == "glitch"
        assert TransitionType.SHAKE.value == "shake"
        assert TransitionType.SPIN.value == "spin"
        assert TransitionType.SWIRL.value == "swirl"

    def test_transition_categories(self):
        """验证转场分类覆盖完整。"""
        system = PremiereTransitionSystem()
        categories = system.list_categories()
        assert "基础转场" in categories
        assert "擦除转场" in categories
        assert "滑动转场" in categories
        assert "高级转场" in categories
        assert "创意转场" in categories


class TestTransitionParam:
    """测试转场参数数据类。"""

    def test_default_params(self):
        """验证默认参数。"""
        params = TransitionParam()
        assert params.transition_type == TransitionType.CROSS_DISSOLVE
        assert params.duration == 1.0
        assert params.direction is None
        assert params.ease_in == 0.0
        assert params.ease_out == 1.0
        assert params.zoom_amount == 1.5
        assert params.blur_amount == 20.0

    def test_custom_params(self):
        """验证自定义参数。"""
        params = TransitionParam(
            transition_type=TransitionType.WHIP_PAN,
            duration=0.5,
            direction=TransitionDirection.RIGHT,
            zoom_amount=2.0,
            blur_amount=30.0,
        )
        assert params.transition_type == TransitionType.WHIP_PAN
        assert params.duration == 0.5
        assert params.direction == TransitionDirection.RIGHT
        assert params.zoom_amount == 2.0
        assert params.blur_amount == 30.0

    def test_to_dict(self):
        """验证参数序列化。"""
        params = TransitionParam(
            transition_type=TransitionType.ZOOM,
            duration=1.5,
            direction=TransitionDirection.IN,
        )
        result = params.to_dict()
        assert result["transition_type"] == "zoom"
        assert result["duration"] == 1.5
        assert result["direction"] == "in"


class TestPremiereTransitionSystem:
    """测试转场系统核心功能。"""

    def test_list_transitions(self):
        """验证列出转场效果。"""
        system = PremiereTransitionSystem()
        transitions = system.list_transitions()
        assert len(transitions) >= 30
        assert all("type" in t for t in transitions)
        assert all("name" in t for t in transitions)
        assert all("category" in t for t in transitions)

    def test_get_transition_info(self):
        """验证获取转场信息。"""
        system = PremiereTransitionSystem()
        info = system.get_transition_info(TransitionType.WHIP_PAN)
        assert info["name"] == "快速摇摄"
        assert info["category"] == "高级转场"
        assert "description" in info

    def test_get_transitions_by_category(self):
        """验证按分类获取转场。"""
        system = PremiereTransitionSystem()
        advanced = system.get_transitions_by_category("高级转场")
        assert len(advanced) > 0
        assert all(t["category"] == "高级转场" for t in advanced)

    def test_generate_transition_script(self):
        """验证生成转场脚本。"""
        system = PremiereTransitionSystem()
        params = TransitionParam(
            transition_type=TransitionType.CROSS_DISSOLVE,
            duration=1.0,
        )
        script = system.generate_transition_script(0, 0, params)
        assert isinstance(script, str)
        assert "Cross Dissolve" in script
        assert "clip.applyTransition" in script

    def test_generate_whip_pan_script(self):
        """验证生成拉镜转场脚本。"""
        system = PremiereTransitionSystem()
        params = TransitionParam(
            transition_type=TransitionType.WHIP_PAN,
            duration=0.5,
            direction=TransitionDirection.RIGHT,
            blur_amount=25.0,
        )
        script = system.generate_advanced_transition_script(0, 0, params)
        assert isinstance(script, str)
        assert "whip_pan" in script.lower()
        assert "Directional Blur" in script
        assert "Transform" in script

    def test_generate_zoom_transition_script(self):
        """验证生成缩放转场脚本。"""
        system = PremiereTransitionSystem()
        params = TransitionParam(
            transition_type=TransitionType.ZOOM,
            duration=1.0,
            zoom_amount=1.5,
            blur_amount=20.0,
        )
        script = system.generate_advanced_transition_script(0, 0, params)
        assert isinstance(script, str)
        assert "zoom" in script.lower()
        assert "Gaussian Blur" in script
        assert "Transform" in script

    def test_generate_glitch_transition_script(self):
        """验证生成故障转场脚本。"""
        system = PremiereTransitionSystem()
        params = TransitionParam(
            transition_type=TransitionType.GLITCH,
            duration=0.5,
            glitch_amount=5.0,
        )
        script = system.generate_advanced_transition_script(0, 0, params)
        assert isinstance(script, str)
        assert "glitch" in script.lower()
        assert "RGB Channel" in script
        assert "Strobe Light" in script

    @pytest.mark.asyncio
    async def test_apply_transition_dry_run(self):
        """验证转场应用（dry run 模式）。"""
        system = PremiereTransitionSystem()
        params = TransitionParam(transition_type=TransitionType.CROSS_DISSOLVE)
        result = await system.apply_transition(0, 0, params)
        assert result["success"] is True
        assert result["status"] == "dry_run"
        assert result["transition_type"] == "cross_dissolve"
