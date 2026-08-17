// 全局公共函数 - 效果参数设置
// 统一的效果设置和关键帧添加
// 用于消除 2 处效果参数设置逻辑的重复代码（settings 遍历 + propertyValueType 分支）

/**
 * 批量应用效果参数设置
 * @param {Effect} effect - 目标效果对象
 * @param {Object} settings - {propName: value} 形式的参数对象
 * @returns {number} 成功应用的参数数量
 */
function applyEffectSettings(effect, settings) {
    // settings 是 {propName: value} 对象
    var applied = 0;
    for (var propName in settings) {
        if (!settings.hasOwnProperty(propName)) continue;
        try {
            var prop = effect.property(propName);
            if (prop) {
                prop.setValue(settings[propName]);
                applied++;
            }
        } catch (e) {
            // 静默忽略无效属性
        }
    }
    return applied;
}

/**
 * 为属性批量添加关键帧
 * @param {Property} prop - 目标属性对象
 * @param {Array} keyframes - 关键帧数组 [{time, value, easing, easeIn, easeOut}]
 * @returns {number} 成功添加的关键帧数量
 */
function addKeyframesToProp(prop, keyframes) {
    // keyframes 是 [{time, value, easing, easeIn, easeOut}] 数组
    var added = 0;
    for (var i = 0; i < keyframes.length; i++) {
        var kf = keyframes[i];
        try {
            prop.setValueAtTime(kf.time, kf.value);
            added++;
            if (kf.easing) {
                applyEasing(prop, prop.nearestKeyIndex(kf.time), kf.easing, kf.easeIn, kf.easeOut);
            }
        } catch (e) {
            // 静默忽略失败关键帧
        }
    }
    return added;
}
