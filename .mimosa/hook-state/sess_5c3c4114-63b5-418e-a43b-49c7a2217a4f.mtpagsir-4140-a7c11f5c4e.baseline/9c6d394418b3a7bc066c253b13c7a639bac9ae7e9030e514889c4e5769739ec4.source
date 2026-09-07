/*
 * ========================================================================
 * AE预设解析与应用闭环系统 (Preset Pipeline)
 * 统一入口脚本 — 整合所有预设解析、提取、应用、验证功能
 *
 * 功能链路:
 *   解析预设(.ffx/.mogrt/.cube) → 提取参数JSON → 应用到AE → 验证效果
 *
 * 兼容性: AE 2025/2026 ExtendScript (ES3)
 * 依赖: 无外部依赖
 * ========================================================================
 */

#target aftereffects

// ============================================================
// 全局配置
// ============================================================
var PRESET_PIPELINE = {
    version: "1.0",
    name: "Preset Pipeline",
    debug: true,
    // 预设类型枚举
    TYPE_FFX: "ffx",
    TYPE_MOGRT: "mogrt",
    TYPE_CUBE: "cube",
    TYPE_3DL: "3dl",
    TYPE_LOOK: "look",
    TYPE_UNKNOWN: "unknown"
};

// ============================================================
// 第一环: 预设文件识别与分类
// ============================================================

/**
 * 识别预设文件类型
 * @param {File} file 预设文件
 * @returns {String} 预设类型
 */
function identifyPresetType(file) {
    if (!file || !file.exists) {
        return PRESET_PIPELINE.TYPE_UNKNOWN;
    }
    var ext = file.name.split(".").pop().toLowerCase();
    switch (ext) {
        case "ffx":
            return PRESET_PIPELINE.TYPE_FFX;
        case "mogrt":
            return PRESET_PIPELINE.TYPE_MOGRT;
        case "cube":
            return PRESET_PIPELINE.TYPE_CUBE;
        case "3dl":
            return PRESET_PIPELINE.TYPE_3DL;
        case "look":
            return PRESET_PIPELINE.TYPE_LOOK;
        default:
            return PRESET_PIPELINE.TYPE_UNKNOWN;
    }
}

/**
 * 获取预设文件信息
 * @param {String} filePath 预设文件路径
 * @returns {Object} 预设信息对象
 */
function getPresetInfo(filePath) {
    var file = new File(filePath);
    var type = identifyPresetType(file);
    var info = {
        name: file.name,
        path: file.fsName,
        type: type,
        size: file.length,
        exists: file.exists
    };
    return info;
}

// ============================================================
// 第二环: 预设解析器（FFX / MOGRT / LUT 统一解析）
// ============================================================

/**
 * 统一预设解析入口
 * @param {String} presetPath 预设文件路径
 * @returns {Object} 解析结果 { type, name, effects[], keyframes[], expressions[], params }
 */
function parsePreset(presetPath) {
    var file = new File(presetPath);
    if (!file.exists) {
        return { error: "文件不存在: " + presetPath };
    }

    var type = identifyPresetType(file);
    var result = {
        type: type,
        name: file.name.replace(/\.[^.]+$/, ""),
        path: file.fsName,
        effects: [],
        keyframes: [],
        expressions: [],
        params: {},
        raw: ""
    };

    switch (type) {
        case PRESET_PIPELINE.TYPE_FFX:
            result = parseFFX(file);
            break;
        case PRESET_PIPELINE.TYPE_MOGRT:
            result = parseMOGRTInfo(file);
            break;
        case PRESET_PIPELINE.TYPE_CUBE:
            result = parseCUBE(file);
            break;
        case PRESET_PIPELINE.TYPE_3DL:
            result = parse3DL(file);
            break;
        case PRESET_PIPELINE.TYPE_LOOK:
            result = parseLOOK(file);
            break;
        default:
            result.error = "未知预设类型: " + file.name;
    }

    return result;
}

/**
 * 解析 .ffx 预设文件（XML格式）
 * @param {File} file .ffx文件
 * @returns {Object} 解析结果
 */
