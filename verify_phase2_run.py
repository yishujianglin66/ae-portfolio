#!/usr/bin/env python3
import sys, json
sys.path.insert(0, r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
from ae_mcp_client import AECommandClient

client = AECommandClient(signature_enabled=False, timeout=60)

with open("verify_phase2.jsx", "r", encoding="utf-8") as f:
    script = f.read()

result = client.send_command("executeAtomScript", {"script": script})
print(json.dumps(result, indent=2, ensure_ascii=False))
