#!/usr/bin/env python3
"""
方向一：摄像机运动 + 三维图层 + 运动曲线 深度进阶 (v2 - 高频轮询修复)
=====================================================================
修复: 100ms高频轮询捕获bridge响应(防止MCP面板删除result文件)
"""
import json, time, sys, os, subprocess
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"
OUTPUT_DIR = Path(r"D:\AE-Work\output\advanced_camera")
FRAMES_DIR = ROOT / "frames"


def send_bridge(code, wait=45):
    """高频轮询(100ms)发送JSX到AE Bridge"""
    if not BRIDGE_CMD.parent.exists():
        return {"success": False, "error": "Bridge not found"}
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": datetime.now().isoformat(), "status": "pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(0.1)
        try:
            if not BRIDGE_RESULT.exists():
                continue
            content = BRIDGE_RESULT.read_text(encoding="utf-8")
            if not content or not content.strip():
                continue
            r = json.loads(content)
            if "result" in r and r.get("status") not in ("waiting", "pending", None):
                return r
        except (json.JSONDecodeError, OSError, IOError):
            pass
        except Exception:
            pass
    return {"success": False, "error": "timeout"}


def parse_result(r):
    inner = r.get("result", {})
    if isinstance(inner, dict):
        if inner.get("success") and "data" in inner:
            result_str = inner["data"].get("result", "")
            if isinstance(result_str, str):
                try:
                    parsed = json.loads(result_str)
                    if parsed.get("status") == "success":
                        return True, parsed
                    elif parsed.get("status") == "error":
                        return False, parsed.get("msg", "unknown")
                except:
                    pass
            return True, result_str
        elif inner.get("success"):
            return True, "ok"
        elif "error" in inner:
            return False, inner["error"]
    return False, str(r)[:200]


def render_comp(comp_name, output_path, wait=90):
    """渲染合成到MP4"""
    out_unix = str(output_path).replace("\\", "/")
    jsx = f'''(function() {{
    try {{
        var comp = null;
        for (var i = 1; i <= app.project.items.length; i++) {{
            var it = app.project.item(i);
            if (it instanceof CompItem && it.name == "{comp_name}") {{ comp = it; break; }}
        }}
        if (!comp) return JSON.stringify({{status:"error", msg:"comp not found: {comp_name}"}});
        var outFile = new File("{out_unix}");
        if (outFile.exists) outFile.remove();
        var rq = app.project.renderQueue.items.add(comp);
        var om = rq.outputModule(1);
        try {{ om.applyTemplate("H.264 \u5339\u914d\u6e90 - \u9ad8\u6bd4\u7279\u7387"); }} catch(e) {{
            try {{ om.applyTemplate("Lossless"); }} catch(e2) {{}}
        }}
        om.file = outFile;
        rq.render();
        rq.remove();
        return JSON.stringify({{status:"success", msg:"rendered"}});
    }} catch(e) {{
        return JSON.stringify({{status:"error", msg: e.toString()}});
    }}
}})();'''
    print(f"  渲染 {comp_name}...")
    r = send_bridge(jsx, wait=wait)
    ok, data = parse_result(r)
    print(f"  {'✓' if ok else '✗'} {data if not ok else 'done'}")
    return ok


def verify_animation(video_path, threshold=15):
    """帧差异验证"""
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        print("  ! PIL不可用,跳过验证")
        return True
    vpath = str(video_path)
    f1 = str(FRAMES_DIR / "adv_f1.png")
    f2 = str(FRAMES_DIR / "adv_f2.png")
    for t, fp in [(0.3, f1), (2.5, f2)]:
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", vpath, "-frames:v", "1", fp],
                      capture_output=True, timeout=30)
    if not os.path.exists(f1) or not os.path.exists(f2):
        return False
    img1 = np.array(Image.open(f1).convert("L"), dtype=np.float32)
    img2 = np.array(Image.open(f2).convert("L"), dtype=np.float32)
    yavg = float(np.mean(np.abs(img1 - img2)))
    print(f"  YAVG={yavg:.1f} (>{threshold})")
    return yavg > threshold


