"""探测粒子类型 1-6 的显示名(Sprite 通常在枚举后段) + Sprite 相关参数区段"""
import json
import os
import time
import uuid
from pathlib import Path

bd = Path(__file__).resolve().parent.parent / ".ae-mcp-bridge"
cmd_id = str(uuid.uuid4())[:8]
out_file = bd / f"_pty2_{cmd_id}.txt"
of_js = str(out_file).replace(chr(92), "/")
lines = [
    "(function(){",
    "  try {",
    "    var comp = app.project.items.addComp('PT2', 100, 100, 1, 2, 30);",
    "    var L = comp.layers.addSolid([1,0,0], 'p', 100, 100, 1.0, 2);",
    "    var fx = L.property('ADBE Effect Parade').addProperty('tc Particular');",
    "    var out = [];",
    "    var p97 = fx.property(97);",
    "    for (var v = 1; v <= 6; v++) {",
    "      try { p97.setValue(v); out.push('type' + v + '=' + p97.value); } catch(e) {}",
    "    }",
    "    // 找 Sprite/精灵 字样的参数名(全参数扫一层, 仅记名字含关键词的)",
    "    for (var j = 90; j <= 130; j++) {",
    "      try {",
    "        var p = fx.property(j);",
    "        if (p && p.name) {",
    "          var nm = p.name.toLowerCase();",
    "          if (nm.indexOf('sprite') >= 0 || p.name.indexOf('精灵') >= 0 || nm.indexOf('layer') >= 0 || p.name.indexOf('图层') >= 0) out.push(j + ':' + p.name);",
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
jsx_file = bd / f"_pty2_{cmd_id}.jsx"
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
