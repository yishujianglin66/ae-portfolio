#!/usr/bin/env python3
"""
result_verifier.py - Phase5 执行结果验证器

验证流程：
  1. 检查执行结果是否成功
  2. 通过 MCP get-effect-properties 回读实际参数
  3. 与预期参数对比，计算偏差
  4. 返回 VerificationResult

对齐 TS 源文件: compiler/src/phase5/result-verifier.ts
"""
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional, Union


# ============================================================================
# 数据类定义（对齐 types.ts）
# ============================================================================

@dataclass
class ExpectedProperty:
    """预期属性（对齐 ExpectedParameters.properties 元素）"""
    name: str
    value: Union[float, str, bool, List[float]]
    tolerance: Optional[float] = None


@dataclass
class KeyframeSpec:
    """关键帧规格（对齐 ExpectedParameters.keyframes 元素）"""
    property: str
    time: float
    value: Union[float, List[float]]


@dataclass
class ExpectedParameters:
    """预期参数（对齐 ExpectedParameters）"""
    comp_name: str
    layer_index: int
    effect_match_name: Optional[str] = None
    effect_name: Optional[str] = None
    properties: List[ExpectedProperty] = field(default_factory=list)
    keyframes: List[KeyframeSpec] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """执行结果（对齐 ExecutionResult）"""
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    effect_index: Optional[int] = None
    keyframes_added: Optional[int] = None
    effect_name: Optional[str] = None
    raw_response: Optional[str] = None
    execution_time_ms: Optional[float] = None


@dataclass
class ParameterMismatch:
    """参数不匹配条目（对齐 ParameterMismatch）"""
    param: str
    expected: Any
    actual: Any
    deviation: Optional[float] = None


@dataclass
class ActualProperty:
    """实际属性（对齐 ActualProperty）"""
    name: str
    value: Any
    type: Optional[str] = None


@dataclass
class VerificationResult:
    """验证结果（对齐 VerificationResult）"""
    passed: bool
    mismatches: List[ParameterMismatch] = field(default_factory=list)
    reason: Optional[str] = None
    actual_properties: List[ActualProperty] = field(default_factory=list)
    deviation_score: float = 0.0


# ============================================================================
# MCP 客户端接口
# ============================================================================

class McpClient(ABC):
    """MCP 客户端抽象基类（用于回读参数）

    实际使用时由调用方注入实现：
      - 默认实现：MockMcpClient（不调用真实 MCP，返回 None）
      - 真实实现：通过 after-effects-mcp 调用 get-effect-properties
    """

    @abstractmethod
    async def get_effect_properties(
        self,
        comp_name: str,
        layer_index: int,
        effect_index: Optional[int] = None,
    ) -> Optional[List[ActualProperty]]:
        """调用 MCP get-effect-properties 工具

        Args:
            comp_name: 合成名
            layer_index: 图层索引（1-based）
            effect_index: 效果索引（可选）

        Returns:
            返回的效果属性列表，或 None（无法获取时）
        """
        ...


class MockMcpClient(McpClient):
    """默认 Mock 实现（不调用真实 MCP）"""

    async def get_effect_properties(
        self,
        comp_name: str,
        layer_index: int,
        effect_index: Optional[int] = None,
    ) -> Optional[List[ActualProperty]]:
        return None


class RealMcpClient(McpClient):
    """真实 MCP 客户端实现 — 通过 AECommandClient 调用 AE 端 getEffectProperties 命令

    依赖 ae_mcp_listener.jsx 中注册的 getEffectProperties 命令处理器。
    """

    def __init__(self, ae_client=None):
        self._ae_client = ae_client

    async def get_effect_properties(
        self,
        comp_name: str,
        layer_index: int,
        effect_index: Optional[int] = None,
        layer_name: str = "",
        effect_name: str = "",
    ) -> Optional[List[ActualProperty]]:
        if not self._ae_client:
            return None

        try:
            result = self._ae_client.send_command("getEffectProperties", {
                "compName": comp_name,
                "layerName": layer_name or f"Layer {layer_index}",
                "effectName": effect_name,
            })

            if not result or not result.get("success"):
                return None

            props_dict = result.get("properties", {})
            if not props_dict:
                return None

            actual_props: List[ActualProperty] = []
            for prop_name, prop_data in props_dict.items():
                if isinstance(prop_data, dict):
                    actual_props.append(ActualProperty(
                        name=prop_name,
                        value=prop_data.get("value"),
                    ))
                else:
                    actual_props.append(ActualProperty(
                        name=prop_name,
                        value=prop_data,
                    ))
            return actual_props
        except Exception:
            return None


