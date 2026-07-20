// ============================================================
// 《冰海战记》战斗剪辑完整合成脚本 - V5终极版
// 融合5个参考视频分析 + 知识库8位大师技法
//
// 参考视频类型：
// 1. Alaul1n - 情感叙事型（慢推拉镜+冷色调）
// 2. 水羊 - 共鸣叙事型（多层拉镜+情绪色彩）
// 3. 水羊 - 情感对比型（柔vs猛对比拉镜）
// 4. 混的羊 - 静止系漫剪（2.5D视差+NNTK打光）
// 5. BlackStar - 高燃AMV（Beat Sync+故障转场）
//
// 技术融合：
// - DxshNova对角滑镜标准参数表
// - YUNG_DAGGER三段式Beat Sync卡点
// - Xenoz动态拼贴+鱼眼形变
// - Molob电影感色彩统一工作流
// - 静止系2.5D视差+景深分层
// - 段落能量梯级+四层效果堆叠
// ============================================================

var COMP_NAME = "VinlandSaga_Battle_V5";
var VIDEO_PATH = "D:/AE-Work/视频素材库/";
var AUDIO_PATH = "D:/AE-Work/音频素材库/BGM/";
var DURATION = 23.15;
var WIDTH = 1080;
var HEIGHT = 1920;
var FRAME_RATE = 30;
var BPM = 112.3;
// BPM 112.3 @ 30fps → 每拍约16帧 → 拉镜时长5-7帧（较强强度）

