// ae/scripts/puppet/breathing_idle.jsx
// 木偶动画：呼吸待机动画（循环表达式）
// 让角色产生自然的呼吸起伏 + 轻微摇摆，无需关键帧
// 用法: 通过 ae_command.json {command:"runScript", args:{code: "..."}} 下发

(function() {
    // ===== 参数（由 Python 端参数化注入） =====
    var COMP_NAME = "{{COMP_NAME}}";
    var LAYER_NAME = "{{LAYER_NAME}}";
    var BREATH_RATE = {{BREATH_RATE}};          // 呼吸频率 Hz（默认 0.25 = 4秒一次）
    var BREATH_AMP = {{BREATH_AMP}};            // 呼吸幅度像素（默认 3.0）
    var SWAY_AMP = {{SWAY_AMP}};               // 摇摆幅度像素（默认 2.0）
    var SWAY_RATE = {{SWAY_RATE}};             // 摇摆频率 Hz（默认 0.15）
    var APPLY_CHEST = {{APPLY_CHEST}};         // 是否应用到胸部（true/false）
    var APPLY_HAIR = {{APPLY_HAIR}};           // 是否应用到头发/附件（true/false）

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

    app.beginUndoGroup("PuppetBreathingIdle");

    // ===== 1. 呼吸表达式（Position Y 轴微动） =====
    // 模拟胸腔起伏：正弦波 + 轻微不对称（吸气快呼气慢）
    var position = layer.property("Transform").property("Position");
    var breathExpr = [
        "// Breathing Idle - Position",
        "var breathRate = " + BREATH_RATE + ";",
        "var breathAmp = " + BREATH_AMP + ";",
        "var swayAmp = " + SWAY_AMP + ";",
        "var swayRate = " + SWAY_RATE + ";",
        "",
        "// 呼吸：非对称正弦（吸气快，呼气慢）",
        "var breathPhase = time * breathRate * 2 * Math.PI;",
        "var breathY = breathAmp * Math.sin(breathPhase) * (1.0 + 0.2 * Math.sin(breathPhase * 2));",
        "",
        "// 摇摆：低频左右微动",
        "var swayX = swayAmp * Math.sin(time * swayRate * 2 * Math.PI);",
        "var swayZ = swayAmp * 0.5 * Math.cos(time * swayRate * 1.7 * 2 * Math.PI);",
        "",
        "// 叠加到原始位置",
        "value + [swayX, -breathY, 0].slice(0, value.length);"
    ].join("\n");

    position.expression = breathExpr;

    // ===== 2. 缩放呼吸（胸腔膨胀感） =====
    var scale = layer.property("Transform").property("Scale");
    var scaleBreathExpr = [
        "// Breathing Idle - Scale",
        "var breathRate = " + BREATH_RATE + ";",
        "var scaleAmp = " + (BREATH_AMP * 0.3) + ";",  // 缩放幅度较小
        "",
        "var breathPhase = time * breathRate * 2 * Math.PI;",
        "var scaleX = 100 + scaleAmp * Math.sin(breathPhase);",
        "var scaleY = 100 + scaleAmp * 0.7 * Math.sin(breathPhase + 0.3);",
        "",
        "[scaleX, scaleY];"
    ].join("\n");

    scale.expression = scaleBreathExpr;

    // ===== 3. 旋转微摆（头部/身体轻微倾斜） =====
    var rotation = layer.property("Transform").property("Rotation");
    var rotExpr = [
        "// Breathing Idle - Rotation",
        "var swayRate = " + SWAY_RATE + ";",
        "var rotAmp = " + (SWAY_AMP * 0.3) + ";",  // 旋转幅度（度）
        "",
        "// 多频率叠加产生自然感",
        "var rot = rotAmp * Math.sin(time * swayRate * 2 * Math.PI)",
        "        + rotAmp * 0.3 * Math.sin(time * swayRate * 3.7 * 2 * Math.PI);",
        "rot;"
    ].join("\n");

    rotation.expression = rotExpr;

    // ===== 4. 锚点微调（呼吸时锚点跟随） =====
    var anchor = layer.property("Transform").property("Anchor Point");
    var anchorExpr = [
        "// Breathing Idle - Anchor Point subtle shift",
        "var breathRate = " + BREATH_RATE + ";",
        "var amp = " + (BREATH_AMP * 0.2) + ";",
        "value + [0, amp * Math.sin(time * breathRate * 2 * Math.PI)];"
    ].join("\n");

    anchor.expression = anchorExpr;

    // ===== 5. 头发/附件额外摆动（如果有子图层） =====
    if (APPLY_HAIR) {
        // 查找名称含 "hair" 或 "accessory" 的图层
        for (var i = 1; i <= comp.numLayers; i++) {
            var l = comp.layer(i);
            var name = l.name.toLowerCase();
            if (name.indexOf("hair") >= 0 || name.indexOf("accessory") >= 0 ||
                name.indexOf("tail") >= 0 || name.indexOf("cloth") >= 0) {
                // 对附件图层应用更强的摆动
                var hairPos = l.property("Transform").property("Position");
                var hairExpr = [
                    "// Hair/Cloth secondary motion",
                    "var swayAmp = " + (SWAY_AMP * 2.5) + ";",
                    "var swayRate = " + (SWAY_RATE * 1.3) + ";",
                    "var delay = 0.15;",  // 延迟跟随
                    "",
                    "var t = time - delay;",
                    "var swingX = swayAmp * Math.sin(t * swayRate * 2 * Math.PI);",
                    "var swingY = swayAmp * 0.4 * Math.cos(t * swayRate * 1.5 * 2 * Math.PI);",
                    "value + [swingX, swingY];"
                ].join("\n");
                hairPos.expression = hairExpr;
            }
        }
    }

    app.endUndoGroup();

    JSON.stringify({
        success: true,
        comp: comp.name,
        layer: layer.name,
        expressionsApplied: ["position_breath", "scale_breath", "rotation_sway", "anchor_shift"],
        breathRate: BREATH_RATE,
        breathAmplitude: BREATH_AMP,
        swayAmplitude: SWAY_AMP,
        hairApplied: APPLY_HAIR,
        loopable: true
    });
})();
