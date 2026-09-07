// ============================================================================
// index-additions.ts
// Phase 2 扩展 - 25个新MCP工具的注册代码
//
// 用途：将本文件内容合并到 after-effects-mcp-main/src/index.ts 中
// 合并方式：
//   1. 将 NEW_ALLOWED_SCRIPTS 中的25个条目合并到现有 allowedScripts 数组
//   2. 将 REGISTER_NEW_TOOLS() 函数调用插入到 server 启动前
//
// 设计原则：
//   - 所有25个新工具复用现有的 writeCommandFile() + waitForBridgeResult() 通信通道
//   - 每个工具都有清晰的 zod schema 用于参数验证
//   - 工具描述包含使用提示，便于AI正确调用
//   - 与现有22个工具保持一致的模式
// ============================================================================

import { z } from "zod";

// ============================================================================
// 第一部分：25个新脚本名称（合并到现有 allowedScripts 数组）
// ============================================================================

export const NEW_ALLOWED_SCRIPTS = [
  // Phase 2 扩展 - 16个新工具
  "addEffectWithKeyframes",
  "setKeyframeEasing",
  "batchAddEffects",
  "setBlendMode",
  "setTrackMatte",
  "setParentLayer",
  "addAdjustmentLayer",
  "addPrecomp",
  "importFootage",
  "setMotionBlur",
  "addMaskWithShape",
  "executeAtomScript",
  "getEffectProperties",
  "setEffectKeyframes",
  "applyNewtonDynamics",
  "createE2EMusicVideo",
  // Phase 3 扩展 - 9个新工具
  "addTextLayer",
  "addShapeLayer",
  "addCamera",
  "addLight",
  "applyLUT",
  "enableTimeRemap",
  "applySaber",
  "applyParticular",
  "applyOpticalFlares"
];

// ============================================================================
// 第二部分：辅助函数 - 调用AE脚本的标准封装
// ============================================================================

/**
 * 调用AE Bridge执行指定脚本并等待结果
 * @param server McpServer 实例（用于访问内部函数）
 * @param scriptName 脚本名（必须在 allowedScripts 中）
 * @param parameters 传递给脚本的参数对象
 * @returns Promise<string> AE 返回的 JSON 字符串
 */
async function callAEScript(
  scriptName: string,
  parameters: Record<string, any> = {}
): Promise<string> {
  // 注意：以下三个函数假定在外部作用域已定义
  // - clearResultsFile()
  // - writeCommandFile(command, args)
  // - waitForBridgeResult(expectedCommand, timeout, poll)
  // 通过 eval 或闭包访问，详见 install.ps1 的合并策略

  // @ts-ignore - 这三个函数在 index.ts 顶层定义
  clearResultsFile();
  // @ts-ignore
  writeCommandFile(scriptName, parameters);
  // @ts-ignore
  return await waitForBridgeResult(scriptName, 8000, 250);
}

/**
 * 解析 AE 返回的 JSON 字符串
 */
function parseAEResult(jsonStr: string): { success: boolean; data?: any; error?: string } {
  try {
    const parsed = JSON.parse(jsonStr);
    if (parsed.status === "success") {
      return { success: true, data: parsed };
    }
    return { success: false, error: parsed.message || parsed.error || "Unknown error" };
  } catch (e) {
    return { success: false, error: `JSON解析失败: ${String(e)}` };
  }
}

// ============================================================================
// 第三部分：25个新MCP工具注册函数
// ============================================================================

/**
 * 注册25个新MCP工具
 * 在 server 启动前调用此函数
 * @param server McpServer 实例
 */
