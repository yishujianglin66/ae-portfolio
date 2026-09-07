// ============================================================
// apply_text_preset.jsx - 文字特效预设应用器
// 从 text_presets_database.json 加载预设并应用到AE文字层
//
// 使用方式:
//   1. 写入命令文件: .ae-mcp-bridge/ae_command.json
//      {"command":"runScript","args":{"code":"<此脚本内容>"}}
//   2. 或通过 Bridge Loader 直接执行
//
// 预设数据结构: data/text_presets_database.json
// ============================================================

// ============================================================
// JSON 解析器 (ExtendScript ES3 兼容)
// ============================================================
if (typeof JSON === "undefined" || !JSON.parse) {
    var JSON = {
        parse: function(str) {
            return eval("(" + str + ")");
        },
        stringify: function(obj) {
            if (obj === null || obj === undefined) return "null";
            if (typeof obj === "number" || typeof obj === "boolean") return String(obj);
            if (typeof obj === "string") return '"' + obj.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n") + '"';
            if (obj instanceof Array) {
                var r = [];
                for (var i = 0; i < obj.length; i++) r.push(JSON.stringify(obj[i]));
                return "[" + r.join(",") + "]";
            }
            var r = [];
            for (var k in obj) {
                if (obj.hasOwnProperty(k)) r.push('"' + k + '":' + JSON.stringify(obj[k]));
            }
            return "{" + r.join(",") + "}";
        }
    };
}

