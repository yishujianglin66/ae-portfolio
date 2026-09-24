// ae/scripts/amv/light_rays.jsx
// 静止系 AMV：光影动画（God Rays / 体积光 / Lens Flare）
// 创建光线扫描 + 体积光效果 + 可选镜头光晕
// 用法: 通过 ae_command.json {command:"executeAtomScript", args:{script: "..."}} 下发

(function() {
    // ===== 参数（由 Python 端参数化注入） =====
    var COMP_NAME = "{{COMP_NAME}}";
    var LIGHT_TYPE = "{{LIGHT_TYPE}}";         // "god_rays" | "volumetric" | "scan"
    var ANGLE_DEG = {{ANGLE_DEG}};             // 光线角度（度，默认 35）
    var INTENSITY = {{INTENSITY}};             // 光线强度 (0-1，默认 0.6)
    var RAY_COUNT = {{RAY_COUNT}};             // 光线数量（默认 5）
    var ANIM_SPEED = {{ANIM_SPEED}};           // 动画速度（默认 0.1）
    var ADD_FLARE = {{ADD_FLARE}};             // 是否添加 Lens Flare
    var FLARE_BRIGHT = {{FLARE_BRIGHT}};       // 光晕亮度 (0-100)
    var VOLUMETRIC = {{VOLUMETRIC}};           // 是否体积散射

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

    app.beginUndoGroup("AMV_LightRays");

    var centerX = comp.width / 2;
    var centerY = comp.height / 2;
    var angleRad = ANGLE_DEG * Math.PI / 180;

    // ===== 1. 创建光线图层（形状图层模拟 God Rays） =====
    var raysLayer = comp.layers.addShape();
    raysLayer.name = "GodRays_" + LIGHT_TYPE;
    raysLayer.threeDLayer = true;
    raysLayer.property("Position").setValue([centerX, centerY, 80]); // 前景偏前

    var rootGroup = raysLayer.property("Contents");

    // 光线源点（从画面外射入）
    var sourceX = centerX + Math.cos(angleRad) * comp.width * 0.8;
    var sourceY = -comp.height * 0.2; // 从上方射入

    for (var i = 0; i < RAY_COUNT; i++) {
        var group = rootGroup.addProperty("ADBE Vector Group");
        group.name = "Ray_" + i;

        // 每条光线略微不同角度和宽度
        var rayAngle = angleRad + (i - RAY_COUNT / 2) * 0.05;
        var rayWidth = 20 + Math.random() * 60;
        var rayLength = comp.height * (1.2 + Math.random() * 0.5);

        // 光线起点和终点
        var startX = sourceX + (i - RAY_COUNT / 2) * 80;
        var endX = startX - Math.sin(rayAngle) * rayLength;
        var endY = sourceY + Math.cos(rayAngle) * rayLength;

        // 创建梯形路径（模拟光束宽度）
        var path = group.property("Contents").addProperty("ADBE Vector Shape - Group");
        var shape = new Shape();
        shape.vertices = [
            [startX - centerX - rayWidth / 2, sourceY - centerY],
            [startX - centerX + rayWidth / 2, sourceY - centerY],
            [endX - centerX + rayWidth * 1.5, endY - centerY],
            [endX - centerX - rayWidth * 1.5, endY - centerY]
        ];
        shape.closed = true;
        path.property("Path").setValue(shape);

        // 渐变填充（从亮到透明）
        var fill = group.property("Contents").addProperty("ADBE Vector Graphic - G-Fill");
        try {
            fill.property("Colors").setValue({
                numKeys: 2,
                keyValues: [
                    [0, 1.0, 0.95, 0.8, INTENSITY],
                    [1, 1.0, 0.95, 0.8, 0]
                ]
            });
        } catch(e) {
            // 渐变设置失败，使用普通填充
            var plainFill = group.property("Contents").addProperty("ADBE Vector Graphic - Fill");
            plainFill.property("Color").setValue([1.0, 0.95, 0.8, INTENSITY * 0.5]);
        }

        // 不透明度
        var groupOpacity = group.property("Transform").property("Opacity");
        groupOpacity.setValue(INTENSITY * 100 * (0.5 + Math.random() * 0.5));
    }

    // ===== 2. 光线动画表达式（缓慢摆动） =====
    var raysRotation = raysLayer.property("Transform").property("Rotation");
    var swayExpr = [
        "// Light rays gentle sway",
        "var speed = " + ANIM_SPEED + ";",
        "var amp = 2.0;",  // 摆动幅度（度）
        "amp * Math.sin(time * speed * 2 * Math.PI);"
    ].join("\n");
    raysRotation.expression = swayExpr;

    // 不透明度呼吸（光线明暗变化）
    var raysOpacity = raysLayer.property("Transform").property("Opacity");
    var opacityExpr = [
        "// Light intensity breathing",
        "var speed = " + ANIM_SPEED + ";",
        "var base = " + (INTENSITY * 100) + ";",
        "var variation = base * 0.2;",
        "base + variation * Math.sin(time * speed * 1.5 * 2 * Math.PI);"
    ].join("\n");
    raysOpacity.expression = opacityExpr;

    // ===== 3. 混合模式（Add/Screen） =====
    try {
        raysLayer.blendingMode = BlendingMode.ADD;
    } catch(e) {
        try { raysLayer.blendingMode = BlendingMode.SCREEN; } catch(e2) {}
    }

    // ===== 4. Lens Flare（可选） =====
    var flareLayer = null;
    if (ADD_FLARE) {
        flareLayer = comp.layers.addSolid([0, 0, 0], "LensFlare", comp.width, comp.height, comp.pixelAspect);
        flareLayer.threeDLayer = true;
        flareLayer.property("Position").setValue([centerX, centerY, 90]);

        var flareEffects = flareLayer.property("ADBE Effect Parade");
        try {
            var flare = flareEffects.addProperty("ADBE Lens Flare");
            if (flare) {
                // 设置光晕位置（与光线源一致）
                flare.property("Flare Center").setValue([sourceX, sourceY + comp.height * 0.3]);
                flare.property("Flare Brightness").setValue(FLARE_BRIGHT);

                // 光晕亮度动画
                var flareBright = flare.property("Flare Brightness");
                var flareExpr = [
                    "// Lens flare flicker",
                    "var base = " + FLARE_BRIGHT + ";",
                    "var speed = " + ANIM_SPEED + ";",
                    "base * (0.8 + 0.2 * Math.sin(time * speed * 3 * 2 * Math.PI));"
                ].join("\n");
                flareBright.expression = flareExpr;
            }
        } catch(e) {
            // Lens Flare 效果不可用
        }

        // 混合模式
        try { flareLayer.blendingMode = BlendingMode.SCREEN; } catch(e) {}
    }

    // ===== 5. 体积散射（可选：添加模糊层模拟） =====
    if (VOLUMETRIC) {
        // 复制光线层 + 高斯模糊 = 体积散射感
        var scatterLayer = raysLayer.duplicate();
        scatterLayer.name = "LightScatter";
        var scatterEffects = scatterLayer.property("ADBE Effect Parade");
        try {
            var blur = scatterEffects.addProperty("ADBE Gaussian Blur 2");
            if (blur) {
                blur.property("Blurriness").setValue(30);
                blur.property("Blur Dimensions").setValue(1); // 水平+垂直
            }
        } catch(e) {}
        // 降低不透明度
        scatterLayer.property("Transform").property("Opacity").setValue(40);
    }

    app.endUndoGroup();

    JSON.stringify({
        success: true,
        comp: comp.name,
        raysLayer: raysLayer.name,
        flareLayer: flareLayer ? flareLayer.name : null,
        lightType: LIGHT_TYPE,
        rayCount: RAY_COUNT,
        angle: ANGLE_DEG,
        intensity: INTENSITY,
        volumetric: VOLUMETRIC,
        effectsApplied: ["god_rays", ADD_FLARE ? "lens_flare" : null, VOLUMETRIC ? "scatter" : null]
    });
})();
