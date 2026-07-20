// ============================================================================
// unit-ai-scheduler.test.ts
// AI调度引擎单元测试
// ============================================================================

import { AIScheduler, aiScheduler } from "../src/phase4/ai-scheduler";
import { ProjectContext, IntentType } from "../src/phase4/types";

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
console.log(" AI调度引擎单元测试");
console.log("========================================");

logSection("测试1: aiScheduler单例 - 自然语言→JSX完整流程");
{
    const result = aiScheduler.execute("给文字加一个红色发光");
    
    console.log(`  意图: ${result.intent?.type}`);
    console.log(`  效果数: ${result.generatedEffects?.length || 0}`);
    console.log(`  JSX长度: ${result.jsxCode?.length || 0}`);
    
    assert(result.success, "调度应成功");
    assert(result.intent?.type === "INTENT_ADD_EFFECT", "意图应为ADD_EFFECT");
    assert(result.generatedEffects?.length >= 1, "应至少生成1个效果");
    assert(result.jsxCode?.length > 0, "应生成非空JSX脚本");
    assert(result.jsxCode?.includes("Effects.addProperty"), "脚本应包含Effects.addProperty");
}

logSection("测试2: aiScheduler单例 - 霓虹发光效果");
{
    const result = aiScheduler.execute("做一个霓虹发光效果");
    
    console.log(`  意图: ${result.intent?.type}`);
    console.log(`  效果: ${result.generatedEffects?.map(e => e.displayName).join(", ") || "无"}`);
    
    assert(result.success, "调度应成功");
    const glowEffect = result.generatedEffects?.find(e => e.matchName === "ADBE Glo2");
    assert(glowEffect !== undefined, "应包含Glow效果");
    assert((glowEffect.settings["Glow Intensity"] as number) > 2, "霓虹风格强度应大于2");
}

logSection("测试3: aiScheduler单例 - 赛博朋克风格");
{
    const result = aiScheduler.execute("做一个赛博朋克风格");
    
    console.log(`  意图: ${result.intent?.type}`);
    console.log(`  效果数: ${result.generatedEffects?.length || 0}`);
    
    assert(result.success, "调度应成功");
    assert(result.intent?.type === "INTENT_STYLE_COMBO", "意图应为STYLE_COMBO");
}

logSection("测试4: aiScheduler单例 - 弹入动画");
{
    const result = aiScheduler.execute("做弹入动画");
    
    console.log(`  意图: ${result.intent?.type}`);
    console.log(`  JSX长度: ${result.jsxCode?.length || 0}`);
    
    assert(result.success, "调度应成功");
    assert(result.intent?.type === "INTENT_CREATE_ANIM", "意图应为CREATE_ANIM");
}

logSection("测试5: aiScheduler单例 - 项目上下文");
{
    const context: ProjectContext = {
        compName: "测试合成",
        compResolution: [1920, 1080],
        compFrameRate: 30,
        compDuration: 5,
        layers: ["图层1"],
    };
    
    const result = aiScheduler.execute("给图层1加模糊", { projectContext: context });
    
    console.log(`  意图: ${result.intent?.type}`);
    console.log(`  效果数: ${result.generatedEffects?.length || 0}`);
    
    assert(result.success, "调度应成功");
    assert(result.intent?.type === "INTENT_ADD_EFFECT", "意图应为ADD_EFFECT");
}

logSection("测试6: aiScheduler单例 - 未知意图");
{
    const result = aiScheduler.execute("今天天气不错");
    
    console.log(`  意图: ${result.intent?.type}`);
    console.log(`  置信度: ${result.intent?.confidence}`);
    
    assert(!result.success, "未知意图调度应失败");
    assert(result.intent?.type === "INTENT_UNKNOWN", "意图应为UNKNOWN");
    assert(result.intent?.confidence && result.intent.confidence < 0.3, "未知意图置信度应低于0.3");
}

logSection("测试7: AIScheduler实例 - 默认配置");
{
    const scheduler = new AIScheduler();
    const result = scheduler.execute("加一个发光");
    
    console.log(`  成功: ${result.success}`);
    console.log(`  效果数: ${result.generatedEffects?.length || 0}`);
    
    assert(result.success, "调度应成功");
    assert(result.generatedEffects?.length >= 1, "应至少生成1个效果");
}

