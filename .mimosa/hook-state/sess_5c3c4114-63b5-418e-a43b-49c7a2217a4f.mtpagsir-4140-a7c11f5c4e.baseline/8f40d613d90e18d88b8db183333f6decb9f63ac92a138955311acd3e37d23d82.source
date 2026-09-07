// 超简单测试脚本 - Step 1: 创建合成
// 在After Effects中运行此脚本

app.beginUndoGroup("测试1 - 创建合成");
try {
    var comp = app.project.items.addComp("测试合成", 1920, 1080, 1, 30, 29.97);
    comp.bgColor = [0, 0, 0];
    alert("✅ 合成创建成功！\n名称：测试合成\n\n下一步：运行 Step 2 脚本");
} catch(e) {
    alert("❌ 错误：" + e.toString());
}
app.endUndoGroup();
