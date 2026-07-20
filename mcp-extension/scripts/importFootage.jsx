// importFootage.jsx
// 导入素材文件
// Phase 2 扩展 - 14个新MCP工具之一

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function importFootage(args) {
    try {
        if (!args.filePath) {
            return buildError("E110", "E110: filePath 参数必填");
        }

        var asSequence = args.asSequence === true;

        var file = new File(args.filePath);
        if (!file.exists) {
            return buildError("E110", "E110: 文件不存在: " + args.filePath);
        }

        app.beginUndoGroup("Import Footage");

        var importOptions = new ImportOptions(file);
        importOptions.sequence = asSequence;

        var footage = null;
        try {
            footage = app.project.importFile(importOptions);
        } catch (importErr) {
            app.endUndoGroup();
            return buildError("E110", "E110: 导入素材失败: " + importErr.toString());
        }

        var result = {
            message: "素材导入成功",
            footageName: footage.name,
            filePath: args.filePath,
            asSequence: asSequence
        };

        // 如果指定 compName，添加到合成
        if (args.compName) {
            var comp = findCompByName(args.compName);
            if (comp) {
                var addedLayer = comp.layers.add(footage);
                if (args.position && args.position > 0 && args.position <= comp.numLayers) {
                    addedLayer.moveAfter(comp.layer(args.position));
                }
                result.compName = args.compName;
                result.layerIndex = addedLayer.index;
            } else {
                result.warning = "E101: 目标合成未找到: " + args.compName + "，素材已导入但未添加到合成";
            }
        }

        app.endUndoGroup();

        return buildSuccess(result);
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = importFootage(args);
$.write(result);
