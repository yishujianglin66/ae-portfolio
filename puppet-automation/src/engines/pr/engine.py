"""
PREngine 兼容 Shims - 已弃用
================================

``PREngine`` 已合并进 :class:`~engines.premiere.engine.PremiereEngine`，
本模块仅作为向后兼容 shim 保留，供旧脚本（``scripts/pr_auto_pipeline.py``、
``scripts/pr_editing_demo.py`` 等）在迁移完成前继续使用。

新代码请直接使用 :class:`~engines.premiere.engine.PremiereEngine`：:

    from engines.premiere.engine import PremiereEngine

    engine = PremiereEngine()
    await engine.ping()
"""
from __future__ import annotations

import warnings

from ..premiere.engine import PremiereEngine

warnings.warn(
    "src.engines.pr.engine.PREngine 已弃用：已合并进 "
    "src.engines.premiere.engine.PremiereEngine，请迁移到新引擎。",
    DeprecationWarning,
    stacklevel=2,
)


class PREngine(PremiereEngine):
    """``PremiereEngine`` 的向后兼容别名。

    行为与 :class:`PremiereEngine` 完全等价，仅保留旧标识
    ``name = "premiere_pro"`` 以兼容依赖该值的旧调用方。
    """

    name = "premiere_pro"


__all__ = ["PREngine"]