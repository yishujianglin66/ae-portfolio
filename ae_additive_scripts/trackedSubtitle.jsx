// trackedSubtitle.jsx
// 动态追踪字幕 - 支持点追踪、面部追踪、对象追踪、平滑跟随、偏移设置、多目标字幕
// Phase 5-2 扩展 - 文字系统全面升级

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

/**
 * 为单个目标图层创建追踪字幕
 */
function createTrackedSubtitleForTarget(comp, targetLayer, subtitleText, trackType, trackRegion, subtitleOffset, smoothAmount, subtitleStyle, autoOrient) {
    var result = {
        layerIndex: -1,
        layerName: "",
        expressionApplied: false,
        autoOrientApplied: false,
        smoothApplied: false
    };

    // 计算追踪点坐标（目标图层空间）
    var trackX = 0;
    var trackY = 0;
    var useRegion = false;

    if (trackRegion && Array.isArray(trackRegion) && trackRegion.length >= 4) {
        trackX = Number(trackRegion[0]) + Number(trackRegion[2]) / 2;
        trackY = Number(trackRegion[1]) + Number(trackRegion[3]) / 2;
        useRegion = true;
    } else {
        // 尝试获取目标图层源尺寸并取中心
        try {
            var srcWidth = targetLayer.source.width || comp.width;
            var srcHeight = targetLayer.source.height || comp.height;
            trackX = srcWidth / 2;
            trackY = srcHeight / 2;
        } catch (e) {
            trackX = comp.width / 2;
            trackY = comp.height / 2;
        }
    }

    // 偏移量
    var offsetX = subtitleOffset && Array.isArray(subtitleOffset) ? Number(subtitleOffset[0]) : 0;
    var offsetY = subtitleOffset && Array.isArray(subtitleOffset) ? Number(subtitleOffset[1]) : -60;

    // 字幕样式
    var fontSize = subtitleStyle && subtitleStyle.fontSize ? Number(subtitleStyle.fontSize) : 36;
    var textColor = subtitleStyle && subtitleStyle.color ? subtitleStyle.color : [1, 1, 1];
    var outline = subtitleStyle && subtitleStyle.outline === true;

    // 创建文字图层
    var textLayer = comp.layers.addText(String(subtitleText));
    textLayer.name = "Tracked_" + targetLayer.name + "_" + subtitleText.substring(0, 10);

    var sourceTextProp = textLayer.property("ADBE Text Properties").property("ADBE Text Document");
    var textDoc = sourceTextProp.value;
    try { textDoc.fontSize = fontSize; } catch (e) {}
    try { textDoc.fillColor = [Number(textColor[0]), Number(textColor[1]), Number(textColor[2])]; } catch (e) {}
    try { textDoc.justification = ParagraphJustification.CENTER_JUSTIFY; } catch (e) {}
    sourceTextProp.setValue(textDoc);

    // 描边
    if (outline) {
        try {
            var lsStroke = textLayer.property("ADBE Layer Styles").property("ADBE Stroke");
            lsStroke.property("ADBE Stroke-0001").setValue(true);
            lsStroke.property("ADBE Stroke-0002").setValue(1);
            lsStroke.property("ADBE Stroke-0003").setValue([0, 0, 0]);
            lsStroke.property("ADBE Stroke-0004").setValue(2);
            lsStroke.property("ADBE Stroke-0005").setValue(2); // center
        } catch (e) {}
    }

    // 应用追踪表达式
    var posProp = textLayer.property("ADBE Transform Group").property("ADBE Position");

    if (trackType === "manual") {
        // 手动模式：一次性设置位置，不添加表达式
        try {
            var targetPos = targetLayer.property("ADBE Transform Group").property("ADBE Position").value;
            posProp.setValue([targetPos[0] + offsetX, targetPos[1] + offsetY]);
        } catch (e) {
            posProp.setValue([comp.width / 2 + offsetX, comp.height / 2 + offsetY]);
        }
        result.expressionApplied = false;
    } else {
        // 自动追踪模式：添加表达式链接到目标图层
        try {
            var smoothWidth = (smoothAmount / 100) * 1.0; // 0-100 映射到 0-1 秒
            var expr = "";

            if (smoothAmount > 0 && useRegion) {
                expr = 'target = thisComp.layer(' + targetLayer.index + '); ' +
                       'trackPoint = target.toComp([' + trackX + ', ' + trackY + ']); ' +
                       'smoothPos = target.position.smooth(' + smoothWidth + ', 5); ' +
                       'offset = trackPoint - target.toComp([0, 0]); ' +
                       'smoothPos + offset + [' + offsetX + ', ' + offsetY + '];';
                result.smoothApplied = true;
            } else if (smoothAmount > 0) {
                expr = 'target = thisComp.layer(' + targetLayer.index + '); ' +
                       'target.position.smooth(' + smoothWidth + ', 5) + [' + offsetX + ', ' + offsetY + '];';
                result.smoothApplied = true;
            } else if (useRegion) {
                expr = 'target = thisComp.layer(' + targetLayer.index + '); ' +
                       'target.toComp([' + trackX + ', ' + trackY + ']) + [' + offsetX + ', ' + offsetY + '];';
            } else {
                expr = 'target = thisComp.layer(' + targetLayer.index + '); ' +
                       'target.position + [' + offsetX + ', ' + offsetY + '];';
            }

            posProp.expression = expr;
            result.expressionApplied = true;
        } catch (e) {
            // 表达式失败时回退到静态位置
            try {
                var fallbackPos = targetLayer.property("ADBE Transform Group").property("ADBE Position").value;
                posProp.setValue([fallbackPos[0] + offsetX, fallbackPos[1] + offsetY]);
            } catch (e2) {}
        }
    }

    // 自动朝向
    if (autoOrient) {
        try {
            if (trackType !== "manual" && result.expressionApplied) {
                // 使用表达式控制旋转，指向目标
                var rotProp = textLayer.property("ADBE Transform Group").property("ADBE Rotation");
                var rotExpr = 'target = thisComp.layer(' + targetLayer.index + '); ' +
                              'p1 = target.position; ' +
                              'p2 = position; ' +
                              'delta = p1 - p2; ' +
                              'angle = Math.atan2(delta[1], delta[0]); ' +
                              '(angle * 180 / Math.PI) - 90;';
                rotProp.expression = rotExpr;
                result.autoOrientApplied = true;
            } else {
                // 尝试使用 AE 内置沿路径自动朝向（需要位置关键帧）
                textLayer.autoOrient = AutoOrientType.ALONG_PATH;
                result.autoOrientApplied = true;
            }
        } catch (e) {
            result.autoOrientApplied = false;
        }
    }

    result.layerIndex = textLayer.index;
    result.layerName = textLayer.name;
    return result;
}

