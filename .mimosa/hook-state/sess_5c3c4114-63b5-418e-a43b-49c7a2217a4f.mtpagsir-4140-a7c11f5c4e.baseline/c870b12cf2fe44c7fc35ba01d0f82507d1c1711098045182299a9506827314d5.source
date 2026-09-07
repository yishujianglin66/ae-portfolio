// setBlendMode.jsx
// 设置图层混合模式
// Phase 2 扩展 - 14个新MCP工具之一

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function setBlendMode(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (typeof args.layerIndex !== "number") {
            return buildError("E102", "E102: layerIndex 参数必填且必须为数字");
        }
        if (!args.blendMode) {
            return buildError("E105", "E105: blendMode 参数必填");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        if (!validateLayerIndex(comp, args.layerIndex)) {
            return buildError("E102", "E102: 图层索引无效: " + args.layerIndex);
        }

        var layer = comp.layer(args.layerIndex);

        // blendModeMap 映射字符串到 BlendingMode 枚举
        var blendModeMap = {
            "NONE": BlendingMode.NONE,
            "DISSOLVE": BlendingMode.DISSOLVE,
            "MULTIPLY": BlendingMode.MULTIPLY,
            "SCREEN": BlendingMode.SCREEN,
            "OVERLAY": BlendingMode.OVERLAY,
            "SOFT_LIGHT": BlendingMode.SOFT_LIGHT,
            "HARD_LIGHT": BlendingMode.HARD_LIGHT,
            "ADD": BlendingMode.ADD,
            "COLOR_DODGE": BlendingMode.COLOR_DODGE,
            "COLOR_BURN": BlendingMode.COLOR_BURN,
            "DARKEN": BlendingMode.DARKEN,
            "LIGHTEN": BlendingMode.LIGHTEN,
            "DIFFERENCE": BlendingMode.DIFFERENCE,
            "EXCLUSION": BlendingMode.EXCLUSION,
            "HUE": BlendingMode.HUE,
            "SATURATION": BlendingMode.SATURATION,
            "COLOR": BlendingMode.COLOR,
            "LUMINOSITY": BlendingMode.LUMINOSITY
        };

        var modeKey = args.blendMode.toUpperCase();
        if (!blendModeMap.hasOwnProperty(modeKey)) {
            return buildError("E105", "E105: 不支持的混合模式: " + args.blendMode);
        }

        app.beginUndoGroup("Set Blend Mode");
        layer.blendingMode = blendModeMap[modeKey];
        app.endUndoGroup();

        return buildSuccess({
            message: "混合模式设置成功",
            layerIndex: args.layerIndex,
            blendMode: modeKey
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs();
var result = setBlendMode(args);
$.write(result);
