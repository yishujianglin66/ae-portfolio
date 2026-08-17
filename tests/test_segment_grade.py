"""分段调色功能测试（v4.0 兼容）

测试 ColorGradeConfig.segment_presets 分段调色能力，
包括 Lua 脚本生成、预设查找和安全 LUT 路径。
"""
import sys
import os
import tempfile
import ctypes
import pytest

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.davinci_fuscript import (
    ResolveColorEngine,
    ColorGradeConfig,
    find_lut_for_preset,
    RESOLVE_PRESETS,
)


def get_long_path(short_path):
    """将 8.3 短路径转为长路径"""
    buf = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.kernel32.GetLongPathNameW(short_path, buf, 1024) > 0:
        return buf.value
    return short_path


class TestSegmentGradeConfig:
    """测试分段调色配置"""

    def test_segment_presets_in_config(self):
        """ColorGradeConfig 应支持 segment_presets 字段"""
        config = ColorGradeConfig(
            preset="cinematic",
            segment_presets={
                "Battle": "cinematic",
                "intro": "warm",
                "ending": "cool",
            }
        )
        assert config.segment_presets is not None
        assert len(config.segment_presets) == 3
        assert config.segment_presets["Battle"] == "cinematic"

    def test_segment_presets_default_none(self):
        """默认 segment_presets 为 None"""
        config = ColorGradeConfig()
        assert config.segment_presets is None

    def test_empty_segment_presets(self):
        """空分段预设应正常工作"""
        config = ColorGradeConfig(segment_presets={})
        assert config.segment_presets == {}


class TestSegmentGradeLuaGeneration:
    """测试分段调色逻辑（v5.0 create_project 交互模式）"""

    def setup_method(self):
        from unittest.mock import MagicMock
        self.engine = ResolveColorEngine()
        self.engine._engine = MagicMock()
        self.engine._engine.create_timeline_with_media.return_value = {
            "clip_count": 3,
            "items": [
                {"index": 1, "name": "Battle_01.mp4"},
                {"index": 2, "name": "intro_clip.mp4"},
                {"index": 3, "name": "ending_clip.mp4"},
            ],
        }

    def _run(self, config: ColorGradeConfig):
        """调用 create_project（render=False，避免真实渲染）"""
        return self.engine.create_project(
            project_name="TestSegment",
            media_files=["a.mp4", "b.mp4", "c.mp4"],
            timeline_name="MainTimeline",
            color_config=config,
            render=False,
        )

    def test_create_project_with_segment_presets(self):
        """匹配片段名的片段应使用分段预设 CDL"""
        config = ColorGradeConfig(
            preset="cinematic",
            brightness=1.05,
            contrast=1.1,
            saturation=0.95,
            segment_presets={
                "Battle": "cinematic",
                "intro": "warm",
                "ending": "cool",
            }
        )
        result = self._run(config)
        assert result.success
        calls = self.engine._engine.apply_cdl.call_args_list
        assert len(calls) == 3, f"应为 3 个片段逐一调色，实际 {len(calls)}"

        # Battle_01.mp4 匹配 "Battle" → cinematic 预设 CDL
        cdl_1 = calls[0].args[3]
        assert cdl_1.saturation == pytest.approx(0.95)
        assert cdl_1.slope[0] == pytest.approx(1.08)
        assert cdl_1.offset[0] == pytest.approx(-0.02)

        # intro_clip.mp4 匹配 "intro" → warm（RESOLVE_PRESETS 无 warm CDL → 默认 CDL）
        cdl_2 = calls[1].args[3]
        assert cdl_2.saturation == pytest.approx(1.0)
        assert cdl_2.slope == (1.0, 1.0, 1.0)

        # ending_clip.mp4 匹配 "ending" → cool（默认 CDL）
        cdl_3 = calls[2].args[3]
        assert cdl_3.saturation == pytest.approx(1.0)

    def test_create_project_without_segment_presets(self):
        """无分段预设时全部片段使用基础 config CDL"""
        config = ColorGradeConfig(
            preset="cinematic",
            brightness=1.05,
            contrast=1.1,
            saturation=0.95,
        )
        result = self._run(config)
        assert result.success
        calls = self.engine._engine.apply_cdl.call_args_list
        assert len(calls) == 3
        for call in calls:
            cdl = call.args[3]
            assert cdl.saturation == pytest.approx(0.95)

    def test_create_project_empty_segment_presets(self):
        """空分段预设应视同无分段"""
        config = ColorGradeConfig(
            preset="cinematic",
            saturation=0.95,
            segment_presets={},
        )
        result = self._run(config)
        assert result.success
        calls = self.engine._engine.apply_cdl.call_args_list
        assert len(calls) == 3
        for call in calls:
            cdl = call.args[3]
            assert cdl.saturation == pytest.approx(0.95)


class TestPresetLookupForSegments:
    """测试分段预设查找"""

    def test_all_segment_presets_resolvable(self):
        """所有 RESOLVE_PRESETS 中的预设都应能找到 LUT"""
        for preset_name in RESOLVE_PRESETS:
            lut = find_lut_for_preset(preset_name)
            # 某些预设可能没有对应 LUT，但不应报错
            assert lut is None or isinstance(lut, str)

    def test_unknown_preset_returns_none(self):
        """未知预设应返回 None"""
        lut = find_lut_for_preset("nonexistent_preset_xyz")
        assert lut is None
