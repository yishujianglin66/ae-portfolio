// textAnimLibrary.jsx
// 程序化文字动画库 - 25种动画效果
// 基于 AE Text Animator 系统（Range/Wiggly/Expression Selector）
// 用法: textAnimLibrary(compIndex, layerIndex, animType, options)

#include "_lib/response_utils.jsx"
#include "_lib/comp_utils.jsx"

// ============ 动画类型注册表 ============
var ANIM_REGISTRY = {
    // --- 入场动画 ---
    "wave":          {name:"波浪入场", cat:"in", props:["position"], selector:"range"},
    "typewriter":    {name:"打字机", cat:"in", props:["opacity"], selector:"range"},
    "bounce":        {name:"弹跳入场", cat:"in", props:["position","scale"], selector:"range"},
    "elastic":       {name:"弹性缩放", cat:"in", props:["scale"], selector:"range"},
    "spiral":        {name:"螺旋飞入", cat:"in", props:["position","rotation"], selector:"range"},
    "fadeCascade":   {name:"级联淡入", cat:"in", props:["opacity","position"], selector:"range"},
    "scalePop":      {name:"缩放弹出", cat:"in", props:["scale","opacity"], selector:"range"},
    "slideUp":       {name:"上滑入场", cat:"in", props:["position","opacity"], selector:"range"},
    "slideDown":     {name:"下滑入场", cat:"in", props:["position","opacity"], selector:"range"},
    "flip3D":        {name:"3D翻转", cat:"in", props:["rotationX","opacity"], selector:"range"},
    "blurReveal":    {name:"模糊揭示", cat:"in", props:["blur","opacity"], selector:"range"},
    "swingIn":       {name:"摆入", cat:"in", props:["rotation","opacity"], selector:"range"},
    "zoomBlur":      {name:"缩放模糊", cat:"in", props:["scale","blur"], selector:"range"},
    "unfold":        {name:"展开", cat:"in", props:["scaleY","opacity"], selector:"range"},
    "glitchIn":      {name:"故障入场", cat:"in", props:["position","opacity"], selector:"wiggly"},
    // --- 持续动画 ---
    "jitter":        {name:"抖动", cat:"loop", props:["position"], selector:"wiggly"},
    "pulse":         {name:"脉冲", cat:"loop", props:["scale"], selector:"wiggly"},
    "flicker":       {name:"闪烁", cat:"loop", props:["opacity"], selector:"wiggly"},
    "wobble":        {name:"摇摆", cat:"loop", props:["rotation"], selector:"wiggly"},
    "breathe":       {name:"呼吸", cat:"loop", props:["scale","opacity"], selector:"expression"},
    "rainbow":       {name:"彩虹流动", cat:"loop", props:["fillColor"], selector:"expression"},
    // --- 退场动画 ---
    "scatterOut":    {name:"散射消失", cat:"out", props:["position","opacity"], selector:"wiggly"},
    "collapseOut":   {name:"坍缩消失", cat:"out", props:["scale","opacity"], selector:"range"},
    "dissolveOut":   {name:"溶解消失", cat:"out", props:["opacity","blur"], selector:"wiggly"},
    "flyOut":        {name:"飞出", cat:"out", props:["position","opacity"], selector:"range"}
};

// ============ 核心引擎 ============

/**
 * 获取或创建文字图层
 */
function getTextLayer(comp, layerIndex) {
    if (layerIndex >= 1 && layerIndex <= comp.numLayers) {
        var layer = comp.layer(layerIndex);
        if (layer.property("Text") !== null) return layer;
    }
    return null;
}

/**
 * 添加 Text Animator 并配置属性
 */
function addAnimator(textProp, animName) {
    var animators = textProp.property("ADBE Text Animators");
    var animator = animators.addProperty("ADBE Text Animator");
    animator.name = animName;
    return animator;
}

/**
 * 配置 Range Selector
 */
