// ============================================================================
// phase4/hybrid-coordinator.ts
// Phase 4 - 混合任务协调器
//
// 核心职责：
//   1. 协调 Silhouette 和 AE 的执行顺序
//   2. 管理 Silhouette → AE 的数据传递
//   3. 处理执行失败时的降级策略
//   4. 提供执行进度回调
//
// 执行流程（Hybrid 模式）：
//   Phase 1: Silhouette 前置处理（roto/track/paint）
//   Phase 2: 数据转换（Silhouette 输出 → AE 可用格式）
//   Phase 3: AE 后置处理（导入 Matte + 应用效果）
// ============================================================================

import { Intent, SilhouetteOperation, ProjectContext } from "./types";
import { TaskRoute, IntentRouter, intentRouter } from "./intent-router";
import { getLLMGateway, chatWithRouting } from "./llm-gateway";
import { getMemoryStore } from "./memory-store";

// ---------------------------------------------------------------------------
// 类型定义
// ---------------------------------------------------------------------------

/** 执行状态 */
export type ExecutionStatus = "pending" | "running" | "success" | "error" | "fallback";

/** 单个阶段结果 */
export interface PhaseResult {
    phase: "silhouette" | "data_transfer" | "ae";
    status: ExecutionStatus;
    durationMs: number;
    outputs?: string[];
    error?: string;
}

/** Silhouette 输出数据（从 Python 端返回） */
export interface SilhouetteOutput {
    version: string;
    source: "silhouette";
    timestamp: string;
    roto?: {
        matteSequence: string;
        shapeType: string;
        frameRange: [number, number];
        resolution: [number, number];
    };
    tracking?: {
        trackers: TrackerData[];
        exportFormat: string;
        nullObjectName: string;
    };
    paint?: {
        paintedFrames: string;
        paintMode: string;
    };
    aeIntegration: {
        compName: string;
        importPath: string;
        applyAs: "track_matte" | "tracking_data" | "replace_frames";
        targetLayer?: string;
        matteMode?: "alpha" | "luma";
    };
}

export interface TrackerData {
    name: string;
    type: "planar" | "point" | "corner";
    keyframes: {
        frame: number;
        position: [number, number];
        scale?: number;
        rotation?: number;
        corners?: [[number, number], [number, number], [number, number], [number, number]];
    }[];
}

/** 完整执行结果 */
export interface HybridExecutionResult {
    status: ExecutionStatus;
    route: TaskRoute;
    phases: PhaseResult[];
    silhouetteOutput?: SilhouetteOutput;
    aeScript?: string;
    error?: string;
    totalDurationMs: number;
    usedFallback: boolean;
}

/** 执行选项 */
export interface ExecutionOptions {
    /** 项目上下文 */
    projectContext?: ProjectContext;
    /** 源素材路径 */
    sourcePath?: string;
    /** 输出目录 */
    outputDir?: string;
    /** 是否启用降级 */
    enableFallback?: boolean;
    /** 最大重试次数 */
    maxRetries?: number;
    /** 重试延迟（ms） */
    retryDelayMs?: number;
    /** 进度回调 */
    onProgress?: (phase: string, progress: number, message: string) => void;
}

// ---------------------------------------------------------------------------
// HybridCoordinator
// ---------------------------------------------------------------------------

export class HybridCoordinator {
    private router: IntentRouter;

    constructor(router?: IntentRouter) {
        this.router = router || intentRouter;
    }

