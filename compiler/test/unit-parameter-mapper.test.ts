// ============================================================================
// unit-parameter-mapper.test.ts
// 参数映射器单元测试 - 覆盖模板映射、修饰词应用、知识图谱查询
// ============================================================================

import { ParameterMapper, parameterMapper } from "../src/phase4/parameter-mapper";
import { EffectDescription, IntensityRef, ColorRef, VocabRef } from "../src/phase4/types";
import { EffectCategory } from "../src/phase4/effect-knowledge-graph";

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
console.log(" 参数映射器单元测试");
console.log("========================================");

logSection("测试1: ParameterMapper实例创建");
{
    const mapper = new ParameterMapper();
    assert(mapper !== undefined, "映射器应能创建");
}

logSection("测试2: map - VT-101发光效果映射");
{
    const description: EffectDescription = {
        effectKeywords: [{ id: "VT-101", name: "边缘发光", matchedKeyword: "发光", confidence: 0.9 }],
        styleKeywords: [],
        directionKeywords: [],
        intensityKeywords: [],
        colorKeywords: [],
        temporalKeywords: [],
    };

    const result = parameterMapper.map(description);
    assert(result.length > 0, "应返回映射结果");
    assert(result[0].matchName === "ADBE Glo2", "matchName应为ADBE Glo2");
    assert(result[0].confidence >= 0.8, "置信度应足够");
    assert(typeof result[0].settings["Glow Intensity"] === "number", "应包含Glow Intensity参数");
}

logSection("测试3: map - VT-001模糊效果映射");
{
    const description: EffectDescription = {
        effectKeywords: [{ id: "VT-001", name: "均匀模糊", matchedKeyword: "模糊", confidence: 0.9 }],
        styleKeywords: [],
        directionKeywords: [],
        intensityKeywords: [],
        colorKeywords: [],
        temporalKeywords: [],
    };

    const result = parameterMapper.map(description);
    assert(result.length > 0, "应返回映射结果");
    assert(result[0].matchName === "ADBE Gaussian Blur 2", "matchName应为ADBE Gaussian Blur 2");
    assert(typeof result[0].settings["Blurriness"] === "number", "应包含Blurriness参数");
}

logSection("测试4: map - 强度修饰词应用");
{
    const intensityRefs: IntensityRef[] = [
        { keyword: "强烈", level: "strong", scale: 1.5 },
    ];

    const description: EffectDescription = {
        effectKeywords: [{ id: "VT-101", name: "边缘发光", matchedKeyword: "发光", confidence: 0.9 }],
        styleKeywords: [],
        directionKeywords: [],
        intensityKeywords: intensityRefs,
        colorKeywords: [],
        temporalKeywords: [],
    };

    const result = parameterMapper.map(description);
    assert(result.length > 0, "应返回映射结果");
    const intensity = result[0].settings["Glow Intensity"] as number;
    assert(intensity > 1.5, "增强强度后应大于默认值");
}

logSection("测试5: map - 颜色修饰词应用");
{
    const colorRefs: ColorRef[] = [
        { keyword: "红色", rgb: [1, 0, 0], temperature: "warm" },
    ];

    const description: EffectDescription = {
        effectKeywords: [{ id: "VT-101", name: "边缘发光", matchedKeyword: "发光", confidence: 0.9 }],
        styleKeywords: [],
        directionKeywords: [],
        intensityKeywords: [],
        colorKeywords: colorRefs,
        temporalKeywords: [],
    };

    const result = parameterMapper.map(description);
    assert(result.length > 0, "应返回映射结果");
    const colorA = result[0].settings["Glow Color A"] as number[];
    assert(colorA[0] > 0.9, "红色发光的R通道应接近1");
    assert(colorA[1] < 0.1, "红色发光的G通道应接近0");
    assert(colorA[2] < 0.1, "红色发光的B通道应接近0");
}

logSection("测试6: map - 多重修饰词组合");
{
    const intensityRefs: IntensityRef[] = [
        { keyword: "强烈", level: "strong", scale: 1.5 },
    ];

    const colorRefs: ColorRef[] = [
        { keyword: "蓝色", rgb: [0, 0, 1], temperature: "cool" },
    ];

    const description: EffectDescription = {
        effectKeywords: [{ id: "VT-101", name: "边缘发光", matchedKeyword: "发光", confidence: 0.9 }],
        styleKeywords: [],
        directionKeywords: [],
        intensityKeywords: intensityRefs,
        colorKeywords: colorRefs,
        temporalKeywords: [],
    };

    const result = parameterMapper.map(description);
    assert(result.length > 0, "应返回映射结果");
    assert(typeof result[0].settings["Glow Intensity"] === "number", "应包含强度参数");
    assert(Array.isArray(result[0].settings["Glow Color A"]), "应包含颜色参数");
}

