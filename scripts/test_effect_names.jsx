// 通过菜单添加效果来测试正确名称
function main() {
    var comp = app.project.items.addComp("Test_Effects2", 1080, 1920, 1, 5, 30);
    var layer = comp.layers.addSolid([0.5, 0.5, 0.5], "Test", 1080, 1920, 1);
    
    var results = [];
    
    // 尝试各种常用效果的可能名称
    var testNames = [
        "Glow",
        "ADBE Glow",
        "Glo",
        "Vignette",
        "ADBE Vignette",
        "Vign",
        "Saturation",
        "ADBE Saturation",
        "Sat",
        "Film Grain",
        "ADBE Film Grain",
        "Film",
        "Color Balance",
        "ADBE Color Balance",
        "ColorBal",
        "Fast Blur",
        "ADBE Fast Blur",
        "Blur",
        "Radial Blur",
        "ADBE Radial Blur",
        "Radial",
        "Tile",
        "ADBE Tile",
        "Slider Control",
        "ADBE Slider Control",
        "Slider"
    ];
    
    for (var i = 0; i < testNames.length; i++) {
        try {
            var eff = layer.property("Effects").addProperty(testNames[i]);
            results.push({name: testNames[i], success: true, matchName: eff.matchName});
            eff.remove();
        } catch (e) {
            results.push({name: testNames[i], success: false});
        }
    }
    
    comp.remove();
    return JSON.stringify(results);
}

return main();