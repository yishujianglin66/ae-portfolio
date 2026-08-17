#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从知识库《风格化预设宝典》3.6节提取20种现代风格预设，转换为JSON格式"""
from __future__ import annotations

import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from ae.preset_system import PresetSystem


def parse_param_table(lines: list[str], start_idx: int) -> dict:
    """解析Markdown参数表"""
    params = {}
    i = start_idx
    while i < len(lines) and not lines[i].startswith("```"):
        if lines[i].startswith("|") and "参数" not in lines[i] and "---" not in lines[i]:
            cols = [c.strip() for c in lines[i].split("|")]
            if len(cols) >= 4:
                param_name = cols[1]
                default_val = cols[2]
                # 转换参数名为snake_case英文变量名
                param_key = _cn_param_to_key(param_name)
                params[param_key] = _parse_default(default_val)
        i += 1
    return params, i


def _cn_param_to_key(cn_name: str) -> str:
    """中文参数名转英文snake_case变量名"""
    mapping = {
        "图层名": "textLayerName",
        "下落高度": "fallHeight",
        "字间延迟": "charDelay",
        "持续时间": "duration",
        "字距变化": "trackingAmount",
        "呼吸频率": "frequency",
        "跳跃高度": "danceHeight",
        "跳舞频率": "frequency",
        "弹跳高度": "bounceHeight",
        "BPM 节拍": "bpm",
        "波浪幅度": "waveAmplitude",
        "波浪频率": "waveFrequency",
        "流动速度": "waveSpeed",
        "分离量": "splitAmount",
        "故障频率": "frequency",
        "霓虹色": "neonColor",
        "脉冲速度": "pulseSpeed",
        "辉光半径": "glowRadius",
        "扫描速度": "scanSpeed",
        "扫描线距": "lineSpacing",
        "全息色": "holoColor",
        "下落速度": "fallSpeed",
        "矩阵色": "matrixColor",
        "流动速度_2": "streamSpeed",
        "字符范围": "charRange",
        "光爆强度": "lightIntensity",
        "金属色": "metalColor",
        "光泽角度": "shineAngle",
        "光线强度": "rayIntensity",
        "光线色": "rayColor",
        "光晕亮度": "flareBrightness",
        "光晕色": "flareColor",
        "震动强度": "shakeIntensity",
        "回弹缩放": "bounceScale",
        "滚动速度": "scrollSpeed",
        "Y轴位置": "yPosition",
        "描边宽度": "strokeWidth",
        "抖动量": "jitterAmount",
        "循环速度": "cycleSpeed",
        "饱和度": "saturation",
        "闪现次数": "flashCount",
    }
    return mapping.get(cn_name, cn_name)


def _parse_default(val: str):
    """解析默认值"""
    val = val.strip()
    if val in ("-", ""):
        return ""
    # 尝试数字
    if val.replace(".", "").replace("-", "").isdigit():
        if "." in val:
            return float(val)
        return int(val)
    # 百分比
    if val.endswith("%"):
        try:
            return float(val[:-1]) / 100
        except ValueError:
            pass
    # px单位
    if val.endswith("px"):
        try:
            return float(val[:-2])
        except ValueError:
            pass
    # Hz单位
    if val.endswith("Hz"):
        try:
            return float(val[:-2])
        except ValueError:
            pass
    # s单位
    if val.endswith("s") and val[:-1].replace(".", "").isdigit():
        try:
            return float(val[:-1])
        except ValueError:
            pass
    # 数组 [R,G,B]
    if val.startswith("[") and val.endswith("]"):
        try:
            parts = val[1:-1].split(",")
            return [float(p.strip()) for p in parts]
        except ValueError:
            pass
    return val


def convert_jsx_placeholders(jsx_code: str) -> str:
    """将 {{param}} 转换为 ${param}"""
    return re.sub(r"\{\{(\w+)\}\}", r"${\1}", jsx_code)


