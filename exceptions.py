#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一异常体系
==========

为项目提供统一的异常基类、错误码映射和异常工具函数。

异常层级:
  AEKnowledgeVaultError (基类)
  ├── ConfigurationError    (配置相关错误)
  ├── ValidationError       (数据验证错误)
  ├── BridgeError           (AE/MCP桥接错误)
  │   ├── BridgeOfflineError
  │   ├── BridgeTimeoutError
  │   └── BridgeCommandError
  ├── ExecutionError        (执行层错误)
  │   ├── EffectNotFoundError
  │   ├── LayerNotFoundError
  │   ├── CompNotFoundError
  │   ├── PropertyNotFoundError
  │   ├── KeyframeError
  │   ├── ExpressionError
  │   └── ParameterOutOfRangeError
  ├── MediaError            (媒体处理错误)
  │   ├── MediaNotFoundError
  │   ├── MediaDecodeError
  │   ├── MediaEncodeError
  │   └── QualityCheckFailedError
  ├── WorkflowError         (工作流错误)
  │   ├── StageFailedError
  │   └── PipelineBrokenError
  ├── ResourceError         (资源相关错误)
  │   ├── OutOfMemoryError
  │   ├── DiskSpaceError
  │   └── TimeoutError
  ├── NetworkError          (网络相关错误)
  └── ExternalToolError     (外部工具错误)

错误码规范:
  E0xx - 系统/基础设施错误
  E1xx - 配置/验证错误
  E2xx - 桥接/通信错误
  E3xx - AE执行错误
  E4xx - 媒体处理错误
  E5xx - 工作流错误
  E6xx - 资源错误
  E7xx - 网络错误
  E8xx - 外部工具错误
  E9xx - 未知/其他错误
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional, Type

# ============================================================================
# 错误码枚举
# ============================================================================

class ErrorCode(str, Enum):
    """统一错误码定义"""
    # E0xx - 系统/基础设施
    UNKNOWN = "E000"
    INTERNAL_ERROR = "E001"
    ASSERTION_FAILED = "E002"

    # E1xx - 配置/验证
    CONFIG_INVALID = "E100"
    CONFIG_MISSING = "E101"
    CONFIG_TYPE_ERROR = "E102"
    VALIDATION_FAILED = "E110"
    PARAMETER_INVALID = "E111"
    PARAMETER_MISSING = "E112"
    PARAMETER_OUT_OF_RANGE = "E113"

    # E2xx - 桥接/通信
    BRIDGE_OFFLINE = "E200"
    BRIDGE_TIMEOUT = "E201"
    BRIDGE_CONNECTION_FAILED = "E202"
    BRIDGE_PROTOCOL_ERROR = "E203"
    MCP_NOT_RESPONDING = "E210"
    MCP_SIGNATURE_INVALID = "E211"

    # E3xx - AE执行错误
    EFFECT_NOT_FOUND = "E300"
    LAYER_NOT_FOUND = "E301"
    COMP_NOT_FOUND = "E302"
    PROPERTY_NOT_FOUND = "E303"
    KEYFRAME_FAILED = "E304"
    EXPRESSION_ERROR = "E305"
    RENDER_FAILED = "E306"
    IMPORT_FAILED = "E307"
    EXPORT_FAILED = "E308"

    # E4xx - 媒体处理错误
    MEDIA_NOT_FOUND = "E400"
    MEDIA_DECODE_ERROR = "E401"
    MEDIA_ENCODE_ERROR = "E402"
    MEDIA_FORMAT_UNSUPPORTED = "E403"
    MEDIA_CORRUPTED = "E404"
    QUALITY_CHECK_FAILED = "E410"

    # E5xx - 工作流错误
    WORKFLOW_FAILED = "E500"
    STAGE_FAILED = "E501"
    PIPELINE_BROKEN = "E502"
    DEPENDENCY_MISSING = "E503"

    # E6xx - 资源错误
    OUT_OF_MEMORY = "E600"
    DISK_SPACE_LOW = "E601"
    DISK_SPACE_FULL = "E602"
    EXECUTION_TIMEOUT = "E610"
    RATE_LIMITED = "E620"

    # E7xx - 网络错误
    NETWORK_ERROR = "E700"
    NETWORK_TIMEOUT = "E701"
    CONNECTION_REFUSED = "E702"
    AUTH_FAILED = "E710"
    PERMISSION_DENIED = "E711"

    # E8xx - 外部工具错误
    EXTERNAL_TOOL_ERROR = "E800"
    FFMPEG_ERROR = "E801"
    BLENDER_ERROR = "E802"
    RESOLVE_ERROR = "E803"
    SILHOUETTE_ERROR = "E804"
    PHOTOSHOP_ERROR = "E805"
    PREMIERE_ERROR = "E806"

    # E9xx - 未知/其他
    NOT_IMPLEMENTED = "E900"
    OPERATION_CANCELLED = "E901"