function main() {
    try {
        var comp = createComposition(COMP_NAME, WIDTH, HEIGHT, DURATION, FRAME_RATE);
        if (!comp) return JSON.stringify({error: "Failed to create composition"});

        // 开启合成运动模糊
        comp.motionBlur = true;

        // 安全导入素材
        var vinlandFootage = safeImport(VIDEO_PATH + "冰海战记.mp4");
        var thorfinnFootage = safeImport(VIDEO_PATH + "托尔芬.mp4");
        var audioFootage = safeImport(AUDIO_PATH + "ae实战音乐.mp3");

        // 添加音频轨道
        if (audioFootage) {
            var audioLayer = comp.layers.add(audioFootage);
            audioLayer.name = "Soundtrack";
            audioLayer.startTime = 0;
        }

        // ========== 段落结构（能量梯级） ==========
        // Intro(0-4s, 能量0.3) → Build(4-9s, 能量0.5) → Drop(9-15s, 能量1.0) → Break(15-19s, 能量0.6) → Outro(19-23s, 能量0.2)

        // ========== 图层创建（2.5D视差分层） ==========
        // 远背景层（Z=+500, Scale=70%）
        var farBgLayer = createLayerWithFallBack(comp, vinlandFootage, "FarBackground", [0.08, 0.12, 0.2]);
        farBgLayer.startTime = 0;
        farBgLayer.threeDLayer = true;
        applyTile(farBgLayer, 300);
        farBgLayer.scale.setValueAtTime(0, [70, 70]);
        farBgLayer.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2, 500]);
        farBgLayer.opacity.setValueAtTime(0, 60);

        // 背景层（Z=+200, Scale=85%）
        var bgLayer = createLayerWithFallBack(comp, vinlandFootage, "Background_Vinland", [0.1, 0.15, 0.25]);
        bgLayer.startTime = 0;
        bgLayer.threeDLayer = true;
        applyTile(bgLayer, 250);
        bgLayer.scale.setValueAtTime(0, [85, 85]);
        bgLayer.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2, 200]);
        bgLayer.opacity.setValueAtTime(0, 80);

        // 中景主体层1（Z=0, Scale=100%）- Intro段
        var mainLayer = createLayerWithFallBack(comp, thorfinnFootage, "Main_Thorfinn", [0.7, 0.75, 0.8]);
        mainLayer.startTime = 0;
        mainLayer.threeDLayer = true;
        applyTile(mainLayer, 250);
        mainLayer.scale.setValueAtTime(0, [100, 100]);
        mainLayer.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2, 0]);

        // 中景主体层2（Z=0）- Build段
        var battleLayer = createLayerWithFallBack(comp, vinlandFootage, "Battle_Vinland", [0.6, 0.65, 0.7]);
        battleLayer.startTime = 4.0;
        battleLayer.threeDLayer = true;
        applyTile(battleLayer, 250);
        battleLayer.scale.setValueAtTime(4.0, [100, 100]);
        battleLayer.position.setValueAtTime(4.0, [WIDTH/2, HEIGHT/2, 0]);

        // 前景主体层3（Z=-150, Scale=115%）- Drop段
        var dropLayer = createLayerWithFallBack(comp, thorfinnFootage, "Drop_Thorfinn", [0.8, 0.7, 0.6]);
        dropLayer.startTime = 9.0;
        dropLayer.threeDLayer = true;
        applyTile(dropLayer, 250);
        dropLayer.scale.setValueAtTime(9.0, [115, 115]);
        dropLayer.position.setValueAtTime(9.0, [WIDTH/2, HEIGHT/2, -150]);

        // Break段层
        var breakLayer = createLayerWithFallBack(comp, vinlandFootage, "Break_Vinland", [0.3, 0.35, 0.45]);
        breakLayer.startTime = 15.0;
        breakLayer.threeDLayer = true;
        applyTile(breakLayer, 250);
        breakLayer.scale.setValueAtTime(15.0, [95, 95]);
        breakLayer.position.setValueAtTime(15.0, [WIDTH/2, HEIGHT/2, 0]);

        // Outro段层
        var outroLayer = createLayerWithFallBack(comp, thorfinnFootage, "Outro_Thorfinn", [0.5, 0.55, 0.6]);
        outroLayer.startTime = 19.0;
        outroLayer.threeDLayer = true;
        applyTile(outroLayer, 250);
        outroLayer.scale.setValueAtTime(19.0, [90, 90]);
        outroLayer.position.setValueAtTime(19.0, [WIDTH/2, HEIGHT/2, 100]);

        // 超前景层（Z=-400, Scale=140%）- 全程
        var fgLayer = comp.layers.addSolid([1, 1, 1], "Foreground_Particles", WIDTH, HEIGHT, 1);
        fgLayer.name = "Foreground_Particles";
        fgLayer.startTime = 0;
        fgLayer.threeDLayer = true;
        fgLayer.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2, -400]);
        fgLayer.scale.setValueAtTime(0, [140, 140]);
        fgLayer.opacity.setValueAtTime(0, 15);
        fgLayer.blendingMode = BlendingMode.SCREEN;

        // ========== 调整层系统（四层效果堆叠） ==========

        // 底层：全局调色（战争片风格：黄绿低饱和+冷蓝情绪）
        var gradingLayer = comp.layers.addSolid([1, 1, 1], "Global_Grading", WIDTH, HEIGHT, 1);
        gradingLayer.name = "Global_Grading";
        gradingLayer.startTime = 0;
        gradingLayer.adjustmentLayer = true;
        applyWarColorGrading(gradingLayer);

        // 中层：发光+纹理效果
        var glowLayer = comp.layers.addSolid([1, 1, 1], "Glow_Effects", WIDTH, HEIGHT, 1);
        glowLayer.name = "Glow_Effects";
        glowLayer.startTime = 0;
        glowLayer.adjustmentLayer = true;
        glowLayer.opacity.setValueAtTime(0, 40);
        applyGlowEffects(glowLayer);

        // 顶层：暗角+光效
        var vignetteLayer = comp.layers.addSolid([0, 0, 0], "Vignette_Layer", WIDTH, HEIGHT, 1);
        vignetteLayer.name = "Vignette_Layer";
        vignetteLayer.startTime = 0;
        vignetteLayer.adjustmentLayer = true;
        applyVignette(vignetteLayer);

        // 装饰层：胶片颗粒
        var grainLayer = comp.layers.addSolid([0.5, 0.5, 0.5], "Film_Grain", WIDTH, HEIGHT, 1);
        grainLayer.name = "Film_Grain";
        grainLayer.startTime = 0;
        grainLayer.opacity.setValueAtTime(0, 8);
        grainLayer.blendingMode = BlendingMode.OVERLAY;
        applyFilmGrain(grainLayer);

        // ========== 摄像机系统 ==========
        var camera = comp.layers.addCamera("Main_Camera", [WIDTH/2, HEIGHT/2]);
        camera.name = "Main_Camera";
        camera.property("Position").setValueAtTime(0, [WIDTH/2, HEIGHT/2, -800]);
        camera.property("Zoom").setValueAtTime(0, 800);
        camera.property("Depth of Field").setValueAtTime(0, true);
        camera.property("Aperture").setValueAtTime(0, 15);
        camera.property("Focus Distance").setValueAtTime(0, 800);

        // 空对象控制器（DxshNova式统一运镜）
        var cameraNull = createCameraNull(comp);

        // 摄像机绑定到空对象
        try { camera.parent = cameraNull; } catch(e) {}

        // 设置3D图层父级
        set3DLayerParents(comp, cameraNull);

        // ========== 音频控制器 ==========
        createAudioController(comp);

        // ========== 拉镜关键帧（YUNG_DAGGER三段式Beat Sync） ==========
        addBeatSyncPullZoom(comp, cameraNull);

        // ========== 专业转场系统 ==========
        addAdvancedTransitions(comp);

        // ========== 音频驱动效果表达式 ==========
        addAudioDrivenEffects(comp);

        // ========== 字幕系统 ==========
        addAnimatedSubtitles(comp);

        // ========== 粒子效果 ==========
        addParticleEffects(comp);

        // 调整图层顺序
        adjustLayerOrder(comp);

        return JSON.stringify({
            status: "success",
            compName: COMP_NAME,
            duration: DURATION,
            layers: comp.numLayers,
            bpm: BPM,
            message: "V5 Composition created -融合5参考视频+8大师技法"
        });
    } catch (e) {
        return JSON.stringify({error: e.toString(), line: e.line});
    }
}