// ============================================================
// 预设数据库 (内嵌精简版 - 由 build_text_preset_matrix.py 生成)
// ============================================================
var PRESET_DB = {
    // ---- 特效组合 ----
    effects: {
        "effect_cyber_glitch": {
            effects: [
                {matchName:"ADBE Glo2", params:{threshold:0.2, radius:20, intensity:2.0, colorA:[0,0.8,1,1], colorB:[0,0.3,0.5,1]}},
                {matchName:"ADBE Turbulent Displace", params:{amount:25, size:30}}
            ],
            animators: [{type:"wiggly", name:"GlitchJitter", prop:"ADBE Text Position 3D", value:[8,5,0], size:30, rate:12}],
            expressions: {position:"if(Math.sin(time*30)>0.9){seedRandom(Math.floor(time*10),true);[value[0]+random(-8,8),value[1]+random(-3,3)];}else value;"}
        },
        "effect_ink_wash": {
            effects: [
                {matchName:"ADBE Turbulent Displace", params:{amount:8, size:50}},
                {matchName:"ADBE Tint", params:{black:[0.1,0.08,0.05,1], white:[0.3,0.25,0.2,1]}}
            ],
            animators: [{type:"range", name:"BlurReveal", prop:"ADBE Text Blur", value:40, start:0, end:100, offsetFrom:-100, offsetTo:0, duration:2.0, shape:2}],
            expressions: {}
        },
        "effect_neon_pulse": {
            effects: [
                {matchName:"ADBE Glo2", params:{threshold:0.15, radius:35, intensity:3.0, colorA:[1,0.2,0.6,1], colorB:[0.3,0.5,1,1]}}
            ],
            animators: [{type:"wiggly", name:"ScalePulse", prop:"ADBE Text Scale 3D", value:[5,5,0], size:40, rate:3}],
            expressions: {opacity:"base=90;flicker=Math.sin(time*60)*5+Math.sin(time*23)*3;if(Math.random()>0.95)base-30;else base+flicker;"}
        },
        "effect_hologram_hud": {
            effects: [
                {matchName:"ADBE Glo2", params:{threshold:0.3, radius:15, intensity:1.5, colorA:[0.3,0.7,1,1], colorB:[0.1,0.3,0.8,1]}},
                {matchName:"ADBE Venetian Blinds", params:{completion:85, width:8, feather:50}}
            ],
            animators: [{type:"range", name:"FloatUp", prop:"ADBE Text Position 3D", value:[0,-30,0], animateOffset:true, animStart:0, animEnd:1.5, shape:5}],
            expressions: {position:"[value[0],value[1]+Math.sin(time*2)*5];"}
        },
        "effect_fire_ice": {
            effects: [
                {matchName:"ADBE Turbulent Displace", params:{amount:40, size:25}},
                {matchName:"ADBE Fractal Noise", params:{noise_type:1, contrast:80, brightness:-30}},
                {matchName:"ADBE Tint", params:{black:[0.2,0.4,0.6,1], white:[0.7,0.9,1,1]}},
                {matchName:"ADBE Glo2", params:{threshold:0.3, radius:25, intensity:1.5, colorA:[0.5,0.8,1,1], colorB:[0.2,0.4,0.8,1]}}
            ],
            animators: [],
            expressions: {position:"freq=15;amp=6;[value[0]+Math.sin(time*freq*0.7)*amp*0.3,value[1]+Math.sin(time*freq)*amp*0.5];"}
        },
        "effect_golden_logo": {
            effects: [
                {matchName:"ADBE Glo2", params:{threshold:0.1, radius:40, intensity:2.5, colorA:[1,0.85,0.3,1], colorB:[1,0.6,0.1,1]}},
                {matchName:"ADBE Ramp", params:{startColor:[1,0.85,0.3,1], endColor:[0.05,0.05,0.08,1], startPoint:[960,540], endPoint:[960,1080]}}
            ],
            animators: [],
            expressions: {scale:"base=value;breath=1+Math.sin(time*2)*0.02;[base[0]*breath,base[1]*breath];"}
        },
        "effect_rgb_split": {
            effects: [
                {matchName:"ADBE Turbulent Displace", params:{amount:11, size:20}},
                {matchName:"ADBE Tint", params:{black:[1,0,0,1], white:[0,1,1,1]}},
                {matchName:"ADBE Glo2", params:{threshold:0.1, radius:8, intensity:1.0, colorA:[1,0,0,1], colorB:[0,0,1,1]}}
            ],
            animators: [{type:"wiggly", name:"RGBJitter", prop:"ADBE Text Position 3D", value:[5,2,0], size:20, rate:8}],
            expressions: {position:"seedRandom(Math.floor(time*8),true);[value[0]+random(-4,4),value[1]+random(-2,2)];"}
        },
        "effect_soft_glow": {
            effects: [
                {matchName:"ADBE Glo2", params:{threshold:0.5, radius:50, intensity:1.0, colorA:[1,0.9,0.95,1], colorB:[0.9,0.7,0.8,1]}}
            ],
            animators: [],
            expressions: {opacity:"95+Math.sin(time*1.5)*5;"}
        },
        "effect_metallic_bevel": {
            effects: [
                {matchName:"ADBE Bevel Emboss", params:{edgeThickness:5, softness:3, direction:1, angle:135, altitude:30, highlightOpacity:80, shadowOpacity:60}},
                {matchName:"ADBE Glo2", params:{threshold:0.5, radius:8, intensity:0.6, colorA:[1,0.95,0.8,1], colorB:[0.8,0.7,0.5,1]}}
            ],
            animators: [], expressions: {}
        },
        "effect_retro_vhs": {
            effects: [
                {matchName:"ADBE Fractal Noise", params:{noise_type:1, contrast:2, brightness:-60}},
                {matchName:"ADBE Tint", params:{black:[0.1,0.05,0.15,1], white:[0.8,0.7,0.9,1]}},
                {matchName:"ADBE Venetian Blinds", params:{completion:92, width:6, feather:60}}
            ],
            animators: [{type:"wiggly", name:"VHSShake", prop:"ADBE Text Position 3D", value:[2,1,0], size:10, rate:5}],
            expressions: {position:"value+[Math.sin(time*3)*2,0];"}
        },
        "effect_electric_shock": {
            effects: [
                {matchName:"ADBE Glo2", params:{threshold:0.05, radius:18, intensity:2.5, colorA:[0.5,0.7,1,1], colorB:[1,1,1,1]}},
                {matchName:"ADBE Turbulent Displace", params:{amount:3, size:10}}
            ],
            animators: [{type:"wiggly", name:"ElectricJitter", prop:"ADBE Text Position 3D", value:[4,3,0], size:60, rate:20}],
            expressions: {opacity:"if(random()>0.92)60;else 100;"}
        },
        "effect_minimal_line": {
            effects: [
                {matchName:"ADBE Drop Shadow", params:{distance:3, angle:135, softness:5, opacity:30}}
            ],
            animators: [{type:"range", name:"LineReveal", prop:"ADBE Text Stroke Width", value:1, start:0, end:100, offsetFrom:-100, offsetTo:0, duration:1.5, shape:2}],
            expressions: {}
        },
        "effect_clean_shadow": {
            effects: [{matchName:"ADBE Drop Shadow", params:{distance:8, angle:135, softness:3, opacity:50}}],
            animators: [], expressions: {}
        }
    },

    // ---- 入场动画 ----
    animations: {
        "anim_bounce_in": {
            keyframes: {scale:[[0,0,0],[0.25,110,110],[0.4,100,100]], opacity:[[0,0],[0.15,100]]},
            duration: 0.5, animator: null, expression: null
        },
        "anim_glitch_pop": {
            keyframes: {scale:[[0,0,0],[0.2,115,115],[0.35,95,95],[0.45,100,100]], opacity:[[0,0],[0.1,100]]},
            duration: 0.5,
            animator: {type:"wiggly", prop:"ADBE Text Position 3D", value:[6,4,0], size:20, rate:10, duration:0.5},
            expression: "if(time<inPoint+0.5){seedRandom(Math.floor(time*12),true);[value[0]+random(-5,5),value[1]+random(-3,3)];}else value;"
        },
        "anim_kinetic_smash": {
            keyframes: {scale:[[0,0,0],[0.15,130,130],[0.25,90,90],[0.35,105,105],[0.45,100,100]], opacity:[[0,0],[0.08,100]]},
            duration: 0.5, animator: null,
            expression: "if(time<inPoint+0.5){seedRandom(Math.floor(time*15),true);[value[0]+random(-4,4),value[1]+random(-2,2)];}else value;"
        },
        "anim_tracking_fade": {
            keyframes: {opacity:[[0,0],[1.5,100]]},
            duration: 1.5,
            animator: {type:"range", prop:"ADBE Text Tracking Amount", value:-200, start:0, end:100, offsetFrom:-100, offsetTo:0, duration:1.5, shape:2},
            expression: null
        },
        "anim_typewriter": {
            keyframes: {},
            duration: 1.5,
            animator: {type:"range", prop:"ADBE Text Opacity", value:0, start:0, end:100, offsetFrom:-100, offsetTo:0, duration:1.5, shape:1},
            expression: null
        },
        "anim_scale_zoom": {
            keyframes: {scale:[[0,50,50],[0.5,100,100]], opacity:[[0,0],[0.3,100]]},
            duration: 0.5, animator: null, expression: null
        },
        "anim_slide_from_bottom": {
            keyframes: {position_y:[[0,300],[0.5,0]], opacity:[[0,0],[0.15,100]]},
            duration: 0.5, animator: null, expression: null
        },
        "anim_blur_reveal": {
            keyframes: {opacity:[[0,0],[0.3,100]]},
            duration: 1.5,
            animator: {type:"range", prop:"ADBE Text Blur", value:40, start:0, end:100, offsetFrom:-100, offsetTo:0, duration:1.5, shape:2},
            expression: null
        },
        "anim_rotate_spin": {
            keyframes: {rotation:[[0,-180],[0.6,0]], scale:[[0,0,0],[0.6,100,100]], opacity:[[0,0],[0.2,100]]},
            duration: 0.6, animator: null, expression: null
        }
    }
};

