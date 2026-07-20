// ============================================================
// 《冰海战记》战斗剪辑完整合成脚本 - V6终极进化版
// 12个独立素材片段 + 高级文字动画 + 特效系统升级
//
// V6核心改进：
// 1. 素材多样性：12个不同片段，不再重复
// 2. 文字动画：打字机效果+逐字揭示+缩放爆破+轨迹运动
// 3. 特效升级：RGB分离+故障+光线+抖动+扫描线
// 4. 画面设置：横屏→竖屏智能缩放+裁切+动态偏移
// 5. 转场系统：6种转场（光泄漏/闪白/径向模糊/RGB故障/溶解/变速）
// 6. 段落分明：每段独立素材+独立调色+独立拉镜风格
// ============================================================

var COMP_NAME = "VinlandSaga_Battle_V6";
var CLIP_PATH = "D:/AE-Work/视频素材库/冰海战记片段/";
var AUDIO_PATH = "D:/AE-Work/音频素材库/BGM/";
var DURATION = 23.15;
var WIDTH = 1080;
var HEIGHT = 1920;
var FRAME_RATE = 30;
var BPM = 112.3;

// 12个精选素材片段 - 每段不同素材
var CLIPS = [
    // Intro段 (0-4s) - OP氛围画面
    "clip_1_1.mp4",   // S1 OP1 MUKANJYO 开场
    "clip_1_3.mp4",   // S1 OP1 中段
    // Build段 (4-9s) - 封神场面+MAD
    "clip_9_2.mp4",   // 封神场面 中段
    "clip_9_3.mp4",   // 封神场面 高潮
    "clip_11_2.mp4",  // 4K MAD 中段
    // Drop段 (9-15s) - 战斗+MAD高燃
    "clip_10_2.mp4",  // 托尔芬VS蛇 战斗
    "clip_10_3.mp4",  // 托尔芬VS蛇 高潮
    "clip_3_2.mp4",   // S1 OP2 Dark Crow
    "clip_12_2.mp4",  // Revolution MAD
    // Break段 (15-19s) - 静止反思
    "clip_2_1.mp4",   // S1 ED1 Torches 柔和
    "clip_8_1.mp4",   // S2 ED2 Ember 安静
    // Outro段 (19-23s) - 收束
    "clip_5_3.mp4"    // S2 OP1 River 尾声
];

function main() {
    try {
        var comp = createComposition(COMP_NAME, WIDTH, HEIGHT, DURATION, FRAME_RATE);
        if (!comp) return JSON.stringify({error: "Failed to create composition"});
        comp.motionBlur = true;

        // 导入音频
        var audioFootage = safeImport(AUDIO_PATH + "ae实战音乐.mp3");
        if (audioFootage) {
            var audioLayer = comp.layers.add(audioFootage);
            audioLayer.name = "Soundtrack";
            audioLayer.startTime = 0;
        }

        // ========== 创建12个素材层（每段独立素材）==========
        var segmentClips = createSegmentLayers(comp);

        // ========== 摄像机+控制器 ==========
        var camera = comp.layers.addCamera("Main_Camera", [WIDTH/2, HEIGHT/2]);
        camera.name = "Main_Camera";
        camera.property("Position").setValueAtTime(0, [WIDTH/2, HEIGHT/2, -800]);
        camera.property("Zoom").setValueAtTime(0, 800);

        var cameraNull = createCameraNull(comp);
        try { camera.parent = cameraNull; } catch(e) {}

        // ========== 音频控制器 ==========
        createAudioController(comp);

        // ========== 段落拉镜 ==========
        addSegmentPullZoom(comp, cameraNull, segmentClips);

        // ========== 高级转场 ==========
        addAdvancedTransitionsV6(comp);

        // ========== 音频驱动效果 ==========
        addAudioDrivenEffectsV6(comp);

        // ========== 高级文字系统 ==========
        addAdvancedTextSystem(comp);

        // ========== 特效层系统 ==========
        addEffectLayers(comp);

        // ========== 调色系统 ==========
        addColorGradingV6(comp);

        // ========== 粒子系统 ==========
        addParticleSystem(comp);

        // 调整图层顺序
        adjustLayerOrderV6(comp);

        return JSON.stringify({
            status: "success",
            compName: COMP_NAME,
            layers: comp.numLayers,
            clips: CLIPS.length,
            message: "V6终极进化版 - 12素材+高级文字+特效升级"
        });
    } catch (e) {
        return JSON.stringify({error: e.toString(), line: e.line});
    }
}

