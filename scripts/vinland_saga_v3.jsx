// ============================================================
// 《冰海战记》战斗剪辑完整合成脚本 - V3修复版
// 修复：素材导入容错 + 图层变量验证 + 占位层机制
// ============================================================

var COMP_NAME = "VinlandSaga_Battle_V3";
var VIDEO_PATH = "D:/AE-Work/视频素材库/";
var AUDIO_PATH = "D:/AE-Work/音频素材库/BGM/";
var DURATION = 23.15;
var WIDTH = 1080;
var HEIGHT = 1920;
var FRAME_RATE = 30;

function main() {
    // 创建合成
    var comp = createComposition(COMP_NAME, WIDTH, HEIGHT, DURATION, FRAME_RATE);
    if (!comp) return JSON.stringify({error: "Failed to create composition"});

    // 安全导入素材
    var vinlandFootage = safeImport(VIDEO_PATH + "冰海战记.mp4");
    var thorfinnFootage = safeImport(VIDEO_PATH + "托尔芬.mp4");
    var audioFootage = safeImport(AUDIO_PATH + "ae实战音乐.mp3");

    // 添加音频轨道
    if (audioFootage) {
        var audioLayer = comp.layers.add(audioFootage);
        audioLayer.name = "Soundtrack";
        audioLayer.startTime = 0;
    } else {
        var audioLayer = comp.layers.addSolid([0, 0, 0], "Soundtrack", 100, 100, 1);
        audioLayer.name = "Soundtrack";
        audioLayer.startTime = 0;
    }

    // 创建分层结构（带安全检查）
    var layers = createLayerStructure(comp, vinlandFootage, thorfinnFootage);
    if (!layers) return JSON.stringify({error: "Failed to create layers"});

    // 创建空对象控制器
    var cameraNull = createCameraNull(comp);

    // 设置父级链接
    setLayerParents(comp, cameraNull);

    // 创建能量滑块控制器
    createAudioController(comp);

    // 添加全局调色
    createGlobalGrading(comp);

    // 添加音频驱动效果
    addAudioDrivenEffects(comp);

    // 添加字幕
    addSubtitles(comp);

    // 添加专业转场
    addProfessionalTransitions(comp);

    // 添加拉镜关键帧
    addPullZoomKeyframes(comp, cameraNull);

    // 调整图层顺序
    adjustLayerOrder(comp);

    return JSON.stringify({
        status: "success",
        compName: COMP_NAME,
        duration: DURATION,
        layers: comp.numLayers,
        message: "Composition V3 created successfully"
    });
}

function createComposition(name, width, height, duration, fps) {
    try {
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === name && app.project.item(i) instanceof CompItem) {
                app.project.item(i).remove();
                break;
            }
        }
        var comp = app.project.items.addComp(name, width, height, 1, duration, fps);
        return comp;
    } catch (e) {
        return null;
    }
}

function safeImport(filePath) {
    try {
        var file = new File(filePath);
        if (!file.exists) {
            $.writeln("文件不存在: " + filePath);
            return null;
        }
        var footage = app.project.importFile(new ImportOptions(file));
        return footage;
    } catch (e) {
        $.writeln("导入失败: " + filePath + " - " + e.toString());
        return null;
    }
}

