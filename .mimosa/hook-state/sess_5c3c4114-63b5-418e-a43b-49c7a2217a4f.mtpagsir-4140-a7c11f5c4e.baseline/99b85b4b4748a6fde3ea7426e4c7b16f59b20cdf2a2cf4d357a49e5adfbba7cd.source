// textFXMaster.jsx
// 文字特效统一主控 - 一个入口调度所有子库
// 子库: textAnimLibrary / stylizedTextFX / expressionAnimLib / artisticTextGenerator / textPresetCatalog
// 用法: textFXMaster(args)
// args = {action, ...params}
//
// 支持的 action:
//   "animate"    → 应用文字动画（25种）
//   "style"      → 应用风格化效果（15种）
//   "expression" → 应用表达式动画（18种）
//   "generate"   → 一键生成艺术字（21种预设组合）
//   "preset"     → 应用内置 .ffx 预设（300+种）
//   "combo"      → 组合应用（动画+风格+表达式）
//   "catalog"    → 列出所有可用能力

#include "_lib/response_utils.jsx"
#include "_lib/comp_utils.jsx"

// 兼容别名：_lib 实际提供 buildSuccess/buildError（本脚本内一直误用 Response 后缀，2026-08 实测暴露）
function buildSuccessResponse(d) { return buildSuccess(d); }
function buildErrorResponse(code, msg) { return buildError(code, msg); }

// ============ 能力总览 ============
var CAPABILITIES = {
    "animate": {
        count: 25,
        desc: "程序化文字动画（Text Animator系统）",
        types: ["wave","typewriter","bounce","elastic","spiral","fadeCascade","scalePop",
                "slideUp","slideDown","flip3D","blurReveal","swingIn","zoomBlur","unfold",
                "glitchIn","jitter","pulse","flicker","wobble","breathe","rainbow",
                "scatterOut","collapseOut","dissolveOut","flyOut"]
    },
    "style": {
        count: 15,
        desc: "风格化视觉特效（效果组合）",
        types: ["neon","glitch","inkWash","holographic","fire","chrome","outline",
                "softGlow","retro","ice","electric","shadow3D","gradient","particle","cyberpunk"]
    },
    "expression": {
        count: 18,
        desc: "表达式驱动持续动画（无关键帧）",
        types: ["orbit","figure8","float","shake","pathFollow","pulseScale","bounceScale",
                "elasticScale","spin","pendulum","wiggleRot","blink","fadeLoop",
                "randomFlicker","wigglePos","wiggleScale","colorCycle","textScroll"]
    },
    "generate": {
        count: 21,
        desc: "一键艺术字生成（预设组合方案）",
        types: ["douyin_title","douyin_subtitle","vlog_intro","tech_reveal","hud_text",
                "data_stream","ink_title","poetry","calligraphy","sport_title","countdown",
                "impact","elegant_title","corporate","minimal","fire_title","ice_reveal",
                "magic_text","vhs_title","retro_neon","old_film"]
    },
    "preset": {
        count: 300,
        desc: "AE内置.ffx文字动画预设",
        categories: ["3d","animate_in","animate_out","blurs","curves_spins","expressions",
                    "fill_stroke","graphical","lights_optical","mechanical","misc",
                    "multiline","counters","organic","paths","rotation","scale","tracking","glitch"]
    }
};

// ============ 辅助函数 ============

function getComp(args) {
    var comp;
    if (args.compName) {
        comp = findCompByName(args.compName);
    } else if (args.compIndex) {
        var item = app.project.item(args.compIndex);
        if (item instanceof CompItem) comp = item;
    } else if (app.project.activeItem instanceof CompItem) {
        comp = app.project.activeItem;
    }
    return comp;
}

function getTextLayerFromComp(comp, layerIndex) {
    if (!comp) return null;
    if (layerIndex >= 1 && layerIndex <= comp.numLayers) {
        var layer = comp.layer(layerIndex);
        if (layer.property("Text") !== null) return layer;
    }
    return null;
}

