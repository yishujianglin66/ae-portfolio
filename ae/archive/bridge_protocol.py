# -*- coding: utf-8 -*-
"""ae.archive.bridge_protocol — 08-29 事故最小重建（详见 ae/archive/__init__.py）。

枚举/数据类/常量按全库引用面还原；BridgeClient 构造兼容，send_command
对真实文件桥执行明确抛错（协议已弃用）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

DEFAULT_TTL_MS = 30000
DEFAULT_POLL_INTERVAL = 0.5
DEFAULT_MAX_RETRIES = 3


class CommandStatus(Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ErrorCode(Enum):
    # 连接/桥接
    AE_NOT_RUNNING = "AE_NOT_RUNNING"
    AE_NOT_RESPONDING = "AE_NOT_RESPONDING"
    MCP_NOT_RESPONDING = "MCP_NOT_RESPONDING"
    NETWORK_ERROR = "NETWORK_ERROR"
    IO_ERROR = "IO_ERROR"
    LOCK_ACQUISITION_FAILED = "LOCK_ACQUISITION_FAILED"
    BRIDGE_DOWN = "BRIDGE_DOWN"
    BRIDGE_OFFLINE = "BRIDGE_OFFLINE"
    BRIDGE_TIMEOUT = "BRIDGE_TIMEOUT"
    BRIDGE_PROTOCOL_ERROR = "BRIDGE_PROTOCOL_ERROR"
    # 执行
    SCRIPT_TIMEOUT = "SCRIPT_TIMEOUT"
    SCRIPT_EXECUTION_ERROR = "SCRIPT_EXECUTION_ERROR"
    SCRIPT_SYNTAX = "SCRIPT_SYNTAX"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    TIMEOUT = "TIMEOUT"
    STAGE_FAILED = "STAGE_FAILED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    KEYFRAME_FAILED = "KEYFRAME_FAILED"
    # 资源
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    PROJECT_NOT_OPEN = "PROJECT_NOT_OPEN"
    COMP_NOT_FOUND = "COMP_NOT_FOUND"
    LAYER_NOT_FOUND = "LAYER_NOT_FOUND"
    EFFECT_NOT_FOUND = "EFFECT_NOT_FOUND"
    PROPERTY_NOT_FOUND = "PROPERTY_NOT_FOUND"
    MEDIA_NOT_FOUND = "MEDIA_NOT_FOUND"
    MEDIA_DECODE_ERROR = "MEDIA_DECODE_ERROR"
    DISK_FULL = "DISK_FULL"
    OUT_OF_MEMORY = "OUT_OF_MEMORY"
    OUTPUT_CORRUPT = "OUTPUT_CORRUPT"
    # 参数/校验
    INVALID_PARAMETER = "INVALID_PARAMETER"
    PARAMETER_INVALID = "PARAMETER_INVALID"
    PARAMETER_OUT_OF_RANGE = "PARAMETER_OUT_OF_RANGE"
    PARAM_OUT_OF_RANGE = "PARAM_OUT_OF_RANGE"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_MISSING = "CONFIG_MISSING"
    # 外部
    EXTERNAL_TOOL_ERROR = "EXTERNAL_TOOL_ERROR"
    FFMPEG_ERROR = "FFMPEG_ERROR"
    EXPRESSION_ERROR = "EXPRESSION_ERROR"
    LICENSE_MISSING = "LICENSE_MISSING"
    LICENCE_POPUP_BLOCKING = "LICENCE_POPUP_BLOCKING"
    QUALITY_CHECK_FAILED = "QUALITY_CHECK_FAILED"
    PIPELINE_BROKEN = "PIPELINE_BROKEN"
    # 杂项
    OPERATION_NOT_SUPPORTED = "OPERATION_NOT_SUPPORTED"
    USER_CANCELLED = "USER_CANCELLED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN = "UNKNOWN"


class Priority(Enum):
    BACKGROUND = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class BridgeMetadata:
    source: str = ""
    target: str = ""
    created_at: float = field(default_factory=time.time)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BridgeCommand:
    command_id: str = ""
    action: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    priority: Priority = Priority.NORMAL
    ttl_ms: int = DEFAULT_TTL_MS
    metadata: Optional[BridgeMetadata] = None
    signature: Optional[str] = None


@dataclass
class BridgeProgress:
    command_id: str = ""
    percent: float = 0.0
    message: str = ""


@dataclass
class BridgeResponse:
    command_id: str = ""
    status: CommandStatus = CommandStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    error_code: Optional[ErrorCode] = None
    signature: Optional[str] = None
    metadata: Optional[BridgeMetadata] = None


class BridgeClient:
    """最小重建客户端：构造兼容；真实文件桥执行明确报错。"""

    def __init__(self, bridge_dir: str = "", signature_enabled: bool = True,
                 secret: Optional[str] = None,
                 secret_file: Optional[str] = None,
                 poll_interval: float = DEFAULT_POLL_INTERVAL,
                 max_retries: int = DEFAULT_MAX_RETRIES,
                 **kwargs: Any) -> None:
        self.bridge_dir = bridge_dir
        self.signature_enabled = signature_enabled
        self._secret = secret
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self._extra = kwargs

    def send_command(self, command: Any = None, **kwargs: Any) -> BridgeResponse:
        raise RuntimeError(
            "ae.archive 桥接协议在 08-29 工作区事故中丢失（从未入库），"
            "当前为最小重建：文件桥执行不可用。该协议已弃用，"
            "请迁移到 ae.unified_ae_client（开源 after-effects-mcp 基线）。")

    def execute(self, *args: Any, **kwargs: Any) -> BridgeResponse:
        return self.send_command(*args, **kwargs)

    def heartbeat(self) -> bool:
        return False
