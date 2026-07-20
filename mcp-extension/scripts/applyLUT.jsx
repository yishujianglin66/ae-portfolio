// applyLUT.jsx
// 对图层应用 LUT（通过 Lumetri Color 效果）
// Phase 3 扩展 - 6 个新 MCP 工具之一（颜色管理）

function applyLUT(args) {
    try {
        if (!args.compName) {
            return JSON.stringify({ status: "error", message: "E101: compName 参数必填" }, null, 2);
        }
        if (typeof args.layerIndex !== "number") {
            return JSON.stringify({ status: "error", message: "E102: layerIndex 参数必填且必须为数字" }, null, 2);
        }
        if (!args.lutPath) {
            return JSON.stringify({ status: "error", message: "E115: lutPath 参数必填" }, null, 2);
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
        var intensity = args.intensity !== undefined ? Number(args.intensity) : 100;

        // 强度范围校验
        if (intensity < 0 || intensity > 100) {
            return JSON.stringify({ status: "error", message: "E116: intensity 必须在 0-100 之间" }, null, 2);
        }

        // 校验 LUT 文件存在
        var lutFile = new File(args.lutPath);
        if (!lutFile.exists) {
            return JSON.stringify({ status: "error", message: "E115: LUT 文件未找到: " + args.lutPath }, null, 2);
        }

        app.beginUndoGroup("Apply LUT");

        // 添加 Lumetri Color 效果
        var effect = layer.Effects.addProperty("ADBE Lumetri");

        // 启用自定义 LUT 模式（设置 "LUT" 属性为 2 表示使用 Custom LUT）
        var lutApplied = false;
        try {
            var lumetri = effect.property("ADBE Lumetri Setup");
            // 将"LUT 选用"切换到"自定义 LUT"选项
            try {
                lumetri.property("ADBE Lumetri LUT Choice").setValue(2);
            } catch (e) {}

            // 设置 LUT 文件路径
            var customLutProp = lumetri.property("ADBE Lumetri Custom LUT File");
            customLutProp.setValue(args.lutPath);
            lutApplied = true;
        } catch (e) {
            // 某些 AE 版本属性路径不同，尝试另一种命名
            try {
                effect.property("ADBE Lumetri Setup").property("ADBE Lumetri Custom LUT File").setValue(args.lutPath);
                lutApplied = true;
            } catch (e2) {
                lutApplied = false;
            }
        }

        // 通过效果的不透明度（效果整体强度）控制 intensity
        // Lumetri 没有直接的 intensity 属性，需要通过添加调整图层或混合处理
        // 这里使用效果的 "Effect Opacity" 属性（部分版本支持）
        if (intensity < 100) {
            try {
                effect.property("ADBE Effect Opacity").setValue(intensity);
            } catch (e) {
                // 若不支持，则使用图层整体不透明度作为近似
                try {
                    layer.property("ADBE Transform Group").property("ADBE Opacity").setValue(intensity);
                } catch (e2) {}
            }
        }

        var effectIndex = effect.propertyIndex;
        var effectName = effect.name;

        app.endUndoGroup();

        return JSON.stringify({
            status: "success",
            message: "LUT 应用成功",
            effectName: effectName,
            effectIndex: effectIndex,
            lutPath: args.lutPath,
            lutApplied: lutApplied,
            intensity: intensity
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

var result = applyLUT(args);
$.write(result);
