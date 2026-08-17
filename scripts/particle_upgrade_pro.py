"""Particle System PRO Upgrade - Industry-grade multi-layer particle compositions
Architecture per comp:
  1. Environment gradient (animated, mood base)
  2. Atmospheric dust layer (z=-300, ambient depth)
  3. Main particle system (z=0, full lifecycle: color temp shift birth->death)
  4. Secondary detail particles (z=+100, different physics)
  5. Foreground bokeh layer (z=+500, large soft particles, DoF aesthetic)
  6. Light interaction (key light intensity synced to particle birth = environment response)
  7. DoF camera with slow drift + focus breathing
  8. Additive blending + Glow post-processing
  9. Narrative rhythm: birth rate envelope (surge -> steady -> decay)
Verified APIs: CC PW flat indices, BlendingMode.ADD, ADBE Glo2, Camera Options DoF, ADBE Ramp
"""
import json, time, sys, os, glob
from pathlib import Path
from datetime import datetime

BRIDGE_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge")
CMD_FILE = BRIDGE_DIR / "ae_command.json"
RES_FILE = BRIDGE_DIR / "ae_result.json"
BASE_OUT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production")

def send_bridge(code, wait=60, tag=""):
    try: RES_FILE.unlink(missing_ok=True)
    except: pass
    ts = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    cmd = {"command": "runScript", "args": {"code": code}, "timestamp": ts, "status": "pending"}
    CMD_FILE.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    print(f"  [{tag}] Sent, waiting up to {wait}s...")
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(0.5)
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

