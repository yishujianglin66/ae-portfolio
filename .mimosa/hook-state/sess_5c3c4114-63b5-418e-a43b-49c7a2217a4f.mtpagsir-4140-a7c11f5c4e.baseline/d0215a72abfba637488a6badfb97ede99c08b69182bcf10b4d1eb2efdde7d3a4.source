// full_analysis.jsx - AE 工程深度分析
// 输出到桌面 aep_full_analysis.json

(function() {
    "use strict";

    if (app.project === null) {
        alert("请先打开一个 AE 项目文件！");
        return;
    }

    var outputFile = new File("~/Desktop/aep_full_analysis.json");

    // JSON polyfill
    function toJson(obj, depth) {
        if (depth === undefined) depth = 0;
        if (depth > 10) return '"..."';
        if (obj === null || obj === undefined) return "null";
        var t = typeof obj;
        if (t === "string") return '"' + obj.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "") + '"';
        if (t === "number" || t === "boolean") return String(obj);
        if (obj instanceof Array) {
            var items = [];
            for (var i = 0; i < obj.length && i < 500; i++) items.push(toJson(obj[i], depth + 1));
            return "[" + items.join(",") + "]";
        }
        var pairs = [];
        for (var k in obj) {
            if (obj.hasOwnProperty(k)) pairs.push('"' + k + '":' + toJson(obj[k], depth + 1));
        }
        return "{" + pairs.join(",") + "}";
    }

    var report = {
        project: {},
        compositions: [],
        effectsByType: {},
        techniques: [],
        stats: { totalComps: 0, totalLayers: 0, totalEffects: 0, totalKeyframes: 0, totalExpressions: 0, totalMasks: 0 }
    };

    report.project.name = app.project.file ? app.project.file.name : "untitled";
    report.project.path = app.project.file ? app.project.file.fsName : "";
    report.project.bitsPerChannel = app.project.bitsPerChannel;
    report.project.numItems = app.project.numItems;

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
                opacity: safeVal(layer.opacity.value),
                parent: null,
                trackMatte: null,
                effects: [],
                masks: [],
                source: null,
                threeD: false,
                transform: {}
            };

            // Parent
            try {
                if (layer.parent) {
                    layerInfo.parent = { index: layer.parent.index, name: layer.parent.name };
                }
            } catch(e) {}

            // Track matte
            try {
                var tm = layer.trackMatteType;
                if (tm === TrackMatteType.ALPHA) layerInfo.trackMatte = "alpha";
                else if (tm === TrackMatteType.ALPHA_INVERTED) layerInfo.trackMatte = "alpha_inverted";
                else if (tm === TrackMatteType.LUMA) layerInfo.trackMatte = "luma";
                else if (tm === TrackMatteType.LUMA_INVERTED) layerInfo.trackMatte = "luma_inverted";
            } catch(e) {}

            // 3D
            try { layerInfo.threeD = layer.threeDLayer; if (layer.threeDLayer) compInfo.has3D = true; } catch(e) {}

            // Transform
            var tProps = ["Position", "Scale", "Rotation", "Opacity"];
            for (var p = 0; p < tProps.length; p++) {
                try {
                    var prop = layer.property(tProps[p]);
                    if (prop && prop.isProperty) {
                        var tInfo = {
                            value: safeVal(prop.value),
                            animated: prop.numKeys > 0,
                            numKeys: prop.numKeys,
                            expression: null
                        };
                        try {
                            if (prop.expression && prop.expression.length > 0) {
                                tInfo.expression = prop.expression;
                                report.stats.totalExpressions++;
                            }
                        } catch(e) {}
                        if (prop.numKeys > 0) report.stats.totalKeyframes += prop.numKeys;
                        layerInfo.transform[tProps[p].toLowerCase()] = tInfo;
                    }
                } catch(e) {}
            }

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
                        paramCount: 0
                    };

                    try {
                        for (var pi = 1; pi <= effect.numProperties; pi++) {
                            var param = effect.property(pi);
                            if (!param || !param.isProperty) continue;
                            effectInfo.paramCount++;
                            if (param.numKeys > 0) report.stats.totalKeyframes += param.numKeys;
                            try {
                                if (param.expression && param.expression.length > 0) report.stats.totalExpressions++;
                            } catch(e) {}
                        }
                    } catch(e) {}

                    layerInfo.effects.push(effectInfo);
                    report.stats.totalEffects++;

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
                        inverted: mask.inverted
                    });
                    report.stats.totalMasks++;
                }
            } catch(e) {}

            // Source
            try {
                if (layer.source) {
                    layerInfo.source = { name: layer.source.name, width: layer.source.width, height: layer.source.height };
                    if (layer.source instanceof CompItem) compInfo.hasPrecomp = true;
                }
            } catch(e) {}

            // Camera
            try { if (layer instanceof CameraLayer) compInfo.hasCamera = true; } catch(e) {}

            compInfo.layers.push(layerInfo);
        }

        report.compositions.push(compInfo);
    }

    // Techniques detection
    var allEffects = [];
    for (var en in report.effectsByType) allEffects.push(en);
    function has(n) { for (var x = 0; x < allEffects.length; x++) if (allEffects[x].indexOf(n) !== -1) return true; return false; }
    if (has("Keylight") || has("Color Key")) report.techniques.push("抠图");
    if (has("Glow")) report.techniques.push("发光");
    if (has("Particular")) report.techniques.push("粒子");
    if (has("Optical Flares")) report.techniques.push("光晕");
    if (has("Curves") || has("Levels") || has("Lumetri")) report.techniques.push("调色");
    if (has("Turbulent Displace")) report.techniques.push("流体置换");
    if (has("Warp Stabilizer")) report.techniques.push("稳定器");
    if (report.stats.totalExpressions > 0) report.techniques.push("表达式动画(" + report.stats.totalExpressions + "个)");

    // Write
    outputFile.open("w");
    outputFile.encoding = "UTF-8";
    outputFile.write(toJson(report));
    outputFile.close();

    alert("分析完成！\n\n" +
        "项目: " + report.project.name + "\n" +
        "合成: " + report.stats.totalComps + "\n" +
        "图层: " + report.stats.totalLayers + "\n" +
        "效果: " + report.stats.totalEffects + "\n" +
        "关键帧: " + report.stats.totalKeyframes + "\n" +
        "表达式: " + report.stats.totalExpressions + "\n\n" +
        "保存到桌面: aep_full_analysis.json");

    // Helpers
    function getLayerType(l) {
        if (l.adjustmentLayer) return "adjustment";
        if (l.nullLayer) return "null";
        try { if (l instanceof CameraLayer) return "camera"; } catch(e) {}
        try { if (l instanceof LightLayer) return "light"; } catch(e) {}
        if (l instanceof ShapeLayer) return "shape";
        if (l instanceof TextLayer) return "text";
        try { if (l.source instanceof CompItem) return "precomp"; } catch(e) {}
        return "footage";
    }
    function getBlendMode(m) {
        try {
            if (m === BlendingMode.NORMAL) return "normal";
            if (m === BlendingMode.MULTIPLY) return "multiply";
            if (m === BlendingMode.SCREEN) return "screen";
            if (m === BlendingMode.ADD) return "add";
            if (m === BlendingMode.OVERLAY) return "overlay";
            if (m === BlendingMode.ALPHA_ADD) return "alpha_add";
            if (m === BlendingMode.COLOR_DODGE) return "color_dodge";
            return "other";
        } catch(e) { return "normal"; }
    }
    function isPlugin(n) {
        var p = ["Particular","Saber","Optical Flares","Element 3D","Trapcode","Form","Deep Glow","Newton","Lockdown","Starglow","Plexus","Mir"];
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
})();
