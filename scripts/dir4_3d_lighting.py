"""Direction 4: 3D Layers + Camera Depth of Field + Lighting
Creates 5 compositions demonstrating 3D depth, DOF, and light/shadow.
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
OUTPUT_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production\dir4_3d_lighting")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def send_bridge(code, wait=60, tag=""):
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
# JSX COMPOSITIONS
# ============================================================

JSX_DEPTH_CORRIDOR = """
(function(){
try{
var comp = app.project.items.addComp("D4_DepthCorridor_Flythrough", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.03, 0.03, 0.06];
// Create corridor of frames at increasing Z depth
var colors = [[0.8,0.2,0.2],[0.2,0.7,0.8],[0.8,0.7,0.1],[0.3,0.8,0.3],[0.7,0.3,0.8],[0.9,0.5,0.2]];
for(var i=0;i<6;i++){
    var frame = comp.layers.addSolid(colors[i], "Frame_"+i, 600-i*60, 400-i*40, 1);
    frame.threeDLayer = true;
    frame.property("Position").setValue([960, 540, i * 400]);
    frame.property("Opacity").setValue(90 - i*10);
}
// Camera flying through corridor
var cam = comp.layers.addCamera("FlyCam", [960, 540]);
var camPos = cam.property("Position");
camPos.setValueAtTime(0, [960, 540, -600]);
camPos.setValueAtTime(3, [960, 540, 1800]);
// Slight drift
camPos.setValueAtTime(1.5, [1050, 480, 600]);
return "OK:DepthCorridor 6 frames flythrough";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_DOF_FOCUS_PULL = """
(function(){
try{
var comp = app.project.items.addComp("D4_DOF_FocusPull", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.08, 0.08, 0.1];
// Foreground object (close)
var fg = comp.layers.addSolid([0.9, 0.3, 0.2], "FG_Object", 300, 300, 1);
fg.threeDLayer = true;
fg.property("Position").setValue([600, 540, -200]);
// Midground
var mg = comp.layers.addSolid([0.2, 0.8, 0.4], "MG_Object", 250, 250, 1);
mg.threeDLayer = true;
mg.property("Position").setValue([960, 540, 300]);
// Background
var bg = comp.layers.addSolid([0.3, 0.4, 0.9], "BG_Object", 400, 400, 1);
bg.threeDLayer = true;
bg.property("Position").setValue([1350, 540, 900]);
// Camera with DOF
var cam = comp.layers.addCamera("DOFCam", [960, 540]);
try{
    var camOpts = cam.property("Camera Options");
    camOpts.property("Depth of Field").setValue(1);
    camOpts.property("Focus Distance").setValueAtTime(0, 400);
    camOpts.property("Focus Distance").setValueAtTime(1.5, 900);
    camOpts.property("Focus Distance").setValueAtTime(3, 1500);
    camOpts.property("Aperture").setValue(15);
    camOpts.property("Blur Level").setValue(100);
}catch(e2){}
cam.property("Position").setValue([960, 540, -600]);
return "OK:DOF focus pull FG->BG";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_SPOTLIGHT_SHADOW = """
(function(){
try{
var comp = app.project.items.addComp("D4_Spotlight_Shadows", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.02, 0.02, 0.03];
// Floor plane
var floor = comp.layers.addSolid([0.3, 0.3, 0.35], "Floor", 2000, 2000, 1);
floor.threeDLayer = true;
floor.property("Position").setValue([960, 800, 0]);
floor.property("X Rotation").setValue(90);
// Objects casting shadows
var obj1 = comp.layers.addSolid([0.8, 0.6, 0.2], "Obj1", 200, 350, 1);
obj1.threeDLayer = true;
obj1.property("Position").setValue([700, 500, 0]);
var obj2 = comp.layers.addSolid([0.2, 0.6, 0.8], "Obj2", 150, 250, 1);
obj2.threeDLayer = true;
obj2.property("Position").setValue([1200, 550, -100]);
// Animate objects
obj1.property("Y Rotation").setValueAtTime(0, 0);
obj1.property("Y Rotation").setValueAtTime(3, 360);
obj2.property("Y Rotation").setValueAtTime(0, 0);
obj2.property("Y Rotation").setValueAtTime(3, -270);
// Spot light with shadows
var light = comp.layers.addLight("SpotLight", [960, 200]);
light.threeDLayer = true;
light.property("Position").setValue([960, 100, -500]);
try{
    light.property("Light Options").property("Intensity").setValue(150);
    light.property("Light Options").property("Color").setValue([1, 0.95, 0.8]);
    light.property("Light Options").property("Cone Angle").setValue(60);
    light.property("Light Options").property("Cone Feather").setValue(50);
    light.property("Light Options").property("Cast Shadows").setValue(1);
    light.property("Light Options").property("Shadow Darkness").setValue(80);
    light.property("Light Options").property("Shadow Diffusion").setValue(10);
}catch(e2){}
// Animate light position (sweep)
var lPos = light.property("Position");
lPos.setValueAtTime(0, [500, 100, -500]);
lPos.setValueAtTime(1.5, [960, 50, -400]);
lPos.setValueAtTime(3, [1400, 100, -500]);
return "OK:Spotlight shadows sweep";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_MULTIPLANE = """
(function(){
try{
var comp = app.project.items.addComp("D4_MultiPlane_Parallax", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.1, 0.15, 0.25];
// Sky layer (far)
var sky = comp.layers.addSolid([0.3, 0.5, 0.8], "Sky", 3000, 1600, 1);
sky.threeDLayer = true;
sky.property("Position").setValue([960, 540, 2000]);
// Mountains (mid-far)
var mtn = comp.layers.addSolid([0.2, 0.35, 0.3], "Mountains", 2500, 600, 1);
mtn.threeDLayer = true;
mtn.property("Position").setValue([960, 700, 1200]);
// Trees (mid)
var trees = comp.layers.addSolid([0.15, 0.45, 0.15], "Trees", 2200, 500, 1);
trees.threeDLayer = true;
trees.property("Position").setValue([960, 750, 600]);
// Foreground (close)
var fg = comp.layers.addSolid([0.25, 0.5, 0.2], "Foreground", 2000, 400, 1);
fg.threeDLayer = true;
fg.property("Position").setValue([960, 900, 0]);
// Objects at various depths
for(var i=0;i<4;i++){
    var obj = comp.layers.addSolid([0.7+i*0.08, 0.4, 0.3-i*0.05], "Obj_"+i, 100+i*30, 150+i*40, 1);
    obj.threeDLayer = true;
    obj.property("Position").setValue([300+i*400, 600, i*400]);
}
// Camera lateral tracking (parallax reveal)
var cam = comp.layers.addCamera("TrackCam", [960, 540]);
cam.property("Position").setValueAtTime(0, [400, 500, -800]);
cam.property("Position").setValueAtTime(3, [1500, 550, -700]);
return "OK:MultiPlane 4-depth parallax";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_POINT_LIGHT_ORBIT = """
(function(){
try{
var comp = app.project.items.addComp("D4_PointLight_Orbit", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.02, 0.02, 0.04];
// Central sphere-like object
var sphere = comp.layers.addSolid([0.6, 0.6, 0.65], "Sphere", 300, 300, 1);
sphere.threeDLayer = true;
sphere.property("Position").setValue([960, 540, 0]);
// Surrounding pillars
for(var i=0;i<6;i++){
    var angle = i * 60 * Math.PI / 180;
    var px = 960 + Math.cos(angle) * 500;
    var pz = Math.sin(angle) * 500;
    var pillar = comp.layers.addSolid([0.4, 0.35, 0.3], "Pillar_"+i, 80, 400, 1);
    pillar.threeDLayer = true;
    pillar.property("Position").setValue([px, 540, pz]);
    pillar.property("Y Rotation").setValue(i * 60);
}
// Point light orbiting the scene
var light = comp.layers.addLight("OrbitLight", [960, 540]);
light.threeDLayer = true;
try{
    light.property("Light Options").property("Intensity").setValue(200);
    light.property("Light Options").property("Color").setValue([1, 0.9, 0.7]);
    light.property("Light Options").property("Cast Shadows").setValue(1);
    light.property("Light Options").property("Shadow Darkness").setValue(70);
}catch(e2){}
// Animate light in circular orbit
var lPos = light.property("Position");
lPos.setValueAtTime(0, [960, 300, -600]);
lPos.setValueAtTime(0.75, [1500, 300, 0]);
lPos.setValueAtTime(1.5, [960, 300, 600]);
lPos.setValueAtTime(2.25, [400, 300, 0]);
lPos.setValueAtTime(3, [960, 300, -600]);
return "OK:PointLight orbit 6 pillars";
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
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("DIRECTION 4: 3D Layers + Camera DOF + Lighting")
    print("=" * 60)

    comps = [
        ("DepthCorridor", JSX_DEPTH_CORRIDOR),
        ("DOFFocusPull", JSX_DOF_FOCUS_PULL),
        ("SpotlightShadow", JSX_SPOTLIGHT_SHADOW),
        ("MultiPlane", JSX_MULTIPLANE),
        ("PointLightOrbit", JSX_POINT_LIGHT_ORBIT),
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
        "DepthCorridor": "D4_DepthCorridor_Flythrough",
        "DOFFocusPull": "D4_DOF_FocusPull",
        "SpotlightShadow": "D4_Spotlight_Shadows",
        "MultiPlane": "D4_MultiPlane_Parallax",
        "PointLightOrbit": "D4_PointLight_Orbit",
    }

    rendered = []
    for key in created:
        comp_name = comp_names[key]
        out_file = str(OUTPUT_DIR / f"{comp_name}.mp4")
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

    # Verify
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