def make_render_jsx(comp_name, output_path):
    out_escaped = output_path.replace("\\", "/")
    return f"""
(function(){{
try{{
var outF = new File("{out_escaped}");
var comp = null;
for (var i = 1; i <= app.project.numItems; i++) {{
    var item = app.project.item(i);
    if (item instanceof CompItem && item.name == "{comp_name}") {{ comp = item; break; }}
}}
if (!comp) return "ERR:comp '{comp_name}' not found";
// Clear any leftover/recovered render queue items first (they can stall render())
while (app.project.renderQueue.numItems > 0) {{ app.project.renderQueue.item(1).remove(); }}
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
# Cleanup: remove old versions of target comps
# ============================================================
JSX_CLEANUP = """
(function(){
var names = ['D5_CCParticle_Fountain','D5_Shatter_Explosion'];
var removed = 0;
for(var n=0;n<names.length;n++){
    for(var i=app.project.numItems;i>=1;i--){
        var it = app.project.item(i);
        if(it.name == names[n] && it instanceof CompItem){ it.remove(); removed++; }
    }
}
return "OK:removed " + removed;
})();
"""

# ============================================================
# COMP 1: PRO FOUNTAIN - 3-layer particle system + DoF + light sync
# 4s @ 30fps = 120 frames, narrative: awakening -> surge -> settle
# ============================================================
JSX_FOUNTAIN_PRO = """
(function(){
try{
var comp = app.project.items.addComp("D5_CCParticle_Fountain", 1920, 1080, 1, 4, 30);
comp.bgColor = [0.01, 0.01, 0.03];
comp.motionBlur = true;

// --- Layer 1: Environment gradient (deep space mood, slow color arc) ---
var bgL = comp.layers.addSolid([0.5,0.5,0.5], "Environment", 1920, 1080, 1);
var bgR = bgL.Effects.addProperty("ADBE Ramp");
bgR.property("ADBE Ramp-0005").setValue(2);
bgR.property("ADBE Ramp-0001").setValue([960, 750]);
bgR.property("ADBE Ramp-0002").setValueAtTime(0, [0.06, 0.04, 0.14]);
bgR.property("ADBE Ramp-0002").setValueAtTime(2, [0.1, 0.06, 0.2]);
bgR.property("ADBE Ramp-0002").setValueAtTime(4, [0.05, 0.08, 0.16]);
bgR.property("ADBE Ramp-0003").setValue([960, 0]);
bgR.property("ADBE Ramp-0004").setValue([0.0, 0.0, 0.02]);

// --- Layer 2: Atmospheric dust (deep background, z=-300) ---
var dustL = comp.layers.addSolid([0,0,0], "AtmoDust", 1920, 1080, 1);
dustL.threeDLayer = true;
dustL.property("Position").setValue([960, 540, -300]);
dustL.blendingMode = BlendingMode.ADD;
var dust = dustL.Effects.addProperty("CC Particle World");
dust.property(14).setValue(25);
dust.property(15).setValue(4);
dust.property(17).setValue(0.5);
dust.property(18).setValue(0.5);
dust.property(20).setValue(0.6);
dust.property(21).setValue(0.4);
dust.property(25).setValue(3);
dust.property(26).setValue(0.12);
dust.property(28).setValue(0.02);
dust.property(53).setValue(6);
dust.property(63).setValue(2.5);
dust.property(64).setValue(1.5);
dust.property(65).setValue(40);
dust.property(66).setValue(35);
dust.property(70).setValue([0.35, 0.45, 0.8]);
dust.property(71).setValue([0.1, 0.15, 0.35]);
dust.property(102).setValue(42);

// --- Layer 3: Main fountain (z=0, lifecycle color shift gold->blue) ---
var mainL = comp.layers.addSolid([0,0,0], "FountainMain", 1920, 1080, 1);
mainL.threeDLayer = true;
mainL.property("Position").setValue([960, 540, 0]);
mainL.blendingMode = BlendingMode.ADD;
var main = mainL.Effects.addProperty("CC Particle World");
// Birth rate narrative envelope: awaken -> surge -> steady -> decay
main.property(14).setValueAtTime(0, 0);
main.property(14).setValueAtTime(0.4, 20);
main.property(14).setValueAtTime(1.2, 110);
main.property(14).setValueAtTime(2.2, 75);
main.property(14).setValueAtTime(3.5, 35);
main.property(14).setValueAtTime(4, 15);
main.property(15).setValue(2.4);
// Producer: SAFE centered + gentle drift (avoids killer combo: tiny radius + off-center Y + kf X + kf velocity)
main.property(17).setValueAtTime(0, 0.47);
main.property(17).setValueAtTime(2, 0.53);
main.property(17).setValueAtTime(4, 0.5);
main.property(18).setValue(0.5);
main.property(20).setValue(0.15);
main.property(21).setValue(0.10);
// Physics: radial burst + gravity arc (constant velocity - validated safe)
main.property(25).setValue(3);
main.property(26).setValue(1.9);
main.property(28).setValue(0.55);
main.property(29).setValue(0.12);
// Particle lifecycle: warm birth -> cool death (color temperature shift)
main.property(53).setValue(6);
main.property(63).setValue(7);
main.property(64).setValue(1.5);
main.property(65).setValue(45);
main.property(66).setValue(95);
main.property(70).setValue([1, 0.88, 0.45]);
main.property(71).setValue([0.2, 0.45, 1.0]);
main.property(102).setValue(7);
// Glow post-process (self-illumination)
var mGlow = mainL.Effects.addProperty("ADBE Glo2");
mGlow.property("ADBE Glo2-0002").setValue(30);
mGlow.property("ADBE Glo2-0003").setValue(45);
mGlow.property("ADBE Glo2-0004").setValue(0.65);

// --- Layer 4: Secondary spray (z=100, faster/smaller/whiter) ---
var sprayL = comp.layers.addSolid([0,0,0], "SprayDetail", 1920, 1080, 1);
sprayL.threeDLayer = true;
sprayL.property("Position").setValue([960, 540, 100]);
sprayL.blendingMode = BlendingMode.ADD;
var spray = sprayL.Effects.addProperty("CC Particle World");
spray.property(14).setValueAtTime(0, 0);
spray.property(14).setValueAtTime(0.7, 10);
spray.property(14).setValueAtTime(1.5, 80);
spray.property(14).setValueAtTime(2.5, 50);
spray.property(14).setValueAtTime(4, 8);
spray.property(15).setValue(1.4);
spray.property(17).setValueAtTime(0, 0.48);
spray.property(17).setValueAtTime(4, 0.52);
spray.property(18).setValue(0.5);
spray.property(20).setValue(0.12);
spray.property(21).setValue(0.08);
spray.property(25).setValue(3);
spray.property(26).setValue(3.0);
spray.property(28).setValue(1.1);
spray.property(29).setValue(0.2);
spray.property(53).setValue(6);
spray.property(63).setValue(3);
spray.property(64).setValue(0.5);
spray.property(65).setValue(60);
spray.property(66).setValue(60);
spray.property(70).setValue([0.9, 0.95, 1.0]);
spray.property(71).setValue([0.4, 0.7, 1.0]);
spray.property(102).setValue(21);

// --- Layer 5: Foreground bokeh (z=500, large soft out-of-focus particles) ---
var bokehL = comp.layers.addSolid([0,0,0], "FGBokeh", 1920, 1080, 1);
bokehL.threeDLayer = true;
bokehL.property("Position").setValue([960, 540, 500]);
bokehL.blendingMode = BlendingMode.ADD;
var bokeh = bokehL.Effects.addProperty("CC Particle World");
bokeh.property(14).setValue(6);
bokeh.property(15).setValue(4);
bokeh.property(17).setValue(0.5);
bokeh.property(18).setValue(0.6);
bokeh.property(20).setValue(0.5);
bokeh.property(25).setValue(3);
bokeh.property(26).setValue(0.25);
bokeh.property(28).setValue(-0.05);
bokeh.property(53).setValue(6);
bokeh.property(63).setValue(28);
bokeh.property(64).setValue(20);
bokeh.property(65).setValue(50);
bokeh.property(66).setValue(14);
bokeh.property(70).setValue([1, 0.8, 0.5]);
bokeh.property(71).setValue([0.5, 0.6, 1.0]);
bokeh.property(102).setValue(99);
var bBlur = bokehL.Effects.addProperty("ADBE Gaussian Blur 2");
bBlur.property("ADBE Gaussian Blur 2-0001").setValue(18);

// --- Layer 6: Core glow (light source visual, pulses with birth) ---
var coreL = comp.layers.addSolid([1, 0.85, 0.5], "CoreGlow", 260, 260, 1);
coreL.threeDLayer = true;
coreL.property("Position").setValueAtTime(0, [885, 780, 0]);
coreL.property("Position").setValueAtTime(2, [1035, 780, 0]);
coreL.property("Position").setValueAtTime(4, [920, 780, 0]);
coreL.blendingMode = BlendingMode.ADD;
var cBlur = coreL.Effects.addProperty("ADBE Gaussian Blur 2");
cBlur.property("ADBE Gaussian Blur 2-0001").setValue(50);
var cScl = coreL.property("Scale");
cScl.setValueAtTime(0, [20, 20]);
cScl.setValueAtTime(1.2, [130, 130]);
cScl.setValueAtTime(2.2, [90, 90]);
cScl.setValueAtTime(4, [50, 50]);
coreL.property("Opacity").setValueAtTime(0, 0);
coreL.property("Opacity").setValueAtTime(0.5, 70);
coreL.property("Opacity").setValueAtTime(4, 30);

// --- Light simulation: 2D ADD glows (SAFE - 3D addLight shades black carrier solids opaque) ---
var keyGlow = comp.layers.addSolid([1, 0.8, 0.5], "KeyGlow", 500, 500, 1);
keyGlow.threeDLayer = true;
keyGlow.property("Position").setValue([960, 650, 200]);
keyGlow.blendingMode = BlendingMode.ADD;
var kgBlur = keyGlow.Effects.addProperty("ADBE Gaussian Blur 2");
kgBlur.property("ADBE Gaussian Blur 2-0001").setValue(80);
keyGlow.property("Opacity").setValueAtTime(0, 5);
keyGlow.property("Opacity").setValueAtTime(1.2, 40);
keyGlow.property("Opacity").setValueAtTime(2.5, 25);
keyGlow.property("Opacity").setValueAtTime(4, 12);
var rimGlow = comp.layers.addSolid([0.4, 0.6, 1.0], "RimGlow", 400, 400, 1);
rimGlow.threeDLayer = true;
rimGlow.property("Position").setValue([200, 150, -400]);
rimGlow.blendingMode = BlendingMode.ADD;
var rgBlur = rimGlow.Effects.addProperty("ADBE Gaussian Blur 2");
rgBlur.property("ADBE Gaussian Blur 2-0001").setValue(60);
rimGlow.property("Opacity").setValue(22);

// --- Camera: cinematic arc + push-in during surge + subtle roll ---
var cam = comp.layers.addCamera("ProCam", [960, 540]);
try{ cam.property("ADBE Camera Options Group").property("ADBE Camera Type").setValue(1); }catch(e2){}
cam.property("Position").setValueAtTime(0, [780, 520, -1000]);
cam.property("Position").setValueAtTime(0.8, [850, 480, -920]);
cam.property("Position").setValueAtTime(1.5, [1020, 450, -820]);
cam.property("Position").setValueAtTime(2.5, [1100, 470, -780]);
cam.property("Position").setValueAtTime(3.5, [1000, 510, -850]);
cam.property("Position").setValueAtTime(4, [950, 530, -880]);
try{
    cam.property("Rotation").setValueAtTime(0, [0, 0, -1.5]);
    cam.property("Rotation").setValueAtTime(2, [0, 0, 1.0]);
    cam.property("Rotation").setValueAtTime(4, [0, 0, -0.5]);
}catch(e4){}
try{
    var co = cam.property("Camera Options");
    co.property("Depth of Field").setValue(1);
    co.property("Focus Distance").setValueAtTime(0, 900);
    co.property("Focus Distance").setValueAtTime(2, 820);
    co.property("Focus Distance").setValueAtTime(4, 880);
    co.property("Aperture").setValue(10);
    co.property("Blur Level").setValue(70);
}catch(e3){}
return "OK:D5_CCParticle_Fountain PRO (3-layer+DoF+lightSync)";
}catch(e){return "ERR:"+e.toString();}
})();
"""

# ============================================================
# COMP 2: PRO EXPLOSION - multi-stage narrative
# charge(0-0.4) -> detonation(0.4) -> blast(0.4-1.5) -> aftermath(1.5-4)
# 5 particle systems + shockwave + flash + camera shake + light response
# ============================================================
JSX_EXPLOSION_PRO = """
(function(){
try{
var comp = app.project.items.addComp("D5_Shatter_Explosion", 1920, 1080, 1, 4, 30);
comp.bgColor = [0.01, 0.01, 0.02];
// NOTE: comp.motionBlur intentionally OFF (motion blur + many particle systems = render hang)

// --- Environment: animated warm void (continuous color evolution for spatial richness) ---
var bgL = comp.layers.addSolid([0.5,0.5,0.5], "Void", 1920, 1080, 1);
var bgR = bgL.Effects.addProperty("ADBE Ramp");
bgR.property("ADBE Ramp-0005").setValue(2);
bgR.property("ADBE Ramp-0001").setValue([960, 540]);
bgR.property("ADBE Ramp-0002").setValueAtTime(0, [0.12, 0.08, 0.16]);
bgR.property("ADBE Ramp-0002").setValueAtTime(0.5, [0.12, 0.07, 0.05]);
bgR.property("ADBE Ramp-0002").setValueAtTime(1.5, [0.14, 0.09, 0.12]);
bgR.property("ADBE Ramp-0002").setValueAtTime(2.5, [0.11, 0.08, 0.14]);
bgR.property("ADBE Ramp-0002").setValueAtTime(3.5, [0.10, 0.07, 0.12]);
bgR.property("ADBE Ramp-0002").setValueAtTime(4, [0.09, 0.07, 0.11]);
bgR.property("ADBE Ramp-0003").setValue([960, 540]);
bgR.property("ADBE Ramp-0004").setValueAtTime(0, [0.06, 0.03, 0.08]);
bgR.property("ADBE Ramp-0004").setValueAtTime(1, [0.03, 0.06, 0.07]);
bgR.property("ADBE Ramp-0004").setValueAtTime(2, [0.05, 0.03, 0.08]);
bgR.property("ADBE Ramp-0004").setValueAtTime(3, [0.03, 0.05, 0.06]);
bgR.property("ADBE Ramp-0004").setValueAtTime(4, [0.06, 0.03, 0.07]);

// --- Atmospheric dust (ADD, centered, large radius, FAST drift for continuous motion) ---
var dustL = comp.layers.addSolid([0,0,0], "VoidDust", 1920, 1080, 1);
dustL.threeDLayer = true;
dustL.property("Position").setValueAtTime(0, [880, 500, -250]);
dustL.property("Position").setValueAtTime(2, [1040, 580, -250]);
dustL.property("Position").setValueAtTime(4, [900, 520, -250]);
dustL.blendingMode = BlendingMode.ADD;
var dust = dustL.Effects.addProperty("CC Particle World");
dust.property(14).setValue(40);
dust.property(15).setValue(4);
dust.property(17).setValue(0.5);
dust.property(18).setValue(0.5);
dust.property(20).setValue(0.8);
dust.property(21).setValue(0.6);
dust.property(25).setValue(3);
dust.property(26).setValue(0.40);
dust.property(53).setValue(6);
dust.property(63).setValue(3.5);
dust.property(64).setValue(1.5);
dust.property(66).setValue(45);
dust.property(70).setValue([0.5, 0.45, 0.6]);
dust.property(71).setValue([0.22, 0.18, 0.32]);
dust.property(102).setValue(11);

// --- Core object (charges then detonates) ---
var core = comp.layers.addSolid([1, 0.7, 0.2], "Core", 200, 200, 1);
core.threeDLayer = true;
core.property("Position").setValue([960, 540, 0]);
core.blendingMode = BlendingMode.ADD;
var coreBlur = core.Effects.addProperty("ADBE Gaussian Blur 2");
coreBlur.property("ADBE Gaussian Blur 2-0001").setValue(25);
var cScl = core.property("Scale");
cScl.setValueAtTime(0, [30, 30]);
cScl.setValueAtTime(0.15, [45, 45]);
cScl.setValueAtTime(0.25, [35, 35]);
cScl.setValueAtTime(0.33, [60, 60]);
cScl.setValueAtTime(0.38, [48, 48]);
cScl.setValueAtTime(0.42, [90, 90]);
cScl.setValueAtTime(0.46, [0, 0]);
core.property("Opacity").setValueAtTime(0.44, 50);
core.property("Opacity").setValueAtTime(0.5, 0);

// --- Detonation flash (2-frame whiteout) ---
var flash = comp.layers.addSolid([1, 0.97, 0.9], "DetFlash", 1920, 1080, 1);
flash.blendingMode = BlendingMode.ADD;
flash.property("Opacity").setValueAtTime(0, 0);
flash.property("Opacity").setValueAtTime(0.42, 0);
flash.property("Opacity").setValueAtTime(0.46, 12);
flash.property("Opacity").setValueAtTime(0.6, 4);
flash.property("Opacity").setValueAtTime(0.85, 0);

// --- Spark burst (ADD, centered producer, moderate radius, type6 - SAFE) ---
var sparkL = comp.layers.addSolid([0,0,0], "Sparks", 1920, 1080, 1);
sparkL.threeDLayer = true;
sparkL.property("Position").setValue([960, 540, 0]);
sparkL.blendingMode = BlendingMode.ADD;
var sparks = sparkL.Effects.addProperty("CC Particle World");
sparks.property(14).setValueAtTime(0, 0);
sparks.property(14).setValueAtTime(0.42, 0);
sparks.property(14).setValueAtTime(0.46, 120);
sparks.property(14).setValueAtTime(0.7, 30);
sparks.property(14).setValueAtTime(1.5, 0);
sparks.property(15).setValue(1.0);
sparks.property(17).setValue(0.5);
sparks.property(18).setValue(0.5);
sparks.property(20).setValue(0.18);
sparks.property(21).setValue(0.15);
sparks.property(25).setValue(3);
sparks.property(26).setValue(3.2);
sparks.property(28).setValue(0.35);
sparks.property(29).setValue(0.3);
sparks.property(53).setValue(6);
sparks.property(63).setValue(2.5);
sparks.property(64).setValue(0.4);
sparks.property(65).setValue(55);
sparks.property(66).setValue(50);
sparks.property(70).setValue([1, 1, 0.85]);
sparks.property(71).setValue([1, 0.4, 0.05]);
sparks.property(102).setValue(13);
var sGlow = sparkL.Effects.addProperty("ADBE Glo2");
sGlow.property("ADBE Glo2-0002").setValue(15);
sGlow.property("ADBE Glo2-0003").setValue(20);
sGlow.property("ADBE Glo2-0004").setValue(0.5);

// --- Debris field (ADD, centered, type6, moderate radius - SAFE) ---
var debrisL = comp.layers.addSolid([0,0,0], "Debris", 1920, 1080, 1);
debrisL.threeDLayer = true;
debrisL.property("Position").setValue([960, 540, -50]);
debrisL.blendingMode = BlendingMode.ADD;
var debris = debrisL.Effects.addProperty("CC Particle World");
debris.property(14).setValueAtTime(0, 0);
debris.property(14).setValueAtTime(0.45, 0);
debris.property(14).setValueAtTime(0.5, 100);
debris.property(14).setValueAtTime(0.9, 15);
debris.property(14).setValueAtTime(1.5, 0);
debris.property(15).setValue(2.2);
debris.property(17).setValue(0.5);
debris.property(18).setValue(0.5);
debris.property(20).setValue(0.20);
debris.property(21).setValue(0.18);
debris.property(25).setValue(3);
debris.property(26).setValue(1.9);
debris.property(28).setValue(1.3);
debris.property(29).setValue(0.15);
debris.property(53).setValue(6);
debris.property(63).setValue(8);
debris.property(64).setValue(3);
debris.property(65).setValue(70);
debris.property(66).setValue(50);
debris.property(70).setValue([0.95, 0.55, 0.1]);
debris.property(71).setValue([0.25, 0.04, 0.01]);
debris.property(102).setValue(31);

// --- Rising embers (ADD, centered, negative gravity - SAFE) ---
var emberL = comp.layers.addSolid([0,0,0], "Embers", 1920, 1080, 1);
emberL.threeDLayer = true;
emberL.property("Position").setValue([960, 540, 50]);
emberL.blendingMode = BlendingMode.ADD;
var embers = emberL.Effects.addProperty("CC Particle World");
embers.property(14).setValueAtTime(0, 0);
embers.property(14).setValueAtTime(0.8, 0);
embers.property(14).setValueAtTime(1.0, 60);
embers.property(14).setValueAtTime(2.5, 45);
embers.property(14).setValueAtTime(4, 18);
embers.property(15).setValue(4.0);
embers.property(17).setValue(0.5);
embers.property(18).setValue(0.5);
embers.property(20).setValue(0.25);
embers.property(21).setValue(0.20);
embers.property(25).setValue(3);
embers.property(26).setValue(0.45);
embers.property(28).setValue(-0.12);
embers.property(29).setValue(0.4);
embers.property(53).setValue(6);
embers.property(63).setValue(8);
embers.property(64).setValue(2.0);
embers.property(65).setValue(55);
embers.property(66).setValue(60);
embers.property(70).setValue([1, 0.55, 0.12]);
embers.property(71).setValue([0.6, 0.28, 0.08]);
embers.property(102).setValue(57);

// --- Smoke (ADD, centered, moderate radius - SAFE) ---
var smokeL = comp.layers.addSolid([0,0,0], "Smoke", 1920, 1080, 1);
smokeL.threeDLayer = true;
smokeL.property("Position").setValue([960, 540, -30]);
smokeL.blendingMode = BlendingMode.ADD;
var smoke = smokeL.Effects.addProperty("CC Particle World");
smoke.property(14).setValueAtTime(0, 0);
smoke.property(14).setValueAtTime(1.0, 0);
smoke.property(14).setValueAtTime(1.3, 35);
smoke.property(14).setValueAtTime(3.0, 20);
smoke.property(14).setValueAtTime(4, 8);
smoke.property(15).setValue(4.0);
smoke.property(17).setValue(0.5);
smoke.property(18).setValue(0.5);
smoke.property(20).setValue(0.22);
smoke.property(21).setValue(0.18);
smoke.property(25).setValue(3);
smoke.property(26).setValue(0.3);
smoke.property(28).setValue(-0.08);
smoke.property(29).setValue(0.5);
smoke.property(53).setValue(6);
smoke.property(63).setValue(20);
smoke.property(64).setValue(55);
smoke.property(65).setValue(45);
smoke.property(66).setValue(45);
smoke.property(70).setValue([0.55, 0.4, 0.3]);
smoke.property(71).setValue([0.28, 0.22, 0.25]);
smoke.property(102).setValue(73);
var smBlur = smokeL.Effects.addProperty("ADBE Gaussian Blur 2");
smBlur.property("ADBE Gaussian Blur 2-0001").setValue(6);

// --- Shockwave ring (expanding, verified mask technique) ---
var ring = comp.layers.addSolid([1, 0.75, 0.3], "Shockwave", 300, 300, 1);
ring.threeDLayer = true;
ring.property("Position").setValue([960, 540, 10]);
ring.blendingMode = BlendingMode.ADD;
var mOuter = ring.property("Masks").addProperty("Mask");
mOuter.maskMode = MaskMode.ADD;
var ov = mOuter.property("Mask Path").value;
ov.vertices = [[150,0],[300,150],[150,300],[0,150]];
ov.closed = true;
mOuter.property("Mask Path").setValue(ov);
var mInner = ring.property("Masks").addProperty("Mask");
mInner.maskMode = MaskMode.SUBTRACT;
var iv = mInner.property("Mask Path").value;
iv.vertices = [[150,40],[260,150],[150,260],[40,150]];
iv.closed = true;
mInner.property("Mask Path").setValue(iv);
var rScl = ring.property("Scale");
rScl.setValueAtTime(0.42, [10, 10]);
rScl.setValueAtTime(1.1, [900, 900]);
ring.property("Opacity").setValueAtTime(0.42, 0);
ring.property("Opacity").setValueAtTime(0.46, 35);
ring.property("Opacity").setValueAtTime(1.1, 0);

// --- Blast glow (2D ADD radial pulse - SAFE; a 3D light layer would shade the black
//     particle carrier solids into opaque surfaces and occlude the whole scene) ---
var glowL = comp.layers.addSolid([1, 0.6, 0.2], "BlastGlow", 700, 700, 1);
glowL.property("Position").setValue([960, 540]);
glowL.blendingMode = BlendingMode.ADD;
var gBlur = glowL.Effects.addProperty("ADBE Gaussian Blur 2");
gBlur.property("ADBE Gaussian Blur 2-0001").setValue(90);
var gScl = glowL.property("Scale");
gScl.setValueAtTime(0, [20, 20]);
gScl.setValueAtTime(0.46, [40, 40]);
gScl.setValueAtTime(0.6, [260, 260]);
gScl.setValueAtTime(1.3, [160, 160]);
gScl.setValueAtTime(2.5, [90, 90]);
glowL.property("Opacity").setValueAtTime(0, 0);
glowL.property("Opacity").setValueAtTime(0.46, 0);
glowL.property("Opacity").setValueAtTime(0.52, 12);
glowL.property("Opacity").setValueAtTime(1.0, 5);
glowL.property("Opacity").setValueAtTime(1.8, 0);

// --- Camera: impact shake (decaying amplitude) + subtle dolly push ---
var cam = comp.layers.addCamera("BlastCam", [960, 540]);
try{ cam.property("ADBE Camera Options Group").property("ADBE Camera Type").setValue(1); }catch(e2){}
cam.property("Position").setValueAtTime(0, [960, 540, -1050]);
cam.property("Position").setValueAtTime(0.46, [960, 540, -1050]);
// Impact shake: sharp lateral hits decaying over 1.5s
cam.property("Position").setValueAtTime(0.50, [948, 548, -1030]);
cam.property("Position").setValueAtTime(0.54, [975, 532, -1020]);
cam.property("Position").setValueAtTime(0.60, [952, 550, -1010]);
cam.property("Position").setValueAtTime(0.68, [970, 535, -1000]);
cam.property("Position").setValueAtTime(0.80, [955, 545, -995]);
cam.property("Position").setValueAtTime(1.0, [965, 538, -990]);
cam.property("Position").setValueAtTime(1.3, [958, 542, -985]);
cam.property("Position").setValueAtTime(1.8, [961, 539, -980]);
cam.property("Position").setValueAtTime(2.5, [960, 540, -975]);
cam.property("Position").setValueAtTime(4, [960, 540, -970]);
return "OK:D5_Shatter_Explosion PRO (5-system multi-stage SAFE)";
}catch(e){return "ERR:"+e.toString();}
})();
"""

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("PARTICLE SYSTEM PRO UPGRADE")
    print("Multi-layer + lifecycle + light fusion + DoF depth")
    print("=" * 60)

    # Phase 0: cleanup old versions
    print("\n[Phase 0] Remove old comps...")
    r = send_bridge(JSX_CLEANUP, wait=30, tag="CLEANUP")
    check_result(r, "CLEANUP")
    time.sleep(1)

    # Phase 1: create (one at a time, confirm each)
    comps = [
        ("D5_CCParticle_Fountain", JSX_FOUNTAIN_PRO, str(BASE_OUT / "dir5_plugin_effects" / "D5_CCParticle_Fountain.mp4")),
        ("D5_Shatter_Explosion", JSX_EXPLOSION_PRO, str(BASE_OUT / "dir5_plugin_effects" / "D5_Shatter_Explosion.mp4")),
    ]

    print("\n[Phase 1] Create PRO compositions...")
    created = []
    for name, jsx, out in comps:
        r = send_bridge(jsx, wait=60, tag=name)
        if check_result(r, name):
            created.append((name, out))
        time.sleep(1)

    if not created:
        print("FATAL: nothing created")
        sys.exit(1)

    # Phase 2: render SEQUENTIALLY (wait for each to fully complete)
    print("\n[Phase 2] Render (600s budget each - heavy particle sims)...")
    rendered = []
    for name, out in created:
        for old in glob.glob(out.replace(".mp4", ".*")):
            try: os.remove(old)
            except: pass
        jsx = make_render_jsx(name, out)
        r = send_bridge(jsx, wait=600, tag=f"RENDER_{name}")
        if check_result(r, f"RENDER_{name}"):
            rendered.append((name, out))
        else:
            # Timeout: ping to confirm AE is idle before continuing
            print(f"  [WARN] Render timeout - pinging AE before next command...")
            ping_ok = False
            for attempt in range(60):
                time.sleep(5)
                pr = send_bridge("(function(){return 'PONG';})();", wait=10, tag="PING")
                if pr:
                    data = pr.get("result", {}).get("data", {}).get("result", "")
                    if "PONG" in data:
                        ping_ok = True
                        break
            print(f"  [PING] AE idle={ping_ok}")
            # Check if file appeared anyway
            if Path(out).exists() and Path(out).stat().st_size > 102400:
                print(f"  [RECOVERED] File exists: {Path(out).stat().st_size/1024:.0f}KB")
                rendered.append((name, out))
        time.sleep(3)

    # Phase 3: verify
    print(f"\n{'='*60}")
    print("VERIFICATION:")
    for name, out in rendered:
        p = Path(out)
        if p.exists():
            kb = p.stat().st_size / 1024
            print(f"  [{'OK' if kb > 100 else 'SMALL'}] {p.name}: {kb:.0f}KB")
        else:
            print(f"  [MISSING] {p.name}")

    print(f"\nSUMMARY: Created={len(created)}/2, Rendered={len(rendered)}/2")
    print("DONE.")
