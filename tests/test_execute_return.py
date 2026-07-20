#!/usr/bin/env python3
import sys, json
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
from ae_mcp_client import AECommandClient

client = AECommandClient(signature_enabled=False, timeout=30)

# 测试显式return
simple = 'var x = {scale: 5, opacity: 3}; return JSON.stringify(x);'
result = client.send_command("executeAtomScript", {"script": simple})
print("显式return测试:", json.dumps(result, indent=2, ensure_ascii=False))

# 运行验证脚本
with open("verify_phase2.jsx", "r", encoding="utf-8") as f:
    verify_script = f.read()
result2 = client.send_command("executeAtomScript", {"script": verify_script})
print("\nPhase2验证:", json.dumps(result2, indent=2, ensure_ascii=False))
