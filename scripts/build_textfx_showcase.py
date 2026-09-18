#!/usr/bin/env python3
"""TextFX Showcase - Bridge文件协议执行JSX + aerender渲染"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

JSX_PATH = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\temp\textfx_showcase_simple.jsx")
BRIDGE_CMD = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_command.json")
BRIDGE_RESULT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_result.json")
AEP_PATH = Path(r"D:\AE-Work\TextFX_Showcase.aep")
OUTPUT_PATH = Path(r"D:\AE-Work\output\TextFX_Showcase.mp4")
AERENDER = Path(r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe")
COMP_NAME = "TextFX_Showcase"

def send_bridge(code, wait=60):
    """通过Bridge文件协议执行JSX代码"""
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": datetime.now().isoformat(), "status": "pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            if "success" in r or "error" in r:
                return r
        except: pass
        if i % 10 == 9: print(f"  等待... ({i+1}s)")
    return {"success": False, "error": "timeout"}

def step1_build():
    print("=" * 60)
    print("Step 1: Bridge执行JSX构建")
    print("=" * 60)
    jsx = JSX_PATH.read_text(encoding="utf-8")
    print(f"JSX: {len(jsx)} chars, {len(jsx.splitlines())} lines")
    r = send_bridge(jsx, 180)
    print(f"Result: {json.dumps(r, ensure_ascii=False)[:500]}")
    return r.get("success", False)

def step2_save():
    print("\n" + "=" * 60)
    print("Step 2: 保存工程")
    print("=" * 60)
    aep = str(AEP_PATH).replace("\\", "/")
    code = f'(function(){{try{{var f=new File("{aep}");app.project.save(f);return "saved:"+f.fsName;}}catch(e){{return "error:"+e;}}}})();'
    r = send_bridge(code, 30)
    print(f"Result: {json.dumps(r, ensure_ascii=False)[:300]}")
    if AEP_PATH.exists():
        print(f"OK: {AEP_PATH} ({AEP_PATH.stat().st_size/1024:.1f} KB)")
        return True
    return r.get("success", False)

def step3_render():
    print("\n" + "=" * 60)
    print("Step 3: aerender渲染")
    print("=" * 60)
    if not AEP_PATH.exists():
        print(f"ERROR: {AEP_PATH} not found"); return False
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(AERENDER), "-project", str(AEP_PATH), "-comp", COMP_NAME,
           "-output", str(OUTPUT_PATH),
           "-OMtemplate", "H.264 - Match Render Settings - 15 Mbps",
           "-RStemplate", "Best Settings", "-mp", "2"]
    print(f"命令: {' '.join(cmd)}\n")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="ignore")
    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None: break
        line = line.strip()
        if "PROGRESS" in line and any(k in line for k in
            ["Starting","Finished","Total Time","0:00:00:00","0:00:05:00",
             "0:00:10:00","0:00:15:00","0:00:20:00","0:00:24:"]):
            print(f"  {line[:150]}")
    if proc.returncode == 0 and OUTPUT_PATH.exists():
        mb = OUTPUT_PATH.stat().st_size / (1024*1024)
        print(f"\nOK! {OUTPUT_PATH} ({mb:.2f} MB)")
        return True
    print(f"\nFailed (exit={proc.returncode})")
    return False

if __name__ == "__main__":
    print("\nTextFX Showcase - Bridge+aerender全自动\n")
    if not step1_build(): print("JSX执行失败"); sys.exit(1)
    if not step2_save(): print("保存失败"); sys.exit(1)
    if not step3_render(): print("渲染失败"); sys.exit(1)
    print(f"\n{'='*60}\nALL DONE!\n输出: {OUTPUT_PATH}\n工程: {AEP_PATH}\n{'='*60}")

