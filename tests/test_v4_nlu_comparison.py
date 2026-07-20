#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek V4 NLU 意图识别对比测试
=================================
对比 V4 API 与本地正则解析器在 Silhouette 意图识别上的准确率和速度。
使用与 test_silhouette_nlu.ts 相同的 10 个测试用例。
"""

import os
import json
import time
import requests
from datetime import datetime

# DeepSeek V4 API 配置
API_BASE = "https://api.deepseek.com"
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
V4_FLASH = "deepseek-v4-flash"
V4_PRO = "deepseek-v4-pro"

# 与 test_silhouette_nlu.ts 相同的 10 个测试用例
TEST_CASES = [
    {"input": "扣个人像", "expected_task": "roto", "expected_intent": "SILHOUETTE_TASK"},
    {"input": "做个角色遮罩", "expected_task": "roto", "expected_intent": "SILHOUETTE_TASK"},
    {"input": "背景抠掉", "expected_task": "roto", "expected_intent": "SILHOUETTE_TASK"},
    {"input": "自动 rotoscope", "expected_task": "roto", "expected_intent": "SILHOUETTE_TASK"},
    {"input": "跟踪这个物体", "expected_task": "track", "expected_intent": "SILHOUETTE_TASK"},
    {"input": "平面跟踪", "expected_task": "track", "expected_intent": "SILHOUETTE_TASK"},
    {"input": "做个点跟踪", "expected_task": "track", "expected_intent": "SILHOUETTE_TASK"},
    {"input": "修掉这个瑕疵", "expected_task": "paint", "expected_intent": "SILHOUETTE_TASK"},
    {"input": "Paint 修复", "expected_task": "paint", "expected_intent": "SILHOUETTE_TASK"},
    {"input": "用 Silhouette 处理", "expected_task": "roto", "expected_intent": "SILHOUETTE_TASK"},
]

SYSTEM_PROMPT = """你是视频制作意图分析专家。分析用户输入，识别Silhouette相关任务意图。

意图类型:
- INTENT_SILHOUETTE_TASK: Silhouette任务（抠像/跟踪/修复）

任务类型:
- roto: 遮罩抠像（扣/抠/遮罩/蒙版/roto/rotoscope）
- track: 跟踪（跟踪/追踪/track）
- paint: 修复（修/擦/paint/修复/去除）

