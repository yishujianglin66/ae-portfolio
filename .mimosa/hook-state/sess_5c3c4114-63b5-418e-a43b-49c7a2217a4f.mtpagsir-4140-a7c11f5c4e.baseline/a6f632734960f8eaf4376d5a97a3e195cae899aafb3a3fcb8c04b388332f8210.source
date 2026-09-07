# -*- coding: utf-8 -*-
"""VisualEvalGateway 单元测试（M2 验收，[AE-sync]）

覆盖：
  1. Rubric 预设与加权总分
  2. 模型输出 JSON 稳健解析（围栏/前后缀/缺维度）
  3. 启发式离线评分与变体优选排序（sharp 高对比 > 模糊暗图）
  4. md5 磁盘缓存幂等
  5. VLM 后端 mock（llm_gateway 通道 + 图片透传 + 解析）
  6. 视频抽帧采样
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
import pytest

from core.visual_eval_gateway import (
    VisualEvalGateway, get_rubric, parse_score_json, weighted_total,
    Rubric, DimensionScore, RUBRIC_AE_DEFAULT, RUBRIC_TEXT_FOCUS,
)


def _make_image(sharp: bool = True, bright: bool = True, size=(320, 240)):
    """合成测试图：sharp=棋盘格高对比；否则模糊纯灰"""
    if sharp:
        img = np.zeros((size[1], size[0], 3), dtype=np.uint8)
        cell = 16
        for y in range(0, size[1], cell):
            for x in range(0, size[0], cell):
                v = 255 if ((x // cell + y // cell) % 2 == 0) else 0
                img[y:y + cell, x:x + cell] = (v, v, v)
    else:
        img = np.full((size[1], size[0], 3), 40 if bright else 10, dtype=np.uint8)
        img = cv2.GaussianBlur(img, (15, 15), 5)
    return img


# ── 1. Rubric 预设 ───────────────────────────────────────────────────
def test_rubric_presets():
    r = get_rubric(RUBRIC_AE_DEFAULT)
    assert r.id == RUBRIC_AE_DEFAULT
    assert [d.name for d in r.dimensions] == [
        "impact", "composition", "color", "fx_quality",
        "text_readability", "style_consistency", "beat_sync"]
    assert all(d.weight > 0 for d in r.dimensions)
    t = get_rubric(RUBRIC_TEXT_FOCUS)
    assert any(d.name == "animation_smoothness" for d in t.dimensions)
    with pytest.raises(ValueError):
        get_rubric("no_such_preset")


def test_weighted_total():
    dims = [DimensionScore(name="a", score=5.0, weight=1.0),
            DimensionScore(name="b", score=1.0, weight=1.0)]
    assert weighted_total(dims) == 50.0
    assert weighted_total([DimensionScore(name="a", score=5.0)]) == 100.0
    assert weighted_total([]) == 0.0
    # 加权：高分高权重拉高总分
    dims2 = [DimensionScore(name="a", score=5.0, weight=3.0),
             DimensionScore(name="b", score=1.0, weight=1.0)]
    assert weighted_total(dims2) == 75.0


# ── 2. JSON 稳健解析 ────────────────────────────────────────────────
def test_parse_score_json_fenced_and_prose():
    r = get_rubric(RUBRIC_AE_DEFAULT)
    text = ('好的，以下是评分：\n```json\n{"dims": {"impact": {"score": 5, '
            '"comment": "冲击力强"}, "composition": {"score": 4, "comment": "层次清晰"}}}\n```\n')
    dims = parse_score_json(text, r)
    assert dims[0].score == 5.0 and dims[1].score == 4.0
    # 缺维度 → 中性 3.0 且不抛错
    assert dims[-1].name == "beat_sync" and dims[-1].score == 3.0
    assert "缺省" in dims[-1].comment


def test_parse_score_json_flat_and_errors():
    r = get_rubric(RUBRIC_AE_DEFAULT)
    dims = parse_score_json('{"impact": 4, "color": 2}', r)
    assert dims[0].score == 4.0 and dims[2].score == 2.0
    with pytest.raises(ValueError):
        parse_score_json("完全不是 JSON", r)
    with pytest.raises(ValueError):
        parse_score_json("", r)


# ── 3. 启发式离线评分与变体优选 ──────────────────────────────────────
def test_heuristic_sharp_beats_blurry(tmp_path):
    gw = VisualEvalGateway(backend="heuristic", cache_dir=str(tmp_path))
    sharp = _make_image(sharp=True)
    blur = _make_image(sharp=False, bright=False)
    s1 = gw.score_frame_sync(sharp)
    s2 = gw.score_frame_sync(blur)
    assert s1.offline and s2.offline
    assert s1.backend == "heuristic"
    # 冲击力/特效完成度/文字可读性：清晰高对比应更高
    assert s1.dim("impact").score > s2.dim("impact").score
    assert s1.dim("fx_quality").score > s2.dim("fx_quality").score
    assert s1.total > s2.total


def test_compare_variants_offline_ranking(tmp_path):
    gw = VisualEvalGateway(backend="heuristic", cache_dir=str(tmp_path))
    p_a = tmp_path / "sharp.jpg"
    p_b = tmp_path / "blur.jpg"
    cv2.imwrite(str(p_a), _make_image(sharp=True))
    cv2.imwrite(str(p_b), _make_image(sharp=False, bright=False))
    report = gw.compare_variants_sync([
        {"label": "sharp_variant", "image_paths": [str(p_a), str(p_a)],
         "params": {"radius": 30}},
        {"label": "blur_variant", "image_paths": [str(p_b), str(p_b)],
         "params": {"radius": 90}},
    ])
    assert report.offline
    assert report.best.label == "sharp_variant"
    assert report.ranking[0][0] == "sharp_variant"
    assert report.ranking[0][1] > report.ranking[1][1]
    assert report.variants[0].params == {"radius": 30}


def test_variant_missing_paths_raises(tmp_path):
    gw = VisualEvalGateway(backend="heuristic", cache_dir=str(tmp_path))
    with pytest.raises(ValueError):
        gw.compare_variants_sync([{"label": "empty", "image_paths": []}])


# ── 4. md5 磁盘缓存 ──────────────────────────────────────────────────
def test_cache_second_hit(tmp_path):
    gw = VisualEvalGateway(backend="heuristic", cache_dir=str(tmp_path))
    p = tmp_path / "img.jpg"
    cv2.imwrite(str(p), _make_image(sharp=True))
    s1 = gw.score_path_sync(str(p))
    assert not s1.from_cache
    s2 = gw.score_path_sync(str(p))
    assert s2.from_cache
    assert s2.total == s1.total
    assert s2.md5 == s1.md5


# ── 5. VLM 后端 mock ─────────────────────────────────────────────────
def test_vlm_backend_mocked(tmp_path):
    import core.llm_gateway as lg_mod

    captured = {}

    async def fake_chat(**kwargs):
        captured["images"] = kwargs.get("images")
        captured["task_type"] = kwargs.get("task_type")
        return lg_mod.LLMResponse(
            success=True,
            content='{"dims": {"impact": {"score": 5, "comment": "爆"}, '
                    '"composition": {"score": 4, "comment": "好"}}}',
            model="fake-vl-model", provider="fake-provider")

    original = lg_mod.llm_gateway.chat_with_routing
    lg_mod.llm_gateway.chat_with_routing = fake_chat
    try:
        gw = VisualEvalGateway(backend="auto", cache_dir=str(tmp_path))
        p = tmp_path / "img.jpg"
        cv2.imwrite(str(p), _make_image(sharp=True))
        score = gw.score_path_sync(str(p))
        assert score.backend == "vlm" and not score.offline
        assert score.model == "fake-vl-model"
        assert score.dim("impact").score == 5.0
        # 图片以 base64 透传，任务类型为视觉理解
        assert captured["images"] and isinstance(captured["images"][0], str)
        assert captured["task_type"] == lg_mod.TaskType.VISION_UNDERSTANDING
    finally:
        lg_mod.llm_gateway.chat_with_routing = original


def test_vlm_failure_falls_back_heuristic(tmp_path):
    import core.llm_gateway as lg_mod

    async def broken_chat(**kwargs):
        return lg_mod.LLMResponse(success=False, error="no key")

    original = lg_mod.llm_gateway.chat_with_routing
    lg_mod.llm_gateway.chat_with_routing = broken_chat
    try:
        gw = VisualEvalGateway(backend="auto", cache_dir=str(tmp_path))
        p = tmp_path / "img.jpg"
        cv2.imwrite(str(p), _make_image(sharp=True))
        score = gw.score_path_sync(str(p))
        assert score.offline and score.backend == "heuristic"
        assert "no key" in score.fallback_reason
    finally:
        lg_mod.llm_gateway.chat_with_routing = original


# ── 6. 视频抽帧 ──────────────────────────────────────────────────────
def test_frames_from_video(tmp_path):
    vp = tmp_path / "tiny.mp4"
    writer = cv2.VideoWriter(str(vp), cv2.VideoWriter_fourcc(*"mp4v"), 30.0,
                             (320, 240))
    for i in range(9):
        img = np.full((240, 320, 3), i * 25, dtype=np.uint8)
        writer.write(img)
    writer.release()
    gw = VisualEvalGateway(backend="heuristic", cache_dir=str(tmp_path))
    frames = gw.frames_from_video(str(vp), times=[0.0, 0.15, 0.28])
    assert len(frames) == 3
    assert all(isinstance(f, np.ndarray) for _, f in frames)
    # 均匀采样路径
    frames2 = gw.frames_from_video(str(vp), max_frames=3)
    assert 1 <= len(frames2) <= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
