// ============================================================
// 《冰海战记》V13 - 电影感镜头语言重编排
//
// 基于 V12 (V11 AE合成 + DaVinci调色) 的全面升级
//
// V13 核心创新:
// 1. 全新无水印素材 (9个新源: NCOP/ED/战斗/MAD/4K MAD)
// 2. 五大电影感镜头语言分段落应用:
//    - Intro/Break: Molob 电影感慢推+3D视差 (15-25帧慢推)
//    - Build: Floby 旋转拉镜 (Rotation ±8° + 不等比缩放)
//    - Drop: Xenoz 鱼眼推拉 (3-8帧极速切换 + 速度斜坡)
//    - Outro: DxshNova 标准骨架 + 高潮推拉
// 3. 三层调色体系: Kodak LUT + 青橙(Teal&Orange) + 段落级色调
// 4. 节拍精密对齐 (BPM=112.35, beat=0.5341s, 视觉提前20ms补偿)
// 5. 匹配剪辑 (Match Cut) + 速度斜坡 (Speed Ramp)
// 6. 横转竖专业方案 (主层+模糊背景+水印遮挡)
//
// BGM: ae实战音乐.mp3 (BPM 112.35, 时长 23.15s, 37节拍)
// 分辨率: 1080x1920 竖屏 / 30fps
// ============================================================

var COMP_NAME = "VinlandSaga_Cinematic_V13";

// AE 2025 路径
var LUT_CREATIVE = "C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/Lumetri/LUTs/Creative/";
var LUT_TECHNICAL = "C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/Lumetri/LUTs/Technical/";

var CLIP_PATH = "D:/AE-Work/视频素材库/冰海战记新素材/";
var AUDIO_PATH = "D:/AE-Work/音频素材库/BGM/";
var DURATION = 23.15;
var WIDTH = 1080;
var HEIGHT = 1920;
var FRAME_RATE = 30;
var BPM = 112.35;
var BEAT_INTERVAL = 60.0 / BPM;  // 0.5341s
var VISUAL_ADVANCE = 0.02;  // 视觉提前20ms补偿 (感知层)

// V13.5补偿: 分级视觉提前量 (不同效果类型感知延迟不同)
var ADVANCE = {
    Scale:      0.030,  // Scale弹跳: 30ms
    Flash:      0.015,  // 闪白/微闪: 15ms
    RGBGlitch:  0.010,  // RGB故障: 10ms
    Transition: 0.020,  // 转场: 20ms
    Position:   0.025,  // 位移: 25ms
    Rotation:   0.020   // 旋转: 20ms
};

// ============ 新无水印素材清单 (9个源) ============
// 运动量分析: vinland_3(61.67)>vinland_1_p07(54.41)>vinland_5(55.58)>vinland_1_p03(52.97)>vinland_1_p01(51.89)>vinland_1_p05(44.26)>vinland_1_p02(28.51)>vinland_2(16.28)
var SOURCES = {
    "MUKANJYO":  "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p01 S1OP1-MUKANJYO.f30077.mp4",
    "TORCHES":   "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p02 S1ED1-Torches.f30080.mp4",
    "DarkCrow":  "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p03 S1OP2-Dark Crow.f30077.mp4",
    "RIVER":     "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p05 S2OP1-River.f30077.mp4",
    "PARADOX":   "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p07 S2OP2-Paradox.f30080.mp4",
    "EPIC_S1":   "vinland_2_冰海战记第一季:最后的封神场面.f30080.mp4",
    "FIGHT_S2":  "vinland_3_【授权转载】冰海战记第二季最精彩的打戏 托尔芬VS蛇.f30077.mp4",
    "MAD_4K":    "vinland_4_4K_MAD.f30077.mp4",           // 新增: 4K 60fps MAD, 时长200.83s, 运动=52.21
    "MAD_REV":   "vinland_5_【MAD⧸冰海战记】There's a revolution coming!.f30080.mp4"
};

// ============ V13 段落编排 (电影感镜头语言) ============
// 每段: name/起止时间/镜头技法/素材清单(源+源起始+时长)/色调
var SEGMENTS = [
    {
        name: "Intro", start: 0, end: 4, technique: "Molob_SlowPush",
        clips: [
            {src: "EPIC_S1",  srcStart: 30, dur: 2.0},   // S1封神慢镜 (motion 16.28)
            {src: "TORCHES",  srcStart: 45, dur: 2.0}    // Torches抒情 (motion 28.51)
        ],
        colorTint: {hue: 200, sat: 15, temp: -10, label: "冷蓝-北欧海洋"}
    },
    {
        name: "Build", start: 4, end: 9, technique: "Floby_Rotation",
        clips: [
            {src: "DarkCrow", srcStart: 50, dur: 1.67},  // Dark Crow OP (motion 52.97)
            {src: "RIVER",    srcStart: 45, dur: 1.67},  // River S2OP1 (motion 44.26)
            {src: "DarkCrow", srcStart: 60, dur: 1.66}   // Dark Crow 第二段
        ],
        colorTint: {hue: 30, sat: 20, temp: 10, label: "暖橙-火光预热"}
    },
    {
        name: "Drop", start: 9, end: 15, technique: "Xenoz_FastPush",
        clips: [
            {src: "FIGHT_S2", srcStart: 20, dur: 1.5},   // 托尔芬VS蛇 战斗1 (motion 61.67 最高)
            {src: "FIGHT_S2", srcStart: 30, dur: 1.5},   // 战斗2
            {src: "FIGHT_S2", srcStart: 40, dur: 1.5},   // 战斗3
            {src: "FIGHT_S2", srcStart: 50, dur: 1.5}    // 战斗4
        ],
        colorTint: {hue: 0, sat: 25, temp: 5, label: "血红-战斗高潮"}
    },
    {
        name: "Break", start: 15, end: 19, technique: "Molob_SlowPull",
        clips: [
            {src: "MUKANJYO", srcStart: 60, dur: 2.0},   // MUKANJYO OP慢镜 (motion 51.89, 之前未使用)
            {src: "MAD_4K",   srcStart: 150, dur: 2.0}   // 新增4K MAD抒情段 (motion 52.21, 新增素材)
        ],
        colorTint: {hue: 220, sat: 10, temp: -15, label: "冷蓝-情感沉淀"}
    },
    {
        name: "Outro", start: 19, end: 23.15, technique: "DxshNova_Standard",
        clips: [
            {src: "PARADOX",  srcStart: 50, dur: 2.075}, // Paradox S2OP2 (motion 54.41)
            {src: "MAD_REV",  srcStart: 100, dur: 2.075} // MAD revolution (motion 55.58)
        ],
        colorTint: {hue: 30, sat: 15, temp: 5, label: "暖→冷渐变-史诗收尾"}
    }
];

