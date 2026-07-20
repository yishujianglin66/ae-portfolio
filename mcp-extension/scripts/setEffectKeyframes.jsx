// setEffectKeyframes.jsx
// 为已有效果的属性批量设置关键帧
// Phase 2 扩展 - 14个新MCP工具之一

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function setEffectKeyframes(args) {
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
        if (!args.propName) {
            return buildError("E113", "E113: propName 参数必填");
        }
        if (!args.keyframes || !args.keyframes.length) {
            return buildError("E113", "E113: keyframes 参数必填且必须为非空数组");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        if (!validateLayerIndex(comp, args.layerIndex)) {
            return buildError("E102", "E102: 图层索引无效: " + args.layerIndex);
        }

        var layer = comp.layer(args.layerIndex);

        // 用 Effects.property 获取效果
        var effectsGroup = layer.property("ADBE Effect Parade");
        if (!effectsGroup || args.effectIndex < 1 || args.effectIndex > effectsGroup.numProperties) {
            return buildError("E112", "E112: 效果索引无效: " + args.effectIndex);
        }

        var effect = effectsGroup.property(args.effectIndex);
        var prop = effect.property(args.propName);
        if (!prop) {
            return buildError("E113", "E113: 属性无效: " + args.propName);
        }

        // 验证 prop.canSetValue
        if (!prop.canSetValue) {
            return buildError("E113", "E113: 属性不可设置: " + args.propName);
        }

        app.beginUndoGroup("Set Effect Keyframes");

        var keyframesAdded = 0;
        for (var k = 0; k < args.keyframes.length; k++) {
            var kf = args.keyframes[k];
            try {
                // 用 setValueAtTime 设置关键帧
                prop.setValueAtTime(kf.time, kf.value);

                // 缓动类型映射到 KeyframeInterpolationType
                if (kf.easingType && kf.easingType !== "linear") {
                    // 用 nearestKeyIndex 获取索引
                    var kfIndex = prop.nearestKeyIndex(kf.time);
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
                    // 用 setInterpolationTypeAtKey 设置缓动
                    prop.setInterpolationTypeAtKey(kfIndex, inType, outType);
                }
                keyframesAdded++;
            } catch (e) {}
        }

        app.endUndoGroup();

        return buildSuccess({
            message: "效果关键帧设置成功",
            effectName: effect.name,
            propName: args.propName,
            keyframesAdded: keyframesAdded,
            totalRequested: args.keyframes.length
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = setEffectKeyframes(args);
$.write(result);
