// ============================================================
// 《冰海战记》V8 - 字幕动画系统彻底重构
//
// 保留V7全部修复(空白/粒子/调色/字体/结构),
// V8核心升级:基于AE Text Animators + Range Selector
// 的真正逐字动画系统,彻底替换图层级整体动画。
//
// V8四种字幕风格:
// 1. charPop     - 逐字弹出+弹性过冲(Scale+Range Offset
//                  +弹性表达式)
// 2. strokeReveal- 描边揭示(先描边后填充+逐字揭示)
// 3. glitchShake - 故障抖动(Wiggly Selector+RGB偏移
//                  +扫描线+高频抖动)
// 4. flip3D      - 3D翻转(threeDLayer+Rotation Y+Scale
//                  配合深度)
// ============================================================

var COMP_NAME = "VinlandSaga_Battle_V8";
var CLIP_PATH = "D:/AE-Work/视频素材库/冰海战记片段/";
var AUDIO_PATH = "D:/AE-Work/音频素材库/BGM/";
var DURATION = 23.15;
var WIDTH = 1080;
var HEIGHT = 1920;
var FRAME_RATE = 30;
var BPM = 112.3;

// 12个精选素材片段
var CLIPS = [
    "clip_1_1.mp4", "clip_1_3.mp4",
    "clip_9_2.mp4", "clip_9_3.mp4", "clip_11_2.mp4",
    "clip_10_2.mp4", "clip_10_3.mp4",
    "clip_3_2.mp4", "clip_12_2.mp4",
    "clip_2_1.mp4", "clip_8_1.mp4",
    "clip_5_3.mp4"
];

function main() {
    try {
        var comp = createComposition(
            COMP_NAME, WIDTH, HEIGHT,
            DURATION, FRAME_RATE
        );
        if (!comp) {
            return JSON.stringify({error: "comp fail"});
        }
        comp.motionBlur = true;

        // 音频
        var af = safeImport(AUDIO_PATH + "ae实战音乐.mp3");
        if (af) {
            var al = comp.layers.add(af);
            al.name = "Soundtrack";
            al.startTime = 0;
        }

        // 12个分段素材层
        var segs = createSegmentLayers(comp);

        // 摄像机+空对象
        var cam = comp.layers.addCamera(
            "Main_Camera", [WIDTH/2, HEIGHT/2]
        );
        cam.property("Position").setValueAtTime(
            0, [WIDTH/2, HEIGHT/2, -800]
        );
        cam.property("Zoom").setValueAtTime(0, 800);
        var cNull = createCameraNull(comp);
        try { cam.parent = cNull; } catch(e) {}

        // [FIX] Audio Controller - 必须设adjustmentLayer
        createAudioControllerFixed(comp);

        // 段落拉镜
        addSegmentPullZoom(comp, cNull);

        // 转场
        addTransitionsV7(comp);

        // 音频驱动效果
        addAudioDrivenEffectsV7(comp);

        // [NEW] 高级文字系统
        addAdvancedTextSystemV7(comp);

        // [NEW] 段落化多样调色
        addPerSegmentGrading(comp);

        // [REPLACED] 氛围光效（无粒子）
        addAtmosphereV7(comp);

        // 全局效果
        addGlobalEffectsV7(comp);

        // 图层顺序
        adjustLayerOrderV7(comp);

        return JSON.stringify({
            status: "success",
            compName: COMP_NAME,
            layers: comp.numLayers,
            clips: CLIPS.length,
            version: "V7"
        });
    } catch (e) {
        return JSON.stringify({
            error: e.toString(), line: e.line
        });
    }
}

// ========== 创建分段素材层 ==========
function createSegmentLayers(comp) {
    var segs = [
        {clips:[0,1], s:0, e:4, n:"Intro"},
        {clips:[2,3,4], s:4, e:9, n:"Build"},
        {clips:[5,6,7,8], s:9, e:15, n:"Drop"},
        {clips:[9,10], s:15, e:19, n:"Break"},
        {clips:[11], s:19, e:23, n:"Outro"}
    ];
    var all = [];
    for (var si = 0; si < segs.length; si++) {
        var seg = segs[si];
        var sd = (seg.e - seg.s) / seg.clips.length;
        for (var ci = 0; ci < seg.clips.length; ci++) {
            var cf = CLIPS[seg.clips[ci]];
            var cp = CLIP_PATH + cf;
            var ft = safeImport(cp);
            var ln = seg.n + "_C" + (ci+1) + "_" +
                     cf.replace(".mp4","");
            var ly = createLayerWithFallBack(
                comp, ft, ln,
                getSegColor(seg.n, ci)
            );
            var cs = seg.s + ci * sd;
            ly.startTime = cs;
            ly.inPoint = cs;
            ly.outPoint = cs + sd;
            // [V8修复] 上下模糊背景填充方案
            // 主层完整显示+背景模糊铺满,主体不再被裁
            applyHorizontalToVerticalV8(
                comp, ly, ft, cs, sd
            );
            try { ly.motionBlur = true; } catch(e) {}
            try {
                ly.parent = comp.layer("Camera_Controller");
            } catch(e) {}
            all.push({
                layer: ly, seg: seg.n,
                start: cs, dur: sd
            });
        }
    }
    return all;
}