function main() {
    try {
        var comp = createComposition(
            COMP_NAME, WIDTH, HEIGHT, DURATION, FRAME_RATE
        );
        if (!comp) return JSON.stringify({error: "comp fail"});
        comp.motionBlur = true;

        // ===== 音频层 =====
        var af = safeImport(AUDIO_PATH + "ae实战音乐.mp3");
        if (af) {
            var al = comp.layers.add(af);
            al.name = "BGM_Soundtrack";
            al.startTime = 0;
        }

        // ===== 3D 摄像机 + 空对象控制器 (Donya 三维空间基础) =====
        var cam = comp.layers.addCamera("Cinema_Camera", [WIDTH/2, HEIGHT/2]);
        cam.property("Position").setValueAtTime(0, [WIDTH/2, HEIGHT/2, -800]);
        cam.property("Zoom").setValueAtTime(0, 800);
        // 开启景深 (Donya 2.5D视差核心)
        try {
            cam.property("Depth of Field").setValue(1);
            cam.property("Focus Distance").setValueAtTime(0, 800);
            cam.property("Aperture").setValueAtTime(0, 50);
        } catch(e) {}

        var cNull = createCameraNull(comp);
        try { cam.parent = cNull; } catch(e) {}

        // ===== 段落素材层 + 横转竖 =====
        var segs = createCinematicSegments(comp);

        // ===== V13 镜头语言: 分段落应用电影感技法 =====
        applyCinematicTechniques(comp, cNull);

        // ===== 节拍精密对齐关键帧 (BPM驱动) =====
        applyBeatSyncKeyframes(comp, cNull);

        // ===== V13.5补偿: 背景层预合成 (性能优化) =====
        precomposeBackgrounds(comp);

        // ===== 三层调色体系 =====
        applyThreeLayerGrading(comp);

        // ===== 转场系统 =====
        addCinematicTransitions(comp);

        // ===== 音频驱动效果 =====
        addAudioDrivenEffectsV13(comp);

        // ===== 文字系统 =====
        addCinematicTextSystem(comp);

        // ===== 战斗粒子 (Drop段) =====
        addBattleParticlesV13(comp);

        // ===== V13.5补偿: 粒子代理模式 (性能优化) =====
        setupParticleProxy(comp);

        // ===== 氛围光效 =====
        addAtmosphereV13(comp);

        // ===== 图层顺序 =====
        adjustLayerOrderV13(comp);

        return JSON.stringify({
            status: "success",
            compName: COMP_NAME,
            layers: comp.numLayers,
            segments: SEGMENTS.length,
            totalClips: SEGMENTS.reduce(function(s, seg) { return s + seg.clips.length; }, 0),
            technique: "Cinematic V13 - 5 Lens Languages",
            version: "V13"
        });
    } catch (e) {
        return JSON.stringify({error: e.toString(), line: e.line});
    }
}

// ========== 创建合成 ==========
function createComposition(name, w, h, dur, fps) {
    var proj = app.project;
    var existing = proj.items.byName(name);
    if (existing) existing.remove();
    var comp = proj.items.addComposition(name, w, h, 1, dur, fps);
    return comp;
}

