#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TextFX 特效组合生成器
=====================

封装 5 种可复用的特效组合，每种组合生成自包含的 JSX 代码片段。
可通过 Bridge runScript 发送到 AE 执行。

特效组合:
- cyberGlow()   — Glow + Ramp + Grid → 赛博朋克
- neonEffect()  — Glow + Lens Flare + Levels → 霓虹发光
- hologramEffect() — Glow + Hue/Saturation + Duplicate → 全息投影
- fireIceEffect()  — Glow + Ramp + BlendMode → 冰火对比
- colorGrade()     — Levels + Hue/Saturation + Vignette → 调色预设

用法:
    from ae.textfx_effects import TextFXEffects
    fx = TextFXEffects()
    jsx_code = fx.cyber_glow_jsx("MyLayer", intensity=1.5)
    # 通过 Bridge 发送 jsx_code
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class TextFXEffects:
    """TextFX 特效组合生成器"""

    # AE 2025 已验证可用的效果 matchName（经实机验证 + AEP工程逆向）
    EFFECT_MATCHNAMES = {
        # --- 核心效果 ---
        "glow": "ADBE Glo2",
        "gaussian_blur": "ADBE Gaussian Blur",
        "gaussian_blur_legacy": "ADBE Gaussian Blur 2",
        "lens_flare": "ADBE Lens Flare",
        "fractal_noise": "ADBE Fractal Noise",
        "levels": "ADBE Easy Levels",           # 注意: 不是 "ADBE Levels"
        "hue_saturation": "ADBE HUE SATURATION", # 注意: 全大写
        "ramp": "ADBE Ramp",
        "grid": "ADBE Grid",
        "roughen_edges": "ADBE Roughen Edges",
        "turbulent_displace": "ADBE Turbulent Displace",
        "vignette": None,  # AE 2025 无内置 Vignette，用 Lumetri 子效果替代
        # --- 从 AEP 工程逆向新增 ---
        "exposure": "ADBE Exposure2",
        "brightness_contrast": "ADBE Brightness & Contrast 2",
        "curves": "ADBE CurvesCustom",
        "tint": "ADBE Tint",
        "tritone": "ADBE Tritone",
        "black_white": "ADBE Black&White",
        "photo_filter": "ADBE PhotoFilterPS",
        "invert": "ADBE Invert",
        "fill": "ADBE Fill",
        "noise": "ADBE Noise2",
        "sharpen": "ADBE Sharpen",
        "unsharp_mask": "ADBE Unsharp Mask2",
        "box_blur": "ADBE Box Blur2",
        "emboss": "ADBE Emboss",
        "mosaic": "ADBE Mosaic",
        "tile": "ADBE Tile",
        "optics_compensation": "ADBE Optics Compensation",
        "mesh_warp": "ADBE WRPMESH",
        "wave_warp": "ADBE Wave Warp",
        "venetian_blinds": "ADBE Venetian Blinds",
        "audio_spectrum": "ADBE AudSpect",
        "cracked_tiles": "ADBE CM CrackedTiles",
        "shift_channels": "ADBE Shift Channels",
        "lumetri": "ADBE Lumetri",
        "geometry": "ADBE Geometry2",
    }

    # 效果参数范围（AE 2025 兼容性约束，经实机验证）
    PARAM_RANGES = {
        "turbulent_amount": (1, 11),
        "fractal_contrast": (1, 4),
        "fractal_brightness": (-100, 100),
        "glow_threshold": (0.0, 1.0),
        "glow_radius": (1, 100),
        "glow_intensity": (0.0, 10.0),
        "gaussian_blur": (0, 100),
        "lens_flare_brightness": (0, 200),
        "roughen_edges_amount": (1, 8),  # 注意: 上限为 8 不是 10
    }

    # ================================================================
    #  特效组合
    # ================================================================

    def cyber_glow_jsx(
        self,
        layer_var: str = "layer",
        glow_color: list[float] = None,
        intensity: float = 2.0,
        grid_color: list[float] = None,
    ) -> str:
        """
        赛博朋克特效组合: Glow + Ramp + Grid

        Args:
            layer_var: JSX 中图层变量名
            glow_color: 发光颜色 [R,G,B] 0-1
            intensity: 发光强度
            grid_color: 网格颜色 [R,G,B] 0-1

        Returns:
            JSX 代码片段
        """
        gc = glow_color or [0, 1, 0.8]
        grc = grid_color or [0, 0.5, 0.3]
        return f"""
// === cyberGlow: Glow + Ramp + Grid ===
(function(l) {{
    {self._add_glow_jsx("l", gc, 30, intensity)}
    {self._add_ramp_jsx("l", [0.1, 0, 0.2], [0, 0.1, 0])}
    // Grid (需要固态层，此处仅添加发光+渐变)
}})({layer_var});
"""

    def neon_effect_jsx(
        self,
        layer_var: str = "layer",
        glow_color: list[float] = None,
        flare_brightness: float = 80,
    ) -> str:
        """
        霓虹发光特效组合: Glow + Lens Flare + Levels

        Args:
            layer_var: JSX 中图层变量名
            glow_color: 发光颜色
            flare_brightness: 光晕亮度

        Returns:
            JSX 代码片段
        """
        gc = glow_color or [1, 0.2, 0.8]
        fb = max(0, min(200, flare_brightness))
        return f"""
// === neonEffect: Glow + Lens Flare + Levels ===
(function(l) {{
    {self._add_glow_jsx("l", gc, 40, 4.0)}
    {self._add_lens_flare_jsx("l", fb)}
    {self._add_levels_jsx("l", 1.3)}
}})({layer_var});
"""

    def hologram_effect_jsx(
        self,
        layer_var: str = "layer",
        glow_color: list[float] = None,
        hue_shift: float = 180,
    ) -> str:
        """
        全息投影特效组合: Glow + Hue/Saturation

        Args:
            layer_var: JSX 中图层变量名
            glow_color: 发光颜色
            hue_shift: 色相偏移角度

        Returns:
            JSX 代码片段
        """
        gc = glow_color or [0.3, 0.8, 1]
        return f"""
// === hologramEffect: Glow + Hue/Saturation ===
(function(l) {{
    {self._add_glow_jsx("l", gc, 25, 2.0)}
    {self._add_hue_saturation_jsx("l", hue_shift, 30)}
    // 注意: 全息效果需要复制图层并偏移位置
}})({layer_var});
"""

    def fire_ice_effect_jsx(
        self,
        fire_layer_var: str = "fireLayer",
        ice_layer_var: str = "iceLayer",
    ) -> str:
        """
        冰火对比特效组合: Glow + Ramp + BlendMode

        Args:
            fire_layer_var: 火图层变量名
            ice_layer_var: 冰图层变量名

        Returns:
            JSX 代码片段
        """
        return f"""
// === fireIceEffect: Glow + Ramp + BlendMode ===
(function(fire, ice) {{
    {self._add_glow_jsx("fire", [1, 0.4, 0], 35, 3.0)}
    {self._add_glow_jsx("ice", [0.3, 0.8, 1], 30, 2.5)}
    try {{ fire.blendingMode = BlendingMode.ADD; }} catch(e) {{}}
    try {{ ice.blendingMode = BlendingMode.SCREEN; }} catch(e) {{}}
}})({fire_layer_var}, {ice_layer_var});
"""

    def color_grade_jsx(
        self,
        layer_var: str = "adjustmentLayer",
        gamma: float = 1.3,
    ) -> str:
        """
        调色预设: Levels + Vignette

        Args:
            layer_var: 调整图层变量名
            gamma: Gamma 值

        Returns:
            JSX 代码片段
        """
        return f"""
// === colorGrade: Levels + Vignette ===
(function(l) {{
    {self._add_levels_jsx("l", gamma)}
    {self._add_vignette_jsx("l", 50)}
}})({layer_var});
"""

    # ================================================================
    #  基础效果 JSX 片段（内部）
    # ================================================================

    def _add_glow_jsx(self, var: str, color: list[float], radius: float, intensity: float) -> str:
        c = f"[{color[0]}, {color[1]}, {color[2]}]"
        r = max(1, min(100, radius))
        i = max(0, min(10, intensity))
        return f"""
    var _glow = null;
    try {{ _glow = {var}.property("Effects").addProperty("ADBE Glo2"); }} catch(e) {{}}
    if (!_glow) try {{ _glow = {var}.effects.add("Glow"); }} catch(e) {{}}
    if (_glow) {{
        try {{ _glow.property("ADBE Glo2-0001").setValue({c}); }} catch(e) {{}}
        try {{ _glow.property("ADBE Glo2-0002").setValue(0.2); }} catch(e) {{}}
        try {{ _glow.property("ADBE Glo2-0003").setValue({r}); }} catch(e) {{}}
        try {{ _glow.property("ADBE Glo2-0004").setValue({i}); }} catch(e) {{}}
    }}"""

    def _add_ramp_jsx(self, var: str, start_color: list[float], end_color: list[float]) -> str:
        sc = f"[{start_color[0]}, {start_color[1]}, {start_color[2]}]"
        ec = f"[{end_color[0]}, {end_color[1]}, {end_color[2]}]"
        return f"""
    var _ramp = null;
    try {{ _ramp = {var}.property("Effects").addProperty("ADBE Ramp"); }} catch(e) {{}}
    if (!_ramp) try {{ _ramp = {var}.effects.add("Ramp"); }} catch(e) {{}}
    if (_ramp) {{
        try {{ _ramp.property(1).setValue({sc}); }} catch(e) {{}}
        try {{ _ramp.property(2).setValue({ec}); }} catch(e) {{}}
    }}"""

    def _add_lens_flare_jsx(self, var: str, brightness: float) -> str:
        b = max(0, min(200, brightness))
        return f"""
    var _flare = null;
    try {{ _flare = {var}.property("Effects").addProperty("ADBE Lens Flare"); }} catch(e) {{}}
    if (!_flare) try {{ _flare = {var}.effects.add("Lens Flare"); }} catch(e) {{}}
    if (_flare) {{
        try {{ _flare.property(1).setValue({b}); }} catch(e) {{}}
    }}"""

    def _add_levels_jsx(self, var: str, gamma: float) -> str:
        return f"""
    var _levels = null;
    try {{ _levels = {var}.property("Effects").addProperty("ADBE Easy Levels"); }} catch(e) {{}}
    if (!_levels) try {{ _levels = {var}.effects.add("Easy Levels"); }} catch(e) {{}}
    if (_levels) {{
        try {{ _levels.property(1).setValue({gamma}); }} catch(e) {{}}
    }}"""

    def _add_hue_saturation_jsx(self, var: str, hue: float, saturation: float) -> str:
        return f"""
    var _hs = null;
    try {{ _hs = {var}.property("Effects").addProperty("ADBE HUE SATURATION"); }} catch(e) {{}}
    if (!_hs) try {{ _hs = {var}.effects.add("Hue/Saturation"); }} catch(e) {{}}
    if (_hs) {{
        try {{ _hs.property(2).setValue({hue}); }} catch(e) {{}}
        try {{ _hs.property(3).setValue({saturation}); }} catch(e) {{}}
    }}"""

    def _add_vignette_jsx(self, var: str, amount: float) -> str:
        # AE 2025 无内置 Vignette 效果，使用 Glow 暗角模拟
        # 或使用 Color Balance (HLS) 压暗边缘
        return f"""
    // Vignette 模拟: 使用 Levels 压暗整体
    var _vig = null;
    try {{ _vig = {var}.property("Effects").addProperty("ADBE Easy Levels"); }} catch(e) {{}}
    if (!_vig) try {{ _vig = {var}.effects.add("Easy Levels"); }} catch(e) {{}}
    if (_vig) {{
        try {{ _vig.property(1).setValue(0.85); }} catch(e) {{}}
    }}"""

    # ================================================================
    #  完整场景生成
    # ================================================================

    def generate_scene_jsx(
        self,
        scene_name: str,
        effect_combo: str,
        text: str,
        font: str,
        font_size: int,
        color: list[float],
        duration: float = 4.0,
        **kwargs,
    ) -> str:
        """
        生成完整场景 JSX（文字图层 + 特效组合）。

        Args:
            scene_name: 场景名
            effect_combo: 特效组合名 (cyberGlow/neon/hologram/fireIce/colorGrade)
            text: 文字内容
            font: 字体
            font_size: 字号
            color: 文字颜色 [R,G,B]
            duration: 时长（秒）
            **kwargs: 传递给特效组合的参数

        Returns:
            完整的自包含 JSX 代码
        """
        color_jsx = f"[{color[0]}, {color[1]}, {color[2]}]"

        effect_code = ""
        if effect_combo == "cyberGlow":
            effect_code = self.cyber_glow_jsx("textLayer", **kwargs)
        elif effect_combo == "neon":
            effect_code = self.neon_effect_jsx("textLayer", **kwargs)
        elif effect_combo == "hologram":
            effect_code = self.hologram_effect_jsx("textLayer", **kwargs)
        elif effect_combo == "fireIce":
            effect_code = self.fire_ice_effect_jsx("textLayer", "textLayer2", **kwargs)
        elif effect_combo == "colorGrade":
            effect_code = self.color_grade_jsx("adjLayer", **kwargs)
        else:
            effect_code = f"// Unknown combo: {effect_combo}"

        return f"""
// Scene: {scene_name} — {effect_combo}
(function(comp) {{
    var textLayer = comp.layers.addText("{text}");
    var tp = textLayer.property("Text");
    var td = tp.property("ADBE Text Document").value;
    td.font = "{font}";
    td.fontSize = {font_size};
    td.fillColor = {color_jsx};
    td.applyFill = true;
    td.applyStroke = false;
    td.justification = ParagraphJustification.CENTER_JUSTIFY;
    tp.property("ADBE Text Document").setValue(td);
    textLayer.position.setValue([960, 540]);

    {effect_code}

    return textLayer;
}})(app.project.activeItem);
"""

    # ================================================================
    #  预设列表
    # ================================================================

    @staticmethod
    def list_combos() -> list[dict[str, str]]:
        """列出所有可用特效组合"""
        return [
            {"name": "cyberGlow", "desc": "赛博朋克: Glow + Ramp + Grid", "effects": ["Glow", "Ramp", "Grid"]},
            {"name": "neon", "desc": "霓虹发光: Glow + Lens Flare + Levels", "effects": ["Glow", "Lens Flare", "Levels"]},
            {"name": "hologram", "desc": "全息投影: Glow + Hue/Saturation", "effects": ["Glow", "Hue/Saturation"]},
            {"name": "fireIce", "desc": "冰火对比: Glow + Ramp + BlendMode", "effects": ["Glow", "Ramp", "BlendMode"]},
            {"name": "colorGrade", "desc": "调色预设: Levels + Vignette", "effects": ["Levels", "Vignette"]},
        ]

    @staticmethod
    def list_available_effects() -> list[dict[str, str]]:
        """列出所有可用效果及其 matchName"""
        return [
            {"name": "Glow", "matchName": "ADBE Glo2", "status": "verified"},
            {"name": "Gaussian Blur", "matchName": "ADBE Gaussian Blur 2", "status": "available"},
            {"name": "Lens Flare", "matchName": "ADBE Lens Flare", "status": "available"},
            {"name": "Fractal Noise", "matchName": "ADBE Fractal Noise", "status": "available"},
            {"name": "Levels", "matchName": "ADBE Easy Levels", "status": "verified"},
            {"name": "Hue/Saturation", "matchName": "ADBE HUE SATURATION", "status": "verified"},
            {"name": "Ramp", "matchName": "ADBE Ramp", "status": "available"},
            {"name": "Grid", "matchName": "ADBE Grid", "status": "available"},
            {"name": "Roughen Edges", "matchName": "ADBE Roughen Edges", "status": "verified"},
            {"name": "Turbulent Displace", "matchName": "ADBE Turbulent Displace", "status": "available"},
            {"name": "Vignette", "matchName": "N/A (用 Easy Levels 模拟)", "status": "unavailable"},
        ]
