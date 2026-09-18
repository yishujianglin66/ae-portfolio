"""
测试 RateLimiter 并发竞态条件缺陷

Bug 描述：
RateLimiter.acquire() 在等待后重新检查时间戳列表时，未重新获取锁，
导致多个协程可能同时通过限流检查，造成限流失效。

触发场景：
1. 多个协程并发调用 acquire()
2. 第一个协程获取锁，检查到需要等待，进入 sleep
3. 第二个协程在第一个 sleep 时也获取锁，检查到相同等待时间
4. 两个协程同时醒来，都认为可以继续，导致短时间内请求数超过限制
"""
import asyncio
import time

import pytest

from core.agent_reach_adapter import RateLimiter


@pytest.mark.asyncio
async def test_ratelimiter_concurrent_race():
    """测试并发竞态条件导致限流失效"""
    # 设置限流：每秒最多 3 个请求
    limiter = RateLimiter(max_requests=3, per_seconds=1.0)

    # 记录所有通过的时间戳
    passed_times = []

    async def try_acquire(idx: int):
        """尝试获取令牌"""
        await limiter.acquire()
        passed_times.append(time.monotonic())
        print(f"Request {idx} passed at {passed_times[-1]:.3f}")

    # 并发发起 5 个请求（超过限制）
    # 预期：前 3 个应该立即通过，后 2 个应该等待至少 1 秒
    start_time = time.monotonic()
    await asyncio.gather(
        try_acquire(0),
        try_acquire(1),
        try_acquire(2),
        try_acquire(3),
        try_acquire(4),
    )
    end_time = time.monotonic()

    # 检查时间窗口内通过的请求数
    window_start = start_time + 1.0  # 1秒窗口
    requests_in_window = sum(1 for t in passed_times if t < window_start)

    print(f"总耗时: {end_time - start_time:.3f}s")
    print(f"前 1 秒内通过的请求数: {requests_in_window}")

    # Bug 检测：如果存在竞态条件，前 1 秒内可能通过 > 3 个请求
    # 正确实现应该限制为恰好 3 个
    assert requests_in_window <= 3, (
        f"限流失效：前 1 秒内通过了 {requests_in_window} 个请求（应 ≤ 3）"
    )


@pytest.mark.asyncio
async def test_ratelimiter_stress():
    """压力测试：20 个并发请求"""
    limiter = RateLimiter(max_requests=5, per_seconds=1.0)
    passed_times = []

    async def try_acquire(idx: int):
        await limiter.acquire()
        passed_times.append(time.monotonic())

    start_time = time.monotonic()
    await asyncio.gather(*[try_acquire(i) for i in range(20)])
    end_time = time.monotonic()

    # 统计每个时间窗口（1秒）内的请求数
    window_size = 1.0
    max_in_window = 0

    for i in range(len(passed_times)):
        window_start = passed_times[i]
        window_end = window_start + window_size
        count = sum(1 for t in passed_times if window_start <= t < window_end)
        max_in_window = max(max_in_window, count)

    print(f"任意 1 秒窗口内最大请求数: {max_in_window}")
    assert max_in_window <= 5, f"限流失效：某窗口内通过 {max_in_window} 个请求（应 ≤ 5）"


if __name__ == "__main__":
    asyncio.run(test_ratelimiter_concurrent_race())