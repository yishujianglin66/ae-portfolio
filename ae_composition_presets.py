#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AE 合成预设配置
===============
常用 AE 合成预设的参数配置，供 V4RemoteOrchestrator.quick_composition() 使用。

每个预设包含：
- name: 预设显示名称
- comp_settings: 合成基础设置（宽/高/帧率/时长/背景色）
- layers: 默认图层配置列表
- effects: 默认效果配置列表
- render_settings: 渲染输出设置
"""

from typing import Any, Dict, List

# 默认输出路径
_DEFAULT_OUTPUT_DIR = "D:/AE-Work/output"

COMPOSITION_PRESETS: Dict[str, Dict[str, Any]] = {
    # ==================================================================
    # 竖屏音乐视频
    # ==================================================================
    "music_video_vertical": {
        "name": "竖屏音乐视频",
        "comp_settings": {
            "width": 576,
            "height": 768,
            "frameRate": 30,
            "duration": 12,
            "bgColor": [0.02, 0.02, 0.06],
        },
        "layers": [
            {
                "op": "addSolidLayer",
                "params": {
                    "name": "背景渐变",
                    "color": [0.02, 0.02, 0.06],
                    "isAdjustment": False,
                },
            },
            {
                "op": "addSolidLayer",
                "params": {
                    "name": "调色层",
                    "color": [1, 1, 1],
                    "isAdjustment": True,
                },
            },
        ],
        "effects": [
            {
                "params": {
                    "layerName": "调色层",
                    "effectName": "ADBE Color Balance",
                },
            },
            {
                "params": {
                    "layerName": "背景渐变",
                    "effectName": "ADBE Glo2",
                },
            },
        ],
        "render_settings": {
            "outputPath": f"{_DEFAULT_OUTPUT_DIR}/music_video_vertical.mp4",
            "format": "mp4",
            "preset": "H.264",
        },
    },

    # ==================================================================
    # 木偶风格
    # ==================================================================
    "puppet_style": {
        "name": "木偶风格",
        "comp_settings": {
            "width": 1920,
            "height": 1080,
            "frameRate": 24,
            "duration": 10,
            "bgColor": [0.15, 0.12, 0.08],
        },
        "layers": [
            {
                "op": "addSolidLayer",
                "params": {
                    "name": "木质背景",
                    "color": [0.15, 0.12, 0.08],
                    "isAdjustment": False,
                },
            },
            {
                "op": "addSolidLayer",
                "params": {
                    "name": "风格调色",
                    "color": [1, 1, 1],
                    "isAdjustment": True,
                },
            },
        ],
        "effects": [
            {
                "params": {
                    "layerName": "风格调色",
                    "effectName": "ADBE Color Balance",
                },
            },
            {
                "params": {
                    "layerName": "木质背景",
                    "effectName": "ADBE Noise",
                },
            },
        ],
        "render_settings": {
            "outputPath": f"{_DEFAULT_OUTPUT_DIR}/puppet_style.mp4",
            "format": "mp4",
            "preset": "H.264",
        },
    },

    # ==================================================================
    # 粒子特效
    # ==================================================================
    "particle_fx": {
        "name": "粒子特效",
        "comp_settings": {
            "width": 1920,
            "height": 1080,
            "frameRate": 30,
            "duration": 8,
            "bgColor": [0, 0, 0],
        },
        "layers": [
            {
                "op": "addSolidLayer",
                "params": {
                    "name": "黑色背景",
                    "color": [0, 0, 0],
                    "isAdjustment": False,
                },
            },
            {
                "op": "addSolidLayer",
                "params": {
                    "name": "粒子发射器",
                    "color": [0, 0, 0],
                    "isAdjustment": False,
                },
            },
            {
                "op": "addSolidLayer",
                "params": {
                    "name": "发光叠加",
                    "color": [0, 0, 0],
                    "isAdjustment": False,
                },
            },
        ],
        "effects": [
            {
                "params": {
                    "layerName": "粒子发射器",
                    "effectName": "ADBE Particular",
                },
            },
            {
                "params": {
                    "layerName": "发光叠加",
                    "effectName": "ADBE Glo2",
                },
            },
        ],
        "render_settings": {
            "outputPath": f"{_DEFAULT_OUTPUT_DIR}/particle_fx.mp4",
            "format": "mp4",
            "preset": "H.264",
        },
    },

    # ==================================================================
    # 文字动画
    # ==================================================================
    "text_animation": {
        "name": "文字动画",
        "comp_settings": {
            "width": 1920,
            "height": 1080,
            "frameRate": 30,
            "duration": 6,
            "bgColor": [0.05, 0.05, 0.05],
        },
        "layers": [
            {
                "op": "addSolidLayer",
                "params": {
                    "name": "深色背景",
                    "color": [0.05, 0.05, 0.05],
                    "isAdjustment": False,
                },
            },
            {
                "op": "addTextLayer",
                "params": {
                    "text": "标题文字",
                    "fontSize": 120,
                    "fontFamily": "Microsoft YaHei",
                },
            },
            {
                "op": "addTextLayer",
                "params": {
                    "text": "副标题文字",
                    "fontSize": 48,
                    "fontFamily": "Microsoft YaHei",
                },
            },
        ],
        "effects": [
            {
                "params": {
                    "layerName": "标题文字",
                    "effectName": "ADBE Glo2",
                },
            },
            {
                "params": {
                    "layerName": "标题文字",
                    "effectName": "ADBE Drop Shadow",
                },
            },
        ],
        "render_settings": {
            "outputPath": f"{_DEFAULT_OUTPUT_DIR}/text_animation.mp4",
            "format": "mp4",
            "preset": "H.264",
        },
    },

    # ==================================================================
    # 3D 场景
    # ==================================================================
    "3d_scene": {
        "name": "3D场景",
        "comp_settings": {
            "width": 1920,
            "height": 1080,
            "frameRate": 30,
            "duration": 10,
            "bgColor": [0.02, 0.02, 0.05],
        },
        "layers": [
            {
                "op": "addSolidLayer",
                "params": {
                    "name": "3D背景",
                    "color": [0.02, 0.02, 0.05],
                    "isAdjustment": False,
                },
            },
            {
                "op": "addCamera",
                "params": {
                    "name": "主摄像机",
                    "focalLength": 50,
                },
            },
            {
                "op": "addLight",
                "params": {
                    "name": "主灯光",
                    "lightType": "Point",
                    "intensity": 100,
                    "color": [1, 0.95, 0.9],
                },
            },
            {
                "op": "addLight",
                "params": {
                    "name": "补光",
                    "lightType": "Ambient",
                    "intensity": 30,
                    "color": [0.6, 0.65, 0.8],
                },
            },
        ],
        "effects": [
            {
                "params": {
                    "layerName": "3D背景",
                    "effectName": "ADBE Glo2",
                },
            },
        ],
        "render_settings": {
            "outputPath": f"{_DEFAULT_OUTPUT_DIR}/3d_scene.mp4",
            "format": "mp4",
            "preset": "H.264",
        },
    },
}


def get_preset_names() -> List[str]:
    """获取所有预设名称列表"""
    return list(COMPOSITION_PRESETS.keys())


def get_preset(name: str) -> Dict[str, Any]:
    """获取指定预设配置

    Args:
        name: 预设键名

    Returns:
        预设配置字典，不存在则返回空字典
    """
    return COMPOSITION_PRESETS.get(name, {})


def list_presets() -> List[Dict[str, Any]]:
    """列出所有预设的摘要信息"""
    result = []
    for key, cfg in COMPOSITION_PRESETS.items():
        cs = cfg.get("comp_settings", {})
        result.append({
            "key": key,
            "name": cfg.get("name", key),
            "width": cs.get("width", 1920),
            "height": cs.get("height", 1080),
            "frameRate": cs.get("frameRate", 30),
            "duration": cs.get("duration", 10),
            "layers_count": len(cfg.get("layers", [])),
            "effects_count": len(cfg.get("effects", [])),
        })
    return result
