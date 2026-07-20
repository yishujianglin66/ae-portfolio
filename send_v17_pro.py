import json, os, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('D:/AE-Work/output/vinland_saga_v15_build.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# ============ 基础修复 (同V16) ============
content = content.replace('Adobe After Effects 2026', 'Adobe After Effects 2025')
content = content.replace('VinlandSaga_Battle_V14_safe.mp4', 'VinlandSaga_Battle_V17.mp4')
content = content.replace('V14_safe', 'V17')
content = content.replace('VinlandSaga_Cinematic_V14', 'VinlandSaga_Cinematic_V17')
content = content.replace('.items.addComposition(', '.items.addComp(')
content = content.replace('p03 S2OP2-Dark Crow', 'p03 S1OP2-Dark Crow')
content = content.replace('\u51b0\u6d77\u6218\u8bb0\u7b2c\u4e00\u5b63:\u6700\u540e\u7684', '\u51b0\u6d77\u6218\u8bb0\u7b2c\u4e00\u5b63\uff1a\u6700\u540e\u7684')
content = content.replace(
    'var existing = proj.items.byName(name);',
    'var existing = null; for (var _i = 1; _i <= proj.numItems; _i++) { if (proj.item(_i).name === name) { existing = proj.item(_i); break; } }'
)
content = content.replace(
    'SEGMENTS.reduce(function(s, seg) { return s + seg.clips.length; }, 0)',
    '(function(){var _t=0;for(var _s=0;_s<SEGMENTS.length;_s++)_t+=SEGMENTS[_s].clips.length;return _t})()'
)
content = content.replace('if (app.project.canImportFile(io)) {', '{')
content = content.replace(
    'D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750/',
    'D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750_AE/'
)
content = content.replace(
    'D:/AE-Work/\u97f3\u9891\u7d20\u6750\u5e93/BGM/',
    'D:/AE-Work/\u89c6\u9891\u7d20\u6750\u5e93/\u51b0\u6d77\u6218\u8bb0\u65b0\u7d20\u6750_AE/'
)
content = content.replace('alert("\u6e32\u67d3\u5df2\u5f00\u59cb!\\n\u8f93\u51fa\u6587\u4ef6: " + OUTPUT_FILE);', '// done')
content = content.replace('alert("\u6e32\u67d3\u5931\u8d25: " + e.message);', '// fail')
content = content.replace('\nmain();', '\nreturn main();')

# ============ V17改进1: 字体系统 (使用已安装字体) ============
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
        cinematic: "DINNextLTPro-Bold",
        epic: "Impact",
        modern: "Arial Black",
        japanese: "AlibabaPuHuiTi-3-45-Light",
        brush: "STHUPO",
        bold_cn: "SimHei",
        serif_cn: "NotoSerifSC-VF",
        bold_en: "DINNextLTPro-Bold"
    };
    return fonts[preset] || "Impact";
}'''
content = content.replace(old_getFont, new_getFont)

# ============ V17改进2: 专业电影字幕系统 ============
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
        td.strokeWidth = 1.5;
        td.strokeOverFill = false;
        td.justification = ParagraphJustification.CENTER_JUSTIFY;
        tl.property("Source Text").setValue(td);
        tl.name = "TXT_" + txt.substring(0, 10);
        tl.startTime = startT;
        tl.inPoint = startT;
        tl.outPoint = endT;
        var dur = endT - startT;
        // 位置: 从下方20px滑入
        tl.position.setValueAtTime(startT, [WIDTH/2, yPos + 25]);
        tl.position.setValueAtTime(startT + 0.4, [WIDTH/2, yPos]);
        // 弹性缩放 (80->108->100)
        tl.scale.setValueAtTime(startT, [80, 80]);
        tl.scale.setValueAtTime(startT + 0.12, [108, 108]);
        tl.scale.setValueAtTime(startT + 0.35, [100, 100]);
        tl.scale.setValueAtTime(endT - 0.25, [100, 100]);
        tl.scale.setValueAtTime(endT, [96, 96]);
        // 平滑透明度
        tl.opacity.setValueAtTime(startT, 0);
        tl.opacity.setValueAtTime(startT + 0.2, 100);
        tl.opacity.setValueAtTime(endT - 0.2, 100);
        tl.opacity.setValueAtTime(endT, 0);
        // Tracking字距动画
        try {
            var srcProp = tl.property("Source Text");
            srcProp.expression = "var td = value; td.tracking = linear(time - " + startT + ", 0, 0.5, 30, 0); td;";
        } catch(e2) {}
        // 发光
        try {
            var glow = tl.property("Effects").addProperty("ADBE Glow");
            glow.property("Glow Threshold").setValue(35);
            glow.property("Glow Radius").setValue(25);
            glow.property("Glow Intensity").setValue(0.9);
        } catch(e3) {}
        try { tl.parent = comp.layer("Camera_Controller"); } catch(e4) {}
    } catch(e) {}
}'''
content = content.replace(old_addTitleText, new_addTitleText)

