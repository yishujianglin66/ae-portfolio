// aerender测试: 创建合成 + 添加到渲染队列
// 用法: aerender -r this_file.jsx
(function() {
    // 创建新项目
    app.newProject();
    
    // 创建测试合成
    var comp = app.project.items.addComp("AERENDER_TEST", 1920, 1080, 1, 2.0, 30);
    
    // 添加背景
    var bg = comp.layers.addSolid([0.1, 0.1, 0.3], "BG", 1920, 1080, 1);
    
    // 添加动画文字
    var txt = comp.layers.addText("AERENDER OK");
    var doc = txt.property("Source Text").value;
    doc.fontSize = 100;
    doc.fillColor = [1, 0.8, 0.2];
    txt.property("Source Text").setValue(doc);
    
    // Scale动画
    var scl = txt.property("Scale");
    scl.setValueAtTime(0, [0, 0]);
    scl.setValueAtTime(1.0, [100, 100]);
    scl.setValueAtTime(2.0, [120, 120]);
    
    // 位置动画
    var pos = txt.property("Position");
    pos.setValueAtTime(0, [960, 800]);
    pos.setValueAtTime(2.0, [960, 540]);
    
    // 添加到渲染队列
    var rq = app.project.renderQueue.items.add(comp);
    var om = rq.outputModule(1);
    
    // 设置输出路径
    var outPath = "D:/AE-Work/output/advanced_camera/_aerender_test.mp4";
    var outFile = new File(outPath);
    if (outFile.exists) outFile.remove();
    om.file = outFile;
    
    // 尝试应用H.264模板
    try {
        om.applyTemplate("H.264 匹配源 - 高比特率");
    } catch(e) {
        try {
            om.applyTemplate("Lossless");
        } catch(e2) {
            // 默认模板
        }
    }
    
    $.writeln("AERENDER_TEST: comp created, render queued -> " + outPath);
})();