// ========== 创建段落素材层 (带时间重映射) ==========
function createCinematicSegments(comp) {
    var allSegs = [];
    for (var si = 0; si < SEGMENTS.length; si++) {
        var seg = SEGMENTS[si];
        var segDur = (seg.end - seg.start) / seg.clips.length;
        for (var ci = 0; ci < seg.clips.length; ci++) {
            var clipInfo = seg.clips[ci];
            var srcFile = CLIP_PATH + SOURCES[clipInfo.src];
            var ft = safeImport(srcFile);
            if (!ft) continue;

            var layerName = seg.name + "_C" + (ci+1) + "_" + clipInfo.src;
            var ly = comp.layers.add(ft);
            ly.name = layerName;
            ly.motionBlur = true;

            // 段落起始时间
            var compStart = seg.start + ci * segDur;
            ly.startTime = compStart;
            ly.inPoint = compStart;
            ly.outPoint = compStart + segDur;

            // V13.5补偿: srcStart 安全校验
            var srcDur = ft ? ft.duration : 0;
            if (srcDur > 0 && clipInfo.srcStart + segDur + 0.1 > srcDur) {
                clipInfo.srcStart = Math.max(0, srcDur - segDur - 0.1);
            }

            // 时间重映射: 从源视频的 srcStart 位置开始播放
            try {
                ly.timeRemapEnabled = true;
                var tr = ly.property("Time Remap");
                tr.setValueAtTime(compStart, clipInfo.srcStart);
                tr.setValueAtTime(compStart + segDur, clipInfo.srcStart + segDur);
            } catch(e) {}

            // 横转竖专业方案 (V8修复版): 主层+模糊背景+水印遮挡
            applyHorizontalToVerticalV13(comp, ly, ft, compStart, segDur);

            // 链接到摄像机控制器
            try { ly.parent = comp.layer("Camera_Controller"); } catch(e) {}

            allSegs.push({
                layer: ly, seg: seg.name, technique: seg.technique,
                start: compStart, dur: segDur, clipInfo: clipInfo,
                colorTint: seg.colorTint
            });
        }
    }
    return allSegs;
}

// ========== 横转竖专业方案 V13 (基于 V8 修复版) ==========
function applyHorizontalToVerticalV13(comp, layer, ft, cs, sd) {
    // 主层: 宽度填满合成,完整显示横屏画面 (Scale 56.25%)
    var sp = 56.25;
    layer.scale.setValueAtTime(0, [sp, sp]);
    layer.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2]);

    // 背景层: 同素材放大铺满 + 高斯模糊 + 降亮度
    if (!ft) return;
    try {
        var bg = comp.layers.add(ft);
        bg.name = layer.name + "_BG";
        bg.startTime = cs;
        bg.inPoint = cs;
        bg.outPoint = cs + sd;
        bg.scale.setValueAtTime(0, [220, 220]);
        var yo = (Math.random() - 0.5) * 200;
        bg.position.setValueAtTime(0, [WIDTH/2, HEIGHT/2 + yo]);

        // 背景同步时间重映射
        try {
            bg.timeRemapEnabled = true;
            var tr = bg.property("Time Remap");
            var mainLayerName = layer.name;
            tr.expression = "var main = thisComp.layer(\"" + mainLayerName + "\");\nmain.timeRemap.valueAtTime(time);";
        } catch(e) {}

        var blur = bg.property("Effects").addProperty("ADBE Fast Blur");
        blur.property("Blurriness").setValue(80);
        blur.property("Repeat Edge Pixels").setValue(true);

        var br = bg.property("Effects").addProperty("Brightness & Contrast");
        br.property("Brightness").setValue(-35);
        br.property("Contrast").setValue(15);

        bg.moveAfter(layer);
        bg.motionBlur = true;
        try { bg.parent = comp.layer("Camera_Controller"); } catch(e) {}
    } catch(e) {}
}

// ========== V13 镜头语言: 分段落应用电影感技法 ==========
function applyCinematicTechniques(comp, cn) {
    for (var si = 0; si < SEGMENTS.length; si++) {
        var seg = SEGMENTS[si];
        if (seg.technique === "Molob_SlowPush") {
            applyMolobSlowPush(comp, cn, seg);
        } else if (seg.technique === "Floby_Rotation") {
            applyFlobyRotation(comp, cn, seg);
        } else if (seg.technique === "Xenoz_FastPush") {
            applyXenozFastPush(comp, cn, seg);
        } else if (seg.technique === "Molob_SlowPull") {
            applyMolobSlowPull(comp, cn, seg);
        } else if (seg.technique === "DxshNova_Standard") {
            applyDxshNovaStandard(comp, cn, seg);
        }
    }
    applyEasing(cn.property("Scale"));
    applyEasing(cn.property("Position"));
    applyEasing(cn.property("Rotation"));
}

// ----- Molob 电影感慢推 (Intro) -----
// 参数: 15-25帧慢推, Scale 100→108%, Position Z -100→0
function applyMolobSlowPush(comp, cn, seg) {
    var s = seg.start, e = seg.end;
    // 缓慢推进
    setKF(cn, "Scale", s, [100, 100, 100]);
    setKF(cn, "Scale", s + 2, [104, 104, 100]);
    setKF(cn, "Scale", e, [108, 108, 100]);
    // 轻微上移 (Position Y)
    setKF(cn, "Position", s, [WIDTH/2, HEIGHT/2, 0]);
    setKF(cn, "Position", e, [WIDTH/2, HEIGHT/2 - 40, 0]);
    // 极轻微旋转 (叙事稳重)
    setKF(cn, "Rotation", s, 0);
    setKF(cn, "Rotation", e, 1.5);
}

// ----- Molob 电影感慢拉 (Break) -----
// 参数: 慢拉远, Scale 108→95%, 制造空间感
function applyMolobSlowPull(comp, cn, seg) {
    var s = seg.start, e = seg.end;
    setKF(cn, "Scale", s, [105, 105, 100]);
    setKF(cn, "Scale", s + 2, [100, 100, 100]);
    setKF(cn, "Scale", e, [93, 93, 100]);
    setKF(cn, "Position", s, [WIDTH/2, HEIGHT/2, 0]);
    setKF(cn, "Position", e, [WIDTH/2, HEIGHT/2 + 30, 0]);
    setKF(cn, "Rotation", s, 0);
    setKF(cn, "Rotation", e, -1);
}