# ============ V17改进3: 电影感字幕内容 (叙事感) ============
old_textSystem = '''// ========== 文字系统 ==========
function addCinematicTextSystem(comp) {
    // Intro 标题 (1.0s 出现, 3.0s 消失)
    addTitleText(comp, "VINLAND SAGA", 1.0, 3.0, HEIGHT/2 - 200, 80, "cinematic");
    addTitleText(comp, "冰 海 战 记", 1.5, 3.0, HEIGHT/2 - 120, 50, "japanese");

    // Outro 收尾标题 (20.5s 出现, 23.15s)
    addTitleText(comp, "VINLAND SAGA", 20.5, 23.15, HEIGHT/2 - 100, 80, "cinematic");
    addTitleText(comp, "- END -", 21.0, 23.15, HEIGHT/2 + 50, 40, "modern");

    // Drop段战斗字幕 (节拍对齐)
    var dropBeats = getBeatsInRange(9, 15);
    var fightTexts = ["战", "斗", "提尔芬", "VS", "蛇"];
    for (var i = 0; i < Math.min(dropBeats.length, fightTexts.length); i++) {
        addTitleText(comp, fightTexts[i],
            dropBeats[i] - VISUAL_ADVANCE,
            dropBeats[i] + 0.5 - VISUAL_ADVANCE,
            HEIGHT/2 + 400, 100, "epic");
    }
}'''
new_textSystem = '''// ========== V17 电影感字幕系统 ==========
function addCinematicTextSystem(comp) {
    // === Intro: 史诗开场 ===
    addTitleText(comp, "VINLAND SAGA", 0.5, 3.5, HEIGHT*0.10, 72, "cinematic");
    addTitleText(comp, "\\u51B0\\u6D77\\u6218\\u8BB0", 1.0, 3.5, HEIGHT*0.17, 48, "bold_cn");
    addTitleText(comp, "\\u2014\\u2014 \\u6218\\u58EB\\u7684\\u53F2\\u8BD7 \\u2014\\u2014", 2.0, 3.8, HEIGHT*0.22, 28, "serif_cn");

    // === Build: 情绪铺垫 ===
    addTitleText(comp, "\\u5F53\\u6218\\u4E89\\u7684\\u706B\\u7130\\u518D\\u6B21\\u71C3\\u8D77", 5.0, 7.5, HEIGHT*0.85, 32, "bold_cn");
    addTitleText(comp, "THE SAGA CONTINUES", 7.5, 9.0, HEIGHT*0.88, 24, "cinematic");

    // === Drop: 战斗字幕 (节拍精准对齐) ===
    var dropBeats = getBeatsInRange(9, 15);
    var fightTexts = ["\\u6218", "\\u6597", "\\u63D0\\u5C14\\u82AC", "VS", "\\u86C7"];
    for (var i = 0; i < Math.min(dropBeats.length, fightTexts.length); i++) {
        addTitleText(comp, fightTexts[i],
            dropBeats[i] - VISUAL_ADVANCE,
            dropBeats[i] + 0.5 - VISUAL_ADVANCE,
            HEIGHT*0.78, 90, "epic");
    }

    // === Break: 情感留白 ===
    addTitleText(comp, "\\u6218\\u4E89\\u4E4B\\u540E\\u2026\\u2026", 15.5, 17.5, HEIGHT*0.50, 36, "serif_cn");
    addTitleText(comp, "REDEMPTION", 17.0, 18.8, HEIGHT*0.55, 28, "cinematic");

    // === Outro: 史诗收尾 ===
    addTitleText(comp, "VINLAND SAGA", 19.5, 22.5, HEIGHT*0.40, 72, "cinematic");
    addTitleText(comp, "\\u51B0\\u6D77\\u6218\\u8BB0", 20.0, 22.5, HEIGHT*0.47, 48, "bold_cn");
    addTitleText(comp, "- FIN -", 21.5, 23.0, HEIGHT*0.55, 36, "cinematic");
}'''
content = content.replace(old_textSystem, new_textSystem)

