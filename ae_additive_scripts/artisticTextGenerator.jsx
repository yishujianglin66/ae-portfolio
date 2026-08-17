// artisticTextGenerator.jsx
// 艺术字一键生成器 - 创建文字 + 应用动画 + 风格化，一步完成
// 用法: artisticTextGenerator(args)
// args = {compIndex, text, fontSize, font, animation, style, position, color, options}

#include "_lib/response_utils.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/easing_utils.jsx"

// ============ 预设组合方案（动画+风格 快速搭配）============
var PRESET_COMBOS = {
    // 抖音/短视频风格
    "douyin_title": {animation:"scalePop", style:"neon", desc:"抖音标题-霓虹弹出"},
    "douyin_subtitle": {animation:"typewriter", style:"outline", desc:"抖音字幕-打字描边"},
    "vlog_intro": {animation:"fadeCascade", style:"softGlow", desc:"Vlog片头-柔光级联"},
    
    // 科技感
    "tech_reveal": {animation:"glitchIn", style:"cyberpunk", desc:"科技揭示-赛博故障"},
    "hud_text": {animation:"blurReveal", style:"holographic", desc:"HUD文字-全息模糊"},
    "data_stream": {animation:"slideUp", style:"electric", desc:"数据流-电弧上滑"},
    
    // 文艺/古风
    "ink_title": {animation:"fadeCascade", style:"inkWash", desc:"水墨标题-级联淡入"},
    "poetry": {animation:"blurReveal", style:"softGlow", desc:"诗词-柔光模糊"},
    "calligraphy": {animation:"swingIn", style:"inkWash", desc:"书法-摆入水墨"},
    
    // 动感/运动
    "sport_title": {animation:"bounce", style:"chrome", desc:"运动标题-弹跳金属"},
    "countdown": {animation:"zoomBlur", style:"outline", desc:"倒计时-缩放模糊"},
    "impact": {animation:"scalePop", style:"shadow3D", desc:"冲击-3D阴影弹出"},
    
    // 优雅/商务
    "elegant_title": {animation:"fadeCascade", style:"gradient", desc:"优雅标题-渐变级联"},
    "corporate": {animation:"slideUp", style:"chrome", desc:"商务-金属上滑"},
    "minimal": {animation:"blurReveal", style:"outline", desc:"极简-描边模糊"},
    
    // 特效/魔幻
    "fire_title": {animation:"bounce", style:"fire", desc:"火焰标题-弹跳燃烧"},
    "ice_reveal": {animation:"blurReveal", style:"ice", desc:"冰霜揭示-模糊冰晶"},
    "magic_text": {animation:"spiral", style:"softGlow", desc:"魔法文字-螺旋柔光"},
    
    // 复古
    "vhs_title": {animation:"glitchIn", style:"retro", desc:"VHS标题-故障复古"},
    "retro_neon": {animation:"flicker", style:"neon", desc:"复古霓虹-闪烁"},
    "old_film": {animation:"fadeCascade", style:"retro", desc:"老电影-级联复古"}
};

// ============ 字体预设 ============
var FONT_PRESETS = {
    "bold": {font:"Arial-BoldMT", size:120},
    "elegant": {font:"Georgia", size:96},
    "modern": {font:"Helvetica Neue", size:100},
    "chinese_bold": {font:"SourceHanSansSC-Bold", size:110},
    "chinese_light": {font:"SourceHanSansSC-Light", size:100},
    "chinese_kai": {font:"KaiTi", size:120},
    "chinese_song": {font:"SimSun", size:100},
    "impact": {font:"Impact", size:140},
    "script": {font:"Brush Script MT", size:110}
};

// ============ 核心功能 ============

/**
 * 创建文字图层
 */
