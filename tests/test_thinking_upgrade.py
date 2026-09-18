import asyncio
import time
from dataclasses import dataclass, field

import pytest

from core.llm_gateway import (
    TASK_TIER_MAP,
    LLMResponse,
    LLMUnavailableError,
    ModelTier,
    TaskType,
    ThinkingBudget,
    ThinkingUpgradePolicy,
    chat_with_thinking_upgrade,
)

# ---------------------------------------------------------------------------
# 保留的原有合法测试（含 M1 / H1 相关断言更新）
# ---------------------------------------------------------------------------


def test_budget_defaults():
    budget = ThinkingBudget()
    assert budget.max_rounds == 3
    assert budget.max_tokens_per_round == 8000
    assert budget.timeout_seconds == 300
    assert budget.max_cost_usd == 0.5


def test_trigger_3d_upgrade():
    decision = ThinkingUpgradePolicy().should_upgrade(TaskType.SCENE_DESCRIPTION, "请做三维坐标校准")
    assert decision.should_upgrade
    # M1: 原 "deep_reasoning" 枚举不存在，改为实际执行轮 QUALITY_REVIEW
    assert decision.upgraded_task_type == "QUALITY_REVIEW"
    assert decision.estimated_cost_usd <= decision.budget.max_cost_usd


def test_trigger_formal_upgrade():
    decision = ThinkingUpgradePolicy().should_upgrade(TaskType.PARAMETER_OPTIMIZATION, "形式化验证参数边界")
    assert decision.should_upgrade


def test_complexity_marker_upgrade():
    prompt = "分析并对比多个方案，同时考虑边界条件"
    decision = ThinkingUpgradePolicy().should_upgrade(TaskType.GENERAL, prompt)
    assert decision.should_upgrade


def test_no_trigger_no_upgrade():
    decision = ThinkingUpgradePolicy().should_upgrade(TaskType.GENERAL, "请问今天是什么日期")
    assert not decision.should_upgrade
    assert decision.reason == "no_trigger"
    assert decision.estimated_cost_usd == 0.0


def test_tier3_no_duplicate_upgrade():
    decision = ThinkingUpgradePolicy().should_upgrade(TaskType.QUALITY_REVIEW, "请做形式化验证")
    assert TASK_TIER_MAP[TaskType.QUALITY_REVIEW] == ModelTier.TIER_3_FLAGSHIP_REASONING
    assert not decision.should_upgrade
    assert decision.reason == "already_tier3"


def test_cost_estimation():
    policy = ThinkingUpgradePolicy()
    cost = policy._estimate_thinking_cost("三维坐标校准" * 10, ThinkingBudget())
    assert cost > 0
    # H2c/M6: 修正口径后计入输出 token 成本（60 字中文提示词，3 轮旗舰推理 ≈ $1.68）
    assert cost > 0.1
    assert cost < 2.0  # 低于 config 上限 max_cost_per_task_usd=2.0


@dataclass
class FakeGateway:
    calls: int = 0

    async def chat_with_routing(self, prompt, task_type, **kwargs):
        self.calls += 1
        content = "PASS" if "请检查" in prompt else f"answer-{self.calls}"
        return LLMResponse(content=content, success=True, cost_usd=0.01, latency_ms=2.0)


@pytest.mark.asyncio
async def test_execute_with_thinking_runs_calibration():
    gateway = FakeGateway()
    answer, trace = await ThinkingUpgradePolicy(gateway).execute_with_thinking(
        "请做三维坐标校准", TaskType.GENERAL
    )
    assert answer.startswith("answer-")
    assert trace.decision.should_upgrade
    assert len(trace.rounds) == 1
    assert trace.rounds[0].passed
    assert gateway.calls == 2


@pytest.mark.asyncio
async def test_execute_with_thinking_retries_failed_check():
    class RetryGateway(FakeGateway):
        async def chat_with_routing(self, prompt, task_type, **kwargs):
            self.calls += 1
            if "请检查" in prompt:
                content = "PASS" if self.calls >= 4 else "缺少边界说明"
            else:
                content = f"answer-{self.calls}"
            return LLMResponse(content=content, success=True, cost_usd=0.01, latency_ms=1.0)

    gateway = RetryGateway()
    _, trace = await ThinkingUpgradePolicy(gateway).execute_with_thinking(
        "请做形式化边界验证", TaskType.GENERAL
    )
    assert len(trace.rounds) == 2
    assert trace.rounds[-1].passed


def test_trace_budget_is_bounded():
    decision = ThinkingUpgradePolicy().should_upgrade(TaskType.GENERAL, "请进行多步推理")
    assert decision.budget.max_rounds <= 3
    # H1: 预算来自 config（max_cost_per_task_usd=2.0）；旧断言 0.5 固化了预算死代码行为
    assert decision.budget.max_cost_usd <= 2.0


