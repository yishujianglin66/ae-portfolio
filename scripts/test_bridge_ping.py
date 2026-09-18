#!/usr/bin/env python3
"""快速测试AE Bridge连通性"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"

print(f"Bridge CMD: {BRIDGE_CMD} exists={BRIDGE_CMD.exists()}")
print(f"Bridge RESULT: {BRIDGE_RESULT} exists={BRIDGE_RESULT.exists()}")

# 写入waiting
BRIDGE_RESULT.write_text('{"status":"waiting"}', encoding="utf-8")

# 发送ping
jsx = '(function(){return JSON.stringify({status:"success",msg:"ping",ae:app.version});})();'
cmd = {"command": "runScript", "args": {"code": jsx},
       "timestamp": datetime.now().isoformat(), "status": "pending"}
BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
print(f"Sent ping at {datetime.now().strftime('%H:%M:%S')}")

# 等待
for i in range(20):
    time.sleep(1)
    try:
        r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
        if r.get("status") != "waiting" and "result" in r:
            print(f"Response ({i+1}s): {json.dumps(r, ensure_ascii=False)[:300]}")
            sys.exit(0)
    except:
        pass

print("TIMEOUT - Bridge未响应")
# 检查result文件当前内容
try:
    content = BRIDGE_RESULT.read_text(encoding="utf-8")
    print(f"Result file content: {content[:200]}")
except:
    pass