function setupRangeSelector(animator, opts) {
    var selectors = animator.property("ADBE Text Selectors");
    var rangeSel = selectors.addProperty("ADBE Text Selector");
    rangeSel.name = "Range Selector 1";
    
    var start = opts.start !== undefined ? opts.start : 0;
    var end = opts.end !== undefined ? opts.end : 100;
    var offset = opts.offset !== undefined ? opts.offset : 0;
    
    rangeSel.property("ADBE Text Percent Start").setValue(start);
    rangeSel.property("ADBE Text Percent End").setValue(end);
    rangeSel.property("ADBE Text Percent Offset").setValue(offset);
    
    // 高级选项
    if (opts.shape) {
        var shapeMap = {"square":1, "ramp_up":2, "ramp_down":3, "triangle":4, "round":5, "smooth":6};
        rangeSel.property("ADBE Text Range Type2").setValue(shapeMap[opts.shape] || 1);
    }
    if (opts.basedOn) {
        var basedMap = {"characters":1, "characters_no_spaces":2, "words":3, "lines":4};
        rangeSel.property("ADBE Text Range Units").setValue(basedMap[opts.basedOn] || 1);
    }
    if (opts.mode) {
        rangeSel.property("ADBE Text Selector Mode").setValue(opts.mode);
    }
    return rangeSel;
}

/**
 * 配置 Wiggly Selector
 */
function setupWigglySelector(animator, opts) {
    var selectors = animator.property("ADBE Text Selectors");
    var wigglySel = selectors.addProperty("ADBE Text Wiggly Selector");
    wigglySel.name = "Wiggly Selector 1";
    
    if (opts.maxAmount !== undefined) wigglySel.property("ADBE Text Wiggly Max Amount").setValue(opts.maxAmount);
    if (opts.minAmount !== undefined) wigglySel.property("ADBE Text Wiggly Min Amount").setValue(opts.minAmount);
    if (opts.wigglesPerSecond !== undefined) wigglySel.property("ADBE Text Wiggly Rate").setValue(opts.wigglesPerSecond);
    if (opts.correlation !== undefined) wigglySel.property("ADBE Text Wiggly Correlation").setValue(opts.correlation);
    if (opts.temporalPhase !== undefined) wigglySel.property("ADBE Text Temporal Phase").setValue(opts.temporalPhase);
    return wigglySel;
}

/**
 * 向 Animator 添加动画属性
 */
function addAnimProperty(animator, propName, value) {
    var props = animator.property("ADBE Text Animator Properties");
    var propMap = {
        "position": "ADBE Text Position 3D",
        "scale": "ADBE Text Scale 3D",
        "scaleX": "ADBE Text Scale 3D",
        "scaleY": "ADBE Text Scale 3D",
        "rotation": "ADBE Text Rotation",
        "rotationX": "ADBE Text Rotation X",
        "rotationY": "ADBE Text Rotation Y",
        "opacity": "ADBE Text Opacity",
        "blur": "ADBE Text Blur",
        "fillColor": "ADBE Text Fill Color",
        "strokeColor": "ADBE Text Stroke Color",
        "strokeWidth": "ADBE Text Stroke Width",
        "tracking": "ADBE Text Tracking Amount",
        "skew": "ADBE Text Skew",
        "anchorPoint": "ADBE Text Anchor Point 3D",
        "characterOffset": "ADBE Text Character Offset"
    };
    
    var matchName = propMap[propName];
    if (!matchName) return null;
    
    var prop = props.addProperty(matchName);
    if (prop && value !== undefined) {
        try { prop.setValue(value); } catch(e) {}
    }
    return prop;
}

/**
 * 设置关键帧动画（Range Selector Offset 驱动）
 */
function animateSelectorOffset(rangeSel, startTime, duration, fromOffset, toOffset, easing) {
    var offsetProp = rangeSel.property("ADBE Text Percent Offset");
    offsetProp.setValueAtTime(startTime, fromOffset);
    offsetProp.setValueAtTime(startTime + duration, toOffset);
    
    // 应用缓动
    if (easing === "ease" || easing === "easeOut" || easing === "easeIn") {
        var easeIn, easeOut;
        if (easing === "ease") {
            easeIn = new KeyframeEase(0, 75);
            easeOut = new KeyframeEase(0, 75);
        } else if (easing === "easeOut") {
            easeIn = new KeyframeEase(0, 33);
            easeOut = new KeyframeEase(0, 90);
        } else {
            easeIn = new KeyframeEase(0, 90);
            easeOut = new KeyframeEase(0, 33);
        }
        offsetProp.setTemporalEaseAtKey(1, [easeIn], [easeOut]);
        offsetProp.setTemporalEaseAtKey(2, [easeIn], [easeOut]);
    }
}

