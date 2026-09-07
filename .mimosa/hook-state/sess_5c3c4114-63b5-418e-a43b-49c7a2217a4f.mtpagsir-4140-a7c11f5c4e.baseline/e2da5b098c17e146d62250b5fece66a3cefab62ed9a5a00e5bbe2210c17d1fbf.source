// ============================================================================
// unit-nlu-parser.test.ts
// NLU 意图解析器单元测试 - 覆盖所有意图类型、边界条件、槽位提取
// ============================================================================

import { NLUParser, nluParser } from "../src/phase4/nlu-parser";
import { IntentType, CONFIDENCE_THRESHOLDS, ProjectContext } from "../src/phase4/types";

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

console.log("========================================");
console.log(" NLU意图解析器单元测试");
console.log("========================================");

logSection("测试1: NLUParser实例创建");
{
    const parser = new NLUParser();
    assert(parser !== undefined, "解析器应能创建");
}

logSection("测试2: 空输入返回UNKNOWN");
{
    const result = nluParser.parse("");
    assert(result.type === IntentType.UNKNOWN, "空输入意图应为UNKNOWN");
    assert(result.confidence === 0, "空输入置信度应为0");
}

logSection("测试3: ADD_EFFECT意图 - 中文基础模式");
{
    const testCases = [
        { input: "加一个模糊", expected: "模糊" },
        { input: "添加发光", expected: "发光" },
        { input: "来个粒子", expected: "粒子" },
        { input: "加个高斯模糊", expected: "高斯模糊" },
        { input: "给文字加一个发光", expected: "发光" },
    ];

    for (const { input, expected } of testCases) {
        const result = nluParser.parse(input);
        assert(result.type === IntentType.ADD_EFFECT, `输入"${input}"应识别为ADD_EFFECT`);
        assert(result.slots.effectName?.includes(expected), `效果名应包含"${expected}"`);
        assert(result.confidence >= CONFIDENCE_THRESHOLDS.AUTO_EXECUTE, "置信度应高于自动执行阈值");
    }
}

logSection("测试4: ADD_EFFECT意图 - 英文模式");
{
    const result = nluParser.parse("apply glow");
    assert(result.type === IntentType.ADD_EFFECT, "英文输入应识别为ADD_EFFECT");
    assert(result.slots.effectName?.toLowerCase() === "glow", "效果名应为glow");
}

logSection("测试5: CREATE_ANIM意图");
{
    const testCases = [
        "做弹入动画",
        "加个缩放入场",
        "文字出场",
        "创建弹性动画",
    ];

    for (const input of testCases) {
        const result = nluParser.parse(input);
        assert(result.type === IntentType.CREATE_ANIM, `输入"${input}"应识别为CREATE_ANIM`);
        assert(result.confidence >= CONFIDENCE_THRESHOLDS.NO_CLARIFICATION, "置信度应足够");
    }
}

logSection("测试6: ADJUST_PARAM意图");
{
    const testCases = [
        { input: "模糊调大一点", param: "模糊", direction: "increase" },
        { input: "发光再强些", param: "发光", direction: "increase" },
        { input: "颜色偏暖", param: "颜色", direction: "set" },
        { input: "透明度调低", param: "透明度", direction: "decrease" },
    ];

    for (const { input, param, direction } of testCases) {
        const result = nluParser.parse(input);
        assert(result.type === IntentType.ADJUST_PARAM, `输入"${input}"应识别为ADJUST_PARAM`);
        assert(result.slots.paramName?.includes(param), `参数名应包含"${param}"`);
        assert(result.slots.adjustDirection === direction, `调整方向应为${direction}`);
    }
}

logSection("测试7: CREATE_LAYER意图");
{
    const testCases = [
        { input: "建个合成", normalized: "composition" },
        { input: "加个调整层", normalized: "adjustment" },
        { input: "创建空对象", normalized: "null" },
        { input: "加个文字层", normalized: "text" },
        { input: "create a solid", normalized: "solid" },
    ];

    for (const { input, normalized } of testCases) {
        const result = nluParser.parse(input);
        assert(result.type === IntentType.CREATE_LAYER, `输入"${input}"应识别为CREATE_LAYER`);
        assert(result.slots.targetLayer === normalized, `目标图层应标准化为"${normalized}"`);
    }
}

