// enableTimeRemap.jsx
// 启用图层的时间重映射并设置关键帧
// Phase 3 扩展 - 6 个新 MCP 工具之一（时间重映射）

function enableTimeRemap(args) {
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
        var enabled = args.enabled !== false; // 默认 true
        var keyframes = args.keyframes || null;

        app.beginUndoGroup("Enable Time Remap");

        // 启用/禁用时间重映射
        layer.timeRemapEnabled = enabled;
        var timeRemapEnabled = layer.timeRemapEnabled;

        // 如果仅启用（未提供关键帧），返回成功
        if (!enabled) {
            app.endUndoGroup();
            return JSON.stringify({
                status: "success",
                message: "时间重映射已禁用",
                timeRemapEnabled: false,
                keyframesSet: 0
            }, null, 2);
        }

        // 启用后获取时间重映射属性
        var timeRemapProp = null;
        var keyframesSet = 0;
        try {
            timeRemapProp = layer.property("ADBE Time Remapping");
        } catch (e) {
            timeRemapProp = null;
        }

        if (!timeRemapProp) {
            app.endUndoGroup();
            return JSON.stringify({
                status: "error",
                message: "E117: 无法获取时间重映射属性（图层可能不支持，如合成图层需预先启用）"
            }, null, 2);
        }

        // 如果提供了关键帧，则设置关键帧
        if (keyframes && keyframes.length > 0) {
            // 先清除所有现有关键帧
            try {
                while (timeRemapProp.numKeys > 0) {
                    timeRemapProp.removeKey(1);
                }
            } catch (e) {}

            // 设置新关键帧
            for (var k = 0; k < keyframes.length; k++) {
                var kf = keyframes[k];
                var kfTime = Number(kf.time);
                var kfValue = Number(kf.value);
                try {
                    timeRemapProp.setValueAtTime(kfTime, kfValue);
                    keyframesSet++;
                } catch (e) {}
            }
        }

        // 收集当前关键帧信息用于返回
        var keyframeTimes = [];
        try {
            var numKeys = timeRemapProp.numKeys;
            for (var j = 1; j <= numKeys; j++) {
                keyframeTimes.push(timeRemapProp.keyTime(j));
            }
        } catch (e) {}

        app.endUndoGroup();

        return JSON.stringify({
            status: "success",
            message: "时间重映射已启用",
            timeRemapEnabled: timeRemapEnabled,
            keyframesSet: keyframesSet,
            totalKeyframes: keyframeTimes.length,
            keyframeTimes: keyframeTimes
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

var result = enableTimeRemap(args);
$.write(result);
