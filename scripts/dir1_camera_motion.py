"""Direction 1: Advanced Camera Motion + 3D Layers + Motion Curves
Creates 5 compositions via AE Bridge and renders 3s verification videos.
"""
import glob
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

BRIDGE_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge")
CMD_FILE = BRIDGE_DIR / "ae_command.json"
RES_FILE = BRIDGE_DIR / "ae_result.json"
OUTPUT_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production\dir1_camera_motion")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def send_bridge(code, wait=60, tag=""):
    """Send runScript command and wait for matching result."""
    ts = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": ts, "status": "pending"}
    # Remove old result
    try: RES_FILE.unlink(missing_ok=True)
    except: pass
    # Write command
    CMD_FILE.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    print(f"  [{tag}] Sent ({ts}), waiting up to {wait}s...")
    # Poll for result
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(0.3)
        try:
            if not RES_FILE.exists():
                continue
            content = RES_FILE.read_text(encoding="utf-8")
            if not content or len(content) < 5:
                continue
            r = json.loads(content)
            # Accept any result that has a result field (bridge v2 format)
            if "result" in r:
                return r
        except (json.JSONDecodeError, OSError):
            pass
    return {"success": False, "error": "timeout", "tag": tag}

def check_result(r, tag):
    """Check if result is successful."""
    if not r:
        print(f"  [{tag}] FAILED: no response")
        return False
    result = r.get("result", {})
    if isinstance(result, dict) and result.get("success"):
        data = result.get("data", {}).get("result", "")
        print(f"  [{tag}] OK: {data[:100]}")
        return True
    else:
        err = result.get("error", {}).get("message", "unknown") if isinstance(result, dict) else str(result)
        print(f"  [{tag}] ERROR: {err}")
        return False

# ============================================================
# JSX SCRIPTS FOR 5 COMPOSITIONS
# ============================================================

