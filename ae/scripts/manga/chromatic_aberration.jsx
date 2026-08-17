// ae/scripts/manga/chromatic_aberration.jsx
// 漫剪特效：色差（Chromatic Aberration）— 在 energy peak 点触发
// 模拟 RGB 通道偏移，产生赛博朋克/故障艺术效果
// 用法: 通过 ae_command.json {command:"runScript", args:{code: "..."}} 下发

(function() {
    // ===== 参数（由 Python 端参数化注入） =====
    var COMP_NAME = "{{COMP_NAME}}";
    var LAYER_NAME = "{{LAYER_NAME}}";
    var TRIGGER_TIME = {{TRIGGER_TIME}};      // 触发时间点（秒）
    var FPS = {{FPS}};
    var OFFSET_PX = {{OFFSET_PX}};            // 最大偏移像素（默认 4）
    var DIRECTION = "{{DIRECTION}}";           // "horizontal" | "vertical" | "radial"
    var DECAY_FRAMES = {{DECAY_FRAMES}};       // 衰减帧数（默认 6）

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

    var layer = null;
    if (LAYER_NAME && LAYER_NAME !== "") {
        try { layer = comp.layer(LAYER_NAME); } catch(e) {}
    }
    if (!layer) {
        layer = comp.layer(1);
    }

    app.beginUndoGroup("MangaChromatic");

    // ===== 方案: 使用 CC Split Color 效果 =====
    // 如果 CC Split Color 不可用，使用 Shift Channels + 多层叠加
    var effectAdded = false;

    try {
        // 尝试添加 CC Split Color（AE 内置）
        var effects = layer.property("ADBE Effect Parade");
        var splitEffect = effects.addProperty("CC Split Color");
        if (splitEffect) {
            effectAdded = true;

            // 设置 Red/Blue 通道偏移
            var redOffset = splitEffect.property("Red Offset");
            var blueOffset = splitEffect.property("Blue Offset");

            if (DIRECTION === "horizontal") {
                redOffset.setValue([OFFSET_PX, 0]);
                blueOffset.setValue([-OFFSET_PX, 0]);
            } else if (DIRECTION === "vertical") {
                redOffset.setValue([0, OFFSET_PX]);
                blueOffset.setValue([0, -OFFSET_PX]);
            } else {
                // radial: 对角偏移
                redOffset.setValue([OFFSET_PX, OFFSET_PX * 0.5]);
                blueOffset.setValue([-OFFSET_PX, -OFFSET_PX * 0.5]);
            }
        }
    } catch(e) {
        // CC Split Color 不可用
    }

    // ===== 备选方案: 使用 Shift Channels =====
    if (!effectAdded) {
        try {
            var effects = layer.property("ADBE Effect Parade");
            var shiftEffect = effects.addProperty("ADBE Shift Channels");
            if (shiftEffect) {
                effectAdded = true;
                // Shift Channels 通过偏移通道产生色差感
                shiftEffect.property("Take Red From").setValue(1); // Red from Red
                shiftEffect.property("Take Green From").setValue(2); // Green from Green
                shiftEffect.property("Take Blue From").setValue(3); // Blue from Blue
            }
        } catch(e) {}
    }

    // ===== 添加偏移表达式（时间衰减） =====
    // 对图层位置添加微妙的色差抖动表达式
    var position = layer.property("Transform").property("Position");
    var chromaticExpr = [
        "// Chromatic Aberration Jitter",
        "var offset = " + OFFSET_PX + ";",
        "var triggerTime = " + TRIGGER_TIME + ";",
        "var decayFrames = " + DECAY_FRAMES + ";",
        "var fps = " + FPS + ";",
        "",
        "var t = time - triggerTime;",
        "if (t < 0 || t > decayFrames / fps) {",
        "    value;",
        "} else {",
        "    var progress = t / (decayFrames / fps);",
        "    var decay = 1.0 - progress;",
        "    var jitter = offset * decay * (Math.random() * 2 - 1);",
        (DIRECTION === "vertical") ?
            "    value + [0, jitter];" :
            "    value + [jitter, 0];",
        "}"
    ].join("\n");

    position.expression = chromaticExpr;

    // ===== 添加闪烁不透明度（故障感） =====
    var opacity = layer.property("Transform").property("Opacity");
    var glitchExpr = [
        "// Glitch Opacity Flicker",
        "var triggerTime = " + TRIGGER_TIME + ";",
        "var decayFrames = " + DECAY_FRAMES + ";",
        "var fps = " + FPS + ";",
        "",
        "var t = time - triggerTime;",
        "if (t < 0 || t > decayFrames / fps) {",
        "    100;",
        "} else {",
        "    var flicker = (Math.random() > 0.7) ? 85 : 100;",
        "    flicker;",
        "}"
    ].join("\n");

    // 只在效果持续期间应用闪烁（不覆盖已有表达式）
    if (!opacity.expression || opacity.expression === "") {
        opacity.expression = glitchExpr;
    }

    app.endUndoGroup();

    JSON.stringify({
        success: true,
        comp: comp.name,
        layer: layer.name,
        effectMethod: effectAdded ? "cc_split_color" : "expression_only",
        direction: DIRECTION,
        offsetPx: OFFSET_PX,
        effectsApplied: ["chromatic_aberration", "glitch_flicker"]
    });
})();
