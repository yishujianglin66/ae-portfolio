/**
 * Code Generator - 代码生成器
 * ------------------------------------
 * 将IR节点转换为ExtendScript可执行代码
 *
 * 生成规则:
 * 1. 使用ExtendScript ES3语法 (var, 无let/const, 无箭头函数, 无模板字符串)
 * 2. 每个操作生成一个原子代码块
 * 3. 使用变量保存中间结果 (comp_001, layer_001, effect_001)
 * 4. 包含错误处理 (try-catch)
 * 5. 支持回传JSON结果
 *
 * @module apc/codegen
 */

import type {
  IRNode,
  Operation,
  CreateCompOp,
  AddLayerOp,
  AddEffectOp,
  SetPropertyOp,
  SetKeyframeOp,
  SetExpressionOp,
  AddMaskOp,
  SetBlendModeOp,
  SetParentOp,
  SetTrackMatteOp,
  BlendMode,
} from "./types.js";

/**
 * 代码生成结果
 */
export interface CodeGenResult {
  script: string;
  variableMap: Map<string, string>; // ref -> 变量名
  errors: Array<{ code: string; message: string }>;
}

// ============ 主入口 ============

/**
 * 生成ExtendScript代码
 */
export function generateCode(nodes: IRNode[]): CodeGenResult {
  const errors: Array<{ code: string; message: string }> = [];
  const variableMap = new Map<string, string>(); // ref -> 变量名
  const codeBlocks: string[] = [];

  // 1. 头部: 启用撤销组, 准备结果收集
  codeBlocks.push(generateHeader());

  // 2. 为每个节点生成代码块
  let varCounter = { comp: 0, layer: 0, effect: 0, mask: 0 };
  for (const node of nodes) {
    try {
      const block = generateNodeCode(node, variableMap, varCounter);
      if (block) {
        codeBlocks.push(block);
      }
    } catch (e) {
      errors.push({
        code: "G000",
        message: `节点 ${node.id} (${node.type}) 代码生成失败: ${String(e)}`,
      });
    }
  }

  // 3. 尾部: 结束撤销组, 返回结果
  codeBlocks.push(generateFooter());

  return {
    script: codeBlocks.join("\n\n"),
    variableMap,
    errors,
  };
}

// ============ 头部/尾部 ============

function generateHeader(): string {
  return `(function() {
    // ============================================
    // AE自动化引擎 - 编译器生成代码
    // 生成时间: ${new Date().toISOString()}
    // ============================================

    var _results = [];
    var _errors = [];

    function _logResult(op, data) {
        _results.push({ op: op, data: data, timestamp: new Date().getTime() });
    }

    function _logError(op, err) {
        _errors.push({ op: op, error: err.toString(), timestamp: new Date().getTime() });
    }

    // 辅助函数: 解析属性路径, 如 "Transform/Position" 或 "Effects.Gaussian Blur.Blurriness"
    function resolveProperty(layer, path) {
        if (!layer) return null;
        // 支持 "/" 分隔符
        var parts = path.split("/").join(".").split(".");
        var current = layer;

        // 处理 "ADBE Transform Group" 这种带空格的matchName
        // 先尝试整体匹配, 再尝试分段匹配
        for (var i = 0; i < parts.length; i++) {
            if (!current) break;
            var part = parts[i].trim();
            try {
                if (current.property) {
                    // 先尝试按名称查找
                    var prop = null;
                    try { prop = current.property(part); } catch (e) { prop = null; }
                    if (!prop) {
                        // 按matchName查找
                        for (var j = 1; j <= (current.numProperties || 0); j++) {
                            var p = current.property(j);
                            if (p && (p.name === part || p.matchName === part)) {
                                prop = p;
                                break;
                            }
                        }
                    }
                    current = prop;
                } else {
                    return null;
                }
            } catch (e) {
                return null;
            }
        }
        return current;
    }

    app.beginUndoGroup("AE Auto Engine - Compiled Script");

    try {`;
}

function generateFooter(): string {
  return `    } catch (e) {
        _logError("top_level", e);
    } finally {
        app.endUndoGroup();
    }

    var _output = {
        status: _errors.length === 0 ? "success" : "partial",
        results: _results,
        errors: _errors,
        timestamp: new Date().toISOString()
    };

    $.write(JSON.stringify(_output, null, 2));
})();`;
}

