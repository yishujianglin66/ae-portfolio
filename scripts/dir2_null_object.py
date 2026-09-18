"""Direction 2: Null Object Driving Multi-Layer Animation
Creates 5 compositions demonstrating Null Object as parent controller.
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
OUTPUT_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production\dir2_null_object")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def send_bridge(code, wait=60, tag=""):
    """Send runScript command and wait for result."""
    try: RES_FILE.unlink(missing_ok=True)
    except: pass
    ts = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    cmd = {"command": "runScript", "args": {"code": code}, "timestamp": ts, "status": "pending"}
    CMD_FILE.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    print(f"  [{tag}] Sent ({ts}), waiting up to {wait}s...")
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(0.4)
        try:
            if RES_FILE.exists():
                r = json.loads(RES_FILE.read_text(encoding="utf-8"))
                if "result" in r:
                    return r
        except: pass
    return None

def check_result(r, tag):
    if not r:
        print(f"  [{tag}] TIMEOUT")
        return False
    data = r.get("result", {}).get("data", {}).get("result", "")
    if data.startswith("ERR"):
        print(f"  [{tag}] ERROR: {data}")
        return False
    print(f"  [{tag}] OK: {data}")
    return True

# ============================================================
# JSX COMPOSITIONS - Null Object Driving
# ============================================================

JSX_SOLAR_SYSTEM = """
(function(){
try{
var comp = app.project.items.addComp("D2_SolarSystem_Orbits", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.02, 0.02, 0.06];
// Central sun
var sun = comp.layers.addSolid([1, 0.85, 0.2], "Sun", 120, 120, 1);
sun.property("Position").setValue([960, 540]);
// Null controllers for each orbit
var colors = [[0.3,0.5,1],[1,0.3,0.3],[0.3,1,0.5],[1,0.6,0.2]];
var radii = [180, 280, 380, 460];
var speeds = [360, 240, 160, 120];
var sizes = [40, 55, 35, 50];
for(var i=0;i<4;i++){
    var nul = comp.layers.addNull();
    nul.name = "OrbitCtrl_" + (i+1);
    nul.property("Position").setValue([960, 540]);
    // Planet parented to null
    var planet = comp.layers.addSolid(colors[i], "Planet_"+(i+1), sizes[i], sizes[i], 1);
    planet.parent = nul;
    planet.property("Position").setValue([radii[i], 0]);
    // Rotate null for orbit animation
    var rot = nul.property("Rotation");
    rot.setValueAtTime(0, i * 90);
    rot.setValueAtTime(3, i * 90 + speeds[i]);
}
return "OK:SolarSystem 4 orbits";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_PUPPET_RIG = """
(function(){
try{
var comp = app.project.items.addComp("D2_PuppetRig_Character", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.15, 0.12, 0.1];
// Body parts as solids
var torso = comp.layers.addSolid([0.2, 0.4, 0.8], "Torso", 100, 200, 1);
torso.property("Position").setValue([960, 500]);
var head = comp.layers.addSolid([0.9, 0.7, 0.5], "Head", 80, 80, 1);
head.property("Position").setValue([960, 360]);
var armL = comp.layers.addSolid([0.2, 0.35, 0.7], "ArmL", 30, 150, 1);
armL.property("Position").setValue([890, 480]);
var armR = comp.layers.addSolid([0.2, 0.35, 0.7], "ArmR", 30, 150, 1);
armR.property("Position").setValue([1030, 480]);
// Master Null controller
var master = comp.layers.addNull();
master.name = "MasterCtrl";
master.property("Position").setValue([960, 540]);
// Parent all to master
torso.parent = master;
head.parent = master;
armL.parent = master;
armR.parent = master;
// Animate master: walk cycle (position bounce + slight rotation)
var mPos = master.property("Position");
mPos.setValueAtTime(0, [960, 540]);
mPos.setValueAtTime(0.5, [960, 520]);
mPos.setValueAtTime(1.0, [960, 540]);
mPos.setValueAtTime(1.5, [960, 520]);
mPos.setValueAtTime(2.0, [960, 540]);
mPos.setValueAtTime(2.5, [960, 520]);
mPos.setValueAtTime(3.0, [960, 540]);
var mRot = master.property("Rotation");
mRot.setValueAtTime(0, 0);
mRot.setValueAtTime(0.75, 3);
mRot.setValueAtTime(1.5, 0);
mRot.setValueAtTime(2.25, -3);
mRot.setValueAtTime(3.0, 0);
// Arm swing via individual nulls
var nulL = comp.layers.addNull();
nulL.name = "ArmLCtrl";
nulL.property("Position").setValue([890, 420]);
armL.parent = nulL;
nulL.parent = master;
var rotL = nulL.property("Rotation");
rotL.setValueAtTime(0, -20);
rotL.setValueAtTime(1.5, 20);
rotL.setValueAtTime(3.0, -20);
var nulR = comp.layers.addNull();
nulR.name = "ArmRCtrl";
nulR.property("Position").setValue([1030, 420]);
armR.parent = nulR;
nulR.parent = master;
var rotR = nulR.property("Rotation");
rotR.setValueAtTime(0, 20);
rotR.setValueAtTime(1.5, -20);
rotR.setValueAtTime(3.0, 20);
return "OK:PuppetRig character walk";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_SPIRAL_FORMATION = """
(function(){
try{
var comp = app.project.items.addComp("D2_Spiral_Formation", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.05, 0.05, 0.08];
// Central null drives spiral expansion
var ctrl = comp.layers.addNull();
ctrl.name = "SpiralMaster";
ctrl.property("Position").setValue([960, 540]);
// Animate master scale and rotation
var scl = ctrl.property("Scale");
scl.setValueAtTime(0, [10, 10]);
scl.setValueAtTime(2, [100, 100]);
scl.setValueAtTime(3, [110, 110]);
var rot = ctrl.property("Rotation");
rot.setValueAtTime(0, 0);
rot.setValueAtTime(3, 720);
// Create 12 elements in spiral, parented to master
for(var i=0;i<12;i++){
    var angle = i * 30 * Math.PI / 180;
    var radius = 40 + i * 35;
    var x = Math.cos(angle) * radius;
    var y = Math.sin(angle) * radius;
    var hue = i / 12.0;
    var r = Math.abs(Math.sin(hue * 6.28));
    var g = Math.abs(Math.sin(hue * 6.28 + 2.09));
    var b = Math.abs(Math.sin(hue * 6.28 + 4.18));
    var sz = 25 + i * 3;
    var el = comp.layers.addSolid([r, g, b], "Spiral_"+i, sz, sz, 1);
    el.parent = ctrl;
    el.property("Position").setValue([x, y]);
    el.property("Rotation").setValue(i * 30);
}
return "OK:Spiral 12 elements";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_NULL_CAMERA_RIG = """
(function(){
try{
var comp = app.project.items.addComp("D2_NullCamera_PanTilt", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.08, 0.1, 0.12];
// Create a scene with depth layers
var bg = comp.layers.addSolid([0.15, 0.2, 0.3], "BG_Far", 2400, 1350, 1);
bg.threeDLayer = true;
bg.property("Position").setValue([960, 540, 500]);
var mid = comp.layers.addSolid([0.3, 0.4, 0.2], "MID_Ground", 1200, 400, 1);
mid.threeDLayer = true;
mid.property("Position").setValue([960, 750, 0]);
var fg1 = comp.layers.addSolid([0.8, 0.3, 0.2], "FG_Obj1", 150, 300, 1);
fg1.threeDLayer = true;
fg1.property("Position").setValue([500, 600, -300]);
var fg2 = comp.layers.addSolid([0.2, 0.6, 0.8], "FG_Obj2", 200, 200, 1);
fg2.threeDLayer = true;
fg2.property("Position").setValue([1400, 500, -500]);
// Camera
var cam = comp.layers.addCamera("CamRig", [960, 540]);
// Null to drive camera (parent camera to null)
var camNull = comp.layers.addNull();
camNull.name = "CameraDriver";
camNull.threeDLayer = true;
camNull.property("Position").setValue([960, 540, -800]);
cam.parent = camNull;
// Animate null: pan left-right + tilt + dolly
var nPos = camNull.property("Position");
nPos.setValueAtTime(0, [960, 540, -800]);
nPos.setValueAtTime(1.5, [700, 480, -600]);
nPos.setValueAtTime(3, [1200, 560, -900]);
var nRotY = camNull.property("Y Rotation");
nRotY.setValueAtTime(0, 0);
nRotY.setValueAtTime(1.5, -15);
nRotY.setValueAtTime(3, 20);
var nRotX = camNull.property("X Rotation");
nRotX.setValueAtTime(0, 0);
nRotX.setValueAtTime(1.5, 5);
nRotX.setValueAtTime(3, -3);
return "OK:NullCamera pan/tilt/dolly";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_WAVE_GRID = """
(function(){
try{
var comp = app.project.items.addComp("D2_WaveGrid_NullDrive", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.03, 0.03, 0.05];
// Master null controls wave amplitude via scale
var waveCtrl = comp.layers.addNull();
waveCtrl.name = "WaveAmplitude";
waveCtrl.property("Position").setValue([960, 540]);
var wScl = waveCtrl.property("Scale");
wScl.setValueAtTime(0, [50, 50]);
wScl.setValueAtTime(1.5, [150, 150]);
wScl.setValueAtTime(3, [80, 80]);
// Create 5x4 grid of tiles, parented to wave controller
var cols = 5, rows = 4;
var spacingX = 300, spacingY = 220;
var startX = 960 - (cols-1) * spacingX / 2;
var startY = 540 - (rows-1) * spacingY / 2;
for(var row=0; row<rows; row++){
    for(var col=0; col<cols; col++){
        var idx = row * cols + col;
        var brightness = 0.3 + (idx % 5) * 0.15;
        var tile = comp.layers.addSolid([brightness*0.5, brightness*0.8, brightness], "Tile_"+idx, 80, 80, 1);
        tile.parent = waveCtrl;
        var bx = (col - (cols-1)/2) * spacingX;
        var by = (row - (rows-1)/2) * spacingY;
        tile.property("Position").setValue([bx, by]);
        // Staggered scale animation per tile
        var tScl = tile.property("Scale");
        var delay = (row + col) * 0.15;
        tScl.setValueAtTime(delay, [60, 60]);
        tScl.setValueAtTime(delay + 0.8, [120, 120]);
        tScl.setValueAtTime(delay + 1.6, [80, 80]);
        tScl.setValueAtTime(3, [100, 100]);
    }
}
return "OK:WaveGrid 20 tiles";
}catch(e){return "ERR:"+e.toString();}
})();
"""

# ============================================================
# RENDER SCRIPT
# ============================================================
def make_render_jsx(comp_name, output_path):
    out_escaped = output_path.replace("\\", "/")
    return f"""
(function(){{
try{{
// Delete existing outputs to prevent overwrite dialog
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
    print("DIRECTION 2: Null Object Driving Multi-Layer Animation")
    print("=" * 60)

    comps = [
        ("SolarSystem", JSX_SOLAR_SYSTEM),
        ("PuppetRig", JSX_PUPPET_RIG),
        ("SpiralFormation", JSX_SPIRAL_FORMATION),
        ("NullCameraRig", JSX_NULL_CAMERA_RIG),
        ("WaveGrid", JSX_WAVE_GRID),
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
        print("FATAL: No compositions created.")
        sys.exit(1)

    # Render
    print(f"\n{'='*60}")
    print("RENDERING verification videos (3s each, H.264)...")

    comp_names = {
        "SolarSystem": "D2_SolarSystem_Orbits",
        "PuppetRig": "D2_PuppetRig_Character",
        "SpiralFormation": "D2_Spiral_Formation",
        "NullCameraRig": "D2_NullCamera_PanTilt",
        "WaveGrid": "D2_WaveGrid_NullDrive",
    }

    rendered = []
    for key in created:
        comp_name = comp_names[key]
        out_file = str(OUTPUT_DIR / f"{comp_name}.mp4")
        # Pre-delete old outputs
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

    # Verify outputs
    print(f"\n{'='*60}")
    print("VERIFICATION:")
    for key in rendered:
        comp_name = comp_names[key]
        out_file = OUTPUT_DIR / f"{comp_name}.mp4"
        if out_file.exists():
            size_kb = out_file.stat().st_size / 1024
            print(f"  [OK] {out_file.name}: {size_kb:.1f} KB")
        else:
            print(f"  [MISSING] {out_file.name}")

    print(f"\n{'='*60}")
    print(f"SUMMARY: Created={len(created)}/5, Rendered={len(rendered)}/5")
    print("DONE.")
