// 最小化测试脚本 - 逐步排查问题
var COMP_NAME = "Test_Minimal";
var VIDEO_PATH = "D:/AE-Work/视频素材库/";
var WIDTH = 1080;
var HEIGHT = 1920;
var DURATION = 10;
var FRAME_RATE = 30;

function main() {
    try {
        // 清理旧合成
        for (var i = 1; i <= app.project.numItems; i++) {
            if (app.project.item(i).name === COMP_NAME && app.project.item(i) instanceof CompItem) {
                app.project.item(i).remove();
                break;
            }
        }
        
        // 创建合成
        var comp = app.project.items.addComp(COMP_NAME, WIDTH, HEIGHT, 1, DURATION, FRAME_RATE);
        $.writeln("合成创建成功: " + COMP_NAME);
        
        // 导入素材
        var vinlandFootage = null;
        try {
            var file = new File(VIDEO_PATH + "冰海战记.mp4");
            if (file.exists) {
                vinlandFootage = app.project.importFile(new ImportOptions(file));
                $.writeln("素材导入成功: 冰海战记.mp4");
            } else {
                $.writeln("文件不存在: " + VIDEO_PATH + "冰海战记.mp4");
            }
        } catch (e) {
            $.writeln("导入失败: " + e.toString());
        }
        
        // 创建背景层
        var bgLayer = null;
        if (vinlandFootage) {
            bgLayer = comp.layers.add(vinlandFootage);
        } else {
            bgLayer = comp.layers.addSolid([0.2, 0.3, 0.5], "Background", WIDTH, HEIGHT, 1);
        }
        bgLayer.name = "Background";
        bgLayer.startTime = 0;
        $.writeln("背景层创建成功");
        
        // 创建空对象
        var nullLayer = comp.layers.addNull();
        nullLayer.name = "Controller";
        $.writeln("空对象创建成功");
        
        // 测试 moveAfter
        nullLayer.moveAfter(bgLayer);
        $.writeln("图层顺序调整成功");
        
        return JSON.stringify({
            status: "success",
            layers: comp.numLayers,
            duration: comp.duration
        });
    } catch (e) {
        $.writeln("错误: " + e.toString() + " 行: " + e.line);
        return JSON.stringify({error: e.toString(), line: e.line});
    }
}

return main();