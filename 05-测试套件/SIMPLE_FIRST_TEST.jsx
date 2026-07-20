/*
 * 极简测试 1: 创建合成
 */
(function() {
    app.beginUndoGroup("Simple Test - Create Comp");
    
    try {
        var comp = app.project.items.addComp("SIMPLE_TEST_COMP", 1920, 1080, 1, 10, 30);
        comp.bgColor = [0, 0, 0];
        
        alert("✅ 极简测试1成功！\n\n已创建合成: " + comp.name);
    } catch (e) {
        alert("❌ 错误: " + e.toString());
    }
    
    app.endUndoGroup();
})();
