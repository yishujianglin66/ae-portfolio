// createComposition.jsx
// 创建新的 After Effects 合成

#include "_lib/response_utils.jsx"

function createComposition(args) {
    try {
        if (!args.name) {
            return buildError("E101", "E101: name 参数必填");
        }

        var width = args.width !== undefined ? Number(args.width) : 1920;
        var height = args.height !== undefined ? Number(args.height) : 1080;
        var duration = args.duration !== undefined ? Number(args.duration) : 10;
        var frameRate = args.frameRate !== undefined ? Number(args.frameRate) : 30;
        var pixelAspect = args.pixelAspect !== undefined ? Number(args.pixelAspect) : 1;

        app.beginUndoGroup("Create Composition");

        var comp = app.project.items.addComp(
            String(args.name),
            width,
            height,
            pixelAspect,
            duration,
            frameRate
        );

        var compName = comp.name;
        var compId = comp.id;

        app.endUndoGroup();

        return buildSuccess({
            message: "合成创建成功",
            compName: compName,
            compId: compId,
            width: width,
            height: height,
            duration: duration,
            frameRate: frameRate,
            pixelAspect: pixelAspect
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var argsFile = new File($.fileName.replace(/[^\\\/]*$/, '') + "temp/args.json");
var args = {};
if (argsFile.exists) {
    argsFile.open("r");
    var _content = argsFile.read();
    argsFile.close();
    if (_content) {
        try { args = JSON.parse(_content); } catch (_e) { args = {}; }
    }
}

var result = createComposition(args);
$.write(result);
