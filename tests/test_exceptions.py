"""exceptions 模块单元测试

覆盖范围:
- 错误码枚举与消息映射
- 异常基类属性与序列化
- 各层级异常类的继承关系
- 异常详细信息（details、cause）
- wrap_exception 包装函数
- safe_execute 安全执行函数
- get_error_message 工具函数
- 字符串与表示形式
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exceptions import (
    ERROR_MESSAGES,
    AEKnowledgeVaultError,
    BlenderError,
    BridgeCommandError,
    BridgeError,
    BridgeOfflineError,
    BridgeTimeoutError,
    CompNotFoundError,
    ConfigMissingError,
    ConfigurationError,
    EffectNotFoundError,
    ErrorCode,
    ExecutionError,
    ExpressionError,
    ExternalToolError,
    FFmpegError,
    KeyframeError,
    LayerNotFoundError,
    MediaDecodeError,
    MediaError,
    MediaNotFoundError,
    NetworkError,
    OutOfMemoryError,
    ParameterInvalidError,
    ParameterOutOfRangeError,
    PhotoshopError,
    PipelineBrokenError,
    PremiereError,
    PropertyNotFoundError,
    QualityCheckFailedError,
    ResolveError,
    ResourceError,
    SilhouetteError,
    StageFailedError,
    TimeoutError_,
    ValidationError,
    WorkflowError,
    get_error_message,
    safe_execute,
    wrap_exception,
)


class TestErrorCode:
    """错误码枚举测试"""

    def test_error_codes_are_unique(self):
        codes = [e.value for e in ErrorCode]
        assert len(codes) == len(set(codes)), "错误码不能重复"

    def test_error_code_prefixes(self):
        for code in ErrorCode:
            val = code.value
            assert val.startswith("E"), f"{code} 应该以 E 开头"
            assert len(val) == 4, f"{code} 应该是4位字符"
            int(val[1:])

    def test_unknown_error_exists(self):
        assert hasattr(ErrorCode, "UNKNOWN")
        assert ErrorCode.UNKNOWN.value == "E000"


class TestErrorMessages:
    """错误消息映射测试"""

    def test_all_codes_have_messages(self):
        for code in ErrorCode:
            assert code in ERROR_MESSAGES, f"错误码 {code} 缺少消息映射"
            assert isinstance(ERROR_MESSAGES[code], str)
            assert len(ERROR_MESSAGES[code]) > 0

    def test_get_error_message_known(self):
        msg = get_error_message(ErrorCode.CONFIG_INVALID)
        assert msg == ERROR_MESSAGES[ErrorCode.CONFIG_INVALID]

    def test_get_error_message_unknown(self):
        msg = get_error_message(ErrorCode.UNKNOWN)
        assert msg == "未知错误"


class TestBaseException:
    """异常基类测试"""

    def test_default_constructor(self):
        exc = AEKnowledgeVaultError()
        assert exc.error_code == ErrorCode.UNKNOWN
        assert exc.message == "未知错误"
        assert exc.details == {}
        assert exc.cause is None

    def test_custom_message(self):
        exc = AEKnowledgeVaultError(message="自定义错误")
        assert str(exc) != ""
        assert "自定义错误" in str(exc)

    def test_custom_error_code(self):
        exc = AEKnowledgeVaultError(error_code=ErrorCode.CONFIG_INVALID)
        assert exc.error_code == ErrorCode.CONFIG_INVALID

    def test_details_dict(self):
        exc = AEKnowledgeVaultError(details={"key": "value", "num": 42})
        assert exc.details["key"] == "value"
        assert exc.details["num"] == 42

    def test_cause_chaining(self):
        orig = ValueError("原始错误")
        exc = AEKnowledgeVaultError(message="包装错误", cause=orig)
        assert exc.cause is orig
        assert "ValueError" in str(exc)

    def test_str_with_details(self):
        exc = AEKnowledgeVaultError(
            message="测试",
            error_code=ErrorCode.VALIDATION_FAILED,
            details={"field": "name"},
        )
        s = str(exc)
        assert "[E110]" in s
        assert "测试" in s
        assert "field=name" in s

    def test_repr_format(self):
        exc = AEKnowledgeVaultError(
            message="test",
            error_code=ErrorCode.UNKNOWN,
            details={"a": 1},
        )
        r = repr(exc)
        assert "AEKnowledgeVaultError" in r
        assert "error_code=" in r
        assert "message=" in r
        assert "details=" in r

    def test_to_dict(self):
        orig = TypeError("type err")
        exc = AEKnowledgeVaultError(
            message="测试序列化",
            error_code=ErrorCode.INTERNAL_ERROR,
            details={"ctx": "test"},
            cause=orig,
        )
        d = exc.to_dict()
        assert d["error_type"] == "AEKnowledgeVaultError"
        assert d["error_code"] == "E001"
        assert d["message"] == "测试序列化"
        assert d["details"] == {"ctx": "test"}
        assert d["cause"] is not None
        assert "type err" in d["cause"]

    def test_inherits_from_exception(self):
        exc = AEKnowledgeVaultError()
        assert isinstance(exc, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(AEKnowledgeVaultError) as exc_info:
            raise AEKnowledgeVaultError("test")
        assert str(exc_info.value) != ""


class TestConfigurationExceptions:
    """配置相关异常测试"""

    def test_configuration_error_default_code(self):
        exc = ConfigurationError()
        assert exc.error_code == ErrorCode.CONFIG_INVALID

    def test_configuration_error_with_config_key(self):
        exc = ConfigurationError(config_key="db.host")
        assert exc.details["config_key"] == "db.host"

    def test_config_missing_error(self):
        exc = ConfigMissingError(config_key="api.key")
        assert exc.error_code == ErrorCode.CONFIG_MISSING
        assert "api.key" in exc.message
        assert exc.details["config_key"] == "api.key"

    def test_config_missing_is_subclass(self):
        assert issubclass(ConfigMissingError, ConfigurationError)
        assert issubclass(ConfigurationError, AEKnowledgeVaultError)


class TestValidationExceptions:
    """验证相关异常测试"""

    def test_validation_error_default_code(self):
        exc = ValidationError()
        assert exc.error_code == ErrorCode.VALIDATION_FAILED

    def test_validation_error_with_field(self):
        exc = ValidationError(field="email")
        assert exc.details["field"] == "email"

    def test_parameter_invalid_error(self):
        exc = ParameterInvalidError(param_name="count", param_value=-1)
        assert exc.error_code == ErrorCode.PARAMETER_INVALID
        assert "count" in exc.message
        assert exc.details["field"] == "count"
        assert exc.details["value"] == -1

    def test_parameter_invalid_no_value(self):
        exc = ParameterInvalidError(param_name="name")
        assert "name" in exc.message


    def test_parameter_out_of_range_full(self):
        exc = ParameterOutOfRangeError(
            param_name="speed", value=150, min_value=0, max_value=100
        )
        assert exc.error_code == ErrorCode.PARAMETER_OUT_OF_RANGE
        assert "speed" in exc.message
        assert exc.details["value"] == 150
        assert exc.details["min"] == 0
        assert exc.details["max"] == 100
        assert "0 ~ 100" in exc.message


    def test_parameter_out_of_range_min_only(self):
        exc = ParameterOutOfRangeError(param_name="age", value=-1, min_value=0)
        assert exc.error_code == ErrorCode.PARAMETER_OUT_OF_RANGE
        assert "最小值" in exc.message


    def test_parameter_out_of_range_max_only(self):
        exc = ParameterOutOfRangeError(param_name="age", value=200, max_value=150)
        assert "最大值" in exc.message

    def test_validation_hierarchy(self):
        assert issubclass(ParameterInvalidError, ValidationError)
        assert issubclass(ParameterOutOfRangeError, ValidationError)
        assert issubclass(ValidationError, AEKnowledgeVaultError)


class TestBridgeExceptions:
    """桥接相关异常测试"""

    def test_bridge_error_default(self):
        exc = BridgeError()
        assert exc.error_code == ErrorCode.BRIDGE_OFFLINE
        assert exc.details["bridge_type"] == "ae-mcp"

    def test_bridge_error_custom_type(self):
        exc = BridgeError(bridge_type="silhouette")
        assert exc.details["bridge_type"] == "silhouette"

    def test_bridge_offline_error(self):
        exc = BridgeOfflineError()
        assert exc.error_code == ErrorCode.BRIDGE_OFFLINE
        assert "离线" in exc.message

    def test_bridge_timeout_error(self):
        exc = BridgeTimeoutError(timeout_ms=5000)
        assert exc.error_code == ErrorCode.BRIDGE_TIMEOUT
        assert exc.details["timeout_ms"] == 5000
        assert "5000ms" in exc.message

    def test_bridge_timeout_no_ms(self):
        exc = BridgeTimeoutError()
        assert "超时" in exc.message

    def test_bridge_command_error(self):
        exc = BridgeCommandError(command="createComp", ae_error="AE is busy")
        assert exc.error_code == ErrorCode.BRIDGE_PROTOCOL_ERROR
        assert exc.details["command"] == "createComp"
        assert exc.details["ae_error"] == "AE is busy"
        assert "createComp" in exc.message

    def test_bridge_hierarchy(self):
        assert issubclass(BridgeOfflineError, BridgeError)
        assert issubclass(BridgeTimeoutError, BridgeError)
        assert issubclass(BridgeCommandError, BridgeError)
        assert issubclass(BridgeError, AEKnowledgeVaultError)


class TestExecutionExceptions:
    """AE执行相关异常测试"""

    def test_execution_error_default(self):
        exc = ExecutionError()
        assert exc.error_code == ErrorCode.INTERNAL_ERROR

    def test_execution_error_with_context(self):
        exc = ExecutionError(comp_name="Main", layer_index=3)
        assert exc.details["comp_name"] == "Main"
        assert exc.details["layer_index"] == 3

    def test_effect_not_found(self):
        exc = EffectNotFoundError(effect_name="Gaussian Blur")
        assert exc.error_code == ErrorCode.EFFECT_NOT_FOUND
        assert "Gaussian Blur" in exc.message
        assert exc.details["effect_name"] == "Gaussian Blur"

    def test_layer_not_found(self):
        exc = LayerNotFoundError(layer_identifier="Video 1")
        assert exc.error_code == ErrorCode.LAYER_NOT_FOUND
        assert exc.details["layer"] == "Video 1"

    def test_comp_not_found(self):
        exc = CompNotFoundError(comp_name="Intro")
        assert exc.error_code == ErrorCode.COMP_NOT_FOUND
        assert exc.details["comp_name"] == "Intro"

    def test_property_not_found(self):
        exc = PropertyNotFoundError(property_name="Opacity", effect_name="Glow")
        assert exc.error_code == ErrorCode.PROPERTY_NOT_FOUND
        assert "Opacity" in exc.message
        assert exc.details["property_name"] == "Opacity"
        assert exc.details["effect_name"] == "Glow"

    def test_property_not_found_no_effect(self):
        exc = PropertyNotFoundError(property_name="Position")
        assert "Position" in exc.message

    def test_keyframe_error(self):
        exc = KeyframeError(property_name="Position", frame=10, ae_error="bad value")
        assert exc.error_code == ErrorCode.KEYFRAME_FAILED
        assert exc.details["property_name"] == "Position"
        assert exc.details["frame"] == 10
        assert exc.details["ae_error"] == "bad value"

    def test_expression_error(self):
        exc = ExpressionError(expression="time*100", ae_error="syntax error")
        assert exc.error_code == ErrorCode.EXPRESSION_ERROR
        assert exc.details["expression"] == "time*100"
        assert exc.details["ae_error"] == "syntax error"

    def test_execution_hierarchy(self):
        assert issubclass(EffectNotFoundError, ExecutionError)
        assert issubclass(LayerNotFoundError, ExecutionError)
        assert issubclass(CompNotFoundError, ExecutionError)
        assert issubclass(PropertyNotFoundError, ExecutionError)
        assert issubclass(KeyframeError, ExecutionError)
        assert issubclass(ExpressionError, ExecutionError)
        assert issubclass(ExecutionError, AEKnowledgeVaultError)


class TestMediaExceptions:
    """媒体处理异常测试"""

    def test_media_error_default(self):
        exc = MediaError()
        assert exc.error_code == ErrorCode.MEDIA_DECODE_ERROR

    def test_media_error_with_path(self):
        exc = MediaError(file_path="/data/video.mp4")
        assert exc.details["file_path"] == "/data/video.mp4"

    def test_media_not_found(self):
        exc = MediaNotFoundError(file_path="/missing.mp4")
        assert exc.error_code == ErrorCode.MEDIA_NOT_FOUND
        assert "/missing.mp4" in exc.message

    def test_media_decode_error(self):
        exc = MediaDecodeError(file_path="/bad.mp4", reason="corrupted")
        assert exc.error_code == ErrorCode.MEDIA_DECODE_ERROR
        assert exc.details["reason"] == "corrupted"

    def test_quality_check_failed(self):
        metrics = {"psnr": 25.0, "ssim": 0.85}
        thresholds = {"psnr": 30.0, "ssim": 0.9}
        exc = QualityCheckFailedError(
            file_path="/out.mp4", metrics=metrics, thresholds=thresholds
        )
        assert exc.error_code == ErrorCode.QUALITY_CHECK_FAILED
        assert exc.details["metrics"] == metrics
        assert exc.details["thresholds"] == thresholds

    def test_media_hierarchy(self):
        assert issubclass(MediaNotFoundError, MediaError)
        assert issubclass(MediaDecodeError, MediaError)
        assert issubclass(QualityCheckFailedError, MediaError)
        assert issubclass(MediaError, AEKnowledgeVaultError)


class TestWorkflowExceptions:
    """工作流异常测试"""

    def test_workflow_error_default(self):
        exc = WorkflowError()
        assert exc.error_code == ErrorCode.WORKFLOW_FAILED

    def test_workflow_error_with_context(self):
        exc = WorkflowError(workflow_name="video_gen", stage="render")
        assert exc.details["workflow_name"] == "video_gen"
        assert exc.details["stage"] == "render"

    def test_stage_failed_error(self):
        exc = StageFailedError(stage_name="perception", stage_error="timeout")
        assert exc.error_code == ErrorCode.STAGE_FAILED
        assert exc.details["stage"] == "perception"
        assert exc.details["stage_error"] == "timeout"

    def test_pipeline_broken_error(self):
        exc = PipelineBrokenError(broken_at="phase2", reason="dependency missing")
        assert exc.error_code == ErrorCode.PIPELINE_BROKEN
        assert exc.details["broken_at"] == "phase2"
        assert exc.details["reason"] == "dependency missing"

    def test_workflow_hierarchy(self):
        assert issubclass(StageFailedError, WorkflowError)
        assert issubclass(PipelineBrokenError, WorkflowError)
        assert issubclass(WorkflowError, AEKnowledgeVaultError)


class TestResourceExceptions:
    """资源相关异常测试"""

    def test_resource_error_default(self):
        exc = ResourceError()
        assert exc.error_code == ErrorCode.OUT_OF_MEMORY

    def test_out_of_memory_error(self):
        exc = OutOfMemoryError(context="rendering 4K video")
        assert exc.error_code == ErrorCode.OUT_OF_MEMORY
        assert "内存不足" in exc.message
        assert exc.details["context"] == "rendering 4K video"

    def test_timeout_error(self):
        exc = TimeoutError_(operation="download", timeout_seconds=30.0)
        assert exc.error_code == ErrorCode.EXECUTION_TIMEOUT
        assert exc.details["operation"] == "download"
        assert exc.details["timeout_seconds"] == 30.0
        assert "download" in exc.message

    def test_resource_hierarchy(self):
        assert issubclass(OutOfMemoryError, ResourceError)
        assert issubclass(TimeoutError_, ResourceError)
        assert issubclass(ResourceError, AEKnowledgeVaultError)


class TestNetworkExceptions:
    """网络异常测试"""

    def test_network_error_default(self):
        exc = NetworkError()
        assert exc.error_code == ErrorCode.NETWORK_ERROR

    def test_network_error_with_url(self):
        exc = NetworkError(url="https://example.com/api")
        assert exc.details["url"] == "https://example.com/api"

    def test_network_hierarchy(self):
        assert issubclass(NetworkError, AEKnowledgeVaultError)


class TestExternalToolExceptions:
    """外部工具异常测试"""

    def test_external_tool_error_base(self):
        exc = ExternalToolError(
            tool_name="custom_tool",
            message="failed",
            exit_code=1,
            stderr="error output",
        )
        assert exc.error_code == ErrorCode.EXTERNAL_TOOL_ERROR
        assert exc.details["tool_name"] == "custom_tool"
        assert exc.details["exit_code"] == 1
        assert exc.details["stderr"] == "error output"

    def test_external_tool_stderr_truncation(self):
        long_stderr = "x" * 1000
        exc = ExternalToolError(tool_name="t", stderr=long_stderr)
        assert len(exc.details["stderr"]) == 500


    def test_ffmpeg_error(self):
        exc = FFmpegError(message="encode failed", exit_code=255)
        assert exc.details["tool_name"] == "FFmpeg"
        assert exc.error_code == ErrorCode.FFMPEG_ERROR


    def test_blender_error(self):
        exc = BlenderError()
        assert exc.details["tool_name"] == "Blender"

    def test_resolve_error(self):
        exc = ResolveError()
        assert exc.details["tool_name"] == "DaVinci Resolve"

    def test_silhouette_error(self):
        exc = SilhouetteError()
        assert exc.details["tool_name"] == "Silhouette"

    def test_photoshop_error(self):
        exc = PhotoshopError()
        assert exc.details["tool_name"] == "Photoshop"

    def test_premiere_error(self):
        exc = PremiereError()
        assert exc.details["tool_name"] == "Premiere Pro"

    def test_external_tool_hierarchy(self):
        assert issubclass(FFmpegError, ExternalToolError)
        assert issubclass(BlenderError, ExternalToolError)
        assert issubclass(ResolveError, ExternalToolError)
        assert issubclass(SilhouetteError, ExternalToolError)
        assert issubclass(PhotoshopError, ExternalToolError)
        assert issubclass(PremiereError, ExternalToolError)
        assert issubclass(ExternalToolError, AEKnowledgeVaultError)


class TestWrapException:
    """wrap_exception 工具函数测试"""

    def test_wrap_standard_exception(self):
        orig = ValueError("bad value")
        wrapped = wrap_exception(orig, ConfigurationError)
        assert isinstance(wrapped, ConfigurationError)
        assert wrapped.cause is orig
        assert wrapped.details["original_type"] == "ValueError"
        assert "bad value" in wrapped.message

    def test_wrap_already_project_exception(self):
        orig = ConfigurationError(config_key="test")
        wrapped = wrap_exception(orig, BridgeError)
        assert isinstance(wrapped, ConfigurationError)
        assert wrapped is orig

    def test_wrap_with_extra_details(self):
        orig = RuntimeError("oops")
        wrapped = wrap_exception(
            orig, ValidationError, field="email", context="signup"
        )
        assert wrapped.details["field"] == "email"
        assert wrapped.details["context"] == "signup"
        assert wrapped.details["original_type"] == "RuntimeError"

    def test_wrap_project_exception_with_extra_details(self):
        orig = ConfigurationError(config_key="host")
        wrapped = wrap_exception(orig, ConfigurationError, extra="info")
        assert wrapped.details["extra"] == "info"
        assert wrapped.details["config_key"] == "host"


class TestSafeExecute:
    """safe_execute 工具函数测试"""

    def test_successful_execution(self):
        def add(a, b):
            return a + b
        result = safe_execute(add, 2, 3)
        assert result == 5

    def test_exception_returns_default(self):
        def fail():
            raise ValueError("error")
        result = safe_execute(fail, default_return="fallback")
        assert result == "fallback"

    def test_exception_with_handler(self):
        def fail():
            raise RuntimeError("boom")

        def handler(exc):
            return f"handled: {exc}"

        result = safe_execute(fail, error_handler=handler)
        assert result == "handled: boom"

    def test_handler_takes_precedence_over_default(self):
        def fail():
            raise ValueError()

        def handler(exc):
            return "from_handler"

        result = safe_execute(fail, default_return="default", error_handler=handler)
        assert result == "from_handler"

    def test_keyword_args_passed(self):
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"
        result = safe_execute(greet, "World", greeting="Hi")
        assert result == "Hi, World!"

    def test_no_exception_no_handler(self):
        def ok():
            return 42
        result = safe_execute(ok, error_handler=lambda e: 0)
        assert result == 42
