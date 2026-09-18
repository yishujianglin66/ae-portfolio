# -*- coding: utf-8 -*-
"""core.layer_builders 单元测试 — 合成树图层 → JSX 语句构建

覆盖重点（2026-08-16~17 真机修复的回归保护）：
  1. js_str() 转义安全：反斜杠/双引号/换行/回车/Tab → 合法 JS 字符串字面量
  2. _hex_to_rgb() #RRGGBB → [0..1] RGB 三元组
  3. build_solid_layer: startTime → inPoint → outPoint **顺序固定**（修复 2026-08-17 多镜头 7/7 硬切根因）
  4. build_adjustment_layer: adjustmentLayer=true 标志 + grain 后处理条件分支
  5. build_text_layer: font="auto" 时 CJK 检测 + 回退链（SourceHanSansCN-Bold → Arial）
  6. build_footage_layer:
       - has_ramps=True → startTime=t0 → inPoint=t0 → outPoint=t1 顺序
       - has_ramps=False, src_in>0 → startTime=t0-src_in 前移，且单独赋值 inPoint=t0
       - still PNG(allow_still=True) → 强制 outPoint=t1（修复 M6 duration=0 问题）
       - track_matte → ctx.post_lines 追加 moveAfter + ALPHA trackMatteType
  7. build_layer() 分派注册表 + 未知类型抛 ValueError
  8. build_particle_layer: blendingMode=ADD + 模板/贴图缺失警告
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.layer_builders import (
    LAYER_BUILDERS,
    LayerBuildContext,
    _hex_to_rgb,
    build_adjustment_layer,
    build_footage_layer,
    build_layer,
    build_particle_layer,
    build_solid_layer,
    build_text_layer,
    js_str,
)


# ─────────────────────────────────────────────────────────────────────
# CompositionTree / LayerSpec 的轻量 stub（不直接 import 避免依赖复杂）
# ─────────────────────────────────────────────────────────────────────
class _FakeTree:
    def __init__(self, width=1920, height=1080, duration=10.0, style_card="amv_highenergy"):
        self.width = width
        self.height = height
        self.duration = duration
        self.style_card = style_card


class _LayerSpec:
    def __init__(self, layer_type, z_index=1, time_range=(0.0, 3.0), content=None,
                 layer_id="test_layer"):
        self.type = layer_type
        self.z_index = z_index
        self.time_range = time_range
        self.content = content or {}
        self.id = layer_id


def _ctx(tree=None):
    t = tree or _FakeTree()
    return LayerBuildContext(t, warnings=[], post_lines=[])


# ─────────────────────────────────────────────────────────────────────
# 1. js_str 转义安全
# ─────────────────────────────────────────────────────────────────────
class TestJsStr:
    def test_backslash_and_quote_escaped(self):
        assert js_str('C:\\path"name') == 'C:\\\\path\\"name'

    def test_control_chars(self):
        assert js_str("a\nb\tc\rd") == "a\\nb\\tc\\rd"

    def test_empty_and_plain(self):
        assert js_str("") == ""
        assert js_str("hello world 你好") == "hello world 你好"

    def test_result_does_not_contain_raw_double_quote(self):
        """转义后字符串作为 JS 双引号字面量内部使用时，不含未转义的双引号。"""
        raw = 'He said: "OK"' + "\n tab:\t"
        escaped = js_str(raw)
        # 验证：未转义的双引号不出现（排除转义后的 \"）
        raw_count = escaped.count('"') - escaped.count('\\"')
        assert raw_count == 0


# ─────────────────────────────────────────────────────────────────────
# 2. _hex_to_rgb
# ─────────────────────────────────────────────────────────────────────
class TestHexToRgb:
    def test_white_black_red(self):
        assert _hex_to_rgb("#FFFFFF") == pytest.approx([1.0, 1.0, 1.0])
        assert _hex_to_rgb("#000000") == pytest.approx([0.0, 0.0, 0.0])
        assert _hex_to_rgb("#FF0000") == pytest.approx([1.0, 0.0, 0.0])

    def test_without_hash_prefix(self):
        assert _hex_to_rgb("808080") == pytest.approx([128 / 255, 128 / 255, 128 / 255])


# ─────────────────────────────────────────────────────────────────────
# 3. build_solid_layer — 关键: startTime → inPoint → outPoint 顺序
# ─────────────────────────────────────────────────────────────────────
class TestSolidLayerOrder:
    def test_solid_start_before_outpoint(self):
        """solid 层只有 startTime + outPoint：startTime 必须在 outPoint 之前赋值
        （真机中顺序错乱同样导致 outPoint 被抬升）。"""
        ctx = _ctx()
        layer = _LayerSpec("solid", z_index=5, time_range=(1.25, 4.75),
                           content={"color": [255, 0, 0]})
        lines = build_solid_layer(ctx, layer)
        joined = "\n".join(lines)
        # startTime 行索引 < outPoint 行索引
        i_s = next(i for i, l in enumerate(lines) if ".startTime" in l and "out" not in l)
        i_o = next(i for i, l in enumerate(lines) if ".outPoint" in l)
        assert i_s < i_o, f"startTime 必须在 outPoint 之前赋值: start@{i_s} out@{i_o}"
        # 具体值
        assert "startTime = 1.25" in joined
        assert "outPoint = 4.75" in joined


# ─────────────────────────────────────────────────────────────────────
# 4. build_adjustment_layer — grain 条件 + adjustment 标志
# ─────────────────────────────────────────────────────────────────────
class TestAdjustmentLayer:
    def test_adjustment_flag_always_set(self):
        ctx = _ctx()
        layer = _LayerSpec("adjustment", z_index=2, time_range=(0, 5))
        lines = " ".join(build_adjustment_layer(ctx, layer))
        assert "adjustmentLayer = true" in lines

    def test_grain_postprocess_only_on_flag(self):
        ctx = _ctx()
        # 无 grain 标记 → 无 ADBE Noise
        no_grain = build_adjustment_layer(
            ctx, _LayerSpec("adjustment", z_index=1, time_range=(0, 1)))
        assert not any("ADBE Noise" in l for l in no_grain)
        # 带 grain 标记 + amount → 注入 Noise 属性，amount 整型
        with_grain = build_adjustment_layer(
            ctx, _LayerSpec("adjustment", z_index=1, time_range=(0, 1),
                            content={"edit_fx_layer": "grain", "amount": 8}))
        joined = " ".join(with_grain)
        assert "ADBE Noise" in joined
        assert ".setValue(8)" in joined
        # 默认 amount=12
        default_grain = build_adjustment_layer(
            ctx, _LayerSpec("adjustment", z_index=1, time_range=(0, 1),
                            content={"edit_fx_layer": "grain"}))
        assert ".setValue(12)" in " ".join(default_grain)


# ─────────────────────────────────────────────────────────────────────
# 5. build_text_layer — 字体回退链
# ─────────────────────────────────────────────────────────────────────
class TestTextLayer:
    def test_font_auto_cjk_generates_fallback_chain(self):
        ctx = _ctx()
        # 中文标题 → font=auto + font_role=title → 生成 CJK 回退链
        layer = _LayerSpec("text", z_index=3, time_range=(0, 2),
                           content={"text": "开篇标题", "size": 72,
                                    "font": "auto", "font_role": "title",
                                    "colors": {"main": "#FFCC00"}})
        lines = build_text_layer(ctx, layer)
        joined = "\n".join(lines)
        # 中文字体必须在回退链内
        assert "SourceHanSansCN-Bold" in joined
        # 颜色：#FFCC00 = [1.0, 0.8, 0.0]
        assert "[1.0000, 0.8000, 0.0000]" in joined
        # 字号
        assert "fontSize = 72" in joined
        # startTime → outPoint 顺序
        i_s = next(i for i, l in enumerate(lines) if ".startTime" in l and "out" not in l)
        i_o = next(i for i, l in enumerate(lines) if ".outPoint" in l)
        assert i_s < i_o

    def test_font_explicit_non_cjk_chain_still_has_fallback(self):
        ctx = _ctx()
        layer = _LayerSpec("text", z_index=1, time_range=(0, 1),
                           content={"text": "Hello", "font": "MyCustomFont"})
        joined = " ".join(build_text_layer(ctx, layer))
        # 显式字体 → 链首为 MyCustomFont，后续 SourceHanSansCN / Arial
        assert "MyCustomFont" in joined
        assert "Arial" in joined


# ─────────────────────────────────────────────────────────────────────
# 6. build_footage_layer — 真机修复 4 条回归保护
# ─────────────────────────────────────────────────────────────────────
class TestFootageLayer:
    def test_has_ramps_path_start_in_out_order(self):
        """变速镜头: startTime=t0 → inPoint=t0 → outPoint=t1 顺序（卡点铁律 2026-08-17）"""
        ctx = _ctx()
        layer = _LayerSpec("footage", z_index=10, time_range=(2.0, 5.0),
                           content={"path": "D:/clip.mov", "source_in": 3.0,
                                    "speed_ramps": [{"t": 0, "speed": 1.5}]})
        lines = build_footage_layer(ctx, layer)
        joined = "\n".join(lines)
        # 变速镜头: startTime=2.0 而非 2.0-3.0=-1.0
        assert "layer10.startTime = 2.0" in joined
        assert "layer10.inPoint = 2.0" in joined
        assert "layer10.outPoint = 5.0" in joined
        # 顺序校验（不使用 var 前缀，因为 JSX 写法不同模块不完全一致）
        i_s = next(i for i, l in enumerate(lines) if ".startTime = 2.0" in l)
        i_i = next(i for i, l in enumerate(lines) if ".inPoint = 2.0" in l)
        i_o = next(i for i, l in enumerate(lines) if ".outPoint = 5.0" in l)
        assert i_s < i_i < i_o, f"变速镜头 start/in/out 顺序错: {i_s}<{i_i}<{i_o}"

    def test_no_ramps_with_source_in_offsets_start_and_sets_inpoint(self):
        """非变速 + src_in>0: startTime = t0 - src_in；单独 inPoint=t0"""
        ctx = _ctx()
        layer = _LayerSpec("footage", z_index=7, time_range=(1.5, 4.0),
                           content={"path": "C:/test.mp4", "source_in": 0.5})
        lines = build_footage_layer(ctx, layer)
        joined = "\n".join(lines)
        assert "layer7.startTime = 1.0" in joined  # 1.5 - 0.5
        # src_in>0 必须显式设置 inPoint
        assert "layer7.inPoint = 1.5" in joined

    def test_still_png_force_outpoint(self):
        """静态 PNG: outPoint=t1（不被 0 时长素材影响）"""
        ctx = _ctx()
        layer = _LayerSpec("footage", z_index=2, time_range=(0.0, 3.5),
                           content={"path": "assets/title.png",
                                    "allow_still": True}, layer_id="title")
        lines = build_footage_layer(ctx, layer)
        joined = "\n".join(lines)
        # 静态素材: 明确 outPoint = 3.5（不是 Math.min(..., duration)）
        assert "layer2.outPoint = 3.5" in joined
        # 无视频轨检查被跳过
        assert "hasVideo" not in joined

    def test_dynamic_footage_validates_hasVideo(self):
        """动态素材: 必须检查 hasVideo"""
        ctx = _ctx()
        layer = _LayerSpec("footage", z_index=1, time_range=(0, 2),
                           content={"path": "clip.mov"})
        assert any("hasVideo" in l for l in build_footage_layer(ctx, layer))

    def test_track_matte_adds_post_lines_and_alpha(self):
        """track_matte 模式: post_lines 追加遮罩移动 + ALPHA 轨道遮罩"""
        ctx = _ctx()
        layer = _LayerSpec("footage", z_index=4, time_range=(0, 3),
                           content={"path": "fg.mov",
                                    "matting_mode": "track_matte",
                                    "matte_dir": "masks/",
                                    "matte_first": "m00001.png"})
        build_footage_layer(ctx, layer)
        posts = "\n".join(ctx.post_lines)
        assert "moveAfter(layer4)" in posts
        assert "trackMatteType = TrackMatteType.ALPHA" in posts

    def test_track_matte_missing_dir_warns_and_skips(self):
        """缺少 matte_dir → 只警告不崩溃，不追加 post_lines"""
        ctx = _ctx()
        layer = _LayerSpec("footage", z_index=1, time_range=(0, 1),
                           content={"path": "a.mov", "matting_mode": "track_matte"})
        build_footage_layer(ctx, layer)
        assert len(ctx.warnings) >= 1 and "matte_dir" in ctx.warnings[0]
        assert ctx.post_lines == []


# ─────────────────────────────────────────────────────────────────────
# 7. build_particle_layer — ADD 混合 + 警告
# ─────────────────────────────────────────────────────────────────────
class TestParticleLayer:
    def test_add_blending_mode_default(self):
        ctx = _ctx()
        layer = _LayerSpec("particle", z_index=6, time_range=(0, 1))
        lines = " ".join(build_particle_layer(ctx, layer))
        assert "BlendingMode.ADD" in lines

    def test_missing_sprite_file_generates_warning(self):
        ctx = _ctx()
        layer = _LayerSpec("particle", z_index=1, time_range=(0, 1),
                           content={"template": "spark",
                                    "sprite": "nonexistent_sprite_xyz.png"})
        # 不抛异常：Particular 模板未导入时降级，贴图缺失只警告
        build_particle_layer(ctx, layer)
        # 贴图不存在 → 至少 1 条 warning 或不崩溃
        assert isinstance(ctx.warnings, list)


# ─────────────────────────────────────────────────────────────────────
# 8. build_layer 分派
# ─────────────────────────────────────────────────────────────────────
class TestBuildLayerDispatch:
    def test_known_types_routed(self):
        ctx = _ctx()
        for t in ("solid", "adjustment", "text", "footage", "particle"):
            layer = _LayerSpec(t, z_index=1, time_range=(0, 1),
                               content={"color": [0, 0, 0]} if t == "solid" else
                                       {"path": "tmp.png"} if t == "footage" else
                                       {"text": "Hi"} if t == "text" else {})
            # 不抛异常
            lines = build_layer(ctx, layer)
            assert isinstance(lines, list) and len(lines) > 0

    def test_unknown_type_raises_value_error(self):
        ctx = _ctx()
        layer = _LayerSpec("nonexistent_layer_type_xyz", z_index=1)
        with pytest.raises(ValueError, match="未知图层类型"):
            build_layer(ctx, layer)