# ---------------------------------------------------------------------------
# 新增测试（FakeGateway 注入，不真实调 LLM）
# ---------------------------------------------------------------------------


@dataclass
class ExplodingGateway(FakeGateway):
    """第一次调用抛异常，之后返回普通结果（用于异常降级测试）。"""

    async def chat_with_routing(self, prompt, task_type, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise LLMUnavailableError("provider down")
        return LLMResponse(content="fallback-answer", success=True, cost_usd=0.01, latency_ms=1.0)


@pytest.mark.asyncio
async def test_exception_downgrades_to_plain_path():
    """1. 异常降级：downgrade_on_failure=True 时网关抛异常 → 返回普通路径结果，不裸抛。"""
    gateway = ExplodingGateway()
    config = {"max_rounds": 3, "downgrade_on_failure": True, "max_cost_usd": 2.0}
    answer, trace = await ThinkingUpgradePolicy(gateway, config).execute_with_thinking(
        "请做三维坐标校准", TaskType.GENERAL
    )
    assert answer == "fallback-answer"
    assert trace.decision.should_upgrade
    assert len(trace.rounds) == 0
    assert "downgraded" in trace.decision.reason
    assert trace.error is not None


@dataclass
class SlowCheckGateway(FakeGateway):
    """审查调用较慢 → 触发 wait_for 超时。"""

    async def chat_with_routing(self, prompt, task_type, **kwargs):
        self.calls += 1
        if "请检查" in prompt:
            await asyncio.sleep(0.5)
        content = "PASS" if "请检查" in prompt else f"answer-{self.calls}"
        return LLMResponse(content=content, success=True, cost_usd=0.01, latency_ms=2.0)


@pytest.mark.asyncio
async def test_timeout_bounds_total_time_and_returns_partial():
    """2. 超时：很小 timeout_seconds + 慢调用 → 总耗时受限且返回部分轮次轨迹。"""
    gateway = SlowCheckGateway()
    config = {
        "max_rounds": 3,
        "timeout_seconds": 0.1,
        "downgrade_on_failure": False,
        "max_cost_usd": 2.0,
    }
    started = time.monotonic()
    answer, trace = await ThinkingUpgradePolicy(gateway, config).execute_with_thinking(
        "请做三维坐标校准", TaskType.GENERAL
    )
    elapsed = time.monotonic() - started
    assert elapsed < 0.5  # 总耗时受限（慢调用 0.5s 被 wait_for 截断）
    assert trace.error == "timeout"
    assert len(trace.rounds) == 1  # 部分轮次轨迹
    assert answer.startswith("answer-")


@dataclass
class ExpensiveGateway(FakeGateway):
    """每次调用成本较高 → 首轮累计即触发成本上限。"""

    async def chat_with_routing(self, prompt, task_type, **kwargs):
        self.calls += 1
        content = "PASS" if "请检查" in prompt else f"answer-{self.calls}"
        return LLMResponse(content=content, success=True, cost_usd=1.5, latency_ms=1.0)


@pytest.mark.asyncio
async def test_cost_cap_stops_early():
    """3. 成本上限：累计成本超 max_cost_usd → 提前中止。"""
    gateway = ExpensiveGateway()
    config = {"max_rounds": 3, "max_cost_usd": 2.0, "downgrade_on_failure": False}
    answer, trace = await ThinkingUpgradePolicy(gateway, config).execute_with_thinking(
        "请做三维坐标校准", TaskType.GENERAL
    )
    assert len(trace.rounds) == 1  # 首轮（回答+审查 $3.0）即达上限，提前中止
    assert trace.error == "cost_capped"
    assert trace.total_cost_usd >= 2.0
    assert answer.startswith("answer-")


def test_trigger_false_positives_do_not_upgrade():
    """4. 触发词假阳性：子串包含 prove/lean/formal 但不触发升级。"""
    policy = ThinkingUpgradePolicy()
    for text in ("improve the layout", "clean the composition", "informal"):
        decision = policy.should_upgrade(TaskType.GENERAL, text)
        assert not decision.should_upgrade, f"{text!r} 不应触发升级"
        assert decision.reason == "no_trigger"


def test_self_check_chinese_pass():
    """5. PASS 中文判定：'全部通过' → True；'不通过，需修正' → False。"""
    assert ThinkingUpgradePolicy._self_check_passed("全部通过") is True
    assert ThinkingUpgradePolicy._self_check_passed("不通过，需修正") is False


def test_self_check_bypass_false_positive():
    """6. PASS 假阳性：'bypass the safety' → passed=False。"""
    assert ThinkingUpgradePolicy._self_check_passed("bypass the safety") is False
    assert ThinkingUpgradePolicy._self_check_passed("") is False
    assert ThinkingUpgradePolicy._self_check_passed("  ") is False


@pytest.mark.asyncio
async def test_max_rounds_zero_no_index_error():
    """7. max_rounds=0：不进入升级循环，走降级路径不抛 IndexError。"""
    gateway = FakeGateway()
    config = {"max_rounds": 0, "downgrade_on_failure": False, "max_cost_usd": 2.0}
    answer, trace = await ThinkingUpgradePolicy(gateway, config).execute_with_thinking(
        "请做三维坐标校准", TaskType.GENERAL
    )
    assert len(trace.rounds) == 0
    assert "max_rounds_zero_downgraded" in trace.decision.reason
    assert gateway.calls == 1  # 只走一次普通调用
    assert answer.startswith("answer-")


@pytest.mark.asyncio
async def test_non_upgrade_execute_plain_path():
    """8. 非升级路径 execute：should_upgrade=False 时 trace.rounds 为空、final_answer 来自普通调用。"""
    gateway = FakeGateway()
    answer, trace = await ThinkingUpgradePolicy(gateway).execute_with_thinking(
        "请问今天是什么日期", TaskType.GENERAL
    )
    assert trace.decision.should_upgrade is False
    assert len(trace.rounds) == 0
    assert answer.startswith("answer-")
    assert gateway.calls == 1


def test_upgraded_task_type_enum_consistency():
    """9. 枚举一致性：upgraded_task_type == 'QUALITY_REVIEW' 且 TaskType['QUALITY_REVIEW'] 可访问。"""
    decision = ThinkingUpgradePolicy().should_upgrade(TaskType.SCENE_DESCRIPTION, "请做三维坐标校准")
    assert decision.should_upgrade
    assert decision.upgraded_task_type == "QUALITY_REVIEW"
    assert TaskType["QUALITY_REVIEW"] is TaskType.QUALITY_REVIEW


def test_budget_from_config_reads_custom_values():
    """10a. 配置接线：ThinkingBudget.from_config 读取自定义 max_rounds 等字段。"""
    budget = ThinkingBudget.from_config({
        "max_rounds": 5,
        "max_tokens_per_round": 4096,
        "timeout_seconds": 60,
        "max_cost_usd": 0.9,
    })
    assert budget.max_rounds == 5
    assert budget.max_tokens_per_round == 4096
    assert budget.timeout_seconds == 60
    assert budget.max_cost_usd == 0.9
    # 旧键名兼容
    assert ThinkingBudget.from_config({"max_cost_per_task_usd": 1.2}).max_cost_usd == 1.2


@pytest.mark.asyncio
async def test_chat_with_thinking_upgrade_disabled_goes_plain(monkeypatch):
    """10b. 配置接线：enabled=False 时 chat_with_thinking_upgrade 直接走普通路径。"""
    from core import llm_gateway as lg

    async def fake_plain(prompt, task_type, **kwargs):
        return LLMResponse(content="plain-answer", success=True, cost_usd=0.0, latency_ms=1.0)

    monkeypatch.setattr(lg, "chat_with_routing", fake_plain)
    answer, trace = await chat_with_thinking_upgrade(
        "请做三维坐标校准", TaskType.GENERAL, config={"enabled": False}
    )
    assert answer == "plain-answer"
    assert trace.decision.should_upgrade is False
    assert trace.decision.reason == "disabled"
    assert len(trace.rounds) == 0


@dataclass
class FailingGateway(FakeGateway):
    """普通调用返回 success=False。"""

    async def chat_with_routing(self, prompt, task_type, **kwargs):
        self.calls += 1
        return LLMResponse(content="", success=False, error="boom", cost_usd=0.0, latency_ms=0.0)


@pytest.mark.asyncio
async def test_non_upgrade_success_false_marks_error():
    """11. success=False 非升级路径：trace.error 被标记。"""
    gateway = FailingGateway()
    answer, trace = await ThinkingUpgradePolicy(gateway).execute_with_thinking(
        "请问今天是什么日期", TaskType.GENERAL
    )
    assert trace.error == "llm_call_failed"
    assert answer == ""


@dataclass
class RecordingGateway(FakeGateway):
    """记录每次调用的 task_type。"""

    task_types: list = field(default_factory=list)

    async def chat_with_routing(self, prompt, task_type, **kwargs):
        self.calls += 1
        self.task_types.append(task_type)
        content = "PASS" if "请检查" in prompt else f"answer-{self.calls}"
        return LLMResponse(content=content, success=True, cost_usd=0.01, latency_ms=2.0)


@pytest.mark.asyncio
async def test_review_round_uses_tier3():
    """12. 审查轮也用 TIER_3：第二次调用 task_type == TaskType.QUALITY_REVIEW。"""
    gateway = RecordingGateway()
    await ThinkingUpgradePolicy(gateway).execute_with_thinking(
        "请做三维坐标校准", TaskType.GENERAL
    )
    assert len(gateway.task_types) == 2
    assert gateway.task_types[0] == TaskType.QUALITY_REVIEW  # 回答轮
    assert gateway.task_types[1] == TaskType.QUALITY_REVIEW  # 审查轮