// ============================================================
// 核心工具函数
// ============================================================
function getActiveComp() {
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) return null;
    return comp;
}

function getSelectedTextLayer(comp) {
    if (!comp) return null;
    for (var i = 1; i <= comp.selectedLayers.length; i++) {
        var layer = comp.selectedLayers[i - 1];
        if (layer instanceof TextLayer) return layer;
    }
    return null;
}

// ============================================================
// 特效应用引擎
// ============================================================
function applyEffect(layer, effectDef) {
    var effects = layer.property("Effects");
    for (var i = 0; i < effectDef.effects.length; i++) {
        var eDef = effectDef.effects[i];
        try {
            var eff = effects.addProperty(eDef.matchName);
            var p = eDef.params;
            // Glow
            if (eDef.matchName === "ADBE Glo2") {
                if (p.threshold !== undefined) eff.property("ADBE Glo2-0002").setValue(p.threshold);
                if (p.radius !== undefined) eff.property("ADBE Glo2-0003").setValue(p.radius);
                if (p.intensity !== undefined) eff.property("ADBE Glo2-0004").setValue(p.intensity);
                if (p.colorA) {
                    try {
                        eff.property("ADBE Glo2-0005").setValue(3);
                        eff.property("ADBE Glo2-0006").setValue(p.colorA);
                        if (p.colorB) eff.property("ADBE Glo2-0007").setValue(p.colorB);
                    } catch(ce) {}
                }
            }
            // Turbulent Displace
            else if (eDef.matchName === "ADBE Turbulent Displace") {
                if (p.amount !== undefined) {
                    var safeAmt = Math.max(1, Math.min(11, p.amount));
                    eff.property("ADBE Turbulent Displace-0001").setValue(safeAmt);
                }
                if (p.size !== undefined) eff.property("ADBE Turbulent Displace-0002").setValue(p.size);
            }
            // Fractal Noise
            else if (eDef.matchName === "ADBE Fractal Noise") {
                if (p.noise_type !== undefined) eff.property("ADBE Fractal Noise-0001").setValue(p.noise_type);
                try {
                    if (p.contrast !== undefined) eff.property("Contrast").setValue(Math.max(1, Math.min(100, p.contrast)));
                    if (p.brightness !== undefined) eff.property("Brightness").setValue(Math.max(-100, Math.min(100, p.brightness)));
                } catch(fe) {}
            }
            // Tint
            else if (eDef.matchName === "ADBE Tint") {
                if (p.black) eff.property("ADBE Tint-0001").setValue(p.black);
                if (p.white) eff.property("ADBE Tint-0002").setValue(p.white);
            }
            // Venetian Blinds
            else if (eDef.matchName === "ADBE Venetian Blinds") {
                if (p.completion !== undefined) eff.property("ADBE Venetian Blinds-0001").setValue(p.completion);
                if (p.width !== undefined) eff.property("ADBE Venetian Blinds-0002").setValue(p.width);
                if (p.feather !== undefined) eff.property("ADBE Venetian Blinds-0003").setValue(p.feather);
            }
            // Bevel Emboss
            else if (eDef.matchName === "ADBE Bevel Emboss") {
                if (p.edgeThickness !== undefined) eff.property("ADBE Bevel Emboss-0001").setValue(p.edgeThickness);
                if (p.softness !== undefined) eff.property("ADBE Bevel Emboss-0002").setValue(p.softness);
                if (p.angle !== undefined) eff.property("ADBE Bevel Emboss-0004").setValue(p.angle);
                if (p.altitude !== undefined) eff.property("ADBE Bevel Emboss-0005").setValue(p.altitude);
            }
            // Drop Shadow
            else if (eDef.matchName === "ADBE Drop Shadow") {
                if (p.distance !== undefined) eff.property("ADBE Drop Shadow-0001").setValue(p.distance);
                if (p.angle !== undefined) eff.property("ADBE Drop Shadow-0002").setValue(p.angle);
                if (p.softness !== undefined) eff.property("ADBE Drop Shadow-0004").setValue(p.softness);
                if (p.opacity !== undefined) eff.property("ADBE Drop Shadow-0005").setValue(p.opacity);
            }
            // Ramp
            else if (eDef.matchName === "ADBE Ramp") {
                try {
                    if (p.startColor) eff.property("Start Color").setValue(p.startColor);
                    if (p.endColor) eff.property("End Color").setValue(p.endColor);
                    if (p.startPoint) eff.property("Start Point").setValue(p.startPoint);
                    if (p.endPoint) eff.property("End Point").setValue(p.endPoint);
                } catch(re) {}
            }
        } catch(e) {
            // 效果添加失败，跳过
        }
    }
}