# ============ V17改进4: 动态文字增强 ============
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
new_dynamicText = '''// V17: 增强动态文字 (使用DIN/阿里巴巴字体)
function addDynamicText(comp) {
    try {
        var texts = [
            { t: 0.3, text: "VINLAND SAGA", y: HEIGHT*0.08, dur: 3.5, size: 80, font: "DINNextLTPro-Bold", color: [1, 0.95, 0.85] },
            { t: 4.2, text: "\\u2014\\u2014 \\u51B0\\u6D77\\u6218\\u8BB0 \\u2014\\u2014", y: HEIGHT*0.90, dur: 2.5, size: 38, font: "AlibabaPuHuiTi-3-45-Light", color: [0.8, 0.9, 1] },
            { t: 9.0, text: "BATTLE", y: HEIGHT*0.80, dur: 1.8, size: 110, font: "Impact", color: [1, 0.25, 0.15] },
            { t: 12.0, text: "VS", y: HEIGHT*0.48, dur: 1.0, size: 140, font: "Impact", color: [1, 0.75, 0.1] },
            { t: 15.3, text: "REDEMPTION", y: HEIGHT*0.12, dur: 3.0, size: 60, font: "DINNextLTPro-Bold", color: [0.7, 0.85, 1] },
            { t: 19.5, text: "VINLAND SAGA", y: HEIGHT*0.38, dur: 3.5, size: 75, font: "DINNextLTPro-Bold", color: [1, 0.92, 0.78] }
        ];
        
        for (var i = 0; i < texts.length; i++) {
            var txt = texts[i];
            var tl = comp.layers.addText(txt.text);
            tl.name = "Dyn_" + txt.text.substring(0, 6);
            tl.startTime = txt.t;
            tl.inPoint = txt.t;
            tl.outPoint = txt.t + txt.dur;
            
            var td = tl.property("Source Text").value;
            td.font = txt.font;
            td.fontSize = txt.size;
            td.fillColor = txt.color;
            td.strokeColor = [0, 0, 0];
            td.strokeWidth = 1.5;
            td.strokeOverFill = true;
            td.justification = ParagraphJustification.CENTER_JUSTIFY;
            tl.property("Source Text").setValue(td);
            
            // 位置滑入
            tl.position.setValueAtTime(txt.t, [WIDTH/2, txt.y + 20]);
            tl.position.setValueAtTime(txt.t + 0.35, [WIDTH/2, txt.y]);
            
            // 弹性缩放
            tl.scale.setValueAtTime(txt.t, [70, 70]);
            tl.scale.setValueAtTime(txt.t + 0.1, [108, 108]);
            tl.scale.setValueAtTime(txt.t + 0.3, [98, 98]);
            tl.scale.setValueAtTime(txt.t + 0.5, [100, 100]);
            tl.scale.setValueAtTime(txt.t + txt.dur - 0.3, [100, 100]);
            tl.scale.setValueAtTime(txt.t + txt.dur, [92, 92]);
            
            // 透明度
            tl.opacity.setValueAtTime(txt.t, 0);
            tl.opacity.setValueAtTime(txt.t + 0.15, 100);
            tl.opacity.setValueAtTime(txt.t + txt.dur - 0.25, 100);
            tl.opacity.setValueAtTime(txt.t + txt.dur, 0);
            
            // Tracking动画
            try {
                tl.property("Source Text").expression = "var td = value; td.tracking = linear(time - " + txt.t + ", 0, 0.5, 25, 0); td;";
            } catch(e_tr) {}
            
            // 发光
            try {
                var glow = tl.property("Effects").addProperty("ADBE Glow");
                glow.property("Glow Threshold").setValue(30);
                glow.property("Glow Radius").setValue(20);
                glow.property("Glow Intensity").setValue(0.7);
            } catch(e_gl) {}
            
            tl.moveToBeginning();
        }
    } catch(e) {}
}'''
content = content.replace(old_dynamicText, new_dynamicText)

# ============ V17改进5: Timewarp插帧 (同V16) ============
old_timeRemap = '''            // 时间重映射: 从源视频的 srcStart 位置开始播放
            try {
                ly.timeRemapEnabled = true;
                var tr = ly.property("Time Remap");
                tr.setValueAtTime(compStart, clipInfo.srcStart);
                tr.setValueAtTime(compStart + segDur, clipInfo.srcStart + segDur);
            } catch(e) {}'''
new_timeRemap = '''            // 时间重映射
            try {
                ly.timeRemapEnabled = true;
                var tr = ly.property("Time Remap");
                tr.setValueAtTime(compStart, clipInfo.srcStart);
                tr.setValueAtTime(compStart + segDur, clipInfo.srcStart + segDur);
            } catch(e) {}
            // V17: Timewarp像素运动插帧
            try {
                var tw = ly.property("Effects").addProperty("ADBE Timewarp");
                tw.property("Method").setValue(2);
                tw.property("Motion Blur").setValue(1);
                tw.property("Shutter Angle").setValue(180);
            } catch(e_tw) {}'''
content = content.replace(old_timeRemap, new_timeRemap)

