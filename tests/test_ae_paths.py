import json, time, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

cmd_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json'
res_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_result.json'

# Test script for AE
test_script = r'''
var results = [];
var basePath = "D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750/";

// Test 1: Simple file (no special chars)
var f1 = new File(basePath + "vinland_4_4K_MAD.f30077.mp4");
results.push({name: "MAD_4K_simple", exists: f1.exists});

// Test 2: File with special char
var f2path = basePath + "vinland_1_\u30101080P\u29F84K\u29F8\u6536\u85CF\u3011\u51b0\u6d77\u6218\u8bb0NCOP&ED\u4e24\u5b63\u5168\u5408\u96c6 p01 S1OP1-MUKANJYO.f30077.mp4";
var f2 = new File(f2path);
results.push({name: "MUKANJYO_special", exists: f2.exists});

// Test 3: Directory listing
var dir = new Folder(basePath);
var fileCount = 0;
var fileNames = [];
if (dir.exists) {
    var contents = dir.getFiles("*.mp4");
    fileCount = contents.length;
    for (var i = 0; i < Math.min(contents.length, 5); i++) {
        fileNames.push(contents[i].name.substring(0, 40));
    }
}
results.push({name: "dir_check", dirExists: dir.exists, fileCount: fileCount, samples: fileNames});

// Test 4: Try import
try {
    var impFile = new File(basePath + "vinland_4_4K_MAD.f30077.mp4");
    if (impFile.exists) {
        var io = new ImportOptions(impFile);
        var imported = app.project.importFile(io);
        results.push({name: "import_simple", ok: true, type: imported ? imported.typename : "null"});
    } else {
        results.push({name: "import_simple", ok: false, reason: "not found"});
    }
} catch(e) {
    results.push({name: "import_simple", ok: false, error: e.toString()});
}

return JSON.stringify(results);
'''

# Clear and send
if os.path.exists(res_path):
    os.remove(res_path)
time.sleep(1)

cmd = {"command": "executeAtomScript", "script": test_script, "processed": False, "description": "test ae file paths"}
with open(cmd_path, 'w', encoding='utf-8') as f:
    json.dump(cmd, f, ensure_ascii=False)

print("Sent. Waiting 5s...")
time.sleep(5)

if os.path.exists(res_path):
    with open(res_path, 'r', encoding='utf-8') as f:
        raw = f.read()
    # Parse and print safely
    result = json.loads(raw)
    if result.get('result'):
        inner = json.loads(result['result']) if isinstance(result['result'], str) else result['result']
        for item in inner:
            print(f"  {item}")
    else:
        print(f"  Raw: {raw[:500]}")
else:
    print("No result yet - AE still processing")