// ============================================================
// Text Animator 应用引擎
// ============================================================
function applyAnimator(layer, animDefs) {
    if (!animDefs || animDefs.length === 0) return;
    var textProp = layer.property("Text");
    var animators = textProp.property("ADBE Text Animators");

    for (var i = 0; i < animDefs.length; i++) {
        var aDef = animDefs[i];
        try {
            var animator = animators.addProperty("ADBE Text Animator");
            animator.name = aDef.name || ("PresetAnim_" + i);

            var selectors = animator.property("ADBE Text Selectors");

            if (aDef.type === "wiggly") {
                var wiggly = selectors.addProperty("ADBE Text Wiggly Selector");
                wiggly.name = "Wiggly";
                if (aDef.size !== undefined) wiggly.property("ADBE Text Wiggly Selector-0001").setValue(aDef.size);
                if (aDef.rate !== undefined) wiggly.property("ADBE Text Wiggly Selector-0002").setValue(aDef.rate);
            } else if (aDef.type === "range") {
                var rangeSel = selectors.addProperty("ADBE Text Selector");
                rangeSel.name = "Range";
                if (aDef.start !== undefined) rangeSel.property("ADBE Text Percent Start").setValue(aDef.start);
                if (aDef.end !== undefined) rangeSel.property("ADBE Text Percent End").setValue(aDef.end);
                if (aDef.shape !== undefined) {
                    try { rangeSel.property("ADBE Text Range Type2").setValue(aDef.shape); } catch(se) {}
                }
                if (aDef.offsetFrom !== undefined && aDef.offsetTo !== undefined && aDef.duration) {
                    var t0 = layer.inPoint;
                    var t1 = t0 + aDef.duration;
                    rangeSel.property("ADBE Text Percent Offset").setValueAtTime(t0, aDef.offsetFrom);
                    rangeSel.property("ADBE Text Percent Offset").setValueAtTime(t1, aDef.offsetTo);
                }
            }

            var properties = animator.property("ADBE Text Properties");
            var prop = properties.addProperty(aDef.prop);
            if (aDef.value) {
                if (aDef.value.length === 3) {
                    prop.setValue(aDef.value);
                } else if (aDef.value.length === 2) {
                    prop.setValue([aDef.value[0], aDef.value[1], 0]);
                } else {
                    prop.setValue(aDef.value);
                }
            }
        } catch(e) {}
    }
}

