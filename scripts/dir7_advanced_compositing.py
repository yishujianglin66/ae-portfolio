"""Direction 7: Expression Linking + Time Remapping + Track Matte + Blend Modes + Precomp Nesting
All API usage validated via diagnostics:
- Effects: matchName only (ADBE Fractal Noise, ADBE Tint, ADBE Ramp, ADBE Glo2, ADBE Gaussian Blur 2)
- Fractal Noise props: 0004=Contrast, 0010=Scale, 0023=Evolution
- Text: get .value -> modify -> setValue (new TextDocument BROKEN in this AE)
- Masks: build vertex arrays FIRST, assign once (empty array assignment BROKEN)
- 2D layers: Position/Anchor take exactly 2-element arrays
- Ramp: 0001=startPos, 0002=startColor, 0003=endPos, 0004=endColor, 0005=shape(2=radial)
"""
import json, time, sys, os, glob
from pathlib import Path
from datetime import datetime

BRIDGE_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge")
CMD_FILE = BRIDGE_DIR / "ae_command.json"
RES_FILE = BRIDGE_DIR / "ae_result.json"
OUTPUT_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production\dir7_advanced_compositing")
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
        time.sleep(0.5)
        try:
            if RES_FILE.exists():
                r = json.loads(RES_FILE.read_text(encoding="utf-8"))
                if "result" in r:
                    print(f"  [{tag}] Response: {str(r.get('result',''))[:120]}")
                    return r
        except: pass
    print(f"  [{tag}] TIMEOUT after {wait}s")
    return None