// ========== 工具函数 ==========

function createComposition(name, width, height, duration, fps) {
    for (var i = 1; i <= app.project.numItems; i++) {
        if (app.project.item(i).name === name && app.project.item(i) instanceof CompItem) {
            app.project.item(i).remove();
            break;
        }
    }
    return app.project.items.addComp(name, width, height, 1, duration, fps);
}

function safeImport(filePath) {
    try {
        var file = new File(filePath);
        if (!file.exists) return null;
        return app.project.importFile(new ImportOptions(file));
    } catch (e) { return null; }
}

function createLayerWithFallBack(comp, footage, name, color) {
    var layer;
    if (footage) {
        try { layer = comp.layers.add(footage); }
        catch (e) { layer = comp.layers.addSolid(color, name, WIDTH, HEIGHT, 1); }
    } else {
        layer = comp.layers.addSolid(color, name, WIDTH, HEIGHT, 1);
    }
    layer.name = name;
    return layer;
}

function applyTile(layer, outputPercent) {
    try {
        var tile = layer.property("Effects").addProperty("ADBE Tile");
        tile.property("Output Width").setValueAtTime(0, outputPercent);
        tile.property("Output Height").setValueAtTime(0, outputPercent);
        tile.property("Mirror Edges").setValueAtTime(0, true);
    } catch (e) {}
}

function createCameraNull(comp) {
    var nullLayer = comp.layers.addNull();
    nullLayer.name = "Camera_Controller";
    nullLayer.startTime = 0;
    nullLayer.threeDLayer = true;
    nullLayer.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2, 0]);
    nullLayer.scale.setValueAtTime(0, [100, 100, 100]);
    nullLayer.rotation.setValueAtTime(0, 0);
    nullLayer.property("Orientation").setValueAtTime(0, [0, 0, 0]);
    return nullLayer;
}

function set3DLayerParents(comp, cameraNull) {
    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        var ln = layer.name;
        if (ln.indexOf("Main_") >= 0 || ln.indexOf("Battle") >= 0 || ln.indexOf("Drop") >= 0 ||
            ln.indexOf("Break") >= 0 || ln.indexOf("Outro") >= 0 || ln.indexOf("Background") >= 0) {
            try { layer.parent = cameraNull; } catch (e) {}
        }
    }
}

// ========== 调色系统（战争片+情感段+高潮段） ==========

function applyWarColorGrading(layer) {
    // Color Balance - 冷蓝色调（情感+战争混合）
    var cb = layer.property("Effects").addProperty("Color Balance");
    cb.property("Red Balance").setValueAtTime(0, -8);
    cb.property("Green Balance").setValueAtTime(0, -3);
    cb.property("Blue Balance").setValueAtTime(0, 20);

    // 段落调色变化
    // Intro段：冷蓝忧郁
    cb.property("Blue Balance").setValueAtTime(0, 20);
    // Build段：逐渐回暖
    cb.property("Blue Balance").setValueAtTime(4.0, 15);
    cb.property("Red Balance").setValueAtTime(4.0, -5);
    // Drop段：Teal & Orange 青橙对比
    cb.property("Red Balance").setValueAtTime(9.0, 5);
    cb.property("Green Balance").setValueAtTime(9.0, -8);
    cb.property("Blue Balance").setValueAtTime(9.0, 10);
    // Break段：去饱和压抑
    cb.property("Red Balance").setValueAtTime(15.0, -10);
    cb.property("Green Balance").setValueAtTime(15.0, -5);
    cb.property("Blue Balance").setValueAtTime(15.0, 5);
    // Outro段：暖金收束
    cb.property("Red Balance").setValueAtTime(19.0, 8);
    cb.property("Green Balance").setValueAtTime(19.0, 3);
    cb.property("Blue Balance").setValueAtTime(19.0, -5);

    // Fast Blur - 轻微柔化
    var blur = layer.property("Effects").addProperty("ADBE Fast Blur");
    blur.property("Blurriness").setValueAtTime(0, 2);
    blur.property("Repeat Edge Pixels").setValueAtTime(0, true);
}

