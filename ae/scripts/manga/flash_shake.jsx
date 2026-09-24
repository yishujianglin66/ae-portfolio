// ae/scripts/manga/flash_shake.jsx
// 漫剪特效：闪白 + 震动（在 drop 点触发）
// 参数通过 Bridge executeAtomScript 注入，或作为独立脚本执行
// 用法: 通过 ae_command.json {command:"executeAtomScript", args:{script: "..."}} 下发

(function() {
    // ===== 参数（由 Python 端参数化注入） =====
    var COMP_NAME = "{{COMP_NAME}}";          // 目标合成名
    var LAYER_NAME = "{{LAYER_NAME}}";        // 目标图层名
    var DROP_TIME = {{DROP_TIME}};            // drop 时间点（秒）
    var FPS = {{FPS}};                        // 帧率
    var FLASH_FRAMES = {{FLASH_FRAMES}};      // 闪白持续帧数（默认 2）
    var SHAKE_AMP = {{SHAKE_AMP}};            // 震动幅度（像素，默认 15）
    var SHAKE_FREQ = {{SHAKE_FREQ}};          // 震动频率（Hz，默认 30）
    var SHAKE_DECAY_FRAMES = {{SHAKE_DECAY}}; // 震动衰减帧数（默认 8）

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
        // 如果找不到指定合成，使用活动合成
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
        layer = comp.layer(1); // 默认使用最顶层图层
    }

    app.beginUndoGroup("MangaFlashShake");

    // ===== 1. 闪白效果 =====
    // 创建一个白色固态层作为闪白层
    var flashLayer = comp.layers.addSolid([1, 1, 1], "Flash_White", comp.width, comp.height, comp.pixelAspect);
    flashLayer.moveBefore(layer);

    // 设置闪白层的时间范围
    var flashStart = DROP_TIME - (FLASH_FRAMES / FPS);
    var flashEnd = DROP_TIME + (FLASH_FRAMES / FPS);
    flashLayer.inPoint = flashStart;
    flashLayer.outPoint = flashEnd;

    // 透明度关键帧：快速淡入淡出
    var opacity = flashLayer.property("Transform").property("Opacity");
    opacity.setValueAtTime(flashStart, 0);
    opacity.setValueAtTime(DROP_TIME, 100);
    opacity.setValueAtTime(flashEnd, 0);

    // 设置缓动
    for (var k = 1; k <= opacity.numKeys; k++) {
        var easeIn = new KeyframeEase(0, 90);
        var easeOut = new KeyframeEase(0, 90);
        opacity.setTemporalEaseAtKey(k, [easeIn], [easeOut]);
    }

    // ===== 2. 震动效果（表达式） =====
    // 对目标图层的位置属性添加震动表达式
    var position = layer.property("Transform").property("Position");
    var shakeExpr = [
        "// Manga Shake Expression",
        "var amp = " + SHAKE_AMP + ";",
        "var freq = " + SHAKE_FREQ + ";",
        "var decayFrames = " + SHAKE_DECAY_FRAMES + ";",
        "var dropTime = " + DROP_TIME + ";",
        "var fps = " + FPS + ";",
        "",
        "var t = time - dropTime;",
        "if (t < 0 || t > decayFrames / fps) {",
        "    value;",
        "} else {",
        "    var decay = 1.0 - t / (decayFrames / fps);",
        "    var dx = amp * decay * Math.sin(t * freq * 2 * Math.PI);",
        "    var dy = amp * decay * Math.cos(t * freq * 2 * Math.PI * 1.3);",
        "    value + [dx, dy];",
        "}"
    ].join("\n");

    position.expression = shakeExpr;

    // ===== 3. 缩放冲击（可选：drop 瞬间轻微放大） =====
    var scale = layer.property("Transform").property("Scale");
    var impactStart = DROP_TIME - 1.0 / FPS;
    var impactPeak = DROP_TIME;
    var impactEnd = DROP_TIME + 4.0 / FPS;
    scale.setValueAtTime(impactStart, [100, 100]);
    scale.setValueAtTime(impactPeak, [103, 103]);
    scale.setValueAtTime(impactEnd, [100, 100]);

    // 缓动
    for (var k = 1; k <= scale.numKeys; k++) {
        var ei = new KeyframeEase(0, 80);
        var eo = new KeyframeEase(0, 80);
        scale.setTemporalEaseAtKey(k, [ei], [eo]);
    }

    app.endUndoGroup();

    // 返回结果
    JSON.stringify({
        success: true,
        comp: comp.name,
        layer: layer.name,
        flashLayer: flashLayer.name,
        dropTime: DROP_TIME,
        effectsApplied: ["flash", "shake", "scale_impact"]
    });
})();