def get_result_str(r):
    if not r: return "TIMEOUT"
    res = r.get("result", {})
    if isinstance(res, dict): return str(res.get("data", res))
    return str(res)

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
# COMP 1: Expression Linking - Master controller drives satellites
# ============================================================
JSX_D7_EXPR_LINK = r"""
(function(){
try{
var comp = app.project.items.addComp("D7_ExprLink_OrbitDriver", 1280, 720, 1, 5, 30);
comp.bgColor = [0.08, 0.06, 0.12];

// Background glow
var bgGlow = comp.layers.addSolid([0.15, 0.1, 0.25], "BG_Glow", 1280, 720, 1);
var rad = bgGlow.Effects.addProperty("ADBE Ramp");
rad.property("ADBE Ramp-0001").setValue([640, 360]);
rad.property("ADBE Ramp-0002").setValue([0.28, 0.2, 0.45]);
rad.property("ADBE Ramp-0003").setValue([640, 360]);
rad.property("ADBE Ramp-0004").setValue([0.08, 0.05, 0.14]);

// Master controller null
var master = comp.layers.addNull(5);
master.name = "MASTER_CTRL";
master.property("Position").setValue([640, 360]);
var rot = master.property("Rotation");
rot.setValueAtTime(0, 0);
rot.setValueAtTime(5, 720);

// Orbit rings (build vertex arrays first, assign once)
for(var ring = 0; ring < 3; ring++){
    var rl = comp.layers.addSolid([0.5, 0.45, 0.7], "Ring_" + ring, 1280, 720, 1);
    var rad2 = 180 + ring * 50;
    var vs1 = [], vs2 = [], tg1 = [], tg2 = [];
    var pts = 40;
    for(var p = 0; p <= pts; p++){
        var a = p / pts * Math.PI * 2;
        vs1.push([640 + rad2 * Math.cos(a), 360 + rad2 * 0.6 * Math.sin(a)]);
        vs2.push([640 + (rad2 - 4) * Math.cos(a), 360 + (rad2 - 4) * 0.6 * Math.sin(a)]);
        tg1.push([0, 0]); tg2.push([0, 0]);
    }
    var mask = rl.Masks.addProperty("Mask");
    var shape = new Shape();
    shape.vertices = vs1; shape.inTangents = tg1; shape.outTangents = tg1; shape.closed = true;
    mask.property("Mask Path").setValue(shape);
    mask.maskMode = MaskMode.ADD;
    var mask2 = rl.Masks.addProperty("Mask");
    var shape2 = new Shape();
    shape2.vertices = vs2; shape2.inTangents = tg2; shape2.outTangents = tg2; shape2.closed = true;
    mask2.property("Mask Path").setValue(shape2);
    mask2.maskMode = MaskMode.SUBTRACT;
    rl.property("Opacity").setValue(50);
}

// Central core driven by master rotation
var core = comp.layers.addSolid([1, 0.85, 0.2], "Core", 160, 160, 1);
core.property("Position").setValue([640, 360]);
core.property("Anchor Point").setValue([80, 80]);
core.property("Scale").expression =
  'var r = thisComp.layer("MASTER_CTRL").transform.rotation;\n' +
  'var pulse = 100 + 25 * Math.sin(r * Math.PI / 90);\n' +
  '[pulse, pulse];';
core.property("Rotation").expression = 'thisComp.layer("MASTER_CTRL").transform.rotation * 0.5;';
var coreGlow = core.Effects.addProperty("ADBE Glo2");
coreGlow.property("ADBE Glo2-0002").setValue(20);
coreGlow.property("ADBE Glo2-0003").setValue(40);
coreGlow.property("ADBE Glo2-0004").setValue(1.2);

// 6 satellites: position/opacity/scale all expression-linked to master
var colors = [[1,0.3,0.3],[0.3,1,0.4],[0.3,0.5,1],[1,0.7,0.2],[0.8,0.3,1],[0.2,1,0.9]];
var names = ["Sat_A","Sat_B","Sat_C","Sat_D","Sat_E","Sat_F"];
for(var i = 0; i < 6; i++){
    var sat = comp.layers.addSolid(colors[i], names[i], 60, 60, 1);
    sat.property("Anchor Point").setValue([30, 30]);
    var phase = i * 60;
    var radius = 180 + (i % 3) * 50;
    sat.property("Position").expression =
      'var r = thisComp.layer("MASTER_CTRL").transform.rotation;\n' +
      'var angle = (r + ' + phase + ') * Math.PI / 180;\n' +
      'var rad = ' + radius + ';\n' +
      '[640 + rad * Math.cos(angle), 360 + rad * Math.sin(angle) * 0.6];';
    sat.property("Opacity").expression =
      'var r = thisComp.layer("MASTER_CTRL").transform.rotation;\n' +
      '60 + 40 * Math.abs(Math.sin((r + ' + (i*30) + ') * Math.PI / 180));';
    sat.property("Scale").expression =
      'var r = thisComp.layer("MASTER_CTRL").transform.rotation;\n' +
      'var s = 80 + 40 * Math.sin((r + ' + phase + ') * Math.PI / 180);\n' +
      '[s, s];';
    var satGlow = sat.Effects.addProperty("ADBE Glo2");
    satGlow.property("ADBE Glo2-0002").setValue(15);
    satGlow.property("ADBE Glo2-0003").setValue(15);
}

return "OK:D7_ExprLink_OrbitDriver layers=" + comp.numLayers;
}catch(e){return "ERR:" + e.toString();}
})();
"""