// ============ 25种动画实现 ============

function anim_wave(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "Wave");
    var pos = addAnimProperty(animator, "position", [0, opts.amplitude || -50, 0]);
    var rangeSel = setupRangeSelector(animator, {start:0, end:20, shape:"smooth", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 1.0, 0, 100, "ease");
    return "wave applied";
}

function anim_typewriter(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "Typewriter");
    addAnimProperty(animator, "opacity", 0);
    var rangeSel = setupRangeSelector(animator, {start:0, end:100, shape:"square", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 1.5, -100, 0, "ease");
    return "typewriter applied";
}

function anim_bounce(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "Bounce");
    addAnimProperty(animator, "position", [0, opts.dropHeight || -200, 0]);
    addAnimProperty(animator, "scale", [120, 80, 100]);
    var rangeSel = setupRangeSelector(animator, {start:0, end:30, shape:"round", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 0.8, -30, 100, "easeOut");
    return "bounce applied";
}

function anim_elastic(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "Elastic");
    addAnimProperty(animator, "scale", [0, 0, 0]);
    addAnimProperty(animator, "opacity", 0);
    var rangeSel = setupRangeSelector(animator, {start:0, end:25, shape:"smooth", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 1.0, -25, 100, "ease");
    // 添加弹性表达式到 Scale
    var scaleProp = animator.property("ADBE Text Animator Properties").property("ADBE Text Scale 3D");
    if (scaleProp) {
        scaleProp.expression = "freq = " + (opts.frequency || 3) + ";\ndecay = " + (opts.decay || 5) + ";\nn = 0;\nif (numKeys > 0) {\n  n = nearestKey(time).index;\n  if (key(n).time > time) n--;\n}\nif (n > 0) {\n  t = time - key(n).time;\n  amp = velocityAtTime(key(n).time - .001);\n  value + amp * Math.sin(freq * t * 2 * Math.PI) / Math.exp(decay * t) / freq;\n} else {\n  value;\n}";
    }
    return "elastic applied";
}

function anim_spiral(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "Spiral");
    addAnimProperty(animator, "position", [opts.radius || 300, opts.radius || 300, 0]);
    addAnimProperty(animator, "rotation", opts.spins || 720);
    addAnimProperty(animator, "opacity", 0);
    var rangeSel = setupRangeSelector(animator, {start:0, end:20, shape:"ramp_up", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 1.2, -20, 100, "ease");
    return "spiral applied";
}

function anim_fadeCascade(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "FadeCascade");
    addAnimProperty(animator, "opacity", 0);
    addAnimProperty(animator, "position", [0, opts.yOffset || 30, 0]);
    var rangeSel = setupRangeSelector(animator, {start:0, end:40, shape:"ramp_up", basedOn:"words"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 1.0, -40, 100, "ease");
    return "fadeCascade applied";
}

function anim_scalePop(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "ScalePop");
    addAnimProperty(animator, "scale", [0, 0, 0]);
    addAnimProperty(animator, "opacity", 0);
    var rangeSel = setupRangeSelector(animator, {start:0, end:15, shape:"round", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 0.6, -15, 100, "easeOut");
    return "scalePop applied";
}

function anim_slideUp(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "SlideUp");
    addAnimProperty(animator, "position", [0, opts.distance || 100, 0]);
    addAnimProperty(animator, "opacity", 0);
    var rangeSel = setupRangeSelector(animator, {start:0, end:30, shape:"ramp_down", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 0.8, -30, 100, "easeOut");
    return "slideUp applied";
}

function anim_slideDown(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "SlideDown");
    addAnimProperty(animator, "position", [0, -(opts.distance || 100), 0]);
    addAnimProperty(animator, "opacity", 0);
    var rangeSel = setupRangeSelector(animator, {start:0, end:30, shape:"ramp_up", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 0.8, -30, 100, "easeOut");
    return "slideDown applied";
}

