"""Deprecated 兼容垫片 — 真实实现已迁至 core/render_cleanup.py。

scripts/ 定位为一次性脚本目录, 不应被核心代码反向依赖(2026-08-16 审计 P1
库化治理)。新代码请: from core.render_cleanup import auto_cleanup_quiet
"""
import warnings

warnings.warn(
    "scripts.render_cleanup 已迁移至 core.render_cleanup,"
    " 请更新 import 路径", DeprecationWarning, stacklevel=2)

from core.render_cleanup import *  # noqa: F401,F403
from core.render_cleanup import auto_cleanup_quiet  # noqa: F401