# === 子项A1: Dolly Zoom ===
JSX_DOLLY_ZOOM = '''(function() {
    try {
        app.beginUndoGroup("DollyZoom");
        var comp = app.project.items.addComp("ADV_dolly_zoom", 1920, 1080, 1, 3.0, 30);
        var bg = comp.layers.addSolid([0.05, 0.05, 0.12], "BG", 1920, 1080, 1);
        bg.threeDLayer = true;
        bg.property("Position").setValue([960, 540, -2000]);
        bg.property("Scale").setValue([400, 400, 100]);
        for (var i = 0; i < 5; i++) {
            var p = comp.layers.addSolid([0.2, 0.25, 0.4], "Pillar_" + i, 80, 600, 1);
            p.threeDLayer = true;
            p.property("Position").setValue([300 + i * 350, 540, -400 - i * 300]);
        }
        var txt = comp.layers.addText("DOLLY ZOOM");
        var doc = txt.property("Source Text").value;
        doc.fontSize = 120; doc.fillColor = [1, 0.85, 0.2]; doc.font = "Arial-BoldMT";
        txt.property("Source Text").setValue(doc);
        txt.threeDLayer = true;
        txt.property("Position").setValue([960, 540, 0]);
        var cam = comp.layers.addCamera("Cam", [960, 540]);
        try { cam.property("ADBE Camera Options Group").property("ADBE Camera Type").setValue(1); } catch(e) {}
        var camPos = cam.property("Position");
        camPos.setValueAtTime(0, [960, 540, 0]);
        camPos.setValueAtTime(3.0, [960, 540, -1200]);
        var zoom = cam.property("ADBE Camera Options Group").property("ADBE Camera Zoom");
        zoom.setValueAtTime(0, 35);
        zoom.setValueAtTime(3.0, 18);
        try {
            camPos.setTemporalEaseAtKey(1, [new KeyframeEase(0,10),new KeyframeEase(0,10),new KeyframeEase(0,10)], [new KeyframeEase(0,10),new KeyframeEase(0,10),new KeyframeEase(0,10)]);
            camPos.setTemporalEaseAtKey(2, [new KeyframeEase(0,90),new KeyframeEase(0,90),new KeyframeEase(0,90)], [new KeyframeEase(0,90),new KeyframeEase(0,90),new KeyframeEase(0,90)]);
        } catch(e) {}
        var kl = comp.layers.addLight("Key", [700, 300]);
        kl.property("Light Options").property("Intensity").setValue(400);
        app.endUndoGroup();
        return JSON.stringify({status:"success", msg:"dolly_zoom ok"});
    } catch(e) { app.endUndoGroup(); return JSON.stringify({status:"error", msg:e.toString()}); }
})();'''

# === 子项A2: 环绕+推进 ===
JSX_ORBIT = '''(function() {
    try {
        app.beginUndoGroup("Orbit");
        var comp = app.project.items.addComp("ADV_orbit_push", 1920, 1080, 1, 3.0, 30);
        var txt = comp.layers.addText("ORBIT");
        var doc = txt.property("Source Text").value;
        doc.fontSize = 150; doc.fillColor = [0.9, 0.3, 0.1]; doc.font = "Arial-BoldMT";
        txt.property("Source Text").setValue(doc);
        txt.threeDLayer = true;
        txt.property("Position").setValue([960, 540, 0]);
        for (var i = 0; i < 8; i++) {
            var a = (i/8) * Math.PI * 2;
            var cube = comp.layers.addSolid([0.15, 0.4, 0.6], "Orb_" + i, 120, 120, 1);
            cube.threeDLayer = true;
            cube.property("Position").setValue([960 + Math.cos(a)*600, 540, Math.sin(a)*600]);
        }
        var floor = comp.layers.addSolid([0.08, 0.08, 0.15], "Floor", 3000, 3000, 1);
        floor.threeDLayer = true;
        floor.property("Position").setValue([960, 900, 0]);
        floor.property("X Rotation").setValue(90);
        var nul = comp.layers.addNull(3.0);
        nul.name = "OrbitDrv"; nul.threeDLayer = true;
        nul.property("Position").setValue([960, 400, 0]);
        nul.property("Y Rotation").setValueAtTime(0, 0);
        nul.property("Y Rotation").setValueAtTime(3.0, 360);
        var cam = comp.layers.addCamera("Cam", [960, 540]);
        try { cam.property("ADBE Camera Options Group").property("ADBE Camera Type").setValue(1); } catch(e) {}
        cam.parent = nul;
        cam.property("Position").setValueAtTime(0, [0, 0, 1400]);
        cam.property("Position").setValueAtTime(3.0, [0, -100, 500]);
        var kl = comp.layers.addLight("Key", [500, 200]);
        kl.property("Light Options").property("Intensity").setValue(500);
        kl.threeDLayer = true; kl.property("Position").setValue([500, 200, 800]);
        app.endUndoGroup();
        return JSON.stringify({status:"success", msg:"orbit ok"});
    } catch(e) { app.endUndoGroup(); return JSON.stringify({status:"error", msg:e.toString()}); }
})();'''

