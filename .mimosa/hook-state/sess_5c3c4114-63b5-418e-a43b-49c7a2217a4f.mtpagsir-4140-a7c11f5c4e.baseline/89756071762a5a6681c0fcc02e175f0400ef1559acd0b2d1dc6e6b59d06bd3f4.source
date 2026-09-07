// applyTracker.jsx
// AE 内置追踪系统 - 创建追踪器并应用追踪数据
// Phase 5-1 扩展 - 核心功能补全之一

#include "_lib/response_utils.jsx"
#include "_lib/comp_utils.jsx"

function applyTracker(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "compName 参数必填");
        }
        if (typeof args.layerIndex !== "number") {
            return buildError("E102", "layerIndex 参数必填且必须为数字");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "合成未找到: " + args.compName);
        }

        if (!validateLayerIndex(comp, args.layerIndex)) {
            return buildError("E102", "图层索引无效: " + args.layerIndex);
        }

        var layer = comp.layer(args.layerIndex);

        // 参数解析与默认值
        var trackerType = args.trackerType || "point";
        var validTypes = ["point", "stabilize", "corner_pin", "planar"];
        var typeValid = false;
        for (var i = 0; i < validTypes.length; i++) {
            if (validTypes[i] === trackerType) {
                typeValid = true;
                break;
            }
        }
        if (!typeValid) {
            return buildError("E103", "不支持的追踪类型: " + trackerType);
        }

        var trackRegion = args.trackRegion || [comp.width / 2 - 50, comp.height / 2 - 50, 100, 100];
        var targetLayerIndex = args.targetLayerIndex !== undefined ? Number(args.targetLayerIndex) : null;
        var trackProperties = args.trackProperties || ["position"];
        var applyMode = args.applyMode || "expression";
        var stabilizeAmount = args.stabilizeAmount !== undefined ? Number(args.stabilizeAmount) : 100;
        stabilizeAmount = Math.max(0, Math.min(100, stabilizeAmount));

        // 追踪区域参数（容错处理）
        var regionX = Number(trackRegion[0]) || comp.width / 2 - 50;
        var regionY = Number(trackRegion[1]) || comp.height / 2 - 50;
        var regionW = Number(trackRegion[2]) || 100;
        var regionH = Number(trackRegion[3]) || 100;
        // 确保区域尺寸合理
        regionW = Math.max(10, Math.min(comp.width, regionW));
        regionH = Math.max(10, Math.min(comp.height, regionH));
        regionX = Math.max(0, Math.min(comp.width - regionW, regionX));
        regionY = Math.max(0, Math.min(comp.height - regionH, regionY));

        app.beginUndoGroup("Apply Tracker");

        var tracker = null;
        var trackPoint = null;
        var trackerIndex = -1;
        var appliedProps = [];
        var trackPointsCreated = 0;

        // 创建 Tracker
        try {
            tracker = layer.trackers.addTracker();
            trackerIndex = layer.trackers.length;
            tracker.name = trackerType + "_tracker_" + trackerIndex;
            appliedProps.push("tracker_created");
        } catch (e) {
            app.endUndoGroup();
            return buildError("E201", "创建 Tracker 失败: " + e.toString());
        }

        // 配置 TrackPoint 参数
        try {
            trackPoint = tracker.trackPoint();
            trackPointsCreated = 1;
            var attachX = regionX + regionW / 2;
            var attachY = regionY + regionH / 2;
            trackPoint.attachPoint.setValue([attachX, attachY]);
            trackPoint.featureCenter.setValue([attachX, attachY]);
            trackPoint.featureSize.setValue([regionW, regionH]);
            trackPoint.searchSize.setValue([regionW * 1.5, regionH * 1.5]);
            appliedProps.push("trackPoint_configured");
        } catch (e) {
            appliedProps.push("trackPoint_config_failed:" + e.toString());
        }

        // Corner Pin 模式：创建四角追踪点
        if (trackerType === "corner_pin") {
            try {
                // 已创建1个，再创建3个
                var corners = [
                    [regionX, regionY],
                    [regionX + regionW, regionY],
                    [regionX + regionW, regionY + regionH],
                    [regionX, regionY + regionH]
                ];
                for (var cpIdx = 1; cpIdx < 4; cpIdx++) {
                    var tp = tracker.trackPoint();
                    tp.attachPoint.setValue(corners[cpIdx]);
                    tp.featureCenter.setValue(corners[cpIdx]);
                    tp.featureSize.setValue([regionW * 0.3, regionH * 0.3]);
                    tp.searchSize.setValue([regionW * 0.5, regionH * 0.5]);
                    trackPointsCreated++;
                }
                appliedProps.push("corner_points_created:" + trackPointsCreated);
            } catch (cpErr) {
                appliedProps.push("corner_points_failed:" + cpErr.toString());
            }
        }

        // Planar 追踪模式：创建多点网格（降级为多点追踪）
        if (trackerType === "planar") {
            try {
                var gridCols = 2;
                var gridRows = 2;
                var cellW = regionW / gridCols;
                var cellH = regionH / gridRows;
                for (var py = 0; py < gridRows; py++) {
                    for (var px = 0; px < gridCols; px++) {
                        if (px === 0 && py === 0) continue; // 第一个已创建
                        var tp = tracker.trackPoint();
                        var gx = regionX + cellW * (px + 0.5);
                        var gy = regionY + cellH * (py + 0.5);
                        tp.attachPoint.setValue([gx, gy]);
                        tp.featureCenter.setValue([gx, gy]);
                        tp.featureSize.setValue([cellW * 0.6, cellH * 0.6]);
                        tp.searchSize.setValue([cellW, cellH]);
                        trackPointsCreated++;
                    }
                }
                appliedProps.push("planar_grid_created:" + trackPointsCreated);
            } catch (plErr) {
                appliedProps.push("planar_grid_failed:" + plErr.toString());
            }
        }

        // 应用追踪数据到目标图层
        var targetLayer = null;
        if (targetLayerIndex !== null && validateLayerIndex(comp, targetLayerIndex)) {
            targetLayer = comp.layer(targetLayerIndex);
        }

        var expressionApplied = false;
        var keyframesApplied = false;

        if (targetLayer) {
            if (applyMode === "expression") {
                for (var pIdx = 0; pIdx < trackProperties.length; pIdx++) {
                    var propName = trackProperties[pIdx];
                    var expr = "";
                    var targetProp = null;

                    if (propName === "position") {
                        targetProp = targetLayer.property("ADBE Transform Group").property("ADBE Position");
                        expr = [
                            "var srcLayer = thisComp.layer(" + args.layerIndex + ");",
                            "var tracker = srcLayer.trackers.item(" + trackerIndex + ");",
                            "var tp = tracker.trackPoint(1);",
                            "tp.attachPoint;"
                        ].join("\n");
                    } else if (propName === "rotation") {
                        targetProp = targetLayer.property("ADBE Transform Group").property("ADBE Rotation");
                        expr = [
                            "var srcLayer = thisComp.layer(" + args.layerIndex + ");",
                            "var tracker = srcLayer.trackers.item(" + trackerIndex + ");",
                            "var tp = tracker.trackPoint(1);",
                            "var p1 = tp.attachPoint.valueAtTime(time);",
                            "var p2 = tp.attachPoint.valueAtTime(time + thisComp.frameDuration);",
                            "radiansToDegrees(Math.atan2(p2[1]-p1[1], p2[0]-p1[0]));"
                        ].join("\n");
                    } else if (propName === "scale") {
                        targetProp = targetLayer.property("ADBE Transform Group").property("ADBE Scale");
                        expr = [
                            "var srcLayer = thisComp.layer(" + args.layerIndex + ");",
                            "var tracker = srcLayer.trackers.item(" + trackerIndex + ");",
                            "var tp = tracker.trackPoint(1);",
                            "var fs = tp.featureSize.valueAtTime(time);",
                            "[100 + (fs[0]-100)*0.5, 100 + (fs[1]-100)*0.5];"
                        ].join("\n");
                    } else if (propName === "anchor_point") {
                        targetProp = targetLayer.property("ADBE Transform Group").property("ADBE Anchor Point");
                        expr = [
                            "var srcLayer = thisComp.layer(" + args.layerIndex + ");",
                            "var tracker = srcLayer.trackers.item(" + trackerIndex + ");",
                            "var tp = tracker.trackPoint(1);",
                            "tp.attachPoint;"
                        ].join("\n");
                    }

                    if (targetProp) {
                        try {
                            targetProp.expression = expr;
                            appliedProps.push("expression_" + propName);
                            expressionApplied = true;
                        } catch (exprErr) {
                            appliedProps.push("expression_" + propName + "_failed");
                        }
                    }
                }
            } else if (applyMode === "keyframes") {
                // 提取已有关键帧并应用到目标图层
                try {
                    if (trackPoint && trackPoint.attachPoint.numKeys > 0) {
                        var attachProp = trackPoint.attachPoint;
                        var targetPos = targetLayer.property("ADBE Transform Group").property("ADBE Position");
                        for (var k = 1; k <= attachProp.numKeys; k++) {
                            var kt = attachProp.keyTime(k);
                            var kv = attachProp.keyValue(k);
                            targetPos.setValueAtTime(kt, kv);
                        }
                        keyframesApplied = true;
                        appliedProps.push("keyframes_position");
                    } else {
                        appliedProps.push("keyframes_no_source_keys");
                    }
                } catch (kfErr) {
                    appliedProps.push("keyframes_apply_failed:" + kfErr.toString());
                }
            }
        }

        // 稳定模式：创建反向运动表达式
        if (trackerType === "stabilize") {
            try {
                var posProp = layer.property("ADBE Transform Group").property("ADBE Position");
                var centerX = comp.width / 2;
                var centerY = comp.height / 2;
                var amt = stabilizeAmount / 100;

                var stabilizeExpr = [
                    "var tracker = thisLayer.trackers.item(" + trackerIndex + ");",
                    "var tp = tracker.trackPoint(1);",
                    "var trackPos = tp.attachPoint.valueAtTime(time);",
                    "var center = [" + centerX + ", " + centerY + "];",
                    "var offset = center - trackPos;",
                    "value + offset * " + amt + ";"
                ].join("\n");

                posProp.expression = stabilizeExpr;
                appliedProps.push("stabilize_expression");
                expressionApplied = true;
            } catch (stabErr) {
                appliedProps.push("stabilize_expression_failed:" + stabErr.toString());
            }
        }

        app.endUndoGroup();

        var resultData = {
            trackerType: trackerType,
            trackerIndex: trackerIndex,
            trackerName: tracker ? tracker.name : null,
            trackRegion: [regionX, regionY, regionW, regionH],
            sourceLayerIndex: args.layerIndex,
            targetLayerIndex: targetLayerIndex,
            applyMode: applyMode,
            trackPointsCreated: trackPointsCreated,
            expressionApplied: expressionApplied,
            keyframesApplied: keyframesApplied,
            appliedProps: appliedProps
        };

        return buildSuccess(resultData, { message: "追踪器创建成功" });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", error.toString());
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

var result = applyTracker(args);
$.write(result);