// ============================================================
// 入场动画应用引擎
// ============================================================
function applyAnimation(layer, animDef) {
    if (!animDef) return;
    var t0 = layer.inPoint;
    var kf = animDef.keyframes;

    // Scale keyframes
    if (kf.scale) {
        for (var i = 0; i < kf.scale.length; i++) {
            var s = kf.scale[i];
            layer.scale.setValueAtTime(t0 + s[0], [s[1], s[2]]);
        }
    }
    // Opacity keyframes
    if (kf.opacity) {
        for (var i = 0; i < kf.opacity.length; i++) {
            var o = kf.opacity[i];
            layer.opacity.setValueAtTime(t0 + o[0], o[1]);
        }
    }
    // Position Y keyframes
    if (kf.position_y) {
        var basePos = layer.position.value;
        for (var i = 0; i < kf.position_y.length; i++) {
            var py = kf.position_y[i];
            layer.position.setValueAtTime(t0 + py[0], [basePos[0], basePos[1] + py[1]]);
        }
    }
    // Rotation keyframes
    if (kf.rotation) {
        for (var i = 0; i < kf.rotation.length; i++) {
            var r = kf.rotation[i];
            layer.rotation.setValueAtTime(t0 + r[0], r[1]);
        }
    }

    // Text Animator
    if (animDef.animator) {
        applyAnimator(layer, [animDef.animator]);
    }

    // Expression
    if (animDef.expression) {
        try {
            if (animDef.animator && animDef.animator.prop === "ADBE Text Position 3D") {
                layer.property("Position").expression = animDef.expression;
            } else {
                layer.property("Position").expression = animDef.expression;
            }
        } catch(ee) {}
    }
}

// ============================================================
// 字体配置引擎
// ============================================================
function applyFont(layer, fontPostScriptName, fontSize, fillColor) {
    var textProp = layer.property("Text");
    var td = textProp.property("ADBE Text Document").value;
    if (fontPostScriptName) td.font = fontPostScriptName;
    if (fontSize) td.fontSize = fontSize;
    if (fillColor) {
        td.fillColor = fillColor;
        td.applyFill = true;
    }
    td.justification = ParagraphJustification.CENTER_JUSTIFY;
    textProp.property("ADBE Text Document").setValue(td);
}

