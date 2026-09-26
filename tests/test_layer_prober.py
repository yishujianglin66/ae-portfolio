# -*- coding: utf-8 -*-
"""layer_prober 判别力测试（准则四：改码必测——信号方向性用合成帧锁定）。

合成帧真值已知，验证 8 信号"方向正确"而非具体数值：
  静止帧 → frozen/低boil；整幅平移 → rigid 高 + parallax 中；
  逐帧噪声 → boil 高；纯色帧 → flat=1.0；平涂双色 → banding 低。
"""
import sys
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.layer_prober import probe_shot  # noqa: E402

H, W = 180, 320


def _img(draw_fn):
    f = np.zeros((H, W, 3), np.uint8)
    draw_fn(f)
    return f


def test_static_frames_frozen():
    # 渐变背景（无大面积同色）+ 方块：静止 → 边缘完全稳定、boil≈0、flat 低
    base = np.tile(np.linspace(30, 220, W, dtype=np.uint8), (H, 1))
    f = np.stack([base] * 3, axis=2)
    cv2.rectangle(f, (80, 40), (240, 140), (200, 120, 60), -1)
    r = probe_shot([f.copy() for _ in range(8)])
    assert r["flat_share"] < 0.1
    assert r["edge_stability"] > 0.9       # 静止=边缘完全稳定
    assert r["line_boil"] < 0.01


def test_solid_frame_flat():
    f = np.full((H, W, 3), 255, np.uint8)
    r = probe_shot([f.copy() for _ in range(8)])
    assert r["flat_share"] > 0.99


def test_translation_rigid_high():
    """刚体方块整体平移 → rigid_consistency 高（块内流一致）。"""
    frames = []
    for i in range(10):
        f = np.zeros((H, W, 3), np.uint8)
        cv2.rectangle(f, (40 + i * 8, 60), (140 + i * 8, 120), (180, 180, 180), -1)
        cv2.rectangle(f, (200, 30), (260, 150), (60, 160, 220), -1)  # 静止块对照
        frames.append(f)
    r = probe_shot(frames)
    assert r["rigid_consistency"] > 0.3    # 方向性：有刚体运动则非零偏高


def test_handdrawn_boil_high():
    """手书模拟：方块边缘逐帧随机抖动 ±2px → 边缘 IoU 波动（boil 高）。
    注：纯噪声不是手书的合成真值——噪声边缘密度统计稳定，IoU 反而恒定。"""
    rng = np.random.default_rng(11)
    frames = []
    for _ in range(10):
        f = np.zeros((H, W, 3), np.uint8)
        jx, jy = rng.integers(-2, 3, 2)
        cv2.rectangle(f, (80 + int(jx), 40 + int(jy)), (240 + int(jx), 140 + int(jy)),
                      (200, 200, 200), 2)  # 线稿=描边无填充
        frames.append(f)
    r = probe_shot(frames)
    assert r["line_boil"] > 0.01           # 方向性：抖动边缘的 IoU 波动明显大于静止
    assert r["edge_stability"] < 0.95


def test_cel_shading_low_banding():
    f = np.zeros((H, W, 3), np.uint8)
    f[:, :, :] = (40, 40, 40)
    f[20:80, 20:80] = (200, 100, 50)       # 平涂双色 = 赛璐璐
    r = probe_shot([f.copy() for _ in range(5)])
    assert r["color_banding"] < 0.01       # 唯一色极少


def test_short_shot_degrades_gracefully():
    r = probe_shot([np.zeros((H, W, 3), np.uint8)])
    assert r["n_frames"] == 1 and "flat_share" in r
