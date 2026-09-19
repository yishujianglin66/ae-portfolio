"""Tests for scripts.check_delivery_spec — 交付规格自检（AKROSS Con 口径）

覆盖：
  1. 位深解析（pix_fmt → bit depth）
  2. 帧率解析（分数字符串）
  3. 路径安全校验（存在性 / 后缀白名单 / 目录）
  4. Report 状态优先级
  5. 端到端：ffmpeg 合成夹具 → 完整检查链路（真实解码，非 mock）
  6. JSON 报告可序列化

夹具生成沿用 tests/test_frame_sampler.py 的写法（参数列表，无 shell 拼接）。
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / "scripts"))

from check_delivery_spec import (  # noqa: E402
    SPEC,
    Check,
    Report,
    bit_depth_of,
    check_one,
    parse_fps,
    safe_media_path,
)

HAS_FFMPEG = shutil.which("ffmpeg") is not None


# ── 纯逻辑 ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pix_fmt,expected", [
    ("yuv420p", 8), ("yuvj420p", 8), ("yuv444p", 8),
    ("yuv420p10le", 10), ("yuv422p10le", 10), ("yuv420p12le", 12),
    ("gray", 8), ("", None), (None, None),
])
def test_bit_depth_of(pix_fmt, expected):
    assert bit_depth_of(pix_fmt) == expected


@pytest.mark.parametrize("s,expected", [
    ("24/1", 24.0), ("30/1", 30.0),
    ("24000/1001", pytest.approx(23.976, abs=1e-3)),
    ("0/0", 0.0), ("", 0.0), ("garbage", 0.0),
])
def test_parse_fps(s, expected):
    assert parse_fps(s) == expected


def test_safe_media_path_rejects_missing():
    assert safe_media_path("does/not/exist.mp4") is None


def test_safe_media_path_rejects_bad_suffix(tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("x", encoding="utf-8")
    assert safe_media_path(f) is None


def test_safe_media_path_rejects_directory(tmp_path):
    d = tmp_path / "adir.mp4"
    d.mkdir()
    assert safe_media_path(d) is None


def test_safe_media_path_accepts_media(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"\x00" * 16)
    got = safe_media_path(f)
    assert got is not None and got.name == "clip.mp4"


def test_report_status_precedence():
    r = Report(path="x")
    r.checks = [Check("a", "PASS", ""), Check("b", "WARN", "")]
    assert r.status == "WARN"
    r.checks.append(Check("c", "FAIL", ""))
    assert r.status == "FAIL"


# ── 端到端（真实 ffmpeg 夹具） ─────────────────────────────────────────

@pytest.fixture(scope="module")
def fixture_video(tmp_path_factory) -> Path:
    """ffmpeg 合成 6s / 24fps / 8bit h264+aac 夹具（真实解码对象）。"""
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")
    out = tmp_path_factory.mktemp("spec") / "fixture.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi",
         "-i", "testsrc2=size=320x240:rate=24:duration=6",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(out)],
        check=True, timeout=120,
    )
    return out


def test_end_to_end_probe(fixture_video):
    rep = check_one(fixture_video, SPEC)
    p = rep.probe
    assert p["vcodec"] == "h264"
    assert p["acodec"] == "aac"
    assert p["width"] == 320 and p["height"] == 240
    assert p["bit_depth"] == 8
    assert p["fps"] == pytest.approx(24.0, abs=0.1)
    assert p["duration_sec"] == pytest.approx(6.0, abs=0.5)


def test_end_to_end_check_names(fixture_video):
    rep = check_one(fixture_video, SPEC)
    names = [c.name for c in rep.checks]
    for expect in ("容器/编码", "帧率", "位深", "码率", "时长", "音频"):
        assert expect in names


def test_end_to_end_fps_pass(fixture_video):
    """24fps 夹具应通过 ≤30fps 闸门。"""
    rep = check_one(fixture_video, SPEC)
    assert next(c for c in rep.checks if c.name == "帧率").status == "PASS"


def test_end_to_end_duration_warn_for_short(fixture_video):
    """6s 夹具低于 AKROSS 1 分钟下限 → 时长 WARN。"""
    rep = check_one(fixture_video, SPEC)
    assert next(c for c in rep.checks if c.name == "时长").status == "WARN"


def test_end_to_end_bitdepth_pass(fixture_video):
    rep = check_one(fixture_video, SPEC)
    d = next(c for c in rep.checks if c.name == "位深")
    assert d.status == "PASS" and d.value == 8


def test_end_to_end_container_pass(fixture_video):
    """h264+aac in mp4 应通过容器/编码闸门。"""
    rep = check_one(fixture_video, SPEC)
    assert next(c for c in rep.checks if c.name == "容器/编码").status == "PASS"


def test_json_serialisable(fixture_video):
    rep = check_one(fixture_video, SPEC)
    payload = {"spec": SPEC, "results": [rep.as_dict()]}
    back = json.loads(json.dumps(payload, ensure_ascii=False))
    assert back["results"][0]["status"] in ("PASS", "WARN", "FAIL")
    assert isinstance(back["results"][0]["checks"], list)


def test_watermark_metrics_shape(fixture_video):
    """台标检测应返回结论；testsrc2 为合成图案，不强制其判定结果。"""
    rep = check_one(fixture_video, SPEC)
    wm = next(c for c in rep.checks if "台标" in c.name)
    assert wm.status in ("PASS", "WARN")