输出格式（严格JSON）:
{
  "intent_type": "INTENT_SILHOUETTE_TASK",
  "task_type": "roto|track|paint",
  "confidence": 0.0-1.0,
  "reason": "简要原因"
}"""


def call_v4_api(model: str, message: str, system_prompt: str = SYSTEM_PROMPT) -> dict:
    """调用 V4 API"""
    url = f"{API_BASE}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        "max_tokens": 200,
        "temperature": 0.1,  # 低温度保证一致性
    }

    start_time = time.time()
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    latency_ms = int((time.time() - start_time) * 1000)

    response.raise_for_status()
    data = response.json()

    return {
        "content": data["choices"][0]["message"]["content"],
        "model": data.get("model", model),
        "latency_ms": latency_ms,
        "tokens_input": data.get("usage", {}).get("prompt_tokens", 0),
        "tokens_output": data.get("usage", {}).get("completion_tokens", 0),
    }


def parse_v4_response(content: str) -> dict:
    """解析 V4 返回的 JSON"""
    import re
    try:
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            return json.loads(json_match.group())
    except:
        pass
    return {"task_type": "unknown", "confidence": 0}


def run_comparison_test():
    """运行对比测试"""
    print("=" * 70)
    print("DeepSeek V4 NLU 意图识别对比测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API Key: {API_KEY[:10]}...{API_KEY[-4:]}")
    print("=" * 70)

    if not API_KEY:
        print("❌ 未设置 DEEPSEEK_API_KEY 环境变量")
        return

    results_flash = []
    results_pro = []

    # 测试 V4-Flash
    print("\n--- V4-Flash 测试 ---")
    for i, tc in enumerate(TEST_CASES):
        try:
            result = call_v4_api(V4_FLASH, tc["input"])
            parsed = parse_v4_response(result["content"])
            actual_task = parsed.get("task_type", "unknown")
            correct = actual_task == tc["expected_task"]

            results_flash.append({
                "input": tc["input"],
                "expected": tc["expected_task"],
                "actual": actual_task,
                "correct": correct,
                "latency_ms": result["latency_ms"],
                "tokens": result["tokens_input"] + result["tokens_output"],
                "confidence": parsed.get("confidence", 0),
            })

            status = "✓" if correct else "✗"
            print(f"  {status} [{result['latency_ms']}ms] '{tc['input']}' -> {actual_task} (期望: {tc['expected_task']})")

        except Exception as e:
            results_flash.append({
                "input": tc["input"],
                "expected": tc["expected_task"],
                "actual": "error",
                "correct": False,
                "error": str(e),
            })
            print(f"  ✗ '{tc['input']}' -> 错误: {e}")

    # 测试 V4-Pro（只测前5个，节省成本）
    print("\n--- V4-Pro 测试 (前5个用例) ---")
    for i, tc in enumerate(TEST_CASES[:5]):
        try:
            result = call_v4_api(V4_PRO, tc["input"])
            parsed = parse_v4_response(result["content"])
            actual_task = parsed.get("task_type", "unknown")
            correct = actual_task == tc["expected_task"]

            results_pro.append({
                "input": tc["input"],
                "expected": tc["expected_task"],
                "actual": actual_task,
                "correct": correct,
                "latency_ms": result["latency_ms"],
                "tokens": result["tokens_input"] + result["tokens_output"],
                "confidence": parsed.get("confidence", 0),
            })

            status = "✓" if correct else "✗"
            print(f"  {status} [{result['latency_ms']}ms] '{tc['input']}' -> {actual_task} (期望: {tc['expected_task']})")

        except Exception as e:
            results_pro.append({
                "input": tc["input"],
                "expected": tc["expected_task"],
                "actual": "error",
                "correct": False,
                "error": str(e),
            })
            print(f"  ✗ '{tc['input']}' -> 错误: {e}")

    # 汇总统计
    print("\n" + "=" * 70)
    print("对比结果汇总")
    print("=" * 70)

    # V4-Flash 统计
    flash_correct = sum(1 for r in results_flash if r.get("correct"))
    flash_accuracy = flash_correct / len(results_flash) * 100
    flash_avg_latency = sum(r.get("latency_ms", 0) for r in results_flash) / len(results_flash)
    flash_total_tokens = sum(r.get("tokens", 0) for r in results_flash)

    # V4-Pro 统计
    pro_correct = sum(1 for r in results_pro if r.get("correct"))
    pro_accuracy = pro_correct / len(results_pro) * 100 if results_pro else 0
    pro_avg_latency = sum(r.get("latency_ms", 0) for r in results_pro) / len(results_pro) if results_pro else 0
    pro_total_tokens = sum(r.get("tokens", 0) for r in results_pro)

    # 本地正则统计（来自 TypeScript 测试结果）
    local_accuracy = 100.0  # 10/10 通过
    local_avg_latency = 0.1  # 正则匹配约 0.1ms

    print(f"\n{'指标':<20} {'本地正则':<15} {'V4-Flash':<15} {'V4-Pro':<15}")
    print("-" * 65)
    print(f"{'准确率':<20} {local_accuracy:>14.1f}% {flash_accuracy:>14.1f}% {pro_accuracy:>14.1f}%")
    print(f"{'平均延迟(ms)':<20} {local_avg_latency:>14.1f} {flash_avg_latency:>14.1f} {pro_avg_latency:>14.1f}")
    print(f"{'总Token消耗':<20} {'0':>15} {flash_total_tokens:>15} {pro_total_tokens:>15}")
    print(f"{'测试用例数':<20} {len(TEST_CASES):>15} {len(results_flash):>15} {len(results_pro):>15}")

    # 费用计算
    flash_cost = (flash_total_tokens / 1_000_000) * 1.5  # 平均输入输出价格
    pro_cost = (pro_total_tokens / 1_000_000) * 4.5

    print(f"\n{'费用估算(¥)':<20} {'0':>15} {flash_cost:>15.6f} {pro_cost:>15.6f}")

    # 结论
    print("\n" + "=" * 70)
    print("结论")
    print("=" * 70)

    if flash_accuracy == 100 and pro_accuracy == 100:
        print("✅ V4-Flash 和 V4-Pro 均达到 100% 准确率，与本地正则持平")
    elif flash_accuracy >= 90:
        print(f"✅ V4-Flash 准确率 {flash_accuracy:.1f}%，达到可用标准")

    if flash_avg_latency < 2000:
        print(f"✅ V4-Flash 平均延迟 {flash_avg_latency:.0f}ms，适合实时交互")
    else:
        print(f"⚠️  V4-Flash 平均延迟 {flash_avg_latency:.0f}ms，建议用于非实时场景")

    print(f"✅ V4-Flash 单次费用约 ¥{flash_cost/len(results_flash):.6f}，成本极低")
    print(f"✅ 本地正则延迟约 {local_avg_latency}ms，适合高频简单意图")
    print(f"✅ 推荐策略: 本地正则优先 → 低置信度时调用 V4-Flash → 复杂分析用 V4-Pro")

    # 保存详细结果
    report = {
        "test_time": datetime.now().isoformat(),
        "test_cases": len(TEST_CASES),
        "v4_flash": {
            "accuracy": flash_accuracy,
            "avg_latency_ms": flash_avg_latency,
            "total_tokens": flash_total_tokens,
            "cost_yuan": flash_cost,
            "details": results_flash,
        },
        "v4_pro": {
            "accuracy": pro_accuracy,
            "avg_latency_ms": pro_avg_latency,
            "total_tokens": pro_total_tokens,
            "cost_yuan": pro_cost,
            "details": results_pro,
        },
        "local_regex": {
            "accuracy": local_accuracy,
            "avg_latency_ms": local_avg_latency,
            "total_tokens": 0,
            "cost_yuan": 0,
        },
    }

    report_path = os.path.join(os.path.dirname(__file__), "v4_nlu_comparison_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告已保存: {report_path}")


if __name__ == "__main__":
    run_comparison_test()
