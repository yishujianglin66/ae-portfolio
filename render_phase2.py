#!/usr/bin/env python3
import sys, json
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
from ae_mcp_client import AECommandClient

client = AECommandClient(signature_enabled=False, timeout=300)

with open("render_phase2.jsx", "r", encoding="utf-8") as f:
    script = f.read()

print("[渲染] 启动 Phase 2 优化版渲染...")
print("  输出: D:/AE-Work/output/E2E_VinlandSaga_Phase2.mp4")
print("  超时: 300秒")

result = client.send_command("executeAtomScript", {"script": script})
print(json.dumps(result, indent=2, ensure_ascii=False))
