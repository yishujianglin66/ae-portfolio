// ============================================================
// 《冰海战记》战斗剪辑完整合成脚本
// 基于 V4-Pro 深度策划的脚本自动生成
// 时长: 23.15秒 | BPM: 112.35
// ============================================================

var COMP_NAME = "VinlandSaga_Battle";
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

    // 导入素材
    var vinlandFootage = importFootage(VIDEO_PATH + "冰海战记.mp4");
    var thorfinnFootage = importFootage(VIDEO_PATH + "托尔芬.mp4");
    var audioFootage = importFootage(AUDIO_PATH + "ae实战音乐.mp3");

    // 添加音频轨道
    if (audioFootage) {
        var audioLayer = comp.layers.add(audioFootage);
        audioLayer.name = "Soundtrack";
        audioLayer.startTime = 0;
    }

    // 创建分层结构
    createLayerStructure(comp, vinlandFootage, thorfinnFootage);

    // 创建能量滑块控制器
    createAudioController(comp);

    // 添加全局调色
    createGlobalGrading(comp);

    // 添加音频驱动效果
    addAudioDrivenEffects(comp);

    // 添加字幕
    addSubtitles(comp);

    // 添加转场
    addTransitions(comp);

    return JSON.stringify({
        status: "success",
        compName: COMP_NAME,
        duration: DURATION,
        layers: comp.numLayers,
        message: "Composition created successfully"
    });
}

function createComposition(name, width, height, duration, fps) {
    try {
        var comp = app.project.items.addComp(name, width, height, 1, duration, fps);
        return comp;
    } catch (e) {
        // 尝试删除已存在的合成
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === name && app.project.item(i) instanceof CompItem) {
                app.project.item(i).remove();
                break;
            }
        }
        return app.project.items.addComp(name, width, height, 1, duration, fps);
    }
}

function importFootage(filePath) {
    try {
        var file = new File(filePath);
        if (!file.exists) return null;
        var footage = app.project.importFile(new ImportOptions(file));
        return footage;
    } catch (e) {
        return null;
    }
}

function createLayerStructure(comp, vinlandFootage, thorfinnFootage) {
    // 背景层 - 冰海战记素材（循环）
    var bgLayer = comp.layers.add(vinlandFootage);
    bgLayer.name = "Background_Vinland";
    bgLayer.startTime = 0;
    bgLayer.scale.setValueAtTime(0, [110, 110]);
    bgLayer.opacity.setValueAtTime(0, 80);

    // 主体层 - 托尔芬特写
    var mainLayer = comp.layers.add(thorfinnFootage);
    mainLayer.name = "Main_Thorfinn";
    mainLayer.startTime = 0;
    mainLayer.scale.setValueAtTime(0, [100, 100]);
    mainLayer.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2]);

    // 第二主体层 - 冰海战记战斗镜头
    var battleLayer = comp.layers.add(vinlandFootage);
    battleLayer.name = "Battle_Vinland";
    battleLayer.startTime = 4.0;
    battleLayer.scale.setValueAtTime(4.0, [105, 105]);
    battleLayer.opacity.setValueAtTime(4.0, 0);
    battleLayer.opacity.setValueAtTime(4.1, 100);
    battleLayer.opacity.setValueAtTime(9.0, 100);
    battleLayer.opacity.setValueAtTime(9.1, 0);

    // 前景粒子层（白色纯色层模拟雪花）
    var foregroundLayer = comp.layers.addSolid([1, 1, 1], "Foreground_Particles", WIDTH, HEIGHT, 1);
    foregroundLayer.name = "Foreground_Snow";
    foregroundLayer.startTime = 0;
    foregroundLayer.opacity.setValueAtTime(0, 15);
    foregroundLayer.blendingMode = BlendingMode.SCREEN;

    // 特效调整层
    var fxLayer = comp.layers.addSolid([1, 1, 1], "FX_Adjustment", WIDTH, HEIGHT, 1);
    fxLayer.name = "FX_Layer";
    fxLayer.startTime = 0;
    fxLayer.adjustmentLayer = true;
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

    // Color Balance
    var cb = gradingLayer.property("Effects").addProperty("ADBE Color Balance");
    cb.property("Shadows Red Balance").setValueAtTime(0, -10);
    cb.property("Shadows Green Balance").setValueAtTime(0, 5);
    cb.property("Shadows Blue Balance").setValueAtTime(0, 20);
    cb.property("Midtones Red Balance").setValueAtTime(0, -5);
    cb.property("Midtones Green Balance").setValueAtTime(0, 0);
    cb.property("Midtones Blue Balance").setValueAtTime(0, 10);
    cb.property("Highlights Red Balance").setValueAtTime(0, 5);
    cb.property("Highlights Green Balance").setValueAtTime(0, -5);
    cb.property("Highlights Blue Balance").setValueAtTime(0, 0);

    // Curves
    try {
        var curves = gradingLayer.property("Effects").addProperty("ADBE Curves");
        var curveProp = curves.property("ADBE Curves Curve");
        var curve = new Curve();
        curve.addKey(new Key(0, 0));
        curve.addKey(new Key(128, 110));
        curve.addKey(new Key(255, 255));
        curveProp.setValueAtTime(0, curve);
    } catch (e) {}

    // Vignette
    var vg = gradingLayer.property("Effects").addProperty("ADBE Vignette");
    vg.property("ADBE Vignette Amount").setValueAtTime(0, 20);
    vg.property("ADBE Vignette Feather").setValueAtTime(0, 50);

    // Saturation
    var sat = gradingLayer.property("Effects").addProperty("ADBE Saturation");
    sat.property("ADBE Saturation Master").setValueAtTime(0, -15);
}

