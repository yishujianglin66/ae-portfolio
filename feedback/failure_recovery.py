"""
failure_recovery.py
Phase 5 - 失败恢复策略模块

处理流程：
  执行失败 → 错误码识别 → 选择恢复策略 → 返回 RecoveryAction
                                               │
                                               ├── retry_with_alternative
                                               ├── retry_with_adjusted_params
                                               ├── retry_with_longer_timeout
                                               ├── wait_and_retry
                                               ├── ask_user
                                               └── report_error

重试控制：
  - 同一错误最多重试 maxRetries 次（默认 3）
  - 超过重试次数 → 升级为 ask_user 或 report_error
  - 跨错误码统计：单次执行总重试次数上限 5

对齐 TS: compiler/src/phase5/failure-recovery.ts
依赖: effect_name_map.py (find_by_match_name, get_by_category, EffectMapEntry)
"""
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from effect_name_map import EffectMapEntry, find_by_match_name, get_by_category

__all__ = [
    "ErrorCode",
    "ExpectedProperty",
    "ExpectedParameters",
    "ExecutionResult",
    "ParameterMismatch",
    "RecoveryAction",
    "FailureRecoveryOptions",
    "RetryCounter",
    "FailureRecovery",
    "failure_recovery",
]


# ---------------------------------------------------------------------------
# 错误码定义
# ---------------------------------------------------------------------------

class ErrorCode(str, Enum):
    """错误码定义（继承 str 以便字符串比较）

    使用方式：
        execution.error_code == ErrorCode.EFFECT_NOT_FOUND.value
        execution.error_code == "E300"
        execution.error_code == ErrorCode.EFFECT_NOT_FOUND  # str Enum 等价
    """
    # 传输层错误
    BRIDGE_OFFLINE = "E006"
    BRIDGE_TIMEOUT = "E007"
    MCP_NOT_RESPONDING = "E008"
    # 执行层错误
    EFFECT_NOT_FOUND = "E300"
    PARAM_OUT_OF_RANGE = "E303"
    LAYER_NOT_FOUND = "E304"
    COMP_NOT_FOUND = "E305"
    PROPERTY_NOT_FOUND = "E306"
    KEYFRAME_FAILED = "E307"
    EXPRESSION_ERROR = "E308"
    # 超时/资源错误
    EXECUTION_TIMEOUT = "E600"
    OUT_OF_MEMORY = "E601"
    # 未知错误
    UNKNOWN = "E000"


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class ExpectedProperty:
    """期望属性"""
    name: str
    value: Any
    tolerance: float | None = None


@dataclass
class ExpectedParameters:
    """期望参数"""
    comp_name: str
    layer_index: int
    effect_match_name: str | None = None
    effect_name: str | None = None
    properties: list[ExpectedProperty] = field(default_factory=list)
    keyframes: list[Any] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    error_code: str | None = None
    error_message: str | None = None
    effect_index: int | None = None
    keyframes_added: int | None = None
    effect_name: str | None = None
    raw_response: str | None = None
    execution_time_ms: float | None = None


@dataclass
class ParameterMismatch:
    """参数不匹配信息"""
    param: str
    expected: Any
    actual: Any
    deviation: float | None = None


@dataclass
class RecoveryAction:
    """恢复动作"""
    action: str
    alternative: str | None = None
    adjusted_params: ExpectedParameters | None = None
    timeout: int | None = None
    delay: int | None = None
    max_retries: int | None = None
    message: str | None = None


@dataclass
class FailureRecoveryOptions:
    """失败恢复选项（所有字段 None 表示使用默认值）"""
    default_timeout: int | None = None
    timeout_backoff_factor: float | None = None
    max_timeout: int | None = None
    initial_retry_delay: int | None = None
    retry_backoff_factor: float | None = None
    max_retries: int | None = None


# ---------------------------------------------------------------------------
# 重试计数器
# ---------------------------------------------------------------------------

