"""tests/test_pipeline_watcher.py — 无人值守调度器单元测试"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline.pipeline_watcher import PipelineWatcher


class _FakeResult:
    def __init__(self, status="success", output_path="", quality=80.0):
        self.status = status
        self.output_path = output_path
        self.quality_score = quality
        self.iterations = 1
        self.errors = []


class _FakePipeline:
    """替换 UnifiedPipeline: 记录 config, 返回受控结果"""
    last_config = None
    next_result = None
    raise_exc = None

    def __init__(self, config):
        _FakePipeline.last_config = config

    def run_all(self):
        if _FakePipeline.raise_exc:
            raise _FakePipeline.raise_exc
        return _FakePipeline.next_result or _FakeResult()


@pytest.fixture
def watcher(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "pipeline.unified_pipeline.UnifiedPipeline", _FakePipeline
    )
    _FakePipeline.last_config = None
    _FakePipeline.next_result = None
    _FakePipeline.raise_exc = None
    return PipelineWatcher(queue_root=tmp_path / "queue")


@pytest.fixture
def material(tmp_path):
    """一个 >100KB 的假视频文件 (避免硬否决)"""
    f = tmp_path / "fake.mp4"
    f.write_bytes(b"\x00" * (150 * 1024))
    return f


def test_submit_creates_pending_spec(watcher):
    path = watcher.submit({"input_topic": "测试主题"}, task_id="t1")
    assert path.exists()
    assert path.parent == watcher.pending
    spec = json.loads(path.read_text(encoding="utf-8"))
    assert spec["input_topic"] == "测试主题"


def test_build_config_ignores_unknown_fields(watcher):
    cfg = watcher._build_config({
        "input_topic": "主题",
        "not_a_real_field": 123,
        "max_quality_iterations": 2,
    })
    assert cfg.input_topic == "主题"
    assert cfg.max_quality_iterations == 2
    assert not hasattr(cfg, "not_a_real_field")


def test_build_config_clamps_invalid_values(watcher):
    cfg = watcher._build_config({
        "max_quality_iterations": 99,
        "visual_judge_backend": "bogus",
    })
    assert cfg.max_quality_iterations == 5
    assert cfg.visual_judge_backend == "auto"


def test_run_one_success_moves_to_done(watcher, material):
    _FakePipeline.next_result = _FakeResult(
        status="success", output_path=str(material)
    )
    spec_path = watcher.submit({"input_topic": "成功任务"}, task_id="ok1")
    entry = watcher._run_one(spec_path)

    assert entry["status"] == "success"
    assert not spec_path.exists()
    assert not (watcher.running / "ok1.json").exists()
    assert (watcher.done / "ok1.json").exists()
    assert (watcher.done / "result_ok1.json").exists()
    result = json.loads((watcher.done / "result_ok1.json").read_text(encoding="utf-8"))
    assert result["output_path"] == str(material)


def test_run_one_pipeline_failed_moves_to_failed(watcher, tmp_path):
    # 管线返回 failed → failed 队列 + 错误记忆
    _FakePipeline.next_result = _FakeResult(status="failed", output_path="")
    spec_path = watcher.submit({"input_topic": "失败任务"}, task_id="bad1")
    entry = watcher._run_one(spec_path)

    assert entry["status"] == "failed"
    assert (watcher.failed / "bad1.json").exists()
    assert (watcher.failed / "result_bad1.json").exists()
    assert not (watcher.done / "bad1.json").exists()


def test_run_one_output_missing_moves_to_failed(watcher):
    # status=success 但输出文件不存在 → 同样归入 failed
    _FakePipeline.next_result = _FakeResult(
        status="success", output_path="/nonexistent/nope.mp4"
    )
    spec_path = watcher.submit({"input_topic": "空输出"}, task_id="ghost1")
    watcher._run_one(spec_path)
    assert (watcher.failed / "ghost1.json").exists()


def test_run_one_crash_moves_to_failed(watcher):
    _FakePipeline.raise_exc = RuntimeError("boom")
    spec_path = watcher.submit({"input_topic": "崩溃任务"}, task_id="crash1")
    entry = watcher._run_one(spec_path)

    assert entry["status"] == "crashed"
    assert "boom" in entry["error"]
    assert (watcher.failed / "crash1.json").exists()
    assert len(watcher.ledger) == 1


def test_load_spec_tolerates_utf8_bom(watcher, material):
    # Windows 工具 (PowerShell/记事本) 写出的规格带 UTF-8 BOM, 不能崩
    _FakePipeline.next_result = _FakeResult(
        status="success", output_path=str(material)
    )
    spec_path = watcher.pending / "bom1.json"
    spec_path.write_bytes(
        b"\xef\xbb\xbf" + '{"input_topic": "带BOM任务"}'.encode("utf-8")
    )
    entry = watcher._run_one(spec_path)
    assert entry["status"] == "success"
    assert _FakePipeline.last_config.input_topic == "带BOM任务"
    assert (watcher.done / "bom1.json").exists()


def test_drain_pending_processes_all(watcher, material):
    _FakePipeline.next_result = _FakeResult(
        status="success", output_path=str(material)
    )
    for i in range(3):
        watcher.submit({"input_topic": f"批量任务{i}"}, task_id=f"batch{i}")
    results = watcher.drain_pending()

    assert len(results) == 3
    assert all(r["status"] == "success" for r in results)
    assert len(list(watcher.pending.glob("*.json"))) == 0
    # done 目录: 3 个规格文件 + 3 个 result 报告
    assert len(list(watcher.done.glob("batch*.json"))) == 3
    assert len(list(watcher.done.glob("result_batch*.json"))) == 3


def test_drain_empty_queue(watcher):
    assert watcher.drain_pending() == []


def test_main_once_mode(tmp_path, monkeypatch, material):
    from pipeline import pipeline_watcher as pw

    monkeypatch.setattr(
        "pipeline.unified_pipeline.UnifiedPipeline", _FakePipeline
    )
    _FakePipeline.next_result = _FakeResult(
        status="success", output_path=str(material)
    )
    queue = tmp_path / "q"
    w = PipelineWatcher(queue_root=queue)
    w.submit({"input_topic": "CLI任务"}, task_id="cli1")

    rc = pw.main(["--once", "--queue", str(queue)])
    assert rc == 0
    assert (w.done / "cli1.json").exists()
