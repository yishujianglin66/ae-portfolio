// applyTextAnimation.jsx
// 文字动画 - 支持逐字、打字机、消散、聚合、3D翻转、弹跳、缩放、路径、波浪、随机闪烁等动画
// Phase 5-2 扩展 - 文字系统全面升级

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"
#include "_lib/easing_utils.jsx"

/**
 * 为单个文字图层添加动画
 */
function applyAnimationToLayer(comp, layer, animType, direction, duration, delay, easing, additionalParams, reverse) {
    var animatorsAdded = [];
    var keyframesAdded = 0;
    var time = comp.time;
    var endTime = time + duration;

    // 获取文本属性组
    var textProps = layer.property("ADBE Text Properties");
    var animatorsGroup = textProps.property("ADBE Text Animators");

    // 辅助：添加 Range Selector 并返回
    function addRangeSelector(animator) {
        var sel = animator.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
        return sel;
    }

    // 辅助：添加 Animator 并返回其属性组
    function addAnimator() {
        var anim = animatorsGroup.addProperty("ADBE Text Animator");
        return anim;
    }

    // 辅助：获取动画属性组
    function getAnimProps(animator) {
        return animator.property("ADBE Text Animator Properties");
    }

    // 辅助：获取属性索引（通过属性名或索引）
    function getSelectorProp(selector, name, fallbackIndex) {
        try { return selector.property(name); } catch (e) {
            try { return selector.property(fallbackIndex); } catch (e2) { return null; }
        }
    }

    // 辅助：设置关键帧并应用缓动
    function setSelectorKeyframe(sel, propName, idx, t, val, easeType) {
        try {
            var prop = sel.property(propName) || sel.property(idx);
            if (prop) {
                prop.setValueAtTime(t, val);
                if (easeType && easeType !== "linear") {
                    var kfIndex = prop.nearestKeyIndex(t);
                    applyEasing(prop, kfIndex, easeType);
                }
                return 1;
            }
        } catch (e) {}
        return 0;
    }

    // 方向映射为位移向量
    function getDirectionOffset(dir, range) {
        var r = range || 500;
        switch (String(dir).toLowerCase()) {
            case "left": return [-r, 0];
            case "right": return [r, 0];
            case "up": return [0, -r];
            case "down": return [0, r];
            case "random": return [(Math.random() - 0.5) * r * 2, (Math.random() - 0.5) * r * 2];
            default: return [0, r]; // center/down 默认
        }
    }

    // 动画类型分发
    switch (animType) {
        case "per_char": {
            // 逐字出现/消失：缩放 + 透明度
            var anim = addAnimator();
            var sel = addRangeSelector(anim);
            var props = getAnimProps(anim);

            try { props.addProperty("ADBE Text Scale 3D").setValue([0, 0, 0]); } catch (e) {}
            try { props.addProperty("ADBE Text Opacity").setValue(0); } catch (e) {}

            if (reverse) {
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, endTime, 100, easing);
            } else {
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, endTime, 100, easing);
            }
            animatorsAdded.push("per_char_scale_opacity");
            break;
        }

        case "typewriter": {
            // 打字机效果：逐字显示
            var anim = addAnimator();
            var sel = addRangeSelector(anim);
            var props = getAnimProps(anim);
            try { props.addProperty("ADBE Text Opacity").setValue(0); } catch (e) {}

            if (reverse) {
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, endTime, 100, easing);
            } else {
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, endTime, 100, easing);
            }

            // 光标闪烁（可选）
            var cursorParams = additionalParams || {};
            if (cursorParams.cursorBlink) {
                try {
                    var cursorAnim = addAnimator();
                    var cursorSel = addRangeSelector(cursorAnim);
                    var cursorProps = getAnimProps(cursorAnim);
                    // 对最后一个字符应用透明度闪烁
                    try {
                        cursorSel.property("Based On").setValue(1); // Characters
                    } catch (e) {}
                    try { cursorProps.addProperty("ADBE Text Opacity").setValue(0); } catch (e) {}
                    // 仅影响末尾区域
                    setSelectorKeyframe(cursorSel, "Start", 1, time, 99, null);
                    setSelectorKeyframe(cursorSel, "End", 2, time, 100, null);
                    // 添加循环关键帧实现闪烁
                    var blinkDur = 0.3;
                    var blinkCount = Math.floor(duration / blinkDur);
                    var endProp = cursorSel.property("End") || cursorSel.property(2);
                    if (endProp) {
                        for (var b = 0; b < blinkCount; b++) {
                            var bt = time + b * blinkDur;
                            endProp.setValueAtTime(bt, 100);
                            endProp.setValueAtTime(bt + blinkDur * 0.5, 99);
                        }
                        keyframesAdded += blinkCount * 2;
                    }
                    animatorsAdded.push("typewriter_cursor");
                } catch (e) {}
            }
            animatorsAdded.push("typewriter");
            break;
        }

        case "dissolve": {
            // 文字消散
            var dissolveType = (additionalParams && additionalParams.dissolveType) ? additionalParams.dissolveType : "fade";
            var anim = addAnimator();
            var sel = addRangeSelector(anim);
            var props = getAnimProps(anim);

            if (dissolveType === "blur") {
                try { props.addProperty("ADBE Text Blur").setValue([20, 20]); } catch (e) {}
            } else if (dissolveType === "pixelate") {
                // 像素化消散：通过缩放模拟
                try { props.addProperty("ADBE Text Scale 3D").setValue([300, 300, 300]); } catch (e) {}
            }
            try { props.addProperty("ADBE Text Opacity").setValue(0); } catch (e) {}

            if (reverse) {
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, endTime, 100, easing);
            } else {
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, endTime, 100, easing);
            }
            animatorsAdded.push("dissolve_" + dissolveType);
            break;
        }

        case "assemble": {
            // 文字聚合
            var scatterRange = (additionalParams && additionalParams.scatterRange) ? Number(additionalParams.scatterRange) : 500;
            var offset = getDirectionOffset(direction, scatterRange);
            var anim = addAnimator();
            var sel = addRangeSelector(anim);
            var props = getAnimProps(anim);

            try { props.addProperty("ADBE Text Position 3D").setValue([offset[0], offset[1], 0]); } catch (e) {}
            try { props.addProperty("ADBE Text Opacity").setValue(0); } catch (e) {}

            if (reverse) {
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, endTime, 100, easing);
            } else {
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, endTime, 100, easing);
            }
            animatorsAdded.push("assemble");
            break;
        }

        case "3d_flip": {
            // 3D 翻转进入
            var anim = addAnimator();
            var sel = addRangeSelector(anim);
            var props = getAnimProps(anim);

            // 尝试设置 Y 轴旋转
            try {
                var rotY = props.addProperty("ADBE Text Rotate Y");
                rotY.setValue(reverse ? -90 : 90);
            } catch (e) {
                try {
                    var rot2 = props.addProperty("ADBE Text Rotation");
                    rot2.setValue(reverse ? -90 : 90);
                } catch (e2) {}
            }
            try { props.addProperty("ADBE Text Opacity").setValue(0); } catch (e) {}

            if (reverse) {
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, endTime, 100, easing);
            } else {
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, endTime, 100, easing);
            }
            animatorsAdded.push("3d_flip");
            break;
        }

        case "bounce_in": {
            // 弹跳进入（从下方弹跳）
            var anim = addAnimator();
            var sel = addRangeSelector(anim);
            var props = getAnimProps(anim);

            var bounceOffset = getDirectionOffset(direction || "down", 600);
            try { props.addProperty("ADBE Text Position 3D").setValue([bounceOffset[0], bounceOffset[1], 0]); } catch (e) {}
            try { props.addProperty("ADBE Text Opacity").setValue(0); } catch (e) {}

            // 使用 easeInOut 或 bounce 模拟弹跳
            var bounceEase = easing || "easeOut";
            if (reverse) {
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, endTime, 100, bounceEase);
            } else {
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, endTime, 100, bounceEase);
            }
            animatorsAdded.push("bounce_in");
            break;
        }

        case "scale_in": {
            // 缩放进入/退出
            var anim = addAnimator();
            var sel = addRangeSelector(anim);
            var props = getAnimProps(anim);

            try { props.addProperty("ADBE Text Scale 3D").setValue([0, 0, 0]); } catch (e) {}
            try { props.addProperty("ADBE Text Opacity").setValue(0); } catch (e) {}

            if (reverse) {
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "End", 2, endTime, 100, easing);
            } else {
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, time, 0, null);
                keyframesAdded += setSelectorKeyframe(sel, "Start", 1, endTime, 100, easing);
            }
            animatorsAdded.push("scale_in");
            break;
        }

        case "path_move": {
            // 路径移动：整体沿路径运动
            var pathShape = (additionalParams && additionalParams.pathShape) ? additionalParams.pathShape : "circle";
            var pathPos = layer.property("ADBE Transform Group").property("ADBE Position");
            var pathKeyframes = [];

            if (pathShape === "circle") {
                var cx = comp.width / 2;
                var cy = comp.height / 2;
                var r = Math.min(comp.width, comp.height) * 0.3;
                for (var i = 0; i <= 8; i++) {
                    var angle = (i / 8) * Math.PI * 2;
                    pathKeyframes.push({
                        time: time + (i / 8) * duration,
                        value: [cx + Math.cos(angle) * r, cy + Math.sin(angle) * r]
                    });
                }
            } else if (pathShape === "wave") {
                var wBaseY = comp.height / 2;
                var wAmp = Math.min(comp.width, comp.height) * 0.2;
                for (var j = 0; j <= 8; j++) {
                    var wt = j / 8;
                    pathKeyframes.push({
                        time: time + wt * duration,
                        value: [wt * comp.width, wBaseY + Math.sin(wt * Math.PI * 2) * wAmp]
                    });
                }
            } else if (additionalParams && additionalParams.customPath && additionalParams.customPath.length >= 2) {
                var cp = additionalParams.customPath;
                for (var k = 0; k < cp.length; k++) {
                    pathKeyframes.push({
                        time: time + (k / (cp.length - 1)) * duration,
                        value: [Number(cp[k][0]), Number(cp[k][1])]
                    });
                }
            }

            for (var p = 0; p < pathKeyframes.length; p++) {
                try {
                    pathPos.setValueAtTime(pathKeyframes[p].time, pathKeyframes[p].value);
                    keyframesAdded++;
                    if (easing && p === pathKeyframes.length - 1) {
                        var kfIdx = pathPos.nearestKeyIndex(pathKeyframes[p].time);
                        applyEasing(pathPos, kfIdx, easing);
                    }
                } catch (e) {}
            }
            animatorsAdded.push("path_move");
            break;
        }

        case "wave": {
            // 波浪动画：使用 Wiggly Selector 或关键帧波浪
            var waveHeight = (additionalParams && additionalParams.waveHeight) ? Number(additionalParams.waveHeight) : 50;
            var waveFreq = (additionalParams && additionalParams.waveFrequency) ? Number(additionalParams.waveFrequency) : 3;

            var anim = addAnimator();
            var sel = addRangeSelector(anim);
            var props = getAnimProps(anim);

            try { props.addProperty("ADBE Text Position 3D").setValue([0, waveHeight, 0]); } catch (e) {}

            // 对 Range Selector 的 Position 属性本身做正弦波动
            var selEndProp = sel.property("End") || sel.property(2);
            if (selEndProp) {
                var steps = Math.max(waveFreq * 4, 8);
                for (var w = 0; w <= steps; w++) {
                    var wt = w / steps;
                    var val = 50 + Math.sin(wt * Math.PI * waveFreq) * 50;
                    selEndProp.setValueAtTime(time + wt * duration, val);
                    keyframesAdded++;
                }
                if (easing) {
                    var finalKf = selEndProp.nearestKeyIndex(time + duration);
                    applyEasing(selEndProp, finalKf, easing);
                }
            }
            animatorsAdded.push("wave");
            break;
        }

        case "random_flicker": {
            // 随机闪烁
            var flickerCount = (additionalParams && additionalParams.flickerCount) ? Number(additionalParams.flickerCount) : 10;
            var anim = addAnimator();
            var sel = addRangeSelector(anim);
            var props = getAnimProps(anim);
            try { props.addProperty("ADBE Text Opacity").setValue(0); } catch (e) {}

            var endProp = sel.property("End") || sel.property(2);
            if (endProp) {
                endProp.setValueAtTime(time, 0);
                keyframesAdded++;
                for (var f = 0; f < flickerCount; f++) {
                    var ft = time + Math.random() * duration;
                    var fv = Math.random() * 100;
                    endProp.setValueAtTime(ft, fv);
                    keyframesAdded++;
                }
                endProp.setValueAtTime(endTime, reverse ? 0 : 100);
                keyframesAdded++;
                if (easing) {
                    var fk = endProp.nearestKeyIndex(endTime);
                    applyEasing(endProp, fk, easing);
                }
            }
            animatorsAdded.push("random_flicker");
            break;
        }

        default:
            break;
    }

    return {
        animatorsAdded: animatorsAdded,
        keyframesAdded: keyframesAdded
    };
}

