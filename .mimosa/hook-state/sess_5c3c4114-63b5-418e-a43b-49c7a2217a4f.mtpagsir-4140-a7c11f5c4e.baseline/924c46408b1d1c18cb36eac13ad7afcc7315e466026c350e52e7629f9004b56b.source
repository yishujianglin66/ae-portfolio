"""failure_recovery 单元测试 - 失败恢复策略引擎"""
import os
import sys
import asyncio
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from failure_recovery import (
    ErrorCode,
    ExpectedProperty,
    ExpectedParameters,
    ExecutionResult,
    ParameterMismatch,
    RecoveryAction,
    FailureRecoveryOptions,
    RetryCounter,
    FailureRecovery,
    failure_recovery,
)


class TestErrorCode:
    def test_error_code_string_values(self):
        assert ErrorCode.BRIDGE_OFFLINE.value == "E006"
        assert ErrorCode.BRIDGE_TIMEOUT.value == "E007"
        assert ErrorCode.MCP_NOT_RESPONDING.value == "E008"
        assert ErrorCode.EFFECT_NOT_FOUND.value == "E300"
        assert ErrorCode.PARAM_OUT_OF_RANGE.value == "E303"
        assert ErrorCode.LAYER_NOT_FOUND.value == "E304"
        assert ErrorCode.COMP_NOT_FOUND.value == "E305"
        assert ErrorCode.PROPERTY_NOT_FOUND.value == "E306"
        assert ErrorCode.KEYFRAME_FAILED.value == "E307"
        assert ErrorCode.EXPRESSION_ERROR.value == "E308"
        assert ErrorCode.EXECUTION_TIMEOUT.value == "E600"
        assert ErrorCode.OUT_OF_MEMORY.value == "E601"
        assert ErrorCode.UNKNOWN.value == "E000"

    def test_error_code_string_comparison(self):
        assert ErrorCode.EFFECT_NOT_FOUND == "E300"
        assert ErrorCode.BRIDGE_OFFLINE == "E006"


class TestDataClasses:
    def test_expected_property_defaults(self):
        ep = ExpectedProperty(name="Glow Radius", value=20.0)
        assert ep.name == "Glow Radius"
        assert ep.value == 20.0
        assert ep.tolerance is None

    def test_expected_property_with_tolerance(self):
        ep = ExpectedProperty(name="x", value=100.0, tolerance=0.5)
        assert ep.tolerance == 0.5

    def test_expected_parameters(self):
        ep = ExpectedParameters(
            comp_name="TestComp",
            layer_index=1,
            effect_match_name="ADBE Glo2",
            effect_name="Glow",
            properties=[ExpectedProperty(name="r", value=10.0)],
            keyframes=[],
        )
        assert ep.comp_name == "TestComp"
        assert ep.layer_index == 1
        assert len(ep.properties) == 1

    def test_execution_result_success(self):
        er = ExecutionResult(success=True, keyframes_added=5)
        assert er.success is True
        assert er.keyframes_added == 5
        assert er.error_code is None

    def test_execution_result_failure(self):
        er = ExecutionResult(
            success=False,
            error_code="E300",
            error_message="Effect not found",
            effect_index=2,
        )
        assert er.success is False
        assert er.error_code == "E300"
        assert er.effect_index == 2

    def test_parameter_mismatch(self):
        pm = ParameterMismatch(
            param="Glow Radius",
            expected=20.0,
            actual=18.5,
            deviation=0.075,
        )
        assert pm.param == "Glow Radius"
        assert pm.expected == 20.0
        assert pm.actual == 18.5
        assert pm.deviation == 0.075

    def test_recovery_action(self):
        ra = RecoveryAction(
            action="retry_with_alternative",
            alternative="ADBE Deep Glow",
            message="using alternative",
        )
        assert ra.action == "retry_with_alternative"
        assert ra.alternative == "ADBE Deep Glow"


class TestRetryCounter:
    def test_initial_count(self):
        rc = RetryCounter(max_retries=3, global_max_retries=5)
        assert rc.get_count("req1") == 0
        assert rc.can_retry("req1") is True

    def test_increment(self):
        rc = RetryCounter(max_retries=3, global_max_retries=5)
        n = rc.increment("req1")
        assert n == 1
        assert rc.get_count("req1") == 1

    def test_can_retry_until_max(self):
        rc = RetryCounter(max_retries=3, global_max_retries=5)
        for i in range(3):
            assert rc.can_retry("req1") is True
            rc.increment("req1")
        assert rc.can_retry("req1") is False

    def test_global_max_retries(self):
        rc = RetryCounter(max_retries=10, global_max_retries=3)
        for i in range(3):
            assert rc.can_retry("req1") is True
            rc.increment("req1")
        assert rc.can_retry("req1") is False

    def test_reset(self):
        rc = RetryCounter(max_retries=3, global_max_retries=5)
        rc.increment("req1")
        rc.increment("req1")
        assert rc.get_count("req1") == 2

        rc.reset("req1")
        assert rc.get_count("req1") == 0
        assert rc.can_retry("req1") is True

    def test_independent_requests(self):
        rc = RetryCounter(max_retries=2, global_max_retries=10)
        rc.increment("req1")
        rc.increment("req1")
        assert rc.can_retry("req1") is False
        assert rc.can_retry("req2") is True


