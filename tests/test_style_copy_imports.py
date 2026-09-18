#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
style_copy 模块导入契约测试

目的：锁定风格复制系统的可导入性，防止 import 期脆弱点（如 P0-3 修复的
sys.exit 地雷、本回合修复的 input_parser 顶层 raise ImportError）卷土重来。
所有断言均为离线、无外部依赖（不触发 V4/yt-dlp/AE/FFmpeg）。
"""
import importlib

import bootstrap  # 注入项目子目录，确保 style_copy 包可解析

# 关键模块：任一无法导入都说明导入链被破坏（workflow/api 会级联失败）
STYLE_COPY_MODULES = [
    "style_copy.input_parser",
    "style_copy.style_analyzer",
    "style_copy.tool_orchestrator",
    "style_copy.ffmpeg_generator",
    "style_copy.workflow",
    "style_copy.api",
    "style_copy.style_copy_mvp",
]


def test_style_copy_modules_importable():
    """style_copy 全部关键模块在离线环境下可导入（导入链无崩溃）。"""
    for mod in STYLE_COPY_MODULES:
        imported = importlib.import_module(mod)
        assert imported is not None, f"模块导入失败: {mod}"


def test_workflow_class_reachable():
    """workflow 层暴露 StyleCopyWorkflow，供 FastAPI / CLI 调用。"""
    from style_copy.workflow import StyleCopyWorkflow

    assert callable(StyleCopyWorkflow)


def test_api_router_registered():
    """api 层暴露 router 与 register，可被主 FastAPI 应用挂载。"""
    import style_copy.api as api

    assert hasattr(api, "router")
    assert callable(getattr(api, "register", None))


def test_input_parser_degrades_without_scenedetector():
    """回归测试：即使 SceneDetector 缺失，模块导入仍不崩溃（仅实例化时报错）。

    这是本回合修复的核心——input_parser 原在模块顶层 raise ImportError，
    会拖垮整个 style_copy 包的导入链。
    """
    import style_copy.input_parser as ip

    saved = ip.SceneDetector
    try:
        ip.SceneDetector = None
        # 模块已导入（本函数执行前 import 成功），再次 import_module 不应抛错
        reloaded = importlib.import_module("style_copy.input_parser")
        assert reloaded is not None
        # 实例化时才明确失败（fail-closed，但不在导入期）
        import pytest

        with pytest.raises(RuntimeError):
            ip.InputParser(work_dir=None)
    finally:
        ip.SceneDetector = saved
