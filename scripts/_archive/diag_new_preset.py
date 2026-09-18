#!/usr/bin/env python3
"""诊断新预设动画状态"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"

def send(code, wait=20):
    BRIDGE_RESULT.write_text('{"status":"waiting"}', encoding="utf-8")
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": datetime.now().isoformat(), "status": "pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.5)
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            if r.get("status") != "waiting" and "result" in r:
                return r
        except:
            pass
    return {"error": "timeout"}

# 检查NEW_oc_camera_impact的动画属性
jsx = '''(function(){
    var comp = null;
    for(var i=1;i<=app.project.items.length;i++){
        var it=app.project.item(i);
        if(it instanceof CompItem && it.name=="NEW_oc_camera_impact"){comp=it;break;}
    }
    if(!comp) return JSON.stringify({error:"comp not found"});
    var info = {name:comp.name, duration:comp.duration, fps:comp.frameRate, layers:comp.numLayers, details:[]};
    for(var li=1;li<=comp.numLayers;li++){
        var layer=comp.layer(li);
        var d = {name:layer.name, type:layer.threeDLayer?"3D":"2D"};
        try{
            var tg=layer.property("ADBE Transform Group");
            var props=[];
            for(var ki=1;ki<=tg.numProperties;ki++){
                var prop=tg.property(ki);
                if(prop.numKeys>0){
                    props.push({name:prop.name, keys:prop.numKeys, 
                        v0:prop.keyValue(1).toString(), 
                        vN:prop.keyValue(prop.numKeys).toString()});
                }
            }
            if(props.length>0) d.keyframed=props;
        }catch(e){d.transformErr=e.toString();}
        try{
            var fx=layer.property("ADBE Effect Parade");
            if(fx && fx.numProperties>0) d.effects=fx.numProperties;
        }catch(e){}
        info.details.push(d);
    }
    return JSON.stringify(info);
})();'''

r = send(jsx, 15)
inner = r.get("result", {})
if isinstance(inner, dict) and inner.get("success") and "data" in inner:
    result_str = inner["data"].get("result", "")
    try:
        parsed = json.loads(result_str)
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    except:
        print(f"Raw: {result_str[:500]}")
else:
    print(f"Error: {json.dumps(r, indent=2, ensure_ascii=False)[:500]}")
