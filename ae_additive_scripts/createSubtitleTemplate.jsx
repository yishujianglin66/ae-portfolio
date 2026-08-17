// createSubtitleTemplate.jsx
// 花样字幕模板 - 支持赛博朋克、复古、手绘、科技、电影、简约、动态等多种风格
// Phase 5-2 扩展 - 文字系统全面升级

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"
#include "_lib/easing_utils.jsx"

/**
 * 为图层添加发光效果（内置 Glow 回退）
 */
function addGlowToLayer(layer, color, radius, intensity) {
    var applied = false;
    try {
        var glowFx = layer.Effects.addProperty("ADBE Glo2i");
        glowFx.property("ADBE Glo2i-0001").setValue([Number(color[0]), Number(color[1]), Number(color[2])]);
        glowFx.property("ADBE Glo2i-0002").setValue(radius || 20);
        glowFx.property("ADBE Glo2i-0003").setValue(intensity !== undefined ? intensity : 1);
        applied = true;
    } catch (e) {
        // 回退到 Outer Glow 图层样式
        try {
            var lsGlow = layer.property("ADBE Layer Styles").property("ADBE Outer Glow");
            lsGlow.property("ADBE Outer Glow-0001").setValue(true);
            lsGlow.property("ADBE Outer Glow-0002").setValue([Number(color[0]), Number(color[1]), Number(color[2])]);
            lsGlow.property("ADBE Outer Glow-0006").setValue(radius || 20);
            applied = true;
        } catch (e2) {}
    }
    return applied;
}

/**
 * 为图层添加阴影效果
 */
function addShadowToLayer(layer, color, distance, blur, angle) {
    var applied = false;
    try {
        var shadowFx = layer.Effects.addProperty("ADBE Drop Shadow");
        shadowFx.property("ADBE Drop Shadow-0002").setValue([Number(color[0]), Number(color[1]), Number(color[2])]);
        shadowFx.property("ADBE Drop Shadow-0004").setValue(angle !== undefined ? angle : 135);
        shadowFx.property("ADBE Drop Shadow-0005").setValue(distance !== undefined ? distance : 5);
        shadowFx.property("ADBE Drop Shadow-0006").setValue(blur !== undefined ? blur : 10);
        applied = true;
    } catch (e) {}
    return applied;
}

/**
 * 创建字幕模板
 */
