// 测试Color Balance属性名称
function main() {
    var comp = app.project.items.addComp("Test_CB", 1080, 1920, 1, 5, 30);
    var layer = comp.layers.addSolid([0.5, 0.5, 0.5], "Test", 1080, 1920, 1);
    
    var cb = layer.property("Effects").addProperty("Color Balance");
    var props = [];
    for (var i = 1; i <= cb.numProperties; i++) {
        props.push({name: cb.property(i).name, matchName: cb.property(i).matchName});
    }
    
    comp.remove();
    return JSON.stringify(props);
}

return main();