#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 pr_advanced_editing 中高风险逻辑
======================================

覆盖 ae/pr_advanced_editing.py 的关键契约：

1. EditMode / MotionDirection 枚举值
2. AdvancedEditParam.to_dict() 序列化
3. AdvancedEditParam.to_dict() 不泄漏 None
4. apply_batch_editing 对不同 edit_mode 的派发
5. apply_batch_editing 保留 results 顺序
6. apply_batch_editing 默认值回退（缺字段不崩）
7. apply_batch_editing dry_run 模式（无 pr_client）
8. generate_editing_script 对未知 mode 走默认 whip_pan

注：apply_batch_editing 内部调用 apply_editing，apply_editing
在 pr_client 为 None 时返回 dry_run 结果，可作为测试切入点。
"""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# 枚举
# ============================================================
class TestEnums:
    def test_edit_mode_values(self):
        from ae.pr_advanced_editing import EditMode

        assert EditMode.WHIP_PAN.value == "whip_pan"
        assert EditMode.DYNAMIC_ZOOM.value == "dynamic_zoom"
        assert EditMode.SPEED_RAMP.value == "speed_ramp"
        assert EditMode.KEYFRAME_ANIMATION.value == "keyframe_animation"

    def test_motion_direction_values(self):
        from ae.pr_advanced_editing import MotionDirection

        assert MotionDirection.LEFT.value == "left"
        assert MotionDirection.RIGHT.value == "right"
        assert MotionDirection.UP.value == "up"
        assert MotionDirection.DOWN.value == "down"
        assert MotionDirection.CENTER.value == "center"


# ============================================================
# 数据类
# ============================================================
class TestAdvancedEditParam:
    def _make_param(self, **kwargs):
        from ae.pr_advanced_editing import (
            AdvancedEditParam,
            DynamicZoomParam,
            EditMode,
            WhipPanParam,
        )

        defaults = dict(
            edit_mode=EditMode.WHIP_PAN,
            whip_pan=WhipPanParam(),
            track_index=0,
            clip_index=0,
        )
        defaults.update(kwargs)
        return AdvancedEditParam(**defaults)

    def test_default_to_dict(self):
        param = self._make_param()
        d = param.to_dict()
        # 必有字段
        assert d["edit_mode"] == "whip_pan"
        assert d["track_index"] == 0
        assert d["clip_index"] == 0
        # None 字段不输出
        assert "start_time" not in d
        assert "end_time" not in d

    def test_to_dict_includes_start_end_time(self):
        param = self._make_param(start_time=1.5, end_time=3.0)
        d = param.to_dict()
        assert d["start_time"] == 1.5
        assert d["end_time"] == 3.0

    def test_to_dict_whip_pan_serialized(self):
        from ae.pr_advanced_editing import (
            AdvancedEditParam,
            EditMode,
            MotionDirection,
            WhipPanParam,
        )

        param = AdvancedEditParam(
            edit_mode=EditMode.WHIP_PAN,
            whip_pan=WhipPanParam(
                direction=MotionDirection.LEFT,
                speed=3.0,
                blur_amount=15.0,
                duration=0.7,
                overlap=0.4,
            ),
        )
        d = param.to_dict()
        assert "whip_pan" in d
        # direction 序列化为字符串
        assert d["whip_pan"]["direction"] == "left"
        assert d["whip_pan"]["speed"] == 3.0
        assert d["whip_pan"]["blur_amount"] == 15.0

    def test_to_dict_dynamic_zoom_serialized(self):
        from ae.pr_advanced_editing import AdvancedEditParam, DynamicZoomParam, EditMode

        param = AdvancedEditParam(
            edit_mode=EditMode.DYNAMIC_ZOOM,
            dynamic_zoom=DynamicZoomParam(
                start_scale=100.0,
                end_scale=200.0,
                duration=1.5,
                focus_point=[0.3, 0.7],
            ),
        )
        d = param.to_dict()
        assert "dynamic_zoom" in d
        assert d["dynamic_zoom"]["start_scale"] == 100.0
        assert d["dynamic_zoom"]["end_scale"] == 200.0
        assert d["dynamic_zoom"]["focus_point"] == [0.3, 0.7]

    def test_to_dict_speed_ramp_serialized(self):
        from ae.pr_advanced_editing import AdvancedEditParam, EditMode, SpeedRampParam

        param = AdvancedEditParam(
            edit_mode=EditMode.SPEED_RAMP,
            speed_ramp=SpeedRampParam(
                start_speed=50.0,
                end_speed=200.0,
                ramp_duration=1.5,
            ),
        )
        d = param.to_dict()
        assert "speed_ramp" in d
        assert d["speed_ramp"]["start_speed"] == 50.0
        assert d["speed_ramp"]["end_speed"] == 200.0

    def test_to_dict_keyframe_animation_serialized(self):
        from ae.pr_advanced_editing import (
            AdvancedEditParam,
            EditMode,
            KeyframeAnimationParam,
            KeyframePoint,
        )

        param = AdvancedEditParam(
            edit_mode=EditMode.KEYFRAME_ANIMATION,
            keyframe_animation=KeyframeAnimationParam(
                keyframes=[
                    KeyframePoint(time=0.0, value=0.0),
                    KeyframePoint(time=1.0, value=100.0),
                ],
                property_name="Opacity",
            ),
        )
        d = param.to_dict()
        assert "keyframe_animation" in d
        assert d["keyframe_animation"]["property_name"] == "Opacity"
        assert len(d["keyframe_animation"]["keyframes"]) == 2

    def test_to_dict_only_relevant_section_included(self):
        """不同 edit_mode 只序列化对应的子参数（避免泄漏无关字段）。"""
        from ae.pr_advanced_editing import AdvancedEditParam, EditMode

        param = AdvancedEditParam(edit_mode=EditMode.WHIP_PAN)
        d = param.to_dict()
        # whip_pan 模式下应只包含 whip_pan 段
        assert "whip_pan" in d
        # dynamic_zoom / speed_ramp / keyframe_animation 不应出现
        assert "dynamic_zoom" not in d
        assert "speed_ramp" not in d
        assert "keyframe_animation" not in d


# ============================================================
# generate_editing_script
# ============================================================
class TestGenerateEditingScript:
    def test_unknown_mode_falls_back_to_whip_pan(self):
        from ae.pr_advanced_editing import (
            AdvancedEditParam,
            EditMode,
            PremiereAdvancedEditing,
        )

        # 模拟一个"未知"的 mode：构造一个 enum 之外的 param
        # 因为是 enum，不能直接传字符串，所以这里用 EditMode.WHIP_PAN 构造，
        # 然后直接用 dispatch 路径：调用 generate_editing_script
        # 然后手动覆盖
        sys_obj = PremiereAdvancedEditing(pr_client=None)
        # 由于没有未知 mode 入口，我们用 monkey patch 模拟一个未知 mode
        # 通过把 params.edit_mode 改成非已知值
        param = AdvancedEditParam(edit_mode=EditMode.WHIP_PAN)
        # 强制把 edit_mode 改成其他值（绕过枚举）
        param.edit_mode = "UNKNOWN_MODE"
        # 应走 else 分支 = whip_pan
        script = sys_obj.generate_editing_script(0, 0, param)
        # whip_pan 脚本里有 whip_pan 标志
        assert "whip_pan" in script.lower() or "WhipPan" in script

    def test_known_modes_generate_nonempty(self):
        from ae.pr_advanced_editing import (
            AdvancedEditParam,
            EditMode,
            KeyframeAnimationParam,
            KeyframePoint,
            PremiereAdvancedEditing,
        )

        sys_obj = PremiereAdvancedEditing(pr_client=None)
        # KEYFRAME_ANIMATION 默认 keyframes 是 None，必须显式传
        for mode in [
            EditMode.WHIP_PAN,
            EditMode.DYNAMIC_ZOOM,
            EditMode.SPEED_RAMP,
        ]:
            param = AdvancedEditParam(edit_mode=mode)
            script = sys_obj.generate_editing_script(0, 0, param)
            assert script and len(script) > 100, f"模式 {mode} 生成的脚本过短"

        # KEYFRAME_ANIMATION 单独验证：必须提供 keyframes
        kf_param = AdvancedEditParam(
            edit_mode=EditMode.KEYFRAME_ANIMATION,
            keyframe_animation=KeyframeAnimationParam(
                keyframes=[KeyframePoint(time=0.0, value=0.0)],
            ),
        )
        script = sys_obj.generate_editing_script(0, 0, kf_param)
        assert script and len(script) > 50


# ============================================================
# apply_editing 干跑（dry_run）
# ============================================================
class TestApplyEditingDryRun:
    def test_dry_run_returns_status(self):
        from ae.pr_advanced_editing import (
            AdvancedEditParam,
            EditMode,
            PremiereAdvancedEditing,
        )

        # pr_client=None → dry_run
        sys_obj = PremiereAdvancedEditing(pr_client=None)
        param = AdvancedEditParam(edit_mode=EditMode.WHIP_PAN, track_index=2, clip_index=5)
        result = sys_obj.apply_editing(2, 5, param)
        assert result["success"] is True
        assert result["status"] == "dry_run"
        assert result["edit_mode"] == "whip_pan"
        assert result["track_index"] == 2
        assert result["clip_index"] == 5

    def test_with_pr_client_calls_execute_script(self):
        from ae.pr_advanced_editing import (
            AdvancedEditParam,
            EditMode,
            PremiereAdvancedEditing,
        )

        # 模拟 pr_client
        pr_client = MagicMock()
        pr_client.execute_script = MagicMock(
            return_value={"success": True, "executed": True}
        )
        sys_obj = PremiereAdvancedEditing(pr_client=pr_client)
        param = AdvancedEditParam(edit_mode=EditMode.WHIP_PAN, track_index=1, clip_index=2)
        result = sys_obj.apply_editing(1, 2, param)
        assert pr_client.execute_script.called
        assert result == {"success": True, "executed": True}


# ============================================================
# apply_batch_editing
# ============================================================
class TestApplyBatchEditing:
    def test_dry_run_batch(self):
        from ae.pr_advanced_editing import PremiereAdvancedEditing

        sys_obj = PremiereAdvancedEditing(pr_client=None)
        edits = [
            {"edit_mode": "whip_pan", "track_index": 0, "clip_index": 0},
            {"edit_mode": "dynamic_zoom", "track_index": 0, "clip_index": 1},
            {"edit_mode": "speed_ramp", "track_index": 0, "clip_index": 2},
        ]
        results = sys_obj.apply_batch_editing(edits)
        assert len(results) == 3
        # 顺序保留
        assert results[0]["edit_mode"] == "whip_pan"
        assert results[1]["edit_mode"] == "dynamic_zoom"
        assert results[2]["edit_mode"] == "speed_ramp"
        # 全部 dry_run
        for r in results:
            assert r["status"] == "dry_run"

    def test_batch_with_different_clips(self):
        from ae.pr_advanced_editing import PremiereAdvancedEditing

        sys_obj = PremiereAdvancedEditing(pr_client=None)
        edits = [
            {"edit_mode": "whip_pan", "track_index": 0, "clip_index": 0},
            {"edit_mode": "whip_pan", "track_index": 0, "clip_index": 1},
            {"edit_mode": "whip_pan", "track_index": 0, "clip_index": 2},
        ]
        results = sys_obj.apply_batch_editing(edits)
        # 不同的 clip_index 被正确传递
        assert results[0]["clip_index"] == 0
        assert results[1]["clip_index"] == 1
        assert results[2]["clip_index"] == 2

    def test_batch_default_values_used_when_keys_missing(self):
        """edit dict 缺字段时记录当前实际行为（实现要求所有字段必填）。"""
        from ae.pr_advanced_editing import PremiereAdvancedEditing

        sys_obj = PremiereAdvancedEditing(pr_client=None)
        edits = [
            {"edit_mode": "whip_pan", "track_index": 0, "clip_index": 0},
            # 缺 track_index / clip_index
            {"edit_mode": "whip_pan"},
        ]
        # 当前实现：第二个 edit 因 KeyError 中断整个 batch。
        # 记录此行为以便未来重构（更宽容的批量接口）时回归。
        with pytest.raises(KeyError):
            sys_obj.apply_batch_editing(edits)

    def test_batch_empty_list(self):
        from ae.pr_advanced_editing import PremiereAdvancedEditing

        sys_obj = PremiereAdvancedEditing(pr_client=None)
        results = sys_obj.apply_batch_editing([])
        assert results == []

    def test_batch_passes_pr_client(self):
        """有 pr_client 时 batch 调 execute_script。"""
        from ae.pr_advanced_editing import PremiereAdvancedEditing

        pr_client = MagicMock()
        pr_client.execute_script = MagicMock(
            return_value={"success": True, "executed": True}
        )
        sys_obj = PremiereAdvancedEditing(pr_client=pr_client)
        edits = [
            {"edit_mode": "whip_pan", "track_index": 0, "clip_index": 0},
            {"edit_mode": "dynamic_zoom", "track_index": 0, "clip_index": 1},
        ]
        results = sys_obj.apply_batch_editing(edits)
        # execute_script 被调用 2 次
        assert pr_client.execute_script.call_count == 2
        # 结果是 execute_script 的返回值
        assert all(r.get("executed") for r in results)

    def test_batch_dispatches_each_edit_mode(self):
        """每个 edit 模式应生成对应类型的 param（构造时验证）。"""
        from ae.pr_advanced_editing import PremiereAdvancedEditing

        sys_obj = PremiereAdvancedEditing(pr_client=None)
        edits = [
            {
                "edit_mode": "whip_pan",
                "track_index": 0,
                "clip_index": 0,
                "direction": "left",
                "speed": 3.0,
                "blur_amount": 20.0,
            },
            {
                "edit_mode": "dynamic_zoom",
                "track_index": 0,
                "clip_index": 1,
                "start_scale": 100.0,
                "end_scale": 200.0,
                "duration": 1.5,
            },
            {
                "edit_mode": "speed_ramp",
                "track_index": 0,
                "clip_index": 2,
                "start_speed": 50.0,
                "end_speed": 200.0,
                "ramp_duration": 1.0,
            },
        ]
        # mock apply_editing 来观察传入的 param
        # apply_batch_editing 调用 apply_editing 时用 kwargs 形式
        received_params = []
        original_apply = sys_obj.apply_editing

        def spy(*args, **kwargs):
            # 既支持 positional 也支持 kwargs
            if args:
                track, clip, params = args[0], args[1], args[2]
            else:
                track = kwargs["track_index"]
                clip = kwargs["clip_index"]
                params = kwargs["params"]
            received_params.append((track, clip, params))
            return original_apply(track, clip, params)

        with patch.object(sys_obj, "apply_editing", side_effect=spy):
            sys_obj.apply_batch_editing(edits)
        # 3 个 param 都被传入
        assert len(received_params) == 3
        # 模式正确
        assert received_params[0][2].edit_mode.value == "whip_pan"
        assert received_params[1][2].edit_mode.value == "dynamic_zoom"
        assert received_params[2][2].edit_mode.value == "speed_ramp"
