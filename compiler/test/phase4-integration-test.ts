// ============================================================================
// phase4-integration-test.ts
// Phase 4 端到端集成测试
//
// 测试完整管线：自然语言 → NLU意图识别 → 效果描述解析 → AnalysisReport → 编译器
//
// 运行：node build/phase4-integration-test.js
// ============================================================================

import {
    processUserInput,
    processClarification,
    nluToReport,
    getPhase4Info,
    IntentType,
    CONFIDENCE_THRESHOLDS,
} from "../src/phase4";
import { compile } from "../src/index";
import { reportToOps } from "../src/phase3";

// ============================================================================
// 测试工具
// ============================================================================

let passCount = 0;
let failCount = 0;

function assert(condition: boolean, message: string): void {
    if (condition) {
        console.log(`  ✓ ${message}`);
        passCount++;
    } else {
        console.log(`  ✗ ${message}`);
        failCount++;
    }
}

function logSection(title: string): void {
    console.log(`\n--- ${title} ---`);
}

// ============================================================================
// 测试用例
// ============================================================================

console.log("========================================");
console.log(" Phase 4 端到端集成测试");
console.log(" 自然语言 → NLU → AnalysisReport → 编译器");
console.log("========================================");

const info = getPhase4Info();
console.log(`[信息] 词汇库大小: ${info.vocabularySize}`);
console.log(`[信息] 词汇分类: ${JSON.stringify(info.vocabularyCategories)}`);
console.log(`[信息] 置信度阈值: ${JSON.stringify(info.confidenceThresholds)}`);

// ---- 测试1: 添加效果（明确指令） ----
logSection("测试1: 添加效果（明确指令）");
{
    const input = "给文字加一个高斯模糊";
    const response = processUserInput(input);

    console.log(`  [输入] "${input}"`);
    console.log(`  [意图] type=${response.intent.type}, confidence=${response.intent.confidence.toFixed(2)}`);
    console.log(`  [槽位] effectName=${response.intent.slots.effectName}, targetLayer=${response.intent.slots.targetLayer}`);
    console.log(`  [效果描述] effectKeywords=${response.effectDescription.effectKeywords.length}`);
    console.log(`  [追问] needed=${response.needsClarification}`);

    assert(response.understood === true, "用户输入应被理解");
    assert(response.intent.type === IntentType.ADD_EFFECT, "意图应为 ADD_EFFECT");
    assert(response.intent.confidence >= 0.7, "置信度应 >= 0.7");
    assert(response.intent.slots.targetLayer === "text", "目标图层应为 text");
    assert(!response.needsClarification, "不应需要追问");
}

// ---- 测试2: 添加效果（模糊指令，需追问） ----
logSection("测试2: 添加效果（模糊指令，需追问）");
{
    const input = "加个模糊";
    const response = processUserInput(input);

    console.log(`  [输入] "${input}"`);
    console.log(`  [意图] type=${response.intent.type}, confidence=${response.intent.confidence.toFixed(2)}`);
    console.log(`  [槽位] effectName=${response.intent.slots.effectName}, targetLayer=${response.intent.slots.targetLayer || "未指定"}`);

    // "模糊"会匹配多个候选效果
    assert(response.understood === true, "用户输入应被理解");
    assert(response.intent.type === IntentType.ADD_EFFECT, "意图应为 ADD_EFFECT");
    // 没有指定目标图层，应触发追问
    if (response.needsClarification) {
        console.log(`  [追问] Q: ${response.clarificationQuestion}`);
        console.log(`  [选项] ${response.clarificationOptions?.join(", ")}`);
        assert(!!response.clarificationQuestion, "应返回追问问题");
        assert((response.clarificationOptions?.length || 0) > 0, "应返回追问选项");
    } else {
        console.log(`  [信息] 置信度足够，未触发追问`);
    }
}

// ---- 测试3: 创建动画 ----
logSection("测试3: 创建动画");
{
    const input = "做弹入动画";
    const response = processUserInput(input);

    console.log(`  [输入] "${input}"`);
    console.log(`  [意图] type=${response.intent.type}, confidence=${response.intent.confidence.toFixed(2)}`);
    console.log(`  [槽位] animType=${response.intent.slots.animType}`);

    assert(response.understood === true, "用户输入应被理解");
    assert(response.intent.type === IntentType.CREATE_ANIM, "意图应为 CREATE_ANIM");
}