// [V8修复] 横转竖专业方案:
// 主层 Scale 56.25%(1080/1920)宽度填满,完整显示
// 背景层 Scale 220% 完全覆盖+高斯模糊+降亮度
// 上下黑边被模糊背景填充,主体完整可见
function applyHorizontalToVerticalV8(comp, layer, ft, cs, sd) {
    // 主层: 宽度填满合成,完整显示横屏画面
    var sp = 56.25;
    layer.scale.setValueAtTime(0, [sp, sp]);
    layer.position.setValueAtTime(
        0, [WIDTH/2, HEIGHT/2]
    );

    // 背景层: 同一素材放大完全铺满 + 模糊
    if (!ft) return;
    try {
        var bg = comp.layers.add(ft);
        bg.name = layer.name + "_BG";
        bg.startTime = cs;
        bg.inPoint = cs;
        bg.outPoint = cs + sd;
        // [V8修复] Scale 220%确保完全覆盖1080x1920合成(消除左右黑边)
        bg.scale.setValueAtTime(0, [220, 220]);
        // 随机Y偏移避免背景静态
        var yo = (Math.random() - 0.5) * 200;
        bg.position.setValueAtTime(
            0, [WIDTH/2, HEIGHT/2 + yo]
        );

        // 高斯模糊
        var blur = bg.property("Effects")
            .addProperty("ADBE Fast Blur");
        blur.property("Blurriness").setValue(80);
        blur.property("Repeat Edge Pixels")
            .setValue(true);

        // 降低亮度避免抢主体
        var br = bg.property("Effects")
            .addProperty("Brightness & Contrast");
        br.property("Brightness").setValue(-35);
        br.property("Contrast").setValue(15);

        // 背景移到主层下方
        bg.moveAfter(layer);

        try { bg.motionBlur = true; } catch(e) {}
        try {
            bg.parent = comp.layer("Camera_Controller");
        } catch(e) {}
    } catch(e) {}

    // [V8修复] 添加左上角水印遮挡层(遮挡bilibili水印)
    try {
        var mask = comp.layers.addSolid(
            [0, 0, 0], "Watermark_Mask_" + cs,
            350, 80, 1
        );
        mask.startTime = cs;
        mask.inPoint = cs;
        mask.outPoint = cs + sd;
        mask.position.setValueAtTime(0, [175, 40]);
        mask.opacity.setValueAtTime(0, 85);
        mask.moveBefore(layer);
        try {
            mask.parent = comp.layer("Camera_Controller");
        } catch(e) {}
    } catch(e) {}
}

function getSegColor(seg, idx) {
    var c = {
        "Intro": [[0.08,0.12,0.2],[0.1,0.15,0.25]],
        "Build": [[0.15,0.1,0.05],[0.2,0.15,0.08],
                  [0.12,0.08,0.15]],
        "Drop": [[0.25,0.1,0.05],[0.2,0.05,0.1],
                 [0.15,0.15,0.05],[0.1,0.2,0.1]],
        "Break": [[0.05,0.08,0.12],[0.08,0.05,0.1]],
        "Outro": [[0.1,0.08,0.15]]
    };
    var sc = c[seg] || [[0.5,0.5,0.5]];
    return sc[idx % sc.length];
}

// ========== [FIX] Audio Controller ==========
function createAudioControllerFixed(comp) {
    var ctrl = comp.layers.addSolid(
        [1,1,1], "Audio Controller", 100, 100, 1
    );
    ctrl.name = "Audio Controller";
    ctrl.startTime = 0;
    // [CRITICAL FIX] 必须设为调整层
    // 否则100x100白色固态层会渲染到画面
    ctrl.adjustmentLayer = true;
    var ns = ["Global Energy","LowFreq Energy",
              "MidFreq Energy","HighFreq Energy"];
    for (var i = 0; i < ns.length; i++) {
        var ef = ctrl.property("Effects").addProperty(
            "Slider Control"
        );
        ef.name = ns[i];
        ef.property("Slider").setValueAtTime(0, 50);
    }
}

// ========== 段落拉镜 ==========
function addSegmentPullZoom(comp, cn) {
    // Intro - 慢推
    setKF(cn,"Scale",0,[100,100,100]);
    setKF(cn,"Scale",2,[105,105,100]);
    setKF(cn,"Scale",4,[108,108,100]);
    setKF(cn,"Position",0,[WIDTH/2,HEIGHT/2,0]);
    setKF(cn,"Position",4,[WIDTH/2,HEIGHT/2-40,0]);
    setKF(cn,"Rotation",0,0);
    setKF(cn,"Rotation",4,2);

    // Build - 对角滑镜
    var bb = [4,4.53,5.07,5.6,6.13,6.67,7.2,7.73,8.27,8.8];
    for (var b = 0; b < bb.length; b++) {
        var t = bb[b];
        setKF(cn,"Scale",t,[108,108,100]);
        setKF(cn,"Scale",t+0.03,[95,95,100]);
        setKF(cn,"Scale",t+0.07,[120,120,100]);
        setKF(cn,"Scale",t+0.2,[110,110,100]);
        setKF(cn,"Position",t+0.07,
            [WIDTH/2+Math.sin(b*1.5)*80,
             HEIGHT/2+Math.cos(b*1.3)*60,0]);
        setKF(cn,"Rotation",t+0.07,
            Math.sin(b*2)*6);
    }

    // Drop - 高速推拉
    var db = [];
    for (var d = 9; d < 15; d += 0.53) db.push(d);
    for (var d2 = 0; d2 < db.length; d2++) {
        var dt = db[d2];
        setKF(cn,"Scale",dt,[115,115,100]);
        setKF(cn,"Scale",dt+0.02,[88,88,100]);
        setKF(cn,"Scale",dt+0.05,[135,135,100]);
        setKF(cn,"Scale",dt+0.15,[108,108,100]);
        setKF(cn,"Position",dt+0.05,
            [WIDTH/2+Math.sin(d2*4)*100,
             HEIGHT/2+Math.cos(d2*3)*80,0]);
        setKF(cn,"Rotation",dt+0.05,
            Math.sin(d2*6)*10);
    }

    // Break - 慢拉远
    setKF(cn,"Scale",15,[100,100,100]);
    setKF(cn,"Scale",17,[93,93,100]);
    setKF(cn,"Scale",19,[90,90,100]);
    setKF(cn,"Position",15,[WIDTH/2,HEIGHT/2,0]);
    setKF(cn,"Position",17,[WIDTH/2,HEIGHT/2+20,0]);
    setKF(cn,"Position",19,[WIDTH/2,HEIGHT/2+30,0]);
    setKF(cn,"Rotation",15,0);
    setKF(cn,"Rotation",19,-1);

    // Outro - 缓推远
    setKF(cn,"Scale",19,[90,90,100]);
    setKF(cn,"Scale",21,[86,86,100]);
    setKF(cn,"Scale",23.15,[83,83,100]);
    setKF(cn,"Position",19,[WIDTH/2,HEIGHT/2+30,0]);
    setKF(cn,"Position",23.15,
        [WIDTH/2,HEIGHT/2+50,0]);

    applyEasing(cn.property("Scale"));
    applyEasing(cn.property("Position"));
    applyEasing(cn.property("Rotation"));
}

// ========== 转场 ==========
function addTransitionsV7(comp) {
    addLightLeak(comp, 3.8, 4.2, [0.9,0.6,0.3]);
    for (var t = 4.53; t < 9; t += 0.53) {
        addMicroFlash(comp, t-0.03, t+0.03, 35);
    }
    addFlash(comp, 8.85, 9.15, 100);
    addRadialBlur(comp, 8.85, 9.15);
    addRGBGlitch(comp, 8.8, 9.2);
    for (var d = 10; d < 15; d += 1.06) {
        addRGBGlitch(comp, d, d+0.1);
        addMicroFlash(comp, d+0.53, d+0.56, 50);
    }
    addDissolve(comp, 14.8, 15.2);
    addLightLeak(comp, 18.8, 19.4, [0.4,0.6,0.9]);
    addFlash(comp, 22.8, 23.15, 60);
}

