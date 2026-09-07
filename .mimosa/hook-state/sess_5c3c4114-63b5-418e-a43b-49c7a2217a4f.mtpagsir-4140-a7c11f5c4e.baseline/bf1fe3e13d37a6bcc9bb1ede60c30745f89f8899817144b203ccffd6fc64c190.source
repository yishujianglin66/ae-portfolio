/**
 * Validator - 输入验证器
 * -----------------------------
 * 验证原子参数JSON的合法性和完整性
 *
 * @module apc/validator
 */

import type {
  CompilerInput,
  Operation,
  CompileError,
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
  EasingType,
  LayerType,
} from "./types.js";

// ============ 常量定义 ============

const VALID_OP_TYPES = new Set([
  "createComp",
  "addLayer",
  "addEffect",
  "setProperty",
  "setKeyframe",
  "setExpression",
  "addMask",
  "setBlendMode",
  "setParent",
  "setTrackMatte",
]);

const VALID_LAYER_TYPES = new Set<LayerType>([
  "text",
  "solid",
  "shape",
  "adjustment",
  "null",
  "camera",
  "light",
  "footage",
]);

const VALID_BLEND_MODES = new Set<BlendMode>([
  "normal",
  "dissolve",
  "dancingDissolve",
  "darken",
  "multiply",
  "colorBurn",
  "classicColorBurn",
  "linearBurn",
  "darkerColor",
  "add",
  "lighten",
  "screen",
  "colorDodge",
  "classicColorDodge",
  "linearDodge",
  "lighterColor",
  "overlay",
  "softLight",
  "hardLight",
  "vividLight",
  "linearLight",
  "pinLight",
  "hardMix",
  "difference",
  "classicDifference",
  "exclusion",
  "hue",
  "saturation",
  "color",
  "luminosity",
  "stencilAlpha",
  "stencilLuma",
  "silhouetteAlpha",
  "silhouetteLuma",
  "alphaAdd",
  "lumaAdd",
  "alphaDifference",
]);

const VALID_EASING_TYPES = new Set<EasingType>([
  "linear",
  "bezier",
  "hold",
  "ease_in",
  "ease_out",
  "ease_in_out",
]);

const VALID_MASK_MODES = new Set(["add", "subtract", "intersect", "difference", "none"]);

const VALID_MATTE_TYPES = new Set([
  "noMatte",
  "alpha",
  "alphaInverted",
  "luma",
  "lumaInverted",
  "alphaOutline",
  "alphaOutlineInverted",
  "lumaOutline",
  "lumaOutlineInverted",
]);

