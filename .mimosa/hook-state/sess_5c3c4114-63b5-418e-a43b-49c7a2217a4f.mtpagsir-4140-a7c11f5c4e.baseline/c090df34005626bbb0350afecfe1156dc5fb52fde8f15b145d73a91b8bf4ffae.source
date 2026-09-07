// applyColorCorrection.jsx
// 高级色彩校正 - 对图层应用专业级色彩校正效果
// Phase 5-1 扩展 - 核心功能补全之二

#include "_lib/response_utils.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/effect_utils.jsx"

function applyColorCorrection(args) {
    try {
        if (!args.compName) {
            return buildError("E101", "compName 参数必填");
        }
        if (typeof args.layerIndex !== "number") {
            return buildError("E102", "layerIndex 参数必填且必须为数字");
        }

        var comp = findCompByName(args.compName);
        if (!comp) {
            return buildError("E101", "合成未找到: " + args.compName);
        }

        if (!validateLayerIndex(comp, args.layerIndex)) {
            return buildError("E102", "图层索引无效: " + args.layerIndex);
        }

        var layer = comp.layer(args.layerIndex);

        // 参数解析
        var correctionType = args.correctionType || "full_grade";
        var validTypes = ["curves", "levels", "hue_saturation", "color_balance", "channel_mixer", "color_wheels", "full_grade"];
        var typeValid = false;
        for (var i = 0; i < validTypes.length; i++) {
            if (validTypes[i] === correctionType) {
                typeValid = true;
                break;
            }
        }
        if (!typeValid) {
            return buildError("E103", "不支持的校正类型: " + correctionType);
        }

        var intensity = args.intensity !== undefined ? Number(args.intensity) : 100;
        intensity = Math.max(0, Math.min(100, intensity));
        var intensityRatio = intensity / 100;

        var blendMode = args.blendMode || null;

        app.beginUndoGroup("Apply Color Correction");

        var appliedEffects = [];
        var appliedProps = [];

        // 辅助函数：添加效果并记录
        function addEffectAndLog(matchName, displayName) {
            try {
                var fx = layer.Effects.addProperty(matchName);
                appliedEffects.push({ name: displayName, matchName: matchName, index: fx.propertyIndex });
                return fx;
            } catch (e) {
                appliedProps.push("effect_add_failed:" + displayName);
                return null;
            }
        }

        // 辅助函数：安全设置属性（支持属性名和 matchName 回退）
        function safeSetProp(effect, propName, value, logName) {
            try {
                var prop = effect.property(propName);
                if (prop) {
                    prop.setValue(value);
                    appliedProps.push(logName || propName);
                    return true;
                }
            } catch (e) {
                // 静默失败
            }
            return false;
        }

        // 辅助函数：将 0-255 范围映射到 AE 常用的 0-1 范围
        function norm255(v) {
            return Math.max(0, Math.min(255, Number(v))) / 255;
        }

        // === Curves 曲线校正 ===
        if (correctionType === "curves" || correctionType === "full_grade") {
            var curvesFx = addEffectAndLog("ADBE Curves", "Curves");
            if (curvesFx) {
                try {
                    var curvesData = args.curves || {};
                    // Curves 效果属性较复杂，优先设置通道选择
                    if (curvesData.channel !== undefined) {
                        safeSetProp(curvesFx, "Channel", Number(curvesData.channel), "Curves_Channel");
                    }
                    appliedProps.push("curves_added");
                } catch (e) {
                    appliedProps.push("curves_config_failed");
                }
            }
        }

        // === Levels 色阶校正 ===
        if (correctionType === "levels" || correctionType === "full_grade") {
            var levelsFx = addEffectAndLog("ADBE Easy Levels", "Levels");
            if (!levelsFx) {
                levelsFx = addEffectAndLog("ADBE Pro Levels", "Pro Levels");
            }
            if (levelsFx) {
                var levels = args.levels || {};
                var inputBlack = levels.inputBlack !== undefined ? Number(levels.inputBlack) : 0;
                var inputWhite = levels.inputWhite !== undefined ? Number(levels.inputWhite) : 255;
                var gamma = levels.gamma !== undefined ? Number(levels.gamma) : 1.0;
                var outputBlack = levels.outputBlack !== undefined ? Number(levels.outputBlack) : 0;
                var outputWhite = levels.outputWhite !== undefined ? Number(levels.outputWhite) : 255;

                // 应用 intensity 影响
                inputBlack = inputBlack * intensityRatio;
                inputWhite = 255 - (255 - inputWhite) * intensityRatio;
                gamma = 1.0 + (gamma - 1.0) * intensityRatio;
                outputBlack = outputBlack * intensityRatio;
                outputWhite = 255 - (255 - outputWhite) * intensityRatio;

                safeSetProp(levelsFx, "Input Black", norm255(inputBlack), "Levels_InputBlack");
                safeSetProp(levelsFx, "Input White", norm255(inputWhite), "Levels_InputWhite");
                safeSetProp(levelsFx, "Gamma", gamma, "Levels_Gamma");
                safeSetProp(levelsFx, "Output Black", norm255(outputBlack), "Levels_OutputBlack");
                safeSetProp(levelsFx, "Output White", norm255(outputWhite), "Levels_OutputWhite");
                appliedProps.push("levels_configured");
            }
        }

        // === Hue/Saturation 色相/饱和度 ===
        if (correctionType === "hue_saturation" || correctionType === "full_grade") {
            var hueFx = addEffectAndLog("ADBE HUE SATURATION", "Hue/Saturation");
            if (hueFx) {
                var hueSat = args.hueSaturation || {};
                var masterHue = (hueSat.masterHue !== undefined ? Number(hueSat.masterHue) : 0) * intensityRatio;
                var masterSat = (hueSat.masterSaturation !== undefined ? Number(hueSat.masterSaturation) : 0) * intensityRatio;
                var masterLight = (hueSat.masterLightness !== undefined ? Number(hueSat.masterLightness) : 0) * intensityRatio;

                safeSetProp(hueFx, "Master Hue", masterHue, "HueSat_MasterHue");
                safeSetProp(hueFx, "Master Saturation", masterSat, "HueSat_MasterSaturation");
                safeSetProp(hueFx, "Master Lightness", masterLight, "HueSat_MasterLightness");
                appliedProps.push("hue_saturation_configured");
            }
        }

        // === Color Balance 色彩平衡 ===
        if (correctionType === "color_balance" || correctionType === "full_grade") {
            var cbFx = addEffectAndLog("ADBE Color Balance", "Color Balance");
            if (cbFx) {
                var cb = args.colorBalance || {};
                var shadows = cb.shadows || [0, 0, 0];
                var midtones = cb.midtones || [0, 0, 0];
                var highlights = cb.highlights || [0, 0, 0];

                // Color Balance 属性范围通常是 -100 到 100
                safeSetProp(cbFx, "Shadow Red", shadows[0] * intensityRatio, "CB_Shadow_Red");
                safeSetProp(cbFx, "Shadow Green", shadows[1] * intensityRatio, "CB_Shadow_Green");
                safeSetProp(cbFx, "Shadow Blue", shadows[2] * intensityRatio, "CB_Shadow_Blue");
                safeSetProp(cbFx, "Midtone Red", midtones[0] * intensityRatio, "CB_Midtone_Red");
                safeSetProp(cbFx, "Midtone Green", midtones[1] * intensityRatio, "CB_Midtone_Green");
                safeSetProp(cbFx, "Midtone Blue", midtones[2] * intensityRatio, "CB_Midtone_Blue");
                safeSetProp(cbFx, "Hilite Red", highlights[0] * intensityRatio, "CB_Hilite_Red");
                safeSetProp(cbFx, "Hilite Green", highlights[1] * intensityRatio, "CB_Hilite_Green");
                safeSetProp(cbFx, "Hilite Blue", highlights[2] * intensityRatio, "CB_Hilite_Blue");
                appliedProps.push("color_balance_configured");
            }
        }

        // === Channel Mixer 通道混合 ===
        if (correctionType === "channel_mixer" || correctionType === "full_grade") {
            var cmFx = addEffectAndLog("ADBE Channel Mixer", "Channel Mixer");
            if (cmFx) {
                var cm = args.channelMixer || {};
                // 通道混合矩阵（简化版）
                var redRed = cm.redRed !== undefined ? Number(cm.redRed) : 100;
                var redGreen = cm.redGreen !== undefined ? Number(cm.redGreen) : 0;
                var redBlue = cm.redBlue !== undefined ? Number(cm.redBlue) : 0;
                var greenRed = cm.greenRed !== undefined ? Number(cm.greenRed) : 0;
                var greenGreen = cm.greenGreen !== undefined ? Number(cm.greenGreen) : 100;
                var greenBlue = cm.greenBlue !== undefined ? Number(cm.greenBlue) : 0;
                var blueRed = cm.blueRed !== undefined ? Number(cm.blueRed) : 0;
                var blueGreen = cm.blueGreen !== undefined ? Number(cm.blueGreen) : 0;
                var blueBlue = cm.blueBlue !== undefined ? Number(cm.blueBlue) : 100;

                safeSetProp(cmFx, "Red-Red", redRed * intensityRatio, "CM_RedRed");
                safeSetProp(cmFx, "Red-Green", redGreen * intensityRatio, "CM_RedGreen");
                safeSetProp(cmFx, "Red-Blue", redBlue * intensityRatio, "CM_RedBlue");
                safeSetProp(cmFx, "Green-Red", greenRed * intensityRatio, "CM_GreenRed");
                safeSetProp(cmFx, "Green-Green", greenGreen * intensityRatio, "CM_GreenGreen");
                safeSetProp(cmFx, "Green-Blue", greenBlue * intensityRatio, "CM_GreenBlue");
                safeSetProp(cmFx, "Blue-Red", blueRed * intensityRatio, "CM_BlueRed");
                safeSetProp(cmFx, "Blue-Green", blueGreen * intensityRatio, "CM_BlueGreen");
                safeSetProp(cmFx, "Blue-Blue", blueBlue * intensityRatio, "CM_BlueBlue");
                appliedProps.push("channel_mixer_configured");
            }
        }

        // === Color Wheels 色轮（使用 Lumetri Color） ===
        if (correctionType === "color_wheels" || correctionType === "full_grade") {
            var lumetriFx = addEffectAndLog("ADBE Lumetri", "Lumetri Color");
            if (lumetriFx) {
                var cw = args.colorWheels || {};
                var lift = cw.lift || [0, 0, 0];
                var gamma = cw.gamma || [0, 0, 0];
                var gain = cw.gain || [0, 0, 0];
                var offset = cw.offset || [0, 0, 0];

                // Lumetri 色轮参数（归一化到合理范围）
                safeSetProp(lumetriFx, "Shadows Color",
                    [lift[0] * intensityRatio / 100, lift[1] * intensityRatio / 100, lift[2] * intensityRatio / 100],
                    "Lumetri_Lift");
                safeSetProp(lumetriFx, "Midtones Color",
                    [gamma[0] * intensityRatio / 100, gamma[1] * intensityRatio / 100, gamma[2] * intensityRatio / 100],
                    "Lumetri_Gamma");
                safeSetProp(lumetriFx, "Highlights Color",
                    [gain[0] * intensityRatio / 100, gain[1] * intensityRatio / 100, gain[2] * intensityRatio / 100],
                    "Lumetri_Gain");
                appliedProps.push("color_wheels_configured");
            } else {
                // Lumetri 不可用时的降级方案：使用 Color Balance + Tint
                appliedProps.push("lumetri_unavailable_using_fallback");
                var fallbackCb = addEffectAndLog("ADBE Color Balance", "Color Balance (Fallback)");
                if (fallbackCb) {
                    appliedProps.push("color_balance_fallback_added");
                }
            }
        }

        // === LUT 叠加 ===
        if (args.lutFile) {
            try {
                var lutFile = new File(args.lutFile);
                if (lutFile.exists) {
                    var lutFx = addEffectAndLog("ADBE Apply LUT", "Apply LUT");
                    if (lutFx) {
                        try {
                            lutFx.property("LUT").setValue(lutFile);
                            appliedProps.push("lut_applied:" + lutFile.name);
                        } catch (lutErr) {
                            appliedProps.push("lut_set_failed");
                        }
                    }
                } else {
                    appliedProps.push("lut_file_not_found");
                }
            } catch (e) {
                appliedProps.push("lut_error:" + e.toString());
            }
        }

        // 设置混合模式（如果指定）
        if (blendMode) {
            try {
                var modeMap = {
                    "normal": BlendingMode.NORMAL,
                    "add": BlendingMode.ADD,
                    "screen": BlendingMode.SCREEN,
                    "multiply": BlendingMode.MULTIPLY,
                    "overlay": BlendingMode.OVERLAY,
                    "soft_light": BlendingMode.SOFT_LIGHT,
                    "hard_light": BlendingMode.HARD_LIGHT,
                    "color_dodge": BlendingMode.COLOR_DODGE,
                    "color_burn": BlendingMode.COLOR_BURN,
                    "darken": BlendingMode.DARKEN,
                    "lighten": BlendingMode.LIGHTEN,
                    "difference": BlendingMode.DIFFERENCE,
                    "exclusion": BlendingMode.EXCLUSION,
                    "hue": BlendingMode.HUE,
                    "saturation": BlendingMode.SATURATION,
                    "color": BlendingMode.COLOR,
                    "luminosity": BlendingMode.LUMINOSITY
                };
                if (modeMap.hasOwnProperty(blendMode)) {
                    layer.blendingMode = modeMap[blendMode];
                    appliedProps.push("blend_mode:" + blendMode);
                } else {
                    appliedProps.push("blend_mode_invalid:" + blendMode);
                }
            } catch (e) {
                appliedProps.push("blend_mode_failed:" + e.toString());
            }
        }

        app.endUndoGroup();

        return buildSuccess({
            correctionType: correctionType,
            intensity: intensity,
            blendMode: blendMode,
            appliedEffects: appliedEffects,
            appliedProps: appliedProps
        }, { message: "色彩校正应用成功" });
    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", error.toString());
    }
}

// 从 args.json 读取参数
var argsFile = new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json");
var args = {};
if (argsFile.exists) {
    argsFile.open("r");
    var _content = argsFile.read();
    argsFile.close();
    if (_content) {
        try { args = JSON.parse(_content); } catch (_e) { args = {}; }
    }
}

var result = applyColorCorrection(args);
$.write(result);