function addAudioDrivenEffects(comp) {
    // 找到主体层
    var mainLayer = null;
    for (var i = 1; i <= comp.numLayers; i++) {
        if (comp.layer(i).name === "Main_Thorfinn") {
            mainLayer = comp.layer(i);
            break;
        }
    }

    if (mainLayer) {
        // Glow
        var glow = mainLayer.property("Effects").addProperty("ADBE Glow");
        glow.property("ADBE Glow Threshold").setValueAtTime(0, 0.5);
        glow.property("ADBE Glow Radius").setValueAtTime(0, 15);
        glow.property("ADBE Glow Intensity").setValueAtTime(0, 0.5);

        // Glow 表达式绑定高频能量
        glow.property("ADBE Glow Intensity").expression =
            "highEng = thisComp.layer(\"Audio Controller\").effect(\"HighFreq Energy\")(\"Slider\") / 100; " +
            "baseGlow = 0.3; maxGlow = 2.0; " +
            "baseGlow + (maxGlow - baseGlow) * highEng;";

        // Opacity 表达式
        mainLayer.property("Opacity").expression =
            "eng = thisComp.layer(\"Audio Controller\").effect(\"Global Energy\")(\"Slider\") / 100; " +
            "base = 70; amp = 30 * eng; " +
            "base + amp + Math.sin(time * Math.PI * 2 * 1.873) * (10 * eng);";

        // Rotation 表达式
        mainLayer.property("Rotation").expression =
            "eng = thisComp.layer(\"Audio Controller\").effect(\"Global Energy\")(\"Slider\") / 100; " +
            "accum = time * 5; " +
            "accum + Math.sin(time * Math.PI * 2 * 1.873) * (3 * eng);";
    }

    // 背景层模糊绑定低频能量
    var bgLayer = null;
    for (var j = 1; j <= comp.numLayers; j++) {
        if (comp.layer(j).name === "Background_Vinland") {
            bgLayer = comp.layer(j);
            break;
        }
    }

    if (bgLayer) {
        var blur = bgLayer.property("Effects").addProperty("ADBE Fast Blur");
        blur.property("ADBE Fast Blur Blurriness").expression =
            "lowEng = thisComp.layer(\"Audio Controller\").effect(\"LowFreq Energy\")(\"Slider\") / 100; " +
            "baseBlur = 2; maxBlur = 15; " +
            "baseBlur + (maxBlur - baseBlur) * lowEng;";
    }
}