// 已知效果的matchName白名单 (用于warning, 不是error)
const KNOWN_EFFECT_MATCHNAMES = new Set([
  // AE原生
  "ADBE Gaussian Blur 2",
  "ADBE Directional Blur",
  "ADBE Radial Blur 2",
  "ADBE Camera Lens Blur",
  "ADBE Glow",
  "ADBE Color Balance (HLS)",
  "ADBE Brightness & Contrast 2",
  "ADBE Hue Saturation",
  "ADBE Tritone",
  "ADBE Vignette",
  "ADBE Turbulent Displace",
  "ADBE Wave Warp",
  "ADBE Fill",
  "ADBE Gradient Ramp",
  "ADBE Fractal Noise",
  "ADBE Light Rays",
  "ADBE Block Load",
  "ADBE Roughen Edges",
  "ADBE Linear Wipe",
  "ADBE Radial Wipe",
  "ADBE Card Wipe",
  "ADBE Particle World",
  "ADBE Motion Tile",
  "ADBE Optics Compensation",
  "ADBE Corner Pin",
  "ADBE Mesh Warp",
  "ADBE Lens Flare",
  "ADBE Channel Blur",
  "ADBE Set Channels",
  "ADBE Fast Box Blur",
  "ADBE Compound Blur",
  "ADBE Transform",
  "ADBE Liquid",
  "ADBE Ripple",
  "ADBE Polar Coordinates",
  "ADBE Wave Warp",
  // 第三方
  "ACP Particular",
  "ACP Form",
  "TC Shine",
  "ACP 3D Stroke",
  "ADBE Starglow",
  "ACP Sound Keys",
  "VC Element",
  "VC Optical Flares",
  "VC Saber",
  "ADBE Deep Glow",
  "ACP Plexus",
  // 第三方插件 matchName 变体（不同插件版本/平台注册的备用 matchName）
  // Saber (Video Copilot) - 主键: VC Saber
  "ADBE VC Saber",
  "ACP VC Saber",
  "VC Saber Legacy",
  // Particular (Trapcode) - 主键: ACP Particular
  "Trapcode Particular",
  "ADBE Trapcode Particular",
  "ACP Trapcode Particular",
  "Trapcode Particular 2",
  "Trapcode Particular 3",
  "Trapcode Particular 4",
  "Particular",
  "RG Particular",
  // Optical Flares (Video Copilot) - 主键: VC Optical Flares
  "Optical Flares",
  "ADBE Optical Flares",
  "ACP Optical Flares",
  // Element 3D (Video Copilot) - 主键: VC Element
  "Element 3D",
  "ADBE Element 3D",
  "ACP Element 3D",
  "VC Element 3D",
  // Plexus (Rowbyte/Trapcode) - 主键: ACP Plexus
  "Plexus",
  "ADBE Plexus",
  // Shine (Trapcode) - 主键: TC Shine
  "Shine",
  "ADBE Shine",
  "ACP Shine",
  "Trapcode Shine",
  // Sapphire 系列
  "S_GaussianBlur",
  "S_Glow",
  "S_Distort",
  "S_ColorBalance",
  "S_AnimTitle",
  // CC 系列原生效果
  "CC Radial Blur",
  "CC Cross Blur",
  "CC Light Rays",
  "CC Bend It",
  "CC Page Turn",
  "CC Particle World",
  "CC Star Burst",
  "CC Glass Wipe",
  "CC Grid Wipe",
  "CC Typewriter",
  // AE 原生补充
  "ADBE Box Blur",
  "ADBE Glo2",
  "ADBE Bezier Warp",
  "ADBE CurvesCustom",
  "ADBE HUE SATURATION",
  "ADBE Vibrance",
  "ADBE Color Balance",
  "ADBE Venetian Blinds",
  "ADBE Drop Shadow",
]);

// ============ 验证器 ============

export interface ValidationResult {
  valid: boolean;
  errors: CompileError[];
  warnings: string[];
  refs: Set<string>; // 所有定义的引用ID
}

/**
 * 主验证函数
 */