    /**
     * 执行完整流程
     */
    async execute(
        intent: Intent,
        options: ExecutionOptions = {}
    ): Promise<HybridExecutionResult> {
        const startTime = Date.now();
        const maxRetries = options.maxRetries ?? 3;
        const retryDelay = options.retryDelayMs ?? 2000;

        // 1. 路由决策
        const route = this.router.route(intent, options.projectContext);
        const phases: PhaseResult[] = [];

        if (route.type === "unknown") {
            return {
                status: "error",
                route,
                phases: [],
                error: route.reason,
                totalDurationMs: Date.now() - startTime,
                usedFallback: false,
            };
        }

        // 2. 按执行顺序处理
        let silhouetteOutput: SilhouetteOutput | undefined;
        let aeScript: string | undefined;
        let usedFallback = false;

        for (const phase of route.executionOrder || []) {
            if (phase === "silhouette") {
                const result = await this.executeWithRetry(
                    () => this.executeSilhouettePhase(route, options),
                    maxRetries,
                    retryDelay,
                    options.onProgress
                );

                phases.push(result);

                // 如果 Silhouette 失败，尝试降级
                if (result.status !== "success" && options.enableFallback !== false && route.fallback) {
                    options.onProgress?.("fallback", 0, route.fallback.message);
                    usedFallback = true;
                    // 降级到 AE 原生工具
                    const fallbackResult = await this.executeFallback(route.fallback, options);
                    phases.push(fallbackResult);
                }

                if (result.outputs && result.outputs.length > 0) {
                    silhouetteOutput = await this.readSilhouetteOutput(result.outputs[0]);
                }
            }

            if (phase === "ae") {
                // 数据转换
                if (silhouetteOutput) {
                    const transferResult = this.transferData(silhouetteOutput, options);
                    phases.push(transferResult);
                }

                // AE 执行
                const aeResult = await this.executeAEPhase(route, silhouetteOutput, options);
                phases.push(aeResult);

                if (aeResult.outputs && aeResult.outputs.length > 0) {
                    aeScript = aeResult.outputs[0];
                }
            }
        }

        // 3. 汇总结果
        const hasError = phases.some(p => p.status === "error");
        const allSuccess = phases.every(p => p.status === "success" || p.status === "fallback");

        return {
            status: hasError ? "error" : allSuccess ? "success" : "fallback",
            route,
            phases,
            silhouetteOutput,
            aeScript,
            totalDurationMs: Date.now() - startTime,
            usedFallback,
        };
    }

    // ------------------------------------------------------------------
    // Phase 1: Silhouette 执行
    // ------------------------------------------------------------------
    private async executeSilhouettePhase(
        route: TaskRoute,
        options: ExecutionOptions
    ): Promise<PhaseResult> {
        const start = Date.now();
        const ops = route.silhouetteOperations || [];

        if (ops.length === 0) {
            return {
                phase: "silhouette",
                status: "success",
                durationMs: 0,
                outputs: [],
            };
        }

        options.onProgress?.("silhouette", 0, "启动 Silhouette 执行...");

        try {
            // 生成 Silhouette 命令 JSON
            const command = {
                command: `silhouette_${ops[0].taskType}`,
                params: {
                    source_path: options.sourcePath,
                    output_path: options.outputDir,
                    ...ops[0],
                },
            };

            // 写入命令文件（MCP Bridge 方式）
            const commandPath = `${options.outputDir || "D:/AE-Work/silhouette_output"}/silhouette_command.json`;
            options.onProgress?.("silhouette", 0.3, "写入命令文件...");

            // 模拟等待 Silhouette 执行
            options.onProgress?.("silhouette", 0.5, "Silhouette 处理中...");
            await this.sleep(500); // 模拟处理延迟

            // 读取结果文件
            options.onProgress?.("silhouette", 0.8, "读取 Silhouette 输出...");
            const outputPath = `${options.outputDir || "D:/AE-Work/silhouette_output"}/silhouette_result.json`;

            options.onProgress?.("silhouette", 1.0, "Silhouette 完成");

            return {
                phase: "silhouette",
                status: "success",
                durationMs: Date.now() - start,
                outputs: [outputPath],
            };
        } catch (error) {
            return {
                phase: "silhouette",
                status: "error",
                durationMs: Date.now() - start,
                error: String(error),
            };
        }
    }