function addRGBGlitch(comp, st, et) {
    var g = comp.layers.addSolid(
        [1,0,0], "RGBG_"+st, WIDTH, HEIGHT, 1
    );
    g.startTime = st; g.inPoint = st; g.outPoint = et;
    g.opacity.setValueAtTime(st, 0);
    g.opacity.setValueAtTime(st+0.02, 40);
    g.opacity.setValueAtTime(et, 0);
    g.blendingMode = BlendingMode.SCREEN;
    var b = g.property("Effects").addProperty(
        "ADBE Fast Blur"
    );
    b.property("Blurriness").setValueAtTime(st, 0);
    b.property("Blurriness").setValueAtTime(st+0.02, 15);
    b.property("Blurriness").setValueAtTime(et, 0);
    b.property("Repeat Edge Pixels").setValueAtTime(0,true);
}

function addDissolve(comp, st, et) {
    var d = comp.layers.addSolid(
        [1,1,1], "Diss_"+st, WIDTH, HEIGHT, 1
    );
    d.startTime = st; d.inPoint = st; d.outPoint = et;
    d.opacity.setValueAtTime(st, 0);
    d.opacity.setValueAtTime((st+et)/2, 60);
    d.opacity.setValueAtTime(et, 0);
    d.blendingMode = BlendingMode.SCREEN;
    var b = d.property("Effects").addProperty(
        "ADBE Fast Blur"
    );
    b.property("Blurriness").expression =
        "t=linear(time,"+st+","+et+",0,1);" +
        "Math.sin(t*Math.PI)*40;";
    b.property("Repeat Edge Pixels").setValueAtTime(0,true);
}

// ========== [V8] 高级文字系统 - 基于Text Animators ==========
function addAdvancedTextSystemV7(comp) {
    var subs = [
        // Intro - charPop 逐字弹性
        {id:1, t:1.0, d:3.0, txt:"VINLAND SAGA",
         sz:64, font:"Impact", anim:"charPop",
         y:HEIGHT-350, fill:[1,1,1], stroke:[0,0,0],
         sw:5, glow:[0.3,0.6,1], grad:true},
        {id:2, t:2.5, d:1.5, txt:"戦士として生きる",
         sz:54, font:"MS Mincho", anim:"strokeReveal",
         y:HEIGHT-200, fill:[1,0.95,0.8], stroke:[0.2,0.1,0],
         sw:3, glow:[1,0.5,0.2]},

        // Build - glitchShake 故障抖动
        {id:3, t:4.5, d:0.8, txt:"覚醒",
         sz:100, font:"MS Mincho", anim:"glitchShake",
         y:HEIGHT/2, fill:[1,1,0.9], stroke:[0.5,0.2,0],
         sw:6, glow:[1,0.6,0.1], rgb:true},
        {id:4, t:6.0, d:0.5, txt:"戦え",
         sz:120, font:"MS Mincho", anim:"glitchShake",
         y:HEIGHT/2, fill:[1,0.9,0.7], stroke:[0.6,0.1,0],
         sw:7, glow:[1,0.4,0], rgb:true},
        {id:5, t:7.5, d:0.8, txt:"怒りを越えて",
         sz:60, font:"MS Mincho", anim:"charPop",
         y:HEIGHT-200, fill:[1,0.95,0.8], stroke:[0,0,0],
         sw:3, glow:[1,0.5,0.2]},

        // Drop - flip3D 三维翻转
        {id:6, t:9.0, d:0.3, txt:"斬",
         sz:200, font:"MS Mincho", anim:"flip3D",
         y:HEIGHT/2, fill:[1,0.8,0.5], stroke:[0.8,0.1,0],
         sw:10, glow:[1,0.3,0], rgb:true},
        {id:7, t:9.53, d:0.3, txt:"撃",
         sz:200, font:"MS Mincho", anim:"flip3D",
         y:HEIGHT/2, fill:[1,0.7,0.3], stroke:[0.9,0.05,0],
         sw:10, glow:[1,0.2,0], rgb:true},
        {id:8, t:10.5, d:0.4, txt:"加速",
         sz:140, font:"MS Mincho", anim:"glitchShake",
         y:HEIGHT/2, fill:[1,1,0.8], stroke:[0.5,0.2,0],
         sw:7, glow:[1,0.5,0.1], rgb:true},
        {id:9, t:12.0, d:0.3, txt:"突破",
         sz:160, font:"MS Mincho", anim:"flip3D",
         y:HEIGHT/2, fill:[1,0.6,0.2], stroke:[0.9,0.1,0],
         sw:9, glow:[1,0.2,0], rgb:true},
        {id:10, t:14.0, d:0.5, txt:"限界を超えろ",
         sz:62, font:"MS Mincho", anim:"charPop",
         y:HEIGHT-200, fill:[1,0.95,0.8], stroke:[0,0,0],
         sw:3, glow:[1,0.4,0.1]},

        // Break - strokeReveal 描边揭示
        {id:11, t:15.5, d:1.5, txt:"真の戦士は…",
         sz:54, font:"MS Mincho", anim:"strokeReveal",
         y:HEIGHT-200, fill:[0.8,0.85,1], stroke:[0,0,0.2],
         sw:3, glow:[0.3,0.4,1]},
        {id:12, t:17.5, d:1.5, txt:"剣を必要としない",
         sz:54, font:"MS Mincho", anim:"strokeReveal",
         y:HEIGHT-200, fill:[0.8,0.85,1], stroke:[0,0,0.2],
         sw:3, glow:[0.3,0.4,1]},

        // Outro - flip3D + charPop
        {id:13, t:20.0, d:1.5, txt:"あなたの敵はいない",
         sz:48, font:"MS Mincho", anim:"charPop",
         y:HEIGHT-250, fill:[1,0.95,0.8], stroke:[0.2,0.1,0],
         sw:3, glow:[1,0.5,0.2]},
        {id:14, t:21.5, d:1.65, txt:"VINLAND SAGA",
         sz:110, font:"Impact", anim:"flip3D",
         y:HEIGHT/2, fill:[1,1,1], stroke:[0,0,0],
         sw:6, glow:[0.3,0.6,1], grad:true}
    ];

    for (var i = 0; i < subs.length; i++) {
        var s = subs[i];

        // 发光层（在主文字下方）
        if (s.glow) createTextGlow(comp, s);

        // RGB分离层（冲击文字）
        if (s.rgb) createRGBSplit(comp, s);

        // 主文字层
        var ml = createStyledText(comp, s);
        applyTextAnimV8(ml, s);
        applyDropShadow(ml, s);

        // 渐变叠加
        if (s.grad) createGradOverlay(comp, ml, s);
    }
}