# ============================================================================
# 错误码描述映射
# ============================================================================

ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.UNKNOWN: "未知错误",
    ErrorCode.INTERNAL_ERROR: "内部系统错误",
    ErrorCode.ASSERTION_FAILED: "断言失败",

    ErrorCode.CONFIG_INVALID: "配置无效",
    ErrorCode.CONFIG_MISSING: "配置缺失",
    ErrorCode.CONFIG_TYPE_ERROR: "配置类型错误",
    ErrorCode.VALIDATION_FAILED: "数据验证失败",
    ErrorCode.PARAMETER_INVALID: "参数无效",
    ErrorCode.PARAMETER_MISSING: "参数缺失",
    ErrorCode.PARAMETER_OUT_OF_RANGE: "参数超出范围",

    ErrorCode.BRIDGE_OFFLINE: "桥接服务离线",
    ErrorCode.BRIDGE_TIMEOUT: "桥接超时",
    ErrorCode.BRIDGE_CONNECTION_FAILED: "桥接连接失败",
    ErrorCode.BRIDGE_PROTOCOL_ERROR: "桥接协议错误",
    ErrorCode.MCP_NOT_RESPONDING: "MCP服务无响应",
    ErrorCode.MCP_SIGNATURE_INVALID: "MCP签名验证失败",

    ErrorCode.EFFECT_NOT_FOUND: "效果未找到",
    ErrorCode.LAYER_NOT_FOUND: "图层未找到",
    ErrorCode.COMP_NOT_FOUND: "合成未找到",
    ErrorCode.PROPERTY_NOT_FOUND: "属性未找到",
    ErrorCode.KEYFRAME_FAILED: "关键帧设置失败",
    ErrorCode.EXPRESSION_ERROR: "表达式错误",
    ErrorCode.RENDER_FAILED: "渲染失败",
    ErrorCode.IMPORT_FAILED: "导入失败",
    ErrorCode.EXPORT_FAILED: "导出失败",

    ErrorCode.MEDIA_NOT_FOUND: "媒体文件不存在",
    ErrorCode.MEDIA_DECODE_ERROR: "媒体解码失败",
    ErrorCode.MEDIA_ENCODE_ERROR: "媒体编码失败",
    ErrorCode.MEDIA_FORMAT_UNSUPPORTED: "不支持的媒体格式",
    ErrorCode.MEDIA_CORRUPTED: "媒体文件损坏",
    ErrorCode.QUALITY_CHECK_FAILED: "质量检查未通过",

    ErrorCode.WORKFLOW_FAILED: "工作流执行失败",
    ErrorCode.STAGE_FAILED: "阶段执行失败",
    ErrorCode.PIPELINE_BROKEN: "流水线中断",
    ErrorCode.DEPENDENCY_MISSING: "依赖项缺失",

    ErrorCode.OUT_OF_MEMORY: "内存不足",
    ErrorCode.DISK_SPACE_LOW: "磁盘空间不足",
    ErrorCode.DISK_SPACE_FULL: "磁盘已满",
    ErrorCode.EXECUTION_TIMEOUT: "执行超时",
    ErrorCode.RATE_LIMITED: "请求频率超限",

    ErrorCode.NETWORK_ERROR: "网络错误",
    ErrorCode.NETWORK_TIMEOUT: "网络超时",
    ErrorCode.CONNECTION_REFUSED: "连接被拒绝",
    ErrorCode.AUTH_FAILED: "认证失败",
    ErrorCode.PERMISSION_DENIED: "权限不足",

    ErrorCode.EXTERNAL_TOOL_ERROR: "外部工具错误",
    ErrorCode.FFMPEG_ERROR: "FFmpeg执行错误",
    ErrorCode.BLENDER_ERROR: "Blender执行错误",
    ErrorCode.RESOLVE_ERROR: "DaVinci Resolve执行错误",
    ErrorCode.SILHOUETTE_ERROR: "Silhouette执行错误",
    ErrorCode.PHOTOSHOP_ERROR: "Photoshop执行错误",
    ErrorCode.PREMIERE_ERROR: "Premiere Pro执行错误",

    ErrorCode.NOT_IMPLEMENTED: "功能未实现",
    ErrorCode.OPERATION_CANCELLED: "操作已取消",
}


