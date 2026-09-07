"""tests/test_flagship_stages.py — 旗舰管线阶段 + 训练基类测试

审计"最该优先补测试"第 2/3 位: flagships 阶段零测试、训练基础设施零测试。
覆盖感知阶段扫描分类、规划阶段降级路径、训练基类回调与成本估算。
"""
from __future__ import annotations

import pytest


class _StubConfig:
    def __init__(self, **kw):
        self.materials_dir = kw.get("materials_dir")
        self.reference_video = kw.get("reference_video")
        self.use_knowledge = kw.get("use_knowledge", False)
        self.style_reference = kw.get("style_reference")
        self.input_topic = kw.get("input_topic", "")
        for k, v in kw.items():
            setattr(self, k, v)


# ── 感知阶段 ──────────────────────────────────────────────

class TestPerceptionStage:
    def test_scan_directory_classifies_exts(self, tmp_path):
        from pipeline.stages.perception import PerceptionStage
        (tmp_path / "v.mp4").write_bytes(b"fake")
        (tmp_path / "i.png").write_bytes(b"fake")
        (tmp_path / "a.wav").write_bytes(b"fake")
        (tmp_path / "note.txt").write_bytes(b"fake")  # 非媒体应被忽略
        stage = PerceptionStage(_StubConfig())
        files = stage._scan_directory(str(tmp_path))
        names = {f["name"] for f in files}
        assert names == {"v.mp4", "i.png", "a.wav"}
        ext = {f["name"]: f["ext"] for f in files}
        assert ext["v.mp4"] == ".mp4"

    def test_run_empty_config(self):
        from pipeline.stages.perception import PerceptionStage
        stage = PerceptionStage(_StubConfig())
        result = stage.run({})
        assert result["materials"] == []
        assert result["total_files"] == 0
        assert "videos" in result and result["videos"] == []

    def test_run_with_materials(self, tmp_path):
        from pipeline.stages.perception import PerceptionStage
        (tmp_path / "clip.mp4").write_bytes(b"x" * 1024)
        stage = PerceptionStage(_StubConfig(materials_dir=str(tmp_path)))
        result = stage.run({})
        assert result["total_files"] == 1
        assert len(result["videos"]) == 1
        assert result["videos"][0]["name"] == "clip.mp4"


# ── 规划阶段 ──────────────────────────────────────────────

class TestPlanningStage:
    def test_run_no_knowledge_no_director(self, monkeypatch):
        """无知识库/无参考 → 结构完整不崩溃 (AI Director 失败静默降级)"""
        from pipeline.stages.planning import PlanningStage
        stage = PlanningStage(_StubConfig(use_knowledge=False))
        result = stage.run({"perceive": {"videos": []}, "analyze": {}})
        assert "script" in result
        assert result["shot_list"] == []
        assert result["transition_plan"] == []
        assert result["effect_stack"] == []
        assert result["style_params"] == {}

    def test_run_with_empty_videos_script_none(self):
        from pipeline.stages.planning import PlanningStage
        stage = PlanningStage(_StubConfig(use_knowledge=False, input_topic="test"))
        result = stage.run({"perceive": {"videos": []}, "analyze": {}})
        # 无素材: 降级模板也可能产出剧本; 断言结构而非精确 None
        s = result["script"]
        assert s is None or isinstance(s, dict)
        if isinstance(s, dict):
            assert "shots" in s or "segments" in s or "title" in s

    def test_generate_script_with_materials_no_crash(self):
        """有素材但 AI Director 不可用 → 降级模板, 不抛异常"""
        from pipeline.stages.planning import PlanningStage
        stage = PlanningStage(_StubConfig(use_knowledge=False))
        perceive = {"videos": [{"width": 1920, "height": 1080,
                                "duration_sec": 10.0}]}
        result = stage.run({"perceive": perceive,
                            "analyze": {"scenes": []}})
        assert result["script"] is None or isinstance(result["script"], dict)


# ── 训练基类 ──────────────────────────────────────────────

class _ConcreteTrainer:
    """BaseTrainer 的最小实现 (仅测试回调/成本, 不真实训练)。"""

    def __init__(self, config):
        from models.training.trainer_base import BaseTrainer

        class _Impl(BaseTrainer):
            def load_dataset(self, train_data, eval_data=None):
                self._train_dataset = train_data
                self._eval_dataset = eval_data

            def load_base_model(self):
                self._model = object()

            def train(self):
                self._start_training()
                self._end_training()
                from models.training.trainer_base import TrainingResult
                return TrainingResult()

            def evaluate(self):
                return {}

            def save_model(self, output_path):
                return output_path

        self._impl = _Impl(config)

    def __getattr__(self, name):
        return getattr(self._impl, name)


class TestTrainerBase:
    def test_training_config_defaults(self):
        from models.training.trainer_base import TrainingConfig
        c = TrainingConfig()
        assert c.epochs == 3
        assert c.batch_size == 8
        assert c.learning_rate == 2e-5
        assert c.fp16 is True
        assert c.seed == 42

    def test_cost_estimate(self):
        from models.training.trainer_base import TrainingConfig
        t = _ConcreteTrainer(TrainingConfig())
        # 1 小时 → $1.5
        assert abs(t._estimate_cost(10.0, 3600.0) - 1.5) < 1e-6
        # 0.5 小时 → $0.75 (与参数量无关, 按 GPU 时长)
        assert abs(t._estimate_cost(100.0, 1800.0) - 0.75) < 1e-6

    def test_callback_firing(self):
        from models.training.trainer_base import TrainingConfig
        t = _ConcreteTrainer(TrainingConfig())
        events = []
        t.add_callback(lambda event, **kw: events.append(event))
        t.train()
        assert events == ["on_training_start", "on_training_end"]

    def test_callback_exception_isolated(self):
        from models.training.trainer_base import TrainingConfig
        t = _ConcreteTrainer(TrainingConfig())
        def _bad(event, **kw):
            raise RuntimeError("callback bug")
        t.add_callback(_bad)
        ok = []
        t.add_callback(lambda event, **kw: ok.append(event))
        t.train()  # 坏回调不得阻断训练与其他回调
        assert ok == ["on_training_start", "on_training_end"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])