function createLayerStructure(comp, vinlandFootage, thorfinnFootage) {
    try {
        // 1. 背景层
        var bgLayer = createLayerWithFallBack(comp, vinlandFootage, "Background_Vinland", [0.1, 0.15, 0.25]);
        bgLayer.startTime = 0;
        applyDynamicTile(bgLayer);
        bgLayer.scale.setValueAtTime(0, [120, 120]);
        bgLayer.opacity.setValueAtTime(0, 70);

        // 2. 主体层1 - 托尔芬特写
        var mainLayer = createLayerWithFallBack(comp, thorfinnFootage, "Main_Thorfinn", [0.7, 0.75, 0.8]);
        mainLayer.startTime = 0;
        applyDynamicTile(mainLayer);
        enableMotionBlur(mainLayer);
        mainLayer.scale.setValueAtTime(0, [100, 100]);
        mainLayer.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2]);

        // 3. 主体层2 - 战斗镜头
        var battleLayer = createLayerWithFallBack(comp, vinlandFootage, "Battle_Vinland", [0.6, 0.65, 0.7]);
        battleLayer.startTime = 4.0;
        applyDynamicTile(battleLayer);
        enableMotionBlur(battleLayer);
        battleLayer.scale.setValueAtTime(4.0, [105, 105]);

        // 4. 主体层3 - 托尔芬战斗
        var thorfinnBattleLayer = createLayerWithFallBack(comp, thorfinnFootage, "Thorfinn_Battle", [0.8, 0.7, 0.6]);
        thorfinnBattleLayer.startTime = 9.0;
        applyDynamicTile(thorfinnBattleLayer);
        enableMotionBlur(thorfinnBattleLayer);
        thorfinnBattleLayer.scale.setValueAtTime(9.0, [110, 110]);

        // 5. 主体层4 - Outro
        var outroLayer = createLayerWithFallBack(comp, vinlandFootage, "Outro_Vinland", [0.2, 0.25, 0.35]);
        outroLayer.startTime = 15.0;
        applyDynamicTile(outroLayer);
        enableMotionBlur(outroLayer);
        outroLayer.scale.setValueAtTime(15.0, [95, 95]);

        // 6. 前景粒子层
        var foregroundLayer = comp.layers.addSolid([1, 1, 1], "Foreground_Snow", WIDTH, HEIGHT, 1);
        foregroundLayer.name = "Foreground_Snow";
        foregroundLayer.startTime = 0;
        foregroundLayer.opacity.setValueAtTime(0, 12);
        foregroundLayer.blendingMode = BlendingMode.SCREEN;

        // 7. 特效调整层
        var fxLayer = comp.layers.addSolid([1, 1, 1], "FX_Adjustment", WIDTH, HEIGHT, 1);
        fxLayer.name = "FX_Layer";
        fxLayer.startTime = 0;
        fxLayer.adjustmentLayer = true;

        return {
            bg: bgLayer,
            main: mainLayer,
            battle: battleLayer,
            thorfinnBattle: thorfinnBattleLayer,
            outro: outroLayer,
            foreground: foregroundLayer,
            fx: fxLayer
        };
    } catch (e) {
        $.writeln("创建图层失败: " + e.toString());
        return null;
    }
}

function createLayerWithFallBack(comp, footage, name, fallbackColor) {
    var layer;
    if (footage) {
        try {
            layer = comp.layers.add(footage);
        } catch (e) {
            layer = comp.layers.addSolid(fallbackColor, name, WIDTH, HEIGHT, 1);
        }
    } else {
        layer = comp.layers.addSolid(fallbackColor, name, WIDTH, HEIGHT, 1);
    }
    layer.name = name;
    return layer;
}

function applyDynamicTile(layer) {
    try {
        var tileEffect = layer.property("Effects").addProperty("ADBE Tile");
        tileEffect.property("ADBE Tile Output Width").setValueAtTime(0, 250);
        tileEffect.property("ADBE Tile Output Height").setValueAtTime(0, 250);
        tileEffect.property("ADBE Tile Mirror Edges").setValueAtTime(0, true);
    } catch (e) {}
}

function enableMotionBlur(layer) {
    layer.motionBlur = MotionBlurType.ON;
}

function createCameraNull(comp) {
    var nullLayer = comp.layers.addNull();
    nullLayer.name = "Camera_Controller";
    nullLayer.startTime = 0;
    nullLayer.scale.setValueAtTime(0, [100, 100]);
    nullLayer.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2]);
    nullLayer.rotation.setValueAtTime(0, 0);
    return nullLayer;
}

function setLayerParents(comp, cameraNull) {
    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        var ln = layer.name;
        if (ln.indexOf("Main_") >= 0 || ln.indexOf("Battle") >= 0 || ln.indexOf("Outro") >= 0) {
            try {
                layer.parent = cameraNull;
            } catch (e) {
                $.writeln("设置父级失败: " + ln);
            }
        }
    }
}

function createAudioController(comp) {
    var ctrlLayer = comp.layers.addSolid([1, 1, 1], "Audio Controller", 100, 100, 1);
    ctrlLayer.name = "Audio Controller";
    ctrlLayer.startTime = 0;
    ctrlLayer.adjustmentLayer = true;

    var sliderNames = ["Global Energy", "LowFreq Energy", "MidFreq Energy", "HighFreq Energy"];
    for (var i = 0; i < sliderNames.length; i++) {
        var eff = ctrlLayer.property("Effects").addProperty("ADBE Slider Control");
        eff.name = sliderNames[i];
        var sProp = eff.property("Slider");
        sProp.setValueAtTime(0, 50);
    }
}

