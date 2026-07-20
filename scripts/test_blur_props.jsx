// 测试Fast Blur属性名称
function main() {
    var comp = app.project.items.addComp("Test_Blur", 1080, 1920, 1, 5, 30);
    var layer = comp.layers.addSolid([0.5, 0.5, 0.5], "Test", 1080, 1920, 1);
    
    var blur = layer.property("Effects").addProperty("ADBE Fast Blur");
    var props = [];
    for (var i = 1; i <= blur.numProperties; i++) {
        props.push({name: blur.property(i).name, matchName: blur.property(i).matchName});
    }
    
    comp.remove();
    return JSON.stringify(props);
}

return main();