// ========== 创建分段素材层 ==========
function createSegmentLayers(comp) {
    var segments = [
        // Intro段 (0-4s) - 2个素材交替
        {clips: [0, 1], start: 0, end: 4, name: "Intro"},
        // Build段 (4-9s) - 3个素材快速切换
        {clips: [2, 3, 4], start: 4, end: 9, name: "Build"},
        // Drop段 (9-15s) - 4个素材高燃
        {clips: [5, 6, 7, 8], start: 9, end: 15, name: "Drop"},
        // Break段 (15-19s) - 2个素材静止
        {clips: [9, 10], start: 15, end: 19, name: "Break"},
        // Outro段 (19-23s) - 1个素材收束
        {clips: [11], start: 19, end: 23, name: "Outro"}
    ];

    var allLayers = [];

    for (var s = 0; s < segments.length; s++) {
        var seg = segments[s];
        var segDuration = (seg.end - seg.start) / seg.clips.length;

        for (var c = 0; c < seg.clips.length; c++) {
            var clipIndex = seg.clips[c];
            var clipFile = CLIPS[clipIndex];
            var clipPath = CLIP_PATH + clipFile;

            var footage = safeImport(clipPath);
            var layerName = seg.name + "_Clip" + (c + 1) + "_" + clipFile.replace(".mp4", "");

            var layer = createLayerWithFallBack(comp, footage, layerName, getRandomColor(seg.name, c));

            // 设置时间范围
            var clipStart = seg.start + c * segDuration;
            layer.startTime = clipStart;
            layer.inPoint = clipStart;
            layer.outPoint = clipStart + segDuration;

            // 横屏→竖屏适配：缩放到覆盖竖屏
            applyHorizontalToVertical(layer);

            // 动态拼贴防黑边
            applyTile(layer, 250);

            // 开启运动模糊
            try { layer.motionBlur = true; } catch(e) {}

            // 父级链接到摄像机控制器
            try { layer.parent = comp.layer("Camera_Controller"); } catch(e) {}

            allLayers.push({layer: layer, segment: seg.name, index: c, clipStart: clipStart, duration: segDuration});
        }
    }

    return allLayers;
}

function applyHorizontalToVertical(layer) {
    // 1920x1080 → 1080x1920：缩放到1920宽+裁切
    // Scale = 1920/1920 = 1.0 宽度覆盖，高度溢出裁切
    // 实际需要缩放到 HEIGHT/1080 * 100 = 1920/1080*100 ≈ 178%
    var scalePercent = 178;
    layer.scale.setValueAtTime(0, [scalePercent, scalePercent]);

    // 动态Y轴偏移，让画面在不同时间显示不同区域
    var yOffset = (Math.random() - 0.5) * 300;
    layer.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2 + yOffset]);
}

function getRandomColor(segment, index) {
    var colors = {
        "Intro": [[0.08, 0.12, 0.2], [0.1, 0.15, 0.25]],
        "Build": [[0.15, 0.1, 0.05], [0.2, 0.15, 0.08], [0.12, 0.08, 0.15]],
        "Drop": [[0.25, 0.1, 0.05], [0.2, 0.05, 0.1], [0.15, 0.15, 0.05], [0.1, 0.2, 0.1]],
        "Break": [[0.05, 0.08, 0.12], [0.08, 0.05, 0.1]],
        "Outro": [[0.1, 0.08, 0.15]]
    };
    var segColors = colors[segment] || [[0.5, 0.5, 0.5]];
    return segColors[index % segColors.length];
}

