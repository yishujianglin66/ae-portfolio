#!/usr/bin/env python3
"""
音频驱动效果参数变化 - 验证流程
模拟BPM=128的音乐，生成节拍同步关键帧
"""
import json
import math

from ae_mcp_client import AECommandClient

# 模拟音频分析结果
BPM = 128
DURATION = 10  # 秒
BEAT_INTERVAL = 60.0 / BPM  # 0.46875s per beat

# 生成节拍时间点
beat_times = []
t = 0.0
while t < DURATION:
    beat_times.append(round(t, 3))
    t += BEAT_INTERVAL

# 模拟能量曲线（正弦波模拟音乐动态）
energy_curve = []
for bt in beat_times:
    # 模拟4拍一个循环：强-弱-次强-弱
    beat_idx = int(bt / BEAT_INTERVAL) % 4
    base_energy = [1.0, 0.4, 0.7, 0.4][beat_idx]
    # 添加一些随机变化
    variation = 0.1 * math.sin(bt * 3.14)
    energy = max(0.2, min(1.0, base_energy + variation))
    energy_curve.append(round(energy, 3))

print(f"Generated {len(beat_times)} beats at BPM={BPM}")
print(f"Beat times: {beat_times[:8]}...")
print(f"Energy curve: {energy_curve[:8]}...")

# 生成关键帧数据
# 效果: Scale 在强拍时放大 (100-115)
# 效果: Rotation 随节拍旋转 (0-30)
# 效果: Opacity 随能量变化
keyframes = []

for i, (bt, energy) in enumerate(zip(beat_times, energy_curve)):
    is_downbeat = (i % 4 == 0)
    
    # Scale - 强拍放大
    scale = 100 + (energy * 15 if is_downbeat else energy * 5)
    keyframes.append({
        "property": "Scale",
        "time": bt,
        "value": [round(scale, 1), round(scale, 1)],
        "easeType": "easeInOut" if is_downbeat else "linear"
    })
    
    # Rotation - 持续旋转
    rotation = (bt / DURATION) * 30
    keyframes.append({
        "property": "Rotation",
        "time": bt,
        "value": round(rotation, 1),
        "easeType": "linear"
    })
    
    # Opacity - 能量越高越不透明
    opacity = 70 + energy * 30
    keyframes.append({
        "property": "Opacity",
        "time": bt,
        "value": round(opacity, 1),
        "easeType": "easeOut" if is_downbeat else "linear"
    })

print(f"\nTotal keyframes to write: {len(keyframes)}")

# 通过 executeAtomScript 批量写入
c = AECommandClient(signature_enabled=False, timeout=30)

# Build ExtendScript
script_lines = [
    'var compName = "E2E_VinlandSaga";',
    'var layerName = "MainVideo";',
    'var comp = null;',
    'for (var i = 1; i <= app.project.numItems; i++) {',
    '    if (app.project.item(i).name === compName && app.project.item(i) instanceof CompItem) {',
    '        comp = app.project.item(i); break;',
    '    }',
    '}',
    'if (!comp) { "Comp not found"; }',
    'else {',
    '    var layer = null;',
    '    for (var j = 1; j <= comp.numLayers; j++) {',
    '        if (comp.layer(j).name === layerName) { layer = comp.layer(j); break; }',
    '    }',
    '    if (!layer) { "Layer not found"; }',
    '    else {',
    '        var written = 0;',
    '        var kfs = ' + json.dumps(keyframes) + ';',
    '        for (var k = 0; k < kfs.length; k++) {',
    '            var kf = kfs[k];',
    '            var prop = layer.property(kf.property);',
    '            if (prop) {',
    '                prop.setValueAtTime(kf.time, kf.value);',
    '                if (kf.easeType !== "linear") {',
    '                    var idx = prop.nearestKeyIndex(kf.time);',
    '                    if (idx > 0) {',
    '                        var eIn = new KeyframeEase(0,33);',
    '                        var eOut = new KeyframeEase(0,33);',
    '                        if (kf.easeType === "easeIn") { eIn = new KeyframeEase(0,75); }',
    '                        else if (kf.easeType === "easeOut") { eOut = new KeyframeEase(0,75); }',
    '                        else if (kf.easeType === "easeInOut") { eIn = new KeyframeEase(0,75); eOut = new KeyframeEase(0,75); }',
    '                        try { prop.setTemporalEaseAtKey(idx,[eIn],[eOut]); } catch(ex) {}',
    '                    }',
    '                }',
    '                written++;',
    '            }',
    '        }',
    '        "Written: " + written + "/" + kfs.length;',
    '    }',
    '}',
]

script = ''.join(script_lines)

print("\n=== Writing audio-driven keyframes to AE ===")
r = c.send_command("executeAtomScript", {"script": script})
print(json.dumps(r, indent=2, ensure_ascii=False))

# Also add audio-reactive expression for continuous effect
print("\n=== Adding audio-reactive expression ===")
expr_script = (
    'var compName = "E2E_VinlandSaga";'
    'var layerName = "MainVideo";'
    'var comp = null;'
    'for (var i = 1; i <= app.project.numItems; i++) {'
    '    if (app.project.item(i).name === compName && app.project.item(i) instanceof CompItem) {'
    '        comp = app.project.item(i); break;'
    '    }'
    '}'
    'if (comp) {'
    '    var layer = null;'
    '    for (var j = 1; j <= comp.numLayers; j++) {'
    '        if (comp.layer(j).name === layerName) { layer = comp.layer(j); break; }'
    '    }'
    '    if (layer) {'
    '        var opacityProp = layer.property("Opacity");'
    '        if (opacityProp) {'
    '            opacityProp.expression = '
    '                "t = time; " +'
    '                "beat = Math.sin(t * 2 * Math.PI * 2.133); " +'
    '                "80 + beat * 20;";'
    '        }'
    '        var rotProp = layer.property("Rotation");'
    '        if (rotProp) {'
    '            rotProp.expression = '
    '                "t = time; " +'
    '                "t * 3 + Math.sin(t * 2 * Math.PI * 2.133) * 5;";'
    '        }'
    '        "Expressions added";'
    '    } else { "Layer not found"; }'
    '} else { "Comp not found"; }'
)

r2 = c.send_command("executeAtomScript", {"script": expr_script})
print(json.dumps(r2, indent=2, ensure_ascii=False))

print("\n=== Audio-driven effects setup complete ===")
print(f"- {len(beat_times)} beats mapped to keyframes")
print("- Scale: beat-synced pulses (100-115)")
print("- Rotation: continuous + beat wobble (0-30)")
print("- Opacity: energy-responsive (70-100)")
print("- Expressions: Opacity sine-wave, Rotation wobble")
