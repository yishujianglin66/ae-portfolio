/**
 * Silhouette NLU + Scheduler 快速验证脚本
 * 验证新增的 SILHOUETTE_TASK 意图识别和操作生成
 */

import { aiScheduler } from "./src/phase4/ai-scheduler";
import { IntentType } from "./src/phase4/types";

const testCases = [
    // Roto/遮罩相关
    { input: "扣个人像", expected: "roto" },
    { input: "做个角色遮罩", expected: "roto" },
    { input: "背景抠掉", expected: "roto" },
    { input: "自动 rotoscope", expected: "roto" },
    // 跟踪相关
    { input: "跟踪这个物体", expected: "track" },
    { input: "平面跟踪", expected: "track" },
    { input: "做个点跟踪", expected: "track" },
    // Paint 相关
    { input: "修掉这个瑕疵", expected: "paint" },
    { input: "Paint 修复", expected: "paint" },
    // 软件名触发
    { input: "用 Silhouette 处理", expected: "roto" },
];

console.log("=".repeat(60));
console.log("Silhouette NLU + Scheduler 验证");
console.log("=".repeat(60));

let passed = 0;
let failed = 0;

for (const tc of testCases) {
    const result = aiScheduler.execute(tc.input);
    const taskType = result.intent?.slots.silhouetteTask;
    const isSilhouetteIntent = result.intent?.type === IntentType.SILHOUETTE_TASK;
    const opsCount = result.silhouetteOperations?.length || 0;

    const ok = isSilhouetteIntent && taskType === tc.expected && opsCount > 0;

    if (ok) passed++;
    else failed++;

    console.log(
        `${ok ? "✓" : "✗"} "${tc.input}" → intent=${isSilhouetteIntent ? "SILHOUETTE" : result.intent?.type
        }, task=${taskType || "N/A"}, ops=${opsCount}`
    );

    if (!ok) {
        console.log(`    期望: SILHOUETTE + task=${tc.expected}`);
        console.log(`    实际: ${result.intent?.type} + task=${taskType}`);
    }
}

console.log("=".repeat(60));
console.log(`结果: ${passed} 通过 / ${failed} 失败 / ${testCases.length} 总计`);
console.log("=".repeat(60));

process.exit(failed > 0 ? 1 : 0);