function createTextLayer(comp, args) {
    var textLayer = comp.layers.addText(args.text || "艺术字");
    
    var textProp = textLayer.property("Text");
    var textDoc = textProp.property("ADBE Text Document").value;
    
    // 字体设置
    var fontPreset = FONT_PRESETS[args.fontPreset] || {};
    textDoc.font = args.font || fontPreset.font || "Arial-BoldMT";
    textDoc.fontSize = args.fontSize || fontPreset.size || 100;
    
    // 颜色
    if (args.color) {
        textDoc.fillColor = args.color;
    } else {
        textDoc.fillColor = [1, 1, 1]; // 默认白色
    }
    
    // 对齐
    if (args.justification) {
        var justMap = {"left":0, "center":1, "right":2};
        textDoc.justification = justMap[args.justification] || 1;
    } else {
        textDoc.justification = 1; // 居中
    }
    
    // 行距
    if (args.leading) {
        textDoc.leading = args.leading;
    }
    
    // 字间距
    if (args.tracking) {
        textDoc.tracking = args.tracking;
    }
    
    textProp.property("ADBE Text Document").setValue(textDoc);
    
    // 位置
    if (args.position) {
        textLayer.property("Position").setValue(args.position);
    } else {
        // 默认居中
        textLayer.property("Position").setValue([comp.width / 2, comp.height / 2]);
    }
    
    // 命名
    textLayer.name = args.layerName || ("ArtText_" + (args.text || "").substring(0, 10));
    
    return textLayer;
}

/**
 * 应用文字动画（调用 textAnimLibrary 的核心逻辑）
 */
