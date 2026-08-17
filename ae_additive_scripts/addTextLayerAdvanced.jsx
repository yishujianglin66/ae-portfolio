// addTextLayerAdvanced.jsx
// 高级艺术字创建 - 支持填充样式、描边、阴影、发光、文字变形、路径、3D文字
// Phase 5-2 扩展 - 文字系统全面升级

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function addTextLayerAdvanced(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (!args.text) {
            return buildError("E110", "E110: text 参数必填");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        // 参数解析与默认值
        var name = args.name || args.text.substring(0, 20);
        var fontSize = args.fontSize !== undefined ? Number(args.fontSize) : 72;
        var fontFamily = args.fontFamily || "Arial";
        var fillType = args.fillType || "solid";
        var fillColor = args.fillColor || [1, 1, 1];
        var position = args.position || [comp.width / 2, comp.height / 2];
        var justification = args.justification || "center";

        // 对齐方式映射
        var justMap = {
            "left": ParagraphJustification.LEFT_JUSTIFY,
            "center": ParagraphJustification.CENTER_JUSTIFY,
            "right": ParagraphJustification.RIGHT_JUSTIFY
        };
        if (!justMap.hasOwnProperty(justification)) {
            return buildError("E111", "E111: 不支持的对齐方式: " + justification);
        }

        // 描边参数
        var stroke = args.stroke || { enabled: false };
        // 阴影参数
        var shadow = args.shadow || { enabled: false };
        // 发光参数
        var glow = args.glow || { enabled: false };
        // 变形参数
        var transform = args.transform || { bend: 0, twist: 0, shear: 0 };
        // 路径参数
        var path = args.path || { enabled: false };
        // 3D参数
        var text3D = args.text3D || { enabled: false };

        app.beginUndoGroup("Add Advanced Text Layer");

        // 创建文字图层
        var textLayer = comp.layers.addText(String(args.text));
        if (name) {
            textLayer.name = name;
        }

        // 设置位置
        try {
            textLayer.property("ADBE Transform Group").property("ADBE Position").setValue(
                [Number(position[0]), Number(position[1])]
            );
        } catch (e) {}

        // 通过 TextDocument 设置基本文字属性
        var sourceTextProp = textLayer.property("ADBE Text Properties").property("ADBE Text Document");
        var textDoc = sourceTextProp.value;

        try { textDoc.fontSize = fontSize; } catch (e) {}
        try { textDoc.font = fontFamily; } catch (e) {}
        try { textDoc.justification = justMap[justification]; } catch (e) {}

        // 填充样式处理
        var fillApplied = "solid";
        if (fillType === "gradient") {
            // 渐变填充：使用 Gradient Ramp 效果模拟
            fillApplied = "gradient";
            try {
                var rampFx = textLayer.Effects.addProperty("ADBE Ramp");
                var gradColors = args.gradient && args.gradient.colors ? args.gradient.colors : [[1,0,0,0],[0,0,1,1]];
                var gradAngle = args.gradient && args.gradient.angle !== undefined ? args.gradient.angle : 90;

                // 设置起始/结束颜色（取渐变数组的首尾）
                if (gradColors.length >= 2) {
                    var startColor = gradColors[0];
                    var endColor = gradColors[gradColors.length - 1];
                    try { rampFx.property("ADBE Ramp-0001").setValue([Number(startColor[0]), Number(startColor[1]), Number(startColor[2])]); } catch (e) {}
                    try { rampFx.property("ADBE Ramp-0002").setValue([Number(endColor[0]), Number(endColor[1]), Number(endColor[2])]); } catch (e) {}
                }
                // 设置渐变方向（通过 Start/End of Ramp 位置）
                var rad = (gradAngle - 90) * Math.PI / 180;
                var cx = comp.width / 2;
                var cy = comp.height / 2;
                var dist = Math.min(comp.width, comp.height) * 0.4;
                try {
                    rampFx.property("ADBE Ramp-0003").setValue([cx - Math.cos(rad) * dist, cy - Math.sin(rad) * dist]);
                    rampFx.property("ADBE Ramp-0004").setValue([cx + Math.cos(rad) * dist, cy + Math.sin(rad) * dist]);
                } catch (e) {}
                // 将 Ramp 与文字 Alpha 混合（使用 Alpha Multiply）
                try { rampFx.property("ADBE Ramp-0006").setValue(1); } catch (e) {} // 1 = Alpha Multiply
            } catch (e) {}
        } else if (fillType === "pattern") {
            // 图案填充：使用 Cell Pattern 效果作为填充基底
            fillApplied = "pattern";
            try {
                var cellFx = textLayer.Effects.addProperty("ADBE Cell Pattern");
                try { cellFx.property("ADBE Cell Pattern-0001").setValue(6); } catch (e) {} // Plaid 图案
                try { cellFx.property("ADBE Cell Pattern-0002").setValue([comp.width / 2, comp.height / 2]); } catch (e) {}
                try { cellFx.property("ADBE Cell Pattern-0003").setValue(50); } catch (e) {}
                try { cellFx.property("ADBE Cell Pattern-0004").setValue(100); } catch (e) {}
                // 混合模式设为 Stencil Alpha
                try { cellFx.property("ADBE Cell Pattern-0010").setValue(3); } catch (e) {}
            } catch (e) {}
        } else {
            // 纯色填充
            try { textDoc.fillColor = [Number(fillColor[0]), Number(fillColor[1]), Number(fillColor[2])]; } catch (e) {}
        }

        sourceTextProp.setValue(textDoc);

        // 应用图层样式 - 描边
        var appliedStyles = [];
        if (stroke.enabled) {
            try {
                var lsStroke = textLayer.property("ADBE Layer Styles").property("ADBE Stroke");
                lsStroke.property("ADBE Stroke-0001").setValue(true); // 启用
                lsStroke.property("ADBE Stroke-0002").setValue(1); // 填充类型：颜色
                var strokeColor = stroke.color || [0, 0, 0];
                lsStroke.property("ADBE Stroke-0003").setValue([Number(strokeColor[0]), Number(strokeColor[1]), Number(strokeColor[2])]);
                lsStroke.property("ADBE Stroke-0004").setValue(stroke.width !== undefined ? Number(stroke.width) : 2);
                var posMap = {"inside": 1, "center": 2, "outside": 3};
                var strokePos = posMap[String(stroke.position).toLowerCase()] || 2;
                lsStroke.property("ADBE Stroke-0005").setValue(strokePos);
                appliedStyles.push("stroke");
            } catch (e) {
                // 回退：使用 Stroke 效果
                try {
                    var strokeFx = textLayer.Effects.addProperty("ADBE Stroke");
                    strokeFx.property("ADBE Stroke-0002").setValue(3); // All Masks
                    strokeFx.property("ADBE Stroke-0003").setValue(stroke.width !== undefined ? Number(stroke.width) : 2);
                    var sc = stroke.color || [0, 0, 0];
                    strokeFx.property("ADBE Stroke-0006").setValue([Number(sc[0]), Number(sc[1]), Number(sc[2])]);
                    appliedStyles.push("stroke_effect");
                } catch (e2) {}
            }
        }

        // 应用图层样式 - 阴影
        if (shadow.enabled) {
            try {
                var lsShadow = textLayer.property("ADBE Layer Styles").property("ADBE Drop Shadow");
                lsShadow.property("ADBE Drop Shadow-0001").setValue(true);
                var shadowColor = shadow.color || [0, 0, 0];
                lsShadow.property("ADBE Drop Shadow-0002").setValue([Number(shadowColor[0]), Number(shadowColor[1]), Number(shadowColor[2])]);
                lsShadow.property("ADBE Drop Shadow-0003").setValue(shadow.opacity !== undefined ? Number(shadow.opacity) : 75);
                lsShadow.property("ADBE Drop Shadow-0004").setValue(shadow.angle !== undefined ? Number(shadow.angle) : 135);
                lsShadow.property("ADBE Drop Shadow-0005").setValue(shadow.distance !== undefined ? Number(shadow.distance) : 5);
                lsShadow.property("ADBE Drop Shadow-0006").setValue(shadow.blur !== undefined ? Number(shadow.blur) : 10);
                appliedStyles.push("shadow");
            } catch (e) {
                // 回退：使用 Drop Shadow 效果
                try {
                    var shadowFx = textLayer.Effects.addProperty("ADBE Drop Shadow");
                    var sc2 = shadow.color || [0, 0, 0];
                    shadowFx.property("ADBE Drop Shadow-0002").setValue([Number(sc2[0]), Number(sc2[1]), Number(sc2[2])]);
                    shadowFx.property("ADBE Drop Shadow-0004").setValue(shadow.angle !== undefined ? Number(shadow.angle) : 135);
                    shadowFx.property("ADBE Drop Shadow-0005").setValue(shadow.distance !== undefined ? Number(shadow.distance) : 5);
                    shadowFx.property("ADBE Drop Shadow-0006").setValue(shadow.blur !== undefined ? Number(shadow.blur) : 10);
                    appliedStyles.push("shadow_effect");
                } catch (e2) {}
            }
        }

        // 应用图层样式 - 发光
        if (glow.enabled) {
            try {
                var lsGlow = textLayer.property("ADBE Layer Styles").property("ADBE Outer Glow");
                lsGlow.property("ADBE Outer Glow-0001").setValue(true);
                var glowColor = glow.color || [1, 0.5, 0];
                lsGlow.property("ADBE Outer Glow-0002").setValue([Number(glowColor[0]), Number(glowColor[1]), Number(glowColor[2])]);
                lsGlow.property("ADBE Outer Glow-0003").setValue(glow.intensity !== undefined ? Number(glow.intensity) : 75);
                lsGlow.property("ADBE Outer Glow-0006").setValue(glow.radius !== undefined ? Number(glow.radius) : 20);
                appliedStyles.push("glow");
            } catch (e) {
                // 回退：使用 Glow 效果
                try {
                    var glowFx = textLayer.Effects.addProperty("ADBE Glo2i");
                    var gc2 = glow.color || [1, 0.5, 0];
                    glowFx.property("ADBE Glo2i-0001").setValue([Number(gc2[0]), Number(gc2[1]), Number(gc2[2])]);
                    glowFx.property("ADBE Glo2i-0002").setValue(glow.radius !== undefined ? Number(glow.radius) : 20);
                    glowFx.property("ADBE Glo2i-0003").setValue(glow.intensity !== undefined ? Number(glow.intensity) : 1);
                    appliedStyles.push("glow_effect");
                } catch (e2) {}
            }
        }

        // 文字变形（使用 Wave Warp / Transform 效果）
        var appliedTransforms = [];
        if (transform.bend !== undefined && Number(transform.bend) !== 0) {
            try {
                var waveFx = textLayer.Effects.addProperty("ADBE Wave Warp");
                waveFx.property("ADBE Wave Warp-0001").setValue(6); // Arc 波形
                waveFx.property("ADBE Wave Warp-0002").setValue(Math.abs(Number(transform.bend)));
                waveFx.property("ADBE Wave Warp-0004").setValue(Number(transform.bend) > 0 ? 0 : 180); // 方向
                waveFx.property("ADBE Wave Warp-0006").setValue(0.5); // 相位居中
                appliedTransforms.push("bend");
            } catch (e) {}
        }
        if (transform.twist !== undefined && Number(transform.twist) !== 0) {
            try {
                var twistFx = textLayer.Effects.addProperty("ADBE Twirl");
                twistFx.property("ADBE Twirl-0002").setValue(Number(transform.twist));
                twistFx.property("ADBE Twirl-0003").setValue(comp.width / 2);
                twistFx.property("ADBE Twirl-0004").setValue(comp.height / 2);
                appliedTransforms.push("twist");
            } catch (e) {}
        }
        if (transform.shear !== undefined && Number(transform.shear) !== 0) {
            try {
                var shearFx = textLayer.Effects.addProperty("ADBE Transform");
                shearFx.property("ADBE Transform-0005").setValue(Number(transform.shear));
                appliedTransforms.push("shear");
            } catch (e) {}
        }

        // 文字路径
        var pathApplied = false;
        if (path.enabled) {
            try {
                var pathShape = String(path.pathShape || "circle").toLowerCase();
                // 在文字图层上创建蒙版路径
                var mask = null;
                if (pathShape === "circle") {
                    mask = textLayer.Masks.addProperty("ADBE Mask Atom");
                    var cx = comp.width / 2;
                    var cy = comp.height / 2;
                    var r = Math.min(comp.width, comp.height) * 0.35;
                    var vertices = [];
                    var inTangents = [];
                    var outTangents = [];
                    for (var i = 0; i < 4; i++) {
                        var angle = i * Math.PI / 2;
                        vertices.push([cx + Math.cos(angle) * r, cy + Math.sin(angle) * r]);
                        var tLen = r * 0.552;
                        inTangents.push([-Math.cos(angle) * tLen, -Math.sin(angle) * tLen]);
                        outTangents.push([Math.cos(angle) * tLen, Math.sin(angle) * tLen]);
                    }
                    mask.maskShape.setValue(new Shape(vertices, inTangents, outTangents, true));
                } else if (pathShape === "wave") {
                    mask = textLayer.Masks.addProperty("ADBE Mask Atom");
                    var wv = [];
                    var wi = [];
                    var wo = [];
                    var segments = 8;
                    var amp = Math.min(comp.width, comp.height) * 0.15;
                    var baseY = comp.height / 2;
                    for (var j = 0; j <= segments; j++) {
                        var t = j / segments;
                        wv.push([t * comp.width, baseY + Math.sin(t * Math.PI * 2) * amp]);
                        wi.push([0, 0]);
                        wo.push([0, 0]);
                    }
                    mask.maskShape.setValue(new Shape(wv, wi, wo, false));
                } else if (pathShape === "custom" && path.customPath && path.customPath.length >= 2) {
                    mask = textLayer.Masks.addProperty("ADBE Mask Atom");
                    var cv = [];
                    var ci = [];
                    var co = [];
                    var cp = path.customPath;
                    for (var k = 0; k < cp.length; k++) {
                        cv.push([Number(cp[k][0]), Number(cp[k][1])]);
                        ci.push([0, 0]);
                        co.push([0, 0]);
                    }
                    mask.maskShape.setValue(new Shape(cv, ci, co, false));
                }

                // 设置文字沿路径排列（通过 Text Path Options）
                if (mask) {
                    var pathOpts = textLayer.property("ADBE Text Properties").property("ADBE Text Path Options");
                    pathOpts.property("ADBE Text Path Options-0001").setValue(2); // 蒙版路径
                    pathOpts.property("ADBE Text Path Options-0002").setValue(1); // 第一个蒙版
                    pathOpts.property("ADBE Text Path Options-0003").setValue(false); // 反转路径
                    pathApplied = true;
                }
            } catch (e) {
                pathApplied = false;
            }
        }

        // 3D 文字
        var applied3D = [];
        if (text3D.enabled) {
            try {
                textLayer.threeDLayer = true;
                applied3D.push("3d_enabled");

                var depth = text3D.depth !== undefined ? Number(text3D.depth) : 50;
                var bevel = text3D.bevel === true || text3D.bevel === "true";
                var material = text3D.material || "standard";

                // 设置几何选项（挤出深度）
                try {
                    var geom = textLayer.property("ADBE Material Options Group");
                    // 挤出深度通过 Text 特有的 3D 属性设置
                    // 在 ExtendScript 中，Text 3D 参数可能在 Text Properties 下的某个组
                    var text3DProp = textLayer.property("ADBE Text Properties").property("ADBE Text Animate Properties");
                    // 实际上 AE 的 Text 3D 参数（深度/倒角）是在 Layer > Geometry Options 中
                    var geoOpt = textLayer.property("ADBE Extrude Options Group");
                    if (geoOpt) {
                        geoOpt.property("ADBE Extrude Options Group-0001").setValue(depth); // Bevel Depth
                        applied3D.push("depth");
                    }
                } catch (e) {}

                // 若启用倒角，尝试设置倒角样式
                if (bevel) {
                    try {
                        var bevelProp = textLayer.property("ADBE Extrude Options Group");
                        if (bevelProp) {
                            bevelProp.property("ADBE Extrude Options Group-0002").setValue(2); // Angular Bevel
                            applied3D.push("bevel");
                        }
                    } catch (e) {}
                }

                // 材质设置（尝试设置材质预设）
                if (material !== "standard") {
                    try {
                        var matOpt = textLayer.property("ADBE Material Options Group");
                        if (matOpt) {
                            var matMap = {"metal": 2, "plastic": 3, "glass": 4};
                            if (matMap[material]) {
                                matOpt.property("ADBE Material Options Group-0001").setValue(matMap[material]);
                                applied3D.push("material_" + material);
                            }
                        }
                    } catch (e) {}
                }
            } catch (e) {}
        }

        var finalIndex = textLayer.index;
        var finalName = textLayer.name;

        app.endUndoGroup();

        return buildSuccess({
            message: "高级艺术字图层创建成功",
            layerIndex: finalIndex,
            layerName: finalName,
            fontSize: fontSize,
            fontFamily: fontFamily,
            fillType: fillApplied,
            justification: justification,
            stylesApplied: appliedStyles,
            transformsApplied: appliedTransforms,
            pathApplied: pathApplied,
            threeDApplied: applied3D
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = addTextLayerAdvanced(args);
$.write(result);