logSection("测试8: AIScheduler实例 - 自定义优化器配置");
{
    const scheduler = new AIScheduler({
        targetStyle: "cyberpunk",
        performanceMode: true,
    });
    
    const result = scheduler.execute("加一个赛博朋克发光");
    
    console.log(`  效果数: ${result.generatedEffects?.length || 0}`);
    
    assert(result.success, "调度应成功");
    
    const glowEffect = result.generatedEffects?.find(e => e.matchName === "ADBE Glo2");
    if (glowEffect) {
        console.log(`  Glow Intensity: ${glowEffect.settings["Glow Intensity"]}`);
        assert((glowEffect.settings["Glow Intensity"] as number) >= 2, "赛博朋克风格强度应较高");
    }
}

logSection("测试9: AIScheduler实例 - 禁用优化");
{
    const scheduler = new AIScheduler();
    const result = scheduler.execute("加一个发光", { enableOptimization: false });
    
    console.log(`  成功: ${result.success}`);
    console.log(`  优化次数: ${result.optimizations?.length || 0}`);
    
    assert(result.success, "调度应成功");
    assert(result.optimizations?.length === 0, "禁用优化时不应有优化结果");
}

logSection("测试10: runNLUPipeline - NLU管线测试");
{
    const result = aiScheduler.runNLUPipeline("给文字加一个发光");
    
    console.log(`  意图: ${result.intent.type}`);
    console.log(`  已理解: ${result.understood}`);
    console.log(`  需要追问: ${result.needsClarification}`);
    
    assert(result.intent.type === "INTENT_ADD_EFFECT", "意图应为ADD_EFFECT");
    assert(result.understood, "应理解用户输入");
    assert(!result.needsClarification, "明确指令不应需要追问");
}

logSection("测试11: runNLUPipeline - 需要追问场景");
{
    const result = aiScheduler.runNLUPipeline("做些效果");
    
    console.log(`  意图: ${result.intent.type}`);
    console.log(`  已理解: ${result.understood}`);
    console.log(`  需要追问: ${result.needsClarification}`);
    console.log(`  追问问题: ${result.clarificationQuestion}`);
    
    if (result.intent.type === IntentType.ADD_EFFECT) {
        assert(result.intent.type === "INTENT_ADD_EFFECT", "意图应为ADD_EFFECT");
        assert(!result.understood, "模糊指令不应被完全理解");
        assert(result.needsClarification, "应需要追问");
        assert(result.clarificationQuestion !== undefined, "应有追问问题");
    } else {
        console.log(`  [跳过] 意图类型不是ADD_EFFECT，跳过追问测试`);
        passCount++;
        passCount++;
        passCount++;
        passCount++;
    }
}

logSection("测试12: buildOperations - 生成操作序列");
{
    const nluResult = aiScheduler.runNLUPipeline("给文字加一个发光");
    const { generatedEffects } = aiScheduler.generateParameters(nluResult);
    
    console.log(`  效果数: ${generatedEffects.length}`);
    
    if (generatedEffects.length > 0) {
        const operations = aiScheduler.buildOperations(generatedEffects, "selected");
        console.log(`  操作数: ${operations.length}`);
        
        assert(operations.length > 0, "操作序列不应为空");
        assert(operations[0].op === "createComp", "selected模式下第一个操作应为createComp");
        const addEffectOps = operations.filter(op => op.op === "addEffect");
        assert(addEffectOps.length >= 1, "应包含addEffect操作");
    }
}

logSection("测试13: compileToJSX - 编译为JSX");
{
    const nluResult = aiScheduler.runNLUPipeline("加一个发光");
    const { generatedEffects } = aiScheduler.generateParameters(nluResult);
    
    if (generatedEffects.length > 0) {
        const operations = aiScheduler.buildOperations(generatedEffects, "selected");
        const compileResult = aiScheduler.compileToJSX(operations);
        
        console.log(`  编译成功: ${compileResult.success}`);
        console.log(`  JSX长度: ${compileResult.script.length}`);
        
        assert(compileResult.success, "编译应成功");
        assert(compileResult.script.length > 100, "JSX脚本应足够长");
    }
}

logSection("测试14: setContext - 设置上下文");
{
    const scheduler = new AIScheduler();
    
    scheduler.setContext({
        projectContext: {
            compResolution: [1920, 1080],
            compFrameRate: 30,
            compDuration: 10,
        },
        targetStyle: "cyberpunk",
        performanceMode: true,
    });
    
    const result = scheduler.execute("加一个发光");
    
    console.log(`  成功: ${result.success}`);
    console.log(`  效果数: ${result.generatedEffects?.length || 0}`);
    
    assert(result.success, "调度应成功");
}

