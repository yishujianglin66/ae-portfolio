// deep_inspect.jsx
// AEP 深度检查脚本 - 在 AE 内部执行，提取完整项目结构
//
// 扩展自 analyzeProject.jsx，新增：
// - 效果参数值读取
// - 关键帧数据导出（时间/值/缓动）
// - 表达式文本读取
// - 父子关系映射
// - 轨道蒙版关系
// - 素材源文件路径
// - 遮罩数据
// - 预合成嵌套图
//
// 用法：在 AE 中通过 MCP Bridge 执行，或直接在 AE 脚本控制台运行
// 输出：JSON 格式写入 ae_result.json 或 stdout

(function() {
    "use strict";

    // JSON polyfill for old ExtendScript
    if (typeof JSON === "undefined") {
        JSON = {
            stringify: function(obj) {
                if (obj === null || obj === undefined) return "null";
                if (typeof obj === "string") return '"' + obj.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"';
                if (typeof obj === "number" || typeof obj === "boolean") return String(obj);
                if (obj instanceof Array) {
                    var items = [];
                    for (var i = 0; i < obj.length; i++) items.push(JSON.stringify(obj[i]));
                    return "[" + items.join(",") + "]";
                }
                var pairs = [];
                for (var k in obj) {
                    if (obj.hasOwnProperty(k)) pairs.push('"' + k + '":' + JSON.stringify(obj[k]));
                }
                return "{" + pairs.join(",") + "}";
            },
            parse: function(str) { return eval("(" + str + ")"); }
        };
    }

    // ========================================================================
    // Main Analysis
    // ========================================================================

    function deepInspect() {
        if (app.project === null) {
            return { error: "NO_PROJECT", message: "No project is open" };
        }

        var report = {
            project: inspectProject(),
            compositions: [],
            precompGraph: {},
            effectsByType: {},
            techniques: [],
            stats: {
                totalComps: 0,
                totalLayers: 0,
                totalEffects: 0,
                totalKeyframes: 0,
                totalExpressions: 0,
                totalMasks: 0
            }
        };

        // Analyze all compositions
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem) {
                report.compositions.push(inspectComp(item, report));
                report.stats.totalComps++;
            }
        }

        // Build precomp graph
        report.precompGraph = buildPrecompGraph(report.compositions);

        // Detect techniques
        report.techniques = detectTechniques(report);

        // Deduplicate techniques
        var unique = [];
        for (var t = 0; t < report.techniques.length; t++) {
            if (unique.indexOf(report.techniques[t]) === -1) {
                unique.push(report.techniques[t]);
            }
        }
        report.techniques = unique;

        return report;
    }

    // ========================================================================
    // Project Inspector
    // ========================================================================

    function inspectProject() {
        var proj = {
            name: null,
            path: null,
            bitsPerChannel: 8,
            timecodeBase: null,
            workingGamma: null,
            workingColorSpace: null,
            items: { total: 0, comps: 0, footage: 0, folders: 0 }
        };

        if (app.project.file) {
            proj.name = app.project.file.name;
            proj.path = app.project.file.fsName;
        }

        proj.bitsPerChannel = app.project.bitsPerChannel;

        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            proj.items.total++;
            if (item instanceof CompItem) proj.items.comps++;
            else if (item instanceof FootageItem) proj.items.footage++;
            else if (item instanceof FolderItem) proj.items.folders++;
        }

        return proj;
    }

    // ========================================================================
    // Composition Inspector
    // ========================================================================

    function inspectComp(comp, report) {
        var compInfo = {
            name: comp.name,
            id: comp.id,
            width: comp.width,
            height: comp.height,
            duration: comp.duration,
            frameRate: comp.frameRate,
            numLayers: comp.numLayers,
            has3D: false,
            hasCamera: false,
            hasLight: false,
            hasAdjustmentLayer: false,
            hasPrecomp: false,
            bgColor: null,
            layers: [],
            layerTypes: {
                adjustment: [],
                null: [],
                shape: [],
                text: [],
                footage: [],
                precomp: [],
                camera: [],
                light: []
            }
        };

        // Background color
        try {
            var bg = comp.bgColor;
            compInfo.bgColor = [Math.round(bg[0]*255), Math.round(bg[1]*255), Math.round(bg[2]*255)];
        } catch(e) {}

        // Inspect each layer
        for (var i = 1; i <= comp.numLayers; i++) {
            var layer = comp.layer(i);
            var layerInfo = inspectLayer(layer, report);
            compInfo.layers.push(layerInfo);
            report.stats.totalLayers++;

            // Categorize layer type
            categorizeLayer(layer, compInfo);
        }

        return compInfo;
    }

    // ========================================================================
    // Layer Inspector (Core Enhancement)
    // ========================================================================

    function inspectLayer(layer, report) {
        var info = {
            name: layer.name,
            index: layer.index,
            id: layer.id,
            type: getLayerTypeName(layer),
            inPoint: layer.inPoint,
            outPoint: layer.outPoint,
            duration: layer.outPoint - layer.inPoint,
            startTime: layer.startTime,
            blendMode: getBlendModeName(layer.blendingMode),
            opacity: {
                value: layer.opacity.value,
                animated: layer.opacity.numKeys > 0,
                expression: getExpression(layer.opacity)
            },
            transform: inspectTransform(layer),
            parent: getParentInfo(layer),
            trackMatte: getTrackMatteInfo(layer),
            effects: inspectEffects(layer, report),
            masks: inspectMasks(layer, report),
            source: getSourceInfo(layer),
            threeD: layer.threeDLayer,
            motionBlur: layer.motionBlur,
            adjustmentLayer: layer.adjustmentLayer,
            locked: layer.locked,
            shy: layer.shy,
            solo: layer.solo,
            enabled: layer.enabled
        };

        return info;
    }

    function inspectTransform(layer) {
        var props = ["Position", "Scale", "Rotation", "Opacity"];
        var transform = {};

        for (var p = 0; p < props.length; p++) {
            var propName = props[p];
            try {
                var prop = layer.property(propName);
                if (!prop || !prop.isProperty) continue;

                var propInfo = {
                    value: safeGetValue(prop),
                    animated: prop.numKeys > 0,
                    expression: getExpression(prop),
                    keyframes: []
                };

                // Extract keyframes
                if (prop.numKeys > 0) {
                    propInfo.keyframes = extractKeyframes(prop);
                }

                transform[propName.toLowerCase()] = propInfo;
            } catch(e) {}
        }

        // 3D-specific properties
        if (layer.threeDLayer) {
            try {
                var xRot = layer.property("X Rotation");
                var yRot = layer.property("Y Rotation");
                if (xRot && xRot.isProperty) {
                    transform["x_rotation"] = {
                        value: xRot.value,
                        animated: xRot.numKeys > 0,
                        keyframes: xRot.numKeys > 0 ? extractKeyframes(xRot) : []
                    };
                }
                if (yRot && yRot.isProperty) {
                    transform["y_rotation"] = {
                        value: yRot.value,
                        animated: yRot.numKeys > 0,
                        keyframes: yRot.numKeys > 0 ? extractKeyframes(yRot) : []
                    };
                }
            } catch(e) {}
        }

        return transform;
    }

    // ========================================================================
    // Effect Inspector (NEW - Parameter Values)
    // ========================================================================

    function inspectEffects(layer, report) {
        var effects = [];

        try {
            var fxGroup = layer.Effects;
            if (!fxGroup) return effects;

            for (var i = 1; i <= fxGroup.numProperties; i++) {
                var effect = fxGroup.property(i);
                if (!effect || effect.isEffectGroup) continue;

                var effectInfo = {
                    name: effect.name,
                    matchName: effect.matchName,
                    index: i,
                    enabled: effect.enabled,
                    isPlugin: isPluginEffect(effect.name),
                    category: getEffectCategory(effect.name),
                    params: [],
                    expressions: []
                };

                // Extract effect parameters
                try {
                    for (var p = 1; p <= effect.numProperties; p++) {
                        var param = effect.property(p);
                        if (!param) continue;

                        if (param.isProperty) {
                            var paramInfo = {
                                name: param.name,
                                index: p,
                                value: safeGetValue(param),
                                animated: param.numKeys > 0,
                                keyframes: []
                            };

                            // Extract keyframes for this parameter
                            if (param.numKeys > 0) {
                                paramInfo.keyframes = extractKeyframes(param);
                                report.stats.totalKeyframes += param.numKeys;
                            }

                            // Check for expression
                            var expr = getExpression(param);
                            if (expr) {
                                effectInfo.expressions.push({
                                    property: param.name,
                                    text: expr
                                });
                                report.stats.totalExpressions++;
                            }

                            effectInfo.params.push(paramInfo);
                        }
                    }
                } catch(e) {}

                effects.push(effectInfo);
                report.stats.totalEffects++;

                // Track effects by type
                var eName = effect.name;
                if (!report.effectsByType[eName]) {
                    report.effectsByType[eName] = {
                        count: 0,
                        matchName: effect.matchName,
                        category: getEffectCategory(eName),
                        isPlugin: isPluginEffect(eName)
                    };
                }
                report.effectsByType[eName].count++;
            }
        } catch(e) {}

        return effects;
    }

    // ========================================================================
    // Keyframe Extractor (NEW)
    // ========================================================================

    function extractKeyframes(prop) {
        var keyframes = [];
        var maxKeys = Math.min(prop.numKeys, 500); // Safety limit

        for (var k = 1; k <= maxKeys; k++) {
            try {
                var kf = {
                    index: k,
                    time: prop.keyTime(k),
                    value: safeKeyValue(prop, k),
                    label: prop.keyLabel(k) || null
                };

                // Temporal ease
                try {
                    var inEase = prop.keyInTemporalEase(k);
                    var outEase = prop.keyOutTemporalEase(k);
                    if (inEase && inEase.length > 0) {
                        kf.inEase = {
                            speed: inEase[0].speed,
                            influence: inEase[0].influence
                        };
                    }
                    if (outEase && outEase.length > 0) {
                        kf.outEase = {
                            speed: outEase[0].speed,
                            influence: outEase[0].influence
                        };
                    }
                } catch(e) {}

                // Interpolation type
                try {
                    var inType = prop.keyInInterpolationType(k);
                    var outType = prop.keyOutInterpolationType(k);
                    kf.interpolation = {
                        in: getInterpolationTypeName(inType),
                        out: getInterpolationTypeName(outType)
                    };
                } catch(e) {}

                keyframes.push(kf);
            } catch(e) {}
        }

        return keyframes;
    }

    // ========================================================================
    // Mask Inspector (NEW)
    // ========================================================================

    function inspectMasks(layer, report) {
        var masks = [];

        try {
            var maskGroup = layer.Masks;
            if (!maskGroup) return masks;

            for (var i = 1; i <= maskGroup.numProperties; i++) {
                var mask = maskGroup.property(i);
                if (!mask || !mask.isProperty) continue;

                try {
                    var maskInfo = {
                        name: mask.name,
                        index: i,
                        mode: getMaskModeName(mask.maskMode),
                        feather: mask.maskFeather ? mask.maskFeather.value : 0,
                        opacity: mask.maskOpacity ? mask.maskOpacity.value : 100,
                        expansion: mask.maskExpansion ? mask.maskExpansion.value : 0,
                        inverted: mask.inverted,
                        locked: mask.locked,
                        color: null
                    };

                    // Mask color
                    try {
                        var c = mask.color;
                        maskInfo.color = [Math.round(c[0]*255), Math.round(c[1]*255), Math.round(c[2]*255)];
                    } catch(e) {}

                    // Mask path
                    try {
                        var maskPath = mask.property("Mask Path");
                        if (maskPath && maskPath.isProperty) {
                            maskInfo.animated = maskPath.numKeys > 0;
                            if (maskPath.numKeys > 0) {
                                maskInfo.keyframes = extractKeyframes(maskPath);
                            }
                        }
                    } catch(e) {}

                    masks.push(maskInfo);
                    report.stats.totalMasks++;
                } catch(e) {}
            }
        } catch(e) {}

        return masks;
    }

    // ========================================================================
    // Helper Functions
    // ========================================================================

    function getParentInfo(layer) {
        try {
            if (layer.parent) {
                return {
                    index: layer.parent.index,
                    name: layer.parent.name
                };
            }
        } catch(e) {}
        return null;
    }

    function getTrackMatteInfo(layer) {
        try {
            var matteType = layer.trackMatteType;
            if (matteType && matteType !== TrackMatteType.NO_TRACK_MATTE) {
                return {
                    type: getTrackMatteTypeName(matteType),
                    layerIndex: layer.index - 1  // Matte is typically the layer above
                };
            }
        } catch(e) {}
        return null;
    }

    function getSourceInfo(layer) {
        try {
            if (layer.source && layer.source.mainSource) {
                var src = layer.source;
                var info = {
                    name: src.name,
                    width: src.width,
                    height: src.height,
                    duration: src.duration,
                    frameRate: src.frameRate || null,
                    path: null
                };

                // Get source file path
                try {
                    if (src.mainSource && src.mainSource.file) {
                        info.path = src.mainSource.file.fsName;
                    }
                } catch(e) {}

                // Check if it's a precomp
                if (src instanceof CompItem) {
                    info.isPrecomp = true;
                    info.precompName = src.name;
                }

                return info;
            }
        } catch(e) {}
        return null;
    }

    function getExpression(prop) {
        try {
            if (prop.expression && prop.expression.length > 0) {
                return {
                    text: prop.expression,
                    enabled: prop.expressionEnabled
                };
            }
        } catch(e) {}
        return null;
    }

    function safeGetValue(prop) {
        try {
            var val = prop.value;
            if (val instanceof Array) {
                // Round numbers for readability
                var rounded = [];
                for (var i = 0; i < val.length; i++) {
                    rounded.push(Math.round(val[i] * 1000) / 1000);
                }
                return rounded;
            }
            if (typeof val === "number") {
                return Math.round(val * 1000) / 1000;
            }
            return val;
        } catch(e) {
            return null;
        }
    }

    function safeKeyValue(prop, keyIndex) {
        try {
            var val = prop.keyValue(keyIndex);
            if (val instanceof Array) {
                var rounded = [];
                for (var i = 0; i < val.length; i++) {
                    rounded.push(Math.round(val[i] * 1000) / 1000);
                }
                return rounded;
            }
            if (typeof val === "number") {
                return Math.round(val * 1000) / 1000;
            }
            return val;
        } catch(e) {
            return null;
        }
    }

    function categorizeLayer(layer, compInfo) {
        try {
            if (layer.adjustmentLayer) compInfo.layerTypes.adjustment.push(layer.name);
            if (layer instanceof CameraLayer) {
                compInfo.hasCamera = true;
                compInfo.layerTypes.camera.push(layer.name);
            }
            if (layer instanceof LightLayer) {
                compInfo.hasLight = true;
                compInfo.layerTypes.light.push(layer.name);
            }
            if (layer instanceof ShapeLayer) compInfo.layerTypes.shape.push(layer.name);
            if (layer instanceof TextLayer) compInfo.layerTypes.text.push(layer.name);
            if (layer.source instanceof CompItem) {
                compInfo.hasPrecomp = true;
                compInfo.layerTypes.precomp.push(layer.name);
            } else if (layer instanceof FootageLayer) {
                compInfo.layerTypes.footage.push(layer.name);
            }
            // Null detection
            if (layer.nullLayer) compInfo.layerTypes.null.push(layer.name);
        } catch(e) {}
    }

    function buildPrecompGraph(compositions) {
        var graph = {};
        for (var c = 0; c < compositions.length; c++) {
            var comp = compositions[c];
            var children = [];
            for (var l = 0; l < comp.layers.length; l++) {
                var src = comp.layers[l].source;
                if (src && src.isPrecomp) {
                    children.push(src.precompName);
                }
            }
            if (children.length > 0) {
                graph[comp.name] = children;
            }
        }
        return graph;
    }

    // ========================================================================
    // Technique Detection
    // ========================================================================

    function detectTechniques(report) {
        var techniques = [];
        var allEffects = [];

        for (var c = 0; c < report.compositions.length; c++) {
            var comp = report.compositions[c];
            for (var l = 0; l < comp.layers.length; l++) {
                var layer = comp.layers[l];
                for (var e = 0; e < layer.effects.length; e++) {
                    allEffects.push(layer.effects[e].name);
                }
            }
        }

        function hasEffect(name) {
            for (var i = 0; i < allEffects.length; i++) {
                if (allEffects[i].indexOf(name) !== -1) return true;
            }
            return false;
        }

        if (hasEffect("Color Key") || hasEffect("Keylight")) techniques.push("绿幕/蓝幕抠图技术");
        if (hasEffect("Glow") && hasEffect("Saber")) techniques.push("发光光效组合");
        if (hasEffect("Particular")) techniques.push("粒子特效");
        if (hasEffect("Optical Flares")) techniques.push("镜头光晕");
        if (hasEffect("Time Remapping")) techniques.push("时间重映射");
        if (hasEffect("Turbulent Displace")) techniques.push("流体/烟雾效果");
        if (hasEffect("Displacement Map")) techniques.push("置换贴图");
        if (hasEffect("LUT")) techniques.push("LUT调色预设");
        if (hasEffect("Warp Stabilizer")) techniques.push("变形稳定器");
        if (hasEffect("Curves") || hasEffect("Levels")) techniques.push("调色校正");
        if (hasEffect("Deep Glow") || hasEffect("Glow")) techniques.push("发光效果");
        if (hasEffect("Element 3D")) techniques.push("3D元素集成");
        if (hasEffect("Newton")) techniques.push("物理模拟");
        if (hasEffect("Lockdown")) techniques.push("平面跟踪");

        // Check for expression-driven animation
        if (report.stats.totalExpressions > 0) {
            techniques.push("表达式驱动动画 (" + report.stats.totalExpressions + "个表达式)");
        }

        // Check for 3D camera
        for (var c2 = 0; c2 < report.compositions.length; c2++) {
            if (report.compositions[c2].hasCamera && report.compositions[c2].has3D) {
                techniques.push("3D摄像机运动");
                break;
            }
        }

        // Check for precomp organization
        if (Object.keys(report.precompGraph).length > 0) {
            techniques.push("预合成组织 (" + Object.keys(report.precompGraph).length + "个预合成)");
        }

        return techniques;
    }

    // ========================================================================
    // Name Lookup Helpers
    // ========================================================================

    function getLayerTypeName(layer) {
        try {
            if (layer.adjustmentLayer) return "adjustment";
            if (layer.nullLayer) return "null";
            if (layer instanceof CameraLayer) return "camera";
            if (layer instanceof LightLayer) return "light";
            if (layer instanceof ShapeLayer) return "shape";
            if (layer instanceof TextLayer) return "text";
            if (layer.source instanceof CompItem) return "precomp";
            return "footage";
        } catch(e) { return "unknown"; }
    }

    function getBlendModeName(mode) {
        var modes = {};
        modes[BlendingMode.NORMAL] = "normal";
        modes[BlendingMode.MULTIPLY] = "multiply";
        modes[BlendingMode.SCREEN] = "screen";
        modes[BlendingMode.OVERLAY] = "overlay";
        modes[BlendingMode.ADD] = "add";
        modes[BlendingMode.COLOR_DODGE] = "color_dodge";
        modes[BlendingMode.COLOR_BURN] = "color_burn";
        modes[BlendingMode.DIFFERENCE] = "difference";
        modes[BlendingMode.EXCLUSION] = "exclusion";
        modes[BlendingMode.LUMINESCENT_PREMUL] = "luminescent_premul";
        try { return modes[mode] || mode.toString(); } catch(e) { return "normal"; }
    }

    function getMaskModeName(mode) {
        try {
            if (mode === MaskMode.ADD) return "add";
            if (mode === MaskMode.SUBTRACT) return "subtract";
            if (mode === MaskMode.INTERSECT) return "intersect";
            if (mode === MaskMode.DIFFERENCE) return "difference";
            return "add";
        } catch(e) { return "unknown"; }
    }

    function getTrackMatteTypeName(type) {
        try {
            if (type === TrackMatteType.ALPHA) return "alpha";
            if (type === TrackMatteType.ALPHA_INVERTED) return "alpha_inverted";
            if (type === TrackMatteType.LUMA) return "luma";
            if (type === TrackMatteType.LUMA_INVERTED) return "luma_inverted";
            return "unknown";
        } catch(e) { return "unknown"; }
    }

    function getInterpolationTypeName(type) {
        try {
            if (type === KeyframeInterpolationType.LINEAR) return "linear";
            if (type === KeyframeInterpolationType.BEZIER) return "bezier";
            if (type === KeyframeInterpolationType.HOLD) return "hold";
            return "unknown";
        } catch(e) { return "unknown"; }
    }

    function getEffectCategory(effectName) {
        var categories = {
            "Particular": "粒子特效", "Saber": "光效", "Optical Flares": "光晕",
            "Element 3D": "3D元素", "Trapcode": "Trapcode系列", "Form": "粒子网格",
            "Color Key": "抠图", "Keylight": "专业抠图", "Luma Key": "亮度抠图",
            "Glow": "发光", "Shine": "扫光", "Deep Glow": "深度发光",
            "Fast Blur": "模糊", "Gaussian Blur": "模糊", "Directional Blur": "模糊",
            "Tint": "色调", "Curves": "曲线", "Levels": "色阶",
            "Hue/Saturation": "色彩", "Color Balance": "色彩",
            "Time Remapping": "时间", "Warp Stabilizer": "稳定",
            "Displacement Map": "置换", "Turbulent Displace": "置换",
            "Drop Shadow": "投影", "Bevel Alpha": "斜面",
            "Slider Control": "控制器", "Checkbox Control": "控制器"
        };
        for (var cat in categories) {
            if (effectName.indexOf(cat) !== -1) return categories[cat];
        }
        return "其他";
    }

    function isPluginEffect(effectName) {
        var plugins = [
            "Particular", "Saber", "Optical Flares", "Element 3D", "Trapcode",
            "Form", "Sound Keys", "Color Finesse", "Magic Bullet", "Red Giant",
            "Boris", "Deep Glow", "Newton", "Lockdown", "Starglow"
        ];
        for (var i = 0; i < plugins.length; i++) {
            if (effectName.indexOf(plugins[i]) !== -1) return true;
        }
        return false;
    }

    // ========================================================================
    // Execute and Output
    // ========================================================================

    var result = deepInspect();
    var jsonStr = JSON.stringify(result);

    // Try to write to result file (for MCP bridge)
    try {
        var resultFile = new File("~/Documents/ae-mcp-bridge/ae_result.json");
        if (resultFile.parent.exists || resultFile.parent.create()) {
            resultFile.open("w");
            resultFile.encoding = "UTF-8";
            resultFile.write(jsonStr);
            resultFile.close();
        }
    } catch(e) {}

    // Also output to console
    try { $.write(jsonStr); } catch(e) {}

})();