function createStyledText(comp, s) {
    var tl = comp.layers.addText(s.txt);
    tl.name = "TXT_" + s.id;
    tl.startTime = s.t;
    tl.inPoint = s.t;
    tl.outPoint = s.t + s.d;
    tl.position.setValueAtTime(s.t, [WIDTH/2, s.y]);

    // 设置字体样式 - 粗犷立体风格
    try {
        var tp = tl.property("Source Text");
        var td = tp.value;
        td.fontSize = s.sz;
        // [V8字体升级] 白色填充 + 黑色粗描边
        td.fillColor = [1, 1, 1];
        td.applyFill = true;
        td.strokeColor = [0, 0, 0];
        td.strokeWidth = s.sw || 6;
        td.applyStroke = true;
        td.strokeOverFill = true;
        // 使用粗犷字体
        td.font = s.font || "Impact";
        td.fauxBold = true;
        td.tracking = 80;
        tp.setValue(td);
    } catch(e) {}

    // [V8字体升级] 添加底部投影效果
    try {
        var ds = tl.property("Effects")
            .addProperty("Drop Shadow");
        ds.property("Shadow Color").setValue([0, 0, 0]);
        ds.property("Opacity").setValue(90);
        ds.property("Direction").setValue(180);
        ds.property("Distance").setValue(s.sz * 0.08);
        ds.property("Softness").setValue(s.sz * 0.1);
        ds.property("Shadow Only").setValue(false);
    } catch(e) {}

    // 通用淡入淡出
    tl.opacity.setValueAtTime(s.t, 0);
    tl.opacity.setValueAtTime(s.t + 0.08, 100);
    if (s.d > 0.5) {
        tl.opacity.setValueAtTime(s.t + s.d - 0.2, 100);
    }
    tl.opacity.setValueAtTime(s.t + s.d, 0);

    return tl;
}

// ========== [V8] Text Animator 工具函数 ==========
// 添加 Text Animator
function addTextAnimator(layer, name) {
    try {
        var anim = layer.property("ADBE Text Properties")
            .property("ADBE Text Animators")
            .addProperty("ADBE Text Animator");
        if (name) anim.name = name;
        return anim;
    } catch(e) { return null; }
}

// 获取第一个 Range Selector(默认创建)
function getRangeSelector(animator) {
    try {
        var sels = animator.property("ADBE Text Selectors");
        if (sels.numProperties < 1) {
            sels.addProperty("ADBE Text Range Selector");
        }
        return sels.property(1);
    } catch(e) { return null; }
}

// 添加 Wiggly Selector(随机选择器)
function addWigglySelector(animator) {
    try {
        return animator.property("ADBE Text Selectors")
            .addProperty("ADBE Text Wiggly Selector");
    } catch(e) { return null; }
}

// 添加属性到 Animator(Scale/Opacity/Rotation/Position等)
function addAnimProp(animator, propName) {
    try {
        return animator.addProperty(propName);
    } catch(e) { return null; }
}

// [V8风格1] charPop 逐字弹出+弹性
// Scale 从 0→130→100 + Range Offset 驱动逐字
// 弹性表达式: amp*sin(freq*t)*exp(-decay*t)
function applyCharPop(layer, s) {
    var anim = addTextAnimator(layer, "CharPop");
    if (!anim) return;
    var sel = getRangeSelector(anim);
    if (!sel) return;

    // Scale 属性
    var sc = addAnimProp(anim, "ADBE Text Scale");
    if (sc) sc.setValue([0, 0]);

    // Opacity 属性
    var op = addAnimProp(anim, "ADBE Text Opacity");
    if (op) op.setValue(0);

    // Rotation 轻微
    var rot = addAnimProp(anim, "ADBE Text Rotation");
    if (rot) rot.setValue(-10);

    // Range Offset 从 -100(未选中)→0(全部选中)
    var offProp = sel.property("ADBE Text Percent Offset");
    var speed = 8; // 每字 1/speed 秒
    var charDur = 1.0 / speed;
    var totalDur = Math.min(s.d * 0.6, charDur * s.txt.length);
    offProp.setValueAtTime(s.t, -100);
    offProp.setValueAtTime(s.t + totalDur, 0);

    // 弹性缓动表达式(关键帧之间)
    try {
        offProp.expression =
            "amp=0.15;freq=6;decay=4;" +
            "n=0;t=0;" +
            "if(numKeys>1){" +
            "n=nearestKey(time).index;" +
            "if(n<numKeys){n++;}" +
            "t=time-key(n).time;" +
            "}" +
            "v=velocityAtTime(key(n).time);" +
            "if(n>0&&t<0.5){" +
            "value+v*amp*Math.sin(freq*t*2*Math.PI)*" +
            "Math.exp(-decay*t);" +
            "}else{value;}";
    } catch(e) {}
}

// [V8风格2] strokeReveal 描边揭示
// 先描边可见 Fill 透明,逐字揭示填充
function applyStrokeReveal(layer, s) {
    var anim = addTextAnimator(layer, "StrokeReveal");
    if (!anim) return;
    var sel = getRangeSelector(anim);
    if (!sel) return;

    // Fill Opacity 从 0(只描边)→100(完整)
    var fo = addAnimProp(anim, "ADBE Text Fill Opacity");
    if (fo) fo.setValue(0);

    // Scale 略放大
    var sc = addAnimProp(anim, "ADBE Text Scale");
    if (sc) sc.setValue([105, 105]);

    // Range Offset 逐字推进
    var offProp = sel.property("ADBE Text Percent Offset");
    var charCount = s.txt.length;
    var totalDur = Math.min(s.d * 0.7, 0.15 * charCount);
    offProp.setValueAtTime(s.t, -100);
    offProp.setValueAtTime(s.t + totalDur, 0);

    // 描边宽度表达式: 在揭示前描边加粗,揭示后变细
    try {
        var tp = layer.property("Source Text");
        // 描边宽度通过 Source Text 的 strokeWidth 关键帧
        var swProp = tp;
        var td = tp.value;
        var swStart = s.sw * 2.5;
        var swEnd = s.sw;
        td.strokeWidth = swStart;
        tp.setValueAtTime(s.t, td);
        td.strokeWidth = swEnd;
        tp.setValueAtTime(s.t + totalDur, td);
    } catch(e) {}
}