# === 子项A3: 手持晃动 ===
JSX_HANDHELD = '''(function() {
    try {
        app.beginUndoGroup("Handheld");
        var comp = app.project.items.addComp("ADV_handheld", 1920, 1080, 1, 3.0, 30);
        var bg = comp.layers.addSolid([0.03, 0.03, 0.08], "BG", 2200, 1400, 1);
        bg.threeDLayer = true; bg.property("Position").setValue([960, 540, -500]);
        bg.property("Scale").setValue([130, 130, 100]);
        for (var i = 0; i < 4; i++) {
            var obj = comp.layers.addSolid([0.1+i*0.15, 0.2+i*0.1, 0.5-i*0.1], "D_"+i, 200+i*100, 200+i*100, 1);
            obj.threeDLayer = true;
            obj.property("Position").setValue([400+i*350, 400+(i%2)*200, -200+i*150]);
        }
        var txt = comp.layers.addText("HANDHELD");
        var doc = txt.property("Source Text").value;
        doc.fontSize = 100; doc.fillColor = [1, 1, 1]; doc.font = "Arial-BoldMT";
        txt.property("Source Text").setValue(doc);
        txt.threeDLayer = true; txt.property("Position").setValue([960, 540, 200]);
        var cam = comp.layers.addCamera("Cam", [960, 540]);
        try { cam.property("ADBE Camera Options Group").property("ADBE Camera Type").setValue(1); } catch(e) {}
        cam.property("Position").property("X Position").expression = "960 + wiggle(2,15)[0]-960 + wiggle(8,4)[0]-960 + wiggle(25,1.5)[0]-960";
        cam.property("Position").property("Y Position").expression = "540 + wiggle(1.8,12)[1]-540 + wiggle(7,3)[1]-540 + wiggle(22,1.2)[1]-540";
        cam.property("Position").property("Z Position").expression = "wiggle(1.5,20)[2]";
        cam.property("Z Rotation").expression = "wiggle(1.2, 0.8)";
        var kl = comp.layers.addLight("Key", [800, 300]);
        kl.property("Light Options").property("Intensity").setValue(450);
        kl.threeDLayer = true; kl.property("Position").setValue([800, 300, 600]);
        app.endUndoGroup();
        return JSON.stringify({status:"success", msg:"handheld ok"});
    } catch(e) { app.endUndoGroup(); return JSON.stringify({status:"error", msg:e.toString()}); }
})();'''