// ============ 节点代码生成 ============

function generateNodeCode(
  node: IRNode,
  variableMap: Map<string, string>,
  counter: { comp: number; layer: number; effect: number; mask: number }
): string {
  const op = node.source;

  switch (op.op) {
    case "createComp":
      return generateCreateComp(op, node, variableMap, counter);
    case "addLayer":
      return generateAddLayer(op, node, variableMap, counter);
    case "addEffect":
      return generateAddEffect(op, node, variableMap, counter);
    case "setProperty":
      return generateSetProperty(op, node, variableMap);
    case "setKeyframe":
      return generateSetKeyframe(op, node, variableMap);
    case "setExpression":
      return generateSetExpression(op, node, variableMap);
    case "addMask":
      return generateAddMask(op, node, variableMap, counter);
    case "setBlendMode":
      return generateSetBlendMode(op, node, variableMap);
    case "setParent":
      return generateSetParent(op, node, variableMap);
    case "setTrackMatte":
      return generateSetTrackMatte(op, node, variableMap);
    default:
      return "";
  }
}

// ============ CreateComp ============

function generateCreateComp(
  op: CreateCompOp,
  node: IRNode,
  variableMap: Map<string, string>,
  counter: { comp: number }
): string {
  const varName = `comp_${String(++counter.comp).padStart(3, "0")}`;
  if (op.ref) variableMap.set(op.ref, varName);

  const name = escapeString(op.name);
  const width = op.width ?? 1920;
  const height = op.height ?? 1080;
  const frameRate = op.frameRate ?? 30;
  const duration = op.duration ?? 10;
  const pixelAspect = op.pixelAspect ?? 1.0;
  const bgColor = op.bgColor ?? [0, 0, 0];

  return `        // [${node.id}] createComp: ${name}
        var ${varName} = app.project.items.addComp(${JSON.stringify(name)}, ${width}, ${height}, ${pixelAspect}, ${duration}, ${frameRate});
        if (${varName}) {
            ${varName}.bgColor = [${bgColor.join(", ")}];
            _logResult("createComp", { name: ${JSON.stringify(name)}, "var": "${varName}", width: ${width}, height: ${height}, fps: ${frameRate}, duration: ${duration} });
        } else {
            throw new Error("Failed to create composition: ${name}");
        }`;
}

// ============ AddLayer ============