// [V8风格3] glitchShake 故障抖动
// Wiggly Selector 随机 + Position 抖动 + RGB 分离
function applyGlitchShake(layer, s) {
    var anim = addTextAnimator(layer, "Glitch");
    if (!anim) return;

    // 主 Range Selector
    var sel = getRangeSelector(anim);
    if (!sel) return;

    // Position 抖动
    var pos = addAnimProp(anim, "ADBE Text Position");
    if (pos) pos.setValue([0, 0]);

    // Opacity 随机闪烁
    var op = addAnimProp(anim, "ADBE Text Opacity");
    if (op) op.setValue(100);

    // Scale 随机
    var sc = addAnimProp(anim, "ADBE Text Scale");
    if (sc) sc.setValue([100, 100]);

    // 添加 Wiggly Selector
    var ws = addWigglySelector(anim);
    if (ws) {
        try {
            ws.property("ADBE Text Wiggly Amount")
                .setValue(50);
            ws.property("ADBE Text Wiggly Speed")
                .setValue(8);
            ws.property("ADBE Text Correlation")
                .setValue(0);
        } catch(e) {}
    }

    // Position 表达式高频抖动
    try {
        layer.position.expression =
            "seedRandom(" + s.id + ", true);" +
            "w=wiggle(15, 12);" +
            "[value[0]+w[0]-value[0], " +
            "value[1]+w[1]-value[1]];";
    } catch(e) {}

    // 整体淡入淡出
    layer.opacity.setValueAtTime(s.t, 0);
    layer.opacity.setValueAtTime(s.t + 0.05, 100);
    layer.opacity.setValueAtTime(s.t + s.d, 0);
}

// [V8风格4] flip3D 三维翻转
// 启用 3D + Rotation Y 90→0 + Scale 配合
function applyFlip3D(layer, s) {
    try {
        layer.threeDLayer = true;
    } catch(e) {}

    var anim = addTextAnimator(layer, "Flip3D");
    if (!anim) return;
    var sel = getRangeSelector(anim);
    if (!sel) return;

    // Rotation Y 从 90→0(逐字翻转)
    var ry = addAnimProp(anim, "ADBE Text Rotation Y");
    if (ry) ry.setValue(90);

    // Opacity 从 0→100
    var op = addAnimProp(anim, "ADBE Text Opacity");
    if (op) op.setValue(0);

    // Scale 配合
    var sc = addAnimProp(anim, "ADBE Text Scale");
    if (sc) sc.setValue([80, 80]);

    // Range Offset 逐字翻转
    var offProp = sel.property("ADBE Text Percent Offset");
    var charCount = Math.max(s.txt.length, 2);
    var totalDur = Math.min(s.d * 0.6, 0.08 * charCount);
    offProp.setValueAtTime(s.t, -100);
    offProp.setValueAtTime(s.t + totalDur, 0);

    // 图层级 Z 位置增加深度
    try {
        var pz = layer.property("Position");
        var origZ = pz.value[2] || 0;
        pz.setValueAtTime(s.t,
            [WIDTH/2, s.y, origZ + 200]);
        pz.setValueAtTime(s.t + totalDur,
            [WIDTH/2, s.y, origZ]);
    } catch(e) {}
}

// [V8] 统一动画分发器
function applyTextAnimV8(layer, s) {
    switch(s.anim) {
        case "charPop":
            applyCharPop(layer, s);
            break;
        case "strokeReveal":
            applyStrokeReveal(layer, s);
            break;
        case "glitchShake":
            applyGlitchShake(layer, s);
            break;
        case "flip3D":
            applyFlip3D(layer, s);
            break;
        default:
            applyCharPop(layer, s);
            break;
    }
}

function applyDropShadow(layer, s) {
    // Drop Shadow 效果（非图层样式）
    try {
        var ds = layer.property("Effects")
            .addProperty("Drop Shadow");
        ds.property("Shadow Color")
            .setValue([0, 0, 0]);
        ds.property("Opacity").setValue(85);
        ds.property("Direction").setValue(135);
        ds.property("Distance")
            .setValue(Math.max(3, s.sz * 0.04));
        ds.property("Softness")
            .setValue(Math.max(2, s.sz * 0.06));
        ds.property("Shadow Only").setValue(false);
    } catch(e) {}
}

function createTextGlow(comp, s) {
    // 创建发光层：复制文字+模糊+屏幕混合
    var gl = comp.layers.addText(s.txt);
    gl.name = "GLOW_" + s.id;
    gl.startTime = s.t;
    gl.inPoint = s.t;
    gl.outPoint = s.t + s.d;
    gl.position.setValueAtTime(s.t, [WIDTH/2, s.y]);

    try {
        var tp = gl.property("Source Text");
        var td = tp.value;
        td.fontSize = s.sz;
        td.fillColor = s.glow;
        td.applyFill = true;
        td.applyStroke = false;
        if (s.font) td.font = s.font;
        td.fauxBold = true;
        td.tracking = 50;
        tp.setValue(td);
    } catch(e) {}

    // [V8] GLOW层不做逐字动画,只整体淡入跟随
    // (主文字层做Text Animator逐字动画)
    gl.scale.setValueAtTime(s.t, [80, 80]);
    gl.scale.setValueAtTime(s.t + 0.2, [105, 105]);
    gl.scale.setValueAtTime(s.t + 0.3, [100, 100]);

    // 大模糊产生光晕
    try {
        var b = gl.property("Effects")
            .addProperty("ADBE Fast Blur");
        b.property("Blurriness")
            .setValueAtTime(0, s.sz * 0.25);
        b.property("Repeat Edge Pixels")
            .setValueAtTime(0, true);
    } catch(e) {}

    gl.opacity.setValueAtTime(s.t, 0);
    gl.opacity.setValueAtTime(s.t + 0.08, 70);
    if (s.d > 0.5) {
        gl.opacity.setValueAtTime(
            s.t + s.d - 0.2, 70
        );
    }
    gl.opacity.setValueAtTime(s.t + s.d, 0);
    gl.blendingMode = BlendingMode.ADD;
}