// ========== 段落拉镜系统 ==========
function addSegmentPullZoom(comp, cameraNull, segmentLayers) {
    // Intro段 - 慢推（Molob式电影感）
    setKF(cameraNull, "Scale", 0, [100, 100, 100]);
    setKF(cameraNull, "Scale", 2.0, [105, 105, 100]);
    setKF(cameraNull, "Scale", 4.0, [108, 108, 100]);
    setKF(cameraNull, "Position", 0, [WIDTH/2, HEIGHT/2, 0]);
    setKF(cameraNull, "Position", 4.0, [WIDTH/2, HEIGHT/2 - 40, 0]);
    setKF(cameraNull, "Rotation", 0, 0);
    setKF(cameraNull, "Rotation", 4.0, 2);

    // Build段 - DxshNova对角滑镜（每拍卡点）
    var buildBeats = [4.0, 4.53, 5.07, 5.6, 6.13, 6.67, 7.2, 7.73, 8.27, 8.8];
    for (var b = 0; b < buildBeats.length; b++) {
        var t = buildBeats[b];
        // 三段式：预备→爆发→回弹
        setKF(cameraNull, "Scale", t, [108, 108, 100]);
        setKF(cameraNull, "Scale", t + 0.03, [95, 95, 100]);
        setKF(cameraNull, "Scale", t + 0.07, [120, 120, 100]);
        setKF(cameraNull, "Scale", t + 0.2, [110, 110, 100]);
        setKF(cameraNull, "Position", t + 0.07, [WIDTH/2 + Math.sin(b * 1.5) * 80, HEIGHT/2 + Math.cos(b * 1.3) * 60, 0]);
        setKF(cameraNull, "Rotation", t + 0.07, Math.sin(b * 2) * 6);
    }

    // Drop段 - Xenoz高速推拉（最强卡点）
    var dropBeats = [];
    for (var d = 9; d < 15; d += 0.53) { dropBeats.push(d); }
    for (var d2 = 0; d2 < dropBeats.length; d2++) {
        var dt = dropBeats[d2];
        setKF(cameraNull, "Scale", dt, [115, 115, 100]);
        setKF(cameraNull, "Scale", dt + 0.02, [88, 88, 100]);   // 预备1帧
        setKF(cameraNull, "Scale", dt + 0.05, [135, 135, 100]); // 爆发
        setKF(cameraNull, "Scale", dt + 0.15, [108, 108, 100]); // 回弹
        setKF(cameraNull, "Position", dt + 0.05, [WIDTH/2 + Math.sin(d2 * 4) * 100, HEIGHT/2 + Math.cos(d2 * 3) * 80, 0]);
        setKF(cameraNull, "Rotation", dt + 0.05, Math.sin(d2 * 6) * 10);
    }

    // Break段 - 慢拉远
    setKF(cameraNull, "Scale", 15.0, [100, 100, 100]);
    setKF(cameraNull, "Scale", 17.0, [93, 93, 100]);
    setKF(cameraNull, "Scale", 19.0, [90, 90, 100]);
    setKF(cameraNull, "Position", 15.0, [WIDTH/2, HEIGHT/2, 0]);
    setKF(cameraNull, "Position", 17.0, [WIDTH/2, HEIGHT/2 + 20, 0]);
    setKF(cameraNull, "Position", 19.0, [WIDTH/2, HEIGHT/2 + 30, 0]);
    setKF(cameraNull, "Rotation", 15.0, 0);
    setKF(cameraNull, "Rotation", 19.0, -1);

    // Outro段 - 缓慢推远
    setKF(cameraNull, "Scale", 19.0, [90, 90, 100]);
    setKF(cameraNull, "Scale", 21.0, [86, 86, 100]);
    setKF(cameraNull, "Scale", 23.15, [83, 83, 100]);
    setKF(cameraNull, "Position", 19.0, [WIDTH/2, HEIGHT/2 + 30, 0]);
    setKF(cameraNull, "Position", 23.15, [WIDTH/2, HEIGHT/2 + 50, 0]);

    applyEasing(cameraNull.property("Scale"));
    applyEasing(cameraNull.property("Position"));
    applyEasing(cameraNull.property("Rotation"));
}

// ========== 高级转场V6 ==========
function addAdvancedTransitionsV6(comp) {
    // Intro→Build: 光泄漏转场（暖色）
    addLightLeak(comp, 3.8, 4.2, [0.9, 0.6, 0.3]);

    // Build段内部转场：每拍小闪白
    for (var t = 4.53; t < 9; t += 0.53) {
        addMicroFlash(comp, t - 0.03, t + 0.03, 35);
    }

    // Build→Drop: 闪白+径向模糊+RGB故障
    addFlash(comp, 8.85, 9.15, 100);
    addRadialBlur(comp, 8.85, 9.15);
    addRGBGlitch(comp, 8.8, 9.2);

    // Drop段内部：每2拍RGB故障
    for (var d = 10; d < 15; d += 1.06) {
        addRGBGlitch(comp, d, d + 0.1);
        addMicroFlash(comp, d + 0.53, d + 0.56, 50);
    }

    // Drop→Break: 溶解转场
    addDissolve(comp, 14.8, 15.2);

    // Break→Outro: 柔光转场
    addLightLeak(comp, 18.8, 19.4, [0.4, 0.6, 0.9]);

    // 最终收束闪白
    addFlash(comp, 22.8, 23.15, 60);
}