// ----- Floby 旋转拉镜 (Build) -----
// 参数: Rotation Z ±8°, Scale X/Y 不等比 (X 120% Y 85% / X 80% Y 120%)
function applyFlobyRotation(comp, cn, seg) {
    var beats = getSubBeatsInRange(seg.start, seg.end, 2);
    for (var i = 0; i < beats.length; i++) {
        var t = beats[i] - VISUAL_ADVANCE;  // 视觉提前补偿
        // 不等比缩放 (横向挤压/纵向拉伸交替)
        var sx = (i % 2 === 0) ? 120 : 80;
        var sy = (i % 2 === 0) ? 85 : 120;
        setKF(cn, "Scale", t, [sx, sy, 100]);
        setKF(cn, "Scale", t + 0.05, [108, 108, 100]);
        setKF(cn, "Scale", t + 0.2, [100, 100, 100]);
        // 旋转
        var rot = (i % 2 === 0) ? 8 : -8;
        setKF(cn, "Rotation", t, rot);
        setKF(cn, "Rotation", t + 0.2, 0);
        // 位置偏移
        setKF(cn, "Position", t + 0.05,
            [WIDTH/2 + Math.sin(i * 1.5) * 60,
             HEIGHT/2 + Math.cos(i * 1.3) * 40, 0]);
    }
}

// ----- Xenoz 鱼眼推拉 (Drop - 战斗高潮) -----
// 参数: 3-8帧极速切换, Scale 100→125, Rotation ±4°, 鱼眼形变
function applyXenozFastPush(comp, cn, seg) {
    var beats = getSubBeatsInRange(seg.start, seg.end, 4);
    for (var i = 0; i < beats.length; i++) {
        var t = beats[i] - VISUAL_ADVANCE;
        // 极速推拉 (3-8帧切换)
        setKF(cn, "Scale", t, [115, 115, 100]);
        setKF(cn, "Scale", t + 0.02, [88, 88, 100]);   // 3帧回弹
        setKF(cn, "Scale", t + 0.05, [125, 125, 100]); // 5帧推到125%
        setKF(cn, "Scale", t + 0.15, [108, 108, 100]); // 回到稳定
        // 鱼眼旋转
        var rot = Math.sin(i * 6) * 4;
        setKF(cn, "Rotation", t + 0.05, rot);
        // 高速位移
        setKF(cn, "Position", t + 0.05,
            [WIDTH/2 + Math.sin(i * 4) * 100,
             HEIGHT/2 + Math.cos(i * 3) * 80, 0]);
    }
    // 应用 Optics Compensation 鱼眼形变 (Xenoz 标志)
    try {
        var oc = cn.property("Effects").addProperty("CC Lens");
        oc.property("Scale").setValueAtTime(seg.start, 1.0);
        oc.property("Scale").setValueAtTime(seg.start + 0.5, 1.3);
        oc.property("Scale").setValueAtTime(seg.end - 0.5, 1.3);
        oc.property("Scale").setValueAtTime(seg.end, 1.0);
    } catch(e) {}
}

// ----- DxshNova 标准骨架 (Outro) -----
// 参数: 空对象控制一切, 标准Scale+Position+Rotation
function applyDxshNovaStandard(comp, cn, seg) {
    var s = seg.start, e = seg.end;
    setKF(cn, "Scale", s, [95, 95, 100]);
    setKF(cn, "Scale", s + 2, [105, 105, 100]);
    setKF(cn, "Scale", e, [100, 100, 100]);
    setKF(cn, "Position", s, [WIDTH/2, HEIGHT/2 + 30, 0]);
    setKF(cn, "Position", e, [WIDTH/2, HEIGHT/2, 0]);
    setKF(cn, "Rotation", s, 0);
    setKF(cn, "Rotation", e, 0);
    // 最后2秒高潮推拉
    var lastBeat = e - BEAT_INTERVAL;
    setKF(cn, "Scale", lastBeat, [110, 110, 100]);
    setKF(cn, "Scale", lastBeat + 0.05, [125, 125, 100]);
    setKF(cn, "Scale", e, [100, 100, 100]);
}

// ========== 节拍精密对齐关键帧 (三层模型) ==========
// 物理层: ±5ms对齐 / 感知层: 视觉提前20ms / 艺术层: 风格化
function applyBeatSyncKeyframes(comp, cn) {
    // 为每个段落的主层添加节拍弹跳 (Scale bounce)
    for (var si = 0; si < SEGMENTS.length; si++) {
        var seg = SEGMENTS[si];
        var beats = getBeatsInRange(seg.start, seg.end);
        for (var bi = 0; bi < beats.length; bi++) {
            var beatTime = beats[bi] - VISUAL_ADVANCE;
            var energy = getEnergyAt(beatTime);
            // V13.5补偿: 能量重映射 (0.21-0.31 → 100-115%)
            var eNorm = (energy - 0.21) / 0.10;
            eNorm = Math.max(0, Math.min(1, eNorm));
            var isPeak = false;
            for (var pi = 0; pi < PEAK_TIMES.length; pi++) {
                if (Math.abs(beatTime - PEAK_TIMES[pi]) < 0.15) {
                    isPeak = true;
                    break;
                }
            }
            var maxBounce = isPeak ? 125 : 115;
            var k = 8;
            var scaleBounce = 100 + (maxBounce - 100) * Math.log(1 + k * eNorm) / Math.log(1 + k);
            // 对所有该段落的图层添加节拍弹跳
            for (var ci = 0; ci < seg.clips.length; ci++) {
                var layerName = seg.name + "_C" + (ci+1) + "_" + seg.clips[ci].src;
                var ly = comp.layer(layerName);
                if (!ly) continue;
                var compStart = seg.start + ci * (seg.end - seg.start) / seg.clips.length;
                var compEnd = compStart + (seg.end - seg.start) / seg.clips.length;
                if (beatTime >= compStart && beatTime < compEnd) {
                    try {
                        ly.scale.setValueAtTime(beatTime, [56.25 * scaleBounce / 100, 56.25 * scaleBounce / 100]);
                        ly.scale.setValueAtTime(beatTime + 0.05, [56.25, 56.25]);
                    } catch(e) {}
                }
            }
        }
    }
}

