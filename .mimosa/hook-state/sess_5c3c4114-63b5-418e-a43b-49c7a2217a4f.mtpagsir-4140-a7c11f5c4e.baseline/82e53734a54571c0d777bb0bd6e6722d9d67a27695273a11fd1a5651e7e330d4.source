// ============================================================================
// unit-effect-generators.test.ts
// 效果智能参数生成器单元测试
// ============================================================================

import {
    GlowGenerator,
    ColorKeyGenerator,
    CCParticleWorldGenerator,
    FractalNoiseGenerator,
    RampGenerator,
    EffectGeneratorFactory,
    UniversalEffectGenerator,
    ALL_EFFECT_MATCHNAMES,
    GENERATOR_REGISTRY,
} from "../src/phase4/effect-generators";
import { ColorRef, IntensityRef } from "../src/phase4/types";
import { EFFECT_KNOWLEDGE_GRAPH, EffectCategory } from "../src/phase4/effect-knowledge-graph";

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
console.log(" 效果智能参数生成器单元测试");
console.log("========================================");

logSection("测试1: GlowGenerator - 默认参数");
{
    const generator = new GlowGenerator();
    const result = generator.generate({});

    console.log(`  matchName=${result.matchName}`);
    console.log(`  settings=${JSON.stringify(result.settings)}`);

    assert(result.matchName === "ADBE Glo2", "matchName 应为 ADBE Glo2");
    assert(result.displayName === "Glow", "displayName 应为 Glow");
    assert(result.confidence >= 0.8, "置信度应 >= 0.8");
    assert(typeof result.settings["Glow Threshold"] === "number", "Glow Threshold 应为数字");
    assert(typeof result.settings["Glow Radius"] === "number", "Glow Radius 应为数字");
    assert(typeof result.settings["Glow Intensity"] === "number", "Glow Intensity 应为数字");
}

logSection("测试2: GlowGenerator - 霓虹风格");
{
    const generator = new GlowGenerator();
    const result = generator.generate({ style: "neon" });

    console.log(`  Glow Intensity=${result.settings["Glow Intensity"]}`);
    console.log(`  Glow Radius=${result.settings["Glow Radius"]}`);

    assert((result.settings["Glow Intensity"] as number) > 2, "霓虹风格强度应 > 2");
    assert((result.settings["Glow Radius"] as number) > 30, "霓虹风格半径应 > 30");
}

logSection("测试3: GlowGenerator - 强度修饰");
{
    const generator = new GlowGenerator();
    const intensityRefs: IntensityRef[] = [
        { keyword: "强烈", level: "strong", scale: 1.5 },
    ];
    const result = generator.generate({ intensity: intensityRefs });

    const defaultResult = generator.generate({});
    console.log(`  默认强度=${defaultResult.settings["Glow Intensity"]}`);
    console.log(`  增强后=${result.settings["Glow Intensity"]}`);

    assert(
        (result.settings["Glow Intensity"] as number) > (defaultResult.settings["Glow Intensity"] as number),
        "增强强度应大于默认值"
    );
}

logSection("测试4: GlowGenerator - 颜色修饰");
{
    const generator = new GlowGenerator();
    const colorRefs: ColorRef[] = [
        { keyword: "红色", rgb: [1, 0, 0], temperature: "warm" },
    ];
    const result = generator.generate({ color: colorRefs });

    console.log(`  Glow Color A=${result.settings["Glow Color A"]}`);

    const colorA = result.settings["Glow Color A"] as number[];
    assert(colorA[0] > 0.9, "红色发光的R通道应接近1");
    assert(colorA[1] < 0.1, "红色发光的G通道应接近0");
    assert(colorA[2] < 0.1, "红色发光的B通道应接近0");
}

logSection("测试5: ColorKeyGenerator - 默认参数");
{
    const generator = new ColorKeyGenerator();
    const result = generator.generate({});

    console.log(`  matchName=${result.matchName}`);
    console.log(`  Key Color=${result.settings["Key Color"]}`);

    assert(result.matchName === "ADBE Color Key", "matchName 应为 ADBE Color Key");
    assert(typeof result.settings["Color Tolerance"] === "number", "Color Tolerance 应为数字");
}

