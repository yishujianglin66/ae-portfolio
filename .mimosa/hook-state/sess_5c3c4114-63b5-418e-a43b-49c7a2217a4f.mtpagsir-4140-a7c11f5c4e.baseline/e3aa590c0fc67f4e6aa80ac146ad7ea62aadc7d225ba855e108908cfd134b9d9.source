"""Direction 5: Built-in Plugin Effects - Parameterized Control
Uses CC Particle World, CC Light Rays, Fractal Noise, Shatter, Beam etc.
"""
import json, time, sys, os, glob
from pathlib import Path
from datetime import datetime

BRIDGE_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge")
CMD_FILE = BRIDGE_DIR / "ae_command.json"
RES_FILE = BRIDGE_DIR / "ae_result.json"
OUTPUT_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production\dir5_plugin_effects")
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
# JSX COMPOSITIONS - Plugin Effects
# ============================================================

JSX_PARTICLE_WORLD = """
(function(){
try{
var comp = app.project.items.addComp("D5_CCParticle_Fountain", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.02, 0.02, 0.05];
var solid = comp.layers.addSolid([0,0,0], "Particles", 1920, 1080, 1);
try{
    var fx = solid.Effects.addProperty("CC Particle World");
    // Producer position animated
    fx.property("Producer").property("Position").setValueAtTime(0, [0.3, 0.8, 0]);
    fx.property("Producer").property("Position").setValueAtTime(1.5, [0.5, 0.3, 0]);
    fx.property("Producer").property("Position").setValueAtTime(3, [0.7, 0.8, 0]);
    // Particle settings
    fx.property("Particle").property("Particle Type").setValue(6);
    fx.property("Particle").property("Birth Size").setValue(8);
    fx.property("Particle").property("Death Size").setValue(2);
    fx.property("Particle").property("Size Variation").setValue(50);
    fx.property("Particle").property("Max Opacity").setValue(80);
    // Physics
    fx.property("Physics").property("Animation").setValue(3);
    fx.property("Physics").property("Velocity").setValue(1.5);
    fx.property("Physics").property("Gravity").setValue(0.5);
    fx.property("Physics").property("Resistance").setValue(0.3);
    // Longevity
    fx.property("Particle").property("Longevity").setValue(2.5);
}catch(e2){}
// Bright background gradient
var bg = comp.layers.addSolid([0.15, 0.1, 0.25], "BG", 1920, 1080, 1);
bg.moveToEnd();
return "OK:CCParticle fountain";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_LIGHT_RAYS = """
(function(){
try{
var comp = app.project.items.addComp("D5_CCLightRays_Sweep", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.05, 0.05, 0.08];
// Base bright shape for light source
var source = comp.layers.addSolid([1, 0.95, 0.7], "LightSource", 200, 200, 1);
source.property("Position").setValue([960, 200]);
var sScl = source.property("Scale");
sScl.setValueAtTime(0, [80, 80]);
sScl.setValueAtTime(1.5, [130, 130]);
sScl.setValueAtTime(3, [90, 90]);
// CC Light Rays on adjustment
var adj = comp.layers.addSolid([1,1,1], "RaysLayer", 1920, 1080, 1);
adj.adjustmentLayer = true;
try{
    var rays = adj.Effects.addProperty("CC Light Rays");
    rays.property("Center").setValueAtTime(0, [960, 200]);
    rays.property("Center").setValueAtTime(1.5, [700, 300]);
    rays.property("Center").setValueAtTime(3, [1200, 200]);
    rays.property("Intensity").setValue(3);
    rays.property("Length").setValue(1.5);
}catch(e2){}
// CC Light Burst on second layer
var adj2 = comp.layers.addSolid([1,1,1], "BurstLayer", 1920, 1080, 1);
adj2.adjustmentLayer = true;
try{
    var burst = adj2.Effects.addProperty("CC Light Burst");
    burst.property("Center").setValue([960, 200]);
    burst.property("Intensity").setValueAtTime(0, 1);
    burst.property("Intensity").setValueAtTime(1.5, 4);
    burst.property("Intensity").setValueAtTime(3, 2);
    burst.property("Radius").setValue(300);
}catch(e3){}
// Dark gradient bg
var bg = comp.layers.addSolid([0.1, 0.08, 0.15], "BG", 1920, 1080, 1);
bg.moveToEnd();
return "OK:CCLightRays sweep";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_FRACTAL_MORPH = """
(function(){
try{
var comp = app.project.items.addComp("D5_FractalNoise_Morph", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.05, 0.05, 0.05];
var solid = comp.layers.addSolid([0.5,0.5,0.5], "FractalLayer", 1920, 1080, 1);
try{
    var fn = solid.Effects.addProperty("Fractal Noise");
    fn.property("Fractal Type").setValue(1);
    fn.property("Noise Type").setValue(3);
    fn.property("Contrast").setValue(150);
    fn.property("Brightness").setValue(-20);
    fn.property("Scale").setValueAtTime(0, 80);
    fn.property("Scale").setValueAtTime(1.5, 150);
    fn.property("Scale").setValueAtTime(3, 60);
    fn.property("Complexity").setValue(4);
    // Animate evolution for motion
    fn.property("Evolution").setValueAtTime(0, 0);
    fn.property("Evolution").setValueAtTime(3, 720);
    // Offset turbulence
    fn.property("Offset Turbulence").setValueAtTime(0, [200, 540]);
    fn.property("Offset Turbulence").setValueAtTime(3, [1700, 540]);
}catch(e2){}
// Colorize with tint
try{
    var tint = solid.Effects.addProperty("Tint");
    tint.property("Map Black To").setValue([0.1, 0.0, 0.3, 1]);
    tint.property("Map White To").setValue([0.2, 0.9, 1.0, 1]);
}catch(e3){}
return "OK:FractalNoise morph";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_SHATTER = """
(function(){
try{
var comp = app.project.items.addComp("D5_Shatter_Explosion", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.08, 0.06, 0.04];
// Bright wall to shatter
var wall = comp.layers.addSolid([0.8, 0.7, 0.5], "Wall", 1920, 1080, 1);
try{
    var shatter = wall.Effects.addProperty("Shatter");
    shatter.property("Pattern").setValue(1);
    shatter.property("Repetitions").setValue(20);
    shatter.property("Direction").setValue(0);
    // Force animation
    shatter.property("Force 1").property("Position").setValue([0.5, 0.5]);
    shatter.property("Force 1").property("Depth").setValue(0.5);
    shatter.property("Force 1").property("Radius").setValue(0.3);
    shatter.property("Force 1").property("Strength").setValueAtTime(0, 0);
    shatter.property("Force 1").property("Strength").setValueAtTime(0.5, 0);
    shatter.property("Force 1").property("Strength").setValueAtTime(1.0, 5);
    shatter.property("Force 1").property("Strength").setValueAtTime(3, 8);
    // Physics
    shatter.property("Physics").property("Rotation Speed").setValue(1);
    shatter.property("Physics").property("Tumble Rate").setValue(0.5);
    shatter.property("Physics").property("Randomness").setValue(0.5);
    shatter.property("Physics").property("Gravity").setValue(0.5);
    // Camera
    shatter.property("Camera").property("Position").setValue([0, 0, -3]);
}catch(e2){}
// Bright bg behind
var bg = comp.layers.addSolid([0.9, 0.85, 0.6], "BehindWall", 1920, 1080, 1);
bg.moveToEnd();
return "OK:Shatter explosion";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_BEAM_ENERGY = """
(function(){
try{
var comp = app.project.items.addComp("D5_Beam_Energy", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.03, 0.03, 0.06];
// Multiple energy beams
var beamColors = [[0.3,0.6,1],[1,0.3,0.5],[0.3,1,0.6]];
for(var i=0;i<3;i++){
    var solid = comp.layers.addSolid([0,0,0], "Beam_"+i, 1920, 1080, 1);
    try{
        var beam = solid.Effects.addProperty("Beam");
        beam.property("Starting Point").setValueAtTime(0, [100+i*200, 900]);
        beam.property("Starting Point").setValueAtTime(1.5, [960, 100+i*100]);
        beam.property("Starting Point").setValueAtTime(3, [1800-i*200, 900]);
        beam.property("Ending Point").setValueAtTime(0, [1800-i*200, 200]);
        beam.property("Ending Point").setValueAtTime(1.5, [960, 900-i*100]);
        beam.property("Ending Point").setValueAtTime(3, [100+i*200, 200]);
        beam.property("Inside Color").setValue(beamColors[i]);
        beam.property("Outside Color").setValue([beamColors[i][0]*0.3, beamColors[i][1]*0.3, beamColors[i][2]*0.3]);
        beam.property("Core Width").setValue(5);
        beam.property("Core Softness").setValue(30);
        beam.property("Outside Width").setValue(20+i*10);
        beam.property("Outside Softness").setValue(60);
        beam.property("Length").setValue(100);
        beam.property("Wave Speed").setValue(3);
        beam.property("Wave Width").setValue(8);
    }catch(e2){}
}
// Bright center glow
var glow = comp.layers.addSolid([0.4, 0.4, 0.5], "CenterGlow", 400, 400, 1);
glow.property("Position").setValue([960, 540]);
var gScl = glow.property("Scale");
gScl.setValueAtTime(0, [80, 80]);
gScl.setValueAtTime(1.5, [150, 150]);
gScl.setValueAtTime(3, [100, 100]);
return "OK:Beam energy 3 beams";
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
    print("DIRECTION 5: Plugin Effects - Parameterized Control")
    print("=" * 60)

    comps = [
        ("CCParticle", JSX_PARTICLE_WORLD),
        ("CCLightRays", JSX_LIGHT_RAYS),
        ("FractalMorph", JSX_FRACTAL_MORPH),
        ("Shatter", JSX_SHATTER),
        ("BeamEnergy", JSX_BEAM_ENERGY),
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
        "CCParticle": "D5_CCParticle_Fountain",
        "CCLightRays": "D5_CCLightRays_Sweep",
        "FractalMorph": "D5_FractalNoise_Morph",
        "Shatter": "D5_Shatter_Explosion",
        "BeamEnergy": "D5_Beam_Energy",
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
