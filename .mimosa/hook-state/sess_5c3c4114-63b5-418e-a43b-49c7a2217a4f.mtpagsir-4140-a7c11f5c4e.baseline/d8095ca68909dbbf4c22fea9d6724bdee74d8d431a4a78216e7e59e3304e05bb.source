"""_probe_part_deep.py — Particular 深层参数探测 v2（jsx 文件通道, 免拼接转义）"""
import json, time, uuid, os
from pathlib import Path

bd = Path(__file__).resolve().parent.parent / ".ae-mcp-bridge"
cmd_id = str(uuid.uuid4())[:8]
out_file = bd / f"_partdeep_{cmd_id}.txt"
of_js = str(out_file).replace(chr(92), "/")

jsx = """(function(){
  try {
    var comp = app.project.items.addComp('PD2', 100, 100, 1, 1, 30);
    var L = comp.layers.addSolid([1,0,0], 'p', 100, 100, 1.0, 1);
    var fx = L.property('ADBE Effect Parade').addProperty('tc Particular');
    var out = [];
    for (var j = 43; j <= 280; j++) {
      try {
        var p = fx.property(j);
        if (p && p.name) out.push(j + ':' + p.name);
      } catch(e) {}
    }
    comp.remove();
    var f = new File('OUTPATH');
    f.encoding = 'UTF-8';
    if (f.open('w')) { f.write(out.join('\\n')); f.close(); return 'W' + out.length; }
    return 'OPENFAIL';
  } catch(e) { return 'ERR:' + String(e); }
})();""".replace("OUTPATH", of_js)

jsx_file = bd / f"_probe_{cmd_id}.jsx"
jsx_file.write_text(jsx, encoding="utf-8")
cmd = {"id": cmd_id, "command": "runScript", "args": {"file": str(jsx_file)}, "timestamp": time.time()}
tmp = bd / f"ae_command_{cmd_id}.tmp"
tmp.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
for _ in range(6):
    try:
        os.replace(str(tmp), str(bd / "ae_command.json")); break
    except PermissionError:
        time.sleep(2)

for i in range(15):
    time.sleep(6)
    if out_file.exists() and out_file.stat().st_size > 0:
        print(out_file.read_text(encoding="utf-8")); break
else:
    print("TIMEOUT")