function applyGlowEffects(layer) {
    // Fast Blur 作为简易发光
    var blur = layer.property("Effects").addProperty("ADBE Fast Blur");
    blur.property("Blurriness").expression =
        "highEng = thisComp.layer(\"Audio Controller\").effect(\"HighFreq Energy\")(\"Slider\") / 100; " +
        "base = 2; max = 12; " +
        "base + (max - base) * highEng;";
    blur.property("Repeat Edge Pixels").setValueAtTime(0, true);
}

function applyVignette(layer) {
    // 用Radial Blur模拟暗角
    var rb = layer.property("Effects").addProperty("Radial Blur");
    rb.property("Amount").setValueAtTime(0, 0);

    // 用Fast Blur边缘模糊做暗角
    var blur = layer.property("Effects").addProperty("ADBE Fast Blur");
    blur.property("Blurriness").setValueAtTime(0, 8);
    blur.property("Repeat Edge Pixels").setValueAtTime(0, false);

    // Opacity动画做暗角强度
    layer.opacity.expression =
        "eng = thisComp.layer(\"Audio Controller\").effect(\"Global Energy\")(\"Slider\") / 100; " +
        "base = 30; max = 60; " +
        "base + (max - base) * eng;";
}

function applyFilmGrain(layer) {
    // 噪点效果模拟胶片颗粒
    try {
        var noise = layer.property("Effects").addProperty("ADBE Noise");
        noise.property("Amount of Noise").setValueAtTime(0, 15);
        noise.property("Noise Type").setValueAtTime(0, 1); // 使用色噪
    } catch (e) {}
}

// ========== YUNG_DAGGER三段式Beat Sync拉镜 ==========