class RetryCounter:
    """重试计数器

    - 单请求维度：同一 requestId 最多重试 max_retries 次
    - 全局维度：单请求总重试次数不超过 global_max_retries
    """

    def __init__(self, max_retries: int = 3, global_max_retries: int = 5):
        self._max_retries = max_retries
        self._global_max_retries = global_max_retries
        self._counts: dict[str, int] = {}

    def get_count(self, request_id: str) -> int:
        """获取指定请求的重试次数"""
        return self._counts.get(request_id, 0)

    def increment(self, request_id: str) -> int:
        """增加指定请求的重试次数，返回新次数"""
        current = self._counts.get(request_id, 0)
        new_count = current + 1
        self._counts[request_id] = new_count
        return new_count

    def can_retry(self, request_id: str) -> bool:
        """判断是否还能重试"""
        current = self.get_count(request_id)
        return (
            current < self._max_retries
            and current < self._global_max_retries
        )

    def reset(self, request_id: str) -> None:
        """重置指定请求的重试计数"""
        self._counts.pop(request_id, None)


# ---------------------------------------------------------------------------
# 失败恢复
# ---------------------------------------------------------------------------

class FailureRecovery:
    """失败恢复策略

    根据 ExecutionResult.error_code 选择合适的恢复策略：
      - EFFECT_NOT_FOUND      → 查找同类原生替代效果
      - PARAM_OUT_OF_RANGE    → 自动调整数值参数
      - EXECUTION_TIMEOUT     → 延展超时时间
      - BRIDGE_OFFLINE/MCP    → 等待后重试（指数退避）
      - LAYER/COMP/PROPERTY   → 升级为 ask_user
      - KEYFRAME/EXPR/OOM     → 升级为 report_error
    """

    def __init__(
        self,
        options: FailureRecoveryOptions | None = None,
        retry_counter: RetryCounter | None = None,
    ):
        opts = options or FailureRecoveryOptions()
        # 应用默认值
        default_timeout = (
            opts.default_timeout if opts.default_timeout is not None else 10000
        )
        timeout_backoff_factor = (
            opts.timeout_backoff_factor
            if opts.timeout_backoff_factor is not None
            else 1.5
        )
        max_timeout = (
            opts.max_timeout if opts.max_timeout is not None else 60000
        )
        initial_retry_delay = (
            opts.initial_retry_delay
            if opts.initial_retry_delay is not None
            else 3000
        )
        retry_backoff_factor = (
            opts.retry_backoff_factor
            if opts.retry_backoff_factor is not None
            else 2.0
        )
        max_retries = (
            opts.max_retries if opts.max_retries is not None else 3
        )
        self._options: dict[str, Any] = {
            "default_timeout": default_timeout,
            "timeout_backoff_factor": timeout_backoff_factor,
            "max_timeout": max_timeout,
            "initial_retry_delay": initial_retry_delay,
            "retry_backoff_factor": retry_backoff_factor,
            "max_retries": max_retries,
        }
        self._retry_counter = retry_counter or RetryCounter(max_retries)
        self._current_retry_delay: int = initial_retry_delay

    async def handle_failure(
        self,
        execution: ExecutionResult,
        expected: ExpectedParameters,
        request_id: str | None = None,
    ) -> RecoveryAction:
        """处理执行失败，返回恢复动作"""
        error_code = execution.error_code or ErrorCode.UNKNOWN.value
        req_id = request_id or f"req_{int(time.time() * 1000)}"

        # 达到最大重试次数 → 升级为 ask_user
        if not self._retry_counter.can_retry(req_id):
            msg = (
                f"已达到最大重试次数 ({self._options['max_retries']})，"
                f"请人工介入。最后错误: {error_code} "
                f"{execution.error_message or ''}"
            ).strip()
            return RecoveryAction(
                action="ask_user",
                message=msg,
                max_retries=self._options["max_retries"],
            )

        # 根据错误码分发到对应处理器
        if error_code == ErrorCode.EFFECT_NOT_FOUND.value:
            action = await self._handle_effect_not_found(expected)
        elif error_code == ErrorCode.PARAM_OUT_OF_RANGE.value:
            action = self._handle_param_out_of_range(expected)
        elif error_code == ErrorCode.EXECUTION_TIMEOUT.value:
            action = self._handle_timeout()
        elif error_code == ErrorCode.BRIDGE_OFFLINE.value:
            action = self._handle_bridge_offline()
        elif error_code == ErrorCode.MCP_NOT_RESPONDING.value:
            action = self._handle_bridge_offline()
        elif error_code in (
            ErrorCode.LAYER_NOT_FOUND.value,
            ErrorCode.COMP_NOT_FOUND.value,
            ErrorCode.PROPERTY_NOT_FOUND.value,
        ):
            action = RecoveryAction(
                action="ask_user",
                message=(
                    f"AE DOM 错误: {error_code} - "
                    f"{execution.error_message or '图层/合成/属性不存在'}"
                ),
            )
        elif error_code == ErrorCode.KEYFRAME_FAILED.value:
            action = RecoveryAction(
                action="report_error",
                message=f"关键帧设置失败: "
                        f"{execution.error_message or '未知原因'}",
            )
        elif error_code == ErrorCode.EXPRESSION_ERROR.value:
            action = RecoveryAction(
                action="report_error",
                message=f"表达式错误: "
                        f"{execution.error_message or '语法错误'}",
            )
        elif error_code == ErrorCode.OUT_OF_MEMORY.value:
            action = RecoveryAction(
                action="report_error",
                message="内存不足，请关闭其他程序后重试",
            )
        elif error_code == ErrorCode.BRIDGE_TIMEOUT.value:
            action = self._handle_timeout()
        else:
            action = RecoveryAction(
                action="report_error",
                message=(
                    f"未知错误: {error_code} "
                    f"{execution.error_message or ''}"
                ).strip(),
            )

        self._retry_counter.increment(req_id)
        return action

    async def _handle_effect_not_found(
        self, expected: ExpectedParameters
    ) -> RecoveryAction:
        """处理效果未找到错误：尝试使用同类原生替代效果"""
        if not expected.effect_match_name:
            return RecoveryAction(
                action="ask_user",
                message="效果未安装且无法确定替代方案，"
                        "请安装对应插件或选择其他效果",
            )
        current_entry: EffectMapEntry | None = find_by_match_name(
            expected.effect_match_name
        )
        if not current_entry:
            return RecoveryAction(
                action="ask_user",
                message=f"效果 {expected.effect_match_name} 未安装，"
                        f"无法找到替代方案",
            )
        # 查找同类原生替代效果（排除自身）
        alternatives = [
            e for e in get_by_category(current_entry.category)
            if e.match_name != current_entry.match_name
            and e.source == "native"
        ]
        if not alternatives:
            return RecoveryAction(
                action="ask_user",
                message=(
                    f"效果 {current_entry.display_name} 未安装，"
                    f"无可用替代方案。请安装插件: {current_entry.source}"
                ),
            )
        alternative = alternatives[0]
        return RecoveryAction(
            action="retry_with_alternative",
            alternative=alternative.match_name,
            message=(
                f"效果 {current_entry.display_name} 未安装，"
                f"尝试使用替代效果: {alternative.display_name}"
            ),
            max_retries=self._options["max_retries"],
        )

    def _handle_param_out_of_range(
        self, expected: ExpectedParameters
    ) -> RecoveryAction:
        """处理参数超出范围错误：自动调整数值（正值乘 0.9，负值乘 1.1）"""
        adjusted_props: list[ExpectedProperty] = []
        for p in expected.properties:
            # bool 是 int 的子类，需排除；仅调整数值类型
            if isinstance(p.value, (int, float)) and not isinstance(p.value, bool):
                adjusted = (
                    p.value * 0.9 if p.value >= 0 else p.value * 1.1
                )
                adjusted_props.append(ExpectedProperty(
                    name=p.name,
                    value=adjusted,
                    tolerance=p.tolerance,
                ))
            else:
                adjusted_props.append(p)
        new_expected = ExpectedParameters(
            comp_name=expected.comp_name,
            layer_index=expected.layer_index,
            effect_match_name=expected.effect_match_name,
            effect_name=expected.effect_name,
            properties=adjusted_props,
            keyframes=list(expected.keyframes),
        )
        return RecoveryAction(
            action="retry_with_adjusted_params",
            adjusted_params=new_expected,
            message="参数值超出范围，已自动调整数值",
            max_retries=self._options["max_retries"],
        )

    def _handle_timeout(self) -> RecoveryAction:
        """处理超时错误：按 backoff 因子延展超时时间"""
        new_timeout = min(
            self._options["default_timeout"]
            * self._options["timeout_backoff_factor"],
            self._options["max_timeout"],
        )
        new_timeout_int = round(new_timeout)
        return RecoveryAction(
            action="retry_with_longer_timeout",
            timeout=new_timeout_int,
            message=f"执行超时，重试时延展超时到 {new_timeout_int}ms",
            max_retries=self._options["max_retries"],
        )

    def _handle_bridge_offline(self) -> RecoveryAction:
        """处理 Bridge 离线错误：等待后重试（指数退避 + jitter，上限 30s）

        退避策略: delay = base * (factor ^ attempt) + random_jitter
        jitter 范围: [0, base * 0.1]，防止多客户端同步重试
        """
        import random
        base_delay = self._current_retry_delay
        # 指数退避 + 随机抖动 (jitter)
        jitter = random.randint(0, max(1, base_delay // 10))
        delay = min(base_delay + jitter, 30000)
        # 下一次退避基数按因子增长
        self._current_retry_delay = min(
            int(self._current_retry_delay
                * self._options["retry_backoff_factor"]),
            30000,
        )
        return RecoveryAction(
            action="wait_and_retry",
            delay=delay,
            max_retries=self._options["max_retries"],
            message=f"Bridge 离线，等待 {delay}ms 后重试 (jitter={jitter}ms)",
        )

    def reset_retry_count(self, request_id: str) -> None:
        """重置指定请求的重试计数，并恢复初始 retry delay"""
        self._retry_counter.reset(request_id)
        self._current_retry_delay = self._options["initial_retry_delay"]

    def get_retry_counter(self) -> RetryCounter:
        """获取内部重试计数器"""
        return self._retry_counter

    @staticmethod
    def build_adjusted_params(
        expected: ExpectedParameters,
        mismatches: list[ParameterMismatch],
    ) -> ExpectedParameters:
        """根据参数不匹配信息构建调整后的参数

        遍历 expected.properties，若某属性在 mismatches 中存在且 actual 非 None，
        则使用 actual 值替换；否则保持原值。tolerance 等元信息保留。
        """
        adjusted_props: list[ExpectedProperty] = []
        for p in expected.properties:
            mismatch = next(
                (m for m in mismatches if m.param == p.name), None
            )
            if mismatch is not None and mismatch.actual is not None:
                adjusted_props.append(ExpectedProperty(
                    name=p.name,
                    value=mismatch.actual,
                    tolerance=p.tolerance,
                ))
            else:
                adjusted_props.append(p)
        return ExpectedParameters(
            comp_name=expected.comp_name,
            layer_index=expected.layer_index,
            effect_match_name=expected.effect_match_name,
            effect_name=expected.effect_name,
            properties=adjusted_props,
            keyframes=list(expected.keyframes),
        )


# ---------------------------------------------------------------------------
# 模块级单例
# ---------------------------------------------------------------------------

failure_recovery = FailureRecovery()


# ---------------------------------------------------------------------------
# 模块自检
# ---------------------------------------------------------------------------

async def _self_test() -> None:
    """模块自检：覆盖主要错误码与边界条件"""
    print("=" * 70)
    print("[failure_recovery] 自检开始")
    print("=" * 70)

    # 1. ErrorCode 值
    print("\n[1] ErrorCode 值检查")
    assert ErrorCode.EFFECT_NOT_FOUND.value == "E300"
    assert ErrorCode.EFFECT_NOT_FOUND == "E300"  # str Enum 等价比较
    assert ErrorCode.BRIDGE_OFFLINE.value == "E006"
    assert ErrorCode.UNKNOWN.value == "E000"
    print(f"  EFFECT_NOT_FOUND = {ErrorCode.EFFECT_NOT_FOUND.value} ✓")
    print(f"  BRIDGE_OFFLINE   = {ErrorCode.BRIDGE_OFFLINE.value} ✓")
    print(f"  UNKNOWN          = {ErrorCode.UNKNOWN.value} ✓")

    # 2. RetryCounter
    print("\n[2] RetryCounter 测试")
    counter = RetryCounter(max_retries=3, global_max_retries=5)
    assert counter.get_count("req1") == 0
    assert counter.can_retry("req1") is True
    n = counter.increment("req1")
    assert n == 1
    assert counter.get_count("req1") == 1
    counter.increment("req1")
    counter.increment("req1")
    assert counter.get_count("req1") == 3
    assert counter.can_retry("req1") is False  # 达到 max_retries=3
    counter.reset("req1")
    assert counter.get_count("req1") == 0
    assert counter.can_retry("req1") is True
    print("  increment / can_retry / reset 全部通过 ✓")

    # 3. handle_failure - EFFECT_NOT_FOUND
    print("\n[3] handle_failure - EFFECT_NOT_FOUND")
    fr = FailureRecovery()
    exec_result = ExecutionResult(
        success=False,
        error_code="E300",
        error_message="Glow not found",
    )
    expected = ExpectedParameters(
        comp_name="Comp 1",
        layer_index=1,
        effect_match_name="ADBE Glo2",
        properties=[
            ExpectedProperty(name="Glow Radius", value=20.0),
            ExpectedProperty(name="Glow Intensity", value=1.5),
        ],
    )
    action = await fr.handle_failure(
        exec_result, expected, request_id="test_eff"
    )
    print(f"  action      = {action.action}")
    print(f"  alternative = {action.alternative}")
    print(f"  message     = {action.message}")
    assert action.action == "retry_with_alternative"
    assert action.alternative == "ADBE Deep Glow"
    print("  ✓ 使用 ADBE Deep Glow 作为替代效果")

    # 4. handle_failure - PARAM_OUT_OF_RANGE
    print("\n[4] handle_failure - PARAM_OUT_OF_RANGE")
    exec_param = ExecutionResult(
        success=False,
        error_code="E303",
        error_message="Glow Radius out of range",
    )
    expected_param = ExpectedParameters(
        comp_name="Comp 1",
        layer_index=1,
        effect_match_name="ADBE Glo2",
        properties=[
            ExpectedProperty(name="Glow Radius", value=100.0),
            ExpectedProperty(name="Label", value="hello"),
        ],
    )
    action = await fr.handle_failure(
        exec_param, expected_param, request_id="test_param"
    )
    print(f"  action  = {action.action}")
    print(f"  message = {action.message}")
    assert action.action == "retry_with_adjusted_params"
    assert action.adjusted_params is not None
    radius = action.adjusted_params.properties[0]
    label = action.adjusted_params.properties[1]
    print(f"  Glow Radius: 100.0 → {radius.value}")
    print(f"  Label (非数值): {label.value}")
    assert abs(radius.value - 90.0) < 1e-6  # 100 * 0.9 = 90
    assert label.value == "hello"
    print("  ✓ 数值参数向 0 调整 10%，非数值参数保持原值")

    # 5. handle_failure - EXECUTION_TIMEOUT
    print("\n[5] handle_failure - EXECUTION_TIMEOUT")
    exec_timeout = ExecutionResult(
        success=False,
        error_code="E600",
        error_message="Execution timed out",
    )
    action = await fr.handle_failure(
        exec_timeout, expected_param, request_id="test_timeout"
    )
    print(f"  action  = {action.action}")
    print(f"  timeout = {action.timeout}")
    print(f"  message = {action.message}")
    assert action.action == "retry_with_longer_timeout"
    assert action.timeout == 15000  # 10000 * 1.5
    print("  ✓ 超时从 10000ms 延展到 15000ms")

    # 6. handle_failure - BRIDGE_OFFLINE
    print("\n[6] handle_failure - BRIDGE_OFFLINE")
    exec_offline = ExecutionResult(
        success=False,
        error_code="E006",
        error_message="Bridge offline",
    )
    action = await fr.handle_failure(
        exec_offline, expected_param, request_id="test_offline"
    )
    print(f"  action  = {action.action}")
    print(f"  delay   = {action.delay}")
    print(f"  message = {action.message}")
    assert action.action == "wait_and_retry"
    assert action.delay == 3000  # 初始 retry delay
    print("  ✓ 初次等待 3000ms")

    # 7. handle_failure - KEYFRAME_FAILED
    print("\n[7] handle_failure - KEYFRAME_FAILED")
    exec_kf = ExecutionResult(
        success=False,
        error_code="E307",
        error_message="Set keyframe failed",
    )
    action = await fr.handle_failure(
        exec_kf, expected_param, request_id="test_kf"
    )
    print(f"  action  = {action.action}")
    print(f"  message = {action.message}")
    assert action.action == "report_error"
    print("  ✓ 关键帧失败 → report_error")

    # 8. handle_failure 达到最大重试次数
    print("\n[8] handle_failure - 达到最大重试次数")
    fr2 = FailureRecovery()  # max_retries=3, global_max_retries=5
    actions_seq = []
    for _ in range(5):
        a = await fr2.handle_failure(
            ExecutionResult(
                success=False,
                error_code="E307",
                error_message="kf fail",
            ),
            expected_param,
            request_id="test_max",
        )
        actions_seq.append(a.action)
    print(f"  连续 5 次调用 action 序列: {actions_seq}")
    # 前 3 次 report_error，第 4 次起升级为 ask_user
    assert actions_seq[0] == "report_error"
    assert actions_seq[1] == "report_error"
    assert actions_seq[2] == "report_error"
    assert actions_seq[3] == "ask_user"
    assert actions_seq[4] == "ask_user"
    print("  ✓ 前 3 次 report_error，达到上限后升级为 ask_user")

    # 9. build_adjusted_params 静态方法
    print("\n[9] build_adjusted_params 静态方法")
    expected_adj = ExpectedParameters(
        comp_name="Comp 1",
        layer_index=1,
        effect_match_name="ADBE Glo2",
        properties=[
            ExpectedProperty(name="Glow Radius", value=20.0, tolerance=0.1),
            ExpectedProperty(name="Glow Intensity", value=1.5),
        ],
    )
    mismatches = [
        ParameterMismatch(
            param="Glow Radius",
            expected=20.0,
            actual=18.5,
            deviation=0.075,
        ),
    ]
    new_expected = FailureRecovery.build_adjusted_params(
        expected_adj, mismatches
    )
    radius_prop = new_expected.properties[0]
    intensity_prop = new_expected.properties[1]
    print(
        f"  Glow Radius:    20.0 → {radius_prop.value} "
        f"(tolerance={radius_prop.tolerance})"
    )
    print(
        f"  Glow Intensity: 1.5 → {intensity_prop.value} "
        f"(无 mismatch，保持原值)"
    )
    assert radius_prop.value == 18.5
    assert radius_prop.tolerance == 0.1  # tolerance 保留
    assert intensity_prop.value == 1.5
    print("  ✓ mismatch 参数使用 actual，其他参数保持原值")

    print("\n" + "=" * 70)
    print("[failure_recovery] 自检全部通过 ✓")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(_self_test())
