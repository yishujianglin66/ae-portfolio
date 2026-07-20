// 超简单测试脚本 - Step 2: 导入素材
// 在After Effects中运行此脚本

app.beginUndoGroup("测试2 - 导入素材");
try {
    var testFile = new File("c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png");
    if (!testFile.exists) {
        alert("❌ 文件不存在！");
        app.endUndoGroup();
        return;
    }
    
    var importOptions = new ImportOptions(testFile);
    var footage = app.project.importFile(importOptions);
    
    alert("✅ 素材导入成功！\n名称：" + footage.name);
} catch(e) {
    alert("❌ 错误：" + e.toString());
}
app.endUndoGroup();
