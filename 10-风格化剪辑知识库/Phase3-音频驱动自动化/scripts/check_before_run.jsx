// ============================================================
// AE 音频驱动自动化 - 预检脚本
// 功能: 在实战前自动检测潜在问题
// 用法: 在AE中执行此脚本，或通过 AE Bridge 调用
// ============================================================

(function() {
    var issues = [];
    var warnings = [];
    var passed = [];

    // 1. 检查音频素材时长
    var audioLayer = null;
    var comp = app.project.activeItem;
    
    if (!comp || !(comp instanceof CompItem)) {
        alert("错误: 请先打开目标合成");
        return;
    }

    for (var i = 1; i <= comp.numLayers; i++) {
        if (comp.layer(i).source && comp.layer(i).source.file) {
            var ext = comp.layer(i).source.file.name.split('.').pop().toLowerCase();
            if (ext === "wav" || ext === "mp3" || ext === "aif" || ext === "aiff") {
                audioLayer = comp.layer(i);
                break;
            }
        }
    }

    if (audioLayer) {
        var duration = audioLayer.source.duration;
        if (duration < 8.0) {
            issues.push("✗ 音频时长不足: " + duration.toFixed(1) + "秒 (建议 ≥8秒)");
        } else {
            passed.push("✓ 音频时长: " + duration.toFixed(1) + "秒");
        }
    } else {
        warnings.push("⚠ 未检测到音频图层");
    }

    // 2. 检查关键图层
    var requiredLayers = ["MainVideo", "Audio Controller"];
    for (var r = 0; r < requiredLayers.length; r++) {
        var found = false;
        for (var j = 1; j <= comp.numLayers; j++) {
            if (comp.layer(j).name === requiredLayers[r]) {
                found = true;
                break;
            }
        }
        if (!found) {
            issues.push("✗ 缺少关键图层: " + requiredLayers[r]);
        } else {
            passed.push("✓ 图层存在: " + requiredLayers[r]);
        }
    }

    // 3. 检查表达式绑定
    var mainLayer = null;
    for (var k = 1; k <= comp.numLayers; k++) {
        if (comp.layer(k).name === "MainVideo") {
            mainLayer = comp.layer(k);
            break;
        }
    }

    if (mainLayer) {
        // 检查 Opacity 表达式
        try {
            var opacityProp = mainLayer.property("Opacity");
            if (opacityProp && opacityProp.expressionEnabled && opacityProp.expression.length > 0) {
                passed.push("✓ Opacity 表达式已绑定");
            } else {
                warnings.push("⚠ Opacity 表达式未绑定");
            }
        } catch (e) {
            warnings.push("⚠ Opacity 属性检查失败");
        }

        // 检查 Rotation 表达式
        try {
            var rotProp = mainLayer.property("Rotation");
            if (rotProp && rotProp.expressionEnabled && rotProp.expression.length > 0) {
                passed.push("✓ Rotation 表达式已绑定");
            } else {
                warnings.push("⚠ Rotation 表达式未绑定");
            }
        } catch (e) {
            warnings.push("⚠ Rotation 属性检查失败");
        }

        // 检查效果
        try {
            var hasGlow = false;
            for (var e = 1; e <= mainLayer.property("Effects").numProperties; e++) {
                if (mainLayer.property("Effects").property(e).matchName.indexOf("Glo") >= 0) {
                    hasGlow = true;
                    var glowProp = mainLayer.property("Effects").property(e).property("Glow Threshold") || 
                                   mainLayer.property("Effects").property(e).property(1);
                    if (glowProp && glowProp.expressionEnabled) {
                        passed.push("✓ Glow 表达式已绑定");
                    } else {
                        warnings.push("⚠ Glow 效果未绑定表达式");
                    }
                    break;
                }
            }
            if (!hasGlow) {
                warnings.push("⚠ 未检测到 Glow 效果");
            }
        } catch (e) {
            warnings.push("⚠ 效果检查失败");
        }
    }

    // 4. 检查能量滑块控制器
    var ctrlLayer = null;
    for (var c = 1; c <= comp.numLayers; c++) {
        if (comp.layer(c).name === "Audio Controller") {
            ctrlLayer = comp.layer(c);
            break;
        }
    }

    if (ctrlLayer) {
        var requiredSliders = ["Global Energy", "HighFreq Energy"];
        var foundSliders = 0;
        try {
            for (var s = 1; s <= ctrlLayer.property("Effects").numProperties; s++) {
                var effName = ctrlLayer.property("Effects").property(s).name;
                if (requiredSliders.indexOf(effName) >= 0) {
                    foundSliders++;
                }
            }
            if (foundSliders >= requiredSliders.length) {
                passed.push("✓ 能量滑块控制器完整 (" + foundSliders + "个)");
            } else {
                warnings.push("⚠ 能量滑块不完整 (已发现 " + foundSliders + "/" + requiredSliders.length + ")");
            }
        } catch (e) {
            warnings.push("⚠ 滑块控制器检查失败");
        }
    } else {
        issues.push("✗ Audio Controller 调整层不存在");
    }

    // 5. 检查分层结构
    var hasBackground = false;
    var hasForeground = false;
    for (var l = 1; l <= comp.numLayers; l++) {
        var lname = comp.layer(l).name.toLowerCase();
        if (lname.indexOf("background") >= 0 || lname.indexOf("bg") >= 0) {
            hasBackground = true;
        }
        if (lname.indexOf("foreground") >= 0 || lname.indexOf("fg") >= 0) {
            hasForeground = true;
        }
    }
    if (!hasBackground && !hasForeground) {
        warnings.push("⚠ 单层驱动（未检测到背景/前景层）");
    } else {
        if (hasBackground) passed.push("✓ 检测到背景层");
        if (hasForeground) passed.push("✓ 检测到前景层");
    }

    // 汇总报告
    var report = "===== AE 音频驱动预检报告 =====\n\n";
    report += "【通过项目】\n" + passed.join("\n") + "\n\n";
    if (warnings.length > 0) {
        report += "【警告项】\n" + warnings.join("\n") + "\n\n";
    }
    if (issues.length > 0) {
        report += "【必须修复】\n" + issues.join("\n") + "\n\n";
        report += "===============================\n";
        report += "结论: 预检未通过，请修复以上问题后再开始实战";
        alert(report, "预检结果 - 未通过");
    } else {
        report += "===============================\n";
        report += "结论: 预检通过，所有必备条件就绪";
        alert(report, "预检结果 - 通过");
    }

    return JSON.stringify({
        passed: passed.length,
        warnings: warnings.length,
        issues: issues.length,
        status: issues.length === 0 ? "OK" : "FAILED"
    });
})();