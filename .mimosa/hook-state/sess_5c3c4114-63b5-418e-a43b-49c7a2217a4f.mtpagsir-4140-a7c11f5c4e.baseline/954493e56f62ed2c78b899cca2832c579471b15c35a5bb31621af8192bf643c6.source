#!/usr/bin/env python3
"""AE 效果测试器 V2 - 使用正确的 AE 2025 API"""
import json, time, sys
from pathlib import Path
from datetime import datetime

BRIDGE_CMD = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_command.json")
BRIDGE_RESULT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_result.json")


def send_bridge(code, wait=60):
    ts = datetime.now().isoformat()
    cmd = {"command": "runScript", "args": {"code": code}, "timestamp": ts, "status": "pending"}
    try: BRIDGE_RESULT.unlink()
    except: pass
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            status = r.get("status")
            if status == "success" or "success" in r or status == "error":
                if isinstance(r.get("result"), dict):
                    for k, v in r["result"].items():
                        if k not in r: r[k] = v
                return r
        except: pass
        if i % 5 == 4: print(f"  等待... ({i+1}s)")
    return {"success": False, "error": "timeout"}


def extract_inner(r):
    if isinstance(r.get("data"), dict) and r["data"].get("result"):
        return r["data"]["result"]
    if isinstance(r.get("result"), dict) and r["result"].get("result"):
        return r["result"]["result"]
    return "{}"


def main():
    print("=" * 60)
    print("AE 效果测试器 V2")
    print("=" * 60)
    
    # 先检查工程状态
    print("\n1. 检查工程状态...")
    code1 = """(function(){try{return JSON.stringify({project:!!app.project,numItems:app.project?app.project.numItems:0});}catch(e){return JSON.stringify({error:e.toString()});}})();"""
    r = send_bridge(code1, 30)
    inner = extract_inner(r)
    print(f"   返回: {inner[:200]}")
    
    # 创建测试合成和图层
    print("\n2. 创建测试合成...")
    code2 = """(function(){
      try {
        var comp = app.project.items.addComp("TestFX", 1920, 1080, 1, 10, 30);
        var layer = comp.layers.addText("Test");
        return JSON.stringify({compName:comp.name,layerName:layer.name,layerIndex:layer.index});
      } catch(e) {
        return JSON.stringify({error:e.toString(),line:e.line});
      }
    })();"""
    r = send_bridge(code2, 30)
    inner = extract_inner(r)
    print(f"   返回: {inner[:200]}")
    
    # 测试添加简单效果 - 使用正确的 API
    print("\n3. 测试添加效果...")
    code3 = """(function(){
      try {
        // 查找合成（AE 2025: app.project.item(index)，不是 items.item(name)）
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
          if (app.project.item(i) instanceof CompItem && app.project.item(i).name === "TestFX") {
            comp = app.project.item(i);
            break;
          }
        }
        if (!comp) return JSON.stringify({error:"comp not found"});
        var layer = comp.layer(1);
        var results = [];
        var effectsToTry = [
          {name:"Gaussian Blur", matchName:"ADBE Gaussian Blur 2"},
          {name:"Glow", matchName:"ADBE Glo2"},
          {name:"Lens Flare", matchName:"ADBE Lens Flare"},
          {name:"Levels", matchName:"ADBE Levels"},
          {name:"Fractal Noise", matchName:"ADBE Fractal Noise"},
          {name:"Ramp", matchName:"ADBE Ramp"},
          {name:"CC Particle Systems II", matchName:"CC Particle Systems II"},
          {name:"CC Particle World", matchName:"CC Particle World"}
        ];
        for (var i = 0; i < effectsToTry.length; i++) {
          var eff = effectsToTry[i];
          try {
            var added = layer.effects.add(eff.name);
            var params = [];
            for (var j = 1; j <= added.numProperties; j++) {
              params.push({name:added.property(j).name, type:added.property(j).propertyValueType.toString()});
            }
            results.push({name:eff.name,success:true,matchName:added.matchName,numProps:added.numProperties,params:params});
            layer.effects.remove(added);
          } catch(e) {
            try {
              var added2 = layer.effects.add(eff.matchName);
              results.push({name:eff.name,matchName:eff.matchName,success:true,matchName2:added2.matchName});
              layer.effects.remove(added2);
            } catch(e2) {
              results.push({name:eff.name,success:false,error:e2.toString().substring(0,50)});
            }
          }
        }
        return JSON.stringify({results:results});
      } catch(e) {
        return JSON.stringify({error:e.toString(),line:e.line});
      }
    })();"""
    r = send_bridge(code3, 60)
    inner = extract_inner(r)
    print(f"   返回: {inner}")
    
    # 清理
    print("\n4. 清理...")
    code4 = """(function(){
      try {
        for (var i = app.project.numItems; i >= 1; i--) {
          if (app.project.item(i) instanceof CompItem && app.project.item(i).name === "TestFX") {
            app.project.item(i).remove();
            break;
          }
        }
        return JSON.stringify({ok:true});
      } catch(e) {
        return JSON.stringify({ok:false,error:e.toString()});
      }
    })();"""
    r = send_bridge(code4, 30)
    inner = extract_inner(r)
    print(f"   返回: {inner}")


if __name__ == "__main__":
    main()
