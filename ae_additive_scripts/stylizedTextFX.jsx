// stylizedTextFX.jsx
// 风格化文字特效库 - 15种视觉风格
// 通过组合 AE 内置效果实现：霓虹/故障/水墨/全息/火焰/金属/描边/发光等
// 用法: stylizedTextFX(args) 其中 args = {compIndex, layerIndex, style, options}

#include "_lib/response_utils.jsx"
#include "_lib/comp_utils.jsx"

// ============ 风格注册表 ============
var STYLE_REGISTRY = {
    "neon":        {name:"霓虹灯", effects:["glow","stroke"], complexity:"medium"},
    "glitch":      {name:"故障风", effects:["displacement","colorShift"], complexity:"high"},
    "inkWash":     {name:"水墨风", effects:["roughen","blur","tint"], complexity:"medium"},
    "holographic": {name:"全息投影", effects:["glow","colorCycle","scanline"], complexity:"high"},
    "fire":        {name:"火焰字", effects:["turbulentDisplace","glow","colorama"], complexity:"high"},
    "chrome":      {name:"金属铬", effects:["bevel","gradient","specular"], complexity:"medium"},
    "outline":     {name:"描边字", effects:["stroke","fill"], complexity:"low"},
    "softGlow":    {name:"柔光", effects:["glow","blur"], complexity:"low"},
    "retro":       {name:"复古VHS", effects:["noise","colorShift","scanline"], complexity:"medium"},
    "ice":         {name:"冰霜字", effects:["fractal","tint","glow"], complexity:"medium"},
    "electric":    {name:"电弧字", effects:["lightning","glow","flicker"], complexity:"high"},
    "shadow3D":    {name:"3D阴影", effects:["dropShadow","extrude"], complexity:"medium"},
    "gradient":    {name:"渐变填充", effects:["gradientRamp","fill"], complexity:"low"},
    "particle":    {name:"粒子消散", effects:["ccParticleSystem","glow"], complexity:"high"},
    "cyberpunk":   {name:"赛博朋克", effects:["glow","glitch","neon","scanline"], complexity:"high"}
};

// ============ 效果构建器 ============

/**
 * 添加发光效果 (Glow)
 */
function addGlowEffect(layer, opts) {
    var glow = layer.Effects.addProperty("ADBE Glo2");
    glow.name = opts.name || "StylizedGlow";
    // 发光阈值
    glow.property("ADBE Glo2-0002").setValue(opts.threshold || 0.6);
    // 发光半径
    glow.property("ADBE Glo2-0003").setValue(opts.radius || 20);
    // 发光强度
    glow.property("ADBE Glo2-0004").setValue(opts.intensity || 1.5);
    // 发光颜色: A&B颜色 / 原始颜色
    if (opts.colorA && opts.colorB) {
        glow.property("ADBE Glo2-0005").setValue(3); // A&B Colors
        glow.property("ADBE Glo2-0006").setValue(opts.colorA); // Color A
        glow.property("ADBE Glo2-0007").setValue(opts.colorB); // Color B
    }
    return glow;
}

/**
 * 添加描边 (Stroke via Fill/Stroke)
 */
function addStrokeToText(layer, opts) {
    var textProp = layer.property("Text");
    var textDoc = textProp.property("ADBE Text Document").value;
    
    // 设置描边
    textDoc.strokeColor = opts.strokeColor || [1, 1, 1];
    textDoc.strokeWidth = opts.strokeWidth || 2;
    textDoc.strokeOverFill = opts.strokeOverFill !== undefined ? opts.strokeOverFill : true;
    
    // 设置填充
    if (opts.fillColor) {
        textDoc.fillColor = opts.fillColor;
    }
    if (opts.noFill) {
        textDoc.fillColor = null;
    }
    
    textProp.property("ADBE Text Document").setValue(textDoc);
}

/**
 * 添加湍流置换 (Turbulent Displace) - 用于火焰/水墨
 */