function generateAddLayer(
  op: AddLayerOp,
  node: IRNode,
  variableMap: Map<string, string>,
  counter: { layer: number }
): string {
  const varName = `layer_${String(++counter.layer).padStart(3, "0")}`;
  if (op.ref) variableMap.set(op.ref, varName);

  const compVar = variableMap.get(op.compRef) || "null";
  const layerType = op.layerType;

  let creationCode = "";
  let setupCode = "";

  switch (layerType) {
    case "text": {
      const text = escapeString(op.text || "Text");
      const fontSize = op.fontSize ?? 48;
      const font = op.font ? JSON.stringify(op.font) : '"Arial"';
      const fillColor = op.fillColor ?? [1, 1, 1];
      setupCode = `
            var _textProp = ${varName}.property("ADBE Text Properties").property("ADBE Text Document");
            var _textDoc = _textProp.value;
            _textDoc.text = ${JSON.stringify(text)};
            _textDoc.fontSize = ${fontSize};
            _textDoc.font = ${font};
            _textDoc.fillColor = [${fillColor.join(", ")}];
            _textDoc.applyFill = true;
            _textProp.setValue(_textDoc);`;
      creationCode = `var ${varName} = ${compVar}.layers.addText(${JSON.stringify(text)});`;
      break;
    }

    case "solid": {
      const color = op.color ?? [1, 1, 1];
      const w = op.width ?? 1920;
      const h = op.height ?? 1080;
      const name = escapeString(op.name || "Solid");
      creationCode = `var ${varName} = ${compVar}.layers.addSolid([${color.join(", ")}], ${JSON.stringify(name)}, ${w}, ${h}, 1.0, ${compVar}.duration);`;
      break;
    }

    case "shape": {
      const name = escapeString(op.name || "Shape");
      creationCode = `var ${varName} = ${compVar}.layers.addShape();
            ${varName}.name = ${JSON.stringify(name)};`;
      break;
    }

    case "adjustment": {
      const color = op.color ?? [1, 1, 1];
      const name = escapeString(op.name || "Adjustment Layer");
      creationCode = `var ${varName} = ${compVar}.layers.addSolid([${color.join(", ")}], ${JSON.stringify(name)}, ${compVar}.width, ${compVar}.height, 1.0, ${compVar}.duration);
            ${varName}.adjustmentLayer = true;`;
      break;
    }

    case "null": {
      const name = escapeString(op.name || "Null");
      creationCode = `var ${varName} = ${compVar}.layers.addNull(${compVar}.duration);
            ${varName}.name = ${JSON.stringify(name)};`;
      break;
    }

    case "camera": {
      const name = escapeString(op.name || "Camera");
      creationCode = `var ${varName} = ${compVar}.layers.addCamera(${JSON.stringify(name)}, [0, 0]);`;
      break;
    }

    case "light": {
      const name = escapeString(op.name || "Light");
      creationCode = `var ${varName} = ${compVar}.layers.addLight(${JSON.stringify(name)}, [${compVar}.width/2, ${compVar}.height/2]);`;
      break;
    }

    case "footage": {
      const filePath = escapeString(op.filePath || "");
      creationCode = `
            var _footageFile = new File(${JSON.stringify(filePath)});
            if (!_footageFile.exists) {
                throw new Error("Footage file not found: ${filePath}");
            }
            var _footage = app.project.importFile(new ImportOptions(_footageFile));
            var ${varName} = ${compVar}.layers.add(_footage);`;
      break;
    }

    default:
      throw new Error(`Unknown layer type: ${layerType}`);
  }

  // 通用Transform属性设置
  let transformCode = "";
  if (op.position) {
    const pos = Array.isArray(op.position) ? op.position : [op.position, op.position];
    transformCode += `
            ${varName}.property("ADBE Transform Group").property("ADBE Position").setValue([${pos.join(", ")}]);`;
  }
  if (op.scale) {
    const scale = Array.isArray(op.scale) ? op.scale : [op.scale, op.scale];
    transformCode += `
            ${varName}.property("ADBE Transform Group").property("ADBE Scale").setValue([${scale.join(", ")}]);`;
  }
  if (op.rotation !== undefined) {
    transformCode += `
            ${varName}.property("ADBE Transform Group").property("ADBE Rotate Z").setValue(${op.rotation});`;
  }
  if (op.opacity !== undefined) {
    transformCode += `
            ${varName}.property("ADBE Transform Group").property("ADBE Opacity").setValue(${op.opacity});`;
  }
  if (op.anchorPoint) {
    transformCode += `
            ${varName}.property("ADBE Transform Group").property("ADBE Anchor Point").setValue([${op.anchorPoint.join(", ")}]);`;
  }
  if (op.is3D) {
    transformCode += `
            ${varName}.threeDLayer = true;`;
  }
  if (op.startTime !== undefined) {
    transformCode += `
            ${varName}.startTime = ${op.startTime};`;
  }

  return `        // [${node.id}] addLayer (${layerType}): ${op.name || ""}
        ${creationCode}
        if (${varName}) {${setupCode}${transformCode}
            _logResult("addLayer", { type: "${layerType}", "var": "${varName}", name: ${JSON.stringify(op.name || layerType)} });
        } else {
            throw new Error("Failed to create ${layerType} layer");
        }`;
}

// ============ AddEffect ============

function generateAddEffect(
  op: AddEffectOp,
  node: IRNode,
  variableMap: Map<string, string>,
  counter: { effect: number }
): string {
  const varName = `fx_${String(++counter.effect).padStart(3, "0")}`;
  if (op.ref) variableMap.set(op.ref, varName);

  const layerVar = variableMap.get(op.layerRef) || "null";
  const matchName = escapeString(op.matchName);

  // 生成settings代码
  let settingsCode = "";
  if (op.settings) {
    const settings = op.settings;
    for (const propName of Object.keys(settings)) {
      const value = settings[propName];
      const valueCode = formatJSXValue(value);
      settingsCode += `
            var _prop = ${varName}.property(${JSON.stringify(propName)});
            if (_prop) {
                _prop.setValue(${valueCode});
            }`;
    }
  }

  return `        // [${node.id}] addEffect: ${matchName}
        var _effParade_${counter.effect} = null;
        try { _effParade_${counter.effect} = ${layerVar}.property("ADBE Effect Parade"); } catch (e) { _effParade_${counter.effect} = null; }
        var ${varName} = null;
        if (_effParade_${counter.effect} && _effParade_${counter.effect}.addProperty) {
            try { ${varName} = _effParade_${counter.effect}.addProperty(${JSON.stringify(matchName)}); } catch (e) { _logError("addEffect", e); }
        } else if (${layerVar}.effects && ${layerVar}.effects.add) {
            try { ${varName} = ${layerVar}.effects.add(${JSON.stringify(matchName)}); } catch (e) { _logError("addEffect", e); }
        }
        if (${varName}) {${settingsCode}
            _logResult("addEffect", { matchName: ${JSON.stringify(matchName)}, "var": "${varName}", layerVar: "${layerVar}" });
        } else {
            throw new Error("Failed to add effect: ${matchName}");
        }`;
}

