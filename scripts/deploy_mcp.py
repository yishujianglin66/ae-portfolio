import shutil
import os

panelsDir = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels"

# 删除旧的 auto_listener（避免冲突）
oldFile = os.path.join(panelsDir, "ae_mcp_auto_listener.jsx")
if os.path.exists(oldFile):
    os.remove(oldFile)
    print(f"已删除旧脚本: ae_mcp_auto_listener.jsx")

# 部署修复后的 v26
src = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\ae_mcp_bridge_v26.jsx"
target = os.path.join(panelsDir, "ae_mcp_bridge_v26.jsx")

shutil.copy2(src, target)
size = os.path.getsize(target)
print(f"已部署: ae_mcp_bridge_v26.jsx ({size} 字节)")

# 验证
lines = open(target, 'r', encoding='utf-8').readlines()
line407 = lines[406].strip()
print(f"第 407 行: {line407}")
if "Arial" in line407:
    print("修复验证: OK")
else:
    print("修复验证: FAIL")
