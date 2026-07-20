// ============================================================================
// phase3/index.ts
// Phase 3 - 决策树→编译器管线 入口
//
// 公开 API：
//   - reportToOps()      解析报告 → 编译器输入
//   - compileReportToScript()  解析报告 → 编译器输入 → ExtendScript代码
//   - analyzeReport()    分析解析报告统计信息
//   - findByName()       通过效果名查找matchName
//   - findByMatchName()  通过matchName查找效果
//   - EFFECT_MAP         完整的效果映射表
//
// 用法：
//   import { reportToOps, compileReportToScript } from "./phase3";
//   const compilerInput = reportToOps(report, options);
//   const result = compileReportToScript(report, options);
// ============================================================================

export {
    reportToOps,
    compileReportToScript,
    analyzeReport,
    ReportToOpsOptions,
    AnalysisReport,
    VisualFeature,
    EffectEntry,
    ParameterEntry,
    TimelineEntry,
    KeyframeEntry,
    KeyframeSpec,
    ReportStats
} from "./report-to-ops";

export {
    findByName,
    findByMatchName,
    getAllEffectNames,
    getByCategory,
    getStats,
    EffectMapEntry,
    EFFECT_MAP
} from "./effect-name-map";

// ============================================================================
// 便捷函数：从JSON字符串加载解析报告
// ============================================================================

import { AnalysisReport, ReportToOpsOptions } from "./report-to-ops";
import { reportToOps as _reportToOps } from "./report-to-ops";

/**
 * 从JSON字符串加载解析报告并转换为编译器输入
 *
 * @param reportJson 解析报告的JSON字符串
 * @param options 转换选项
 * @returns 编译器输入
 */
export function reportJsonToOps(
    reportJson: string,
    options?: ReportToOpsOptions
): { success: boolean; input?: any; error?: string } {
    try {
        const report = JSON.parse(reportJson) as AnalysisReport;
        const input = _reportToOps(report, options);
        return { success: true, input };
    } catch (e: any) {
        return {
            success: false,
            error: `Failed to parse report JSON: ${e?.message || String(e)}`
        };
    }
}

// ============================================================================
// 文档：完整调用链
// ============================================================================

/**
 * ## Phase 3 完整调用链
 *
 * ```
 * [视频] → [Phase 4 NLU] → [解析报告 JSON] → [Phase 3 转换] → [编译器输入 JSON] → [Phase 1 编译] → [ExtendScript 代码] → [Phase 2 MCP execute-atom-script] → [AE 执行]
 * ```
 *
 * ### 典型使用流程：
 *
 * ```typescript
 * import { reportToOps } from "./phase3";
 * import { compile } from "./index";
 *
 * // 1. 决策树输出的解析报告（来自 Phase 4 NLU 或手动编写）
 * const report = {
 *   metadata: { frame_rate: 30 },
 *   effects: [{ effect_id: "EI-001", effect_name: "Gaussian Blur", confidence: 0.85 }],
 *   parameters: [{ effect_id: "EI-001", parameter: "Blurriness", value: 25 }],
 *   keyframes: [{
 *     effect_id: "EI-001",
 *     parameter: "Blurriness",
 *     keyframes: [
 *       { frame: 60, value: 0, easing: "linear" },
 *       { frame: 100, value: 25, easing: "ease_out", bezier: [0, 0, 0.58, 1] },
 *       { frame: 150, value: 0, easing: "ease_in_out", bezier: [0.42, 0, 0.58, 1] }
 *     ]
 *   }]
 * };
 *
 * // 2. 转换为编译器输入
 * const compilerInput = reportToOps(report, { compName: "My Comp" });
 *
 * // 3. 编译为 ExtendScript
 * const result = compile(compilerInput);
 * if (result.success) {
 *   // 4. 通过 MCP execute-atom-script 工具执行
 *   // callMCP("execute-atom-script", { scriptContent: result.code });
 * }
 * ```
 */