# ============================================================
# COMP 2: Time Remapping - speed ramp + freeze + reverse
# ============================================================
JSX_D7_TIME_REMAP = r"""
(function(){
try{
// Inner precomp: bouncing ball
var inner = app.project.items.addComp("D7_TR_Source", 1280, 720, 1, 5, 30);
inner.bgColor = [0.05, 0.08, 0.12];
var bgFill = inner.layers.addSolid([0.12, 0.16, 0.25], "BG", 1280, 720, 1);

var ball = inner.layers.addSolid([1, 0.6, 0.1], "Ball", 100, 100, 1);
ball.property("Anchor Point").setValue([50, 50]);
var pos = ball.property("Position");
var bounces = [[100,200],[380,550],[640,200],[900,550],[1180,200]];
for(var b = 0; b < bounces.length; b++){
    pos.setValueAtTime(b * 1.25, bounces[b]);
}
var scl = ball.property("Scale");
for(var s = 1; s < 4; s++){
    var t = s * 1.25;
    scl.setValueAtTime(t - 0.08, [100, 100]);
    scl.setValueAtTime(t, [135, 55]);
    scl.setValueAtTime(t + 0.08, [100, 100]);
}
var ballGlow = ball.Effects.addProperty("ADBE Glo2");
ballGlow.property("ADBE Glo2-0002").setValue(15);
ballGlow.property("ADBE Glo2-0003").setValue(25);

var floor = inner.layers.addSolid([0.35, 0.55, 0.75], "Floor", 1280, 10, 1);
floor.property("Position").setValue([640, 555]);

// Main comp with time remapping
var comp = app.project.items.addComp("D7_TimeRemap_SpeedRamp", 1280, 720, 1, 7, 30);
comp.bgColor = [0.04, 0.05, 0.1];

var precompLayer = comp.layers.add(inner);
precompLayer.name = "TR_Precomp";
precompLayer.timeRemapEnabled = true;
var tr = precompLayer.property("ADBE Time Remapping");
// normal -> slow-mo -> freeze -> reverse -> fast (values within 0~4.9)
tr.setValueAtTime(0, 0);
tr.setValueAtTime(1.5, 1.5);
tr.setValueAtTime(4.0, 2.5);
tr.setValueAtTime(5.0, 2.5);
tr.setValueAtTime(6.0, 1.0);
tr.setValueAtTime(6.8, 4.9);

// HUD text (via .value approach)
var hud = comp.layers.addText("TR");
var hDoc = hud.property("Source Text").value;
hDoc.fontSize = 42;
hDoc.fillColor = [0.9, 0.9, 1.0];
hDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
hud.property("Source Text").setValue(hDoc);
hud.property("Position").setValue([640, 80]);
hud.property("Opacity").expression = '60 + 30 * Math.sin(time * 4);';

// Progress bar driven by time remap value (expression linking)
var bar = comp.layers.addSolid([0.2, 0.9, 0.5], "ProgressBar", 1000, 14, 1);
bar.property("Anchor Point").setValue([0, 7]);
bar.property("Position").setValue([140, 670]);
bar.property("Scale").expression =
  'var srcTime = thisComp.layer("TR_Precomp").timeRemap;\n' +
  'var pct = srcTime / 5 * 100;\n' +
  '[Math.max(2, pct), 100];';

return "OK:D7_TimeRemap_SpeedRamp layers=" + comp.numLayers;
}catch(e){return "ERR:" + e.toString();}
})();
"""

