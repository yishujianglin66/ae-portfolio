#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预设加载与执行引擎

功能：
1. 动态加载预设配置文件
2. 支持预设组合和链式调用
3. 自动生成可执行的JSX脚本
4. 与AE客户端集成执行
5. 支持参数优化和调整
6. 风格组合引擎：根据风格名称自动选择预设、风格混合、强度调整
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from .preset_system import PresetSystem, Preset


class PresetExecutor:
    """预设执行器"""

    def __init__(self, preset_system: PresetSystem = None):
        self.preset_system = preset_system or PresetSystem()

    def execute_preset(
        self,
        preset_name: str,
        ae_client=None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行单个预设

        Args:
            preset_name: 预设名称
            ae_client: AE客户端实例
            kwargs: 参数覆盖

        Returns:
            执行结果
        """
        preset = self.preset_system.get_preset(preset_name)
        if not preset:
            return {
                "success": False,
                "error": f"预设不存在: {preset_name}",
            }

        jsx_code = preset.generate_jsx(**kwargs)

        if ae_client:
            try:
                result = ae_client.run_script(jsx_code)
                return {
                    "success": True,
                    "preset": preset_name,
                    "category": preset.category,
                    "result": result,
                    "jsx": jsx_code,
                }
            except Exception as e:
                return {
                    "success": False,
                    "preset": preset_name,
                    "error": str(e),
                    "jsx": jsx_code,
                }
        else:
            return {
                "success": True,
                "preset": preset_name,
                "category": preset.category,
                "status": "dry_run",
                "jsx": jsx_code,
                "parameters": kwargs,
            }

    def execute_preset_chain(
        self,
        preset_names: List[str],
        ae_client=None,
        shared_params: Dict[str, Any] = None,
        per_preset_params: Dict[str, Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行预设链（按顺序执行多个预设）

        Args:
            preset_names: 预设名称列表
            ae_client: AE客户端实例
            shared_params: 所有预设共享的参数
            per_preset_params: 每个预设的独立参数 {preset_name: {param: value}}

        Returns:
            执行结果
        """
        results = []
        shared_params = shared_params or {}
        per_preset_params = per_preset_params or {}

        for preset_name in preset_names:
            params = {**shared_params, **per_preset_params.get(preset_name, {})}
            result = self.execute_preset(preset_name, ae_client, **params)
            results.append(result)

        success_count = sum(1 for r in results if r.get("success"))

        return {
            "total_presets": len(preset_names),
            "success_count": success_count,
            "failed_count": len(preset_names) - success_count,
            "results": results,
        }

    def generate_combined_script(
        self,
        preset_names: List[str],
        **kwargs
    ) -> str:
        """
        生成组合脚本（将多个预设合并为一个JSX脚本）

        Args:
            preset_names: 预设名称列表
            kwargs: 参数

        Returns:
            合并后的JSX脚本
        """
        scripts = []

        for preset_name in preset_names:
            preset = self.preset_system.get_preset(preset_name)
            if preset:
                jsx_code = preset.generate_jsx(**kwargs.get(preset_name, {}))
                scripts.append(jsx_code)

        return "\n\n// === 预设组合 ===\n" + "\n\n".join(scripts)

    def search_and_execute(
        self,
        keyword: str,
        ae_client=None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        搜索预设并执行

        Args:
            keyword: 搜索关键词
            ae_client: AE客户端实例
            kwargs: 参数

        Returns:
            执行结果
        """
        presets = self.preset_system.search_presets(keyword)

        if not presets:
            return {
                "success": False,
                "error": f"未找到匹配的预设: {keyword}",
            }

        preset = presets[0]
        return self.execute_preset(preset.name, ae_client, **kwargs)

    def get_preset_info(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """
        获取预设详细信息

        Args:
            preset_name: 预设名称

        Returns:
            预设信息
        """
        preset = self.preset_system.get_preset(preset_name)
        if preset:
            return preset.to_dict()
        return None

    def list_presets_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        按分类列出预设

        Args:
            category: 分类名称

        Returns:
            预设列表
        """
        preset_names = self.preset_system.list_presets(category)
        return [
            self.get_preset_info(name)
            for name in preset_names
            if self.get_preset_info(name)
        ]


class PresetCombination:
    """预设组合"""

    def __init__(self, name: str, description: str, presets: List[str]):
        self.name = name
        self.description = description
        self.presets = presets
        self.parameters: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "presets": self.presets,
            "parameters": self.parameters,
        }


class PresetLibrary:
    """预设库"""

    def __init__(self):
        self.combinations: Dict[str, PresetCombination] = {}
        self._load_combinations()

    def _load_combinations(self):
        """加载预设组合"""
        combinations_dir = Path(__file__).resolve().parent / "presets" / "combinations"
        if combinations_dir.exists():
            for json_file in combinations_dir.glob("*.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        combo = PresetCombination(
                            data.get("name", ""),
                            data.get("description", ""),
                            data.get("presets", []),
                        )
                        combo.parameters = data.get("parameters", {})
                        self.combinations[combo.name] = combo
                except Exception as e:
                    print(f"加载组合文件失败 {json_file}: {e}")

    def get_combination(self, name: str) -> Optional[PresetCombination]:
        """获取预设组合"""
        return self.combinations.get(name)

    def list_combinations(self) -> List[str]:
        """列出所有组合"""
        return list(self.combinations.keys())

    def create_combination(self, name: str, description: str, presets: List[str]) -> PresetCombination:
        """创建预设组合"""
        combo = PresetCombination(name, description, presets)
        self.combinations[name] = combo

        combinations_dir = Path(__file__).resolve().parent / "presets" / "combinations"
        combinations_dir.mkdir(exist_ok=True)

        filepath = combinations_dir / f"{name}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(combo.to_dict(), f, ensure_ascii=False, indent=2)

        return combo


def create_preset_executor() -> PresetExecutor:
    """创建预设执行器实例"""
    return PresetExecutor()


def create_preset_library() -> PresetLibrary:
    """创建预设库实例"""
    return PresetLibrary()


# ============================================================
# 风格组合引擎
# ============================================================

# 风格名称映射（支持中英文、ID、别名）
STYLE_ALIASES: Dict[str, List[str]] = {
    "anime_puppet": ["动漫木偶风", "木偶风", "动漫风", "anime", "puppet"],
    "cinematic_color": ["电影感调色", "电影风", "电影调色", "cinematic", "color_grading"],
    "glitch_digital": ["故障数字风", "故障风", "数字风", "glitch", "digital"],
    "audio_visual": ["音频可视化", "音频风", "音频", "audio", "visualizer"],
    "particle_ambient": ["粒子氛围风", "粒子风", "氛围风", "particle", "ambient"],
    "text_animation": ["文字动画风", "文字风", "打字机", "text", "typewriter"],
    "3d_spatial": ["3D空间风", "3D风", "空间风", "3d", "spatial"],
}

# 反向索引：别名/中文名 -> 风格ID
_ALIAS_TO_STYLE_ID: Dict[str, str] = {}
for _style_id, _aliases in STYLE_ALIASES.items():
    _ALIAS_TO_STYLE_ID[_style_id] = _style_id  # ID 本身也可用于查找
    for _alias in _aliases:
        _ALIAS_TO_STYLE_ID[_alias.lower()] = _style_id

# 参数类型分类：决定强度调整策略
# angle/percent/signed_percent/float → 线性缩放
# pixel/hertz/seconds → 最小50%保底缩放
# enum/boolean/color → 不调整
_INTENSITY_LINEAR_TYPES = {"angle", "percent", "signed_percent", "float", "integer"}
_INTENSITY_FLOOR_TYPES = {"pixel", "hertz", "seconds"}
_INTENSITY_FIXED_TYPES = {"enum", "boolean", "color", "expression"}

# 默认合成参数
_DEFAULT_COMP_SETTINGS = {
    "width": 1920,
    "height": 1080,
    "frame_rate": 30,
    "duration": 10,
}


def resolve_style_id(style_name: str) -> Optional[str]:
    """将风格名称（ID、中文名、别名）解析为标准风格ID。

    参数:
        style_name: 风格ID、中文名或别名

    返回:
        标准风格ID，未找到返回 None
    """
    if not style_name:
        return None
    # 精确匹配
    if style_name in _ALIAS_TO_STYLE_ID:
        return _ALIAS_TO_STYLE_ID[style_name]
    # 大小写不敏感匹配
    key = style_name.lower()
    if key in _ALIAS_TO_STYLE_ID:
        return _ALIAS_TO_STYLE_ID[key]
    return None


def adjust_parameter_by_intensity(
    param_info: Dict[str, Any],
    intensity: float,
) -> Any:
    """根据强度调整参数值。

    调整规则:
    - intensity=1.0 → 原始参数值
    - intensity=0.5 → 线性类型减半；像素/尺寸类型减至75%
    - intensity=0.0 → 线性类型归零/默认值；像素/尺寸类型减至50%
    - 枚举/布尔/颜色/表达式 → 不变

    参数:
        param_info: 参数信息字典，包含 type/value/range 等
        intensity: 强度 0.0-1.0

    返回:
        调整后的参数值
    """
    intensity = max(0.0, min(1.0, intensity))
    param_type = param_info.get("type", "")
    value = param_info.get("value")

    if param_type in _INTENSITY_FIXED_TYPES:
        return value

    if param_type in _INTENSITY_LINEAR_TYPES:
        # 线性缩放：value * intensity
        if isinstance(value, (int, float)):
            adjusted = value * intensity
            # 整数类型保持整数
            if isinstance(value, int):
                adjusted = int(round(adjusted))
            return adjusted
        return value

    if param_type in _INTENSITY_FLOOR_TYPES:
        # 最小50%保底：value * (0.5 + 0.5 * intensity)
        if isinstance(value, (int, float)):
            adjusted = value * (0.5 + 0.5 * intensity)
            if isinstance(value, int):
                adjusted = int(round(adjusted))
            return adjusted
        return value

    # 未知类型，不做调整
    return value


def mix_parameters(
    params_a: Dict[str, Dict[str, Any]],
    params_b: Dict[str, Dict[str, Any]],
    weight_a: float,
    weight_b: float,
) -> Dict[str, Dict[str, Any]]:
    """混合两组效果参数。

    冲突参数（两个风格都有同一效果同一参数名）：取加权平均
    独有参数：按所属风格的权重缩放

    参数:
        params_a: 风格A的参数 {param_name: {type, value, range, ...}}
        params_b: 风格B的参数 {param_name: {type, value, range, ...}}
        weight_a: 风格A的权重
        weight_b: 风格B的权重

    返回:
        混合后的参数字典
    """
    total = weight_a + weight_b
    if total == 0:
        return {}
    norm_a = weight_a / total
    norm_b = weight_b / total

    mixed: Dict[str, Dict[str, Any]] = {}

    # 先处理风格A的独有参数
    for name, info in params_a.items():
        if name in params_b:
            # 冲突参数：根据类型决定混合策略
            val_a = info.get("value", 0)
            val_b = params_b[name].get("value", 0)
            param_type = info.get("type", params_b[name].get("type", ""))

            if param_type in _INTENSITY_FIXED_TYPES:
                # 枚举/布尔/颜色/表达式：取权重高的
                mixed_val = val_a if weight_a >= weight_b else val_b
            elif isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                # 数值类型：加权平均
                mixed_val = val_a * norm_a + val_b * norm_b
                if isinstance(val_a, int) and isinstance(val_b, int):
                    mixed_val = int(round(mixed_val))
            else:
                # 非数值类型取权重高的
                mixed_val = val_a if weight_a >= weight_b else val_b

            mixed[name] = {
                **info,
                "value": mixed_val,
                "source": "mixed",
            }
        else:
            # 风格A独有：按权重缩放
            mixed[name] = {
                **info,
                "value": adjust_parameter_by_intensity(info, norm_a),
                "source": info.get("source", "style_a"),
            }

    # 处理风格B的独有参数
    for name, info in params_b.items():
        if name not in params_a:
            mixed[name] = {
                **info,
                "value": adjust_parameter_by_intensity(info, norm_b),
                "source": info.get("source", "style_b"),
            }

    return mixed


class StyleCompositionEngine:
    """风格组合引擎

    根据风格名称自动组合预设，支持：
    - 风格名称解析（中英文、ID、别名）
    - 强度调整（0.0-1.0）
    - 风格混合（多风格按权重混合参数）
    - 生成可执行JSX代码
    """

    def __init__(
        self,
        profiles_path: str | Path | None = None,
        presets_dir: str | Path | None = None,
    ):
        """初始化风格组合引擎。

        参数:
            profiles_path: style_parameter_profiles.json 路径
            presets_dir: 风格预设JSX文件目录
        """
        project_root = Path(__file__).resolve().parent.parent
        if profiles_path is None:
            profiles_path = (
                project_root
                / "output_director"
                / "ae_project_analysis"
                / "style_parameter_profiles.json"
            )
        if presets_dir is None:
            presets_dir = (
                project_root
                / "output_director"
                / "ae_project_analysis"
                / "style_presets"
            )

        self.profiles_path = Path(profiles_path)
        self.presets_dir = Path(presets_dir)
        self._profiles: Dict[str, Any] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        """加载风格参数配置文件"""
        if self.profiles_path.exists():
            try:
                with open(self.profiles_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._profiles = data.get("styles", {})
            except Exception as e:
                print(f"加载风格参数配置失败 {self.profiles_path}: {e}")

    def get_style_profile(self, style_id: str) -> Optional[Dict[str, Any]]:
        """获取风格参数配置

        参数:
            style_id: 标准风格ID

        返回:
            风格参数配置字典，不存在返回 None
        """
        return self._profiles.get(style_id)

    def load_style_jsx(self, style_id: str) -> Optional[str]:
        """加载风格预设JSX文件内容

        参数:
            style_id: 标准风格ID

        返回:
            JSX文件内容字符串，不存在返回 None
        """
        jsx_path = self.presets_dir / f"style_{style_id}.jsx"
        if jsx_path.exists():
            try:
                with open(jsx_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                return None
        return None

    def _apply_intensity_to_effects_chain(
        self,
        effects_chain: List[Dict[str, Any]],
        intensity: float,
    ) -> List[Dict[str, Any]]:
        """对效果链中的参数应用强度调整

        参数:
            effects_chain: 效果链列表
            intensity: 强度 0.0-1.0

        返回:
            调整后的效果链
        """
        adjusted_chain = []
        for effect in effects_chain:
            new_effect = {**effect}
            new_params = {}
            for param_name, param_info in effect.get("parameters", {}).items():
                new_params[param_name] = {
                    **param_info,
                    "value": adjust_parameter_by_intensity(param_info, intensity),
                }
            new_effect["parameters"] = new_params
            adjusted_chain.append(new_effect)
        return adjusted_chain

    def _mix_two_styles(
        self,
        profile_a: Dict[str, Any],
        profile_b: Dict[str, Any],
        weight_a: float,
        weight_b: float,
    ) -> Dict[str, Any]:
        """混合两个风格配置

        参数:
            profile_a: 风格A的参数配置
            profile_b: 风格B的参数配置
            weight_a: 风格A权重
            weight_b: 风格B权重

        返回:
            混合后的风格配置
        """
        # 合并效果链：按 effect_matchname 对齐
        effects_a = {e["effect_matchname"]: e for e in profile_a.get("effects_chain", [])}
        effects_b = {e["effect_matchname"]: e for e in profile_b.get("effects_chain", [])}

        mixed_effects = []
        all_matchnames = list(dict.fromkeys(
            list(effects_a.keys()) + list(effects_b.keys())
        ))

        for matchname in all_matchnames:
            ea = effects_a.get(matchname)
            eb = effects_b.get(matchname)

            if ea and eb:
                # 两个风格都有此效果：混合参数
                mixed_params = mix_parameters(
                    ea.get("parameters", {}),
                    eb.get("parameters", {}),
                    weight_a,
                    weight_b,
                )
                mixed_effects.append({
                    "effect_matchname": matchname,
                    "effect_display_name": ea.get("effect_display_name", eb.get("effect_display_name", "")),
                    "parameters": mixed_params,
                    "source": "mixed",
                    "confidence": max(
                        ea.get("confidence", 0),
                        eb.get("confidence", 0),
                    ),
                })
            elif ea:
                # 仅风格A有：按权重缩放
                adjusted = self._apply_intensity_to_effects_chain([ea], weight_a / (weight_a + weight_b))
                mixed_effects.extend(adjusted)
            elif eb:
                adjusted = self._apply_intensity_to_effects_chain([eb], weight_b / (weight_a + weight_b))
                mixed_effects.extend(adjusted)

        # 合成设置：取权重较高者的设置，时长取加权平均
        comp_a = profile_a.get("composition_settings", {})
        comp_b = profile_b.get("composition_settings", {})
        total = weight_a + weight_b
        mixed_comp = {
            "width": comp_a.get("width", 1920) if weight_a >= weight_b else comp_b.get("width", 1920),
            "height": comp_a.get("height", 1080) if weight_a >= weight_b else comp_b.get("height", 1080),
            "frame_rate": comp_a.get("frame_rate", 30) if weight_a >= weight_b else comp_b.get("frame_rate", 30),
            "duration": round(comp_a.get("duration", 10) * (weight_a / total) + comp_b.get("duration", 10) * (weight_b / total), 1),
            "bg_color": comp_a.get("bg_color", [0, 0, 0]) if weight_a >= weight_b else comp_b.get("bg_color", [0, 0, 0]),
            "pixel_aspect": 1.0,
        }

        # 合并表达式
        exprs_a = profile_a.get("expressions", [])
        exprs_b = profile_b.get("expressions", [])
        seen_ids = set()
        mixed_exprs = []
        for expr in exprs_a + exprs_b:
            tid = expr.get("template_id", "")
            if tid not in seen_ids:
                seen_ids.add(tid)
                mixed_exprs.append(expr)

        # 合并图层结构
        layers_a = profile_a.get("layer_structure", [])
        layers_b = profile_b.get("layer_structure", [])
        seen_layer_names = set()
        mixed_layers = []
        for layer in layers_a + layers_b:
            lname = layer.get("name", "")
            if lname not in seen_layer_names:
                seen_layer_names.add(lname)
                mixed_layers.append(layer)

        style_ids = [
            profile_a.get("style_id", "unknown"),
            profile_b.get("style_id", "unknown"),
        ]

        return {
            "style_id": "+".join(style_ids),
            "style_name": f"{profile_a.get('style_name', '')}+{profile_b.get('style_name', '')}",
            "effects_chain": mixed_effects,
            "expressions": mixed_exprs,
            "composition_settings": mixed_comp,
            "layer_structure": mixed_layers,
        }

    def compose(
        self,
        style_name: str,
        params: Dict[str, Any] | None = None,
    ) -> str:
        """根据风格名称组合预设，生成JSX代码。

        参数:
            style_name: 风格ID或中文名（如 "anime_puppet" 或 "动漫木偶风"）
            params: 可选参数覆盖
                - intensity: 强度 0.0-1.0（默认1.0）
                - duration: 持续时间秒（默认10）
                - width/height: 分辨率（默认1920x1080）
                - frame_rate: 帧率（默认30）
                - mix_styles: 混合风格列表 [{"style": "cinematic_color", "weight": 0.5}]

        返回:
            生成的JSX代码字符串
        """
        params = params or {}
        intensity = params.get("intensity", 1.0)
        mix_styles = params.get("mix_styles", [])

        # 解析主风格
        style_id = resolve_style_id(style_name)
        if style_id is None:
            return f"// 错误：未识别的风格名称 '{style_name}'\n"

        profile = self.get_style_profile(style_id)
        if profile is None:
            return f"// 错误：未找到风格配置 '{style_id}'\n"

        # 应用强度调整
        working_profile = self._deep_copy_profile(profile)
        if intensity < 1.0:
            working_profile["effects_chain"] = self._apply_intensity_to_effects_chain(
                working_profile.get("effects_chain", []), intensity
            )
            # 同步调整表达式中的数值参数
            for expr in working_profile.get("expressions", []):
                expr_params = expr.get("parameters", {})
                for pname, pval in expr_params.items():
                    if isinstance(pval, (int, float)):
                        expr_params[pname] = pval * intensity

        # 处理风格混合
        for mix_spec in mix_styles:
            mix_style_name = mix_spec.get("style", "")
            mix_weight = mix_spec.get("weight", 0.5)
            mix_style_id = resolve_style_id(mix_style_name)
            if mix_style_id is None:
                continue
            mix_profile = self.get_style_profile(mix_style_id)
            if mix_profile is None:
                continue
            # 主风格权重 = 1.0 - mix_weight，混合风格权重 = mix_weight
            working_profile = self._mix_two_styles(
                working_profile, mix_profile,
                1.0 - mix_weight, mix_weight,
            )

        # 覆盖合成参数
        comp = working_profile.get("composition_settings", {})
        comp["duration"] = params.get("duration", comp.get("duration", 10))
        comp["width"] = params.get("width", comp.get("width", 1920))
        comp["height"] = params.get("height", comp.get("height", 1080))
        comp["frame_rate"] = params.get("frame_rate", comp.get("frame_rate", 30))
        working_profile["composition_settings"] = comp

        # 生成JSX
        return self._generate_jsx_from_profile(working_profile)

    def _deep_copy_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """深拷贝风格配置（避免修改原始数据）"""
        return json.loads(json.dumps(profile))

    def _generate_jsx_from_profile(self, profile: Dict[str, Any]) -> str:
        """从风格配置生成完整JSX脚本

        参数:
            profile: 风格配置字典

        返回:
            JSX代码字符串
        """
        style_id = profile.get("style_id", "unknown")
        style_name = profile.get("style_name", "Unknown Style")
        comp = profile.get("composition_settings", {})
        effects_chain = profile.get("effects_chain", [])
        layer_structure = profile.get("layer_structure", [])
        expressions = profile.get("expressions", [])

        width = comp.get("width", 1920)
        height = comp.get("height", 1080)
        duration = comp.get("duration", 10)
        framerate = comp.get("frame_rate", 30)
        bg_color = comp.get("bg_color", [0.05, 0.05, 0.08])

        lines: List[str] = []
        lines.append(f"// ============================================================================")
        lines.append(f"// 风格组合引擎生成: {style_name}")
        lines.append(f"// 风格ID: {style_id}")
        lines.append(f"// ============================================================================")

        # 安全初始化
        lines.append("app.beginSuppressDialogs();")
        lines.append("$.level = 0;")
        lines.append("")

        # 检查项目
        lines.append("var proj = app.project;")
        lines.append('if (!proj) { alert("没有打开的项目"); app.endSuppressDialogs(); throw new Error("No project"); }')
        lines.append("")

        # 工具函数（复用标准模板）
        lines.extend(self._generate_utility_functions())
        lines.append("")

        # 创建合成
        lines.append("// ===== 创建合成 =====")
        comp_name = f"Style_{style_id}"
        lines.append(f'var comp = createOrGetComp("{comp_name}", {width}, {height}, {duration}, {framerate});')
        lines.append("comp.openInViewer();")
        lines.append("")

        # 创建图层
        lines.append("// ===== 创建图层 =====")
        layer_var_map: Dict[str, str] = {}
        for i, layer_info in enumerate(layer_structure):
            layer_type = layer_info.get("type", "solid")
            layer_name = layer_info.get("name", f"Layer_{i}")
            var_name = f"layer_{layer_name.replace('~', '_').replace('[', '').replace(']', '').replace(' ', '_').replace('.', '_').replace('-', '_')}"
            # 确保变量名唯一
            if var_name in layer_var_map.values():
                var_name = f"{var_name}_{i}"
            layer_var_map[layer_name] = var_name

            if layer_type == "solid":
                r, g, b = bg_color[0], bg_color[1], bg_color[2]
                lines.append(f'var {var_name} = safeAddSolid(comp, "{layer_name}", {width}, {height}, {r}, {g}, {b}, 1);')
            elif layer_type == "null":
                lines.append(f'var {var_name} = safeAddNull(comp, "{layer_name}");')
            elif layer_type == "text":
                lines.append(f'var {var_name} = safeAddText(comp, "{layer_name}", "{layer_name}");')
            elif layer_type == "camera":
                lines.append(f'var {var_name} = safeAddCamera(comp, "{layer_name}");')
            elif layer_type == "light":
                lt = layer_info.get("light_type", "Ambient")
                lines.append(f'var {var_name} = safeAddLight(comp, "{layer_name}", "{lt}");')
            elif layer_type == "adjustment":
                lines.append(f'var {var_name} = comp.layers.addSolid([0, 0, 0, 0], "{layer_name}", {width}, {height}, 1);')
                lines.append(f"if ({var_name}) {{ {var_name}.adjustmentLayer = true; }}")
            elif layer_type == "precomp":
                sub_comp_name = f"{comp_name}_{layer_name}"
                lines.append(f'var {var_name}_subcomp = createOrGetComp("{sub_comp_name}", {width}, {height}, {duration}, {framerate});')
                lines.append(f'var {var_name} = comp.layers.add({var_name}_subcomp);')
                lines.append(f'if ({var_name}) {{ {var_name}.name = "{layer_name}"; }}')
            elif layer_type == "audio":
                lines.append(f'var {var_name} = safeAddSolid(comp, "{layer_name}", {width}, {height}, 0, 0, 0, 0);')
                lines.append(f"if ({var_name}) {{ {var_name}.adjustmentLayer = true; }}")
            elif layer_type == "footage":
                r, g, b = bg_color[0], bg_color[1], bg_color[2]
                lines.append(f'var {var_name} = safeAddSolid(comp, "{layer_name}", {width}, {height}, {r}, {g}, {b}, 1);')
            else:
                r, g, b = bg_color[0], bg_color[1], bg_color[2]
                lines.append(f'var {var_name} = safeAddSolid(comp, "{layer_name}", {width}, {height}, {r}, {g}, {b}, 1);')

            # 3D图层标记
            if layer_info.get("is_3d"):
                lines.append(f"if ({var_name}) {{ {var_name}.threeDLayer = true; }}")

            # 混合模式
            if "blend_mode" in layer_info:
                blend = layer_info["blend_mode"]
                lines.append(f"if ({var_name}) {{ {var_name}.blendingMode = BlendingMode.{blend.upper()}; }}")

            # 不透明度
            if "opacity" in layer_info:
                lines.append(f"if ({var_name}) {{ safeSetValue({var_name}.transform.opacity, {layer_info['opacity']}); }}")

            lines.append("")

        # 应用效果链
        lines.append("// ===== 应用效果链 =====")
        for effect in effects_chain:
            matchname = effect.get("effect_matchname", "")
            display_name = effect.get("effect_display_name", "")
            parameters = effect.get("parameters", {})

            # 确定效果应用在哪个图层（优先找第一个匹配的图层）
            target_var = self._find_layer_var_for_effect(matchname, layer_structure, layer_var_map)
            if target_var is None:
                # 没有特定目标，应用到第一个图层
                if layer_var_map:
                    target_var = list(layer_var_map.values())[0]
                else:
                    continue

            lines.append(f"if ({target_var}) {{")
            lines.append(f'    var fx = safeApplyEffect({target_var}, "{matchname}");')
            if parameters:
                lines.append("    if (fx) {")
                lines.append(f"        // {display_name}")
                for param_name, param_info in parameters.items():
                    pval = param_info.get("value")
                    ptype = param_info.get("type", "")
                    pidx = param_info.get("idx")

                    if ptype == "expression":
                        expr_code = param_info.get("expression", str(pval))
                        lines.append(f'        try {{ fx("{param_name}").expression = "{self._escape_jsx_string(expr_code)}"; }} catch(e) {{}}')
                    elif ptype == "color" and isinstance(pval, list):
                        lines.append(f'        try {{ safeSetValue(fx("{param_name}"), {pval}); }} catch(e) {{}}')
                    elif ptype == "boolean":
                        js_val = "true" if pval else "false"
                        lines.append(f'        try {{ safeSetValue(fx("{param_name}"), {js_val}); }} catch(e) {{}}')
                    else:
                        if pidx is not None:
                            lines.append(f"        try {{ safeSetValue(fx({pidx + 1}), {self._format_jsx_value(pval)}); }} catch(e) {{}}")
                        else:
                            lines.append(f'        try {{ safeSetValue(fx("{param_name}"), {self._format_jsx_value(pval)}); }} catch(e) {{}}')
                lines.append("    }")
            lines.append("}")
            lines.append("")

        # 表达式绑定参考
        if expressions:
            lines.append("// ===== 表达式绑定(参考模板) =====")
            for expr in expressions:
                tid = expr.get("template_id", "")
                desc = expr.get("description", "")
                code = expr.get("code_template", "")
                expr_params = expr.get("parameters", {})
                lines.append(f"// ----- 表达式: {tid} -----")
                lines.append(f"// {desc}")
                if expr_params:
                    lines.append(f"// 参数: {json.dumps(expr_params, ensure_ascii=False)}")
                if code:
                    for code_line in code.strip().split("\n"):
                        lines.append(f"//   {code_line}")
                lines.append("")

        # 合成设置备注
        lines.append("// ===== 合成设置 =====")
        lines.append(f"// 背景色: {bg_color} (AE内部[0-1]范围)")
        lines.append("// 像素宽高比: 1.0")
        lines.append("")

        # 结束
        lines.append("app.endSuppressDialogs();")
        lines.append("// 风格组合引擎生成完成")

        return "\n".join(lines)

    def _find_layer_var_for_effect(
        self,
        effect_matchname: str,
        layer_structure: List[Dict[str, Any]],
        layer_var_map: Dict[str, str],
    ) -> Optional[str]:
        """根据效果matchname查找对应图层的变量名"""
        # 效果到图层类型的映射
        effect_layer_hints = {
            "ADBE Fractal Noise": ["FractalNoise", "Fractal", "BG", "Particles", "Detail"],
            "ADBE Glo2": ["Glow", "Spectrum", "Character", "Particles", "Correction"],
            "ADBE HUE SATURATION": ["Hue", "Fractal", "Particles"],
            "ADBE AudSpect": ["Audio", "Spectrum"],
            "ADBE FreePin3": ["Sway", "Character", "Puppet"],
            "ADBE Mosaic": ["Glitch", "Mosaic"],
            "ADBE Invert": ["Glitch", "Invert"],
            "ADBE Noise2": ["Noise", "BG", "Glitch"],
            "ADBE Lumetri": ["Footage", "Place"],
            "ADBE CurvesCustom": ["Footage", "Place"],
            "ADBE Exposure2": ["Footage", "Place"],
            "ADBE PhotoFilterPS": ["Footage", "Place"],
            "ADBE Camera Lens Blur": ["Camera", "Lens"],
            "ADBE Geometry2": ["Card", "3D"],
            "ADBE Optics Compensation": ["Card", "3D", "Scene"],
            "ADBE Ramp": ["Gradient", "BG"],
            "ADBE Black&White": ["BW", "Black"],
            "ADBE Text Properties": ["Text", "Typewriter"],
        }

        hints = effect_layer_hints.get(effect_matchname, [])
        for hint in hints:
            for layer_name, var_name in layer_var_map.items():
                if hint.lower() in layer_name.lower():
                    return var_name

        return None

    def _generate_utility_functions(self) -> List[str]:
        """生成标准工具函数JSX代码"""
        return [
            "// ===== 工具函数 =====",
            "function safeApplyEffect(layer, effectName) {",
            "    try {",
            "        var fx = layer.effect.addProperty(effectName);",
            "        return fx;",
            "    } catch (e) {",
            "        try {",
            "            for (var i = 1; i <= layer.effect.numProperties; i++) {",
            '                if (layer.effect(i).matchName === effectName || layer.effect(i).name === effectName) {',
            "                    return layer.effect(i);",
            "                }",
            "            }",
            "        } catch (e2) {}",
            "        return null;",
            "    }",
            "}",
            "",
            "function safeSetValue(prop, value) {",
            "    try {",
            '        if (typeof value === "string") {',
            "            if (/wiggle|loopOut|ease\\(|time\\s\\*|seedRandom|linear\\(/.test(value)) {",
            "                prop.expression = value;",
            "            } else {",
            "                prop.setValue(value);",
            "            }",
            "        } else {",
            "            prop.setValue(value);",
            "        }",
            "    } catch (e) {}",
            "}",
            "",
            "function createOrGetComp(compName, width, height, durationSec, framerate) {",
            "    for (var i = 1; i <= app.project.numItems; i++) {",
            "        if (app.project.item(i) instanceof CompItem && app.project.item(i).name === compName) {",
            "            return app.project.item(i);",
            "        }",
            "    }",
            "    return app.project.items.addComp(compName, width, height, 1, durationSec, framerate);",
            "}",
            "",
            "function safeAddSolid(comp, name, width, height, r, g, b, a) {",
            "    try {",
            "        var solid = comp.layers.addSolid([r, g, b, a || 1], name, width, height, 1);",
            "        return solid;",
            '    } catch (e) { return null; }',
            "}",
            "",
            "function safeAddNull(comp, name) {",
            "    try {",
            "        var nullObj = comp.layers.addNull();",
            "        nullObj.name = name;",
            "        return nullObj;",
            '    } catch (e) { return null; }',
            "}",
            "",
            "function safeAddText(comp, name, text) {",
            "    try {",
            "        var textLayer = comp.layers.addText(text || name);",
            "        textLayer.name = name;",
            "        return textLayer;",
            '    } catch (e) { return null; }',
            "}",
            "",
            "function safeAddCamera(comp, name) {",
            "    try {",
            "        var cam = comp.layers.addCamera(name, [comp.width / 2, comp.height / 2]);",
            "        return cam;",
            '    } catch (e) { return null; }',
            "}",
            "",
            "function safeAddLight(comp, name, lightType) {",
            "    try {",
            "        var light = comp.layers.addLight(name, [comp.width / 2, comp.height / 2]);",
            '        if (lightType === "Ambient") { light.lightType = LightType.AMBIENT; }',
            '        else if (lightType === "Point") { light.lightType = LightType.POINT; }',
            "        return light;",
            '    } catch (e) { return null; }',
            "}",
        ]

    @staticmethod
    def _escape_jsx_string(s: str) -> str:
        """转义JSX字符串中的特殊字符"""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    @staticmethod
    def _format_jsx_value(value: Any) -> str:
        """格式化JSX值"""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, float):
            if value == int(value):
                return str(int(value))
            return str(value)
        if isinstance(value, list):
            return json.dumps(value)
        if value is None:
            return "null"
        return str(value)


def compose_style(style_name: str, params: dict | None = None) -> str:
    """根据风格名称组合预设，生成JSX代码。

    参数:
        style_name: 风格ID或中文名（如 "anime_puppet" 或 "动漫木偶风"）
        params: 可选参数覆盖
            - intensity: 强度 0.0-1.0（默认1.0）
            - duration: 持续时间秒（默认10）
            - width/height: 分辨率（默认1920x1080）
            - frame_rate: 帧率（默认30）
            - mix_styles: 混合风格列表 [{"style": "cinematic_color", "weight": 0.5}]

    返回:
        生成的JSX代码字符串
    """
    engine = StyleCompositionEngine()
    return engine.compose(style_name, params)


# ============================================================
# 预设组合模板
# ============================================================

DEFAULT_COMBINATIONS = [
    {
        "name": "cyberpunk_title_sequence",
        "description": "赛博朋克标题序列 - 故障文字 + 赛博朋克调色 + 能量环特效",
        "presets": ["cyberpunk_glitch_text", "cyberpunk_grade", "energy_rings"],
        "parameters": {
            "textLayerName": "CYBERPUNK",
            "glitchIntensity": 0.7,
        },
    },
    {
        "name": "cinematic_intro",
        "description": "电影感开场 - 打字机效果 + 电影感调色 + 光扫特效",
        "presets": ["typewriter_effect", "cinematic_grade", "light_sweep"],
        "parameters": {
            "textLayerName": "CINEMATIC",
            "duration": 4.0,
        },
    },
    {
        "name": "hologram_display",
        "description": "全息显示效果 - 全息文字 + 扫描线 + 色差特效",
        "presets": ["hologram_text", "scanline_effect", "chromatic_aberration"],
        "parameters": {
            "textLayerName": "HOLOGRAM",
            "hueShiftSpeed": 10,
        },
    },
    {
        "name": "ink_painting",
        "description": "水墨画卷效果 - 水墨文字 + 梦幻柔和调色 + 翻页转场",
        "presets": ["ink_spread_text", "dreamy_soft", "page_flip_transition"],
        "parameters": {
            "textLayerName": "水墨画",
            "duration": 5.0,
        },
    },
    {
        "name": "neon_sign",
        "description": "霓虹灯效果 - 霓虹脉冲文字 + 霓虹发光效果 + 光扫",
        "presets": ["neon_pulse_text", "neon_glow", "light_sweep"],
        "parameters": {
            "textLayerName": "NEON",
            "pulseFrequency": 2.0,
        },
    },
]


def initialize_default_combinations(library: PresetLibrary):
    """初始化默认预设组合"""
    for combo_data in DEFAULT_COMBINATIONS:
        if combo_data["name"] not in library.combinations:
            library.create_combination(
                combo_data["name"],
                combo_data["description"],
                combo_data["presets"],
            )