# ============================================================================
# 基类异常
# ============================================================================

class AEKnowledgeVaultError(Exception):
    """项目所有自定义异常的基类

    属性:
        error_code: 错误码 (ErrorCode)
        message: 错误消息
        details: 详细信息字典
        cause: 原始异常 (如果有)
    """

    def __init__(
        self,
        message: str | None = None,
        error_code: ErrorCode = ErrorCode.UNKNOWN,
        details: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ):
        if message is None:
            message = ERROR_MESSAGES.get(error_code, "未知错误")
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.cause = cause

    def __str__(self) -> str:
        parts = [f"[{self.error_code.value}] {self.message}"]
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            parts.append(f" ({detail_str})")
        if self.cause:
            parts.append(f" [caused by: {type(self.cause).__name__}: {self.cause}]")
        return "".join(parts)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"error_code={self.error_code.value!r}, "
            f"message={self.message!r}, "
            f"details={self.details!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "error_type": type(self).__name__,
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
        }


# ============================================================================
# 配置/验证异常
# ============================================================================

class ConfigurationError(AEKnowledgeVaultError):
    """配置相关错误"""

    def __init__(
        self,
        message: str | None = None,
        error_code: ErrorCode = ErrorCode.CONFIG_INVALID,
        config_key: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            **kwargs,
        )
        if config_key:
            self.details["config_key"] = config_key


class ConfigMissingError(ConfigurationError):
    """配置缺失错误"""

    def __init__(self, config_key: str, **kwargs):
        super().__init__(
            message=f"配置项缺失: {config_key}",
            config_key=config_key,
            error_code=ErrorCode.CONFIG_MISSING,
            **kwargs,
        )


class ValidationError(AEKnowledgeVaultError):
    """数据验证错误"""

    def __init__(
        self,
        message: str | None = None,
        error_code: ErrorCode = ErrorCode.VALIDATION_FAILED,
        field: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            **kwargs,
        )
        if field:
            self.details["field"] = field


class ParameterInvalidError(ValidationError):
    """参数无效错误"""

    def __init__(self, param_name: str, param_value: Any = None, **kwargs):
        msg = f"参数无效: {param_name}"
        if param_value is not None:
            msg += f" = {param_value!r}"
        super().__init__(
            message=msg,
            field=param_name,
            error_code=ErrorCode.PARAMETER_INVALID,
            **kwargs,
        )
        if param_value is not None:
            self.details["value"] = param_value


