/*
 * 极简测试 2: 导入素材
 */
(function() {
    app.beginUndoGroup("Simple Test - Import Footage");
    
    try {
        var filePath = "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png";
        var file = new File(filePath);
        
        if (!file.exists) {
            alert("❌ 文件不存在:\n" + filePath);
            app.endUndoGroup();
            return;
        }
        
        var importOptions = new ImportOptions(file);
        var footage = app.project.importFile(importOptions);
        
        alert("✅ 极简测试2成功！\n\n已导入素材:\n" + footage.name);
    } catch (e) {
        alert("❌ 错误: " + e.toString());
    }
    
    app.endUndoGroup();
})();
