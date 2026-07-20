// 测试助手脚本: test_importFootage_helper.jsx
// 用于直接在 After Effects 中测试 importFootage 功能

(function() {
    // 测试用例 1: 基础素材导入
    function testCase1() {
        var args = {
            filePath: "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png",
            asSequence: false
        };
        
        alert("开始测试用例 1: 基础素材导入\n参数:\n" + JSON.stringify(args, null, 2));
        
        try {
            var result = importFootage(args);
            alert("测试用例 1 结果:\n" + result);
            return result;
        } catch (e) {
            alert("测试用例 1 异常:\n" + e.toString());
            return JSON.stringify({ status: "error", message: e.toString() });
        }
    }
    
    // 测试用例 2: 导入素材到合成
    function testCase2() {
        // 先创建一个测试合成
        var comp = app.project.items.addComp("F3测试合成", 1920, 1080, 1, 5, 30);
        
        var args = {
            filePath: "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png",
            compName: "F3测试合成",
            asSequence: false
        };
        
        alert("开始测试用例 2: 导入素材到合成\n参数:\n" + JSON.stringify(args, null, 2));
        
        try {
            var result = importFootage(args);
            alert("测试用例 2 结果:\n" + result);
            return result;
        } catch (e) {
            alert("测试用例 2 异常:\n" + e.toString());
            return JSON.stringify({ status: "error", message: e.toString() });
        }
    }
    
    // 测试用例 3: 序列素材导入
    function testCase3() {
        var args = {
            filePath: "c:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\05-测试套件\\test_resources\\test_image.png",
            compName: "F3测试合成",
            asSequence: true
        };
        
        alert("开始测试用例 3: 序列素材导入\n参数:\n" + JSON.stringify(args, null, 2));
        
        try {
            var result = importFootage(args);
            alert("测试用例 3 结果:\n" + result);
            return result;
        } catch (e) {
            alert("测试用例 3 异常:\n" + e.toString());
            return JSON.stringify({ status: "error", message: e.toString() });
        }
    }
    
    // 测试用例 4: 错误处理 - 文件不存在
    function testCase4() {
        var args = {
            filePath: "c:\\Users\\不存在的文件.png",
            asSequence: false
        };
        
        alert("开始测试用例 4: 文件不存在测试\n参数:\n" + JSON.stringify(args, null, 2));
        
        try {
            var result = importFootage(args);
            alert("测试用例 4 结果:\n" + result);
            return result;
        } catch (e) {
            alert("测试用例 4 异常:\n" + e.toString());
            return JSON.stringify({ status: "error", message: e.toString() });
        }
    }
    
    // 测试用例 5: 错误处理 - 缺少必填参数
    function testCase5() {
        var args = {};
        
        alert("开始测试用例 5: 缺少必填参数\n参数:\n" + JSON.stringify(args, null, 2));
        
        try {
            var result = importFootage(args);
            alert("测试用例 5 结果:\n" + result);
            return result;
        } catch (e) {
            alert("测试用例 5 异常:\n" + e.toString());
            return JSON.stringify({ status: "error", message: e.toString() });
        }
    }
    
    // 主函数
    function main() {
        if (!confirm("这将运行 importFootage.jsx 的测试用例。\n请确保项目已保存。\n\n继续?")) {
            return;
        }
        
        app.beginUndoGroup("importFootage 测试");
        
        var results = [];
        
        try {
            results.push({ test: 1, result: testCase1() });
            results.push({ test: 2, result: testCase2() });
            results.push({ test: 3, result: testCase3() });
            results.push({ test: 4, result: testCase4() });
            results.push({ test: 5, result: testCase5() });
        } finally {
            app.endUndoGroup();
        }
        
        // 显示总结果
        var summary = "测试完成!\n\n";
        for (var i = 0; i < results.length; i++) {
            var r = results[i];
            try {
                var parsed = JSON.parse(r.result);
                summary += "测试 " + r.test + ": " + (parsed.status || "unknown") + "\n";
            } catch (e) {
                summary += "测试 " + r.test + ": 无法解析结果\n";
            }
        }
        alert(summary);
    }
    
    main();
})();