# === 子项B: 视差分层 ===
JSX_PARALLAX = '''(function() {
    try {
        app.beginUndoGroup("Parallax");
        var comp = app.project.items.addComp("ADV_parallax", 1920, 1080, 1, 3.0, 30);
        var bgB = comp.layers.addSolid([0.02, 0.02, 0.06], "BG", 4000, 1080, 1);
        bgB.threeDLayer = true; bgB.property("Position").setValue([960, 540, -800]);
        bgB.property("Scale").setValue([200, 100, 100]);
        for (var i = 0; i < 10; i++) {
            var s = comp.layers.addSolid([0.3, 0.35, 0.6], "Star_"+i, 10+(i%3)*5, 10+(i%3)*5, 1);
            s.threeDLayer = true;
            s.property("Position").setValue([200+(i*317)%3500, 100+(i*193)%880, -700-(i%3)*100]);
        }
        var txt = comp.layers.addText("PARALLAX");
        var doc = txt.property("Source Text").value;
        doc.fontSize = 130; doc.fillColor = [0.95, 0.8, 0.2]; doc.font = "Arial-BoldMT";
        txt.property("Source Text").setValue(doc);
        txt.threeDLayer = true; txt.property("Position").setValue([960, 540, 0]);
        for (var i = 0; i < 4; i++) {
            var fg = comp.layers.addSolid([0.05, 0.15, 0.3], "FG_"+i, 60+i*30, 300+i*80, 1);
            fg.threeDLayer = true;
            fg.property("Position").setValue([-200+i*600, 540, 350+(i%3)*100]);
            fg.property("Opacity").setValue(25+i*8);
            try { var bl = fg.property("Effects").addProperty("ADBE Gaussian Blur 2"); bl.property("ADBE Gaussian Blur 2-0001").setValue(3+i*2); } catch(e) {}
        }
        var cam = comp.layers.addCamera("Cam", [960, 540]);
        try { cam.property("ADBE Camera Options Group").property("ADBE Camera Type").setValue(1); } catch(e) {}
        cam.property("Position").setValueAtTime(0, [400, 500, 800]);
        cam.property("Position").setValueAtTime(3.0, [1500, 560, 750]);
        var kl = comp.layers.addLight("Key", [960, 200]);
        kl.property("Light Options").property("Intensity").setValue(350);
        kl.threeDLayer = true; kl.property("Position").setValue([960, 200, 600]);
        app.endUndoGroup();
        return JSON.stringify({status:"success", msg:"parallax ok"});
    } catch(e) { app.endUndoGroup(); return JSON.stringify({status:"error", msg:e.toString()}); }
})();'''

# === 子项C: 运动曲线 ===
JSX_MOTION_CURVE = '''(function() {
    try {
        app.beginUndoGroup("MotionCurve");
        var comp = app.project.items.addComp("ADV_motion_curve", 1920, 1080, 1, 3.0, 30);
        comp.layers.addSolid([0.04, 0.04, 0.1], "BG", 1920, 1080, 1);
        var ball = comp.layers.addSolid([1, 0.4, 0.1], "Ball", 100, 100, 1);
        var pos = ball.property("Position");
        pos.setValueAtTime(0, [200, 540]);
        pos.setValueAtTime(0.8, [960, 540]);
        pos.setValueAtTime(1.5, [1600, 540]);
        pos.setValueAtTime(1.7, [1660, 540]);
        pos.setValueAtTime(2.2, [1600, 540]);
        try {
            pos.setTemporalEaseAtKey(1, [new KeyframeEase(0,100),new KeyframeEase(0,100)], [new KeyframeEase(0,100),new KeyframeEase(0,100)]);
            pos.setTemporalEaseAtKey(2, [new KeyframeEase(800,15),new KeyframeEase(800,15)], [new KeyframeEase(800,15),new KeyframeEase(800,15)]);
            pos.setTemporalEaseAtKey(3, [new KeyframeEase(600,80),new KeyframeEase(600,80)], [new KeyframeEase(200,80),new KeyframeEase(200,80)]);
            pos.setTemporalEaseAtKey(4, [new KeyframeEase(100,50),new KeyframeEase(100,50)], [new KeyframeEase(100,50),new KeyframeEase(100,50)]);
            pos.setTemporalEaseAtKey(5, [new KeyframeEase(50,75),new KeyframeEase(50,75)], [new KeyframeEase(0,100),new KeyframeEase(0,100)]);
        } catch(e) {}
        var txt = comp.layers.addText("IMPACT");
        var doc = txt.property("Source Text").value;
        doc.fontSize = 90; doc.fillColor = [0.2, 0.9, 0.5]; doc.font = "Arial-BoldMT";
        txt.property("Source Text").setValue(doc);
        txt.property("Position").setValue([960, 850]);
        var scl = txt.property("Scale");
        scl.setValueAtTime(0.5, [0, 0]);
        scl.setValueAtTime(1.0, [130, 130]);
        scl.setValueAtTime(1.3, [95, 95]);
        scl.setValueAtTime(1.6, [103, 103]);
        scl.setValueAtTime(2.0, [100, 100]);
        try {
            scl.setTemporalEaseAtKey(1, [new KeyframeEase(0,100),new KeyframeEase(0,100)], [new KeyframeEase(500,20),new KeyframeEase(500,20)]);
            scl.setTemporalEaseAtKey(2, [new KeyframeEase(200,40),new KeyframeEase(200,40)], [new KeyframeEase(200,40),new KeyframeEase(200,40)]);
            scl.setTemporalEaseAtKey(5, [new KeyframeEase(30,80),new KeyframeEase(30,80)], [new KeyframeEase(0,100),new KeyframeEase(0,100)]);
        } catch(e) {}
        try { var g = txt.property("Effects").addProperty("ADBE Glo2"); g.property("ADBE Glo2-0001").setValue(40); g.property("ADBE Glo2-0002").setValue(25); } catch(e) {}
        app.endUndoGroup();
        return JSON.stringify({status:"success", msg:"motion_curve ok"});
    } catch(e) { app.endUndoGroup(); return JSON.stringify({status:"error", msg:e.toString()}); }
})();'''