function addTurbulentDisplace(layer, opts) {
    var td = layer.Effects.addProperty("ADBE Turbulent Displace");
    td.name = opts.name || "TurbulentDisplace";
    td.property("ADBE Turbulent Displace-0001").setValue(opts.amount || 30);
    td.property("ADBE Turbulent Displace-0002").setValue(opts.size || 50);
    // 动画演化
    var evoProp = td.property("ADBE Turbulent Displace-0005");
    var st = opts.startTime || 0;
    var dur = opts.duration || 4;
    evoProp.setValueAtTime(st, 0);
    evoProp.setValueAtTime(st + dur, opts.evolution || 360);
    // 表达式循环
    if (opts.loop) {
        evoProp.expression = "time * " + (opts.speed || 90);
    }
    return td;
}

/**
 * 添加快速模糊 (Fast Box Blur)
 */
function addBlurEffect(layer, opts) {
    var blur = layer.Effects.addProperty("ADBE Box Blur2");
    blur.name = opts.name || "StylizedBlur";
    blur.property("ADBE Box Blur2-0001").setValue(opts.radius || 5);
    blur.property("ADBE Box Blur2-0002").setValue(opts.radius || 5);
    return blur;
}

/**
 * 添加色相/饱和度 - 用于色彩偏移
 */
function addHueSaturation(layer, opts) {
    var hs = layer.Effects.addProperty("ADBE HUE SATURATION");
    hs.name = opts.name || "ColorShift";
    if (opts.hueShift) hs.property("ADBE HUE SATURATION-0001").setValue(opts.hueShift);
    if (opts.saturation) hs.property("ADBE HUE SATURATION-0002").setValue(opts.saturation);
    if (opts.lightness) hs.property("ADBE HUE SATURATION-0003").setValue(opts.lightness);
    return hs;
}

/**
 * 添加噪波 (Noise) - 用于复古/VHS
 */
function addNoiseEffect(layer, opts) {
    var noise = layer.Effects.addProperty("ADBE Noise");
    noise.name = opts.name || "RetroNoise";
    noise.property("ADBE Noise-0001").setValue(opts.amount || 15);
    return noise;
}

/**
 * 添加分形噪波 (Fractal Noise) - 用于冰霜/纹理
 */
function addFractalNoise(layer, opts) {
    var fn = layer.Effects.addProperty("ADBE Fractal Noise");
    fn.name = opts.name || "FractalTexture";
    fn.property("ADBE Fractal Noise-0001").setValue(opts.fractalType || 1); // Basic
    fn.property("ADBE Fractal Noise-0002").setValue(opts.noiseType || 3); // Spline
    fn.property("ADBE Fractal Noise-0003").setValue(opts.contrast || 150);
    fn.property("ADBE Fractal Noise-0004").setValue(opts.brightness || -20);
    // 演化动画
    var evoProp = fn.property("ADBE Fractal Noise-0006");
    if (opts.animate) {
        evoProp.expression = "time * " + (opts.speed || 30);
    }
    return fn;
}

/**
 * 添加色调 (Tint) - 用于水墨/单色
 */
function addTintEffect(layer, opts) {
    var tint = layer.Effects.addProperty("ADBE Tint");
    tint.name = opts.name || "Tint";
    tint.property("ADBE Tint-0001").setValue(opts.blackColor || [0, 0, 0, 1]);
    tint.property("ADBE Tint-0002").setValue(opts.whiteColor || [1, 1, 1, 1]);
    tint.property("ADBE Tint-0003").setValue(opts.amount || 100);
    return tint;
}

/**
 * 添加 CC Light Rays 模拟光束
 */
function addLightRays(layer, opts) {
    try {
        var lr = layer.Effects.addProperty("CC Light Rays");
        lr.name = opts.name || "LightRays";
        return lr;
    } catch(e) {
        return null; // 插件不可用
    }
}

/**
 * 添加 Venetian Blinds 扫描线效果
 */
function addScanlines(layer, opts) {
    // 用 Venetian Blinds 模拟扫描线
    var vb = layer.Effects.addProperty("ADBE Venetian Blinds");
    vb.name = opts.name || "Scanlines";
    vb.property("ADBE Venetian Blinds-0001").setValue(opts.direction || 90);
    vb.property("ADBE Venetian Blinds-0002").setValue(opts.width || 3);
    vb.property("ADBE Venetian Blinds-0003").setValue(opts.feather || 0);
    vb.property("ADBE Venetian Blinds-0004").setValue(opts.opacity || 30);
    return vb;
}

/**
 * 添加 Drop Shadow
 */
