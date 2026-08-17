"""Direction 6: Keyframe Motion Curves + Expression-Driven Animation
Elastic, overshoot, wiggle, loopOut, sine wave expressions.
"""
import json, time, sys, os, glob
from pathlib import Path
from datetime import datetime

BRIDGE_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge")
CMD_FILE = BRIDGE_DIR / "ae_command.json"
RES_FILE = BRIDGE_DIR / "ae_result.json"
OUTPUT_DIR = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production\dir6_expressions")
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
# JSX COMPOSITIONS - Expression Driven
# ============================================================

JSX_WIGGLE = """
(function(){
try{
var comp = app.project.items.addComp("D6_Wiggle_Organic", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.12, 0.12, 0.16];
var colors = [[0.9,0.3,0.3],[0.3,0.8,0.9],[0.9,0.8,0.2],[0.4,0.9,0.4]];
var positions = [[480,300],[1440,300],[480,780],[1440,780]];
for(var i=0;i<4;i++){
    var el = comp.layers.addSolid(colors[i], "Wiggle_"+i, 200, 200, 1);
    el.property("Position").setValue(positions[i]);
    try{
        el.property("Position").expression = "wiggle(" + (1+i) + ", " + (40+i*30) + ")";
        el.property("Rotation").expression = "wiggle(" + (2+i) + ", 15)";
        el.property("Scale").expression = "wiggle(" + (1+i) + ", 10) + [90,90]";
    }catch(e2){}
}
return "OK:Wiggle 4 objects";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_ELASTIC_BOUNCE = """
(function(){
try{
var comp = app.project.items.addComp("D6_Elastic_Bounce", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.1, 0.1, 0.14];
// Floor
var floor = comp.layers.addSolid([0.3, 0.3, 0.35], "Floor", 1920, 150, 1);
floor.property("Position").setValue([960, 1000]);
// Bouncing ball with elastic expression
var ball = comp.layers.addSolid([0.95, 0.6, 0.1], "Ball", 150, 150, 1);
var pos = ball.property("Position");
pos.setValueAtTime(0, [960, 200]);
pos.setValueAtTime(1.0, [960, 850]);
// Elastic bounce expression
try{
    pos.expression = "n=0;if(numKeys>0){n=nearestKey(time).index;if(key(n).time>time)n--;}if(n==0){t=0}else{t=time-key(n).time}if(n>0&&t<2){v=velocityAtTime(key(n).time-thisComp.frameDuration/10);amp=.06;freq=5;decay=6;value+v*amp*Math.sin(freq*t*2*Math.PI)/Math.exp(decay*t)/freq}else{value}";
}catch(e2){}
return "OK:Elastic bounce";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_OVERSHOOT = """
(function(){
try{
var comp = app.project.items.addComp("D6_Overshoot_Punch", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.12, 0.1, 0.14];
// Punch-in shape with overshoot on scale
var shape = comp.layers.addSolid([0.2, 0.7, 0.9], "PunchShape", 300, 300, 1);
shape.property("Position").setValue([960, 540]);
var scl = shape.property("Scale");
scl.setValueAtTime(0, [0, 0]);
scl.setValueAtTime(0.6, [100, 100]);
// Overshoot expression
try{
    scl.expression = "n=0;if(numKeys>0){n=nearestKey(time).index;if(key(n).time>time)n--;}if(n==0){t=0}else{t=time-key(n).time}if(n>0&&t<1.5){v=velocityAtTime(key(n).time-thisComp.frameDuration/10);amp=.08;freq=6;decay=5;value+v*amp*Math.sin(freq*t*2*Math.PI)/Math.exp(decay*t)/freq}else{value}";
}catch(e2){}
// Second element sliding in with overshoot
var bar = comp.layers.addSolid([0.9, 0.4, 0.3], "SlideBar", 600, 100, 1);
var bPos = bar.property("Position");
bPos.setValueAtTime(0.8, [-300, 800]);
bPos.setValueAtTime(1.4, [960, 800]);
try{
    bPos.expression = "n=0;if(numKeys>0){n=nearestKey(time).index;if(key(n).time>time)n--;}if(n==0){t=0}else{t=time-key(n).time}if(n>0&&t<1.5){v=velocityAtTime(key(n).time-thisComp.frameDuration/10);amp=.05;freq=5;decay=6;value+v*amp*Math.sin(freq*t*2*Math.PI)/Math.exp(decay*t)/freq}else{value}";
}catch(e3){}
return "OK:Overshoot punch";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_LOOPOUT = """
(function(){
try{
var comp = app.project.items.addComp("D6_LoopOut_Cycle", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.1, 0.12, 0.15];
// Rotating fan blades with loopOut
var hub = comp.layers.addSolid([0.8, 0.8, 0.85], "Hub", 100, 100, 1);
hub.property("Position").setValue([960, 540]);
for(var i=0;i<4;i++){
    var blade = comp.layers.addSolid([0.3+i*0.15, 0.5, 0.8-i*0.1], "Blade_"+i, 60, 350, 1);
    blade.property("Position").setValue([960, 400]);
    blade.property("Anchor Point").setValue([30, 175]);
    var rot = blade.property("Rotation");
    rot.setValueAtTime(0, i*90);
    rot.setValueAtTime(0.5, i*90 + 180);
    try{
        rot.expression = "loopOut('cycle')";
    }catch(e2){}
}
// Orbiting satellite with loopOut
var sat = comp.layers.addSolid([0.95, 0.8, 0.2], "Satellite", 60, 60, 1);
var satNull = comp.layers.addNull();
satNull.name = "OrbitNull";
satNull.property("Position").setValue([960, 540]);
sat.parent = satNull;
sat.property("Position").setValue([400, 0]);
var nRot = satNull.property("Rotation");
nRot.setValueAtTime(0, 0);
nRot.setValueAtTime(1, 360);
try{
    nRot.expression = "loopOut('cycle')";
}catch(e3){}
return "OK:LoopOut fan+orbit";
}catch(e){return "ERR:"+e.toString();}
})();
"""

JSX_SINE_WAVE = """
(function(){
try{
var comp = app.project.items.addComp("D6_SineWave_March", 1920, 1080, 1, 3, 30);
comp.bgColor = [0.08, 0.1, 0.12];
// Row of objects oscillating with phase-offset sine expressions
for(var i=0;i<8;i++){
    var hue = i / 8.0;
    var r = Math.abs(Math.sin(hue * 6.28)) * 0.6 + 0.3;
    var g = Math.abs(Math.sin(hue * 6.28 + 2.09)) * 0.6 + 0.3;
    var b = Math.abs(Math.sin(hue * 6.28 + 4.18)) * 0.6 + 0.3;
    var el = comp.layers.addSolid([r, g, b], "Wave_"+i, 120, 120, 1);
    el.property("Position").setValue([240 + i*210, 540]);
    try{
        el.property("Position").expression = "value + [0, Math.sin(time*4 + " + (i*0.6) + ")*180]";
        el.property("Scale").expression = "[100,100] + [Math.sin(time*4 + " + (i*0.6) + ")*20, Math.sin(time*4 + " + (i*0.6) + ")*20]";
    }catch(e2){}
}
return "OK:SineWave 8 objects";
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
    print("DIRECTION 6: Motion Curves + Expression-Driven Animation")
    print("=" * 60)

    comps = [
        ("Wiggle", JSX_WIGGLE),
        ("ElasticBounce", JSX_ELASTIC_BOUNCE),
        ("Overshoot", JSX_OVERSHOOT),
        ("LoopOut", JSX_LOOPOUT),
        ("SineWave", JSX_SINE_WAVE),
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
        "Wiggle": "D6_Wiggle_Organic",
        "ElasticBounce": "D6_Elastic_Bounce",
        "Overshoot": "D6_Overshoot_Punch",
        "LoopOut": "D6_LoopOut_Cycle",
        "SineWave": "D6_SineWave_March",
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