function parseFFX(file) {
    var result = {
        type: PRESET_PIPELINE.TYPE_FFX,
        name: file.name.replace(/\.ffx$/i, ""),
        effects: [],
        keyframes: [],
        expressions: [],
        params: {}
    };

    file.encoding = "UTF-8";
    file.open("r");
    var content = file.read();
    file.close();

    result.raw = content;

    // 提取效果名称
    var effectRegex = /<effect\s+name="([^"]+)"[^>]*>/gi;
    var match;
    while ((match = effectRegex.exec(content)) !== null) {
        result.effects.push({
            name: match[1],
            matchName: extractAttribute(content, match.index, "matchName")
        });
    }

    // 提取属性和参数
    var propRegex = /<property\s+name="([^"]+)"[^>]*>([\s\S]*?)<\/property>/gi;
    while ((match = propRegex.exec(content)) !== null) {
        var propName = match[1];
        var propContent = match[2];

        // 提取参数值
        var valueRegex = /<value>([^<]+)<\/value>/i;
        var valueMatch = valueRegex.exec(propContent);
        if (valueMatch) {
            result.params[propName] = valueMatch[1].trim();
        }

        // 提取关键帧
        var kfRegex = /<keyframe\s+time="([^"]+)"[^>]*>([\s\S]*?)<\/keyframe>/gi;
        var kfMatch;
        while ((kfMatch = kfRegex.exec(propContent)) !== null) {
            result.keyframes.push({
                property: propName,
                time: parseFloat(kfMatch[1]),
                value: extractTagContent(kfMatch[2], "value"),
                easing: extractTagContent(kfMatch[2], "ease"),
                interpolation: extractTagContent(kfMatch[2], "interp")
            });
        }

        // 提取表达式
        var exprRegex = /<expression>([\s\S]*?)<\/expression>/i;
        var exprMatch = exprRegex.exec(propContent);
        if (exprMatch) {
            result.expressions.push({
                property: propName,
                expression: exprMatch[1].trim()
            });
        }
    }

    // 如果正则未匹配到任何效果，尝试另一种格式
    if (result.effects.length === 0) {
        // 某些FFX使用不同的XML命名空间
        var altEffectRegex = /name="([^"]+)"/gi;
        var altMatch;
        var count = 0;
        while ((altMatch = altEffectRegex.exec(content)) !== null && count < 50) {
            var n = altMatch[1];
            // 过滤掉明显不是效果名的标签
            if (n && n.indexOf("ADBE") === 0 || n.indexOf("TC ") === 0 ||
                n.indexOf("VC ") === 0 || n.indexOf("S_") === 0 ||
                n.indexOf("BCC") === 0) {
                result.effects.push({ name: n, matchName: n });
                count++;
            }
        }
    }

    return result;
}

/**
 * 解析 .mogrt 文件信息（不解压，仅读取基本信息）
 * @param {File} file .mogrt文件
 * @returns {Object} 解析结果
 */
function parseMOGRTInfo(file) {
    var result = {
        type: PRESET_PIPELINE.TYPE_MOGRT,
        name: file.name.replace(/\.mogrt$/i, ""),
        effects: [],
        keyframes: [],
        expressions: [],
        params: {},
        note: "MOGRT文件需要解压才能获取完整参数，请使用 extractMOGRT() 函数"
    };

    // 读取ZIP头部信息
    file.encoding = "binary";
    file.open("r");
    var header = file.read(4);
    file.close();

    // 检查是否为ZIP格式（PK头）
    if (header.charCodeAt(0) === 80 && header.charCodeAt(1) === 75) {
        result.isZip = true;
        result.note = "MOGRT文件是ZIP格式，包含Project.aegraphic。使用 extractMOGRT() 解压获取完整参数。";
    } else {
        result.isZip = false;
        result.note = "MOGRT文件格式异常，可能已损坏。";
    }

    return result;
}

/**
 * 解析 .cube LUT文件
 * @param {File} file .cube文件
 * @returns {Object} 解析结果
 */
function parseCUBE(file) {
    var result = {
        type: PRESET_PIPELINE.TYPE_CUBE,
        name: file.name.replace(/\.cube$/i, ""),
        effects: [],
        keyframes: [],
        expressions: [],
        params: {},
        lut: {
            title: "",
            size: 0,
            domainMin: [0, 0, 0],
            domainMax: [1, 1, 1],
            data: []
        }
    };

    file.encoding = "UTF-8";
    file.open("r");
    var content = file.read();
    file.close();

    var lines = content.split(/\r?\n/);
    var dataStarted = false;
    var dataCount = 0;

    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();

        // 跳过空行和注释
        if (line === "" || line.charAt(0) === "#") continue;

        // 解析标题
        if (line.indexOf("TITLE") === 0) {
            result.lut.title = line.replace(/^TITLE\s+/i, "").replace(/"/g, "");
            continue;
        }

        // 解析LUT尺寸
        if (line.indexOf("LUT_3D_SIZE") === 0) {
            result.lut.size = parseInt(line.split(/\s+/)[1]);
            continue;
        }

        // 解析域范围
        if (line.indexOf("DOMAIN_MIN") === 0) {
            var minParts = line.split(/\s+/);
            result.lut.domainMin = [
                parseFloat(minParts[1]),
                parseFloat(minParts[2]),
                parseFloat(minParts[3])
            ];
            continue;
        }
        if (line.indexOf("DOMAIN_MAX") === 0) {
            var maxParts = line.split(/\s+/);
            result.lut.domainMax = [
                parseFloat(maxParts[1]),
                parseFloat(maxParts[2]),
                parseFloat(maxParts[3])
            ];
            continue;
        }

        // 解析数据行
        var parts = line.split(/\s+/);
        if (parts.length >= 3 && !isNaN(parseFloat(parts[0]))) {
            dataStarted = true;
            result.lut.data.push([
                parseFloat(parts[0]),
                parseFloat(parts[1]),
                parseFloat(parts[2])
            ]);
            dataCount++;
        }
    }

    result.params.totalPoints = dataCount;
    result.params.lutSize = result.lut.size;
    result.params.title = result.lut.title;
    result.params.dataPoints = dataCount;

    return result;
}

/**
 * 解析 .3dl LUT文件
 * @param {File} file .3dl文件
 * @returns {Object} 解析结果
 */
