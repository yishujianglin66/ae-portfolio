#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将知识库提取的20个现代风格预设整合到现有JSON预设文件中"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path


def _infer_param_type(key: str, value) -> str:
    """推断参数类型"""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        if value.replace(".", "").replace("-", "").isdigit():
            return "number"
        try:
            float(value)
            return "number"
        except ValueError:
            pass
        return "string"
    return "string"


def _infer_param_meta(key: str, value, preset_name: str) -> dict:
    """推断参数的元数据（min/max/description）"""
    meta = {"type": _infer_param_type(key, value)}

    # 根据参数名推断描述和范围
    desc_map = {
        "textLayerName": "目标文字图层名",
        "fallHeight": "下落距离 (px)",
        "charDelay": "字间错开帧数",
        "duration": "动画总时长 (秒)",
        "trackingAmount": "字距变化量 (px)",
        "frequency": "频率 (Hz)",
        "danceHeight": "跳跃距离 (px)",
        "bounceHeight": "弹跳距离 (px)",
        "bpm": "节拍速度 (BPM)",
        "waveAmplitude": "波浪高度 (px)",
        "waveFrequency": "波浪密度 (Hz)",
        "waveSpeed": "流动快慢",
        "splitAmount": "通道分离量 (px)",
        "neonColor": "霓虹颜色 [R,G,B]",
        "pulseSpeed": "脉冲频率 (Hz)",
        "glowRadius": "辉光范围 (px)",
        "scanSpeed": "扫描频率",
        "lineSpacing": "线条间距 (px)",
        "holoColor": "全息颜色 [R,G,B]",
        "fallSpeed": "下落速度 (px/s)",
        "matrixColor": "矩阵颜色 [R,G,B]",
        "streamSpeed": "字符变换速度",
        "charRange": "字符偏移范围",
        "lightIntensity": "光爆亮度",
        "metalColor": "金属颜色 [R,G,B]",
        "shineAngle": "光泽方向 (度)",
        "rayIntensity": "光线亮度",
        "rayColor": "光线颜色 [R,G,B]",
        "flareBrightness": "光晕强度",
        "flareColor": "光晕颜色 [R,G,B]",
        "shakeIntensity": "震动幅度 (px)",
        "bounceScale": "回弹峰值缩放 (%)",
        "scrollSpeed": "滚动快慢 (px/s)",
        "yPosition": "垂直位置 (px)",
        "strokeWidth": "描边粗细 (px)",
        "jitterAmount": "抖动幅度 (px)",
        "cycleSpeed": "色相旋转速度",
        "saturation": "颜色饱和度 (%)",
        "flashCount": "闪烁次数",
    }

    meta["description"] = desc_map.get(key, key)

    # 推断范围
    range_map = {
        "fallHeight": (50, 1000),
        "charDelay": (0, 15),
        "duration": (0.3, 5.0),
        "trackingAmount": (1, 50),
        "frequency": (0.2, 10.0),
        "danceHeight": (5, 100),
        "bounceHeight": (5, 150),
        "bpm": (60, 200),
        "waveAmplitude": (5, 100),
        "waveFrequency": (0.5, 8.0),
        "waveSpeed": (0.1, 5.0),
        "splitAmount": (2, 80),
        "pulseSpeed": (0.2, 10.0),
        "glowRadius": (5, 100),
        "scanSpeed": (0.2, 10.0),
        "lineSpacing": (1, 20),
        "fallSpeed": (50, 800),
        "streamSpeed": (1, 30),
        "charRange": (10, 100),
        "lightIntensity": (50, 300),
        "shineAngle": (0, 360),
        "rayIntensity": (20, 300),
        "flareBrightness": (50, 300),
        "shakeIntensity": (0, 50),
        "bounceScale": (110, 200),
        "scrollSpeed": (50, 1000),
        "yPosition": (0, 1080),
        "strokeWidth": (5, 40),
        "jitterAmount": (0, 30),
        "cycleSpeed": (0.1, 5.0),
        "saturation": (0, 100),
        "flashCount": (2, 20),
    }

    if key in range_map:
        meta["min"] = range_map[key][0]
        meta["max"] = range_map[key][1]

    return meta


def convert_kb_preset_to_standard(kb_preset: dict) -> dict:
    """将知识库提取的预设转换为标准JSON格式"""
    # 清理无效参数
    clean_params = {}
    for k, v in kb_preset["parameters"].items():
        if k == "------" or k == "":
            continue
        clean_params[k] = v

    # 构建parameters元数据
    parameters = {}
    for k, v in clean_params.items():
        parameters[k] = _infer_param_meta(k, v, kb_preset["name"])

    # 构建default_values
    default_values = {}
    for k, v in clean_params.items():
        if isinstance(v, list):
            default_values[k] = v
        elif isinstance(v, str):
            # 尝试转换为数字
            try:
                if "." in v:
                    default_values[k] = float(v)
                else:
                    default_values[k] = int(v)
            except ValueError:
                default_values[k] = v
        else:
            default_values[k] = v

    # 推断subcategory
    preset_id = kb_preset.get("preset_id", "")
    subcategory_map = {
        "kt_": "kinetic_typography",
        "cp_": "cyberpunk",
        "ci_": "cinematic",
        "sm_": "social_media",
    }
    subcategory = "general"
    for prefix, sc in subcategory_map.items():
        if preset_id.startswith(prefix):
            subcategory = sc
            break

    return {
        "name": kb_preset["name"],
        "category": kb_preset["category"],
        "subcategory": subcategory,
        "description": kb_preset["description"],
        "tags": kb_preset["tags"],
        "parameters": parameters,
        "default_values": default_values,
        "script_template": kb_preset["script_template"],
        "compatibility": {
            "ae": ["2024", "2025"],
            "platform": ["windows", "macos"]
        }
    }


def integrate_presets():
    """将知识库预设整合到现有JSON文件中"""
    kb_path = Path("output/kb_modern_presets.json")
    kb_presets = json.loads(kb_path.read_text(encoding="utf-8"))

    # 按分类分组
    by_category = {}
    for kp in kb_presets:
        std = convert_kb_preset_to_standard(kp)
        cat = std["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(std)

    # 追加到各分类JSON文件
    presets_dir = Path("ae/presets")
    total_added = 0

    for cat, presets in by_category.items():
        json_file = presets_dir / f"{cat}.json"
        if not json_file.exists():
            print(f"警告: {json_file} 不存在，跳过")
            continue

        existing = json.loads(json_file.read_text(encoding="utf-8"))
        existing_names = {p["name"] for p in existing}

        added = 0
        for p in presets:
            if p["name"] not in existing_names:
                existing.append(p)
                added += 1
                print(f"  [追加] {cat}/{p['name']} ({p['subcategory']})")
            else:
                print(f"  [已存在] {cat}/{p['name']}")

        if added > 0:
            json_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
            total_added += added
            print(f"  -> {json_file.name}: 新增 {added} 个预设")

    print(f"\n总计新增: {total_added} 个预设")
    return total_added


def main():
    print("=== 整合知识库现代风格预设到JSON文件 ===")
    count = integrate_presets()
    if count > 0:
        print("\n重新加载PresetSystem验证...")
        # 重新实例化以加载最新JSON
        import importlib

        import ae.preset_system as ps_mod
        from ae.preset_system import PresetSystem
        importlib.reload(ps_mod)
        ps = ps_mod.PresetSystem()
        print(f"PresetSystem加载: {len(ps.list_presets())} 个预设")
    return 0 if count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
