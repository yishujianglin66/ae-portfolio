# -*- coding: utf-8 -*-
"""core/otio_bridge.py 单元测试（P2-11 OTIO 时间线互换层）。

不依赖 Resolve/媒体文件：用构造 EDL + 假媒体路径（stream/duration 探针失败走保守
分支）锁定映射不变式。真实导入验证见 tmp/e2e_otio_resolve2.py（已 PASS）。
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import opentimelineio as otio  # noqa: E402

from core.otio_bridge import (  # noqa: E402
    edl_to_otio, otio_to_edl, roundtrip_check,
)

WORDS_EDL = {
    "schema_version": "1.1",
    "render": {"style": "word_cut", "theme": "t", "duration": 4.0, "fps": 30,
               "resolution": "1920x1080"},
    "inputs": [{"path": "vo.wav", "sha1": "x", "size_bytes": 1}],
    "cuts": [
        {"index": 0, "start_time": 0.0, "end_time": 1.0, "source_file": "vo.wav",
         "source_start": 0.0, "speed": 1.0, "transition": "cut", "mood": "m", "energy": 0},
        # vo 模式：0.5s 停顿 -> 应生成 Gap
        {"index": 1, "start_time": 1.5, "end_time": 3.0, "source_file": "vo.wav",
         "source_start": 1.5, "speed": 1.0, "transition": "cut", "mood": "m", "energy": 0},
    ],
    "cut_points": [0.0, 1.5],
    "text_events": [
        {"t_in": 0.1, "t_out": 0.4, "word": "你好", "style_id": "default"},
        {"t_in": 1.6, "t_out": 1.9, "word": "世界", "style_id": "default"},
    ],
    "effects": [{"effect_id": "e1", "effect_type": "bloom",
                 "time_range": {"t_in": 0.0, "t_out": 1.0}, "parameters": {}}],
    "overlays": [{"file": "logo.png", "start_in_output": 0.5, "duration": 1.0}],
}


def test_structure_mapping():
    tl = edl_to_otio(WORDS_EDL)
    assert tl.name == "t"
    names = [t.name for t in tl.tracks]
    assert "KV Video 1" in names and "KV Text" in names and "KV Overlay" in names
    vtrack = next(t for t in tl.tracks if t.name == "KV Video 1")
    # 2 clip + 1 gap（停顿）
    kinds = [type(i).__name__ for i in vtrack]
    assert kinds.count("Clip") == 2 and kinds.count("Gap") == 1
    # 文字 marker 数
    ttrack = next(t for t in tl.tracks if t.name == "KV Text")
    assert len(ttrack.markers) == 2
    # effect 挂载（time_range 命中 clip）
    clips = [i for i in vtrack if isinstance(i, otio.schema.Clip)]
    assert any(len(c.effects) > 0 for c in clips) or len(tl.effects) > 0


def test_speed_warp_mapping():
    edl = dict(WORDS_EDL)
    edl["cuts"] = [dict(WORDS_EDL["cuts"][0], speed=0.5)]
    edl["text_events"] = []
    tl = edl_to_otio(edl)
    clip = next(i for i in tl.tracks[0] if isinstance(i, otio.schema.Clip))
    warps = [e for e in clip.effects if isinstance(e, otio.schema.LinearTimeWarp)]
    assert len(warps) == 1 and abs(warps[0].time_warp_scale - 0.5) < 1e-6


def test_roundtrip_lossless_envelope():
    rep = roundtrip_check(WORDS_EDL)
    assert rep["verdict"] == "PASS", rep
    back = otio_to_edl(edl_to_otio(WORDS_EDL))
    assert back["cuts"][0]["mood"] == "m"          # kv_edl 信封字段完整保留
    assert back["render"]["fps"] == 30
    assert back["cut_points"] == [0.0, 1.5]


def test_third_party_inference_path():
    """无 kv 信封的第三方 OTIO timeline -> 标准推断出可用 EDL。"""
    tl = otio.schema.Timeline(name="foreign")
    trk = otio.schema.Track(name="V1", kind=otio.schema.TrackKind.Video)
    ref = otio.schema.ExternalReference(target_url="movie.mp4")
    from opentimelineio.opentime import RationalTime, TimeRange
    clip = otio.schema.Clip(name="c1", media_reference=ref,
                            source_range=TimeRange(RationalTime(0, 24), RationalTime(48, 24)))
    trk.append(clip)
    tl.tracks.append(trk)
    edl = otio_to_edl(tl)
    assert edl["schema_version"] == "1.1"
    assert edl["cuts"][0]["source_file"] == "movie.mp4"
    assert edl["cuts"][0]["end_time"] == 2.0  # 48 帧 @24fps