function applyTextAnimation(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "E101: compName 参数必填");
        }
        if (typeof args.layerIndex !== "number" && !Array.isArray(args.layerIndex)) {
            return buildError("E102", "E102: layerIndex 参数必填且必须为数字或数组");
        }
        if (!args.animationType) {
            return buildError("E113", "E113: animationType 参数必填");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "E101: 合成未找到: " + args.compName);
        }

        var animType = String(args.animationType).toLowerCase();
        var direction = args.direction || "down";
        var duration = args.duration !== undefined ? Number(args.duration) : 2.0;
        var delay = args.delay !== undefined ? Number(args.delay) : 0;
        var easing = args.easing || "easeOut";
        var additionalParams = args.additionalParams || {};
        var reverse = args.reverse === true || args.reverse === "true";

        // 支持批量处理
        var layerIndices = [];
        if (Array.isArray(args.layerIndex)) {
            layerIndices = args.layerIndex;
        } else {
            layerIndices = [args.layerIndex];
        }

        // 验证所有图层
        for (var li = 0; li < layerIndices.length; li++) {
            if (!validateLayerIndex(comp, layerIndices[li])) {
                return buildError("E102", "E102: 图层索引无效: " + layerIndices[li]);
            }
        }

        app.beginUndoGroup("Apply Text Animation");

        var results = [];
        for (var i = 0; i < layerIndices.length; i++) {
            var layer = comp.layer(layerIndices[i]);

            // 验证是否为文字图层
            var isText = false;
            try {
                if (layer.property("ADBE Text Properties")) isText = true;
            } catch (e) {}
            if (!isText) {
                results.push({
                    layerIndex: layerIndices[i],
                    layerName: layer.name,
                    skipped: true,
                    reason: "非文字图层"
                });
                continue;
            }

            var res = applyAnimationToLayer(comp, layer, animType, direction, duration, delay, easing, additionalParams, reverse);
            results.push({
                layerIndex: layerIndices[i],
                layerName: layer.name,
                animatorsAdded: res.animatorsAdded,
                keyframesAdded: res.keyframesAdded
            });
        }

        app.endUndoGroup();

        return buildSuccess({
            message: "文字动画应用完成",
            animationType: animType,
            duration: duration,
            easing: easing,
            reverse: reverse,
            results: results
        });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "E200: " + error.toString());
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = applyTextAnimation(args);
$.write(result);
