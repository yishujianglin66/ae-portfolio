#!/usr/bin/env python3
"""AE 调试工具 - 检查 layer 对象属性和效果 API"""
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
    print("AE 调试工具")
    print("=" * 60)
    
    # 创建测试合成
    print("\n1. 创建测试合成...")
    code1 = """(function(){
      try {
        var comp = app.project.items.addComp("DebugTest", 1920, 1080, 1, 10, 30);
        var layer = comp.layers.addText("Debug");
        return JSON.stringify({compName:comp.name,layerName:layer.name});
      } catch(e) {
        return JSON.stringify({error:e.toString()});
      }
    })();"""
    r = send_bridge(code1, 30)
    inner = extract_inner(r)
    print(f"   返回: {inner}")
    
    # 检查 layer 对象属性
    print("\n2. 检查 layer 对象属性...")
    code2 = """(function(){
      try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
          if (app.project.item(i) instanceof CompItem && app.project.item(i).name === "DebugTest") {
            comp = app.project.item(i);
            break;
          }
        }
        var layer = comp.layer(1);
        var props = [];
        for (var propName in layer) {
          try {
            var val = layer[propName];
            props.push({name:propName, type:(typeof val), value:String(val).substring(0,50)});
          } catch(e) {
            props.push({name:propName, type:"error", error:e.toString().substring(0,30)});
          }
        }
        return JSON.stringify({layerProps:props.slice(0,50)});
      } catch(e) {
        return JSON.stringify({error:e.toString()});
      }
    })();"""
    r = send_bridge(code2, 30)
    inner = extract_inner(r)
    print(f"   返回: {inner[:500]}")
    
    # 检查 effects 属性
    print("\n3. 检查 effects 属性...")
    code3 = """(function(){
      try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
          if (app.project.item(i) instanceof CompItem && app.project.item(i).name === "DebugTest") {
            comp = app.project.item(i);
            break;
          }
        }
        var layer = comp.layer(1);
        var info = {};
        try { info.effects = String(layer.effects); } catch(e) { info.effectsErr = e.toString(); }
        try { info.effectsType = typeof layer.effects; } catch(e) { info.effectsTypeErr = e.toString(); }
        try { info.numEffects = layer.effects.numProperties; } catch(e) { info.numEffectsErr = e.toString(); }
        return JSON.stringify(info);
      } catch(e) {
        return JSON.stringify({error:e.toString()});
      }
    })();"""
    r = send_bridge(code3, 30)
    inner = extract_inner(r)
    print(f"   返回: {inner}")
    
    # 测试用 property("Effects") 方式
    print("\n4. 测试 property('Effects') 方式...")
    code4 = """(function(){
      try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
          if (app.project.item(i) instanceof CompItem && app.project.item(i).name === "DebugTest") {
            comp = app.project.item(i);
            break;
          }
        }
        var layer = comp.layer(1);
        var info = {};
        try { info.effectsProp = String(layer.property("Effects")); } catch(e) { info.effectsPropErr = e.toString(); }
        try { 
          var fx = layer.property("Effects");
          info.fxNumProps = fx.numProperties;
        } catch(e) { info.fxNumPropsErr = e.toString(); }
        return JSON.stringify(info);
      } catch(e) {
        return JSON.stringify({error:e.toString()});
      }
    })();"""
    r = send_bridge(code4, 30)
    inner = extract_inner(r)
    print(f"   返回: {inner}")
    
    # 测试直接添加效果的完整路径
    print("\n5. 测试添加效果 - 使用完整路径...")
    code5 = """(function(){
      try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
          if (app.project.item(i) instanceof CompItem && app.project.item(i).name === "DebugTest") {
            comp = app.project.item(i);
            break;
          }
        }
        var layer = comp.layer(1);
        try {
          var fx = layer.effects.add("Gaussian Blur");
          return JSON.stringify({success:true, name:fx.name});
        } catch(e) {
          try {
            var fx2 = layer.property("Effects").addProperty("ADBE Gaussian Blur 2");
            return JSON.stringify({success:true, name:fx2.name});
          } catch(e2) {
            return JSON.stringify({success:false, error1:e.toString(), error2:e2.toString()});
          }
        }
      } catch(e) {
        return JSON.stringify({error:e.toString()});
      }
    })();"""
    r = send_bridge(code5, 30)
    inner = extract_inner(r)
    print(f"   返回: {inner}")
    
    # 清理
    print("\n6. 清理...")
    code6 = """(function(){
      try {
        for (var i = app.project.numItems; i >= 1; i--) {
          if (app.project.item(i) instanceof CompItem && app.project.item(i).name === "DebugTest") {
            app.project.item(i).remove();
            break;
          }
        }
        return JSON.stringify({ok:true});
      } catch(e) {
        return JSON.stringify({ok:false,error:e.toString()});
      }
    })();"""
    r = send_bridge(code6, 30)
    inner = extract_inner(r)
    print(f"   返回: {inner}")


if __name__ == "__main__":
    main()
