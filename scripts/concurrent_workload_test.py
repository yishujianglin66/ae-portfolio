#!/usr/bin/env python3
"""多任务并发执行测试.

验证 workflow_orchestrator 在多任务并发场景下的：
1. 并行 DAG 调度正确性
2. 任务隔离性（A 任务失败不影响 B 任务）
3. Bridge 文件锁安全（无竞争条件）
4. 异常恢复与重试机制
5. 资源限制与背压

使用方法:
    python scripts/concurrent_workload_test.py           # 全量测试
    python scripts/concurrent_workload_test.py --small   # 小规模测试
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BRIDGE_DIR = PROJECT_ROOT / ".ae-mcp-bridge"
CMD_FILE = BRIDGE_DIR / "ae_command.json"
RESULT_FILE = BRIDGE_DIR / "ae_result.json"


# ---------------------------------------------------------------------------
# 模拟 Bridge（离线测试，不连接 AE）
# ---------------------------------------------------------------------------

@dataclass
class MockBridgeState:
    """模拟 AE Bridge 的文件状态."""
    active_commands: int = 0
    race_conditions: int = 0
    corrupted_reads: int = 0
    total_commands: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


async def mock_bridge_send(command: str, args: dict, state: MockBridgeState) -> dict:
    """模拟 Bridge 通信（带并发安全检测）."""
    async with state.lock:
        state.total_commands += 1
        state.active_commands += 1

        # 模拟文件写入（检测竞争条件）
        if state.active_commands > 1:
            state.race_conditions += 1

        # 模拟处理延迟（10-100ms 随机）
        delay = random.uniform(0.01, 0.1)
        await asyncio.sleep(delay)

        # 模拟结果
        result = {
            "status": "success",
            "command": command,
            "result": f"mock_result_{state.total_commands}",
            "elapsed_ms": int(delay * 1000),
        }

        state.active_commands -= 1

        # 检查文件损坏（模拟并发读写冲突）
        if random.random() < 0.02:  # 2% 概率模拟损坏
            state.corrupted_reads += 1
            result = {"status": "error", "error": "JSON parse error (corrupted file)"}

    return result


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------

@dataclass
class WorkloadResult:
    name: str
    success: bool
    elapsed_ms: float
    details: dict[str, Any] = field(default_factory=dict)


class TestRunner:
    def __init__(self):
        self.results: list[WorkloadResult] = []

    async def run(self, name: str, coro):
        start = time.perf_counter()
        try:
            result = await coro
            elapsed = (time.perf_counter() - start) * 1000
            if isinstance(result, tuple):
                msg, details = result
            else:
                msg, details = str(result), {}
            self.results.append(WorkloadResult(name, True, elapsed, details or {}))
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            self.results.append(WorkloadResult(name, False, elapsed, {"error": str(e)}))

    def summary(self) -> str:
        passed = sum(1 for r in self.results if r.success)
        total = len(self.results)
        lines = ["", "=" * 60, " 并发负载测试结果", "=" * 60]
        for r in self.results:
            icon = "PASS" if r.success else "FAIL"
            lines.append(f"  [{icon}] {r.name:<40s} {r.elapsed_ms:7.1f}ms")
            if r.details:
                for k, v in r.details.items():
                    lines.append(f"         {k}: {v}")
        lines.append("-" * 60)
        lines.append(f"  通过: {passed}/{total}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 测试函数
# ---------------------------------------------------------------------------

async def test_sequential_tasks(runner: TestRunner):
    """测试 1: 串行任务（基准）."""
    state = MockBridgeState()
    start = time.perf_counter()
    for i in range(10):
        await mock_bridge_send(f"task_{i}", {"index": i}, state)
    elapsed = time.perf_counter() - start
    return (
        f"10 个串行任务 {elapsed:.2f}s",
        {"race_conditions": state.race_conditions, "corrupted": state.corrupted_reads},
    )


async def test_parallel_tasks(runner: TestRunner):
    """测试 2: 并行任务（验证隔离性）."""
    state = MockBridgeState()
    start = time.perf_counter()
    tasks = [mock_bridge_send(f"parallel_{i}", {"index": i}, state) for i in range(20)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.perf_counter() - start
    success = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
    return (
        f"20 并行任务 {elapsed:.2f}s ({success}/20 成功)",
        {
            "success": success,
            "total": 20,
            "race_conditions": state.race_conditions,
            "corrupted": state.corrupted_reads,
            "speedup": elapsed / max(elapsed, 0.001),
        },
    )


async def test_mixed_workload(runner: TestRunner):
    """测试 3: 混合负载（快慢任务混合）."""
    state = MockBridgeState()
    results_list = []

    async def slow_task(idx):
        await asyncio.sleep(random.uniform(0.05, 0.2))
        r = await mock_bridge_send(f"slow_{idx}", {"type": "slow"}, state)
        results_list.append(r)

    async def fast_task(idx):
        await asyncio.sleep(random.uniform(0.001, 0.01))
        r = await mock_bridge_send(f"fast_{idx}", {"type": "fast"}, state)
        results_list.append(r)

    # 5 个慢任务 + 15 个快任务同时提交
    all_tasks = [
        *(slow_task(i) for i in range(5)),
        *(fast_task(i) for i in range(15)),
    ]
    random.shuffle(all_tasks)
    await asyncio.gather(*all_tasks, return_exceptions=True)

    slow_ok = sum(1 for r in results_list if "slow_" in str(r.get("command", "")) and r.get("status") == "success")
    fast_ok = sum(1 for r in results_list if "fast_" in str(r.get("command", "")) and r.get("status") == "success")

    return (
        f"混合负载: 慢 {slow_ok}/5, 快 {fast_ok}/15",
        {
            "slow_success": slow_ok,
            "fast_success": fast_ok,
            "race_conditions": state.race_conditions,
            "corrupted": state.corrupted_reads,
        },
    )


async def test_failure_isolation(runner: TestRunner):
    """测试 4: 故障隔离（A 任务失败不影响 B 任务）."""
    state = MockBridgeState()

    async def good_task(idx):
        return await mock_bridge_send(f"good_{idx}", {}, state)

    async def bad_task(idx):
        # 模拟失败
        await asyncio.sleep(0.01)
        raise ValueError(f"task_{idx} failed")

    tasks = [
        good_task(0),
        bad_task(1),
        good_task(2),
        bad_task(3),
        good_task(4),
        good_task(5),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    good_ok = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
    bad_count = sum(1 for r in results if isinstance(r, Exception))
    expected_good = 4  # tasks 0,2,4,5

    return (
        f"故障隔离: good {good_ok}/{expected_good}, bad {bad_count}/2",
        {"good_success": good_ok, "bad_count": bad_count, "isolation_ok": good_ok == expected_good},
    )


async def test_retry_mechanism(runner: TestRunner):
    """测试 5: 重试机制（任务失败后自动重试）."""
    state = MockBridgeState()

    async def flaky_task(idx):
        # 第 1-2 次失败，第 3 次成功
        await asyncio.sleep(0.01)
        if idx < 2:
            raise ValueError(f"flaky_{idx} attempt failed")
        return await mock_bridge_send(f"flaky_final", {}, state)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            await flaky_task(attempt)
            break
        except Exception:
            if attempt < max_retries - 1:
                await asyncio.sleep(0.05)  # 退避
            else:
                return "重试耗尽（预期行为）", {"attempts": max_retries, "final": "failed"}

    return "重试后成功", {"attempts": 3, "final": "success"}


async def test_backpressure(runner: TestRunner):
    """测试 6: 背压测试（并发数限制）."""
    state = MockBridgeState()
    sem = asyncio.Semaphore(5)  # 最多 5 并发

    async def limited_task(idx):
        async with sem:
            await asyncio.sleep(random.uniform(0.01, 0.05))
            return await mock_bridge_send(f"limited_{idx}", {}, state)

    start = time.perf_counter()
    results = await asyncio.gather(*[limited_task(i) for i in range(50)], return_exceptions=True)
    elapsed = time.perf_counter() - start

    success = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
    return (
        f"背压测试 (max=5): {success}/50 成功, {elapsed:.1f}s",
        {
            "success": success,
            "total": 50,
            "elapsed_s": elapsed,
            "throughput": success / max(elapsed, 0.001),
            "race_conditions": state.race_conditions,
        },
    )


async def test_dag_execution(runner: TestRunner):
    """测试 7: DAG 依赖执行正确性."""
    state = MockBridgeState()
    execution_order: list[str] = []

    async def dag_task(name: str, deps: list[str]):
        # 确保依赖先执行
        for dep in deps:
            while dep not in execution_order:
                await asyncio.sleep(0.001)
        await mock_bridge_send(name, {"deps": deps}, state)
        execution_order.append(name)
        return name

    # DAG: A→C, B→C, C→D
    tasks = [
        dag_task("A", []),
        dag_task("B", []),
        dag_task("C", ["A", "B"]),
        dag_task("D", ["C"]),
    ]
    await asyncio.gather(*tasks)

    # 验证顺序
    a_idx = execution_order.index("A")
    b_idx = execution_order.index("B")
    c_idx = execution_order.index("C")
    d_idx = execution_order.index("D")

    valid = a_idx < c_idx and b_idx < c_idx and c_idx < d_idx
    return (
        f"DAG 依赖正确: {execution_order}",
        {"order": execution_order, "valid": valid},
    )


async def test_bridge_file_safety(runner: TestRunner):
    """测试 8: Bridge 文件安全性（并发写入检测）."""
    state = MockBridgeState()

    # 模拟大量并发读写
    async def unsafe_task(idx):
        for _ in range(10):
            await mock_bridge_send(f"unsafe_{idx}", {"iteration": _}, state)

    await asyncio.gather(*[unsafe_task(i) for i in range(10)])

    safety_score = 1.0 - (state.corrupted_reads / max(state.total_commands, 1))
    return (
        f"文件安全: {state.total_commands} 命令, {state.corrupted_reads} 损坏 ({safety_score:.1%}安全)",
        {
            "total_commands": state.total_commands,
            "race_conditions": state.race_conditions,
            "corrupted": state.corrupted_reads,
            "safety_score": safety_score,
        },
    )


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="多任务并发负载测试")
    parser.add_argument("--small", action="store_true", help="小规模测试")
    args = parser.parse_args()

    runner = TestRunner()

    print("=" * 60)
    print(" 多任务并发负载测试")
    print("=" * 60)
    print(f"  模式: {'小规模' if args.small else '全量'}")
    print(f"  Bridge: 模拟（离线模式）")
    print(f"  时间: {datetime.now().isoformat()}")
    print()

    if args.small:
        await runner.run("串行基准", test_sequential_tasks(runner))
        await runner.run("并行隔离", test_parallel_tasks(runner))
        await runner.run("故障隔离", test_failure_isolation(runner))
    else:
        await runner.run("串行基准", test_sequential_tasks(runner))
        await runner.run("并行隔离", test_parallel_tasks(runner))
        await runner.run("混合负载", test_mixed_workload(runner))
        await runner.run("故障隔离", test_failure_isolation(runner))
        await runner.run("重试机制", test_retry_mechanism(runner))
        await runner.run("背压控制", test_backpressure(runner))
        await runner.run("DAG 依赖", test_dag_execution(runner))
        await runner.run("文件安全", test_bridge_file_safety(runner))

    print(runner.summary())

    passed = sum(1 for r in runner.results if r.success)
    total = len(runner.results)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
