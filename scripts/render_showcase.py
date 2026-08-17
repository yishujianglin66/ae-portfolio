#!/usr/bin/env python3
"""查询输出模板并用正确模板渲染总合成"""
import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"
OUTPUT = r"D:\AE-Work\output\ALL_PRESETS_SHOWCASE.mp4"

def send(code, wait=60):
    BRIDGE_RESULT.write_text('{"status":"waiting"}', encoding='utf-8')
    cmd = {'command':'runScript','args':{'code':code},
           'timestamp':datetime.now().isoformat(),'status':'pending'}
    BRIDGE_CMD.write_text(json.dumps(cmd,ensure_ascii=False), encoding='utf-8')
    time.sleep(1)
    for _ in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding='utf-8'))
            if r.get('status') != 'waiting' and 'result' in r:
                inner = r.get('result', {})
                if isinstance(inner, dict) and inner.get('success') and 'data' in inner:
                    return inner['data'].get('result', '')
                return json.dumps(r, ensure_ascii=False)
        except:
            pass
    return 'TIMEOUT'

# Step 1: 查询可用输出模板
print("[Step 1] Querying output module templates...")
q = '''(function(){
try{
  var master=null;
  for(var i=1;i<=app.project.items.length;i++){
    var it=app.project.item(i);
    if(it instanceof CompItem && it.name=="ALL_PRESETS_SHOWCASE"){master=it;break;}
  }
  if(!master){return JSON.stringify({err:"no master"});}
  var rq=app.project.renderQueue.items.add(master);
  var tpls=rq.outputModule(1).templates;
  rq.remove();
  return JSON.stringify({templates:tpls});
}catch(e){return JSON.stringify({err:e.toString()});}
})();'''
res = send(q, 20)
print("  ", res[:400])

templates = []
try:
    info = json.loads(res)
    templates = info.get('templates', [])
except:
    pass

# 选择合适的MP4模板
mp4_tpl = None
for t in templates:
    tl = t.lower()
    if 'h.264' in tl or 'h264' in tl or 'mp4' in tl:
        mp4_tpl = t
        break
if not mp4_tpl:
    for t in templates:
        if 'mpeg' in t.lower():
            mp4_tpl = t
            break

print(f"\n  Selected template: {mp4_tpl}")
if not mp4_tpl:
    print("  No MP4 template found, will use default + set format")

# Step 2: 删除旧输出
out = Path(OUTPUT)
if out.parent.exists():
    for f in out.parent.glob("ALL_PRESETS_SHOWCASE.*"):
        try:
            f.unlink()
            print(f"  Deleted old: {f.name}")
        except:
            pass

# Step 3: 渲染
print("\n[Step 2] Rendering master comp...")
out_unix = OUTPUT.replace("\\", "/")
tpl_jsx = f'om.applyTemplate("{mp4_tpl}");' if mp4_tpl else ''
render_jsx = '''(function(){
try{
  var master=null;
  for(var i=1;i<=app.project.items.length;i++){
    var it=app.project.item(i);
    if(it instanceof CompItem && it.name=="ALL_PRESETS_SHOWCASE"){master=it;break;}
  }
  if(!master){return JSON.stringify({status:"error",msg:"master not found"});}
  var rq=app.project.renderQueue.items.add(master);
  var om=rq.outputModule(1);
  ''' + tpl_jsx + '''
  om.file=new File("''' + out_unix + '''");
  app.project.renderQueue.render();
  return JSON.stringify({status:"rendered"});
}catch(e){return JSON.stringify({status:"error",msg:e.toString(),line:e.line});}
})();'''
res = send(render_jsx, 900)
print("  ", res[:300])

# Step 4: 验证
print("\n[Step 3] Verifying...")
if out.exists():
    mb = out.stat().st_size / (1024*1024)
    print(f"  SUCCESS: {OUTPUT}")
    print(f"  Size: {mb:.1f} MB")
else:
    print(f"  Not found: {OUTPUT}")
    # 列出output目录
    d = Path(r"D:\AE-Work\output")
    if d.exists():
        print("  Files in output dir:")
        for f in list(d.glob("*"))[:10]:
            print(f"    {f.name}")
