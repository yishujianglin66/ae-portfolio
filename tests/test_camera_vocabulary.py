"""core/camera_vocabulary.py 单元测试。

覆盖: 方向映射表完整性 / 典型多标签 → 扁平标签 / 多维拆分。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.camera_vocabulary import (  # noqa: E402
    ANNOTATION_LABEL_SCHEMA,
    CAMERABENCH_LABELS,
    DIRECTION_TO_PROJECT,
    map_camerabench_multi,
    map_camerabench_to_project,
)


def test_camerabench_label_count():
    # 34 原语 = 26 方向 + 7 tracking + 3 speed + 4 stability + 1 complexity
    assert len(CAMERABENCH_LABELS) == 34


def test_direction_table_maps_to_project_labels():
    from core.camera_movement_classifier import CAMERA_LABELS
    proj = set(CAMERA_LABELS)
    for v in DIRECTION_TO_PROJECT.values():
        assert v in proj, f"映射目标 {v} 不在项目 CAMERA_LABELS"


def test_static_group():
    assert map_camerabench_to_project(["static"]) == "static"
    assert map_camerabench_to_project(["no-motion"]) == "static"
    assert map_camerabench_to_project(["no-motion", "static", "regular-speed"]) == "static"


def test_pan_truck():
    assert map_camerabench_to_project(["pan-left"]) == "pan_left"
    assert map_camerabench_to_project(["truck-right"]) == "pan_right"


def test_tilt_pedestal():
    assert map_camerabench_to_project(["tilt-up"]) == "tilt_up"
    assert map_camerabench_to_project(["pedestal-down"]) == "tilt_down"


def test_zoom_vs_dolly_distinction():
    # 关键: lens zoom 与物理 dolly 区分 (项目 push/zoom_back 精确对应 dolly)
    assert map_camerabench_to_project(["zoom-in"]) == "zoom_in"
    assert map_camerabench_to_project(["zoom-out"]) == "zoom_out"
    assert map_camerabench_to_project(["dolly-in"]) == "push"
    assert map_camerabench_to_project(["dolly-out"]) == "zoom_back"


def test_orbit_roll():
    assert map_camerabench_to_project(["arc-CW"]) == "orbit"
    assert map_camerabench_to_project(["roll-CCW"]) == "orbit"


def test_tracking_merge_with_direction():
    # 跟拍与显式方向同轴合并 → 不冲突
    assert map_camerabench_to_project(["side-tracking", "truck-right"]) == "pan_right"


def test_multi_axis_is_complex():
    # 多轴方向 → complex
    assert map_camerabench_to_project(["pan-left", "arc-CCW"]) == "complex"
    # 双向冲突 → complex
    assert map_camerabench_to_project(["pan-left", "pan-right"]) == "complex"


def test_complex_motion_fallback():
    # 无方向但有 complex-motion → complex (复杂度兜底)
    assert map_camerabench_to_project(["complex-motion"]) == "complex"
    # complex-motion 是复杂度维度, 不覆盖唯一方向
    assert map_camerabench_to_project(["complex-motion", "tilt-down"]) == "tilt_down"


def test_empty_unknown():
    assert map_camerabench_to_project([]) == "unknown"
    assert map_camerabench_to_project(["regular-speed", "no-shaking"]) == "unknown"


def test_multi_schema():
    r = map_camerabench_multi(["dolly-in", "fast-speed", "unsteady"])
    assert r == {"direction": "push", "speed": "fast-speed", "stability": "unsteady"}
    # 默认 speed/stability
    r2 = map_camerabench_multi(["pan-left"])
    assert r2["direction"] == "pan_left"
    assert r2["speed"] == "regular-speed"
    assert r2["stability"] == "no-shaking"


def test_annotation_schema_for_step4():
    # Step 4 VLM 预标注 schema 必须覆盖项目 13 类方向语义
    assert "push" in ANNOTATION_LABEL_SCHEMA["direction"]
    assert "zoom_back" in ANNOTATION_LABEL_SCHEMA["direction"]
    assert len(ANNOTATION_LABEL_SCHEMA["speed"]) == 3
    assert len(ANNOTATION_LABEL_SCHEMA["stability"]) == 4