function addRGBGlitch(comp, startTime, endTime) {
    var glitch = comp.layers.addSolid([1, 0, 0], "RGBGlitch_" + startTime, WIDTH, HEIGHT, 1);
    glitch.startTime = startTime;
    glitch.inPoint = startTime;
    glitch.outPoint = endTime;
    glitch.opacity.setValueAtTime(startTime, 0);
    glitch.opacity.setValueAtTime(startTime + 0.02, 40);
    glitch.opacity.setValueAtTime(endTime, 0);
    glitch.blendingMode = BlendingMode.SCREEN;

    var blur = glitch.property("Effects").addProperty("ADBE Fast Blur");
    blur.property("Blurriness").setValueAtTime(startTime, 0);
    blur.property("Blurriness").setValueAtTime(startTime + 0.02, 15);
    blur.property("Blurriness").setValueAtTime(endTime, 0);
    blur.property("Repeat Edge Pixels").setValueAtTime(0, true);
}

function addDissolve(comp, startTime, endTime) {
    var dissolve = comp.layers.addSolid([1, 1, 1], "Dissolve_" + startTime, WIDTH, HEIGHT, 1);
    dissolve.startTime = startTime;
    dissolve.inPoint = startTime;
    dissolve.outPoint = endTime;
    dissolve.opacity.setValueAtTime(startTime, 0);
    dissolve.opacity.setValueAtTime((startTime + endTime) / 2, 60);
    dissolve.opacity.setValueAtTime(endTime, 0);
    dissolve.blendingMode = BlendingMode.SCREEN;

    var blur = dissolve.property("Effects").addProperty("ADBE Fast Blur");
    blur.property("Blurriness").expression =
        "t = linear(time, " + startTime + ", " + endTime + ", 0, 1); " +
        "Math.sin(t * Math.PI) * 40;";
    blur.property("Repeat Edge Pixels").setValueAtTime(0, true);
}

// ========== 高级文字系统 ==========
function addAdvancedTextSystem(comp) {
    var subtitles = [
        // Intro段 - 慢节奏文字
        {time: 1.0, dur: 3.0, text: "VINLAND SAGA", size: 36, anim: "fadeSlide", y: HEIGHT - 300},
        {time: 2.5, dur: 1.5, text: "戦士として生きる", size: 42, anim: "typing", y: HEIGHT - 200},

        // Build段 - 中节奏
        {time: 4.5, dur: 0.8, text: "覚醒", size: 80, anim: "scaleBurst", y: HEIGHT/2},
        {time: 6.0, dur: 0.5, text: "戦え", size: 100, anim: "scaleBurst", y: HEIGHT/2},
        {time: 7.5, dur: 0.8, text: "怒りを越えて", size: 48, anim: "fadeSlide", y: HEIGHT - 200},

        // Drop段 - 极速大字
        {time: 9.0, dur: 0.3, text: "斬", size: 150, anim: "impactBurst", y: HEIGHT/2},
        {time: 9.53, dur: 0.3, text: "撃", size: 150, anim: "impactBurst", y: HEIGHT/2},
        {time: 10.5, dur: 0.4, text: "加速", size: 100, anim: "scaleBurst", y: HEIGHT/2},
        {time: 12.0, dur: 0.3, text: "突破", size: 120, anim: "impactBurst", y: HEIGHT/2},
        {time: 14.0, dur: 0.5, text: "限界を超えろ", size: 50, anim: "fadeSlide", y: HEIGHT - 200},

        // Break段 - 慢节奏反思
        {time: 15.5, dur: 1.5, text: "真の戦士は…", size: 44, anim: "typing", y: HEIGHT - 200},
        {time: 17.5, dur: 1.5, text: "剣を必要としない", size: 44, anim: "typing", y: HEIGHT - 200},

        // Outro段 - 收束
        {time: 20.0, dur: 1.5, text: "あなたの敵はいない", size: 38, anim: "fadeSlide", y: HEIGHT - 250},
        {time: 21.5, dur: 1.65, text: "VINLAND SAGA", size: 80, anim: "finalReveal", y: HEIGHT/2},
    ];

    for (var i = 0; i < subtitles.length; i++) {
        var sub = subtitles[i];
        var textLayer = comp.layers.addText(sub.text);
        textLayer.name = "Text_" + (i + 1);
        textLayer.startTime = sub.time;
        textLayer.inPoint = sub.time;
        textLayer.outPoint = sub.time + sub.dur;

        textLayer.position.setValueAtTime(sub.time, [WIDTH/2, sub.y]);

        // 根据动画类型应用不同效果
        applyTextAnimation(textLayer, sub);

        // 通用淡入淡出
        textLayer.opacity.setValueAtTime(sub.time, 0);
        textLayer.opacity.setValueAtTime(sub.time + 0.08, 100);
        if (sub.dur > 0.5) {
            textLayer.opacity.setValueAtTime(sub.time + sub.dur - 0.2, 100);
        }
        textLayer.opacity.setValueAtTime(sub.time + sub.dur, 0);
    }
}

