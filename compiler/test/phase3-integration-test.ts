// ============================================================================
// phase3-integration-test.ts
// Phase 3 端到端集成测试
//
// 测试完整管线：决策树解析报告 → 编译器输入 → ExtendScript代码 → MCP执行参数
//
// 运行：node build/phase3-integration-test.js
// ============================================================================

import { reportToOps, compileReportToScript, analyzeReport, AnalysisReport, getStats, findByName } from "../src/phase3";
import { compile } from "../src/index";

// ============================================================================
// 测试用例
// ============================================================================

const testCases: Array<{
    name: string;
    report: AnalysisReport;
    options?: any;
    expectSuccess: boolean;
    expectOps?: number;
}> = [
    // ---- 测试1: 单效果+参数 ----
    {
        name: "单效果+参数（Gaussian Blur）",
        report: {
            metadata: {
                video_file: "sample1.mp4",
                frame_rate: 30,
                resolution: "1920x1080"
            },
            effects: [{
                effect_id: "EI-001",
                effect_name: "Gaussian Blur",
                start_frame: 0,
                end_frame: 150,
                confidence: 0.85,
                evidence: ["均匀模糊扩散", "无方向性"]
            }],
            parameters: [{
                effect_id: "EI-001",
                parameter: "Blurriness",
                value: 25,
                value_range: [20, 30],
                confidence: 0.80
            }],
            timeline: [{
                effect_id: "EI-001",
                start_frame: 0,
                end_frame: 150,
                duration_frames: 150,
                duration_seconds: 5.0
            }],
            keyframes: []
        },
        expectSuccess: true,
        expectOps: 3 // createComp + addLayer + addEffect + setProperty = 4? 检查
    },

    // ---- 测试2: 单效果+关键帧动画 ----
    {
        name: "单效果+关键帧动画（Glow）",
        report: {
            metadata: {
                video_file: "sample2.mp4",
                frame_rate: 30
            },
            effects: [{
                effect_id: "EI-101",
                effect_name: "Glow",
                start_frame: 0,
                end_frame: 90,
                confidence: 0.90
            }],
            parameters: [{
                effect_id: "EI-101",
                parameter: "Glow Threshold",
                value: 50,
                value_range: [40, 60],
                confidence: 0.75
            }],
            keyframes: [{
                effect_id: "EI-101",
                parameter: "Glow Intensity",
                keyframes: [
                    { frame: 0, value: 0, easing: "linear" },
                    { frame: 30, value: 3, easing: "ease_out", bezier: [0, 0, 0.58, 1] },
                    { frame: 60, value: 5, easing: "ease_in_out", bezier: [0.42, 0, 0.58, 1] },
                    { frame: 90, value: 0, easing: "ease_in_out", bezier: [0.42, 0, 0.58, 1] }
                ],
                keyframe_count: 4
            }]
        },
        expectSuccess: true
    },

    // ---- 测试3: 多效果叠加 ----
    {
        name: "多效果叠加（Gaussian Blur + Glow + Vignette）",
        report: {
            metadata: { frame_rate: 30 },
            effects: [
                {
                    effect_id: "EI-001",
                    effect_name: "Gaussian Blur",
                    confidence: 0.85
                },
                {
                    effect_id: "EI-101",
                    effect_name: "Glow",
                    confidence: 0.80
                },
                {
                    effect_id: "EI-301",
                    effect_name: "Vignette",
                    confidence: 0.90
                }
            ],
            parameters: [
                { effect_id: "EI-001", parameter: "Blurriness", value: 15, confidence: 0.80 },
                { effect_id: "EI-101", parameter: "Glow Threshold", value: 50, confidence: 0.75 },
                { effect_id: "EI-101", parameter: "Glow Intensity", value: 2, confidence: 0.75 },
                { effect_id: "EI-301", parameter: "Amount", value: -65, confidence: 0.85 },
                { effect_id: "EI-301", parameter: "Softness", value: 50, confidence: 0.85 }
            ],
            keyframes: []
        },
        expectSuccess: true
    },

    // ---- 测试4: 置信度过滤 ----
    {
        name: "置信度过滤（minConfidence=0.85）",
        report: {
            metadata: { frame_rate: 30 },
            effects: [
                { effect_id: "EI-001", effect_name: "Gaussian Blur", confidence: 0.90 },
                { effect_id: "EI-101", effect_name: "Glow", confidence: 0.60 }  // 应被过滤
            ],
            parameters: [
                { effect_id: "EI-001", parameter: "Blurriness", value: 25, confidence: 0.85 },
                { effect_id: "EI-101", parameter: "Glow Threshold", value: 50, confidence: 0.50 } // 应被过滤
            ]
        },
        options: { minConfidence: 0.85 },
        expectSuccess: true
    },

    // ---- 测试5: 未知效果名（应跳过） ----
    {
        name: "未知效果名（应跳过+警告）",
        report: {
            metadata: { frame_rate: 30 },
            effects: [
                { effect_id: "EI-001", effect_name: "Gaussian Blur", confidence: 0.85 },
                { effect_id: "EI-999", effect_name: "不存在的效果XYZ", confidence: 0.99 }
            ],
            parameters: [
                { effect_id: "EI-001", parameter: "Blurriness", value: 25, confidence: 0.80 }
            ]
        },
        expectSuccess: true
    },

    // ---- 测试6: 多种缓动类型 ----
    {
        name: "多种缓动类型（linear/ease_in/hold/bezier）",
        report: {
            metadata: { frame_rate: 30 },
            effects: [{
                effect_id: "EI-001",
                effect_name: "Gaussian Blur",
                confidence: 0.90
            }],
            keyframes: [{
                effect_id: "EI-001",
                parameter: "Blurriness",
                keyframes: [
                    { frame: 0, value: 0, easing: "linear" },
                    { frame: 30, value: 15, easing: "ease_in" },
                    { frame: 60, value: 25, easing: "ease_in_out", bezier: [0.42, 0, 0.58, 1] },
                    { frame: 90, value: 25, easing: "hold" },
                    { frame: 120, value: 0, easing: "bezier", bezier: [0.25, 0.1, 0.25, 1] }
                ]
            }]
        },
        expectSuccess: true
    }
];