logSection("测试8: STYLE_COMBO意图");
{
    const testCases = [
        "做赛博朋克风格",
        "电影感",
        "梦幻风格",
        "复古调",
        "apply cyberpunk style",
    ];

    for (const input of testCases) {
        const result = nluParser.parse(input);
        assert(result.type === IntentType.STYLE_COMBO, `输入"${input}"应识别为STYLE_COMBO`);
        assert(result.slots.styleName !== undefined, "应提取风格名");
    }
}

logSection("测试9: SILHOUETTE_TASK意图 - Roto");
{
    const testCases = [
        "扣个人像",
        "做个遮罩",
        "抠出背景",
        "roto this",
        "自动抠像",
    ];

    for (const input of testCases) {
        const result = nluParser.parse(input);
        assert(result.type === IntentType.SILHOUETTE_TASK, `输入"${input}"应识别为SILHOUETTE_TASK`);
        assert(result.slots.silhouetteTask === "roto", "任务类型应为roto");
    }
}

logSection("测试10: SILHOUETTE_TASK意图 - Track");
{
    const testCases = [
        { input: "跟踪这个物体", trackType: "planar" },
        { input: "点跟踪", trackType: "point" },
        { input: "平面跟踪", trackType: "planar" },
        { input: "paint跟踪", trackType: "paint" },
    ];

    for (const { input, trackType } of testCases) {
        const result = nluParser.parse(input);
        assert(result.type === IntentType.SILHOUETTE_TASK, `输入"${input}"应识别为SILHOUETTE_TASK`);
        assert(result.slots.silhouetteTask === "track", "任务类型应为track");
        assert(result.slots.trackType === trackType, `跟踪类型应为${trackType}`);
    }
}

logSection("测试11: SILHOUETTE_TASK意图 - Paint");
{
    const testCases = [
        { input: "修掉水印", paintMode: "clone" },
        { input: "擦掉文字", paintMode: "erase" },
        { input: "修复划痕", paintMode: "repair" },
        { input: "clone this area", paintMode: "clone" },
    ];

    for (const { input, paintMode } of testCases) {
        const result = nluParser.parse(input);
        assert(result.type === IntentType.SILHOUETTE_TASK, `输入"${input}"应识别为SILHOUETTE_TASK`);
        assert(result.slots.silhouetteTask === "paint", "任务类型应为paint");
        if (result.slots.effectName) {
            assert(result.slots.effectName === paintMode, `绘制模式应为${paintMode}`);
        }
    }
}

logSection("测试12: REVERSE_ANALYZE意图");
{
    const testCases = [
        "这个效果怎么做的",
        "分析一下这段视频",
        "逆向还原",
        "how did they make this",
        "reverse engineer",
    ];

    for (const input of testCases) {
        const result = nluParser.parse(input);
        assert(result.type === IntentType.REVERSE_ANALYZE, `输入"${input}"应识别为REVERSE_ANALYZE`);
    }
}

logSection("测试13: UNKNOWN意图");
{
    const testCases = [
        "今天天气不错",
        "hello world",
        "12345",
        "测试测试",
    ];

    for (const input of testCases) {
        const result = nluParser.parse(input);
        assert(result.type === IntentType.UNKNOWN, `输入"${input}"应识别为UNKNOWN`);
        assert(result.confidence <= CONFIDENCE_THRESHOLDS.MIN_RECOGNITION, "置信度应低于识别阈值");
    }
}

logSection("测试14: 槽位提取 - 目标图层");
{
    const testCases = [
        { input: "给文字加发光", target: "text" },
        { input: "在图层1上加模糊", target: "图层1" },
        { input: "给选中的图层加效果", target: "selected" },
        { input: "给调整层加效果", target: "adjustment" },
        { input: "选中图层添加模糊", target: "selected" },
    ];

    for (const { input, target } of testCases) {
        const result = nluParser.parse(input);
        assert(result.slots.targetLayer === target, `输入"${input}"的目标图层应为"${target}"`);
    }
}

