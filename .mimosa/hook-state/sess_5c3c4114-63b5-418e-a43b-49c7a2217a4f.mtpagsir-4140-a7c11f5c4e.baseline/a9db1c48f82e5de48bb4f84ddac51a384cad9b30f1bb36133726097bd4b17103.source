/**
 * Silhouette AI 调度器完整演示
 * 展示：自然语言 → NLU解析 → 意图识别 → 操作生成
 */

import { aiScheduler } from "./src/phase4/ai-scheduler";
import { IntentType } from "./src/phase4/types";

const demoCases = [
    {
        title: "案例1: 人像抠图（Roto）",
        input: "扣个人像，用贝塞尔曲线，边缘容差 1.5",
    },
    {
        title: "案例2: 平面跟踪",
        input: "对这段视频做平面跟踪，精度高一些",
    },
    {
        title: "案例3: Paint 修复",
        input: "用 clone 模式修掉画面里的水印",
    },
    {
        title: "案例4: 背景分离",
        input: "把背景抠掉，用 x-spline",
    },
    {
        title: "案例5: 点跟踪",
        input: "做个点跟踪，搜索区域 31",
    },
];

console.log("=".repeat(70));
console.log("  Silhouette AI 调度器 - 完整演示");
console.log("=".repeat(70));

let totalPassed = 0;
let totalFailed = 0;

for (let i = 0; i < demoCases.length; i++) {
    const demo = demoCases[i];
    const result = aiScheduler.execute(demo.input);

    const isSilhouette = result.intent?.type === IntentType.SILHOUETTE_TASK;
    const hasOps = (result.silhouetteOperations?.length || 0) > 0;
    const passed = isSilhouette && hasOps;

    if (passed) totalPassed++;
    else totalFailed++;

    console.log(`\n  ${demo.title}`);
    console.log("  " + "─".repeat(50));
    console.log(`  输入: "${demo.input}"`);
    console.log();
    console.log(`  意图类型: ${isSilhouette ? "✓ SILHOUETTE_TASK" : "✗ " + result.intent?.type}`);
    console.log(`  置信度: ${(result.confidence * 100).toFixed(0)}%`);

    if (result.intent?.slots.silhouetteTask) {
        console.log(`  任务类型: ${result.intent.slots.silhouetteTask}`);
    }
    if (result.intent?.slots.rotoTarget) {
        console.log(`  遮罩目标: ${result.intent.slots.rotoTarget}`);
    }
    if (result.intent?.slots.trackType) {
        console.log(`  跟踪类型: ${result.intent.slots.trackType}`);
    }
    if (result.intent?.slots.effectName) {
        console.log(`  形状/模式: ${result.intent.slots.effectName}`);
    }

    if (result.silhouetteOperations && result.silhouetteOperations.length > 0) {
        console.log();
        console.log(`  生成操作 (${result.silhouetteOperations.length} 个):`);
        result.silhouetteOperations.forEach((op, idx) => {
            console.log(`    [${idx + 1}] ${op.taskType.toUpperCase()}`);
            const entries = Object.entries(op).filter(([k]) => k !== "taskType");
            entries.forEach(([key, val]) => {
                if (val !== undefined && val !== null) {
                    console.log(`        ${key}: ${JSON.stringify(val)}`);
                }
            });
        });
    }

    console.log();
    console.log(`  结果: ${passed ? "✓ 通过" : "✗ 失败"}`);
}

console.log("\n" + "=".repeat(70));
console.log(`  总计: ${totalPassed} 通过 / ${totalFailed} 失败 / ${demoCases.length} 案例`);
console.log("=".repeat(70));

console.log(`
  后续流程（在完整管线中）:
    SilhouetteOperation[]
          ↓
    silhouette_executor.py（Python 执行端）
          ↓
    Silhouette fx 脚本生成
          ↓
    Matte 序列 / 跟踪数据 / Paint 结果
          ↓
    AE 合成使用
          ↓
    最终渲染输出
`);
