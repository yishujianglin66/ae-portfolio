"""test_global_source_dedup.py — 全局同片段去重 + 单文件占比封顶 回归测试。

对应修复 (2026-09-04 洛天依/同源重复缺陷): 引擎 source 选择只防相邻同源,
不防全局同片段复用; 且单源文件占比失控 (独自升级5 曾达 30.2%)。
见 docs/handoff-2026-09-04-v6-full-sync.md §3 与 ai/production_director.py
的 _enforce_global_source_uniqueness。
"""

import types

import pytest

from ai.production_director import ProductionDirector


def _make_obj(durations):
    obj = ProductionDirector.__new__(ProductionDirector)
    obj._source_durations = dict(durations)
    return obj


def _seg(source_file, source_start, duration=0.25):
    return types.SimpleNamespace(
        source_file=source_file, source_start=float(source_start),
        duration=float(duration),
    )


def _clusters(segs, gap=0.5):
    """按 (同文件, source_start 相距<=gap) 聚类, 返回复用簇数。"""
    from collections import defaultdict
    by = defaultdict(list)
    for s in segs:
        by[s.source_file].append(float(s.source_start))
    n = 0
    for pts in by.values():
        pts = sorted(pts)
        run = 1
        for i in range(1, len(pts)):
            if pts[i] - pts[i - 1] <= gap:
                run += 1
            else:
                if run > 1:
                    n += 1
                run = 1
        if run > 1:
            n += 1
    return n


class TestGlobalSourceDedup:
    def test_dedups_same_file_same_start(self):
        obj = _make_obj({"A.mp4": 60.0, "B.mp4": 60.0})
        segs = [_seg("A.mp4", 2.0), _seg("A.mp4", 2.0), _seg("A.mp4", 2.0)]
        obj._enforce_global_source_uniqueness(segs)
        assert _clusters(segs) == 0
        assert len(segs) == 3
        assert all(s.duration == 0.25 for s in segs)

    def test_caps_per_file_share(self):
        # 20 镜, max_share=0.25 → 每文件封顶 5 镜; A.mp4 独占 12 镜应被拆到 B/C/D
        obj = _make_obj({"A.mp4": 60.0, "B.mp4": 60.0, "C.mp4": 60.0, "D.mp4": 60.0})
        segs = [_seg("A.mp4", k * 2.0) for k in range(12)] + \
               [_seg("B.mp4", k * 2.0) for k in range(8)]
        obj._enforce_global_source_uniqueness(segs, max_share=0.25)
        from collections import Counter
        cnt = Counter(s.source_file for s in segs)
        assert len(segs) == 20
        assert max(cnt.values()) <= 5, dict(cnt)
        assert _clusters(segs) == 0

    def test_preserves_count_and_duration(self):
        obj = _make_obj({"A.mp4": 60.0})
        segs = [_seg("A.mp4", 1.0, 0.3), _seg("A.mp4", 1.1, 0.3),
                _seg("A.mp4", 30.0, 0.3)]
        before = [(s.source_start, s.duration) for s in segs]
        obj._enforce_global_source_uniqueness(segs)
        assert len(segs) == 3
        assert [s.duration for s in segs] == [b[1] for b in before]

    def test_empty_and_single_noop(self):
        obj = _make_obj({"A.mp4": 60.0})
        assert obj._enforce_global_source_uniqueness([]) == []
        one = [_seg("A.mp4", 5.0)]
        obj._enforce_global_source_uniqueness(one)
        assert one[0].source_start == 5.0

    def test_swap_falls_back_within_file_when_pool_exhausted(self):
        # 单一源也要能正常跑完 (换源无候选 → 兜底同文件硬找), 不崩溃不重复
        obj = _make_obj({"A.mp4": 10.0})
        segs = [_seg("A.mp4", 1.0), _seg("A.mp4", 1.0), _seg("A.mp4", 1.0)]
        obj._enforce_global_source_uniqueness(segs)
        assert len(segs) == 3
        assert _clusters(segs) == 0


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))