function addDropShadow(layer, opts) {
    var ds = layer.Effects.addProperty("ADBE Drop Shadow");
    ds.name = opts.name || "DropShadow";
    ds.property("ADBE Drop Shadow-0001").setValue(opts.color || [0, 0, 0, 0.7]);
    ds.property("ADBE Drop Shadow-0002").setValue(opts.opacity || 180);
    ds.property("ADBE Drop Shadow-0003").setValue(opts.direction || 135);
    ds.property("ADBE Drop Shadow-0004").setValue(opts.distance || 10);
    ds.property("ADBE Drop Shadow-0005").setValue(opts.softness || 8);
    return ds;
}

/**
 * 添加 Gradient Ramp 到文字
 */
function addGradientFill(layer, opts) {
    // 通过 Text Document 设置渐变不直接支持
    // 使用 Fill 效果 + Set Matte 或 Gradient Ramp 叠加
    var gr = layer.Effects.addProperty("ADBE Ramp");
    gr.name = opts.name || "GradientFill";
    gr.property("ADBE Ramp-0001").setValue(opts.startPoint || [960, 200]);
    gr.property("ADBE Ramp-0002").setValue(opts.startColor || [1, 0, 0.5, 1]);
    gr.property("ADBE Ramp-0003").setValue(opts.endPoint || [960, 800]);
    gr.property("ADBE Ramp-0004").setValue(opts.endColor || [0, 0.5, 1, 1]);
    gr.property("ADBE Ramp-0005").setValue(opts.rampShape || 1); // Linear
    // 设置为 Alpha 叠加模式
    gr.property("ADBE Ramp-0006").setValue(3); // Composite with Original: Behind
    return gr;
}

// ============ 15种风格组合 ============

function style_neon(comp, layer, opts) {
    // 霓虹灯：无填充 + 彩色描边 + 强发光
    addStrokeToText(layer, {
        fillColor: opts.fillColor || [0, 0, 0],
        strokeColor: opts.neonColor || [0, 1, 1],
        strokeWidth: opts.strokeWidth || 3,
        strokeOverFill: true
    });
    addGlowEffect(layer, {
        radius: opts.glowRadius || 25,
        intensity: opts.glowIntensity || 2.0,
        threshold: 0.3,
        colorA: opts.neonColor || [0, 1, 1],
        colorB: opts.neonColor2 || [1, 0, 1]
    });
    // 添加微弱闪烁
    if (opts.flicker !== false) {
        var glow = layer.Effects.property("StylizedGlow");
        if (glow) {
            glow.property("ADBE Glo2-0004").expression = "base = " + (opts.glowIntensity || 2.0) + ";\nbase + random(-0.3, 0.3) * (Math.sin(time * 15) > 0.8 ? 1 : 0);";
        }
    }
    return "neon style applied";
}

function style_glitch(comp, layer, opts) {
    // 故障风：RGB分离 + 位移 + 闪烁
    // 复制两层做 RGB 分离
    var redLayer = layer.duplicate();
    redLayer.name = layer.name + "_R";
    var blueLayer = layer.duplicate();
    blueLayer.name = layer.name + "_B";
    
    // 红色通道层
    var redShift = redLayer.Effects.addProperty("ADBE HUE SATURATION");
    redShift.property("ADBE HUE SATURATION-0002").setValue(-100);
    redLayer.Effects.addProperty("ADBE Fill");
    redLayer.Effects.property("ADBE Fill").property("ADBE Fill-0002").setValue([1, 0, 0, 1]);
    redLayer.blendingMode = BlendingMode.ADD;
    
    // 蓝色通道层
    blueLayer.Effects.addProperty("ADBE Fill");
    blueLayer.Effects.property("ADBE Fill").property("ADBE Fill-0002").setValue([0, 0, 1, 1]);
    blueLayer.blendingMode = BlendingMode.ADD;
    
    // 位移动画表达式
    var offset = opts.offset || 5;
    redLayer.property("Position").expression = "seedRandom(1, false);\n[value[0] + random(-" + offset + "," + offset + ") * (Math.random() > 0.9 ? 1 : 0), value[1]];";
    blueLayer.property("Position").expression = "seedRandom(2, false);\n[value[0] + random(-" + offset + "," + offset + ") * (Math.random() > 0.9 ? 1 : 0), value[1]];";
    
    // 原始层添加偶尔的位移抖动
    layer.property("Position").expression = "t = time;\nif (Math.sin(t * 30) > 0.95) {\n  seedRandom(Math.floor(t*10), true);\n  [value[0] + random(-8,8), value[1] + random(-3,3)];\n} else {\n  value;\n}";
    
    return "glitch style applied (3 layers)";
}

