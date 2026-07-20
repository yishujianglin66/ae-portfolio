// applySaber.jsx
// Video Copilot Saber 集成 - 在图层上应用 Saber 效果
// Phase 4 扩展 - 第三方插件深度集成之一

function applySaber(args) {
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
        var coreThickness = args.coreThickness !== undefined ? Number(args.coreThickness) : 8;
        var glowIntensity = args.glowIntensity !== undefined ? Number(args.glowIntensity) : 80;
        var glowWidth = args.glowWidth !== undefined ? Number(args.glowWidth) : 15;
        var glowColor = args.glowColor || [0.2, 0.8, 1];
        var coreColor = args.coreColor || [1, 1, 1];
        var textGlow = args.textGlow === true || args.textGlow === "true";
        var flickerIntensity = args.flickerIntensity !== undefined ? Number(args.flickerIntensity) : 0;
        var flickerSpeed = args.flickerSpeed !== undefined ? Number(args.flickerSpeed) : 0;

        // 预设类型映射为整数索引
        var presetMap = {
            "energy_sword": 0,
            "neon": 1,
            "ice_fire": 2,
            "electric": 3,
            "laser": 4,
            "glow": 5,
            "trail": 6,
            "plasma": 7
        };
        var presetIndex = -1;
        if (args.presetType && presetMap.hasOwnProperty(String(args.presetType).toLowerCase())) {
            presetIndex = presetMap[String(args.presetType).toLowerCase()];
        }

        app.beginUndoGroup("Apply VC Saber");

        // 尝试多种 matchName 添加 Saber 效果
        var saberFx = null;
        var matchNames = ["VC Saber", "ADBE VC Saber", "ACP VC Saber"];
        for (var m = 0; m < matchNames.length; m++) {
            try {
                saberFx = layer.Effects.addProperty(matchNames[m]);
                if (saberFx) break;
            } catch (e) {}
        }
        if (!saberFx) {
            app.endUndoGroup();
            return JSON.stringify({
                status: "error",
                message: "E201: Video Copilot Saber 效果未安装，matchName 尝试: " + matchNames.join(", ")
            }, null, 2);
        }

        var applied = [];
        var presetApplied = false;

        // 通用属性设置函数（单属性失败不影响整体）
        function setProp(propName, value) {
            try {
                var p = saberFx.property(propName);
                if (p) {
                    p.setValue(value);
                    applied.push(propName);
                }
            } catch (e) {}
        }

        // 设置核心参数（使用 AE 内部属性名）
        if (presetIndex >= 0) {
            setProp("ADBE VC Saber-0001", presetIndex);
            try { saberFx.property("Preset Type").setValue(presetIndex); applied.push("Preset Type"); } catch (e) {}
            presetApplied = true;
        }
        setProp("ADBE VC Saber-0002", coreThickness);
        try { saberFx.property("Core Thickness").setValue(coreThickness); applied.push("Core Thickness"); } catch (e) {}

        setProp("ADBE VC Saber-0003", glowIntensity);
        try { saberFx.property("Glow Intensity").setValue(glowIntensity); applied.push("Glow Intensity"); } catch (e) {}

        setProp("ADBE VC Saber-0004", glowWidth);
        try { saberFx.property("Glow Width").setValue(glowWidth); applied.push("Glow Width"); } catch (e) {}

        try {
            var gc = saberFx.property("ADBE VC Saber-0005");
            if (gc) { gc.setValue(glowColor); applied.push("Glow Color"); }
        } catch (e) {
            try { saberFx.property("Glow Color").setValue(glowColor); applied.push("Glow Color"); } catch (e2) {}
        }

        try {
            var cc = saberFx.property("ADBE VC Saber-0006");
            if (cc) { cc.setValue(coreColor); applied.push("Core Color"); }
        } catch (e) {
            try { saberFx.property("Core Color").setValue(coreColor); applied.push("Core Color"); } catch (e2) {}
        }

        // 文字辉光模式（部分版本支持）
        if (textGlow) {
            try {
                var tg = saberFx.property("Text Mode") || saberFx.property("ADBE VC Saber-0007");
                if (tg) { tg.setValue(true); applied.push("Text Mode"); }
            } catch (e) {}
        }

        // 闪烁参数
        if (flickerIntensity > 0) {
            try {
                var fi = saberFx.property("Flicker Intensity") || saberFx.property("ADBE VC Saber-0008");
                if (fi) { fi.setValue(flickerIntensity); applied.push("Flicker Intensity"); }
            } catch (e) {}
        }
        if (flickerSpeed > 0) {
            try {
                var fs = saberFx.property("Flicker Speed") || saberFx.property("ADBE VC Saber-0009");
                if (fs) { fs.setValue(flickerSpeed); applied.push("Flicker Speed"); }
            } catch (e) {}
        }

        // 应用 .ffx 预设文件（如果提供路径）
        var presetFileApplied = false;
        var presetFileName = "";
        if (args.presetFile) {
            var presetFile = new File(args.presetFile);
            if (presetFile.exists) {
                try {
                    saberFx.applyPreset(presetFile);
                    presetFileApplied = true;
                    presetFileName = presetFile.name;
                    applied.push("FFX Preset: " + presetFileName);
                } catch (e) {}
            }
        }

        var effectIndex = saberFx.propertyIndex;
        var effectName = saberFx.name;

        app.endUndoGroup();

        return JSON.stringify({
            status: "success",
            message: "VC Saber 效果应用成功",
            effectName: effectName,
            effectIndex: effectIndex,
            presetApplied: presetApplied,
            presetType: args.presetType || null,
            presetFileApplied: presetFileApplied,
            presetFileName: presetFileName,
            params: {
                coreThickness: coreThickness,
                glowIntensity: glowIntensity,
                glowWidth: glowWidth,
                glowColor: glowColor,
                coreColor: coreColor,
                textGlow: textGlow,
                flickerIntensity: flickerIntensity,
                flickerSpeed: flickerSpeed
            },
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

var result = applySaber(args);
$.write(result);