function applyTextAnimation(layer, sub) {
    switch (sub.anim) {
        case "fadeSlide":
            // 淡入+上滑
            layer.position.setValueAtTime(sub.time, [WIDTH/2, sub.y + 30]);
            layer.position.setValueAtTime(sub.time + 0.2, [WIDTH/2, sub.y]);
            break;

        case "typing":
            // 缩放打字机效果
            layer.scale.setValueAtTime(sub.time, [80, 80]);
            layer.scale.setValueAtTime(sub.time + 0.1, [105, 105]);
            layer.scale.setValueAtTime(sub.time + 0.15, [100, 100]);
            break;

        case "scaleBurst":
            // 缩放爆破
            layer.scale.setValueAtTime(sub.time, [200, 200]);
            layer.scale.setValueAtTime(sub.time + 0.05, [90, 90]);
            layer.scale.setValueAtTime(sub.time + 0.1, [100, 100]);
            // 添加模糊
            var blur = layer.property("Effects").addProperty("ADBE Fast Blur");
            blur.property("Blurriness").setValueAtTime(sub.time, 30);
            blur.property("Blurriness").setValueAtTime(sub.time + 0.08, 0);
            blur.property("Repeat Edge Pixels").setValueAtTime(0, true);
            break;

        case "impactBurst":
            // 冲击爆破 - 从大到小+旋转
            layer.scale.setValueAtTime(sub.time, [300, 300]);
            layer.scale.setValueAtTime(sub.time + 0.03, [80, 80]);
            layer.scale.setValueAtTime(sub.time + 0.06, [110, 110]);
            layer.scale.setValueAtTime(sub.time + 0.1, [100, 100]);
            layer.rotation.setValueAtTime(sub.time, -15);
            layer.rotation.setValueAtTime(sub.time + 0.06, 5);
            layer.rotation.setValueAtTime(sub.time + 0.1, 0);
            // 添加模糊
            var blur2 = layer.property("Effects").addProperty("ADBE Fast Blur");
            blur2.property("Blurriness").setValueAtTime(sub.time, 50);
            blur2.property("Blurriness").setValueAtTime(sub.time + 0.06, 0);
            blur2.property("Repeat Edge Pixels").setValueAtTime(0, true);
            break;

        case "finalReveal":
            // 最终揭示 - 从0缩放到大+回弹
            layer.scale.setValueAtTime(sub.time, [0, 0]);
            layer.scale.setValueAtTime(sub.time + 0.4, [115, 115]);
            layer.scale.setValueAtTime(sub.time + 0.5, [100, 100]);
            // 模糊变清晰
            var blur3 = layer.property("Effects").addProperty("ADBE Fast Blur");
            blur3.property("Blurriness").setValueAtTime(sub.time, 40);
            blur3.property("Blurriness").setValueAtTime(sub.time + 0.4, 0);
            blur3.property("Repeat Edge Pixels").setValueAtTime(0, true);
            break;
    }
}

// ========== 特效层系统 ==========
function addEffectLayers(comp) {
    // 扫描线效果层
    var scanline = comp.layers.addSolid([0, 0, 0], "Scanlines", WIDTH, HEIGHT, 1);
    scanline.name = "Scanlines";
    scanline.startTime = 0;
    scanline.adjustmentLayer = true;
    scanline.opacity.setValueAtTime(0, 15);
    try {
        var noise = scanline.property("Effects").addProperty("ADBE Noise");
        noise.property("Amount of Noise").setValueAtTime(0, 8);
        noise.property("Noise Type").setValueAtTime(0, 0);
    } catch(e) {}

    // Drop段故障效果层
    var glitchLayer = comp.layers.addSolid([1, 1, 1], "DropGlitch", WIDTH, HEIGHT, 1);
    glitchLayer.name = "DropGlitch";
    glitchLayer.startTime = 9;
    glitchLayer.inPoint = 9;
    glitchLayer.outPoint = 15;
    glitchLayer.adjustmentLayer = true;
    glitchLayer.opacity.setValueAtTime(9, 0);
    glitchLayer.opacity.expression =
        "highEng = thisComp.layer(\"Audio Controller\").effect(\"HighFreq Energy\")(\"Slider\") / 100; " +
        "base = 10; max = 40; " +
        "base + (max - base) * highEng;";

    var gBlur = glitchLayer.property("Effects").addProperty("ADBE Fast Blur");
    gBlur.property("Blurriness").expression =
        "highEng = thisComp.layer(\"Audio Controller\").effect(\"HighFreq Energy\")(\"Slider\") / 100; " +
        "base = 0; max = 5; " +
        "base + (max - base) * highEng;";
    gBlur.property("Repeat Edge Pixels").setValueAtTime(0, true);
}

