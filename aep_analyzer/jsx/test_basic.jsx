// test_basic.jsx - 极简测试脚本
// 在 AE 中运行，测试基本功能

(function() {
    "use strict";

    // 写入桌面
    var outputFile = new File("~/Desktop/ae_test_result.txt");

    outputFile.open("w");
    outputFile.writeln("Script started");

    if (app.project === null) {
        outputFile.writeln("ERROR: No project open");
        outputFile.close();
        alert("请先打开一个 AE 项目文件！");
        return;
    }

    outputFile.writeln("Project: " + (app.project.file ? app.project.file.name : "untitled"));
    outputFile.writeln("Num items: " + app.project.numItems);

    var compCount = 0;
    for (var i = 1; i <= app.project.numItems; i++) {
        var item = app.project.item(i);
        if (item instanceof CompItem) {
            compCount++;
            outputFile.writeln("Comp " + compCount + ": " + item.name + " (" + item.numLayers + " layers)");
        }
    }

    outputFile.writeln("Total comps: " + compCount);
    outputFile.writeln("SUCCESS");
    outputFile.close();

    alert("测试完成！结果已保存到桌面 ae_test_result.txt");
})();
