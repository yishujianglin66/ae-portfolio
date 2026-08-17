// ae/scripts/manga/speed_lines.jsx
// 漫剪特效：速度线（Speed Lines）— 转场/冲击时使用
// 从中心向外辐射的动态线条，模拟漫画中的速度感
// 用法: 通过 ae_command.json {command:"runScript", args:{code: "..."}} 下发

(function() {
    // ===== 参数（由 Python 端参数化注入） =====
    var COMP_NAME = "{{COMP_NAME}}";
    var TRIGGER_TIME = {{TRIGGER_TIME}};       // 触发时间（秒）
    var FPS = {{FPS}};
    var DURATION_FRAMES = {{DURATION_FRAMES}}; // 持续帧数（默认 12）
    var LINE_COUNT = {{LINE_COUNT}};           // 线条数量（默认 80）
    var CENTER_X = {{CENTER_X}};               // 辐射中心 X (0-1, 默认 0.5)
    var CENTER_Y = {{CENTER_Y}};               // 辐射中心 Y (0-1, 默认 0.5)
    var LINE_SPEED = {{LINE_SPEED}};           // 线条速度倍率（默认 2.0）

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

    app.beginUndoGroup("MangaSpeedLines");

    var duration = DURATION_FRAMES / FPS;
    var cx = comp.width * CENTER_X;
    var cy = comp.height * CENTER_Y;

    // ===== 创建速度线图层（使用形状图层） =====
    var speedLayer = comp.layers.addShape();
    speedLayer.name = "SpeedLines_" + Math.round(TRIGGER_TIME * FPS);
    speedLayer.inPoint = TRIGGER_TIME;
    speedLayer.outPoint = TRIGGER_TIME + duration;

    // 获取形状属性
    var rootGroup = speedLayer.property("Contents");

    // 创建多条放射线
    var maxRadius = Math.sqrt(comp.width * comp.width + comp.height * comp.height) * 0.6;

    for (var i = 0; i < LINE_COUNT; i++) {
        var angle = (i / LINE_COUNT) * 2 * Math.PI + (Math.random() * 0.1 - 0.05);
        var innerRadius = maxRadius * (0.15 + Math.random() * 0.2);
        var outerRadius = maxRadius * (0.6 + Math.random() * 0.4);
        var lineWidth = 1 + Math.random() * 3;

        // 计算端点
        var x1 = cx + Math.cos(angle) * innerRadius;
        var y1 = cy + Math.sin(angle) * innerRadius;
        var x2 = cx + Math.cos(angle) * outerRadius;
        var y2 = cy + Math.sin(angle) * outerRadius;

        // 添加路径组
        var group = rootGroup.addProperty("ADBE Vector Group");
        group.name = "Line_" + i;

        // 路径
        var path = group.property("Contents").addProperty("ADBE Vector Shape - Group");
        var shape = new Shape();
        shape.vertices = [[x1, y1], [x2, y2]];
        shape.closed = false;
        path.property("Path").setValue(shape);

        // 描边
        var stroke = group.property("Contents").addProperty("ADBE Vector Graphic - Stroke");
        stroke.property("Color").setValue([1, 1, 1, 1]); // 白色
        stroke.property("Stroke Width").setValue(lineWidth);
        stroke.property("Line Cap").setValue(2); // Round cap

        // 不透明度（随机）
        var opacityProp = group.property("Transform").property("Opacity");
        opacityProp.setValue(40 + Math.random() * 60);
    }

    // ===== 添加动画：线条从中心向外扩展 =====
    // 使用缩放动画模拟速度线冲出效果
    var scale = speedLayer.property("Transform").property("Scale");
    var startTime = TRIGGER_TIME;
    var endTime = TRIGGER_TIME + duration;

    scale.setValueAtTime(startTime, [10, 10]);
    scale.setValueAtTime(startTime + duration * 0.3, [100, 100]);
    scale.setValueAtTime(endTime, [130 * LINE_SPEED, 130 * LINE_SPEED]);

    // 缓动
    for (var k = 1; k <= scale.numKeys; k++) {
        var ei = new KeyframeEase(0, 90);
        var eo = new KeyframeEase(0, 60);
        scale.setTemporalEaseAtKey(k, [ei], [eo]);
    }

    // ===== 不透明度淡出 =====
    var layerOpacity = speedLayer.property("Transform").property("Opacity");
    layerOpacity.setValueAtTime(startTime, 0);
    layerOpacity.setValueAtTime(startTime + 2.0 / FPS, 100);
    layerOpacity.setValueAtTime(endTime - 2.0 / FPS, 80);
    layerOpacity.setValueAtTime(endTime, 0);

    // ===== 运动模糊 =====
    speedLayer.motionBlur = true;

    app.endUndoGroup();

    JSON.stringify({
        success: true,
        comp: comp.name,
        layer: speedLayer.name,
        lineCount: LINE_COUNT,
        duration: duration,
        effectsApplied: ["speed_lines", "scale_animation", "motion_blur"]
    });
})();