function parse3DL(file) {
    var result = {
        type: PRESET_PIPELINE.TYPE_3DL,
        name: file.name.replace(/\.3dl$/i, ""),
        effects: [],
        keyframes: [],
        expressions: [],
        params: {},
        lut: {
            size: 0,
            data: []
        }
    };

    file.encoding = "UTF-8";
    file.open("r");
    var content = file.read();
    file.close();

    var lines = content.split(/\r?\n/);

    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();

        // 第一行通常是网格大小
        if (i === 0 && !isNaN(parseInt(line))) {
            result.lut.size = parseInt(line);
            continue;
        }

        // 数据行
        var parts = line.split(/\s+/);
        if (parts.length >= 3 && !isNaN(parseInt(parts[0]))) {
            result.lut.data.push([
                parseInt(parts[0]),
                parseInt(parts[1]),
                parseInt(parts[2])
            ]);
        }
    }

    result.params.lutSize = result.lut.size;
    result.params.dataPoints = result.lut.data.length;

    return result;
}

/**
 * 解析 .look 文件
 * @param {File} file .look文件
 * @returns {Object} 解析结果
 */
function parseLOOK(file) {
    var result = {
        type: PRESET_PIPELINE.TYPE_LOOK,
        name: file.name.replace(/\.look$/i, ""),
        effects: [],
        keyframes: [],
        expressions: [],
        params: {},
        note: ".look文件是SpeedGrade格式，建议转换为.cube后解析"
    };

    file.encoding = "UTF-8";
    file.open("r");
    var content = file.read();
    file.close();

    result.raw = content.substring(0, 1000); // 仅存储前1000字符

    return result;
}

// ============================================================
// 辅助函数
// ============================================================

function extractAttribute(content, startIndex, attrName) {
    var subContent = content.substr(startIndex, 500);
    var regex = new RegExp(attrName + "=\"([^\"]+)\"", "i");
    var match = regex.exec(subContent);
    return match ? match[1] : "";
}

function extractTagContent(content, tagName) {
    var regex = new RegExp("<" + tagName + ">([^<]*)</" + tagName + ">", "i");
    var match = regex.exec(content);
    return match ? match[1].trim() : "";
}

// ============================================================
// 第三环: 预设参数提取为标准化JSON
// ============================================================

/**
 * 将解析结果转换为标准化参数JSON
 * @param {Object} parseResult parsePreset()的返回值
 * @returns {Object} 标准化JSON
 */
function normalizePresetParams(parseResult) {
    var normalized = {
        metadata: {
            name: parseResult.name,
            type: parseResult.type,
            timestamp: new Date().toISOString(),
            parser: "Preset Pipeline v" + PRESET_PIPELINE.version
        },
        effects: [],
        keyframes: [],
        expressions: [],
        lut: null
    };

    // 标准化效果参数
    for (var i = 0; i < parseResult.effects.length; i++) {
        var fx = parseResult.effects[i];
        normalized.effects.push({
            index: i,
            name: fx.name || "",
            matchName: fx.matchName || fx.name || "",
            params: []
        });
    }

    // 标准化关键帧
    for (var j = 0; j < parseResult.keyframes.length; j++) {
        var kf = parseResult.keyframes[j];
        normalized.keyframes.push({
            property: kf.property || "",
            time: kf.time || 0,
            value: kf.value || "",
            easing: kf.easing || "linear",
            interpolation: kf.interpolation || "linear"
        });
    }

    // 标准化表达式
    for (var k = 0; k < parseResult.expressions.length; k++) {
        var expr = parseResult.expressions[k];
        normalized.expressions.push({
            property: expr.property || "",
            expression: expr.expression || ""
        });
    }

    // 标准化LUT
    if (parseResult.lut) {
        normalized.lut = {
            title: parseResult.lut.title || "",
            size: parseResult.lut.size || 0,
            domainMin: parseResult.lut.domainMin || [0, 0, 0],
            domainMax: parseResult.lut.domainMax || [1, 1, 1],
            dataPoints: parseResult.lut.data ? parseResult.lut.data.length : 0
        };
    }

    return normalized;
}

/**
 * 将标准化JSON输出为字符串
 * @param {Object} obj JSON对象
 * @returns {String} 格式化JSON字符串
 */
function toJSONString(obj) {
    var str = "{\n";
    var keys = [];
    for (var k in obj) {
        keys.push(k);
    }
    for (var i = 0; i < keys.length; i++) {
        var key = keys[i];
        var val = obj[key];
        str += '  "' + key + '": ' + _toJSON(val, 1) + (i < keys.length - 1 ? "," : "") + "\n";
    }
    str += "}";
    return str;
}

