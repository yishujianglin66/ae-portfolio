// batchAddEffects.jsx
// 批量向指定图层添加多个效果
// Phase 2 扩展 - 14个新MCP工具之一

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/effect_utils.jsx"
#include "_lib/response_utils.jsx"

function batchAddEffects(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (typeof args.layerIndex !== "number") {
            return buildError("E102", "E102: layerIndex 参数必填且必须为数字");
        }
        if (!args.effects || !args.effects.length) {
            return buildError("E113", "E113: effects 参数必填且必须为数组");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        if (!validateLayerIndex(comp, args.layerIndex)) {
            return buildError("E102", "E102: 图层索引无效: " + args.layerIndex);
        }

        var layer = comp.layer(args.layerIndex);

        app.beginUndoGroup("Batch Add Effects");

        var addedEffects = [];
        for (var e = 0; e < args.effects.length; e++) {
            var effDef = args.effects[e];
            if (!effDef.effectMatchName) continue;
            try {
                var effect = layer.Effects.addProperty(effDef.effectMatchName);

                // 使用公共库批量应用效果参数
                var settings = effDef.settings || {};
                applyEffectSettings(effect, settings);

                addedEffects.push({
                    index: effect.propertyIndex,
                    name: effect.name,
                    matchName: effDef.effectMatchName
                });
            } catch (e3) {}
        }

        app.endUndoGroup();

        return buildSuccess({
            message: "批量添加效果完成",
            addedCount: addedEffects.length,
            addedEffects: addedEffects
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = batchAddEffects(args);
$.write(result);
