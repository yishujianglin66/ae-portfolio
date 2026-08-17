"""
pipeline/presets.py - 模板预设系统
====================================
预定义的管线配置模板，一键套用常见视频风格。

用法:
    from pipeline.presets import apply_preset, list_presets

    # 查看可用模板
    print(list_presets())

    # 套用模板
    config = PipelineConfig(input_topic="利威尔高燃混剪")
    config = apply_preset(config, "high_energy")
    pipe = UnifiedPipeline(config)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import replace


# ============================================================================
#  预设模板库
# ============================================================================

PRESETS: Dict[str, Dict[str, Any]] = {
    "high_energy": {
        "name": "高燃混剪",
        "description": "快节奏、强视觉冲击的混剪风格",
        "config_overrides": {
            "project_name_suffix": "_high_energy",
        },
        "script_hints": {
            "pacing": "fast",           # 快节奏
            "avg_shot_duration": 2.0,   # 平均镜头2秒
            "transition_style": "dynamic",  # 动态转场
            "effect_intensity": 0.9,    # 高效果强度
            "color_grading": "high_contrast_warm",
            "music_bpm_range": [120, 160],
        },
        "kb_keywords": ["高燃", "混剪", "VFX", "快节奏", "视觉冲击"],
        "style_master": "andrew_kramer",  # 匹配大师风格
    },

    "cinematic": {
        "name": "电影感",
        "description": "经典电影调色风格，高对比度、宽银幕、胶片质感",
        "config_overrides": {
            "project_name_suffix": "_cinematic",
        },
        "script_hints": {
            "pacing": "moderate",
            "avg_shot_duration": 4.0,
            "transition_style": "dissolve",
            "effect_intensity": 0.5,
            "color_grading": "teal_orange",
            "aspect_ratio": "2.35:1",
            "music_bpm_range": [60, 90],
        },
        "kb_keywords": ["电影", "胶片", "调色", "cinematic", "宽银幕"],
        "style_master": "roger_deakins",
    },

    "product_showcase": {
        "name": "产品展示",
        "description": "干净、专业的产品展示风格",
        "config_overrides": {
            "project_name_suffix": "_product",
        },
        "script_hints": {
            "pacing": "slow",
            "avg_shot_duration": 5.0,
            "transition_style": "clean",
            "effect_intensity": 0.3,
            "color_grading": "clean_bright",
            "background": "white_minimal",
        },
        "kb_keywords": ["产品", "展示", "商业", "干净", "专业"],
        "style_master": "peter_mckinnon",
    },

    "vlog": {
        "name": "电影感Vlog",
        "description": "个人Vlog风格，轻松自然但有质感",
        "config_overrides": {
            "project_name_suffix": "_vlog",
        },
        "script_hints": {
            "pacing": "moderate",
            "avg_shot_duration": 3.5,
            "transition_style": "smooth",
            "effect_intensity": 0.4,
            "color_grading": "warm_natural",
            "music_bpm_range": [80, 110],
        },
        "kb_keywords": ["Vlog", "日常", "旅行", "自然", "温暖"],
        "style_master": "peter_mckinnon",
    },

    "lyric_video": {
        "name": "歌词视频",
        "description": "音乐歌词可视化，文字动画为主",
        "config_overrides": {
            "project_name_suffix": "_lyrics",
        },
        "script_hints": {
            "pacing": "music_sync",
            "avg_shot_duration": 3.0,
            "transition_style": "fade",
            "effect_intensity": 0.6,
            "text_animation": "typewriter",
            "color_grading": "moody_dark",
        },
        "kb_keywords": ["歌词", "文字", "动画", "音乐", "排版"],
        "style_master": "default",
    },

    "motion_graphics": {
        "name": "动态图形",
        "description": "MG动画风格，几何图形+流畅运动",
        "config_overrides": {
            "project_name_suffix": "_mg",
        },
        "script_hints": {
            "pacing": "rhythmic",
            "avg_shot_duration": 2.5,
            "transition_style": "morph",
            "effect_intensity": 0.7,
            "color_grading": "vibrant_flat",
            "shape_layers": True,
        },
        "kb_keywords": ["MG", "动态图形", "几何", "运动", "图形"],
        "style_master": "default",
    },
}


def list_presets() -> List[Dict[str, str]]:
    """列出所有可用预设模板"""
    return [
        {"key": k, "name": v["name"], "description": v["description"]}
        for k, v in PRESETS.items()
    ]


def get_preset(preset_key: str) -> Optional[Dict[str, Any]]:
    """获取指定预设"""
    return PRESETS.get(preset_key)


def apply_preset(config, preset_key: str, **extra_hints) -> Any:
    """
    将预设模板应用到 PipelineConfig

    Args:
        config: PipelineConfig 实例
        preset_key: 预设键名
        **extra_hints: 额外的 script_hints 覆盖

    Returns:
        修改后的 config（原地修改并返回）
    """
    preset = PRESETS.get(preset_key)
    if not preset:
        raise ValueError(f"Unknown preset: {preset_key}. Available: {list(PRESETS.keys())}")

    # 应用 config 覆盖
    overrides = preset.get("config_overrides", {})
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    # 注入 script_hints 到 config
    hints = {**preset.get("script_hints", {}), **extra_hints}
    if hasattr(config, 'script_hints'):
        config.script_hints.update(hints)
    else:
        config.script_hints = hints

    # 注入 KB 关键词
    kb_keywords = preset.get("kb_keywords", [])
    if hasattr(config, 'kb_keywords'):
        config.kb_keywords.extend(kb_keywords)
    else:
        config.kb_keywords = kb_keywords

    # 注入大师风格匹配
    style_master = preset.get("style_master")
    if style_master and style_master != "default":
        if hasattr(config, 'style_master_hint'):
            config.style_master_hint = style_master
        else:
            config.style_master_hint = style_master

    return config


def get_preset_context(preset_key: str) -> str:
    """获取预设的 LLM 上下文描述（供 planning 阶段使用）"""
    preset = PRESETS.get(preset_key)
    if not preset:
        return ""

    hints = preset.get("script_hints", {})
    lines = [
        f"## 风格模板: {preset['name']}",
        f"{preset['description']}",
        "",
        "### 剧本参数",
        f"- 节奏: {hints.get('pacing', 'moderate')}",
        f"- 平均镜头时长: {hints.get('avg_shot_duration', 3)}s",
        f"- 转场风格: {hints.get('transition_style', 'dissolve')}",
        f"- 效果强度: {hints.get('effect_intensity', 0.5)}",
        f"- 调色风格: {hints.get('color_grading', 'natural')}",
    ]

    if hints.get("aspect_ratio"):
        lines.append(f"- 画幅比: {hints['aspect_ratio']}")
    if hints.get("music_bpm_range"):
        lines.append(f"- 音乐BPM: {hints['music_bpm_range'][0]}-{hints['music_bpm_range'][1]}")

    return "\n".join(lines)