function applyAnimation(comp, layer, animType, options) {
    var textProp = layer.property("Text");
    var animators = textProp.property("ADBE Text Animators");
    var animator = animators.addProperty("ADBE Text Animator");
    animator.name = "Anim_" + animType;
    
    var props = animator.property("ADBE Text Animator Properties");
    var selectors = animator.property("ADBE Text Selectors");
    
    var startTime = options.startTime || 0;
    var duration = options.duration || 1.0;
    
    switch(animType) {
        case "wave":
            props.addProperty("ADBE Text Position 3D").setValue([0, -50, 0]);
            var sel = selectors.addProperty("ADBE Text Selector");
            sel.property("ADBE Text Percent Start").setValue(0);
            sel.property("ADBE Text Percent End").setValue(20);
            sel.property("ADBE Text Range Type2").setValue(6); // Smooth
            var off = sel.property("ADBE Text Percent Offset");
            off.setValueAtTime(startTime, 0);
            off.setValueAtTime(startTime + duration, 100);
            break;
            
        case "typewriter":
            props.addProperty("ADBE Text Opacity").setValue(0);
            var sel = selectors.addProperty("ADBE Text Selector");
            sel.property("ADBE Text Percent Start").setValue(0);
            sel.property("ADBE Text Percent End").setValue(100);
            var off = sel.property("ADBE Text Percent Offset");
            off.setValueAtTime(startTime, -100);
            off.setValueAtTime(startTime + duration, 0);
            break;
            
        case "bounce":
            props.addProperty("ADBE Text Position 3D").setValue([0, -200, 0]);
            props.addProperty("ADBE Text Scale 3D").setValue([120, 80, 100]);
            var sel = selectors.addProperty("ADBE Text Selector");
            sel.property("ADBE Text Percent End").setValue(30);
            sel.property("ADBE Text Range Type2").setValue(5); // Round
            var off = sel.property("ADBE Text Percent Offset");
            off.setValueAtTime(startTime, -30);
            off.setValueAtTime(startTime + duration, 100);
            break;
            
        case "scalePop":
            props.addProperty("ADBE Text Scale 3D").setValue([0, 0, 0]);
            props.addProperty("ADBE Text Opacity").setValue(0);
            var sel = selectors.addProperty("ADBE Text Selector");
            sel.property("ADBE Text Percent End").setValue(15);
            sel.property("ADBE Text Range Type2").setValue(5);
            var off = sel.property("ADBE Text Percent Offset");
            off.setValueAtTime(startTime, -15);
            off.setValueAtTime(startTime + duration, 100);
            break;
            
        case "fadeCascade":
            props.addProperty("ADBE Text Opacity").setValue(0);
            props.addProperty("ADBE Text Position 3D").setValue([0, 30, 0]);
            var sel = selectors.addProperty("ADBE Text Selector");
            sel.property("ADBE Text Percent End").setValue(40);
            sel.property("ADBE Text Range Type2").setValue(2); // Ramp Up
            sel.property("ADBE Text Range Units").setValue(3); // Words
            var off = sel.property("ADBE Text Percent Offset");
            off.setValueAtTime(startTime, -40);
            off.setValueAtTime(startTime + duration, 100);
            break;
            
        case "slideUp":
            props.addProperty("ADBE Text Position 3D").setValue([0, 100, 0]);
            props.addProperty("ADBE Text Opacity").setValue(0);
            var sel = selectors.addProperty("ADBE Text Selector");
            sel.property("ADBE Text Percent End").setValue(30);
            sel.property("ADBE Text Range Type2").setValue(3); // Ramp Down
            var off = sel.property("ADBE Text Percent Offset");
            off.setValueAtTime(startTime, -30);
            off.setValueAtTime(startTime + duration, 100);
            break;
            
        case "blurReveal":
            props.addProperty("ADBE Text Blur").setValue([30, 30]);
            props.addProperty("ADBE Text Opacity").setValue(0);
            var sel = selectors.addProperty("ADBE Text Selector");
            sel.property("ADBE Text Percent End").setValue(50);
            sel.property("ADBE Text Range Type2").setValue(6); // Smooth
            var off = sel.property("ADBE Text Percent Offset");
            off.setValueAtTime(startTime, -50);
            off.setValueAtTime(startTime + duration, 100);
            break;
            
        case "glitchIn":
            props.addProperty("ADBE Text Opacity").setValue(0);
            props.addProperty("ADBE Text Character Offset").setValue(10);
            var sel = selectors.addProperty("ADBE Text Wiggly Selector");
            sel.property("ADBE Text Wiggly Max Amount").setValue(100);
            sel.property("ADBE Text Wiggly Rate").setValue(15);
            // 表达式控制稳定
            props.property("ADBE Text Opacity").expression = "t = time - " + startTime + ";\ndur = " + duration + ";\nif (t < dur) { Math.random() > (t/dur) ? 0 : 100; } else { 100; }";
            break;
            
        case "spiral":
            props.addProperty("ADBE Text Position 3D").setValue([300, 300, 0]);
            props.addProperty("ADBE Text Rotation").setValue(720);
            props.addProperty("ADBE Text Opacity").setValue(0);
            var sel = selectors.addProperty("ADBE Text Selector");
            sel.property("ADBE Text Percent End").setValue(20);
            sel.property("ADBE Text Range Type2").setValue(2);
            var off = sel.property("ADBE Text Percent Offset");
            off.setValueAtTime(startTime, -20);
            off.setValueAtTime(startTime + duration, 100);
            break;
            
        case "zoomBlur":
            props.addProperty("ADBE Text Scale 3D").setValue([300, 300, 100]);
            props.addProperty("ADBE Text Blur").setValue([20, 20]);
            props.addProperty("ADBE Text Opacity").setValue(0);
            var sel = selectors.addProperty("ADBE Text Selector");
            sel.property("ADBE Text Percent End").setValue(30);
            sel.property("ADBE Text Range Type2").setValue(6);
            var off = sel.property("ADBE Text Percent Offset");
            off.setValueAtTime(startTime, -30);
            off.setValueAtTime(startTime + duration, 100);
            break;
            
        case "swingIn":
            props.addProperty("ADBE Text Rotation").setValue(-60);
            props.addProperty("ADBE Text Opacity").setValue(0);
            props.addProperty("ADBE Text Anchor Point 3D").setValue([0, -50, 0]);
            var sel = selectors.addProperty("ADBE Text Selector");
            sel.property("ADBE Text Percent End").setValue(20);
            sel.property("ADBE Text Range Type2").setValue(2);
            var off = sel.property("ADBE Text Percent Offset");
            off.setValueAtTime(startTime, -20);
            off.setValueAtTime(startTime + duration, 100);
            break;
            
        case "flip3D":
            layer.threeDLayer = true;
            props.addProperty("ADBE Text Rotation X").setValue(-90);
            props.addProperty("ADBE Text Opacity").setValue(0);
            var sel = selectors.addProperty("ADBE Text Selector");
            sel.property("ADBE Text Percent End").setValue(25);
            sel.property("ADBE Text Range Type2").setValue(6);
            var off = sel.property("ADBE Text Percent Offset");
            off.setValueAtTime(startTime, -25);
            off.setValueAtTime(startTime + duration, 100);
            break;
            
        case "flicker":
            props.addProperty("ADBE Text Opacity").setValue(0);
            var sel = selectors.addProperty("ADBE Text Wiggly Selector");
            sel.property("ADBE Text Wiggly Max Amount").setValue(100);
            sel.property("ADBE Text Wiggly Rate").setValue(8);
            break;
            
        default:
            // 默认淡入
            props.addProperty("ADBE Text Opacity").setValue(0);
            var sel = selectors.addProperty("ADBE Text Selector");
            var off = sel.property("ADBE Text Percent Offset");
            off.setValueAtTime(startTime, -100);
            off.setValueAtTime(startTime + duration, 0);
    }
    
    return animType;
}

