// batchApplySubtitles.jsx
// 批量字幕应用 - 支持 JSON/SRT/ASS 导入、模板批量应用、时间码对齐、多语言、多轨道
// Phase 5-2 扩展 - 文字系统全面升级

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

/**
 * 解析 SRT 时间码为秒
 */
function parseSRTTime(timeStr) {
    try {
        var clean = String(timeStr).replace(',', '.').trim();
        var parts = clean.split(':');
        if (parts.length !== 3) return 0;
        var h = parseFloat(parts[0]) || 0;
        var m = parseFloat(parts[1]) || 0;
        var s = parseFloat(parts[2]) || 0;
        return h * 3600 + m * 60 + s;
    } catch (e) {
        return 0;
    }
}

/**
 * 解析 ASS 时间码为秒
 */
function parseASSTime(timeStr) {
    try {
        var parts = String(timeStr).trim().split(':');
        if (parts.length !== 3) return 0;
        var h = parseFloat(parts[0]) || 0;
        var m = parseFloat(parts[1]) || 0;
        var s = parseFloat(parts[2]) || 0;
        return h * 3600 + m * 60 + s;
    } catch (e) {
        return 0;
    }
}

/**
 * 解析 SRT 内容
 */
function parseSRT(content) {
    var subtitles = [];
    var blocks = content.split(/\r?\n\r?\n/);
    for (var i = 0; i < blocks.length; i++) {
        var lines = blocks[i].split(/\r?\n/);
        if (lines.length < 2) continue;

        var timeLineIndex = -1;
        for (var j = 0; j < lines.length; j++) {
            if (lines[j].indexOf('-->') >= 0) {
                timeLineIndex = j;
                break;
            }
        }
        if (timeLineIndex < 0) continue;

        var timeParts = lines[timeLineIndex].split('-->');
        if (timeParts.length < 2) continue;

        var start = parseSRTTime(timeParts[0]);
        var end = parseSRTTime(timeParts[1]);
        var textLines = [];
        for (var k = timeLineIndex + 1; k < lines.length; k++) {
            if (lines[k]) textLines.push(lines[k]);
        }
        if (textLines.length === 0) continue;

        subtitles.push({
            text: textLines.join('\n'),
            start: start,
            end: end,
            style: "default"
        });
    }
    return subtitles;
}

/**
 * 解析 ASS 内容
 */
function parseASS(content) {
    var subtitles = [];
    var lines = content.split(/\r?\n/);
    var inEvents = false;
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (line === '[Events]') {
            inEvents = true;
            continue;
        }
        if (line.indexOf('[') === 0 && line.lastIndexOf(']') === line.length - 1) {
            inEvents = false;
            continue;
        }
        if (inEvents && line.indexOf('Dialogue:') === 0) {
            var parts = line.substring(9).split(','); // remove "Dialogue:"
            if (parts.length >= 9) {
                var start = parseASSTime(parts[0].trim());
                var end = parseASSTime(parts[1].trim());
                var styleName = parts[2].trim();
                var text = parts.slice(8).join(',').replace(/\{.*?\}/g, '').replace(/\\N/g, '\n').replace(/\\n/g, '\n');
                subtitles.push({
                    text: text,
                    start: start,
                    end: end,
                    style: styleName
                });
            }
        }
    }
    return subtitles;
}

/**
 * 解析 JSON 内容
 */
function parseJSONSubtitles(content) {
    try {
        var data = JSON.parse(content);
        if (!Array.isArray(data)) return [];
        var subtitles = [];
        for (var i = 0; i < data.length; i++) {
            var item = data[i];
            subtitles.push({
                text: String(item.text || ""),
                start: Number(item.start) || 0,
                end: Number(item.end) || 0,
                style: String(item.style || "default")
            });
        }
        return subtitles;
    } catch (e) {
        return [];
    }
}

/**
 * 检测字幕重叠
 */
function detectOverlaps(subtitles) {
    var overlaps = [];
    for (var i = 0; i < subtitles.length; i++) {
        for (var j = i + 1; j < subtitles.length; j++) {
            var a = subtitles[i];
            var b = subtitles[j];
            if (a.start < b.end && a.end > b.start) {
                overlaps.push({
                    indexA: i,
                    indexB: j,
                    startA: a.start,
                    endA: a.end,
                    startB: b.start,
                    endB: b.end
                });
            }
        }
    }
    return overlaps;
}

