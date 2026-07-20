/**
 * AE原子参数编译器 (Atomic Parameter Compiler, APC)
 * -----------------------------------------------
 * 将原子级参数JSON编译为AE可执行的ExtendScript代码
 *
 * 编译流程:
 *   JSON Input → Validator → IR Builder → Scheduler → Code Generator → ExtendScript
 *
 * @module apc
 */

// ============ 类型定义 ============

/**
 * 操作类型枚举
 */
export type OperationType =
  | "createComp"
  | "addLayer"
  | "addEffect"
  | "setProperty"
  | "setKeyframe"
  | "setExpression"
  | "addMask"
  | "setBlendMode"
  | "setParent"
  | "setTrackMatte";

/**
 * 缓动类型枚举
 */
export type EasingType =
  | "linear"
  | "bezier"
  | "hold"
  | "ease_in"
  | "ease_out"
  | "ease_in_out";

/**
 * 图层类型枚举
 */
export type LayerType =
  | "text"
  | "solid"
  | "shape"
  | "adjustment"
  | "null"
  | "camera"
  | "light"
  | "footage";

/**
 * 原子操作基础接口
 */
export interface BaseOperation {
  op: OperationType;
  ref?: string; // 引用ID, 用于其他操作引用此操作的结果
  dependsOn?: string[]; // 依赖的其他操作引用ID
}

/**
 * 创建合成操作
 */
export interface CreateCompOp extends BaseOperation {
  op: "createComp";
  name: string;
  width?: number; // 默认1920
  height?: number; // 默认1080
  frameRate?: number; // 默认30
  duration?: number; // 秒, 默认10
  bgColor?: [number, number, number]; // 0-1 RGB
  pixelAspect?: number; // 默认1.0
}

/**
 * 添加图层操作
 */
export interface AddLayerOp extends BaseOperation {
  op: "addLayer";
  compRef: string; // 合成的引用ID
  layerType: LayerType;
  name?: string;
  // text 类型
  text?: string;
  fontSize?: number;
  font?: string;
  fillColor?: [number, number, number];
  justification?: "left" | "center" | "right";
  // solid 类型
  color?: [number, number, number];
  width?: number;
  height?: number;
  // footage 类型
  filePath?: string;
  // 通用 Transform 属性
  position?: [number, number] | [number, number, number];
  scale?: [number, number] | number;
  rotation?: number;
  opacity?: number;
  anchorPoint?: [number, number] | [number, number, number];
  // 时间
  startTime?: number;
  inPoint?: number;
  outPoint?: number;
  // 3D
  is3D?: boolean;
}

/**
 * 添加效果操作
 */
export interface AddEffectOp extends BaseOperation {
  op: "addEffect";
  layerRef: string; // 图层的引用ID
  matchName: string; // 效果的matchName, 如 "ADBE Gaussian Blur 2"
  name?: string; // 显示名（可选）
  settings?: Record<string, number | string | boolean | number[]>; // 效果参数键值对
}

/**
 * 设置属性操作
 */
export interface SetPropertyOp extends BaseOperation {
  op: "setProperty";
  layerRef: string;
  propertyPath: string; // 如 "Transform/Position" 或 "Effects.Gaussian Blur.Blurriness"
  value: number | string | boolean | number[];
}

/**
 * 设置关键帧操作
 */
export interface SetKeyframeOp extends BaseOperation {
  op: "setKeyframe";
  layerRef: string;
  propertyPath: string;
  keyframes: Array<{
    time: number; // 秒
    value: number | string | boolean | number[];
    easing?: {
      type: EasingType;
      inSpeed?: number; // 0-100
      inInfluence?: number; // 0-100
      outSpeed?: number;
      outInfluence?: number;
    };
  }>;
}

/**
 * 设置表达式操作
 */
export interface SetExpressionOp extends BaseOperation {
  op: "setExpression";
  layerRef: string;
  propertyPath: string;
  expression: string;
}

/**
 * 添加遮罩操作
 */
export interface AddMaskOp extends BaseOperation {
  op: "addMask";
  layerRef: string;
  vertices: Array<[number, number]>; // 遮罩路径顶点
  closed?: boolean; // 默认true
  mode?: "add" | "subtract" | "intersect" | "difference" | "none";
  feather?: number;
  expansion?: number;
  opacity?: number;
}

/**
 * 设置混合模式操作
 */
export interface SetBlendModeOp extends BaseOperation {
  op: "setBlendMode";
  layerRef: string;
  blendMode: BlendMode;
}

/**
 * 混合模式枚举
 */
export type BlendMode =
  | "normal"
  | "dissolve"
  | "dancingDissolve"
  | "darken"
  | "multiply"
  | "colorBurn"
  | "classicColorBurn"
  | "linearBurn"
  | "darkerColor"
  | "add"
  | "lighten"
  | "screen"
  | "colorDodge"
  | "classicColorDodge"
  | "linearDodge"
  | "lighterColor"
  | "overlay"
  | "softLight"
  | "hardLight"
  | "vividLight"
  | "linearLight"
  | "pinLight"
  | "hardMix"
  | "difference"
  | "classicDifference"
  | "exclusion"
  | "hue"
  | "saturation"
  | "color"
  | "luminosity"
  | "stencilAlpha"
  | "stencilLuma"
  | "silhouetteAlpha"
  | "silhouetteLuma"
  | "alphaAdd"
  | "lumaAdd"
  | "alphaDifference";

/**
 * 设置父子关系操作
 */
export interface SetParentOp extends BaseOperation {
  op: "setParent";
  layerRef: string;
  parentRef: string;
}

/**
 * 设置轨道遮罩操作
 */
export interface SetTrackMatteOp extends BaseOperation {
  op: "setTrackMatte";
  layerRef: string;
  matteRef: string;
  matteType:
    | "noMatte"
    | "alpha"
    | "alphaInverted"
    | "luma"
    | "lumaInverted"
    | "alphaOutline"
    | "alphaOutlineInverted"
    | "lumaOutline"
    | "lumaOutlineInverted";
}

/**
 * 联合类型: 所有操作
 */
export type Operation =
  | CreateCompOp
  | AddLayerOp
  | AddEffectOp
  | SetPropertyOp
  | SetKeyframeOp
  | SetExpressionOp
  | AddMaskOp
  | SetBlendModeOp
  | SetParentOp
  | SetTrackMatteOp;

/**
 * 编译器输入
 */
export interface CompilerInput {
  metadata?: {
    source?: string;
    confidence?: number;
    timestamp?: string;
    description?: string;
  };
  operations: Operation[];
}

/**
 * IR节点类型
 */
export type IRNodeType = Operation["op"];

/**
 * IR节点基类
 */
export interface IRNode {
  id: string; // 唯一ID
  type: IRNodeType;
  deps: string[]; // 依赖的其他IR节点ID
  source: Operation; // 原始操作
}

/**
 * 编译结果
 */
export interface CompileResult {
  success: boolean;
  script: string; // 生成的ExtendScript代码
  errors: CompileError[];
  warnings: string[];
  stats: {
    operationCount: number;
    irNodeCount: number;
    scriptSize: number;
    compileTimeMs: number;
  };
}

/**
 * 编译错误
 */
export interface CompileError {
  code: string;
  message: string;
  operationIndex?: number;
  ref?: string;
}
