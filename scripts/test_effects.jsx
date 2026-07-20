// 效果名称测试脚本
function main() {
    var comp = app.project.items.addComp("Test_Effects", 1080, 1920, 1, 5, 30);
    var layer = comp.layers.addSolid([0.5, 0.5, 0.5], "Test", 1080, 1920, 1);
    
    var effectsList = [];
    
    // 测试各种效果
    var effectNames = [
        "ADBE Tile",
        "ADBE Glow",
        "ADBE Color Balance",
        "ADBE Vignette",
        "ADBE Saturation",
        "ADBE Fast Blur",
        "ADBE Film Grain",
        "ADBE Radial Blur",
        "ADBE Slider Control"
    ];
    
    for (var i = 0; i < effectNames.length; i++) {
        try {
            var eff = layer.property("Effects").addProperty(effectNames[i]);
            effectsList.push({name: effectNames[i], success: true});
            eff.remove();
        } catch (e) {
            effectsList.push({name: effectNames[i], success: false, error: e.toString()});
        }
    }
    
    comp.remove();
    return JSON.stringify(effectsList);
}

return main();