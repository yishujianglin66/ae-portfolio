#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预设系统架构 - 从知识库提取预设参数并转化为可执行脚本

设计目标：
1. 将知识库中的300+预设参数（转场、文字动画、调色、特效、背景、音频可视化、MG动画、3D效果）转化为结构化配置
2. 支持动态加载和组合预设
3. 与创意规划引擎无缝集成
4. 支持参数覆盖和优化
5. 自动生成JSX脚本代码

预设分类：
- 转场预设（50种）
- 文字动画预设（50种）
- 调色预设（50种）
- 特效预设（50种）
- 背景预设（30种）
- 音频可视化预设（20种）
- MG动画预设（30种）
- 3D效果预设（20种）
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class Preset:
    """预设类"""

    def __init__(self, data: dict[str, Any]):
        self.name = data.get("name", "")
        self.category = data.get("category", "")
        self.subcategory = data.get("subcategory", "")
        self.description = data.get("description", "")
        self.tags = data.get("tags", [])
        self.parameters = data.get("parameters", {})
        self.script_template = data.get("script_template", "")
        self.default_values = data.get("default_values", {})
        self.compatibility = data.get("compatibility", {"ae": ["2024", "2025", "2026"]})

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "subcategory": self.subcategory,
            "description": self.description,
            "tags": self.tags,
            "parameters": self.parameters,
            "script_template": self.script_template,
            "default_values": self.default_values,
            "compatibility": self.compatibility,
        }

    def generate_jsx(self, **kwargs) -> str:
        """生成JSX脚本代码"""
        import json
        params = {**self.default_values, **kwargs}
        script = self.script_template
        for key, value in params.items():
            placeholder = f"${{{key}}}"
            if placeholder in script:
                if isinstance(value, bool):
                    # ExtendScript 使用小写 true/false，而非 Python 的 True/False
                    script = script.replace(placeholder, "true" if value else "false")
                elif isinstance(value, str):
                    script = script.replace(placeholder, f'"{value}"')
                elif isinstance(value, list):
                    js_array = json.dumps(value)
                    script = script.replace(placeholder, js_array)
                elif value is None:
                    # ExtendScript 使用 null 而非 Python 的 None
                    script = script.replace(placeholder, "null")
                else:
                    script = script.replace(placeholder, str(value))
        return script

    def validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """验证参数"""
        validated = {}
        for param_name, param_info in self.parameters.items():
            if param_name in params:
                value = params[param_name]
                min_val = param_info.get("min")
                max_val = param_info.get("max")
                if min_val is not None and value < min_val:
                    value = min_val
                if max_val is not None and value > max_val:
                    value = max_val
                validated[param_name] = value
            elif param_name in self.default_values:
                validated[param_name] = self.default_values[param_name]
        return validated


class PresetSystem:
    """预设系统"""

    def __init__(self, presets_dir: str = None):
        self.presets_dir = Path(presets_dir or "ae/presets")
        self.presets: dict[str, Preset] = {}
        self.categories: dict[str, list[str]] = {}
        self.load_all_presets()

    def load_all_presets(self):
        """加载所有预设（递归扫描顶层与分类子目录）"""
        if not self.presets_dir.exists():
            self.presets_dir.mkdir(parents=True, exist_ok=True)

        # 排除由 PresetLibrary 单独加载的组合目录，以及 PR 转换产物目录
        excluded_subdirs = {"combinations", "pr_converted"}

        for json_file in self.presets_dir.rglob("*.json"):
            rel_parts = json_file.relative_to(self.presets_dir).parts
            if any(part in excluded_subdirs for part in rel_parts[:-1]):
                continue
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            preset = Preset(item)
                            self._register_preset(preset)
                    else:
                        preset = Preset(data)
                        self._register_preset(preset)
            except Exception as e:
                print(f"加载预设文件失败 {json_file}: {e}")

    def _register_preset(self, preset: Preset):
        """注册预设"""
        self.presets[preset.name] = preset

        if preset.category not in self.categories:
            self.categories[preset.category] = []
        if preset.name not in self.categories[preset.category]:
            self.categories[preset.category].append(preset.name)

    def get_preset(self, name: str) -> Preset | None:
        """获取预设"""
        return self.presets.get(name)

    def list_presets(self, category: str = None) -> list[str]:
        """列出预设"""
        if category:
            return self.categories.get(category, [])
        return list(self.presets.keys())

    def search_presets(self, keyword: str) -> list[Preset]:
        """搜索预设（匹配名称、描述、标签、分类名）"""
        keyword_lower = keyword.lower()
        results = []
        # 构建分类名映射（支持中文和英文搜索）
        category_names = {k: v["name"].lower() for k, v in PRESET_CATEGORIES.items()}
        for preset in self.presets.values():
            cat_name = category_names.get(preset.category, "")
            if (
                keyword_lower in preset.name.lower()
                or keyword_lower in preset.description.lower()
                or any(keyword_lower in tag.lower() for tag in preset.tags)
                or keyword_lower in cat_name
                or keyword_lower in preset.category.lower()
            ):
                results.append(preset)
        return results

    def generate_script(self, preset_name: str, **kwargs) -> str:
        """生成脚本"""
        preset = self.get_preset(preset_name)
        if not preset:
            raise ValueError(f"预设不存在: {preset_name}")

        validated_params = preset.validate_params(kwargs)
        return preset.generate_jsx(**validated_params)

    def create_preset(self, data: dict[str, Any]) -> Preset:
        """创建预设"""
        preset = Preset(data)
        self._register_preset(preset)
        self._save_preset(preset)
        return preset

    def _save_preset(self, preset: Preset):
        """保存预设到文件"""
        category_dir = self.presets_dir / preset.category
        category_dir.mkdir(exist_ok=True)

        filepath = category_dir / f"{preset.name}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(preset.to_dict(), f, ensure_ascii=False, indent=2)

    def get_category_info(self) -> dict[str, dict[str, Any]]:
        """获取分类信息"""
        info = {}
        for category, presets in self.categories.items():
            info[category] = {
                "count": len(presets),
                "presets": presets,
            }
        return info


# ============================================================
# 预设注册表
# ============================================================

PRESET_CATEGORIES = {
    "transition": {"name": "转场", "icon": "🎬", "description": "镜头转场效果"},
    "text_animation": {"name": "文字动画", "icon": "📝", "description": "文字图层动画效果"},
    "color_grading": {"name": "调色", "icon": "🎨", "description": "颜色校正和风格化"},
    "effect": {"name": "特效", "icon": "✨", "description": "视觉特效组合"},
    "background": {"name": "背景", "icon": "🖼️", "description": "背景生成和样式"},
    "audio_visualization": {"name": "音频可视化", "icon": "🎵", "description": "音频驱动的视觉效果"},
    "mg_animation": {"name": "MG动画", "icon": "📐", "description": "运动图形动画"},
    "3d_effect": {"name": "3D效果", "icon": "🔷", "description": "三维空间效果"},
    "puppet_style": {"name": "木偶风格", "icon": "🎭", "description": "木偶风格化效果"},
    "lut_preset": {"name": "LUT预设", "icon": "🎞️", "description": "LUT调色预设"},
}


def create_preset_system() -> PresetSystem:
    """创建预设系统实例"""
    return PresetSystem()


def get_preset_category_info() -> dict[str, dict[str, Any]]:
    """获取预设分类信息"""
    return PRESET_CATEGORIES
