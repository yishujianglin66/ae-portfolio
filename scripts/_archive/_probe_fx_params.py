"""_probe_fx_params.py — 四大插件参数布局探测（独立文件输出, 绕开 ae_result 竞态）"""
import json
import os
import time
import uuid
from pathlib import Path

bd = Path(__file__).resolve().parent.parent / ".ae-mcp-bridge"
cmd_id = str(uuid.uuid4())[:8]
out_file = bd / f"_fxparams_{cmd_id}.txt"
of_js = str(out_file).replace(chr(92), "/")

code = (
    "(function(){"
    "  try {"
    "    var comp = app.project.items.addComp('FxP4', 100, 100, 1, 1, 30);"
    "    var L = comp.layers.addSolid([1,0,0], 'p', 100, 100, 1.0, 1);"
    "    var targets = [['tc Particular','PART', 42], ['S_Glow','SGL', 18], ['S_Shake','SHK', 14], ['GUTS BadTV','BTV', 14]];"
    "    var out = [];"
    "    for (var t = 0; t < targets.length; t++) {"
    "      var fx;"
    "      try { fx = L.property('ADBE Effect Parade').addProperty(targets[t][0]); } catch(e) { out.push(targets[t][1] + '=ADDFAIL'); continue; }"
    "      var lim = Math.min(fx.numProperties, targets[t][2]);"
    "      out.push(targets[t][1] + '=total' + fx.numProperties);"
    "      for (var j = 1; j <= lim; j++) out.push(targets[t][1] + '.' + j + ':' + fx.property(j).name);"
    "    }"
    "    comp.remove();"
    "    var f = new File('" + of_js + "');"
    "    f.encoding = 'UTF-8';"
    "    if (f.open('w')) { f.write(out.join('\\n')); f.close(); return 'WRITTEN'; }"
    "    return 'OPENFAIL';"
    "  } catch(e) { return 'ERR:' + String(e); }"
    "})();"
)

cmd = {"id": cmd_id, "command": "runScript", "args": {"code": code}, "timestamp": time.time()}
tmp = bd / f"ae_command_{cmd_id}.tmp"
tmp.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
for _ in range(6):
    try:
        os.replace(str(tmp), str(bd / "ae_command.json"))
        break
    except PermissionError:
        time.sleep(2)

for i in range(12):
    time.sleep(6)
    if out_file.exists() and out_file.stat().st_size > 0:
        print(out_file.read_text(encoding="utf-8"))
        break
else:
    print("TIMEOUT")
