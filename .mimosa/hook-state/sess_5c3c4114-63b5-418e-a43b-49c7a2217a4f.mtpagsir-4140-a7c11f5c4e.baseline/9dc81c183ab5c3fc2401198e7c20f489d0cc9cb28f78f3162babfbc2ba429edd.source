// ============================================================================
// unit-param-optimizer.test.ts
// 参数优化器单元测试
// ============================================================================

import { ParameterOptimizer } from "../src/phase4/param-optimizer";
import { EffectParams } from "../src/phase4/effect-generators";

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
console.log(" 参数优化器单元测试");
console.log("========================================");

logSection("测试1: Glow参数边界约束");
{
    const optimizer = new ParameterOptimizer();
    const input: EffectParams = {
        matchName: "ADBE Glo2",
        displayName: "Glow",
        settings: {
            "Glow Threshold": 150,
            "Glow Radius": -10,
            "Glow Intensity": 15,
        },
        confidence: 0.85,
    };

    const result = optimizer.optimize(input);
    console.log(`  优化前: ${JSON.stringify(input.settings)}`);
    console.log(`  优化后: ${JSON.stringify(result.optimizedParams.settings)}`);

    assert(
        (result.optimizedParams.settings["Glow Threshold"] as number) <= 100,
        "Glow Threshold 应被限制在最大100"
    );
    assert(
        (result.optimizedParams.settings["Glow Radius"] as number) >= 0,
        "Glow Radius 应被限制在最小0"
    );
    assert(
        (result.optimizedParams.settings["Glow Intensity"] as number) <= 10,
        "Glow Intensity 应被限制在最大10"
    );
    assert(result.changes.length > 0, "应有参数调整记录");
}

logSection("测试2: Glow参数冲突检测");
{
    const optimizer = new ParameterOptimizer();
    const input: EffectParams = {
        matchName: "ADBE Glo2",
        displayName: "Glow",
        settings: {
            "Glow Radius": 160,
            "Glow Intensity": 6,
            "Glow Threshold": 40,
        },
        confidence: 0.85,
    };

    const result = optimizer.optimize(input);
    console.log(`  警告: ${result.warnings.join(", ")}`);

    assert(result.warnings.length > 0, "应检测到参数冲突警告");
    assert(
        (result.optimizedParams.settings["Glow Intensity"] as number) <= 4,
        "Glow Intensity 应被降低以解决冲突"
    );
}

logSection("测试3: Glow最佳实践应用");
{
    const optimizer = new ParameterOptimizer();
    const input: EffectParams = {
        matchName: "ADBE Glo2",
        displayName: "Glow",
        settings: {
            "Glow Intensity": 4,
            "Glow Threshold": 15,
            "Glow Radius": 30,
        },
        confidence: 0.85,
    };

    const result = optimizer.optimize(input);
    console.log(`  调整记录: ${result.changes.map(c => `${c.paramName}: ${c.oldValue}→${c.newValue}`).join(", ")}`);

    assert(result.changes.length > 0, "应有参数调整");
    const thresholdChange = result.changes.find(c => c.paramName === "Glow Threshold");
    assert(thresholdChange !== undefined, "应调整 Glow Threshold");
    assert(
        (thresholdChange.newValue as number) >= 25,
        "高强度发光需要提高阈值"
    );
}

logSection("测试4: Color Key参数边界约束");
{
    const optimizer = new ParameterOptimizer();
    const input: EffectParams = {
        matchName: "ADBE Color Key",
        displayName: "Color Key",
        settings: {
            "Color Tolerance": 150,
            "Edge Feather": 15,
            "Edge Thin": 10,
            "Edge Contrast": -5,
        },
        confidence: 0.80,
    };

    const result = optimizer.optimize(input);

    assert(
        (result.optimizedParams.settings["Color Tolerance"] as number) <= 100,
        "Color Tolerance 应被限制在最大100"
    );
    assert(
        (result.optimizedParams.settings["Edge Feather"] as number) <= 10,
        "Edge Feather 应被限制在最大10"
    );
    assert(
        (result.optimizedParams.settings["Edge Thin"] as number) <= 5,
        "Edge Thin 应被限制在最大5"
    );
    assert(
        (result.optimizedParams.settings["Edge Contrast"] as number) >= 0,
        "Edge Contrast 应被限制在最小0"
    );
}

