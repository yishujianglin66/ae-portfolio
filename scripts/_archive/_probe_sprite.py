"""探测 Particular Sprite（精灵贴图）设置路径: 粒子类型值 + 精灵图层引用"""
import json
import os
import time
import uuid
from pathlib import Path

bd = Path(__file__).resolve().parent.parent / ".ae-mcp-bridge"
cmd_id = str(uuid.uuid4())[:8]
out_file = bd / f"_sprite_{cmd_id}.txt"
of_js = str(out_file).replace(chr(92), "/")
# 先导入一张贴图作精灵候选, 探测粒子类型枚举值与精灵图层参数
sprite_path = str(Path("resources/effects/光点类/exp_glow.png").resolve()).replace(chr(92), "/")
jsx = """(function(){
  try {
    var comp = app.project.items.addComp('SPR', 100, 100, 1, 2, 30);
    var L = comp.layers.addSolid([1,0,0], 'p', 100, 100, 1.0, 2);
    var fx = L.property('ADBE Effect Parade').addProperty('tc Particular');
    var out = [];
    // 粒子类型参数(96/97)枚举
    var pt = fx.property(96);
    for (var v = 0; v <= 26; v++) {
      try { pt.setValue(v); out.push('ptype=' + v + ':' + pt.value); } catch(e) { break; }
    }
    // 尝试精灵引用: 先把贴图导入工程
    var io = new ImportOptions(new File('SPRITEPATH'));
    var ftg = app.project.importFile(io);
    out.push('imported=' + ftg.name);
    // Layer 精灵: 粒子类型=Sprite(常见值), 然后设 property(101) 图层选择
    comp.layers.add(ftg);
    try {
      pt.setValue(20); // 试 Sprite 区段
      var lay = fx.property(101);
      lay.setValue(2); // 引用工程内图层 index
      out.push('sprite101=SET idx2');
    } catch(e) { out.push('sprite101 FAIL:' + String(e).substring(0,60)); }
    comp.remove();
    var f = new File('OUTPATH');
    f.encoding = 'UTF-8';
    if (f.open('w')) { f.write(out.join('\n')); f.close(); return 'W'; }
    return 'OPENFAIL';
  } catch(e) { return 'ERR:' + String(e); }
})();""".replace("SPRITEPATH", sprite_path).replace("OUTPATH", of_js)
jsx_file = bd / f"_spr_{cmd_id}.jsx"
jsx_file.write_text(jsx, encoding="utf-8")
cmd = {"id": cmd_id, "command": "runScript", "args": {"file": str(jsx_file)}, "timestamp": time.time()}
tmp = bd / f"ae_command_{cmd_id}.tmp"
tmp.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
for _ in range(6):
    try: os.replace(str(tmp), str(bd/"ae_command.json")); break
    except PermissionError: time.sleep(2)
for i in range(15):
    time.sleep(6)
    if out_file.exists() and out_file.stat().st_size > 0:
        print(out_file.read_text(encoding="utf-8")); break
else: print("TIMEOUT")
