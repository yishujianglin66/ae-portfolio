"""Tests for ai.director_feedback_hook - D2 根因修复

验证导演渲染成功后将真实参数(speed_ramp 等)写入 param_feedback.json。
"""
import json
from pathlib import Path
from ai.director_feedback_hook import record_director_feedback


def test_record_director_feedback_writes_real_records(tmp_path, monkeypatch):
    """导演运行后写入真实参数反馈"""
    store = tmp_path / "param_feedback.json"
    monkeypatch.setenv("PARAM_FEEDBACK_PATH", str(store))
    run_info = {
        "run_id": "director_test_001",
        "quality": 74.5,
        "ramps": [{"type": "speed_ramp", "peak_speed": 2.4, "beat_aligned": True}],
        "style": "高燃",
    }
    written = record_director_feedback(run_info)
    assert written == 1

    data = json.loads(store.read_text(encoding="utf-8"))
    recs = [r for r in data["records"] if r["metadata"].get("source") == "director_v23"]
    assert len(recs) == 1
    assert recs[0]["effect_name"] == "speed_ramp"
    assert recs[0]["parameters"]["peak_speed"] == 2.4
    assert recs[0]["rating"] > 0.7
    assert recs[0]["record_id"].startswith("director_")


def test_record_director_feedback_multiple_ramps(tmp_path, monkeypatch):
    """多个 ramp 全部写入"""
    store = tmp_path / "param_feedback.json"
    monkeypatch.setenv("PARAM_FEEDBACK_PATH", str(store))
    run_info = {
        "run_id": "director_test_002",
        "quality": 80.0,
        "ramps": [
            {"type": "speed_ramp", "peak_speed": 1.5},
            {"type": "speed_ramp", "peak_speed": 3.0},
            {"type": "zoom_effect", "zoom_level": 1.2},
        ],
        "style": "抒情",
    }
    written = record_director_feedback(run_info)
    assert written == 3

    data = json.loads(store.read_text(encoding="utf-8"))
    assert len(data["records"]) == 3


def test_record_director_feedback_no_ramps(tmp_path, monkeypatch):
    """无 ramp → 不写入, 返回 0"""
    store = tmp_path / "param_feedback.json"
    monkeypatch.setenv("PARAM_FEEDBACK_PATH", str(store))
    run_info = {
        "run_id": "director_test_003",
        "quality": 60.0,
        "ramps": [],
        "style": "高燃",
    }
    written = record_director_feedback(run_info)
    assert written == 0
    assert not store.exists()  # 无内容不创建文件


def test_record_director_feedback_appends(tmp_path, monkeypatch):
    """多次调用追加, 不覆盖"""
    store = tmp_path / "param_feedback.json"
    monkeypatch.setenv("PARAM_FEEDBACK_PATH", str(store))

    record_director_feedback({
        "run_id": "run_1", "quality": 70.0,
        "ramps": [{"type": "speed_ramp", "peak_speed": 2.0}],
        "style": "高燃",
    })
    record_director_feedback({
        "run_id": "run_2", "quality": 80.0,
        "ramps": [{"type": "speed_ramp", "peak_speed": 1.5}],
        "style": "抒情",
    })

    data = json.loads(store.read_text(encoding="utf-8"))
    assert len(data["records"]) == 2


def test_rating_bounded(tmp_path, monkeypatch):
    """rating 必须在 [0, 1]"""
    store = tmp_path / "param_feedback.json"
    monkeypatch.setenv("PARAM_FEEDBACK_PATH", str(store))

    # quality > 100 → rating 截断为 1.0
    record_director_feedback({
        "run_id": "run_high", "quality": 150.0,
        "ramps": [{"type": "speed_ramp", "peak_speed": 2.0}],
    })
    data = json.loads(store.read_text(encoding="utf-8"))
    assert data["records"][0]["rating"] == 1.0

    # quality < 0 → rating 截断为 0.0
    store.unlink()
    record_director_feedback({
        "run_id": "run_low", "quality": -10.0,
        "ramps": [{"type": "speed_ramp", "peak_speed": 2.0}],
    })
    data = json.loads(store.read_text(encoding="utf-8"))
    assert data["records"][0]["rating"] == 0.0