def main():
    print("=" * 60)
    print("方向一：摄像机运动 + 三维图层 + 运动曲线 (v2)")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Phase 1: 创建合成
    print("\n[Phase 1] 创建合成")
    comps = [
        ("A1-Dolly Zoom", JSX_DOLLY_ZOOM, "ADV_dolly_zoom"),
        ("A2-环绕推进", JSX_ORBIT, "ADV_orbit_push"),
        ("A3-手持晃动", JSX_HANDHELD, "ADV_handheld"),
        ("B-视差分层", JSX_PARALLAX, "ADV_parallax"),
        ("C-运动曲线", JSX_MOTION_CURVE, "ADV_motion_curve"),
    ]
    
    created = {}
    for label, jsx, comp_name in comps:
        print(f"\n  [{label}]")
        r = send_bridge(jsx, wait=30)
        ok, data = parse_result(r)
        created[comp_name] = ok
        print(f"    {'✓' if ok else '✗'} {data if not ok else 'created'}")
        time.sleep(1)
    
    # Phase 2: 渲染
    print("\n[Phase 2] 渲染验证")
    rendered = {}
    for label, jsx, comp_name in comps:
        if not created.get(comp_name):
            print(f"  跳过 {comp_name} (未创建)")
            continue
        out_path = OUTPUT_DIR / f"{comp_name.lower()}.mp4"
        rendered[comp_name] = render_comp(comp_name, out_path)
        time.sleep(2)
    
    # Phase 3: 动画验证
    print("\n[Phase 3] 帧差异验证")
    verified = {}
    for label, jsx, comp_name in comps:
        out_path = OUTPUT_DIR / f"{comp_name.lower()}.mp4"
        if out_path.exists() and out_path.stat().st_size > 10000:
            print(f"\n  [{comp_name}]")
            verified[comp_name] = verify_animation(out_path)
        else:
            verified[comp_name] = False
    
    # 总结
    print(f"\n{'='*60}")
    print("总结:")
    for label, jsx, comp_name in comps:
        c = '✓' if created.get(comp_name) else '✗'
        r = '✓' if rendered.get(comp_name) else '✗'
        v = '✓' if verified.get(comp_name) else '✗'
        print(f"  {label}: 创建={c} 渲染={r} 动画={v}")
    print(f"输出: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
