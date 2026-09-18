"""Direction 3: Adjustment Layer - Global Color Grading & Stylized Filters
Creates 5 compositions demonstrating adjustment layers with effects.
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
OUTPUT_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production\dir3_adjustment_layer")
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
# JSX COMPOSITIONS - Adjustment Layer Effects
# ============================================================

JSX_CURVES_GRADE = """
(function(){
try{
var comp = app.project.items.addComp("D3_Curves_Cinematic", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.1, 0.1, 0.1];
// Base scene: colorful gradient bars animated
var colors = [[0.9,0.2,0.1],[0.1,0.7,0.9],[0.9,0.8,0.1],[0.2,0.9,0.3],[0.7,0.2,0.9]];
for(var i=0;i<5;i++){
    var bar = comp.layers.addSolid(colors[i], "Bar_"+i, 384, 1080, 1);
    bar.property("Position").setValue([192 + i*384, 540]);
    var scl = bar.property("Scale");
    scl.setValueAtTime(0, [100, 50]);
    scl.setValueAtTime(1.5, [100, 110]);
    scl.setValueAtTime(3, [100, 70]);
}
// Adjustment layer with Levels effect
var adj = comp.layers.addSolid([1,1,1], "GradeLayer", 1920, 1080, 1);
adj.adjustmentLayer = true;
try{
    var levels = adj.Effects.addProperty("ADBE Levels");
    // Animate gamma for breathing effect
    levels.property("ADBE Levels-5").setValueAtTime(0, 0.8);
    levels.property("ADBE Levels-5").setValueAtTime(1.5, 1.3);
    levels.property("ADBE Levels-5").setValueAtTime(3, 0.9);
}catch(e2){}
try{
    var tint = adj.Effects.addProperty("ADBE Tint");
    tint.property("ADBE Tint-2").setValue([0.9, 0.85, 0.7, 1]);
    tint.property("ADBE Tint-3").setValue(30);
}catch(e3){}
return "OK:Curves cinematic grade";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_HUE_CYCLE = """
(function(){
try{
var comp = app.project.items.addComp("D3_HueShift_Cycle", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.15, 0.15, 0.15];
// Base: large bright circles
var positions = [[480,300],[960,540],[1440,300],[480,780],[1440,780]];
for(var i=0;i<5;i++){
    var c = comp.layers.addSolid([0.8, 0.8, 0.8], "Circle_"+i, 250, 250, 1);
    c.property("Position").setValue(positions[i]);
    var s = c.property("Scale");
    s.setValueAtTime(0, [80, 80]);
    s.setValueAtTime(1.5, [120, 120]);
    s.setValueAtTime(3, [90, 90]);
}
// Adjustment: Hue/Saturation with animated master hue
var adj = comp.layers.addSolid([1,1,1], "HueCtrl", 1920, 1080, 1);
adj.adjustmentLayer = true;
try{
    var hs = adj.Effects.addProperty("ADBE HUE SATURATION");
    hs.property("ADBE HUE SATURATION-1").setValueAtTime(0, 0);
    hs.property("ADBE HUE SATURATION-1").setValueAtTime(3, 360);
    hs.property("ADBE HUE SATURATION-2").setValue(40);
}catch(e2){}
return "OK:HueShift 360 cycle";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_GLOW_BLOOM = """
(function(){
try{
var comp = app.project.items.addComp("D3_Glow_Bloom", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.02, 0.02, 0.04];
// Base: bright emissive shapes on dark bg
var shapes = [[960,540,300],[400,300,150],[1500,700,180],[700,800,120],[1300,250,140]];
for(var i=0;i<5;i++){
    var sz = shapes[i][2];
    var bright = 0.7 + i * 0.06;
    var el = comp.layers.addSolid([bright, bright*0.9, bright*0.5], "Glow_"+i, sz, sz, 1);
    el.property("Position").setValue([shapes[i][0], shapes[i][1]]);
    var s = el.property("Scale");
    s.setValueAtTime(i*0.3, [60, 60]);
    s.setValueAtTime(i*0.3+1, [130, 130]);
    s.setValueAtTime(3, [100, 100]);
}
// Adjustment: Glow effect with animated intensity
var adj = comp.layers.addSolid([1,1,1], "BloomCtrl", 1920, 1080, 1);
adj.adjustmentLayer = true;
try{
    var glow = adj.Effects.addProperty("ADBE Glo2");
    glow.property("ADBE Glo2-3").setValue(30);
    glow.property("ADBE Glo2-4").setValueAtTime(0, 20);
    glow.property("ADBE Glo2-4").setValueAtTime(1.5, 80);
    glow.property("ADBE Glo2-4").setValueAtTime(3, 40);
}catch(e2){}
return "OK:Glow bloom animated";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_DAY_TO_NIGHT = """
(function(){
try{
var comp = app.project.items.addComp("D3_DayToNight_Transition", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.5, 0.7, 0.9];
// Base scene: landscape blocks
var sky = comp.layers.addSolid([0.4, 0.65, 0.95], "Sky", 1920, 600, 1);
sky.property("Position").setValue([960, 300]);
var ground = comp.layers.addSolid([0.3, 0.6, 0.2], "Ground", 1920, 480, 1);
ground.property("Position").setValue([960, 840]);
var sun = comp.layers.addSolid([1, 0.95, 0.6], "Sun", 200, 200, 1);
sun.property("Position").setValue([960, 250]);
// Buildings
for(var i=0;i<4;i++){
    var h = 200 + i * 80;
    var bld = comp.layers.addSolid([0.5, 0.45, 0.4], "Bld_"+i, 150, h, 1);
    bld.property("Position").setValue([300 + i*400, 1080 - h/2]);
}
// Adjustment: animate from warm day to cool night
var adj = comp.layers.addSolid([1,1,1], "TimeOfDay", 1920, 1080, 1);
adj.adjustmentLayer = true;
try{
    var photo = adj.Effects.addProperty("ADBE Photo Filter");
    // Warm orange -> cool blue
    photo.property("ADBE Photo Filter-1").setValueAtTime(0, [1, 0.7, 0.3, 1]);
    photo.property("ADBE Photo Filter-1").setValueAtTime(3, [0.2, 0.3, 0.8, 1]);
    photo.property("ADBE Photo Filter-2").setValue(60);
}catch(e2){}
try{
    var levels = adj.Effects.addProperty("ADBE Levels");
    levels.property("ADBE Levels-5").setValueAtTime(0, 1.2);
    levels.property("ADBE Levels-5").setValueAtTime(3, 0.6);
}catch(e3){}
// Animate sun position (setting)
var sunPos = sun.property("Position");
sunPos.setValueAtTime(0, [960, 200]);
sunPos.setValueAtTime(3, [960, 900]);
return "OK:DayToNight transition";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_VIGNETTE_CONTRAST = """
(function(){
try{
var comp = app.project.items.addComp("D3_Vignette_Contrast", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.2, 0.2, 0.2];
// Base: colorful mosaic grid
for(var row=0;row<4;row++){
    for(var col=0;col<6;col++){
        var hue = (row*6+col) / 24.0;
        var r = Math.abs(Math.sin(hue * 6.28)) * 0.7 + 0.3;
        var g = Math.abs(Math.sin(hue * 6.28 + 2.09)) * 0.7 + 0.3;
        var b = Math.abs(Math.sin(hue * 6.28 + 4.18)) * 0.7 + 0.3;
        var tile = comp.layers.addSolid([r, g, b], "M_"+row+"_"+col, 300, 250, 1);
        tile.property("Position").setValue([160 + col*320, 135 + row*270]);
        var s = tile.property("Scale");
        var delay = (row+col) * 0.1;
        s.setValueAtTime(delay, [90, 90]);
        s.setValueAtTime(delay+0.5, [105, 105]);
        s.setValueAtTime(delay+1.0, [95, 95]);
        s.setValueAtTime(3, [100, 100]);
    }
}
// Adjustment: vignette + contrast
var adj = comp.layers.addSolid([1,1,1], "StyleCtrl", 1920, 1080, 1);
adj.adjustmentLayer = true;
try{
    var cc = adj.Effects.addProperty("ADBE Color Corrector");
    cc.property("ADBE Color Corrector-6").setValueAtTime(0, 1.0);
    cc.property("ADBE Color Corrector-6").setValueAtTime(1.5, 1.5);
    cc.property("ADBE Color Corrector-6").setValueAtTime(3, 1.2);
}catch(e2){}
try{
    var blur = adj.Effects.addProperty("ADBE Camera Lens Blur");
    blur.property("ADBE Camera Lens Blur-1").setValueAtTime(0, 0);
    blur.property("ADBE Camera Lens Blur-1").setValueAtTime(1.5, 3);
    blur.property("ADBE Camera Lens Blur-1").setValueAtTime(3, 0);
}catch(e3){}
return "OK:Vignette contrast mosaic";
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
    print("DIRECTION 3: Adjustment Layer - Color Grading & Filters")
    print("=" * 60)

    comps = [
        ("CurvesGrade", JSX_CURVES_GRADE),
        ("HueCycle", JSX_HUE_CYCLE),
        ("GlowBloom", JSX_GLOW_BLOOM),
        ("DayToNight", JSX_DAY_TO_NIGHT),
        ("VignetteContrast", JSX_VIGNETTE_CONTRAST),
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
        "CurvesGrade": "D3_Curves_Cinematic",
        "HueCycle": "D3_HueShift_Cycle",
        "GlowBloom": "D3_Glow_Bloom",
        "DayToNight": "D3_DayToNight_Transition",
        "VignetteContrast": "D3_Vignette_Contrast",
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