function anim_flip3D(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "Flip3D");
    addAnimProperty(animator, "rotationX", opts.angle || -90);
    addAnimProperty(animator, "opacity", 0);
    // 启用3D
    layer.threeDLayer = true;
    var rangeSel = setupRangeSelector(animator, {start:0, end:25, shape:"smooth", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 1.0, -25, 100, "ease");
    return "flip3D applied";
}

function anim_blurReveal(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "BlurReveal");
    addAnimProperty(animator, "blur", [opts.blurAmount || 30, opts.blurAmount || 30]);
    addAnimProperty(animator, "opacity", 0);
    var rangeSel = setupRangeSelector(animator, {start:0, end:50, shape:"smooth", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 1.2, -50, 100, "ease");
    return "blurReveal applied";
}

function anim_swingIn(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "SwingIn");
    addAnimProperty(animator, "rotation", opts.angle || -60);
    addAnimProperty(animator, "opacity", 0);
    addAnimProperty(animator, "anchorPoint", [0, -(opts.pivotY || 50), 0]);
    var rangeSel = setupRangeSelector(animator, {start:0, end:20, shape:"ramp_up", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 0.9, -20, 100, "easeOut");
    return "swingIn applied";
}

function anim_zoomBlur(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "ZoomBlur");
    addAnimProperty(animator, "scale", [opts.startScale || 300, opts.startScale || 300, 100]);
    addAnimProperty(animator, "blur", [20, 20]);
    addAnimProperty(animator, "opacity", 0);
    var rangeSel = setupRangeSelector(animator, {start:0, end:30, shape:"smooth", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 0.8, -30, 100, "easeOut");
    return "zoomBlur applied";
}

function anim_unfold(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "Unfold");
    addAnimProperty(animator, "scale", [100, 0, 100]);
    addAnimProperty(animator, "opacity", 0);
    addAnimProperty(animator, "anchorPoint", [0, -(opts.pivotOffset || 30), 0]);
    var rangeSel = setupRangeSelector(animator, {start:0, end:20, shape:"ramp_down", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 0, opts.duration || 0.7, -20, 100, "easeOut");
    return "unfold applied";
}

function anim_glitchIn(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "GlitchIn");
    addAnimProperty(animator, "position", [0, 0, 0]);
    addAnimProperty(animator, "opacity", 0);
    addAnimProperty(animator, "characterOffset", opts.charShift || 10);
    var wigglySel = setupWigglySelector(animator, {
        maxAmount: opts.maxAmount || 100,
        minAmount: 0,
        wigglesPerSecond: opts.speed || 15,
        correlation: opts.correlation || 0
    });
    // 添加表达式控制逐渐稳定
    var opacityProp = animator.property("ADBE Text Animator Properties").property("ADBE Text Opacity");
    if (opacityProp) {
        opacityProp.expression = "t = time - " + (opts.startTime || 0) + ";\ndur = " + (opts.duration || 1.0) + ";\nif (t < dur) {\n  Math.random() > (t/dur) ? 0 : 100;\n} else {\n  100;\n}";
    }
    return "glitchIn applied";
}

function anim_jitter(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "Jitter");
    addAnimProperty(animator, "position", [0, 0, 0]);
    setupWigglySelector(animator, {
        maxAmount: opts.amount || 5,
        minAmount: -(opts.amount || 5),
        wigglesPerSecond: opts.speed || 20,
        correlation: 0
    });
    return "jitter applied (loop)";
}

function anim_pulse(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "Pulse");
    addAnimProperty(animator, "scale", [0, 0, 0]);
    setupWigglySelector(animator, {
        maxAmount: opts.amount || 15,
        minAmount: -(opts.amount || 5),
        wigglesPerSecond: opts.speed || 2,
        correlation: opts.correlation || 50
    });
    return "pulse applied (loop)";
}

function anim_flicker(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "Flicker");
    addAnimProperty(animator, "opacity", 0);
    setupWigglySelector(animator, {
        maxAmount: opts.maxAmount || 100,
        minAmount: 0,
        wigglesPerSecond: opts.speed || 8,
        correlation: 0
    });
    return "flicker applied (loop)";
}

