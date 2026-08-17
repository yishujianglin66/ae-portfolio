"""MovieShots 数据集适配器单元测试。

覆盖: JSON 三种结构解析 / 标签映射 / 统一 JSONL 导出 / 分布统计。
"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.data.movieshots_dataset import (  # noqa: E402
    MOVEMENT_TO_PROJECT,
    MovieShotsDataset,
    MovieShotSample,
    _iter_movieshots_json,
    build_label_stats,
)
from models.data.dataset_base import DatasetConfig  # noqa: E402


def _write_v1(tmp: str) -> str:
    """v1 结构: {trailer_id: {shot_idx: {scale, movement}}}"""
    data = {
        "tt0000001": {
            "0001": {"scale": {"value": 1, "label": "CS"},
                     "movement": {"value": 4, "label": "Static"}},
            "0002": {"scale": {"value": 3, "label": "MS"},
                     "movement": {"value": 1, "label": "Motion"}},
        },
        "tt0000002": {
            "0003": {"movement": {"value": 3, "label": "Push"}},
        },
    }
    p = os.path.join(tmp, "v1_full_trailer.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return tmp


def _write_v3(tmp: str) -> str:
    """v3 结构: {"full": {"movie": {imdb: {shot_idx: {...}}}}}"""
    data = {
        "full": {
            "movie": {
                "tt1000000": {
                    "0010": {"scale": {"value": 0, "label": "LS"},
                             "movement": {"value": 2, "label": "Pull"}},
                }
            }
        }
    }
    p = os.path.join(tmp, "v3_full.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return tmp


def test_v1_parse_and_mapping(tmp_path):
    _write_v1(str(tmp_path))
    samples = _iter_movieshots_json(os.path.join(str(tmp_path), "v1_full_trailer.json"))
    assert len(samples) == 3
    by_key = {(s.movie_id, s.shot_idx): s for s in samples}
    assert by_key[("tt0000001", "0001")].movement_label == "static"
    assert by_key[("tt0000001", "0002")].movement_label == "pan_left"  # Motion -> pan_left
    assert by_key[("tt0000002", "0003")].movement_label == "zoom_in"   # Push -> zoom_in
    assert by_key[("tt0000001", "0001")].scale_label == "CS"


def test_v3_parse(tmp_path):
    _write_v3(str(tmp_path))
    samples = _iter_movieshots_json(os.path.join(str(tmp_path), "v3_full.json"))
    assert len(samples) == 1
    assert samples[0].movement_label == "zoom_out"  # Pull -> zoom_out
    assert samples[0].scale_label == "LS"


def test_mapping_table_complete():
    # 每个 MovieShots 原始标签都要有项目映射
    assert MOVEMENT_TO_PROJECT["Static"] == "static"
    assert MOVEMENT_TO_PROJECT["Motion"] == "pan_left"
    assert MOVEMENT_TO_PROJECT["Pull"] == "zoom_out"
    assert MOVEMENT_TO_PROJECT["Push"] == "zoom_in"
    assert MOVEMENT_TO_PROJECT["Multi_movement"] == "complex"


def test_dataset_prepare_and_jsonl(tmp_path):
    _write_v1(str(tmp_path))
    _write_v3(str(tmp_path))
    cfg = DatasetConfig(dataset_name="MovieShots", data_path=str(tmp_path),
                        data_augmentation=False)
    ds = MovieShotsDataset(cfg)
    stats = ds.prepare()
    assert stats.total_samples == 4  # 3 (v1) + 1 (v3)

    # 导出 JSONL 并回读
    out = os.path.join(str(tmp_path), "unified.jsonl")
    n = ds.to_jsonl(out)
    assert n == 4
    with open(out, encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    assert len(lines) == 4
    assert {l["movement_label"] for l in lines} == {"static", "pan_left", "zoom_in", "zoom_out"}


def test_label_stats(tmp_path):
    samples = [
        MovieShotSample("t1", "0001", "static", "Static", 4),
        MovieShotSample("t1", "0002", "pan_left", "Motion", 1),
        MovieShotSample("t2", "0001", "static", "Static", 4),
    ]
    dist = build_label_stats(samples)
    assert dist == {"static": 2, "pan_left": 1}


def test_unknown_label_filtered(tmp_path):
    _write_v1(str(tmp_path))
    # 追加一个 unknown 样本
    p = os.path.join(str(tmp_path), "v1_full_trailer.json")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    data["tt0000003"] = {"0001": {"movement": {"value": -1, "label": "Bogus"}}}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f)
    cfg = DatasetConfig(dataset_name="MovieShots", data_path=str(tmp_path),
                        data_augmentation=False)
    ds = MovieShotsDataset(cfg)
    stats = ds.prepare()
    # unknown 在 preprocess 阶段被过滤 (filter_invalid 之前)
    assert stats.total_samples == 3
    assert all(s.movement_label != "unknown"
               for s in ds.get_train_data() + ds.get_val_data() + ds.get_test_data())
