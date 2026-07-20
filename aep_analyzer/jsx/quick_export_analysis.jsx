// quick_export_analysis.jsx
// 在 AE 中运行此脚本，将当前项目的完整分析导出到 JSON 文件
// 运行方式：AE 菜单 File > Scripts > Run Script File... > 选择此文件

(function() {
    "use strict";

    // JSON polyfill
    if (typeof JSON === "undefined") {
        JSON = {
            stringify: function(obj) {
                if (obj === null || obj === undefined) return "null";
                if (typeof obj === "string") return '"' + obj.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n") + '"';
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
            }
        };
    }

    if (app.project === null) {
        alert("请先打开一个 AE 项目文件！");
        return;
    }

    // 输出路径
    var outputFile = new File(Folder.myDocuments + "/ae-mcp-bridge/aep_analysis_export.json");
    outputFile.parent.create();

    var report = {
        project: {},
        compositions: [],
        effectsByType: {},
        techniques: [],
        stats: { totalComps: 0, totalLayers: 0, totalEffects: 0, totalKeyframes: 0, totalExpressions: 0, totalMasks: 0 }
    };

    // Project info
    report.project.name = app.project.file ? app.project.file.name : "untitled";
    report.project.path = app.project.file ? app.project.file.fsName : "";
    report.project.bitsPerChannel = app.project.bitsPerChannel;
    report.project.numItems = app.project.numItems;

    // Analyze all compositions
    for (var i = 1; i <= app.project.numItems; i++) {
        var item = app.project.item(i);
        if (!(item instanceof CompItem)) continue;

        report.stats.totalComps++;
        var compInfo = {
            name: item.name,
            width: item.width,
            height: item.height,
            duration: item.duration,
            frameRate: item.frameRate,
            numLayers: item.numLayers,
            has3D: false,
            hasCamera: false,
            hasPrecomp: false,
            layers: []
        };

        for (var li = 1; li <= item.numLayers; li++) {
            var layer = item.layer(li);
            report.stats.totalLayers++;

            var layerInfo = {
                name: layer.name,
                index: layer.index,
                type: getLayerType(layer),
                blendMode: getBlendMode(layer.blendingMode),
                opacity: layer.opacity.value,
                parent: layer.parent ? { index: layer.parent.index, name: layer.parent.name } : null,
                trackMatte: getTrackMatte(layer),
                effects: [],
                masks: [],
                source: getSourceInfo(layer),
                threeD: layer.threeDLayer,
                transform: {}
            };

            // Transform properties
            var props = ["Position", "Scale", "Rotation", "Opacity"];
            for (var p = 0; p < props.length; p++) {
                try {
                    var prop = layer.property(props[p]);
                    if (prop && prop.isProperty) {
                        layerInfo.transform[props[p].toLowerCase()] = {
                            value: safeVal(prop.value),
                            animated: prop.numKeys > 0,
                            numKeys: prop.numKeys,
                            expression: (prop.expression && prop.expression.length > 0) ? prop.expression : null,
                            keyframes: extractKeys(prop)
                        };
                        if (prop.numKeys > 0) report.stats.totalKeyframes += prop.numKeys;
                        if (prop.expression && prop.expression.length > 0) report.stats.totalExpressions++;
                    }
                } catch(e) {}
            }

            if (layer.threeDLayer) compInfo.has3D = true;

            // Effects
            try {
                for (var ei = 1; ei <= layer.Effects.numProperties; ei++) {
                    var effect = layer.Effects.property(ei);
                    if (!effect || effect.isEffectGroup) continue;

                    var effectInfo = {
                        name: effect.name,
                        matchName: effect.matchName,
                        enabled: effect.enabled,
                        isPlugin: isPlugin(effect.name),
                        params: []
                    };

                    for (var pi = 1; pi <= effect.numProperties; pi++) {
                        try {
                            var param = effect.property(pi);
                            if (!param || !param.isProperty) continue;
                            var pInfo = {
                                name: param.name,
                                value: safeVal(param.value),
                                animated: param.numKeys > 0,
                                numKeys: param.numKeys,
                                keyframes: param.numKeys > 0 ? extractKeys(param) : []
                            };
                            if (param.numKeys > 0) report.stats.totalKeyframes += param.numKeys;
                            if (param.expression && param.expression.length > 0) {
                                pInfo.expression = param.expression;
                                report.stats.totalExpressions++;
                            }
                            effectInfo.params.push(pInfo);
                        } catch(e) {}
                    }

                    layerInfo.effects.push(effectInfo);
                    report.stats.totalEffects++;

                    // Track by type
                    if (!report.effectsByType[effect.name]) {
                        report.effectsByType[effect.name] = { count: 0, matchName: effect.matchName, isPlugin: isPlugin(effect.name) };
                    }
                    report.effectsByType[effect.name].count++;
                }
            } catch(e) {}

            // Masks
            try {
                for (var mi = 1; mi <= layer.Masks.numProperties; mi++) {
                    var mask = layer.Masks.property(mi);
                    if (!mask || !mask.isProperty) continue;
                    layerInfo.masks.push({
                        name: mask.name,
                        mode: getMaskMode(mask.maskMode),
                        feather: mask.maskFeather ? mask.maskFeather.value : 0,
                        inverted: mask.inverted
                    });
                    report.stats.totalMasks++;
                }
            } catch(e) {}

            // Check types
            if (layer instanceof CameraLayer) compInfo.hasCamera = true;
            if (layer.source instanceof CompItem) compInfo.hasPrecomp = true;

            compInfo.layers.push(layerInfo);
        }

        report.compositions.push(compInfo);
    }

    // Detect techniques
    var allEffects = [];
    for (var en in report.effectsByType) allEffects.push(en);
    function has(n) { for (var x = 0; x < allEffects.length; x++) if (allEffects[x].indexOf(n) !== -1) return true; return false; }
    if (has("Keylight") || has("Color Key")) report.techniques.push("抠图");
    if (has("Glow")) report.techniques.push("发光");
    if (has("Particular")) report.techniques.push("粒子");
    if (has("Optical Flares")) report.techniques.push("光晕");
    if (has("Curves") || has("Levels") || has("Lumetri")) report.techniques.push("调色");
    if (has("Turbulent Displace")) report.techniques.push("流体置换");
    if (has("Time Remapping")) report.techniques.push("时间重映射");
    if (has("Warp Stabilizer")) report.techniques.push("稳定器");
    if (report.stats.totalExpressions > 0) report.techniques.push("表达式动画(" + report.stats.totalExpressions + "个)");
    if (compInfo.hasCamera && compInfo.has3D) report.techniques.push("3D摄像机");

    // Write output
    var jsonStr = JSON.stringify(report);
    outputFile.open("w");
    outputFile.encoding = "UTF-8";
    outputFile.write(jsonStr);
    outputFile.close();

    alert("分析完成！\n\n" +
        "项目: " + report.project.name + "\n" +
        "合成: " + report.stats.totalComps + "\n" +
        "图层: " + report.stats.totalLayers + "\n" +
        "效果: " + report.stats.totalEffects + "\n" +
        "关键帧: " + report.stats.totalKeyframes + "\n" +
        "表达式: " + report.stats.totalExpressions + "\n\n" +
        "结果已保存到:\n" + outputFile.fsName);

    // === Helper Functions ===
    function getLayerType(l) {
        if (l.adjustmentLayer) return "adjustment";
        if (l.nullLayer) return "null";
        if (l instanceof CameraLayer) return "camera";
        if (l instanceof LightLayer) return "light";
        if (l instanceof ShapeLayer) return "shape";
        if (l instanceof TextLayer) return "text";
        if (l.source instanceof CompItem) return "precomp";
        return "footage";
    }
    function getBlendMode(m) {
        try {
            if (m === BlendingMode.NORMAL) return "normal";
            if (m === BlendingMode.MULTIPLY) return "multiply";
            if (m === BlendingMode.SCREEN) return "screen";
            if (m === BlendingMode.ADD) return "add";
            if (m === BlendingMode.OVERLAY) return "overlay";
            return m.toString();
        } catch(e) { return "normal"; }
    }
    function getTrackMatte(l) {
        try {
            var t = l.trackMatteType;
            if (t === TrackMatteType.NO_TRACK_MATTE) return null;
            if (t === TrackMatteType.ALPHA) return "alpha";
            if (t === TrackMatteType.ALPHA_INVERTED) return "alpha_inverted";
            if (t === TrackMatteType.LUMA) return "luma";
            if (t === TrackMatteType.LUMA_INVERTED) return "luma_inverted";
        } catch(e) {}
        return null;
    }
    function getSourceInfo(l) {
        try {
            if (l.source) return { name: l.source.name, width: l.source.width, height: l.source.height, duration: l.source.duration, path: (l.source.mainSource && l.source.mainSource.file) ? l.source.mainSource.file.fsName : null };
        } catch(e) {}
        return null;
    }
    function getMaskMode(m) {
        try { if (m === MaskMode.ADD) return "add"; if (m === MaskMode.SUBTRACT) return "subtract"; return "add"; } catch(e) { return "unknown"; }
    }
    function isPlugin(n) {
        var p = ["Particular","Saber","Optical Flares","Element 3D","Trapcode","Form","Deep Glow","Newton","Lockdown","Starglow"];
        for (var i = 0; i < p.length; i++) if (n.indexOf(p[i]) !== -1) return true;
        return false;
    }
    function safeVal(v) {
        try {
            if (v instanceof Array) { var r = []; for (var i = 0; i < v.length; i++) r.push(Math.round(v[i]*1000)/1000); return r; }
            if (typeof v === "number") return Math.round(v*1000)/1000;
            return v;
        } catch(e) { return null; }
    }
    function extractKeys(prop) {
        var keys = [];
        var max = Math.min(prop.numKeys, 200);
        for (var k = 1; k <= max; k++) {
            try {
                var kf = { time: prop.keyTime(k), value: safeVal(prop.keyValue(k)) };
                try {
                    var ie = prop.keyInTemporalEase(k);
                    if (ie && ie.length > 0) kf.ease = { speed: ie[0].speed, influence: ie[0].influence };
                } catch(e) {}
                keys.push(kf);
            } catch(e) {}
        }
        return keys;
    }
})();