// ============ SetProperty ============

function generateSetProperty(
  op: SetPropertyOp,
  node: IRNode,
  variableMap: Map<string, string>
): string {
  const layerVar = variableMap.get(op.layerRef) || "null";
  const path = op.propertyPath;
  const value = formatJSXValue(op.value);

  return `        // [${node.id}] setProperty: ${path} = ${formatInlineValue(op.value)}
        var _prop = resolveProperty(${layerVar}, ${JSON.stringify(path)});
        if (_prop) {
            _prop.setValue(${value});
            _logResult("setProperty", { path: ${JSON.stringify(path)}, value: ${JSON.stringify(op.value)} });
        } else {
            throw new Error("Property not found: ${path}");
        }`;
}

// ============ SetKeyframe ============

function generateSetKeyframe(
  op: SetKeyframeOp,
  node: IRNode,
  variableMap: Map<string, string>
): string {
  const layerVar = variableMap.get(op.layerRef) || "null";
  const path = op.propertyPath;

  // 为每个关键帧生成代码
  let kfCode = "";
  op.keyframes.forEach((kf, i) => {
    const value = formatJSXValue(kf.value);
    kfCode += `
            // keyframe ${i + 1} at t=${kf.time}s
            _prop.setValueAtTime(${kf.time}, ${value});`;

    if (kf.easing) {
      const e = kf.easing;
      const interpType = mapEasingType(e.type);
      kfCode += `
            var _kIdx = _prop.nearestKeyIndex(${kf.time});
            _prop.setInterpolationTypeAtKey(_kIdx, ${interpType});`;

      if (e.type !== "linear" && e.type !== "hold") {
        const inSpeed = e.inSpeed ?? 0;
        const inInfluence = e.inInfluence ?? 33;
        const outSpeed = e.outSpeed ?? 0;
        const outInfluence = e.outInfluence ?? 33;
        kfCode += `
            var _inEase = new KeyframeEase(${inSpeed}, ${inInfluence});
            var _outEase = new KeyframeEase(${outSpeed}, ${outInfluence});
            _prop.setTemporalEaseAtKey(_kIdx, [_inEase], [_outEase]);`;
      }
    }
  });

  return `        // [${node.id}] setKeyframe: ${path} (${op.keyframes.length} keyframes)
        var _prop = resolveProperty(${layerVar}, ${JSON.stringify(path)});
        if (_prop) {${kfCode}
            _logResult("setKeyframe", { path: ${JSON.stringify(path)}, count: ${op.keyframes.length} });
        } else {
            throw new Error("Property not found for keyframes: ${path}");
        }`;
}

// ============ SetExpression ============

function generateSetExpression(
  op: SetExpressionOp,
  node: IRNode,
  variableMap: Map<string, string>
): string {
  const layerVar = variableMap.get(op.layerRef) || "null";
  const path = op.propertyPath;
  // 转义反斜杠和反引号(ExtendScript不支持模板字符串)
  const expr = escapeExpression(op.expression);

  return `        // [${node.id}] setExpression: ${path}
        var _prop = resolveProperty(${layerVar}, ${JSON.stringify(path)});
        if (_prop) {
            _prop.expression = ${JSON.stringify(expr)};
            _logResult("setExpression", { path: ${JSON.stringify(path)}, exprLength: ${expr.length} });
        } else {
            throw new Error("Property not found for expression: ${path}");
        }`;
}

// ============ AddMask ============

