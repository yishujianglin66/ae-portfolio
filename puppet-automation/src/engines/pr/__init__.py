"""Premiere Pro 兼容 shim 包（已弃用）。

``engines.pr`` 已合并进 ``engines.premiere``，本包仅作为向后兼容保留
``PREngine`` 别名。新代码请使用 ``engines.premiere.engine.PremiereEngine``。
"""
from __future__ import annotations

from .engine import PREngine

__all__ = ["PREngine"]