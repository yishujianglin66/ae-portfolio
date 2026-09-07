// expressionAnimLib.jsx
// 表达式驱动动画库 - 程序化持续动画
// 无需关键帧，纯表达式实现循环/响应式动画
// 用法: expressionAnimLib(args) 其中 args = {compIndex, layerIndex, exprType, options}

#include "_lib/response_utils.jsx"
#include "_lib/comp_utils.jsx"

// ============ 表达式模板库 ============
var EXPR_TEMPLATES = {
    // --- 位置类 ---
    "orbit": {
        name: "环绕运动",
        target: "Position",
        template: "center = [%(cx)s, %(cy)s];\nradiusX = %(rx)s;\nradiusY = %(ry)s;\nspeed = %(speed)s;\nangle = time * speed * Math.PI * 2;\n[center[0] + radiusX * Math.cos(angle), center[1] + radiusY * Math.sin(angle)];"
    },
    "figure8": {
        name: "8字运动",
        target: "Position",
        template: "center = [%(cx)s, %(cy)s];\namp = %(amplitude)s;\nspeed = %(speed)s;\nt = time * speed * Math.PI * 2;\n[center[0] + amp * Math.sin(t), center[1] + amp * Math.sin(t * 2) / 2];"
    },
    "float": {
        name: "漂浮",
        target: "Position",
        template: "amp = %(amplitude)s;\nspeed = %(speed)s;\nseedRandom(%(seed)s, true);\nphase = random() * Math.PI * 2;\n[value[0] + Math.sin(time * speed + phase) * amp * 0.3, value[1] + Math.sin(time * speed * 0.7 + phase) * amp];"
    },
    "shake": {
        name: "震动",
        target: "Position",
        template: "amp = %(amplitude)s;\nfreq = %(frequency)s;\ndecay = %(decay)s;\nt = time - %(startTime)s;\nif (t > 0) {\n  n = amp * Math.sin(t * freq * Math.PI * 2) / Math.exp(t * decay);\n  [value[0] + n, value[1] + n * 0.5];\n} else value;"
    },
    "pathFollow": {
        name: "路径跟随",
        target: "Position",
        template: "speed = %(speed)s;\npath = thisComp.layer('%(pathLayer)s').mask('%(maskName)s').maskPath;\nt = (time * speed) %% 1;\npath.pointOnPath(t);"
    },
    
    // --- 缩放类 ---
    "pulseScale": {
        name: "脉冲缩放",
        target: "Scale",
        template: "amp = %(amplitude)s;\nspeed = %(speed)s;\nbase = value;\nfactor = 1 + amp/100 * Math.sin(time * speed * Math.PI * 2);\n[base[0] * factor, base[1] * factor, base.length > 2 ? base[2] * factor : 100];"
    },
    "bounceScale": {
        name: "弹跳缩放",
        target: "Scale",
        template: "speed = %(speed)s;\namp = %(amplitude)s;\nt = time * speed;\nbounce = Math.abs(Math.sin(t * Math.PI)) * amp;\n[value[0] + bounce, value[1] - bounce * 0.5, 100];"
    },
    "elasticScale": {
        name: "弹性缩放",
        target: "Scale",
        template: "freq = %(frequency)s;\ndecay = %(decay)s;\namp = %(amplitude)s;\nt = time - %(startTime)s;\nif (t > 0) {\n  n = amp * Math.sin(freq * t * Math.PI * 2) / Math.exp(decay * t);\n  [value[0] + n, value[1] + n, 100];\n} else value;"
    },
    
    // --- 旋转类 ---
    "spin": {
        name: "匀速旋转",
        target: "Rotation",
        template: "time * %(speed)s;"
    },
    "pendulum": {
        name: "钟摆",
        target: "Rotation",
        template: "amp = %(amplitude)s;\nspeed = %(speed)s;\ndamping = %(damping)s;\namp * Math.sin(time * speed * Math.PI * 2) / Math.exp(time * damping);"
    },
    "wiggleRot": {
        name: "随机旋转",
        target: "Rotation",
        template: "wiggle(%(frequency)s, %(amplitude)s);"
    },
    
    // --- 不透明度类 ---
    "blink": {
        name: "闪烁",
        target: "Opacity",
        template: "speed = %(speed)s;\nminVal = %(minOpacity)s;\nmaxVal = %(maxOpacity)s;\nMath.sin(time * speed * Math.PI * 2) > 0 ? maxVal : minVal;"
    },
    "fadeLoop": {
        name: "呼吸淡入淡出",
        target: "Opacity",
        template: "speed = %(speed)s;\nminVal = %(minOpacity)s;\nmaxVal = %(maxOpacity)s;\nrange = maxVal - minVal;\nminVal + range * (0.5 + 0.5 * Math.sin(time * speed * Math.PI * 2));"
    },
    "randomFlicker": {
        name: "随机闪烁",
        target: "Opacity",
        template: "speed = %(speed)s;\nseedRandom(Math.floor(time * speed), true);\nrandom(%(minOpacity)s, %(maxOpacity)s);"
    },
    
    // --- 通用 wiggle ---
    "wigglePos": {
        name: "位置抖动",
        target: "Position",
        template: "wiggle(%(frequency)s, %(amplitude)s);"
    },
    "wiggleScale": {
        name: "缩放抖动",
        target: "Scale",
        template: "w = wiggle(%(frequency)s, %(amplitude)s);\n[w[0], w[1], value.length > 2 ? w[2] : 100];"
    },
    
    // --- 颜色类 ---
    "colorCycle": {
        name: "颜色循环",
        target: "Effects",
        template: "// 需要配合 Fill 效果使用\nspeed = %(speed)s;\nhue = (time * speed) %% 1;\nfunction hsl2rgb(h){\n  var r = Math.abs(h * 6 - 3) - 1;\n  var g = 2 - Math.abs(h * 6 - 2);\n  var b = 2 - Math.abs(h * 6 - 4);\n  return [Math.max(0,Math.min(1,r)), Math.max(0,Math.min(1,g)), Math.max(0,Math.min(1,b)), 1];\n}\nhsl2rgb(hue);"
    },
    
    // --- 文字专用 ---
    "typewriterCursor": {
        name: "打字机光标",
        target: "Opacity",
        template: "// 配合 Source Text 表达式使用\nMath.sin(time * 4) > 0 ? 100 : 0;"
    },
    "textScroll": {
        name: "文字滚动",
        target: "Position",
        template: "speed = %(speed)s;\n[value[0] - time * speed, value[1]];"
    }
};

