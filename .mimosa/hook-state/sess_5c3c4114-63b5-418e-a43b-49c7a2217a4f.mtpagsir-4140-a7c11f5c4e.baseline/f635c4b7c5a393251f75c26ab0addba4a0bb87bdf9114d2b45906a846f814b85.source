// addMaskWithShape.jsx
// 向图层添加自定义形状遮罩
// Phase 2 扩展 - 14个新MCP工具之一

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function addMaskWithShape(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (typeof args.layerIndex !== "number") {
            return buildError("E102", "E102: layerIndex 参数必填且必须为数字");
        }
        if (!args.vertices || !args.vertices.length) {
            return buildError("E113", "E113: vertices 参数必填且必须为非空数组");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        if (!validateLayerIndex(comp, args.layerIndex)) {
            return buildError("E102", "E102: 图层索引无效: " + args.layerIndex);
        }

        var layer = comp.layer(args.layerIndex);

        var feather = args.feather || [0, 0];
        var mode = args.mode || "add";
        var opacity = args.opacity !== undefined ? args.opacity : 100;
        var expansion = args.expansion !== undefined ? args.expansion : 0;
        var inverted = args.inverted === true;

        // modeMap 映射字符串到 MaskMode
        var modeMap = {
            "add": MaskMode.ADD,
            "subtract": MaskMode.SUBTRACT,
            "intersect": MaskMode.INTERSECT,
            "difference": MaskMode.DIFFERENCE,
            "lighten": MaskMode.LIGHTEN,
            "darken": MaskMode.DARKEN,
            "none": MaskMode.NONE
        };

        if (!modeMap.hasOwnProperty(mode)) {
            return buildError("E113", "E113: 不支持的遮罩模式: " + mode);
        }

        app.beginUndoGroup("Add Mask With Shape");

        // 添加遮罩
        var mask = layer.Masks.addProperty();
        var shape = new Shape();

        // 遍历 vertices 构造 verts/inTangents/outTangents 数组
        var verts = [];
        var inTangents = [];
        var outTangents = [];
        for (var v = 0; v < args.vertices.length; v++) {
            var vertex = args.vertices[v];
            verts.push([Number(vertex.x), Number(vertex.y)]);
            if (vertex.inTangent) {
                inTangents.push([Number(vertex.inTangent.x), Number(vertex.inTangent.y)]);
            } else {
                inTangents.push([0, 0]);
            }
            if (vertex.outTangent) {
                outTangents.push([Number(vertex.outTangent.x), Number(vertex.outTangent.y)]);
            } else {
                outTangents.push([0, 0]);
            }
        }

        shape.vertices = verts;
        shape.inTangents = inTangents;
        shape.outTangents = outTangents;
        shape.closed = true;

        // 设置遮罩形状
        mask.property("ADBE Mask Shape").setValue(shape);
        mask.maskMode = modeMap[mode];

        // 设置羽化
        try {
            mask.property("ADBE Mask Feather").setValue([Number(feather[0]), Number(feather[1])]);
        } catch (e) {}

        // 设置不透明度
        try {
            mask.property("ADBE Mask Opacity").setValue(Number(opacity));
        } catch (e) {}

        // 设置扩展
        try {
            mask.property("ADBE Mask Expansion").setValue(Number(expansion));
        } catch (e) {}

        // 设置反转
        mask.inverted = inverted;

        var maskIndex = mask.propertyIndex;

        app.endUndoGroup();

        return buildSuccess({
            message: "遮罩添加成功",
            maskIndex: maskIndex,
            mode: mode,
            vertexCount: verts.length,
            feather: feather,
            opacity: opacity,
            expansion: expansion,
            inverted: inverted
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = addMaskWithShape(args);
$.write(result);