// ========== 三层调色体系 ============
// Layer 1: 母带LUT (Kodak 2383 D55) - 全局统一色调
// Layer 2: 青橙调色 (Teal & Orange) - 阴影蓝/高光橙
// Layer 3: 段落级色调 - 每段独立调整层
function applyThreeLayerGrading(comp) {
    // V13.5补偿: LUT 文件存在性检查
    var lutPath = LUT_CREATIVE + "Kodak_2383_D55.cube";
    var lutFile = new File(lutPath);
    var lutExists = lutFile.exists;

    // ===== Layer 1: 母带 LUT =====
    try {
        var master = comp.layers.addSolid([1,1,1], "GRADE_Master_LUT", WIDTH, HEIGHT, 1);
        master.adjustmentLayer = true;
        master.startTime = 0;
        master.inPoint = 0;
        master.outPoint = DURATION;
        var lumetri = master.property("Effects").addProperty("ADBE Lumetri Color");
        // V13.5补偿: LUT 存在则应用, 否则用 Lumetri Look 预设回退
        if (lutExists) {
            try {
                lumetri.property("LUT File").setValue(lutPath);
            } catch(e) {}
        } else {
            // 回退方案: 用 Lumetri Color 内置参数模拟胶片感
            try {
                lumetri.property("Contrast").setValue(25);
                lumetri.property("Saturation").setValue(-15);
                // 阴影偏冷蓝
                lumetri.property("Shadows").setValue([-0.1, 0, 0.15, 0]);
                // 高光偏暖橙
                lumetri.property("Highlights").setValue([0.15, 0.05, -0.1, 0]);
            } catch(e) {}
        }
        // 基础校正
        try {
            lumetri.property("WB Temperature").setValue(-5);
            lumetri.property("Contrast").setValue(15);
            lumetri.property("Saturation").setValue(-10);
        } catch(e) {}
    } catch(e) {}

    // ===== Layer 2: 青橙调色 (Teal & Orange) =====
    try {
        var tealOrange = comp.layers.addSolid([1,1,1], "GRADE_TealOrange", WIDTH, HEIGHT, 1);
        tealOrange.adjustmentLayer = true;
        tealOrange.startTime = 0;
        tealOrange.inPoint = 0;
        tealOrange.outPoint = DURATION;
        var colorBalance = tealOrange.property("Effects").addProperty("ADBE Color Balance");
        // 阴影偏青蓝
        colorBalance.property("Shadows Red").setValue(-15);
        colorBalance.property("Shadows Green").setValue(5);
        colorBalance.property("Shadows Blue").setValue(20);
        // 高光偏暖橙
        colorBalance.property("Highlights Red").setValue(20);
        colorBalance.property("Highlights Green").setValue(5);
        colorBalance.property("Highlights Blue").setValue(-15);
        tealOrange.opacity.setValue(70);
    } catch(e) {}

    // ===== Layer 3: 段落级色调 =====
    for (var si = 0; si < SEGMENTS.length; si++) {
        var seg = SEGMENTS[si];
        try {
            var segAdj = comp.layers.addSolid([1,1,1], "GRADE_" + seg.name, WIDTH, HEIGHT, 1);
            segAdj.adjustmentLayer = true;
            segAdj.startTime = seg.start;
            segAdj.inPoint = seg.start;
            segAdj.outPoint = seg.end;
            // Hue/Saturation 调色
            var hueSat = segAdj.property("Effects").addProperty("ADBE HUE SATURATION");
            hueSat.property("Colorize").setValue(1);
            hueSat.property("Colorize Hue").setValue(seg.colorTint.hue / 360);
            hueSat.property("Colorize Saturation").setValue(seg.colorTint.sat);
            hueSat.property("Colorize Lightness").setValue(0);
            // V13.5补偿: 段落色调分级透明度
            var segOpacity = 25;
            if (seg.name === "Drop") segOpacity = 45;
            else if (seg.name === "Build") segOpacity = 35;
            else if (seg.name === "Outro") segOpacity = 35;
            else if (seg.name === "Break") segOpacity = 30;
            segAdj.opacity.setValue(segOpacity);
        } catch(e) {}
    }
}