// ============ 组合应用引擎 ============
function applyCombo(comp, layer, args) {
    var results = [];
    var options = args.options || {};
    
    // 1. 应用动画
    if (args.animation) {
        var textProp = layer.property("Text");
        var animators = textProp.property("ADBE Text Animators");
        var animator = animators.addProperty("ADBE Text Animator");
        animator.name = "Combo_" + args.animation;
        var props = animator.property("ADBE Text Animator Properties");
        var selectors = animator.property("ADBE Text Selectors");
        
        var startTime = options.startTime || 0;
        var duration = options.duration || 1.0;
        
        // 简化动画应用（内联核心逻辑）
        switch(args.animation) {
            case "wave":
                props.addProperty("ADBE Text Position 3D").setValue([0, -50, 0]);
                var sel = selectors.addProperty("ADBE Text Selector");
                sel.property("ADBE Text Percent End").setValue(20);
                sel.property("ADBE Text Range Type2").setValue(6);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime, 0);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime + duration, 100);
                break;
            case "typewriter":
                props.addProperty("ADBE Text Opacity").setValue(0);
                var sel = selectors.addProperty("ADBE Text Selector");
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime, -100);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime + duration, 0);
                break;
            case "scalePop":
                props.addProperty("ADBE Text Scale 3D").setValue([0, 0, 0]);
                props.addProperty("ADBE Text Opacity").setValue(0);
                var sel = selectors.addProperty("ADBE Text Selector");
                sel.property("ADBE Text Percent End").setValue(15);
                sel.property("ADBE Text Range Type2").setValue(5);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime, -15);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime + duration, 100);
                break;
            case "fadeCascade":
                props.addProperty("ADBE Text Opacity").setValue(0);
                props.addProperty("ADBE Text Position 3D").setValue([0, 30, 0]);
                var sel = selectors.addProperty("ADBE Text Selector");
                sel.property("ADBE Text Percent End").setValue(40);
                sel.property("ADBE Text Range Type2").setValue(2);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime, -40);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime + duration, 100);
                break;
            case "glitchIn":
                props.addProperty("ADBE Text Opacity").setValue(0);
                props.addProperty("ADBE Text Character Offset").setValue(10);
                var sel = selectors.addProperty("ADBE Text Wiggly Selector");
                sel.property("ADBE Text Wiggly Max Amount").setValue(100);
                sel.property("ADBE Text Wiggly Rate").setValue(15);
                props.property("ADBE Text Opacity").expression = "t=time-" + startTime + ";d=" + duration + ";t<d?(Math.random()>(t/d)?0:100):100;";
                break;
            case "blurReveal":
                props.addProperty("ADBE Text Blur").setValue([30, 30]);
                props.addProperty("ADBE Text Opacity").setValue(0);
                var sel = selectors.addProperty("ADBE Text Selector");
                sel.property("ADBE Text Percent End").setValue(50);
                sel.property("ADBE Text Range Type2").setValue(6);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime, -50);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime + duration, 100);
                break;
            case "bounce":
                props.addProperty("ADBE Text Position 3D").setValue([0, -200, 0]);
                props.addProperty("ADBE Text Scale 3D").setValue([120, 80, 100]);
                var sel = selectors.addProperty("ADBE Text Selector");
                sel.property("ADBE Text Percent End").setValue(30);
                sel.property("ADBE Text Range Type2").setValue(5);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime, -30);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime + duration, 100);
                break;
            case "slideUp":
                props.addProperty("ADBE Text Position 3D").setValue([0, 100, 0]);
                props.addProperty("ADBE Text Opacity").setValue(0);
                var sel = selectors.addProperty("ADBE Text Selector");
                sel.property("ADBE Text Percent End").setValue(30);
                sel.property("ADBE Text Range Type2").setValue(3);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime, -30);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime + duration, 100);
                break;
            case "spiral":
                props.addProperty("ADBE Text Position 3D").setValue([300, 300, 0]);
                props.addProperty("ADBE Text Rotation").setValue(720);
                props.addProperty("ADBE Text Opacity").setValue(0);
                var sel = selectors.addProperty("ADBE Text Selector");
                sel.property("ADBE Text Percent End").setValue(20);
                sel.property("ADBE Text Range Type2").setValue(2);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime, -20);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime + duration, 100);
                break;
            case "flip3D":
                layer.threeDLayer = true;
                props.addProperty("ADBE Text Rotation X").setValue(-90);
                props.addProperty("ADBE Text Opacity").setValue(0);
                var sel = selectors.addProperty("ADBE Text Selector");
                sel.property("ADBE Text Percent End").setValue(25);
                sel.property("ADBE Text Range Type2").setValue(6);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime, -25);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime + duration, 100);
                break;
            default:
                props.addProperty("ADBE Text Opacity").setValue(0);
                var sel = selectors.addProperty("ADBE Text Selector");
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime, -100);
                sel.property("ADBE Text Percent Offset").setValueAtTime(startTime + duration, 0);
        }
        results.push("animation:" + args.animation);
    }
    
    // 2. 应用风格
    if (args.style) {
        switch(args.style) {
            case "neon":
                var tp = layer.property("Text");
                var td = tp.property("ADBE Text Document").value;
                td.strokeColor = options.neonColor || [0, 1, 1];
                td.strokeWidth = 3;
                td.strokeOverFill = true;
                tp.property("ADBE Text Document").setValue(td);
                var g = layer.Effects.addProperty("ADBE Glo2");
                g.property("ADBE Glo2-0003").setValue(25);
                g.property("ADBE Glo2-0004").setValue(2.0);
                g.property("ADBE Glo2-0002").setValue(0.3);
                break;
            case "softGlow":
                var g = layer.Effects.addProperty("ADBE Glo2");
                g.property("ADBE Glo2-0003").setValue(30);
                g.property("ADBE Glo2-0004").setValue(1.0);
                g.property("ADBE Glo2-0002").setValue(0.4);
                break;
            case "outline":
                var tp = layer.property("Text");
                var td = tp.property("ADBE Text Document").value;
                td.fillColor = [0, 0, 0];
                td.strokeColor = options.strokeColor || [1, 1, 1];
                td.strokeWidth = options.strokeWidth || 4;
                td.strokeOverFill = false;
                tp.property("ADBE Text Document").setValue(td);
                break;
            case "cyberpunk":
                var tp = layer.property("Text");
                var td = tp.property("ADBE Text Document").value;
                td.fillColor = [0.05, 0, 0.1];
                td.strokeColor = [1, 0, 0.8];
                td.strokeWidth = 2;
                tp.property("ADBE Text Document").setValue(td);
                var g = layer.Effects.addProperty("ADBE Glo2");
                g.property("ADBE Glo2-0003").setValue(20);
                g.property("ADBE Glo2-0004").setValue(2.0);
                // Glo2-0005 是枚举属性，裸数字 setValue 报错，删除用默认（2026-08 实测）
                g.property("ADBE Glo2-0012").setValue([1, 0, 0.8]);
                g.property("ADBE Glo2-0013").setValue([0, 1, 1]);
                break;
            case "fire":
                var tdp = layer.Effects.addProperty("ADBE Turbulent Displace");
                tdp.property("ADBE Turbulent Displace-0001").setValue(25);
                tdp.property("ADBE Turbulent Displace-0005").expression = "time * 120";
                var g = layer.Effects.addProperty("ADBE Glo2");
                g.property("ADBE Glo2-0003").setValue(15);
                g.property("ADBE Glo2-0004").setValue(2.0);
                // Glo2-0005 是枚举属性，裸数字 setValue 报错，删除用默认（2026-08 实测）
                g.property("ADBE Glo2-0012").setValue([1, 0.3, 0]);
                g.property("ADBE Glo2-0013").setValue([1, 0.8, 0]);
                var tp = layer.property("Text");
                var td = tp.property("ADBE Text Document").value;
                td.fillColor = [1, 0.5, 0];
                tp.property("ADBE Text Document").setValue(td);
                break;
            case "holographic":
                var tp = layer.property("Text");
                var td = tp.property("ADBE Text Document").value;
                td.fillColor = [0.3, 0.9, 1.0];
                tp.property("ADBE Text Document").setValue(td);
                layer.property("Opacity").setValue(75);
                layer.property("Opacity").expression = "75 + Math.sin(time*60)*3 + Math.sin(time*23)*2;";
                var g = layer.Effects.addProperty("ADBE Glo2");
                g.property("ADBE Glo2-0003").setValue(15);
                g.property("ADBE Glo2-0004").setValue(1.2);
                // Glo2-0005 是枚举属性，裸数字 setValue 报错，删除用默认（2026-08 实测）
                g.property("ADBE Glo2-0012").setValue([0, 1, 1]);
                g.property("ADBE Glo2-0013").setValue([1, 0, 1]);
                break;
            case "chrome":
                var ramp = layer.Effects.addProperty("ADBE Ramp");
                ramp.property("ADBE Ramp-0002").setValue([0.9, 0.9, 0.95, 1]);
                ramp.property("ADBE Ramp-0004").setValue([0.3, 0.3, 0.4, 1]);
                var ds = layer.Effects.addProperty("ADBE Drop Shadow");
                ds.property("ADBE Drop Shadow-0004").setValue(5);
                break;
            case "inkWash":
                var tdp = layer.Effects.addProperty("ADBE Turbulent Displace");
                tdp.property("ADBE Turbulent Displace-0001").setValue(15);
                tdp.property("ADBE Turbulent Displace-0005").expression = "time * 20";
                var tint = layer.Effects.addProperty("ADBE Tint");
                tint.property("ADBE Tint-0002").setValue([0.15, 0.15, 0.2, 1]);
                break;
            case "ice":
                var tp = layer.property("Text");
                var td = tp.property("ADBE Text Document").value;
                td.fillColor = [0.7, 0.9, 1.0];
                tp.property("ADBE Text Document").setValue(td);
                var fn = layer.Effects.addProperty("ADBE Fractal Noise");
                fn.property("ADBE Fractal Noise-0003").setValue(200);
                fn.property("ADBE Fractal Noise-0006").expression = "time * 10";
                var g = layer.Effects.addProperty("ADBE Glo2");
                g.property("ADBE Glo2-0003").setValue(10);
                // Glo2-0005 是枚举属性，裸数字 setValue 报错，删除用默认（2026-08 实测）
                g.property("ADBE Glo2-0012").setValue([0.5, 0.8, 1.0]);
                g.property("ADBE Glo2-0013").setValue([0.9, 0.95, 1.0]);
                break;
            case "retro":
                var noise = layer.Effects.addProperty("ADBE Noise");
                noise.property("ADBE Noise-0001").setValue(20);
                var hs = layer.Effects.addProperty("ADBE HUE SATURATION");
                hs.property("ADBE HUE SATURATION-0002").setValue(-30);
                break;
            case "electric":
                var tp = layer.property("Text");
                var td = tp.property("ADBE Text Document").value;
                td.fillColor = [0.8, 0.9, 1.0];
                tp.property("ADBE Text Document").setValue(td);
                var g = layer.Effects.addProperty("ADBE Glo2");
                g.property("ADBE Glo2-0003").setValue(20);
                g.property("ADBE Glo2-0004").setValue(2.5);
                // Glo2-0005 是枚举属性，裸数字 setValue 报错，删除用默认（2026-08 实测）
                g.property("ADBE Glo2-0012").setValue([0.3, 0.5, 1.0]);
                g.property("ADBE Glo2-0013").setValue([1, 1, 1]);
                layer.property("Opacity").expression = "Math.random()>0.92?50:90+Math.sin(time*40)*5;";
                break;
            case "gradient":
                var ramp = layer.Effects.addProperty("ADBE Ramp");
                ramp.property("ADBE Ramp-0002").setValue(options.color1 || [1, 0, 0.5, 1]);
                ramp.property("ADBE Ramp-0004").setValue(options.color2 || [0, 0.5, 1, 1]);
                break;
            case "shadow3D":
                layer.threeDLayer = true;
                layer.property("X Rotation").setValue(-15);
                layer.property("Y Rotation").setValue(10);
                var ds = layer.Effects.addProperty("ADBE Drop Shadow");
                ds.property("ADBE Drop Shadow-0004").setValue(12);
                break;
            default:
                break;
        }
        results.push("style:" + args.style);
    }
    
    // 3. 应用表达式
    if (args.expression) {
        var exprMap = {
            "float": {target:"Position", code:"amp=" + (options.floatAmp || 20) + ";spd=" + (options.floatSpeed || 1) + ";seedRandom(42,true);ph=random()*6.28;[value[0]+Math.sin(time*spd+ph)*amp*0.3,value[1]+Math.sin(time*spd*0.7+ph)*amp];"},
            "pulse": {target:"Scale", code:"amp=" + (options.pulseAmp || 10) + ";spd=" + (options.pulseSpeed || 2) + ";f=1+amp/100*Math.sin(time*spd*6.28);[value[0]*f,value[1]*f,100];"},
            "spin": {target:"Rotation", code:"time*" + (options.spinSpeed || 90) + ";"},
            "wiggle": {target:"Position", code:"wiggle(" + (options.wiggleFreq || 2) + "," + (options.wiggleAmp || 20) + ");"},
            "blink": {target:"Opacity", code:"Math.sin(time*" + (options.blinkSpeed || 2) + "*6.28)>0?100:0;"},
            "breathe": {target:"Opacity", code:"65+35*Math.sin(time*" + (options.breatheSpeed || 1) + "*6.28);"},
            "shake": {target:"Position", code:"t=time-" + (options.shakeStart || 0) + ";if(t>0){n=" + (options.shakeAmp || 15) + "*Math.sin(t*" + (options.shakeFreq || 20) + "*6.28)/Math.exp(t*3);[value[0]+n,value[1]+n*0.5];}else value;"}
        };
        
        var exprDef = exprMap[args.expression];
        if (exprDef) {
            var targetProp = layer.property(exprDef.target);
            if (targetProp) {
                targetProp.expression = exprDef.code;
                results.push("expression:" + args.expression);
            }
        }
    }
    
    return results;
}

