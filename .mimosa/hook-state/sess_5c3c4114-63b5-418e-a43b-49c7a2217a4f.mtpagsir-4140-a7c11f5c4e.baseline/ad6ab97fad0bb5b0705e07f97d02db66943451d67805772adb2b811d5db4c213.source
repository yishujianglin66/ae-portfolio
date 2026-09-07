// ============================================
// AE 2026 一拳超人工程重建脚本 - 稳定版 v2
// 基于诊断结果精确修复属性索引
// ============================================

function log(msg) {
    $.writeln(msg);
    try {
        var f = new File(Folder.myDocuments.fsName + "/ae-mcp-bridge/rebuild_log.txt");
        f.encoding = "UTF-8"; f.open("a"); f.write(msg + "\n"); f.close();
    } catch(e) {}
}

app.beginUndoGroup("一拳超人重建_v26_fixed");

try {
    var compName = "一拳超人_埼玉_重构版_v26";
    var frameDir = "C:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\frames";
    var compW = 576;
    var compH = 768;
    var compDur = 12;
    var compFps = 30;

    // ===== Phase 1: 清理和创建合成 =====
    log("[Phase 1] 清理旧合成...");
    for (var i = app.project.numItems; i >= 1; i--) {
        if (app.project.item(i).name == compName && app.project.item(i) instanceof CompItem) {
            app.project.item(i).remove();
        }
    }

    log("[Phase 1] 创建主合成...");
    var comp = app.project.items.addComp(compName, compW, compH, 1, compDur, compFps);

    // ===== Phase 2: 导入帧序列 =====
    log("[Phase 2] 导入帧序列...");
    var frameFiles = [];
    for (var f = 1; f <= 18; f++) {
        var num = f < 10 ? "00" + f : (f < 100 ? "0" + f : "" + f);
        var fp = new File(frameDir + "/frame_" + num + ".png");
        if (fp.exists) {
            var importOpts = new ImportOptions(fp);
            importOpts.sequence = false;
            var footage = app.project.importFile(importOpts);
            footage.name = "Frame_" + num;
            frameFiles.push(footage);
        } else {
            log("  [WARN] 未找到: " + fp.fsName);
        }
    }
    log("  导入帧数: " + frameFiles.length);
    if (frameFiles.length == 0) throw "未找到任何帧文件";

    // ===== Phase 3: 创建帧序列预合成 =====
    log("[Phase 3] 创建FrameSeq预合成...");
    var seqDuration = frameFiles.length * (1/30);
    var seqComp = app.project.items.addComp("FrameSeq", compW, compH, 1, seqDuration, compFps);
    for (var i = 0; i < frameFiles.length; i++) {
        var layer = seqComp.layers.add(frameFiles[i]);
        layer.startTime = i * (1/30);
        layer.outPoint = (i + 1) * (1/30);
    }
    seqComp.duration = seqDuration;

    // ===== Phase 4: 主合成基础层 =====
    log("[Phase 4] 添加主合成层...");
    var seqLayer = comp.layers.add(seqComp);
    seqLayer.name = "FrameSeq";
    try { seqLayer.stretch = -50; } catch(e) { log("  stretch error"); }
    try { seqLayer.motionBlur = true; } catch(e) { log("  motionBlur error"); }

    // ===== Phase 5: 主体抠图层 =====
    log("[Phase 5] 创建Saitama主体层...");
    var saitama = seqLayer.duplicate();
    saitama.name = "Saitama_Main";
    saitama.moveToBeginning();

    try {
        var ck = saitama.property("ADBE Effect Parade").addProperty("ADBE Color Key");
        if (ck && !(ck instanceof Error)) {
            ck.property(2).setValue(30);  // Color Tolerance first
            ck.property(1).setValue([0.1, 0.6, 0.2]);  // Key Color
            ck.property(3).setValue(0);   // Edge Thin
            ck.property(4).setValue(2);   // Edge Feather
            log("  Color Key OK");
        } else {
            log("  Color Key add failed");
        }
    } catch(e) {
        log("  Color Key error");
    }

    // Glo2: property(1)=枚举 1=Color Channels; property(2)=Threshold; property(3)=Radius; property(4)=Intensity
    try {
        var glow = saitama.property("ADBE Effect Parade").addProperty("ADBE Glo2");
        glow.property(1).setValue(1);   // Glow Based On: Color Channels
        glow.property(2).setValue(80);  // Glow Threshold
        glow.property(3).setValue(2.5); // Glow Radius
        glow.property(4).setValue(1.2); // Glow Intensity
        log("  Glow OK");
    } catch(e) {
        log("  Glow error: " + e.toString());
    }

    try {
        var mc = saitama.property("ADBE Effect Parade").addProperty("ADBE Matte Choker");
        // Matte Choker属性结构（AE 2026）:
        // property(1) = Geometric Softness 1 (默认4)
        // property(2) = Choke 1 (百分比，默认75) - 收缩遮罩边缘
        // property(5) = Choke 2 (百分比，默认0)
        mc.property(2).setValue(5);  // Choke 1: 5% 收缩边缘清除杂点
        mc.property(5).setValue(3);  // Choke 2: 3% 二次收缩
        log("  Matte Choker OK");
    } catch(e) {
        log("  Matte Choker error: " + e.toString());
    }

    try {
        var tint = saitama.property("ADBE Effect Parade").addProperty("ADBE Tint");
        tint.property(1).setValue([0.1, 0.15, 0.3]);  // Map Black To (深蓝)
        tint.property(2).setValue([0.8, 0.85, 1.0]);  // Map White To (亮蓝)
        tint.property(3).setValue(15);  // Amount to Tint: 15%（百分比，不是小数）
        log("  Tint OK");
    } catch(e) {
        log("  Tint error: " + e.toString());
    }

    // ===== Phase 6: 披风层 =====
    log("[Phase 6] 创建披风层...");
    var cape = saitama.duplicate();
    cape.name = "Cape_Layer";
    try { cape.threeDLayer = true; } catch(e) { log("  3D error"); }
    try { cape.position.setValue([303, 384, -50]); } catch(e) { log("  pos error"); }
    try { cape.scale.setValue([105, 105, 105]); } catch(e) { log("  scale error"); }

    try {
        while (cape.property("ADBE Effect Parade").numProperties > 0) {
            cape.property("ADBE Effect Parade").property(1).remove();
        }
    } catch(e) { log("  remove fx error"); }

    try {
        var ck2 = cape.property("ADBE Effect Parade").addProperty("ADBE Color Key");
        ck2.property(2).setValue(25);
        ck2.property(1).setValue([0.1, 0.6, 0.2]);
        ck2.property(3).setValue(0);
        ck2.property(4).setValue(2);
    } catch(e) { log("  Cape Color Key error"); }

    try {
        var tint2 = cape.property("ADBE Effect Parade").addProperty("ADBE Tint");
        tint2.property(1).setValue([0.9, 0.9, 0.95]);
        tint2.property(2).setValue([1.0, 1.0, 1.0]);
        tint2.property(3).setValue(30);  // Amount to Tint: 30%
    } catch(e) { log("  Cape Tint error: " + e.toString()); }

    try {
        var glow2 = cape.property("ADBE Effect Parade").addProperty("ADBE Glo2");
        glow2.property(1).setValue(1);   // Glow Based On: Color Channels
        glow2.property(2).setValue(60);  // Glow Threshold
        glow2.property(3).setValue(2.0); // Glow Radius
        glow2.property(4).setValue(1.5); // Glow Intensity
    } catch(e) { log("  Cape Glow error: " + e.toString()); }

    // ===== Phase 7: 三层粒子 =====
    log("[Phase 7] 创建粒子层...");
    function createParticleLayer(name, color, zPos, birthRate, longevity, velocity, radius) {
        var solid = comp.layers.addSolid(color, name, compW, compH, 1, compDur);
        solid.threeDLayer = true;
        solid.position.setValue([compW/2, compH/2, zPos]);
        try {
            var pw = solid.property("ADBE Effect Parade").addProperty("CC Particle World");
            // 基于诊断结果的精确属性索引
            pw.property(14).setValue(birthRate);      // Birth Rate
            pw.property(15).setValue(longevity);      // Longevity (sec)
            pw.property(26).setValue(velocity);       // Velocity
            pw.property(20).setValue(radius / 1000);  // Radius X (normalized)
            pw.property(21).setValue(radius / 1000);  // Radius Y (normalized)
            log("  " + name + " OK");
        } catch(e) {
            log("  " + name + " error: " + e.toString());
        }
        return solid;
    }

    createParticleLayer("P_BG", [0.05, 0.05, 0.1], 800, 0.5, 2.0, 0.02, 50);
    createParticleLayer("P_MID", [0.1, 0.1, 0.15], 200, 1.0, 1.5, 0.05, 30);
    createParticleLayer("P_FG", [0.15, 0.15, 0.2], -100, 2.0, 1.0, 0.08, 15);

    // ===== Phase 8: 背景和大气 =====
    log("[Phase 8] 背景大气...");
    var sky = comp.layers.addSolid([0.02, 0.02, 0.08], "Sky_BG", compW, compH, 1, compDur);
    try {
        var ramp = sky.property("ADBE Effect Parade").addProperty("ADBE Ramp");
        ramp.property(1).setValue([compW/2, 100]);
        ramp.property(2).setValue([0.05, 0.05, 0.15]);
        ramp.property(3).setValue([compW/2, compH - 68]);
        ramp.property(4).setValue([0.01, 0.01, 0.03]);
    } catch(e) { log("  Ramp error: " + e.toString()); }

    var fog = comp.layers.addSolid([0.5, 0.5, 0.5], "Fog_Overlay", compW, compH, 1, compDur);
    try { fog.opacity.setValue(25); } catch(e) { log("  fog opacity error"); }
    try {
        var fn = fog.property("ADBE Effect Parade").addProperty("ADBE Fractal Noise");
        fn.property(1).setValue(6);
        fn.property(2).setValue(1);
        fn.property(8).setValue(200);
    } catch(e) { log("  Fractal Noise error: " + e.toString()); }

    var vig = comp.layers.addSolid([0, 0, 0], "Vignette", compW, compH, 1, compDur);
    try { vig.opacity.setValue(40); } catch(e) { log("  vig opacity error"); }

    // ===== Phase 9: 调色调整层 =====
    log("[Phase 9] 调色调整层...");
    var adj = comp.layers.addSolid([0.5, 0.5, 0.5], "Color_Adjust", compW, compH, 1, compDur);
    adj.adjustmentLayer = true;

    try {
        var curves = adj.property("ADBE Effect Parade").addProperty("ADBE CurvesCustom");
        curves.property(1).setValue(1); // Channel: RGB
        // 注意: Curves的曲线点是CUSTOM_VALUE类型，ExtendScript无法直接设置
        // 曲线需手动在AE中调整。此处保留默认直线。
        log("  Curves added (curve points require manual adjustment)");
    } catch(e) {
        log("  Curves error: " + e.toString());
    }

    // 使用Brightness & Contrast实现可脚本化的对比度微调
    try {
        var bc = adj.property("ADBE Effect Parade").addProperty("ADBE Brightness & Contrast 2");
        bc.property(1).setValue(5);   // Brightness
        bc.property(2).setValue(10);  // Contrast
        log("  Brightness & Contrast OK");
    } catch(e) {
        log("  Brightness & Contrast error: " + e.toString());
    }

    try {
        var hueSat = adj.property("ADBE Effect Parade").addProperty("ADBE HUE SATURATION");
        hueSat.property(1).setValue(1);  // Channel Control: Master
        hueSat.property(3).setValue(0);   // Master Hue
        hueSat.property(4).setValue(15);  // Master Saturation
        hueSat.property(5).setValue(10);  // Master Lightness
        log("  HueSat OK");
    } catch(e) {
        log("  HueSat error: " + e.toString());
    }

    // ===== Phase 10: 摄像机 =====
    log("[Phase 10] 摄像机...");
    var cam = comp.layers.addCamera("Main_Camera", [compW/2, compH/2]);
    try {
        var camOpts = cam.property("ADBE Camera Options Group");
        camOpts.property(1).setValue(800);   // Zoom (~50mm on 576px comp)
        camOpts.property(2).setValue(1);     // Depth of Field: On
        camOpts.property(3).setValue(400);   // Focus Distance
        camOpts.property(4).setValue(5.6);   // Aperture
        camOpts.property(5).setValue(80);    // Blur Level
        log("  Camera Options OK");

        var camPos = cam.property("ADBE Transform Group").property("ADBE Position");
        camPos.setValueAtTime(0, [compW/2, compH/2, -600]);
        camPos.setValueAtTime(4, [compW/2, compH/2, -500]);
        camPos.setValueAtTime(8, [compW/2 + 12, compH/2 + 6, -550]);
        camPos.setValueAtTime(12, [compW/2, compH/2, -600]);
        log("  Camera Animation OK");
    } catch(e) {
        log("  Camera error: " + e.toString());
    }

    // ===== Phase 11: 全局控制器 =====
    log("[Phase 11] 全局控制器...");
    var ctrl = comp.layers.addNull();
    ctrl.name = "Global_Controller";
    try {
        var sc1 = ctrl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
        sc1.name = "Speed";
        sc1.property(1).setValue(100);
        var sc2 = ctrl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
        sc2.name = "Glow_Intensity";
        sc2.property(1).setValue(100);
        var sc3 = ctrl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
        sc3.name = "Particle_Amount";
        sc3.property(1).setValue(100);
        log("  Controller OK");
    } catch(e) {
        log("  Controller error: " + e.toString());
    }

    // ===== Phase 12: 整理层顺序 =====
    log("[Phase 12] 整理层顺序...");
    var layerOrder = ["Sky_BG", "P_BG", "P_MID", "FrameSeq", "Saitama_Main", "Cape_Layer", "P_FG", "Fog_Overlay", "Vignette", "Color_Adjust"];
    for (var i = 0; i < layerOrder.length; i++) {
        for (var j = 1; j <= comp.numLayers; j++) {
            if (comp.layer(j).name == layerOrder[i]) {
                comp.layer(j).moveToEnd();
                break;
            }
        }
    }
    for (var j = 1; j <= comp.numLayers; j++) {
        if (comp.layer(j).name == "Main_Camera") comp.layer(j).moveToBeginning();
        if (comp.layer(j).name == "Global_Controller") comp.layer(j).moveToBeginning();
    }

    log("========================================");
    log("工程重建完成!");
    log("合成: " + compName);
    log("总层数: " + comp.numLayers);
    log("========================================");

    try {
        var logFile = new File(Folder.myDocuments.fsName + "/ae-mcp-bridge/rebuild_log.txt");
        logFile.encoding = "UTF-8";
        logFile.open("a");
        logFile.write("[SUCCESS] 工程重建完成! 合成: " + compName + ", 总层数: " + comp.numLayers + "\n");
        logFile.close();
    } catch(e) {}

} catch (err) {
    log("[FATAL ERROR] " + err.toString());
}

app.endUndoGroup();
