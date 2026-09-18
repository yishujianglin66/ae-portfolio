#!/usr/bin/env python3
"""创建总合成 + AE内部渲染单个完整视频"""
import json
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
from pathlib import Path

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

# Step 1: 检查现有 P3s_ 合成
print("[Step 1] Checking existing P3s_ comps...")
check = '''(function(){var r=[];for(var i=1;i<=app.project.items.length;i++){var it=app.project.item(i);if(it instanceof CompItem && it.name.indexOf("P3s_")==0){r.push(it.name);}}return JSON.stringify({count:r.length,sample:r.slice(0,3)});})();'''
res = send(check, 15)
print("  Result:", res[:200])

try:
    info = json.loads(res)
    count = info.get('count', 0)
except:
    count = 0

if count == 0:
    print("  No P3s_ comps found. Need to create them first.")
    sys.exit(1)

print(f"  Found {count} preset comps")

# Step 2: 创建总合成, 把所有P3s_合成按顺序排列
print("\n[Step 2] Creating master showcase comp...")
master_jsx = '''(function(){
try{
  // 收集所有P3s_合成
  var comps=[];
  for(var i=1;i<=app.project.items.length;i++){
    var it=app.project.item(i);
    if(it instanceof CompItem && it.name.indexOf("P3s_")==0){
      comps.push(it);
    }
  }
  if(comps.length==0){return JSON.stringify({status:"error",msg:"no comps"});}
  // 按名称排序保证顺序稳定
  comps.sort(function(a,b){return a.name<b.name?-1:1;});
  var seg=3.0;
  var total=comps.length*seg;
  // 删除旧的总合成
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
res = send(master_jsx, 30)
print("  Result:", res[:300])

# Step 3: 删除旧输出文件(防覆盖弹窗)
out = Path(OUTPUT)
if out.parent.exists():
    for f in out.parent.glob("ALL_PRESETS_SHOWCASE.*"):
        try:
            f.unlink()
            print(f"  Deleted old: {f.name}")
        except:
            pass

# Step 4: 加入渲染队列并渲染
print("\n[Step 3] Adding to render queue and rendering...")
out_unix = OUTPUT.replace("\\", "/")
render_jsx = '''(function(){
try{
  var master=null;
  for(var i=1;i<=app.project.items.length;i++){
    var it=app.project.item(i);
    if(it instanceof CompItem && it.name=="ALL_PRESETS_SHOWCASE"){master=it;break;}
  }
  if(!master){return JSON.stringify({status:"error",msg:"master comp not found"});}
  var rq=app.project.renderQueue.items.add(master);
  var om=rq.outputModule(1);
  om.applyTemplate("H.264");
  var f=new File("''' + out_unix + '''");
  om.file=f;
  rq.render();
  return JSON.stringify({status:"rendered",output:"''' + out_unix + '''"});
}catch(e){return JSON.stringify({status:"error",msg:e.toString(),line:e.line});}
})();'''
res = send(render_jsx, 600)
print("  Result:", res[:300])

# Step 5: 验证
print("\n[Step 4] Verifying output...")
if out.exists():
    mb = out.stat().st_size / (1024*1024)
    print(f"  SUCCESS: {OUTPUT}")
    print(f"  Size: {mb:.1f} MB")
else:
    print(f"  Output not found: {OUTPUT}")
