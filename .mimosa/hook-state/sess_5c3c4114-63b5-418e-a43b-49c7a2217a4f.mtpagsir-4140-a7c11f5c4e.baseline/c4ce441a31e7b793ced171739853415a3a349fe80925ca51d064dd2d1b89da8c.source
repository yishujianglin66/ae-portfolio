"""Tests for knowledge distillation (D4 root cause fix)

验证 review 结果被蒸馏为知识行追加到 evolution_knowledge.jsonl。
"""
import json
from core.auto_evolution import distill_review_knowledge


def test_distill_writes_knowledge_line(tmp_path):
    """蒸馏写入知识行"""
    sink = tmp_path / "evolution_knowledge.jsonl"
    reviews = [
        {"run_id": "r1", "quality": 72.0, "deviation": 0.31, "success": True},
        {"run_id": "r2", "quality": 55.0, "deviation": 0.62, "success": False},
    ]
    n = distill_review_knowledge(reviews, sink_path=str(sink))
    assert n == 2
    lines = [json.loads(l) for l in sink.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["run_id"] == "r1"
    assert lines[0]["failure_mode"] is False  # quality=72 >= 60 and success=True
    assert lines[1]["run_id"] == "r2"
    assert lines[1]["failure_mode"] is True   # quality=55 < 60


def test_distill_dedup_same_run(tmp_path):
    """同 run_id 不重复写入"""
    sink = tmp_path / "evolution_knowledge.jsonl"
    reviews = [{"run_id": "rX", "quality": 60.0, "deviation": 0.4, "success": True}]
    n1 = distill_review_knowledge(reviews, sink_path=str(sink))
    assert n1 == 1
    n2 = distill_review_knowledge(reviews, sink_path=str(sink))  # 重复写入
    assert n2 == 0
    assert len(sink.read_text(encoding="utf-8").splitlines()) == 1


def test_distill_empty_reviews(tmp_path):
    """空 reviews → 不写入"""
    sink = tmp_path / "evolution_knowledge.jsonl"
    n = distill_review_knowledge([], sink_path=str(sink))
    assert n == 0
    assert not sink.exists()


def test_distill_failure_mode_detection(tmp_path):
    """failure_mode: quality<60 或 success=False 均为失败模式"""
    sink = tmp_path / "evolution_knowledge.jsonl"
    reviews = [
        {"run_id": "a", "quality": 80.0, "success": True},    # 正常
        {"run_id": "b", "quality": 40.0, "success": True},    # 低质量
        {"run_id": "c", "quality": 80.0, "success": False},   # 失败
        {"run_id": "d", "quality": 40.0, "success": False},   # 双重失败
    ]
    distill_review_knowledge(reviews, sink_path=str(sink))
    lines = [json.loads(l) for l in sink.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["failure_mode"] is False
    assert lines[1]["failure_mode"] is True
    assert lines[2]["failure_mode"] is True
    assert lines[3]["failure_mode"] is True
