// ============================================================================
// unit-effect-description-parser.test.ts
// 效果描述解析器单元测试 - 覆盖词汇扫描、分类提取、风格配方加载
// ============================================================================

import { EffectDescriptionParser, effectDescriptionParser, getStyleRecipe, getAllStyles, getStats } from "../src/phase4/effect-description-parser";
import { IntentType } from "../src/phase4/types";

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
console.log(" 效果描述解析器单元测试");
console.log("========================================");

logSection("测试1: EffectDescriptionParser实例创建");
{
    const parser = new EffectDescriptionParser();
    assert(parser !== undefined, "解析器应能创建");
}

logSection("测试2: 空输入返回空结果");
{
    const result = effectDescriptionParser.parse("");
    assert(result.effectKeywords.length === 0, "效果关键词应为空");
    assert(result.colorKeywords.length === 0, "颜色关键词应为空");
    assert(result.intensityKeywords.length === 0, "强度关键词应为空");
    assert(result.temporalKeywords.length === 0, "时间关键词应为空");
    assert(result.styleKeywords.length === 0, "风格关键词应为空");
    assert(result.directionKeywords.length === 0, "方向关键词应为空");
}

logSection("测试3: 模糊类效果关键词提取");
{
    const testCases = [
        "加一个高斯模糊",
        "柔和模糊",
        "motion blur",
        "做一个方向模糊",
    ];

    for (const input of testCases) {
        const result = effectDescriptionParser.parse(input);
        assert(result.effectKeywords.length > 0, `输入"${input}"应提取效果关键词`);
    }
}

logSection("测试4: 发光类效果关键词提取");
{
    const testCases = [
        "加一个发光",
        "霓虹效果",
        "边缘发光",
        "辉光",
    ];

    for (const input of testCases) {
        const result = effectDescriptionParser.parse(input);
        assert(result.effectKeywords.length > 0, `输入"${input}"应提取效果关键词`);
    }
}

logSection("测试5: 颜色关键词提取");
{
    const testCases = [
        { input: "红色发光", hasColor: true },
        { input: "蓝色模糊", hasColor: true },
        { input: "warm glow", hasColor: true },
        { input: "青色粒子", hasColor: true },
        { input: "紫色渐变", hasColor: true },
    ];

    for (const { input, hasColor } of testCases) {
        const result = effectDescriptionParser.parse(input);
        assert(result.colorKeywords.length > 0 === hasColor, `输入"${input}"颜色提取应正确`);
        if (hasColor) {
            assert(result.colorKeywords[0].rgb.length === 3, "颜色RGB应包含3个通道");
        }
    }
}

logSection("测试6: 强度关键词提取");
{
    const testCases = [
        { input: "强烈发光", expectIntensity: true },
        { input: "柔和模糊", expectIntensity: true },
        { input: "extreme glow", expectIntensity: true },
        { input: "subtle blur", expectIntensity: true },
        { input: "中等强度", expectIntensity: true },
    ];

    for (const { input, expectIntensity } of testCases) {
        const result = effectDescriptionParser.parse(input);
        if (expectIntensity) {
            assert(result.intensityKeywords.length > 0, `输入"${input}"应提取强度关键词`);
            if (result.intensityKeywords.length > 0) {
                assert(result.intensityKeywords[0].scale > 0, "强度缩放因子应大于0");
            }
        }
    }
}

logSection("测试7: 时间关键词提取");
{
    const testCases = [
        "开头淡入",
        "结尾淡出",
        "持续3秒",
        "at start",
        "end of clip",
    ];

    for (const input of testCases) {
        const result = effectDescriptionParser.parse(input);
        assert(result.temporalKeywords.length > 0, `输入"${input}"应提取时间关键词`);
    }
}

logSection("测试8: 方向关键词提取");
{
    const testCases = [
        { input: "向上移动", directions: ["up"] },
        { input: "向左模糊", directions: ["left"] },
        { input: "向外辐射", directions: ["out"] },
        { input: "inward glow", directions: ["in"] },
        { input: "向右向上", directions: ["right", "up"] },
    ];

    for (const { input, directions } of testCases) {
        const result = effectDescriptionParser.parse(input);
        assert(result.directionKeywords.length === directions.length, `输入"${input}"方向数量应正确`);
        for (const dir of directions) {
            assert(result.directionKeywords.includes(dir), `应包含方向"${dir}"`);
        }
    }
}