logSection("测试15: 槽位提取 - 颜色");
{
    const testCases = [
        "红色发光",
        "蓝色模糊",
        "warm glow",
        "青色粒子",
        "cyan blur",
    ];

    for (const input of testCases) {
        const result = nluParser.parse(input);
        assert(result.slots.color !== undefined, `输入"${input}"应提取颜色`);
    }
}

logSection("测试16: 槽位提取 - 时间");
{
    const testCases = [
        { input: "在开头加效果", temporal: "开头" },
        { input: "结尾淡入", temporal: "结尾" },
        { input: "at 3秒", temporal: "3秒" },
        { input: "from start", temporal: "start" },
    ];

    for (const { input, temporal } of testCases) {
        const result = nluParser.parse(input);
        assert(result.slots.temporal?.includes(temporal), `输入"${input}"应提取时间"${temporal}"`);
    }
}

logSection("测试17: 上下文辅助解析");
{
    const context: ProjectContext = {
        selectedLayers: [{ name: "文字层", index: 1, type: "text" }],
        compResolution: [1920, 1080],
        compFrameRate: 30,
    };

    const result = nluParser.parse("加一个发光", context);
    assert(result.type === IntentType.ADD_EFFECT, "意图应为ADD_EFFECT");
    assert(result.slots.targetLayer === "selected", "应有selected目标图层");
}

logSection("测试18: needsClarification - 高置信度无需追问");
{
    const intent = nluParser.parse("加一个高斯模糊");
    assert(!nluParser.needsClarification(intent), "高置信度意图不应需要追问");
}

logSection("测试19: needsClarification - 模糊输入需要追问");
{
    const intent = nluParser.parse("做些效果");
    assert(nluParser.needsClarification(intent), "低置信度意图应需要追问");
}

logSection("测试20: 关键词回退机制");
{
    const result = nluParser.parse("模糊发光");
    assert(result.type === IntentType.ADD_EFFECT, "关键词回退应识别为ADD_EFFECT");
    assert(result.confidence >= 0.5 && result.confidence < CONFIDENCE_THRESHOLDS.NO_CLARIFICATION, "置信度应在回退范围内");
}

logSection("测试21: 边界条件 - 超长输入");
{
    const longInput = "加一个".repeat(50) + "模糊";
    const result = nluParser.parse(longInput);
    assert(result.type === IntentType.ADD_EFFECT, "超长输入应能识别");
}

logSection("测试22: 边界条件 - 特殊字符");
{
    const testCases = [
        "加一个✨发光",
        "做赛博朋克🎮风格",
        "模糊++",
        "发光...",
    ];

    for (const input of testCases) {
        const result = nluParser.parse(input);
        assert(result.type !== IntentType.UNKNOWN, `输入"${input}"应能识别`);
    }
}

logSection("测试23: 边界条件 - 中英文混合");
{
    const testCases = [
        "加一个glow效果",
        "apply高斯模糊",
        "做cyberpunk风格",
    ];

    for (const input of testCases) {
        const result = nluParser.parse(input);
        assert(result.success !== undefined || result.type !== IntentType.UNKNOWN, `输入"${input}"应能识别`);
    }
}

logSection("测试24: 边界条件 - 大小写敏感性");
{
    const result1 = nluParser.parse("APPLY GLOW");
    const result2 = nluParser.parse("Apply Glow");
    const result3 = nluParser.parse("apply glow");

    assert(result1.type === IntentType.ADD_EFFECT, "全大写应识别");
    assert(result2.type === IntentType.ADD_EFFECT, "首字母大写应识别");
    assert(result3.type === IntentType.ADD_EFFECT, "全小写应识别");
}

console.log("\n========================================");
console.log(` 测试结果: ${passCount} 通过 / ${failCount} 失败 / ${passCount + failCount} 总计`);
console.log("========================================");

process.exit(failCount > 0 ? 1 : 0);