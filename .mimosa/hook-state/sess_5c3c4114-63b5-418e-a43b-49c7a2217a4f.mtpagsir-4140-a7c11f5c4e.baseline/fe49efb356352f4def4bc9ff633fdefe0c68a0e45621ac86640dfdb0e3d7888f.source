"""
DaVinci Resolve Color 页面调色自动化 — 单元测试
========================================

覆盖 ``integrations.davinci_color_grading`` 和 ``integrations.color_presets`` 的核心能力：

- 数据结构序列化（``ColorWheelValues``、``ColorGradingPreset``）
- 枚举与常量
- ``ColorGrader`` 全功能（色轮/节点/曲线/Qualifier/LUT/批量）
- 内置预设库加载
- 预设 JSON 落盘/读取
- 异常路径
- Lua 桥接脚本生成

使用 ``unittest.mock.MagicMock`` 模拟 Resolve 顶层对象，确保测试无需
真实 DaVinci Resolve 环境即可运行。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from integrations.davinci_color_grading import (  # noqa: E402
    CURVE_TYPES,
    NODE_TYPE_LAYER,
    NODE_TYPE_OUTSIDE,
    NODE_TYPE_PARALLEL,
    NODE_TYPE_SERIAL,
    ColorBalanceType,
    ColorGrader,
    ColorGradingPreset,
    ColorGradingError,
    ColorWheelChannel,
    ColorWheelValues,
    CurveType,
    NodeType,
    ResolveNotFoundError,
    InvalidNodeError,
)
from integrations.color_presets import (  # noqa: E402
    BUILTIN_PRESETS,
    PRESETS_DIR,
    export_all_builtin_presets,
    get_preset,
    get_preset_file_path,
    list_preset_names,
    list_presets,
    load_preset_from_file,
    presets_by_tag,
    save_preset_to_file,
)
from integrations.davinci_color_lua import (  # noqa: E402
    build_apply_lut_lua,
    build_apply_preset_lua,
    build_batch_grade_lua,
    build_custom_curve_lua,
    build_export_lut_lua,
    build_full_grading_lua,
    build_node_management_lua,
    build_qualifier_lua,
    build_set_color_wheel_lua,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_resolve():
    """构造一个 Mock Resolve 顶层对象 + 返回关键的内部 mock。"""
    resolve = MagicMock()
    resolve.GetProductName.return_value = "DaVinci Resolve Studio (Mock)"

    project = MagicMock()
    timeline = MagicMock()
    item = MagicMock()

    # 节点与色轮默认值
    item.GetNodeColorWheels.return_value = {
        "Red": 0.0, "Green": 0.0, "Blue": 0.0, "Master": 0.0,
    }
    item.GetNumNodes.return_value = 1
    item.AddNode.return_value = 1
    item.DeleteNode.return_value = True
    item.SetNodeOpacity.return_value = True
    item.SetNodeLabel.return_value = True
    item.SetSaturation.return_value = True
    item.SetContrast.return_value = True
    item.SetPivot.return_value = True
    item.SetCustomCurve.return_value = True
    item.GetCustomCurve.return_value = [0.0, 0.0, 1.0, 1.0]
    item.SetQualifier.return_value = True
    item.SetLUT.return_value = True
    item.ExportLUT.return_value = True
    item.GetSaturation.return_value = 1.0
    item.GetContrast.return_value = 1.0

    timeline.GetItemListInTrack.return_value = [item, item, item, item]
    project.GetCurrentTimeline.return_value = timeline
    project.GetCurrentProject.return_value = project

    pm = MagicMock()
    pm.GetCurrentProject.return_value = project
    pm.LoadProject.return_value = project
    resolve.GetProjectManager.return_value = pm

    return resolve, item, timeline


@pytest.fixture
def grader(mock_resolve):
    """构造一个绑定到 Mock Resolve 的 ColorGrader。"""
    resolve, _, _ = mock_resolve
    return ColorGrader(resolve=resolve)


# ============================================================================
# 数据结构测试
# ============================================================================

class TestColorWheelValues:
    def test_defaults(self):
        cw = ColorWheelValues()
        assert cw.red == 0.0 and cw.green == 0.0
        assert cw.is_neutral()

    def test_to_dict_rgb(self):
        cw = ColorWheelValues(red=0.1, green=0.2, blue=0.3, master=0.05)
        d = cw.to_dict(ColorBalanceType.RGB)
        assert d == {"Red": 0.1, "Green": 0.2, "Blue": 0.3, "Master": 0.05}

    def test_to_dict_hsl(self):
        cw = ColorWheelValues(red=180.0, green=0.5, blue=0.7, master=0.1)
        d = cw.to_dict(ColorBalanceType.HSL)
        assert d == {"Hue": 180.0, "Saturation": 0.5, "Luminance": 0.7, "Master": 0.1}

    def test_from_dict_roundtrip_rgb(self):
        d = {"Red": 0.1, "Green": -0.2, "Blue": 0.3, "Master": 0.0}
        cw = ColorWheelValues.from_dict(d, ColorBalanceType.RGB)
        assert cw.red == 0.1 and cw.green == -0.2 and cw.blue == 0.3

    def test_from_dict_roundtrip_hsl(self):
        d = {"Hue": 90.0, "Saturation": 0.4, "Luminance": 0.6, "Master": 0.05}
        cw = ColorWheelValues.from_dict(d, ColorBalanceType.HSL)
        assert cw.red == 90.0 and cw.green == 0.4 and cw.blue == 0.6

    def test_from_dict_empty(self):
        cw = ColorWheelValues.from_dict({}, ColorBalanceType.RGB)
        assert cw.is_neutral()

    def test_is_neutral_tolerance(self):
        cw = ColorWheelValues(red=1e-9, green=-1e-9)
        assert cw.is_neutral(tolerance=1e-6)
        cw2 = ColorWheelValues(red=0.01)
        assert not cw2.is_neutral()


class TestColorGradingPreset:
    def test_defaults(self):
        p = ColorGradingPreset(name="x")
        assert p.saturation == 1.0
        assert p.contrast == 1.0
        assert p.pivot == 0.435
        assert p.lift.is_neutral()
        assert p.tags == []

    def test_to_dict(self):
        p = ColorGradingPreset(
            name="Test",
            description="demo",
            lift=ColorWheelValues(red=0.01, blue=-0.02),
            saturation=1.1,
            tags=["a", "b"],
        )
        d = p.to_dict()
        assert d["name"] == "Test"
        assert d["saturation"] == 1.1
        assert d["lift"]["Red"] == 0.01
        assert d["lift"]["Blue"] == -0.02
        assert d["tags"] == ["a", "b"]

    def test_from_dict_roundtrip(self):
        original = ColorGradingPreset(
            name="RT",
            lift=ColorWheelValues(red=0.05, green=-0.03, blue=0.02, master=0.01),
            gamma=ColorWheelValues(red=-0.02, blue=0.04),
            gain=ColorWheelValues(red=0.1, green=0.0, blue=-0.1),
            offset=ColorWheelValues(),
            saturation=1.25,
            contrast=1.15,
            pivot=0.5,
            highlight_saturation=1.1,
            shadow_saturation=0.9,
            blend_opacity=0.8,
            tags=["x", "y"],
        )
        restored = ColorGradingPreset.from_dict(original.to_dict())
        assert restored.name == "RT"
        assert restored.saturation == 1.25
        assert restored.lift.red == 0.05
        assert restored.lift.green == -0.03
        assert restored.lift.master == 0.01
        assert restored.gain.blue == -0.1
        assert restored.blend_opacity == 0.8
        assert restored.tags == ["x", "y"]

    def test_summary(self):
        p = ColorGradingPreset(name="T", saturation=1.1, contrast=1.05, tags=["x"])
        s = p.summary()
        assert "T" in s and "1.10" in s and "x" in s

    def test_json_roundtrip(self):
        p = ColorGradingPreset(name="Json", lift=ColorWheelValues(red=0.1))
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "p.json"
            f.write_text(json.dumps(p.to_dict()), encoding="utf-8")
            data = json.loads(f.read_text(encoding="utf-8"))
            restored = ColorGradingPreset.from_dict(data)
            assert restored.lift.red == 0.1


# ============================================================================
# 枚举与常量
# ============================================================================

class TestEnums:
    def test_color_wheel_channel_values(self):
        assert ColorWheelChannel.LIFT.value == "Lift"
        assert ColorWheelChannel.GAMMA.value == "Gamma"
        assert ColorWheelChannel.GAIN.value == "Gain"
        assert ColorWheelChannel.OFFSET.value == "Offset"
        assert ColorWheelChannel.SATURATION.value == "Saturation"

    def test_node_type_values(self):
        assert NodeType.SERIAL.value == NODE_TYPE_SERIAL
        assert NodeType.PARALLEL.value == NODE_TYPE_PARALLEL
        assert NodeType.LAYER.value == NODE_TYPE_LAYER
        assert NodeType.KEY.value == 3
        assert NodeType.OUTSIDE.value == NODE_TYPE_OUTSIDE
        assert NodeType.PARALLEL.label == "parallel"

    def test_curve_type_values(self):
        assert CurveType.CUSTOM.value == "Custom"
        assert CurveType.HUE_VS_HUE.value == "HueVsHue"
        for ct in CurveType:
            assert ct.value in CURVE_TYPES

    def test_color_balance_type_values(self):
        assert ColorBalanceType.RGB.value == "rgb"
        assert ColorBalanceType.HSL.value == "hsl"
        assert ColorBalanceType.YRGB.value == "yrgb"


# ============================================================================
# ColorGrader 初始化
# ============================================================================

class TestColorGraderInit:
    def test_init_with_resolve(self, mock_resolve):
        resolve, _, _ = mock_resolve
        grader = ColorGrader(resolve=resolve)
        assert grader.resolve is resolve

    def test_init_with_none_raises(self, monkeypatch):
        # 模拟两端都不可用
        monkeypatch.setattr(
            "integrations.davinci_color_grading.HAS_RESOLVE_API", False
        )
        with pytest.raises(ResolveNotFoundError):
            ColorGrader(resolve=None)

    def test_init_validates_resolve(self):
        bad = MagicMock()
        # GetProductName 抛错
        bad.GetProductName.side_effect = RuntimeError("nope")
        with pytest.raises(ResolveNotFoundError):
            ColorGrader(resolve=bad)

    def test_init_with_none_resolve_obj(self):
        # 构造一个没有任何 Resolve API 属性的对象
        class _Bad:
            pass
        with pytest.raises(ResolveNotFoundError):
            ColorGrader(resolve=_Bad())


# ============================================================================
# 色轮控制
# ============================================================================

class TestColorWheelControl:
    def test_set_color_wheel(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        values = ColorWheelValues(red=0.1, green=-0.05, blue=0.2, master=0.02)
        ok = grader.set_color_wheel(0, 0, ColorWheelChannel.LIFT, values)
        assert ok is True
        item.SetNodeColorWheels.assert_called()

    def test_set_color_wheel_hsl(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        values = ColorWheelValues(red=180.0, green=0.5, blue=0.7)
        grader.set_color_wheel(0, 0, ColorWheelChannel.LIFT, values, ColorBalanceType.HSL)
        # 第一次参数应该是 (0, "Lift", "hsl", dict)
        args, _ = item.SetNodeColorWheels.call_args
        assert args[0] == 0
        assert args[1] == "Lift"
        assert args[2] == "hsl"
        assert "Hue" in args[3]

    def test_get_color_wheel(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        item.GetNodeColorWheels.return_value = {
            "Red": 0.1, "Green": 0.2, "Blue": 0.3, "Master": 0.0,
        }
        values = grader.get_color_wheel(0, 0, ColorWheelChannel.GAIN)
        assert values.red == 0.1
        assert values.green == 0.2
        assert values.blue == 0.3

    def test_apply_preset(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        preset = ColorGradingPreset(
            name="P",
            lift=ColorWheelValues(red=0.01),
            gamma=ColorWheelValues(green=0.02),
            gain=ColorWheelValues(blue=0.03),
            offset=ColorWheelValues(master=0.04),
            saturation=1.1,
            contrast=1.05,
            pivot=0.45,
            blend_opacity=0.9,
        )
        ok = grader.apply_preset(0, 0, preset)
        assert ok is True
        # 4 个色轮 + saturation + contrast + pivot + opacity
        assert item.SetNodeColorWheels.call_count >= 4
        item.SetSaturation.assert_called_with(1.1, 0)
        item.SetContrast.assert_called_with(1.05, 0)
        item.SetPivot.assert_called_with(0.45, 0)
        item.SetNodeOpacity.assert_called_with(0, 0.9)

    def test_save_preset_from_node(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        item.GetNodeColorWheels.return_value = {
            "Red": 0.05, "Green": -0.05, "Blue": 0.0, "Master": 0.0,
        }
        item.GetSaturation.return_value = 1.2
        item.GetContrast.return_value = 1.1
        preset = grader.save_preset_from_node(0, 0, "Saved", "from node")
        assert preset.name == "Saved"
        assert preset.saturation == 1.2
        assert preset.contrast == 1.1


# ============================================================================
# 节点图管理
# ============================================================================

class TestNodeGraph:
    def test_add_node(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        item.AddNode.return_value = 5
        idx = grader.add_node(0, NodeType.PARALLEL, label="PQ")
        assert idx == 5
        item.AddNode.assert_called_with(NODE_TYPE_PARALLEL)
        item.SetNodeLabel.assert_called_with(5, "PQ")

    def test_add_node_without_label(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        item.AddNode.return_value = 2
        idx = grader.add_node(0, NodeType.LAYER)
        assert idx == 2
        item.SetNodeLabel.assert_not_called()

    def test_add_node_failure(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        item.AddNode.return_value = -1
        with pytest.raises(ColorGradingError):
            grader.add_node(0, NodeType.SERIAL)

    def test_delete_node(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        ok = grader.delete_node(0, 1)
        assert ok is True
        item.DeleteNode.assert_called_with(1)

    def test_set_node_opacity(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        ok = grader.set_node_opacity(0, 1, 0.5)
        assert ok is True
        item.SetNodeOpacity.assert_called_with(1, 0.5)

    def test_set_node_label(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        ok = grader.set_node_label(0, 1, "MyLabel")
        assert ok is True
        item.SetNodeLabel.assert_called_with(1, "MyLabel")

    def test_get_node_count(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        item.GetNumNodes.return_value = 7
        assert grader.get_node_count(0) == 7

    def test_clip_out_of_range(self, grader, mock_resolve):
        _, _, _ = mock_resolve
        with pytest.raises(InvalidNodeError):
            grader.set_color_wheel(99, 0, ColorWheelChannel.LIFT, ColorWheelValues())


# ============================================================================
# 自定义曲线
# ============================================================================

class TestCustomCurves:
    def test_set_custom_curve(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        ok = grader.set_custom_curve(0, 0, CurveType.CUSTOM, [0.0, 0.0, 1.0, 1.0])
        assert ok is True
        item.SetCustomCurve.assert_called_with(0, "Custom", [0.0, 0.0, 1.0, 1.0])

    def test_set_curve_string_type(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        ok = grader.set_custom_curve(0, 0, "HueVsHue", [0.0, 0.0, 0.5, 0.6])
        assert ok is True
        item.SetCustomCurve.assert_called_with(0, "HueVsHue", [0.0, 0.0, 0.5, 0.6])

    def test_set_invalid_curve(self, grader):
        with pytest.raises(ColorGradingError):
            grader.set_custom_curve(0, 0, "BadType", [])

    def test_add_curve_point(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        # 默认 mock 返回 [0,0,1,1]
        ok = grader.add_curve_point(0, 0, CurveType.CUSTOM, 0.5, 0.6)
        assert ok is True
        # 验证 SetCustomCurve 被以 6 个点调用
        args, _ = item.SetCustomCurve.call_args
        assert args[0] == 0 and args[1] == "Custom"
        assert len(args[2]) == 6

    def test_reset_curve(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        ok = grader.reset_curve(0, 0, CurveType.CUSTOM)
        assert ok is True
        item.SetCustomCurve.assert_called_with(0, "Custom", [])

    def test_get_custom_curve(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        item.GetCustomCurve.return_value = [0.0, 0.0, 0.5, 0.5]
        pts = grader.get_custom_curve(0, 0, CurveType.CUSTOM)
        assert pts == [0.0, 0.0, 0.5, 0.5]


# ============================================================================
# Qualifier
# ============================================================================

class TestQualifier:
    def test_select_with_qualifier(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        ok = grader.select_with_qualifier(
            clip_index=0, node_index=0,
            hue_range=(180.0, 240.0),
            sat_range=(0.3, 0.9),
            lum_range=(0.2, 0.8),
        )
        assert ok is True
        item.SetQualifier.assert_called_once()
        args = item.SetQualifier.call_args[0]
        qual = args[1]
        assert qual["Hue"]["min"] == 180.0
        assert qual["Hue"]["max"] == 240.0
        assert qual["Sat"]["max"] == 0.9

    def test_invert_selection(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        ok = grader.invert_selection(0, 0)
        assert ok is True
        item.InvertQualifierSelection.assert_called_with(0)

    def test_invert_unavailable(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        del item.InvertQualifierSelection
        assert grader.invert_selection(0, 0) is False


# ============================================================================
# LUT
# ============================================================================

class TestLUT:
    def test_apply_lut(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        ok = grader.apply_lut(0, 0, "C:/Luts/test.cube")
        assert ok is True
        item.SetLUT.assert_called_with(0, "C:/Luts/test.cube")

    def test_apply_lut_copies_non_ascii_path(self, grader, mock_resolve, tmp_path):
        _, item, _ = mock_resolve
        src = tmp_path / "lut_中文.cube"
        src.write_text("# test")
        ok = grader.apply_lut(0, 0, str(src))
        assert ok is True
        # 实际路径应不再是中文路径
        called_path = item.SetLUT.call_args[0][1]
        assert called_path.encode("ascii", errors="strict") == called_path.encode("utf-8")

    def test_export_lut(self, grader, mock_resolve, tmp_path):
        _, item, _ = mock_resolve
        out = tmp_path / "out.cube"
        ok = grader.export_lut(0, 0, out, cube_size=17)
        assert ok is True
        item.ExportLUT.assert_called_with(0, str(out), 17)


# ============================================================================
# 批量调色
# ============================================================================

class TestBatchGrade:
    def test_grade_clip_range(self, grader, mock_resolve):
        _, _, _ = mock_resolve
        preset = ColorGradingPreset(
            name="B",
            lift=ColorWheelValues(red=0.01, blue=-0.01),
            gamma=ColorWheelValues(red=0.02),
            gain=ColorWheelValues(red=0.03),
            offset=ColorWheelValues(),
        )
        results = grader.grade_clip_range([0, 1, 2], node_index=0, preset=preset)
        assert results == {0: True, 1: True, 2: True}

    def test_copy_grading(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        item.GetNodeColorWheels.return_value = {
            "Red": 0.05, "Green": -0.03, "Blue": 0.02, "Master": 0.0,
        }
        results = grader.copy_grading(0, [1, 2, 3], node_index=0)
        assert 1 in results and 2 in results and 3 in results


# ============================================================================
# 预设文件 IO
# ============================================================================

class TestPresetIO:
    def test_save_and_load(self, grader, tmp_path):
        preset = ColorGradingPreset(name="IO", lift=ColorWheelValues(red=0.05))
        f = tmp_path / "io.json"
        grader.save_preset_to_file(preset, f)
        loaded = grader.load_preset_from_file(f)
        assert loaded.name == "IO"
        assert loaded.lift.red == 0.05

    def test_load_nonexistent(self, grader, tmp_path):
        with pytest.raises(FileNotFoundError):
            grader.load_preset_from_file(tmp_path / "missing.json")

    def test_load_from_default_dir(self, grader, tmp_path):
        # 应能在默认预设目录找到内置 preset
        for name in list_preset_names():
            f = get_preset_file_path(name)
            if f is None:
                continue
            loaded = load_preset_from_file(f)
            assert loaded.name == get_preset(name).name


# ============================================================================
# 色彩空间
# ============================================================================

class TestColorSpace:
    def test_set_color_space(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        # Mock 没有 SetColorSpace 方法（用 type(item).SetColorSpace 屏蔽 MagicMock 自动创建）
        item.SetColorSpace = None
        ok = grader.set_color_space(0, 0, "Rec.2020", "Rec.709")
        assert ok is True
        item.SetNodeLabel.assert_called()
        # 标签应包含色彩空间信息
        label_arg = item.SetNodeLabel.call_args[0][1]
        assert "Rec.2020" in label_arg and "Rec.709" in label_arg

    def test_set_color_space_native(self, grader, mock_resolve):
        _, item, _ = mock_resolve
        # 增加 SetColorSpace 模拟原生 API
        item.SetColorSpace = MagicMock(return_value=True)
        ok = grader.set_color_space(0, 0, "Rec.2020", "Rec.709")
        assert ok is True
        item.SetColorSpace.assert_called_with(0, "Rec.2020", "Rec.709")


# ============================================================================
# 内置预设库
# ============================================================================

class TestBuiltinPresets:
    def test_at_least_six(self):
        assert len(BUILTIN_PRESETS) >= 6, f"only {len(BUILTIN_PRESETS)} presets"

    def test_list_preset_names(self):
        names = list_preset_names()
        assert "cinematic_teal_orange" in names
        assert "vintage_film" in names
        assert "high_key_bright" in names
        assert "low_key_dark" in names
        assert "music_video_punch" in names
        assert "black_and_white_classic" in names

    def test_get_preset_returns_dataclass(self):
        p = get_preset("cinematic_teal_orange")
        assert p is not None
        assert isinstance(p, ColorGradingPreset)
        assert p.name == "Cinematic Teal & Orange"

    def test_get_preset_missing(self):
        assert get_preset("not_a_preset") is None

    def test_presets_by_tag(self):
        cinematic = presets_by_tag("cinematic")
        assert any(p.name == "Cinematic Teal & Orange" for p in cinematic)
        bw = presets_by_tag("noir")
        assert any(p.name == "Black & White Classic" for p in bw)

    def test_bw_preset_is_neutral_wheels(self):
        bw = get_preset("black_and_white_classic")
        assert bw.saturation == 0.0
        assert bw.lift.is_neutral()
        assert bw.gain.is_neutral()

    def test_builtin_presets_have_tags(self):
        for name, p in BUILTIN_PRESETS.items():
            assert p.tags, f"preset {name} has no tags"

    def test_export_all_builtin(self, tmp_path):
        out_dir = tmp_path / "exported"
        written = export_all_builtin_presets(out_dir)
        assert len(written) >= 6
        for p in written:
            assert p.exists() and p.stat().st_size > 0


# ============================================================================
# 预设 JSON 文件存在性
# ============================================================================

class TestPresetJSONFiles:
    @pytest.mark.parametrize("name", [
        "cinematic_teal_orange",
        "vintage_film",
        "high_key_bright",
        "low_key_dark",
        "music_video_punch",
        "black_and_white_classic",
        "warm_portrait",
        "cold_scifi",
    ])
    def test_json_exists_and_valid(self, name):
        f = PRESETS_DIR / f"{name}.json"
        assert f.exists(), f"missing preset file: {f}"
        data = json.loads(f.read_text(encoding="utf-8"))
        # 必须能反序列化为 ColorGradingPreset
        preset = ColorGradingPreset.from_dict(data)
        assert preset.name


# ============================================================================
# Lua 桥接脚本生成
# ============================================================================

class TestLuaBuilders:
    def test_build_set_color_wheel_lua(self):
        lua = build_set_color_wheel_lua(
            project_name="P", clip_index=0, node_index=0,
            channel="Lift", red=-0.02, green=0.01, blue=0.04, master=-0.02,
        )
        assert "pcall(Resolve)" in lua
        assert "SetNodeColorWheels" in lua
        assert '"Lift"' in lua or "'Lift'" in lua
        assert "DONE" in lua

    def test_build_set_color_wheel_lua_hsl(self):
        lua = build_set_color_wheel_lua(
            project_name="P", clip_index=0, node_index=0,
            channel="Lift", red=180, green=0.5, blue=0.7, master=0.0,
            balance_type="hsl",
        )
        assert "Hue" in lua
        assert "Saturation" in lua
        assert "Luminance" in lua

    def test_build_custom_curve_lua(self):
        lua = build_custom_curve_lua(
            project_name="P", clip_index=0, node_index=0,
            curve_type="Custom", points=[0.0, 0.0, 1.0, 1.0],
        )
        assert "SetCustomCurve" in lua
        assert "Custom" in lua

    def test_build_node_management_add(self):
        lua = build_node_management_lua(
            project_name="P", clip_index=0, action="add",
            node_type=NodeType.PARALLEL, label="X",
        )
        assert "AddNode" in lua
        assert "SetNodeLabel" in lua

    def test_build_node_management_delete(self):
        lua = build_node_management_lua(
            project_name="P", clip_index=0, action="delete", node_index=2,
        )
        assert "DeleteNode" in lua

    def test_build_node_management_opacity(self):
        lua = build_node_management_lua(
            project_name="P", clip_index=0, action="opacity",
            node_index=1, opacity=0.5,
        )
        assert "SetNodeOpacity" in lua
        assert "0.5" in lua

    def test_build_node_management_label(self):
        lua = build_node_management_lua(
            project_name="P", clip_index=0, action="label",
            node_index=1, label="MyNode",
        )
        assert "SetNodeLabel" in lua
        assert "MyNode" in lua

    def test_build_node_management_invalid(self):
        with pytest.raises(ValueError):
            build_node_management_lua(project_name="P", clip_index=0, action="bad")

    def test_build_qualifier_lua(self):
        lua = build_qualifier_lua(
            project_name="P", clip_index=0, node_index=0,
            hue_range=(180.0, 240.0),
            sat_range=(0.3, 0.9),
            lum_range=(0.2, 0.8),
            invert=True,
        )
        assert "SetQualifier" in lua
        assert "Hue" in lua
        assert "InvertQualifierSelection" in lua

    def test_build_apply_lut_lua(self):
        lua = build_apply_lut_lua(
            project_name="P", clip_index=0, node_index=0,
            lut_path="C:/Luts/test.cube",
        )
        assert "SetLUT" in lua
        assert "test.cube" in lua

    def test_build_export_lut_lua(self):
        lua = build_export_lut_lua(
            project_name="P", clip_index=0, node_index=0,
            output_path="C:/out.cube", cube_size=33,
        )
        assert "ExportLUT" in lua
        assert "33" in lua

    def test_build_apply_preset_lua(self):
        preset = get_preset("cinematic_teal_orange")
        lua = build_apply_preset_lua(
            project_name="P", clip_index=0, node_index=0, preset=preset,
        )
        assert "SetNodeColorWheels" in lua
        assert "Lift" in lua and "Gamma" in lua and "Gain" in lua and "Offset" in lua
        assert "SetSaturation" in lua
        assert "SetContrast" in lua

    def test_build_apply_preset_requires_preset(self):
        with pytest.raises(ValueError):
            build_apply_preset_lua(project_name="P", clip_index=0, node_index=0)

    def test_build_full_grading_lua(self, tmp_path):
        preset = get_preset("cinematic_teal_orange")
        fake_lut = tmp_path / "fake.cube"
        fake_lut.write_text("# fake")
        lua = build_full_grading_lua(
            project_name="P", clip_index=0, preset=preset,
            custom_curves={"Custom": [0.0, 0.0, 1.0, 1.0]},
            lut_path=str(fake_lut),
            node_label="MyNode",
        )
        assert "SetNodeColorWheels" in lua
        assert "SetCustomCurve" in lua
        assert "SetLUT" in lua
        assert "SetNodeLabel" in lua

    def test_build_batch_grade_lua(self):
        preset = get_preset("vintage_film")
        lua = build_batch_grade_lua(
            project_name="P", clip_indices=[0, 1, 2], preset=preset, node_index=0,
        )
        assert "SetNodeColorWheels" in lua
        assert "Batch graded" in lua


# ============================================================================
# 异常与边界
# ============================================================================

class TestExceptions:
    def test_invalid_node_raised(self, grader, mock_resolve):
        _, _, _ = mock_resolve
        # clip_index 99 越界
        with pytest.raises(InvalidNodeError):
            grader.set_color_wheel(99, 0, ColorWheelChannel.LIFT, ColorWheelValues())

    def test_color_grading_error_base(self):
        with pytest.raises(ColorGradingError):
            raise ColorGradingError("boom")

    def test_save_preset_to_file_helper(self, tmp_path):
        p = ColorGradingPreset(name="X")
        f = tmp_path / "x.json"
        save_preset_to_file(p, f)
        assert f.exists()


# ============================================================================
# 切换页面
# ============================================================================

class TestPageSwitch:
    def test_switch_to_color_page(self, mock_resolve):
        resolve, _, _ = mock_resolve
        grader = ColorGrader(resolve=resolve)
        grader.switch_to_color_page()
        resolve.OpenPage.assert_called_with("color")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
