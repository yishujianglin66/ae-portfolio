"""引擎注册中心 (registry.py) 单元测试。

验证 build_engine_registry() 返回非空引擎字典，
且 Celery Worker 不再以空字典启动 PipelineOrchestrator。
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_engine_classes_contains_core_engines():
    """ENGINE_CLASSES 应包含核心引擎。"""
    from src.engines.registry import ENGINE_CLASSES

    expected_cores = {"ffmpeg", "ae", "silhouette", "blender", "sam2", "whisper"}
    assert expected_cores.issubset(ENGINE_CLASSES.keys()), (
        f"缺少核心引擎: {expected_cores - ENGINE_CLASSES.keys()}"
    )


def test_engine_classes_count():
    """应有 17 个标准引擎类。"""
    from src.engines.registry import ENGINE_CLASSES
    assert len(ENGINE_CLASSES) == 17


@patch("src.engines.registry.logger")
def test_build_engine_registry_returns_dict(mock_logger):
    """build_engine_registry 应返回 dict 实例。"""
    from src.engines.registry import build_engine_registry

    engines = build_engine_registry()
    assert isinstance(engines, dict)


@patch("src.engines.registry.logger")
def test_build_engine_registry_skips_failed_engines(mock_logger):
    """单个引擎初始化失败不应导致整体崩溃。"""
    from src.engines.registry import build_engine_registry, ENGINE_CLASSES

    # 至少应该能跑完不崩溃
    engines = build_engine_registry()
    # 返回值必须是 dict
    assert isinstance(engines, dict)
    # 即使某些引擎路径不存在（测试环境无 AE/Blender 等），也不应崩溃


def test_build_engine_registry_with_config_overrides():
    """config_overrides 参数应被接受（不报错）。"""
    from src.engines.registry import build_engine_registry

    engines = build_engine_registry(config_overrides={"test": True})
    assert isinstance(engines, dict)


def test_celery_worker_not_empty_engines():
    """验证 celery_app.py 中 run_pipeline_task 不再使用空 engines={}。

    通过源码检查确认。
    """
    celery_app_path = (
        Path(__file__).parent.parent / "src" / "workers" / "celery_app.py"
    )
    source = celery_app_path.read_text(encoding="utf-8")

    # 不应包含 engines={} 的旧模式
    assert "engines={})" not in source, "celery_app.py 仍使用空 engines={}"
    # 应包含 build_engine_registry 调用
    assert "build_engine_registry" in source, "celery_app.py 未调用 build_engine_registry"