JSX_DOLLY_ZOOM = """
(function(){
try{
var comp = app.project.items.addComp("D1_DollyZoom_Hitchcock", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.05, 0.05, 0.1];
var cam = comp.layers.addCamera("DollyCam", [960, 540]);
var subj = comp.layers.addSolid([0.9, 0.2, 0.1], "Subject", 200, 400, 1);
subj.threeDLayer = true;
subj.property("Position").setValue([960, 540, 0]);
var bg = comp.layers.addSolid([0.2, 0.3, 0.5], "Background", 3000, 2000, 1);
bg.threeDLayer = true;
bg.property("Position").setValue([960, 540, -1500]);
bg.property("Scale").setValue([300, 300, 100]);
// Dolly Zoom: Camera Z moves back, Zoom widens
var camPos = cam.property("Position");
var camZoom = cam.property("ADBE Camera Options Group").property("ADBE Camera Zoom");
camPos.setValueAtTime(0, [960, 540, -800]);
camPos.setValueAtTime(3, [960, 540, -2000]);
camZoom.setValueAtTime(0, 35);
camZoom.setValueAtTime(3, 18);
return "OK:DollyZoom";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_ORBIT_PUSH = """
(function(){
try{
var comp = app.project.items.addComp("D2_OrbitPush_Composite", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.02, 0.02, 0.08];
var cam = comp.layers.addCamera("OrbitCam", [960, 540]);
// 3D objects at different depths
for (var i = 0; i < 5; i++) {
    var s = comp.layers.addSolid([0.2+i*0.15, 0.4, 0.8-i*0.1], "Obj_"+i, 150, 150, 1);
    s.threeDLayer = true;
    s.property("Position").setValue([400+i*300, 540, -200*i]);
    s.property("Y Rotation").setValue(i*20);
}
// Orbit: camera position orbits around center
var camPos = cam.property("Position");
camPos.setValueAtTime(0, [960, 540, -1200]);
camPos.setValueAtTime(1.5, [1400, 400, -800]);
camPos.setValueAtTime(3, [960, 540, -600]);
// POI tracks center
var poi = cam.property("Point of Interest");
poi.setValueAtTime(0, [960, 540, 0]);
poi.setValueAtTime(3, [960, 540, -200]);
return "OK:OrbitPush";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_HANDHELD = """
(function(){
try{
var comp = app.project.items.addComp("D3_Handheld_Shake", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.1, 0.08, 0.05];
var cam = comp.layers.addCamera("HandheldCam", [960, 540]);
// Scene content
var scene = comp.layers.addSolid([0.4, 0.6, 0.3], "Scene", 2500, 1500, 1);
scene.threeDLayer = true;
scene.property("Position").setValue([960, 540, -500]);
scene.property("Scale").setValue([200, 200, 100]);
var fg = comp.layers.addSolid([0.8, 0.7, 0.2], "Foreground", 300, 500, 1);
fg.threeDLayer = true;
fg.property("Position").setValue([700, 600, 200]);
// Handheld shake via expression on camera position
var posExpr = 'var t = time;'
+ 'var lx = wiggle(2, 15, 1, 0.5, t)[0] - value[0];'
+ 'var ly = wiggle(2, 12, 1, 0.5, t+100)[1] - value[1];'
+ 'var mx = wiggle(8, 4, 1, 0.5, t+200)[0] - value[0];'
+ 'var my = wiggle(8, 3, 1, 0.5, t+300)[1] - value[1];'
+ 'var hx = wiggle(25, 1.5, 1, 0.5, t+400)[0] - value[0];'
+ 'var hy = wiggle(25, 1, 1, 0.5, t+500)[1] - value[1];'
+ 'value + [lx+mx+hx, ly+my+hy, 0]';
cam.property("Position").expression = posExpr;
return "OK:Handheld";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_PARALLAX = """
(function(){
try{
var comp = app.project.items.addComp("D4_MultiZ_Parallax", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.0, 0.0, 0.05];
var cam = comp.layers.addCamera("ParallxCam", [960, 540]);
// 5 depth layers (front to back)
var depths = [400, 100, -200, -600, -1200];
var colors = [[1,0.3,0.3],[0.3,1,0.5],[0.3,0.5,1],[0.7,0.3,1],[1,0.8,0.2]];
var sizes = [[200,300],[350,250],[500,400],[700,500],[1000,700]];
for (var i = 0; i < 5; i++) {
    var lyr = comp.layers.addSolid(colors[i], "Depth_"+i, sizes[i][0], sizes[i][1], 1);
    lyr.threeDLayer = true;
    var posY = lyr.property("Position");
    var speed = (5 - i) * 30;
    posY.setValueAtTime(0, [960, 540 + speed, depths[i]]);
    posY.setValueAtTime(3, [960, 540 - speed, depths[i]]);
}
// Camera forward push
var camPos = cam.property("Position");
camPos.setValueAtTime(0, [960, 540, -1500]);
camPos.setValueAtTime(3, [960, 540, -1200]);
return "OK:Parallax 5 layers";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_MOTION_CURVE = """
(function(){
try{
var comp = app.project.items.addComp("D5_MotionCurve_Overshoot", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.12, 0.12, 0.15];
var ball = comp.layers.addSolid([1, 0.6, 0.1], "Ball", 250, 250, 1);
ball.threeDLayer = true;
var pos = ball.property("Position");
// 5 keyframes: start, accelerate, hard stop, overshoot, settle
pos.setValueAtTime(0, [200, 540, 0]);
pos.setValueAtTime(0.8, [900, 540, 0]);
pos.setValueAtTime(1.2, [1500, 540, 0]);
pos.setValueAtTime(1.5, [1552, 540, 0]);
pos.setValueAtTime(2.0, [1500, 540, 0]);
// Scale pulse at impact
var scl = ball.property("Scale");
scl.setValueAtTime(1.0, [100, 100, 100]);
scl.setValueAtTime(1.2, [120, 80, 100]);
scl.setValueAtTime(1.5, [90, 110, 100]);
scl.setValueAtTime(2.0, [100, 100, 100]);
return "OK:MotionCurve overshoot";
}catch(e){return "ERR:"+e.toString();}
})();
"""

# ============================================================
# RENDER SCRIPT (uses AE internal render queue)
# ============================================================
def make_render_jsx(comp_name, output_path):
    out_escaped = output_path.replace("\\", "/")
    return f"""
(function(){{
try{{
// Delete existing outputs to prevent overwrite dialog blocking
var outF = new File("{out_escaped}");
var base = outF.name.replace(/\\.[^.]+$/, "");
var matches = outF.parent.getFiles(base + ".*");
for(var d=0;d<matches.length;d++){{try{{if(matches[d] instanceof File)matches[d].remove();}}catch(ed){{}}}}

var comp = null;
for (var i = 1; i <= app.project.numItems; i++) {{
    var item = app.project.item(i);
    if (item instanceof CompItem && item.name == "{comp_name}") {{ comp = item; break; }}
}}
if (!comp) return "ERR:comp '{comp_name}' not found";
var rqItem = app.project.renderQueue.items.add(comp);
var om = rqItem.outputModule(1);
var tpl = om.templates;
var found = "";
for (var i = 0; i < tpl.length; i++) {{
    if (tpl[i].indexOf("H.264") >= 0) {{ found = tpl[i]; break; }}
}}
if (found) {{ om.applyTemplate(found); }}
else {{ om.applyTemplate(tpl[0]); }}
om.file = new File("{out_escaped}");
app.project.renderQueue.render();
rqItem.remove();
var f = new File("{out_escaped}");
return "RENDERED size=" + (f.exists ? f.length : "MISSING");
}}catch(e){{return "ERR:"+e.toString();}}
}})();
"""

# ============================================================
# MAIN EXECUTION
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("DIRECTION 1: Advanced Camera Motion + 3D + Motion Curves")
    print("=" * 60)
    
    # Step 1: Create all 5 compositions
    comps = [
        ("DollyZoom", JSX_DOLLY_ZOOM),
        ("OrbitPush", JSX_ORBIT_PUSH),
        ("Handheld", JSX_HANDHELD),
        ("Parallax", JSX_PARALLAX),
        ("MotionCurve", JSX_MOTION_CURVE),
    ]
    
    created = []
    for name, jsx in comps:
        print(f"\n[CREATE] {name}...")
        r = send_bridge(jsx, wait=30, tag=name)
        if check_result(r, name):
            created.append(name)
        time.sleep(1)
    
    print(f"\n{'='*60}")
    print(f"Created {len(created)}/5 compositions: {created}")
    
    if len(created) == 0:
        print("FATAL: No compositions created. Bridge may not be working.")
        sys.exit(1)
    
    # Step 2: Render each composition
    print(f"\n{'='*60}")
    print("RENDERING verification videos (3s each, H.264/QuickTime)...")
    
    comp_names = {
        "DollyZoom": "D1_DollyZoom_Hitchcock",
        "OrbitPush": "D2_OrbitPush_Composite",
        "Handheld": "D3_Handheld_Shake",
        "Parallax": "D4_MultiZ_Parallax",
        "MotionCurve": "D5_MotionCurve_Overshoot",
    }
    
    rendered = []
    for key in created:
        comp_name = comp_names[key]
        out_file = str(OUTPUT_DIR / f"{comp_name}.mp4")
        # Pre-delete old outputs from Python side (prevent AE overwrite dialog)
        import glob
        base = str(OUTPUT_DIR / comp_name) + ".*"
        for old in glob.glob(base):
            try: os.remove(old)
            except: pass
        print(f"\n[RENDER] {comp_name}...")
        jsx = make_render_jsx(comp_name, out_file)
        r = send_bridge(jsx, wait=300, tag=f"RENDER_{key}")
        if check_result(r, f"RENDER_{key}"):
            rendered.append(key)
        time.sleep(2)
    
    # Step 3: Verify outputs
    print(f"\n{'='*60}")
    print("VERIFICATION:")
    for key in rendered:
        comp_name = comp_names[key]
        out_file = OUTPUT_DIR / f"{comp_name}.mp4"
        if out_file.exists():
            size_mb = out_file.stat().st_size / (1024*1024)
            print(f"  [OK] {out_file.name}: {size_mb:.2f} MB")
        else:
            print(f"  [MISSING] {out_file.name}")
    
    print(f"\n{'='*60}")
    print(f"SUMMARY: Created={len(created)}/5, Rendered={len(rendered)}/5")
    print("DONE.")