logSection("测试9: 风格配方加载 - 赛博朋克");
{
    const result = effectDescriptionParser.parse("做赛博朋克风格", IntentType.STYLE_COMBO);
    assert(result.styleKeywords.length > 0, "应加载风格配方");
    assert(result.styleKeywords.some(k => k.id === "VT-101"), "应包含边缘发光");
    assert(result.styleKeywords.some(k => k.id === "VT-303"), "应包含青品色调");
}

logSection("测试10: 风格配方加载 - 电影感");
{
    const result = effectDescriptionParser.parse("做电影感", IntentType.STYLE_COMBO);
    assert(result.styleKeywords.length > 0, "应加载风格配方");
}

logSection("测试11: 风格配方加载 - 梦幻");
{
    const result = effectDescriptionParser.parse("梦幻风格", IntentType.STYLE_COMBO);
    assert(result.styleKeywords.length > 0, "应加载风格配方");
}

logSection("测试12: 非STYLE_COMBO意图不加载风格配方");
{
    const result = effectDescriptionParser.parse("做赛博朋克风格", IntentType.ADD_EFFECT);
    assert(result.styleKeywords.length === 0, "非STYLE_COMBO意图不应加载风格配方");
}

logSection("测试13: getStyleRecipe - 获取风格配方");
{
    const recipe = getStyleRecipe("赛博朋克");
    assert(recipe !== undefined, "应获取到赛博朋克配方");
    assert(recipe.effectIds.length > 0, "配方应包含效果ID");
    assert(typeof recipe.description === "string", "配方应有描述");
}

logSection("测试14: getStyleRecipe - 大小写不敏感");
{
    const recipe1 = getStyleRecipe("CYBERPUNK");
    const recipe2 = getStyleRecipe("Cyberpunk");
    const recipe3 = getStyleRecipe("cyberpunk");
    
    assert(recipe1 !== undefined, "全大写应获取到配方");
    assert(recipe2 !== undefined, "首字母大写应获取到配方");
    assert(recipe3 !== undefined, "全小写应获取到配方");
}

logSection("测试15: getStyleRecipe - 未知风格");
{
    const recipe = getStyleRecipe("未知风格");
    assert(recipe === undefined, "未知风格应返回undefined");
}

logSection("测试16: getAllStyles - 获取所有风格");
{
    const styles = getAllStyles();
    assert(styles.length >= 5, "应至少有5种风格");
    assert(styles.includes("赛博朋克"), "应包含赛博朋克");
    assert(styles.includes("电影感"), "应包含电影感");
    assert(styles.includes("梦幻"), "应包含梦幻");
}

logSection("测试17: 多修饰词组合");
{
    const result = effectDescriptionParser.parse("给文字加一个强烈的红色发光");
    assert(result.effectKeywords.length > 0, "应提取效果关键词");
    assert(result.colorKeywords.length > 0, "应提取颜色关键词");
    assert(result.intensityKeywords.length > 0, "应提取强度关键词");
}

logSection("测试18: 中英文混合输入");
{
    const result = effectDescriptionParser.parse("add a red glow");
    assert(result.effectKeywords.length > 0, "应提取效果关键词");
    assert(result.colorKeywords.length > 0, "应提取颜色关键词");
}

logSection("测试19: 特殊字符处理");
{
    const result = effectDescriptionParser.parse("✨发光 🌟");
    assert(result.effectKeywords.length > 0, "应能处理特殊字符");
}

logSection("测试20: getStats - 获取词汇统计");
{
    const stats = getStats();
    assert(stats !== undefined, "应返回统计信息");
}

logSection("测试21: 词汇分类 - VT前缀分类");
{
    const result = effectDescriptionParser.parse("加一个发光");
    for (const kw of result.effectKeywords) {
        assert(kw.id.startsWith("VT-") || kw.id.startsWith("KF-"), "词汇ID应符合规范");
    }
}

logSection("测试22: 词汇分类 - 颜色类VT-3xx");
{
    const result = effectDescriptionParser.parse("青品色调");
    assert(result.colorKeywords.length > 0, "颜色类词汇应归入colorKeywords");
}

logSection("测试23: 空字符串安全处理");
{
    const result = effectDescriptionParser.parse("   ");
    assert(result.effectKeywords.length === 0, "空白字符串应返回空结果");
}

logSection("测试24: 重复词汇去重");
{
    const result = effectDescriptionParser.parse("发光发光发光");
    const glowKeywords = result.effectKeywords.filter(k => k.matchedKeyword.includes("发光"));
    assert(glowKeywords.length <= 2, "重复关键词不应过度提取");
}

console.log("\n========================================");
console.log(` 测试结果: ${passCount} 通过 / ${failCount} 失败 / ${passCount + failCount} 总计`);
console.log("========================================");

process.exit(failCount > 0 ? 1 : 0);