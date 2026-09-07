// setTrackMatte.jsx
// 设置轨道遮罩类型
// Phase 2 扩展 - 14个新MCP工具之一

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function setTrackMatte(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (typeof args.layerIndex !== "number") {
            return buildError("E102", "E102: layerIndex 参数必填且必须为数字");
        }
        if (!args.matteType) {
            return buildError("E106", "E106: matteType 参数必填");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        if (!validateLayerIndex(comp, args.layerIndex)) {
            return buildError("E102", "E102: 图层索引无效: " + args.layerIndex);
        }

        var layer = comp.layer(args.layerIndex);

        // matteMap 映射到 TrackMatteType 枚举
        var matteMap = {
            "NO_TRACK_MATTE": TrackMatteType.NO_TRACK_MATTE,
            "ALPHA_TRACK_MATTE": TrackMatteType.ALPHA_TRACK_MATTE,
            "ALPHA_INVERTED_TRACK_MATTE": TrackMatteType.ALPHA_INVERTED_TRACK_MATTE,
            "LUMA_TRACK_MATTE": TrackMatteType.LUMA_TRACK_MATTE,
            "LUMA_INVERTED_TRACK_MATTE": TrackMatteType.LUMA_INVERTED_TRACK_MATTE
        };

        var matteKey = args.matteType.toUpperCase();
        if (!matteMap.hasOwnProperty(matteKey)) {
            return buildError("E106", "E106: 不支持的轨道遮罩类型: " + args.matteType);
        }

        app.beginUndoGroup("Set Track Matte");
        layer.trackMatteType = matteMap[matteKey];
        app.endUndoGroup();

        return buildSuccess({
            message: "轨道遮罩设置成功",
            layerIndex: args.layerIndex,
            matteType: matteKey
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs();
var result = setTrackMatte(args);
$.write(result);
