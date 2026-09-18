#!/usr/bin/env python3
"""Test render for Vinland Saga composition"""
import json
import os
import time

from ae_mcp_client import AECommandClient

c = AECommandClient(signature_enabled=False, timeout=30)

# Check project
print("=== Project Info ===")
r = c.send_command("getProjectInfo", {})
print(json.dumps(r, indent=2, ensure_ascii=False))

# Render script
script = (
    'var comp = null;'
    'for (var i = 1; i <= app.project.numItems; i++) {'
    '    if (app.project.item(i).name === "E2E_VinlandSaga"'
    '        && app.project.item(i) instanceof CompItem) {'
    '        comp = app.project.item(i);'
    '        break;'
    '    }'
    '}'
    'if (!comp) { "Composition not found"; }'
    'else {'
    '    var outDir = new Folder("D:/AE-Work/output");'
    '    if (!outDir.exists) outDir.create();'
    '    while (app.project.renderQueue.numItems > 0) {'
    '        app.project.renderQueue.item('
    '            app.project.renderQueue.numItems).remove();'
    '    }'
    '    var rqItem = app.project.renderQueue.items.add(comp);'
    '    var om = rqItem.outputModule(1);'
    '    om.file = new File("D:/AE-Work/output/E2E_VinlandSaga.mp4");'
    '    app.project.renderQueue.render();'
    '    "Render completed for E2E_VinlandSaga";'
    '}'
)

print("\n=== Start Render ===")
r2 = c.send_command("executeAtomScript", {"scriptContent": script})
print(json.dumps(r2, indent=2, ensure_ascii=False))

# Wait and check output
print("\n=== Waiting for render (checking output file) ===")
output_path = "D:/AE-Work/output/E2E_VinlandSaga.mp4"
for i in range(30):
    time.sleep(2)
    if os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  Output file found! Size: {size_mb:.1f} MB")
        break
    print(f"  Waiting... ({(i+1)*2}s)")
else:
    print("  Render still in progress or failed")

# Final check
if os.path.exists(output_path):
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print("\n=== RENDER SUCCESS ===")
    print(f"  File: {output_path}")
    print(f"  Size: {size_mb:.1f} MB")
else:
    print(f"\n=== Output not yet found at {output_path} ===")
    print("  AE may still be rendering. Check AE render queue.")