class ParameterOutOfRangeError(ValidationError):
    """参数超出范围错误"""

    def __init__(
        self,
        param_name: str,
        value: float,
        min_value: float | None = None,
        max_value: float | None = None,
        **kwargs,
    ):
        parts = [f"参数 {param_name} = {value} 超出范围"]
        if min_value is not None and max_value is not None:
            parts.append(f" (允许范围: {min_value} ~ {max_value})")
        elif min_value is not None:
            parts.append(f" (最小值: {min_value})")
        elif max_value is not None:
            parts.append(f" (最大值: {max_value})")
        super().__init__(
            message="".join(parts),
            field=param_name,
            error_code=ErrorCode.PARAMETER_OUT_OF_RANGE,
            **kwargs,
        )
        self.details.update({
            "value": value,
            "min": min_value,
            "max": max_value,
        })


# ============================================================================
# 桥接/通信异常
# ============================================================================

class BridgeError(AEKnowledgeVaultError):
    """AE/MCP桥接错误"""

    def __init__(
        self,
        message: str | None = None,
        error_code: ErrorCode = ErrorCode.BRIDGE_OFFLINE,
        bridge_type: str = "ae-mcp",
        details: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            **kwargs,
        )
        self.details["bridge_type"] = bridge_type


class BridgeOfflineError(BridgeError):
    """桥接服务离线"""

    def __init__(self, **kwargs):
        super().__init__(
            error_code=ErrorCode.BRIDGE_OFFLINE,
            message="桥接服务离线，请确认AE已启动并运行MCP监听器",
            **kwargs,
        )


class BridgeTimeoutError(BridgeError):
    """桥接超时"""

    def __init__(self, timeout_ms: int | None = None, **kwargs):
        msg = "桥接请求超时"
        if timeout_ms:
            msg += f" (超时: {timeout_ms}ms)"
        super().__init__(
            message=msg,
            error_code=ErrorCode.BRIDGE_TIMEOUT,
            **kwargs,
        )
        if timeout_ms:
            self.details["timeout_ms"] = timeout_ms


class BridgeCommandError(BridgeError):
    """桥接命令执行错误"""

    def __init__(
        self,
        command: str,
        ae_error: str | None = None,
        **kwargs,
    ):
        msg = f"命令执行失败: {command}"
        if ae_error:
            msg += f" (AE错误: {ae_error})"
        super().__init__(
            message=msg,
            error_code=ErrorCode.BRIDGE_PROTOCOL_ERROR,
            **kwargs,
        )
        self.details["command"] = command
        if ae_error:
            self.details["ae_error"] = ae_error


# ============================================================================
# AE执行异常
# ============================================================================

class ExecutionError(AEKnowledgeVaultError):
    """AE执行层错误"""

    def __init__(
        self,
        message: str | None = None,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        comp_name: str | None = None,
        layer_index: int | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            **kwargs,
        )
        if comp_name:
            self.details["comp_name"] = comp_name
        if layer_index is not None:
            self.details["layer_index"] = layer_index


class EffectNotFoundError(ExecutionError):
    """效果未找到"""

    def __init__(self, effect_name: str, **kwargs):
        super().__init__(
            message=f"效果未找到: {effect_name}",
            error_code=ErrorCode.EFFECT_NOT_FOUND,
            **kwargs,
        )
        self.details["effect_name"] = effect_name


class LayerNotFoundError(ExecutionError):
    """图层未找到"""

    def __init__(self, layer_identifier: str, **kwargs):
        super().__init__(
            message=f"图层未找到: {layer_identifier}",
            error_code=ErrorCode.LAYER_NOT_FOUND,
            **kwargs,
        )
        self.details["layer"] = layer_identifier


class CompNotFoundError(ExecutionError):
    """合成未找到"""

    def __init__(self, comp_name: str, **kwargs):
        super().__init__(
            message=f"合成未找到: {comp_name}",
            error_code=ErrorCode.COMP_NOT_FOUND,
            **kwargs,
        )
        self.details["comp_name"] = comp_name


