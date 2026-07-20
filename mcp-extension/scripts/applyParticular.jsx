// applyParticular.jsx
// Trapcode Particular 集成 - 在图层上应用 Particular 粒子效果
// Phase 4 扩展 - 第三方插件深度集成之二

function applyParticular(args) {
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
        var particlesPerSec = args.particlesPerSec !== undefined ? Number(args.particlesPerSec) : 100;
        var velocity = args.velocity !== undefined ? Number(args.velocity) : 100;
        var velocityRandom = args.velocityRandom !== undefined ? Number(args.velocityRandom) : 20;
        var particleLife = args.particleLife !== undefined ? Number(args.particleLife) : 3;
        var particleSize = args.particleSize !== undefined ? Number(args.particleSize) : 5;
        var sizeRandom = args.sizeRandom !== undefined ? Number(args.sizeRandom) : 50;
        var opacity = args.opacity !== undefined ? Number(args.opacity) : 100;
        var particleColor = args.particleColor || [1, 1, 1];
        var gravity = args.gravity !== undefined ? Number(args.gravity) : 0;
        var windX = args.windX !== undefined ? Number(args.windX) : 0;
        var windY = args.windY !== undefined ? Number(args.windY) : 0;
        var windZ = args.windZ !== undefined ? Number(args.windZ) : 0;
        var airResistance = args.airResistance !== undefined ? Number(args.airResistance) : 0;
        var motionBlur = args.motionBlur === true || args.motionBlur === "true";

        // 发射器类型映射（1-6 整数）
        var emitterTypeMap = {
            "point": 1,
            "box": 2,
            "sphere": 3,
            "grid": 4,
            "light": 5,
            "layer": 6
        };
        var emitterTypeStr = args.emitterType || "point";
        var emitterTypeIdx = emitterTypeMap[String(emitterTypeStr).toLowerCase()] || 1;

        app.beginUndoGroup("Apply Trapcode Particular");

        // 运动模糊（合成 + 图层）
        if (motionBlur) {
            try { comp.motionBlur = true; } catch (e) {}
            try { layer.motionBlur = true; } catch (e) {}
            try { layer.shutterAngle = 360; } catch (e) {}
        }

        // 尝试多种 matchName 添加 Particular 效果
        var partFx = null;
        var matchNames = ["Particular", "Trapcode Particular", "ACP Particular", "RG Particular"];
        var usedMatchName = "";
        for (var m = 0; m < matchNames.length; m++) {
            try {
                partFx = layer.Effects.addProperty(matchNames[m]);
                if (partFx) {
                    usedMatchName = matchNames[m];
                    break;
                }
            } catch (e) {}
        }
        if (!partFx) {
            app.endUndoGroup();
            return JSON.stringify({
                status: "error",
                message: "E201: Trapcode Particular 效果未安装，matchName 尝试: " + matchNames.join(", ")
            }, null, 2);
        }

        var applied = [];

        // 通用属性设置函数（在指定组内设置属性）
        function setProp(group, propName, value) {
            try {
                var p = group.property(propName);
                if (p) {
                    p.setValue(value);
                    applied.push(propName);
                }
            } catch (e) {}
        }

        // === Emitter Group ===
        var emitterGroup = null;
        try { emitterGroup = partFx.property("Emitter"); } catch (e) {}
        if (emitterGroup) {
            try {
                var eType = emitterGroup.property("Emitter Type");
                if (eType) { eType.setValue(emitterTypeIdx); applied.push("Emitter Type"); }
            } catch (e) {}
            setProp(emitterGroup, "Particles/sec", particlesPerSec);
            setProp(emitterGroup, "Velocity", velocity);
            setProp(emitterGroup, "Velocity Random [%]", velocityRandom);
        }

        // === Particle Group ===
        var particleGroup = null;
        try { particleGroup = partFx.property("Particle"); } catch (e) {}
        if (particleGroup) {
            setProp(particleGroup, "Life [sec]", particleLife);
            setProp(particleGroup, "Life Random [%]", 30);
            setProp(particleGroup, "Size", particleSize);
            setProp(particleGroup, "Size Random [%]", sizeRandom);
            setProp(particleGroup, "Opacity", opacity);
            setProp(particleGroup, "Opacity Random [%]", 20);
            try {
                var cp = particleGroup.property("Color");
                if (cp) { cp.setValue(particleColor); applied.push("Color"); }
            } catch (e) {}
        }

        // === Physics Group ===
        var physGroup = null;
        try { physGroup = partFx.property("Physics"); } catch (e) {}
        if (physGroup) {
            setProp(physGroup, "Gravity", gravity);
            try {
                var airGroup = physGroup.property("Air");
                if (airGroup) {
                    setProp(airGroup, "Air Resistance", airResistance);
                    setProp(airGroup, "Wind X", windX);
                    setProp(airGroup, "Wind Y", windY);
                    setProp(airGroup, "Wind Z", windZ);
                }
            } catch (e) {}
        }

        var effectIndex = partFx.propertyIndex;
        var effectName = partFx.name;

        app.endUndoGroup();

        return JSON.stringify({
            status: "success",
            message: "Trapcode Particular 效果应用成功",
            effectName: effectName,
            effectIndex: effectIndex,
            matchName: usedMatchName,
            emitterType: emitterTypeStr,
            emitterTypeIndex: emitterTypeIdx,
            particleCount: particlesPerSec,
            motionBlur: motionBlur,
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

var result = applyParticular(args);
$.write(result);
