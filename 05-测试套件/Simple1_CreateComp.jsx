// 最简单的测试脚本 v1.0 - 创建合成
// 兼容性最高的版本

var compName = "测试合成";
var comp = app.project.items.addComp(compName, 1920, 1080, 1, 30, 29.97);
comp.bgColor = [0, 0, 0];
alert("成功！\n\n已创建合成：" + compName);
