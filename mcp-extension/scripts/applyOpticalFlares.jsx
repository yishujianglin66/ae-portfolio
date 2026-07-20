// applyOpticalFlares.jsx
// Video Copilot Optical Flares 集成 - 在图层上应用镜头光晕效果
// Phase 4 扩展 - 第三方插件深度集成之三

function applyOpticalFlares(args) {
    try {
        if (!args.compName) {
            return JSON.stringify({ status: "error", message: "E101: compName 参数必填" }, null, 2);
        }
        if (typeof args.layerIndex !== "number") {
            return JSON.stringify({ status: "error", message: "E102: layerIndex 参数必填且必须为数字" }, null, 2);
        }

        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {
                comp = item;
                break;
            }
        }
        if (!comp) {
            return JSON.stringify({ status: "error", message: "E101: 合成未找到: " + args.compName }, null, 2);
        }

        if (args.layerIndex < 1 || args.layerIndex > comp.numLayers) {
            return JSON.stringify({ status: "error", message: "E102: 图层索引无效: " + args.layerIndex }, null, 2);
        }

        var layer = comp.layer(args.layerIndex);

        // 参数默认值
        var brightness = args.brightness !== undefined ? Number(args.brightness) : 100;
        var scale = args.scale !== undefined ? Number(args.scale) : 100;
        var color = args.color || [1, 1, 1];
        var flicker = args.flicker === true || args.flicker === "true";
        var flickerSpeed = args.flickerSpeed !== undefined ? Number(args.flickerSpeed) : 0;
        var audioReact = args.audioReact === true || args.audioReact === "true";
        var audioSource = args.audioSource || "";
        var position = args.position || [comp.width / 2, comp.height / 2];

        // 光效类型映射为整数索引（参考 VC Optical Flares 内部枚举）
        var flareTypeMap = {
            "standard": 0,
            "anamorphic": 1,
            "energy": 2,
            "sun": 3,
            "lens": 4,
            "streak": 5
        };
        var flareTypeStr = args.flareType || "standard";
        var flareTypeIdx = flareTypeMap[String(flareTypeStr).toLowerCase()];

        app.beginUndoGroup("Apply VC Optical Flares");

        // 尝试多种 matchName 添加 Optical Flares 效果
        var ofFx = null;
        var matchNames = ["Optical Flares", "VC Optical Flares", "ACP Optical Flares"];
        var usedMatchName = "";
        for (var m = 0; m < matchNames.length; m++) {
            try {
                ofFx = layer.Effects.addProperty(matchNames[m]);
                if (ofFx) {
                    usedMatchName = matchNames[m];
                    break;
                }
            } catch (e) {}
        }
        if (!ofFx) {
            app.endUndoGroup();
            return JSON.stringify({
                status: "error",
                message: "E201: Video Copilot Optical Flares 效果未安装，matchName 尝试: " + matchNames.join(", ")
            }, null, 2);
        }

        var applied = [];

        // 通用属性设置函数（单属性失败不影响整体）
        function setProp(propName, value) {
            try {
                var p = ofFx.property(propName);
                if (p) {
                    p.setValue(value);
                    applied.push(propName);
                    return true;
                }
            } catch (e) {}
            return false;
        }

        // 位置属性（支持 "Position XY" 和 AE 内部 matchName "ADBE Optical Flares Position XY"）
        var posSet = setProp("Position XY", position);
        if (!posSet) setProp("ADBE Optical Flares-0001", position);

        // 亮度
        var brightSet = setProp("Brightness", brightness);
        if (!brightSet) setProp("ADBE Optical Flares-0002", brightness);

        // 缩放
        var scaleSet = setProp("Scale", scale);
        if (!scaleSet) setProp("ADBE Optical Flares-0003", scale);

        // 颜色
        var colorSet = setProp("Color", color);
        if (!colorSet) setProp("ADBE Optical Flares-0004", color);

        // 光效类型（部分版本支持 "Flare Type" 属性）
        if (flareTypeIdx !== undefined) {
            setProp("Flare Type", flareTypeIdx);
            setProp("ADBE Optical Flares-0005", flareTypeIdx);
        }

        // 闪烁开关
        if (flicker) {
            var flickerOn = setProp("Flicker", true);
            if (!flickerOn) setProp("ADBE Optical Flares-0006", true);

            if (flickerSpeed > 0) {
                var fsSet = setProp("Flicker Speed", flickerSpeed);
                if (!fsSet) setProp("ADBE Optical Flares-0007", flickerSpeed);
            }
        }

        // 音频反应模式
        var audioReactEnabled = false;
        if (audioReact) {
            try {
                var arProp = ofFx.property("Audio React") || ofFx.property("ADBE Optical Flares-0008");
                if (arProp) {
                    arProp.setValue(true);
                    applied.push("Audio React");
                    audioReactEnabled = true;

                    // 关联音频源图层
                    if (audioSource) {
                        var audioLayer = null;
                        for (var li = 1; li <= comp.numLayers; li++) {
                            if (comp.layer(li).name === audioSource) {
                                audioLayer = comp.layer(li);
                                break;
                            }
                        }
                        if (audioLayer) {
                            try {
                                var srcProp = ofFx.property("Audio Source") || ofFx.property("ADBE Optical Flares-0009");
                                if (srcProp) {
                                    // 部分版本通过图层引用设置
                                    srcProp.setValue(audioLayer.index);
                                    applied.push("Audio Source: " + audioSource);
                                }
                            } catch (e) {}
                        }
                    }
                }
            } catch (e) {}
        }

        var effectIndex = ofFx.propertyIndex;
        var effectName = ofFx.name;

        app.endUndoGroup();

        return JSON.stringify({
            status: "success",
            message: "VC Optical Flares 效果应用成功",
            effectName: effectName,
            effectIndex: effectIndex,
            matchName: usedMatchName,
            flareType: flareTypeStr,
            flareTypeIndex: flareTypeIdx !== undefined ? flareTypeIdx : null,
            audioReactEnabled: audioReactEnabled,
            audioSource: audioReactEnabled ? audioSource : null,
            appliedProps: applied
        }, null, 2);
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return JSON.stringify({ status: "error", message: "E200: " + error.toString() }, null, 2);
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

var result = applyOpticalFlares(args);
$.write(result);
