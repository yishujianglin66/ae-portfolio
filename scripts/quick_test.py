#!/usr/bin/env python3
"""简单测试 - 添加单个效果"""
import json
import time
from pathlib import Path

BRIDGE_CMD = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_command.json")
BRIDGE_RESULT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_result.json")

def send(code, wait=30):
    cmd = {"command": "runScript", "args": {"code": code}, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "status": "pending"}
    try: BRIDGE_RESULT.unlink()
    except: pass
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            if r.get("status") == "success":
                return r
        except: pass
    return None

# 创建合成
r = send("(function(){app.project.items.addComp('QT',1920,1080,1,10,30);return 'ok';})();")
print(f"Create comp: {r}")

# 添加效果
r = send("(function(){var comp=null;for(var i=1;i<=app.project.numItems;i++){if(app.project.item(i) instanceof CompItem && app.project.item(i).name==='QT'){comp=app.project.item(i);break;}}var layer=comp.layer(1);var eff=layer.effects.add('高斯模糊');return JSON.stringify({name:eff.name,matchName:eff.matchName});})();")
print(f"Add effect: {r}")

# 清理
r = send("(function(){for(var i=app.project.numItems;i>=1;i--){if(app.project.item(i) instanceof CompItem && app.project.item(i).name==='QT'){app.project.item(i).remove();break;}}return 'ok';})();")
print(f"Cleanup: {r}")