class PropertyNotFoundError(ExecutionError):
    """属性未找到"""

    def __init__(self, property_name: str, effect_name: str | None = None, **kwargs):
        msg = f"属性未找到: {property_name}"
        if effect_name:
            msg += f" (效果: {effect_name})"
        super().__init__(
            message=msg,
            error_code=ErrorCode.PROPERTY_NOT_FOUND,
            **kwargs,
        )
        self.details["property_name"] = property_name
        if effect_name:
            self.details["effect_name"] = effect_name


class KeyframeError(ExecutionError):
    """关键帧错误"""

    def __init__(
        self,
        property_name: str | None = None,
        frame: int | None = None,
        ae_error: str | None = None,
        **kwargs,
    ):
        parts = ["关键帧操作失败"]
        if property_name:
            parts.append(f" 属性: {property_name}")
        if frame is not None:
            parts.append(f" 帧: {frame}")
        if ae_error:
            parts.append(f" (AE错误: {ae_error})")
        super().__init__(
            message="".join(parts),
            error_code=ErrorCode.KEYFRAME_FAILED,
            **kwargs,
        )
        if property_name:
            self.details["property_name"] = property_name
        if frame is not None:
            self.details["frame"] = frame
        if ae_error:
            self.details["ae_error"] = ae_error


class ExpressionError(ExecutionError):
    """表达式错误"""

    def __init__(self, expression: str | None = None, ae_error: str | None = None, **kwargs):
        msg = "表达式执行错误"
        if ae_error:
            msg += f": {ae_error}"
        super().__init__(
            message=msg,
            error_code=ErrorCode.EXPRESSION_ERROR,
            **kwargs,
        )
        if expression:
            self.details["expression"] = expression
        if ae_error:
            self.details["ae_error"] = ae_error


# ============================================================================
# 媒体处理异常
# ============================================================================

class MediaError(AEKnowledgeVaultError):
    """媒体处理错误"""

    def __init__(
        self,
        message: str | None = None,
        error_code: ErrorCode = ErrorCode.MEDIA_DECODE_ERROR,
        file_path: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            **kwargs,
        )
        if file_path:
            self.details["file_path"] = file_path


class MediaNotFoundError(MediaError):
    """媒体文件不存在"""

    def __init__(self, file_path: str, **kwargs):
        super().__init__(
            message=f"媒体文件不存在: {file_path}",
            error_code=ErrorCode.MEDIA_NOT_FOUND,
            file_path=file_path,
            **kwargs,
        )


class MediaDecodeError(MediaError):
    """媒体解码失败"""

    def __init__(self, file_path: str, reason: str | None = None, **kwargs):
        msg = f"媒体解码失败: {file_path}"
        if reason:
            msg += f" ({reason})"
        super().__init__(
            message=msg,
            error_code=ErrorCode.MEDIA_DECODE_ERROR,
            file_path=file_path,
            **kwargs,
        )
        if reason:
            self.details["reason"] = reason