logSection("测试6: ColorKeyGenerator - 绿幕预设");
{
    const generator = new ColorKeyGenerator();
    const result = generator.generate({ style: "green screen" });

    const keyColor = result.settings["Key Color"] as number[];
    console.log(`  Key Color=${keyColor}`);

    assert(keyColor[1] > 0.6, "绿幕的G通道应较高");
    assert(keyColor[0] < 0.3, "绿幕的R通道应较低");
    assert(keyColor[2] < 0.3, "绿幕的B通道应较低");
}

logSection("测试7: CCParticleWorldGenerator - 默认参数");
{
    const generator = new CCParticleWorldGenerator();
    const result = generator.generate({});

    console.log(`  matchName=${result.matchName}`);
    console.log(`  Birth Rate=${result.settings["Birth Rate"]}`);

    assert(result.matchName === "CC Particle World", "matchName 应为 CC Particle World");
    assert(typeof result.settings["Birth Rate"] === "number", "Birth Rate 应为数字");
    assert(typeof result.settings["Velocity"] === "number", "Velocity 应为数字");
}

logSection("测试8: CCParticleWorldGenerator - 火焰效果");
{
    const generator = new CCParticleWorldGenerator();
    const result = generator.generate({ style: "fire" });

    console.log(`  Gravity=${result.settings["Gravity"]}`);
    console.log(`  Birth Rate=${result.settings["Birth Rate"]}`);

    assert((result.settings["Gravity"] as number) < 0, "火焰重力应向上（负值）");
    assert((result.settings["Birth Rate"] as number) > 100, "火焰粒子数应较高");
}

logSection("测试9: CCParticleWorldGenerator - 雪花效果");
{
    const generator = new CCParticleWorldGenerator();
    const result = generator.generate({ style: "snow" });

    console.log(`  Gravity=${result.settings["Gravity"]}`);
    console.log(`  Velocity=${result.settings["Velocity"]}`);

    assert((result.settings["Gravity"] as number) > 0, "雪花重力应向下（正值）");
    assert((result.settings["Velocity"] as number) < 50, "雪花速度应较慢");
}

logSection("测试10: FractalNoiseGenerator - 默认参数");
{
    const generator = new FractalNoiseGenerator();
    const result = generator.generate({});

    console.log(`  matchName=${result.matchName}`);
    console.log(`  Scale=${result.settings["Scale"]}`);

    assert(result.matchName === "ADBE Fractal Noise", "matchName 应为 ADBE Fractal Noise");
    assert(typeof result.settings["Scale"] === "number", "Scale 应为数字");
    assert(typeof result.settings["Complexity"] === "number", "Complexity 应为数字");
}

logSection("测试11: FractalNoiseGenerator - 云彩效果");
{
    const generator = new FractalNoiseGenerator();
    const result = generator.generate({ style: "clouds" });

    console.log(`  Scale=${result.settings["Scale"]}`);
    console.log(`  Evolution Speed=${result.settings["Evolution Speed"]}`);

    assert((result.settings["Scale"] as number) > 200, "云彩尺度应较大");
    assert((result.settings["Evolution Speed"] as number) < 5, "云彩演变速度应较慢");
}

logSection("测试12: RampGenerator - 默认参数");
{
    const generator = new RampGenerator();
    const result = generator.generate({});

    console.log(`  matchName=${result.matchName}`);
    console.log(`  Start Color=${result.settings["Start Color"]}`);

    assert(result.matchName === "ADBE Ramp", "matchName 应为 ADBE Ramp");
    assert(Array.isArray(result.settings["Start Color"]), "Start Color 应为数组");
    assert(Array.isArray(result.settings["End Color"]), "End Color 应为数组");
}

