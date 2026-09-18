"""Fix Rebuild: 7 compositions that failed >100KB size check
Root causes: effects silently failed (display names), scenes too static for H.264
Strategy: full-screen continuous motion + bright colors + verified matchName/index access
- Effects: matchName ONLY (ADBE Fractal Noise, ADBE Tint, ADBE Ramp, ADBE Glo2, ADBE Lightning 2, CC Particle World)
- CC Particle World: FLAT indices (14=BirthRate, 15=Longevity, 17-19=ProducerXYZ, 26=Velocity, 28=Gravity, 53=Type, 63/64=Size, 66=Opacity, 70/71=Colors)
- Lightning 2: 0002=Source[x,y], 0003=Target[x,y], 0008=CoreColor[r,g,b,a]
- Fractal Noise: 0004=Contrast, 0010=Scale, 0013=OffsetTurbulence, 0023=Evolution
- Text: .value modify approach; 2D=[x,y]; never iterate app.effects
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
# Phase 0: Cleanup old comps + DIAG comps
# ============================================================
JSX_CLEANUP = """
(function(){
var names = ['D3_Handheld_Shake','D4_MultiZ_Parallax','D5_FractalNoise_Morph','D5_Shatter_Explosion','D5_Beam_Energy','D6_Elastic_Bounce','D6_Overshoot_Punch','DIAG3','DIAG4','DIAG5','DIAG6','DIAG7'];
var removed = 0;
for(var n=0;n<names.length;n++){
    for(var i=app.project.numItems;i>=1;i--){
        var it = app.project.item(i);
        if(it.name == names[n] && it instanceof CompItem){ it.remove(); removed++; }
    }
}
return "OK:removed " + removed + " comps";
})();
"""

# ============================================================
# 1. D3_Handheld_Shake - 3D scene + multi-freq wiggle camera + animated light
# ============================================================
JSX_D3_HANDHELD = """
(function(){
try{
var comp = app.project.items.addComp("D3_Handheld_Shake", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.05, 0.05, 0.1];
// Animated background ramp (full-screen motion base)
var bgL = comp.layers.addSolid([0.5,0.5,0.5], "BGRamp", 1920, 1080, 1);
var bgR = bgL.Effects.addProperty("ADBE Ramp");
bgR.property("ADBE Ramp-0001").setValue([960, 0]);
bgR.property("ADBE Ramp-0002").setValue([0.15, 0.05, 0.35]);
bgR.property("ADBE Ramp-0003").setValue([960, 1080]);
bgR.property("ADBE Ramp-0004").setValueAtTime(0, [0.05, 0.15, 0.3]);
bgR.property("ADBE Ramp-0004").setValueAtTime(1.5, [0.35, 0.1, 0.15]);
bgR.property("ADBE Ramp-0004").setValueAtTime(3, [0.1, 0.3, 0.25]);
// Scene objects at multiple depths (bright colors)
var cols = [[0.9,0.3,0.2],[0.2,0.8,0.9],[0.95,0.85,0.2],[0.4,0.9,0.4],[0.9,0.5,0.8],[0.3,0.5,0.95],[0.95,0.6,0.1],[0.6,0.9,0.9]];
for(var i=0;i<8;i++){
    var sz = 120 + (i%4)*80;
    var obj = comp.layers.addSolid(cols[i], "Obj_"+i, sz, sz, 1);
    obj.threeDLayer = true;
    obj.property("Position").setValue([200+i*220, 250+(i%3)*250, -600+i*200]);
    obj.property("Y Rotation").setValueAtTime(0, i*45);
    obj.property("Y Rotation").setValueAtTime(3, i*45 + 180 + i*30);
}
// Text
var txt = comp.layers.addText("HANDHELD");
var doc = txt.property("Source Text").value;
doc.fontSize = 140; doc.fillColor = [1, 1, 0.9];
doc.justification = ParagraphJustification.CENTER_JUSTIFY;
txt.property("Source Text").setValue(doc);
txt.threeDLayer = true;
txt.property("Position").setValue([960, 540, 300]);
// Camera with keyframed drift + multi-frequency wiggle
var cam = comp.layers.addCamera("Cam", [960, 540]);
try{ cam.property("ADBE Camera Options Group").property("ADBE Camera Type").setValue(1); }catch(e2){}
var cp = cam.property("Position");
cp.setValueAtTime(0, [960, 540, 1200]);
cp.setValueAtTime(1.5, [860, 480, 1000]);
cp.setValueAtTime(3, [1060, 580, 1100]);
try{
    cam.property("Position").property("X Position").expression = "value + wiggle(2,25)[0]-960 + wiggle(9,6)[0]-960";
    cam.property("Position").property("Y Position").expression = "value + wiggle(1.7,18)[1]-540 + wiggle(8,5)[1]-540";
    cam.property("Z Rotation").expression = "wiggle(1.3, 1.2)";
}catch(e3){}
// Animated light sweeping
var lt = comp.layers.addLight("Sweep", [400, 200]);
lt.threeDLayer = true;
lt.property("Position").setValueAtTime(0, [300, 200, 800]);
lt.property("Position").setValueAtTime(1.5, [1600, 400, 600]);
lt.property("Position").setValueAtTime(3, [500, 700, 900]);
lt.property("Light Options").property("Intensity").setValue(500);
return "OK:D3_Handheld_Shake";
}catch(e){return "ERR:"+e.toString();}
})();
"""

# ============================================================
# 2. D4_MultiZ_Parallax - camera fly-through 6 depth planes
# ============================================================
JSX_D4_MULTIZ = """
(function(){
try{
var comp = app.project.items.addComp("D4_MultiZ_Parallax", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.02, 0.02, 0.06];
// Deep background ramp
var bgL = comp.layers.addSolid([0.5,0.5,0.5], "DeepBG", 2400, 1400, 1);
bgL.threeDLayer = true;
bgL.property("Position").setValue([960, 540, -1500]);
var bgR = bgL.Effects.addProperty("ADBE Ramp");
bgR.property("ADBE Ramp-0001").setValue([1200, 0]);
bgR.property("ADBE Ramp-0002").setValue([0.3, 0.1, 0.5]);
bgR.property("ADBE Ramp-0003").setValue([1200, 1400]);
bgR.property("ADBE Ramp-0004").setValueAtTime(0, [0.05, 0.2, 0.4]);
bgR.property("ADBE Ramp-0004").setValueAtTime(3, [0.4, 0.15, 0.1]);
// 6 depth planes with objects
var planeZ = [-1000, -600, -200, 200, 600, 1000];
var planeCols = [[0.2,0.3,0.7],[0.7,0.2,0.5],[0.2,0.7,0.4],[0.8,0.6,0.1],[0.5,0.2,0.8],[0.9,0.3,0.3]];
for(var p=0;p<6;p++){
    for(var j=0;j<3;j++){
        var w = 80 + p*30 + j*40;
        var el = comp.layers.addSolid(planeCols[p], "P"+p+"_"+j, w, w*0.6, 1);
        el.threeDLayer = true;
        el.property("Position").setValue([200+j*600+p*80, 200+((p+j)%3)*300, planeZ[p]]);
        el.property("Y Rotation").setValueAtTime(0, p*20+j*40);
        el.property("Y Rotation").setValueAtTime(3, p*20+j*40+120);
        el.property("Opacity").setValue(60+p*7);
    }
}
// Text at mid depth
var txt = comp.layers.addText("PARALLAX");
var doc = txt.property("Source Text").value;
doc.fontSize = 160; doc.fillColor = [1, 0.9, 0.3];
doc.justification = ParagraphJustification.CENTER_JUSTIFY;
txt.property("Source Text").setValue(doc);
txt.threeDLayer = true;
txt.property("Position").setValue([960, 540, 0]);
// Camera fly-through (strong Z movement)
var cam = comp.layers.addCamera("Cam", [960, 540]);
try{ cam.property("ADBE Camera Options Group").property("ADBE Camera Type").setValue(1); }catch(e2){}
cam.property("Position").setValueAtTime(0, [960, 540, 1800]);
cam.property("Position").setValueAtTime(1.5, [760, 440, 600]);
cam.property("Position").setValueAtTime(3, [1100, 600, -200]);
// Light following camera
var lt = comp.layers.addLight("Key", [960, 300]);
lt.threeDLayer = true;
lt.property("Position").setValueAtTime(0, [960, 300, 1600]);
lt.property("Position").setValueAtTime(3, [700, 400, 400]);
lt.property("Light Options").property("Intensity").setValue(450);
return "OK:D4_MultiZ_Parallax";
}catch(e){return "ERR:"+e.toString();}
})();
"""

# ============================================================
# 3. D5_FractalNoise_Morph - REAL fractal noise via matchName
# ============================================================
JSX_D5_FRACTAL = """
(function(){
try{
var comp = app.project.items.addComp("D5_FractalNoise_Morph", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.02, 0.02, 0.04];
var solid = comp.layers.addSolid([0.5,0.5,0.5], "FractalLayer", 1920, 1080, 1);
var fn = solid.Effects.addProperty("ADBE Fractal Noise");
fn.property("ADBE Fractal Noise-0004").setValue(180);
fn.property("ADBE Fractal Noise-0010").setValueAtTime(0, 100);
fn.property("ADBE Fractal Noise-0010").setValueAtTime(1.5, 220);
fn.property("ADBE Fractal Noise-0010").setValueAtTime(3, 70);
fn.property("ADBE Fractal Noise-0023").setValueAtTime(0, 0);
fn.property("ADBE Fractal Noise-0023").setValueAtTime(3, 1080);
fn.property("ADBE Fractal Noise-0013").setValueAtTime(0, [300, 540]);
fn.property("ADBE Fractal Noise-0013").setValueAtTime(3, [1600, 400]);
// Colorize
var tint = solid.Effects.addProperty("ADBE Tint");
tint.property("ADBE Tint-0001").setValue([0.05, 0.0, 0.25, 1]);
tint.property("ADBE Tint-0002").setValue([0.3, 0.95, 1.0, 1]);
return "OK:D5_FractalNoise_Morph";
}catch(e){return "ERR:"+e.toString();}
})();
"""

# ============================================================
# 4. D5_Shatter_Explosion - CC Particle World burst (flat indices)
# ============================================================
JSX_D5_EXPLOSION = """
(function(){
try{
var comp = app.project.items.addComp("D5_Shatter_Explosion", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.03, 0.02, 0.05];
// Animated radial background (shockwave feel)
var bgL = comp.layers.addSolid([0.5,0.5,0.5], "ShockBG", 1920, 1080, 1);
var bgR = bgL.Effects.addProperty("ADBE Ramp");
bgR.property("ADBE Ramp-0005").setValue(2);
bgR.property("ADBE Ramp-0001").setValue([960, 540]);
bgR.property("ADBE Ramp-0002").setValueAtTime(0, [0.5, 0.35, 0.1]);
bgR.property("ADBE Ramp-0002").setValueAtTime(0.5, [0.9, 0.7, 0.3]);
bgR.property("ADBE Ramp-0002").setValueAtTime(1.5, [0.3, 0.15, 0.05]);
bgR.property("ADBE Ramp-0002").setValueAtTime(3, [0.1, 0.05, 0.15]);
bgR.property("ADBE Ramp-0003").setValue([960, 540]);
bgR.property("ADBE Ramp-0004").setValue([0.02, 0.02, 0.04]);
// Particle explosion layer
var pL = comp.layers.addSolid([0,0,0], "Explosion", 1920, 1080, 1);
var pw = pL.Effects.addProperty("CC Particle World");
pw.property(14).setValueAtTime(0, 0);
pw.property(14).setValueAtTime(0.2, 350);
pw.property(14).setValueAtTime(0.6, 0);
pw.property(15).setValue(2.2);
pw.property(17).setValue(0.0);
pw.property(18).setValue(0.4);
pw.property(19).setValue(0.0);
pw.property(25).setValue(2);
pw.property(26).setValue(2.5);
pw.property(28).setValue(0.6);
pw.property(29).setValue(0.4);
pw.property(53).setValue(6);
pw.property(63).setValue(14);
pw.property(64).setValue(2);
pw.property(65).setValue(60);
pw.property(66).setValue(100);
pw.property(70).setValue([1, 0.85, 0.3]);
pw.property(71).setValue([0.7, 0.1, 0.0]);
// Flash layer
var flash = comp.layers.addSolid([1, 0.95, 0.8], "Flash", 1920, 1080, 1);
flash.property("Opacity").setValueAtTime(0, 0);
flash.property("Opacity").setValueAtTime(0.25, 95);
flash.property("Opacity").setValueAtTime(0.9, 0);
var fScl = flash.property("Scale");
fScl.setValueAtTime(0, [30, 30]);
fScl.setValueAtTime(0.9, [160, 160]);
return "OK:D5_Shatter_Explosion";
}catch(e){return "ERR:"+e.toString();}
})();
"""

# ============================================================
# 5. D5_Beam_Energy - 3x Lightning 2 bolts + animated bg
# ============================================================
JSX_D5_BEAM = """
(function(){
try{
var comp = app.project.items.addComp("D5_Beam_Energy", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.02, 0.02, 0.05];
// Animated radial bg
var bgL = comp.layers.addSolid([0.5,0.5,0.5], "EnergyBG", 1920, 1080, 1);
var bgR = bgL.Effects.addProperty("ADBE Ramp");
bgR.property("ADBE Ramp-0005").setValue(2);
bgR.property("ADBE Ramp-0001").setValueAtTime(0, [960, 540]);
bgR.property("ADBE Ramp-0001").setValueAtTime(1.5, [700, 400]);
bgR.property("ADBE Ramp-0001").setValueAtTime(3, [1200, 650]);
bgR.property("ADBE Ramp-0002").setValueAtTime(0, [0.08, 0.05, 0.2]);
bgR.property("ADBE Ramp-0002").setValueAtTime(1.5, [0.2, 0.08, 0.3]);
bgR.property("ADBE Ramp-0002").setValueAtTime(3, [0.05, 0.15, 0.25]);
bgR.property("ADBE Ramp-0003").setValue([960, 540]);
bgR.property("ADBE Ramp-0004").setValue([0.01, 0.01, 0.03]);
// 3 lightning bolts
var boltCols = [[0.4,0.7,1,1],[1,0.4,0.6,1],[0.4,1,0.7,1]];
var starts = [[200,900],[960,1000],[1700,900]];
var ends = [[1600,150],[960,80],[300,150]];
for(var i=0;i<3;i++){
    var bL = comp.layers.addSolid([0,0,0], "Bolt_"+i, 1920, 1080, 1);
    var bolt = bL.Effects.addProperty("ADBE Lightning 2");
    bolt.property("ADBE Lightning 2-0002").setValueAtTime(0, starts[i]);
    bolt.property("ADBE Lightning 2-0002").setValueAtTime(1.5, [starts[i][0]+300-i*300, starts[i][1]-400]);
    bolt.property("ADBE Lightning 2-0002").setValueAtTime(3, [starts[i][0]-200+i*200, starts[i][1]-100]);
    bolt.property("ADBE Lightning 2-0003").setValueAtTime(0, ends[i]);
    bolt.property("ADBE Lightning 2-0003").setValueAtTime(1.5, [ends[i][0]-300+i*300, ends[i][1]+300]);
    bolt.property("ADBE Lightning 2-0003").setValueAtTime(3, [ends[i][0]+200-i*200, ends[i][1]+100]);
    bolt.property("ADBE Lightning 2-0008").setValue(boltCols[i]);
}
// Pulsing center glow
var glow = comp.layers.addSolid([0.5, 0.5, 0.6], "CoreGlow", 500, 500, 1);
glow.property("Position").setValue([960, 540]);
var gScl = glow.property("Scale");
gScl.setValueAtTime(0, [60, 60]);
gScl.setValueAtTime(0.75, [140, 140]);
gScl.setValueAtTime(1.5, [80, 80]);
gScl.setValueAtTime(2.25, [150, 150]);
gScl.setValueAtTime(3, [70, 70]);
glow.property("Opacity").setValue(70);
try{
    var gfx = glow.Effects.addProperty("ADBE Gaussian Blur 2");
    gfx.property("ADBE Gaussian Blur 2-0001").setValue(60);
}catch(e2){}
return "OK:D5_Beam_Energy";
}catch(e){return "ERR:"+e.toString();}
})();
"""

# ============================================================
# 6. D6_Elastic_Bounce - 4 balls + squash + animated bg
# ============================================================
JSX_D6_ELASTIC = """
(function(){
try{
var comp = app.project.items.addComp("D6_Elastic_Bounce", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.08, 0.08, 0.12];
// Animated background
var bgL = comp.layers.addSolid([0.5,0.5,0.5], "BounceBG", 1920, 1080, 1);
var bgR = bgL.Effects.addProperty("ADBE Ramp");
bgR.property("ADBE Ramp-0001").setValue([0, 0]);
bgR.property("ADBE Ramp-0002").setValueAtTime(0, [0.15, 0.08, 0.25]);
bgR.property("ADBE Ramp-0002").setValueAtTime(1.5, [0.08, 0.2, 0.25]);
bgR.property("ADBE Ramp-0002").setValueAtTime(3, [0.25, 0.12, 0.08]);
bgR.property("ADBE Ramp-0003").setValue([1920, 1080]);
bgR.property("ADBE Ramp-0004").setValueAtTime(0, [0.05, 0.1, 0.15]);
bgR.property("ADBE Ramp-0004").setValueAtTime(1.5, [0.15, 0.05, 0.1]);
bgR.property("ADBE Ramp-0004").setValueAtTime(3, [0.05, 0.15, 0.2]);
// Floor with color shift
var floor = comp.layers.addSolid([0.35, 0.35, 0.4], "Floor", 1920, 160, 1);
floor.property("Position").setValue([960, 990]);
// 4 bouncing balls with staggered elastic
var ballCols = [[0.95,0.6,0.1],[0.2,0.85,0.9],[0.9,0.25,0.4],[0.5,0.9,0.3]];
var ballX = [380, 760, 1140, 1520];
var delays = [0, 0.25, 0.5, 0.75];
for(var i=0;i<4;i++){
    var ball = comp.layers.addSolid(ballCols[i], "Ball_"+i, 140, 140, 1);
    var pos = ball.property("Position");
    var d = delays[i];
    pos.setValueAtTime(d, [ballX[i], 150]);
    pos.setValueAtTime(d+0.7, [ballX[i], 850]);
    pos.setValueAtTime(d+1.1, [ballX[i], 500]);
    pos.setValueAtTime(d+1.5, [ballX[i], 850]);
    pos.setValueAtTime(d+1.8, [ballX[i], 700]);
    pos.setValueAtTime(d+2.1, [ballX[i], 850]);
    try{
        pos.expression = "n=0;if(numKeys>0){n=nearestKey(time).index;if(key(n).time>time)n--;}if(n==0){t=0}else{t=time-key(n).time}if(n>0&&t<1.5){v=velocityAtTime(key(n).time-thisComp.frameDuration/10);amp=.05;freq=6;decay=7;value+v*amp*Math.sin(freq*t*2*Math.PI)/Math.exp(decay*t)/freq}else{value}";
    }catch(e2){}
    // Squash on impact
    var scl = ball.property("Scale");
    scl.setValueAtTime(d+0.65, [100, 100]);
    scl.setValueAtTime(d+0.72, [135, 60]);
    scl.setValueAtTime(d+0.85, [90, 115]);
    scl.setValueAtTime(d+1.0, [100, 100]);
    scl.setValueAtTime(d+1.45, [100, 100]);
    scl.setValueAtTime(d+1.52, [130, 65]);
    scl.setValueAtTime(d+1.65, [95, 110]);
    scl.setValueAtTime(d+1.8, [100, 100]);
}
// Title
var txt = comp.layers.addText("ELASTIC");
var doc = txt.property("Source Text").value;
doc.fontSize = 100; doc.fillColor = [1, 1, 1];
doc.justification = ParagraphJustification.CENTER_JUSTIFY;
txt.property("Source Text").setValue(doc);
txt.property("Position").setValue([960, 200]);
var tScl = txt.property("Scale");
tScl.setValueAtTime(0, [0, 0]);
tScl.setValueAtTime(0.4, [115, 115]);
tScl.setValueAtTime(0.6, [95, 95]);
tScl.setValueAtTime(0.8, [100, 100]);
return "OK:D6_Elastic_Bounce";
}catch(e){return "ERR:"+e.toString();}
})();
"""

# ============================================================
# 7. D6_Overshoot_Punch - multi-element overshoot + rotating bg
# ============================================================
JSX_D6_OVERSHOOT = """
(function(){
try{
var comp = app.project.items.addComp("D6_Overshoot_Punch", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.1, 0.08, 0.14];
// Animated bg
var bgL = comp.layers.addSolid([0.5,0.5,0.5], "PunchBG", 1920, 1080, 1);
var bgR = bgL.Effects.addProperty("ADBE Ramp");
bgR.property("ADBE Ramp-0005").setValue(2);
bgR.property("ADBE Ramp-0001").setValue([960, 540]);
bgR.property("ADBE Ramp-0002").setValueAtTime(0, [0.18, 0.1, 0.25]);
bgR.property("ADBE Ramp-0002").setValueAtTime(1.5, [0.25, 0.15, 0.1]);
bgR.property("ADBE Ramp-0002").setValueAtTime(3, [0.1, 0.2, 0.22]);
bgR.property("ADBE Ramp-0003").setValue([960, 540]);
bgR.property("ADBE Ramp-0004").setValue([0.04, 0.03, 0.07]);
// Rotating background star (continuous motion)
var star = comp.layers.addSolid([0.25, 0.2, 0.35], "StarBG", 1400, 1400, 1);
star.property("Position").setValue([960, 540]);
star.property("Opacity").setValue(50);
star.property("Rotation").expression = "time*40";
// Main punch shape with overshoot
var shape = comp.layers.addSolid([0.2, 0.7, 0.9], "PunchShape", 320, 320, 1);
shape.property("Position").setValue([960, 480]);
var scl = shape.property("Scale");
scl.setValueAtTime(0, [0, 0]);
scl.setValueAtTime(0.5, [100, 100]);
try{
    scl.expression = "n=0;if(numKeys>0){n=nearestKey(time).index;if(key(n).time>time)n--;}if(n==0){t=0}else{t=time-key(n).time}if(n>0&&t<2){v=velocityAtTime(key(n).time-thisComp.frameDuration/10);amp=.09;freq=5;decay=4.5;value+v*amp*Math.sin(freq*t*2*Math.PI)/Math.exp(decay*t)/freq}else{value}";
}catch(e2){}
shape.property("Rotation").setValueAtTime(0, -15);
shape.property("Rotation").setValueAtTime(0.5, 0);
// Slide bars with overshoot (3 bars staggered)
var barCols = [[0.9,0.4,0.3],[0.95,0.8,0.2],[0.4,0.9,0.5]];
for(var i=0;i<3;i++){
    var bar = comp.layers.addSolid(barCols[i], "Bar_"+i, 700, 80, 1);
    var bPos = bar.property("Position");
    var st = 0.6 + i*0.3;
    bPos.setValueAtTime(st, [-400, 750+i*90]);
    bPos.setValueAtTime(st+0.5, [960, 750+i*90]);
    try{
        bPos.expression = "n=0;if(numKeys>0){n=nearestKey(time).index;if(key(n).time>time)n--;}if(n==0){t=0}else{t=time-key(n).time}if(n>0&&t<1.5){v=velocityAtTime(key(n).time-thisComp.frameDuration/10);amp=.06;freq=5;decay=5;value+v*amp*Math.sin(freq*t*2*Math.PI)/Math.exp(decay*t)/freq}else{value}";
    }catch(e3){}
}
// Text pop
var txt = comp.layers.addText("POW!");
var doc = txt.property("Source Text").value;
doc.fontSize = 120; doc.fillColor = [1, 0.95, 0.3];
doc.justification = ParagraphJustification.CENTER_JUSTIFY;
txt.property("Source Text").setValue(doc);
txt.property("Position").setValue([960, 480]);
var tScl = txt.property("Scale");
tScl.setValueAtTime(0.9, [0, 0]);
tScl.setValueAtTime(1.3, [120, 120]);
tScl.setValueAtTime(1.5, [95, 95]);
tScl.setValueAtTime(1.7, [100, 100]);
try{
    var glow = txt.Effects.addProperty("ADBE Glo2");
    glow.property("ADBE Glo2-0003").setValue(25);
    glow.property("ADBE Glo2-0004").setValue(0.7);
}catch(e4){}
return "OK:D6_Overshoot_Punch";
}catch(e){return "ERR:"+e.toString();}
})();
"""

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("FIX REBUILD: 7 compositions (size>100KB requirement)")
    print("=" * 60)

    # Phase 0: cleanup
    print("\n[Phase 0] Cleanup old comps...")
    r = send_bridge(JSX_CLEANUP, wait=30, tag="CLEANUP")
    check_result(r, "CLEANUP")
    time.sleep(1)

    # Phase 1: create
    comps = [
        ("D3_Handheld_Shake", JSX_D3_HANDHELD, str(BASE_OUT / "dir1_camera_motion" / "D3_Handheld_Shake.mp4")),
        ("D4_MultiZ_Parallax", JSX_D4_MULTIZ, str(BASE_OUT / "dir1_camera_motion" / "D4_MultiZ_Parallax.mp4")),
        ("D5_FractalNoise_Morph", JSX_D5_FRACTAL, str(BASE_OUT / "dir5_plugin_effects" / "D5_FractalNoise_Morph.mp4")),
        ("D5_Shatter_Explosion", JSX_D5_EXPLOSION, str(BASE_OUT / "dir5_plugin_effects" / "D5_Shatter_Explosion.mp4")),
        ("D5_Beam_Energy", JSX_D5_BEAM, str(BASE_OUT / "dir5_plugin_effects" / "D5_Beam_Energy.mp4")),
        ("D6_Elastic_Bounce", JSX_D6_ELASTIC, str(BASE_OUT / "dir6_expressions" / "D6_Elastic_Bounce.mp4")),
        ("D6_Overshoot_Punch", JSX_D6_OVERSHOOT, str(BASE_OUT / "dir6_expressions" / "D6_Overshoot_Punch.mp4")),
    ]

    print("\n[Phase 1] Create compositions...")
    created = []
    for name, jsx, out in comps:
        r = send_bridge(jsx, wait=45, tag=name)
        if check_result(r, name):
            created.append((name, out))
        time.sleep(1)

    print(f"\n  Created {len(created)}/7")
    if not created:
        print("FATAL: nothing created")
        sys.exit(1)

    # Phase 2: render
    print("\n[Phase 2] Render...")
    rendered = []
    for name, out in created:
        # Remove old file
        for old in glob.glob(out.replace(".mp4", ".*")):
            try: os.remove(old)
            except: pass
        jsx = make_render_jsx(name, out)
        r = send_bridge(jsx, wait=300, tag=f"RENDER_{name}")
        if check_result(r, f"RENDER_{name}"):
            rendered.append((name, out))
        time.sleep(2)

    # Phase 3: verify sizes
    print(f"\n{'='*60}")
    print("VERIFICATION:")
    all_ok = True
    for name, out in rendered:
        p = Path(out)
        if p.exists():
            kb = p.stat().st_size / 1024
            status = "OK" if kb > 100 else "TOO SMALL"
            if kb <= 100: all_ok = False
            print(f"  [{status}] {p.name}: {kb:.0f}KB")
        else:
            all_ok = False
            print(f"  [MISSING] {p.name}")

    print(f"\n{'='*60}")
    print(f"SUMMARY: Created={len(created)}/7, Rendered={len(rendered)}/7, SizeOK={'YES' if all_ok else 'NO'}")
    print("DONE.")
