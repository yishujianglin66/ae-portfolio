// 全局公共函数 - 合成和图层操作工具
// 提供 findCompByName / findLayerByName / validateLayerIndex 等公共函数
// 用于消除 16 个 JSX 工具中合成查找逻辑的重复代码（原重复 15 次）

/**
 * 按名称查找合成（不依赖 app.activeItem）
 * @param {string} compName - 合成名称
 * @returns {CompItem|null} 找到的合成对象，未找到返回 null
 */
function findCompByName(compName) {
    // 按名称循环查找合成，不依赖 app.activeItem
    for (var i = 1; i <= app.project.numItems; i++) {
        var item = app.project.item(i);
        if (item instanceof CompItem && item.name === compName) {
            return item;
        }
    }
    return null;
}

/**
 * 按名称查找图层
 * @param {CompItem} comp - 目标合成
 * @param {string} layerName - 图层名称
 * @returns {Layer|null} 找到的图层对象，未找到返回 null
 */
function findLayerByName(comp, layerName) {
    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        if (layer.name === layerName) return layer;
    }
    return null;
}

/**
 * 校验图层索引是否有效（AE 图层索引为 1-based）
 * @param {CompItem} comp - 目标合成
 * @param {number} layerIndex - 图层索引（1-based）
 * @returns {boolean} 索引有效返回 true，否则返回 false
 */
function validateLayerIndex(comp, layerIndex) {
    if (layerIndex < 1 || layerIndex > comp.numLayers) return false;
    return true;
}