// ============================================================
// 表达式应用引擎
// ============================================================
function applyExpressions(layer, exprMap) {
    if (!exprMap) return;
    for (var prop in exprMap) {
        if (exprMap.hasOwnProperty(prop)) {
            try {
                if (prop === "position") layer.property("Position").expression = exprMap[prop];
                else if (prop === "opacity") layer.property("Opacity").expression = exprMap[prop];
                else if (prop === "scale") layer.property("Scale").expression = exprMap[prop];
                else if (prop === "rotation") layer.property("Rotation").expression = exprMap[prop];
            } catch(e) {}
        }
    }
}

// ============================================================
// 主入口: 应用预设
// ============================================================
function applyPreset(presetType, presetId, options) {
    var comp = getActiveComp();
    if (!comp) return {status:"error", message:"No active composition"};

    var opts = options || {};
    var text = opts.text || "PRESET TEXT";
    var font = opts.font || null;
    var fontSize = opts.fontSize || 120;
    var fillColor = opts.fillColor || [1, 1, 1];
    var position = opts.position || [comp.width / 2, comp.height / 2];

    // 创建或获取文字层
    var layer = getSelectedTextLayer(comp);
    if (!layer) {
        var tl = comp.layers.addText(text);
        layer = tl;
    }
    layer.name = presetId;

    // 应用字体
    if (font) applyFont(layer, font, fontSize, fillColor);
    else applyFont(layer, null, fontSize, fillColor);

    layer.position.setValue(position);

    // 应用特效组合
    if (presetType === "effect" && PRESET_DB.effects[presetId]) {
        var eDef = PRESET_DB.effects[presetId];
        applyEffect(layer, eDef);
        applyAnimator(layer, eDef.animators);
        applyExpressions(layer, eDef.expressions);
        return {status:"success", preset:presetId, layer:layer.name, type:"effect"};
    }

    // 应用入场动画
    if (presetType === "animation" && PRESET_DB.animations[presetId]) {
        var aDef = PRESET_DB.animations[presetId];
        applyAnimation(layer, aDef);
        return {status:"success", preset:presetId, layer:layer.name, type:"animation"};
    }

    // 组合应用: effect + animation
    if (presetType === "combo") {
        var effectId = opts.effectId;
        var animId = opts.animId;
        if (effectId && PRESET_DB.effects[effectId]) {
            var eDef = PRESET_DB.effects[effectId];
            applyEffect(layer, eDef);
            applyAnimator(layer, eDef.animators);
            applyExpressions(layer, eDef.expressions);
        }
        if (animId && PRESET_DB.animations[animId]) {
            var aDef = PRESET_DB.animations[animId];
            applyAnimation(layer, aDef);
        }
        return {status:"success", preset:presetId, layer:layer.name, type:"combo",
                effect:effectId, animation:animId};
    }

    return {status:"error", message:"Unknown preset: " + presetId};
}

// ============================================================
// 列出所有可用预设
// ============================================================
function listPresets() {
    var result = {effects: [], animations: []};
    for (var k in PRESET_DB.effects) {
        if (PRESET_DB.effects.hasOwnProperty(k)) {
            result.effects.push({id: k, name: PRESET_DB.effects[k].name || k});
        }
    }
    for (var k in PRESET_DB.animations) {
        if (PRESET_DB.animations.hasOwnProperty(k)) {
            result.animations.push({id: k, name: PRESET_DB.animations[k].name || k});
        }
    }
    return result;
}

// ============================================================
// 执行入口 (通过 Bridge 命令调用)
// ============================================================
(function() {
    var _result = {};
    try {
        var comp = getActiveComp();
        if (!comp) {
            _result = {status:"error", message:"No active composition. Please open a comp first."};
            return JSON.stringify(_result);
        }

        // 默认演示: 应用 cyber_glitch 特效 + bounce_in 动画
        var presetType = "combo";
        var opts = {
            text: "TEXT FX",
            font: "Impact",
            fontSize: 140,
            fillColor: [0, 1, 0.8],
            position: [comp.width / 2, comp.height / 2],
            effectId: "effect_cyber_glitch",
            animId: "anim_bounce_in"
        };

        _result = applyPreset(presetType, "demo_combo", opts);
        _result.comp = comp.name;
        _result.compSize = comp.width + "x" + comp.height;
    } catch(e) {
        _result = {status:"error", message:e.toString(), line:e.line};
    }
    return JSON.stringify(_result);
})();