function trackedSubtitle(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (!args.subtitleText) {
            return buildError("E110", "E110: subtitleText 参数必填");
        }
        if (typeof args.trackLayerIndex !== "number" && !Array.isArray(args.trackLayerIndex)) {
            return buildError("E102", "E102: trackLayerIndex 参数必填且必须为数字或数组");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        var trackType = String(args.trackType || "point").toLowerCase();
        var trackRegion = args.trackRegion || null;
        var subtitleOffset = args.subtitleOffset || [0, -60];
        var smoothAmount = args.smoothAmount !== undefined ? Number(args.smoothAmount) : 0;
        var subtitleStyle = args.subtitleStyle || {};
        var autoOrient = args.autoOrient === true || args.autoOrient === "true";
        var subtitleText = String(args.subtitleText);

        // 支持批量追踪多个目标
        var trackLayerIndices = [];
        if (Array.isArray(args.trackLayerIndex)) {
            trackLayerIndices = args.trackLayerIndex;
        } else {
            trackLayerIndices = [args.trackLayerIndex];
        }

        // 验证所有追踪图层
        for (var li = 0; li < trackLayerIndices.length; li++) {
            if (!validateLayerIndex(comp, trackLayerIndices[li])) {
                return buildError("E102", "E102: 追踪图层索引无效: " + trackLayerIndices[li]);
            }
        }

        app.beginUndoGroup("Create Tracked Subtitle");

        var results = [];
        for (var i = 0; i < trackLayerIndices.length; i++) {
            var targetLayer = comp.layer(trackLayerIndices[i]);
            var res = createTrackedSubtitleForTarget(
                comp, targetLayer, subtitleText, trackType, trackRegion,
                subtitleOffset, smoothAmount, subtitleStyle, autoOrient
            );
            results.push(res);
        }

        app.endUndoGroup();

        return buildSuccess({
            message: "追踪字幕创建成功",
            trackType: trackType,
            trackLayerCount: trackLayerIndices.length,
            autoOrient: autoOrient,
            smoothAmount: smoothAmount,
            results: results
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = trackedSubtitle(args);
$.write(result);
