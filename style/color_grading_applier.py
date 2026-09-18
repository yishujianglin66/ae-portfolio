#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
color_grading_applier.py — 调色自动应用管线
=============================================

将 VRS v2 分析出的调色参数自动应用到 AE 调整层。

支持的调色效果：
  - Lumetri Color: 色温/色调/曝光/对比度/饱和度/阴影高光色调
  - Curves: RGB/R/G/B 曲线控制点
  - Color Balance: 阴影/中间调/高光色彩平衡
  - Tritone: 三色调映射
  - Import LUT: 导入 .cube LUT 文件

用法：
    from color_grading_applier import ColorGradingApplier

    applier = ColorGradingApplier()
    jsx = applier.generate_color_grade_jsx(color_analysis)
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


class ColorGradingApplier:
    """调色自动应用管线。"""

    def generate_color_grade_jsx(
        self,
        color_analysis: dict[str, Any],
        adjustment_layer_name: str = "Color_Grade_Adjust",
        comp_width: int = 1920,
        comp_height: int = 1080,
        duration: float = 30.0,
    ) -> str:
        """根据调色分析结果生成 JSX 脚本。

        Args:
            color_analysis: 调色分析结果，可包含:
                - lumetri: Lumetri Color 参数
                - curves: 曲线控制点
                - color_balance: 色彩平衡参数
                - tritone: 三色调参数
                - lut_path: LUT 文件路径
            adjustment_layer_name: 调整层名称
            comp_width: 合成宽度
            comp_height: 合成高度
            duration: 合成时长

        Returns:
            JSX 脚本字符串
        """
        lines = [
            "// ============================================",
            "// Color Grading - Auto-generated",
            "// ============================================",
            "",
            'var comp = thisComp;',
            f'var adj = comp.layers.addSolid([0.5, 0.5, 0.5], "{adjustment_layer_name}", '
            f'{comp_width}, {comp_height}, 1, {duration});',
            'adj.adjustmentLayer = true;',
            '',
        ]

        # 1. Lumetri Color
        lumetri = color_analysis.get("lumetri", {})
        if lumetri:
            lines.extend(self._generate_lumetri_jsx(lumetri))

        # 2. Curves
        curves = color_analysis.get("curves", {})
        if curves:
            lines.extend(self._generate_curves_jsx(curves))

        # 3. Color Balance
        color_balance = color_analysis.get("color_balance", {})
        if color_balance:
            lines.extend(self._generate_color_balance_jsx(color_balance))

        # 4. Tritone
        tritone = color_analysis.get("tritone", {})
        if tritone:
            lines.extend(self._generate_tritone_jsx(tritone))

        # 5. LUT
        lut_path = color_analysis.get("lut_path", "")
        if lut_path:
            lines.extend(self._generate_lut_jsx(lut_path))

        # 6. Brightness & Contrast (if present)
        bc = color_analysis.get("brightness_contrast", {})
        if bc:
            lines.extend(self._generate_bc_jsx(bc))

        return '\n'.join(lines)

    def extract_color_params_from_vrs(self, vrs_analysis: dict[str, Any]) -> dict[str, Any]:
        """从 VRS v2 完整分析结果中提取调色相关参数。

        将 VRS 的 effect 列表中 color 类型的效果参数提取出来，
        转化为 generate_color_grade_jsx 可接受的格式。

        Args:
            vrs_analysis: VRS v2 完整分析结果

        Returns:
            调色参数字典
        """
        color_params: dict[str, Any] = {}

        # 提取效果列表
        effects = self._extract_color_effects(vrs_analysis)

        for eff in effects:
            eff_type = eff.get("type", "")
            match_name = eff.get("matchName", "")
            params = eff.get("params", {})

            if "Lumetri" in match_name or eff_type == "lumetri":
                color_params["lumetri"] = params
            elif "Curves" in match_name or eff_type == "curves":
                color_params["curves"] = params
            elif "Color Balance" in match_name or eff_type == "color_balance":
                color_params["color_balance"] = params
            elif "Tritone" in match_name or eff_type == "tritone":
                color_params["tritone"] = params
            elif "LUT" in match_name or eff_type == "lut":
                color_params["lut_path"] = params.get("path", "")
            elif "Brightness" in match_name:
                color_params["brightness_contrast"] = params

        return color_params

    # =========================================================================
    # 内部 JSX 生成方法
    # =========================================================================

    def _generate_lumetri_jsx(self, lumetri: dict[str, Any]) -> list[str]:
        """生成 Lumetri Color 效果 JSX。"""
        lines = [
            '// --- Lumetri Color ---',
            'var lumetri = adj.Effects.addProperty("ADBE Lumetri Color");',
            'lumetri.name = "Auto_Lumetri";',
        ]

        param_map = {
            "Temperature": "Temperature",
            "Tint": "Tint",
            "Exposure": "Exposure",
            "Contrast": "Contrast",
            "Highlights": "Highlights",
            "Shadows": "Shadows",
            "Whites": "Whites",
            "Blacks": "Blacks",
            "Saturation": "Saturation",
            # VRS 可能输出的别名
            "temperature": "Temperature",
            "tint": "Tint",
            "exposure": "Exposure",
            "contrast": "Contrast",
            "saturation": "Saturation",
            "shadows_hue": "Shadows",
            "highlights_hue": "Highlights",
        }

        for src_key, dst_key in param_map.items():
            if src_key in lumetri:
                val = lumetri[src_key]
                val = self._clamp(val, -100, 100) if dst_key != "Exposure" else self._clamp(val, -5, 5)
                lines.append(f'lumetri.property("{dst_key}").setValue({val});')

        lines.append('')
        return lines

    def _generate_curves_jsx(self, curves: dict[str, Any]) -> list[str]:
        """生成 Curves 效果 JSX。"""
        lines = [
            '// --- Curves ---',
            'var curves = adj.Effects.addProperty("ADBE Curves");',
            'curves.name = "Auto_Curves";',
        ]

        curve_map = {
            "RGB Curve": "rgb_points",
            "Red Curve": "r_points",
            "Green Curve": "g_points",
            "Blue Curve": "b_points",
        }

        for ae_name, src_key in curve_map.items():
            if src_key in curves:
                points = curves[src_key]
                if isinstance(points, list) and len(points) >= 2:
                    # AE Curves 需要设置控制点
                    lines.append(f'// {ae_name}: {json.dumps(points)}')
                    lines.append('// (Curves control points require manual adjustment in AE UI)')

        lines.append('')
        return lines

    def _generate_color_balance_jsx(self, cb: dict[str, Any]) -> list[str]:
        """生成 Color Balance 效果 JSX。"""
        lines = [
            '// --- Color Balance ---',
            'var cb = adj.Effects.addProperty("ADBE Color Balance");',
            'cb.name = "Auto_ColorBalance";',
        ]

        params = [
            "Red Shadow Level", "Green Shadow Level", "Blue Shadow Level",
            "Red Midtone Level", "Green Midtone Level", "Blue Midtone Level",
            "Red Highlight Level", "Green Highlight Level", "Blue Highlight Level",
        ]

        for p in params:
            if p in cb:
                val = self._clamp(cb[p], -100, 100)
                lines.append(f'cb.property("{p}").setValue({val});')

        if "Preserve Luminosity" in cb:
            lines.append(f'cb.property("Preserve Luminosity").setValue({"true" if cb["Preserve Luminosity"] else "false"});')

        lines.append('')
        return lines

    def _generate_tritone_jsx(self, tritone: dict[str, Any]) -> list[str]:
        """生成 Tritone 效果 JSX。"""
        lines = [
            '// --- Tritone ---',
            'var tritone = adj.Effects.addProperty("ADBE Tritone");',
            'tritone.name = "Auto_Tritone";',
        ]

        color_params = ["Shadows", "Midtones", "Highlights"]
        for p in color_params:
            if p in tritone:
                val = tritone[p]
                if isinstance(val, list) and len(val) == 4:
                    lines.append(f'tritone.property("{p}").setValue([{val[0]}, {val[1]}, {val[2]}, {val[3]}]);')

        if "Blend" in tritone:
            lines.append(f'tritone.property("Blend").setValue({self._clamp(tritone["Blend"], 0, 100)});')

        lines.append('')
        return lines

    def _generate_lut_jsx(self, lut_path: str) -> list[str]:
        """生成 Import LUT 效果 JSX。"""
        escaped = lut_path.replace('\\', '\\\\').replace('"', '\\"')
        return [
            '// --- Import LUT ---',
            'var lut = adj.Effects.addProperty("ADBE ImportLUT");',
            'lut.name = "Auto_LUT";',
            f'// LUT file: {escaped}',
            f'// Import the LUT via AE UI: Effect > ImportLUT > Browse > "{escaped}"',
            '',
        ]

    def _generate_bc_jsx(self, bc: dict[str, Any]) -> list[str]:
        """生成 Brightness & Contrast 效果 JSX。"""
        lines = [
            '// --- Brightness & Contrast ---',
            'var bc = adj.Effects.addProperty("ADBE Brightness & Contrast 2");',
            'bc.name = "Auto_BC";',
        ]

        if "Brightness" in bc:
            lines.append(f'bc.property("Brightness").setValue({self._clamp(bc["Brightness"], -100, 100)});')
        if "Contrast" in bc:
            lines.append(f'bc.property("Contrast").setValue({self._clamp(bc["Contrast"], -100, 100)});')

        lines.append('')
        return lines

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _extract_color_effects(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        """从 VRS 分析结果中提取 color 类型的效果。"""
        color_effects = []

        # 从 merged 结构
        merged = analysis.get("merged", {})
        for eff in merged.get("effects", []):
            if eff.get("type") in ("color", "lumetri", "curves", "color_balance", "tritone", "lut"):
                color_effects.append(eff)

        # 从 vision_result
        if not color_effects:
            vision = analysis.get("vision_result", {})
            for eff in vision.get("aggregated_effects", []):
                if eff.get("type") in ("color", "lumetri", "curves", "color_balance", "tritone", "lut"):
                    color_effects.append(eff)

        # 顶层
        if not color_effects:
            for eff in analysis.get("effects", []):
                if eff.get("type") in ("color", "lumetri", "curves", "color_balance", "tritone", "lut"):
                    color_effects.append(eff)

        return color_effects

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))


# ============================================================================
# CLI 测试入口
# ============================================================================

if __name__ == "__main__":
    applier = ColorGradingApplier()

    mock_color = {
        "lumetri": {
            "Temperature": 10,
            "Tint": -5,
            "Exposure": 0.3,
            "Contrast": 20,
            "Saturation": 15,
            "Highlights": -10,
            "Shadows": 5,
        },
        "color_balance": {
            "Red Shadow Level": 5,
            "Green Shadow Level": 2,
            "Blue Shadow Level": -3,
            "Red Midtone Level": 8,
            "Green Midtone Level": 4,
            "Blue Midtone Level": -5,
            "Red Highlight Level": 3,
            "Green Highlight Level": 2,
            "Blue Highlight Level": -2,
            "Preserve Luminosity": True,
        },
        "tritone": {
            "Shadows": [0.0, 0.0, 0.2, 1.0],
            "Midtones": [0.5, 0.5, 0.5, 1.0],
            "Highlights": [1.0, 0.9, 0.7, 1.0],
        },
    }

    print("Color Grading JSX:")
    print("=" * 60)
    print(applier.generate_color_grade_jsx(mock_color))
