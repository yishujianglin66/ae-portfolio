"""Test configuration and fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


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