// ---- 测试4: 调整参数 ----
logSection("测试4: 调整参数");
{
    const input = "模糊调大一点";
    const response = processUserInput(input);

    console.log(`  [输入] "${input}"`);
    console.log(`  [意图] type=${response.intent.type}, confidence=${response.intent.confidence.toFixed(2)}`);
    console.log(`  [槽位] paramName=${response.intent.slots.paramName}, direction=${response.intent.slots.adjustDirection}`);

    assert(response.understood === true, "用户输入应被理解");
    assert(response.intent.type === IntentType.ADJUST_PARAM, "意图应为 ADJUST_PARAM");
    assert(response.intent.slots.adjustDirection === "increase", "调整方向应为 increase");
}

// ---- 测试5: 创建图层 ----
logSection("测试5: 创建图层");
{
    const input = "建一个合成";
    const response = processUserInput(input);

    console.log(`  [输入] "${input}"`);
    console.log(`  [意图] type=${response.intent.type}, confidence=${response.intent.confidence.toFixed(2)}`);
    console.log(`  [槽位] targetLayer=${response.intent.slots.targetLayer}`);

    assert(response.understood === true, "用户输入应被理解");
    assert(response.intent.type === IntentType.CREATE_LAYER, "意图应为 CREATE_LAYER");
    assert(response.intent.slots.targetLayer === "composition", "图层类型应为 composition");
}

// ---- 测试6: 风格化组合 ----
logSection("测试6: 风格化组合");
{
    const input = "做一个赛博朋克风格";
    const response = processUserInput(input);

    console.log(`  [输入] "${input}"`);
    console.log(`  [意图] type=${response.intent.type}, confidence=${response.intent.confidence.toFixed(2)}`);
    console.log(`  [槽位] styleName=${response.intent.slots.styleName}`);

    assert(response.understood === true, "用户输入应被理解");
    assert(response.intent.type === IntentType.STYLE_COMBO, "意图应为 STYLE_COMBO");
    assert(response.intent.slots.styleName === "赛博朋克", "风格名应为 赛博朋克");
}

// ---- 测试7: 逆向分析 ----
logSection("测试7: 逆向分析");
{
    const input = "这个效果怎么做的";
    const response = processUserInput(input);

    console.log(`  [输入] "${input}"`);
    console.log(`  [意图] type=${response.intent.type}, confidence=${response.intent.confidence.toFixed(2)}`);

    assert(response.understood === true, "用户输入应被理解");
    assert(response.intent.type === IntentType.REVERSE_ANALYZE, "意图应为 REVERSE_ANALYZE");
}

// ---- 测试8: 未知意图 ----
logSection("测试8: 未知意图");
{
    const input = "今天天气不错";
    const response = processUserInput(input);

    console.log(`  [输入] "${input}"`);
    console.log(`  [意图] type=${response.intent.type}, confidence=${response.intent.confidence.toFixed(2)}`);

    assert(response.understood === false, "未知意图应不被理解");
    assert(response.intent.type === IntentType.UNKNOWN, "意图应为 UNKNOWN");
    assert(response.intent.confidence < 0.3, "置信度应 < 0.3");
}

// ---- 测试9: 中英文双语 - 发光 ----
logSection("测试9: 中英文双语 - 发光");
{
    const inputs = ["加一个发光", "add glow", "来个辉光"];
    for (const input of inputs) {
        const response = processUserInput(input);
        console.log(`  [输入] "${input}" → intent.type=${response.intent.type}`);
        assert(response.understood === true, `"${input}" 应被理解`);
        assert(response.intent.type === IntentType.ADD_EFFECT, `"${input}" 意图应为 ADD_EFFECT`);
    }
}

// ---- 测试10: 追问机制 ----
logSection("测试10: 追问机制");
{
    const input = "加个模糊";
    const response = processUserInput(input);

    console.log(`  [输入] "${input}"`);
    console.log(`  [追问] needed=${response.needsClarification}`);

    if (response.needsClarification && response.clarificationOptions) {
        // 模拟用户选择"高斯模糊"
        const answer = response.clarificationOptions[0];
        console.log(`  [用户回答] "${answer}"`);

        // 应用追问答案
        const updatedResponse = processClarification(
            response.intent,
            response.effectDescription,
            answer,
            "targetLayer", // 假设追问的是目标图层
        );

        console.log(`  [更新后] confidence=${updatedResponse.intent.confidence.toFixed(2)}`);
        assert(updatedResponse.intent.confidence > response.intent.confidence, "追问后置信度应提升");
    } else {
        console.log(`  [信息] 置信度足够，未触发追问`);
    }
}