function addSubtitles(comp) {
    var subtitles = [
        { time: 2.5, duration: 1.5, text: "戦士として…" },
        { time: 9.0, duration: 0.5, text: "今！" },
        { time: 14.0, duration: 1.0, text: "仇を越えて" },
        { time: 21.0, duration: 2.15, text: "VINLAND SAGA" }
    ];

    for (var i = 0; i < subtitles.length; i++) {
        var sub = subtitles[i];
        var textLayer = comp.layers.addText(sub.text);
        textLayer.name = "Subtitle_" + (i + 1);
        textLayer.startTime = sub.time;
        textLayer.inPoint = sub.time;
        textLayer.outPoint = sub.time + sub.duration;

        // 设置文字属性
        var sourceText = textLayer.property("Source Text");
        var textDoc = sourceText.getValueAtTime(0);
        textDoc.fontSize = (i === 3) ? 72 : 48;
        textDoc.fillColor = [0.839, 0.894, 0.941]; // 冷白色
        textDoc.strokeColor = [0.169, 0.306, 0.494]; // 冰蓝色描边
        textDoc.strokeWidth = 3;
        textDoc.strokeOverFill = true;
        textDoc.justification = ParagraphJustification.CENTER_JUSTIFY;
        sourceText.setValueAtTime(0, textDoc);

        // 位置居中
        textLayer.position.setValueAtTime(sub.time, [WIDTH/2, HEIGHT - 150]);

        // 淡入淡出
        textLayer.opacity.setValueAtTime(sub.time, 0);
        textLayer.opacity.setValueAtTime(sub.time + 0.2, 100);
        textLayer.opacity.setValueAtTime(sub.time + sub.duration - 0.3, 100);
        textLayer.opacity.setValueAtTime(sub.time + sub.duration, 0);

        // 标题特殊动画
        if (i === 3) {
            textLayer.scale.setValueAtTime(21.0, [0, 0]);
            textLayer.scale.setValueAtTime(21.5, [100, 100]);
            textLayer.opacity.setValueAtTime(21.0, 0);
            textLayer.opacity.setValueAtTime(21.5, 100);
        }
    }
}

function addTransitions(comp) {
    // Intro -> Build 转场 (4.0秒)
    var flash1 = comp.layers.addSolid([1, 1, 1], "Transition_Flash1", WIDTH, HEIGHT, 1);
    flash1.name = "Flash_Intro_Build";
    flash1.startTime = 3.9;
    flash1.inPoint = 3.9;
    flash1.outPoint = 4.1;
    flash1.opacity.setValueAtTime(3.9, 0);
    flash1.opacity.setValueAtTime(3.95, 100);
    flash1.opacity.setValueAtTime(4.0, 100);
    flash1.opacity.setValueAtTime(4.05, 0);
    flash1.blendingMode = BlendingMode.SCREEN;

    // Build -> Drop 转场 (9.0秒)
    var flash2 = comp.layers.addSolid([1, 1, 1], "Transition_Flash2", WIDTH, HEIGHT, 1);
    flash2.name = "Flash_Build_Drop";
    flash2.startTime = 8.9;
    flash2.inPoint = 8.9;
    flash2.outPoint = 9.15;
    flash2.opacity.setValueAtTime(8.9, 0);
    flash2.opacity.setValueAtTime(8.95, 100);
    flash2.opacity.setValueAtTime(9.0, 100);
    flash2.opacity.setValueAtTime(9.1, 0);
    flash2.blendingMode = BlendingMode.SCREEN;

    // Drop -> Break 转场 (15.0秒)
    var breakFlash = comp.layers.addSolid([1, 1, 1], "Transition_Break", WIDTH, HEIGHT, 1);
    breakFlash.name = "Flash_Drop_Break";
    breakFlash.startTime = 14.9;
    breakFlash.inPoint = 14.9;
    breakFlash.outPoint = 15.2;
    breakFlash.opacity.setValueAtTime(14.9, 0);
    breakFlash.opacity.setValueAtTime(15.0, 100);
    breakFlash.opacity.setValueAtTime(15.1, 0);
    breakFlash.blendingMode = BlendingMode.SCREEN;

    // Break -> Outro 转场 (19.0秒)
    var outroFlash = comp.layers.addSolid([1, 1, 1], "Transition_Outro", WIDTH, HEIGHT, 1);
    outroFlash.name = "Flash_Break_Outro";
    outroFlash.startTime = 18.9;
    outroFlash.inPoint = 18.9;
    outroFlash.outPoint = 19.3;
    outroFlash.opacity.setValueAtTime(18.9, 0);
    outroFlash.opacity.setValueAtTime(19.0, 100);
    outroFlash.opacity.setValueAtTime(19.2, 0);
    outroFlash.blendingMode = BlendingMode.SCREEN;
}

return main();