/**
 * 应用风格化效果（简化版，直接操作）
 */
function applyStyle(layer, styleType, options) {
    switch(styleType) {
        case "neon":
            var textProp = layer.property("Text");
            var textDoc = textProp.property("ADBE Text Document").value;
            textDoc.strokeColor = options.neonColor || [0, 1, 1];
            textDoc.strokeWidth = 3;
            textDoc.strokeOverFill = true;
            textProp.property("ADBE Text Document").setValue(textDoc);
            var glow = layer.Effects.addProperty("ADBE Glo2");
            glow.property("ADBE Glo2-0003").setValue(25);
            glow.property("ADBE Glo2-0004").setValue(2.0);
            glow.property("ADBE Glo2-0002").setValue(0.3);
            break;
            
        case "glow":
        case "softGlow":
            var glow = layer.Effects.addProperty("ADBE Glo2");
            glow.property("ADBE Glo2-0003").setValue(options.radius || 30);
            glow.property("ADBE Glo2-0004").setValue(options.intensity || 1.0);
            glow.property("ADBE Glo2-0002").setValue(0.4);
            break;
            
        case "outline":
            var textProp = layer.property("Text");
            var textDoc = textProp.property("ADBE Text Document").value;
            textDoc.fillColor = [0, 0, 0];
            textDoc.strokeColor = options.strokeColor || [1, 1, 1];
            textDoc.strokeWidth = options.strokeWidth || 4;
            textDoc.strokeOverFill = false;
            textProp.property("ADBE Text Document").setValue(textDoc);
            break;
            
        case "chrome":
            var ramp = layer.Effects.addProperty("ADBE Ramp");
            ramp.property("ADBE Ramp-0001").setValue([960, 300]);
            ramp.property("ADBE Ramp-0002").setValue([0.9, 0.9, 0.95, 1]);
            ramp.property("ADBE Ramp-0003").setValue([960, 700]);
            ramp.property("ADBE Ramp-0004").setValue([0.3, 0.3, 0.4, 1]);
            var ds = layer.Effects.addProperty("ADBE Drop Shadow");
            ds.property("ADBE Drop Shadow-0004").setValue(5);
            ds.property("ADBE Drop Shadow-0005").setValue(3);
            break;
            
        case "fire":
            var td = layer.Effects.addProperty("ADBE Turbulent Displace");
            td.property("ADBE Turbulent Displace-0001").setValue(25);
            td.property("ADBE Turbulent Displace-0002").setValue(40);
            td.property("ADBE Turbulent Displace-0005").expression = "time * 120";
            var glow = layer.Effects.addProperty("ADBE Glo2");
            glow.property("ADBE Glo2-0003").setValue(15);
            glow.property("ADBE Glo2-0004").setValue(2.0);
            glow.property("ADBE Glo2-0005").setValue(3);
            glow.property("ADBE Glo2-0006").setValue([1, 0.3, 0, 1]);
            glow.property("ADBE Glo2-0007").setValue([1, 0.8, 0, 1]);
            var textProp = layer.property("Text");
            var textDoc = textProp.property("ADBE Text Document").value;
            textDoc.fillColor = [1, 0.5, 0];
            textProp.property("ADBE Text Document").setValue(textDoc);
            break;
            
        case "inkWash":
            var td = layer.Effects.addProperty("ADBE Turbulent Displace");
            td.property("ADBE Turbulent Displace-0001").setValue(15);
            td.property("ADBE Turbulent Displace-0002").setValue(30);
            td.property("ADBE Turbulent Displace-0005").expression = "time * 20";
            var tint = layer.Effects.addProperty("ADBE Tint");
            tint.property("ADBE Tint-0002").setValue([0.15, 0.15, 0.2, 1]);
            break;
            
        case "holographic":
            var textProp = layer.property("Text");
            var textDoc = textProp.property("ADBE Text Document").value;
            textDoc.fillColor = [0.3, 0.9, 1.0];
            textProp.property("ADBE Text Document").setValue(textDoc);
            layer.property("Opacity").setValue(75);
            layer.property("Opacity").expression = "75 + Math.sin(time * 60) * 3 + Math.sin(time * 23) * 2;";
            var glow = layer.Effects.addProperty("ADBE Glo2");
            glow.property("ADBE Glo2-0003").setValue(15);
            glow.property("ADBE Glo2-0004").setValue(1.2);
            glow.property("ADBE Glo2-0005").setValue(3);
            glow.property("ADBE Glo2-0006").setValue([0, 1, 1, 1]);
            glow.property("ADBE Glo2-0007").setValue([1, 0, 1, 1]);
            break;
            
        case "cyberpunk":
            var textProp = layer.property("Text");
            var textDoc = textProp.property("ADBE Text Document").value;
            textDoc.fillColor = [0.05, 0, 0.1];
            textDoc.strokeColor = [1, 0, 0.8];
            textDoc.strokeWidth = 2;
            textProp.property("ADBE Text Document").setValue(textDoc);
            var glow = layer.Effects.addProperty("ADBE Glo2");
            glow.property("ADBE Glo2-0003").setValue(20);
            glow.property("ADBE Glo2-0004").setValue(2.0);
            glow.property("ADBE Glo2-0005").setValue(3);
            glow.property("ADBE Glo2-0006").setValue([1, 0, 0.8, 1]);
            glow.property("ADBE Glo2-0007").setValue([0, 1, 1, 1]);
            layer.property("Position").expression = "if (Math.sin(time * 20) > 0.97) { seedRandom(Math.floor(time*5), true); [value[0] + random(-6,6), value[1]]; } else value;";
            break;
            
        case "electric":
            var textProp = layer.property("Text");
            var textDoc = textProp.property("ADBE Text Document").value;
            textDoc.fillColor = [0.8, 0.9, 1.0];
            textProp.property("ADBE Text Document").setValue(textDoc);
            var glow = layer.Effects.addProperty("ADBE Glo2");
            glow.property("ADBE Glo2-0003").setValue(20);
            glow.property("ADBE Glo2-0004").setValue(2.5);
            glow.property("ADBE Glo2-0005").setValue(3);
            glow.property("ADBE Glo2-0006").setValue([0.3, 0.5, 1.0, 1]);
            glow.property("ADBE Glo2-0007").setValue([1, 1, 1, 1]);
            layer.property("Opacity").expression = "base = 90; if (Math.random() > 0.92) base - 40; else base + Math.sin(time * 40) * 5;";
            break;
            
        case "ice":
            var textProp = layer.property("Text");
            var textDoc = textProp.property("ADBE Text Document").value;
            textDoc.fillColor = [0.7, 0.9, 1.0];
            textProp.property("ADBE Text Document").setValue(textDoc);
            var fn = layer.Effects.addProperty("ADBE Fractal Noise");
            fn.property("ADBE Fractal Noise-0003").setValue(200);
            fn.property("ADBE Fractal Noise-0004").setValue(-30);
            fn.property("ADBE Fractal Noise-0006").expression = "time * 10";
            var glow = layer.Effects.addProperty("ADBE Glo2");
            glow.property("ADBE Glo2-0003").setValue(10);
            glow.property("ADBE Glo2-0004").setValue(1.0);
            glow.property("ADBE Glo2-0005").setValue(3);
            glow.property("ADBE Glo2-0006").setValue([0.5, 0.8, 1.0, 1]);
            glow.property("ADBE Glo2-0007").setValue([0.9, 0.95, 1.0, 1]);
            break;
            
        case "retro":
            var noise = layer.Effects.addProperty("ADBE Noise");
            noise.property("ADBE Noise-0001").setValue(20);
            var hs = layer.Effects.addProperty("ADBE HUE SATURATION");
            hs.property("ADBE HUE SATURATION-0002").setValue(-30);
            layer.property("Position").expression = "[value[0] + Math.sin(time * 50) * 0.5, value[1]];";
            break;
            
        case "gradient":
            var ramp = layer.Effects.addProperty("ADBE Ramp");
            ramp.property("ADBE Ramp-0001").setValue([960, 300]);
            ramp.property("ADBE Ramp-0002").setValue(options.color1 || [1, 0, 0.5, 1]);
            ramp.property("ADBE Ramp-0003").setValue([960, 700]);
            ramp.property("ADBE Ramp-0004").setValue(options.color2 || [0, 0.5, 1, 1]);
            break;
            
        case "shadow3D":
            layer.threeDLayer = true;
            layer.property("X Rotation").setValue(-15);
            layer.property("Y Rotation").setValue(10);
            var ds = layer.Effects.addProperty("ADBE Drop Shadow");
            ds.property("ADBE Drop Shadow-0004").setValue(12);
            ds.property("ADBE Drop Shadow-0005").setValue(5);
            break;
            
        default:
            // 无额外风格
            break;
    }
    return styleType;
}

