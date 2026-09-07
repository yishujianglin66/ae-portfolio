// addPrecomp.jsx
// 将指定图层预合成为新合成
// Phase 2 扩展 - 14个新MCP工具之一

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function addPrecomp(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (!args.name) {
            return buildError("E113", "E113: name 参数必填");
        }
        if (!args.layerIndices || !args.layerIndices.length) {
            return buildError("E109", "E109: layerIndices 参数必填且必须为非空数组");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        // 验证所有图层索引都有效
        for (var li = 0; li < args.layerIndices.length; li++) {
            var idx = args.layerIndices[li];
            if (!validateLayerIndex(comp, idx)) {
                return buildError("E102", "E102: 图层索引无效: " + idx);
            }
        }

        var moveAllAttributes = args.moveAllAttributes !== false;

        app.beginUndoGroup("Add Precomp");

        // 清除所有图层选中状态
        for (var c = 1; c <= comp.numLayers; c++) {
            comp.layer(c).selected = false;
        }

        // 选中要预合成的图层
        for (var s = 0; s < args.layerIndices.length; s++) {
            comp.layer(args.layerIndices[s]).selected = true;
        }

        // 执行预合成
        var precomp = comp.layers.precompose(args.layerIndices, args.name, moveAllAttributes);

        // 清除所有图层选中状态
        for (var c2 = 1; c2 <= comp.numLayers; c2++) {
            comp.layer(c2).selected = false;
        }

        var precompName = precomp.name;
        var precompDuration = precomp.duration;

        app.endUndoGroup();

        return buildSuccess({
            message: "预合成创建成功",
            precompName: precompName,
            precompDuration: precompDuration,
            sourceLayerCount: args.layerIndices.length
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = addPrecomp(args);
$.write(result);
