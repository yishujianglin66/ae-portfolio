"""Quick render test - try different formats"""
import json
import time
from datetime import datetime
from pathlib import Path

BD = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge")
CMD = BD / "ae_command.json"
RES = BD / "ae_result.json"
OUT = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output_production/dir1_camera_motion"

def send(code, wait=60):
    try: RES.unlink(missing_ok=True)
    except: pass
    cmd = {"command":"runScript","args":{"code":code},"timestamp":datetime.now().isoformat(),"status":"pending"}
    CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(0.3)
        try:
            if RES.exists():
                r = json.loads(RES.read_text(encoding="utf-8"))
                if "result" in r: return r
        except: pass
    return None

# Step 1: Check what comps exist
print("=== Checking comps ===")
r = send("""
(function(){
    var names = [];
    for(var i=1;i<=app.project.numItems;i++){
        var it = app.project.item(i);
        if(it instanceof CompItem) names.push(it.name);
    }
    return names.join(", ");
})();
""")
if r:
    data = r.get("result",{}).get("data",{}).get("result","")
    print(f"  Comps: {data[:300]}")

# Step 2: Try render with Lossless template (most reliable)
print("\n=== Render test: D1 with Lossless AVI ===")
jsx = f"""
(function(){{
try{{
    var comp = null;
    for(var i=1;i<=app.project.numItems;i++){{
        var it=app.project.item(i);
        if(it instanceof CompItem && it.name=="D1_DollyZoom_Hitchcock"){{comp=it;break;}}
    }}
    if(!comp) return "ERR:comp not found";
    var rq = app.project.renderQueue.items.add(comp);
    var om = rq.outputModule(1);
    // Use Lossless template
    om.applyTemplate("Lossless");
    om.file = new File("{OUT}/D1_test.avi");
    rq.render();
    rq.remove();
    var f = new File("{OUT}/D1_test.avi");
    return "RENDERED size=" + (f.exists ? f.length : "MISSING");
}}catch(e){{return "ERR:"+e.toString();}}
}})();
"""
r = send(jsx, wait=90)
if r:
    data = r.get("result",{}).get("data",{}).get("result","")
    print(f"  Result: {data}")
else:
    print("  TIMEOUT")

# Step 3: Check output
import os

for f in os.listdir(OUT):
    fp = os.path.join(OUT, f)
    print(f"  FILE: {f} ({os.path.getsize(fp)} bytes)")
