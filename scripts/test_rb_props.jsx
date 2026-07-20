// 测试Radial Blur属性名称
function main() {
    var comp = app.project.items.addComp("Test_RB", 1080, 1920, 1, 5, 30);
    var layer = comp.layers.addSolid([0.5, 0.5, 0.5], "Test", 1080, 1920, 1);
    
    var rb = layer.property("Effects").addProperty("Radial Blur");
    var props = [];
    for (var i = 1; i <= rb.numProperties; i++) {
        props.push({name: rb.property(i).name, matchName: rb.property(i).matchName});
    }
    
    comp.remove();
    return JSON.stringify(props);
}

return main();