function createGlobalGrading(comp) {
    var gradingLayer = comp.layers.addSolid([1, 1, 1], "Global Grading", WIDTH, HEIGHT, 1);
    gradingLayer.name = "Global_Grading";
    gradingLayer.startTime = 0;
    gradingLayer.adjustmentLayer = true;

    var cb = gradingLayer.property("Effects").addProperty("ADBE Color Balance");
    cb.property("Shadows Red Balance").setValueAtTime(0, -10);
    cb.property("Shadows Green Balance").setValueAtTime(0, 5);
    cb.property("Shadows Blue Balance").setValueAtTime(0, 25);
    cb.property("Midtones Red Balance").setValueAtTime(0, -8);
    cb.property("Midtones Green Balance").setValueAtTime(0, 0);
    cb.property("Midtones Blue Balance").setValueAtTime(0, 15);
    cb.property("Highlights Red Balance").setValueAtTime(0, 8);
    cb.property("Highlights Green Balance").setValueAtTime(0, -8);
    cb.property("Highlights Blue Balance").setValueAtTime(0, 5);

    var vg = gradingLayer.property("Effects").addProperty("ADBE Vignette");
    vg.property("ADBE Vignette Amount").setValueAtTime(0, 25);
    vg.property("ADBE Vignette Feather").setValueAtTime(0, 45);

    var sat = gradingLayer.property("Effects").addProperty("ADBE Saturation");
    sat.property("ADBE Saturation Master").setValueAtTime(0, -20);

    var grain = gradingLayer.property("Effects").addProperty("ADBE Film Grain");
    grain.property("ADBE Film Grain Amount").setValueAtTime(0, 3);
}

function addAudioDrivenEffects(comp) {
    var mainLayer = findLayer(comp, "Main_Thorfinn");
    if (mainLayer) {
        var glow = mainLayer.property("Effects").addProperty("ADBE Glow");
        glow.property("ADBE Glow Threshold").setValueAtTime(0, 0.5);
        glow.property("ADBE Glow Radius").setValueAtTime(0, 20);
        glow.property("ADBE Glow Intensity").expression =
            "highEng = thisComp.layer(\"Audio Controller\").effect(\"HighFreq Energy\")(\"Slider\") / 100; " +
            "baseGlow = 0.3; maxGlow = 2.5; " +
            "baseGlow + (maxGlow - baseGlow) * highEng;";

        mainLayer.property("Opacity").expression =
            "eng = thisComp.layer(\"Audio Controller\").effect(\"Global Energy\")(\"Slider\") / 100; " +
            "base = 75; amp = 25 * eng; " +
            "base + amp + Math.sin(time * Math.PI * 2 * 1.873) * (8 * eng);";
    }

    var bgLayer = findLayer(comp, "Background_Vinland");
    if (bgLayer) {
        var blur = bgLayer.property("Effects").addProperty("ADBE Fast Blur");
        blur.property("ADBE Fast Blur Blurriness").expression =
            "lowEng = thisComp.layer(\"Audio Controller\").effect(\"LowFreq Energy\")(\"Slider\") / 100; " +
            "baseBlur = 3; maxBlur = 20; " +
            "baseBlur + (maxBlur - baseBlur) * lowEng;";
    }
}

function addSubtitles(comp) {
    var subtitles = [
        { time: 2.5, duration: 1.5, text: "戦士として…" },
        { time: 9.0, duration: 0.6, text: "今！" },
        { time: 14.0, duration: 1.2, text: "仇を越えて" },
        { time: 21.0, duration: 2.15, text: "VINLAND SAGA" }
    ];

    for (var i = 0; i < subtitles.length; i++) {
        var sub = subtitles[i];
        var textLayer = comp.layers.addText(sub.text);
        textLayer.name = "Subtitle_" + (i + 1);
        textLayer.startTime = sub.time;
        textLayer.inPoint = sub.time;
        textLayer.outPoint = sub.time + sub.duration;

        var sourceText = textLayer.property("Source Text");
        var textDoc = sourceText.getValueAtTime(0);
        textDoc.fontSize = (i === 3) ? 80 : 52;
        textDoc.fillColor = [0.839, 0.894, 0.941];
        textDoc.strokeColor = [0.169, 0.306, 0.494];
        textDoc.strokeWidth = 3;
        textDoc.strokeOverFill = true;
        textDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
        sourceText.setValueAtTime(0, textDoc);

        textLayer.position.setValueAtTime(sub.time, [WIDTH/2, HEIGHT - 180]);

        textLayer.opacity.setValueAtTime(sub.time, 0);
        textLayer.opacity.setValueAtTime(sub.time + 0.15, 100);
        textLayer.opacity.setValueAtTime(sub.time + sub.duration - 0.25, 100);
        textLayer.opacity.setValueAtTime(sub.time + sub.duration, 0);

        if (i === 3) {
            textLayer.scale.setValueAtTime(21.0, [0, 0]);
            textLayer.scale.setValueAtTime(21.4, [110, 110]);
            textLayer.scale.setValueAtTime(21.5, [100, 100]);
        }
    }
}

