// MCP 利威尔素材导入脚本
// 一键导入真正的利威尔视频素材到 After Effects

(function() {
    app.beginUndoGroup("MCP 利威尔素材导入");
    
    try {
        // 检查是否有项目打开
        if (app.project.numItems === 0) {
            alert("请先创建一个项目！文件 -> 新建 -> 新建项目");
            return;
        }
        
        // 创建测试合成
        var comp = app.project.items.addComp(
            "利威尔高燃混剪",
            1920, 1080, 1, 30, 29.97
        );
        comp.bgColor = [0, 0, 0];
        
        // 利威尔素材文件夹
        var folderPath = "c:\\Users\\Administrator\\Desktop\\视频剪辑工作流\\利威尔剪辑素材";
        var folder = new Folder(folderPath);
        
        if (!folder.exists) {
            alert("❌ 找不到素材文件夹：\n" + folderPath);
            app.endUndoGroup();
            return;
        }
        
        // 获取所有视频文件
        var files = folder.getFiles("*.mp4");
        var imported = 0;
        
        if (files.length === 0) {
            alert("❌ 在文件夹中没有找到视频文件！");
            app.endUndoGroup();
            return;
        }
        
        // 导入前几个视频素材
        var maxImport = Math.min(files.length, 5); // 先导入前5个
        for (var i = 0; i < maxImport; i++) {
            var file = files[i];
            if (file.exists) {
                var importOptions = new ImportOptions(file);
                if (importOptions.canImportAs(ImportAsType.FOOTAGE)) {
                    var footage = app.project.importFile(importOptions);
                    var layer = comp.layers.add(footage);
                    
                    // 缩放和定位
                    layer.scale.setValue([50, 50]);
                    layer.position.setValue([960, 540]);
                    layer.startTime = i * 2; // 每个间隔2秒
                    
                    imported++;
                }
            }
        }
        
        app.endUndoGroup();
        
        alert("✅ 成功！\n\n导入了 " + imported + " 个利威尔视频素材\n创建了合成：" + comp.name);
        
    } catch (err) {
        app.endUndoGroup();
        alert("❌ 错误：\n" + err.toString());
    }
})();