/**
 * 应用字幕样式到文字图层
 */
function applySubtitleStyle(textLayer, templateType, fontSize) {
    var applied = [];
    try {
        if (templateType === "cyberpunk") {
            try {
                var glowFx = textLayer.Effects.addProperty("ADBE Glo2i");
                glowFx.property("ADBE Glo2i-0001").setValue([0, 1, 1]);
                glowFx.property("ADBE Glo2i-0002").setValue(25);
                applied.push("glow_cyan");
            } catch (e) {}
            try {
                var lsStroke = textLayer.property("ADBE Layer Styles").property("ADBE Stroke");
                lsStroke.property("ADBE Stroke-0001").setValue(true);
                lsStroke.property("ADBE Stroke-0003").setValue([0, 0.5, 0.5]);
                lsStroke.property("ADBE Stroke-0004").setValue(2);
                applied.push("stroke");
            } catch (e) {}
        } else if (templateType === "retro") {
            try {
                var triFx = textLayer.Effects.addProperty("ADBE Tritone");
                triFx.property("ADBE Tritone-0001").setValue([0.2, 0.1, 0.05]);
                triFx.property("ADBE Tritone-0002").setValue([0.6, 0.4, 0.2]);
                triFx.property("ADBE Tritone-0003").setValue([1, 0.9, 0.7]);
                applied.push("tritone");
            } catch (e) {}
            try {
                var shadowFx = textLayer.Effects.addProperty("ADBE Drop Shadow");
                shadowFx.property("ADBE Drop Shadow-0002").setValue([0.1, 0.05, 0]);
                applied.push("shadow");
            } catch (e) {}
        } else if (templateType === "handdrawn") {
            try {
                var reFx = textLayer.Effects.addProperty("ADBE Roughen Edges");
                reFx.property("ADBE Roughen Edges-0002").setValue(3);
                applied.push("roughen");
            } catch (e) {}
        } else if (templateType === "tech") {
            try {
                var techGlow = textLayer.Effects.addProperty("ADBE Glo2i");
                techGlow.property("ADBE Glo2i-0001").setValue([0, 1, 0.5]);
                techGlow.property("ADBE Glo2i-0002").setValue(20);
                applied.push("glow_green");
            } catch (e) {}
        } else if (templateType === "cinematic") {
            try {
                var dsFx = textLayer.Effects.addProperty("ADBE Drop Shadow");
                dsFx.property("ADBE Drop Shadow-0002").setValue([0, 0, 0]);
                dsFx.property("ADBE Drop Shadow-0005").setValue(8);
                dsFx.property("ADBE Drop Shadow-0006").setValue(15);
                applied.push("shadow");
            } catch (e) {}
            try {
                var cgFx = textLayer.Effects.addProperty("ADBE Glo2i");
                cgFx.property("ADBE Glo2i-0001").setValue([1, 1, 0.9]);
                cgFx.property("ADBE Glo2i-0002").setValue(10);
                applied.push("glow_soft");
            } catch (e) {}
        } else if (templateType === "minimal") {
            try {
                var minDs = textLayer.Effects.addProperty("ADBE Drop Shadow");
                minDs.property("ADBE Drop Shadow-0002").setValue([0, 0, 0]);
                minDs.property("ADBE Drop Shadow-0005").setValue(2);
                minDs.property("ADBE Drop Shadow-0006").setValue(4);
                applied.push("shadow_minimal");
            } catch (e) {}
        } else if (templateType === "dynamic") {
            try {
                var dynGlow = textLayer.Effects.addProperty("ADBE Glo2i");
                dynGlow.property("ADBE Glo2i-0001").setValue([1, 0.2, 0]);
                dynGlow.property("ADBE Glo2i-0002").setValue(30);
                applied.push("glow_orange");
            } catch (e) {}
        }
    } catch (e) {}
    return applied;
}

