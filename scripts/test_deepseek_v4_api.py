#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek V4 正式版 API 测试脚本
================================

测试项目：
1. API 连接验证
2. V4-Flash 模型调用
3. V4-Pro 模型调用
4. 1M 上下文窗口测试
5. Token 消耗统计
6. 响应时间基准
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 尝试导入 requests
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.error
    import urllib.request

# DeepSeek V4 正式版 API 配置
DEEPSEEK_API_BASE = "https://api.deepseek.com"
V4_MODELS = {
    "flash": "deepseek-v4-flash",
    "pro": "deepseek-v4-pro",
}

# V4 定价（元/百万token）
V4_PRICING = {
    "flash": {"input": 1.0, "output": 2.0},  # 低谷时段更便宜
    "pro": {"input": 3.0, "output": 6.0},
}

# 峰谷定价时段
PEAK_HOURS = [(9, 12), (14, 18)]  # 高峰时段


class DeepSeekV4APITester:
    """DeepSeek V4 API 测试器"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = DEEPSEEK_API_BASE
        self.test_results = []

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _http_post(self, url: str, data: dict) -> dict:
        """发送 POST 请求"""
        if HAS_REQUESTS:
            response = requests.post(url, headers=self._get_headers(), json=data, timeout=300)
            response.raise_for_status()
            return response.json()
        else:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers=self._get_headers(),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as response:
                return json.loads(response.read().decode("utf-8"))

    def test_api_connection(self) -> dict:
        """测试 1: API 连接验证"""
        print("\n" + "=" * 60)
        print("测试 1: API 连接验证")
        print("=" * 60)

        start_time = time.time()
        result = {
            "test": "api_connection",
            "status": "unknown",
            "latency_ms": 0,
            "error": None,
        }

        try:
            # 简单的 hello 测试
            url = f"{self.base_url}/v1/chat/completions"
            payload = {
                "model": V4_MODELS["flash"],
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 10,
            }

            response = self._http_post(url, payload)

            if "choices" in response and response["choices"]:
                result["status"] = "success"
                result["latency_ms"] = int((time.time() - start_time) * 1000)
                result["model"] = response.get("model", "unknown")
                print("✅ API 连接成功")
                print(f"   模型: {result['model']}")
                print(f"   响应时间: {result['latency_ms']}ms")
            else:
                result["status"] = "failed"
                result["error"] = "Invalid response format"
                print("❌ API 返回格式异常")

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            print(f"❌ API 连接失败: {e}")

        self.test_results.append(result)
        return result

    def test_v4_flash(self) -> dict:
        """测试 2: V4-Flash 模型调用"""
        print("\n" + "=" * 60)
        print("测试 2: V4-Flash 模型调用")
        print("=" * 60)

        start_time = time.time()
        result = {
            "test": "v4_flash",
            "status": "unknown",
            "latency_ms": 0,
            "tokens_input": 0,
            "tokens_output": 0,
            "error": None,
        }

        try:
            url = f"{self.base_url}/v1/chat/completions"
            payload = {
                "model": V4_MODELS["flash"],
                "messages": [
                    {"role": "system", "content": "你是视频制作专家"},
                    {"role": "user", "content": "请用一句话解释什么是遮罩抠像(Roto)"},
                ],
                "max_tokens": 200,
                "temperature": 0.7,
            }

            response = self._http_post(url, payload)
            latency = int((time.time() - start_time) * 1000)

            if "choices" in response and response["choices"]:
                content = response["choices"][0]["message"]["content"]
                usage = response.get("usage", {})

                result["status"] = "success"
                result["latency_ms"] = latency
                result["tokens_input"] = usage.get("prompt_tokens", 0)
                result["tokens_output"] = usage.get("completion_tokens", 0)
                result["content"] = content
                result["model"] = response.get("model", "unknown")

                print("✅ V4-Flash 调用成功")
                print(f"   模型: {result['model']}")
                print(f"   响应时间: {latency}ms")
                print(f"   Token: 输入={result['tokens_input']}, 输出={result['tokens_output']}")
                print(f"   回复: {content[:100]}...")
            else:
                result["status"] = "failed"
                result["error"] = "Invalid response"
                print("❌ V4-Flash 调用失败")

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            print(f"❌ V4-Flash 调用异常: {e}")

        self.test_results.append(result)
        return result

    def test_v4_pro(self) -> dict:
        """测试 3: V4-Pro 模型调用"""
        print("\n" + "=" * 60)
        print("测试 3: V4-Pro 模型调用")
        print("=" * 60)

        start_time = time.time()
        result = {
            "test": "v4_pro",
            "status": "unknown",
            "latency_ms": 0,
            "tokens_input": 0,
            "tokens_output": 0,
            "error": None,
        }

        try:
            url = f"{self.base_url}/v1/chat/completions"
            payload = {
                "model": V4_MODELS["pro"],
                "messages": [
                    {"role": "system", "content": "你是After Effects脚本专家"},
                    {"role": "user", "content": "请分析Silhouette Roto节点的工作流程，用3个步骤概括"},
                ],
                "max_tokens": 500,
                "temperature": 0.7,
            }

            response = self._http_post(url, payload)
            latency = int((time.time() - start_time) * 1000)

            if "choices" in response and response["choices"]:
                content = response["choices"][0]["message"]["content"]
                usage = response.get("usage", {})

                result["status"] = "success"
                result["latency_ms"] = latency
                result["tokens_input"] = usage.get("prompt_tokens", 0)
                result["tokens_output"] = usage.get("completion_tokens", 0)
                result["content"] = content
                result["model"] = response.get("model", "unknown")

                print("✅ V4-Pro 调用成功")
                print(f"   模型: {result['model']}")
                print(f"   响应时间: {latency}ms")
                print(f"   Token: 输入={result['tokens_input']}, 输出={result['tokens_output']}")
                print(f"   回复: {content[:200]}...")
            else:
                result["status"] = "failed"
                result["error"] = "Invalid response"
                print("❌ V4-Pro 调用失败")

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            print(f"❌ V4-Pro 调用异常: {e}")

        self.test_results.append(result)
        return result

    def test_large_context(self, context_size: int = 50000) -> dict:
        """测试 4: 大上下文窗口测试"""
        print("\n" + "=" * 60)
        print(f"测试 4: 大上下文窗口测试 ({context_size} tokens)")
        print("=" * 60)

        start_time = time.time()
        result = {
            "test": "large_context",
            "context_size": context_size,
            "status": "unknown",
            "latency_ms": 0,
            "tokens_input": 0,
            "tokens_output": 0,
            "error": None,
        }

        try:
            # 生成大上下文（模拟知识库内容）
            # 实际 token 数 ≈ 字符数 / 2（中文）
            context_text = "这是测试上下文内容。用于验证V4的1M上下文能力。" * (context_size // 20)

            url = f"{self.base_url}/v1/chat/completions"
            payload = {
                "model": V4_MODELS["flash"],  # Flash 更便宜，适合大上下文测试
                "messages": [
                    {"role": "system", "content": "你是知识库助手"},
                    {"role": "user", "content": f"以下是一段测试文本，请回答：这段文本包含多少个'测试'字样？\n\n{context_text}"},
                ],
                "max_tokens": 100,
            }

            response = self._http_post(url, payload)
            latency = int((time.time() - start_time) * 1000)

            if "choices" in response and response["choices"]:
                usage = response.get("usage", {})

                result["status"] = "success"
                result["latency_ms"] = latency
                result["tokens_input"] = usage.get("prompt_tokens", 0)
                result["tokens_output"] = usage.get("completion_tokens", 0)
                result["model"] = response.get("model", "unknown")

                print("✅ 大上下文测试成功")
                print(f"   模型: {result['model']}")
                print(f"   响应时间: {latency}ms")
                print(f"   Token: 输入={result['tokens_input']}, 输出={result['tokens_output']}")

                # 估算实际上下文大小
                estimated_tokens = len(context_text) // 2
                print(f"   估算上下文: ~{estimated_tokens} tokens")
            else:
                result["status"] = "failed"
                result["error"] = "Invalid response"
                print("❌ 大上下文测试失败")

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            print(f"❌ 大上下文测试异常: {e}")

        self.test_results.append(result)
        return result

    def test_silhouette_intent(self) -> dict:
        """测试 5: Silhouette 意图识别测试"""
        print("\n" + "=" * 60)
        print("测试 5: Silhouette 意图识别测试")
        print("=" * 60)

        test_cases = [
            ("扣出人物", "roto", "person"),
            ("跟踪这个平面", "track", "planar"),
            ("修掉画面中的水印", "paint", "erase"),
            ("自动roto这个镜头", "roto", "auto"),
            ("paint修复这个区域", "paint", "repair"),
        ]

        results = []
        for query, expected_task, expected_detail in test_cases:
            start_time = time.time()
            try:
                url = f"{self.base_url}/v1/chat/completions"
                payload = {
                    "model": V4_MODELS["flash"],
                    "messages": [
                        {
                            "role": "system",
                            "content": """分析用户意图，返回JSON格式：
{
  "task_type": "roto|track|paint",
  "target": "目标对象",
  "confidence": 0.0-1.0
}""",
                        },
                        {"role": "user", "content": query},
                    ],
                    "max_tokens": 100,
                    "temperature": 0.1,
                }

                response = self._http_post(url, payload)
                latency = int((time.time() - start_time) * 1000)

                if "choices" in response and response["choices"]:
                    content = response["choices"][0]["message"]["content"]
                    usage = response.get("usage", {})

                    # 尝试解析 JSON
                    try:
                        # 提取 JSON
                        import re
                        json_match = re.search(r'\{[\s\S]*\}', content)
                        if json_match:
                            parsed = json.loads(json_match.group())
                            actual_task = parsed.get("task_type", "unknown")
                            correct = actual_task == expected_task
                        else:
                            correct = False
                            parsed = {}
                    except:
                        correct = False
                        parsed = {}

                    results.append({
                        "query": query,
                        "expected": expected_task,
                        "actual": parsed.get("task_type", "parse_error"),
                        "correct": correct,
                        "latency_ms": latency,
                        "tokens": usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0),
                    })

            except Exception as e:
                results.append({
                    "query": query,
                    "expected": expected_task,
                    "actual": "error",
                    "correct": False,
                    "error": str(e),
                })

        # 统计准确率
        correct_count = sum(1 for r in results if r.get("correct"))
        accuracy = correct_count / len(results) if results else 0

        result = {
            "test": "silhouette_intent",
            "status": "success" if accuracy >= 0.8 else "partial",
            "accuracy": accuracy,
            "correct": correct_count,
            "total": len(results),
            "details": results,
        }

        print("✅ 意图识别测试完成")
        print(f"   准确率: {accuracy * 100:.1f}% ({correct_count}/{len(results)})")
        for r in results:
            status = "✓" if r.get("correct") else "✗"
            print(f"   {status} '{r['query']}' -> {r.get('actual', 'error')} (期望: {r['expected']})")

        self.test_results.append(result)
        return result

    def calculate_cost(self, model: str, tokens_input: int, tokens_output: int) -> float:
        """计算费用（元）"""
        pricing = V4_PRICING.get(model, V4_PRICING["flash"])
        input_cost = (tokens_input / 1_000_000) * pricing["input"]
        output_cost = (tokens_output / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def generate_report(self) -> str:
        """生成测试报告"""
        report = []
        report.append("\n" + "=" * 60)
        report.append("DeepSeek V4 正式版 API 测试报告")
        report.append("=" * 60)
        report.append(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"API 端点: {self.base_url}")
        report.append("")

        # 汇总统计
        total_tests = len(self.test_results)
        success_tests = sum(1 for r in self.test_results if r.get("status") == "success")
        total_tokens_in = sum(r.get("tokens_input", 0) for r in self.test_results)
        total_tokens_out = sum(r.get("tokens_output", 0) for r in self.test_results)
        total_latency = sum(r.get("latency_ms", 0) for r in self.test_results if r.get("latency_ms"))

        report.append("## 测试汇总")
        report.append(f"- 总测试数: {total_tests}")
        report.append(f"- 成功数: {success_tests}")
        report.append(f"- 成功率: {success_tests / total_tests * 100:.1f}%")
        report.append(f"- 总Token: 输入={total_tokens_in}, 输出={total_tokens_out}")
        report.append(f"- 平均响应时间: {total_latency / success_tests if success_tests else 0:.0f}ms")
        report.append("")

        # 费用估算
        flash_tokens_in = sum(r.get("tokens_input", 0) for r in self.test_results if "flash" in r.get("test", ""))
        flash_tokens_out = sum(r.get("tokens_output", 0) for r in self.test_results if "flash" in r.get("test", ""))
        pro_tokens_in = sum(r.get("tokens_input", 0) for r in self.test_results if "pro" in r.get("test", ""))
        pro_tokens_out = sum(r.get("tokens_output", 0) for r in self.test_results if "pro" in r.get("test", ""))

        flash_cost = self.calculate_cost("flash", flash_tokens_in, flash_tokens_out)
        pro_cost = self.calculate_cost("pro", pro_tokens_in, pro_tokens_out)

        report.append("## 费用估算")
        report.append(f"- V4-Flash: ¥{flash_cost:.6f} (输入={flash_tokens_in}, 输出={flash_tokens_out})")
        report.append(f"- V4-Pro: ¥{pro_cost:.6f} (输入={pro_tokens_in}, 输出={pro_tokens_out})")
        report.append(f"- 总费用: ¥{flash_cost + pro_cost:.6f}")
        report.append("")

        # 各测试详情
        report.append("## 测试详情")
        for r in self.test_results:
            status_icon = "✅" if r.get("status") == "success" else "⚠️" if r.get("status") == "partial" else "❌"
            report.append(f"\n### {status_icon} {r.get('test', 'unknown')}")
            for key, value in r.items():
                if key != "test" and key != "status" and key != "details":
                    report.append(f"- {key}: {value}")

        return "\n".join(report)


def main():
    """主入口"""
    print("=" * 60)
    print("DeepSeek V4 正式版 API 测试")
    print("=" * 60)

    # 检查 API Key
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")

    if not api_key:
        print("\n⚠️  未检测到 DEEPSEEK_API_KEY 环境变量")
        print("\n请设置环境变量后重试：")
        print("  Windows PowerShell: $env:DEEPSEEK_API_KEY = 'your_api_key'")
        print("  Linux/Mac: export DEEPSEEK_API_KEY='your_api_key'")
        print("\n获取 API Key: https://platform.deepseek.com/")
        print("\n" + "=" * 60)

        # 模拟报告
        print("\n进入模拟模式，生成预期测试报告...\n")

        mock_report = """