// ============================================================================
// 测试执行
// ============================================================================

function runTests(): void {
    console.log("========================================");
    console.log(" Phase 3 端到端集成测试");
    console.log(" 决策树解析报告 → 编译器输入 → ExtendScript");
    console.log("========================================\n");

    let passed = 0;
    let failed = 0;

    // 显示效果映射表统计
    const stats = getStats();
    console.log(`[信息] 效果映射表: ${stats.total}个效果`);
    console.log(`[信息] 分类分布: ${JSON.stringify(stats.byCategory)}`);
    console.log(`[信息] 来源分布: ${JSON.stringify(stats.bySource)}\n`);

    for (let i = 0; i < testCases.length; i++) {
        const tc = testCases[i];
        const testName = `测试${i + 1}: ${tc.name}`;

        console.log(`\n--- ${testName} ---`);

        try {
            // 1. 分析报告
            const reportStats = analyzeReport(tc.report);
            console.log(`  [分析] 效果数: ${reportStats.totalEffects}, 已映射: ${reportStats.mappedEffects}`);
            if (reportStats.unknownEffects.length > 0) {
                console.log(`  [分析] 未知效果: ${reportStats.unknownEffects.join(", ")}`);
            }
            console.log(`  [分析] 关键帧数: ${reportStats.totalKeyframes}`);
            console.log(`  [分析] 平均置信度: ${reportStats.avgConfidence.toFixed(2)}`);

            // 2. 转换为编译器输入
            const compilerInput = reportToOps(tc.report, tc.options || {});
            console.log(`  [转换] 生成操作数: ${compilerInput.operations.length}`);

            // 统计操作类型
            const opsByType: Record<string, number> = {};
            for (const op of compilerInput.operations) {
                opsByType[op.op] = (opsByType[op.op] || 0) + 1;
            }
            console.log(`  [转换] 操作类型分布: ${JSON.stringify(opsByType)}`);

            // 3. 调用 Phase 1 编译器
            const compileResult = compile(compilerInput);
            if (compileResult.success) {
                console.log(`  [编译] ✓ 成功`);
                console.log(`  [编译] 脚本大小: ${compileResult.script?.length || 0} 字符`);
                console.log(`  [编译] 编译时间: ${compileResult.stats?.compileTimeMs}ms`);
            } else {
                console.log(`  [编译] ✗ 失败`);
                console.log(`  [编译] 错误: ${JSON.stringify(compileResult.errors)}`);
            }

            // 4. 验证 MCP execute-atom-script 调用参数
            if (compileResult.success && compileResult.script) {
                const mcpParams = {
                    scriptContent: compileResult.script,
                    scriptName: `phase3-test-${i + 1}`,
                    dryRun: true
                };
                console.log(`  [MCP] execute-atom-script 参数已就绪 (scriptContent.length: ${mcpParams.scriptContent.length})`);
            }

            // 判定测试结果
            const testPassed = compileResult.success === tc.expectSuccess;
            if (testPassed) {
                console.log(`  [结果] ✓ 通过`);
                passed++;
            } else {
                console.log(`  [结果] ✗ 失败 (期望 ${tc.expectSuccess ? "成功" : "失败"}, 实际 ${compileResult.success ? "成功" : "失败"})`);
                failed++;
            }

        } catch (e: any) {
            console.log(`  [异常] ${e?.message || String(e)}`);
            console.log(`  [结果] ✗ 失败`);
            failed++;
        }
    }

    // ---- 测试 findByName ----
    console.log("\n--- 附加测试: findByName ---");
    const findTests = [
        { name: "Gaussian Blur", expectMatch: "ADBE Gaussian Blur 2" },
        { name: "高斯模糊", expectMatch: "ADBE Gaussian Blur 2" },
        { name: "Glow", expectMatch: "ADBE Glo2" },
        { name: "Optical Flares", expectMatch: "ACP Optical Flares" },
        { name: "deep glow", expectMatch: "ADBE Deep Glow" },  // 大小写不敏感
        { name: "Particular", expectMatch: "ACP Particular" },
        { name: "不存在的效果", expectMatch: null }
    ];

    for (const ft of findTests) {
        const entry = findByName(ft.name);
        if (ft.expectMatch === null) {
            if (!entry) {
                console.log(`  [findByName] ✓ '${ft.name}' 正确返回 undefined`);
                passed++;
            } else {
                console.log(`  [findByName] ✗ '${ft.name}' 应返回 undefined 但找到了: ${entry.matchName}`);
                failed++;
            }
        } else {
            if (entry && entry.matchName === ft.expectMatch) {
                console.log(`  [findByName] ✓ '${ft.name}' → ${ft.expectMatch}`);
                passed++;
            } else {
                console.log(`  [findByName] ✗ '${ft.name}' 应为 ${ft.expectMatch}, 实际: ${entry?.matchName || "未找到"}`);
                failed++;
            }
        }
    }

    // ---- 测试 compileReportToScript 端到端 ----
    console.log("\n--- 附加测试: compileReportToScript 端到端 ---");
    const e2eReport: AnalysisReport = {
        metadata: { frame_rate: 30, video_file: "e2e-test.mp4" },
        effects: [
            { effect_id: "EI-001", effect_name: "Gaussian Blur", confidence: 0.90 }
        ],
        parameters: [
            { effect_id: "EI-001", parameter: "Blurriness", value: 30, confidence: 0.85 }
        ],
        keyframes: [{
            effect_id: "EI-001",
            parameter: "Blurriness",
            keyframes: [
                { frame: 0, value: 0, easing: "linear" },
                { frame: 30, value: 30, easing: "ease_out", bezier: [0, 0, 0.58, 1] }
            ]
        }]
    };

    const e2eResult = compileReportToScript(e2eReport, { compName: "E2E Test Comp" }, compile);
    if (e2eResult.success && e2eResult.jsx) {
        console.log(`  [端到端] ✓ 成功生成 ExtendScript`);
        console.log(`  [端到端] 脚本大小: ${e2eResult.jsx.length} 字符`);
        console.log(`  [端到端] 生成的脚本预览 (前200字符):`);
        console.log(`    ${e2eResult.jsx.substring(0, 200).replace(/\n/g, "\n    ")}`);
        passed++;
    } else {
        console.log(`  [端到端] ✗ 失败: ${JSON.stringify(e2eResult.errors)}`);
        failed++;
    }

    // ---- 测试总结 ----
    console.log("\n========================================");
    console.log(` 测试结果: ${passed} 通过 / ${failed} 失败 / ${passed + failed} 总计`);
    console.log("========================================");

    if (failed > 0) {
        process.exit(1);
    }
}

// 执行
runTests();
