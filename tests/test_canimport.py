import json, os, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

cmd_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json'
res_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_result.json'

# Test: canImportFile vs direct import for H.264
test_script = r'''
var results = [];
var basePath = "D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750_AE/";
var f = new File(basePath + "vinland_4_4K_MAD.f30077.mp4");

var io = new ImportOptions(f);

// Test canImportFile
try {
    var canImport = app.project.canImportFile(io);
    results.push({step: "canImportFile", result: canImport});
} catch(e) {
    results.push({step: "canImportFile", error: e.toString()});
}

// Test direct import
try {
    var io2 = new ImportOptions(f);
    var imported = app.project.importFile(io2);
    results.push({step: "directImport", ok: imported != null, dur: imported ? imported.duration : -1});
} catch(e) {
    results.push({step: "directImport", error: e.toString()});
}

// Check audio file
var audioFile = new File(basePath + "ae\u5b9e\u6218\u97f3\u4e50.mp3");
results.push({step: "audio", exists: audioFile.exists, path: basePath + "ae\u5b9e\u6218\u97f3\u4e50.mp3"});

// Check all files in _AE dir
var dir = new Folder(basePath);
var files = dir.getFiles();
var fileList = [];
for (var i = 0; i < files.length; i++) {
    fileList.push(files[i].name);
}
results.push({step: "dirFiles", count: files.length, names: fileList});

return JSON.stringify(results);
'''

if os.path.exists(res_path):
    os.remove(res_path)
time.sleep(1)

cmd = {"command": "executeAtomScript", "script": test_script, "processed": False, "description": "test_canImport"}
with open(cmd_path, 'w', encoding='utf-8') as f:
    json.dump(cmd, f, ensure_ascii=False)

print("Testing canImportFile vs direct import...")
time.sleep(10)

if os.path.exists(res_path):
    with open(res_path, 'r', encoding='utf-8') as f:
        raw = f.read()
    result = json.loads(raw)
    if result.get('result'):
        inner = json.loads(result['result']) if isinstance(result['result'], str) else result['result']
        for item in inner:
            print(f"  {item}")
    else:
        print(f"  Error: {result}")
else:
    print("  No result")