function _toJSON(val, indent) {
    var pad = "";
    for (var i = 0; i < indent; i++) pad += "  ";
    var pad2 = pad + "  ";

    if (val === null || val === undefined) return "null";
    if (typeof val === "boolean") return val ? "true" : "false";
    if (typeof val === "number") return String(val);
    if (typeof val === "string") return '"' + val.replace(/"/g, '\\"').replace(/\n/g, "\\n") + '"';

    if (val instanceof Array) {
        if (val.length === 0) return "[]";
        var arrStr = "[\n";
        for (var j = 0; j < val.length; j++) {
            arrStr += pad2 + _toJSON(val[j], indent + 1) + (j < val.length - 1 ? "," : "") + "\n";
        }
        arrStr += pad + "]";
        return arrStr;
    }

    if (typeof val === "object") {
        var keys = [];
        for (var key in val) keys.push(key);
        if (keys.length === 0) return "{}";
        var objStr = "{\n";
        for (var m = 0; m < keys.length; m++) {
            objStr += pad2 + '"' + keys[m] + '": ' + _toJSON(val[keys[m]], indent + 1) + (m < keys.length - 1 ? "," : "") + "\n";
        }
        objStr += pad + "}";
        return objStr;
    }

    return '""';
}

// ============================================================
// 第四环: 预设应用到AE
// ============================================================

/**
 * 应用FFX预设到图层
 * @param {String} presetPath 预设文件路径
 * @param {Number} layerIndex 图层索引（可选，默认选中图层）
 * @returns {Object} 应用结果
 */
function applyPresetToLayer(presetPath, layerIndex) {
    var result = {
        success: false,
        presetPath: presetPath,
        appliedEffects: [],
        appliedKeyframes: 0,
        errors: []
    };

    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {
        result.errors.push("没有打开的合成");
        return result;
    }

    var layer;
    if (layerIndex !== undefined) {
        layer = comp.layer(layerIndex);
    } else if (comp.selectedLayers.length > 0) {
        layer = comp.selectedLayers[0];
    } else {
        result.errors.push("没有选中的图层");
        return result;
    }

    var file = new File(presetPath);
    if (!file.exists) {
        result.errors.push("预设文件不存在: " + presetPath);
        return result;
    }

    try {
        // 方法1: 直接应用预设到图层
        var effectGroup = layer.property("ADBE Effect Parade");
        if (!effectGroup) {
            effectGroup = layer.addProperty("ADBE Effect Parade");
        }

        // 应用预设
        layer.applyPreset(file);

        // 获取应用后的效果列表
        for (var i = 1; i <= effectGroup.numProperties; i++) {
            var fx = effectGroup.property(i);
            result.appliedEffects.push({
                name: fx.name,
                matchName: fx.matchName,
                enabled: fx.enabled
            });
        }

        result.success = true;
        result.appliedKeyframes = countKeyframes(layer);

    } catch (e) {
        result.errors.push("应用预设失败: " + e.toString());
    }

    return result;
}

/**
 * 根据参数JSON构建效果并应用到图层
 * @param {Object} paramsJSON 标准化参数JSON
 * @param {Layer} targetLayer 目标图层
 * @returns {Object} 构建结果
 */
function applyParamsJSON(paramsJSON, targetLayer) {
    var result = {
        success: false,
        addedEffects: [],
        setProperties: 0,
        addedKeyframes: 0,
        setExpressions: 0,
        errors: []
    };

    if (!targetLayer) {
        result.errors.push("目标图层为空");
        return result;
    }

    try {
        var effectGroup = targetLayer.property("ADBE Effect Parade");
        if (!effectGroup) {
            effectGroup = targetLayer.addProperty("ADBE Effect Parade");
        }

        // 添加效果
        if (paramsJSON.effects) {
            for (var i = 0; i < paramsJSON.effects.length; i++) {
                var fxDef = paramsJSON.effects[i];
                var matchName = fxDef.matchName || fxDef.name;

                try {
                    var effect = effectGroup.addProperty(matchName);
                    result.addedEffects.push({
                        name: effect.name,
                        matchName: effect.matchName
                    });

                    // 设置效果参数
                    if (fxDef.params) {
                        for (var j = 0; j < fxDef.params.length; j++) {
                            var param = fxDef.params[j];
                            try {
                                var prop = effect.property(param.name);
                                if (prop) {
                                    prop.setValue(param.value);
                                    result.setProperties++;
                                }
                            } catch (pe) {
                                result.errors.push("设置参数失败: " + param.name + " - " + pe.toString());
                            }
                        }
                    }
                } catch (ee) {
                    result.errors.push("添加效果失败: " + matchName + " - " + ee.toString());
                }
            }
        }

        // 设置表达式
        if (paramsJSON.expressions) {
            for (var k = 0; k < paramsJSON.expressions.length; k++) {
                var exprDef = paramsJSON.expressions[k];
                try {
                    var prop = _resolvePropertyPath(targetLayer, exprDef.property);
                    if (prop) {
                        prop.expression = exprDef.expression;
                        result.setExpressions++;
                    }
                } catch (ex) {
                    result.errors.push("设置表达式失败: " + exprDef.property + " - " + ex.toString());
                }
            }
        }

        // 添加关键帧
        if (paramsJSON.keyframes) {
            for (var m = 0; m < paramsJSON.keyframes.length; m++) {
                var kfDef = paramsJSON.keyframes[m];
                try {
                    var kfProp = _resolvePropertyPath(targetLayer, kfDef.property);
                    if (kfProp) {
                        // 确保是可动画属性
                        if (kfProp.canVaryOverTime) {
                            kfProp.setValueAtTime(kfDef.time, kfDef.value);
                            result.addedKeyframes++;

                            // 设置缓动
                            if (kfDef.easing && kfDef.easing !== "linear") {
                                _applyEasing(kfProp, kfDef);
                            }
                        }
                    }
                } catch (ke) {
                    result.errors.push("添加关键帧失败: " + kfDef.property + " - " + ke.toString());
                }
            }
        }

        result.success = result.errors.length === 0 || result.addedEffects.length > 0;

    } catch (e) {
        result.errors.push("构建失败: " + e.toString());
    }

    return result;
}

/**
 * 解析属性路径
 * 支持: "position", "scale", "effect('Glow')('Glow Intensity')" 等
 */
function _resolvePropertyPath(layer, path) {
    if (!path || path === "") return null;

    // 简单变换属性
    var transformMap = {
        "position": "ADBE Position",
        "scale": "ADBE Scale",
        "rotation": "ADBE Rotate Z",
        "opacity": "ADBE Opacity",
        "anchorpoint": "ADBE Anchor Point",
        "anchor_point": "ADBE Anchor Point",
        "orientation": "ADBE Orientation"
    };

    var lowerPath = path.toLowerCase();
    if (transformMap[lowerPath]) {
        return layer.property("Transform").property(transformMap[lowerPath]);
    }

    // 效果属性: effect('效果名')('参数名')
    var effectMatch = path.match(/^effect\(['"]([^'"]+)['"]\)\(['"]([^'"]+)['"]\)$/i);
    if (effectMatch) {
        var effectName = effectMatch[1];
        var paramName = effectMatch[2];
        var effect = layer.effect(effectName);
        if (effect) {
            return effect.property(paramName);
        }
    }

    // 尝试直接访问
    try {
        return layer.property(path);
    } catch (e) {
        return null;
    }
}

/**
 * 应用关键帧缓动
 */
function _applyEasing(prop, kfDef) {
    try {
        var keyIndex = prop.numKeys;
        if (keyIndex === 0) return;

        var easeIn = 50;
        var easeOut = 50;

        if (kfDef.easing === "easein") {
            easeIn = 75; easeOut = 0;
        } else if (kfDef.easing === "easeout") {
            easeIn = 0; easeOut = 75;
        } else if (kfDef.easing === "easeinout") {
            easeIn = 60; easeOut = 60;
        }

        var inEase = new KeyframeEase(easeIn, 0);
        var outEase = new KeyframeEase(easeOut, 0);

        // 尝试设置时间缓动
        if (prop.isTimeVarying) {
            prop.setTemporalEaseAtKey(keyIndex, [inEase], [outEase]);
        }
    } catch (e) {
        // 缓动设置失败不中断流程
    }
}

/**
 * 计算图层关键帧总数
 */
function countKeyframes(layer) {
    var count = 0;
    function scanProps(propGroup) {
        for (var i = 1; i <= propGroup.numProperties; i++) {
            var prop = propGroup.property(i);
            if (prop.canVaryOverTime) {
                count += prop.numKeys;
            }
            if (prop.numProperties) {
                scanProps(prop);
            }
        }
    }
    try {
        scanProps(layer);
    } catch (e) {}
    return count;
}

// ============================================================
// 第五环: 验证效果（参数级验证 + 渲染验证）
// ============================================================

/**
 * 参数级验证：检查应用后的效果参数是否符合预期
 * @param {Layer} layer 目标图层
 * @param {Object} expectedParams 预期参数JSON
 * @returns {Object} 验证结果
 */
function verifyAppliedEffects(layer, expectedParams) {
    var result = {
        verified: true,
        matched: 0,
        mismatched: 0,
        missing: 0,
        details: []
    };

    if (!layer) {
        result.verified = false;
        result.details.push({ error: "图层为空" });
        return result;
    }

    var effectGroup = layer.property("ADBE Effect Parade");
    if (!effectGroup) {
        result.verified = false;
        result.details.push({ error: "图层没有效果组" });
        return result;
    }

    // 检查每个预期效果是否存在
    if (expectedParams.effects) {
        for (var i = 0; i < expectedParams.effects.length; i++) {
            var expectedFx = expectedParams.effects[i];
            var found = false;

            for (var j = 1; j <= effectGroup.numProperties; j++) {
                var actualFx = effectGroup.property(j);
                if (actualFx.matchName === expectedFx.matchName ||
                    actualFx.name === expectedFx.name) {
                    found = true;
                    result.matched++;

                    // 验证参数值
                    if (expectedFx.params) {
                        for (var k = 0; k < expectedFx.params.length; k++) {
                            var param = expectedFx.params[k];
                            var actualParam = actualFx.property(param.name);
                            if (actualParam) {
                                var actualValue = actualParam.value;
                                var expectedValue = param.value;

                                // 数值比较（容差0.01）
                                if (typeof expectedValue === "number") {
                                    if (Math.abs(actualValue - expectedValue) < 0.01) {
                                        result.details.push({
                                            effect: expectedFx.name,
                                            param: param.name,
                                            status: "match",
                                            expected: expectedValue,
                                            actual: actualValue
                                        });
                                    } else {
                                        result.mismatched++;
                                        result.details.push({
                                            effect: expectedFx.name,
                                            param: param.name,
                                            status: "mismatch",
                                            expected: expectedValue,
                                            actual: actualValue
                                        });
                                    }
                                }
                            }
                        }
                    }
                    break;
                }
            }

            if (!found) {
                result.missing++;
                result.details.push({
                    effect: expectedFx.name,
                    status: "missing"
                });
            }
        }
    }

    result.verified = (result.missing === 0 && result.mismatched === 0);
    return result;
}

/**
 * 渲染验证：渲染当前合成到图片序列并输出信息
 * @param {CompItem} comp 合成
 * @param {String} outputPath 输出路径
 * @param {Number} startTime 开始时间
 * @param {Number} endTime 结束时间
 * @returns {Object} 渲染结果
 */
function renderVerification(comp, outputPath, startTime, endTime) {
    var result = {
        success: false,
        outputPath: outputPath,
        frameCount: 0,
        duration: 0,
        errors: []
    };

    if (!comp || !(comp instanceof CompItem)) {
        result.errors.push("无效的合成");
        return result;
    }

    try {
        // 设置渲染队列
        var renderQueue = app.project.renderQueue;
        // 清空已有渲染项目
        while (renderQueue.numItems > 0) {
            renderQueue.item(renderQueue.numItems).remove();
        }

        var render = renderQueue.items.add(comp);

        // 设置输出模块
        var outputModule = render.outputModule(1);
        var omTemplate = outputModule.templates;
        outputModule.applyTemplate("PNG Sequence");

        // 设置输出路径
        var outputFile = new File(outputPath + "/frame_[####].png");
        outputModule.file = outputFile;

        // 设置渲染范围
        render.timeSpanStart = startTime || 0;
        render.timeSpanDuration = (endTime || comp.duration) - (startTime || 0);

        // 设置渲染品质
        render.settings.applyTemplate("Best Settings");

        result.duration = render.timeSpanDuration;
        result.frameCount = Math.round(result.duration * comp.frameRate);

        // 执行渲染
        app.beginSuppressDialogs();
        renderQueue.render();
        app.endSuppressDialogs(false);

        result.success = true;

    } catch (e) {
        result.errors.push("渲染失败: " + e.toString());
    }

    return result;
}

/**
 * 导出当前图层的效果参数为JSON（用于对比验证）
 * @param {Layer} layer 图层
 * @returns {Object} 效果参数JSON
 */
function exportLayerEffectsJSON(layer) {
    var result = {
        layerName: layer.name,
        effects: [],
        expressions: [],
        keyframes: []
    };

    var effectGroup = layer.property("ADBE Effect Parade");
    if (!effectGroup) return result;

    for (var i = 1; i <= effectGroup.numProperties; i++) {
        var fx = effectGroup.property(i);
        var effectData = {
            name: fx.name,
            matchName: fx.matchName,
            enabled: fx.enabled,
            params: []
        };

        // 遍历效果参数
        for (var j = 1; j <= fx.numProperties; j++) {
            var param = fx.property(j);
            if (param) {
                var paramData = {
                    name: param.name,
                    matchName: param.matchName,
                    value: null
                };

                try {
                    if (param.propertyValueType === PropertyValueType.One_D) {
                        paramData.value = param.value;
                    } else if (param.propertyValueType === PropertyValueType.Two_D) {
                        paramData.value = [param.value[0], param.value[1]];
                    } else if (param.propertyValueType === PropertyValueType.Three_D) {
                        paramData.value = [param.value[0], param.value[1], param.value[2]];
                    } else if (param.propertyValueType === PropertyValueType.COLOR) {
                        paramData.value = [param.value[0], param.value[1], param.value[2]];
                    } else if (param.propertyValueType === PropertyValueType.NO_VALUE) {
                        paramData.value = null;
                    } else {
                        paramData.value = param.value;
                    }
                } catch (e) {
                    paramData.value = "error";
                }

                effectData.params.push(paramData);

                // 提取表达式
                if (param.expression && param.expression !== "") {
                    result.expressions.push({
                        effect: fx.name,
                        param: param.name,
                        expression: param.expression
                    });
                }

                // 提取关键帧
                if (param.numKeys > 0) {
                    for (var k = 1; k <= param.numKeys; k++) {
                        result.keyframes.push({
                            effect: fx.name,
                            param: param.name,
                            time: param.keyTime(k),
                            value: param.keyValue(k),
                            keyIndex: k
                        });
                    }
                }
            }
        }

        result.effects.push(effectData);
    }

    return result;
}

// ============================================================
// 第六环: 端到端闭环流水线
// ============================================================

/**
 * 端到端预设流水线
 * 从解析预设 → 提取参数 → 应用到AE → 验证效果
 *
 * @param {String} presetPath 预设文件路径
 * @param {Number} layerIndex 目标图层索引（可选）
 * @param {Boolean} doRender 是否渲染验证（可选）
 * @param {String} renderPath 渲染输出路径（可选）
 * @returns {Object} 完整流水线结果
 */
function runPresetPipeline(presetPath, layerIndex, doRender, renderPath) {
    var pipeline = {
        steps: [],
        success: false,
        errors: []
    };

    // 步骤1: 解析预设
    var step1 = { name: "解析预设", status: "pending", result: null };
    try {
        step1.result = parsePreset(presetPath);
        step1.status = step1.result.error ? "failed" : "success";
        pipeline.steps.push(step1);

        if (step1.result.error) {
            pipeline.errors.push("解析失败: " + step1.result.error);
            return pipeline;
        }
    } catch (e) {
        step1.status = "failed";
        step1.result = { error: e.toString() };
        pipeline.steps.push(step1);
        pipeline.errors.push("解析异常: " + e.toString());
        return pipeline;
    }

    // 步骤2: 标准化参数
    var step2 = { name: "标准化参数", status: "pending", result: null };
    try {
        step2.result = normalizePresetParams(step1.result);
        step2.status = "success";
    } catch (e) {
        step2.status = "failed";
        step2.result = { error: e.toString() };
        pipeline.errors.push("标准化失败: " + e.toString());
    }
    pipeline.steps.push(step2);

    // 步骤3: 应用到AE
    var step3 = { name: "应用到AE", status: "pending", result: null };
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) {
            step3.status = "failed";
            step3.result = { error: "没有打开的合成" };
            pipeline.errors.push("没有打开的合成");
        } else {
            var layer = (layerIndex !== undefined) ?
                comp.layer(layerIndex) :
                (comp.selectedLayers.length > 0 ? comp.selectedLayers[0] : null);

            if (!layer) {
                step3.status = "failed";
                step3.result = { error: "没有目标图层" };
                pipeline.errors.push("没有目标图层");
            } else {
                // 如果是FFX文件，直接应用
                if (step1.result.type === PRESET_PIPELINE.TYPE_FFX) {
                    step3.result = applyPresetToLayer(presetPath, layerIndex);
                } else {
                    // 其他类型使用参数JSON构建
                    step3.result = applyParamsJSON(step2.result, layer);
                }
                step3.status = step3.result.success ? "success" : "failed";
                if (!step3.result.success) {
                    pipeline.errors.push("应用失败");
                }
            }
        }
    } catch (e) {
        step3.status = "failed";
        step3.result = { error: e.toString() };
        pipeline.errors.push("应用异常: " + e.toString());
    }
    pipeline.steps.push(step3);

    // 步骤4: 验证效果
    var step4 = { name: "验证效果", status: "pending", result: null };
    try {
        var comp2 = app.project.activeItem;
        if (comp2) {
            var layer2 = (layerIndex !== undefined) ?
                comp2.layer(layerIndex) :
                (comp2.selectedLayers.length > 0 ? comp2.selectedLayers[0] : null);

            if (layer2) {
                // 参数级验证
                step4.result = verifyAppliedEffects(layer2, step2.result);
                step4.status = step4.result.verified ? "success" : "warning";
            } else {
                step4.status = "skipped";
                step4.result = { note: "无法验证: 没有目标图层" };
            }
        } else {
            step4.status = "skipped";
            step4.result = { note: "无法验证: 没有打开的合成" };
        }
    } catch (e) {
        step4.status = "failed";
        step4.result = { error: e.toString() };
    }
    pipeline.steps.push(step4);

    // 步骤5: 渲染验证（可选）
    if (doRender && renderPath) {
        var step5 = { name: "渲染验证", status: "pending", result: null };
        try {
            var comp3 = app.project.activeItem;
            step5.result = renderVerification(comp3, renderPath, 0, 1);
            step5.status = step5.result.success ? "success" : "failed";
        } catch (e) {
            step5.status = "failed";
            step5.result = { error: e.toString() };
        }
        pipeline.steps.push(step5);
    }

    // 总结
    var allSuccess = true;
    for (var s = 0; s < pipeline.steps.length; s++) {
        if (pipeline.steps[s].status === "failed") {
            allSuccess = false;
            break;
        }
    }
    pipeline.success = allSuccess;

    return pipeline;
}