function style_inkWash(comp, layer, opts) {
    // 水墨风：粗糙边缘 + 模糊 + 黑白
    addTurbulentDisplace(layer, {
        amount: opts.roughness || 15,
        size: opts.inkSize || 30,
        loop: true,
        speed: 20
    });
    addBlurEffect(layer, {radius: opts.blurAmount || 1.5});
    addTintEffect(layer, {
        blackColor: [0.05, 0.05, 0.05, 1],
        whiteColor: opts.inkColor || [0.15, 0.15, 0.2, 1],
        amount: 100
    });
    return "inkWash style applied";
}

function style_holographic(comp, layer, opts) {
    // 全息投影：半透明 + 彩色发光 + 扫描线 + 闪烁
    var textProp = layer.property("Text");
    var textDoc = textProp.property("ADBE Text Document").value;
    textDoc.fillColor = opts.holoColor || [0.3, 0.9, 1.0];
    textProp.property("ADBE Text Document").setValue(textDoc);
    
    // 整体透明度
    layer.property("Opacity").setValue(opts.baseOpacity || 75);
    
    // 发光
    addGlowEffect(layer, {
        radius: 15,
        intensity: 1.2,
        threshold: 0.2,
        colorA: [0, 1, 1],
        colorB: [1, 0, 1]
    });
    
    // 扫描线
    addScanlines(layer, {width: 2, opacity: 20});
    
    // 全息闪烁表达式
    layer.property("Opacity").expression = "base = " + (opts.baseOpacity || 75) + ";\nflicker = Math.sin(time * 60) * 3 + Math.sin(time * 23) * 2;\nbase + flicker;";
    
    return "holographic style applied";
}

function style_fire(comp, layer, opts) {
    // 火焰字：湍流置换 + 发光 + 暖色
    addTurbulentDisplace(layer, {
        amount: opts.flameAmount || 25,
        size: opts.flameSize || 40,
        loop: true,
        speed: 120
    });
    addGlowEffect(layer, {
        radius: opts.glowRadius || 15,
        intensity: 2.0,
        threshold: 0.3,
        colorA: [1, 0.3, 0],
        colorB: [1, 0.8, 0]
    });
    // 设置文字颜色为火焰色
    var textProp = layer.property("Text");
    var textDoc = textProp.property("ADBE Text Document").value;
    textDoc.fillColor = [1, 0.5, 0];
    textProp.property("ADBE Text Document").setValue(textDoc);
    
    // 向上漂移表达式
    layer.property("Position").expression = "[value[0], value[1] + Math.sin(time * 3) * 2];";
    
    return "fire style applied";
}

function style_chrome(comp, layer, opts) {
    // 金属铬：渐变 + 高对比 + 投影
    addGradientFill(layer, {
        startPoint: [960, 300],
        startColor: [0.9, 0.9, 0.95, 1],
        endPoint: [960, 700],
        endColor: [0.3, 0.3, 0.4, 1]
    });
    addDropShadow(layer, {
        distance: 5,
        softness: 3,
        opacity: 200
    });
    // 添加轻微发光模拟金属反光
    addGlowEffect(layer, {
        radius: 3,
        intensity: 0.5,
        threshold: 0.8
    });
    return "chrome style applied";
}

function style_outline(comp, layer, opts) {
    // 描边字：无填充 + 粗描边
    addStrokeToText(layer, {
        noFill: true,
        strokeColor: opts.strokeColor || [1, 1, 1],
        strokeWidth: opts.strokeWidth || 4,
        strokeOverFill: false
    });
    if (opts.glow) {
        addGlowEffect(layer, {radius: 8, intensity: 0.8, threshold: 0.4});
    }
    return "outline style applied";
}

