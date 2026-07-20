// 列出所有可用效果名称
function main() {
    var comp = app.project.items.addComp("Test_List", 1080, 1920, 1, 5, 30);
    var layer = comp.layers.addSolid([0.5, 0.5, 0.5], "Test", 1080, 1920, 1);
    
    var effects = [];
    
    // 获取所有可用效果类型
    var availableEffects = app.project.getAvailableEffects();
    for (var i = 0; i < availableEffects.length; i++) {
        effects.push(availableEffects[i]);
    }
    
    comp.remove();
    return JSON.stringify(effects);
}

return main();