// ========== 转场系统 (节拍对齐) ==========
function addCinematicTransitions(comp) {
    // Intro→Build: 光泄漏过渡 (4.0s)
    addLightLeak(comp, 3.8, 4.2, [0.9, 0.6, 0.3]);

    // V13.5补偿: Build段 能量驱动微闪
    var buildBeats = getBeatsInRange(4, 9);
    for (var i = 0; i < buildBeats.length; i++) {
        var bEnergy = getEnergyAt(buildBeats[i]);
        var bIntensity = Math.round(30 + 40 * bEnergy);
        addMicroFlash(comp, buildBeats[i] - 0.03, buildBeats[i] + 0.03, bIntensity);
    }

    // V13.5补偿: Build段每两拍一个 Whip Pan 甩镜
    for (var wi = 0; wi < buildBeats.length; wi += 2) {
        var panDir = (wi % 4 === 0) ? 90 : 270;
        addWhipPan(comp, buildBeats[wi] - 0.02, buildBeats[wi] + 0.08, panDir);
    }

    // Build→Drop: 闪白+径向模糊+RGB故障 (9.0s 重击转场)
    addFlash(comp, 8.85, 9.15, 100);
    addRadialBlur(comp, 8.85, 9.15);
    addRGBGlitch(comp, 8.8, 9.2);

    // V13.5补偿: Drop段 RGBGlitch 减频 (每两拍一个) + 能量驱动微闪
    var dropBeats = getBeatsInRange(9, 15);
    for (var i = 0; i < dropBeats.length; i++) {
        if (i % 2 === 0) {
            addRGBGlitch(comp, dropBeats[i] - 0.01, dropBeats[i] + 0.09);
        }
        // 能量驱动微闪强度: intensity = 30 + 40 × energy
        var flashEnergy = getEnergyAt(dropBeats[i] + 0.267);
        var flashIntensity = Math.round(30 + 40 * flashEnergy);
        addMicroFlash(comp, dropBeats[i] + 0.267, dropBeats[i] + 0.297, flashIntensity);
    }

    // Drop→Break: 交叉溶解 (15.0s 情感过渡)
    addDissolve(comp, 14.8, 15.2);

    // Break→Outro: 光泄漏 (19.0s)
    addLightLeak(comp, 18.8, 19.4, [0.4, 0.6, 0.9]);

    // Outro→结尾: 闪白收尾 (23.0s)
    addFlash(comp, 22.8, 23.15, 60);
}

// ========== 音频驱动效果 ==========
function addAudioDrivenEffectsV13(comp) {
    var ctrl = comp.layers.addSolid([1,1,1], "Audio Controller", 100, 100, 1);
    ctrl.name = "Audio Controller";
    ctrl.adjustmentLayer = true;
    var ns = ["Global_Energy", "LowFreq", "MidFreq", "HighFreq"];
    for (var i = 0; i < ns.length; i++) {
        var ef = ctrl.property("Effects").addProperty("Slider Control");
        ef.name = ns[i];
        ef.property("Slider").setValueAtTime(0, 50);
    }
}

// ========== 文字系统 ==========
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
}

function addTitleText(comp, txt, startT, endT, yPos, fontSize, preset) {
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
}

function getFont(preset) {
    var fonts = {
        cinematic: "Bebas Neue Bold",
        epic: "Alfa Slab One",
        modern: "Montserrat Bold",
        japanese: "Microsoft YaHei",
        brush: "Ma Shan Zheng"
    };
    return fonts[preset] || "Impact";
}

// ========== 战斗粒子 (Drop段) ==========
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
}

// ========== 氛围光效 ==========
function addAtmosphereV13(comp) {
    // 全局光晕 (Optical Flares 风格)
    try {
        var flare = comp.layers.addSolid([1, 0.9, 0.7], "Atmosphere_Flare", WIDTH, HEIGHT, 1);
        flare.adjustmentLayer = true;
        flare.startTime = 0;
        flare.inPoint = 0;
        flare.outPoint = DURATION;
        var glow = flare.property("Effects").addProperty("ADBE Glow");
        glow.property("Glow Threshold").setValue(0.6);
        glow.property("Glow Radius").setValue(40);
        glow.property("Glow Intensity").setValue(0.3);
        flare.opacity.setValueAtTime(0, 20);
        flare.opacity.setValueAtTime(9, 50);  // Drop段增强
        flare.opacity.setValueAtTime(15, 30);
        flare.opacity.setValueAtTime(23.15, 20);
    } catch(e) {}

    // 暗角 (Vignette) - 使用 CC Vignette 插件
    try {
        var vig = comp.layers.addSolid([0, 0, 0], "Atmosphere_Vignette", WIDTH, HEIGHT, 1);
        vig.adjustmentLayer = true;
        vig.startTime = 0;
        vig.inPoint = 0;
        vig.outPoint = DURATION;
        try {
            var vc = vig.property("Effects").addProperty("CC Vignette");
            vc.property("Amount").setValue(50);
            vc.property("Feather").setValue(100);
        } catch(e) {
            // 后备方案: 使用圆形遮罩
            var mask = vig.property("Masks").addProperty("Mask");
            var maskShape = mask.property("Mask Shape");
            var shape = new Shape();
            shape.vertices = [
                [0, 0], [WIDTH, 0], [WIDTH, HEIGHT], [0, HEIGHT]
            ];
            shape.inTangents = [[0,0],[0,0],[0,0],[0,0]];
            shape.outTangents = [[0,0],[0,0],[0,0],[0,0]];
            shape.closed = true;
            maskShape.setValue(shape);
            mask.property("Mask Expansion").setValue(-200);
            mask.property("Mask Feather").setValue(300);
            mask.invert = true;
        }
        vig.opacity.setValue(60);
    } catch(e) {}

    // 胶片颗粒 (Film Grain)
    try {
        var grain = comp.layers.addSolid([0.5, 0.5, 0.5], "Atmosphere_Grain", WIDTH, HEIGHT, 1);
        grain.adjustmentLayer = true;
        grain.startTime = 0;
        grain.inPoint = 0;
        grain.outPoint = DURATION;
        var ng = grain.property("Effects").addProperty("ADBE Noise");
        ng.property("Amount of Noise").setValue(8);
        grain.opacity.setValue(15);
        grain.blendingMode = BlendingMode.OVERLAY;
    } catch(e) {}
}

