#!/usr/bin/env python3
"""精确诊断Bridge通信 - 逐步排查"""
import json, time, sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"

def test_send(label, code, wait=30):
    print(f"\n[{label}]")
    print(f"  发送前 result文件: {BRIDGE_RESULT.read_text(encoding='utf-8')[:80] if BRIDGE_RESULT.exists() else 'NOT_EXIST'}")
    
    # 写入命令
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": datetime.now().isoformat(), "status": "pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    print(f"  命令已写入, 等待响应...")
    
    time.sleep(2)
    for i in range(wait):
        time.sleep(1)
        try:
            content = BRIDGE_RESULT.read_text(encoding="utf-8")
            if not content.strip():
                continue
            r = json.loads(content)
            status = r.get("status", "")
            has_result = "result" in r
            if has_result and status not in ("waiting", "pending"):
                # 提取内部结果
                inner = r.get("result", {})
                if isinstance(inner, dict) and inner.get("success") and "data" in inner:
                    data_str = inner["data"].get("result", "")
                    print(f"  ✓ 响应({i+1}s): {data_str[:100]}")
                    return True, data_str
                print(f"  ✓ 响应({i+1}s): {str(r)[:100]}")
                return True, r
        except json.JSONDecodeError:
            print(f"  [{i+1}s] JSON解析失败: {content[:50]}")
        except Exception as e:
            print(f"  [{i+1}s] 异常: {e}")
    
    final = BRIDGE_RESULT.read_text(encoding="utf-8")[:100] if BRIDGE_RESULT.exists() else "NOT_EXIST"
    print(f"  ✗ 超时! 最终result: {final}")
    return False, "timeout"

# Test 1: 简单ping
ok1, _ = test_send("T1-简单ping", 
    '(function(){return JSON.stringify({status:"success",v:app.version});})();')

# Test 2: 创建简单合成
ok2, _ = test_send("T2-创建合成",
    '(function(){try{var c=app.project.items.addComp("DIAG_TEST",100,100,1,1,30);c.remove();return JSON.stringify({status:"success",msg:"comp_ok"});}catch(e){return JSON.stringify({status:"error",msg:e.toString()});}})();',
    wait=20)

# Test 3: 枚举效果(轻量)
ok3, _ = test_send("T3-枚举效果数量",
    '(function(){try{return JSON.stringify({status:"success",count:app.effects.length});}catch(e){return JSON.stringify({status:"error",msg:e.toString()});}})();',
    wait=20)

print(f"\n{'='*40}")
print(f"诊断结果: T1={'✓' if ok1 else '✗'} T2={'✓' if ok2 else '✗'} T3={'✓' if ok3 else '✗'}")