# ============================================================
# COMP 3: Track Matte - luma wipe + alpha spotlight
# ============================================================
JSX_D7_TRACK_MATTE = r"""
(function(){
try{
var comp = app.project.items.addComp("D7_TrackMatte_Reveal", 1280, 720, 1, 5, 30);
comp.bgColor = [0.06, 0.04, 0.1];

// Background gradient
var bg = comp.layers.addSolid([0.12, 0.08, 0.2], "BG", 1280, 720, 1);
var ramp = bg.Effects.addProperty("ADBE Ramp");
ramp.property("ADBE Ramp-0001").setValue([640, 0]);
ramp.property("ADBE Ramp-0002").setValue([0.22, 0.14, 0.38]);
ramp.property("ADBE Ramp-0003").setValue([640, 720]);
ramp.property("ADBE Ramp-0004").setValue([0.08, 0.05, 0.14]);

// === Luma matte: radial wipe revealing title ===
var wipeMatte = comp.layers.addSolid([0, 0, 0], "WipeMatte", 1280, 720, 1);
var wipeRamp = wipeMatte.Effects.addProperty("ADBE Ramp");
wipeRamp.property("ADBE Ramp-0005").setValue(2);
wipeRamp.property("ADBE Ramp-0001").setValueAtTime(0, [-300, 360]);
wipeRamp.property("ADBE Ramp-0001").setValueAtTime(2.5, [1580, 360]);
wipeRamp.property("ADBE Ramp-0002").setValue([1, 1, 1]);
wipeRamp.property("ADBE Ramp-0003").setValue([640, 360]);
wipeRamp.property("ADBE Ramp-0004").setValue([0, 0, 0]);

var titleText = comp.layers.addText("MATTE");
var tDoc = titleText.property("Source Text").value;
tDoc.fontSize = 130;
tDoc.fillColor = [1, 0.85, 0.3];
tDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
titleText.property("Source Text").setValue(tDoc);
titleText.property("Position").setValue([640, 320]);
titleText.setTrackMatte(wipeMatte, TrackMatteType.LUMA);
wipeMatte.enabled = false;

// === Alpha matte: moving spotlight reveals animated pattern ===
var spotMatte = comp.layers.addSolid([1, 1, 1], "SpotMatte", 1280, 720, 1);
var spotMask = spotMatte.Masks.addProperty("Mask");
var svs = [], sts = [];
for(var sp = 0; sp <= 24; sp++){
    var sa = sp / 24 * Math.PI * 2;
    svs.push([640 + 220 * Math.cos(sa), 360 + 130 * Math.sin(sa)]);
    sts.push([0, 0]);
}
var spotShape = new Shape();
spotShape.vertices = svs; spotShape.inTangents = sts; spotShape.outTangents = sts; spotShape.closed = true;
spotMask.property("Mask Path").setValue(spotShape);
spotMask.property("Mask Feather").setValue([60, 60]);
spotMatte.property("Position").expression =
  'var x = 400 * Math.sin(time * 1.8);\n' +
  'var y = 60 * Math.cos(time * 2.5);\n' +
  '[x, y];';

// Pattern layer: animated fractal noise, tinted, revealed by spotlight
var pattern = comp.layers.addSolid([0.9, 0.2, 0.4], "PatternLayer", 1280, 720, 1);
var fn = pattern.Effects.addProperty("ADBE Fractal Noise");
fn.property("ADBE Fractal Noise-0010").setValue(50);
fn.property("ADBE Fractal Noise-0004").setValue(250);
fn.property("ADBE Fractal Noise-0005").setValue(-10);
fn.property("ADBE Fractal Noise-0023").expression = 'time * 200;';
var patTint = pattern.Effects.addProperty("ADBE Tint");
patTint.property("ADBE Tint-0001").setValue([0.0, 0.05, 0.1, 1]);
patTint.property("ADBE Tint-0002").setValue([0.3, 1.0, 0.8, 1]);
pattern.setTrackMatte(spotMatte, TrackMatteType.ALPHA);
spotMatte.enabled = false;

// Subtitle
var sub = comp.layers.addText("sub");
var subDoc = sub.property("Source Text").value;
subDoc.fontSize = 36;
subDoc.fillColor = [0.85, 0.85, 0.95];
subDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
sub.property("Source Text").setValue(subDoc);
sub.property("Position").setValue([640, 660]);

return "OK:D7_TrackMatte_Reveal layers=" + comp.numLayers;
}catch(e){return "ERR:" + e.toString();}
})();
"""