logSection("测试5: CC Particle World性能优化");
{
    const optimizer = new ParameterOptimizer({ performanceMode: true, maxParticles: 300 });
    const input: EffectParams = {
        matchName: "CC Particle World",
        displayName: "CC Particle World",
        settings: {
            "Birth Rate": 500,
            "Longevity": 3.0,
            "Velocity": 100,
            "Gravity": 50,
            "Particle Radius": 10,
        },
        confidence: 0.82,
    };

    const result = optimizer.optimize(input);
    console.log(`  警告: ${result.warnings.join(", ")}`);
    console.log(`  调整记录: ${result.changes.map(c => `${c.paramName}: ${c.oldValue}→${c.newValue}`).join(", ")}`);

    assert(result.warnings.length > 0, "应检测到性能警告");
    assert(
        (result.optimizedParams.settings["Birth Rate"] as number) < 500,
        "Birth Rate 应被降低"
    );
}

logSection("测试6: 风格规范应用 - 赛博朋克");
{
    const optimizer = new ParameterOptimizer({ targetStyle: "cyberpunk" });
    const input: EffectParams = {
        matchName: "ADBE Glo2",
        displayName: "Glow",
        settings: {
            "Glow Threshold": 40,
            "Glow Radius": 25,
            "Glow Intensity": 1.5,
        },
        confidence: 0.85,
    };

    const result = optimizer.optimize(input);
    console.log(`  优化后强度: ${result.optimizedParams.settings["Glow Intensity"]}`);

    assert(
        (result.optimizedParams.settings["Glow Intensity"] as number) >= 2.5,
        "赛博朋克风格需要更高强度"
    );
}

logSection("测试7: 风格规范应用 - 梦幻");
{
    const optimizer = new ParameterOptimizer({ targetStyle: "dreamy" });
    const input: EffectParams = {
        matchName: "ADBE Glo2",
        displayName: "Glow",
        settings: {
            "Glow Threshold": 40,
            "Glow Radius": 40,
            "Glow Intensity": 3.0,
        },
        confidence: 0.85,
    };

    const result = optimizer.optimize(input);
    console.log(`  优化后强度: ${result.optimizedParams.settings["Glow Intensity"]}`);

    assert(
        (result.optimizedParams.settings["Glow Intensity"] as number) <= 1.5,
        "梦幻风格需要柔和发光"
    );
}

logSection("测试8: 优化评分计算");
{
    const optimizer = new ParameterOptimizer();
    const input: EffectParams = {
        matchName: "ADBE Glo2",
        displayName: "Glow",
        settings: {
            "Glow Threshold": 40,
            "Glow Radius": 25,
            "Glow Intensity": 1.5,
        },
        confidence: 0.85,
    };

    const result = optimizer.optimize(input);
    console.log(`  优化评分: ${result.score.toFixed(2)}`);

    assert(result.score >= 0.9, "合理参数应获得高评分");
    assert(result.score <= 1.0, "评分不应超过1.0");
}

logSection("测试9: 无效效果matchName处理");
{
    const optimizer = new ParameterOptimizer();
    const input: EffectParams = {
        matchName: "Unknown Effect",
        displayName: "Unknown",
        settings: {
            "Unknown Param": 100,
        },
        confidence: 0.5,
    };

    const result = optimizer.optimize(input);

    assert(result.warnings.length > 0, "应返回警告");
    assert(result.score === 1.0, "未知效果评分应为1.0");
}

logSection("测试10: Fractal Noise复杂度约束");
{
    const optimizer = new ParameterOptimizer({ performanceMode: true });
    const input: EffectParams = {
        matchName: "ADBE Fractal Noise",
        displayName: "Fractal Noise",
        settings: {
            "Contrast": 50,
            "Brightness": 0,
            "Scale": 200,
            "Complexity": 8,
            "Evolution Speed": 10,
        },
        confidence: 0.78,
    };

    const result = optimizer.optimize(input);
    console.log(`  优化后复杂度: ${result.optimizedParams.settings["Complexity"]}`);

    assert(
        (result.optimizedParams.settings["Complexity"] as number) <= 6,
        "性能模式下复杂度应被限制"
    );
}

logSection("测试11: 支持效果列表");
{
    const optimizer = new ParameterOptimizer();
    const supported = optimizer.listSupportedEffects();

    console.log(`  支持的效果: ${supported.join(", ")}`);

    assert(supported.length >= 5, "应至少支持5个效果");
    assert(supported.includes("ADBE Glo2"), "应支持 Glow");
    assert(supported.includes("CC Particle World"), "应支持 CC Particle World");
}

logSection("测试12: 获取约束信息");
{
    const optimizer = new ParameterOptimizer();
    const constraints = optimizer.getConstraints("ADBE Glo2");

    console.log(`  Glow约束: ${constraints ? "存在" : "不存在"}`);

    assert(constraints !== undefined, "应能获取Glow的约束");
    assert(constraints!.params["Glow Intensity"] !== undefined, "应包含Glow Intensity约束");
}

console.log("\n========================================");
console.log(` 测试结果: ${passCount} 通过 / ${failCount} 失败 / ${passCount + failCount} 总计`);
console.log("========================================");

process.exit(failCount > 0 ? 1 : 0);