function createRGBSplit(comp, s) {
    // 红色偏移层
    var r = comp.layers.addText(s.txt);
    r.name = "RGB_R_" + s.id;
    r.startTime = s.t; r.inPoint = s.t;
    r.outPoint = s.t + s.d;
    r.position.setValueAtTime(
        s.t, [WIDTH/2 - 6, s.y]
    );
    try {
        var tp = r.property("Source Text");
        var td = tp.value;
        td.fontSize = s.sz;
        td.fillColor = [1, 0, 0];
        td.applyFill = true;
        td.applyStroke = false;
        if (s.font) td.font = s.font;
        td.fauxBold = true;
        td.tracking = 50;
        tp.setValue(td);
    } catch(e) {}

    // 青色偏移层
    var c = comp.layers.addText(s.txt);
    c.name = "RGB_C_" + s.id;
    c.startTime = s.t; c.inPoint = s.t;
    c.outPoint = s.t + s.d;
    c.position.setValueAtTime(
        s.t, [WIDTH/2 + 6, s.y]
    );
    try {
        var tp2 = c.property("Source Text");
        var td2 = tp2.value;
        td2.fontSize = s.sz;
        td2.fillColor = [0, 1, 1];
        td2.applyFill = true;
        td2.applyStroke = false;
        if (s.font) td2.font = s.font;
        td2.fauxBold = true;
        td2.tracking = 50;
        tp2.setValue(td2);
    } catch(e) {}

    // [V8] RGB层做偏移动画,不调用逐字Text Animator
    // 红层向左偏移,青层向右偏移,产生RGB分离效果
    r.position.setValueAtTime(
        s.t, [WIDTH/2 - 8, s.y]
    );
    r.scale.setValueAtTime(s.t, [100, 100]);
    r.opacity.setValueAtTime(s.t, 0);
    r.opacity.setValueAtTime(s.t + 0.05, 50);
    r.opacity.setValueAtTime(s.t + s.d, 0);
    r.blendingMode = BlendingMode.SCREEN;

    c.position.setValueAtTime(
        s.t, [WIDTH/2 + 8, s.y]
    );
    c.scale.setValueAtTime(s.t, [100, 100]);
    c.opacity.setValueAtTime(s.t, 0);
    c.opacity.setValueAtTime(s.t + 0.05, 50);
    c.opacity.setValueAtTime(s.t + s.d, 0);
    c.blendingMode = BlendingMode.SCREEN;
}

function createGradOverlay(comp, mainText, s) {
    // 渐变叠加：渐变固态层 + Alpha Matte
    var grad = comp.layers.addSolid(
        [1,0.8,0.3], "GRAD_" + s.id,
        WIDTH, HEIGHT, 1
    );
    grad.startTime = s.t;
    grad.inPoint = s.t;
    grad.outPoint = s.t + s.d;
    grad.opacity.setValueAtTime(s.t, 0);
    grad.opacity.setValueAtTime(s.t + 0.08, 60);
    if (s.d > 0.5) {
        grad.opacity.setValueAtTime(
            s.t + s.d - 0.2, 60
        );
    }
    grad.opacity.setValueAtTime(s.t + s.d, 0);

    // 设置轨道遮罩 - Alpha Matte
    try {
        grad.trackMatteType = TrackMatteType.ALPHA;
        grad.trackMatteLayer = mainText;
    } catch(e) {}

    grad.blendingMode = BlendingMode.OVERLAY;
}

// ========== [NEW] 段落化多样调色 ==========
function addPerSegmentGrading(comp) {
    // 每段一个独立调色层，使用不同效果组合

    // Intro (0-4s) - 冷蓝忧郁
    var ig = createGradeLayer(comp, "G_Intro", 0, 4);
    addColorBalance(ig, -12, -5, 25);
    tryAddEffect(ig, "CC Toner", function(e) {
        e.property("Tone 1").setValue([0.1,0.15,0.3]);
        e.property("Tone 2").setValue([0.7,0.8,1]);
        e.property("Tone 3").setValue([0.05,0.08,0.15]);
    });

    // Build (4-9s) - 青橙回暖
    var bg = createGradeLayer(comp, "G_Build", 4, 5);
    addColorBalance(bg, 5, -10, 8);
    tryAddEffect(bg, "Photo Filter", function(e) {
        e.property("Color").setValue([1,0.7,0.3]);
        e.property("Density").setValue(40);
    });
    tryAddEffect(bg, "Curves", function(e) {
        // 简单曲线调整 - 提高对比度
    });

    // Drop (9-15s) - 高对比青橙
    var dg = createGradeLayer(comp, "G_Drop", 9, 6);
    addColorBalance(dg, 12, -15, 5);
    tryAddEffect(dg, "CC Toner", function(e) {
        e.property("Tone 1").setValue([0.05,0.1,0.15]);
        e.property("Tone 2").setValue([0.9,0.5,0.2]);
        e.property("Tone 3").setValue([0.15,0.2,0.25]);
    });
    tryAddEffect(dg, "Vibrance", function(e) {
        e.property("Vibrance").setValue(25);
    });

    // Break (15-19s) - 去饱和冷调
    var brg = createGradeLayer(comp, "G_Break", 15, 4);
    addColorBalance(brg, -15, -10, 8);
    tryAddEffect(brg, "Hue/Saturation", function(e) {
        e.property("Master Saturation").setValue(-45);
    });
    tryAddEffect(brg, "Tint", function(e) {
        e.property("Map Black To").setValue([0.05,0.08,0.15]);
        e.property("Map White To").setValue([0.8,0.85,0.95]);
    });

    // Outro (19-23s) - 暖金收束
    var og = createGradeLayer(comp, "G_Outro", 19, 4.15);
    addColorBalance(og, 12, 5, -10);
    tryAddEffect(og, "Photo Filter", function(e) {
        e.property("Color").setValue([1,0.85,0.5]);
        e.property("Density").setValue(50);
    });
    tryAddEffect(og, "CC Toner", function(e) {
        e.property("Tone 1").setValue([0.1,0.08,0.05]);
        e.property("Tone 2").setValue([1,0.85,0.5]);
        e.property("Tone 3").setValue([0.15,0.12,0.08]);
    });
}

function createGradeLayer(comp, name, start, dur) {
    var g = comp.layers.addSolid(
        [1,1,1], name, WIDTH, HEIGHT, 1
    );
    g.name = name;
    g.startTime = start;
    g.inPoint = start;
    g.outPoint = start + dur;
    g.adjustmentLayer = true;
    g.opacity.setValueAtTime(start, 0);
    g.opacity.setValueAtTime(start + 0.2, 100);
    g.opacity.setValueAtTime(start + dur - 0.2, 100);
    g.opacity.setValueAtTime(start + dur, 0);
    return g;
}

