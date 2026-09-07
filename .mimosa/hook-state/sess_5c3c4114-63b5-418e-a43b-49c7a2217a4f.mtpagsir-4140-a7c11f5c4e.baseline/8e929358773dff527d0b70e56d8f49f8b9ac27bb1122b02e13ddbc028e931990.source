// Phase 2 优化版渲染脚本
var compName = "E2E_VinlandSaga";
var outputPath = "D:/AE-Work/output/E2E_VinlandSaga_Phase2.mp4";

var comp = null;
for (var i = 1; i <= app.project.numItems; i++) {
    if (app.project.item(i).name === compName && app.project.item(i) instanceof CompItem) {
        comp = app.project.item(i); break;
    }
}

if (!comp) {
    return JSON.stringify({error: "Comp not found"});
}

// 设置渲染队列
var rq = app.project.renderQueue.items.add(comp);

// 输出模块设置
var om = rq.outputModule(1);
om.file = new File(outputPath);

// 尝试设置格式为 H.264
var formats = om.getFormats ? om.getFormats() : [];
var foundFormat = false;
for (var f = 0; f < formats.length; f++) {
    if (formats[f].indexOf("H.264") >= 0 || formats[f].indexOf("MP4") >= 0) {
        om.applyTemplate(formats[f]);
        foundFormat = true;
        break;
    }
}

// 开始渲染
rq.render = true;
app.project.renderQueue.render();

return JSON.stringify({
    status: "rendered",
    output: outputPath,
    duration: comp.duration,
    formatSet: foundFormat
});
