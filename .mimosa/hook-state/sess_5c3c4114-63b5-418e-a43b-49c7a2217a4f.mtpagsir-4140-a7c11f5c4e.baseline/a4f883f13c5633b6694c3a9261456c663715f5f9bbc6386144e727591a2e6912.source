/*
 * ==========================================
 * MCP 素材导入功能完整测试套件
 * ==========================================
 * 通过MCP桥接机制进行全自动测试
 */

(function() {
    // 测试结果存储
    var testResults = [];
    
    // 日志函数
    function log(message) {
        $.writeln("[测试] " + message);
    }
    
    function addTestResult(testName, success, details) {
        testResults.push({
            name: testName,
            success: success,
            details: details,
            timestamp: new Date().toLocaleTimeString()
        });
    }
    
    // ==========================================
    // 测试1: 创建测试合成
    // ==========================================
    function test1_CreateComp() {
        log("========== 测试1: 创建测试合成 ==========");
        app.beginUndoGroup("MCP Test 1 - Create Comp");
        
        try {
            var comp = app.project.items.addComp("MCP_Test_Comp", 1920, 1080, 1, 10, 30);
            comp.bgColor = [0, 0, 0];
            
            addTestResult("创建测试合成", true, 
                "✅ 成功创建: " + comp.name + "\n尺寸: 1920x1080\n时长: 10秒\n帧率: 30fps");
            log("✅ 测试1通过");
            
        } catch (e) {
            addTestResult("创建测试合成", false, "❌ 失败: " + e.toString());
            log("❌ 测试1失败: " + e.toString());
        }
        
        app.endUndoGroup();
    }
    
    // ==========================================
    // 测试2: 基础素材导入 (PNG)
    // ==========================================
    function test2_BasicImport() {
        log("\n========== 测试2: 基础素材导入 ==========");
        app.beginUndoGroup("MCP Test 2 - Basic Import");
        
        try {
            var filePath = "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png";
            var file = new File(filePath);
            
            if (!file.exists) {
                addTestResult("基础素材导入", false, "❌ 文件不存在: " + filePath);
                log("❌ 文件不存在");
                app.endUndoGroup();
                return;
            }
            
            var importOptions = new ImportOptions(file);
            var footage = app.project.importFile(importOptions);
            
            addTestResult("基础素材导入", true, 
                "✅ 成功导入: " + footage.name + "\n文件路径: " + filePath);
            log("✅ 测试2通过: 导入了 " + footage.name);
            
        } catch (e) {
            addTestResult("基础素材导入", false, "❌ 失败: " + e.toString());
            log("❌ 测试2失败: " + e.toString());
        }
        
        app.endUndoGroup();
    }
    
    // ==========================================
    // 测试3: 导入素材并添加到合成
    // ==========================================
    function test3_ImportToComp() {
        log("\n========== 测试3: 导入到合成 ==========");
        app.beginUndoGroup("MCP Test 3 - Import to Comp");
        
        try {
            var filePath = "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png";
            var file = new File(filePath);
            
            if (!file.exists) {
                addTestResult("导入到合成", false, "❌ 文件不存在: " + filePath);
                app.endUndoGroup();
                return;
            }
            
            // 找到测试合成
            var comp = null;
            for (var i = 1; i <= app.project.numItems; i++) {
                var item = app.project.item(i);
                if (item instanceof CompItem && item.name === "MCP_Test_Comp") {
                    comp = item;
                    break;
                }
            }
            
            if (!comp) {
                comp = app.project.items.addComp("MCP_Test_Comp", 1920, 1080, 1, 10, 30);
            }
            
            // 导入并添加
            var importOptions = new ImportOptions(file);
            var footage = app.project.importFile(importOptions);
            var layer = comp.layers.add(footage);
            
            // 居中素材
            layer.property("Position").setValue([comp.width/2, comp.height/2]);
            
            addTestResult("导入到合成", true, 
                "✅ 成功\n素材: " + footage.name + "\n合成: " + comp.name + "\n图层索引: " + layer.index);
            log("✅ 测试3通过");
            
        } catch (e) {
            addTestResult("导入到合成", false, "❌ 失败: " + e.toString());
            log("❌ 测试3失败: " + e.toString());
        }
        
        app.endUndoGroup();
    }
    
    // ==========================================
    // 测试4: 错误处理 - 文件不存在
    // ==========================================
    function test4_ErrorHandling_FileNotFound() {
        log("\n========== 测试4: 错误处理 - 文件不存在 ==========");
        app.beginUndoGroup("MCP Test 4 - Error Handling");
        
        try {
            var filePath = "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\non_existent_file.png";
            var file = new File(filePath);
            
            if (file.exists) {
                addTestResult("错误处理测试", false, "❌ 错误：测试文件应该不存在但却存在");
            } else {
                addTestResult("错误处理测试", true, 
                    "✅ 正确检测到文件不存在\n路径: " + filePath + "\n\n这是预期的行为 - 错误处理工作正常!");
                log("✅ 测试4通过: 正确检测到文件不存在");
            }
            
        } catch (e) {
            addTestResult("错误处理测试", false, "❌ 失败: " + e.toString());
            log("❌ 测试4失败: " + e.toString());
        }
        
        app.endUndoGroup();
    }
    
    // ==========================================
    // 显示测试结果
    // ==========================================
    function showResults() {
        var successCount = 0;
        var failCount = 0;
        var report = "==========================================\n";
        report += "    MCP 素材导入功能测试报告\n";
        report += "==========================================\n\n";
        
        for (var i = 0; i < testResults.length; i++) {
            var result = testResults[i];
            report += "【测试" + (i+1) + "】 " + result.name + "\n";
            report += "状态: " + (result.success ? "✅ 通过" : "❌ 失败") + "\n";
            report += "详情:\n" + result.details + "\n";
            report += "时间: " + result.timestamp + "\n";
            report += "------------------------------------------\n\n";
            
            if (result.success) successCount++;
            else failCount++;
        }
        
        report += "==========================================\n";
        report += "总计: " + testResults.length + " 个测试\n";
        report += "✅ 通过: " + successCount + "\n";
        report += "❌ 失败: " + failCount + "\n";
        report += "==========================================\n";
        
        alert(report);
        log(report);
    }
    
    // ==========================================
    // 主函数 - 运行所有测试
    // ==========================================
    function runAllTests() {
        log("\n==========================================");
        log("    开始 MCP 素材导入功能完整测试");
        log("==========================================\n");
        
        // 检查项目是否打开
        if (app.project.file == null) {
            alert("⚠️  请先保存After Effects项目！\n\n测试需要一个已保存的项目。");
            return;
        }
        
        // 运行所有测试
        test1_CreateComp();
        test2_BasicImport();
        test3_ImportToComp();
        test4_ErrorHandling_FileNotFound();
        
        // 显示结果
        showResults();
    }
    
    // 启动测试
    runAllTests();
    
})();
