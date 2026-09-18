"""tests/test_camera_classifier.py - 运镜分类器测试 (T3 策略3)

TDD: 先写失败测试 → 再实现 core/camera_movement_classifier.py

方向约定 (已通过 debug 验证):
  窗口左移 → 特征右移 (dx > 0) → pan_left
  窗口右移 → 特征左移 (dx < 0) → pan_right
  窗口扩大 + resize → 特征内缩 (radial < 0) → zoom_in
  窗口缩小 + resize → 特征外扩 (radial > 0) → zoom_out

测试 fixture 使用 OpenCV 程序化生成, 不依赖 ffmpeg。
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

# ── 合成视频参数 ──────────────────────────────────────────────────────
_W, _H = 320, 240
_FPS = 24
_N_FRAMES = 50
_SRC_SIZE = (800, 600)


# ── 合成 fixture 生成器 ──────────────────────────────────────────────

def _make_source_image() -> np.ndarray:
    """纹理丰富的源图 (随机色块 + 圆 + 线条)"""
    rng = np.random.RandomState(42)
    img = rng.randint(40, 220, _SRC_SIZE[::-1] + (3,), dtype=np.uint8)
    for _ in range(60):
        cx, cy = rng.randint(50, _SRC_SIZE[0] - 50), rng.randint(50, _SRC_SIZE[1] - 50)
        r = rng.randint(8, 45)
        color = tuple(int(c) for c in rng.randint(0, 256, 3))
        cv2.circle(img, (cx, cy), r, color, -1)
    for _ in range(40):
        pt1 = tuple(int(v) for v in rng.randint(20, _SRC_SIZE[0] - 20, 2))
        pt2 = tuple(int(v) for v in rng.randint(20, _SRC_SIZE[0] - 20, 2))
        color = tuple(int(c) for c in rng.randint(0, 256, 3))
        cv2.line(img, pt1, pt2, color, 2)
    cv2.GaussianBlur(img, (3, 3), 0, img)
    return img


def _gen_video(frames: list[np.ndarray], path: Path) -> Path:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, _FPS, (_W, _H))
    for f in frames:
        writer.write(f)
    writer.release()
    return path


def _gen_static(n: int = _N_FRAMES) -> list[np.ndarray]:
    src = _make_source_image()
    cx, cy = (_SRC_SIZE[0] - _W) // 2, (_SRC_SIZE[1] - _H) // 2
    base = src[cy:cy + _H, cx:cx + _W]
    return [base.copy() for _ in range(n)]


def _gen_pan_left(n: int = _N_FRAMES) -> list[np.ndarray]:
    """相机向左: 窗口左移 → 特征右移 (dx > 0) → pan_left"""
    src = _make_source_image()
    cy = (_SRC_SIZE[1] - _H) // 2
    start_x = (_SRC_SIZE[0] - _W) // 2 + 60
    end_x = (_SRC_SIZE[0] - _W) // 2 - 60
    frames = []
    for i in range(n):
        t = i / max(n - 1, 1)
        x = int(start_x + (end_x - start_x) * t)
        frames.append(src[cy:cy + _H, x:x + _W].copy())
    return frames


def _gen_pan_right(n: int = _N_FRAMES) -> list[np.ndarray]:
    """相机向右: 窗口右移 → 特征左移 (dx < 0) → pan_right"""
    src = _make_source_image()
    cy = (_SRC_SIZE[1] - _H) // 2
    start_x = (_SRC_SIZE[0] - _W) // 2 - 60
    end_x = (_SRC_SIZE[0] - _W) // 2 + 60
    frames = []
    for i in range(n):
        t = i / max(n - 1, 1)
        x = int(start_x + (end_x - start_x) * t)
        frames.append(src[cy:cy + _H, x:x + _W].copy())
    return frames


def _gen_zoom_in(n: int = _N_FRAMES) -> list[np.ndarray]:
    """推近: 窗口从大到小 (1.4→1.0) + resize → 内容放大 → radial > 0 → zoom_in

    (2026-08-15 方向翻转同步: 推近=画面放大=特征外扩=radial>0;
     旧 fixture 窗口方向与名称相反, 被判成 zoom_out)
    """
    src = _make_source_image()
    sh, sw = _SRC_SIZE[1], _SRC_SIZE[0]
    cx_s, cy_s = sw / 2.0, sh / 2.0
    frames = []
    for i in range(n):
        t = i / max(n - 1, 1)
        scale = 1.4 - 0.4 * t  # 窗口缩小: 1.4 → 1.0 (内容放大)
        ww, wh = int(_W * scale), int(_H * scale)
        x0 = int(cx_s - ww / 2)
        y0 = int(cy_s - wh / 2)
        roi = src[y0:y0 + wh, x0:x0 + ww]
        frames.append(cv2.resize(roi, (_W, _H), interpolation=cv2.INTER_LINEAR))
    return frames


def _gen_zoom_out(n: int = _N_FRAMES) -> list[np.ndarray]:
    """拉远: 窗口从小到大 (1.0→1.4) + resize → 内容缩小 → radial < 0 → zoom_out"""
    src = _make_source_image()
    sh, sw = _SRC_SIZE[1], _SRC_SIZE[0]
    cx_s, cy_s = sw / 2.0, sh / 2.0
    frames = []
    for i in range(n):
        t = i / max(n - 1, 1)
        scale = 1.0 + 0.4 * t  # 窗口扩大: 1.0 → 1.4 (内容缩小)
        ww, wh = int(_W * scale), int(_H * scale)
        x0 = int(cx_s - ww / 2)
        y0 = int(cy_s - wh / 2)
        roi = src[y0:y0 + wh, x0:x0 + ww]
        frames.append(cv2.resize(roi, (_W, _H), interpolation=cv2.INTER_LINEAR))
    return frames


# ── pytest fixtures ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def video_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("cam_cls")


@pytest.fixture(scope="module")
def static_video(video_dir: Path) -> Path:
    return _gen_video(_gen_static(), video_dir / "static.mp4")


@pytest.fixture(scope="module")
def pan_left_video(video_dir: Path) -> Path:
    return _gen_video(_gen_pan_left(), video_dir / "pan_left.mp4")


@pytest.fixture(scope="module")
def pan_right_video(video_dir: Path) -> Path:
    return _gen_video(_gen_pan_right(), video_dir / "pan_right.mp4")


@pytest.fixture(scope="module")
def zoom_in_video(video_dir: Path) -> Path:
    return _gen_video(_gen_zoom_in(), video_dir / "zoom_in.mp4")


@pytest.fixture(scope="module")
def zoom_out_video(video_dir: Path) -> Path:
    return _gen_video(_gen_zoom_out(), video_dir / "zoom_out.mp4")


@pytest.fixture(scope="module")
def complex_video(video_dir: Path) -> Path:
    """复合运动: 平移+缩放同时"""
    src = _make_source_image()
    sh, sw = _SRC_SIZE[1], _SRC_SIZE[0]
    cx_s, cy_s = sw / 2.0, sh / 2.0
    frames = []
    for i in range(_N_FRAMES):
        t = i / max(_N_FRAMES - 1, 1)
        scale = 1.0 + 0.2 * t
        ww, wh = int(_W * scale), int(_H * scale)
        offset_x = int(80 * t)
        x0 = int(cx_s - ww / 2) + offset_x
        y0 = int(cy_s - wh / 2)
        x0 = max(0, min(x0, sw - ww))
        y0 = max(0, min(y0, sh - wh))
        roi = src[y0:y0 + wh, x0:x0 + ww]
        frames.append(cv2.resize(roi, (_W, _H), interpolation=cv2.INTER_LINEAR))
    return _gen_video(frames, video_dir / "complex.mp4")


# ══════════════════════════════════════════════════════════════════════
# 测试用例
# ══════════════════════════════════════════════════════════════════════

class TestClassifySegment:
    """classify_video: 给定视频 → 返回运镜类型"""

    def test_static_returns_static(self, static_video):
        from core.camera_movement_classifier import classify_video
        result = classify_video(str(static_video))
        assert result["dominant"] == "static", (
            f"静态视频应判为 static, 实际: {result['dominant']}"
        )

    def test_pan_left_detected(self, pan_left_video):
        from core.camera_movement_classifier import classify_video
        result = classify_video(str(pan_left_video))
        assert result["dominant"] == "pan_left", (
            f"向左平移应判为 pan_left, 实际: {result['dominant']}, "
            f"dx={result['flow_stats']['mean_dx']:.1f}"
        )

    def test_pan_right_detected(self, pan_right_video):
        from core.camera_movement_classifier import classify_video
        result = classify_video(str(pan_right_video))
        assert result["dominant"] == "pan_right", (
            f"向右平移应判为 pan_right, 实际: {result['dominant']}, "
            f"dx={result['flow_stats']['mean_dx']:.1f}"
        )

    def test_zoom_in_detected(self, zoom_in_video):
        from core.camera_movement_classifier import classify_video
        result = classify_video(str(zoom_in_video))
        assert result["dominant"] == "zoom_in", (
            f"推近应判为 zoom_in, 实际: {result['dominant']}, "
            f"radial={result['flow_stats']['mean_radial']:.2f}"
        )

    def test_zoom_out_detected(self, zoom_out_video):
        from core.camera_movement_classifier import classify_video
        result = classify_video(str(zoom_out_video))
        assert result["dominant"] == "zoom_out", (
            f"拉远应判为 zoom_out, 实际: {result['dominant']}, "
            f"radial={result['flow_stats']['mean_radial']:.2f}"
        )

    def test_complex_not_static(self, complex_video):
        """复合运动不应被判为 static"""
        from core.camera_movement_classifier import classify_video
        result = classify_video(str(complex_video))
        assert result["dominant"] != "static", "复合运动不应判为 static"


class TestClassifyVideo:
    """返回结构完整性"""

    def test_result_has_required_keys(self, static_video):
        from core.camera_movement_classifier import classify_video
        result = classify_video(str(static_video))
        assert "dominant" in result
        assert "confidence" in result
        assert "flow_stats" in result
        assert "per_segment" in result

    def test_confidence_in_range(self, static_video):
        from core.camera_movement_classifier import classify_video
        result = classify_video(str(static_video))
        assert 0.0 <= result["confidence"] <= 1.0

    def test_per_segment_nonempty(self, static_video):
        from core.camera_movement_classifier import classify_video
        result = classify_video(str(static_video))
        assert len(result["per_segment"]) >= 1

    def test_missing_file_returns_safe_default(self):
        from core.camera_movement_classifier import classify_video
        result = classify_video("/nonexistent/video.mp4")
        assert result["dominant"] == "unknown"
        assert result["confidence"] == 0.0


class TestCameraVocabulary:
    """运镜词汇表与 taste_contract 运镜池兼容"""

    def test_all_labels_are_strings(self):
        from core.camera_movement_classifier import CAMERA_LABELS
        for label in CAMERA_LABELS:
            assert isinstance(label, str)

    def test_labels_overlap_taste_contract_pools(self):
        from ai.taste_contract import (
            HIGH_MOTION_POOL,
            LOW_MOTION_POOL,
            MID_MOTION_POOL,
        )
        from core.camera_movement_classifier import CAMERA_LABELS
        all_pool = set(LOW_MOTION_POOL) | set(MID_MOTION_POOL) | set(HIGH_MOTION_POOL)
        for name in all_pool:
            assert name in CAMERA_LABELS, (
                f"taste_contract 运镜 '{name}' 不在分类器输出词汇表中"
            )


class TestBatchClassify:
    """batch_classify: 批量扫描视频文件"""

    def test_batch_returns_list(self, static_video, pan_left_video):
        from core.camera_movement_classifier import batch_classify
        results = batch_classify([str(static_video), str(pan_left_video)])
        assert len(results) == 2
        assert all("dominant" in r for r in results)
        assert all("video_path" in r for r in results)

    def test_batch_empty_input(self):
        from core.camera_movement_classifier import batch_classify
        assert batch_classify([]) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])