// ---- 测试11: 端到端 - 自然语言 → AnalysisReport → 编译器 ----
logSection("测试11: 端到端 - 自然语言 → 编译器");
{
    const input = "给文字加一个高斯模糊";
    console.log(`  [输入] "${input}"`);

    // 1. NLU → AnalysisReport
    const report = nluToReport(input);
    const overallConfidence = report.confidence?.overall || report.metadata.confidence || 0;
    console.log(`  [报告] effects=${report.effects?.length || 0}, params=${report.parameters?.length || 0}`);
    console.log(`  [报告] confidence=${overallConfidence.toFixed(2)}`);
    console.log(`  [报告] visual_features=${(report.visual_features || []).map(v => v.term_name).join(", ")}`);

    assert((report.effects?.length || 0) > 0, "报告应包含至少一个效果");
    assert((report.parameters?.length || 0) > 0, "报告应包含至少一个参数");
    assert(overallConfidence > 0.5, "置信度应 > 0.5");

    // 2. AnalysisReport → 编译器输入
    const compilerInput = reportToOps(report);
    console.log(`  [编译器] 操作数=${compilerInput.operations.length}`);
    console.log(`  [编译器] 操作类型=${JSON.stringify(countOpTypes(compilerInput.operations))}`);

    assert(compilerInput.operations.length > 0, "编译器输入应包含操作");

    // 3. 编译
    const result = compile(compilerInput);
    console.log(`  [编译] success=${result.success}, scriptSize=${result.script.length}`);

    assert(result.success, "编译应成功");
    assert(result.script.length > 0, "生成的脚本应非空");
    assert(result.script.includes("Effects.addProperty"), "脚本应包含 Effects.addProperty 调用");

    console.log(`  [脚本预览] (前150字符):`);
    console.log(`    ${result.script.slice(0, 150).replace(/\n/g, "\n    ")}`);
}

// ---- 测试12: 端到端 - 风格化组合 ----
logSection("测试12: 端到端 - 风格化组合（赛博朋克）");
{
    const input = "做一个赛博朋克风格";
    console.log(`  [输入] "${input}"`);

    const report = nluToReport(input);
    console.log(`  [报告] effects=${report.effects?.length || 0}, params=${report.parameters?.length || 0}`);

    assert((report.effects?.length || 0) >= 2, "赛博朋克风格应包含至少2个效果");

    const compilerInput = reportToOps(report);
    console.log(`  [编译器] 操作数=${compilerInput.operations.length}`);

    const result = compile(compilerInput);
    console.log(`  [编译] success=${result.success}, scriptSize=${result.script.length}`);

    assert(result.success, "编译应成功");
}

// ---- 测试13: 端到端 - 动画 ----
logSection("测试13: 端到端 - 弹入动画");
{
    const input = "做弹入动画";
    console.log(`  [输入] "${input}"`);

    const report = nluToReport(input);
    console.log(`  [报告] keyframes=${report.keyframes?.length || 0}`);

    assert((report.keyframes?.length || 0) > 0, "应包含关键帧");

    const compilerInput = reportToOps(report);
    console.log(`  [编译器] 操作数=${compilerInput.operations.length}`);

    const result = compile(compilerInput);
    console.log(`  [编译] success=${result.success}, scriptSize=${result.script.length}`);

    assert(result.success, "编译应成功");
    assert(result.script.includes("setValueAtTime"), "脚本应包含 setValueAtTime 调用");
}

// ---- 测试14: 项目上下文使用 ----
logSection("测试14: 项目上下文使用");
{
    const input = "加一个模糊";
    const context = {
        activeCompName: "MyComp",
        selectedLayers: [{ name: "Layer1", index: 1, type: "solid" }],
        compResolution: [1920, 1080] as [number, number],
        compFrameRate: 30,
        compDuration: 5,
    };

    const report = nluToReport(input, context);
    console.log(`  [上下文] duration=${context.compDuration}s, fps=${context.compFrameRate}`);
    console.log(`  [报告] metadata.frame_rate=${report.metadata.frame_rate}, duration=${report.metadata.duration}`);

    assert(report.metadata.frame_rate === 30, "metadata.frame_rate 应等于上下文的 fps");
    assert(report.metadata.duration === "5s", "metadata.duration 应等于上下文的 duration");
}

// ============================================================================
// 辅助函数
// ============================================================================

function countOpTypes(operations: any[]): Record<string, number> {
    const result: Record<string, number> = {};
    for (const op of operations) {
        const t = op.op || "unknown";
        result[t] = (result[t] || 0) + 1;
    }
    return result;
}

// ============================================================================
// 测试结果汇总
// ============================================================================

console.log("\n========================================");
console.log(` 测试结果: ${passCount} 通过 / ${failCount} 失败 / ${passCount + failCount} 总计`);
console.log("========================================");

process.exit(failCount > 0 ? 1 : 0);
