"""Test configuration and fixtures."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# 测试环境统一认证 bypass：/api/v1/* 中间件在请求时读此变量（仅限本地测试，
# main.py 对其有显式告警）；消除存量“测试不带 Bearer token”导致的 401 失败。
os.environ.setdefault("PUPPET_DISABLE_AUTH", "1")
# Resolve 装在非默认目录时，官方 MCP/DaVinciResolveScript 需要显式指路（2026-09-24 实测）。
_davinci_dll = Path(r"D:\app\fusionscript.dll")
if _davinci_dll.exists():
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", str(_davinci_dll))


@pytest.fixture
def sample_video_path(tmp_path) -> Path:
    """Create a dummy video file for testing."""
    video = tmp_path / "test_input.mp4"
    video.write_bytes(b"fake video data")
    return video


@pytest.fixture
def sample_job_id() -> str:
    """Sample job ID."""
    return "test_job_001"