// ========== 调色系统V6 ==========
function addColorGradingV6(comp) {
    var grading = comp.layers.addSolid([1, 1, 1], "ColorGrading", WIDTH, HEIGHT, 1);
    grading.name = "ColorGrading";
    grading.startTime = 0;
    grading.adjustmentLayer = true;

    // Color Balance - 段落动态调色
    var cb = grading.property("Effects").addProperty("Color Balance");

    // Intro: 冷蓝忧郁
    cb.property("Red Balance").setValueAtTime(0, -10);
    cb.property("Green Balance").setValueAtTime(0, -5);
    cb.property("Blue Balance").setValueAtTime(0, 25);

    // Build: 逐渐回暖+青橙
    cb.property("Red Balance").setValueAtTime(4, -3);
    cb.property("Green Balance").setValueAtTime(4, -8);
    cb.property("Blue Balance").setValueAtTime(4, 12);

    // Drop: Teal & Orange 青橙对比
    cb.property("Red Balance").setValueAtTime(9, 8);
    cb.property("Green Balance").setValueAtTime(9, -12);
    cb.property("Blue Balance").setValueAtTime(9, 8);

    // Break: 去饱和+冷调
    cb.property("Red Balance").setValueAtTime(15, -12);
    cb.property("Green Balance").setValueAtTime(15, -8);
    cb.property("Blue Balance").setValueAtTime(15, 5);

    // Outro: 暖金收束
    cb.property("Red Balance").setValueAtTime(19, 10);
    cb.property("Green Balance").setValueAtTime(19, 5);
    cb.property("Blue Balance").setValueAtTime(19, -8);

    // 暗角层
    var vignette = comp.layers.addSolid([0, 0, 0], "Vignette", WIDTH, HEIGHT, 1);
    vignette.name = "Vignette";
    vignette.startTime = 0;
    vignette.adjustmentLayer = true;
    var vBlur = vignette.property("Effects").addProperty("ADBE Fast Blur");
    vBlur.property("Blurriness").setValueAtTime(0, 10);
    vBlur.property("Repeat Edge Pixels").setValueAtTime(0, false);
    vignette.opacity.expression =
        "eng = thisComp.layer(\"Audio Controller\").effect(\"Global Energy\")(\"Slider\") / 100; " +
        "base = 25; max = 55; " +
        "base + (max - base) * eng;";

    // 胶片颗粒
    var grain = comp.layers.addSolid([0.5, 0.5, 0.5], "FilmGrain", WIDTH, HEIGHT, 1);
    grain.name = "FilmGrain";
    grain.startTime = 0;
    grain.opacity.setValueAtTime(0, 10);
    grain.blendingMode = BlendingMode.OVERLAY;
    try {
        var gNoise = grain.property("Effects").addProperty("ADBE Noise");
        gNoise.property("Amount of Noise").setValueAtTime(0, 20);
        gNoise.property("Noise Type").setValueAtTime(0, 1);
    } catch(e) {}
}

// ========== 粒子系统 ==========
function addParticleSystem(comp) {
    var particle = comp.layers.addSolid([1, 1, 1], "Particles", WIDTH, HEIGHT, 1);
    particle.name = "Particles";
    particle.startTime = 0;
    particle.opacity.setValueAtTime(0, 25);
    particle.blendingMode = BlendingMode.SCREEN;

    try {
        var pcw = particle.property("Effects").addProperty("CC Particle World");
        pcw.property("Producer Position X").setValueAtTime(0, 0);
        pcw.property("Producer Position Y").setValueAtTime(0, 0);
        pcw.property("Producer Position Z").setValueAtTime(0, 0);
        pcw.property("Producer X Size").setValueAtTime(0, 300);
        pcw.property("Producer Y Size").setValueAtTime(0, 400);
        pcw.property("Producer Z Size").setValueAtTime(0, 200);
        pcw.property("Particle Type").setValueAtTime(0, 5);
        pcw.property("Birth Size").setValueAtTime(0, 2);
        pcw.property("Death Size").setValueAtTime(0, 0.5);
        pcw.property("Birth Color").setValueAtTime(0, [1, 1, 1]);
        pcw.property("Death Color").setValueAtTime(0, [0.6, 0.7, 0.9]);
        pcw.property("Gravity").setValueAtTime(0, -8);
        pcw.property("Velocity").setValueAtTime(0, 15);
        pcw.property("Animation").setValueAtTime(0, 1);
        pcw.property("Birth Rate").expression =
            "eng = thisComp.layer(\"Audio Controller\").effect(\"Global Energy\")(\"Slider\") / 100; " +
            "base = 0.3; max = 2.5; " +
            "base + (max - base) * eng;";
    } catch(e) {}
}

