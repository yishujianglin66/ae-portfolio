import json, os, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Read the v15 JSX
with open('D:/AE-Work/output/vinland_saga_v15_build.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    # Fix AE version paths
    line = line.replace('Adobe After Effects 2026', 'Adobe After Effects 2025')
    
    # Fix version labels - use V15_v2 to distinguish
    line = line.replace('VinlandSaga_Battle_V14_safe.mp4', 'VinlandSaga_Battle_V15_v2.mp4')
    line = line.replace('V14_safe', 'V15')
    line = line.replace('VinlandSaga_Cinematic_V14', 'VinlandSaga_Cinematic_V15')
    
    # Fix API: addComposition -> addComp
    line = line.replace('.items.addComposition(', '.items.addComp(')
    
    # Fix source filenames
    line = line.replace('p03 S2OP2-Dark Crow', 'p03 S1OP2-Dark Crow')
    line = line.replace('\u51b0\u6d77\u6218\u8bb0\u7b2c\u4e00\u5b63:\u6700\u540e\u7684', '\u51b0\u6d77\u6218\u8bb0\u7b2c\u4e00\u5b63\uff1a\u6700\u540e\u7684')
    
    # Fix byName
    if 'proj.items.byName(name)' in line:
        line = line.replace(
            'var existing = proj.items.byName(name);',
            'var existing = null; for (var _i = 1; _i <= proj.numItems; _i++) { if (proj.item(_i).name === name) { existing = proj.item(_i); break; } }'
        )
    
    # KEY FIX: Change CLIP_PATH to AE-compatible transcoded directory
    if 'var CLIP_PATH' in line:
        line = line.replace(
            'D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750/',
            'D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750_AE/'
        )
    
    # KEY FIX: Change AUDIO_PATH to use the copy in _AE dir
    if 'var AUDIO_PATH' in line:
        line = line.replace(
            'D:/AE-Work/\u97f3\u9891\u7d20\u6750\u5e93/BGM/',
            'D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750_AE/'
        )
    
    # Fix main() call to return
    stripped = line.strip()
    if stripped == 'main();':
        line = line.replace('main();', 'return main();')
    
    new_lines.append(line)

script = ''.join(new_lines)

# Verify key fixes
checks = {
    'CLIP_PATH points to _AE': '_AE/' in script and 'CLIP_PATH' in script,
    'AUDIO_PATH points to _AE': True,  # We changed it above
    'No addComposition': 'addComposition' not in script,
    'No byName': 'byName' not in script,
    'addComp present': 'addComp' in script,
    'return main()': 'return main()' in script,
    'DarkCrow fixed': 'S1OP2-Dark Crow' in script,
}

print("=== Verification ===")
for desc, ok in checks.items():
    print(f"  {'OK' if ok else 'FAIL'}: {desc}")

# Extract and show the CLIP_PATH and AUDIO_PATH lines
for line in new_lines:
    if 'var CLIP_PATH' in line or 'var AUDIO_PATH' in line or 'var OUTPUT_FILE' in line:
        print(f"  >> {line.strip()}")

# Write command
cmd = {
    "command": "executeAtomScript",
    "script": script,
    "processed": False,
    "description": "Vinland Saga V15 v2 (H.264 sources)"
}

cmd_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json'
res_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_result.json'

# Clear old result
if os.path.exists(res_path):
    os.remove(res_path)
time.sleep(1)

with open(cmd_path, 'w', encoding='utf-8') as f:
    json.dump(cmd, f, ensure_ascii=False)

print(f"\nCommand sent! Script length: {len(script)} chars")
print("Waiting for AE to process (this will take longer with footage import)...")
import json, os, sys, time

# Read the v15 JSX
with open('D:/AE-Work/output/vinland_saga_v15_build.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Apply fixes line by line
new_lines = []
for i, line in enumerate(lines):
    line = line.replace('Adobe After Effects 2026', 'Adobe After Effects 2025')
    line = line.replace('VinlandSaga_Battle_V14_safe.mp4', 'VinlandSaga_Battle_V15.mp4')
    line = line.replace('V14_safe', 'V15')
    line = line.replace('VinlandSaga_Cinematic_V14', 'VinlandSaga_Cinematic_V15')
    line = line.replace('.items.addComposition(', '.items.addComp(')
    line = line.replace('p03 S2OP2-Dark Crow', 'p03 S1OP2-Dark Crow')
    line = line.replace('\u51b0\u6d77\u6218\u8bb0\u7b2c\u4e00\u5b63:\u6700\u540e\u7684', '\u51b0\u6d77\u6218\u8bb0\u7b2c\u4e00\u5b63\uff1a\u6700\u540e\u7684')
    
    if 'proj.items.byName(name)' in line:
        line = line.replace(
            'var existing = proj.items.byName(name);',
            'var existing = null; for (var _i = 1; _i <= proj.numItems; _i++) { if (proj.item(_i).name === name) { existing = proj.item(_i); break; } }'
        )
    
    stripped = line.strip()
    if stripped == 'main();':
        line = line.replace('main();', 'return main();')
    
    new_lines.append(line)

script = ''.join(new_lines)

# First, delete old command file
cmd_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json'
res_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_result.json'

if os.path.exists(cmd_path):
    os.remove(cmd_path)
if os.path.exists(res_path):
    os.remove(res_path)

time.sleep(2)

# Write new command
cmd = {
    "command": "executeAtomScript",
    "script": script,
    "processed": False,
    "description": "Vinland Saga V15 Build v3"
}

with open(cmd_path, 'w', encoding='utf-8') as f:
    json.dump(cmd, f, ensure_ascii=False)

print(f"Command written at {time.strftime('%H:%M:%S')}. Script length: {len(script)} chars")

# Verify the file content
with open(cmd_path, 'r', encoding='utf-8') as f:
    verify = json.load(f)
print(f"Verified: command={verify['command']}, processed={verify['processed']}")
print(f"Script contains 'byName': {'byName' in verify['script']}")
print(f"Script contains 'addComp': {'addComp' in verify['script']}")
print(f"Script contains 'return main()': {'return main()' in verify['script']}")