function addProfessionalTransitions(comp) {
    var flash1 = comp.layers.addSolid([1, 1, 1], "Flash_Intro_Build", WIDTH, HEIGHT, 1);
    flash1.startTime = 3.8;
    flash1.inPoint = 3.8;
    flash1.outPoint = 4.2;
    flash1.opacity.setValueAtTime(3.8, 0);
    flash1.opacity.setValueAtTime(3.92, 100);
    flash1.opacity.setValueAtTime(4.0, 100);
    flash1.opacity.setValueAtTime(4.1, 0);
    flash1.blendingMode = BlendingMode.SCREEN;

    var flash2 = comp.layers.addSolid([1, 1, 1], "Flash_Build_Drop", WIDTH, HEIGHT, 1);
    flash2.startTime = 8.8;
    flash2.inPoint = 8.8;
    flash2.outPoint = 9.2;
    flash2.opacity.setValueAtTime(8.8, 0);
    flash2.opacity.setValueAtTime(8.92, 100);
    flash2.opacity.setValueAtTime(9.0, 90);
    flash2.opacity.setValueAtTime(9.1, 0);
    flash2.blendingMode = BlendingMode.SCREEN;

    var blurTransition = comp.layers.addSolid([0, 0, 0], "Radial_Blur_Drop", WIDTH, HEIGHT, 1);
    blurTransition.startTime = 8.9;
    blurTransition.inPoint = 8.9;
    blurTransition.outPoint = 9.15;
    blurTransition.opacity.setValueAtTime(8.9, 30);
    blurTransition.opacity.setValueAtTime(9.0, 50);
    blurTransition.opacity.setValueAtTime(9.1, 0);
    
    var rb = blurTransition.property("Effects").addProperty("ADBE Radial Blur");
    rb.property("ADBE Radial Blur Amount").setValueAtTime(8.9, 0);
    rb.property("ADBE Radial Blur Amount").setValueAtTime(9.0, 50);
    rb.property("ADBE Radial Blur Amount").setValueAtTime(9.1, 0);

    var breakFlash = comp.layers.addSolid([1, 1, 1], "Flash_Drop_Break", WIDTH, HEIGHT, 1);
    breakFlash.startTime = 14.8;
    breakFlash.inPoint = 14.8;
    breakFlash.outPoint = 15.2;
    breakFlash.opacity.setValueAtTime(14.8, 0);
    breakFlash.opacity.setValueAtTime(14.95, 80);
    breakFlash.opacity.setValueAtTime(15.05, 0);
    breakFlash.blendingMode = BlendingMode.SCREEN;

    var outroFlash = comp.layers.addSolid([1, 1, 1], "Flash_Break_Outro", WIDTH, HEIGHT, 1);
    outroFlash.startTime = 18.8;
    outroFlash.inPoint = 18.8;
    outroFlash.outPoint = 19.4;
    outroFlash.opacity.setValueAtTime(18.8, 0);
    outroFlash.opacity.setValueAtTime(19.0, 100);
    outroFlash.opacity.setValueAtTime(19.2, 50);
    outroFlash.opacity.setValueAtTime(19.4, 0);
    outroFlash.blendingMode = BlendingMode.SCREEN;
}

