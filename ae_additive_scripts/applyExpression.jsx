// applyExpression.jsx
// 表达式控制系统 - 为图层属性添加常用表达式
// Phase 5-1 扩展 - 核心功能补全之四

#include "_lib/response_utils.jsx"
#include "_lib/comp_utils.jsx"

function applyExpression(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "compName 参数必填");
        }
        if (typeof args.layerIndex !== "number") {
            return buildError("E102", "layerIndex 参数必填且必须为数字");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "合成未找到: " + args.compName);
        }

        if (!validateLayerIndex(comp, args.layerIndex)) {
            return buildError("E102", "图层索引无效: " + args.layerIndex);
        }

        var layer = comp.layer(args.layerIndex);

        // 参数解析
        var propertyPath = args.propertyPath || "Position";
        var expressionType = args.expressionType || "wiggle";
        var expressionParams = args.expressionParams || {};
        var overwriteExisting = args.overwriteExisting === true || args.overwriteExisting === "true";

        // 属性路径映射（支持常见属性和自定义路径）
        var propMap = {
            "Position": ["ADBE Transform Group", "ADBE Position"],
            "Scale": ["ADBE Transform Group", "ADBE Scale"],
            "Rotation": ["ADBE Transform Group", "ADBE Rotation"],
            "Opacity": ["ADBE Transform Group", "ADBE Opacity"],
            "Anchor Point": ["ADBE Transform Group", "ADBE Anchor Point"],
            "ADBE Text Properties/ADBE Text Document": ["ADBE Text Properties", "ADBE Text Document"]
        };

        var propKeys = null;
        if (propMap.hasOwnProperty(propertyPath)) {
            propKeys = propMap[propertyPath];
        } else if (propertyPath.indexOf("/") > 0) {
            // 支持自定义嵌套路径，如 "ADBE Effect Parade/ADBE Slider Control/ADBE Slider Control-0001"
            var parts = propertyPath.split("/");
            propKeys = parts;
        }

        if (!propKeys) {
            return buildError("E104", "不支持的属性路径: " + propertyPath);
        }

        // 逐级访问属性
        var targetProp = null;
        try {
            targetProp = layer.property(propKeys[0]);
            for (var pi = 1; pi < propKeys.length; pi++) {
                targetProp = targetProp.property(propKeys[pi]);
            }
        } catch (e) {
            return buildError("E105", "无法访问属性: " + propertyPath + "，错误: " + e.toString());
        }

        if (!targetProp) {
            return buildError("E105", "属性未找到: " + propertyPath);
        }

        // 检查是否支持表达式
        if (!targetProp.canSetExpression) {
            return buildError("E106", "该属性不支持表达式: " + propertyPath);
        }

        // 检查是否已有表达式
        if (!overwriteExisting && targetProp.expression && targetProp.expression.length > 0) {
            return buildError("E107", "属性已有表达式，设置 overwriteExisting=true 覆盖");
        }

        app.beginUndoGroup("Apply Expression");

        var expression = "";
        var appliedProps = [];

        // 根据表达式类型生成高质量表达式代码
        switch (expressionType) {
            case "bounce": {
                var amp = expressionParams.amplitude !== undefined ? Number(expressionParams.amplitude) : 100;
                var freq = expressionParams.frequency !== undefined ? Number(expressionParams.frequency) : 2;
                var decay = expressionParams.decay !== undefined ? Number(expressionParams.decay) : 3;
                expression = [
                    "amp = " + amp + ";",
                    "freq = " + freq + ";",
                    "decay = " + decay + ";",
                    "n = 0;",
                    "if (numKeys > 0) {",
                    "  n = nearestKey(time).index;",
                    "  if (key(n).time > time) n--;",
                    "}",
                    "if (n == 0) {",
                    "  t = 0;",
                    "} else {",
                    "  t = time - key(n).time;",
                    "}",
                    "if (n > 0 && t < 4) {",
                    "  v = velocityAtTime(key(n).time - thisComp.frameDuration/10);",
                    "  value + v*amp*Math.sin(freq*t*2*Math.PI)/Math.exp(decay*t);",
                    "} else {",
                    "  value;",
                    "}"
                ].join("\n");
                appliedProps.push("bounce");
                break;
            }

            case "loop": {
                var loopType = expressionParams.type || "cycle";
                var validLoopTypes = ["cycle", "pingpong", "offset"];
                var loopTypeValid = false;
                for (var i = 0; i < validLoopTypes.length; i++) {
                    if (validLoopTypes[i] === loopType) {
                        loopTypeValid = true;
                        break;
                    }
                }
                if (!loopTypeValid) loopType = "cycle";
                expression = [
                    "try {",
                    "  loopOut(\"" + loopType + "\");",
                    "} catch (e) {",
                    "  value;",
                    "}"
                ].join("\n");
                appliedProps.push("loop:" + loopType);
                break;
            }

            case "wiggle": {
                var wFreq = expressionParams.frequency !== undefined ? Number(expressionParams.frequency) : 2;
                var wAmt = expressionParams.amount !== undefined ? Number(expressionParams.amount) : 50;
                expression = "wiggle(" + wFreq + ", " + wAmt + ");";
                appliedProps.push("wiggle");
                break;
            }

            case "audio_react": {
                var audioIdx = expressionParams.audioLayerIndex !== undefined ? Number(expressionParams.audioLayerIndex) : 2;
                var audioProp = expressionParams.property || "both";
                var sensitivity = expressionParams.sensitivity !== undefined ? Number(expressionParams.sensitivity) : 100;
                var smoothness = expressionParams.smoothness !== undefined ? Number(expressionParams.smoothness) : 0.2;

                if (audioProp === "scale") {
                    expression = [
                        "audioLayer = thisComp.layer(" + audioIdx + ");",
                        "audioAmp = audioLayer.audioLevels[0] / 100;",
                        "sensitivity = " + sensitivity + " / 100;",
                        "smoothAmp = audioAmp;",
                        "if (smoothness > 0) {",
                        "  smoothAmp = audioLayer.audioLevels.smooth(smoothness)[0] / 100;",
                        "}",
                        "value * (1 + smoothAmp * sensitivity);"
                    ].join("\n");
                } else if (audioProp === "position") {
                    expression = [
                        "audioLayer = thisComp.layer(" + audioIdx + ");",
                        "audioAmp = audioLayer.audioLevels[0] / 100;",
                        "sensitivity = " + sensitivity + " / 100;",
                        "smoothAmp = audioAmp;",
                        "if (smoothness > 0) {",
                        "  smoothAmp = audioLayer.audioLevels.smooth(smoothness)[0] / 100;",
                        "}",
                        "value + [0, -smoothAmp * sensitivity * 50];"
                    ].join("\n");
                } else {
                    // both - 通用音频反应
                    expression = [
                        "audioLayer = thisComp.layer(" + audioIdx + ");",
                        "audioAmp = audioLayer.audioLevels[0] / 100;",
                        "sensitivity = " + sensitivity + " / 100;",
                        "smoothAmp = audioAmp;",
                        "if (smoothness > 0) {",
                        "  smoothAmp = audioLayer.audioLevels.smooth(smoothness)[0] / 100;",
                        "}",
                        "value * (1 + smoothAmp * sensitivity * 0.5);"
                    ].join("\n");
                }
                appliedProps.push("audio_react:" + audioProp);
                break;
            }

            case "time_delay": {
                var delay = expressionParams.delay !== undefined ? Number(expressionParams.delay) : 0.5;
                expression = "valueAtTime(time - " + delay + ");";
                appliedProps.push("time_delay");
                break;
            }

            case "smooth_follow": {
                var width = expressionParams.width !== undefined ? Number(expressionParams.width) : 0.2;
                var samples = expressionParams.samples !== undefined ? Number(expressionParams.samples) : 5;
                var tension = expressionParams.tension !== undefined ? Number(expressionParams.tension) : 2;
                expression = "smooth(" + width + ", " + samples + ", " + tension + ");";
                appliedProps.push("smooth_follow");
                break;
            }

            case "radial_array": {
                var centerX = expressionParams.centerX !== undefined ? Number(expressionParams.centerX) : comp.width / 2;
                var centerY = expressionParams.centerY !== undefined ? Number(expressionParams.centerY) : comp.height / 2;
                var radius = expressionParams.radius !== undefined ? Number(expressionParams.radius) : 200;
                var numItems = expressionParams.numItems !== undefined ? Number(expressionParams.numItems) : 8;
                expression = [
                    "center = [" + centerX + ", " + centerY + "];",
                    "radius = " + radius + ";",
                    "numItems = " + numItems + ";",
                    "angle = (index - 1) * (360 / numItems);",
                    "center + [Math.cos(degreesToRadians(angle)) * radius, Math.sin(degreesToRadians(angle)) * radius];"
                ].join("\n");
                appliedProps.push("radial_array");
                break;
            }

            case "typewriter": {
                var speed = expressionParams.speed !== undefined ? Number(expressionParams.speed) : 5;
                var cursor = expressionParams.cursor !== undefined ? String(expressionParams.cursor) : "|";
                // 转义光标字符中的特殊引号和反斜杠
                cursor = cursor.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
                expression = [
                    "text = value;",
                    "speed = " + speed + ";",
                    "cursor = \"" + cursor + "\";",
                    "n = Math.min(Math.floor(time * speed), text.length);",
                    "text.substr(0, n) + (n < text.length ? cursor : \"\");"
                ].join("\n");
                appliedProps.push("typewriter");
                break;
            }

            default: {
                app.endUndoGroup();
                return buildError("E108", "不支持的表达式类型: " + expressionType);
            }
        }

        // 应用表达式
        try {
            targetProp.expression = expression;
        } catch (exprErr) {
            app.endUndoGroup();
            return buildError("E109", "表达式应用失败: " + exprErr.toString());
        }

        app.endUndoGroup();

        return buildSuccess({
            layerIndex: args.layerIndex,
            layerName: layer.name,
            propertyPath: propertyPath,
            expressionType: expressionType,
            expressionLength: expression.length,
            overwriteExisting: overwriteExisting,
            appliedProps: appliedProps
        }, { message: "表达式应用成功" });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", error.toString());
    }
}

// 从 args.json 读取参数
var argsFile = new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json");
var args = {};
if (argsFile.exists) {
    argsFile.open("r");
    var _content = argsFile.read();
    argsFile.close();
    if (_content) {
        try { args = JSON.parse(_content); } catch (_e) { args = {}; }
    }
}

var result = applyExpression(args);
$.write(result);