class TestFailureRecoveryOptions:
    def test_default_options(self):
        opts = FailureRecoveryOptions()
        assert opts.default_timeout is None
        assert opts.timeout_backoff_factor is None
        assert opts.max_timeout is None
        assert opts.initial_retry_delay is None
        assert opts.retry_backoff_factor is None
        assert opts.max_retries is None

    def test_custom_options(self):
        opts = FailureRecoveryOptions(
            default_timeout=5000,
            max_retries=5,
        )
        assert opts.default_timeout == 5000
        assert opts.max_retries == 5


class TestFailureRecovery:
    def test_default_initialization(self):
        fr = FailureRecovery()
        assert fr is not None
        assert fr._retry_counter is not None

    def test_custom_options(self):
        opts = FailureRecoveryOptions(
            default_timeout=5000,
            max_timeout=30000,
            max_retries=5,
        )
        fr = FailureRecovery(options=opts)
        assert fr._options["default_timeout"] == 5000
        assert fr._options["max_timeout"] == 30000
        assert fr._options["max_retries"] == 5

    def test_custom_retry_counter(self):
        rc = RetryCounter(max_retries=2, global_max_retries=3)
        fr = FailureRecovery(retry_counter=rc)
        assert fr.get_retry_counter() is rc

    @pytest.mark.asyncio
    async def test_handle_effect_not_found(self):
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
            properties=[ExpectedProperty(name="Glow Radius", value=20.0)],
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_effect")
        assert action.action == "retry_with_alternative"
        assert action.alternative is not None
        assert action.message is not None

    @pytest.mark.asyncio
    async def test_handle_effect_not_found_no_match_name(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(
            success=False,
            error_code="E300",
        )
        expected = ExpectedParameters(
            comp_name="Comp 1",
            layer_index=1,
            effect_match_name=None,
            properties=[],
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_no_match")
        assert action.action == "ask_user"

    @pytest.mark.asyncio
    async def test_handle_param_out_of_range_positive(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E303")
        expected = ExpectedParameters(
            comp_name="Comp 1",
            layer_index=1,
            properties=[
                ExpectedProperty(name="Glow Radius", value=100.0),
                ExpectedProperty(name="Label", value="hello"),
            ],
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_param_pos")
        assert action.action == "retry_with_adjusted_params"
        assert action.adjusted_params is not None
        radius = action.adjusted_params.properties[0]
        assert radius.value == pytest.approx(90.0)
        label = action.adjusted_params.properties[1]
        assert label.value == "hello"

    @pytest.mark.asyncio
    async def test_handle_param_out_of_range_negative(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E303")
        expected = ExpectedParameters(
            comp_name="Comp 1",
            layer_index=1,
            properties=[
                ExpectedProperty(name="Offset", value=-50.0),
            ],
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_param_neg")
        assert action.action == "retry_with_adjusted_params"
        offset = action.adjusted_params.properties[0]
        assert offset.value == pytest.approx(-55.0)

    @pytest.mark.asyncio
    async def test_handle_param_out_of_range_bool_not_adjusted(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E303")
        expected = ExpectedParameters(
            comp_name="Comp 1",
            layer_index=1,
            properties=[
                ExpectedProperty(name="Enabled", value=True),
                ExpectedProperty(name="Checked", value=False),
            ],
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_param_bool")
        assert action.adjusted_params.properties[0].value is True
        assert action.adjusted_params.properties[1].value is False

    @pytest.mark.asyncio
    async def test_handle_execution_timeout(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E600")
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_timeout")
        assert action.action == "retry_with_longer_timeout"
        assert action.timeout == 15000

    @pytest.mark.asyncio
    async def test_handle_bridge_timeout(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E007")
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_bridge_timeout")
        assert action.action == "retry_with_longer_timeout"

    @pytest.mark.asyncio
    async def test_handle_bridge_offline(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E006")
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_offline")
        assert action.action == "wait_and_retry"
        assert action.delay is not None
        assert action.delay > 0

    @pytest.mark.asyncio
    async def test_handle_mcp_not_responding(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E008")
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_mcp")
        assert action.action == "wait_and_retry"

    @pytest.mark.asyncio
    async def test_handle_layer_not_found(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E304")
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_layer")
        assert action.action == "ask_user"

    @pytest.mark.asyncio
    async def test_handle_comp_not_found(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E305")
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_comp")
        assert action.action == "ask_user"

    @pytest.mark.asyncio
    async def test_handle_property_not_found(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E306")
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_prop")
        assert action.action == "ask_user"

    @pytest.mark.asyncio
    async def test_handle_keyframe_failed(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E307")
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_kf")
        assert action.action == "report_error"

    @pytest.mark.asyncio
    async def test_handle_expression_error(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E308")
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_expr")
        assert action.action == "report_error"

    @pytest.mark.asyncio
    async def test_handle_out_of_memory(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E601")
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_oom")
        assert action.action == "report_error"

    @pytest.mark.asyncio
    async def test_handle_unknown_error(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code="E999")
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_unknown")
        assert action.action == "report_error"

    @pytest.mark.asyncio
    async def test_handle_none_error_code(self):
        fr = FailureRecovery()
        exec_result = ExecutionResult(success=False, error_code=None)
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        action = await fr.handle_failure(exec_result, expected, request_id="test_none")
        assert action.action == "report_error"

    @pytest.mark.asyncio
    async def test_max_retries_escalates_to_ask_user(self):
        fr = FailureRecovery(options=FailureRecoveryOptions(max_retries=2))
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        actions = []
        for i in range(5):
            a = await fr.handle_failure(
                ExecutionResult(success=False, error_code="E307"),
                expected,
                request_id="test_max_retries",
            )
            actions.append(a.action)

        assert actions[0] == "report_error"
        assert actions[1] == "report_error"
        assert actions[2] == "ask_user"
        assert actions[3] == "ask_user"
        assert actions[4] == "ask_user"

    @pytest.mark.asyncio
    async def test_reset_retry_count(self):
        fr = FailureRecovery(options=FailureRecoveryOptions(max_retries=1))
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )

        a1 = await fr.handle_failure(
            ExecutionResult(success=False, error_code="E307"),
            expected,
            request_id="test_reset",
        )
        assert a1.action == "report_error"

        a2 = await fr.handle_failure(
            ExecutionResult(success=False, error_code="E307"),
            expected,
            request_id="test_reset",
        )
        assert a2.action == "ask_user"

        fr.reset_retry_count("test_reset")

        a3 = await fr.handle_failure(
            ExecutionResult(success=False, error_code="E307"),
            expected,
            request_id="test_reset",
        )
        assert a3.action == "report_error"

    def test_build_adjusted_params(self):
        expected = ExpectedParameters(
            comp_name="Comp 1",
            layer_index=1,
            effect_match_name="ADBE Glo2",
            properties=[
                ExpectedProperty(name="Glow Radius", value=20.0, tolerance=0.1),
                ExpectedProperty(name="Glow Intensity", value=1.5),
                ExpectedProperty(name="Threshold", value=50.0),
            ],
        )
        mismatches = [
            ParameterMismatch(
                param="Glow Radius",
                expected=20.0,
                actual=18.5,
                deviation=0.075,
            ),
            ParameterMismatch(
                param="Threshold",
                expected=50.0,
                actual=45.0,
                deviation=0.1,
            ),
        ]
        result = FailureRecovery.build_adjusted_params(expected, mismatches)
        props = {p.name: p for p in result.properties}

        assert props["Glow Radius"].value == 18.5
        assert props["Glow Radius"].tolerance == 0.1
        assert props["Glow Intensity"].value == 1.5
        assert props["Threshold"].value == 45.0
        assert result.comp_name == "Comp 1"
        assert result.effect_match_name == "ADBE Glo2"

    def test_build_adjusted_params_empty_mismatches(self):
        expected = ExpectedParameters(
            comp_name="Comp 1",
            layer_index=1,
            properties=[ExpectedProperty(name="x", value=1.0)],
        )
        result = FailureRecovery.build_adjusted_params(expected, [])
        assert result.properties[0].value == 1.0

    def test_build_adjusted_params_none_actual(self):
        expected = ExpectedParameters(
            comp_name="Comp 1",
            layer_index=1,
            properties=[ExpectedProperty(name="x", value=1.0)],
        )
        mismatches = [
            ParameterMismatch(param="x", expected=1.0, actual=None, deviation=None),
        ]
        result = FailureRecovery.build_adjusted_params(expected, mismatches)
        assert result.properties[0].value == 1.0

    @pytest.mark.asyncio
    async def test_exponential_backoff_bridge_offline(self):
        fr = FailureRecovery(
            options=FailureRecoveryOptions(
                initial_retry_delay=1000,
                retry_backoff_factor=2.0,
                max_retries=5,
            )
        )
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )

        delays = []
        for i in range(4):
            a = await fr.handle_failure(
                ExecutionResult(success=False, error_code="E006"),
                expected,
                request_id="test_backoff",
            )
            delays.append(a.delay)

        assert delays[1] >= delays[0]
        assert delays[2] >= delays[1]
        assert delays[3] >= delays[2]

    @pytest.mark.asyncio
    async def test_timeout_max_cap(self):
        fr = FailureRecovery(
            options=FailureRecoveryOptions(
                default_timeout=50000,
                timeout_backoff_factor=2.0,
                max_timeout=60000,
            )
        )
        expected = ExpectedParameters(
            comp_name="Comp 1", layer_index=1, properties=[]
        )
        action = await fr.handle_failure(
            ExecutionResult(success=False, error_code="E600"),
            expected,
            request_id="test_timeout_cap",
        )
        assert action.timeout <= 60000