function style_softGlow(comp, layer, opts) {
    // 柔光：温和发光 + 轻微模糊
    addGlowEffect(layer, {
        radius: opts.radius || 30,
        intensity: opts.intensity || 1.0,
        threshold: 0.4
    });
    // 复制一层做底光
    var glowLayer = layer.duplicate();
    glowLayer.name = layer.name + "_SoftGlow";
    glowLayer.moveAfter(layer);
    addBlurEffect(glowLayer, {radius: opts.baseBlur || 8});
    glowLayer.property("Opacity").setValue(50);
    glowLayer.blendingMode = BlendingMode.ADD;
    return "softGlow style applied";
}

function style_retro(comp, layer, opts) {
    // 复古VHS：噪波 + 色偏 + 扫描线
    addNoiseEffect(layer, {amount: opts.noiseAmount || 20});
    addHueSaturation(layer, {saturation: opts.saturation || -30});
    addScanlines(layer, {width: 2, opacity: 15});
    // 轻微抖动
    layer.property("Position").expression = "[value[0] + Math.sin(time * 50) * 0.5, value[1]];";
    return "retro style applied";
}

function style_ice(comp, layer, opts) {
    // 冰霜：分形纹理 + 冷色调 + 发光
    var textProp = layer.property("Text");
    var textDoc = textProp.property("ADBE Text Document").value;
    textDoc.fillColor = [0.7, 0.9, 1.0];
    textProp.property("ADBE Text Document").setValue(textDoc);
    
    addFractalNoise(layer, {contrast: 200, brightness: -30, animate: true, speed: 10});
    addGlowEffect(layer, {
        radius: 10,
        intensity: 1.0,
        threshold: 0.5,
        colorA: [0.5, 0.8, 1.0],
        colorB: [0.9, 0.95, 1.0]
    });
    return "ice style applied";
}

function style_electric(comp, layer, opts) {
    // 电弧：强发光 + 闪烁 + 蓝白色
    var textProp = layer.property("Text");
    var textDoc = textProp.property("ADBE Text Document").value;
    textDoc.fillColor = [0.8, 0.9, 1.0];
    textProp.property("ADBE Text Document").setValue(textDoc);
    
    addGlowEffect(layer, {
        radius: 20,
        intensity: 2.5,
        threshold: 0.2,
        colorA: [0.3, 0.5, 1.0],
        colorB: [1.0, 1.0, 1.0]
    });
    // 电弧闪烁
    layer.property("Opacity").expression = "base = 90;\nif (Math.random() > 0.92) base - 40;\nelse base + Math.sin(time * 40) * 5;";
    return "electric style applied";
}

function style_shadow3D(comp, layer, opts) {
    // 3D阴影：多层投影 + 立体感
    layer.threeDLayer = true;
    layer.property("X Rotation").setValue(opts.tiltX || -15);
    layer.property("Y Rotation").setValue(opts.tiltY || 10);
    
    // 多层阴影模拟厚度
    for (var i = 1; i <= (opts.depth || 5); i++) {
        var shadowLayer = layer.duplicate();
        shadowLayer.name = layer.name + "_Shadow" + i;
        shadowLayer.moveAfter(layer);
        var textProp = shadowLayer.property("Text");
        var textDoc = textProp.property("ADBE Text Document").value;
        var darkness = 0.3 - (i * 0.04);
        textDoc.fillColor = [darkness, darkness, darkness + 0.05];
        textProp.property("ADBE Text Document").setValue(textDoc);
        shadowLayer.property("Position").setValue([
            layer.property("Position").value[0] + i * 2,
            layer.property("Position").value[1] + i * 2,
            layer.property("Position").value[2] - i * 5
        ]);
    }
    return "shadow3D style applied (" + (opts.depth || 5) + " layers)";
}

function style_gradient(comp, layer, opts) {
    // 渐变填充
    addGradientFill(layer, {
        startPoint: opts.startPoint || [960, 300],
        startColor: opts.color1 || [1, 0, 0.5, 1],
        endPoint: opts.endPoint || [960, 700],
        endColor: opts.color2 || [0, 0.5, 1, 1]
    });
    if (opts.glow) {
        addGlowEffect(layer, {radius: 10, intensity: 0.8, threshold: 0.5});
    }
    return "gradient style applied";
}

