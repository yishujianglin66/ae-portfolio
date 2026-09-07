"""根级 feedback 反馈隔离测试。

验证根级 config.settings 暴露 feedback_dir，
且 pipeline/feedback_loop.py 的 FeedbackLoop / ErrorPatternMemory
默认写入 settings.feedback_dir(二线实战反馈隔离目录)，不再硬编码 data/pipeline_feedback。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import settings as root_settings
import pipeline.feedback_loop as feedback_loop_module
from pipeline.feedback_loop import ErrorPatternMemory, FeedbackLoop


class _FakeSettings:
    """独立于全局单例的 settings 替身，避免 monkeypatch 全局单例带来的执行顺序依赖。"""

    def __init__(self, feedback_dir):
        self.feedback_dir = str(feedback_dir)
        self.data_dir = str(Path(feedback_dir).parent)


class TestRootSettingsExposesFeedbackDir:
    """根级 settings 必须暴露独立的二线反馈目录。"""

    def test_settings_has_feedback_dir(self):
        assert hasattr(root_settings, "feedback_dir")
        assert str(root_settings.feedback_dir).endswith("engine_feedback")

    def test_feedback_dir_under_data_dir(self):
        assert Path(root_settings.feedback_dir).is_relative_to(root_settings.data_dir)


class TestFeedbackLoopUsesSettingsFeedbackDir:
    """FeedbackLoop 无参实例化时默认写入 settings.feedback_dir。"""

    def test_default_feedback_dir_matches_settings(self, tmp_path, monkeypatch):
        target = tmp_path / "data" / "engine_feedback"
        monkeypatch.setattr(feedback_loop_module, "settings", _FakeSettings(target))
        loop = FeedbackLoop()
        assert loop.feedback_dir == target

    def test_explicit_feedback_dir_still_respected(self, tmp_path):
        explicit = tmp_path / "custom_feedback"
        loop = FeedbackLoop(feedback_dir=str(explicit))
        assert loop.feedback_dir == explicit
        assert explicit.exists()  # 显式传入仍由其自身创建


class TestErrorPatternMemoryUsesSettingsFeedbackDir:
    """ErrorPatternMemory 无参实例化时默认写入 settings.feedback_dir 下。"""

    def test_default_memory_dir_under_settings_feedback_dir(self, tmp_path, monkeypatch):
        target = tmp_path / "data" / "engine_feedback"
        monkeypatch.setattr(feedback_loop_module, "settings", _FakeSettings(target))
        memory = ErrorPatternMemory()
        assert str(memory.memory_dir).startswith(str(target))

    def test_explicit_memory_dir_still_respected(self, tmp_path):
        explicit = tmp_path / "custom_memory"
        memory = ErrorPatternMemory(memory_dir=str(explicit))
        assert memory.memory_dir == explicit