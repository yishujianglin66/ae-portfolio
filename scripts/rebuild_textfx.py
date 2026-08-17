#!/usr/bin/env python3
"""TextFX Showcase 重建工程 + 渲染 - 修复黑屏问题
步骤：
1. 关闭旧工程（不保存）
2. 新建空工程
3. 通过 Bridge 执行简化版 JSX（创建 8 图层合成）
4. 保存到 D:/AE-Work/TextFX_Showcase.aep
5. 诊断：验证 8 个图层都创建成功
6. aerender 渲染到 mp4
"""
import json, time, subprocess, sys
from pathlib import Path
from datetime import datetime

BRIDGE_CMD = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_command.json")
BRIDGE_RESULT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_result.json")
JSX_PATH = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\temp\textfx_showcase_simple.jsx")
AEP_PATH = Path(r"D:\AE-Work\TextFX_Showcase.aep")
OUTPUT_PATH = Path(r"D:\AE-Work\output\TextFX_Showcase.mp4")
AERENDER = Path(r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe")
COMP_NAME = "TextFX_Showcase"


def send_bridge(code, wait=120):
    """发送 JSX 到 Bridge 并等待结果。
    Bridge 返回: {"command":"runScript","status":"success","result":{"success":true,"data":{"result":"<inner JSON>"}}}
    """
    ts = datetime.now().isoformat()
    cmd = {"command": "runScript", "args": {"code": code}, "timestamp": ts, "status": "pending"}
    try: BRIDGE_RESULT.unlink()
    except: pass
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            status = r.get("status")
            if status == "success" or "success" in r or "error" in r or status == "error":
                # 统一格式：把 result 内的 dict 字段提升到顶层
                if isinstance(r.get("result"), dict):
                    for k, v in r["result"].items():
                        if k not in r: r[k] = v
                return r
        except: pass
        if i % 10 == 9: print(f"  等待... ({i+1}s)")
    return {"success": False, "error": "timeout"}


def extract_inner(r):
    """从 Bridge 返回中提取 JSX 字符串返回值"""
    # 优先 r.data.result（旧格式）
    if isinstance(r.get("data"), dict) and r["data"].get("result"):
        return r["data"]["result"]
    # 再试 r.result.result（新格式）
    if isinstance(r.get("result"), dict) and r["result"].get("result"):
        return r["result"]["result"]
    return "{}"


def step1_clean_project():
    """关闭旧工程，新建空工程"""
    print("=" * 60)
    print("Step 1: 关闭旧工程，新建空工程")
    print("=" * 60)
    code = r"""
(function(){
  try {
    // 关闭当前工程，不保存
    if (app.project) {
      try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); } catch(e) {}
    }
    // 新建空工程
    app.newProject();
    // 确保工程存在
    if (!app.project) { return JSON.stringify({status:"error", error:"no project after new"}); }
    return JSON.stringify({status:"success", numItems: app.project.numItems});
  } catch(e) {
    return JSON.stringify({status:"error", error:e.toString(), line:e.line});
  }
})();
"""
    r = send_bridge(code, 60)
    inner = extract_inner(r)
    try:
        d = json.loads(inner)
        print(f"  结果: {d}")
        if d.get("status") == "success":
            print(f"  OK: 新工程已创建，items={d['numItems']}")
            return True
        print(f"  FAIL: {d.get('error')}")
        return False
    except Exception as e:
        print(f"  解析失败: {e}, inner={inner[:200]}")
        return False


def step2_build_layers():
    """执行简化版 JSX 创建合成与图层"""
    print("\n" + "=" * 60)
    print("Step 2: 执行简化版 JSX 创建合成与图层")
    print("=" * 60)
    jsx = JSX_PATH.read_text(encoding="utf-8")
    print(f"  JSX: {len(jsx)} chars, {len(jsx.splitlines())} lines")
    r = send_bridge(jsx, 180)
    inner = extract_inner(r)
    try:
        d = json.loads(inner)
        print(f"  结果: {d}")
        if d.get("status") == "success":
            print(f"  OK: 合成 '{d.get('comp')}' 已创建，layers={d.get('layers')}, duration={d.get('duration')}s")
            return True
        print(f"  FAIL: {d.get('error')}")
        return False
    except Exception as e:
        print(f"  解析失败: {e}, inner={inner[:500]}")
        return False


def step3_save_project():
    """保存工程"""
    print("\n" + "=" * 60)
    print("Step 3: 保存工程")
    print("=" * 60)
    aep_str = str(AEP_PATH).replace("\\", "/")
    code = f'(function(){{try{{var f=new File("{aep_str}");app.project.save(f);return JSON.stringify({{status:"success",path:f.fsName}});}}catch(e){{return JSON.stringify({{status:"error",error:e.toString()}});}}}})();'
    r = send_bridge(code, 60)
    inner = extract_inner(r)
    try:
        d = json.loads(inner)
        if d.get("status") == "success":
            print(f"  OK: {d['path']}")
            if AEP_PATH.exists():
                print(f"  文件大小: {AEP_PATH.stat().st_size/1024:.1f} KB")
            return True
        print(f"  FAIL: {d.get('error')}")
        return False
    except Exception as e:
        print(f"  解析失败: {e}, inner={inner[:200]}")
        return False


def step4_diagnose():
    """诊断：验证 8 个图层都创建成功，每个图层时间范围正确"""
    print("\n" + "=" * 60)
    print("Step 4: 诊断工程状态")
    print("=" * 60)
    diag_jsx = r"""
(function(){
  try {
    var comp = null;
    for (var i=1; i<=app.project.numItems; i++) {
      var it = app.project.item(i);
      if (it instanceof CompItem && it.name === "%COMP%") { comp = it; break; }
    }
    if (!comp) return JSON.stringify({status:"error", error:"comp not found"});
    var info = {
      status: "ok",
      comp: {name:comp.name, numLayers:comp.numLayers, duration:comp.duration, frameRate:comp.frameRate, bgColor:[comp.bgColor[0],comp.bgColor[1],comp.bgColor[2]]},
      layers: []
    };
    for (var k=1; k<=comp.numLayers; k++) {
      var L = comp.layer(k);
      var opAt0 = null, opAtMid = null;
      try {
        opAt0 = L.property("Transform").property("Opacity").valueAtTime(0, false);
        // 取该图层中点的 opacity
        var mid = L.inPoint + (L.outPoint - L.inPoint)/2;
        opAtMid = L.property("Transform").property("Opacity").valueAtTime(mid, false);
      } catch(e) {}
      info.layers.push({
        index:k, name:L.name, enabled:L.enabled,
        inPoint:L.inPoint, outPoint:L.outPoint, startTime:L.startTime,
        opacityAt0: opAt0, opacityAtMid: opAtMid
      });
    }
    return JSON.stringify(info);
  } catch(e) { return JSON.stringify({status:"error", error:e.toString(), line:e.line}); }
})();
""".replace("%COMP%", COMP_NAME)
    r = send_bridge(diag_jsx, 60)
    inner = extract_inner(r)
    try:
        d = json.loads(inner)
        if d.get("status") != "ok":
            print(f"  FAIL: {d.get('error')}")
            return False
        c = d["comp"]
        print(f"  合成: {c['name']}, layers={c['numLayers']}, duration={c['duration']}s, fps={c['frameRate']}, bg={c['bgColor']}")
        if c["numLayers"] < 8:
            print(f"  ⚠ 图层数 {c['numLayers']} < 8，期望 8 个")
        for L in d["layers"]:
            print(f"  [{L['index']}] {L['name']}: enabled={L['enabled']} inPoint={L['inPoint']:.2f}s outPoint={L['outPoint']:.2f}s opacity@0={L['opacityAt0']} opacity@mid={L['opacityAtMid']}")
        return c["numLayers"] >= 8
    except Exception as e:
        print(f"  解析失败: {e}, inner={inner[:300]}")
        return False


def step5_render():
    """aerender 渲染"""
    print("\n" + "=" * 60)
    print("Step 5: aerender 渲染")
    print("=" * 60)
    if not AEP_PATH.exists():
        print(f"  ERROR: {AEP_PATH} not found")
        return False
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 删除旧输出
    try: OUTPUT_PATH.unlink()
    except: pass
    # 不指定 OMtemplate，让 AE 使用默认的 Lossless 输出
    # 先用 AVI 无损测试，排除 H.264 编码问题
    avi_output = OUTPUT_PATH.with_suffix(".avi")
    try: avi_output.unlink()
    except: pass
    cmd = [str(AERENDER), "-project", str(AEP_PATH), "-comp", COMP_NAME,
           "-output", str(avi_output),
           "-RStemplate", "Best Settings",
           "-mp", "2"]
    print(f"  命令: {' '.join(cmd)}\n")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="ignore", bufsize=1)
    last_progress = ""
    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None: break
        line = line.strip()
        if not line: continue
        # 只打印关键进度行
        if "PROGRESS" in line and ("%" in line or "Finished" in line or "Starting" in line or "Total Time" in line):
            # 只在新进度行变化大时打印
            if line != last_progress:
                if "%" in line:
                    pct = line[line.find("PROGRESS"):][:30]
                    print(f"  {pct}")
                else:
                    print(f"  {line[:150]}")
                last_progress = line
    err = proc.stderr.read() if proc.stderr else ""
    if proc.returncode != 0:
        print(f"\n  渲染失败 exit={proc.returncode}")
        if err: print(f"  stderr: {err[:500]}")
        return False
    if avi_output.exists():
        size_mb = avi_output.stat().st_size / (1024*1024)
        print(f"\n  OK: {avi_output} ({size_mb:.2f} MB)")
        return True
    print(f"\n  渲染完成但输出文件不存在")
    return False


if __name__ == "__main__":
    print("\nTextFX Showcase - 重建工程 + 渲染（黑屏修复）\n")
    if not step1_clean_project(): print("\n步骤1失败"); sys.exit(1)
    if not step2_build_layers(): print("\n步骤2失败"); sys.exit(1)
    if not step3_save_project(): print("\n步骤3失败"); sys.exit(1)
    if not step4_diagnose(): print("\n步骤4诊断失败 - 图层数不对"); sys.exit(1)
    if not step5_render(): print("\n步骤5渲染失败"); sys.exit(1)
    print(f"\n{'='*60}\nALL DONE!\n输出: {OUTPUT_PATH.with_suffix('.avi')}\n工程: {AEP_PATH}\n{'='*60}")