function addPullZoomKeyframes(comp, cameraNull) {
    // Intro
    cameraNull.scale.setValueAtTime(0, [100, 100]);
    cameraNull.scale.setValueAtTime(2.0, [105, 105]);
    cameraNull.scale.setValueAtTime(4.0, [108, 108]);
    cameraNull.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2]);
    cameraNull.position.setValueAtTime(4.0, [WIDTH/2, HEIGHT/2 - 30]);
    cameraNull.rotation.setValueAtTime(0, 0);
    cameraNull.rotation.setValueAtTime(4.0, 2);

    // Build
    cameraNull.scale.setValueAtTime(4.0, [108, 108]);
    cameraNull.scale.setValueAtTime(6.0, [115, 115]);
    cameraNull.scale.setValueAtTime(8.0, [125, 125]);
    cameraNull.scale.setValueAtTime(9.0, [135, 135]);
    cameraNull.position.setValueAtTime(4.0, [WIDTH/2, HEIGHT/2 - 30]);
    cameraNull.position.setValueAtTime(7.0, [WIDTH/2 - 20, HEIGHT/2 - 50]);
    cameraNull.position.setValueAtTime(9.0, [WIDTH/2, HEIGHT/2 - 60]);
    cameraNull.rotation.setValueAtTime(4.0, 2);
    cameraNull.rotation.setValueAtTime(6.0, -3);
    cameraNull.rotation.setValueAtTime(8.0, 5);
    cameraNull.rotation.setValueAtTime(9.0, -2);

    // Drop
    cameraNull.scale.setValueAtTime(9.0, [135, 135]);
    cameraNull.scale.setValueAtTime(10.0, [120, 120]);
    cameraNull.scale.setValueAtTime(11.0, [140, 140]);
    cameraNull.scale.setValueAtTime(12.0, [115, 115]);
    cameraNull.scale.setValueAtTime(13.0, [150, 150]);
    cameraNull.scale.setValueAtTime(15.0, [100, 100]);
    cameraNull.position.setValueAtTime(9.0, [WIDTH/2, HEIGHT/2 - 60]);
    cameraNull.position.setValueAtTime(10.5, [WIDTH/2 + 50, HEIGHT/2 - 80]);
    cameraNull.position.setValueAtTime(12.0, [WIDTH/2 - 40, HEIGHT/2 - 100]);
    cameraNull.position.setValueAtTime(13.5, [WIDTH/2 + 30, HEIGHT/2 - 70]);
    cameraNull.position.setValueAtTime(15.0, [WIDTH/2, HEIGHT/2]);
    cameraNull.rotation.setValueAtTime(9.0, -2);
    cameraNull.rotation.setValueAtTime(10.5, 8);
    cameraNull.rotation.setValueAtTime(12.0, -6);
    cameraNull.rotation.setValueAtTime(13.5, 4);
    cameraNull.rotation.setValueAtTime(15.0, 0);

    // Break
    cameraNull.scale.setValueAtTime(15.0, [100, 100]);
    cameraNull.scale.setValueAtTime(17.0, [95, 95]);
    cameraNull.scale.setValueAtTime(19.0, [92, 92]);
    cameraNull.position.setValueAtTime(15.0, [WIDTH/2, HEIGHT/2]);
    cameraNull.position.setValueAtTime(17.0, [WIDTH/2, HEIGHT/2 + 20]);
    cameraNull.position.setValueAtTime(19.0, [WIDTH/2, HEIGHT/2 + 30]);

    // Outro
    cameraNull.scale.setValueAtTime(19.0, [92, 92]);
    cameraNull.scale.setValueAtTime(21.0, [88, 88]);
    cameraNull.scale.setValueAtTime(23.15, [85, 85]);
    cameraNull.position.setValueAtTime(19.0, [WIDTH/2, HEIGHT/2 + 30]);
    cameraNull.position.setValueAtTime(21.0, [WIDTH/2, HEIGHT/2 + 40]);
    cameraNull.position.setValueAtTime(23.15, [WIDTH/2, HEIGHT/2 + 50]);

    applyEasing(cameraNull.property("Scale"));
    applyEasing(cameraNull.property("Position"));
    applyEasing(cameraNull.property("Rotation"));
}

function applyEasing(prop) {
    for (var i = 1; i <= prop.numKeys; i++) {
        try {
            prop.setTemporalEaseAtKey(i, [new KeyframeEase(0, 70)], [new KeyframeEase(0, 70)]);
        } catch (e) {}
    }
}

function adjustLayerOrder(comp) {
    var layerNames = [
        "Foreground_Snow", "FX_Layer", "Outro_Vinland", "Thorfinn_Battle",
        "Battle_Vinland", "Main_Thorfinn", "Background_Vinland",
        "Audio Controller", "Global_Grading", "Soundtrack", "Camera_Controller"
    ];

    for (var i = 0; i < layerNames.length; i++) {
        var layer = findLayer(comp, layerNames[i]);
        if (layer && layer.isValid) {
            if (i === 0) {
                layer.moveToBeginning();
            } else {
                var prevLayer = findLayer(comp, layerNames[i-1]);
                if (prevLayer && prevLayer.isValid) {
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