def extract_presets_from_kb() -> list[dict]:
    """从知识库3.6节提取20种预设"""
    kb_path = Path("10-风格化剪辑知识库/风格化预设宝典.md")
    content = kb_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    presets = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # 匹配 ##### X.X.X.X 预设名称
        match = re.match(r"^#{5}\s+\d+\.\d+\.\d+\.\d+\s+(.+)$", line)
        if match:
            name_cn = match.group(1).strip()
            # 查找英文名（从JSX代码中的 preset: 字段）
            jsx_code = ""
            param_lines = []
            in_code = False
            j = i + 1
            while j < len(lines) and not re.match(r"^#{5}\s+", lines[j]):
                if lines[j].startswith("```jsx"):
                    in_code = True
                    j += 1
                    continue
                if lines[j].startswith("```") and in_code:
                    in_code = False
                    j += 1
                    continue
                if in_code:
                    jsx_code += lines[j] + "\n"
                if lines[j].startswith("|") and "参数" not in lines[j]:
                    param_lines.append(lines[j])
                j += 1

            # 从JSX中提取preset ID
            preset_id_match = re.search(r"preset:'(\w+)'", jsx_code)
            preset_id = preset_id_match.group(1) if preset_id_match else ""

            # 提取参数
            params = {}
            for pl in param_lines:
                cols = [c.strip() for c in pl.split("|")]
                if len(cols) >= 4 and cols[1] and cols[1] != "参数":
                    param_key = _cn_param_to_key(cols[1])
                    params[param_key] = _parse_default(cols[2])

            # 转换为snake_case名称
            name_snake = _cn_to_snake(name_cn)

            presets.append({
                "name": name_snake,
                "name_cn": name_cn,
                "preset_id": preset_id,
                "description": f"{name_cn} - 现代风格预设",
                "category": _infer_category(name_cn, preset_id),
                "parameters": params,
                "script_template": convert_jsx_placeholders(jsx_code.strip()),
                "tags": _infer_tags(name_cn, preset_id),
            })
            i = j
            continue
        i += 1

    return presets


def _cn_to_snake(cn: str) -> str:
    """中文预设名转snake_case"""
    mapping = {
        "字符瀑布流": "kt_char_waterfall",
        "字距呼吸": "kt_tracking_breathe",
        "文字舞蹈": "kt_text_dance",
        "节拍弹跳": "kt_beat_bounce",
        "字符波浪": "kt_char_wave",
        "RGB分离故障": "cp_rgb_split_glitch",
        "霓虹脉冲": "cp_neon_pulse",
        "全息扫描": "cp_hologram_scan",
        "矩阵雨": "cp_matrix_rain",
        "数据流文字": "cp_data_stream",
        "史诗开场": "ci_epic_opener",
        "金属质感": "ci_metallic_text",
        "光线穿透": "ci_light_rays_text",
        "镜头光晕": "ci_lens_flare_text",
        "大片预告": "ci_trailer_title",
        "抖音弹跳标题": "sm_douyin_bounce",
        "弹幕滚动": "sm_danmaku_scroll",
        "表情包文字": "sm_emoji_text",
        "彩虹渐变标题": "sm_rainbow_gradient",
        "快闪文字": "sm_quick_flash",
    }
    if cn in mapping:
        return mapping[cn]
    # 通用转换
    return re.sub(r"[^\w]+", "_", cn).strip("_").lower()


def _infer_category(name_cn: str, preset_id: str) -> str:
    """推断预设分类"""
    if preset_id.startswith("kt_"):
        return "text_animation"
    if preset_id.startswith("cp_"):
        return "effect"
    if preset_id.startswith("ci_"):
        return "text_animation"
    if preset_id.startswith("sm_"):
        return "text_animation"
    if "文字" in name_cn or "字符" in name_cn or "字距" in name_cn:
        return "text_animation"
    if "故障" in name_cn or "霓虹" in name_cn or "全息" in name_cn or "矩阵" in name_cn:
        return "effect"
    return "text_animation"


def _infer_tags(name_cn: str, preset_id: str) -> list[str]:
    """推断标签"""
    tags = []
    if preset_id.startswith("kt_"):
        tags.extend(["kinetic", "typography", "modern"])
    if preset_id.startswith("cp_"):
        tags.extend(["cyberpunk", "glitch", "neon"])
    if preset_id.startswith("ci_"):
        tags.extend(["cinematic", "film", "title"])
    if preset_id.startswith("sm_"):
        tags.extend(["social", "media", "modern"])
    if "文字" in name_cn or "字符" in name_cn:
        tags.append("text")
    if "故障" in name_cn:
        tags.append("glitch")
    if "霓虹" in name_cn:
        tags.append("neon")
    if "矩阵" in name_cn:
        tags.append("matrix")
    return list(set(tags))


def main():
    print("=== 从知识库提取现代风格预设 ===")
    presets = extract_presets_from_kb()
    print(f"提取到 {len(presets)} 个预设")

    # 检查哪些已存在于JSON中
    ps = PresetSystem()
    existing = set(ps.list_presets())

    new_presets = []
    for p in presets:
        if p["name"] in existing:
            print(f"  [已存在] {p['name']} ({p['name_cn']})")
        else:
            print(f"  [新增] {p['name']} ({p['name_cn']}) - {p['category']}")
            new_presets.append(p)

    print(f"\n新增预设: {len(new_presets)} 个")

    # 保存为JSON
    output = Path("output/kb_modern_presets.json")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(new_presets, f, ensure_ascii=False, indent=2)
    print(f"已保存到: {output}")

    return new_presets


if __name__ == "__main__":
    main()
