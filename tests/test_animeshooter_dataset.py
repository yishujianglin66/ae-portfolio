"""AnimeShooter 数据集适配器单元测试。

覆盖: JSON 解析 (顶层解包 / 段内镜头) / 时间计算 / 导出 JSONL / 统计。
"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.data.animeshooter_dataset import (  # noqa: E402
    SCHEMA,
    AnimeShooterDataset,
    AnimeShotSample,
    _iter_annotation_json,
    _parse_clock,
    build_shot_stats,
)
from models.data.dataset_base import DatasetConfig  # noqa: E402


def _write_annot(tmp: str) -> str:
    """写一个含 2 段、每段 2 镜头的标注 JSON。"""
    data = {
        "video_id": "oqGuJhOeMek",
        "url": "https://youtube.com/watch?v=oqGuJhOeMek",
        "fps": 24.0,
        "segments": [
            {
                "start frame index": 0,
                "end frame index": 1440,
                "story script": {
                    "storyline": "test story A",
                    "shots": [
                        {"start time": "00:00", "end time": "00:05",
                         "is_prologue_or_epilogue": True,
                         "main characters": ["c1"], "scene": "s1",
                         "visual annotation": {"narrative caption": "n1",
                                               "descriptive caption": "d1"}},
                        {"start time": "00:05", "end time": "00:12",
                         "main characters": ["c2"], "scene": "s2",
                         "visual annotation": {"narrative caption": "n2",
                                               "descriptive caption": "d2"}},
                    ],
                },
            },
            {
                "start frame index": 1440,
                "end frame index": 2880,
                "story script": {
                    "storyline": "test story B",
                    "shots": [
                        {"start time": "00:00", "end time": "00:10",
                         "main characters": ["c1"], "scene": "s1",
                         "visual annotation": {"narrative caption": "n3",
                                               "descriptive caption": "d3"}},
                    ],
                },
            },
        ],
    }
    p = os.path.join(tmp, "oqGuJhOeMek.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return p


def test_parse_clock():
    assert _parse_clock("00:12") == 12.0
    assert _parse_clock("01:30") == 90.0
    assert _parse_clock("1:02:03") == 3723.0
    assert _parse_clock("") == 0.0
    assert _parse_clock(None) == 0.0


def test_parse_annotation(tmp_path):
    p = _write_annot(str(tmp_path))
    samples = _iter_annotation_json(p)
    assert len(samples) == 3
    # 第 1 段第 1 镜: 0s -> 5s, prologue
    assert samples[0].video_id == "oqGuJhOeMek"
    assert samples[0].segment_idx == 0 and samples[0].shot_idx == 0
    assert samples[0].start_sec == 0.0 and samples[0].end_sec == 5.0
    assert samples[0].is_prologue_or_epilogue is True
    # 第 2 段第 1 镜: 段起始帧 1440/24=60s + 0s = 60s
    assert samples[2].segment_idx == 1
    assert samples[2].start_sec == 60.0 and samples[2].end_sec == 70.0
    assert samples[2].narrative_caption == "n3"


def test_dataset_prepare_and_jsonl(tmp_path):
    _write_annot(str(tmp_path))
    cfg = DatasetConfig(dataset_name="AnimeShooter", data_path=str(tmp_path),
                        data_augmentation=False)
    ds = AnimeShooterDataset(cfg)
    stats = ds.prepare()
    assert stats.total_samples == 3

    out = os.path.join(str(tmp_path), "shots.jsonl")
    n = ds.to_jsonl(out)
    assert n == 3
    with open(out, encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    assert len(lines) == 3
    assert all(l["schema"] == SCHEMA for l in lines)
    assert all(l["movement_label"] is None for l in lines)  # 待 VLM 预标注


def test_shot_stats(tmp_path):
    _write_annot(str(tmp_path))
    samples = _iter_annotation_json(_write_annot(str(tmp_path)))
    st = build_shot_stats(samples)
    assert st["n_shots"] == 3
    assert st["n_videos"] == 1
    assert st["avg_duration_sec"] > 0


def test_invalid_duration_filtered(tmp_path):
    p = _write_annot(str(tmp_path))
    # 追加一个 0 时长镜头 (start == end), 应在 preprocess 被过滤
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    data["segments"][1]["story script"]["shots"].append(
        {"start time": "00:10", "end time": "00:10",
         "visual annotation": {"narrative caption": "zero", "descriptive caption": ""}})
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    cfg = DatasetConfig(dataset_name="AnimeShooter", data_path=str(tmp_path),
                        data_augmentation=False)
    ds = AnimeShooterDataset(cfg)
    stats = ds.prepare()
    assert stats.total_samples == 3  # 4 - 1 (0 时长)
