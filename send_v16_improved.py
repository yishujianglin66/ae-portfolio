import json, os, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('D:/AE-Work/output/vinland_saga_v15_build.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# ============ 基础修复 (AE 2025 兼容) ============
content = content.replace('Adobe After Effects 2026', 'Adobe After Effects 2025')
content = content.replace('VinlandSaga_Battle_V14_safe.mp4', 'VinlandSaga_Battle_V16.mp4')
content = content.replace('V14_safe', 'V16')
content = content.replace('VinlandSaga_Cinematic_V14', 'VinlandSaga_Cinematic_V16')
content = content.replace('.items.addComposition(', '.items.addComp(')
content = content.replace('p03 S2OP2-Dark Crow', 'p03 S1OP2-Dark Crow')
content = content.replace('\u51b0\u6d77\u6218\u8bb0\u7b2c\u4e00\u5b63:\u6700\u540e\u7684', '\u51b0\u6d77\u6218\u8bb0\u7b2c\u4e00\u5b63\uff1a\u6700\u540e\u7684')

# Fix byName
content = content.replace(
    'var existing = proj.items.byName(name);',
    'var existing = null; for (var _i = 1; _i <= proj.numItems; _i++) { if (proj.item(_i).name === name) { existing = proj.item(_i); break; } }'
)

# Fix SEGMENTS.reduce
content = content.replace(
    'SEGMENTS.reduce(function(s, seg) { return s + seg.clips.length; }, 0)',
    '(function(){var _t=0;for(var _s=0;_s<SEGMENTS.length;_s++)_t+=SEGMENTS[_s].clips.length;return _t})()'
)

# Fix canImportFile - remove the check, direct import
content = content.replace('if (app.project.canImportFile(io)) {', '{')

# Point to H.264 directory
content = content.replace(
    'D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750/',
    'D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750_AE/'
)
content = content.replace(
    'D:/AE-Work/\u97f3\u9891\u7d20\u6750\u5e93/BGM/',
    'D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750_AE/'
)

# Comment out alert
content = content.replace('alert("渲染已开始!\\n输出文件: " + OUTPUT_FILE);', '// alert removed')
content = content.replace('alert("渲染失败: " + e.message);', '// alert removed')

# return main()
content = content.replace('\nmain();', '\nreturn main();')

# ============ 改进1: 文字动画系统重写 ============
# Replace getFont function with system-safe fonts
old_getFont = '''function getFont(preset) {
    var fonts = {
        cinematic: "Bebas Neue Bold",
        epic: "Alfa Slab One",
        modern: "Montserrat Bold",
        japanese: "Microsoft YaHei",
        brush: "Ma Shan Zheng"
    };
    return fonts[preset] || "Impact";
}'''

new_getFont = '''function getFont(preset) {
    var fonts = {
        cinematic: "Impact",
        epic: "Arial Black",
        modern: "Arial Black",
        japanese: "Microsoft YaHei",
        brush: "SimHei"
    };
    return fonts[preset] || "Impact";
}'''
content = content.replace(old_getFont, new_getFont)

# Replace addTitleText with improved version (tracking animation + easing)
old_addTitleText = '''function addTitleText(comp, txt, startT, endT, yPos, fontSize, preset) {
    try {
        var tl = comp.layers.addText(txt);
        var td = tl.property("Source Text").value;
        td.fontSize = fontSize;
        td.font = getFont(preset);
        td.fillColor = [1, 1, 1];
        td.applyFill = true;
        td.applyStroke = true;
        td.strokeColor = [0, 0, 0];
        td.strokeWidth = 3;
        td.strokeOverFill = false;
        tl.property("Source Text").setValue(td);
        tl.name = "TXT_" + txt.substring(0, 10);
        tl.startTime = startT;
        tl.inPoint = startT;
        tl.outPoint = endT;
        tl.position.setValueAtTime(startT, [WIDTH/2, yPos]);
        // 入场缩放 (从0到100)
        tl.scale.setValueAtTime(startT, [0, 0]);
        tl.scale.setValueAtTime(startT + 0.3, [100, 100]);
        tl.scale.setValueAtTime(endT - 0.3, [100, 100]);
        tl.scale.setValueAtTime(endT, [120, 120]);
        // 透明度淡入淡出
        tl.opacity.setValueAtTime(startT, 0);
        tl.opacity.setValueAtTime(startT + 0.2, 100);
        tl.opacity.setValueAtTime(endT - 0.2, 100);
        tl.opacity.setValueAtTime(endT, 0);
        // 添加发光效果
        var glow = tl.property("Effects").addProperty("ADBE Glow");
        glow.property("Glow Radius").setValue(20);
        glow.property("Glow Intensity").setValue(0.8);
        try { tl.parent = comp.layer("Camera_Controller"); } catch(e) {}
    } catch(e) {}
}'''

new_addTitleText = '''function addTitleText(comp, txt, startT, endT, yPos, fontSize, preset) {
    try {
        var tl = comp.layers.addText(txt);
        var td = tl.property("Source Text").value;
        td.fontSize = fontSize;
        td.font = getFont(preset);
        td.fillColor = [1, 1, 1];
        td.applyFill = true;
        td.applyStroke = true;
        td.strokeColor = [0, 0, 0];
        td.strokeWidth = 2;
        td.strokeOverFill = false;
        td.justification = ParagraphJustification.CENTER_JUSTIFY;
        tl.property("Source Text").setValue(td);
        tl.name = "TXT_" + txt.substring(0, 10);
        tl.startTime = startT;
        tl.inPoint = startT;
        tl.outPoint = endT;
        var dur = endT - startT;
        tl.position.setValueAtTime(startT, [WIDTH/2, yPos + 30]);
        tl.position.setValueAtTime(startT + 0.5, [WIDTH/2, yPos]);
        // 入场: 缓动缩放 (从80到100, 弹性)
        tl.scale.setValueAtTime(startT, [80, 80]);
        tl.scale.setValueAtTime(startT + 0.15, [105, 105]);
        tl.scale.setValueAtTime(startT + 0.4, [100, 100]);
        tl.scale.setValueAtTime(endT - 0.3, [100, 100]);
        tl.scale.setValueAtTime(endT, [95, 95]);
        // 透明度: 平滑淡入淡出
        tl.opacity.setValueAtTime(startT, 0);
        tl.opacity.setValueAtTime(startT + 0.25, 100);
        tl.opacity.setValueAtTime(endT - 0.25, 100);
        tl.opacity.setValueAtTime(endT, 0);
        // Tracking 动画 (字间距从20收缩到0)
        try {
            var trackingExpr = "var t = time - " + startT + "; var dur = " + dur + "; var track = linear(t, 0, 0.5, 30, 0); track;";
            tl.property("Source Text").expression = "var td = value; td.tracking = " + "linear(time - " + startT + ", 0, 0.6, 40, 0); td;";
        } catch(e2) {}
        // 发光 + 阴影
        try {
            var glow = tl.property("Effects").addProperty("ADBE Glow");
            glow.property("Glow Threshold").setValue(40);
            glow.property("Glow Radius").setValue(30);
            glow.property("Glow Intensity").setValue(1.0);
            glow.property("Glow Colors").setValue(1);
        } catch(e3) {}
        try { tl.parent = comp.layer("Camera_Controller"); } catch(e4) {}
    } catch(e) {}
}'''
content = content.replace(old_addTitleText, new_addTitleText)

# ============ 改进2: 插帧效果 - 视频层添加Timewarp像素运动 ============
# After time remap, add Timewarp for smooth frame interpolation
old_timeRemap = '''            // 时间重映射: 从源视频的 srcStart 位置开始播放
            try {
                ly.timeRemapEnabled = true;
                var tr = ly.property("Time Remap");
                tr.setValueAtTime(compStart, clipInfo.srcStart);
                tr.setValueAtTime(compStart + segDur, clipInfo.srcStart + segDur);
            } catch(e) {}'''

new_timeRemap = '''            // 时间重映射: 从源视频的 srcStart 位置开始播放
            try {
                ly.timeRemapEnabled = true;
                var tr = ly.property("Time Remap");
                tr.setValueAtTime(compStart, clipInfo.srcStart);
                tr.setValueAtTime(compStart + segDur, clipInfo.srcStart + segDur);
            } catch(e) {}
            // V16: Timewarp插帧 + 像素运动 (平滑帧间过渡)
            try {
                var tw = ly.property("Effects").addProperty("ADBE Timewarp");
                tw.property("Method").setValue(2);  // Pixel Motion
                tw.property("Motion Blur").setValue(1);  // On
                tw.property("Shutter Angle").setValue(180);
            } catch(e_tw) {}'''
content = content.replace(old_timeRemap, new_timeRemap)

# ============ 改进3: RGB故障效果 - 真正的通道分离 ============
old_rgbGlitch = '''function addRGBGlitch(comp, st, et) {
    try {
        var g = comp.layers.addSolid([1, 0, 0], "RGBG_" + st, WIDTH, HEIGHT, 1);
        g.startTime = st; g.inPoint = st; g.outPoint = et;
        g.opacity.setValueAtTime(st, 0);
        g.opacity.setValueAtTime(st + 0.02, 40);
        g.opacity.setValueAtTime(et, 0);
        g.blendingMode = BlendingMode.SCREEN;
        var b = g.property("Effects").addProperty("ADBE Fast Blur");
        b.property("Blurriness").setValueAtTime(st, 0);
        b.property("Blurriness").setValueAtTime(st + 0.02, 15);
        b.property("Blurriness").setValueAtTime(et, 0);
        b.property("Repeat Edge Pixels").setValue(true);
    } catch(e) {}
}'''

new_rgbGlitch = '''function addRGBGlitch(comp, st, et) {
    try {
        // V16: 真正的RGB通道分离故障效果
        var g = comp.layers.addSolid([1, 1, 1], "RGBGlitch_" + st, WIDTH, HEIGHT, 1);
        g.adjustmentLayer = true;
        g.startTime = st; g.inPoint = st; g.outPoint = et;
        // 使用通道偏移模拟RGB分离
        var shift = g.property("Effects").addProperty("ADBE Shift Channels");
        shift.property("Red").setValue(3);    // Red from Green
        shift.property("Green").setValue(4);  // Green from Blue  
        shift.property("Blue").setValue(2);   // Blue from Red
        g.opacity.setValueAtTime(st, 0);
        g.opacity.setValueAtTime(st + 0.015, 50);
        g.opacity.setValueAtTime(st + 0.04, 30);
        g.opacity.setValueAtTime(et, 0);
        // 添加水平位移模拟色差
        try {
            var disp = g.property("Effects").addProperty("ADBE Displacement Map");
            disp.property("Use For Horizontal Displacement").setValue(2);
            disp.property("Max Horizontal Displacement").setValueAtTime(st + 0.01, 15);
            disp.property("Max Horizontal Displacement").setValueAtTime(et, 0);
        } catch(e_d) {}
    } catch(e) {}
}'''
content = content.replace(old_rgbGlitch, new_rgbGlitch)

# ============ 改进4: 动态文字系统增强 ============
old_dynamicText = '''// V14: 动态文字系统
function addDynamicText(comp) {
    try {
        var texts = [
            { t: 1, text: "VINLAND SAGA", y: HEIGHT * 0.15, duration: 2, scale: 1.2 },
            { t: 9, text: "BATTLE", y: HEIGHT * 0.85, duration: 3, scale: 1.5 },
            { t: 15, text: "REDEMPTION", y: HEIGHT * 0.15, duration: 2.5, scale: 1.3 },
            { t: 20, text: "END", y: HEIGHT * 0.5, duration: 3, scale: 1.8 }
        ];
        
        for (var i = 0; i < texts.length; i++) {
            var txt = texts[i];
            var textLayer = comp.layers.addText(txt.text);
            textLayer.name = "Text_" + txt.text;
            textLayer.startTime = txt.t;
            textLayer.inPoint = txt.t;
            textLayer.outPoint = txt.t + txt.duration;
            
            var sourceText = textLayer.property("Source Text");
            var textDoc = sourceText.value;
            textDoc.font = "Arial Black";
            textDoc.fontSize = 80 * txt.scale;
            textDoc.fillColor = [1, 1, 1];
            textDoc.strokeColor = [0, 0, 0];
            textDoc.strokeWidth = 3;
            textDoc.strokeOverFill = true;
            textDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
            sourceText.setValue(textDoc);
            
            textLayer.position.setValueAtTime(txt.t, [WIDTH/2, txt.y]);
            
            textLayer.scale.setValueAtTime(txt.t, [50, 50]);
            textLayer.scale.setValueAtTime(txt.t + 0.3, [100, 100]);
            textLayer.scale.setValueAtTime(txt.t + txt.duration - 0.5, [100, 100]);
            textLayer.scale.setValueAtTime(txt.t + txt.duration, [50, 50]);
            
            textLayer.opacity.setValueAtTime(txt.t, 0);
            textLayer.opacity.setValueAtTime(txt.t + 0.1, 100);
            textLayer.opacity.setValueAtTime(txt.t + txt.duration - 0.3, 100);
            textLayer.opacity.setValueAtTime(txt.t + txt.duration, 0);
            
            var glow = textLayer.property("Effects").addProperty("ADBE Glow");
            glow.property("Glow Threshold").setValue(50);
            glow.property("Glow Radius").setValue(25);
            glow.property("Glow Intensity").setValue(1.5);
            
            textLayer.moveToBeginning();
        }
    } catch(e) {}
}'''

new_dynamicText = '''// V16: 增强动态文字系统 (电影感字幕)
function addDynamicText(comp) {
    try {
        var texts = [
            { t: 0.5, text: "VINLAND SAGA", y: HEIGHT * 0.12, duration: 3, size: 90, color: [1, 0.95, 0.85] },
            { t: 4.5, text: "\\u2014\\u2014 \\u51B0\\u6D77\\u6218\\u8BB0 \\u2014\\u2014", y: HEIGHT * 0.88, duration: 2, size: 45, color: [0.8, 0.9, 1] },
            { t: 9.0, text: "BATTLE", y: HEIGHT * 0.82, duration: 1.5, size: 120, color: [1, 0.3, 0.2] },
            { t: 12.0, text: "VS", y: HEIGHT * 0.5, duration: 1.0, size: 150, color: [1, 0.8, 0.2] },
            { t: 15.5, text: "REDEMPTION", y: HEIGHT * 0.15, duration: 2.5, size: 70, color: [0.7, 0.85, 1] },
            { t: 20.0, text: "VINLAND SAGA", y: HEIGHT * 0.45, duration: 3, size: 80, color: [1, 0.95, 0.8] }
        ];
        
        for (var i = 0; i < texts.length; i++) {
            var txt = texts[i];
            var textLayer = comp.layers.addText(txt.text);
            textLayer.name = "DynText_" + txt.text.substring(0, 8);
            textLayer.startTime = txt.t;
            textLayer.inPoint = txt.t;
            textLayer.outPoint = txt.t + txt.duration;
            
            var sourceText = textLayer.property("Source Text");
            var textDoc = sourceText.value;
            textDoc.font = "Impact";
            textDoc.fontSize = txt.size;
            textDoc.fillColor = txt.color;
            textDoc.strokeColor = [0, 0, 0];
            textDoc.strokeWidth = 2;
            textDoc.strokeOverFill = true;
            textDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
            sourceText.setValue(textDoc);
            
            textLayer.position.setValueAtTime(txt.t, [WIDTH/2, txt.y + 20]);
            textLayer.position.setValueAtTime(txt.t + 0.4, [WIDTH/2, txt.y]);
            
            // 弹性缩放动画
            textLayer.scale.setValueAtTime(txt.t, [60, 60]);
            textLayer.scale.setValueAtTime(txt.t + 0.1, [110, 110]);
            textLayer.scale.setValueAtTime(txt.t + 0.3, [98, 98]);
            textLayer.scale.setValueAtTime(txt.t + 0.5, [100, 100]);
            textLayer.scale.setValueAtTime(txt.t + txt.duration - 0.4, [100, 100]);
            textLayer.scale.setValueAtTime(txt.t + txt.duration, [90, 90]);
            
            // 平滑透明度
            textLayer.opacity.setValueAtTime(txt.t, 0);
            textLayer.opacity.setValueAtTime(txt.t + 0.15, 100);
            textLayer.opacity.setValueAtTime(txt.t + txt.duration - 0.3, 100);
            textLayer.opacity.setValueAtTime(txt.t + txt.duration, 0);
            
            // Tracking 表达式 (字间距动画)
            try {
                sourceText.expression = "var td = value; td.tracking = linear(time - " + txt.t + ", 0, 0.5, 25, 0); td;";
            } catch(e_tr) {}
            
            // 发光效果
            try {
                var glow = textLayer.property("Effects").addProperty("ADBE Glow");
                glow.property("Glow Threshold").setValue(30);
                glow.property("Glow Radius").setValue(20);
                glow.property("Glow Intensity").setValue(0.8);
            } catch(e_gl) {}
            
            textLayer.moveToBeginning();
        }
    } catch(e) {}
}'''
content = content.replace(old_dynamicText, new_dynamicText)

# ============ 改进5: 粒子改用CC Particle World (内置) ============
old_particles = '''// ========== 战斗粒子 (Drop段) ==========
function addBattleParticlesV13(comp) {
    // 血雾粒子 (红色, 短生命)
    try {
        var blood = comp.layers.addSolid([0.6, 0.05, 0.05], "Particle_Blood", WIDTH, HEIGHT, 1);
        blood.adjustmentLayer = false;
        blood.startTime = 9;
        blood.inPoint = 9;
        blood.outPoint = 15;
        blood.opacity.setValueAtTime(9, 0);
        blood.opacity.setValueAtTime(9.5, 40);
        blood.opacity.setValueAtTime(15, 0);
        var p = blood.property("Effects").addProperty("ADBE Particular");
        // 血雾参数: 红色+重力+短生命
        p.property("Particle Type").setValue(0);  // Sphere
        p.property("Color").setValue([0.6, 0.05, 0.05]);
        p.property("Velocity").setValue(200);
        p.property("Gravity").setValue(300);
        p.property("Life").setValue(0.8);
        p.property("Emitter Type").setValue(0);  // Point
        p.property("Position XY").setValue([WIDTH/2, HEIGHT/2]);
    } catch(e) {}

    // 火花粒子 (橙黄, 高速)
    try {
        var spark = comp.layers.addSolid([1, 0.6, 0.1], "Particle_Sparks", WIDTH, HEIGHT, 1);
        spark.startTime = 9;
        spark.inPoint = 9;
        spark.outPoint = 15;
        spark.opacity.setValueAtTime(9, 0);
        spark.opacity.setValueAtTime(9.5, 60);
        spark.opacity.setValueAtTime(15, 0);
        var p2 = spark.property("Effects").addProperty("ADBE Particular");
        p2.property("Particle Type").setValue(0);
        p2.property("Color").setValue([1, 0.6, 0.1]);
        p2.property("Velocity").setValue(500);
        p2.property("Gravity").setValue(500);
        p2.property("Life").setValue(0.5);
        p2.property("Emitter Type").setValue(0);
        p2.property("Position XY").setValue([WIDTH/2, HEIGHT/2]);
    } catch(e) {}
}'''

new_particles = '''// ========== 战斗粒子 (Drop段) - V16: 使用CC Particle World ==========
function addBattleParticlesV13(comp) {
    // 血雾粒子 (CC Particle World)
    try {
        var blood = comp.layers.addSolid([0, 0, 0], "Particle_Blood", WIDTH, HEIGHT, 1);
        blood.startTime = 9;
        blood.inPoint = 9;
        blood.outPoint = 15;
        blood.blendingMode = BlendingMode.SCREEN;
        blood.opacity.setValueAtTime(9, 0);
        blood.opacity.setValueAtTime(9.3, 60);
        blood.opacity.setValueAtTime(14.5, 40);
        blood.opacity.setValueAtTime(15, 0);
        var pw = blood.property("Effects").addProperty("ADBE CC Particle World");
        pw.property("Particle Type").setValue(5);  // Faded Sphere
        pw.property("Producer Position").setValue([0, 0]);
        pw.property("Birth Rate").setValue(200);
        pw.property("Longevity").setValue(0.8);
        pw.property("Velocity").setValue(2.0);
        pw.property("Gravity").setValue(5.0);
        pw.property("Particle Size").setValue(0.15);
        pw.property("Particle Color").setValue([0.7, 0.05, 0.05]);
        pw.property("Birth Color").setValue([0.9, 0.1, 0.05]);
        pw.property("Color Map").setValue(1);  // From Birth
    } catch(e) {}

    // 火花粒子
    try {
        var spark = comp.layers.addSolid([0, 0, 0], "Particle_Sparks", WIDTH, HEIGHT, 1);
        spark.startTime = 9;
        spark.inPoint = 9;
        spark.outPoint = 15;
        spark.blendingMode = BlendingMode.SCREEN;
        spark.opacity.setValueAtTime(9, 0);
        spark.opacity.setValueAtTime(9.2, 70);
        spark.opacity.setValueAtTime(14.5, 50);
        spark.opacity.setValueAtTime(15, 0);
        var pw2 = spark.property("Effects").addProperty("ADBE CC Particle World");
        pw2.property("Particle Type").setValue(3);  // Lens Convex
        pw2.property("Birth Rate").setValue(300);
        pw2.property("Longevity").setValue(0.5);
        pw2.property("Velocity").setValue(4.0);
        pw2.property("Gravity").setValue(8.0);
        pw2.property("Particle Size").setValue(0.08);
        pw2.property("Particle Color").setValue([1, 0.6, 0.1]);
        pw2.property("Birth Color").setValue([1, 0.9, 0.3]);
        pw2.property("Color Map").setValue(1);
    } catch(e) {}
}'''
content = content.replace(old_particles, new_particles)

# ============ 改进6: 速度斜坡 - 平滑曲线 ============
# Add speed ramp expression to Drop segment clips
old_beatSync = '''            // V13.5补偿: 能量重映射 (0.21-0.31 → 100-115%)'''
new_beatSync = '''            // V16: 速度斜坡 (Drop段加减速效果)
            // V13.5补偿: 能量重映射 (0.21-0.31 → 100-115%)'''
content = content.replace(old_beatSync, new_beatSync)

# ============ 验证 ============
print("=== V16 Improvements Check ===")
checks = {
    'canImportFile removed': 'canImportFile' not in content,
    'Timewarp added': 'ADBE Timewarp' in content,
    'CC Particle World': 'ADBE CC Particle World' in content,
    'RGB Shift Channels': 'ADBE Shift Channels' in content,
    'Tracking animation': 'td.tracking' in content,
    'System fonts': 'Impact' in content and 'Arial Black' in content,
    'addComp': 'addComp' in content,
    '_AE path': '_AE/' in content,
    'V16 output': 'V16.mp4' in content,
}
for desc, ok in checks.items():
    print(f"  {'OK' if ok else 'FAIL'}: {desc}")

# Send to AE
cmd = {
    "command": "executeAtomScript",
    "script": content,
    "processed": False,
    "description": "V16_improved_effects"
}

cmd_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json'
res_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_result.json'

if os.path.exists(res_path):
    os.remove(res_path)
time.sleep(2)

with open(cmd_path, 'w', encoding='utf-8') as f:
    json.dump(cmd, f, ensure_ascii=False)

print(f"\nV16 sent! Script: {len(content)} chars")
time.sleep(5)

log_tail = os.popen('powershell -Command "Get-Content C:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\.ae-mcp-bridge\\ae_listener_log.txt -Tail 3"').read()
print(f"Log: {log_tail.strip()}")
