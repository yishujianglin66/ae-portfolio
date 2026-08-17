// textImpactMaster.jsx
// 文字打击感主控 - 高燃/AMV 风格文字动画（P4-B 实测验证版）
// 用法: textImpactMaster(args)
// args = {action, ...params}
//
// 支持的 action:
//   "impact"    → 打击感入场：大缩放砸入 + 落地抖动表达式 + 可选白色闪光层
//   "beat_sync" → 按 beat 时间戳做缩放脉冲（卡点）
//   "rgb_glitch"→ RGB 故障字：错位位移 + 随机跳切 + 辉光
//   "catalog"   → 列出能力
//
// 实测 matchName（2026-08 中文 AE）：
//   Glow = "ADBE Glo2"  (-0003 发光半径 / -0004 发光强度)
//   Offset = "ADBE Offset"（位移/循环）
// 教训：BlendingMode 必须用枚举对象，不能传裸数字

#include "_lib/response_utils.jsx"
#include "_lib/comp_utils.jsx"

function buildSuccessResponse(d) { return buildSuccess(d); }
function buildErrorResponse(code, msg) { return buildError(code, msg); }

function findComp(compName) {
    if (!compName) return (app.project.activeItem instanceof CompItem) ? app.project.activeItem : null;
    return findCompByName(compName);
}

function resolveTextLayer(comp, args) {
    if (!comp) return null;
    if (args.layerName) {
        var l = findLayerByName(comp, args.layerName);
        if (l) return l;
    }
    var idx = args.layerIndex || 1;
    if (idx >= 1 && idx <= comp.numLayers) return comp.layer(idx);
    return null;
}

// ---------- 工具：给属性加关键帧（简化） ----------
function setKeys(prop, keys) {
    // keys = [[t, v], ...]
    for (var i = 0; i < keys.length; i++) prop.setValueAtTime(keys[i][0], keys[i][1]);
}

// ---------- 1. 打击感入场 ----------
function doImpact(comp, args) {
    var layer = resolveTextLayer(comp, args);
    if (!layer) return buildErrorResponse("layer_not_found", "文字图层未找到");

    var t0 = (typeof args.time === "number") ? args.time : comp.time;
    var startScale = args.startScale || 160;
    var landDur = args.landDur || 0.12;
    var flash = (args.flash !== false);

    // 缩放砸入：startScale → 100（急停），透明度 0 → 100
    var scale = layer.property("Scale");
    setKeys(scale, [[t0, [startScale, startScale]], [t0 + landDur, [100, 100]]]);
    var op = layer.property("Opacity");
    op.setValueAtTime(t0, 0);
    op.setValueAtTime(t0 + landDur * 0.5, 100);

    // 落地抖动表达式（衰减正弦，对齐 textFXMaster shake 写法）
    var amp = args.shakeAmp || 12;
    var pos = layer.property("Position");
    pos.expression = "var t0=" + t0 + ";" +
        "if(time>t0+0.02){var tt=time-t0;" +
        "var n=" + amp + "*Math.sin(tt*25*6.28)/Math.exp(tt*8);" +
        "[value[0]+n,value[1]+n*0.6];}else value;";

    // 白色闪光层（可选）：0.1s 快闪，加色混合
    var flashName = null;
    if (flash) {
        var fs = comp.layers.addSolid([1, 1, 1], "ImpactFlash_" + layer.name.substring(0, 6),
            comp.width, comp.height, 1);
        fs.moveBefore(layer);
        fs.blendingMode = BlendingMode.ADD;
        var fop = fs.property("Opacity");
        fop.setValueAtTime(t0 + landDur * 0.5, 60);
        fop.setValueAtTime(t0 + landDur * 0.5 + 0.1, 0);
        fs.inPoint = t0;
        fs.outPoint = Math.min(comp.duration, t0 + landDur * 0.5 + 0.15);
        flashName = fs.name;
    }
    return buildSuccessResponse({action: "impact", layer: layer.name, comp: comp.name,
        time: t0, flash: flashName, shakeExpr: true});
}