class QualityCheckFailedError(MediaError):
    """质量检查未通过"""

    def __init__(
        self,
        file_path: str,
        metrics: dict[str, Any] | None = None,
        thresholds: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(
            message=f"视频质量检查未通过: {file_path}",
            error_code=ErrorCode.QUALITY_CHECK_FAILED,
            file_path=file_path,
            **kwargs,
        )
        if metrics:
            self.details["metrics"] = metrics
        if thresholds:
            self.details["thresholds"] = thresholds


# ============================================================================
# 工作流异常
# ============================================================================

class WorkflowError(AEKnowledgeVaultError):
    """工作流错误"""

    def __init__(
        self,
        message: str | None = None,
        error_code: ErrorCode = ErrorCode.WORKFLOW_FAILED,
        workflow_name: str | None = None,
        stage: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            **kwargs,
        )
        if workflow_name:
            self.details["workflow_name"] = workflow_name
        if stage:
            self.details["stage"] = stage


class StageFailedError(WorkflowError):
    """阶段执行失败"""

    def __init__(
        self,
        stage_name: str,
        stage_error: str | None = None,
        **kwargs,
    ):
        msg = f"阶段执行失败: {stage_name}"
        if stage_error:
            msg += f" ({stage_error})"
        super().__init__(
            message=msg,
            error_code=ErrorCode.STAGE_FAILED,
            stage=stage_name,
            **kwargs,
        )
        if stage_error:
            self.details["stage_error"] = stage_error


class PipelineBrokenError(WorkflowError):
    """流水线中断"""

    def __init__(
        self,
        broken_at: str,
        reason: str | None = None,
        **kwargs,
    ):
        msg = f"流水线在 {broken_at} 处中断"
        if reason:
            msg += f"，原因: {reason}"
        super().__init__(
            message=msg,
            error_code=ErrorCode.PIPELINE_BROKEN,
            **kwargs,
        )
        self.details["broken_at"] = broken_at
        if reason:
            self.details["reason"] = reason


# ============================================================================
# 资源异常
# ============================================================================

class ResourceError(AEKnowledgeVaultError):
    """资源相关错误"""

    def __init__(
        self,
        message: str | None = None,
        error_code: ErrorCode = ErrorCode.OUT_OF_MEMORY,
        details: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            **kwargs,
        )


class OutOfMemoryError(ResourceError):
    """内存不足"""

    def __init__(self, context: str | None = None, **kwargs):
        msg = "内存不足，请关闭其他程序后重试"
        if context:
            msg += f" (上下文: {context})"
        super().__init__(
            message=msg,
            error_code=ErrorCode.OUT_OF_MEMORY,
            **kwargs,
        )
        if context:
            self.details["context"] = context


class TimeoutError_(ResourceError):
    """执行超时（避免与内置 TimeoutError 冲突，加下划线）"""

    def __init__(
        self,
        operation: str,
        timeout_seconds: float | None = None,
        **kwargs,
    ):
        msg = f"操作超时: {operation}"
        if timeout_seconds:
            msg += f" (超时: {timeout_seconds}s)"
        super().__init__(
            message=msg,
            error_code=ErrorCode.EXECUTION_TIMEOUT,
            **kwargs,
        )
        self.details["operation"] = operation
        if timeout_seconds:
            self.details["timeout_seconds"] = timeout_seconds


# ============================================================================
# 网络异常
# ============================================================================

class NetworkError(AEKnowledgeVaultError):
    """网络错误"""

    def __init__(
        self,
        message: str | None = None,
        error_code: ErrorCode = ErrorCode.NETWORK_ERROR,
        url: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            **kwargs,
        )
        if url:
            self.details["url"] = url


# ============================================================================
# 外部工具异常
# ============================================================================

class ExternalToolError(AEKnowledgeVaultError):
    """外部工具执行错误"""

    def __init__(
        self,
        tool_name: str,
        message: str | None = None,
        error_code: ErrorCode = ErrorCode.EXTERNAL_TOOL_ERROR,
        exit_code: int | None = None,
        stderr: str | None = None,
        details: dict[str, Any] | None = None,
        **kwargs,
    ):
        msg = f"{tool_name} 执行错误"
        if message:
            msg += f": {message}"
        if exit_code is not None:
            msg += f" (退出码: {exit_code})"
        super().__init__(
            message=msg,
            error_code=error_code,
            details=details,
            **kwargs,
        )
        self.details["tool_name"] = tool_name
        if exit_code is not None:
            self.details["exit_code"] = exit_code
        if stderr:
            self.details["stderr"] = stderr[:500] if len(stderr) > 500 else stderr


class FFmpegError(ExternalToolError):
    """FFmpeg执行错误"""

    def __init__(self, **kwargs):
        super().__init__(
            tool_name="FFmpeg",
            error_code=ErrorCode.FFMPEG_ERROR,
            **kwargs,
        )


class BlenderError(ExternalToolError):
    """Blender执行错误"""

    def __init__(self, **kwargs):
        super().__init__(
            tool_name="Blender",
            error_code=ErrorCode.BLENDER_ERROR,
            **kwargs,
        )


class ResolveError(ExternalToolError):
    """DaVinci Resolve执行错误"""

    def __init__(self, **kwargs):
        super().__init__(
            tool_name="DaVinci Resolve",
            error_code=ErrorCode.RESOLVE_ERROR,
            **kwargs,
        )


class SilhouetteError(ExternalToolError):
    """Silhouette执行错误"""

    def __init__(self, **kwargs):
        super().__init__(
            tool_name="Silhouette",
            error_code=ErrorCode.SILHOUETTE_ERROR,
            **kwargs,
        )


class PhotoshopError(ExternalToolError):
    """Photoshop执行错误"""

    def __init__(self, **kwargs):
        super().__init__(
            tool_name="Photoshop",
            error_code=ErrorCode.PHOTOSHOP_ERROR,
            **kwargs,
        )


class PremiereError(ExternalToolError):
    """Premiere Pro执行错误"""

    def __init__(self, **kwargs):
        super().__init__(
            tool_name="Premiere Pro",
            error_code=ErrorCode.PREMIERE_ERROR,
            **kwargs,
        )


# ============================================================================
# 异常工具函数
# ============================================================================

def wrap_exception(
    exc: BaseException,
    target_type: type[AEKnowledgeVaultError],
    **extra_details,
) -> AEKnowledgeVaultError:
    """将任意异常包装为项目自定义异常

    Args:
        exc: 原始异常
        target_type: 目标异常类型
        **extra_details: 额外的详细信息

    Returns:
        包装后的自定义异常
    """
    if isinstance(exc, AEKnowledgeVaultError):
        if extra_details:
            exc.details.update(extra_details)
        return exc

    details = extra_details.copy()
    details["original_type"] = type(exc).__name__

    return target_type(
        message=str(exc),
        details=details,
        cause=exc,
    )


def safe_execute(
    func,
    *args,
    default_return=None,
    error_handler=None,
    **kwargs,
):
    """安全执行函数，捕获所有异常并可选处理

    Args:
        func: 要执行的函数
        *args: 位置参数
        default_return: 异常时返回的默认值
        error_handler: 异常处理函数，签名: handler(exc) -> Any
        **kwargs: 关键字参数

    Returns:
        函数返回值，或异常时的默认值
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if error_handler:
            return error_handler(e)
        return default_return


def get_error_message(error_code: ErrorCode) -> str:
    """获取错误码对应的默认消息"""
    return ERROR_MESSAGES.get(error_code, "未知错误")


# ============================================================================
# 导出列表
# ============================================================================

__all__ = [
    # 错误码
    "ErrorCode",
    "ERROR_MESSAGES",
    # 基类
    "AEKnowledgeVaultError",
    # 配置/验证
    "ConfigurationError",
    "ConfigMissingError",
    "ValidationError",
    "ParameterInvalidError",
    "ParameterOutOfRangeError",
    # 桥接
    "BridgeError",
    "BridgeOfflineError",
    "BridgeTimeoutError",
    "BridgeCommandError",
    # 执行
    "ExecutionError",
    "EffectNotFoundError",
    "LayerNotFoundError",
    "CompNotFoundError",
    "PropertyNotFoundError",
    "KeyframeError",
    "ExpressionError",
    # 媒体
    "MediaError",
    "MediaNotFoundError",
    "MediaDecodeError",
    "QualityCheckFailedError",
    # 工作流
    "WorkflowError",
    "StageFailedError",
    "PipelineBrokenError",
    # 资源
    "ResourceError",
    "OutOfMemoryError",
    "TimeoutError_",
    # 网络
    "NetworkError",
    # 外部工具
    "ExternalToolError",
    "FFmpegError",
    "BlenderError",
    "ResolveError",
    "SilhouetteError",
    "PhotoshopError",
    "PremiereError",
    # 工具函数
    "wrap_exception",
    "safe_execute",
    "get_error_message",
]
