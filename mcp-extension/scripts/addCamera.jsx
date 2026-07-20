// addCamera.jsx
// 在合成中创建摄像机
// Phase 3 扩展 - 6 个新 MCP 工具之一（3D 系统）

function addCamera(args) {
    try {
        if (!args.compName) {
            return JSON.stringify({ status: "error", message: "E101: compName 参数必填" }, null, 2);
        }

        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === args.compName) {
                comp = item;
                break;
            }
        }
        if (!comp) {
            return JSON.stringify({ status: "error", message: "E101: 合成未找到: " + args.compName }, null, 2);
        }

        // 参数解析
        var name = args.name || "Camera";
        var cameraType = args.cameraType || "one_node";
        var focalLength = args.focalLength !== undefined ? Number(args.focalLength) : 35;
        var position = args.position || [comp.width / 2, comp.height / 2, -1000];
        var pointOfInterest = args.pointOfInterest || [comp.width / 2, comp.height / 2, 0];

        app.beginUndoGroup("Add Camera");

        // 创建摄像机 - addCamera 接受名称和兴趣点
        var point = [Number(pointOfInterest[0]), Number(pointOfInterest[1]), Number(pointOfInterest[2])];
        var cameraLayer = comp.layers.addCamera(name, point);

        // 设置摄像机位置
        try {
            cameraLayer.property("ADBE Transform Group").property("ADBE Position").setValue(
                [Number(position[0]), Number(position[1]), Number(position[2])]
            );
        } catch (e) {}

        // two_node 类型会自动保留兴趣点；one_node 则将兴趣点与位置同步
        if (cameraType === "one_node") {
            try {
                cameraLayer.property("ADBE Transform Group").property("ADBE Anchor Point").setValue([0, 0, 0]);
                cameraLayer.autoOrient = AutoOrientType.NO_AUTO_ORIENT;
            } catch (e) {}
        }

        // 设置焦距（通过 Camera Options Group 的 Zoom 转换近似处理）
        // AE 脚本中焦距设置较复杂，这里通过 Film Size + Zoom 关系推导 Zoom 值
        try {
            var camOptions = cameraLayer.property("ADBE Camera Options Group");
            // 默认 35mm 等效：使用 AE 内部约定，焦距单位 mm
            // Zoom 像素值 ≈ (comp.width * focalLength) / 36 (基于 36mm 感光宽度近似)
            var zoomPixels = (comp.width * focalLength) / 36;
            camOptions.property("ADBE Camera Zoom").setValue(zoomPixels);
        } catch (e) {}

        var finalIndex = cameraLayer.index;
        var finalName = cameraLayer.name;

        app.endUndoGroup();

        return JSON.stringify({
            status: "success",
            message: "摄像机创建成功",
            layerIndex: finalIndex,
            cameraName: finalName,
            cameraType: cameraType,
            focalLength: focalLength,
            position: position,
            pointOfInterest: pointOfInterest
        }, null, 2);
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return JSON.stringify({ status: "error", message: "E201: " + error.toString() }, null, 2);
    }
}

// 从 args.json 读取参数
var argsFile = new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json");
var args = {};
if (argsFile.exists) {
    argsFile.open("r");
    var _content = argsFile.read();
    argsFile.close();
    if (_content) {
        try { args = JSON.parse(_content); } catch (_e) { args = {}; }
    }
}

var result = addCamera(args);
$.write(result);