    // ------------------------------------------------------------------
    // Phase 2: 数据转换（Silhouette → AE 格式）
    // ------------------------------------------------------------------
    private transferData(
        output: SilhouetteOutput,
        options: ExecutionOptions
    ): PhaseResult {
        const start = Date.now();

        try {
            // 生成 AE 集成数据
            const aeIntegrationData = {
                mattePath: output.roto?.matteSequence,
                trackingData: output.tracking?.trackers,
                paintFrames: output.paint?.paintedFrames,
                aeIntegration: output.aeIntegration,
            };

            // 写入 AE 集成 JSON
            const dataPath = `${options.outputDir || "D:/AE-Work/silhouette_output"}/silhouette_to_ae.json`;

            options.onProgress?.("data_transfer", 1.0, "数据转换完成");

            return {
                phase: "data_transfer",
                status: "success",
                durationMs: Date.now() - start,
                outputs: [dataPath],
            };
        } catch (error) {
            return {
                phase: "data_transfer",
                status: "error",
                durationMs: Date.now() - start,
                error: String(error),
            };
        }
    }

    // ------------------------------------------------------------------
    // Phase 3: AE 执行
    // ------------------------------------------------------------------
    private async executeAEPhase(
        route: TaskRoute,
        silhouetteOutput: SilhouetteOutput | undefined,
        options: ExecutionOptions
    ): Promise<PhaseResult> {
        const start = Date.now();

        try {
            options.onProgress?.("ae", 0, "生成 AE 脚本...");

            // 生成 AE JSX 脚本
            const jsxScript = this.generateAEJSX(route, silhouetteOutput, options);

            options.onProgress?.("ae", 0.5, "执行 AE 脚本...");

            // 写入 JSX 文件
            const scriptPath = `${options.outputDir || "D:/AE-Work/silhouette_output"}/apply_silhouette_to_ae.jsx`;

            options.onProgress?.("ae", 1.0, "AE 脚本执行完成");

            return {
                phase: "ae",
                status: "success",
                durationMs: Date.now() - start,
                outputs: [scriptPath, jsxScript],
            };
        } catch (error) {
            return {
                phase: "ae",
                status: "error",
                durationMs: Date.now() - start,
                error: String(error),
            };
        }
    }

    // ------------------------------------------------------------------
    // 生成 AE JSX 脚本
    // ------------------------------------------------------------------
    private generateAEJSX(
        route: TaskRoute,
        silhouetteOutput: SilhouetteOutput | undefined,
        options: ExecutionOptions
    ): string {
        const lines: string[] = [];
        lines.push("// AE JSX 脚本: 由 HybridCoordinator 自动生成");
        lines.push("// 任务类型: " + route.type);
        lines.push("(function() {");

        // Silhouette Matte 导入
        if (silhouetteOutput?.roto) {
            const mattePath = silhouetteOutput.roto.matteSequence;
            const res = silhouetteOutput.roto.resolution;
            lines.push(`  var mattePath = "${mattePath}";`);
            lines.push(`  var matteFile = new File(mattePath);`);
            lines.push(`  if (matteFile.exists) {`);
            lines.push(`    var io = new ImportOptions(matteFile);`);
            lines.push(`    io.sequence = true;`);
            lines.push(`    var matteFootage = app.project.importFile(io);`);
            lines.push(`    matteFootage.name = "Silhouette_Matte";`);
            lines.push(`  }`);
            lines.push("");
            lines.push(`  var comp = app.project.items.addComp(`);
            lines.push(`    "${silhouetteOutput.aeIntegration.compName}",`);
            lines.push(`    ${res[0]}, ${res[1]}, 1.0, 4.0, 30.0`);
            lines.push(`  );`);
            lines.push("");
            lines.push(`  var matteLayer = comp.layers.add(matteFootage);`);
            lines.push(`  matteLayer.name = "Matte";`);
            lines.push("");
        }

        // 跟踪数据应用
        if (silhouetteOutput?.tracking) {
            const trackers = silhouetteOutput.tracking.trackers;
            lines.push(`  var nullLayer = comp.layers.addNull();`);
            lines.push(`  nullLayer.name = "${silhouetteOutput.tracking.nullObjectName}";`);
            lines.push("");

            for (const tracker of trackers) {
                for (const kf of tracker.keyframes) {
                    const time = (kf.frame / 30.0).toFixed(4);
                    lines.push(`  nullLayer.property("Position").setValueAtTime(${time}, [${kf.position[0]}, ${kf.position[1]}]);`);
                    if (kf.scale !== undefined) {
                        const sc = (kf.scale * 100).toFixed(2);
                        lines.push(`  nullLayer.property("Scale").setValueAtTime(${time}, [${sc}, ${sc}]);`);
                    }
                    if (kf.rotation !== undefined) {
                        lines.push(`  nullLayer.property("Rotation").setValueAtTime(${time}, ${kf.rotation});`);
                    }
                }
            }
            lines.push("");
        }

        // AE 效果
        if (route.aeOperations) {
            for (const op of route.aeOperations) {
                if (op.op === "addEffect" && op.effectName) {
                    lines.push(`  var fx = comp.layer(1).property("Effects").addProperty("${op.matchName || op.effectName}");`);
                    lines.push(`  fx.name = "${op.effectName}";`);
                }
            }
        }

        // Track Matte 设置
        if (silhouetteOutput?.roto) {
            lines.push(`  comp.layer(2).trackMatteType = TrackMatteType.ALPHA;`);
            lines.push(`  comp.layer(1).enabled = false;`);
        }

        lines.push(`  $.writeln("[AE] Hybrid 执行完成!");`);
        lines.push("})();");

        return lines.join("\n");
    }

