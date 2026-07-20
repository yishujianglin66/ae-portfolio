// listCompositions.jsx
// 列出项目中所有合成的基本信息

#include "_lib/response_utils.jsx"

function listCompositions(args) {
    try {
        if (app.project === null) {
            return buildError("NO_PROJECT", "没有打开的项目");
        }

        var comps = [];

        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem) {
                comps.push({
                    id: item.id,
                    name: item.name,
                    width: item.width,
                    height: item.height,
                    duration: item.duration,
                    frameRate: item.frameRate,
                    pixelAspect: item.pixelAspect,
                    numLayers: item.numLayers,
                    hasVideo: item.hasVideo,
                    hasAudio: item.hasAudio
                });
            }
        }

        return buildSuccess({
            message: "获取合成列表成功",
            totalComps: comps.length,
            compositions: comps
        });
    } catch (error) {
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

var result = listCompositions(args);
$.write(result);
