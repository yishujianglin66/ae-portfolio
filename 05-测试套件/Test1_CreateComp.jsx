/*
 * 测试1：创建测试合成
 */
(function() {
    app.beginUndoGroup("Test1 - Create Comp");
    
    try {
        var comp = app.project.items.addComp("Test_Comp", 1920, 1080, 1, 10, 30);
        comp.bgColor = [0, 0, 0];
        
        alert("✅ 测试1成功！\n\n已创建合成: " + comp.name + "\n尺寸: 1920x1080\n时长: 10秒\n帧率: 30fps");
        
    } catch (e) {
        alert("❌ 测试1失败：\n" + e.toString());
    }
    
    app.endUndoGroup();
})();
