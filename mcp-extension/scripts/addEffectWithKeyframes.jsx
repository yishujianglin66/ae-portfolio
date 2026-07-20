// addEffectWithKeyframes.jsx
// 向指定图层添加效果并设置关键帧动画
// Phase 2 扩展 - 14个新MCP工具之一

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/effect_utils.jsx"
#include "_lib/response_utils.jsx"

function addEffectWithKeyframes(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (typeof args.layerIndex !== "number") {
            return buildError("E102", "E102: layerIndex 参数必填且必须为数字");
        }
        if (!args.effectMatchName) {
            return buildError("E113", "E113: effectMatchName 参数必填");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        if (!validateLayerIndex(comp, args.layerIndex)) {
            return buildError("E102", "E102: 图层索引无效: " + args.layerIndex);
        }

        var layer = comp.layer(args.layerIndex);

        app.beginUndoGroup("Add Effect With Keyframes");

        // 添加效果
        var effect = layer.Effects.addProperty(args.effectMatchName);
        var effectIndex = effect.propertyIndex;
        var effectName = effect.name;

        // 使用公共库批量应用效果初始参数
        var settings = args.settings || {};
        applyEffectSettings(effect, settings);

        // 设置关键帧（保留原有缓动逻辑：支持 easingType 字段）
        var keyframesAdded = 0;
        var keyframes = args.keyframes || [];
        for (var k = 0; k < keyframes.length; k++) {
            var kf = keyframes[k];
            try {
                var kfProp = effect.property(kf.propertyName);
                if (!kfProp) continue;
                kfProp.setValueAtTime(kf.time, kf.value);

                // 缓动类型映射
                if (kf.easingType && kf.easingType !== "linear") {
                    var kfIndex = kfProp.nearestKeyIndex(kf.time);
                    var inType = KeyframeInterpolationType.BEZIER;
                    var outType = KeyframeInterpolationType.BEZIER;
                    if (kf.easingType === "hold") {
                        inType = KeyframeInterpolationType.HOLD;
                        outType = KeyframeInterpolationType.HOLD;
                    } else if (kf.easingType === "easeIn") {
                        inType = KeyframeInterpolationType.BEZIER;
                        outType = KeyframeInterpolationType.LINEAR;
                    } else if (kf.easingType === "easeOut") {
                        inType = KeyframeInterpolationType.LINEAR;
                        outType = KeyframeInterpolationType.BEZIER;
                    } else if (kf.easingType === "easeInOut" || kf.easingType === "bezier") {
                        inType = KeyframeInterpolationType.BEZIER;
                        outType = KeyframeInterpolationType.BEZIER;
                    }
                    kfProp.setInterpolationTypeAtKey(kfIndex, inType, outType);
                }
                keyframesAdded++;
            } catch (e) {}
        }

        app.endUndoGroup();

        return buildSuccess({
            message: "效果添加成功",
            effectIndex: effectIndex,
            effectName: effectName,
            keyframesAdded: keyframesAdded
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = addEffectWithKeyframes(args);
$.write(result);