logSection("测试7: map - 风格关键词映射");
{
    const styleRefs: VocabRef[] = [
        { id: "VT-101", name: "边缘发光", matchedKeyword: "赛博朋克", confidence: 0.75 },
        { id: "VT-303", name: "青品色调", matchedKeyword: "赛博朋克", confidence: 0.75 },
    ];

    const description: EffectDescription = {
        effectKeywords: [],
        styleKeywords: styleRefs,
        directionKeywords: [],
        intensityKeywords: [],
        colorKeywords: [],
        temporalKeywords: [],
    };

    const result = parameterMapper.map(description);
    assert(result.length >= 1, "应返回风格映射结果");
}

logSection("测试8: map - 重复matchName去重");
{
    const description: EffectDescription = {
        effectKeywords: [
            { id: "VT-101", name: "边缘发光", matchedKeyword: "发光", confidence: 0.9 },
            { id: "VT-102", name: "强发光", matchedKeyword: "发光", confidence: 0.85 },
        ],
        styleKeywords: [],
        directionKeywords: [],
        intensityKeywords: [],
        colorKeywords: [],
        temporalKeywords: [],
    };

    const result = parameterMapper.map(description);
    const glowMatches = result.filter(r => r.matchName === "ADBE Glo2");
    assert(glowMatches.length === 1, "重复matchName应去重");
}

logSection("测试9: map - 空输入返回空数组");
{
    const description: EffectDescription = {
        effectKeywords: [],
        styleKeywords: [],
        directionKeywords: [],
        intensityKeywords: [],
        colorKeywords: [],
        temporalKeywords: [],
    };

    const result = parameterMapper.map(description);
    assert(result.length === 0, "空描述应返回空数组");
}

logSection("测试10: mapFromMatchName - 通过matchName映射");
{
    const result = parameterMapper.mapFromMatchName("ADBE Glo2");
    assert(result !== null, "应返回映射结果");
    assert(result.matchName === "ADBE Glo2", "matchName应正确");
    assert(Object.keys(result.settings).length > 0, "应包含参数");
}

logSection("测试11: mapFromMatchName - 带修饰词");
{
    const result = parameterMapper.mapFromMatchName("ADBE Glo2", {
        intensity: 2.0,
        color: { rgb: [1, 0, 0] },
        style: "cyberpunk",
    });

    assert(result !== null, "应返回映射结果");
    const intensity = result.settings["Glow Intensity"] as number;
    assert(intensity > 1.5, "强度修饰应生效");
}

logSection("测试12: mapFromMatchName - 未知matchName");
{
    const result = parameterMapper.mapFromMatchName("Unknown Effect");
    assert(result === null, "未知matchName应返回null");
}

logSection("测试13: mapFromEffectName - 通过效果名映射");
{
    const result = parameterMapper.mapFromEffectName("glow");
    assert(result !== null, "应返回映射结果");
    assert(result.matchName === "ADBE Glo2", "matchName应正确");
}

logSection("测试14: mapFromEffectName - 带风格");
{
    const result = parameterMapper.mapFromEffectName("glow", { style: "cyberpunk" });
    assert(result !== null, "应返回映射结果");
}

logSection("测试15: mapFromEffectName - 未知效果名");
{
    const result = parameterMapper.mapFromEffectName("unknown");
    assert(result === null, "未知效果名应返回null");
}

logSection("测试16: getEffectsByCategory - 获取分类效果");
{
    const blurEffects = parameterMapper.getEffectsByCategory("blur_sharpen");
    const colorEffects = parameterMapper.getEffectsByCategory("color_correction");
    
    assert(blurEffects.length >= 1, "模糊类应有效果");
    assert(colorEffects.length >= 1, "颜色校正类应有效果");
}

logSection("测试17: getTotalEffectCount - 获取效果总数");
{
    const count = parameterMapper.getTotalEffectCount();
    assert(count >= 50, "效果总数应 >= 50");
}

logSection("测试18: getEffectInfo - 获取效果信息");
{
    const info = parameterMapper.getEffectInfo("ADBE Glo2");
    assert(info !== null, "应获取到效果信息");
    assert(info.matchName === "ADBE Glo2", "matchName应正确");
    assert(typeof info.displayName === "string", "应有displayName");
}

