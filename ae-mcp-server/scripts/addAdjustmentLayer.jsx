// addAdjustmentLayer.jsx
// 创建调整图层
// Phase 2 扩展 - 14个新MCP工具之一

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function addAdjustmentLayer(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        var name = args.name || "Adjustment Layer";
        var position = args.position !== undefined ? args.position : 1;

        app.beginUndoGroup("Add Adjustment Layer");

        // 用 addSolid 创建黑色固态层
        var adjLayer = comp.layers.addSolid(
            [0, 0, 0],
            name,
            comp.width,
            comp.height,
            comp.pixelAspect,
            comp.duration
        );

        // 设置为调整图层
        adjLayer.adjustmentLayer = true;
        adjLayer.isGuideLayer = false;

        // 设置插入位置
        if (position > 0 && position <= comp.numLayers) {
            adjLayer.moveAfter(comp.layer(position));
        } else if (position <= 0) {
            adjLayer.moveToBeginning();
        }

        var finalIndex = adjLayer.index;

        app.endUndoGroup();

        return buildSuccess({
            message: "调整图层创建成功",
            layerIndex: finalIndex,
            name: name
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs();
var result = addAdjustmentLayer(args);
$.write(result);