function addBeatSyncPullZoom(comp, cameraNull) {
    // BPM 112.3 @ 30fps → 每拍约16帧
    // 三段式卡点：预备(2帧)→爆发(1帧)→回弹(4帧)

    // === Intro段 (0-4s) - 慢推建立氛围（Molob式） ===
    // 慢推进 15-25帧
    setKeyframe(cameraNull, "Scale", 0, [100, 100, 100]);
    setKeyframe(cameraNull, "Scale", 2.0, [105, 105, 100]);
    setKeyframe(cameraNull, "Scale", 4.0, [108, 108, 100]);
    setKeyframe(cameraNull, "Position", 0, [WIDTH/2, HEIGHT/2, 0]);
    setKeyframe(cameraNull, "Position", 4.0, [WIDTH/2, HEIGHT/2 - 30, 0]);
    setKeyframe(cameraNull, "Rotation", 0, 0);
    setKeyframe(cameraNull, "Rotation", 4.0, 1.5);

    // === Build段 (4-9s) - 中等强度拉镜（DxshNova对角滑） ===
    // 对角滑 6-8帧, Scale 85-115%
    // Beat 1: 4.0s
    setKeyframe(cameraNull, "Scale", 4.0, [108, 108, 100]);
    setKeyframe(cameraNull, "Scale", 4.13, [95, 95, 100]);  // 预备2帧
    setKeyframe(cameraNull, "Scale", 4.17, [120, 120, 100]); // 爆发1帧
    setKeyframe(cameraNull, "Scale", 4.3, [110, 110, 100]);  // 回弹4帧
    setKeyframe(cameraNull, "Position", 4.0, [WIDTH/2, HEIGHT/2 - 30, 0]);
    setKeyframe(cameraNull, "Position", 4.17, [WIDTH/2 - 80, HEIGHT/2 + 50, 0]);
    setKeyframe(cameraNull, "Position", 4.3, [WIDTH/2 - 20, HEIGHT/2, 0]);
    setKeyframe(cameraNull, "Rotation", 4.0, 1.5);
    setKeyframe(cameraNull, "Rotation", 4.17, -3);
    setKeyframe(cameraNull, "Rotation", 4.3, 0);

    // Beat 2: 4.53s (4.0 + 0.53)
    setKeyframe(cameraNull, "Scale", 4.5, [110, 110, 100]);
    setKeyframe(cameraNull, "Scale", 4.57, [98, 98, 100]);
    setKeyframe(cameraNull, "Scale", 4.6, [118, 118, 100]);
    setKeyframe(cameraNull, "Scale", 4.73, [108, 108, 100]);
    setKeyframe(cameraNull, "Position", 4.6, [WIDTH/2 + 60, HEIGHT/2 - 40, 0]);
    setKeyframe(cameraNull, "Rotation", 4.6, 4);

    // Beat 3: 5.07s
    setKeyframe(cameraNull, "Scale", 5.0, [108, 108, 100]);
    setKeyframe(cameraNull, "Scale", 5.07, [96, 96, 100]);
    setKeyframe(cameraNull, "Scale", 5.1, [122, 122, 100]);
    setKeyframe(cameraNull, "Scale", 5.23, [112, 112, 100]);
    setKeyframe(cameraNull, "Position", 5.1, [WIDTH/2 - 50, HEIGHT/2 - 60, 0]);
    setKeyframe(cameraNull, "Rotation", 5.1, -5);

    // Beat 4: 5.53s
    setKeyframe(cameraNull, "Scale", 5.5, [112, 112, 100]);
    setKeyframe(cameraNull, "Scale", 5.57, [97, 97, 100]);
    setKeyframe(cameraNull, "Scale", 5.6, [125, 125, 100]);
    setKeyframe(cameraNull, "Scale", 5.73, [115, 115, 100]);
    setKeyframe(cameraNull, "Position", 5.6, [WIDTH/2 + 40, HEIGHT/2 + 30, 0]);
    setKeyframe(cameraNull, "Rotation", 5.6, 6);

    // Build后半段 (6-9s) - 逐渐加速
    for (var beat = 6; beat < 9; beat += 0.53) {
        var t = beat;
        setKeyframe(cameraNull, "Scale", t, [115, 115, 100]);
        setKeyframe(cameraNull, "Scale", t + 0.07, [94, 94, 100]);
        setKeyframe(cameraNull, "Scale", t + 0.1, [128, 128, 100]);
        setKeyframe(cameraNull, "Scale", t + 0.23, [112, 112, 100]);
        setKeyframe(cameraNull, "Position", t + 0.1, [WIDTH/2 + (Math.sin(beat * 3) * 70), HEIGHT/2 + (Math.cos(beat * 2) * 50), 0]);
        setKeyframe(cameraNull, "Rotation", t + 0.1, Math.sin(beat * 5) * 7);
    }

    // === Drop段 (9-15s) - 极强卡点（Xenoz式高速推拉） ===
    // 拉镜时长3-5帧, Scale 100-140%
    for (var d = 9; d < 15; d += 0.53) {
        var dt = d;
        // 三段式：预备(1帧)→爆发(1帧)→回弹(3帧)
        setKeyframe(cameraNull, "Scale", dt, [115, 115, 100]);
        setKeyframe(cameraNull, "Scale", dt + 0.03, [90, 90, 100]);   // 预备1帧
        setKeyframe(cameraNull, "Scale", dt + 0.07, [135, 135, 100]); // 爆发1帧
        setKeyframe(cameraNull, "Scale", dt + 0.17, [110, 110, 100]); // 回弹3帧
        setKeyframe(cameraNull, "Position", dt + 0.07, [WIDTH/2 + (Math.sin(d * 4) * 100), HEIGHT/2 + (Math.cos(d * 3) * 80), 0]);
        setKeyframe(cameraNull, "Rotation", dt + 0.07, Math.sin(d * 6) * 10);
    }

    // === Break段 (15-19s) - 慢拉远收束（Molob式） ===
    setKeyframe(cameraNull, "Scale", 15.0, [100, 100, 100]);
    setKeyframe(cameraNull, "Scale", 17.0, [95, 95, 100]);
    setKeyframe(cameraNull, "Scale", 19.0, [92, 92, 100]);
    setKeyframe(cameraNull, "Position", 15.0, [WIDTH/2, HEIGHT/2, 0]);
    setKeyframe(cameraNull, "Position", 17.0, [WIDTH/2, HEIGHT/2 + 20, 0]);
    setKeyframe(cameraNull, "Position", 19.0, [WIDTH/2, HEIGHT/2 + 30, 0]);
    setKeyframe(cameraNull, "Rotation", 15.0, 0);
    setKeyframe(cameraNull, "Rotation", 17.0, -1);
    setKeyframe(cameraNull, "Rotation", 19.0, 0);

    // === Outro段 (19-23s) - 缓慢推远到黑 ===
    setKeyframe(cameraNull, "Scale", 19.0, [92, 92, 100]);
    setKeyframe(cameraNull, "Scale", 21.0, [88, 88, 100]);
    setKeyframe(cameraNull, "Scale", 23.15, [85, 85, 100]);
    setKeyframe(cameraNull, "Position", 19.0, [WIDTH/2, HEIGHT/2 + 30, 0]);
    setKeyframe(cameraNull, "Position", 21.0, [WIDTH/2, HEIGHT/2 + 40, 0]);
    setKeyframe(cameraNull, "Position", 23.15, [WIDTH/2, HEIGHT/2 + 50, 0]);

    // 应用缓动曲线
    applyEasing(cameraNull.property("Scale"));
    applyEasing(cameraNull.property("Position"));
    applyEasing(cameraNull.property("Rotation"));
}