// ========== 图层顺序 ==========
function adjustLayerOrderV13(comp) {
    // 调整层移到顶部
    var adjustNames = ["GRADE_Master_LUT", "GRADE_TealOrange", "Audio Controller",
                       "Atmosphere_Flare", "Atmosphere_Vignette", "Atmosphere_Grain"];
    for (var i = 0; i < adjustNames.length; i++) {
        try {
            var ly = comp.layer(adjustNames[i]);
            if (ly) ly.moveToEnd();
        } catch(e) {}
    }
    // 段落调色层在主调色之下
    for (var si = 0; si < SEGMENTS.length; si++) {
        try {
            var ly = comp.layer("GRADE_" + SEGMENTS[si].name);
            if (ly) ly.moveToEnd();
        } catch(e) {}
    }
}

// ========== 工具函数 ==========

function getSubBeatsInRange(startT, endT, division) {
    var beats = [];
    var fullBeats = getBeatsInRange(startT - BEAT_INTERVAL, endT + BEAT_INTERVAL);
    for (var i = 0; i < fullBeats.length - 1; i++) {
        var b0 = fullBeats[i];
        var b1 = fullBeats[i + 1];
        for (var d = 0; d < division; d++) {
            var t = b0 + (b1 - b0) * d / division;
            if (t >= startT && t < endT) {
                beats.push(t);
            }
        }
    }
    var lastT = fullBeats[fullBeats.length - 1];
    if (lastT >= startT && lastT < endT) beats.push(lastT);
    return beats;
}

var PEAK_TIMES = [9.2, 11.0, 12.8, 14.5];

// V13.5补偿: 背景层预合成 (减少主合成图层数)
function precomposeBackgrounds(comp) {
    try {
        var bgLayerNames = [];
        for (var i = 1; i <= comp.numLayers; i++) {
            var ly = comp.layer(i);
            if (ly.name.indexOf("_BG") !== -1) {
                bgLayerNames.push(ly.name);
            }
        }
        if (bgLayerNames.length === 0) return;

        var bgComp = app.project.items.addComposition(
            "Precomp_Backgrounds_V13_5", WIDTH, HEIGHT, 1, DURATION, FRAME_RATE
        );

        // 从后往前移动背景层到预合成
        for (var j = bgLayerNames.length - 1; j >= 0; j--) {
            try {
                var bgLy = comp.layer(bgLayerNames[j]);
                if (bgLy) bgLy.moveToBeginning(bgComp);
            } catch(e) {}
        }

        var bgPrecompLayer = comp.layers.add(bgComp);
        bgPrecompLayer.name = "PRECOMP_Backgrounds";
        bgPrecompLayer.startTime = 0;
        bgPrecompLayer.motionBlur = true;
        try { bgPrecompLayer.parent = comp.layer("Camera_Controller"); } catch(e) {}
        bgPrecompLayer.moveToEnd();
    } catch(e) {}
}

// V13.5补偿: 粒子层代理模式
var PARTICLE_PROXY_MODE = true;
function setupParticleProxy(comp) {
    if (!PARTICLE_PROXY_MODE) return;
    var particleNames = ["Particle_Blood", "Particle_Sparks"];
    for (var i = 0; i < particleNames.length; i++) {
        try {
            var pLayer = comp.layer(particleNames[i]);
            if (!pLayer) continue;
            var pEffect = pLayer.property("Effects").property("ADBE Particular");
            if (!pEffect) continue;
            try {
                var origVel = pEffect.property("Velocity").value;
                pEffect.property("Velocity").setValue(origVel * 0.3);
            } catch(e) {}
        } catch(e) {}
    }
}

function safeImport(path) {
    try {
        var f = new File(path);
        if (!f.exists) return null;
        var io = new ImportOptions(f);
        if (app.project.canImportFile(io)) {
            var items = app.project.importFile(io);
            return items;
        }
    } catch(e) {}
    return null;
}

function createCameraNull(comp) {
    var n = comp.layers.addNull();
    n.name = "Camera_Controller";
    n.threeDLayer = true;
    n.property("Position").setValueAtTime(0, [WIDTH/2, HEIGHT/2, 0]);
    n.property("Scale").setValueAtTime(0, [100, 100, 100]);
    n.property("Rotation").setValueAtTime(0, 0);
    return n;
}

function setKF(layer, propName, time, value) {
    try {
        layer.property(propName).setValueAtTime(time, value);
    } catch(e) {}
}

function applyEasing(prop) {
    try {
        for (var i = 1; i <= prop.numKeys; i++) {
            var ki = prop.keyInSpatialTangents(i);
            var ko = prop.keyOutSpatialTangents(i);
            try {
                prop.keyInTemporalEase(i);
                prop.keyOutTemporalEase(i);
            } catch(e) {}
        }
    } catch(e) {}
}

// V13.5补偿: 完整37节拍 (BPM=112.35, 每拍0.53405s)
var ALL_BEATS = [
    0.116, 0.697, 1.231, 1.765, 2.299, 2.833, 3.344, 3.878,
    4.389, 4.923, 5.457, 5.991, 6.525, 7.036, 7.570, 8.104,
    8.638, 9.172, 9.706, 10.217, 10.751, 11.285, 11.819,
    12.330, 12.864, 13.398, 13.932, 14.443, 14.977, 15.511,
    16.045, 16.579, 17.113, 17.647, 18.181, 18.715, 19.249
];