function anim_wobble(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "Wobble");
    addAnimProperty(animator, "rotation", 0);
    setupWigglySelector(animator, {
        maxAmount: opts.amount || 10,
        minAmount: -(opts.amount || 10),
        wigglesPerSecond: opts.speed || 3,
        correlation: opts.correlation || 30
    });
    return "wobble applied (loop)";
}

function anim_breathe(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "Breathe");
    var scaleProp = addAnimProperty(animator, "scale", [0, 0, 0]);
    var opacityProp = addAnimProperty(animator, "opacity", 0);
    setupRangeSelector(animator, {start:0, end:100});
    // 呼吸表达式
    if (scaleProp) {
        var amp = opts.amplitude || 5;
        var speed = opts.speed || 1.5;
        scaleProp.expression = "amp = " + amp + ";\nspeed = " + speed + ";\n[value[0] + amp * Math.sin(time * speed * Math.PI * 2), value[1] + amp * Math.sin(time * speed * Math.PI * 2), value[2]];";
    }
    if (opacityProp) {
        opacityProp.expression = "base = 85;\namp = 15;\nbase + amp * Math.sin(time * " + (opts.speed || 1.5) + " * Math.PI * 2);";
    }
    return "breathe applied (loop)";
}

function anim_rainbow(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "Rainbow");
    var fillProp = addAnimProperty(animator, "fillColor", [1, 0, 0, 1]);
    setupRangeSelector(animator, {start:0, end:100, basedOn:"characters"});
    // 彩虹表达式
    if (fillProp) {
        var speed = opts.speed || 0.5;
        fillProp.expression = "speed = " + speed + ";\nidx = textIndex;\ntotal = textTotal;\nhue = (idx / total + time * speed) % 1.0;\n// HSL to RGB\nfunction hsl2rgb(h,s,l){\n  var r,g,b;\n  if(s==0){r=g=b=l;}else{\n    function hue2rgb(p,q,t){if(t<0)t+=1;if(t>1)t-=1;if(t<1/6)return p+(q-p)*6*t;if(t<1/2)return q;if(t<2/3)return p+(q-p)*(2/3-t)*6;return p;}\n    var q=l<0.5?l*(1+s):l+s-l*s;var p=2*l-q;\n    r=hue2rgb(p,q,h+1/3);g=hue2rgb(p,q,h);b=hue2rgb(p,q,h-1/3);\n  }\n  return [r,g,b,1];\n}\nhsl2rgb(hue, 1.0, 0.5);";
    }
    return "rainbow applied (loop)";
}

function anim_scatterOut(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "ScatterOut");
    addAnimProperty(animator, "position", [0, 0, 0]);
    addAnimProperty(animator, "opacity", 0);
    setupWigglySelector(animator, {
        maxAmount: opts.amount || 100,
        minAmount: -(opts.amount || 100),
        wigglesPerSecond: 0.01,
        temporalPhase: 0
    });
    // 用表达式控制触发时间
    var posProp = animator.property("ADBE Text Animator Properties").property("ADBE Text Position 3D");
    if (posProp) {
        var st = opts.startTime || 2.0;
        posProp.expression = "t = time - " + st + ";\nif (t > 0) {\n  seedRandom(textIndex, true);\n  var dx = random(-1,1) * " + (opts.scatter || 500) + " * t;\n  var dy = random(-1,1) * " + (opts.scatter || 500) + " * t;\n  [dx, dy, 0];\n} else {\n  [0,0,0];\n}";
    }
    return "scatterOut applied";
}

function anim_collapseOut(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "CollapseOut");
    addAnimProperty(animator, "scale", [0, 0, 0]);
    addAnimProperty(animator, "opacity", 0);
    var rangeSel = setupRangeSelector(animator, {start:0, end:30, shape:"round", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 2.0, opts.duration || 0.6, 100, -30, "easeIn");
    return "collapseOut applied";
}