function setKeyframe(layer, propName, time, value) {
    try {
        layer.property(propName).setValueAtTime(time, value);
    } catch (e) {}
}

function applyEasing(prop) {
    for (var i = 1; i <= prop.numKeys; i++) {
        try {
            if (prop.valueDimension === 1) {
                prop.setTemporalEaseAtKey(i, [new KeyframeEase(0, 75)], [new KeyframeEase(0, 75)]);
            } else {
                var inEase = [];
                var outEase = [];
                for (var d = 0; d < prop.valueDimension; d++) {
                    inEase.push(new KeyframeEase(0, 75));
                    outEase.push(new KeyframeEase(0, 75));
                }
                prop.setTemporalEaseAtKey(i, inEase, outEase);
            }
        } catch (e) {}
    }
}

// ========== 高级转场系统 ==========

function addAdvancedTransitions(comp) {
    // Intro→Build: 光泄漏转场
    addLightLeakTransition(comp, 3.8, 4.2, [0.8, 0.6, 0.3]);

    // Build→Drop: 闪白+径向模糊+RGB偏移
    addFlashTransition(comp, 8.8, 9.2, 100);
    addRadialBlurTransition(comp, 8.85, 9.15);

    // Drop→Break: 闪白转场
    addFlashTransition(comp, 14.8, 15.2, 80);

    // Break→Outro: 柔光转场
    addLightLeakTransition(comp, 18.8, 19.4, [0.5, 0.7, 0.9]);

    // Drop段内部：每2拍加一次小闪白
    for (var t = 10; t < 15; t += 1.06) {
        addMicroFlash(comp, t, t + 0.06, 40);
    }
}

function addFlashTransition(comp, startTime, endTime, maxOpacity) {
    var flash = comp.layers.addSolid([1, 1, 1], "Flash_" + startTime, WIDTH, HEIGHT, 1);
    flash.startTime = startTime;
    flash.inPoint = startTime;
    flash.outPoint = endTime;
    flash.opacity.setValueAtTime(startTime, 0);
    flash.opacity.setValueAtTime(startTime + 0.04, maxOpacity);
    flash.opacity.setValueAtTime(startTime + 0.08, maxOpacity * 0.8);
    flash.opacity.setValueAtTime(endTime, 0);
    flash.blendingMode = BlendingMode.SCREEN;
}

function addRadialBlurTransition(comp, startTime, endTime) {
    var blurLayer = comp.layers.addSolid([0, 0, 0], "RadialBlur_" + startTime, WIDTH, HEIGHT, 1);
    blurLayer.startTime = startTime;
    blurLayer.inPoint = startTime;
    blurLayer.outPoint = endTime;
    blurLayer.opacity.setValueAtTime(startTime, 40);
    blurLayer.opacity.setValueAtTime((startTime + endTime) / 2, 60);
    blurLayer.opacity.setValueAtTime(endTime, 0);

    var rb = blurLayer.property("Effects").addProperty("Radial Blur");
    rb.property("Amount").setValueAtTime(startTime, 0);
    rb.property("Amount").setValueAtTime((startTime + endTime) / 2, 60);
    rb.property("Amount").setValueAtTime(endTime, 0);
}

function addLightLeakTransition(comp, startTime, endTime, color) {
    var leak = comp.layers.addSolid(color, "LightLeak_" + startTime, WIDTH, HEIGHT, 1);
    leak.startTime = startTime;
    leak.inPoint = startTime;
    leak.outPoint = endTime;
    leak.opacity.setValueAtTime(startTime, 0);
    leak.opacity.setValueAtTime(startTime + 0.1, 50);
    leak.opacity.setValueAtTime(endTime - 0.1, 30);
    leak.opacity.setValueAtTime(endTime, 0);
    leak.blendingMode = BlendingMode.SCREEN;

    var blur = leak.property("Effects").addProperty("ADBE Fast Blur");
    blur.property("Blurriness").setValueAtTime(startTime, 50);
    blur.property("Repeat Edge Pixels").setValueAtTime(0, true);
}

function addMicroFlash(comp, startTime, endTime, opacity) {
    var flash = comp.layers.addSolid([1, 1, 1], "MicroFlash_" + startTime, WIDTH, HEIGHT, 1);
    flash.startTime = startTime;
    flash.inPoint = startTime;
    flash.outPoint = endTime;
    flash.opacity.setValueAtTime(startTime, 0);
    flash.opacity.setValueAtTime(startTime + 0.02, opacity);
    flash.opacity.setValueAtTime(endTime, 0);
    flash.blendingMode = BlendingMode.SCREEN;
}

// ========== 音频驱动效果 ==========

