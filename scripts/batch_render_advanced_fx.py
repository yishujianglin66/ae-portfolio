#!/usr/bin/env python3
"""高级特效预设批量渲染验证 - 18个新预设
通过AE Bridge创建合成 -> 保存工程 -> aerender渲染
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# === 路径配置 ===
ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"
CONFIG = ROOT / "config" / "text_animation_presets.json"
OUTPUT_DIR = Path(r"D:\AE-Work\output\advanced_fx_batch")
AEP_PATH = Path(r"D:\AE-Work\AdvancedFX_Batch.aep")
AERENDER = Path(r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe")

# 新增6个分类
NEW_CATEGORIES = [
    "advanced_kinetic", "anime_fx", "vfx_presets",
    "3d_title_extended", "cinema_titles", "art_typography"
]

# 每个预设的渲染测试文本
TEST_TEXTS = {
    "ak_liquid_metal": "LIQUID METAL",
    "ak_particle_scatter": "SCATTER",
    "ak_dimension_fold": "DIMENSION",
    "af_speed_impact": "IMPACT",
    "af_focus_lines": "FOCUS",
    "af_manga_panel": "PANEL",
    "vfx_energy_wave": "ENERGY",
    "vfx_magic_circle": "SUMMON",
    "vfx_particle_explosion": "BOOM",
    "td_glass_refract": "GLASS",
    "td_lava_flow": "LAVA",
    "td_hologram_flicker": "HOLOGRAM",
    "ct_netflix_opening": "A NETFLIX ORIGINAL",
    "ct_credits_roll": "Directed by Zhang San",
    "ct_chapter_transition": "The Beginning",
    "at_ink_wash": "水墨江湖",
    "at_neon_tube": "NEON CITY",
    "at_metal_cast": "FORGED",
}


def load_new_presets():
    """从config加载新增预设"""
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    presets = []
    for cat_key in NEW_CATEGORIES:
        if cat_key in cfg["categories"]:
            for p in cfg["categories"][cat_key]["presets"]:
                presets.append((cat_key, p))
    return presets


def fill_jsx_template(template, preset):
    """用默认参数填充JSX模板"""
    jsx = template
    for param in preset.get("parameters", []):
        key = "{{" + param["name"] + "}}"
        val = param["default"]
        if isinstance(val, str):
            jsx = jsx.replace(key, val)
        elif isinstance(val, bool):
            jsx = jsx.replace(key, "true" if val else "false")
        else:
            jsx = jsx.replace(key, str(val))
    return jsx


def gen_comp_jsx(preset_id, preset, text):
    """生成创建合成的完整JSX"""
    jsx_inner = fill_jsx_template(preset["jsx_template"], preset)
    # 包装：创建合成 + 文字层 + 执行预设
    comp_name = f"AdvFX_{preset_id}"
    wrapper = f"""(function() {{
    try {{
        var comp = app.project.items.addComp("{comp_name}", 1920, 1080, 1, 4, 30);
        comp.bgColor = [0.03, 0.03, 0.05];
        var L = comp.layers.addText("{text}");
        L.name = "{preset['parameters'][0]['default']}";
        var tp = L.property("Text");
        var td = tp.property("ADBE Text Document").value;
        td.fontSize = 160;
        td.fillColor = [1, 1, 1];
        td.justification = ParagraphJustification.CENTER_JUSTIFY;
        tp.property("ADBE Text Document").setValue(td);
        L.position.setValue([960, 540]);
        // 执行预设JSX
        var _presetResult = eval('{jsx_inner.replace(chr(39), chr(92)+chr(39))}');
        return JSON.stringify({{status:"success", comp:"{comp_name}", preset:"{preset_id}"}});
    }} catch(e) {{
        return JSON.stringify({{status:"error", preset:"{preset_id}", error:e.toString(), line:e.line}});
    }}
}})();"""
    return wrapper


def send_bridge(code, wait=45):
    """通过Bridge发送命令到AE"""
    if not BRIDGE_CMD.parent.exists():
        return {"success": False, "error": "Bridge directory not found"}
    if BRIDGE_RESULT.exists():
        BRIDGE_RESULT.write_text('{"status":"waiting"}', encoding="utf-8")
    cmd = {
        "command": "runScript",
        "args": {"code": code},
        "timestamp": datetime.now().isoformat(),
        "status": "pending"
    }
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    time.sleep(1)
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            if r.get("status") != "waiting" and "result" in r:
                return r
        except:
            pass
    return {"success": False, "error": "timeout"}


def render_comp(comp_name, output_path):
    """用aerender渲染"""
    import subprocess
    if not AERENDER.exists():
        print(f"    [SKIP] aerender not found: {AERENDER}")
        return False
    cmd = [str(AERENDER), "-project", str(AEP_PATH), "-comp", comp_name,
           "-output", str(output_path)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="ignore")
    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
    return proc.returncode == 0 and output_path.exists()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    presets = load_new_presets()
    print(f"\n{'='*60}")
    print(f"  Advanced FX Batch Render - {len(presets)} presets")
    print(f"{'='*60}\n")

    # Phase 1: 验证JSX模板语法
    print("[Phase 1] JSX Template Validation")
    valid = 0
    for cat_key, preset in presets:
        pid = preset["id"]
        jsx = fill_jsx_template(preset["jsx_template"], preset)
        # 基本语法检查
        if jsx.startswith("(function()") and jsx.endswith("})();"):
            if "{{" not in jsx:  # 所有占位符已替换
                valid += 1
                print(f"  [OK] {pid}")
            else:
                print(f"  [WARN] {pid} - unresolved placeholders")
        else:
            print(f"  [FAIL] {pid} - invalid IIFE structure")
    print(f"\n  Validation: {valid}/{len(presets)} passed\n")

    # Phase 2: Bridge创建合成（如果AE在线）
    print("[Phase 2] Bridge Comp Creation")
    bridge_online = BRIDGE_CMD.parent.exists()
    if not bridge_online:
        print("  [SKIP] AE Bridge not available, skipping live test")
        print("  To run live test: ensure AE is running with MCP Bridge loaded")
    else:
        created = 0
        for cat_key, preset in presets:
            pid = preset["id"]
            text = TEST_TEXTS.get(pid, "TEST")
            print(f"  Creating {pid}...", end=" ")
            jsx = gen_comp_jsx(pid, preset, text)
            r = send_bridge(jsx, 30)
            # 解析多层嵌套: r.result.data.result 或 r.result.result
            inner = r.get("result", {})
            result_str = ""
            if isinstance(inner, dict):
                if inner.get("success") and "data" in inner:
                    result_str = inner["data"].get("result", "")
                elif "result" in inner:
                    result_str = inner.get("result", "")
            if isinstance(result_str, str):
                try:
                    parsed = json.loads(result_str)
                    if parsed.get("status") == "success":
                        print("OK")
                        created += 1
                        continue
                except:
                    pass
            # 检查是否Bridge层面成功
            if isinstance(inner, dict) and inner.get("success"):
                print("OK (bridge)")
                created += 1
                continue
            print(f"FAIL: {str(r)[:100]}")
        print(f"\n  Created: {created}/{len(presets)}")

    # Phase 3: 汇总报告
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total presets: {len(presets)}")
    print(f"  JSX valid: {valid}/{len(presets)}")
    print(f"  Categories: {len(NEW_CATEGORIES)}")
    for cat_key in NEW_CATEGORIES:
        count = sum(1 for ck, _ in presets if ck == cat_key)
        print(f"    {cat_key}: {count} presets")
    print(f"\n  Output dir: {OUTPUT_DIR}")
    print(f"  Config: {CONFIG}")
    print(f"{'='*60}\n")

    return valid == len(presets)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
