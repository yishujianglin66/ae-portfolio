import json
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

cmd_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json'
res_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_result.json'

# Diagnostic script: check what's in the project
diag_script = r'''
var info = {};

// List all items
info.items = [];
for (var i = 1; i <= app.project.numItems; i++) {
    var item = app.project.item(i);
    info.items.push({
        name: item.name.substring(0, 60),
        type: item.typename,
        dur: item.duration ? item.duration.toFixed(2) : "N/A"
    });
}

// Check render queue
info.renderQueue = [];
for (var r = 1; r <= app.project.renderQueue.numItems; r++) {
    var rqItem = app.project.renderQueue.item(r);
    info.renderQueue.push({
        compName: rqItem.comp ? rqItem.comp.name : "null",
        status: rqItem.status,
        elapsed: rqItem.elapsedTime ? rqItem.elapsedTime.toFixed(1) : "N/A"
    });
}

// Check if V15 comp exists and its layers
info.v15Layers = [];
for (var i = 1; i <= app.project.numItems; i++) {
    if (app.project.item(i) instanceof CompItem && app.project.item(i).name.indexOf("V15") >= 0) {
        var comp = app.project.item(i);
        info.v15Comp = comp.name;
        info.v15NumLayers = comp.numLayers;
        for (var l = 1; l <= Math.min(comp.numLayers, 15); l++) {
            var layer = comp.layer(l);
            info.v15Layers.push({
                name: layer.name ? layer.name.substring(0, 40) : "unnamed",
                source: layer.source ? layer.source.name.substring(0, 40) : "null",
                sourceType: layer.source ? layer.source.typename : "null"
            });
        }
        break;
    }
}

return JSON.stringify(info);
'''

if os.path.exists(res_path):
    os.remove(res_path)
time.sleep(1)

cmd = {"command": "executeAtomScript", "script": diag_script, "processed": False, "description": "diag_v15_project"}
with open(cmd_path, 'w', encoding='utf-8') as f:
    json.dump(cmd, f, ensure_ascii=False)

print("Diagnosing AE project...")
time.sleep(10)

if os.path.exists(res_path):
    with open(res_path, 'r', encoding='utf-8') as f:
        raw = f.read()
    result = json.loads(raw)
    if result.get('result'):
        inner = json.loads(result['result']) if isinstance(result['result'], str) else result['result']
        print(f"\n=== Items ({len(inner.get('items', []))}) ===")
        for item in inner.get('items', [])[:20]:
            print(f"  [{item['type']}] {item['name']} (dur={item['dur']})")
        
        print(f"\n=== Render Queue ({len(inner.get('renderQueue', []))}) ===")
        for rq in inner.get('renderQueue', []):
            print(f"  Comp: {rq['compName']}, Status: {rq['status']}, Elapsed: {rq['elapsed']}s")
        
        print("\n=== V15 Comp ===")
        print(f"  Name: {inner.get('v15Comp', 'NOT FOUND')}")
        print(f"  Layers: {inner.get('v15NumLayers', 0)}")
        for layer in inner.get('v15Layers', []):
            print(f"    [{layer['sourceType']}] {layer['name']} -> source: {layer['source']}")
    else:
        print(f"  Error: {result.get('error', 'unknown')}")
        print(f"  Raw: {raw[:300]}")
else:
    print("  No result - AE still busy")
    log = os.popen('powershell -Command "Get-Content C:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\.ae-mcp-bridge\\ae_listener_log.txt -Tail 3"').read()
    print(f"  Log: {log.strip()}")
