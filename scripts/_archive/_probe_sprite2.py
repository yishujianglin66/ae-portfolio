"""精灵路径探测 v2: 路径 hex 编码规避转义, ASCII 文件名复制到临时位置"""
import json
import os
import shutil
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bd = ROOT / ".ae-mcp-bridge"
# 复制贴图到 ASCII 路径（绕开中文+引号问题）
src = ROOT / "resources" / "effects" / "光点类" / "exp_glow.png"
tmp_png = ROOT / "tmp" / "sprite_glow.png"
tmp_png.parent.mkdir(exist_ok=True)
shutil.copy(src, tmp_png)
sprite_path = str(tmp_png).replace(chr(92), "/")

cmd_id = str(uuid.uuid4())[:8]
out_file = bd / f"_spr2_{cmd_id}.txt"
of_js = str(out_file).replace(chr(92), "/")

jsx_lines = [
    "(function(){",
    "  try {",
    "    var comp = app.project.items.addComp('SPR2', 100, 100, 1, 2, 30);",
    "    var L = comp.layers.addSolid([1,0,0], 'p', 100, 100, 1.0, 2);",
    "    var fx = L.property('ADBE Effect Parade').addProperty('tc Particular');",
    "    var out = [];",
    "    var io = new ImportOptions(new File('" + sprite_path + "'));",
    "    var ftg = app.project.importFile(io);",
    "    out.push('imported=' + ftg.name);",
    "    var sl = comp.layers.add(ftg);",
    "    sl.shy = true;",  # shy 隐藏引导层
    "    var pt = fx.property(96);",
    "    for (var v = 16; v <= 26; v++) {",
    "      try { pt.setValue(v); out.push('ptype' + v + '=OK val=' + pt.value); } catch(e) { out.push('ptype' + v + '=no'); }",
    "    }",
    "    try { pt.setValue(20); var lay = fx.property(101); lay.setValue(2); out.push('spriteLayer101=SET'); } catch(e) { out.push('s101fail:' + String(e).substring(0,50)); }",
    "    comp.remove();",
    "    var f = new File('" + of_js + "');",
    "    f.encoding = 'UTF-8';",
    r"    if (f.open('w')) { f.write(out.join('\n')); f.close(); return 'W'; }",
    "    return 'OPENFAIL';",
    "  } catch(e) { return 'ERR:' + String(e); }",
    "})();",
]
jsx_file = bd / f"_spr2_{cmd_id}.jsx"
jsx_file.write_text("\n".join(jsx_lines), encoding="utf-8")
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
