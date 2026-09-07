import json, os, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

cmd_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json'
res_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_result.json'

# Simple test: import one H.264 file and check
test_script = r'''
var results = [];
var basePath = "D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750_AE/";

// Check directory
var dir = new Folder(basePath);
results.push({step: "dir", exists: dir.exists});

// Check file
var f = new File(basePath + "vinland_4_4K_MAD.f30077.mp4");
results.push({step: "file_exists", exists: f.exists});

// Try import
try {
    var io = new ImportOptions(f);
    var imported = app.project.importFile(io);
    results.push({step: "import", ok: imported != null, type: imported ? imported.typename : "null", dur: imported ? imported.duration : -1});
} catch(e) {
    results.push({step: "import", ok: false, error: e.toString()});
}

// Check current comps
var compCount = 0;
var compNames = [];
for (var i = 1; i <= app.project.numItems; i++) {
    if (app.project.item(i) instanceof CompItem) {
        compCount++;
        compNames.push(app.project.item(i).name);
    }
}
results.push({step: "comps", count: compCount, names: compNames});

// Check total items
results.push({step: "total_items", count: app.project.numItems});

return JSON.stringify(results);
'''

if os.path.exists(res_path):
    os.remove(res_path)
time.sleep(1)

cmd = {"command": "executeAtomScript", "script": test_script, "processed": False, "description": "test_h264_import"}
with open(cmd_path, 'w', encoding='utf-8') as f:
    json.dump(cmd, f, ensure_ascii=False)

print("Testing H.264 import in AE...")
time.sleep(8)

if os.path.exists(res_path):
    with open(res_path, 'r', encoding='utf-8') as f:
        raw = f.read()
    result = json.loads(raw)
    if result.get('result'):
        inner = json.loads(result['result']) if isinstance(result['result'], str) else result['result']
        for item in inner:
            print(f"  {item}")
    else:
        print(f"  Raw result: {raw[:500]}")
else:
    print("  No result - AE still busy with previous command")
    # Check log
    log = os.popen('powershell -Command "Get-Content C:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\.ae-mcp-bridge\\ae_listener_log.txt -Tail 3"').read()
    print(f"  Log: {log.strip()}")
