// ae/scripts/amv/camera_move.jsx
// 静止系 AMV：摄像机运动路径
// 创建摄像机 + Null 控制器 + 贝塞尔运动路径 + 缓动
// 用法: 通过 ae_command.json {command:"runScript", args:{code: "..."}} 下发

(function() {
    // ===== 参数（由 Python 端参数化注入） =====
    var COMP_NAME = "{{COMP_NAME}}";
    var START_X = {{START_X}};                 // 起始位置 X
    var START_Y = {{START_Y}};                 // 起始位置 Y
    var START_Z = {{START_Z}};                 // 起始位置 Z（默认 -800）
    var END_X = {{END_X}};                     // 结束位置 X
    var END_Y = {{END_Y}};                     // 结束位置 Y
    var END_Z = {{END_Z}};                     // 结束位置 Z（默认 -600）
    var DURATION = {{DURATION}};               // 运动持续时间（秒）
    var EASE_INFLUENCE = {{EASE_INFLUENCE}};   // 缓动影响（0-100，默认 75）
    var ADD_NULL = {{ADD_NULL}};               // 是否添加 Null 控制器
    var DRIFT_AMP = {{DRIFT_AMP}};             // 漂移幅度（默认 20）

    // ===== 查找合成 =====
    var comp = null;
    for (var i = 1; i <= app.project.numItems; i++) {
        var item = app.project.item(i);
        if (item instanceof CompItem && item.name === COMP_NAME) {
            comp = item;
            break;
        }
    }
    if (!comp) {
        if (app.project.activeItem instanceof CompItem) {
            comp = app.project.activeItem;
        } else {
            throw new Error("Comp not found: " + COMP_NAME);
        }
    }

    app.beginUndoGroup("AMV_CameraMove");

    // ===== 1. 创建 Null 控制器（可选） =====
    var nullLayer = null;
    if (ADD_NULL) {
        nullLayer = comp.layers.addNull(comp.duration);
        nullLayer.name = "Camera_Controller";
        nullLayer.threeDLayer = true;

        // Null 的位置关键帧（作为摄像机的父级控制）
        var nullPos = nullLayer.property("Position");
        nullPos.setValueAtTime(0, [comp.width / 2, comp.height / 2, 0]);
        nullPos.setValueAtTime(DURATION, [comp.width / 2 + DRIFT_AMP, comp.height / 2 - DRIFT_AMP * 0.5, 0]);

        // 缓动
        for (var k = 1; k <= nullPos.numKeys; k++) {
            var ei = new KeyframeEase(0, EASE_INFLUENCE);
            var eo = new KeyframeEase(0, EASE_INFLUENCE);
            nullPos.setTemporalEaseAtKey(k, [ei, ei, ei], [eo, eo, eo]);
        }
    }

    // ===== 2. 创建摄像机 =====
    var camera = comp.layers.addCamera("AMV_Camera", [comp.width / 2, comp.height / 2]);

    // 设置摄像机类型（单节点 = 只看目标点，双节点 = 自由旋转）
    try {
        camera.property("Auto-Orientation").setValue(1); // Orient along path
    } catch(e) {}

    // ===== 3. 摄像机位置关键帧 =====
    var camPos = camera.property("Position");
    var startTime = 0;
    var endTime = Math.min(DURATION, comp.duration);

    camPos.setValueAtTime(startTime, [START_X, START_Y, START_Z]);
    camPos.setValueAtTime(endTime, [END_X, END_Y, END_Z]);

    // 添加中间关键帧（贝塞尔弧线运动）
    var midTime = endTime * 0.5;
    var midX = (START_X + END_X) / 2 + DRIFT_AMP;
    var midY = (START_Y + END_Y) / 2 - DRIFT_AMP * 0.3;
    var midZ = (START_Z + END_Z) / 2 + 50; // 中间稍微拉远
    camPos.setValueAtTime(midTime, [midX, midY, midZ]);

    // ===== 4. 设置缓动（贝塞尔） =====
    for (var k = 1; k <= camPos.numKeys; k++) {
        var easeIn = new KeyframeEase(0, EASE_INFLUENCE);
        var easeOut = new KeyframeEase(0, EASE_INFLUENCE);
        // 3D 位置需要 3 个缓动值
        camPos.setTemporalEaseAtKey(k, [easeIn, easeIn, easeIn], [easeOut, easeOut, easeOut]);
    }

    // ===== 5. 摄像机目标点（Point of Interest） =====
    var poi = camera.property("Point of Interest");
    poi.setValueAtTime(startTime, [comp.width / 2, comp.height / 2, 0]);
    poi.setValueAtTime(endTime, [comp.width / 2, comp.height / 2 - 30, 0]);

    for (var k = 1; k <= poi.numKeys; k++) {
        var ei = new KeyframeEase(0, 60);
        var eo = new KeyframeEase(0, 60);
        poi.setTemporalEaseAtKey(k, [ei, ei, ei], [eo, eo, eo]);
    }

    // ===== 6. 父子链接（摄像机 → Null） =====
    if (nullLayer) {
        camera.parent = nullLayer;
    }

    // ===== 7. 添加微妙的漂移表达式（手持感） =====
    var driftExpr = [
        "// Subtle camera drift (handheld feel)",
        "var amp = " + DRIFT_AMP + ";",
        "var freqX = 0.1;",
        "var freqY = 0.13;",
        "",
        "var dx = amp * 0.3 * Math.sin(time * freqX * 2 * Math.PI);",
        "var dy = amp * 0.2 * Math.cos(time * freqY * 2 * Math.PI);",
        "",
        "value + [dx, dy, 0];"
    ].join("\n");

    // 只对 Null 应用漂移（避免覆盖摄像机关键帧）
    if (nullLayer) {
        nullLayer.property("Position").expression = driftExpr;
    }

    // ===== 8. 焦距动画（可选：轻微推拉） =====
    try {
        var zoom = camera.property("Zoom");
        var startZoom = zoom.value;
        zoom.setValueAtTime(startTime, startZoom);
        zoom.setValueAtTime(endTime, startZoom * 1.1); // 轻微推近
    } catch(e) {}

    app.endUndoGroup();

    JSON.stringify({
        success: true,
        comp: comp.name,
        camera: camera.name,
        nullController: nullLayer ? nullLayer.name : null,
        path: {
            start: [START_X, START_Y, START_Z],
            mid: [midX, midY, midZ],
            end: [END_X, END_Y, END_Z]
        },
        duration: endTime,
        easing: EASE_INFLUENCE,
        driftApplied: DRIFT_AMP > 0
    });
})();
