// addLight.jsx
// 在合成中创建灯光
// Phase 3 扩展 - 6 个新 MCP 工具之一（3D 系统）

function addLight(args) {
    try {
        if (!args.compName) {
            return JSON.stringify({ status: "error", message: "E101: compName 参数必填" }, null, 2);
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

        // 参数解析
        var name = args.name || "Light";
        var lightType = args.lightType || "point";
        var color = args.color || [1, 1, 1];
        var intensity = args.intensity !== undefined ? Number(args.intensity) : 100;
        var position = args.position || [comp.width / 2, comp.height / 2, -500];
        var pointOfInterest = args.pointOfInterest || [comp.width / 2, comp.height / 2, 0];

        // lightType 映射
        var lightTypeMap = {
            "parallel": LightType.PARALLEL,
            "spot": LightType.SPOT,
            "point": LightType.POINT,
            "ambient": LightType.AMBIENT
        };
        if (!lightTypeMap.hasOwnProperty(lightType)) {
            return JSON.stringify({ status: "error", message: "E114: 不支持的灯光类型: " + lightType }, null, 2);
        }

        app.beginUndoGroup("Add Light");

        // 创建灯光 - addLight 接受名称和兴趣点
        var point = [Number(pointOfInterest[0]), Number(pointOfInterest[1]), Number(pointOfInterest[2])];
        var lightLayer = comp.layers.addLight(name, point);

        // 设置灯光类型
        try {
            var lightOptions = lightLayer.property("ADBE Light Options Group");
            lightOptions.property("ADBE Light Type").setValue(lightTypeMap[lightType]);
            // 颜色
            lightOptions.property("ADBE Light Color").setValue(
                [Number(color[0]), Number(color[1]), Number(color[2])]
            );
            // 强度
            lightOptions.property("ADBE Light Intensity").setValue(intensity);
        } catch (e) {}

        // 设置位置（ambient 灯光位置无关紧要，但其他类型需要）
        try {
            lightLayer.property("ADBE Transform Group").property("ADBE Position").setValue(
                [Number(position[0]), Number(position[1]), Number(position[2])]
            );
        } catch (e) {}

        // parallel / spot 需要兴趣点；ambient / point 不需要
        if (lightType === "parallel" || lightType === "spot") {
            try {
                lightLayer.property("ADBE Transform Group").property("ADBE Point of Interest").setValue(
                    [Number(pointOfInterest[0]), Number(pointOfInterest[1]), Number(pointOfInterest[2])]
                );
            } catch (e) {}
        }

        var finalIndex = lightLayer.index;
        var finalName = lightLayer.name;

        app.endUndoGroup();

        return JSON.stringify({
            status: "success",
            message: "灯光创建成功",
            layerIndex: finalIndex,
            lightName: finalName,
            lightType: lightType,
            intensity: intensity,
            color: color,
            position: position,
            pointOfInterest: pointOfInterest
        }, null, 2);
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return JSON.stringify({ status: "error", message: "E201: " + error.toString() }, null, 2);
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

var result = addLight(args);
$.write(result);