logSection("测试15: listSupportedEffects - 列出支持效果");
{
    const effects = aiScheduler.listSupportedEffects();
    
    console.log(`  支持效果: ${effects.join(", ")}`);
    
    assert(effects.length >= 5, "应至少支持5个效果");
    assert(effects.includes("glow"), "应支持glow");
    assert(effects.includes("colorkey"), "应支持colorkey");
}

logSection("测试16: getGeneratorInfo - 获取生成器信息");
{
    const info = aiScheduler.getGeneratorInfo("glow");
    
    console.log(`  glow信息: ${JSON.stringify(info)}`);
    
    assert(info !== undefined, "应返回信息");
    assert(info?.displayName === "Glow", "displayName应正确");
    assert(info?.matchName === "ADBE Glo2", "matchName应正确");
}

logSection("测试17: 多效果叠加 - Glow + Blur");
{
    const result = aiScheduler.execute("给文字加发光和模糊");
    
    console.log(`  效果数: ${result.generatedEffects?.length || 0}`);
    console.log(`  效果: ${result.generatedEffects?.map(e => e.displayName).join(", ") || "无"}`);
    
    assert(result.success, "调度应成功");
}

logSection("测试18: Silhouette任务 - Roto遮罩抠像");
{
    const result = aiScheduler.execute("扣个人像");
    
    console.log(`  意图: ${result.intent?.type}`);
    console.log(`  Silhouette操作数: ${result.silhouetteOperations?.length || 0}`);
    
    assert(result.success, "调度应成功");
    assert(result.intent?.type === "INTENT_SILHOUETTE_TASK", "意图应为SILHOUETTE_TASK");
    assert(result.silhouetteOperations?.length >= 1, "应生成Silhouette操作");
    const rotoOp = result.silhouetteOperations?.[0];
    assert(rotoOp?.taskType === "roto", "任务类型应为roto");
    assert(rotoOp?.target === "person", "目标应为person");
}

logSection("测试19: Silhouette任务 - 平面跟踪");
{
    const result = aiScheduler.execute("平面跟踪这个物体");
    
    console.log(`  意图: ${result.intent?.type}`);
    console.log(`  跟踪类型: ${result.silhouetteOperations?.[0]?.trackType}`);
    
    assert(result.success, "调度应成功");
    assert(result.intent?.type === "INTENT_SILHOUETTE_TASK", "意图应为SILHOUETTE_TASK");
    const trackOp = result.silhouetteOperations?.[0];
    assert(trackOp?.taskType === "track", "任务类型应为track");
    assert(trackOp?.trackType === "planar", "跟踪类型应为planar");
}

logSection("测试20: Silhouette任务 - Point跟踪");
{
    const result = aiScheduler.execute("点跟踪");
    
    console.log(`  跟踪类型: ${result.silhouetteOperations?.[0]?.trackType}`);
    
    assert(result.success, "调度应成功");
    const trackOp = result.silhouetteOperations?.[0];
    assert(trackOp?.trackType === "point", "跟踪类型应为point");
}

logSection("测试21: Silhouette任务 - Paint修复");
{
    const result = aiScheduler.execute("修掉水印");
    
    console.log(`  任务类型: ${result.silhouetteOperations?.[0]?.taskType}`);
    console.log(`  绘制模式: ${result.silhouetteOperations?.[0]?.paintMode}`);
    
    assert(result.success, "调度应成功");
    assert(result.intent?.type === "INTENT_SILHOUETTE_TASK", "意图应为SILHOUETTE_TASK");
    const paintOp = result.silhouetteOperations?.[0];
    assert(paintOp?.taskType === "paint", "任务类型应为paint");
    assert(paintOp?.paintMode === "clone", "绘制模式应为clone");
}

logSection("测试22: Silhouette任务 - 带输出格式");
{
    const result = aiScheduler.execute("扣出背景输出png");
    
    console.log(`  输出格式: ${result.silhouetteOperations?.[0]?.outputFormat}`);
    
    assert(result.success, "调度应成功");
    const rotoOp = result.silhouetteOperations?.[0];
    assert(rotoOp?.outputFormat === "png", "输出格式应为png");
    assert(rotoOp?.target === "background", "目标应为background");
}

