#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PR 预设转化器 - AE 预设 → PR 参数映射
======================================

将 AE 知识库中的 300+ 预设转化为 Premiere Pro 可用的效果参数。

转化策略：
1. 转场预设：AE 图层动画 → PR 内置转场 / 效果组合
2. 调色预设：AE 效果参数 → PR Lumetri Color 参数
3. 特效预设：AE 效果链 → PR 效果面板等价参数
4. 文字动画：AE 文字动画 → PR 图形/标题动画

映射规则基于 ExtendScript API 差异：
- AE: layer.Effects.addProperty("ADBE xxx")
- PR: clip.effects.addVideoEffect("xxx")
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional


class PRPresetConverter:
    """AE 预设到 PR 预设的转化器。"""

    # AE 效果名 → PR 效果名映射表
    AE_TO_PR_EFFECT_MAP: Dict[str, str] = {
        # 调色类
        "ADBE Curves": "Lumetri Color",
        "ADBE Hue Saturation": "Lumetri Color",
        "ADBE Brightness & Contrast": "Lumetri Color",
        "ADBE Color Balance": "Lumetri Color",
        "ADBE Tint": "Lumetri Color",
        "ADBE Photo Filter": "Lumetri Color",
        # 模糊类
        "ADBE Gaussian Blur": "Gaussian Blur",
        "ADBE Directional Blur": "Directional Blur",
        "ADBE Radial Blur": "Radial Blur",
        "ADBE Camera Lens Blur": "Camera Blur",
        "ADBE Fast Blur": "Fast Blur",
        # 扭曲类
        "ADBE Transform": "Transform",
        "ADBE Corner Pin": "Corner Pin",
        "ADBE Mesh Warp": "Mesh Warp",
        "ADBE Optics Compensation": "Lens Distortion",
        # 生成类
        "ADBE Fractal Noise": "Noise",
        "ADBE Gradient Ramp": "Gradient",
        "ADBE Grid": "Grid",
        # 键控类
        "ADBE Extract": "Luma Key",
        "ADBE Color Key": "Color Key",
        "ADBE Difference Matte": "Difference Matte",
        # 风格化
        "ADBE Find Edges": "Find Edges",
        "ADBE Emboss": "Emboss",
        "ADBE Mosaic": "Mosaic",
        "ADBE Posterize": "Posterize",
        "ADBE Threshold": "Threshold",
        # 时间类
        "ADBE Echo": "Echo",
        "ADBE Time Difference": "Time Interpolation",
        # 通道类
        "ADBE Shift Channels": "Channel Mixer",
        "ADBE Invert": "Invert",
        "ADBE Solid Composite": "Solid Composite",
        # 实用类
        "ADBE Color Profile Converter": "Lumetri Color",
        "ADBE Grow Bounds": "Crop",
    }

    # AE 转场类型 → PR 转场类型映射
    AE_TO_PR_TRANSITION_MAP: Dict[str, str] = {
        "cross_dissolve": "Cross Dissolve",
        "dip_to_black": "Dip to Black",
        "dip_to_white": "Dip to White",
        "wipe_left": "Wipe Left",
        "wipe_right": "Wipe Right",
        "wipe_up": "Wipe Up",
        "wipe_down": "Wipe Down",
        "slide_left": "Slide Left",
        "slide_right": "Slide Right",
        "slide_up": "Slide Up",
        "slide_down": "Slide Down",
        "zoom_in": "Zoom In",
        "zoom_out": "Zoom Out",
        "whip_pan": "Whip Pan",
        "spin": "Spin",
        "stretch": "Stretch",
        "glitch": "Glitch",
        "shake": "Shake",
        "swirl": "Swirl",
        "strobe": "Strobe",
    }

    # AE 参数名 → PR 参数名映射
    AE_TO_PR_PARAM_MAP: Dict[str, str] = {
        # 通用变换
        "position": "Position",
        "scale": "Scale",
        "rotation": "Rotation",
        "opacity": "Opacity",
        "anchorPoint": "Anchor Point",
        # 模糊
        "blurriness": "Blurriness",
        "blurDimensions": "Blur Dimensions",
        "blurLength": "Blur Length",
        "blurDirection": "Blur Direction",
        # 调色
        "brightness": "Brightness",
        "contrast": "Contrast",
        "saturation": "Saturation",
        "hue": "Hue",
        "lightness": "Lightness",
        "tintColor": "Tint Color",
        "tintAmount": "Tint Amount",
        # 扭曲
        "cornerPin1": "Upper Left",
        "cornerPin2": "Upper Right",
        "cornerPin3": "Lower Left",
        "cornerPin4": "Lower Right",
        # 生成
        "fractalType": "Fractal Type",
        "subScaling": "Sub Scaling",
        "subRotation": "Sub Rotation",
        "subOffset": "Sub Offset",
        "center": "Center",
        # 风格化
        "edgeThickness": "Edge Thickness",
        "edgeIntensity": "Edge Intensity",
        "blendWithOriginal": "Blend With Original",
    }

    def __init__(self, presets_dir: Optional[Path] = None):
        self.presets_dir = presets_dir or Path(__file__).parent / "presets"
        self._converted_cache: Dict[str, Dict[str, Any]] = {}

    def convert_effect_preset(self, ae_preset: Dict[str, Any]) -> Dict[str, Any]:
        """将 AE 效果预设转化为 PR 效果预设。

        Args:
            ae_preset: AE 预设字典，包含 name, category, parameters, default_values

        Returns:
            PR 预设字典
        """
        pr_preset = {
            "name": ae_preset.get("name", ""),
            "category": ae_preset.get("category", "effect"),
            "subcategory": ae_preset.get("subcategory", "general"),
            "description": ae_preset.get("description", ""),
            "tags": ae_preset.get("tags", []),
            "compatibility": {
                "pr": ["2024", "2025"],
            },
            "source": "ae_converted",
        }

        # 转化效果参数
        pr_effects = []
        ae_params = ae_preset.get("parameters", {})
        ae_defaults = ae_preset.get("default_values", {})

        for param_name, param_meta in ae_params.items():
            pr_param_name = self.AE_TO_PR_PARAM_MAP.get(param_name, param_name)
            pr_effect = {
                "effect_name": self._infer_pr_effect_name(param_name, param_meta),
                "parameters": {
                    pr_param_name: {
                        "type": param_meta.get("type", "number"),
                        "min": param_meta.get("min"),
                        "max": param_meta.get("max"),
                        "default": ae_defaults.get(param_name),
                    }
                },
            }
            pr_effects.append(pr_effect)

        pr_preset["effects"] = pr_effects
        pr_preset["default_values"] = ae_defaults

        # 存入缓存
        self._converted_cache[pr_preset["name"]] = pr_preset

        return pr_preset

    def convert_transition_preset(self, ae_preset: Dict[str, Any]) -> Dict[str, Any]:
        """将 AE 转场预设转化为 PR 转场预设。

        Args:
            ae_preset: AE 转场预设字典

        Returns:
            PR 转场预设字典
        """
        pr_preset = {
            "name": ae_preset.get("name", ""),
            "category": "transition",
            "subcategory": ae_preset.get("subcategory", "general"),
            "description": ae_preset.get("description", ""),
            "tags": ae_preset.get("tags", []),
            "compatibility": {
                "pr": ["2024", "2025"],
            },
            "source": "ae_converted",
        }

        # 提取转场类型
        ae_name = ae_preset.get("name", "").lower()
        pr_transition_name = "Cross Dissolve"  # 默认

        for ae_key, pr_name in self.AE_TO_PR_TRANSITION_MAP.items():
            if ae_key in ae_name:
                pr_transition_name = pr_name
                break

        pr_preset["transition_name"] = pr_transition_name
        pr_preset["duration"] = ae_preset.get("default_values", {}).get("duration", 1.0)

        # 转化额外参数
        ae_defaults = ae_preset.get("default_values", {})
        pr_params = {}

        if "glitchIntensity" in ae_defaults:
            pr_params["glitch_amount"] = ae_defaults["glitchIntensity"]
        if "rgbShiftAmount" in ae_defaults:
            pr_params["rgb_shift"] = ae_defaults["rgbShiftAmount"]
        if "shakeIntensity" in ae_defaults:
            pr_params["shake_intensity"] = ae_defaults["shakeIntensity"]
        if "zoomAmount" in ae_defaults:
            pr_params["zoom_amount"] = ae_defaults["zoomAmount"]

        pr_preset["parameters"] = pr_params

        # 存入缓存
        self._converted_cache[pr_preset["name"]] = pr_preset

        return pr_preset

    def convert_color_grading_preset(self, ae_preset: Dict[str, Any]) -> Dict[str, Any]:
        """将 AE 调色预设转化为 PR Lumetri Color 预设。

        Args:
            ae_preset: AE 调色预设字典

        Returns:
            PR 调色预设字典
        """
        pr_preset = {
            "name": ae_preset.get("name", ""),
            "category": "color_grading",
            "subcategory": ae_preset.get("subcategory", "cinematic"),
            "description": ae_preset.get("description", ""),
            "tags": ae_preset.get("tags", []),
            "compatibility": {
                "pr": ["2024", "2025"],
            },
            "source": "ae_converted",
        }

        ae_defaults = ae_preset.get("default_values", {})
        lumetri_params = {}

        # 映射基本校正参数
        if "brightness" in ae_defaults:
            lumetri_params["exposure"] = ae_defaults["brightness"] / 100.0
        if "contrast" in ae_defaults:
            lumetri_params["contrast"] = ae_defaults["contrast"]
        if "saturation" in ae_defaults:
            lumetri_params["saturation"] = ae_defaults["saturation"]

        # 映射创意参数
        if "tintColor" in ae_defaults:
            lumetri_params["shadowTint"] = ae_defaults["tintColor"]
        if "tintAmount" in ae_defaults:
            lumetri_params["tintBalance"] = ae_defaults["tintAmount"]

        # 映射曲线参数
        if "shadows" in ae_defaults:
            lumetri_params["shadows"] = ae_defaults["shadows"]
        if "highlights" in ae_defaults:
            lumetri_params["highlights"] = ae_defaults["highlights"]

        pr_preset["effect_name"] = "Lumetri Color"
        pr_preset["parameters"] = lumetri_params
        pr_preset["default_values"] = lumetri_params

        # 存入缓存
        self._converted_cache[pr_preset["name"]] = pr_preset

        return pr_preset

    def _infer_pr_effect_name(self, param_name: str, param_meta: Dict[str, Any]) -> str:
        """根据参数名推断 PR 效果名称。"""
        param_lower = param_name.lower()

        if any(kw in param_lower for kw in ["blur", "blurriness"]):
            return "Gaussian Blur"
        elif any(kw in param_lower for kw in ["brightness", "contrast", "saturation", "hue"]):
            return "Lumetri Color"
        elif any(kw in param_lower for kw in ["position", "scale", "rotation", "anchor"]):
            return "Transform"
        elif any(kw in param_lower for kw in ["corner", "pin", "warp"]):
            return "Corner Pin"
        elif any(kw in param_lower for kw in ["noise", "fractal"]):
            return "Noise"
        elif any(kw in param_lower for kw in ["edge", "emboss", "mosaic"]):
            return "Find Edges"
        elif any(kw in param_lower for kw in ["channel", "shift", "invert"]):
            return "Channel Mixer"
        elif any(kw in param_lower for kw in ["color", "tint", "filter"]):
            return "Lumetri Color"
        else:
            return "Transform"

    def convert_preset_file(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
    ) -> List[Dict[str, Any]]:
        """批量转化预设文件。

        Args:
            input_path: AE 预设 JSON 文件路径
            output_path: PR 预设输出路径（可选）

        Returns:
            转化后的 PR 预设列表
        """
        with open(input_path, "r", encoding="utf-8") as f:
            ae_presets = json.load(f)

        if not isinstance(ae_presets, list):
            ae_presets = [ae_presets]

        pr_presets = []
        for ae_preset in ae_presets:
            category = ae_preset.get("category", "effect")

            if category == "transition":
                pr_preset = self.convert_transition_preset(ae_preset)
            elif category == "color_grading":
                pr_preset = self.convert_color_grading_preset(ae_preset)
            else:
                pr_preset = self.convert_effect_preset(ae_preset)

            pr_presets.append(pr_preset)
            self._converted_cache[pr_preset["name"]] = pr_preset

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(pr_presets, f, ensure_ascii=False, indent=2)
            print(f"Converted {len(pr_presets)} presets to {output_path}")

        return pr_presets

    def convert_all_presets(
        self,
        input_dir: Path,
        output_dir: Path,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """批量转化目录中的所有预设文件。

        Args:
            input_dir: AE 预设目录
            output_dir: PR 预设输出目录

        Returns:
            按文件分类的转化结果
        """
        results = {}
        output_dir.mkdir(parents=True, exist_ok=True)

        for preset_file in input_dir.glob("*.json"):
            output_file = output_dir / f"pr_{preset_file.name}"
            converted = self.convert_preset_file(preset_file, output_file)
            results[preset_file.name] = converted

        return results

    def get_conversion_report(self) -> Dict[str, Any]:
        """获取转化报告。"""
        return {
            "total_converted": len(self._converted_cache),
            "converted_presets": list(self._converted_cache.keys()),
            "effect_map_coverage": len(self.AE_TO_PR_EFFECT_MAP),
            "transition_map_coverage": len(self.AE_TO_PR_TRANSITION_MAP),
        }


def main():
    """命令行入口：批量转化 AE 预设到 PR 预设。"""
    import argparse

    parser = argparse.ArgumentParser(description="Convert AE presets to PR presets")
    parser.add_argument("--input-dir", type=Path, default=Path(__file__).parent / "presets")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "presets" / "pr_converted")
    args = parser.parse_args()

    converter = PRPresetConverter()
    results = converter.convert_all_presets(args.input_dir, args.output_dir)

    total = sum(len(v) for v in results.values())
    print(f"\nConversion complete: {total} presets converted")
    print(f"Files processed: {len(results)}")
    print(f"Output directory: {args.output_dir}")

    # 打印报告
    report = converter.get_conversion_report()
    print(f"\nReport: {report}")


if __name__ == "__main__":
    main()
