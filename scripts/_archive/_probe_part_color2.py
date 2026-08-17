"""探测 Particular 颜色/辉光参数区段（上色/颜色填充在107-108附近, 探测96-130 + 辉光区段）"""
import json, time, uuid, os
from pathlib import Path
bd = Path(__file__).resolve().parent.parent / ".ae-mcp-bridge"
cmd_id = str(uuid.uuid4())[:8]
out_file = bd / f"_pclr_{cmd_id}.txt"
of_js = str(out_file).replace(chr(92), "/")
lines = [
    "(function(){",
    "  try {",
    "    var comp = app.project.items.addComp('PCLR', 100, 100, 1, 1, 30);",
    "    var L = comp.layers.addSolid([0,0,0], 'p', 100, 100, 1.0, 1);",
    "    var fx = L.property('ADBE Effect Parade').addProperty('tc Particular');",
    "    var out = [];",
    "    for (var j = 96; j <= 145; j++) {",
    "      try {",
    "        var p = fx.property(j);",
    "        if (p && p.name) {",
    "          var nm = p.name;",
    "          if (nm.indexOf('颜色') >= 0 || nm.indexOf('上色') >= 0 || nm.indexOf('辉光') >= 0 || nm.indexOf('不透明') >= 0 || nm.indexOf('混合') >= 0 || nm.indexOf('随机') >= 0 || nm.indexOf('精灵') >= 0 || nm.indexOf('旋转') >= 0) out.push(j + ':' + nm);",
    "        }",
    "      } catch(e) {}",
    "    }",
    "    comp.remove();",
    "    var f = new File('" + of_js + "');",
    "    f.encoding = 'UTF-8';",
    r"    if (f.open('w')) { f.write(out.join('\n')); f.close(); return 'W'; }",
    "    return 'OPENFAIL';",
    "  } catch(e) { return 'ERR:' + String(e); }",
    "})();",
]
jsx_file = bd / f"_pclr_{cmd_id}.jsx"
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
