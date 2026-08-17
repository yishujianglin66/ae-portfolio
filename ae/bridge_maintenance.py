"""兼容转发模块：``ae.bridge_maintenance`` → ``ae.archive.bridge_maintenance``。

自研 Bridge 协议已迁移到开源 after-effects-mcp 方案，原模块归档于
``ae.archive``。此模块通过惰性 ``__getattr__`` 转发所有符号，为历史测试与
尚未迁移的调用方提供向后兼容（包括 ``patch`` 顶层属性都能正确生效），
新代码请使用 ``ae.unified_ae_client`` 统一接口。
"""
from __future__ import annotations

import importlib as _importlib
from typing import Any

_TARGET = "ae.archive.bridge_maintenance"


def __getattr__(name: str) -> Any:
    module = _importlib.import_module(_TARGET)
    try:
        return getattr(module, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None


def __dir__() -> list[str]:
    module = _importlib.import_module(_TARGET)
    return sorted(set(globals()) | set(dir(module)))