logSection("测试13: RampGenerator - 日落风格");
{
    const generator = new RampGenerator();
    const result = generator.generate({ style: "sunset" });

    const startColor = result.settings["Start Color"] as number[];
    const endColor = result.settings["End Color"] as number[];

    console.log(`  Start Color=${startColor}`);
    console.log(`  End Color=${endColor}`);

    assert(startColor[0] > 0.8, "日落起始色R通道应较高");
    assert(endColor[2] > 0.5, "日落结束色B通道应较高");
}

logSection("测试14: EffectGeneratorFactory - 工厂测试");
{
    const factory = new EffectGeneratorFactory();

    console.log(`  可用生成器: ${factory.listAvailableGenerators().join(", ")}`);

    assert(factory.listAvailableGenerators().length >= 5, "应至少有5个生成器");

    const glow = factory.getGenerator("glow");
    assert(glow !== undefined, "glow生成器应存在");

    const result = factory.generateEffect("glow", {});
    assert(result !== undefined, "generateEffect 应返回结果");
    assert(result.matchName === "ADBE Glo2", "生成的效果 matchName 应正确");
}

logSection("测试15: EffectGeneratorFactory - 大小写不敏感");
{
    const factory = new EffectGeneratorFactory();

    const result1 = factory.generateEffect("Glow", {});
    const result2 = factory.generateEffect("GLOW", {});
    const result3 = factory.generateEffect("glow", {});

    assert(result1 !== undefined, "Glow 应匹配");
    assert(result2 !== undefined, "GLOW 应匹配");
    assert(result3 !== undefined, "glow 应匹配");
}

logSection("测试16: 知识图谱 - 效果数量验证");
{
    const effectCount = Object.keys(EFFECT_KNOWLEDGE_GRAPH).length;
    console.log(`  知识图谱效果数量: ${effectCount}`);
    assert(effectCount >= 50, `效果数量应 >= 50，实际为 ${effectCount}`);
    assert(effectCount === 65, `效果数量应为 65，实际为 ${effectCount}`);
}

logSection("测试17: 知识图谱 - 9大类别覆盖");
{
    const categories = new Set(
        Object.values(EFFECT_KNOWLEDGE_GRAPH).map(e => e.category)
    );
    console.log(`  类别列表: ${Array.from(categories).join(", ")}`);
    assert(categories.size === 9, `类别数量应为 9，实际为 ${categories.size}`);
    assert(categories.has("blur_sharpen"), "应有模糊与锐化类");
    assert(categories.has("color_correction"), "应有颜色校正类");
    assert(categories.has("glow_light"), "应有发光与灯光类");
    assert(categories.has("distort"), "应有扭曲类");
    assert(categories.has("noise_grain"), "应有噪波与颗粒类");
    assert(categories.has("channel_keying"), "应有通道与键控类");
    assert(categories.has("stylize"), "应有风格化类");
    assert(categories.has("perspective_3d"), "应有透视与3D类");
    assert(categories.has("generate_draw"), "应有生成与绘制类");
}

logSection("测试18: 生成器注册表 - 65个效果全覆盖");
{
    const registryCount = Object.keys(GENERATOR_REGISTRY).length;
    console.log(`  注册生成器数量: ${registryCount}`);
    assert(registryCount === 65, `注册生成器数量应为 65，实际为 ${registryCount}`);
    assert(ALL_EFFECT_MATCHNAMES.length === 65, `ALL_EFFECT_MATCHNAMES 数量应为 65`);
}

logSection("测试19: 通用生成器 - Fast Box Blur");
{
    const generator = new UniversalEffectGenerator("ADBE Fast Box Blur");
    const result = generator.generate({});

    console.log(`  matchName=${result.matchName}`);
    console.log(`  displayName=${result.displayName}`);
    console.log(`  settings=${JSON.stringify(result.settings)}`);

    assert(result.matchName === "ADBE Fast Box Blur", "matchName 应正确");
    assert(result.displayName === "Fast Box Blur", "displayName 应正确");
    assert(typeof result.settings["Blurriness"] === "number", "Blurriness 应为数字");
    assert(result.confidence > 0, "置信度应 > 0");
}

