"""二线实战反馈隔离目录测试。

验证二线(引擎实战任务)的反馈产物写入独立目录 data/engine_feedback，
与一线 learning 状态(data/digital_twin / self_evolution / versions 等)物理隔离，
并确保该目录被引擎路径安全白名单允许写入。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.config import settings as global_settings
from src.engines.base import validate_path_safety


class TestFeedbackDirConfigured:
    """settings 必须暴露独立的二线反馈目录。"""

    def test_settings_has_feedback_dir(self):
        assert hasattr(global_settings, "feedback_dir")
        assert str(global_settings.feedback_dir).endswith("engine_feedback")

    def test_feedback_dir_is_under_data_dir(self):
        assert global_settings.feedback_dir.is_relative_to(global_settings.data_dir)

    def test_feedback_dir_distinct_from_learning_state_dirs(self):
        """反馈目录不得与一线学习状态目录重叠。"""
        learning_dirs = [
            "digital_twin",
            "self_evolution",
            "versions",
            "meta_strategy",
            "bayesian-optimizer",
            "online_learner",
            "causal_engine",
        ]
        for name in learning_dirs:
            candidate = global_settings.data_dir / name
            assert global_settings.feedback_dir != candidate, (
                f"feedback_dir 不得与学习状态目录重叠: {name}"
            )

    def test_ensure_dirs_creates_feedback_dir(self, monkeypatch):
        from src.config.settings import Settings

        tmp = Path(str(global_settings.data_dir))
        monkeypatch.setattr(global_settings, "data_dir", tmp)
        monkeypatch.setattr(global_settings, "feedback_dir", tmp / "engine_feedback")
        global_settings.ensure_dirs()
        assert (tmp / "engine_feedback").exists()


class TestFeedbackDirInAllowedRoots:
    """反馈目录必须被路径安全白名单允许，二线才能写入产物。"""

    def test_feedback_dir_is_allowed_root(self, tmp_path, monkeypatch):
        from src.engines import base

        project_root = tmp_path
        for name in ("output", "data", "temp", "resources"):
            (project_root / name).mkdir(parents=True, exist_ok=True)

        feedback_dir = tmp_path / "data" / "engine_feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(global_settings, "project_root", str(project_root))
        monkeypatch.setattr(global_settings, "output_dir", str(project_root / "output"))
        monkeypatch.setattr(global_settings, "feedback_dir", str(feedback_dir))

        # 反馈产物可安全写入
        feedback_file = feedback_dir / "feedback_run_001.json"
        feedback_file.write_bytes(b"{}")
        resolved = validate_path_safety(feedback_file, must_exist=True)
        assert resolved == feedback_file.resolve()

    def test_feedback_outside_root_still_rejected(self, tmp_path, monkeypatch):
        from src.engines import base

        project_root = tmp_path
        for name in ("output", "data", "temp", "resources"):
            (project_root / name).mkdir(parents=True, exist_ok=True)

        feedback_dir = tmp_path / "data" / "engine_feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(global_settings, "project_root", str(project_root))
        monkeypatch.setattr(global_settings, "output_dir", str(project_root / "output"))
        monkeypatch.setattr(global_settings, "feedback_dir", str(feedback_dir))

        outside = tmp_path.parent / f"outside_{tmp_path.name}" / "malware.sh"
        outside.parent.mkdir(exist_ok=True)
        outside.write_bytes(b"x")

        with pytest.raises(ValueError, match="路径不在允许的目录范围内"):
            validate_path_safety(outside, must_exist=True)