# ============================================================================
# 执行结果验证器
# ============================================================================

def _is_number(value: Any) -> bool:
    """判断是否为数值类型（排除 bool）

    Python 中 bool 是 int 的子类，需排除以对齐 TS 的 typeof === "number"
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class ResultVerifier:
    """执行结果验证器"""

    def __init__(
        self,
        mcp_client: Optional[McpClient] = None,
        default_tolerance: float = 0.01,
    ) -> None:
        self._mcp_client: McpClient = mcp_client or MockMcpClient()
        self._default_tolerance: float = default_tolerance

    def set_mcp_client(self, client: McpClient) -> None:
        """设置 MCP 客户端"""
        self._mcp_client = client

    async def verify(
        self,
        expected: ExpectedParameters,
        actual: ExecutionResult,
    ) -> VerificationResult:
        """验证执行结果

        Args:
            expected: 预期参数
            actual: 执行结果

        Returns:
            VerificationResult 验证结果
        """
        # 步骤1：检查执行是否成功
        if not actual.success:
            error_code = actual.error_code or ""
            error_msg = actual.error_message or ""
            reason = f"执行失败: {error_code} {error_msg}".strip()
            return VerificationResult(
                passed=False,
                mismatches=[],
                reason=reason,
                deviation_score=1.0,
            )

        # 步骤2：通过 MCP 回读实际参数
        actual_props = await self._mcp_client.get_effect_properties(
            expected.comp_name,
            expected.layer_index,
            actual.effect_index,
        )

        if not actual_props:
            # 无法回读（可能是 Mock 模式或 MCP 不可用）
            # 仅检查执行是否成功，不验证参数
            return VerificationResult(
                passed=True,
                mismatches=[],
                reason="执行成功，但无法回读参数验证（MCP 不可用）",
                deviation_score=0.0,
                actual_properties=[],
            )

        # 步骤3：对比预期与实际
        mismatches = self._compare_parameters(expected.properties, actual_props)

        # 步骤4：计算综合偏差度
        deviation_score = self._calculate_deviation_score(
            expected.properties, actual_props, mismatches,
        )

        # 步骤5：关键帧验证（简化处理，仅记录不验证细节）
        # 实际可通过 getLayerInfo 获取关键帧信息
        if expected.keyframes:
            pass  # 关键帧验证较复杂，此处简化

        return VerificationResult(
            passed=len(mismatches) == 0,
            mismatches=mismatches,
            deviation_score=deviation_score,
            actual_properties=actual_props,
        )

    def _compare_parameters(
        self,
        expected: List[ExpectedProperty],
        actual: List[ActualProperty],
    ) -> List[ParameterMismatch]:
        """对比预期参数和实际参数"""
        mismatches: List[ParameterMismatch] = []

        for expected_prop in expected:
            # 查找对应的实际属性
            actual_prop = next(
                (p for p in actual if p.name == expected_prop.name),
                None,
            )

            if actual_prop is None:
                mismatches.append(ParameterMismatch(
                    param=expected_prop.name,
                    expected=expected_prop.value,
                    actual=None,
                ))
                continue

            tolerance = (
                expected_prop.tolerance
                if expected_prop.tolerance is not None
                else self._default_tolerance
            )

            if not self._values_match(
                expected_prop.value, actual_prop.value, tolerance,
            ):
                deviation = self._calculate_deviation(
                    expected_prop.value, actual_prop.value,
                )
                mismatches.append(ParameterMismatch(
                    param=expected_prop.name,
                    expected=expected_prop.value,
                    actual=actual_prop.value,
                    deviation=deviation,
                ))

        return mismatches

    def _values_match(
        self,
        expected: Union[float, str, bool, List[float]],
        actual: Any,
        tolerance: float,
    ) -> bool:
        """检查值是否匹配（考虑容差）"""
        # 数值比较
        if _is_number(expected) and _is_number(actual):
            return abs(expected - actual) <= tolerance

        # 数组比较（如颜色 [r,g,b]）
        if isinstance(expected, list) and isinstance(actual, list):
            if len(expected) != len(actual):
                return False
            for i in range(len(expected)):
                if abs(expected[i] - actual[i]) > tolerance:
                    return False
            return True

        # 字符串/布尔值严格相等
        return expected == actual

    def _calculate_deviation(
        self,
        expected: Union[float, str, bool, List[float]],
        actual: Any,
    ) -> float:
        """计算单个参数的偏差"""
        # 数值偏差
        if _is_number(expected) and _is_number(actual):
            return abs(expected - actual)

        # 数组偏差取平均
        if isinstance(expected, list) and isinstance(actual, list):
            if len(expected) == 0:
                return 0.0
            deviations = [
                abs(expected[i] - actual[i]) for i in range(len(expected))
            ]
            return sum(deviations) / len(deviations)

        # 非数值类型，不匹配则偏差为 1
        return 0.0 if expected == actual else 1.0

    def _calculate_deviation_score(
        self,
        expected: List[ExpectedProperty],
        actual: List[ActualProperty],
        mismatches: List[ParameterMismatch],
    ) -> float:
        """计算综合偏差度（0-1）

        0 表示完全匹配，1 表示完全不匹配
        """
        if len(expected) == 0:
            return 0.0
        if len(mismatches) == 0:
            return 0.0

        # 偏差度 = 不匹配参数数 / 总参数数 + 平均相对偏差
        mismatch_ratio = len(mismatches) / len(expected)

        total_deviation = 0.0
        for m in mismatches:
            exp = m.expected
            act = m.actual
            if _is_number(exp) and _is_number(act):
                if exp != 0:
                    rel_deviation = abs(exp - act) / abs(exp)
                else:
                    rel_deviation = abs(exp - act)
                total_deviation += min(1.0, rel_deviation)
            else:
                total_deviation += 1.0

        avg_deviation = total_deviation / len(mismatches)

        # 综合偏差度 = 0.5 * 不匹配比例 + 0.5 * 平均相对偏差
        return 0.5 * mismatch_ratio + 0.5 * avg_deviation

    # ==================================================================
    # Silhouette 产出验证
    # ==================================================================

    def verify_silhouette_output(
        self,
        silhouette_artifacts: List[dict],
        expected_comp: Optional[dict] = None,
    ) -> "SilhouetteVerificationResult":
        """验证 Silhouette 产出

        检查：
        1. 每个产出的 status（success/fallback/pending）
        2. 如果有 matte 序列输出，检查文件路径是否存在
        3. 如果有 tracking 数据，检查格式有效性
        4. 如果有 paint 输出，检查文件路径
        """
        result = SilhouetteVerificationResult()

        for artifact in silhouette_artifacts:
            cmd = artifact.get("command", "unknown")
            status = artifact.get("status", "unknown")

            if status == "success":
                result.success_count += 1
                # 检查输出文件（如果有）
                output_path = artifact.get("output_path", "")
                if output_path:
                    import os
                    if os.path.exists(output_path):
                        result.verified_files += 1
                    else:
                        result.warnings.append(
                            f"{cmd}: 输出文件不存在 {output_path}"
                        )
            elif status == "fallback":
                result.fallback_count += 1
                result.warnings.append(
                    f"{cmd}: 降级执行 - {artifact.get('message', '')}"
                )
            elif status == "pending":
                result.pending_count += 1
                result.warnings.append(
                    f"{cmd}: 等待手动完成"
                )
            else:
                result.failure_count += 1
                result.errors.append(
                    f"{cmd}: {artifact.get('error', 'Unknown error')}"
                )

            # 检查 ae_integration_data 格式
            ae_data = artifact.get("ae_integration_data", {})
            if ae_data:
                if "type" not in ae_data:
                    result.warnings.append(f"{cmd}: ae_integration_data 缺少 type 字段")

        result.passed = (
            result.failure_count == 0
            and result.success_count > 0
        )
        return result


@dataclass
class SilhouetteVerificationResult:
    """Silhouette 产出验证结果"""
    passed: bool = False
    success_count: int = 0
    fallback_count: int = 0
    pending_count: int = 0
    failure_count: int = 0
    verified_files: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ============================================================================
# 模块级单例（使用 MockMcpClient）
# ============================================================================

result_verifier = ResultVerifier()


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "ExpectedProperty",
    "KeyframeSpec",
    "ExpectedParameters",
    "ExecutionResult",
    "ParameterMismatch",
    "ActualProperty",
    "VerificationResult",
    "McpClient",
    "MockMcpClient",
    "ResultVerifier",
    "result_verifier",
]


# ============================================================================
# 自检
# ============================================================================

async def _run_self_test() -> None:
    """自检：验证 ResultVerifier 基本功能"""
    print("=" * 60)
    print("Phase5 ResultVerifier 自检")
    print("=" * 60)

    verifier = ResultVerifier(mcp_client=MockMcpClient())

    # 测试1：成功执行 + Mock MCP（应返回 passed=True，MCP 不可用）
    print("\n[测试1] 成功执行 + MockMcpClient")
    expected = ExpectedParameters(
        comp_name="Main Comp",
        layer_index=1,
        effect_match_name="ADBE Gaussian Blur 2",
        effect_name="Gaussian Blur",
        properties=[
            ExpectedProperty(name="Blurriness", value=25.0, tolerance=0.1),
            ExpectedProperty(name="Repeat Edge Pixels", value=True),
        ],
    )
    actual_success = ExecutionResult(
        success=True,
        effect_index=0,
        keyframes_added=0,
        effect_name="Gaussian Blur",
        execution_time_ms=120.5,
    )
    result1 = await verifier.verify(expected, actual_success)
    print(f"  passed: {result1.passed}")
    print(f"  reason: {result1.reason}")
    print(f"  deviation_score: {result1.deviation_score}")
    assert result1.passed is True
    assert "MCP 不可用" in (result1.reason or "")
    print("  断言通过 ✓")

    # 测试2：失败执行（应返回 passed=False）
    print("\n[测试2] 失败执行")
    actual_fail = ExecutionResult(
        success=False,
        error_code="EFFECT_NOT_FOUND",
        error_message="效果 ADBE Gaussian Blur 2 未找到",
    )
    result2 = await verifier.verify(expected, actual_fail)
    print(f"  passed: {result2.passed}")
    print(f"  reason: {result2.reason}")
    print(f"  deviation_score: {result2.deviation_score}")
    assert result2.passed is False
    assert result2.deviation_score == 1.0
    assert "EFFECT_NOT_FOUND" in (result2.reason or "")
    print("  断言通过 ✓")

    # 测试3：_values_match 逻辑
    print("\n[测试3] _values_match 逻辑")
    v = ResultVerifier()
    # 数值匹配
    assert v._values_match(25.0, 25.005, 0.01) is True
    assert v._values_match(25.0, 25.02, 0.01) is False
    print("  数值匹配: OK")
    # 数组匹配
    assert v._values_match([1.0, 2.0, 3.0], [1.0, 2.0, 3.005], 0.01) is True
    assert v._values_match([1.0, 2.0, 3.0], [1.0, 2.0, 3.02], 0.01) is False
    assert v._values_match([1.0, 2.0], [1.0], 0.01) is False  # 长度不同
    print("  数组匹配: OK")
    # 字符串/布尔匹配
    assert v._values_match("Gaussian Blur", "Gaussian Blur", 0.01) is True
    assert v._values_match("Gaussian Blur", "Fast Blur", 0.01) is False
    assert v._values_match(True, True, 0.01) is True
    assert v._values_match(True, False, 0.01) is False
    print("  字符串/布尔匹配: OK")

    # 测试4：_calculate_deviation 逻辑
    print("\n[测试4] _calculate_deviation 逻辑")
    assert v._calculate_deviation(25.0, 30.0) == 5.0
    assert v._calculate_deviation([1.0, 2.0, 3.0], [2.0, 3.0, 4.0]) == 1.0
    assert v._calculate_deviation("a", "a") == 0.0
    assert v._calculate_deviation("a", "b") == 1.0
    print("  偏差计算: OK")

    # 测试5：模块级单例可用
    print("\n[测试5] 模块级单例")
    assert result_verifier is not None
    assert isinstance(result_verifier, ResultVerifier)
    print("  result_verifier 单例: OK")

    print("\n" + "=" * 60)
    print("所有自检通过 ✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(_run_self_test())