function createSubtitleTemplate(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (!args.subtitleText) {
            return buildError("E110", "E110: subtitleText 参数必填");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        var templateType = String(args.templateType || "minimal").toLowerCase();
        var subtitleText = String(args.subtitleText);
        var subtitlePosition = String(args.subtitlePosition || "bottom").toLowerCase();
        var animation = String(args.animation || "none").toLowerCase();
        var background = args.background || { enabled: false };
        var additionalEffects = args.additionalEffects || [];
        var fontOverride = args.fontOverride || {};

        // 计算字幕位置（考虑安全边距）
        var marginX = comp.width * 0.1;  // 10% 水平安全边距
        var marginY = comp.height * 0.15; // 15% 垂直安全边距
        var posX = comp.width / 2;
        var posY = comp.height * 0.85;

        if (subtitlePosition === "top") {
            posY = marginY + comp.height * 0.05;
        } else if (subtitlePosition === "center") {
            posY = comp.height / 2;
        } else if (subtitlePosition === "bottom") {
            posY = comp.height - marginY;
        } else if (subtitlePosition === "custom" && Array.isArray(args.customPosition) && args.customPosition.length >= 2) {
            posX = Number(args.customPosition[0]);
            posY = Number(args.customPosition[1]);
        }

        // 各风格默认字体与颜色
        var styleDefaults = {
            "cyberpunk": { fontFamily: "Arial", fontSize: 64, color: [0, 1, 1], glowColor: [0, 1, 1] },
            "retro": { fontFamily: "Courier New", fontSize: 56, color: [1, 0.9, 0.6], glowColor: [1, 0.5, 0] },
            "handdrawn": { fontFamily: "Comic Sans MS", fontSize: 60, color: [0.2, 0.2, 0.2], glowColor: [1, 1, 1] },
            "tech": { fontFamily: "Arial", fontSize: 58, color: [0.8, 1, 0.8], glowColor: [0, 1, 0.5] },
            "cinematic": { fontFamily: "Georgia", fontSize: 72, color: [1, 1, 1], glowColor: [1, 1, 0.8] },
            "minimal": { fontFamily: "Arial", fontSize: 56, color: [1, 1, 1], glowColor: [1, 1, 1] },
            "dynamic": { fontFamily: "Impact", fontSize: 80, color: [1, 1, 1], glowColor: [1, 0.2, 0] }
        };

        var defaults = styleDefaults[templateType] || styleDefaults["minimal"];
        var fontFamily = fontOverride.family || defaults.fontFamily;
        var fontSize = fontOverride.size || defaults.fontSize;
        var textColor = args.textColor || defaults.color;
        var glowColor = args.glowColor || defaults.glowColor;

        app.beginUndoGroup("Create Subtitle Template");

        // 创建字幕专用合成
        var subCompName = "Subtitle_" + templateType + "_" + subtitleText.substring(0, 10);
        var subComp = app.project.items.addComp(subCompName, comp.width, comp.height, comp.pixelAspect, comp.duration, comp.frameRate);

        var createdLayers = [];

        // 1. 背景层
        if (background.enabled) {
            try {
                var bgColor = background.color || [0, 0, 0];
                var bgOpacity = background.opacity !== undefined ? Number(background.opacity) : 0.5;
                var bgBlur = background.blur !== undefined ? Number(background.blur) : 0;

                var bgLayer = subComp.layers.addSolid(
                    [Number(bgColor[0]), Number(bgColor[1]), Number(bgColor[2])],
                    "Subtitle BG",
                    comp.width,
                    comp.height * 0.25,
                    comp.pixelAspect,
                    comp.duration
                );
                // 将背景置于底部中央
                try {
                    bgLayer.property("ADBE Transform Group").property("ADBE Position").setValue([comp.width / 2, posY]);
                    bgLayer.property("ADBE Transform Group").property("ADBE Opacity").setValue(bgOpacity * 100);
                } catch (e) {}
                createdLayers.push(bgLayer);

                if (bgBlur > 0) {
                    try {
                        var blurFx = bgLayer.Effects.addProperty("ADBE Fast Blur");
                        blurFx.property("ADBE Fast Blur-0001").setValue(bgBlur);
                    } catch (e) {}
                }
            } catch (e) {}
        }

        // 2. 根据风格创建装饰元素
        if (templateType === "cyberpunk") {
            // 扫描线背景
            try {
                var scanlineLayer = subComp.layers.addSolid([0, 0, 0], "Scanlines", comp.width, comp.height, comp.pixelAspect, comp.duration);
                var vbFx = scanlineLayer.Effects.addProperty("ADBE Venetian Blinds");
                vbFx.property("ADBE Venetian Blinds-0001").setValue(2); // 2 = Horizontal
                vbFx.property("ADBE Venetian Blinds-0002").setValue(3); // Transition Completion
                vbFx.property("ADBE Venetian Blinds-0003").setValue(60); // Direction
                vbFx.property("ADBE Venetian Blinds-0004").setValue(100); // Width
                scanlineLayer.property("ADBE Transform Group").property("ADBE Opacity").setValue(15);
                createdLayers.push(scanlineLayer);
            } catch (e) {}

            // 网格装饰
            try {
                var gridLayer = subComp.layers.addSolid([0, 0, 0], "Grid", comp.width, comp.height, comp.pixelAspect, comp.duration);
                var gridFx = gridLayer.Effects.addProperty("ADBE Grid");
                gridFx.property("ADBE Grid-0001").setValue([100, 100]);
                gridFx.property("ADBE Grid-0006").setValue([0, 1, 1]); // 青色网格
                gridFx.property("ADBE Grid-0007").setValue(0.5); // 边框宽度
                gridLayer.property("ADBE Transform Group").property("ADBE Opacity").setValue(20);
                createdLayers.push(gridLayer);
            } catch (e) {}
        } else if (templateType === "retro") {
            // 暗角层
            try {
                var vigLayer = subComp.layers.addSolid([0.1, 0.05, 0.02], "Vignette", comp.width, comp.height, comp.pixelAspect, comp.duration);
                var rampFx = vigLayer.Effects.addProperty("ADBE Ramp");
                rampFx.property("ADBE Ramp-0001").setValue([0.1, 0.05, 0.02]);
                rampFx.property("ADBE Ramp-0002").setValue([0.3, 0.2, 0.1]);
                rampFx.property("ADBE Ramp-0005").setValue(2); // Radial Ramp
                vigLayer.property("ADBE Transform Group").property("ADBE Opacity").setValue(40);
                createdLayers.push(vigLayer);
            } catch (e) {}

            // 噪点
            try {
                var noiseLayer = subComp.layers.addSolid([0.5, 0.5, 0.5], "Noise", comp.width, comp.height, comp.pixelAspect, comp.duration);
                var noiseFx = noiseLayer.Effects.addProperty("ADBE Noise");
                noiseFx.property("ADBE Noise-0001").setValue(10); // Amount
                noiseLayer.property("ADBE Transform Group").property("ADBE Opacity").setValue(15);
                noiseLayer.blendingMode = BlendingMode.SCREEN;
                createdLayers.push(noiseLayer);
            } catch (e) {}
        } else if (templateType === "cinematic") {
            // 电影黑边
            try {
                var barHeight = comp.height * 0.1;
                var topBar = subComp.layers.addSolid([0, 0, 0], "Top Bar", comp.width, barHeight, comp.pixelAspect, comp.duration);
                topBar.property("ADBE Transform Group").property("ADBE Position").setValue([comp.width / 2, barHeight / 2]);
                createdLayers.push(topBar);

                var bottomBar = subComp.layers.addSolid([0, 0, 0], "Bottom Bar", comp.width, barHeight, comp.pixelAspect, comp.duration);
                bottomBar.property("ADBE Transform Group").property("ADBE Position").setValue([comp.width / 2, comp.height - barHeight / 2]);
                createdLayers.push(bottomBar);
            } catch (e) {}
        } else if (templateType === "handdrawn") {
            // 纸张纹理背景
            try {
                var paperLayer = subComp.layers.addSolid([0.95, 0.92, 0.88], "Paper", comp.width, comp.height, comp.pixelAspect, comp.duration);
                var fnFx = paperLayer.Effects.addProperty("ADBE Fractal Noise");
                fnFx.property("ADBE Fractal Noise-0001").setValue(1); // Subscale
                fnFx.property("ADBE Fractal Noise-0010").setValue(15); // Subscale
                fnFx.property("ADBE Fractal Noise-0011").setValue(0.3); // Brightness
                fnFx.property("ADBE Fractal Noise-0012").setValue(0.8); // Contrast
                paperLayer.property("ADBE Transform Group").property("ADBE Opacity").setValue(30);
                createdLayers.push(paperLayer);
            } catch (e) {}
        } else if (templateType === "tech") {
            // 科技网格
            try {
                var techGrid = subComp.layers.addSolid([0, 0, 0], "Tech Grid", comp.width, comp.height, comp.pixelAspect, comp.duration);
                var tgFx = techGrid.Effects.addProperty("ADBE Grid");
                tgFx.property("ADBE Grid-0001").setValue([80, 80]);
                tgFx.property("ADBE Grid-0006").setValue([0, 0.8, 0.2]);
                tgFx.property("ADBE Grid-0007").setValue(0.3);
                techGrid.property("ADBE Transform Group").property("ADBE Opacity").setValue(25);
                createdLayers.push(techGrid);
            } catch (e) {}
        } else if (templateType === "dynamic") {
            // 速度线背景
            try {
                var speedLayer = subComp.layers.addSolid([0.1, 0.1, 0.1], "Speed Lines", comp.width, comp.height, comp.pixelAspect, comp.duration);
                var mtFx = speedLayer.Effects.addProperty("ADBE Motion Tile");
                mtFx.property("ADBE Motion Tile-0001").setValue(200);
                mtFx.property("ADBE Motion Tile-0005").setValue(true); // Mirror Edges
                var dirBlur = speedLayer.Effects.addProperty("ADBE Directional Blur");
                dirBlur.property("ADBE Directional Blur-0001").setValue(20);
                dirBlur.property("ADBE Directional Blur-0002").setValue(90); // Horizontal
                speedLayer.property("ADBE Transform Group").property("ADBE Opacity").setValue(20);
                createdLayers.push(speedLayer);
            } catch (e) {}
        }

        // 3. 创建文字图层
        var textLayer = subComp.layers.addText(subtitleText);
        textLayer.name = "Subtitle Text";
        var sourceTextProp = textLayer.property("ADBE Text Properties").property("ADBE Text Document");
        var textDoc = sourceTextProp.value;
        try { textDoc.fontSize = fontSize; } catch (e) {}
        try { textDoc.fillColor = [Number(textColor[0]), Number(textColor[1]), Number(textColor[2])]; } catch (e) {}
        try { textDoc.font = fontFamily; } catch (e) {}
        try { textDoc.justification = ParagraphJustification.CENTER_JUSTIFY; } catch (e) {}
        sourceTextProp.setValue(textDoc);

        try {
            textLayer.property("ADBE Transform Group").property("ADBE Position").setValue([comp.width / 2, posY]);
        } catch (e) {}
        createdLayers.push(textLayer);

        // 4. 应用风格专属效果
        if (templateType === "cyberpunk") {
            addGlowToLayer(textLayer, glowColor, 30, 1.5);
            try {
                var saberFx = textLayer.Effects.addProperty("VC Saber");
                saberFx.property("ADBE VC Saber-0003").setValue(100);
                saberFx.property("ADBE VC Saber-0004").setValue(20);
                saberFx.property("ADBE VC Saber-0005").setValue(glowColor);
            } catch (e) {}
        } else if (templateType === "retro") {
            addGlowToLayer(textLayer, [0.8, 0.6, 0.3], 15, 0.8);
            try {
                var triFx = textLayer.Effects.addProperty("ADBE Tritone");
                triFx.property("ADBE Tritone-0001").setValue([0.2, 0.1, 0.05]); // Shadows
                triFx.property("ADBE Tritone-0002").setValue([0.6, 0.4, 0.2]); // Midtones
                triFx.property("ADBE Tritone-0003").setValue([1, 0.9, 0.7]); // Highlights
            } catch (e) {}
        } else if (templateType === "handdrawn") {
            try {
                var reFx = textLayer.Effects.addProperty("ADBE Roughen Edges");
                reFx.property("ADBE Roughen Edges-0001").setValue(3); // Edge Type
                reFx.property("ADBE Roughen Edges-0002").setValue(5); // Border
                reFx.property("ADBE Roughen Edges-0003").setValue(0.3); // Edge Sharpness
                reFx.property("ADBE Roughen Edges-0004").setValue(0.5); // Fractal Influence
            } catch (e) {}
            addShadowToLayer(textLayer, [0.3, 0.3, 0.3], 3, 5, 135);
        } else if (templateType === "tech") {
            addGlowToLayer(textLayer, glowColor, 20, 1);
            try {
                var ccFx = textLayer.Effects.addProperty("ADBE Color Control"); // 占位，实际添加 Scanline
                // 用 Venetian Blinds 模拟扫描线
                var techScan = textLayer.Effects.addProperty("ADBE Venetian Blinds");
                techScan.property("ADBE Venetian Blinds-0001").setValue(2);
                techScan.property("ADBE Venetian Blinds-0002").setValue(2);
                techScan.property("ADBE Venetian Blinds-0004").setValue(40);
            } catch (e) {}
        } else if (templateType === "cinematic") {
            addShadowToLayer(textLayer, [0, 0, 0], 8, 15, 135);
            addGlowToLayer(textLayer, [1, 1, 0.9], 10, 0.5);
        } else if (templateType === "minimal") {
            addShadowToLayer(textLayer, [0, 0, 0], 2, 4, 135);
        } else if (templateType === "dynamic") {
            addGlowToLayer(textLayer, glowColor, 25, 1.2);
            try {
                var mbFx = textLayer.Effects.addProperty("ADBE Motion Blur");
                mbFx.property("ADBE Motion Blur-0001").setValue(180); // Shutter Angle
                mbFx.property("ADBE Motion Blur-0002").setValue(-90); // Shutter Phase
            } catch (e) {}
        }

        // 5. 应用附加效果
        for (var ae = 0; ae < additionalEffects.length; ae++) {
            var effName = String(additionalEffects[ae]).toLowerCase();
            if (effName === "glow") {
                addGlowToLayer(textLayer, glowColor, 20, 1);
            } else if (effName === "shadow") {
                addShadowToLayer(textLayer, [0, 0, 0], 5, 10, 135);
            } else if (effName === "scanline") {
                try {
                    var slFx = textLayer.Effects.addProperty("ADBE Venetian Blinds");
                    slFx.property("ADBE Venetian Blinds-0001").setValue(2);
                    slFx.property("ADBE Venetian Blinds-0002").setValue(1);
                    slFx.property("ADBE Venetian Blinds-0004").setValue(60);
                } catch (e) {}
            } else if (effName === "vignette") {
                try {
                    var vigFx = textLayer.Effects.addProperty("ADBE Glo2i");
                    vigFx.property("ADBE Glo2i-0001").setValue([0, 0, 0]);
                    vigFx.property("ADBE Glo2i-0002").setValue(comp.width * 0.4);
                    vigFx.property("ADBE Glo2i-0004").setValue(2); // Glow Dimensions: Horizontal & Vertical
                    vigFx.property("ADBE Glo2i-0005").setValue(3); // Glow Colors: A & B Colors
                } catch (e) {}
            }
        }

        // 6. 应用动画
        var animInfo = [];
        var time = 0;
        var animDuration = 1.5;
        if (animation === "fade") {
            try {
                var op = textLayer.property("ADBE Transform Group").property("ADBE Opacity");
                op.setValueAtTime(time, 0);
                op.setValueAtTime(time + 0.5, 100);
                op.setValueAtTime(subComp.duration - 0.5, 100);
                op.setValueAtTime(subComp.duration, 0);
                animInfo.push("fade");
            } catch (e) {}
        } else if (animation === "slide") {
            try {
                var slideOp = textLayer.property("ADBE Transform Group").property("ADBE Opacity");
                slideOp.setValueAtTime(time, 0);
                slideOp.setValueAtTime(time + 0.5, 100);
                slideOp.setValueAtTime(subComp.duration - 0.5, 100);
                slideOp.setValueAtTime(subComp.duration, 0);

                var slidePos = textLayer.property("ADBE Transform Group").property("ADBE Position");
                var startPos = [comp.width / 2, posY + 50];
                var endPos = [comp.width / 2, posY];
                slidePos.setValueAtTime(time, startPos);
                slidePos.setValueAtTime(time + animDuration, endPos);
                animInfo.push("slide");
            } catch (e) {}
        } else if (animation === "typewriter") {
            try {
                var animatorsGroup = textLayer.property("ADBE Text Properties").property("ADBE Text Animators");
                var typeAnim = animatorsGroup.addProperty("ADBE Text Animator");
                var typeSel = typeAnim.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
                var typeProps = typeAnim.property("ADBE Text Animator Properties");
                try { typeProps.addProperty("ADBE Text Opacity").setValue(0); } catch (e) {}
                var startProp = typeSel.property("Start") || typeSel.property(1);
                if (startProp) {
                    startProp.setValueAtTime(time, 0);
                    startProp.setValueAtTime(time + animDuration, 100);
                }
                animInfo.push("typewriter");
            } catch (e) {}
        } else if (animation === "glitch") {
            try {
                var glitchCount = 8;
                var glitchPos = textLayer.property("ADBE Transform Group").property("ADBE Position");
                for (var g = 0; g < glitchCount; g++) {
                    var gt = time + (g / glitchCount) * 0.5;
                    var gx = comp.width / 2 + (Math.random() - 0.5) * 20;
                    glitchPos.setValueAtTime(gt, [gx, posY]);
                }
                glitchPos.setValueAtTime(time + 0.6, [comp.width / 2, posY]);
                animInfo.push("glitch");
            } catch (e) {}
        }

        // 7. 将字幕合成嵌套到主合成
        var nestedLayer = comp.layers.add(subComp);
        nestedLayer.name = subCompName;
        nestedLayer.startTime = comp.time;

        app.endUndoGroup();

        return buildSuccess({
            message: "字幕模板创建成功",
            templateType: templateType,
            precompName: subCompName,
            layerIndex: nestedLayer.index,
            layerName: nestedLayer.name,
            fontFamily: fontFamily,
            fontSize: fontSize,
            textColor: textColor,
            position: [posX, posY],
            animationApplied: animInfo,
            backgroundEnabled: background.enabled
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = createSubtitleTemplate(args);
$.write(result);
