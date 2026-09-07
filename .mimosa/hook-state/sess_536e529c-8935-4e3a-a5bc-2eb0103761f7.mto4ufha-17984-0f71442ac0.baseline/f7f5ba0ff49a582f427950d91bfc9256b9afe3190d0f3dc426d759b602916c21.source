// addTextLayer.jsx
// 在合成中创建文字图层
// Phase 3 扩展 - 6 个新 MCP 工具之一（文字系统）

function addTextLayer(args) {
    try {
        if (!args.compName) {
            return JSON.stringify({ status: "error", message: "E101: compName 参数必填" }, null, 2);
        }
        if (!args.text) {
            return JSON.stringify({ status: "error", message: "E110: text 参数必填" }, null, 2);
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

        // 参数解析
        var name = args.name || null;
        var fontSize = args.fontSize !== undefined ? Number(args.fontSize) : 72;
        var fillColor = args.fillColor || [1, 1, 1];
        var fontFamily = args.fontFamily || "Arial";
        var justification = args.justification || "center";
        var position = args.position || [comp.width / 2, comp.height / 2];

        // justification 映射
        var justMap = {
            "left": ParagraphJustification.LEFT_JUSTIFY,
            "center": ParagraphJustification.CENTER_JUSTIFY,
            "right": ParagraphJustification.RIGHT_JUSTIFY
        };
        if (!justMap.hasOwnProperty(justification)) {
            return JSON.stringify({ status: "error", message: "E111: 不支持的对齐方式: " + justification }, null, 2);
        }

        app.beginUndoGroup("Add Text Layer");

        // 创建文字图层
        var textLayer = comp.layers.addText(String(args.text));

        // 设置图层名称
        if (name) {
            textLayer.name = name;
        }

        // 设置位置
        try {
            textLayer.property("ADBE Transform Group").property("ADBE Position").setValue(
                [Number(position[0]), Number(position[1])]
            );
        } catch (e) {}

        // 通过 TextDocument 设置字体属性
        var sourceTextProp = textLayer.property("ADBE Text Properties").property("ADBE Text Document");
        var textDoc = sourceTextProp.value;

        try { textDoc.fontSize = fontSize; } catch (e) {}
        try { textDoc.fillColor = [Number(fillColor[0]), Number(fillColor[1]), Number(fillColor[2])]; } catch (e) {}
        try { textDoc.font = fontFamily; } catch (e) {}
        try { textDoc.justification = justMap[justification]; } catch (e) {}

        // 应用 TextDocument 回写
        sourceTextProp.setValue(textDoc);

        var finalIndex = textLayer.index;
        var finalName = textLayer.name;

        app.endUndoGroup();

        return JSON.stringify({
            status: "success",
            message: "文字图层创建成功",
            layerIndex: finalIndex,
            layerName: finalName,
            fontSize: fontSize,
            fontFamily: fontFamily,
            justification: justification
        }, null, 2);
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return JSON.stringify({ status: "error", message: "E201: " + error.toString() }, null, 2);
    }
}

#include "_lib/args_loader.jsx"

var args = loadArgs();
var result = addTextLayer(args);
$.write(result);