// ============================================================
// UI面板
// ============================================================

function buildPipelineUI() {
    var panel = (this instanceof Panel) ? this : new Window("palette", "预设流水线 v" + PRESET_PIPELINE.version, undefined, { resizeable: true });
    panel.orientation = "column";
    panel.alignChildren = ["fill", "top"];
    panel.spacing = 4;
    panel.margins = 8;

    // 文件选择
    var fileGroup = panel.add("group");
    fileGroup.orientation = "row";
    fileGroup.alignChildren = ["left", "center"];
    fileGroup.add("statictext", [0, 0, 60, 20], "预设文件:");
    var fileInput = fileGroup.add("edittext", [0, 0, 300, 20], "");
    var browseBtn = fileGroup.add("button", [0, 0, 60, 20], "浏览...");

    browseBtn.onClick = function() {
        var file = File.openDialog("选择预设文件", "*.ffx;*.mogrt;*.cube;*.3dl", false);
        if (file) {
            fileInput.text = file.fsName;
        }
    };

    // 目标图层
    var layerGroup = panel.add("group");
    layerGroup.orientation = "row";
    layerGroup.alignChildren = ["left", "center"];
    layerGroup.add("statictext", [0, 0, 60, 20], "目标图层:");
    var layerDropdown = layerGroup.add("dropdownlist", [0, 0, 200, 20]);
    layerDropdown.add("item", "选中图层");
    refreshLayerList();

    function refreshLayerList() {
        layerDropdown.removeAll();
        layerDropdown.add("item", "选中图层");
        var comp = app.project.activeItem;
        if (comp && comp instanceof CompItem) {
            for (var i = 1; i <= comp.numLayers; i++) {
                layerDropdown.add("item", i + ": " + comp.layer(i).name);
            }
        }
        layerDropdown.selection = 0;
    }

    var refreshBtn = layerGroup.add("button", [0, 0, 60, 20], "刷新");
    refreshBtn.onClick = function() { refreshLayerList(); };

    // 选项
    var optGroup = panel.add("group");
    optGroup.orientation = "row";
    var renderCheck = optGroup.add("checkbox", [0, 0, 150, 20], "渲染验证");
    var exportCheck = optGroup.add("checkbox", [0, 0, 150, 20], "导出参数JSON");

    // 按钮
    var btnGroup = panel.add("group");
    btnGroup.orientation = "row";
    var parseBtn = btnGroup.add("button", [0, 0, 100, 25], "解析预设");
    var applyBtn = btnGroup.add("button", [0, 0, 100, 25], "应用预设");
    var pipelineBtn = btnGroup.add("button", [0, 0, 100, 25], "完整流水线");
    var exportBtn = btnGroup.add("button", [0, 0, 100, 25], "导出当前效果");

    // 日志输出
    var logGroup = panel.add("panel", [0, 0, 420, 200], "日志输出");
    logGroup.orientation = "column";
    logGroup.alignChildren = ["fill", "fill"];
    var logText = logGroup.add("edittext", [0, 0, 400, 170], "", { multiline: true, scrolling: true });
    logText.text = "预设流水线 v" + PRESET_PIPELINE.version + " 已就绪\n";

    function log(msg) {
        logText.text += msg + "\n";
        logText.textselection = logText.text.length;
    }

    // 解析按钮
    parseBtn.onClick = function() {
        var path = fileInput.text;
        if (!path) { log("请选择预设文件"); return; }
        log("正在解析: " + path);
        var result = parsePreset(path);
        if (result.error) {
            log("解析失败: " + result.error);
        } else {
            log("解析成功!");
            log("  类型: " + result.type);
            log("  名称: " + result.name);
            log("  效果数: " + result.effects.length);
            log("  关键帧数: " + result.keyframes.length);
            log("  表达式数: " + result.expressions.length);
            if (result.params) {
                log("  参数: " + toJSONString(result.params));
            }
        }
    };

    // 应用按钮
    applyBtn.onClick = function() {
        var path = fileInput.text;
        if (!path) { log("请选择预设文件"); return; }
        var layerIdx = layerDropdown.selection.index;
        if (layerIdx === 0) layerIdx = undefined;
        else layerIdx = layerIdx; // 1-based

        log("正在应用预设到图层...");
        var result = applyPresetToLayer(path, layerIdx);
        if (result.success) {
            log("应用成功!");
            log("  添加效果: " + result.appliedEffects.length + "个");
            for (var i = 0; i < result.appliedEffects.length; i++) {
                log("    " + (i + 1) + ". " + result.appliedEffects[i].name + " (" + result.appliedEffects[i].matchName + ")");
            }
            log("  关键帧总数: " + result.appliedKeyframes);
        } else {
            log("应用失败: " + result.errors.join("; "));
        }
    };

    // 完整流水线按钮
    pipelineBtn.onClick = function() {
        var path = fileInput.text;
        if (!path) { log("请选择预设文件"); return; }
        var layerIdx = layerDropdown.selection.index;
        if (layerIdx === 0) layerIdx = undefined;

        log("=== 启动完整流水线 ===");
        var result = runPresetPipeline(path, layerIdx, renderCheck.value, "");

        for (var i = 0; i < result.steps.length; i++) {
            var step = result.steps[i];
            var statusIcon = step.status === "success" ? "[OK]" :
                             step.status === "failed" ? "[FAIL]" :
                             step.status === "warning" ? "[WARN]" : "[SKIP]";
            log(statusIcon + " 步骤" + (i + 1) + ": " + step.name + " - " + step.status);
        }

        if (result.success) {
            log("=== 流水线完成: 全部成功 ===");
        } else {
            log("=== 流水线完成: 存在错误 ===");
            log("错误: " + result.errors.join("; "));
        }
    };

    // 导出当前效果按钮
    exportBtn.onClick = function() {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) { log("没有打开的合成"); return; }
        var layer = comp.selectedLayers.length > 0 ? comp.selectedLayers[0] : null;
        if (!layer) { log("没有选中的图层"); return; }

        log("正在导出图层效果参数...");
        var result = exportLayerEffectsJSON(layer);
        log("  图层: " + result.layerName);
        log("  效果数: " + result.effects.length);
        log("  表达式数: " + result.expressions.length);
        log("  关键帧数: " + result.keyframes.length);

        if (exportCheck.value) {
            var outFile = new File("~/Desktop/layer_effects_export.json");
            outFile.open("w");
            outFile.write(toJSONString(result));
            outFile.close();
            log("  已导出到: " + outFile.fsName);
        }
    };

    panel.layout.layout(true);

    if (panel instanceof Window) {
        panel.center();
        panel.show();
    }

    return panel;
}

// ============================================================
// 启动
// ============================================================

// 如果作为脚本运行（不是面板），则创建窗口
if (typeof buildPipelineUI === "function") {
    // 在AE中运行
    try {
        buildPipelineUI();
    } catch (e) {
        alert("预设流水线启动失败: " + e.toString());
    }
}