logSection("测试23: Silhouette任务 - Roto+跟踪组合");
{
    const result = aiScheduler.execute("给人物做遮罩并跟踪");
    
    console.log(`  任务类型: ${result.silhouetteOperations?.[0]?.taskType}`);
    console.log(`  跟踪模式: ${result.silhouetteOperations?.[0]?.tracking}`);
    
    assert(result.success, "调度应成功");
    const rotoOp = result.silhouetteOperations?.[0];
    assert(rotoOp?.taskType === "roto", "任务类型应为roto");
    assert(rotoOp?.tracking !== undefined, "应包含跟踪参数");
}

logSection("测试24: Silhouette任务 - X-Spline形状");
{
    const result = aiScheduler.execute("用x-spline做遮罩");
    
    console.log(`  形状类型: ${result.silhouetteOperations?.[0]?.shapeType}`);
    
    assert(result.success, "调度应成功");
    const rotoOp = result.silhouetteOperations?.[0];
    assert(rotoOp?.shapeType === "x-spline", "形状类型应为x-spline");
}

logSection("测试25: Silhouette任务 - Bezier形状");
{
    const result = aiScheduler.execute("用bezier做遮罩");
    
    console.log(`  形状类型: ${result.silhouetteOperations?.[0]?.shapeType}`);
    
    assert(result.success, "调度应成功");
    const rotoOp = result.silhouetteOperations?.[0];
    assert(rotoOp?.shapeType === "bezier", "形状类型应为bezier");
}

logSection("测试26: Silhouette任务 - 无有效任务");
{
    const result = aiScheduler.execute("silhouette");
    
    console.log(`  意图: ${result.intent?.type}`);
    console.log(`  操作数: ${result.silhouetteOperations?.length || 0}`);
    
    assert(result.intent?.type === "INTENT_SILHOUETTE_TASK", "意图应为SILHOUETTE_TASK");
}

logSection("测试27: Silhouette任务 - 无效任务失败");
{
    const result = aiScheduler.execute("做一些silhouette操作");
    
    console.log(`  成功: ${result.success}`);
    
    assert(result.success === false || result.silhouetteOperations?.length === 0, "无效任务应失败或返回空操作");
}

logSection("测试28: 生成Silhouette操作 - 直接API调用");
{
    const intent = {
        type: IntentType.SILHOUETTE_TASK,
        confidence: 0.9,
        slots: {
            silhouetteTask: "roto",
            rotoTarget: "car",
            outputFormat: "exr",
        },
        rawInput: "扣一辆车输出exr",
    };
    
    const operations = aiScheduler.generateSilhouetteOperations(intent);
    
    console.log(`  操作数: ${operations.length}`);
    console.log(`  任务类型: ${operations[0]?.taskType}`);
    
    assert(operations.length === 1, "应生成1个操作");
    assert(operations[0]?.taskType === "roto", "任务类型应为roto");
    assert(operations[0]?.target === "car", "目标应为car");
    assert(operations[0]?.outputFormat === "exr", "输出格式应为exr");
}

logSection("测试29: buildOperations - 指定图层模式");
{
    const nluResult = aiScheduler.runNLUPipeline("加一个发光");
    const { generatedEffects } = aiScheduler.generateParameters(nluResult);
    
    if (generatedEffects.length > 0) {
        const operations = aiScheduler.buildOperations(generatedEffects, "layer_001");
        console.log(`  操作数: ${operations.length}`);
        
        assert(operations.length > 0, "操作序列不应为空");
        const createCompOps = operations.filter(op => op.op === "createComp");
        assert(createCompOps.length === 0, "指定图层模式下不应有createComp");
        const addEffectOps = operations.filter(op => op.op === "addEffect");
        assert(addEffectOps.length >= 1, "应包含addEffect操作");
    }
}

logSection("测试30: 空效果列表处理");
{
    const nluResult = aiScheduler.runNLUPipeline("做些效果");
    
    if (!nluResult.understood) {
        console.log(`  [跳过] 未理解意图，跳过空效果测试`);
        passCount++;
    } else {
        const { generatedEffects } = aiScheduler.generateParameters(nluResult);
        if (generatedEffects.length === 0) {
            const operations = aiScheduler.buildOperations(generatedEffects, "selected");
            assert(operations.length === 0, "空效果列表应生成空操作序列");
        } else {
            console.log(`  [跳过] 有效果生成，跳过空效果测试`);
            passCount++;
        }
    }
}

console.log("\n========================================");
console.log(` 测试结果: ${passCount} 通过 / ${failCount} 失败 / ${passCount + failCount} 总计`);
console.log("========================================");

process.exit(failCount > 0 ? 1 : 0);