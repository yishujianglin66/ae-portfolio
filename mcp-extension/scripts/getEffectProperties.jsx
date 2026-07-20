// getEffectProperties.jsx
// 获取图层上指定效果的所有属性及当前值
// Phase 2 扩展 - 14个新MCP工具之一

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function getEffectProperties(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (typeof args.layerIndex !== "number") {
            return buildError("E102", "E102: layerIndex 参数必填且必须为数字");
        }
        if (typeof args.effectIndex !== "number") {
            return buildError("E112", "E112: effectIndex 参数必填且必须为数字");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        if (!validateLayerIndex(comp, args.layerIndex)) {
            return buildError("E102", "E102: 图层索引无效: " + args.layerIndex);
        }

        var layer = comp.layer(args.layerIndex);

        // 用 Effects.property 而非 effect()
        var effectsGroup = layer.property("ADBE Effect Parade");
        if (!effectsGroup || args.effectIndex < 1 || args.effectIndex > effectsGroup.numProperties) {
            return buildError("E112", "E112: 效果索引无效: " + args.effectIndex);
        }

        var effect = effectsGroup.property(args.effectIndex);

        // 遍历 1 到 effect.numProperties 收集每个 prop 的信息
        var properties = [];
        for (var p = 1; p <= effect.numProperties; p++) {
            var prop = effect.property(p);
            var propInfo = {
                index: p,
                name: prop.name,
                matchName: prop.matchName,
                propertyType: prop.propertyType.toString(),
                propertyValueType: prop.propertyValueType.toString(),
                hasKeyframes: false,
                keyframeCount: 0,
                value: null,
                canSetValue: prop.canSetValue ? true : false
            };

            // 读取关键帧信息
            try {
                if (prop.numKeys > 0) {
                    propInfo.hasKeyframes = true;
                    propInfo.keyframeCount = prop.numKeys;
                }
            } catch (e) {}

            // 读取 value 时 try-catch
            try {
                if (prop.canSetValue) {
                    propInfo.value = prop.value;
                }
            } catch (e) {
                propInfo.value = null;
            }

            properties.push(propInfo);
        }

        return buildSuccess({
            message: "效果属性获取成功",
            effectName: effect.name,
            matchName: effect.matchName,
            effectIndex: args.effectIndex,
            propertyCount: properties.length,
            properties: properties
        });
    } catch (error) {
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = getEffectProperties(args);
$.write(result);
