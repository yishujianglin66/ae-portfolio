#!/usr/bin/env python3
"""诊断渲染队列 + 重新渲染到正确路径"""
import json
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"

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

# 检查渲染队列
print("[1] Render queue status:")
q = '''(function(){var r=[];var rq=app.project.renderQueue;for(var i=1;i<=rq.numItems;i++){var it=rq.item(i);var om=it.outputModule(1);var fn="none";try{fn=om.file?om.file.fsName:"none";}catch(e){}r.push({comp:it.comp?it.comp.name:"?",status:String(it.status),file:fn});}return JSON.stringify({count:rq.numItems,items:r});})();'''
print("  ", send(q, 15)[:500])

# 清空渲染队列, 重新添加并渲染到桌面(简单路径避免权限问题)
print("\n[2] Clearing queue and re-rendering to D:/AE-Work/output/")
out_path = "D:/AE-Work/output/ALL_PRESETS_SHOWCASE.mp4"
render = '''(function(){
try{
  var rq=app.project.renderQueue;
  while(rq.numItems>0){rq.item(1).remove();}
  var master=null;
  for(var i=1;i<=app.project.items.length;i++){
    var it=app.project.item(i);
    if(it instanceof CompItem && it.name=="ALL_PRESETS_SHOWCASE"){master=it;break;}
  }
  if(!master){return JSON.stringify({status:"error",msg:"no master comp"});}
  var ri=rq.items.add(master);
  var om=ri.outputModule(1);
  om.applyTemplate("H.264 - \\u5339\\u914d\\u6e32\\u67d3\\u8bbe\\u7f6e - 15 Mbps");
  om.file=new File("''' + out_path + '''");
  var outFile=om.file?om.file.fsName:"set-failed";
  rq.render();
  var done=String(ri.status);
  return JSON.stringify({status:"ok",output:outFile,finalStatus:done});
}catch(e){return JSON.stringify({status:"error",msg:e.toString(),line:e.line});}
})();'''
res = send(render, 900)
print("  ", res[:400])

# 验证
print("\n[3] Verify:")
p = Path(r"D:\AE-Work\output\ALL_PRESETS_SHOWCASE.mp4")
if p.exists():
    print(f"  SUCCESS! {p} = {p.stat().st_size/1048576:.1f} MB")
else:
    print("  Not at expected path. Searching...")
    import glob
    for pat in [r"D:\AE-Work\output\ALL_PRESETS*", r"D:\AE-Work\ALL_PRESETS*", r"C:\Users\Administrator\Desktop\ALL_PRESETS*"]:
        for f in glob.glob(pat):
            print(f"  Found: {f} ({Path(f).stat().st_size/1048576:.1f} MB)")