export function registerNewTools(server: any) {

  // ---- 工具1: add-effect-with-keyframes ----
  server.tool(
    "add-effect-with-keyframes",
    "向指定图层添加效果并设置关键帧动画。一次性完成效果添加+参数设置+关键帧动画，避免多次调用。常用matchName: ADBE Gaussian Blur 2(高斯模糊)/ADBE Glo2(发光)/ADBE Curve(曲线)/ADBE Vibrance(自然饱和度)",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().positive().describe("目标图层索引（1-based）"),
      effectMatchName: z.string().describe("效果matchName，如 'ADBE Gaussian Blur 2'"),
      settings: z.record(z.string(), z.unknown()).optional().describe("效果初始参数 {propName: value}"),
      keyframes: z.array(z.object({
        propertyName: z.string().describe("效果内属性名，如 'Blurriness'"),
        time: z.number().describe("关键帧时间（秒）"),
        value: z.union([z.number(), z.array(z.number())]).describe("关键帧值"),
        easingType: z.enum(["linear", "easeIn", "easeOut", "easeInOut", "bezier"]).optional().default("linear")
      })).optional().describe("关键帧列表")
    },
    async ({ compName, layerIndex, effectMatchName, settings, keyframes }) => {
      try {
        const result = await callAEScript("addEffectWithKeyframes", {
          compName, layerIndex, effectMatchName, settings: settings || {}, keyframes: keyframes || []
        });
        const parsed = parseAEResult(result);
        return {
          content: [{ type: "text", text: result }],
          isError: !parsed.success
        };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具2: set-keyframe-easing ----
  server.tool(
    "set-keyframe-easing",
    "设置指定关键帧的缓动曲线。支持linear/easeIn/easeOut/easeInOut/bezier/hold六种缓动。bezier类型可指定speed和influence控制曲线形状。常用：easeInOut(speed=0,influence=90)产生平滑缓动",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().positive().describe("目标图层索引"),
      propertyPath: z.string().describe("属性路径，如 'transform.position' 或 'effect(\"Gaussian Blur\")(1)'"),
      keyIndex: z.number().int().positive().describe("关键帧索引（1-based）"),
      easingType: z.enum(["linear", "easeIn", "easeOut", "easeInOut", "bezier", "hold"]).describe("缓动类型"),
      easeIn: z.object({
        speed: z.number().default(0),
        influence: z.number().default(33)
      }).optional().describe("入缓动参数（贝塞尔控制点）"),
      easeOut: z.object({
        speed: z.number().default(0),
        influence: z.number().default(33)
      }).optional().describe("出缓动参数")
    },
    async ({ compName, layerIndex, propertyPath, keyIndex, easingType, easeIn, easeOut }) => {
      try {
        const result = await callAEScript("setKeyframeEasing", {
          compName, layerIndex, propertyPath, keyIndex, easingType,
          easeIn: easeIn || { speed: 0, influence: 33 },
          easeOut: easeOut || { speed: 0, influence: 33 }
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具3: batch-add-effects ----
  server.tool(
    "batch-add-effects",
    "批量向指定图层添加多个效果。适用于需要叠加多个效果的风格化操作，如同时添加模糊+发光+调色。比逐个调用更高效，所有效果在一个undo组中",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().positive().describe("目标图层索引"),
      effects: z.array(z.object({
        effectMatchName: z.string().describe("效果matchName"),
        settings: z.record(z.string(), z.unknown()).optional().describe("效果参数")
      })).min(1).describe("要添加的效果列表")
    },
    async ({ compName, layerIndex, effects }) => {
      try {
        const result = await callAEScript("batchAddEffects", { compName, layerIndex, effects });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具4: set-blend-mode ----
  server.tool(
    "set-blend-mode",
    "设置图层混合模式。常用模式：SCREEN(滤色/发光叠加)、MULTIPLY(正片叠底/暗部叠加)、ADD(相加/光效叠加)、OVERLAY(叠加/对比增强)、SOFT_LIGHT(柔光)、HARD_LIGHT(强光)",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().positive().describe("目标图层索引"),
      blendMode: z.enum([
        "NONE", "DISSOLVE", "MULTIPLY", "SCREEN", "OVERLAY", "SOFT_LIGHT", "HARD_LIGHT",
        "ADD", "COLOR_DODGE", "COLOR_BURN", "DARKEN", "LIGHTEN", "DIFFERENCE", "EXCLUSION",
        "HUE", "SATURATION", "COLOR", "LUMINOSITY"
      ]).describe("混合模式名称")
    },
    async ({ compName, layerIndex, blendMode }) => {
      try {
        const result = await callAEScript("setBlendMode", { compName, layerIndex, blendMode });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具5: set-track-matte ----
  server.tool(
    "set-track-matte",
    "设置图层轨道遮罩类型。ALPHA(Alpha遮罩用上层Alpha通道)、LUMA(亮度遮罩用上层亮度值)、INVERTED(反转)。遮罩层需在目标图层上方",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().positive().describe("目标图层索引"),
      matteType: z.enum([
        "NO_TRACK_MATTE", "ALPHA_TRACK_MATTE", "ALPHA_INVERTED_TRACK_MATTE",
        "LUMA_TRACK_MATTE", "LUMA_INVERTED_TRACK_MATTE"
      ]).describe("遮罩类型")
    },
    async ({ compName, layerIndex, matteType }) => {
      try {
        const result = await callAEScript("setTrackMatte", { compName, layerIndex, matteType });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具6: set-parent-layer ----
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
        const result = await callAEScript("setParentLayer", { compName, layerIndex, parentIndex });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具7: add-adjustment-layer ----
  server.tool(
    "add-adjustment-layer",
    "创建调整图层。调整图层本身不渲染，但会对其下方所有图层应用效果。常用于全局调色、全局模糊、深度合成等",
    {
      compName: z.string().describe("目标合成名称"),
      name: z.string().optional().default("Adjustment Layer").describe("调整图层名称"),
      position: z.number().int().min(0).optional().default(1).describe("插入位置索引，0表示最上方")
    },
    async ({ compName, name, position }) => {
      try {
        const result = await callAEScript("addAdjustmentLayer", { compName, name, position });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具8: add-precomp ----
  server.tool(
    "add-precomp",
    "将指定图层预合成为新的合成。预合成可简化时间轴、嵌套效果、实现复杂层级结构。moveAllAttributes=true将所有关键帧和属性移入新合成",
    {
      compName: z.string().describe("源合成名称"),
      name: z.string().describe("新预合成名称"),
      layerIndices: z.array(z.number().int().positive()).min(1).describe("要预合成的图层索引列表"),
      moveAllAttributes: z.boolean().optional().default(true).describe("是否将所有属性移入新合成")
    },
    async ({ compName, name, layerIndices, moveAllAttributes }) => {
      try {
        const result = await callAEScript("addPrecomp", { compName, name, layerIndices, moveAllAttributes });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具9: import-footage ----
  server.tool(
    "import-footage",
    "导入素材文件到AE项目。支持图片、视频、音频、序列。可指定目标合成自动添加。常用格式：.png/.jpg/.mp4/.mov/.wav/.ai/.psd",
    {
      filePath: z.string().describe("素材文件的绝对路径"),
      compName: z.string().optional().describe("目标合成名称（不填则仅导入项目）"),
      asSequence: z.boolean().optional().default(false).describe("是否作为序列导入"),
      position: z.number().int().optional().describe("在合成中的插入位置索引")
    },
    async ({ filePath, compName, asSequence, position }) => {
      try {
        const result = await callAEScript("importFootage", { filePath, compName, asSequence, position });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具10: set-motion-blur ----
  server.tool(
    "set-motion-blur",
    "设置运动模糊。快门角度180°为标准电影感，360°为强烈拖尾，720°为极限拖尾。需同时启用合成和图层的运动模糊开关",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().optional().describe("图层索引，0或省略表示仅设置合成级别"),
      enabled: z.boolean().describe("是否启用运动模糊"),
      shutterAngle: z.number().min(0).max(720).optional().describe("快门角度（0-720），默认180"),
      shutterPhase: z.number().min(-360).max(360).optional().describe("快门相位（-360到360）")
    },
    async ({ compName, layerIndex, enabled, shutterAngle, shutterPhase }) => {
      try {
        const result = await callAEScript("setMotionBlur", {
          compName, layerIndex: layerIndex || 0, enabled, shutterAngle, shutterPhase
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具11: add-mask-with-shape ----
  server.tool(
    "add-mask-with-shape",
    "向图层添加自定义形状遮罩。支持贝塞尔曲线顶点、羽化、模式设置。常用于区域限制效果范围、创建复杂形状",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().positive().describe("目标图层索引"),
      vertices: z.array(z.object({
        x: z.number().describe("顶点X坐标"),
        y: z.number().describe("顶点Y坐标"),
        inTangent: z.array(z.number()).optional().describe("入贝塞尔控制点 [x,y]"),
        outTangent: z.array(z.number()).optional().describe("出贝塞尔控制点 [x,y]")
      })).min(3).describe("遮罩顶点坐标数组"),
      feather: z.array(z.number()).length(2).optional().default([0, 0]).describe("遮罩羽化 [水平, 垂直]"),
      mode: z.enum(["add", "subtract", "intersect", "difference", "lighten", "darken", "none"]).optional().default("add").describe("遮罩模式"),
      opacity: z.number().min(0).max(100).optional().default(100).describe("遮罩不透明度"),
      expansion: z.number().optional().default(0).describe("遮罩扩展"),
      inverted: z.boolean().optional().default(false).describe("是否反转遮罩")
    },
    async ({ compName, layerIndex, vertices, feather, mode, opacity, expansion, inverted }) => {
      try {
        const result = await callAEScript("addMaskWithShape", {
          compName, layerIndex, vertices,
          feather: feather || [0, 0],
          mode: mode || "add",
          opacity: opacity || 100,
          expansion: expansion || 0,
          inverted: inverted || false
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具12: execute-atom-script ----
  server.tool(
    "execute-atom-script",
    "执行原子参数编译器生成的ExtendScript脚本。这是知识编译器→AE执行的直接通道，支持干运行验证。dryRun=true仅检查语法不执行",
    {
      scriptContent: z.string().describe("编译器生成的ExtendScript代码"),
      scriptName: z.string().optional().default("atom-script").describe("脚本名称（用于日志和调试）"),
      timeout: z.number().optional().default(10000).describe("执行超时时间（毫秒）"),
      dryRun: z.boolean().optional().default(false).describe("干运行模式，仅验证语法不执行")
    },
    async ({ scriptContent, scriptName, timeout, dryRun }) => {
      try {
        const result = await callAEScript("executeAtomScript", {
          scriptContent, scriptName, timeout: timeout || 10000, dryRun: dryRun || false
        });
        // executeAtomScript的Bridge超时可能需要更长时间
        // 因为编译器输出的脚本可能包含大量操作
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具13: get-effect-properties ----
  server.tool(
    "get-effect-properties",
    "获取图层上指定效果的所有属性及当前值。用于验证效果参数、读取当前状态、检查关键帧。返回的属性列表包含name/matchName/value/hasKeyframes/keyframeCount",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().positive().describe("目标图层索引"),
      effectIndex: z.number().int().positive().describe("效果索引（1-based）")
    },
    async ({ compName, layerIndex, effectIndex }) => {
      try {
        const result = await callAEScript("getEffectProperties", { compName, layerIndex, effectIndex });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具14: set-effect-keyframes ----
  server.tool(
    "set-effect-keyframes",
    "为已有效果的属性批量设置关键帧。与add-effect-with-keyframes不同，此工具用于已存在效果的动画设置。每个关键帧可单独设置缓动类型",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().positive().describe("目标图层索引"),
      effectIndex: z.number().int().positive().describe("效果索引（1-based）"),
      propName: z.string().describe("效果内的属性名，如 'Blurriness'"),
      keyframes: z.array(z.object({
        time: z.number().describe("关键帧时间（秒）"),
        value: z.union([z.number(), z.array(z.number())]).describe("关键帧值"),
        easingType: z.enum(["linear", "easeIn", "easeOut", "easeInOut", "hold"]).optional().default("linear")
      })).min(1).describe("关键帧列表")
    },
    async ({ compName, layerIndex, effectIndex, propName, keyframes }) => {
      try {
        const result = await callAEScript("setEffectKeyframes", {
          compName, layerIndex, effectIndex, propName, keyframes
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具15: create-e2e-music-video ----
  server.tool(
    "create-e2e-music-video",
    "一键创建完整音乐视频合成。包含帧序列导入、主体/披风层处理、粒子系统、背景大气、调色、摄像机节拍同步、BGM导入等全部步骤。需要先在AE中运行ae_mcp_listener.jsx监听，然后调用此工具。使用AE内置效果(ADBE Color Key/ADBE Glo2/ADBE Ramp)确保兼容性",
    {
      compName: z.string().optional().default("E2E_音乐视频").describe("合成名称"),
      // 参数化：移除硬编码默认值，frameDir 改为必填（原 .default("D:/AE-Work/视频素材库/frames")）
      frameDir: z.string().describe("帧序列目录（必填，绝对路径）"),
      bgmPath: z.string().optional().describe("背景音乐文件路径"),
      beatTimes: z.array(z.number()).optional().describe("节拍时间点数组（秒）"),
      energyPeaks: z.array(z.number()).optional().describe("能量峰值时间点数组（秒）"),
      peakValues: z.array(z.number()).optional().describe("能量峰值强度数组"),
      bpm: z.number().optional().default(0).describe("音乐BPM"),
      width: z.number().int().positive().optional().default(576).describe("合成宽度"),
      height: z.number().int().positive().optional().default(768).describe("合成高度"),
      duration: z.number().positive().optional().default(12).describe("合成时长（秒）"),
      fps: z.number().int().positive().optional().default(30).describe("帧率")
    },
    async ({ compName, frameDir, bgmPath, beatTimes, energyPeaks, peakValues, bpm, width, height, duration, fps }) => {
      try {
        const result = await callAEScript("createE2EMusicVideo", {
          compName: compName || "E2E_音乐视频",
          // 参数化：frameDir 必填（schema 已校验），移除原 fallback "D:/AE-Work/视频素材库/frames"
          frameDir: frameDir,
          bgmPath: bgmPath || "",
          beatTimes: beatTimes || [],
          energyPeaks: energyPeaks || [],
          peakValues: peakValues || [],
          bpm: bpm || 0,
          width: width || 576,
          height: height || 768,
          duration: duration || 12,
          fps: fps || 30
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具16: apply-newton-dynamics ----
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
        const result = await callAEScript("applyNewtonDynamics", {
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
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具17: add-text-layer ----
  server.tool(
    "add-text-layer",
    "在合成中创建文字图层。支持字体、字号、颜色、对齐方式、位置等参数。常用场景：标题、字幕、说明文字、动态排版。fillColor为RGB三通道数组（0-1范围）",
    {
      compName: z.string().describe("目标合成名称"),
      text: z.string().describe("文字内容"),
      name: z.string().optional().describe("图层名称（不填则使用文字内容）"),
      fontSize: z.number().positive().optional().default(72).describe("字号，默认72"),
      fontFamily: z.string().optional().default("Arial").describe("字体名称，如 'Arial'、'Microsoft YaHei'"),
      fillColor: z.array(z.number()).length(3).optional().default([1, 1, 1]).describe("文字颜色 [R,G,B] 0-1范围"),
      justification: z.enum(["left", "center", "right"]).optional().default("center").describe("对齐方式"),
      position: z.array(z.number()).length(2).optional().describe("图层位置 [x,y]，默认合成中心")
    },
    async ({ compName, text, name, fontSize, fontFamily, fillColor, justification, position }) => {
      try {
        const result = await callAEScript("addTextLayer", {
          compName, text, name,
          fontSize: fontSize || 72,
          fontFamily: fontFamily || "Arial",
          fillColor: fillColor || [1, 1, 1],
          justification: justification || "center",
          position: position || null
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具18: add-shape-layer ----
  server.tool(
    "add-shape-layer",
    "创建带路径的形状图层。支持rectangle(矩形)/ellipse(椭圆)/star(星形)/polygon(多边形)四种形状。可设置填充、描边、位置、尺寸。常用于背景元素、UI图形、动画路径",
    {
      compName: z.string().describe("目标合成名称"),
      shapeType: z.enum(["rectangle", "ellipse", "star", "polygon"]).describe("形状类型"),
      name: z.string().optional().describe("图层名称"),
      position: z.array(z.number()).length(2).optional().describe("图层位置 [x,y]，默认合成中心"),
      size: z.array(z.number()).length(2).optional().describe("形状尺寸 [width,height]，默认合成尺寸的50%"),
      fillColor: z.array(z.number()).length(3).optional().default([1, 1, 1]).describe("填充颜色 [R,G,B] 0-1范围"),
      strokeColor: z.array(z.number()).length(3).optional().default([0, 0, 0]).describe("描边颜色 [R,G,B] 0-1范围"),
      strokeWidth: z.number().min(0).optional().default(0).describe("描边宽度，0表示无描边")
    },
    async ({ compName, shapeType, name, position, size, fillColor, strokeColor, strokeWidth }) => {
      try {
        const result = await callAEScript("addShapeLayer", {
          compName, shapeType, name,
          position: position || null,
          size: size || null,
          fillColor: fillColor || [1, 1, 1],
          strokeColor: strokeColor || [0, 0, 0],
          strokeWidth: strokeWidth !== undefined ? strokeWidth : 0
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具19: add-camera ----
  server.tool(
    "add-camera",
    "在合成中创建摄像机图层。one_node=单节点（无兴趣点，方向跟随位置），two_node=双节点（独立的兴趣点控制朝向）。focalLength单位为mm，35mm为标准视角，50mm为人眼视角，24mm为广角",
    {
      compName: z.string().describe("目标合成名称"),
      name: z.string().optional().default("Camera").describe("摄像机名称"),
      cameraType: z.enum(["one_node", "two_node"]).optional().default("one_node").describe("摄像机类型"),
      focalLength: z.number().positive().optional().default(35).describe("焦距（mm），35=标准，24=广角，85=长焦"),
      position: z.array(z.number()).length(3).optional().describe("摄像机位置 [x,y,z]，默认合成中心前方-1000"),
      pointOfInterest: z.array(z.number()).length(3).optional().describe("兴趣点 [x,y,z]，默认合成中心")
    },
    async ({ compName, name, cameraType, focalLength, position, pointOfInterest }) => {
      try {
        const result = await callAEScript("addCamera", {
          compName,
          name: name || "Camera",
          cameraType: cameraType || "one_node",
          focalLength: focalLength || 35,
          position: position || null,
          pointOfInterest: pointOfInterest || null
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具20: add-light ----
  server.tool(
    "add-light",
    "在合成中创建灯光图层。parallel=平行光（模拟太阳光）、spot=聚光灯（锥形范围）、point=点光源（全向照射）、ambient=环境光（全局填充）。需启用合成3D开关才能生效",
    {
      compName: z.string().describe("目标合成名称"),
      name: z.string().optional().default("Light").describe("灯光名称"),
      lightType: z.enum(["parallel", "spot", "point", "ambient"]).optional().default("point").describe("灯光类型"),
      color: z.array(z.number()).length(3).optional().default([1, 1, 1]).describe("灯光颜色 [R,G,B] 0-1范围"),
      intensity: z.number().min(0).optional().default(100).describe("灯光强度，默认100"),
      position: z.array(z.number()).length(3).optional().describe("灯光位置 [x,y,z]"),
      pointOfInterest: z.array(z.number()).length(3).optional().describe("兴趣点 [x,y,z]（仅parallel/spot有效）")
    },
    async ({ compName, name, lightType, color, intensity, position, pointOfInterest }) => {
      try {
        const result = await callAEScript("addLight", {
          compName,
          name: name || "Light",
          lightType: lightType || "point",
          color: color || [1, 1, 1],
          intensity: intensity !== undefined ? intensity : 100,
          position: position || null,
          pointOfInterest: pointOfInterest || null
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具21: apply-lut ----
  server.tool(
    "apply-lut",
    "对图层应用LUT（通过Lumetri Color效果）。支持.cube/.3dl等标准LUT格式。intensity<100时通过效果不透明度近似实现混合。常用场景：电影调色、风格化预设、相机匹配",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().positive().describe("目标图层索引（1-based）"),
      lutPath: z.string().describe("LUT文件的绝对路径（.cube/.3dl）"),
      intensity: z.number().min(0).max(100).optional().default(100).describe("应用强度0-100，100=完全应用")
    },
    async ({ compName, layerIndex, lutPath, intensity }) => {
      try {
        const result = await callAEScript("applyLUT", {
          compName, layerIndex, lutPath,
          intensity: intensity !== undefined ? intensity : 100
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具22: enable-time-remap ----
  server.tool(
    "enable-time-remap",
    "启用/禁用图层的时间重映射，并可设置关键帧。时间重映射允许对图层播放速度进行精确控制（变速、倒放、冻结）。keyframes数组每个元素是{time, value}对，value为该时间点映射到的源时间",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().positive().describe("目标图层索引（1-based）"),
      enabled: z.boolean().optional().default(true).describe("是否启用时间重映射，false=禁用"),
      keyframes: z.array(z.object({
        time: z.number().describe("关键帧时间（秒）"),
        value: z.number().describe("映射到的源时间（秒）")
      })).optional().describe("时间重映射关键帧列表，用于变速/倒放/冻结")
    },
    async ({ compName, layerIndex, enabled, keyframes }) => {
      try {
        const result = await callAEScript("enableTimeRemap", {
          compName, layerIndex,
          enabled: enabled !== false,
          keyframes: keyframes || null
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具23: apply-saber ----
  server.tool(
    "apply-saber",
    "为图层应用Video Copilot Saber效果（VC Saber）。常用于光剑、激光、能量光束、霓虹描边等效果。settings中的常用参数：Core Type(0=Text 1=Layer 2=Solid Mask 3=Path)、Core Size、Core Color、Glow Intensity、Glow Width、Glow Color",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().positive().describe("目标图层索引（1-based）"),
      settings: z.record(z.string(), z.unknown()).optional().describe("Saber效果参数 {propName: value}，如 {\"Core Size\": 5, \"Glow Intensity\": 100, \"Core Color\": [1, 0, 0, 1]}")
    },
    async ({ compName, layerIndex, settings }) => {
      try {
        const result = await callAEScript("applySaber", {
          compName, layerIndex,
          settings: settings || {}
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具24: apply-particular ----
  server.tool(
    "apply-particular",
    "为图层应用Trapcode Particular效果（ACP Particular）。强大的3D粒子系统，用于烟雾、火焰、雨雪、星光、爆炸等效果。settings常用参数：Particles/sec(发射速率)、Velocity(初速度)、Life(寿命)、Size(粒子大小)、Color(颜色)、Emitter X/Y/Z(发射器位置)",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().positive().describe("目标图层索引（1-based）"),
      settings: z.record(z.string(), z.unknown()).optional().describe("Particular效果参数 {propName: value}，如 {\"Particles/sec\": 200, \"Velocity\": 100, \"Size\": 5, \"Color\": [1, 0.8, 0.3, 1]}")
    },
    async ({ compName, layerIndex, settings }) => {
      try {
        const result = await callAEScript("applyParticular", {
          compName, layerIndex,
          settings: settings || {}
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );

  // ---- 工具25: apply-optical-flares ----
  server.tool(
    "apply-optical-flares",
    "为图层应用Video Copilot Optical Flares效果（VC Optical Flares）。专业镜头光晕插件，用于镜头光斑、能量光球、特效发光等。settings常用参数：Brightness(亮度)、Scale(缩放)、Position XY(位置)、Tint Color(染色)",
    {
      compName: z.string().describe("目标合成名称"),
      layerIndex: z.number().int().positive().describe("目标图层索引（1-based）"),
      settings: z.record(z.string(), z.unknown()).optional().describe("Optical Flares效果参数 {propName: value}，如 {\"Brightness\": 100, \"Scale\": 1.5, \"Position XY\": [960, 540]}")
    },
    async ({ compName, layerIndex, settings }) => {
      try {
        const result = await callAEScript("applyOpticalFlares", {
          compName, layerIndex,
          settings: settings || {}
        });
        const parsed = parseAEResult(result);
        return { content: [{ type: "text", text: result }], isError: !parsed.success };
      } catch (e) {
        return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
      }
    }
  );
}