function batchApplySubtitles(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        var templateType = String(args.templateType || "default").toLowerCase();
        var trackIndex = args.trackIndex !== undefined ? Number(args.trackIndex) : 0;
        var importFromFile = args.importFromFile === true || args.importFromFile === "true";
        var filePath = args.filePath || "";
        var fileFormat = String(args.fileFormat || "json").toLowerCase();
        var textLayerOnly = args.textLayerOnly === true || args.textLayerOnly === "true";

        // 获取字幕数据
        var subtitles = [];
        if (importFromFile && filePath) {
            var file = new File(filePath);
            if (!file.exists) {
                return buildError("E105", "E105: 字幕文件不存在: " + filePath);
            }
            file.encoding = "UTF-8";
            file.open("r");
            var content = file.read();
            file.close();

            if (!content) {
                return buildError("E105", "E105: 字幕文件为空");
            }

            // 根据扩展名推断格式
            if (fileFormat === "auto") {
                var ext = String(filePath).toLowerCase();
                if (ext.lastIndexOf(".srt") === ext.length - 4) fileFormat = "srt";
                else if (ext.lastIndexOf(".ass") === ext.length - 4) fileFormat = "ass";
                else fileFormat = "json";
            }

            if (fileFormat === "srt") {
                subtitles = parseSRT(content);
            } else if (fileFormat === "ass") {
                subtitles = parseASS(content);
            } else {
                subtitles = parseJSONSubtitles(content);
            }
        } else if (args.subtitleData && Array.isArray(args.subtitleData)) {
            subtitles = args.subtitleData;
        } else {
            return buildError("E106", "E106: 未提供有效的字幕数据（subtitleData 或 filePath）");
        }

        if (subtitles.length === 0) {
            return buildError("E106", "E106: 未解析到任何字幕条目");
        }

        // 按开始时间排序
        subtitles.sort(function(a, b) { return a.start - b.start; });

        // 检测重叠
        var overlaps = detectOverlaps(subtitles);

        app.beginUndoGroup("Batch Apply Subtitles");

        var createdLayers = [];
        var baseFontSize = 48;
        var basePosY = comp.height * 0.85 - (trackIndex * baseFontSize * 1.8);
        var safeMarginX = comp.width * 0.1;

        // 样式默认值
        var styleColors = {
            "cyberpunk": [0, 1, 1],
            "retro": [1, 0.9, 0.6],
            "handdrawn": [0.2, 0.2, 0.2],
            "tech": [0.8, 1, 0.8],
            "cinematic": [1, 1, 1],
            "minimal": [1, 1, 1],
            "dynamic": [1, 1, 1],
            "default": [1, 1, 1]
        };
        var textColor = styleColors[templateType] || [1, 1, 1];

        for (var i = 0; i < subtitles.length; i++) {
            var sub = subtitles[i];
            var subText = String(sub.text || "");
            var start = Number(sub.start) || 0;
            var end = Number(sub.end) || (start + 2);

            if (end <= start) {
                end = start + 2; // 默认2秒
            }

            // 创建文字图层
            var textLayer = comp.layers.addText(subText);
            textLayer.name = "Sub_" + (i + 1) + "_" + subText.substring(0, 15).replace(/\s/g, "_");

            // 设置入点出点
            try {
                textLayer.inPoint = start;
                textLayer.outPoint = end;
            } catch (e) {}

            // 设置文字属性
            var sourceTextProp = textLayer.property("ADBE Text Properties").property("ADBE Text Document");
            var textDoc = sourceTextProp.value;
            try { textDoc.fontSize = baseFontSize; } catch (e) {}
            try { textDoc.fillColor = [Number(textColor[0]), Number(textColor[1]), Number(textColor[2])]; } catch (e) {}
            try { textDoc.justification = ParagraphJustification.CENTER_JUSTIFY; } catch (e) {}
            sourceTextProp.setValue(textDoc);

            // 计算位置（考虑安全边距与轨道偏移）
            var posX = comp.width / 2;
            var posY = basePosY;
            try {
                textLayer.property("ADBE Transform Group").property("ADBE Position").setValue([posX, posY]);
            } catch (e) {}

            // 应用模板样式
            var appliedStyles = [];
            if (!textLayerOnly) {
                appliedStyles = applySubtitleStyle(textLayer, templateType, baseFontSize);
            }

            createdLayers.push({
                index: textLayer.index,
                name: textLayer.name,
                text: subText,
                start: start,
                end: end,
                stylesApplied: appliedStyles
            });
        }

        app.endUndoGroup();

        return buildSuccess({
            message: "批量字幕应用完成",
            totalCount: subtitles.length,
            createdCount: createdLayers.length,
            templateType: templateType,
            trackIndex: trackIndex,
            format: fileFormat,
            overlapsDetected: overlaps.length,
            overlaps: overlaps,
            layers: createdLayers
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = batchApplySubtitles(args);
$.write(result);
