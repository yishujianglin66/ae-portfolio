import json, os, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('D:/AE-Work/output/vinland_saga_v15_build.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    line = line.replace('Adobe After Effects 2026', 'Adobe After Effects 2025')
    line = line.replace('VinlandSaga_Battle_V14_safe.mp4', 'VinlandSaga_Battle_V15_v4.mp4')
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
    
    if 'SEGMENTS.reduce' in line:
        line = line.replace(
            'SEGMENTS.reduce(function(s, seg) { return s + seg.clips.length; }, 0)',
            '(function(){var _t=0;for(var _s=0;_s<SEGMENTS.length;_s++)_t+=SEGMENTS[_s].clips.length;return _t})()'
        )
    
    # KEY FIX: Remove canImportFile check (undefined in AE 2025)
    if 'app.project.canImportFile(io)' in line:
        line = line.replace('if (app.project.canImportFile(io)) {', '{')
    
    if 'var CLIP_PATH' in line:
        line = line.replace(
            'D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750/',
            'D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750_AE/'
        )
    if 'var AUDIO_PATH' in line:
        line = line.replace(
            'D:/AE-Work/\u97f3\u9891\u7d20\u6750\u5e93/BGM/',
            'D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750_AE/'
        )
    
    # Comment out alert to prevent blocking
    if line.strip().startswith('alert('):
        line = '//' + line
    
    stripped = line.strip()
    if stripped == 'main();':
        line = line.replace('main();', 'return main();')
    
    new_lines.append(line)

script = ''.join(new_lines)

# Quick verify
print("Key checks:")
print(f"  canImportFile removed: {'canImportFile' not in script}")
print(f"  _AE path: {'_AE/' in script}")
print(f"  addComp: {'addComp' in script}")
print(f"  return main: {'return main()' in script}")

cmd = {
    "command": "executeAtomScript",
    "script": script,
    "processed": False,
    "description": "V15_FINAL_canImport_fix"
}

cmd_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json'
res_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_result.json'

if os.path.exists(res_path):
    os.remove(res_path)
time.sleep(2)

with open(cmd_path, 'w', encoding='utf-8') as f:
    json.dump(cmd, f, ensure_ascii=False)

print(f"\nSent! Script: {len(script)} chars")
time.sleep(5)

log_tail = os.popen('powershell -Command "Get-Content C:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\.ae-mcp-bridge\\ae_listener_log.txt -Tail 3"').read()
print(f"Log: {log_tail.strip()}")
