/*
 * 测试3：导入素材并添加到合成
 */
(function() {
    app.beginUndoGroup("Test3 - Import to Comp");
    
    try {
        var filePath = "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png";
        var file = new File(filePath);
        
        if (!file.exists) {
            alert("❌ 文件不存在：\n" + filePath);
            return;
        }
        
        // 找到或创建测试合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === "Test_Comp") {
                comp = item;
                break;
            }
        }
        
        if (!comp) {
            comp = app.project.items.addComp("Test_Comp", 1920, 1080, 1, 10, 30);
        }
        
        // 导入素材
        var importOptions = new ImportOptions(file);
        var footage = app.project.importFile(importOptions);
        
        // 添加到合成
        var layer = comp.layers.add(footage);
        
        alert("✅ 测试3成功！\n\n已完成：\n1. 导入素材: " + footage.name + "\n2. 添加到合成: " + comp.name + "\n3. 图层索引: " + layer.index);
        
    } catch (e) {
        alert("❌ 测试3失败：\n" + e.toString());
    }
    
    app.endUndoGroup();
})();