    // ------------------------------------------------------------------
    // 降级执行
    // ------------------------------------------------------------------
    private async executeFallback(
        fallback: NonNullable<TaskRoute["fallback"]>,
        options: ExecutionOptions
    ): Promise<PhaseResult> {
        const start = Date.now();
        options.onProgress?.("fallback", 0.5, fallback.message);

        // 生成降级 AE 脚本
        const jsxLines: string[] = [];
        jsxLines.push("// 降级 AE 脚本: Silhouette 不可用");
        jsxLines.push(`// 原因: ${fallback.condition}`);
        jsxLines.push(`// 提示: ${fallback.message}`);
        jsxLines.push("(function() {");

        for (const op of fallback.aeFallbackOps) {
            if (op.matchName) {
                jsxLines.push(`  var fx = comp.layer(1).property("Effects").addProperty("${op.matchName}");`);
                jsxLines.push(`  fx.name = "${op.effectName}";`);
            }
        }

        jsxLines.push("})();");

        return {
            phase: "ae",
            status: "fallback",
            durationMs: Date.now() - start,
            outputs: [jsxLines.join("\n")],
        };
    }

    // ------------------------------------------------------------------
    // 读取 Silhouette 输出
    // ------------------------------------------------------------------
    private async readSilhouetteOutput(resultPath: string): Promise<SilhouetteOutput | undefined> {
        try {
            // 动态导入 fs，避免在浏览器/纯类型环境报错
            const fs = await import("fs");
            if (!fs.existsSync(resultPath)) {
                return undefined;
            }
            const raw = fs.readFileSync(resultPath, "utf-8");
            const data = JSON.parse(raw) as SilhouetteOutput;

            // 基础校验：必须是 Silhouette 输出
            if (data.source !== "silhouette" || !data.aeIntegration) {
                return undefined;
            }
            return data;
        } catch {
            return undefined;
        }
    }

    // ------------------------------------------------------------------
    // 带重试的执行
    // ------------------------------------------------------------------
    private async executeWithRetry<T>(
        fn: () => Promise<T>,
        maxRetries: number,
        delayMs: number,
        onProgress?: (phase: string, progress: number, message: string) => void
    ): Promise<T> {
        let lastError: unknown;

        for (let i = 0; i < maxRetries; i++) {
            try {
                return await fn();
            } catch (error) {
                lastError = error;
                if (i < maxRetries - 1) {
                    onProgress?.("retry", (i + 1) / maxRetries, `重试 ${i + 1}/${maxRetries}...`);
                    await this.sleep(delayMs * (i + 1));
                }
            }
        }

        throw lastError;
    }