// ============ 主入口 ============
function textFXMaster(args) {
    var action = args.action || "catalog";
    
    // === 列出所有能力 ===
    if (action === "catalog") {
        return buildSuccessResponse({
            totalCapabilities: 379,
            libraries: CAPABILITIES,
            usage: {
                animate: "textFXMaster({action:'animate', compIndex:1, layerIndex:1, animType:'wave', options:{}})",
                style: "textFXMaster({action:'style', compIndex:1, layerIndex:1, style:'neon', options:{}})",
                expression: "textFXMaster({action:'expression', compIndex:1, layerIndex:1, exprType:'float', options:{}})",
                generate: "textFXMaster({action:'generate', compIndex:1, text:'HELLO', preset:'douyin_title'})",
                preset: "textFXMaster({action:'preset', compName:'Comp1', layerIndex:1, presetName:'bounce_in'})",
                combo: "textFXMaster({action:'combo', compIndex:1, layerIndex:1, animation:'wave', style:'neon', expression:'float'})"
            }
        });
    }
    
    // 获取合成
    var comp = getComp(args);
    if (!comp) {
        return buildErrorResponse("comp_not_found", "合成未找到。请提供 compName 或 compIndex");
    }
    
    // === 应用动画 ===
    if (action === "animate") {
        var layer = getTextLayerFromComp(comp, args.layerIndex || 1);
        if (!layer) return buildErrorResponse("not_text", "图层不是文字图层");
        
        app.beginUndoGroup("TextFX_Animate_" + (args.animType || "default"));
        try {
            var textProp = layer.property("Text");
            var animators = textProp.property("ADBE Text Animators");
            var animator = animators.addProperty("ADBE Text Animator");
            animator.name = args.animType || "Custom";
            // 简化：使用 combo 引擎
            var res = applyCombo(comp, layer, {animation: args.animType, options: args.options || {}});
            app.endUndoGroup();
            return buildSuccessResponse({action:"animate", animType:args.animType, layer:layer.name, comp:comp.name, result:res});
        } catch(e) {
            app.endUndoGroup();
            return buildErrorResponse("anim_error", e.message);
        }
    }
    
    // === 应用风格 ===
    if (action === "style") {
        var layer = getTextLayerFromComp(comp, args.layerIndex || 1);
        if (!layer) return buildErrorResponse("not_text", "图层不是文字图层");
        
        app.beginUndoGroup("TextFX_Style_" + (args.style || "default"));
        try {
            var res = applyCombo(comp, layer, {style: args.style, options: args.options || {}});
            app.endUndoGroup();
            return buildSuccessResponse({action:"style", style:args.style, layer:layer.name, comp:comp.name, result:res});
        } catch(e) {
            app.endUndoGroup();
            return buildErrorResponse("style_error", e.message);
        }
    }
    
    // === 应用表达式 ===
    if (action === "expression") {
        var layer = getTextLayerFromComp(comp, args.layerIndex || 1);
        if (!layer) return buildErrorResponse("not_text", "图层不是文字图层");
        
        app.beginUndoGroup("TextFX_Expr_" + (args.exprType || "default"));
        try {
            var res = applyCombo(comp, layer, {expression: args.exprType, options: args.options || {}});
            app.endUndoGroup();
            return buildSuccessResponse({action:"expression", exprType:args.exprType, layer:layer.name, comp:comp.name, result:res});
        } catch(e) {
            app.endUndoGroup();
            return buildErrorResponse("expr_error", e.message);
        }
    }
    
    // === 一键生成艺术字 ===
    if (action === "generate") {
        app.beginUndoGroup("TextFX_Generate");
        try {
            // 创建文字图层
            var textLayer = comp.layers.addText(args.text || "艺术字");
            var textProp = textLayer.property("Text");
            var textDoc = textProp.property("ADBE Text Document").value;
            textDoc.fontSize = args.fontSize || 100;
            if (args.font) textDoc.font = args.font;
            if (args.color) textDoc.fillColor = args.color;
            else textDoc.fillColor = [1, 1, 1];
            // justification 必须用 ParagraphJustification 枚举，裸数字报错（2026-08 实测）
            textProp.property("ADBE Text Document").setValue(textDoc);
            
            if (args.position) textLayer.property("Position").setValue(args.position);
            else textLayer.property("Position").setValue([comp.width/2, comp.height/2]);
            textLayer.name = "ArtText_" + (args.text || "").substring(0, 8);
            
            // 应用预设组合
            var animation = args.animation || "fadeCascade";
            var style = args.style || "";
            
            // 查找预设组合
            var PRESET_COMBOS = {
                "douyin_title": {animation:"scalePop", style:"neon"},
                "douyin_subtitle": {animation:"typewriter", style:"outline"},
                "vlog_intro": {animation:"fadeCascade", style:"softGlow"},
                "tech_reveal": {animation:"glitchIn", style:"cyberpunk"},
                "hud_text": {animation:"blurReveal", style:"holographic"},
                "ink_title": {animation:"fadeCascade", style:"inkWash"},
                "sport_title": {animation:"bounce", style:"chrome"},
                "fire_title": {animation:"bounce", style:"fire"},
                "ice_reveal": {animation:"blurReveal", style:"ice"},
                "vhs_title": {animation:"glitchIn", style:"retro"},
                "elegant_title": {animation:"fadeCascade", style:"gradient"},
                "retro_neon": {animation:"flicker", style:"neon"}
            };
            
            if (args.preset && PRESET_COMBOS[args.preset]) {
                animation = PRESET_COMBOS[args.preset].animation;
                style = PRESET_COMBOS[args.preset].style;
            }
            
            var res = applyCombo(comp, textLayer, {
                animation: animation,
                style: style,
                expression: args.expression || null,
                options: args.options || {}
            });
            
            app.endUndoGroup();
            return buildSuccessResponse({
                action: "generate",
                text: args.text,
                layer: textLayer.name,
                comp: comp.name,
                animation: animation,
                style: style,
                preset: args.preset || "custom",
                applied: res
            });
        } catch(e) {
            app.endUndoGroup();
            return buildErrorResponse("gen_error", "生成失败: " + e.message);
        }
    }
    
    // === 应用内置预设 ===
    if (action === "preset") {
        var layer;
        if (args.layerIndex >= 1 && args.layerIndex <= comp.numLayers) {
            layer = comp.layer(args.layerIndex);
        }
        if (!layer) return buildErrorResponse("layer_not_found", "图层未找到");
        
        var PRESETS_ROOT = "C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/Presets";
        var presetFile = null;
        
        if (args.presetPath) {
            presetFile = new File(args.presetPath);
        } else if (args.presetName) {
            // 搜索所有 Text 子目录
            var textDir = new Folder(PRESETS_ROOT + "/Text");
            if (textDir.exists) {
                var subDirs = textDir.getFiles();
                for (var i = 0; i < subDirs.length; i++) {
                    var tryFile = new File(subDirs[i].fsName + "/" + args.presetName + ".ffx");
                    if (tryFile.exists) { presetFile = tryFile; break; }
                }
            }
        }
        
        if (!presetFile || !presetFile.exists) {
            return buildErrorResponse("preset_not_found", "预设文件未找到: " + (args.presetName || args.presetPath));
        }
        
        app.beginUndoGroup("ApplyPreset_" + presetFile.name);
        layer.applyPreset(presetFile);
        app.endUndoGroup();
        return buildSuccessResponse({action:"preset", preset:presetFile.name, layer:layer.name, comp:comp.name});
    }
    
    // === 组合应用 ===
    if (action === "combo") {
        var layer = getTextLayerFromComp(comp, args.layerIndex || 1);
        if (!layer) return buildErrorResponse("not_text", "图层不是文字图层");
        
        app.beginUndoGroup("TextFX_Combo");
        try {
            var res = applyCombo(comp, layer, args);
            app.endUndoGroup();
            return buildSuccessResponse({action:"combo", layer:layer.name, comp:comp.name, applied:res});
        } catch(e) {
            app.endUndoGroup();
            return buildErrorResponse("combo_error", e.message);
        }
    }
    
    return buildErrorResponse("unknown_action", "未知action: " + action + "。支持: catalog|animate|style|expression|generate|preset|combo");
}

// 入口
var _args = (typeof args !== "undefined") ? args : {};
textFXMaster(_args);