# ============================================================
# COMP 4: Blend Modes - additive orbs, screen streaks, multiply
# shadow, overlay noise, difference text
# ============================================================
JSX_D7_BLEND_MODES = r"""
(function(){
try{
var comp = app.project.items.addComp("D7_BlendModes_LightMix", 1280, 720, 1, 5, 30);
comp.bgColor = [0.1, 0.08, 0.06];

// Base gradient
var base = comp.layers.addSolid([0.15, 0.12, 0.1], "Base", 1280, 720, 1);
var ramp = base.Effects.addProperty("ADBE Ramp");
ramp.property("ADBE Ramp-0001").setValue([640, 720]);
ramp.property("ADBE Ramp-0002").setValue([0.3, 0.22, 0.15]);
ramp.property("ADBE Ramp-0003").setValue([640, 0]);
ramp.property("ADBE Ramp-0004").setValue([0.1, 0.08, 0.18]);

// ADD: 3 orbiting glow orbs (additive color mixing where they overlap)
var orbColors = [[1, 0.4, 0.1], [0.1, 0.8, 1], [0.9, 0.2, 0.9]];
var orbNames = ["Orb_Add_R", "Orb_Add_G", "Orb_Add_B"];
for(var i = 0; i < 3; i++){
    var orb = comp.layers.addSolid(orbColors[i], orbNames[i], 320, 320, 1);
    orb.blendingMode = BlendingMode.ADD;
    orb.property("Anchor Point").setValue([160, 160]);
    var phase = i * 120;
    orb.property("Position").expression =
      'var a = (time * 90 + ' + phase + ') * Math.PI / 180;\n' +
      '[640 + 280 * Math.cos(a), 360 + 160 * Math.sin(a)];';
    var blur = orb.Effects.addProperty("ADBE Gaussian Blur 2");
    blur.property("ADBE Gaussian Blur 2-0001").setValue(60);
    orb.property("Opacity").setValue(75);
}

// SCREEN: rising light streaks
for(var s = 0; s < 4; s++){
    var streak = comp.layers.addSolid([0.35, 0.3, 0.18], "Streak_" + s, 10, 420, 1);
    streak.blendingMode = BlendingMode.SCREEN;
    streak.property("Rotation").setValue(-15 + s * 10);
    var sBlur = streak.Effects.addProperty("ADBE Gaussian Blur 2");
    sBlur.property("ADBE Gaussian Blur 2-0001").setValue(12);
    streak.property("Opacity").expression = '35 + 30 * Math.sin(time * 3 + ' + s + ');';
    streak.property("Position").expression =
      'var y = 820 - ((time * 80 + ' + (s * 220) + ') % 1000);\n' +
      '[' + (200 + s * 280) + ', y];';
}

// MULTIPLY: drifting shadow for depth
var shadow1 = comp.layers.addSolid([0.6, 0.55, 0.5], "Shadow_M", 500, 500, 1);
shadow1.blendingMode = BlendingMode.MULTIPLY;
shadow1.property("Anchor Point").setValue([250, 250]);
shadow1.property("Position").expression = '[640 + 300 * Math.sin(time * 0.7), 360];';
shadow1.property("Rotation").setValue(45);
var shBlur = shadow1.Effects.addProperty("ADBE Gaussian Blur 2");
shBlur.property("ADBE Gaussian Blur 2-0001").setValue(80);

// OVERLAY: animated noise texture for contrast
var overlayL = comp.layers.addSolid([0.5, 0.5, 0.5], "Overlay_Tex", 1280, 720, 1);
overlayL.blendingMode = BlendingMode.OVERLAY;
var noise = overlayL.Effects.addProperty("ADBE Fractal Noise");
noise.property("ADBE Fractal Noise-0002").setValue(3);
noise.property("ADBE Fractal Noise-0010").setValue(250);
noise.property("ADBE Fractal Noise-0023").expression = 'time * 40;';
overlayL.property("Opacity").setValue(40);

// DIFFERENCE: text that inverts colors beneath it
var txt = comp.layers.addText("blend");
var bDoc = txt.property("Source Text").value;
bDoc.fontSize = 95;
bDoc.fillColor = [0.75, 0.75, 0.75];
bDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
txt.property("Source Text").setValue(bDoc);
txt.property("Position").setValue([640, 390]);
txt.blendingMode = BlendingMode.DIFFERENCE;

return "OK:D7_BlendModes_LightMix layers=" + comp.numLayers;
}catch(e){return "ERR:" + e.toString();}
})();
"""