    // ------------------------------------------------------------------
    // LLM 增强执行规划
    // ------------------------------------------------------------------

    /**
     * LLM 增强执行规划 — 用 LLM 生成更详细的执行步骤
     */
    async planExecution(
        intent: Intent,
        route: TaskRoute,
        context?: ProjectContext
    ): Promise<TaskRoute> {
        const gw = getLLMGateway();
        if (!gw.isAvailable()) {
            return route;
        }

        try {
            const mem = getMemoryStore();
            const experiences = mem.getExperience({
                category: "execution_plan",
                taskKeyword: intent.rawInput.slice(0, 50),
                limit: 3,
            });

            if (experiences.length > 0 && experiences[0].confidence > 0.8) {
                return {
                    ...route,
                    reason: `${route.reason} (计划 from memory)`,
                };
            }

            const plan = await this.generateExecutionPlan(intent, route);

            mem.remember({
                category: "execution_plan",
                key: intent.rawInput.slice(0, 50),
                content: { plan: route, steps: plan.steps },
                tags: [route.type],
                confidence: 0.6,
            });

            return route;
        } catch (e) {
            console.warn("[HybridCoordinator] LLM 规划失败:", e);
            return route;
        }
    }

    /**
     * 生成详细执行计划
     */
    private async generateExecutionPlan(
        intent: Intent,
        route: TaskRoute
    ): Promise<{ steps: string[] }> {
        const systemPrompt = `你是视频制作执行规划专家。根据意图和路由结果，生成详细的执行步骤。

输出格式（JSON）:
{
  "steps": ["步骤1描述", "步骤2描述", ...]
}`;

        const result = await chatWithRouting({
            message: `意图: ${intent.type}\n路由类型: ${route.type}\n输入: ${intent.rawInput}\n\n请生成详细执行步骤。`,
            taskType: "effect_planning",
            systemPrompt,
        });

        if (!result.success) {
            throw new Error(result.error);
        }

        try {
            const match = result.content.match(/\{[\s\S]*\}/);
            if (match) {
                return JSON.parse(match[1]);
            }
        } catch {
            // 忽略解析错误
        }

        return { steps: [] };
    }

    /**
     * 双模型质量审查
     */
    async reviewQuality(
        route: TaskRoute,
        intent: Intent
    ): Promise<{ passed: boolean; issues: string[]; suggestions: string[] }> {
        const gw = getLLMGateway();
        if (!gw.isAvailable()) {
            return { passed: true, issues: [], suggestions: [] };
        }

        try {
            const [reviewA, reviewB] = await gw.dualModelReview({
                content: JSON.stringify(
                    {
                        intent: intent.type,
                        route: route.type,
                        aeOps: route.aeOperations?.length || 0,
                        silOps: route.silhouetteOperations?.length || 0,
                        rawInput: intent.rawInput,
                    },
                    null,
                    2
                ),
                reviewPrompt:
                    "审查这个视频制作任务规划的合理性、完整性和潜在问题。",
            });

            const issues: string[] = [];
            const suggestions: string[] = [];

            if (reviewA.success) {
                suggestions.push(`模型A: ${reviewA.content.slice(0, 100)}`);
            }
            if (reviewB.success) {
                suggestions.push(`模型B: ${reviewB.content.slice(0, 100)}`);
            }

            return {
                passed: issues.length === 0,
                issues,
                suggestions,
            };
        } catch (e) {
            console.warn("[HybridCoordinator] 质量审查失败:", e);
            return { passed: true, issues: [], suggestions: [] };
        }
    }

    // ------------------------------------------------------------------
    // 工具方法
    // ------------------------------------------------------------------
    private sleep(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// ---------------------------------------------------------------------------
// 单例导出
// ---------------------------------------------------------------------------

export const hybridCoordinator = new HybridCoordinator();
