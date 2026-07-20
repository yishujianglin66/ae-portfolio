"""
send_v17_with_fonts.py
=======================
V17 冰海战记 + 字体规范融合实战版

继承自 send_v17_pro.py 的7项V17改进（字体系统/字幕/Timewarp/RGB Glitch/
CC Particle World等），叠加本项目的 font_manager 风格化设计经验：

- 8大场景→字体映射
- 5种动画配方 (bounce_in / kinetic_smash / glitch_pop / tracking_fade / typewriter)
- 23款预审可用字体（本地安装的3038款中精选）
- 自动按场景拉取对应字体注入JSX
- 完整的 PostScript 名 + 颜色 + 描边 一键生成

执行模式:
    py send_v17_with_fonts.py            # 走 MCP Bridge
    py send_v17_with_fonts.py --dry      # 仅生成JSX到文件不发送
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT))

from core.font_manager import FontManager  # noqa: E402


# V17 5段结构 (1080x1920 / 30fps / 23.15s)
WIDTH = 1080
HEIGHT = 1920
DURATION = 23.15
VISUAL_ADVANCE = 0.0  # 节拍视觉提前量(秒)

# 5段场景列表 - 每段指定字体+动画+文字
SCENES = [
    # 0-4s Intro 史诗开场
    {
        "name": "Intro",
        "start": 0.0, "end": 4.0,
        "texts": [
            {"text": "VINLAND SAGA", "scene": "intro_hero",
             "y": HEIGHT * 0.08, "size": 88, "anim": "bounce_in",
             "start": 0.3, "end": 3.8},
            {"text": "冰 海 战 记", "scene": "intro_hero",
             "y": HEIGHT * 0.18, "size": 56, "anim": "tracking_fade",
             "start": 1.0, "end": 3.8},
            {"text": "—— 战士的史诗 ——", "scene": "intro_credit",
             "y": HEIGHT * 0.24, "size": 30, "anim": "tracking_fade",
             "start": 2.0, "end": 3.6},
        ],
    },
    # 4-9s Build 情绪铺垫
    {
        "name": "Build",
        "start": 4.0, "end": 9.0,
        "texts": [
            {"text": "当战争的火焰再次燃起", "scene": "build_action",
             "y": HEIGHT * 0.85, "size": 36, "anim": "tracking_fade",
             "start": 5.0, "end": 7.5},
            {"text": "THE SAGA CONTINUES", "scene": "build_action",
             "y": HEIGHT * 0.88, "size": 26, "anim": "tracking_fade",
             "start": 7.5, "end": 9.0},
        ],
    },
    # 9-15s Drop 战斗高潮
    {
        "name": "Drop",
        "start": 9.0, "end": 15.0,
        "texts": [
            {"text": "BATTLE", "scene": "drop_battle_en",
             "y": HEIGHT * 0.80, "size": 110, "anim": "kinetic_smash",
             "start": 9.0, "end": 10.8},
            {"text": "VS", "scene": "drop_battle_en",
             "y": HEIGHT * 0.50, "size": 140, "anim": "kinetic_smash",
             "start": 11.5, "end": 12.5},
            {"text": "REDEMPTION", "scene": "drop_battle_en",
             "y": HEIGHT * 0.20, "size": 80, "anim": "bounce_in",
             "start": 13.0, "end": 14.8},
            # 卡点战吼字 (V17 Drop段核心)
            {"text": "战", "scene": "drop_battle_cn",
             "y": HEIGHT * 0.65, "size": 130, "anim": "kinetic_smash",
             "start": 9.3, "end": 9.7},
            {"text": "斗", "scene": "drop_battle_cn",
             "y": HEIGHT * 0.65, "size": 130, "anim": "kinetic_smash",
             "start": 10.4, "end": 10.8},
            {"text": "提尔芬", "scene": "drop_battle_cn",
             "y": HEIGHT * 0.65, "size": 80, "anim": "bounce_in",
             "start": 11.2, "end": 12.0},
            {"text": "蛇", "scene": "drop_battle_cn",
             "y": HEIGHT * 0.65, "size": 130, "anim": "kinetic_smash",
             "start": 13.5, "end": 13.9},
        ],
    },
    # 15-19s Break 留白
    {
        "name": "Break",
        "start": 15.0, "end": 19.0,
        "texts": [
            {"text": "战争之后……", "scene": "break_memory",
             "y": HEIGHT * 0.50, "size": 40, "anim": "tracking_fade",
             "start": 15.5, "end": 17.5},
            {"text": "REDEMPTION", "scene": "break_quote",
             "y": HEIGHT * 0.56, "size": 30, "anim": "tracking_fade",
             "start": 17.0, "end": 18.8},
        ],
    },
    # 19-23.15s Outro 收尾
    {
        "name": "Outro",
        "start": 19.0, "end": 23.15,
        "texts": [
            {"text": "VINLAND SAGA", "scene": "outro_hero",
             "y": HEIGHT * 0.38, "size": 80, "anim": "bounce_in",
             "start": 19.5, "end": 22.5},
            {"text": "冰 海 战 记", "scene": "outro_hero",
             "y": HEIGHT * 0.46, "size": 50, "anim": "tracking_fade",
             "start": 20.0, "end": 22.5},
            {"text": "— FIN —", "scene": "outro_credit",
             "y": HEIGHT * 0.55, "size": 36, "anim": "tracking_fade",
             "start": 21.5, "end": 23.0},
            {"text": "Director: Vinland Saga Team", "scene": "outro_credit",
             "y": HEIGHT * 0.92, "size": 18, "anim": "tracking_fade",
             "start": 22.3, "end": 23.1},
        ],
    },
]


def build_text_blocks(fm: FontManager) -> tuple[str, list[dict]]:
    """根据SCENES生成所有JSX文本块 + 用到的字体元信息"""
    blocks = []
    used_fonts: list[dict] = []
    seen_keys: set = set()

    for seg in SCENES:
        for txt in seg["texts"]:
            preset = fm.get_scene_font(txt["scene"])
            if not preset:
                continue
            jsx = fm.generate_apply_jsx(
                font_key=preset["key"],
                text=txt["text"],
                font_size=txt["size"],
                start_t=txt["start"],
                end_t=txt["end"],
                y_pos=txt["y"],
                anim=txt["anim"],
                x_center=WIDTH / 2,
            )
            blocks.append(f"// === {seg['name']} :: {txt['scene']} :: {txt['text']} ===\n{jsx}")
            if preset["key"] not in seen_keys:
                seen_keys.add(preset["key"])
                used_fonts.append({
                    "key": preset["key"],
                    "name": preset["name"],
                    "postscript": preset["postscript"],
                    "tag": preset.get("tag", ""),
                    "sample_text": preset.get("sample_text", ""),
                })
    return "\n\n".join(blocks), used_fonts


def build_full_jsx(text_jsx: str) -> str:
    """包装完整的V17 IIFE - 包含场景段落/字体/字幕全部逻辑"""
    return f'''(function(){{var _r={{}};try{{
var proj=app.project;
var existing=null;
for(var _i=1;_i<=proj.numItems;_i++){{if(proj.item(_i).name==="V17_Font_Edition"){{existing=proj.item(_i);break;}}}}
if(existing){{existing.remove();}}
var comp=proj.items.addComp("V17_Font_Edition",{WIDTH},{HEIGHT},1,{DURATION},30);
comp.bgColor=[0.02,0.02,0.05];
_r.compName=comp.name;_r.width={WIDTH};_r.height={HEIGHT};_r.duration={DURATION};
{text_jsx}
_r.status="success";_r.textBlocks={sum(len(s["texts"]) for s in SCENES)};
}}catch(e){{_r={{status:"error",message:e.toString()}};}}
return JSON.stringify(_r);}})();'''


def send_via_mcp(jsx_content: str) -> dict:
    """通过MCP Bridge发送JSX到AE"""
    cmd_path = PROJECT_ROOT / ".ae-mcp-bridge" / "ae_command.json"
    res_path = PROJECT_ROOT / ".ae-mcp-bridge" / "ae_result.json"
    if res_path.exists():
        res_path.unlink()
    payload = {
        "command": "executeAtomScript",
        "script": jsx_content,
        "processed": False,
        "description": "V17_cinematic_with_fonts",
    }
    cmd_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    time.sleep(5)
    if res_path.exists():
        return json.loads(res_path.read_text(encoding="utf-8"))
    return {"status": "timeout", "message": "AE Bridge 未在5秒内响应"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="只生成JSX不发送")
    args = parser.parse_args()

    fm = FontManager()

    print("=" * 60)
    print("V17 字体规范融合版 - 实战生成")
    print("=" * 60)
    print(f"已配置字体: {len(fm.list_presets())} 款")
    print(f"系统安装:   {fm.installed_count} 个")

    validation = fm.validate_all_presets()
    available = [v for v in validation if v["installed"]]
    print(f"可用预设:   {len(available)}/{len(validation)}")
    print()

    text_jsx, used_fonts = build_text_blocks(fm)
    full_jsx = build_full_jsx(text_jsx)

    print("=== 场景→字体映射 ===")
    for uf in used_fonts:
        ok = fm.is_font_installed(uf["name"], uf["postscript"])
        mark = "OK" if ok else "MISS"
        print(f"  [{mark}] {uf['key']:<22} -> {uf['name']:<22} ({uf['tag']})")
    print()

    out_dir = PROJECT_ROOT / "output_production" / "v17_fonts"
    out_dir.mkdir(parents=True, exist_ok=True)
    jsx_file = out_dir / "v17_font_edition.jsx"
    jsx_file.write_text(full_jsx, encoding="utf-8")
    print(f"JSX 已生成: {jsx_file} ({len(full_jsx):,} chars)")

    info_file = out_dir / "v17_font_info.json"
    info_file.write_text(
        json.dumps(
            {
                "scenes": SCENES,
                "used_fonts": used_fonts,
                "styling_guide": fm.get_styling_guide(),
                "validation": validation,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"字体信息:   {info_file}")

    if args.dry:
        print("\n[DRY 模式] 已跳过 MCP Bridge 发送")
        return

    print("\n>>> 推送到 AE Bridge ...")
    result = send_via_mcp(full_jsx)
    print(f"AE 响应: {json.dumps(result, ensure_ascii=False)[:300]}")


if __name__ == "__main__":
    main()