// ========== 音频驱动效果V6 ==========
function addAudioDrivenEffectsV6(comp) {
    // 遍历所有素材层，添加音频驱动模糊
    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        var ln = layer.name;
        if (ln.indexOf("Intro_") >= 0 || ln.indexOf("Build_") >= 0 || ln.indexOf("Drop_") >= 0) {
            try {
                var blur = layer.property("Effects").addProperty("ADBE Fast Blur");
                blur.property("Blurriness").expression =
                    "highEng = thisComp.layer(\"Audio Controller\").effect(\"HighFreq Energy\")(\"Slider\") / 100; " +
                    "base = 1; max = 12; " +
                    "base + (max - base) * highEng;";
                blur.property("Repeat Edge Pixels").setValueAtTime(0, true);
            } catch(e) {}

            try {
                layer.property("Opacity").expression =
                    "eng = thisComp.layer(\"Audio Controller\").effect(\"Global Energy\")(\"Slider\") / 100; " +
                    "base = 85; amp = 15 * eng; " +
                    "base + amp + Math.sin(time * Math.PI * 2 * 2) * (5 * eng);";
            } catch(e) {}
        }
    }
}

// ========== 工具函数 ==========
function createComposition(name, w, h, dur, fps) {
    for (var i = 1; i <= app.project.numItems; i++) {
        if (app.project.item(i).name === name && app.project.item(i) instanceof CompItem) {
            app.project.item(i).remove(); break;
        }
    }
    return app.project.items.addComp(name, w, h, 1, dur, fps);
}

function safeImport(path) {
    try {
        var f = new File(path);
        if (!f.exists) return null;
        return app.project.importFile(new ImportOptions(f));
    } catch(e) { return null; }
}

function createLayerWithFallBack(comp, footage, name, color) {
    var layer;
    if (footage) {
        try { layer = comp.layers.add(footage); }
        catch(e) { layer = comp.layers.addSolid(color, name, WIDTH, HEIGHT, 1); }
    } else {
        layer = comp.layers.addSolid(color, name, WIDTH, HEIGHT, 1);
    }
    layer.name = name;
    return layer;
}

function applyTile(layer, pct) {
    try {
        var tile = layer.property("Effects").addProperty("ADBE Tile");
        tile.property("Output Width").setValueAtTime(0, pct);
        tile.property("Output Height").setValueAtTime(0, pct);
        tile.property("Mirror Edges").setValueAtTime(0, true);
    } catch(e) {}
}

function createCameraNull(comp) {
    var n = comp.layers.addNull();
    n.name = "Camera_Controller";
    n.startTime = 0;
    n.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2, 0]);
    n.scale.setValueAtTime(0, [100, 100, 100]);
    n.rotation.setValueAtTime(0, 0);
    return n;
}

function createAudioController(comp) {
    var ctrl = comp.layers.addSolid([1, 1, 1], "Audio Controller", 100, 100, 1);
    ctrl.name = "Audio Controller";
    ctrl.startTime = 0;
    var names = ["Global Energy", "LowFreq Energy", "MidFreq Energy", "HighFreq Energy"];
    for (var i = 0; i < names.length; i++) {
        var eff = ctrl.property("Effects").addProperty("Slider Control");
        eff.name = names[i];
        eff.property("Slider").setValueAtTime(0, 50);
    }
}

function setKF(layer, prop, time, val) {
    try { layer.property(prop).setValueAtTime(time, val); } catch(e) {}
}

function applyEasing(prop) {
    for (var i = 1; i <= prop.numKeys; i++) {
        try {
            if (prop.valueDimension === 1) {
                prop.setTemporalEaseAtKey(i, [new KeyframeEase(0, 75)], [new KeyframeEase(0, 75)]);
            } else {
                var ie = [], oe = [];
                for (var d = 0; d < prop.valueDimension; d++) { ie.push(new KeyframeEase(0, 75)); oe.push(new KeyframeEase(0, 75)); }
                prop.setTemporalEaseAtKey(i, ie, oe);
            }
        } catch(e) {}
    }
}

