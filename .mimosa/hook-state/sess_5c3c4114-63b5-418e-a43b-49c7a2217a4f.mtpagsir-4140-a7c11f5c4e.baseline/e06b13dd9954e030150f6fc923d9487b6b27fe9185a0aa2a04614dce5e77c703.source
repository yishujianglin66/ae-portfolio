// setKeyframeEasing.jsx
// 设置指定关键帧的缓动曲线
// Phase 2 扩展 - 14个新MCP工具之一

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function setKeyframeEasing(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (typeof args.layerIndex !== "number") {
            return buildError("E102", "E102: layerIndex 参数必填且必须为数字");
        }
        if (!args.propertyPath) {
            return buildError("E103", "E103: propertyPath 参数必填");
        }
        if (typeof args.keyIndex !== "number") {
            return buildError("E104", "E104: keyIndex 参数必填且必须为数字");
        }
        if (!args.easingType) {
            return buildError("E113", "E113: easingType 参数必填");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        if (!validateLayerIndex(comp, args.layerIndex)) {
            return buildError("E102", "E102: 图层索引无效: " + args.layerIndex);
        }

        var layer = comp.layer(args.layerIndex);

        app.beginUndoGroup("Set Keyframe Easing");

        // 按 "." 分割 propertyPath 逐层访问
        var parts = args.propertyPath.split(".");
        var prop = layer;
        for (var p = 0; p < parts.length; p++) {
            prop = prop.property(parts[p]);
            if (!prop) {
                app.endUndoGroup();
                return buildError("E103", "E103: 属性路径无效: " + args.propertyPath);
            }
        }

        // 验证关键帧
        if (prop.numKeys < 1) {
            app.endUndoGroup();
            return buildError("E104", "E104: 该属性没有关键帧");
        }

        if (args.keyIndex < 1 || args.keyIndex > prop.numKeys) {
            app.endUndoGroup();
            return buildError("E104", "E104: 关键帧索引超出范围: " + args.keyIndex + " (1-" + prop.numKeys + ")");
        }

        // 缓动类型映射到 KeyframeInterpolationType
        // 保留原有逻辑：支持 {speed, influence} 对象与单独的 in/out 类型
        var inType = KeyframeInterpolationType.LINEAR;
        var outType = KeyframeInterpolationType.LINEAR;
        var useBezier = false;

        if (args.easingType === "linear") {
            inType = KeyframeInterpolationType.LINEAR;
            outType = KeyframeInterpolationType.LINEAR;
        } else if (args.easingType === "hold") {
            inType = KeyframeInterpolationType.HOLD;
            outType = KeyframeInterpolationType.HOLD;
        } else if (args.easingType === "easeIn") {
            inType = KeyframeInterpolationType.BEZIER;
            outType = KeyframeInterpolationType.LINEAR;
            useBezier = true;
        } else if (args.easingType === "easeOut") {
            inType = KeyframeInterpolationType.LINEAR;
            outType = KeyframeInterpolationType.BEZIER;
            useBezier = true;
        } else if (args.easingType === "easeInOut") {
            inType = KeyframeInterpolationType.BEZIER;
            outType = KeyframeInterpolationType.BEZIER;
            useBezier = true;
        } else if (args.easingType === "bezier") {
            inType = KeyframeInterpolationType.BEZIER;
            outType = KeyframeInterpolationType.BEZIER;
            useBezier = true;
        }

        prop.setInterpolationTypeAtKey(args.keyIndex, inType, outType);

        // bezier 类型用 KeyframeEase 创建缓动对象
        if (useBezier) {
            var easeIn = args.easeIn || { speed: 0, influence: 33.333 };
            var easeOut = args.easeOut || { speed: 0, influence: 33.333 };
            var inEaseObj = new KeyframeEase(easeIn.speed, easeIn.influence);
            var outEaseObj = new KeyframeEase(easeOut.speed, easeOut.influence);

            // 根据 propertyValueType 创建对应长度的 ease 数组
            var pvt = prop.propertyValueType;
            var inEases = null;
            var outEases = null;
            if (pvt === PropertyValueType.OneD) {
                inEases = [inEaseObj];
                outEases = [outEaseObj];
            } else if (pvt === PropertyValueType.TwoD || pvt === PropertyValueType.TwoD_SPATIAL) {
                inEases = [inEaseObj, inEaseObj];
                outEases = [outEaseObj, outEaseObj];
            } else if (pvt === PropertyValueType.ThreeD || pvt === PropertyValueType.ThreeD_SPATIAL) {
                inEases = [inEaseObj, inEaseObj, inEaseObj];
                outEases = [outEaseObj, outEaseObj, outEaseObj];
            } else {
                inEases = [inEaseObj];
                outEases = [outEaseObj];
            }

            prop.setTemporalEaseAtKey(args.keyIndex, inEases, outEases);
        }

        app.endUndoGroup();

        return buildSuccess({
            message: "缓动设置成功",
            keyIndex: args.keyIndex,
            easingType: args.easingType,
            propertyPath: args.propertyPath
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = setKeyframeEasing(args);
$.write(result);
