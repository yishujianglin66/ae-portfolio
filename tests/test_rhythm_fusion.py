"""tests/test_rhythm_fusion.py — 双节拍网格调和测试 (纯计算, 无模型)"""
from __future__ import annotations

import pytest


class FakeGrid:
    def __init__(self, beats, numbers, tempo):
        self.beats = beats
        self.beat_numbers = numbers
        self.tempo = tempo


def _grid_120_4_4():
    """120BPM 4/4: 拍 0.0/0.5/1.0/1.5/2.0..., 编号 1/2/3/4 循环。"""
    beats = [i * 0.5 for i in range(17)]
    numbers = [(i % 4) + 1 for i in range(17)]
    return FakeGrid(beats, numbers, 120.0)


class TestFusion:
    def test_perfect_alignment(self):
        from models.beat.rhythm_fusion import fuse_beatgrids
        grid = _grid_120_4_4()
        project = [i * 0.5 for i in range(16)]
        f = fuse_beatgrids(project, grid)
        assert f.n_aligned == 16
        assert f.alignment_rate == 1.0
        assert f.tempo_consistent is True
        assert abs(f.tempo_project - 120.0) < 0.5
        assert len(f.downbeat_times) == 4  # 16 拍 = 4 小节

    def test_tempo_mismatch_detected(self):
        from models.beat.rhythm_fusion import fuse_beatgrids
        grid = _grid_120_4_4()
        # 项目拍 100BPM (0.6s 间隔) → tempo 不一致
        project = [i * 0.6 for i in range(16)]
        f = fuse_beatgrids(project, grid)
        assert f.tempo_consistent is False
        assert f.tempo_delta > 0.08
        # 对齐率应显著 < 1 (两网格错位)
        assert f.alignment_rate < 0.5

    def test_partial_alignment(self):
        from models.beat.rhythm_fusion import fuse_beatgrids
        grid = _grid_120_4_4()
        # 一半对齐, 一半偏移 0.2s (超出容差)
        project = [i * 0.5 if i % 2 == 0 else i * 0.5 + 0.2
                   for i in range(16)]
        f = fuse_beatgrids(project, grid)
        assert f.n_aligned == 8
        assert f.alignment_rate == 0.5

    def test_downbeat_inheritance(self):
        from models.beat.rhythm_fusion import fuse_beatgrids
        grid = _grid_120_4_4()
        project = [0.0, 0.5, 1.0, 1.5, 2.0]
        f = fuse_beatgrids(project, grid)
        assert f.fused_beats[0]["is_downbeat"] is True    # 第 1 拍
        assert f.fused_beats[1]["is_downbeat"] is False
        assert f.fused_beats[4]["is_downbeat"] is True    # 第 5 拍 = 新小节
        assert f.fused_beats[0]["beat_number"] == 1

    def test_empty_inputs(self):
        from models.beat.rhythm_fusion import fuse_beatgrids
        f = fuse_beatgrids([], FakeGrid([], [], 0.0))
        assert f.alignment_rate == 0.0
        assert f.tempo_consistent is False
        assert f.fused_beats == []

    def test_to_dict(self):
        from models.beat.rhythm_fusion import fuse_beatgrids
        f = fuse_beatgrids([0.0, 0.5], _grid_120_4_4())
        d = f.to_dict()
        assert d["tempo_consistent"] is True
        assert d["n_downbeats"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])
