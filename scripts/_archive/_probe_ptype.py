"""探测粒子类型参数(96/97)合法枚举值 + 属性名"""
import json, time, uuid, os
from pathlib import Path
bd = Path(__file__).resolve().parent.parent / ".ae-mcp-bridge"
cmd_id = str(uuid.uuid4())[:8]
out_file = bd / f"_pty_{cmd_id}.txt"
of_js = str(out_file).replace(chr(92), "/")
lines = [
    "(function(){",
    "  try {",
    "    var comp = app.project.items.addComp('PT', 100, 100, 1, 2, 30);",
    "    var L = comp.layers.addSolid([1,0,0], 'p', 100, 100, 1.0, 2);",
    "    var fx = L.property('ADBE Effect Parade').addProperty('tc Particular');",
    "    var out = [];",
    "    var p96 = fx.property(96);",
    "    var p97 = fx.property(97);",
    "    out.push('p96name=' + p96.name + ' val=' + p96.value);",
    "    out.push('p97name=' + p97.name + ' val=' + p97.value);",
    "    for (var v = 0; v <= 18; v++) {",
    "      try { p97.setValue(v); out.push('p97=' + v + ':OK->' + p97.value); } catch(e) { out.push('p97=' + v + ':no'); }",
    "    }",
    "    comp.remove();",
    "    var f = new File('" + of_js + "');",
    "    f.encoding = 'UTF-8';",
    r"    if (f.open('w')) { f.write(out.join('\n')); f.close(); return 'W'; }",
    "    return 'OPENFAIL';",
    "  } catch(e) { return 'ERR:' + String(e); }",
    "})();",
]
jsx_file = bd / f"_pty_{cmd_id}.jsx"
jsx_file.write_text("\n".join(lines), encoding="utf-8")
cmd = {"id": cmd_id, "command": "runScript", "args": {"file": str(jsx_file)}, "timestamp": time.time()}
tmp = bd / f"ae_command_{cmd_id}.tmp"
tmp.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
for _ in range(6):
    try: os.replace(str(tmp), str(bd / "ae_command.json")); break
    except PermissionError: time.sleep(2)
for i in range(15):
    time.sleep(6)
    if out_file.exists() and out_file.stat().st_size > 0:
        print(out_file.read_text(encoding="utf-8")); break
else: print("TIMEOUT")
