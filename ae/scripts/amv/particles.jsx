// ae/scripts/amv/particles.jsx
// 静止系 AMV：粒子氛围（尘埃/光斑/雪花）
// 使用 CC Particle World 创建氛围粒子
// 用法: 通过 ae_command.json {command:"executeAtomScript", args:{script: "..."}} 下发

(function() {
    // ===== 参数（由 Python 端参数化注入） =====
    var COMP_NAME = "{{COMP_NAME}}";
    var PARTICLE_TYPE = "{{PARTICLE_TYPE}}";   // "dust_motes" | "light_orbs" | "snow"
    var COUNT = {{COUNT}};                     // 粒子数量（默认 200）
    var SIZE_MIN = {{SIZE_MIN}};               // 最小尺寸
    var SIZE_MAX = {{SIZE_MAX}};               // 最大尺寸
    var SPEED_MIN = {{SPEED_MIN}};             // 最小速度
    var SPEED_MAX = {{SPEED_MAX}};             // 最大速度
    var OPACITY_MIN = {{OPACITY_MIN}};         // 最小不透明度 (0-100)
    var OPACITY_MAX = {{OPACITY_MAX}};         // 最大不透明度 (0-100)
    var GRAVITY = {{GRAVITY}};                 // 重力（负值=上升）
    var WIND_X = {{WIND_X}};                   // X 方向风力
    var COLOR_R = {{COLOR_R}};                 // 颜色 R (0-1)
    var COLOR_G = {{COLOR_G}};                 // 颜色 G (0-1)
    var COLOR_B = {{COLOR_B}};                 // 颜色 B (0-1)

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

    app.beginUndoGroup("AMV_Particles");

    // ===== 创建粒子图层 =====
    var particleLayer = comp.layers.addSolid([0, 0, 0], "Particles_" + PARTICLE_TYPE, comp.width, comp.height, comp.pixelAspect);
    particleLayer.name = "Particles_" + PARTICLE_TYPE;

    // 设置为 3D 图层（让粒子参与视差）
    particleLayer.threeDLayer = true;
    particleLayer.property("Position").setValue([comp.width / 2, comp.height / 2, 50]); // 前景偏前

    // ===== 添加 CC Particle World =====
    var effects = particleLayer.property("ADBE Effect Parade");
    var particleEffect = null;
    var effectName = "";

    try {
        particleEffect = effects.addProperty("CC Particle World");
        effectName = "CC Particle World";
    } catch(e) {
        // 备选：CC Particle Systems II
        try {
            particleEffect = effects.addProperty("CC Particle Systems II");
            effectName = "CC Particle Systems II";
        } catch(e2) {
            // 都不可用，使用表达式模拟
        }
    }

    if (particleEffect) {
        // ===== 配置粒子参数 =====
        try {
            // Birth Rate（出生率）
            var birthRate = COUNT / comp.duration;
            try { particleEffect.property("Birth Rate").setValue(birthRate); } catch(e) {}

            // Longevity（寿命）
            try { particleEffect.property("Longevity").setValue(comp.duration * 0.8); } catch(e) {}

            // Gravity
            try { particleEffect.property("Physics").property("Gravity").setValue(GRAVITY / 100); } catch(e) {}

            // Velocity
            var avgSpeed = (SPEED_MIN + SPEED_MAX) / 2;
            try { particleEffect.property("Physics").property("Velocity").setValue(avgSpeed / 50); } catch(e) {}

            // Particle size
            var avgSize = (SIZE_MIN + SIZE_MAX) / 2;
            try {
                particleEffect.property("Particle").property("Birth Size").setValue(avgSize);
                particleEffect.property("Particle").property("Death Size").setValue(avgSize * 0.5);
            } catch(e) {}

            // Opacity
            try {
                particleEffect.property("Particle").property("Birth Opacity").setValue(OPACITY_MAX / 100);
                particleEffect.property("Particle").property("Death Opacity").setValue(OPACITY_MIN / 100);
            } catch(e) {}

            // Color
            try {
                particleEffect.property("Particle").property("Birth Color").setValue([COLOR_R, COLOR_G, COLOR_B, 1]);
                particleEffect.property("Particle").property("Death Color").setValue([COLOR_R, COLOR_G, COLOR_B, 0.3]);
            } catch(e) {}

            // Particle Type（根据类型设置）
            try {
                if (PARTICLE_TYPE === "light_orbs") {
                    particleEffect.property("Particle").property("Particle Type").setValue(6); // Glow
                } else if (PARTICLE_TYPE === "snow") {
                    particleEffect.property("Particle").property("Particle Type").setValue(2); // Disc
                } else {
                    particleEffect.property("Particle").property("Particle Type").setValue(4); // Faded
                }
            } catch(e) {}

        } catch(e) {
            // 参数设置部分失败，继续
        }
    } else {
        // ===== 备选：使用形状图层 + 表达式模拟粒子 =====
        // 删除固态层，改用形状图层
        particleLayer.remove();
        particleLayer = comp.layers.addShape();
        particleLayer.name = "Particles_Shape_" + PARTICLE_TYPE;
        particleLayer.threeDLayer = true;

        var rootGroup = particleLayer.property("Contents");

        // 创建多个小圆点模拟粒子
        var simCount = Math.min(COUNT, 50); // 形状图层限制数量
        for (var i = 0; i < simCount; i++) {
            var group = rootGroup.addProperty("ADBE Vector Group");
            group.name = "P_" + i;

            // 椭圆路径
            var ellipse = group.property("Contents").addProperty("ADBE Vector Shape - Ellipse");
            var size = SIZE_MIN + Math.random() * (SIZE_MAX - SIZE_MIN);
            ellipse.property("Size").setValue([size, size]);

            // 随机位置
            var px = Math.random() * comp.width;
            var py = Math.random() * comp.height;
            ellipse.property("Position").setValue([px - comp.width / 2, py - comp.height / 2]);

            // 填充
            var fill = group.property("Contents").addProperty("ADBE Vector Graphic - Fill");
            fill.property("Color").setValue([COLOR_R, COLOR_G, COLOR_B, (OPACITY_MIN + Math.random() * (OPACITY_MAX - OPACITY_MIN)) / 100]);
        }

        // 整体漂移表达式
        var posExpr = [
            "// Particle drift",
            "var windX = " + WIND_X + ";",
            "var gravity = " + GRAVITY + ";",
            "value + [time * windX, time * gravity * 0.1, 0];"
        ].join("\n");
        particleLayer.property("Position").expression = posExpr;

        effectName = "shape_simulation";
    }

    // ===== 设置混合模式（光斑用 Add/Screen） =====
    if (PARTICLE_TYPE === "light_orbs" || PARTICLE_TYPE === "dust_motes") {
        try {
            particleLayer.blendingMode = BlendingMode.ADD;
        } catch(e) {
            try { particleLayer.blendingMode = BlendingMode.SCREEN; } catch(e2) {}
        }
    }

    // ===== 运动模糊 =====
    particleLayer.motionBlur = true;

    app.endUndoGroup();

    JSON.stringify({
        success: true,
        comp: comp.name,
        layer: particleLayer.name,
        effectUsed: effectName,
        particleType: PARTICLE_TYPE,
        count: COUNT,
        blending: "additive"
    });
})();
