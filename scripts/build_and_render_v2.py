#!/usr/bin/env python3
"""构建总合成 + 渲染输出 (所有P3s_合成已创建后执行)"""
import sys, json, time
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"
OUTPUT = Path(r"D:\AE-Work\output\ALL_PRESETS_SHOWCASE.mp4")

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

# Step 1: 统计P3s_合成
print("[Step 1] Counting P3s_ comps...")
check = '''(function(){var r=[];for(var i=1;i<=app.project.items.length;i++){var it=app.project.item(i);if(it instanceof CompItem && it.name.indexOf("P3s_")==0){r.push(it.name);}}return JSON.stringify({count:r.length,sample:r.slice(0,5)});})();'''
res = send(check, 15)
print(f"  {res[:200]}")
try:
    info = json.loads(res)
    count = info.get('count', 0)
except:
    count = 0
print(f"  Found {count} preset comps")
if count == 0:
    print("  ERROR: No P3s_ comps! Run render_all_presets_v2.py first.")
    sys.exit(1)

# Step 2: 创建总合成
print(f"\n[Step 2] Creating master comp ({count} x 3s = {count*3}s)...")
master_jsx = '''(function(){
try{
  var comps=[];
  for(var i=1;i<=app.project.items.length;i++){
    var it=app.project.item(i);
    if(it instanceof CompItem && it.name.indexOf("P3s_")==0){
      comps.push(it);
    }
  }
  if(comps.length==0){return JSON.stringify({status:"error",msg:"no comps"});}
  comps.sort(function(a,b){return a.name<b.name?-1:1;});
  var seg=3.0;
  var total=comps.length*seg;
  for(var j=app.project.items.length;j>=1;j--){
    var jt=app.project.item(j);
    if(jt instanceof CompItem && jt.name=="ALL_PRESETS_SHOWCASE"){jt.remove();}
  }
  var master=app.project.items.addComp("ALL_PRESETS_SHOWCASE",1920,1080,1,total,30);
  master.bgColor=[0,0,0];
  for(var k=0;k<comps.length;k++){
    var layer=master.layers.add(comps[k]);
    layer.startTime=k*seg;
    layer.outPoint=(k+1)*seg;
  }
  return JSON.stringify({status:"success",comps:comps.length,duration:total,layers:master.numLayers});
}catch(e){return JSON.stringify({status:"error",msg:e.toString(),line:e.line});}
})();'''
res = send(master_jsx, 60)
print(f"  {res[:300]}")

# Step 3: 查询渲染模板
print("\n[Step 3] Querying render templates...")
tpl_jsx = '''(function(){
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
res = send(tpl_jsx, 20)
mp4_tpl = None
try:
    info = json.loads(res)
    for t in info.get('templates', []):
        tl = t.lower()
        if 'h.264' in tl or 'mp4' in tl:
            mp4_tpl = t
            break
except:
    pass
print(f"  Template: {mp4_tpl or 'default'}")

# Step 4: 删除旧输出
if OUTPUT.parent.exists():
    for f in OUTPUT.parent.glob("ALL_PRESETS_SHOWCASE.*"):
        try:
            f.unlink()
            print(f"  Deleted old: {f.name}")
        except:
            pass
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Step 5: 渲染
print(f"\n[Step 4] Rendering {count*3}s video...")
out_unix = str(OUTPUT).replace("\\", "/")
tpl_apply = f'om.applyTemplate("{mp4_tpl}");' if mp4_tpl else ''
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
  ''' + tpl_apply + '''
  om.file=new File("''' + out_unix + '''");
  app.project.renderQueue.render();
  return JSON.stringify({status:"rendered",duration:master.duration,frames:master.duration*30});
}catch(e){return JSON.stringify({status:"error",msg:e.toString(),line:e.line});}
})();'''
res = send(render_jsx, 1800)  # 30 min timeout
print(f"  {res[:300]}")

# Step 6: 验证
print("\n[Step 5] Verifying output...")
if OUTPUT.exists():
    mb = OUTPUT.stat().st_size / (1024*1024)
    print(f"  SUCCESS: {OUTPUT}")
    print(f"  Size: {mb:.2f} MB")
else:
    print(f"  NOT FOUND: {OUTPUT}")
    # 搜索可能的输出
    d = Path(r"D:\AE-Work\output")
    if d.exists():
        for f in sorted(d.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            print(f"    {f.name} ({f.stat().st_size/1024:.0f}KB)")