// ============ 核心引擎 ============

/**
 * 解析模板中的占位符
 */
function resolveTemplate(template, params) {
    var result = template;
    for (var key in params) {
        var placeholder = "%(" + key + ")s";
        while (result.indexOf(placeholder) !== -1) {
            result = result.replace(placeholder, String(params[key]));
        }
    }
    return result;
}

/**
 * 获取默认参数
 */
function getDefaults(exprType) {
    var defaults = {
        "orbit": {cx:960, cy:540, rx:200, ry:100, speed:0.5},
        "figure8": {cx:960, cy:540, amplitude:200, speed:0.3},
        "float": {amplitude:20, speed:1.0, seed:42},
        "shake": {amplitude:15, frequency:20, decay:3, startTime:0},
        "pathFollow": {speed:0.2, pathLayer:"Path", maskName:"Mask 1"},
        "pulseScale": {amplitude:10, speed:2},
        "bounceScale": {speed:2, amplitude:15},
        "elasticScale": {frequency:3, decay:4, amplitude:30, startTime:0},
        "spin": {speed:90},
        "pendulum": {amplitude:30, speed:1, damping:0.3},
        "wiggleRot": {frequency:2, amplitude:10},
        "blink": {speed:2, minOpacity:0, maxOpacity:100},
        "fadeLoop": {speed:1, minOpacity:30, maxOpacity:100},
        "randomFlicker": {speed:10, minOpacity:50, maxOpacity:100},
        "wigglePos": {frequency:2, amplitude:20},
        "wiggleScale": {frequency:1.5, amplitude:5},
        "colorCycle": {speed:0.2},
        "typewriterCursor": {},
        "textScroll": {speed:100}
    };
    return defaults[exprType] || {};
}