function generateAddMask(
  op: AddMaskOp,
  node: IRNode,
  variableMap: Map<string, string>,
  counter: { mask: number }
): string {
  const varName = `mask_${String(++counter.mask).padStart(3, "0")}`;
  if (op.ref) variableMap.set(op.ref, varName);

  const layerVar = variableMap.get(op.layerRef) || "null";

  // 构建Shape对象
  const vertices = op.vertices;
  const closed = op.closed !== false;
  const mode = mapMaskMode(op.mode || "add");
  const feather = op.feather ?? 0;
  const expansion = op.expansion ?? 0;
  const opacity = op.opacity ?? 100;

  // 顶点数组
  const verticesArray = vertices.map((v) => `[${v[0]}, ${v[1]}]`).join(", ");
  // inTangents / outTangents (全0)
  const tangents = vertices.map(() => `[0, 0]`).join(", ");

  return `        // [${node.id}] addMask: ${vertices.length} vertices
        var _shape = new Shape();
        _shape.vertices = [${verticesArray}];
        _shape.inTangents = [${tangents}];
        _shape.outTangents = [${tangents}];
        _shape.closed = ${closed};

        var ${varName} = ${layerVar}.property("ADBE Mask Parade").addShape(_shape);
        if (${varName}) {
            ${varName}.rotoBezier = true;
            ${varName}.property("ADBE Mask Shape").setValue(_shape);
            ${varName}.property("ADBE Mask Feather").setValue(${feather});
            ${varName}.property("ADBE Mask Expansion").setValue(${expansion});
            ${varName}.property("ADBE Mask Opacity").setValue(${opacity});
            ${varName}.maskMode = ${mode};
            _logResult("addMask", { "var": "${varName}", vertices: ${vertices.length}, mode: "${op.mode || "add"}" });
        } else {
            throw new Error("Failed to add mask");
        }`;
}

// ============ SetBlendMode ============

function generateSetBlendMode(
  op: SetBlendModeOp,
  node: IRNode,
  variableMap: Map<string, string>
): string {
  const layerVar = variableMap.get(op.layerRef) || "null";
  const blendModeConst = mapBlendMode(op.blendMode);

  return `        // [${node.id}] setBlendMode: ${op.blendMode}
        ${layerVar}.blendingMode = ${blendModeConst};
        _logResult("setBlendMode", { blendMode: "${op.blendMode}" });`;
}

// ============ SetParent ============

function generateSetParent(
  op: SetParentOp,
  node: IRNode,
  variableMap: Map<string, string>
): string {
  const layerVar = variableMap.get(op.layerRef) || "null";
  const parentVar = variableMap.get(op.parentRef) || "null";

  return `        // [${node.id}] setParent: ${op.layerRef} -> ${op.parentRef}
        ${layerVar}.parent = ${parentVar};
        _logResult("setParent", { layer: "${op.layerRef}", parent: "${op.parentRef}" });`;
}

// ============ SetTrackMatte ============

function generateSetTrackMatte(
  op: SetTrackMatteOp,
  node: IRNode,
  variableMap: Map<string, string>
): string {
  const layerVar = variableMap.get(op.layerRef) || "null";
  const matteVar = variableMap.get(op.matteRef) || "null";
  const matteTypeConst = mapMatteType(op.matteType);

  return `        // [${node.id}] setTrackMatte: ${op.matteRef} -> ${op.layerRef}
        ${layerVar}.trackMatteType = ${matteTypeConst};
        _logResult("setTrackMatte", { layer: "${op.layerRef}", matte: "${op.matteRef}", type: "${op.matteType}" });`;
}

// ============ 辅助函数 ============

/**
 * 转义字符串中的特殊字符
 */
function escapeString(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "\\r").replace(/\t/g, "\\t");
}

/**
 * 转义表达式（表达式内部的换行和引号需要特殊处理）
 */
function escapeExpression(expr: string): string {
  // ExtendScript表达式不能包含原始换行符在双引号字符串中
  return expr.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\r\n/g, "\\r\\n").replace(/\n/g, "\\r").replace(/\t/g, "\\t");
}

/**
 * 格式化JSX值
 */
