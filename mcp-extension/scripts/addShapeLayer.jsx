// addShapeLayer.jsx
// 创建带路径的形状图层
// Phase 3 扩展 - 6 个新 MCP 工具之一（形状系统）

function addShapeLayer(args) {
    try {
        if (!args.compName) {
            return JSON.stringify({ status: "error", message: "E101: compName 参数必填" }, null, 2);
        }
        if (!args.shapeType) {
            return JSON.stringify({ status: "error", message: "E112: shapeType 参数必填" }, null, 2);
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

        // 形状类型映射
        var shapeMap = {
            "rectangle": "ADBE Vector Shape - Rect",
            "ellipse": "ADBE Vector Shape - Ellipse",
            "star": "ADBE Vector Shape - Star",
            "polygon": "ADBE Vector Shape - Polystar"
        };
        var shapeType = String(args.shapeType).toLowerCase();
        if (!shapeMap.hasOwnProperty(shapeType)) {
            return JSON.stringify({ status: "error", message: "E112: 不支持的形状类型: " + args.shapeType }, null, 2);
        }

        // 参数解析
        var name = args.name || null;
        var position = args.position || [comp.width / 2, comp.height / 2];
        var size = args.size || [comp.width * 0.5, comp.height * 0.5];
        var fillColor = args.fillColor || [1, 1, 1];
        var strokeColor = args.strokeColor || [0, 0, 0];
        var strokeWidth = args.strokeWidth !== undefined ? Number(args.strokeWidth) : 0;

        app.beginUndoGroup("Add Shape Layer");

        // 创建形状图层
        var shapeLayer = comp.layers.addShape();

        // 设置图层名称
        if (name) {
            shapeLayer.name = name;
        }

        // 添加形状组
        var contents = shapeLayer.property("ADBE Root Vectors Group");
        var shapeGroup = contents.addProperty("ADBE Vector Group");

        // 在组中添加形状路径
        var groupContents = shapeGroup.property("ADBE Vectors Group");
        var shapePath = groupContents.addProperty(shapeMap[shapeType]);

        // 设置形状尺寸（不同形状属性名不同）
        try {
            if (shapeType === "rectangle") {
                shapePath.property("ADBE Vector Rect Size").setValue(
                    [Number(size[0]) / 2, Number(size[1]) / 2]
                );
                shapePath.property("ADBE Vector Rect Position").setValue([0, 0]);
            } else if (shapeType === "ellipse") {
                shapePath.property("ADBE Vector Ellipse Size").setValue(
                    [Number(size[0]), Number(size[1])]
                );
                shapePath.property("ADBE Vector Ellipse Position").setValue([0, 0]);
            } else if (shapeType === "star" || shapeType === "polygon") {
                // Polystar/Star 通用属性
                shapePath.property("ADBE Vector Polystar Size").setValue(
                    [Number(size[0]), Number(size[1])]
                );
                shapePath.property("ADBE Vector Polystar Position").setValue([0, 0]);
                shapePath.property("ADBE Vector Polystar Points").setValue(5);
                if (shapeType === "star") {
                    shapePath.property("ADBE Vector Polystar Inner Radius").setValue(50);
                }
            }
        } catch (e) {}

        // 添加填充
        var fill = groupContents.addProperty("ADBE Vector Graphic - Fill");
        try {
            fill.property("ADBE Vector Fill Color").setValue(
                [Number(fillColor[0]), Number(fillColor[1]), Number(fillColor[2]), 1]
            );
        } catch (e) {}

        // 添加描边（仅当宽度大于 0）
        if (strokeWidth > 0) {
            var stroke = groupContents.addProperty("ADBE Vector Graphic - Stroke");
            try {
                stroke.property("ADBE Vector Stroke Color").setValue(
                    [Number(strokeColor[0]), Number(strokeColor[1]), Number(strokeColor[2]), 1]
                );
                stroke.property("ADBE Vector Stroke Width").setValue(strokeWidth);
            } catch (e) {}
        }

        // 设置图层位置
        try {
            shapeLayer.property("ADBE Transform Group").property("ADBE Position").setValue(
                [Number(position[0]), Number(position[1])]
            );
        } catch (e) {}

        var finalIndex = shapeLayer.index;
        var finalName = shapeLayer.name;

        app.endUndoGroup();

        return JSON.stringify({
            status: "success",
            message: "形状图层创建成功",
            layerIndex: finalIndex,
            layerName: finalName,
            shapeType: shapeType,
            size: size
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

var result = addShapeLayer(args);
$.write(result);