## DeepSeek V4 正式版 API 规格

| 模型 | 模型名 | 上下文 | 输出上限 | 输入价格 | 输出价格 |
|------|--------|--------|----------|----------|----------|
| V4-Flash | deepseek-v4-flash | 1M | 384K | ¥1/M | ¥2/M |
| V4-Pro | deepseek-v4-pro | 1M | 384K | ¥3/M | ¥6/M |

## 旧模型停用通知

- ❌ deepseek-chat (已停用)
- ❌ deepseek-reasoner (已停用)
- ✅ 请迁移至 deepseek-v4-flash 或 deepseek-v4-pro

## 峰谷定价时段

- 高峰时段: 9:00-12:00, 14:00-18:00
- 低谷时段: 其他时段价格更低
- 建议: 批量任务安排在低谷时段执行

## 1M 上下文能力

- 可一次性加载 AE-Knowledge-Vault 全部代码 (~50万 tokens)
- 可加载 Silhouette fx API 文档 (517 节点类型, ~10万 tokens)
- 可加载全部知识库文档 (777 个, ~30万 tokens)

## 成本对比

| 场景 | V3 价格 | V4 价格 | 降幅 |
|------|---------|---------|------|
| 意图识别 (100次/天) | ¥0.10 | ¥0.03 | -70% |
| 知识问答 (50次/天) | ¥0.50 | ¥0.15 | -70% |
| 脚本生成 (20次/天) | ¥0.20 | ¥0.06 | -70% |
"""
        print(mock_report)
        return

    # 有 API Key，执行真实测试
    tester = DeepSeekV4APITester(api_key)

    # 执行测试
    tester.test_api_connection()
    tester.test_v4_flash()
    tester.test_v4_pro()
    tester.test_large_context(10000)  # 先用较小的上下文测试
    tester.test_silhouette_intent()

    # 生成报告
    report = tester.generate_report()
    print(report)

    # 保存报告
    report_path = Path(__file__).parent / "deepseek_v4_test_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n报告已保存到: {report_path}")


if __name__ == "__main__":
    main()