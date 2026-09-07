// 全局公共函数 - 关键帧缓动
// 统一的缓动类型映射和应用
// 用于消除 3 处关键帧缓动映射逻辑的重复代码（easingType → KeyframeInterpolationType）

/**
 * 为指定关键帧应用缓动设置
 * 支持 linear / easeIn / easeOut / easeInOut / bezier / hold 六种缓动类型
 * 自动适配 OneD / TwoD / ThreeD 等不同 propertyValueType 的 ease 数组维度
 * @param {Property} prop - 目标属性对象
 * @param {number} keyIndex - 关键帧索引（1-based）
 * @param {string} easingType - 缓动类型：linear/easeIn/easeOut/easeInOut/bezier/hold
 * @param {number} [easeIn] - 缓入影响值（0-100），默认 50
 * @param {number} [easeOut] - 缓出影响值（0-100），默认 50
 */
function applyEasing(prop, keyIndex, easingType, easeIn, easeOut) {
    // easingType: linear/easeIn/easeOut/easeInOut/bezier/hold
    var interpolation;
    switch (String(easingType).toLowerCase()) {
        case "linear":
            interpolation = KeyframeInterpolationType.LINEAR;
            break;
        case "easein":
            interpolation = KeyframeInterpolationType.BEZIER;
            prop.setTemporalEaseAtKey(keyIndex, [new KeyframeEase(0, 100)], prop.propertyValueType === PropertyValueType.TwoD ? [new KeyframeEase(0, 100)] : []);
            return;
        case "easeout":
            interpolation = KeyframeInterpolationType.BEZIER;
            prop.setTemporalEaseAtKey(keyIndex, prop.propertyValueType === PropertyValueType.TwoD ? [new KeyframeEase(0, 100)] : [], [new KeyframeEase(0, 100)]);
            return;
        case "easeinout":
            interpolation = KeyframeInterpolationType.BEZIER;
            var ei = typeof easeIn === "number" ? easeIn : 50;
            var eo = typeof easeOut === "number" ? easeOut : 50;
            prop.setTemporalEaseAtKey(keyIndex, [new KeyframeEase(0, ei)], [new KeyframeEase(0, eo)]);
            return;
        case "hold":
            interpolation = KeyframeInterpolationType.HOLD;
            break;
        case "bezier":
        default:
            interpolation = KeyframeInterpolationType.BEZIER;
            break;
    }
    prop.setInterpolationTypeAtKey(keyIndex, interpolation);

    if (interpolation === KeyframeInterpolationType.BEZIER) {
        var ei = typeof easeIn === "number" ? easeIn : 50;
        var eo = typeof easeOut === "number" ? easeOut : 50;
        var inEase = [new KeyframeEase(0, ei)];
        var outEase = [new KeyframeEase(0, eo)];
        if (prop.propertyValueType === PropertyValueType.TwoD) {
            inEase = [new KeyframeEase(0, ei), new KeyframeEase(0, ei)];
            outEase = [new KeyframeEase(0, eo), new KeyframeEase(0, eo)];
        } else if (prop.propertyValueType === PropertyValueType.ThreeD) {
            inEase = [new KeyframeEase(0, ei), new KeyframeEase(0, ei), new KeyframeEase(0, ei)];
            outEase = [new KeyframeEase(0, eo), new KeyframeEase(0, eo), new KeyframeEase(0, eo)];
        }
        prop.setTemporalEaseAtKey(keyIndex, inEase, outEase);
    }
}