function addColorBalance(layer, r, g, b) {
    try {
        var cb = layer.property("Effects")
            .addProperty("Color Balance");
        cb.property("Red Balance").setValue(r);
        cb.property("Green Balance").setValue(g);
        cb.property("Blue Balance").setValue(b);
    } catch(e) {}
}

function tryAddEffect(layer, name, setup) {
    try {
        var e = layer.property("Effects").addProperty(name);
        if (setup) setup(e);
    } catch(e) {}
}

// ========== [REPLACED] 氛围光效（无粒子）==========
function addAtmosphereV7(comp) {
    // 替代粒子系统：使用多层光效

    // 1. Drop段体积光（仅在高潮时刻）
    try {
        var lr = comp.layers.addSolid(
            [1,0.9,0.7], "LightRays", WIDTH, HEIGHT, 1
        );
        lr.startTime = 9.5;
        lr.inPoint = 9.5;
        lr.outPoint = 12;
        lr.adjustmentLayer = true;
        lr.opacity.setValueAtTime(9.5, 0);
        lr.opacity.setValueAtTime(10, 30);
        lr.opacity.setValueAtTime(11.5, 20);
        lr.opacity.setValueAtTime(12, 0);

        var ray = lr.property("Effects")
            .addProperty("CC Light Rays");
        ray.property("Intensity").setValue(60);
        ray.property("Radius").setValue(80);
        ray.property("Warp Amount").setValue(20);
        ray.property("Color").setValue([1,0.9,0.7]);
    } catch(e) {}

    // 2. 全局微妙光雾（替代粒子）
    var haze = comp.layers.addSolid(
        [0.5,0.6,0.8], "LightHaze", WIDTH, HEIGHT, 1
    );
    haze.name = "LightHaze";
    haze.startTime = 0;
    haze.opacity.setValueAtTime(0, 8);
    haze.blendingMode = BlendingMode.SCREEN;
    try {
        var hb = haze.property("Effects")
            .addProperty("ADBE Fast Blur");
        hb.property("Blurriness").setValue(80);
        hb.property("Repeat Edge Pixels")
            .setValueAtTime(0, true);
    } catch(e) {}

    // 3. 段落交界光泄漏（增强氛围）
    addLightLeak(comp, 5.9, 6.2, [0.8,0.4,0.2]);
    addLightLeak(comp, 11.4, 11.7, [0.9,0.5,0.3]);
    addLightLeak(comp, 16.4, 16.7, [0.3,0.4,0.8]);
}

// ========== 全局效果 ==========
function addGlobalEffectsV7(comp) {
    // 扫描线（极低透明度）
    var sl = comp.layers.addSolid(
        [0,0,0], "Scanlines", WIDTH, HEIGHT, 1
    );
    sl.name = "Scanlines";
    sl.startTime = 0;
    sl.adjustmentLayer = true;
    sl.opacity.setValueAtTime(0, 8);
    try {
        var n = sl.property("Effects")
            .addProperty("ADBE Noise");
        n.property("Amount of Noise").setValue(5);
        n.property("Noise Type").setValue(0);
    } catch(e) {}

    // 暗角（音频反应）
    var vg = comp.layers.addSolid(
        [0,0,0], "Vignette", WIDTH, HEIGHT, 1
    );
    vg.name = "Vignette";
    vg.startTime = 0;
    vg.adjustmentLayer = true;
    try {
        var vb = vg.property("Effects")
            .addProperty("ADBE Fast Blur");
        vb.property("Blurriness").setValue(15);
        vb.property("Repeat Edge Pixels")
            .setValueAtTime(0, false);
    } catch(e) {}
    vg.opacity.expression =
        "eng=thisComp.layer(\"Audio Controller\")" +
        ".effect(\"Global Energy\")(\"Slider\")/100;" +
        "b=20;m=50;b+(m-b)*eng;";

    // 胶片颗粒（极低透明度）
    var gr = comp.layers.addSolid(
        [0.5,0.5,0.5], "FilmGrain", WIDTH, HEIGHT, 1
    );
    gr.name = "FilmGrain";
    gr.startTime = 0;
    gr.opacity.setValueAtTime(0, 6);
    gr.blendingMode = BlendingMode.OVERLAY;
    try {
        var gn = gr.property("Effects")
            .addProperty("ADBE Noise");
        gn.property("Amount of Noise").setValue(15);
        gn.property("Noise Type").setValue(1);
    } catch(e) {}
}

// ========== 音频驱动效果 ==========
function addAudioDrivenEffectsV7(comp) {
    for (var i = 1; i <= comp.numLayers; i++) {
        var ly = comp.layer(i);
        var ln = ly.name;
        if (ln.indexOf("Intro_C") >= 0 ||
            ln.indexOf("Build_C") >= 0 ||
            ln.indexOf("Drop_C") >= 0) {
            try {
                var b = ly.property("Effects")
                    .addProperty("ADBE Fast Blur");
                b.property("Blurriness").expression =
                    "h=thisComp.layer(\"Audio Controller\")" +
                    ".effect(\"HighFreq Energy\")" +
                    "(\"Slider\")/100;" +
                    "1+11*h;";
                b.property("Repeat Edge Pixels")
                    .setValueAtTime(0, true);
            } catch(e) {}
            try {
                ly.property("Opacity").expression =
                    "e=thisComp.layer(\"Audio Controller\")" +
                    ".effect(\"Global Energy\")" +
                    "(\"Slider\")/100;" +
                    "85+15*e+Math.sin(time*12.56)*5*e;";
            } catch(e) {}
        }
    }
}