function anim_dissolveOut(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "DissolveOut");
    addAnimProperty(animator, "opacity", 0);
    addAnimProperty(animator, "blur", [opts.blurAmount || 15, opts.blurAmount || 15]);
    setupWigglySelector(animator, {
        maxAmount: 100,
        minAmount: 0,
        wigglesPerSecond: 0.01,
        temporalPhase: 0
    });
    var opProp = animator.property("ADBE Text Animator Properties").property("ADBE Text Opacity");
    if (opProp) {
        var st = opts.startTime || 2.0;
        var dur = opts.duration || 1.0;
        opProp.expression = "t = time - " + st + ";\nif (t > 0) {\n  seedRandom(textIndex, true);\n  var threshold = t / " + dur + ";\n  random() < threshold ? 0 : 100;\n} else {\n  100;\n}";
    }
    return "dissolveOut applied";
}

function anim_flyOut(comp, layer, opts) {
    var textProp = layer.property("Text");
    var animator = addAnimator(textProp, "FlyOut");
    addAnimProperty(animator, "position", [0, -(opts.distance || 300), 0]);
    addAnimProperty(animator, "opacity", 0);
    var rangeSel = setupRangeSelector(animator, {start:0, end:25, shape:"ramp_up", basedOn:"characters"});
    animateSelectorOffset(rangeSel, opts.startTime || 2.0, opts.duration || 0.7, 100, -25, "easeIn");
    return "flyOut applied";
}

// ============ 主入口 ============
function textAnimLibrary(args) {
    var compIndex = args.compIndex || 1;
    var layerIndex = args.layerIndex || 1;
    var animType = args.animType || "wave";
    var options = args.options || {};
    
    // 获取合成
    var comp;
    if (args.compName) {
        comp = findCompByName(args.compName);
    } else {
        comp = app.project.item(compIndex);
    }
    if (!comp || !(comp instanceof CompItem)) {
        return buildErrorResponse("comp_not_found", "合成未找到: index=" + compIndex);
    }
    
    // 获取文字图层
    var layer = getTextLayer(comp, layerIndex);
    if (!layer) {
        return buildErrorResponse("layer_not_text", "图层 " + layerIndex + " 不是文字图层");
    }
    
    // 分发动画
    var animFunc = {
        "wave": anim_wave, "typewriter": anim_typewriter, "bounce": anim_bounce,
        "elastic": anim_elastic, "spiral": anim_spiral, "fadeCascade": anim_fadeCascade,
        "scalePop": anim_scalePop, "slideUp": anim_slideUp, "slideDown": anim_slideDown,
        "flip3D": anim_flip3D, "blurReveal": anim_blurReveal, "swingIn": anim_swingIn,
        "zoomBlur": anim_zoomBlur, "unfold": anim_unfold, "glitchIn": anim_glitchIn,
        "jitter": anim_jitter, "pulse": anim_pulse, "flicker": anim_flicker,
        "wobble": anim_wobble, "breathe": anim_breathe, "rainbow": anim_rainbow,
        "scatterOut": anim_scatterOut, "collapseOut": anim_collapseOut,
        "dissolveOut": anim_dissolveOut, "flyOut": anim_flyOut
    };
    
    var func = animFunc[animType];
    if (!func) {
        // 列出所有可用动画
        var available = [];
        for (var key in ANIM_REGISTRY) { available.push(key); }
        return buildErrorResponse("unknown_anim", "未知动画类型: " + animType + "。可用: " + available.join(", "));
    }
    
    // 执行
    app.beginUndoGroup("TextAnim_" + animType);
    try {
        var result = func(comp, layer, options);
        app.endUndoGroup();
        return buildSuccessResponse({
            animation: animType,
            category: ANIM_REGISTRY[animType].cat,
            description: ANIM_REGISTRY[animType].name,
            layer: layer.name,
            comp: comp.name,
            result: result
        });
    } catch(e) {
        app.endUndoGroup();
        return buildErrorResponse("anim_error", animType + " 执行失败: " + e.message);
    }
}

// 列出所有动画
function listAnimations() {
    var list = [];
    for (var key in ANIM_REGISTRY) {
        list.push({
            id: key,
            name: ANIM_REGISTRY[key].name,
            category: ANIM_REGISTRY[key].cat,
            selector: ANIM_REGISTRY[key].selector
        });
    }
    return buildSuccessResponse({total: list.length, animations: list});
}

// 入口调度
var _args = (typeof args !== "undefined") ? args : {};
if (_args.action === "list") {
    listAnimations();
} else {
    textAnimLibrary(_args);
}