function formatJSXValue(value: unknown): string {
  if (typeof value === "number") {
    return String(value);
  }
  if (typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (Array.isArray(value)) {
    return `[${value.map(formatJSXValue).join(", ")}]`;
  }
  if (value === null || value === undefined) {
    return "null";
  }
  return JSON.stringify(value);
}

/**
 * 格式化内联值（用于注释）
 */
function formatInlineValue(value: unknown): string {
  if (typeof value === "string") {
    return value.length > 30 ? `"${value.substring(0, 30)}..."` : `"${value}"`;
  }
  return formatJSXValue(value);
}

/**
 * 缓动类型映射到ExtendScript常量
 */
function mapEasingType(type: string): string {
  const map: Record<string, string> = {
    linear: "KeyframeInterpolationType.LINEAR",
    bezier: "KeyframeInterpolationType.BEZIER",
    hold: "KeyframeInterpolationType.HOLD",
    ease_in: "KeyframeInterpolationType.BEZIER",
    ease_out: "KeyframeInterpolationType.BEZIER",
    ease_in_out: "KeyframeInterpolationType.BEZIER",
  };
  return map[type] || "KeyframeInterpolationType.BEZIER";
}

/**
 * 遮罩模式映射
 */
function mapMaskMode(mode: string): string {
  const map: Record<string, string> = {
    add: "MaskMode.ADD",
    subtract: "MaskMode.SUBTRACT",
    intersect: "MaskMode.INTERSECT",
    difference: "MaskMode.DIFFERENCE",
    none: "MaskMode.NONE",
  };
  return map[mode] || "MaskMode.ADD";
}

/**
 * 混合模式映射
 */
function mapBlendMode(mode: BlendMode): string {
  // 转换PascalCase: "normal" -> "BlendingMode.NORMAL"
  const pascal = mode.charAt(0).toUpperCase() + mode.slice(1);
  // 处理特殊情况
  const specialMap: Record<string, string> = {
    "dancingDissolve": "BlendingMode.DANCING_DISSOLVE",
    "colorBurn": "BlendingMode.COLOR_BURN",
    "classicColorBurn": "BlendingMode.CLASSIC_COLOR_BURN",
    "linearBurn": "BlendingMode.LINEAR_BURN",
    "darkerColor": "BlendingMode.DARKER_COLOR",
    "colorDodge": "BlendingMode.COLOR_DODGE",
    "classicColorDodge": "BlendingMode.CLASSIC_COLOR_DODGE",
    "linearDodge": "BlendingMode.LINEAR_DODGE",
    "lighterColor": "BlendingMode.LIGHTER_COLOR",
    "softLight": "BlendingMode.SOFT_LIGHT",
    "hardLight": "BlendingMode.HARD_LIGHT",
    "vividLight": "BlendingMode.VIVID_LIGHT",
    "linearLight": "BlendingMode.LINEAR_LIGHT",
    "pinLight": "BlendingMode.PIN_LIGHT",
    "hardMix": "BlendingMode.HARD_MIX",
    "classicDifference": "BlendingMode.CLASSIC_DIFFERENCE",
    "stencilAlpha": "BlendingMode.STENCIL_ALPHA",
    "stencilLuma": "BlendingMode.STENCIL_LUMA",
    "silhouetteAlpha": "BlendingMode.SILHOUETTE_ALPHA",
    "silhouetteLuma": "BlendingMode.SILHOUETTE_LUMA",
    "alphaAdd": "BlendingMode.ALPHA_ADD",
    "lumaAdd": "BlendingMode.LUMA_ADD",
    "alphaDifference": "BlendingMode.ALPHA_DIFFERENCE",
  };
  return specialMap[mode] || `BlendingMode.${pascal.toUpperCase()}`;
}

/**
 * 轨道遮罩类型映射
 */
function mapMatteType(type: string): string {
  const map: Record<string, string> = {
    noMatte: "TrackMatteType.NO_TRACK_MATTE",
    alpha: "TrackMatteType.ALPHA",
    alphaInverted: "TrackMatteType.ALPHA_INVERTED",
    luma: "TrackMatteType.LUMA",
    lumaInverted: "TrackMatteType.LUMA_INVERTED",
    alphaOutline: "TrackMatteType.ALPHA_OUTLINE",
    alphaOutlineInverted: "TrackMatteType.ALPHA_OUTLINE_INVERTED",
    lumaOutline: "TrackMatteType.LUMA_OUTLINE",
    lumaOutlineInverted: "TrackMatteType.LUMA_OUTLINE_INVERTED",
  };
  return map[type] || "TrackMatteType.NO_TRACK_MATTE";
}
