// ae/scripts/amv/parallax_setup.jsx
// 静止系 AMV：2.5D 视差初始化
// 将静态图拆分为前景/中景/背景图层，启用 3D + 设置 Z 深度
// 用法: 通过 ae_command.json {command:"runScript", args:{code: "..."}} 下发

(function() {
    // ===== 参数（由 Python 端参数化注入） =====
    var COMP_NAME = "{{COMP_NAME}}";
    var BG_DEPTH = {{BG_DEPTH}};               // 背景 Z 深度（默认 -200）
    var MID_DEPTH = {{MID_DEPTH}};             // 中景 Z 深度（默认 0）
    var FG_DEPTH = {{FG_DEPTH}};               // 前景 Z 深度（默认 150）
    var SCALE_COMP = {{SCALE_COMP}};           // 是否缩放补偿（true/false）
    var EDGE_PAD = {{EDGE_PAD}};               // 边缘扩展像素（默认 100）

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

    app.beginUndoGroup("AMV_ParallaxSetup");

    var centerX = comp.width / 2;
    var centerY = comp.height / 2;
    var layersProcessed = [];

    // ===== 识别并设置图层深度 =====
    // 按名称匹配：Background/Midground/Foreground
    // 如果没有命名，按图层顺序（底层=背景，顶层=前景）
    var bgLayer = null, midLayer = null, fgLayer = null;

    for (var i = 1; i <= comp.numLayers; i++) {
        var l = comp.layer(i);
        var name = l.name.toLowerCase();
        if (name.indexOf("background") >= 0 || name.indexOf("bg") >= 0) {
            bgLayer = l;
        } else if (name.indexOf("midground") >= 0 || name.indexOf("mid") >= 0) {
            midLayer = l;
        } else if (name.indexOf("foreground") >= 0 || name.indexOf("fg") >= 0) {
            fgLayer = l;
        }
    }

    // 如果没有命名匹配，按图层索引分配
    if (!bgLayer && !midLayer && !fgLayer && comp.numLayers >= 3) {
        bgLayer = comp.layer(comp.numLayers);     // 最底层
        midLayer = comp.layer(Math.ceil(comp.numLayers / 2));  // 中间
        fgLayer = comp.layer(1);                  // 最顶层
    } else if (!bgLayer && comp.numLayers >= 1) {
        bgLayer = comp.layer(comp.numLayers);
    }

    // ===== 设置 3D + Z 深度 =====
    function setupLayer3D(layer, zDepth, label) {
        if (!layer) return;

        layer.threeDLayer = true;

        var pos = layer.property("Position");
        var currentPos = pos.value;
        // 设置为 3D 位置 [x, y, z]
        pos.setValue([centerX, centerY, zDepth]);

        // 缩放补偿：Z 深度越远，需要放大才能填满画面
        if (SCALE_COMP && zDepth !== 0) {
            var cameraZ = -800; // 假设摄像机在 Z=-800
            var distToCamera = Math.abs(cameraZ - zDepth);
            var baseDist = Math.abs(cameraZ); // 中景到摄像机距离
            var scaleFactor = distToCamera / baseDist;
            var scalePercent = scaleFactor * 100;
            layer.property("Scale").setValue([scalePercent, scalePercent, scalePercent]);
        }

        // 边缘扩展（防止视差运动时露出边缘）
        if (EDGE_PAD > 0 && zDepth < MID_DEPTH) {
            // 背景需要额外放大以覆盖边缘
            var currentScale = layer.property("Scale").value;
            var padScale = 100 + (EDGE_PAD / comp.width * 100) * 2;
            layer.property("Scale").setValue([
                Math.max(currentScale[0], padScale),
                Math.max(currentScale[1], padScale),
                currentScale.length > 2 ? currentScale[2] : 100
            ]);
        }

        layersProcessed.push({
            name: layer.name,
            label: label,
            zDepth: zDepth,
            threeD: true
        });
    }

    setupLayer3D(bgLayer, BG_DEPTH, "background");
    setupLayer3D(midLayer, MID_DEPTH, "midground");
    setupLayer3D(fgLayer, FG_DEPTH, "foreground");

    // ===== 设置合成渲染器为 3D =====
    try {
        comp.renderer = "ADBE Advanced 3d";
    } catch(e) {
        // 某些版本不支持切换渲染器
    }

    app.endUndoGroup();

    JSON.stringify({
        success: true,
        comp: comp.name,
        layersProcessed: layersProcessed,
        depths: {background: BG_DEPTH, midground: MID_DEPTH, foreground: FG_DEPTH},
        scaleCompensation: SCALE_COMP,
        edgePadding: EDGE_PAD
    });
})();