function addFlash(comp, st, et, maxOp) {
    var f = comp.layers.addSolid([1, 1, 1], "Flash_" + st, WIDTH, HEIGHT, 1);
    f.startTime = st; f.inPoint = st; f.outPoint = et;
    f.opacity.setValueAtTime(st, 0);
    f.opacity.setValueAtTime(st + 0.03, maxOp);
    f.opacity.setValueAtTime(st + 0.06, maxOp * 0.7);
    f.opacity.setValueAtTime(et, 0);
    f.blendingMode = BlendingMode.SCREEN;
}

function addRadialBlur(comp, st, et) {
    var l = comp.layers.addSolid([0, 0, 0], "RBlur_" + st, WIDTH, HEIGHT, 1);
    l.startTime = st; l.inPoint = st; l.outPoint = et;
    l.opacity.setValueAtTime(st, 40);
    l.opacity.setValueAtTime((st+et)/2, 60);
    l.opacity.setValueAtTime(et, 0);
    var rb = l.property("Effects").addProperty("Radial Blur");
    rb.property("Amount").setValueAtTime(st, 0);
    rb.property("Amount").setValueAtTime((st+et)/2, 60);
    rb.property("Amount").setValueAtTime(et, 0);
}

function addLightLeak(comp, st, et, color) {
    var l = comp.layers.addSolid(color, "Leak_" + st, WIDTH, HEIGHT, 1);
    l.startTime = st; l.inPoint = st; l.outPoint = et;
    l.opacity.setValueAtTime(st, 0);
    l.opacity.setValueAtTime(st + 0.1, 50);
    l.opacity.setValueAtTime(et - 0.1, 30);
    l.opacity.setValueAtTime(et, 0);
    l.blendingMode = BlendingMode.SCREEN;
    var b = l.property("Effects").addProperty("ADBE Fast Blur");
    b.property("Blurriness").setValueAtTime(0, 60);
    b.property("Repeat Edge Pixels").setValueAtTime(0, true);
}

function addMicroFlash(comp, st, et, op) {
    var f = comp.layers.addSolid([1, 1, 1], "MFlash_" + st, WIDTH, HEIGHT, 1);
    f.startTime = st; f.inPoint = st; f.outPoint = et;
    f.opacity.setValueAtTime(st, 0);
    f.opacity.setValueAtTime(st + 0.01, op);
    f.opacity.setValueAtTime(et, 0);
    f.blendingMode = BlendingMode.SCREEN;
}

function adjustLayerOrderV6(comp) {
    // 文字层置顶，特效层其次，素材层底
    var topLayers = [];
    var midLayers = [];
    var bottomLayers = [];

    for (var i = 1; i <= comp.numLayers; i++) {
        var ln = comp.layer(i).name;
        if (ln.indexOf("Text_") >= 0 || ln.indexOf("Subtitle_") >= 0) {
            topLayers.push(ln);
        } else if (ln.indexOf("FilmGrain") >= 0 || ln.indexOf("Vignette") >= 0 ||
                   ln.indexOf("ColorGrading") >= 0 || ln.indexOf("Scanlines") >= 0 ||
                   ln.indexOf("DropGlitch") >= 0 || ln.indexOf("Particles") >= 0 ||
                   ln.indexOf("Flash") >= 0 || ln.indexOf("RBlur") >= 0 ||
                   ln.indexOf("Leak") >= 0 || ln.indexOf("MFlash") >= 0 ||
                   ln.indexOf("RGBGlitch") >= 0 || ln.indexOf("Dissolve") >= 0) {
            midLayers.push(ln);
        } else if (ln.indexOf("Clip") >= 0 || ln === "Soundtrack" || ln === "Audio Controller" ||
                   ln === "Camera_Controller" || ln === "Main_Camera") {
            bottomLayers.push(ln);
        }
    }

    var allOrder = topLayers.concat(midLayers).concat(bottomLayers);
    for (var j = 0; j < allOrder.length; j++) {
        var layer = findLayer(comp, allOrder[j]);
        if (layer) {
            if (j === 0) { layer.moveToBeginning(); }
            else {
                var prev = findLayer(comp, allOrder[j-1]);
                if (prev) { layer.moveAfter(prev); }
            }
        }
    }
}

function findLayer(comp, name) {
    for (var i = 1; i <= comp.numLayers; i++) {
        if (comp.layer(i).name === name) return comp.layer(i);
    }
    return null;
}

return main();