#!/usr/bin/env python3
"""全量预设渲染 - 109个预设 x 3秒 = 完整视频输出
用法: py -3.12 scripts/render_all_presets_3s.py [--batch N] [--start M]
  --batch N : 每批渲染N个(默认20)
  --start M : 从第M个开始(默认0)
  --create-only : 只创建合成不渲染
  --render-only : 只渲染已创建的合成
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# === 路径 ===
ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"
CONFIG = ROOT / "config" / "text_animation_presets.json"
OUTPUT_DIR = Path(r"D:\AE-Work\output\all_presets_3s")
AEP_PATH = Path(r"D:\AE-Work\AllPresets3s.aep")
AERENDER = Path(r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe")

DURATION = 3.0  # 每个预设3秒
FPS = 30
WIDTH, HEIGHT = 1920, 1080

# 每个预设的展示文字(按分类)
CATEGORY_TEXTS = {
    "kinetic_typography": "KINETIC",
    "cyberpunk": "CYBER",
    "cinematic": "CINEMA",
    "social_media": "SOCIAL",
    "3d_title": "3D TITLE",
    "advanced_kinetic": "ADVANCED",
    "anime_fx": "IMPACT",
    "vfx_presets": "VFX",
    "3d_title_extended": "EXTENDED",
    "cinema_titles": "CHAPTER",
    "art_typography": "ART",
}


def load_all_presets():
    """加载全部预设"""
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    presets = []
    for cat_key, cat_data in cfg["categories"].items():
        for p in cat_data.get("presets", []):
            presets.append({
                "category": cat_key,
                "id": p["id"],
                "name": p.get("name", p["id"]),
                "jsx_template": p.get("jsx_template", ""),
                "parameters": p.get("parameters", []),
            })
    return presets


def fill_template(template, parameters):
    """用默认参数填充模板占位符"""
    jsx = template
    for param in parameters:
        key = "{{" + param["name"] + "}}"
        val = param.get("default", "")
        if isinstance(val, bool):
            jsx = jsx.replace(key, "true" if val else "false")
        elif isinstance(val, str):
            jsx = jsx.replace(key, val)
        else:
            jsx = jsx.replace(key, str(val))
    # 清理未替换的占位符
    import re
    jsx = re.sub(r'\{\{(\w+)\}\}', '0', jsx)
    return jsx


def gen_create_jsx(preset, text):
    """生成创建3秒合成的JSX"""
    pid = preset["id"]
    comp_name = f"P3s_{pid}"
    jsx_inner = fill_template(preset["jsx_template"], preset["parameters"])
    
    # 转义内部JSX中的单引号用于eval
    jsx_escaped = jsx_inner.replace("'", "\\'").replace("\n", " ").replace("\r", "")
    
    wrapper = f"""(function() {{
    try {{
        // 删除同名旧合成
        for (var i = app.project.items.length; i >= 1; i--) {{
            if (app.project.item(i) instanceof CompItem && app.project.item(i).name == "{comp_name}") {{
                app.project.item(i).remove();
            }}
        }}
        var comp = app.project.items.addComp("{comp_name}", {WIDTH}, {HEIGHT}, 1, {DURATION}, {FPS});
        comp.bgColor = [0.02, 0.02, 0.04];
        var L = comp.layers.addText("{text}");
        L.name = "\\u6807\\u9898\\u6587\\u5b57";
        var tp = L.property("Text");
        var td = tp.property("ADBE Text Document").value;
        td.fontSize = 160;
        td.fillColor = [1, 1, 1];
        td.justification = ParagraphJustification.CENTER_JUSTIFY;
        tp.property("ADBE Text Document").setValue(td);
        L.position.setValue([960, 540]);
        // 执行预设
        try {{ eval('{jsx_escaped}'); }} catch(pe) {{}}
        return JSON.stringify({{status:"success", comp:"{comp_name}"}});
    }} catch(e) {{
        return JSON.stringify({{status:"error", error:e.toString(), line:e.line}});
    }}
}})();"""
    return wrapper, comp_name


def send_bridge(code, wait=30):
    """Bridge通信"""
    if not BRIDGE_CMD.parent.exists():
        return {"success": False, "error": "Bridge not found"}
    if BRIDGE_RESULT.exists():
        BRIDGE_RESULT.write_text('{"status":"waiting"}', encoding="utf-8")
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": datetime.now().isoformat(), "status": "pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.5)
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            if r.get("status") != "waiting" and "result" in r:
                return r
        except:
            pass
    return {"success": False, "error": "timeout"}


def parse_bridge_result(r):
    """解析Bridge返回"""
    inner = r.get("result", {})
    if isinstance(inner, dict):
        if inner.get("success") and "data" in inner:
            result_str = inner["data"].get("result", "")
            if isinstance(result_str, str):
                try:
                    parsed = json.loads(result_str)
                    return parsed.get("status") == "success"
                except:
                    pass
            return True
        elif inner.get("success"):
            return True
    return False


def save_project():
    """保存AE工程"""
    aep_unix = str(AEP_PATH).replace("\\", "/")
    code = f'(function(){{try{{var f=new File("{aep_unix}");app.project.save(f);return JSON.stringify({{status:"saved"}});}}catch(e){{return JSON.stringify({{status:"error",err:e.toString()}});}}}})();'
    send_bridge(code, 15)


def render_one(comp_name, output_path):
    """渲染单个合成"""
    if not AERENDER.exists():
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(AERENDER), "-project", str(AEP_PATH), "-comp", comp_name,
           "-output", str(output_path), "-s", "0", "-e", str(DURATION)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="ignore", timeout=120)
        return output_path.exists() and output_path.stat().st_size > 1000
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--create-only", action="store_true")
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    presets = load_all_presets()
    total = len(presets)
    
    print(f"\n{'='*60}")
    print(f"  ALL PRESETS RENDER - {total} presets x {DURATION}s")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"{'='*60}\n")

    # === Phase 1: 创建合成 ===
    if not args.render_only:
        print(f"[Phase 1] Creating comps in AE (start={args.start}, batch={args.batch})")
        end_idx = min(args.start + args.batch, total)
        created = 0
        failed = []
        
        for i in range(args.start, end_idx):
            p = presets[i]
            text = CATEGORY_TEXTS.get(p["category"], "TEXT")
            print(f"  [{i+1}/{total}] {p['id']}...", end=" ", flush=True)
            
            jsx, comp_name = gen_create_jsx(p, text)
            r = send_bridge(jsx, 20)
            
            if parse_bridge_result(r):
                print("OK")
                created += 1
            else:
                err = str(r.get("result", {}).get("error", ""))[:60]
                print(f"FAIL ({err})")
                failed.append(p["id"])
        
        print(f"\n  Created: {created}/{end_idx - args.start}")
        if failed:
            print(f"  Failed: {failed}")
        
        # 保存工程
        print("\n  Saving project...")
        save_project()
        print(f"  Saved: {AEP_PATH}")

    # === Phase 2: 渲染 ===
    if not args.create_only:
        print("\n[Phase 2] Rendering to video")
        if not AERENDER.exists():
            print(f"  [ERROR] aerender not found: {AERENDER}")
            print("  Please install AE or update AERENDER path")
            return
        
        rendered = 0
        end_idx = min(args.start + args.batch, total)
        for i in range(args.start, end_idx):
            p = presets[i]
            comp_name = f"P3s_{p['id']}"
            out_file = OUTPUT_DIR / f"{p['category']}" / f"{p['id']}.mp4"
            print(f"  [{i+1}/{total}] Rendering {p['id']}...", end=" ", flush=True)
            
            if render_one(comp_name, out_file):
                mb = out_file.stat().st_size / (1024*1024)
                print(f"OK ({mb:.1f}MB)")
                rendered += 1
            else:
                print("FAIL")
        
        print(f"\n  Rendered: {rendered}/{end_idx - args.start}")

    # === Summary ===
    print(f"\n{'='*60}")
    print("  DONE")
    print(f"  Total presets: {total}")
    print(f"  Duration each: {DURATION}s")
    print(f"  Total video time: {total * DURATION / 60:.1f} min")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