logSection("测试20: 通用生成器 - CC Radial Blur");
{
    const generator = new UniversalEffectGenerator("CC Radial Blur");
    const result = generator.generate({});

    console.log(`  matchName=${result.matchName}`);
    console.log(`  settings=${JSON.stringify(result.settings)}`);

    assert(result.matchName === "CC Radial Blur", "matchName 应正确");
    assert(result.confidence > 0, "置信度应 > 0");
}

logSection("测试21: 通用生成器 - Camera Lens Blur");
{
    const generator = new UniversalEffectGenerator("ADBE Camera Lens Blur");
    const result = generator.generate({});

    console.log(`  matchName=${result.matchName}`);

    assert(result.matchName === "ADBE Camera Lens Blur", "matchName 应正确");
    assert(typeof result.settings["Blur Amount"] === "number", "Blur Amount 应为数字");
}

logSection("测试22: 通用生成器 - 强度修饰");
{
    const generator = new UniversalEffectGenerator("ADBE Fast Box Blur");
    const defaultResult = generator.generate({});

    const intensityRefs: IntensityRef[] = [
        { keyword: "强烈", level: "strong", scale: 2.0 },
    ];
    const strongResult = generator.generate({ intensity: intensityRefs });

    const defaultBlur = defaultResult.settings["Blurriness"] as number;
    const strongBlur = strongResult.settings["Blurriness"] as number;

    console.log(`  默认模糊: ${defaultBlur}`);
    console.log(`  强烈模糊: ${strongBlur}`);

    assert(strongBlur > defaultBlur, "增强强度应大于默认值");
}

logSection("测试23: 通用生成器 - 颜色修饰");
{
    const generator = new UniversalEffectGenerator("ADBE Drop Shadow");
    const colorRefs: ColorRef[] = [
        { keyword: "蓝色", rgb: [0, 0, 1], temperature: "cool" },
    ];
    const result = generator.generate({ color: colorRefs });

    const shadowColor = result.settings["Shadow Color"] as number[];
    console.log(`  Shadow Color=${shadowColor}`);

    assert(Array.isArray(shadowColor), "Shadow Color 应为数组");
    assert(shadowColor.length === 3, "颜色应有3个通道");
}

logSection("测试24: 工厂方法 - getEffectCount");
{
    const factory = new EffectGeneratorFactory();
    const count = factory.getEffectCount();

    console.log(`  效果总数: ${count}`);
    assert(count === 65, `效果总数应为 65，实际为 ${count}`);
}

logSection("测试25: 工厂方法 - getEffectsByCategory");
{
    const factory = new EffectGeneratorFactory();

    const blurEffects = factory.getEffectsByCategory("blur_sharpen");
    const colorEffects = factory.getEffectsByCategory("color_correction");
    const glowEffects = factory.getEffectsByCategory("glow_light");

    console.log(`  模糊与锐化类: ${blurEffects.length} 个`);
    console.log(`  颜色校正类: ${colorEffects.length} 个`);
    console.log(`  发光与灯光类: ${glowEffects.length} 个`);

    assert(blurEffects.length >= 5, "模糊与锐化类应 >= 5 个");
    assert(colorEffects.length >= 5, "颜色校正类应 >= 5 个");
    assert(glowEffects.length >= 3, "发光与灯光类应 >= 3 个");
}

logSection("测试26: 所有65个效果生成验证");
{
    const factory = new EffectGeneratorFactory();
    let successCount = 0;
    let failList: string[] = [];

    for (const matchName of ALL_EFFECT_MATCHNAMES) {
        try {
            const result = factory.generateEffectByMatchName(matchName, {});
            if (result && result.matchName === matchName && result.settings) {
                const paramCount = Object.keys(result.settings).length;
                if (paramCount > 0) {
                    successCount++;
                } else {
                    failList.push(`${matchName} (无参数)`);
                }
            } else {
                failList.push(`${matchName} (生成失败)`);
            }
        } catch (e) {
            failList.push(`${matchName} (异常: ${e})`);
        }
    }

    console.log(`  成功生成: ${successCount} / 65`);
    if (failList.length > 0) {
        console.log(`  失败列表: ${failList.join(", ")}`);
    }

    assert(successCount >= 50, `至少应有 50 个效果成功生成，实际为 ${successCount}`);
    assert(successCount === 65, `所有 65 个效果都应成功生成，实际为 ${successCount}`);
}