# ============================================================
# COMP 5: Precomp Nesting + Parenting Chain
# ============================================================
JSX_D7_PRECOMP_NEST = r"""
(function(){
try{
// Level 3: spinning gear
var gear = app.project.items.addComp("D7_Nest_Gear", 200, 200, 1, 5, 30);
gear.bgColor = [0, 0, 0];
var gearSolid = gear.layers.addSolid([1, 0.75, 0.2], "GearBody", 160, 160, 1);
gearSolid.property("Position").setValue([100, 100]);
gearSolid.property("Anchor Point").setValue([80, 80]);
gearSolid.property("Rotation").expression = 'time * 180;';
for(var t = 0; t < 8; t++){
    var tooth = gear.layers.addSolid([1, 0.75, 0.2], "Tooth_" + t, 30, 50, 1);
    tooth.property("Anchor Point").setValue([15, 25]);
    var ang = t * 45 * Math.PI / 180;
    tooth.property("Position").setValue([100 + 90 * Math.cos(ang), 100 + 90 * Math.sin(ang)]);
    tooth.property("Rotation").setValue(t * 45);
    tooth.parent = gearSolid;
}
var gearGlow = gearSolid.Effects.addProperty("ADBE Glo2");
gearGlow.property("ADBE Glo2-0002").setValue(15);
gearGlow.property("ADBE Glo2-0003").setValue(12);

// Level 2: arm assembly
var arm = app.project.items.addComp("D7_Nest_Arm", 600, 400, 1, 5, 30);
arm.bgColor = [0, 0, 0];
var armBar = arm.layers.addSolid([0.5, 0.6, 0.85], "ArmBar", 400, 26, 1);
armBar.property("Position").setValue([300, 200]);
armBar.property("Anchor Point").setValue([50, 13]);
armBar.property("Rotation").expression = '30 * Math.sin(time * 2);';
var g1 = arm.layers.add(gear);
g1.name = "Gear1";
g1.property("Position").setValue([480, 200]);
g1.parent = armBar;
var g2 = arm.layers.add(gear);
g2.name = "Gear2";
g2.property("Position").setValue([140, 200]);
g2.property("Scale").setValue([70, 70]);
g2.parent = armBar;
var hub = arm.layers.addSolid([0.95, 0.45, 0.3], "Hub", 55, 55, 1);
hub.property("Position").setValue([100, 200]);
hub.property("Anchor Point").setValue([27, 27]);
var hubGlow = hub.Effects.addProperty("ADBE Glo2");
hubGlow.property("ADBE Glo2-0002").setValue(12);
hubGlow.property("ADBE Glo2-0003").setValue(15);

// Main comp
var comp = app.project.items.addComp("D7_PrecompNest_Machine", 1280, 720, 1, 5, 30);
comp.bgColor = [0.06, 0.08, 0.1];

var gridBg = comp.layers.addSolid([0.12, 0.15, 0.2], "GridBG", 1280, 720, 1);
var gridRamp = gridBg.Effects.addProperty("ADBE Ramp");
gridRamp.property("ADBE Ramp-0001").setValue([640, 0]);
gridRamp.property("ADBE Ramp-0002").setValue([0.16, 0.22, 0.32]);
gridRamp.property("ADBE Ramp-0003").setValue([640, 720]);
gridRamp.property("ADBE Ramp-0004").setValue([0.07, 0.09, 0.15]);

// Master null drives everything via parenting + expressions
var masterNull = comp.layers.addNull(5);
masterNull.name = "Machine_Master";
masterNull.property("Position").expression =
  '[640 + 100 * Math.sin(time * 0.8), 360 + 50 * Math.cos(time * 1.2)];';
masterNull.property("Scale").expression =
  'var s = 100 + 15 * Math.sin(time * 2);\n[s, s];';

var arm1 = comp.layers.add(arm);
arm1.name = "ArmAssembly_1";
arm1.property("Position").setValue([640, 300]);
arm1.parent = masterNull;
var arm2 = comp.layers.add(arm);
arm2.name = "ArmAssembly_2";
arm2.property("Position").setValue([640, 480]);
arm2.property("Scale").setValue([80, 80]);
arm2.property("Rotation").setValue(180);
arm2.parent = masterNull;

var mainGear = comp.layers.add(gear);
mainGear.name = "MainGear";
mainGear.property("Position").setValue([640, 360]);
mainGear.property("Scale").setValue([150, 150]);
mainGear.parent = masterNull;

// Energy ring linked to master scale via expression
var ring = comp.layers.addSolid([0.3, 0.8, 1], "EnergyRing", 1280, 720, 1);
ring.blendingMode = BlendingMode.ADD;
var rvs = [], rts = [];
for(var rp = 0; rp <= 30; rp++){
    var ra = rp / 30 * Math.PI * 2;
    rvs.push([640 + 260 * Math.cos(ra), 360 + 180 * Math.sin(ra)]);
    rts.push([0, 0]);
}
var ringMask = ring.Masks.addProperty("Mask");
var ringShape = new Shape();
ringShape.vertices = rvs; ringShape.inTangents = rts; ringShape.outTangents = rts; ringShape.closed = true;
ringMask.property("Mask Path").setValue(ringShape);
ringMask.property("Mask Feather").setValue([35, 35]);
ring.property("Opacity").expression =
  'var s = thisComp.layer("Machine_Master").transform.scale[0];\n' +
  'Math.max(0, (s - 85) * 4);';
var ringBlur = ring.Effects.addProperty("ADBE Gaussian Blur 2");
ringBlur.property("ADBE Gaussian Blur 2-0001").setValue(10);

// HUD
var hud = comp.layers.addText("hud");
var hDoc = hud.property("Source Text").value;
hDoc.fontSize = 34;
hDoc.fillColor = [0.8, 0.9, 1.0];
hDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
hud.property("Source Text").setValue(hDoc);
hud.property("Position").setValue([640, 60]);

return "OK:D7_PrecompNest_Machine layers=" + comp.numLayers;
}catch(e){return "ERR:" + e.toString();}
})();
"""