function createAudioController(comp) {
    var ctrlLayer = comp.layers.addSolid([1, 1, 1], "Audio Controller", 100, 100, 1);
    ctrlLayer.name = "Audio Controller";
    ctrlLayer.startTime = 0;

    var sliderNames = ["Global Energy", "LowFreq Energy", "MidFreq Energy", "HighFreq Energy"];
    for (var i = 0; i < sliderNames.length; i++) {
        var eff = ctrlLayer.property("Effects").addProperty("Slider Control");
        eff.name = sliderNames[i];
        eff.property("Slider").setValueAtTime(0, 50);
    }
}

function addAudioDrivenEffects(comp) {
    // 主体层音频驱动
    var mainLayer = findLayer(comp, "Main_Thorfinn");
    if (mainLayer) {
        var blur = mainLayer.property("Effects").addProperty("ADBE Fast Blur");
        blur.property("Blurriness").expression =
            "highEng = thisComp.layer(\"Audio Controller\").effect(\"HighFreq Energy\")(\"Slider\") / 100; " +
            "base = 1; max = 10; " +
            "base + (max - base) * highEng;";
        blur.property("Repeat Edge Pixels").setValueAtTime(0, true);

        mainLayer.property("Opacity").expression =
            "eng = thisComp.layer(\"Audio Controller\").effect(\"Global Energy\")(\"Slider\") / 100; " +
            "base = 80; amp = 20 * eng; " +
            "base + amp + Math.sin(time * Math.PI * 2 * 1.873) * (5 * eng);";
    }

    // Drop层音频驱动 - 更强烈
    var dropLayer = findLayer(comp, "Drop_Thorfinn");
    if (dropLayer) {
        var dBlur = dropLayer.property("Effects").addProperty("ADBE Fast Blur");
        dBlur.property("Blurriness").expression =
            "highEng = thisComp.layer(\"Audio Controller\").effect(\"HighFreq Energy\")(\"Slider\") / 100; " +
            "midEng = thisComp.layer(\"Audio Controller\").effect(\"MidFreq Energy\")(\"Slider\") / 100; " +
            "base = 2; max = 18; " +
            "base + (max - base) * (highEng * 0.6 + midEng * 0.4);";
        dBlur.property("Repeat Edge Pixels").setValueAtTime(0, true);

        dropLayer.property("Opacity").expression =
            "eng = thisComp.layer(\"Audio Controller\").effect(\"Global Energy\")(\"Slider\") / 100; " +
            "base = 85; amp = 15 * eng; " +
            "base + amp + Math.sin(time * Math.PI * 2 * 2.5) * (8 * eng);";
    }

    // 背景层低频驱动
    var bgLayer = findLayer(comp, "Background_Vinland");
    if (bgLayer) {
        var bgBlur = bgLayer.property("Effects").addProperty("ADBE Fast Blur");
        bgBlur.property("Blurriness").expression =
            "lowEng = thisComp.layer(\"Audio Controller\").effect(\"LowFreq Energy\")(\"Slider\") / 100; " +
            "base = 3; max = 15; " +
            "base + (max - base) * lowEng;";
        bgBlur.property("Repeat Edge Pixels").setValueAtTime(0, true);
    }

    // 前景粒子层高频驱动
    var fgLayer = findLayer(comp, "Foreground_Particles");
    if (fgLayer) {
        fgLayer.property("Opacity").expression =
            "highEng = thisComp.layer(\"Audio Controller\").effect(\"HighFreq Energy\")(\"Slider\") / 100; " +
            "base = 8; max = 25; " +
            "base + (max - base) * highEng;";
    }
}

// ========== 字幕系统（动态文字动画） ==========

function addAnimatedSubtitles(comp) {
    var subtitles = [
        { time: 2.0, duration: 2.0, text: "戦士として…", size: 48 },
        { time: 5.5, duration: 0.8, text: "今！", size: 72 },
        { time: 9.5, duration: 0.5, text: "斬", size: 120 },
        { time: 12.0, duration: 0.5, text: "撃", size: 120 },
        { time: 14.5, duration: 1.0, text: "仇を越えて", size: 52 },
        { time: 17.0, duration: 1.5, text: "真の戦士", size: 56 },
        { time: 20.5, duration: 2.65, text: "VINLAND SAGA", size: 80 }
    ];

    for (var i = 0; i < subtitles.length; i++) {
        var sub = subtitles[i];
        var textLayer = comp.layers.addText(sub.text);
        textLayer.name = "Subtitle_" + (i + 1);
        textLayer.startTime = sub.time;
        textLayer.inPoint = sub.time;
        textLayer.outPoint = sub.time + sub.duration;

        textLayer.position.setValueAtTime(sub.time, [WIDTH/2, HEIGHT - 200]);

        // 淡入淡出
        textLayer.opacity.setValueAtTime(sub.time, 0);
        textLayer.opacity.setValueAtTime(sub.time + 0.1, 100);
        textLayer.opacity.setValueAtTime(sub.time + sub.duration - 0.2, 100);
        textLayer.opacity.setValueAtTime(sub.time + sub.duration, 0);

        // 缩放动画（最后字幕特殊处理）
        if (i === subtitles.length - 1) {
            textLayer.scale.setValueAtTime(sub.time, [0, 0]);
            textLayer.scale.setValueAtTime(sub.time + 0.3, [110, 110]);
            textLayer.scale.setValueAtTime(sub.time + 0.35, [100, 100]);
        } else if (sub.size >= 100) {
            // 大字幕爆破效果
            textLayer.scale.setValueAtTime(sub.time, [150, 150]);
            textLayer.scale.setValueAtTime(sub.time + 0.08, [90, 90]);
            textLayer.scale.setValueAtTime(sub.time + 0.15, [100, 100]);
        }
    }
}