function style_particle(comp, layer, opts) {
    // 粒子消散效果（使用 CC Particle World 如果可用）
    try {
        var pw = layer.Effects.addProperty("CC Particle World");
        pw.name = "ParticleDissolve";
        // 基础设置
        pw.property("CC Particle World-0001").setValue(0); // Longevity
        return "particle style applied (CC Particle World)";
    } catch(e) {
        // 降级方案：使用粗糙化 + 不透明度动画
        addTurbulentDisplace(layer, {amount: 40, size: 20, loop: true, speed: 60});
        layer.property("Opacity").expression = "t = time - " + (opts.startTime || 2) + ";\nif (t > 0) Math.max(0, 100 - t * 50);\nelse 100;";
        return "particle style applied (fallback: turbulent dissolve)";
    }
}

function style_cyberpunk(comp, layer, opts) {
    // 赛博朋克：霓虹 + 故障 + 扫描线
    addStrokeToText(layer, {
        fillColor: [0.05, 0, 0.1],
        strokeColor: opts.neonColor || [1, 0, 0.8],
        strokeWidth: 2
    });
    addGlowEffect(layer, {
        radius: 20,
        intensity: 2.0,
        threshold: 0.2,
        colorA: [1, 0, 0.8],
        colorB: [0, 1, 1]
    });
    addScanlines(layer, {width: 2, opacity: 10});
    // 故障抖动
    layer.property("Position").expression = "if (Math.sin(time * 20) > 0.97) {\n  seedRandom(Math.floor(time*5), true);\n  [value[0] + random(-6,6), value[1]];\n} else value;";
    return "cyberpunk style applied";
}

// ============ 主入口 ============
function stylizedTextFX(args) {
    var compIndex = args.compIndex || 1;
    var layerIndex = args.layerIndex || 1;
    var style = args.style || "neon";
    var options = args.options || {};
    
    // 获取合成
    var comp;
    if (args.compName) {
        comp = findCompByName(args.compName);
    } else {
        comp = app.project.item(compIndex);
    }
    if (!comp || !(comp instanceof CompItem)) {
        return buildErrorResponse("comp_not_found", "合成未找到");
    }
    
    // 获取文字图层
    var layer;
    if (layerIndex >= 1 && layerIndex <= comp.numLayers) {
        layer = comp.layer(layerIndex);
    }
    if (!layer || layer.property("Text") === null) {
        return buildErrorResponse("layer_not_text", "图层不是文字图层");
    }
    
    // 分发风格
    var styleFunc = {
        "neon": style_neon, "glitch": style_glitch, "inkWash": style_inkWash,
        "holographic": style_holographic, "fire": style_fire, "chrome": style_chrome,
        "outline": style_outline, "softGlow": style_softGlow, "retro": style_retro,
        "ice": style_ice, "electric": style_electric, "shadow3D": style_shadow3D,
        "gradient": style_gradient, "particle": style_particle, "cyberpunk": style_cyberpunk
    };
    
    var func = styleFunc[style];
    if (!func) {
        var available = [];
        for (var key in STYLE_REGISTRY) { available.push(key); }
        return buildErrorResponse("unknown_style", "未知风格: " + style + "。可用: " + available.join(", "));
    }
    
    app.beginUndoGroup("StylizedFX_" + style);
    try {
        var result = func(comp, layer, options);
        app.endUndoGroup();
        return buildSuccessResponse({
            style: style,
            styleName: STYLE_REGISTRY[style].name,
            complexity: STYLE_REGISTRY[style].complexity,
            layer: layer.name,
            comp: comp.name,
            result: result
        });
    } catch(e) {
        app.endUndoGroup();
        return buildErrorResponse("style_error", style + " 执行失败: " + e.message);
    }
}

// 列出所有风格
function listStyles() {
    var list = [];
    for (var key in STYLE_REGISTRY) {
        list.push({
            id: key,
            name: STYLE_REGISTRY[key].name,
            complexity: STYLE_REGISTRY[key].complexity,
            effects: STYLE_REGISTRY[key].effects
        });
    }
    return buildSuccessResponse({total: list.length, styles: list});
}

// 入口调度
var _args = (typeof args !== "undefined") ? args : {};
if (_args.action === "list") {
    listStyles();
} else {
    stylizedTextFX(_args);
}