# ============================================================
COMPS = [
    ("D7_ExprLink_OrbitDriver", JSX_D7_EXPR_LINK, "ExprLink"),
    ("D7_TimeRemap_SpeedRamp", JSX_D7_TIME_REMAP, "TimeRemap"),
    ("D7_TrackMatte_Reveal", JSX_D7_TRACK_MATTE, "TrackMatte"),
    ("D7_BlendModes_LightMix", JSX_D7_BLEND_MODES, "BlendModes"),
    ("D7_PrecompNest_Machine", JSX_D7_PRECOMP_NEST, "PrecompNest"),
]

def main():
    print("=" * 60)
    print("DIRECTION 7: Expression Linking + Time Remap + Track Matte")
    print("             + Blend Modes + Precomp Nesting")
    print("=" * 60)

    # Phase 0: Cleanup old D7 comps
    print("\n--- Phase 0: Cleanup old D7_* comps ---")
    cleanup_jsx = r"""
(function(){
var removed = 0;
for(var i = app.project.numItems; i >= 1; i--){
    var item = app.project.item(i);
    if(item instanceof CompItem && item.name.indexOf("D7_") === 0){
        item.remove();
        removed++;
    }
}
return "OK:removed " + removed + " old D7 comps";
})();
"""
    r = send_bridge(cleanup_jsx, wait=30, tag="CLEANUP")
    print(f"  {get_result_str(r)}")
    time.sleep(1)

    # Phase 1: Create all comps
    print("\n--- Phase 1: Creating compositions ---")
    create_ok = 0
    for comp_name, jsx, tag in COMPS:
        r = send_bridge(jsx, wait=60, tag=f"CREATE_{tag}")
        result = get_result_str(r)
        if "ERR" in result or result == "TIMEOUT":
            print(f"  !! {comp_name} FAILED: {result}")
        else:
            create_ok += 1
        time.sleep(1)
    print(f"\n  Created: {create_ok}/5")
    if create_ok < 5:
        print("  !! Some comps failed creation - aborting render phase")
        return

    # Phase 2: Render all comps
    print("\n--- Phase 2: Rendering ---")
    for comp_name, jsx, tag in COMPS:
        out_file = str(OUTPUT_DIR / f"{comp_name}.mp4")
        base = out_file.replace(".mp4", ".*")
        for old in glob.glob(base):
            try: os.remove(old)
            except: pass
        r = send_bridge(make_render_jsx(comp_name, out_file), wait=300, tag=f"RENDER_{tag}")
        result = get_result_str(r)
        print(f"  {comp_name}: {result[:100]}")
        time.sleep(2)

    # Phase 3: Verify files
    print("\n--- Phase 3: File verification ---")
    all_pass = True
    for comp_name, jsx, tag in COMPS:
        out_file = OUTPUT_DIR / f"{comp_name}.mp4"
        if out_file.exists():
            size_kb = out_file.stat().st_size / 1024
            status = "OK" if size_kb > 100 else "SMALL"
            print(f"  [{status}] {comp_name}.mp4: {size_kb:.0f} KB")
            if size_kb <= 100: all_pass = False
        else:
            print(f"  [MISSING] {comp_name}.mp4")
            all_pass = False

    print("\n" + "=" * 60)
    print("ALL 5 COMPS RENDERED" if all_pass else "SOME COMPS FAILED - check above")
    print("=" * 60)

if __name__ == "__main__":
    main()