# ============ V17改进6: RGB通道分离故障 ============
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
        var g = comp.layers.addSolid([1, 1, 1], "RGBGlitch_" + st, WIDTH, HEIGHT, 1);
        g.adjustmentLayer = true;
        g.startTime = st; g.inPoint = st; g.outPoint = et;
        var shift = g.property("Effects").addProperty("ADBE Shift Channels");
        shift.property("Red").setValue(3);
        shift.property("Green").setValue(4);
        shift.property("Blue").setValue(2);
        g.opacity.setValueAtTime(st, 0);
        g.opacity.setValueAtTime(st + 0.015, 45);
        g.opacity.setValueAtTime(st + 0.04, 25);
        g.opacity.setValueAtTime(et, 0);
    } catch(e) {}
}'''
content = content.replace(old_rgbGlitch, new_rgbGlitch)

# ============ V17改进7: CC Particle World ============
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
new_particles = '''// ========== V17: 战斗粒子 (CC Particle World) ==========
function addBattleParticlesV13(comp) {
    try {
        var blood = comp.layers.addSolid([0, 0, 0], "Particle_Blood", WIDTH, HEIGHT, 1);
        blood.startTime = 9; blood.inPoint = 9; blood.outPoint = 15;
        blood.blendingMode = BlendingMode.SCREEN;
        blood.opacity.setValueAtTime(9, 0);
        blood.opacity.setValueAtTime(9.3, 55);
        blood.opacity.setValueAtTime(14.5, 35);
        blood.opacity.setValueAtTime(15, 0);
        var pw = blood.property("Effects").addProperty("ADBE CC Particle World");
        pw.property("Particle Type").setValue(5);
        pw.property("Birth Rate").setValue(180);
        pw.property("Longevity").setValue(0.8);
        pw.property("Velocity").setValue(1.8);
        pw.property("Gravity").setValue(4.0);
        pw.property("Particle Size").setValue(0.12);
        pw.property("Birth Color").setValue([0.9, 0.08, 0.05]);
        pw.property("Death Color").setValue([0.3, 0.02, 0.02]);
        pw.property("Color Map").setValue(1);
    } catch(e) {}
    try {
        var spark = comp.layers.addSolid([0, 0, 0], "Particle_Sparks", WIDTH, HEIGHT, 1);
        spark.startTime = 9; spark.inPoint = 9; spark.outPoint = 15;
        spark.blendingMode = BlendingMode.SCREEN;
        spark.opacity.setValueAtTime(9, 0);
        spark.opacity.setValueAtTime(9.2, 65);
        spark.opacity.setValueAtTime(14.5, 45);
        spark.opacity.setValueAtTime(15, 0);
        var pw2 = spark.property("Effects").addProperty("ADBE CC Particle World");
        pw2.property("Particle Type").setValue(3);
        pw2.property("Birth Rate").setValue(250);
        pw2.property("Longevity").setValue(0.4);
        pw2.property("Velocity").setValue(3.5);
        pw2.property("Gravity").setValue(6.0);
        pw2.property("Particle Size").setValue(0.06);
        pw2.property("Birth Color").setValue([1, 0.85, 0.2]);
        pw2.property("Death Color").setValue([1, 0.3, 0.05]);
        pw2.property("Color Map").setValue(1);
    } catch(e) {}
}'''
content = content.replace(old_particles, new_particles)

# ============ 验证 ============
print("=== V17 Improvements ===")
checks = {
    'canImportFile removed': 'canImportFile' not in content,
    'Timewarp': 'ADBE Timewarp' in content,
    'CC Particle World': 'ADBE CC Particle World' in content,
    'RGB Shift Channels': 'ADBE Shift Channels' in content,
    'DIN font': 'DINNextLTPro-Bold' in content,
    'Alibaba font': 'AlibabaPuHuiTi' in content,
    'NotoSerif': 'NotoSerifSC' in content,
    'STHUPO': 'STHUPO' in content,
    'Tracking anim': 'td.tracking' in content,
    'Cinematic text': '\\u53F2\\u8BD7' in content or '\\u6218\\u58EB' in content,
    'addComp': 'addComp' in content,
    '_AE path': '_AE/' in content,
    'V17 output': 'V17.mp4' in content,
}
for desc, ok in checks.items():
    print(f"  {'OK' if ok else 'FAIL'}: {desc}")

# Send
cmd = {"command": "executeAtomScript", "script": content, "processed": False, "description": "V17_cinematic_pro"}
cmd_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json'
res_path = 'C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_result.json'
if os.path.exists(res_path):
    os.remove(res_path)
time.sleep(2)
with open(cmd_path, 'w', encoding='utf-8') as f:
    json.dump(cmd, f, ensure_ascii=False)
print(f"\nV17 sent! ({len(content)} chars)")
time.sleep(5)
log = os.popen('powershell -Command "Get-Content C:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\.ae-mcp-bridge\\ae_listener_log.txt -Tail 3"').read()
print(f"Log: {log.strip()}")
