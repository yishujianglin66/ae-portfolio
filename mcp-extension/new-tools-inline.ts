// ============================================================================
// new-tools-inline.ts
// Phase 2 扩展 - 14个新MCP工具的内联注册代码
//
// 用途：本文件包含的14个 server.tool() 调用将直接追加到 index.ts 末尾
// 优势：所有工具注册代码与现有22个工具在同一作用域，可直接访问：
//   - writeCommandFile()
//   - waitForBridgeResult()
//   - clearResultsFile()
//   - server (McpServer 实例)
//   - z (zod)
// ============================================================================

// ============================================================================
// 工具1: add-effect-with-keyframes
// 添加效果并设置关键帧动画（一次性完成）
// ============================================================================
server.tool(
  "add-effect-with-keyframes",
  "向指定图层添加效果并设置关键帧动画。一次性完成效果添加+参数设置+关键帧动画。常用matchName: ADBE Gaussian Blur 2(高斯模糊)/ADBE Glo2(发光)/ADBE Curve(曲线)/ADBE Vibrance(自然饱和度)",
  {
    compName: z.string().describe("目标合成名称"),
    layerIndex: z.number().int().positive().describe("目标图层索引（1-based）"),
    effectMatchName: z.string().describe("效果matchName，如 'ADBE Gaussian Blur 2'"),
    settings: z.record(z.string(), z.unknown()).optional().describe("效果初始参数 {propName: value}"),
    keyframes: z.array(z.object({
      propertyName: z.string(),
      time: z.number(),
      value: z.union([z.number(), z.array(z.number())]),
      easingType: z.enum(["linear", "easeIn", "easeOut", "easeInOut", "bezier"]).optional().default("linear")
    })).optional()
  },
  async ({ compName, layerIndex, effectMatchName, settings, keyframes }) => {
    try {
      clearResultsFile();
      writeCommandFile("addEffectWithKeyframes", {
        compName, layerIndex, effectMatchName, settings: settings || {}, keyframes: keyframes || []
      });
      const result = await waitForBridgeResult("addEffectWithKeyframes", 8000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具2: set-keyframe-easing
// 设置关键帧缓动曲线
// ============================================================================
server.tool(
  "set-keyframe-easing",
  "设置指定关键帧的缓动曲线。支持linear/easeIn/easeOut/easeInOut/bezier/hold六种缓动。常用：easeInOut(speed=0,influence=90)产生平滑缓动",
  {
    compName: z.string().describe("目标合成名称"),
    layerIndex: z.number().int().positive().describe("目标图层索引"),
    propertyPath: z.string().describe("属性路径，如 'transform.position'"),
    keyIndex: z.number().int().positive().describe("关键帧索引（1-based）"),
    easingType: z.enum(["linear", "easeIn", "easeOut", "easeInOut", "bezier", "hold"]),
    easeIn: z.object({
      speed: z.number().default(0),
      influence: z.number().default(33)
    }).optional(),
    easeOut: z.object({
      speed: z.number().default(0),
      influence: z.number().default(33)
    }).optional()
  },
  async ({ compName, layerIndex, propertyPath, keyIndex, easingType, easeIn, easeOut }) => {
    try {
      clearResultsFile();
      writeCommandFile("setKeyframeEasing", {
        compName, layerIndex, propertyPath, keyIndex, easingType,
        easeIn: easeIn || { speed: 0, influence: 33 },
        easeOut: easeOut || { speed: 0, influence: 33 }
      });
      const result = await waitForBridgeResult("setKeyframeEasing", 8000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具3: batch-add-effects
// 批量添加多个效果
// ============================================================================
server.tool(
  "batch-add-effects",
  "批量向指定图层添加多个效果。适用于需要叠加多个效果的风格化操作，如同时添加模糊+发光+调色。所有效果在一个undo组中",
  {
    compName: z.string().describe("目标合成名称"),
    layerIndex: z.number().int().positive().describe("目标图层索引"),
    effects: z.array(z.object({
      effectMatchName: z.string(),
      settings: z.record(z.string(), z.unknown()).optional()
    })).min(1)
  },
  async ({ compName, layerIndex, effects }) => {
    try {
      clearResultsFile();
      writeCommandFile("batchAddEffects", { compName, layerIndex, effects });
      const result = await waitForBridgeResult("batchAddEffects", 8000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具4: set-blend-mode
// 设置图层混合模式
// ============================================================================
server.tool(
  "set-blend-mode",
  "设置图层混合模式。常用模式：SCREEN(滤色/发光叠加)、MULTIPLY(正片叠底/暗部叠加)、ADD(相加/光效叠加)、OVERLAY(叠加/对比增强)",
  {
    compName: z.string().describe("目标合成名称"),
    layerIndex: z.number().int().positive().describe("目标图层索引"),
    blendMode: z.enum([
      "NONE", "DISSOLVE", "MULTIPLY", "SCREEN", "OVERLAY", "SOFT_LIGHT", "HARD_LIGHT",
      "ADD", "COLOR_DODGE", "COLOR_BURN", "DARKEN", "LIGHTEN", "DIFFERENCE", "EXCLUSION",
      "HUE", "SATURATION", "COLOR", "LUMINOSITY"
    ])
  },
  async ({ compName, layerIndex, blendMode }) => {
    try {
      clearResultsFile();
      writeCommandFile("setBlendMode", { compName, layerIndex, blendMode });
      const result = await waitForBridgeResult("setBlendMode", 8000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具5: set-track-matte
// 设置轨道遮罩
// ============================================================================
server.tool(
  "set-track-matte",
  "设置图层轨道遮罩类型。ALPHA遮罩用上层Alpha通道，LUMA遮罩用上层亮度值。遮罩层需在目标图层上方",
  {
    compName: z.string().describe("目标合成名称"),
    layerIndex: z.number().int().positive().describe("目标图层索引"),
    matteType: z.enum([
      "NO_TRACK_MATTE", "ALPHA_TRACK_MATTE", "ALPHA_INVERTED_TRACK_MATTE",
      "LUMA_TRACK_MATTE", "LUMA_INVERTED_TRACK_MATTE"
    ])
  },
  async ({ compName, layerIndex, matteType }) => {
    try {
      clearResultsFile();
      writeCommandFile("setTrackMatte", { compName, layerIndex, matteType });
      const result = await waitForBridgeResult("setTrackMatte", 8000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具6: set-parent-layer
// 设置图层父子关系
// ============================================================================
server.tool(
  "set-parent-layer",
  "设置图层父子关系。子图层将继承父图层的变换。parentIndex=0取消父子关系。常用于Null控制多图层、摄像机绑定",
  {
    compName: z.string().describe("目标合成名称"),
    layerIndex: z.number().int().positive().describe("子图层索引"),
    parentIndex: z.number().int().min(0).describe("父图层索引，0表示取消父子关系")
  },
  async ({ compName, layerIndex, parentIndex }) => {
    try {
      clearResultsFile();
      writeCommandFile("setParentLayer", { compName, layerIndex, parentIndex });
      const result = await waitForBridgeResult("setParentLayer", 8000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具7: add-adjustment-layer
// 创建调整图层
// ============================================================================
server.tool(
  "add-adjustment-layer",
  "创建调整图层。调整图层本身不渲染，但会对其下方所有图层应用效果。常用于全局调色、全局模糊",
  {
    compName: z.string().describe("目标合成名称"),
    name: z.string().optional().default("Adjustment Layer"),
    position: z.number().int().min(0).optional().default(1).describe("插入位置索引，0表示最上方")
  },
  async ({ compName, name, position }) => {
    try {
      clearResultsFile();
      writeCommandFile("addAdjustmentLayer", { compName, name, position });
      const result = await waitForBridgeResult("addAdjustmentLayer", 8000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具8: add-precomp
// 创建预合成
// ============================================================================
server.tool(
  "add-precomp",
  "将指定图层预合成为新的合成。预合成可简化时间轴、嵌套效果、实现复杂层级结构",
  {
    compName: z.string().describe("源合成名称"),
    name: z.string().describe("新预合成名称"),
    layerIndices: z.array(z.number().int().positive()).min(1).describe("要预合成的图层索引列表"),
    moveAllAttributes: z.boolean().optional().default(true)
  },
  async ({ compName, name, layerIndices, moveAllAttributes }) => {
    try {
      clearResultsFile();
      writeCommandFile("addPrecomp", { compName, name, layerIndices, moveAllAttributes });
      const result = await waitForBridgeResult("addPrecomp", 8000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具9: import-footage
// 导入素材
// ============================================================================
server.tool(
  "import-footage",
  "导入素材文件到AE项目。支持图片、视频、音频、序列。可指定目标合成自动添加",
  {
    filePath: z.string().describe("素材文件的绝对路径"),
    compName: z.string().optional().describe("目标合成名称（不填则仅导入项目）"),
    asSequence: z.boolean().optional().default(false),
    position: z.number().int().optional().describe("在合成中的插入位置索引")
  },
  async ({ filePath, compName, asSequence, position }) => {
    try {
      clearResultsFile();
      writeCommandFile("importFootage", { filePath, compName, asSequence, position });
      const result = await waitForBridgeResult("importFootage", 8000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具10: set-motion-blur
// 设置运动模糊
// ============================================================================
server.tool(
  "set-motion-blur",
  "设置运动模糊。快门角度180°为标准电影感，360°为强烈拖尾。需同时启用合成和图层的运动模糊开关",
  {
    compName: z.string().describe("目标合成名称"),
    layerIndex: z.number().int().optional().describe("图层索引，0或省略表示仅设置合成级别"),
    enabled: z.boolean(),
    shutterAngle: z.number().min(0).max(720).optional().describe("快门角度（0-720），默认180"),
    shutterPhase: z.number().min(-360).max(360).optional()
  },
  async ({ compName, layerIndex, enabled, shutterAngle, shutterPhase }) => {
    try {
      clearResultsFile();
      writeCommandFile("setMotionBlur", {
        compName, layerIndex: layerIndex || 0, enabled, shutterAngle, shutterPhase
      });
      const result = await waitForBridgeResult("setMotionBlur", 8000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具11: add-mask-with-shape
// 添加形状遮罩
// ============================================================================
server.tool(
  "add-mask-with-shape",
  "向图层添加自定义形状遮罩。支持贝塞尔曲线顶点、羽化、模式设置。常用于区域限制效果范围",
  {
    compName: z.string().describe("目标合成名称"),
    layerIndex: z.number().int().positive().describe("目标图层索引"),
    vertices: z.array(z.object({
      x: z.number(),
      y: z.number(),
      inTangent: z.array(z.number()).optional(),
      outTangent: z.array(z.number()).optional()
    })).min(3).describe("遮罩顶点坐标数组"),
    feather: z.array(z.number()).length(2).optional().default([0, 0]).describe("遮罩羽化 [水平, 垂直]"),
    mode: z.enum(["add", "subtract", "intersect", "difference", "lighten", "darken", "none"]).optional().default("add"),
    opacity: z.number().min(0).max(100).optional().default(100),
    expansion: z.number().optional().default(0),
    inverted: z.boolean().optional().default(false)
  },
  async ({ compName, layerIndex, vertices, feather, mode, opacity, expansion, inverted }) => {
    try {
      clearResultsFile();
      writeCommandFile("addMaskWithShape", {
        compName, layerIndex, vertices,
        feather: feather || [0, 0],
        mode: mode || "add",
        opacity: opacity || 100,
        expansion: expansion || 0,
        inverted: inverted || false
      });
      const result = await waitForBridgeResult("addMaskWithShape", 8000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具12: execute-atom-script
// 执行编译器生成的脚本（Phase 1 → Phase 2 直接通道）
// ============================================================================
server.tool(
  "execute-atom-script",
  "执行原子参数编译器生成的ExtendScript脚本。这是知识编译器→AE执行的直接通道，支持干运行验证。dryRun=true仅检查语法不执行",
  {
    scriptContent: z.string().describe("编译器生成的ExtendScript代码"),
    scriptName: z.string().optional().default("atom-script"),
    timeout: z.number().optional().default(10000),
    dryRun: z.boolean().optional().default(false)
  },
  async ({ scriptContent, scriptName, timeout, dryRun }) => {
    try {
      clearResultsFile();
      writeCommandFile("executeAtomScript", {
        scriptContent, scriptName, timeout: timeout || 10000, dryRun: dryRun || false
      });
      // 原子脚本可能执行时间较长，使用更长超时
      const result = await waitForBridgeResult("executeAtomScript", 15000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具13: get-effect-properties
// 获取效果属性
// ============================================================================
server.tool(
  "get-effect-properties",
  "获取图层上指定效果的所有属性及当前值。用于验证效果参数、读取当前状态、检查关键帧",
  {
    compName: z.string().describe("目标合成名称"),
    layerIndex: z.number().int().positive().describe("目标图层索引"),
    effectIndex: z.number().int().positive().describe("效果索引（1-based）")
  },
  async ({ compName, layerIndex, effectIndex }) => {
    try {
      clearResultsFile();
      writeCommandFile("getEffectProperties", { compName, layerIndex, effectIndex });
      const result = await waitForBridgeResult("getEffectProperties", 8000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具14: set-effect-keyframes
// 为效果属性设置关键帧
// ============================================================================
server.tool(
  "set-effect-keyframes",
  "为已有效果的属性批量设置关键帧。与add-effect-with-keyframes不同，此工具用于已存在效果的动画设置",
  {
    compName: z.string().describe("目标合成名称"),
    layerIndex: z.number().int().positive().describe("目标图层索引"),
    effectIndex: z.number().int().positive().describe("效果索引（1-based）"),
    propName: z.string().describe("效果内的属性名，如 'Blurriness'"),
    keyframes: z.array(z.object({
      time: z.number(),
      value: z.union([z.number(), z.array(z.number())]),
      easingType: z.enum(["linear", "easeIn", "easeOut", "easeInOut", "hold"]).optional().default("linear")
    })).min(1)
  },
  async ({ compName, layerIndex, effectIndex, propName, keyframes }) => {
    try {
      clearResultsFile();
      writeCommandFile("setEffectKeyframes", { compName, layerIndex, effectIndex, propName, keyframes });
      const result = await waitForBridgeResult("setEffectKeyframes", 8000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

// ============================================================================
// 工具15: apply-newton-dynamics
// 牛顿动力学 - 为图层添加物理模拟（重力/弹性/摩擦/碰撞）
// ============================================================================
server.tool(
  "apply-newton-dynamics",
  "牛顿动力学物理模拟。为图层添加重力、弹性、摩擦、边界碰撞等物理效果。支持expression模式（实时可调整）和bake模式（烘焙关键帧）。常用场景：掉落弹跳、悬浮振荡、碰撞动画、物理模拟效果",
  {
    compName: z.string().describe("目标合成名称"),
    layerIndices: z.array(z.number().int().positive()).min(1).describe("应用动力学的图层索引列表"),
    mode: z.enum(["expression", "keyframe", "bake"]).optional().default("expression").describe("expression=表达式模式（可实时调整参数），keyframe/bake=烘焙关键帧模式"),
    gravity: z.number().optional().default(2000).describe("重力加速度（像素/秒^2），默认2000"),
    bounce: z.number().min(0).max(1).optional().default(0.6).describe("弹性系数（0-1），0=无弹性，1=完全弹性"),
    friction: z.number().min(0).max(1).optional().default(0.98).describe("摩擦系数（0-1），越小摩擦力越大"),
    groundY: z.number().optional().describe("地面Y坐标（像素），默认合成高度-50"),
    startVelocity: z.array(z.number()).length(2).optional().describe("初始速度 [vx, vy]，默认[0,0]"),
    gravityDirection: z.enum(["down", "up", "left", "right"]).optional().default("down").describe("重力方向")
  },
  async ({ compName, layerIndices, mode, gravity, bounce, friction, groundY, startVelocity, gravityDirection }) => {
    try {
      clearResultsFile();
      writeCommandFile("applyNewtonDynamics", {
        compName,
        layerIndices,
        mode: mode || "expression",
        gravity: gravity !== undefined ? gravity : 2000,
        bounce: bounce !== undefined ? bounce : 0.6,
        friction: friction !== undefined ? friction : 0.98,
        groundY: groundY !== undefined ? groundY : null,
        startVelocity: startVelocity || [0, 0],
        gravityDirection: gravityDirection || "down"
      });
      const result = await waitForBridgeResult("applyNewtonDynamics", 15000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);