/**
 * 应用表达式到图层属性
 */
function applyExpression(layer, exprType, options) {
    var tmpl = EXPR_TEMPLATES[exprType];
    if (!tmpl) return null;
    
    // 合并默认参数和用户参数
    var params = getDefaults(exprType);
    for (var key in options) {
        params[key] = options[key];
    }
    
    // 解析模板
    var exprCode = resolveTemplate(tmpl.template, params);
    
    // 确定目标属性
    var targetProp;
    switch(tmpl.target) {
        case "Position":
            targetProp = layer.property("Position");
            break;
        case "Scale":
            targetProp = layer.property("Scale");
            break;
        case "Rotation":
            targetProp = layer.property("Rotation");
            break;
        case "Opacity":
            targetProp = layer.property("Opacity");
            break;
        case "Effects":
            // 需要先添加 Fill 效果
            try {
                var fill = layer.Effects.addProperty("ADBE Fill");
                fill.name = "ExprColorCycle";
                targetProp = fill.property("ADBE Fill-0002");
            } catch(e) {
                return null;
            }
            break;
        default:
            targetProp = layer.property(tmpl.target);
    }
    
    if (!targetProp) return null;
    
    // 设置表达式
    targetProp.expression = exprCode;
    return targetProp;
}

// ============ 主入口 ============
function expressionAnimLib(args) {
    var compIndex = args.compIndex || 1;
    var layerIndex = args.layerIndex || 1;
    var exprType = args.exprType || "float";
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
    
    // 获取图层
    var layer;
    if (layerIndex >= 1 && layerIndex <= comp.numLayers) {
        layer = comp.layer(layerIndex);
    }
    if (!layer) {
        return buildErrorResponse("layer_not_found", "图层未找到: " + layerIndex);
    }
    
    // 验证表达式类型
    if (!EXPR_TEMPLATES[exprType]) {
        var available = [];
        for (var key in EXPR_TEMPLATES) { available.push(key); }
        return buildErrorResponse("unknown_expr", "未知表达式: " + exprType + "。可用: " + available.join(", "));
    }
    
    app.beginUndoGroup("ExprAnim_" + exprType);
    try {
        var prop = applyExpression(layer, exprType, options);
        app.endUndoGroup();
        
        if (!prop) {
            return buildErrorResponse("apply_failed", "无法应用表达式到目标属性");
        }
        
        return buildSuccessResponse({
            exprType: exprType,
            name: EXPR_TEMPLATES[exprType].name,
            target: EXPR_TEMPLATES[exprType].target,
            layer: layer.name,
            comp: comp.name,
            expression: prop.expression
        });
    } catch(e) {
        app.endUndoGroup();
        return buildErrorResponse("expr_error", exprType + " 执行失败: " + e.message);
    }
}

// 列出所有表达式模板
function listExpressions() {
    var list = [];
    for (var key in EXPR_TEMPLATES) {
        list.push({
            id: key,
            name: EXPR_TEMPLATES[key].name,
            target: EXPR_TEMPLATES[key].target,
            params: getDefaults(key)
        });
    }
    return buildSuccessResponse({total: list.length, expressions: list});
}

// 入口调度
var _args = (typeof args !== "undefined") ? args : {};
if (_args.action === "list") {
    listExpressions();
} else {
    expressionAnimLib(_args);
}