// ---------- 2. beat 卡点脉冲 ----------
function doBeatSync(comp, args) {
    var layer = resolveTextLayer(comp, args);
    if (!layer) return buildErrorResponse("layer_not_found", "文字图层未找到");
    var beats = args.beats;
    if (!beats || beats.length === 0) return buildErrorResponse("no_beats", "beats 数组为空");

    var peak = args.peakScale || 118;
    var decay = args.decay || 0.15;
    var scale = layer.property("Scale");
    var base = (args.baseScale || 100);
    for (var i = 0; i < beats.length; i++) {
        var b = beats[i];
        if (b < 0 || b > comp.duration) continue;
        scale.setValueAtTime(b, [peak, peak]);
        scale.setValueAtTime(Math.min(comp.duration, b + decay), [base, base]);
    }
    return buildSuccessResponse({action: "beat_sync", layer: layer.name, comp: comp.name,
        beatsApplied: beats.length, peakScale: peak});
}

// ---------- 3. RGB 故障字 ----------
function doRgbGlitch(comp, args) {
    var layer = resolveTextLayer(comp, args);
    if (!layer) return buildErrorResponse("layer_not_found", "文字图层未找到");

    var t0 = (typeof args.startTime === "number") ? args.startTime : 0;
    var tEnd = (typeof args.endTime === "number") ? args.endTime : comp.duration;
    var glitchDur = Math.max(0.1, tEnd - t0);
    var offsetMax = args.offsetMax || 12;
    var numKeys = args.glitchKeys || 10;

    // 副本层：Offset 随机水平错位 + 透明度跳切
    var dup = layer.duplicate();
    dup.name = "GlitchCopy_" + layer.name.substring(0, 8);
    var off = dup.property("ADBE Effect Parade").addProperty("ADBE Offset");
    var offProp = off.property(1); // 位移（中心点）
    var baseVal = offProp.value;
    var seed = args.seed || 7;
    for (var k = 0; k <= numKeys; k++) {
        var tt = t0 + glitchDur * k / numKeys;
        seed = (seed * 9301 + 49297) % 233280;
        var rnd = seed / 233280.0;
        var dx = (rnd - 0.5) * 2 * offsetMax;
        offProp.setValueAtTime(tt, [baseVal[0] + dx, baseVal[1]]);
    }
    // 透明度随机跳切（闪烁故障感）
    var dop = dup.property("Opacity");
    seed = (seed + 13) % 233280;
    for (var k2 = 0; k2 <= numKeys; k2++) {
        var tt2 = t0 + glitchDur * k2 / numKeys;
        seed = (seed * 9301 + 49297) % 233280;
        var vis = (seed / 233280.0) > 0.35 ? 80 : 20;
        dop.setValueAtTime(tt2, vis);
    }
    // 辉光增强（Glo2：-0003 半径 / -0004 强度）
    var glow = layer.property("ADBE Effect Parade").addProperty("ADBE Glo2");
    glow.property("ADBE Glo2-0003").setValue(args.glowRadius || 25);
    glow.property("ADBE Glo2-0004").setValue(args.glowIntensity || 0.6);

    return buildSuccessResponse({action: "rgb_glitch", layer: layer.name,
        copy: dup.name, comp: comp.name, keys: numKeys, glow: true});
}

// ---------- 主入口 ----------
function textImpactMaster(args) {
    var action = args.action || "catalog";

    if (action === "catalog") {
        return buildSuccessResponse({
            actions: ["impact", "beat_sync", "rgb_glitch", "catalog"],
            desc: {
                impact: "打击感入场（缩放砸入+抖动+闪光）",
                beat_sync: "beat 卡点缩放脉冲",
                rgb_glitch: "RGB 故障字（错位+跳切+辉光）"
            }
        });
    }

    var comp = findComp(args.compName);
    if (!comp) return buildErrorResponse("comp_not_found", "合成未找到: " + args.compName);

    app.beginUndoGroup("TextImpact_" + action);
    try {
        var res;
        if (action === "impact") res = doImpact(comp, args);
        else if (action === "beat_sync") res = doBeatSync(comp, args);
        else if (action === "rgb_glitch") res = doRgbGlitch(comp, args);
        else res = buildErrorResponse("unknown_action", "未知 action: " + action);
        app.endUndoGroup();
        return res;
    } catch (e) {
        app.endUndoGroup();
        return buildErrorResponse("exec_error", e.toString());
    }
}

// 入口（附加式调用约定：外层注入 args 对象）
var _args = (typeof args !== "undefined") ? args : {};
textImpactMaster(_args);
