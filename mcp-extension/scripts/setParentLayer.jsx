// setParentLayer.jsx
// 设置图层父子关系
// Phase 2 扩展 - 14个新MCP工具之一

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function setParentLayer(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (typeof args.layerIndex !== "number") {
            return buildError("E102", "E102: layerIndex 参数必填且必须为数字");
        }
        if (typeof args.parentIndex !== "number") {
            return buildError("E107", "E107: parentIndex 参数必填且必须为数字");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        if (!validateLayerIndex(comp, args.layerIndex)) {
            return buildError("E102", "E102: 图层索引无效: " + args.layerIndex);
        }

        var layer = comp.layer(args.layerIndex);

        app.beginUndoGroup("Set Parent Layer");

        // parentIndex===0 时取消父子关系
        if (args.parentIndex === 0) {
            layer.parent = null;
            app.endUndoGroup();
            return buildSuccess({
                message: "已取消父子关系",
                layerIndex: args.layerIndex,
                parentIndex: 0
            });
        }

        // 验证图层不能成为自己的父图层
        if (args.parentIndex === args.layerIndex) {
            app.endUndoGroup();
            return buildError("E108", "E108: 图层不能成为自己的父图层");
        }

        // 验证父图层索引有效
        if (!validateLayerIndex(comp, args.parentIndex)) {
            app.endUndoGroup();
            return buildError("E107", "E107: 父图层索引无效: " + args.parentIndex);
        }

        var parentLayer = comp.layer(args.parentIndex);
        layer.parent = parentLayer;

        app.endUndoGroup();

        return buildSuccess({
            message: "父子关系设置成功",
            layerIndex: args.layerIndex,
            parentIndex: args.parentIndex
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = setParentLayer(args);
$.write(result);
