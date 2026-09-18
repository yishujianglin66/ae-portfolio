#!/usr/bin/env python3
"""AE 效果名称测试 - 测试中英文效果名"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

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
    print("AE 效果名称测试")
    print("=" * 60)
    
    # 创建测试合成
    print("\n1. 创建测试合成...")
    code1 = """(function(){
      try {
        var comp = app.project.items.addComp("NameTest", 1920, 1080, 1, 10, 30);
        comp.layers.addText("Test");
        return JSON.stringify({ok:true});
      } catch(e) {
        return JSON.stringify({ok:false, error:e.toString()});
      }
    })();"""
    r = send_bridge(code1, 30)
    inner = extract_inner(r)
    print(f"   {inner}")
    
    # 测试中英文效果名
    print("\n2. 测试中英文效果名...")
    test_effects = [
        {"en":"Gaussian Blur", "zh":"高斯模糊"},
        {"en":"Glow", "zh":"发光"},
        {"en":"Lens Flare", "zh":"镜头光晕"},
        {"en":"Levels", "zh":"色阶"},
        {"en":"Fractal Noise", "zh":"分形噪波"},
        {"en":"Ramp", "zh":"渐变"},
        {"en":"CC Particle Systems II", "zh":"CC粒子系统 II"},
    ]
    
    code2 = """(function(){
      try {
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
          if (app.project.item(i) instanceof CompItem && app.project.item(i).name === "NameTest") {
            comp = app.project.item(i);
            break;
          }
        }
        var layer = comp.layer(1);
        var results = [];
        
        var tests = [
          {"en":"Gaussian Blur", "zh":"高斯模糊"},
          {"en":"Glow", "zh":"发光"},
          {"en":"Lens Flare", "zh":"镜头光晕"},
          {"en":"Levels", "zh":"色阶"},
          {"en":"Fractal Noise", "zh":"分形噪波"},
          {"en":"Ramp", "zh":"渐变"},
          {"en":"CC Particle Systems II", "zh":"CC粒子系统 II"}
        ];
        
        for (var i = 0; i < tests.length; i++) {
          var t = tests[i];
          var enSuccess = false, zhSuccess = false;
          var enMatchName = null, zhMatchName = null;
          
          try {
            var eff = layer.effects.add(t.en);
            enSuccess = true;
            enMatchName = eff.matchName;
            layer.effects.remove(eff);
          } catch(e) {}
          
          try {
            var eff2 = layer.effects.add(t.zh);
            zhSuccess = true;
            zhMatchName = eff2.matchName;
            layer.effects.remove(eff2);
          } catch(e) {}
          
          results.push({en:t.en, zh:t.zh, enSuccess:enSuccess, zhSuccess:zhSuccess, enMatchName:enMatchName, zhMatchName:zhMatchName});
        }
        
        return JSON.stringify({results:results});
      } catch(e) {
        return JSON.stringify({error:e.toString()});
      }
    })();"""
    r = send_bridge(code2, 30)
    inner = extract_inner(r)
    try:
        d = json.loads(inner)
        if d.get("error"):
            print(f"   ERROR: {d['error']}")
        else:
            for res in d["results"]:
                status = ""
                if res["enSuccess"]: status += f"EN:{res['enMatchName']} "
                if res["zhSuccess"]: status += f"ZH:{res['zhMatchName']}"
                if not res["enSuccess"] and not res["zhSuccess"]: status = "BOTH FAILED"
                print(f"   {res['en']} / {res['zh']}: {status}")
    except Exception as e:
        print(f"   解析失败: {e}, inner={inner[:300]}")
    
    # 清理
    print("\n3. 清理...")
    code3 = """(function(){
      try {
        for (var i = app.project.numItems; i >= 1; i--) {
          if (app.project.item(i) instanceof CompItem && app.project.item(i).name === "NameTest") {
            app.project.item(i).remove();
            break;
          }
        }
        return JSON.stringify({ok:true});
      } catch(e) {
        return JSON.stringify({ok:false, error:e.toString()});
      }
    })();"""
    r = send_bridge(code3, 30)
    inner = extract_inner(r)
    print(f"   {inner}")


if __name__ == "__main__":
    main()