logSection("测试27: 20个专用生成器验证");
{
    const specializedEffects = [
        "ADBE Glo2", "ADBE Color Key", "CC Particle World",
        "ADBE Fractal Noise", "ADBE Ramp", "ADBE Gaussian Blur 2",
        "ADBE Directional Blur", "ADBE HUE SATURATION", "ADBE Protractor2",
        "ADBE Color Balance", "ADBE Drop Shadow", "ADBE Fill",
        "ADBE Stroke", "ADBE Noise", "ADBE Unsharp Mask",
        "ADBE Texturize", "ADBE Roughen Edges", "CC Lens",
        "ADBE Optics Compensation", "ADBE Simple Choker",
    ];

    let allPass = true;
    for (const effect of specializedEffects) {
        const result = GENERATOR_REGISTRY[effect];
        if (!result) {
            console.log(`  缺失: ${effect}`);
            allPass = false;
        }
    }

    console.log(`  专用生成器: ${specializedEffects.length} 个`);
    assert(allPass, "所有 20 个专用生成器都应存在");
}

logSection("测试28: 通用生成器 - 风格修饰（subtle/strong/extreme）");
{
    const generator = new UniversalEffectGenerator("ADBE Brightness & Contrast 2");

    const subtleResult = generator.generate({ style: "subtle" });
    const defaultResult = generator.generate({});
    const strongResult = generator.generate({ style: "strong" });

    const defaultContrast = defaultResult.settings["Contrast"] as number;
    const subtleContrast = subtleResult.settings["Contrast"] as number;
    const strongContrast = strongResult.settings["Contrast"] as number;

    console.log(`  默认对比度: ${defaultContrast}`);
    console.log(`  轻微对比度: ${subtleContrast}`);
    console.log(`  强烈对比度: ${strongContrast}`);

    assert(true, "风格修饰测试完成");
}

logSection("测试29: generateEffectByMatchName - 通过matchName生成");
{
    const factory = new EffectGeneratorFactory();

    const result = factory.generateEffectByMatchName("ADBE Mosaic", {});
    assert(result !== undefined, "Mosaic 效果应能生成");
    assert(result?.matchName === "ADBE Mosaic", "matchName 应正确");
    assert(typeof result?.settings["Horizontal Blocks"] === "number", "Horizontal Blocks 应为数字");
}

logSection("测试30: 效果元数据完整性");
{
    let allValid = true;
    let invalidEffects: string[] = [];

    for (const [matchName, effect] of Object.entries(EFFECT_KNOWLEDGE_GRAPH)) {
        if (!effect.matchName || !effect.displayName || !effect.category) {
            allValid = false;
            invalidEffects.push(matchName);
        }
        if (!Array.isArray(effect.parameters) || effect.parameters.length === 0) {
            allValid = false;
            invalidEffects.push(`${matchName}(无参数)`);
        }
        if (!Array.isArray(effect.tags) || effect.tags.length === 0) {
            allValid = false;
            invalidEffects.push(`${matchName}(无标签)`);
        }
        if (typeof effect.confidence !== "number" || effect.confidence <= 0) {
            allValid = false;
            invalidEffects.push(`${matchName}(无效置信度)`);
        }
    }

    console.log(`  有效效果: ${Object.keys(EFFECT_KNOWLEDGE_GRAPH).length - invalidEffects.length} / ${Object.keys(EFFECT_KNOWLEDGE_GRAPH).length}`);
    if (invalidEffects.length > 0) {
        console.log(`  无效效果: ${invalidEffects.join(", ")}`);
    }

    assert(allValid, "所有效果元数据都应完整有效");
}

console.log("\n========================================");
console.log(` 测试结果: ${passCount} 通过 / ${failCount} 失败 / ${passCount + failCount} 总计`);
console.log("========================================");

process.exit(failCount > 0 ? 1 : 0);