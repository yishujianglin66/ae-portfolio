"""完整精灵链验证: 设粒子类型→选图层→渲染一帧看粒子是否变贴图"""
import json, time, uuid, os, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
bd = ROOT / ".ae-mcp-bridge"
tmp_png = ROOT / "tmp" / "sprite_glow.png"
cmd_id = str(uuid.uuid4())[:8]
out_file = bd / f"_spr3_{cmd_id}.txt"
of_js = str(out_file).replace(chr(92), "/")
sp = str(tmp_png).replace(chr(92), "/")
lines = [
    "(function(){",
    "  try {",
    "    var comp = app.project.items.addComp('SPR3', 200, 200, 1, 1, 30);",
    "    var L = comp.layers.addSolid([0,0,0], 'p', 200, 200, 1.0, 1);",
    "    var fx = L.property('ADBE Effect Parade').addProperty('tc Particular');",
    "    var out = [];",
    "    // 类型枚举名记录(1-6)",
    "    var p97 = fx.property(97);",
    "    for (var v = 1; v <= 6; v++) {",
    "      p97.setValue(v);",
    "      out.push('v' + v + 'sel');",
    "    }",
    "    // 导入贴图并加为图层(引导层, shy 不渲染但可被精灵引用)",
    "    var ftg = app.project.importFile(new ImportOptions(new File('" + sp + "')));",
    "    var sl = comp.layers.add(ftg);",
    "    sl.guideLayer = true;",
    "    out.push('layerAdded idx=' + sl.index);",
    "    // 试每个类型值 + 设图层引用",
    "    for (var t = 1; t <= 6; t++) {",
    "      try {",
    "        p97.setValue(t);",
    "        fx.property(101).setValue(sl.index);",
    "        out.push('type' + t + '+layer' + sl.index + '=OK');",
    "        break;",
    "      } catch(e) { out.push('type' + t + 'fail:' + String(e).substring(0,30)); }",
    "    }",
    "    // 粒子/秒提一档确保有粒子",
    "    fx.property(14).setValue(200);",
    "    fx.property(121).setValue(12);",
    "    comp.remove();",
    "    var f = new File('" + of_js + "');",
    "    f.encoding = 'UTF-8';",
    r"    if (f.open('w')) { f.write(out.join('\n')); f.close(); return 'W'; }",
    "    return 'OPENFAIL';",
    "  } catch(e) { return 'ERR:' + String(e); }",
    "})();",
]
jsx_file = bd / f"_spr3_{cmd_id}.jsx"
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
