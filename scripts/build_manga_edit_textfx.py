#!/usr/bin/env python3
"""MangaEdit TextFX - Bridge执行JSX + aerender渲染全自动"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

JSX_PATH = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\temp\manga_edit_textfx.jsx")
BRIDGE_CMD = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_command.json")
BRIDGE_RESULT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_result.json")
AEP_PATH = Path(r"D:\AE-Work\MangaEdit_TextFX.aep")
OUTPUT_PATH = Path(r"D:\AE-Work\output\MangaEdit_TextFX.mp4")
AERENDER = Path(r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe")
COMP_NAME = "MangaEdit_TextFX"

def send_bridge(code, wait=60):
    """通过Bridge文件协议执行JSX代码"""
    # 清除旧结果
    if BRIDGE_RESULT.exists():
        BRIDGE_RESULT.write_text('{"status":"waiting"}', encoding="utf-8")
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": datetime.now().isoformat(), "status": "pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    print(f"  [SENT] {datetime.now().strftime('%H:%M:%S')}")
    time.sleep(1)  # 等待Bridge开始处理
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            if r.get("status") == "waiting":
                continue
            if "result" in r or ("success" in r and r.get("success") is not None):
                return r
        except: pass
        if i % 10 == 9: print(f"  等待... ({i+1}s)")
    return {"success": False, "error": "timeout"}

def step1_build():
    print("=" * 60)
    print("Step 1: Bridge执行JSX构建漫剪特效工程")
    print("=" * 60)
    jsx = JSX_PATH.read_text(encoding="utf-8")
    print(f"  JSX: {len(jsx)} chars, {len(jsx.splitlines())} lines")
    r = send_bridge(jsx, 180)
    result_str = json.dumps(r, ensure_ascii=False)[:500]
    print(f"  Result: {result_str}")
    # 检查结果 - bridge返回格式: {"command":"runScript","status":"success","result":{...}}
    if r.get("status") == "success":
        inner = r.get("result", {})
        if isinstance(inner, dict):
            if inner.get("success") == True:
                inner_result = inner.get("result", "")
                if isinstance(inner_result, str):
                    try:
                        parsed = json.loads(inner_result)
                        if parsed.get("status") == "success":
                            return True
                        elif parsed.get("status") == "saved":
                            return True
                    except: pass
                return True
        return True
    return False

def step2_verify():
    print("\n" + "=" * 60)
    print("Step 2: 验证工程文件")
    print("=" * 60)
    if AEP_PATH.exists():
        mb = AEP_PATH.stat().st_size / (1024*1024)
        print(f"  OK: {AEP_PATH} ({mb:.2f} MB)")
        return True
    # 尝试通过Bridge保存
    print("  AEP不存在，尝试Bridge保存...")
    aep_unix = str(AEP_PATH).replace("\\", "/")
    code = f'(function(){{try{{var f=new File("{aep_unix}");app.project.save(f);return JSON.stringify({{status:"saved",path:f.fsName}});}}catch(e){{return JSON.stringify({{status:"error",err:e.toString()}});}}}})();'
    r = send_bridge(code, 30)
    print(f"  Save result: {json.dumps(r, ensure_ascii=False)[:300]}")
    if AEP_PATH.exists():
        mb = AEP_PATH.stat().st_size / (1024*1024)
        print(f"  OK: {AEP_PATH} ({mb:.2f} MB)")
        return True
    return False

def step3_render():
    print("\n" + "=" * 60)
    print("Step 3: aerender渲染输出")
    print("=" * 60)
    if not AEP_PATH.exists():
        print(f"  ERROR: {AEP_PATH} not found")
        return False
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(AERENDER), "-project", str(AEP_PATH), "-comp", COMP_NAME,
           "-output", str(OUTPUT_PATH)]
    print(f"  命令: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="ignore")
    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None: break
        line = line.strip()
        if "PROGRESS" in line:
            print(f"  {line[:150]}")
    if proc.returncode == 0 and OUTPUT_PATH.exists():
        mb = OUTPUT_PATH.stat().st_size / (1024*1024)
        print(f"\n  OK! {OUTPUT_PATH} ({mb:.2f} MB)")
        return True
    print(f"\n  Failed (exit={proc.returncode})")
    return False

if __name__ == "__main__":
    print("\nMangaEdit TextFX - 漫剪风格文字特效全自动构建\n")
    ok = step1_build()
    if not ok:
        print("\n[FAIL] JSX执行失败")
        sys.exit(1)
    if not step2_verify():
        print("\n[FAIL] 工程保存失败")
        sys.exit(1)
    if not step3_render():
        print("\n[FAIL] 渲染失败")
        sys.exit(1)
    print(f"\n{'='*60}")
    print("ALL DONE!")
    print(f"输出: {OUTPUT_PATH}")
    print(f"工程: {AEP_PATH}")
    print(f"{'='*60}")