export function validate(input: CompilerInput): ValidationResult {
  const errors: CompileError[] = [];
  const warnings: string[] = [];
  const refs = new Set<string>();

  // 1. 顶层结构检查
  if (!input || typeof input !== "object") {
    errors.push({
      code: "E001",
      message: "输入必须是一个对象",
    });
    return { valid: false, errors, warnings, refs };
  }

  if (!Array.isArray(input.operations)) {
    errors.push({
      code: "E002",
      message: "operations 必须是一个数组",
    });
    return { valid: false, errors, warnings, refs };
  }

  // 2. 收集所有ref (跳过非对象操作)
  for (const op of input.operations) {
    if (op && typeof op === "object" && op.ref) {
      if (refs.has(op.ref)) {
        errors.push({
          code: "E010",
          message: `重复的ref: "${op.ref}"`,
        });
      }
      refs.add(op.ref);
    }
  }

  // 3. 逐个验证操作
  input.operations.forEach((op, index) => {
    const opErrors = validateOperation(op, index, refs);
    errors.push(...opErrors);
  });

  // 4. 引用完整性检查 (跳过非对象操作)
  for (const op of input.operations) {
    if (!op || typeof op !== "object") continue;
    // 检查 dependsOn 引用
    if (op.dependsOn) {
      for (const dep of op.dependsOn) {
        if (!refs.has(dep)) {
          errors.push({
            code: "E020",
            message: `操作 ${op.op} 引用了不存在的依赖: "${dep}"`,
            operationIndex: input.operations.indexOf(op),
          });
        }
      }
    }
    // 检查 compRef/layerRef/parentRef/matteRef
    const refChecks: Array<[string, string]> = [
      ["compRef" as keyof Operation, "compRef"],
      ["layerRef" as keyof Operation, "layerRef"],
      ["parentRef" as keyof Operation, "parentRef"],
      ["matteRef" as keyof Operation, "matteRef"],
    ];
    for (const [field, label] of refChecks) {
      const refValue = (op as Record<string, unknown>)[label];
      if (refValue && typeof refValue === "string" && !refs.has(refValue)) {
        errors.push({
          code: "E021",
          message: `操作 ${op.op} 引用了不存在的${label}: "${refValue}"`,
          operationIndex: input.operations.indexOf(op),
          ref: refValue,
        });
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
    refs,
  };
}

/**
 * 验证单个操作
 */
function validateOperation(op: Operation, index: number, refs: Set<string>): CompileError[] {
  const errors: CompileError[] = [];

  if (!op || typeof op !== "object") {
    errors.push({
      code: "E003",
      message: `操作 #${index} 必须是一个对象`,
      operationIndex: index,
    });
    return errors;
  }

  if (!op.op || !VALID_OP_TYPES.has(op.op)) {
    errors.push({
      code: "E004",
      message: `操作 #${index} 无效的op类型: "${op.op}"。有效类型: ${Array.from(VALID_OP_TYPES).join(", ")}`,
      operationIndex: index,
    });
    return errors;
  }

  // 根据op类型分发验证
  switch (op.op) {
    case "createComp":
      return validateCreateComp(op as CreateCompOp, index);
    case "addLayer":
      return validateAddLayer(op as AddLayerOp, index);
    case "addEffect":
      return validateAddEffect(op as AddEffectOp, index);
    case "setProperty":
      return validateSetProperty(op as SetPropertyOp, index);
    case "setKeyframe":
      return validateSetKeyframe(op as SetKeyframeOp, index);
    case "setExpression":
      return validateSetExpression(op as SetExpressionOp, index);
    case "addMask":
      return validateAddMask(op as AddMaskOp, index);
    case "setBlendMode":
      return validateSetBlendMode(op as SetBlendModeOp, index);
    case "setParent":
      return validateSetParent(op as SetParentOp, index);
    case "setTrackMatte":
      return validateSetTrackMatte(op as SetTrackMatteOp, index);
    default:
      return [];
  }
}

function validateCreateComp(op: CreateCompOp, index: number): CompileError[] {
  const errors: CompileError[] = [];

  if (!op.name || typeof op.name !== "string") {
    errors.push({ code: "E100", message: `createComp #${index}: name必填且为字符串`, operationIndex: index });
  }

  if (op.width !== undefined && (typeof op.width !== "number" || op.width < 1 || op.width > 32768)) {
    errors.push({ code: "E101", message: `createComp #${index}: width必须在1-32768之间`, operationIndex: index });
  }

  if (op.height !== undefined && (typeof op.height !== "number" || op.height < 1 || op.height > 32768)) {
    errors.push({ code: "E102", message: `createComp #${index}: height必须在1-32768之间`, operationIndex: index });
  }

  if (op.frameRate !== undefined && (typeof op.frameRate !== "number" || op.frameRate < 1 || op.frameRate > 120)) {
    errors.push({ code: "E103", message: `createComp #${index}: frameRate必须在1-120之间`, operationIndex: index });
  }

  if (op.duration !== undefined && (typeof op.duration !== "number" || op.duration < 0.1)) {
    errors.push({ code: "E104", message: `createComp #${index}: duration必须>0.1秒`, operationIndex: index });
  }

  if (op.bgColor && (!Array.isArray(op.bgColor) || op.bgColor.length !== 3 || !op.bgColor.every((c) => c >= 0 && c <= 1))) {
    errors.push({ code: "E105", message: `createComp #${index}: bgColor必须是3个0-1的数字`, operationIndex: index });
  }

  return errors;
}

function validateAddLayer(op: AddLayerOp, index: number): CompileError[] {
  const errors: CompileError[] = [];

  if (!op.compRef || typeof op.compRef !== "string") {
    errors.push({ code: "E200", message: `addLayer #${index}: compRef必填`, operationIndex: index });
  }

  if (!op.layerType || !VALID_LAYER_TYPES.has(op.layerType)) {
    errors.push({
      code: "E201",
      message: `addLayer #${index}: 无效的layerType "${op.layerType}"。有效: ${Array.from(VALID_LAYER_TYPES).join(", ")}`,
      operationIndex: index,
    });
  }

  // text类型必须有text内容
  if (op.layerType === "text" && !op.text) {
    errors.push({ code: "E202", message: `addLayer #${index}: text类型必须提供text内容`, operationIndex: index });
  }

  // solid类型必须有color
  if (op.layerType === "solid" && !op.color) {
    errors.push({ code: "E203", message: `addLayer #${index}: solid类型必须提供color`, operationIndex: index });
  }

  // footage类型必须有filePath
  if (op.layerType === "footage" && !op.filePath) {
    errors.push({ code: "E204", message: `addLayer #${index}: footage类型必须提供filePath`, operationIndex: index });
  }

  // 验证颜色值
  const colorFields: Array<keyof AddLayerOp> = ["fillColor", "color"];
  for (const field of colorFields) {
    const v = op[field] as [number, number, number] | undefined;
    if (v && (!Array.isArray(v) || v.length !== 3 || !v.every((c) => c >= 0 && c <= 1))) {
      errors.push({ code: "E205", message: `addLayer #${index}: ${field}必须是3个0-1的数字`, operationIndex: index });
    }
  }

  // 验证opacity
  if (op.opacity !== undefined && (typeof op.opacity !== "number" || op.opacity < 0 || op.opacity > 100)) {
    errors.push({ code: "E206", message: `addLayer #${index}: opacity必须在0-100之间`, operationIndex: index });
  }

  return errors;
}

function validateAddEffect(op: AddEffectOp, index: number): CompileError[] {
  const errors: CompileError[] = [];

  if (!op.layerRef || typeof op.layerRef !== "string") {
    errors.push({ code: "E300", message: `addEffect #${index}: layerRef必填`, operationIndex: index });
  }

  if (!op.matchName || typeof op.matchName !== "string") {
    errors.push({ code: "E301", message: `addEffect #${index}: matchName必填`, operationIndex: index });
  }

  // 已知效果检查（warning, 不是error）
  if (op.matchName && !KNOWN_EFFECT_MATCHNAMES.has(op.matchName)) {
    // 这是一个警告 - 第三方插件可能不在白名单中
  }

  // settings 验证
  if (op.settings && typeof op.settings !== "object") {
    errors.push({ code: "E302", message: `addEffect #${index}: settings必须是对象`, operationIndex: index });
  }

  return errors;
}

function validateSetProperty(op: SetPropertyOp, index: number): CompileError[] {
  const errors: CompileError[] = [];

  if (!op.layerRef) {
    errors.push({ code: "E400", message: `setProperty #${index}: layerRef必填`, operationIndex: index });
  }

  if (!op.propertyPath || typeof op.propertyPath !== "string") {
    errors.push({ code: "E401", message: `setProperty #${index}: propertyPath必填`, operationIndex: index });
  }

  if (op.value === undefined) {
    errors.push({ code: "E402", message: `setProperty #${index}: value必填`, operationIndex: index });
  }

  return errors;
}

function validateSetKeyframe(op: SetKeyframeOp, index: number): CompileError[] {
  const errors: CompileError[] = [];

  if (!op.layerRef) {
    errors.push({ code: "E500", message: `setKeyframe #${index}: layerRef必填`, operationIndex: index });
  }

  if (!op.propertyPath) {
    errors.push({ code: "E501", message: `setKeyframe #${index}: propertyPath必填`, operationIndex: index });
  }

  if (!Array.isArray(op.keyframes) || op.keyframes.length === 0) {
    errors.push({ code: "E502", message: `setKeyframe #${index}: keyframes必须是非空数组`, operationIndex: index });
    return errors;
  }

  // 验证每个关键帧
  op.keyframes.forEach((kf, kfIndex) => {
    if (typeof kf.time !== "number" || kf.time < 0) {
      errors.push({
        code: "E503",
        message: `setKeyframe #${index}: keyframe[${kfIndex}].time必须是非负数字`,
        operationIndex: index,
      });
    }

    if (kf.value === undefined) {
      errors.push({
        code: "E504",
        message: `setKeyframe #${index}: keyframe[${kfIndex}].value必填`,
        operationIndex: index,
      });
    }

    if (kf.easing && kf.easing.type && !VALID_EASING_TYPES.has(kf.easing.type)) {
      errors.push({
        code: "E505",
        message: `setKeyframe #${index}: keyframe[${kfIndex}].easing.type无效: "${kf.easing.type}"`,
        operationIndex: index,
      });
    }
  });

  // 检查关键帧时间是否单调递增
  for (let i = 1; i < op.keyframes.length; i++) {
    if (op.keyframes[i].time < op.keyframes[i - 1].time) {
      errors.push({
        code: "E506",
        message: `setKeyframe #${index}: keyframe时间必须单调递增 (keyframe[${i}].time < keyframe[${i - 1}].time)`,
        operationIndex: index,
      });
      break;
    }
  }

  return errors;
}

function validateSetExpression(op: SetExpressionOp, index: number): CompileError[] {
  const errors: CompileError[] = [];

  if (!op.layerRef) {
    errors.push({ code: "E600", message: `setExpression #${index}: layerRef必填`, operationIndex: index });
  }

  if (!op.propertyPath) {
    errors.push({ code: "E601", message: `setExpression #${index}: propertyPath必填`, operationIndex: index });
  }

  if (!op.expression || typeof op.expression !== "string") {
    errors.push({ code: "E602", message: `setExpression #${index}: expression必填且为字符串`, operationIndex: index });
  }

  // 简单的表达式语法检查（不深度解析）
  if (op.expression) {
    const expr = op.expression.trim();
    // 检查括号平衡
    const parens = (expr.match(/\(/g) || []).length - (expr.match(/\)/g) || []).length;
    if (parens !== 0) {
      errors.push({
        code: "E603",
        message: `setExpression #${index}: expression括号不平衡 (${parens > 0 ? "缺少)" : "缺少("})`,
        operationIndex: index,
      });
    }
    // 检查分号结尾
    if (!expr.endsWith(";") && !expr.endsWith("}")) {
      // 单行表达式可以没有分号，但多行应该有 - 仅作warning
    }
  }

  return errors;
}

function validateAddMask(op: AddMaskOp, index: number): CompileError[] {
  const errors: CompileError[] = [];

  if (!op.layerRef) {
    errors.push({ code: "E700", message: `addMask #${index}: layerRef必填`, operationIndex: index });
  }

  if (!Array.isArray(op.vertices) || op.vertices.length < 3) {
    errors.push({ code: "E701", message: `addMask #${index}: vertices必须至少3个点`, operationIndex: index });
  }

  // 验证顶点坐标
  if (op.vertices) {
    op.vertices.forEach((v, vIndex) => {
      if (!Array.isArray(v) || v.length !== 2 || !v.every((c) => typeof c === "number")) {
        errors.push({
          code: "E702",
          message: `addMask #${index}: vertices[${vIndex}]必须是[x,y]数字数组`,
          operationIndex: index,
        });
      }
    });
  }

  if (op.mode && !VALID_MASK_MODES.has(op.mode)) {
    errors.push({
      code: "E703",
      message: `addMask #${index}: 无效的mode "${op.mode}"`,
      operationIndex: index,
    });
  }

  return errors;
}

function validateSetBlendMode(op: SetBlendModeOp, index: number): CompileError[] {
  const errors: CompileError[] = [];

  if (!op.layerRef) {
    errors.push({ code: "E800", message: `setBlendMode #${index}: layerRef必填`, operationIndex: index });
  }

  if (!op.blendMode || !VALID_BLEND_MODES.has(op.blendMode)) {
    errors.push({
      code: "E801",
      message: `setBlendMode #${index}: 无效的blendMode "${op.blendMode}"`,
      operationIndex: index,
    });
  }

  return errors;
}

function validateSetParent(op: SetParentOp, index: number): CompileError[] {
  const errors: CompileError[] = [];

  if (!op.layerRef) {
    errors.push({ code: "E900", message: `setParent #${index}: layerRef必填`, operationIndex: index });
  }

  if (!op.parentRef) {
    errors.push({ code: "E901", message: `setParent #${index}: parentRef必填`, operationIndex: index });
  }

  if (op.layerRef === op.parentRef) {
    errors.push({ code: "E902", message: `setParent #${index}: layerRef和parentRef不能相同`, operationIndex: index });
  }

  return errors;
}

function validateSetTrackMatte(op: SetTrackMatteOp, index: number): CompileError[] {
  const errors: CompileError[] = [];

  if (!op.layerRef) {
    errors.push({ code: "EA00", message: `setTrackMatte #${index}: layerRef必填`, operationIndex: index });
  }

  if (!op.matteRef) {
    errors.push({ code: "EA01", message: `setTrackMatte #${index}: matteRef必填`, operationIndex: index });
  }

  if (!op.matteType || !VALID_MATTE_TYPES.has(op.matteType)) {
    errors.push({
      code: "EA02",
      message: `setTrackMatte #${index}: 无效的matteType "${op.matteType}"`,
      operationIndex: index,
    });
  }

  return errors;
}
