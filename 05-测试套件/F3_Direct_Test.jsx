// AE测试脚本：直接测试importFootage功能
// 在After Effects中选择 文件 -> 脚本 -> 运行脚本文件... 即可运行

(function() {
    // 测试文件路径
    var testImagePath = "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\test-projects\\2026-07-06-利威尔高燃混剪\\02-素材\\图片素材\\test_image.png";
    var testCompName = "[Main]_利威尔高燃混剪_1920x1080";
    
    alert("开始测试importFootage功能！\n\n测试文件：" + testImagePath);
    
    app.beginUndoGroup("F3测试 - importFootage");
    
    try {
        var results = [];
        
        // === 测试1：检查文件是否存在 ===
        alert("【测试1】检查测试文件是否存在...");
        var file = new File(testImagePath);
        if (!file.exists) {
            alert("❌ 测试文件不存在！请确保路径正确。");
            app.endUndoGroup();
            return;
        }
        alert("✅ 文件存在！");
        results.push("测试1: 文件存在检查 - 成功");
        
        // === 测试2：检查并创建合成 ===
        alert("【测试2】检查并创建测试合成...");
        var testComp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item.name === testCompName && item.typeName === "合成") {
                testComp = item;
                break;
            }
        }
        
        if (!testComp) {
            alert("创建新合成...");
            testComp = app.project.items.addComp(testCompName, 1920, 1080, 1, 30, 29.97);
            testComp.bgColor = [0,0,0]; // 黑色背景
        }
        alert("✅ 合成已准备！");
        results.push("测试2: 合成准备 - 成功");
        
        // === 测试3：导入素材到项目 ===
        alert("【测试3】开始导入素材到项目...");
        var importOptions = new ImportOptions(file);
        if (!importOptions.canImportAs(ImportAsType.FOOTAGE)) {
            alert("❌ 无法导入此文件！");
            app.endUndoGroup();
            return;
        }
        
        var footageItem = app.project.importFile(importOptions);
        if (footageItem) {
            alert("✅ 素材导入项目成功！\n素材名称：" + footageItem.name);
            results.push("测试3: 导入到项目 - 成功");
            
            // === 测试4：添加素材到合成 ===
            alert("【测试4】添加素材到合成...");
            var layer = testComp.layers.add(footageItem);
            if (layer) {
                alert("✅ 素材已添加到合成！");
                results.push("测试4: 添加到合成 - 成功");
            } else {
                results.push("测试4: 添加到合成 - 失败");
            }
        } else {
            results.push("测试3: 导入到项目 - 失败");
        }
        
        app.endUndoGroup();
        
        // === 显示最终结果 ===
        var resultMsg = "=== 测试结果汇总 ===\n\n";
        for (var j = 0; j < results.length; j++) {
            resultMsg += results[j] + "\n";
        }
        resultMsg += "\n✅ 测试完成！";
        alert(resultMsg);
        
    } catch (err) {
        app.endUndoGroup();
        alert("❌ 测试出错！\n\n错误信息：" + err.toString() + "\n行号：" + err.line);
    }
})();
