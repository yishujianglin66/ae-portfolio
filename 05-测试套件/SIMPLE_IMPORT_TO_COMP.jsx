/*
 * 极简测试 3: 导入素材到合成
 */
(function() {
    app.beginUndoGroup("Simple Test - Import to Comp");
    
    try {
        var filePath = "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png";
        var file = new File(filePath);
        
        if (!file.exists) {
            alert("❌ 文件不存在:\n" + filePath);
            app.endUndoGroup();
            return;
        }
        
        // 查找或创建测试合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === "SIMPLE_TEST_COMP") {
                comp = item;
                break;
            }
        }
        
        if (!comp) {
            comp = app.project.items.addComp("SIMPLE_TEST_COMP", 1920, 1080, 1, 10, 30);
        }
        
        // 导入素材
        var importOptions = new ImportOptions(file);
        var footage = app.project.importFile(importOptions);
        
        // 添加到合成
        var layer = comp.layers.add(footage);
        
        // 居中素材
        layer.property("Position").setValue([comp.width/2, comp.height/2]);
        
        alert("✅ 极简测试3成功！\n\n已完成:\n- 导入素材: " + footage.name + "\n- 添加到合成: " + comp.name + "\n- 图层索引: " + layer.index);
    } catch (e) {
        alert("❌ 错误: " + e.toString());
    }
    
    app.endUndoGroup();
})();
