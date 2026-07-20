// setMotionBlur.jsx
// 设置运动模糊
// Phase 2 扩展 - 14个新MCP工具之一

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function setMotionBlur(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (typeof args.enabled !== "boolean") {
            return buildError("E113", "E113: enabled 参数必填且必须为布尔值");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        var shutterAngle = args.shutterAngle !== undefined ? args.shutterAngle : 180;
        var shutterPhase = args.shutterPhase !== undefined ? args.shutterPhase : 0;

        // 验证参数范围
        if (shutterAngle < 0 || shutterAngle > 720) {
            return buildError("E113", "E113: shutterAngle 必须在 0-720 之间");
        }
        if (shutterPhase < -360 || shutterPhase > 360) {
            return buildError("E113", "E113: shutterPhase 必须在 -360 到 360 之间");
        }

        app.beginUndoGroup("Set Motion Blur");

        // 设置合成级别
        comp.motionBlur = args.enabled;
        comp.shutterAngle = shutterAngle;
        comp.shutterPhase = shutterPhase;

        // layerIndex>0 时设置图层级别
        var layerSet = false;
        if (args.layerIndex && args.layerIndex > 0) {
            if (validateLayerIndex(comp, args.layerIndex)) {
                var layer = comp.layer(args.layerIndex);
                layer.motionBlur = args.enabled;
                layerSet = true;
            }
        }

        app.endUndoGroup();

        return buildSuccess({
            message: "运动模糊设置成功",
            compMotionBlur: args.enabled,
            shutterAngle: shutterAngle,
            shutterPhase: shutterPhase,
            layerMotionBlurSet: layerSet,
            layerIndex: args.layerIndex || 0
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = setMotionBlur(args);
$.write(result);