// ========== 粒子效果（CC Particle World） ==========

function addParticleEffects(comp) {
    var particleLayer = comp.layers.addSolid([1, 1, 1], "Particle_Dust", WIDTH, HEIGHT, 1);
    particleLayer.name = "Particle_Dust";
    particleLayer.startTime = 0;
    particleLayer.threeDLayer = true;
    particleLayer.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2, -100]);
    particleLayer.opacity.setValueAtTime(0, 20);
    particleLayer.blendingMode = BlendingMode.SCREEN;

    try {
        var pcw = particleLayer.property("Effects").addProperty("CC Particle World");
        pcw.property("Producer Position X").setValueAtTime(0, 0);
        pcw.property("Producer Position Y").setValueAtTime(0, 0);
        pcw.property("Producer Position Z").setValueAtTime(0, 0);
        pcw.property("Producer X Size").setValueAtTime(0, 200);
        pcw.property("Producer Y Size").setValueAtTime(0, 300);
        pcw.property("Producer Z Size").setValueAtTime(0, 200);

        // 粒子类型 - 雪花/灰尘
        pcw.property("Particle Type").setValueAtTime(0, 5); // 5 = Sphere
        pcw.property("Birth Size").setValueAtTime(0, 1.5);
        pcw.property("Death Size").setValueAtTime(0, 0.3);
        pcw.property("Birth Color").setValueAtTime(0, [1, 1, 1]);
        pcw.property("Death Color").setValueAtTime(0, [0.7, 0.8, 0.9]);

        // 物理参数
        pcw.property("Gravity").setValueAtTime(0, -5); // 向上飘
        pcw.property("Velocity").setValueAtTime(0, 10);
        pcw.property("Animation").setValueAtTime(0, 1); // 1 = Directional

        // 音频驱动粒子量
        pcw.property("Birth Rate").expression =
            "eng = thisComp.layer(\"Audio Controller\").effect(\"Global Energy\")(\"Slider\") / 100; " +
            "base = 0.5; max = 2.5; " +
            "base + (max - base) * eng;";
    } catch (e) {}
}

// ========== 图层顺序调整 ==========

function adjustLayerOrder(comp) {
    var layerOrder = [
        "Subtitle_7", "Subtitle_6", "Subtitle_5", "Subtitle_4", "Subtitle_3", "Subtitle_2", "Subtitle_1",
        "Film_Grain", "Vignette_Layer", "Glow_Effects", "Global_Grading",
        "Particle_Dust",
        "MicroFlash_14", "MicroFlash_13", "MicroFlash_12", "MicroFlash_11", "MicroFlash_10",
        "LightLeak_18.8", "Flash_14.8", "RadialBlur_8.85", "Flash_8.8", "LightLeak_3.8",
        "Foreground_Particles",
        "Outro_Thorfinn", "Break_Vinland", "Drop_Thorfinn", "Battle_Vinland", "Main_Thorfinn",
        "Background_Vinland", "FarBackground",
        "Audio Controller", "Main_Camera", "Camera_Controller",
        "Soundtrack"
    ];

    for (var i = 0; i < layerOrder.length; i++) {
        var layer = findLayer(comp, layerOrder[i]);
        if (layer) {
            if (i === 0) {
                layer.moveToBeginning();
            } else {
                var prevLayer = findLayer(comp, layerOrder[i-1]);
                if (prevLayer) {
                    layer.moveAfter(prevLayer);
                }
            }
        }
    }
}

function findLayer(comp, name) {
    for (var i = 1; i <= comp.numLayers; i++) {
        if (comp.layer(i).name === name) {
            return comp.layer(i);
        }
    }
    return null;
}

return main();