// ============ 主入口 ============
function artisticTextGenerator(args) {
    var compIndex = args.compIndex || 1;
    
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
    
    // 检查是否使用预设组合
    var animation = args.animation || "fadeCascade";
    var style = args.style || "";
    var options = args.options || {};
    
    if (args.preset && PRESET_COMBOS[args.preset]) {
        var combo = PRESET_COMBOS[args.preset];
        animation = combo.animation;
        style = combo.style;
    }
    
    app.beginUndoGroup("ArtisticText_" + (args.preset || animation + "_" + style));
    try {
        // 1. 创建文字图层
        var layer = createTextLayer(comp, args);
        
        // 2. 应用动画
        var animResult = applyAnimation(comp, layer, animation, options);
        
        // 3. 应用风格
        var styleResult = style ? applyStyle(layer, style, options) : "none";
        
        app.endUndoGroup();
        
        return buildSuccessResponse({
            text: args.text,
            layer: layer.name,
            comp: comp.name,
            animation: animResult,
            style: styleResult,
            preset: args.preset || "custom",
            presetDesc: args.preset ? PRESET_COMBOS[args.preset].desc : "自定义组合"
        });
    } catch(e) {
        app.endUndoGroup();
        return buildErrorResponse("gen_error", "艺术字生成失败: " + e.message);
    }
}

// 列出预设组合
function listPresets() {
    var list = [];
    for (var key in PRESET_COMBOS) {
        list.push({
            id: key,
            desc: PRESET_COMBOS[key].desc,
            animation: PRESET_COMBOS[key].animation,
            style: PRESET_COMBOS[key].style
        });
    }
    return buildSuccessResponse({total: list.length, presets: list});
}

// 入口调度
var _args = (typeof args !== "undefined") ? args : {};
if (_args.action === "list") {
    listPresets();
} else {
    artisticTextGenerator(_args);
}