function getBeatsInRange(startT, endT) {
    var beats = [];
    for (var i = 0; i < ALL_BEATS.length; i++) {
        if (ALL_BEATS[i] >= startT && ALL_BEATS[i] < endT) {
            beats.push(ALL_BEATS[i]);
        }
    }
    return beats;
}

// V13.5补偿: 能量曲线线性插值 (替代整秒阶梯)
function getEnergyAt(t) {
    var energyCurve = [
        0.2944, 0.3004, 0.2072, 0.2375, 0.2941, 0.3097, 0.3007, 0.3047,
        0.2995, 0.3103, 0.301, 0.3098, 0.2913, 0.2964, 0.2973, 0.2895,
        0.293, 0.3037, 0.3054, 0.2954, 0.3062, 0.2185, 0.1566, 0.0856
    ];
    if (t < 0) return energyCurve[0];
    if (t >= energyCurve.length - 1) return energyCurve[energyCurve.length - 1];
    var idx = Math.floor(t);
    var frac = t - idx;
    return energyCurve[idx] + (energyCurve[idx + 1] - energyCurve[idx]) * frac;
}

// ========== 转场效果工具 ==========
function addLightLeak(comp, st, et, color) {
    try {
        var ll = comp.layers.addSolid(color, "LightLeak_" + st, WIDTH, HEIGHT, 1);
        ll.startTime = st; ll.inPoint = st; ll.outPoint = et;
        ll.opacity.setValueAtTime(st, 0);
        ll.opacity.setValueAtTime((st + et) / 2, 60);
        ll.opacity.setValueAtTime(et, 0);
        ll.blendingMode = BlendingMode.SCREEN;
        var b = ll.property("Effects").addProperty("ADBE Fast Blur");
        b.property("Blurriness").setValue(60);
        b.property("Repeat Edge Pixels").setValue(true);
    } catch(e) {}
}

function addFlash(comp, st, et, intensity) {
    try {
        var f = comp.layers.addSolid([1, 1, 1], "Flash_" + st, WIDTH, HEIGHT, 1);
        f.startTime = st; f.inPoint = st; f.outPoint = et;
        f.opacity.setValueAtTime(st, 0);
        f.opacity.setValueAtTime(st + 0.02, intensity);
        f.opacity.setValueAtTime(et, 0);
        f.blendingMode = BlendingMode.SCREEN;
    } catch(e) {}
}

function addMicroFlash(comp, st, et, intensity) {
    try {
        var f = comp.layers.addSolid([1, 1, 1], "MicroFlash_" + st, WIDTH, HEIGHT, 1);
        f.startTime = st; f.inPoint = st; f.outPoint = et;
        f.opacity.setValueAtTime(st, 0);
        f.opacity.setValueAtTime(st + 0.01, intensity);
        f.opacity.setValueAtTime(et, 0);
        f.blendingMode = BlendingMode.SCREEN;
    } catch(e) {}
}

function addRadialBlur(comp, st, et) {
    try {
        var rb = comp.layers.addSolid([1, 1, 1], "RadialBlur_" + st, WIDTH, HEIGHT, 1);
        rb.adjustmentLayer = true;
        rb.startTime = st; rb.inPoint = st; rb.outPoint = et;
        var b = rb.property("Effects").addProperty("ADBE Radial Blur");
        b.property("Amount").setValueAtTime(st, 0);
        b.property("Amount").setValueAtTime((st + et) / 2, 50);
        b.property("Amount").setValueAtTime(et, 0);
    } catch(e) {}
}

function addRGBGlitch(comp, st, et) {
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
}

function addDissolve(comp, st, et) {
    try {
        var d = comp.layers.addSolid([1, 1, 1], "Diss_" + st, WIDTH, HEIGHT, 1);
        d.startTime = st; d.inPoint = st; d.outPoint = et;
        d.opacity.setValueAtTime(st, 0);
        d.opacity.setValueAtTime((st + et) / 2, 60);
        d.opacity.setValueAtTime(et, 0);
        d.blendingMode = BlendingMode.SCREEN;
        var b = d.property("Effects").addProperty("ADBE Fast Blur");
        b.property("Blurriness").expression =
            "t=linear(time," + st + "," + et + ",0,1);Math.sin(t*Math.PI)*40;";
        b.property("Repeat Edge Pixels").setValue(true);
    } catch(e) {}
}

// V13.5补偿: Whip Pan 甩镜转场
function addWhipPan(comp, st, et, direction) {
    try {
        var wp = comp.layers.addSolid([1, 1, 1], "WhipPan_" + st, WIDTH, HEIGHT, 1);
        wp.adjustmentLayer = true;
        wp.startTime = st; wp.inPoint = st; wp.outPoint = et;
        var mb = wp.property("Effects").addProperty("ADBE Directional Blur");
        mb.property("Blur Length").setValueAtTime(st, 0);
        mb.property("Blur Length").setValueAtTime(st + 0.04, 200);
        mb.property("Blur Length").setValueAtTime(et, 0);
        mb.property("Direction").setValue(direction);
        wp.opacity.setValueAtTime(st, 0);
        wp.opacity.setValueAtTime(st + 0.02, 80);
        wp.opacity.setValueAtTime(et, 0);
    } catch(e) {}
}

// ========== 执行 ==========
main();
