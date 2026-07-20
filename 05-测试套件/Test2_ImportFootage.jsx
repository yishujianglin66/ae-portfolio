/*
 * 测试2：基础素材导入
 */
(function() {
    app.beginUndoGroup("Test2 - Import Footage");
    
    try {
        var filePath = "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png";
        var file = new File(filePath);
        
        if (!file.exists) {
            alert("❌ 文件不存在：\n" + filePath);
            return;
        }
        
        var importOptions = new ImportOptions(file);
        var footage = app.project.importFile(importOptions);
        
        alert("✅ 测试2成功！\n\n已导入素材：\n" + footage.name + "\n\n素材已添加到项目面板！");
        
    } catch (e) {
        alert("❌ 测试2失败：\n" + e.toString());
    }
    
    app.endUndoGroup();
})();
