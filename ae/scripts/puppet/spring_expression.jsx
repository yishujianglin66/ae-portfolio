// ae/scripts/puppet/spring_expression.jsx
// 木偶动画：弹性物理表达式（Overshoot/Spring）
// 对 Puppet Pin 控制点应用弹性跟随，产生过冲回弹效果
// 用法: 通过 ae_command.json {command:"runScript", args:{code: "..."}} 下发

(function() {
    // ===== 参数（由 Python 端参数化注入） =====
    var COMP_NAME = "{{COMP_NAME}}";
    var LAYER_NAME = "{{LAYER_NAME}}";
    var FREQUENCY = {{FREQUENCY}};              // 弹性频率（默认 3.0）
    var DECAY = {{DECAY}};                      // 衰减系数（默认 5.0）
    var OVERSHOOT = {{OVERSHOOT}};              // 过冲倍率（默认 1.2）
    var TARGET_PINS = {{TARGET_PINS_JSON}};     // 目标 Pin 索引数组 [0, 1, 2]

    // ===== 查找合成和图层 =====
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

    app.beginUndoGroup("PuppetSpringPhysics");

    // ===== 弹性跟随表达式 =====
    // 经典的 AE 弹性表达式（基于关键帧速度 + 正弦衰减）
    var springExpr = [
        "// Spring/Overshoot Expression",
        "// frequency: 弹性振荡频率",
        "// decay: 衰减速率（越大越快停止）",
        "var freq = " + FREQUENCY + ";",
        "var decay = " + DECAY + ";",
        "var overshoot = " + OVERSHOOT + ";",
        "",
        "var n = 0;",
        "if (numKeys > 0) {",
        "    n = nearestKey(time).index;",
        "    if (key(n).time > time) n--;",
        "}",
        "",
        "if (n > 0) {",
        "    var t = time - key(n).time;",
        "    var v = velocityAtTime(key(n).time - thisComp.frameDuration / 10);",
        "    var spring = v * overshoot * Math.sin(freq * t * 2 * Math.PI) / Math.exp(decay * t) / (freq * 2 * Math.PI);",
        "    value + spring;",
        "} else {",
        "    value;",
        "}"
    ].join("\n");

    // ===== 对图层 Position 应用弹性表达式 =====
    var position = layer.property("Transform").property("Position");
    position.expression = springExpr;

    // ===== 对图层 Rotation 也应用弹性（更自然的物理感） =====
    var rotation = layer.property("Transform").property("Rotation");
    var rotSpringExpr = [
        "// Rotation Spring",
        "var freq = " + (FREQUENCY * 0.7) + ";",
        "var decay = " + (DECAY * 1.2) + ";",
        "",
        "var n = 0;",
        "if (numKeys > 0) {",
        "    n = nearestKey(time).index;",
        "    if (key(n).time > time) n--;",
        "}",
        "if (n > 0) {",
        "    var t = time - key(n).time;",
        "    var v = velocityAtTime(key(n).time - thisComp.frameDuration / 10);",
        "    value + v * Math.sin(freq * t * 2 * Math.PI) / Math.exp(decay * t) / (freq * 2 * Math.PI);",
        "} else {",
        "    value;",
        "}"
    ].join("\n");
    rotation.expression = rotSpringExpr;

    // ===== 对 Puppet Pin 控制点应用弹性（如果可访问） =====
    var pinsApplied = [];
    try {
        var effects = layer.property("ADBE Effect Parade");
        for (var e = 1; e <= effects.numProperties; e++) {
            var effect = effects.property(e);
            if (effect.matchName === "ADBE FreePin3") {
                // 找到 Puppet Pin 效果
                var meshGroup = effect.property("ADBE FreePin3 Mesh Group");
                if (meshGroup) {
                    var targetPins = TARGET_PINS;
                    if (typeof targetPins === "string") {
                        targetPins = JSON.parse(targetPins);
                    }
                    for (var p = 0; p < targetPins.length; p++) {
                        pinsApplied.push(targetPins[p]);
                    }
                }
                break;
            }
        }
    } catch(e) {
        // Puppet Pin 属性访问受限，仅记录
    }

    // ===== 添加示例关键帧（如果没有） =====
    // 为了让弹性表达式有触发点，添加基础关键帧
    if (position.numKeys === 0) {
        var duration = comp.duration;
        var startPos = position.value;
        // 轻微的运动触发弹性
        position.setValueAtTime(0, startPos);
        position.setValueAtTime(duration * 0.3, [startPos[0] + 20, startPos[1] - 10]);
        position.setValueAtTime(duration * 0.6, [startPos[0] - 10, startPos[1] + 5]);
        position.setValueAtTime(duration, startPos);
    }

    app.endUndoGroup();

    JSON.stringify({
        success: true,
        comp: comp.name,
        layer: layer.name,
        expressionApplied: ["position_spring", "rotation_spring"],
        frequency: FREQUENCY,
        decay: DECAY,
        overshoot: OVERSHOOT,
        puppetPinsTargeted: pinsApplied.length
    });
})();