logSection("测试19: getEffectInfo - 未知效果");
{
    const info = parameterMapper.getEffectInfo("Unknown");
    assert(info === null, "未知效果应返回null");
}

logSection("测试20: searchEffects - 关键词搜索");
{
    const results = parameterMapper.searchEffects("blur");
    assert(results.length > 0, "搜索blur应有结果");
    assert(results.some(r => r.toLowerCase().includes("blur")), "结果应包含blur");
}

logSection("测试21: searchEffects - 中文关键词");
{
    const results = parameterMapper.searchEffects("发光");
    assert(results.length > 0, "搜索发光应有结果");
}

logSection("测试22: searchEffects - 无结果");
{
    const results = parameterMapper.searchEffects("nonexistent-keyword-xyz");
    assert(results.length === 0, "无匹配应返回空数组");
}

logSection("测试23: getTemplate - 获取模板");
{
    const template = parameterMapper.getTemplate("VT-101");
    assert(template !== undefined, "应获取到模板");
    assert(template.matchName === "ADBE Glo2", "matchName应正确");
    assert(Object.keys(template.defaultSettings).length > 0, "应有默认参数");
}

logSection("测试24: getTemplate - 未知模板");
{
    const template = parameterMapper.getTemplate("VT-999");
    assert(template === undefined, "未知模板应返回undefined");
}

logSection("测试25: listAvailableEffects - 获取可用效果列表");
{
    const effects = parameterMapper.listAvailableEffects();
    assert(effects.length >= 5, "应至少有5个可用效果");
    assert(effects.includes("VT-101"), "应包含VT-101");
}

logSection("测试26: listAllEffects - 获取所有效果列表");
{
    const effects = parameterMapper.listAllEffects();
    assert(effects.length >= 50, "应至少有50个效果");
}

logSection("测试27: setContext - 设置上下文");
{
    const mapper = new ParameterMapper();
    mapper.setContext({
        compWidth: 1920,
        compHeight: 1080,
        frameRate: 30,
        duration: 10,
    });
    assert(true, "设置上下文不应报错");
}

logSection("测试28: 参数范围约束 - 超过最大值");
{
    const intensityRefs: IntensityRef[] = [
        { keyword: "极端", level: "extreme", scale: 3.0 },
    ];

    const description: EffectDescription = {
        effectKeywords: [{ id: "VT-101", name: "边缘发光", matchedKeyword: "发光", confidence: 0.9 }],
        styleKeywords: [],
        directionKeywords: [],
        intensityKeywords: intensityRefs,
        colorKeywords: [],
        temporalKeywords: [],
    };

    const result = parameterMapper.map(description);
    const intensity = result[0].settings["Glow Intensity"] as number;
    assert(intensity <= 10, "Glow Intensity应被限制在最大值10以内");
}

logSection("测试29: 参数范围约束 - 低于最小值");
{
    const intensityRefs: IntensityRef[] = [
        { keyword: "微弱", level: "subtle", scale: 0.1 },
    ];

    const description: EffectDescription = {
        effectKeywords: [{ id: "VT-101", name: "边缘发光", matchedKeyword: "发光", confidence: 0.9 }],
        styleKeywords: [],
        directionKeywords: [],
        intensityKeywords: intensityRefs,
        colorKeywords: [],
        temporalKeywords: [],
    };

    const result = parameterMapper.map(description);
    const intensity = result[0].settings["Glow Intensity"] as number;
    assert(intensity >= 0, "Glow Intensity应被限制在最小值0以上");
}

logSection("测试30: 粒子效果映射 - VT-401");
{
    const description: EffectDescription = {
        effectKeywords: [{ id: "VT-401", name: "火焰粒子", matchedKeyword: "粒子", confidence: 0.9 }],
        styleKeywords: [],
        directionKeywords: [],
        intensityKeywords: [],
        colorKeywords: [],
        temporalKeywords: [],
    };

    const result = parameterMapper.map(description);
    assert(result.length > 0, "应返回映射结果");
    assert(result[0].matchName === "CC Particle World", "matchName应为CC Particle World");
    assert(typeof result[0].settings["Birth Rate"] === "number", "应包含Birth Rate参数");
}

console.log("\n========================================");
console.log(` 测试结果: ${passCount} 通过 / ${failCount} 失败 / ${passCount + failCount} 总计`);
console.log("========================================");

process.exit(failCount > 0 ? 1 : 0);