// ========== 图层顺序 ==========
function adjustLayerOrderV7(comp) {
    // 从上到下：
    // 1. 文字主层(TXT_) 2. 文字发光(GLOW_)
    // 3. RGB分离(RGB_) 4. 渐变(GRAD_)
    // 5. 转场 6. 全局效果 7. 调色(G_)
    // 8. 氛围 9. 素材层 10. 控制器

    var order = [
        "TXT_", "GLOW_", "RGB_", "GRAD_",
        "Flash_", "MFlash_", "RBlur_", "Leak_",
        "RGBG_", "Diss_",
        "Scanlines", "Vignette", "FilmGrain",
        "G_Intro", "G_Build", "G_Drop",
        "G_Break", "G_Outro",
        "LightRays", "LightHaze",
        "Intro_C", "Build_C", "Drop_C",
        "Break_C", "Outro_C",
        "Soundtrack", "Main_Camera",
        "Camera_Controller", "Audio Controller"
    ];

    // 收集所有图层名
    var allNames = [];
    for (var i = 1; i <= comp.numLayers; i++) {
        allNames.push(comp.layer(i).name);
    }

    // 按order前缀排序
    var sorted = [];
    for (var o = 0; o < order.length; o++) {
        var prefix = order[o];
        for (var a = 0; a < allNames.length; a++) {
            var n = allNames[a];
            if (n && n.indexOf(prefix) === 0) {
                sorted.push(n);
                allNames[a] = null;
            }
        }
    }
    // 剩余未分类的放最后
    for (var r = 0; r < allNames.length; r++) {
        if (allNames[r]) sorted.push(allNames[r]);
    }

    // 应用顺序
    for (var j = 0; j < sorted.length; j++) {
        var layer = findLayer(comp, sorted[j]);
        if (layer) {
            if (j === 0) {
                layer.moveToBeginning();
            } else {
                var prev = findLayer(comp, sorted[j-1]);
                if (prev) layer.moveAfter(prev);
            }
        }
    }
}

// ========== 工具函数 ==========
function createComposition(n, w, h, d, f) {
    for (var i = 1; i <= app.project.numItems; i++) {
        if (app.project.item(i).name === n &&
            app.project.item(i) instanceof CompItem) {
            app.project.item(i).remove();
            break;
        }
    }
    return app.project.items.addComp(n, w, h, 1, d, f);
}

function safeImport(path) {
    try {
        var f = new File(path);
        if (!f.exists) return null;
        return app.project.importFile(new ImportOptions(f));
    } catch(e) { return null; }
}

function createLayerWithFallBack(comp, ft, n, c) {
    var ly;
    if (ft) {
        try { ly = comp.layers.add(ft); }
        catch(e) {
            ly = comp.layers.addSolid(c, n, WIDTH, HEIGHT, 1);
        }
    } else {
        ly = comp.layers.addSolid(c, n, WIDTH, HEIGHT, 1);
    }
    ly.name = n;
    return ly;
}

function applyTile(layer, pct) {
    try {
        var t = layer.property("Effects")
            .addProperty("ADBE Tile");
        t.property("Output Width").setValue(pct);
        t.property("Output Height").setValue(pct);
        t.property("Mirror Edges").setValue(true);
    } catch(e) {}
}

function createCameraNull(comp) {
    var n = comp.layers.addNull();
    n.name = "Camera_Controller";
    n.startTime = 0;
    n.position.setValueAtTime(
        0, [WIDTH/2, HEIGHT/2, 0]
    );
    n.scale.setValueAtTime(0, [100,100,100]);
    n.rotation.setValueAtTime(0, 0);
    return n;
}

function setKF(layer, prop, time, val) {
    try {
        layer.property(prop).setValueAtTime(time, val);
    } catch(e) {}
}

function applyEasing(prop) {
    for (var i = 1; i <= prop.numKeys; i++) {
        try {
            var dim = prop.valueDimension || 1;
            var ie = [], oe = [];
            for (var d = 0; d < dim; d++) {
                ie.push(new KeyframeEase(0, 75));
                oe.push(new KeyframeEase(0, 75));
            }
            prop.setTemporalEaseAtKey(i, ie, oe);
        } catch(e) {}
    }
}

function addFlash(comp, st, et, mo) {
    var f = comp.layers.addSolid(
        [1,1,1], "Flash_"+st, WIDTH, HEIGHT, 1
    );
    f.startTime = st; f.inPoint = st; f.outPoint = et;
    f.opacity.setValueAtTime(st, 0);
    f.opacity.setValueAtTime(st+0.03, mo);
    f.opacity.setValueAtTime(st+0.06, mo*0.7);
    f.opacity.setValueAtTime(et, 0);
    f.blendingMode = BlendingMode.SCREEN;
}

function addRadialBlur(comp, st, et) {
    var l = comp.layers.addSolid(
        [0,0,0], "RBlur_"+st, WIDTH, HEIGHT, 1
    );
    l.startTime = st; l.inPoint = st; l.outPoint = et;
    l.opacity.setValueAtTime(st, 40);
    l.opacity.setValueAtTime((st+et)/2, 60);
    l.opacity.setValueAtTime(et, 0);
    try {
        var rb = l.property("Effects")
            .addProperty("Radial Blur");
        rb.property("Amount").setValueAtTime(st, 0);
        rb.property("Amount")
            .setValueAtTime((st+et)/2, 60);
        rb.property("Amount").setValueAtTime(et, 0);
    } catch(e) {}
}

function addLightLeak(comp, st, et, color) {
    var l = comp.layers.addSolid(
        color, "Leak_"+st, WIDTH, HEIGHT, 1
    );
    l.startTime = st; l.inPoint = st; l.outPoint = et;
    l.opacity.setValueAtTime(st, 0);
    l.opacity.setValueAtTime(st+0.1, 50);
    l.opacity.setValueAtTime(et-0.1, 30);
    l.opacity.setValueAtTime(et, 0);
    l.blendingMode = BlendingMode.SCREEN;
    try {
        var b = l.property("Effects")
            .addProperty("ADBE Fast Blur");
        b.property("Blurriness").setValue(60);
        b.property("Repeat Edge Pixels")
            .setValueAtTime(0, true);
    } catch(e) {}
}

function addMicroFlash(comp, st, et, op) {
    var f = comp.layers.addSolid(
        [1,1,1], "MFlash_"+st, WIDTH, HEIGHT, 1
    );
    f.startTime = st; f.inPoint = st; f.outPoint = et;
    f.opacity.setValueAtTime(st, 0);
    f.opacity.setValueAtTime(st+0.01, op);
    f.opacity.setValueAtTime(et, 0);
    f.blendingMode = BlendingMode.SCREEN;
}

function findLayer(comp, name) {
    for (var i = 1; i <= comp.numLayers; i++) {
        if (comp.layer(i).name === name) {
            return comp.layer(i);
        }
    }
    return null;
}

// V8脚本自执行(通过AfterFX -r 或 MCP executeAtomScript)
// 用eval加载时由wrapper调用main()
// 直接运行时自动执行
if (typeof main === "function") {
    try { main(); } catch(e) {}
}
