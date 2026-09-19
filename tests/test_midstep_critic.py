"""tests/test_midstep_critic.py — StageCritic 中途自评节点验收测试

验收目标（对应方案文档第六章）：
1. 正常渲染产物 → critic 判 continue，原子检查全过
2. 黑帧注入产物 → frame_luminance_ok 失败，裁决 retry/abort（S3→S4 边界拦截）
3. 静帧产物 → frame_temporal_variability_ok 失败（防静帧）
4. 节拍文件缺陷 → S2 边界拦截
5. CriticVerdict 可 JSON 序列化（manifest.critic_reports 落盘前提）

所有检测均用真实 FFmpeg 生成的视频做真跑验证，无 mock。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.midstep_critic import (  # noqa: E402
    CriticAbortError,
    CriticVerdict,
    StageCritic,
    ffprobe_duration,
    sample_frame_stats,
)

FFMPEG = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"

pytestmark = pytest.mark.skipif(
    not Path(FFMPEG).exists() and shutil.which("ffmpeg") is None,
    reason="ffmpeg 不可用",
)


@pytest.fixture(scope="module")
def fixture_dir(tmp_path_factory) -> Path:
    """真实生成三类测试视频：正常动画 / 全黑帧 / 恒定静帧。"""
    d = tmp_path_factory.mktemp("critic_fixtures")
    subprocess.run([
        FFMPEG, "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=8",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=8",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        str(d / "normal.mp4"),
    ], check=True, timeout=180)
    subprocess.run([
        FFMPEG, "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=black:size=640x360:rate=24:duration=8",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "black.mp4"),
    ], check=True, timeout=180)
    subprocess.run([
        FFMPEG, "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=0x80A0C0:size=640x360:rate=24:duration=8",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "static.mp4"),
    ], check=True, timeout=180)
    return d


# ---- 帧统计真跑 ------------------------------------------------------------

def test_ffprobe_duration_real(fixture_dir: Path) -> None:
    dur = ffprobe_duration(fixture_dir / "normal.mp4")
    assert 7.5 <= dur <= 8.5, f"时长解析异常: {dur}"


def test_sample_frame_stats_normal(fixture_dir: Path) -> None:
    yavg, fdiff = sample_frame_stats(fixture_dir / "normal.mp4")
    assert yavg > 20.0, f"正常视频 Y 均值应 >20，实际 {yavg}"
    assert fdiff > 1.0, f"正常视频帧间像素差分应 >1.0，实际 {fdiff}"


def test_sample_frame_stats_black(fixture_dir: Path) -> None:
    yavg, fdiff = sample_frame_stats(fixture_dir / "black.mp4")
    # H.264 纯黑编码实测 YAVG≈16，阈值 20 可拦截
    assert yavg <= 20.0, f"黑帧 Y 均值应 <=20，实际 {yavg}"


def test_sample_frame_stats_static(fixture_dir: Path) -> None:
    yavg, fdiff = sample_frame_stats(fixture_dir / "static.mp4")
    assert yavg > 20.0, f"静帧亮度充足，Y={yavg}"
    assert fdiff <= 1.0, f"静帧像素差分应 <=1.0，实际 {fdiff}"


# ---- S3→S4 边界裁决 ----------------------------------------------------------

def test_s3_normal_continue(fixture_dir: Path) -> None:
    critic = StageCritic()
    verdict = critic.evaluate(
        "S3", {"renders_list": [fixture_dir / "normal.mp4"]},
        {"min_render_duration": 5.0},
    )
    assert all(verdict.atomic_checks.values()), verdict.reasons
    assert verdict.decision == "continue"
    assert verdict.value_estimate >= 0.6


def test_s3_blackframe_intercepted(fixture_dir: Path) -> None:
    """核心验收：黑帧产物在 S3→S4 边界被拦截（retry 或 abort，绝不 continue）。"""
    critic = StageCritic(max_retry=0)  # retry 耗尽 → 直接 abort
    verdict = critic.evaluate("S3", {"renders_list": [fixture_dir / "black.mp4"]})
    assert verdict.atomic_checks["frame_luminance_ok"] is False
    assert verdict.decision == "abort"


def test_s3_static_frame_intercepted(fixture_dir: Path) -> None:
    critic = StageCritic()
    verdict = critic.evaluate("S3", {"renders_list": [fixture_dir / "static.mp4"]})
    assert verdict.atomic_checks["frame_temporal_variability_ok"] is False
    assert verdict.decision in ("retry", "abort")


def test_s3_retry_then_abort(fixture_dir: Path) -> None:
    """retry 限次机制：第一次 retry，第二次 abort。"""
    critic = StageCritic(max_retry=1)
    v1 = critic.evaluate("S3", {"renders_list": [fixture_dir / "black.mp4"]})
    v2 = critic.evaluate("S3", {"renders_list": [fixture_dir / "black.mp4"]})
    assert v1.decision == "retry"
    assert v2.decision == "abort"


# ---- S2→S3 边界裁决 ----------------------------------------------------------

def test_s2_valid_beats_continue(fixture_dir: Path) -> None:
    beats = fixture_dir / "beats.json"
    beats.write_text(json.dumps({"beats": [0.5, 1.0, 1.5, 2.0, 2.5]}), encoding="utf-8")
    critic = StageCritic()
    verdict = critic.evaluate(
        "S2",
        {"beats_json": beats, "audio": fixture_dir / "normal.mp4"},
        {"source_video_duration": 8.0},
    )
    assert verdict.atomic_checks["beats_file_valid"] is True
    assert verdict.atomic_checks["beat_count_sufficient"] is True
    assert verdict.decision == "continue"


def test_s2_empty_beats_retry(fixture_dir: Path) -> None:
    beats = fixture_dir / "beats_empty.json"
    beats.write_text(json.dumps({"beats": []}), encoding="utf-8")
    critic = StageCritic()
    verdict = critic.evaluate("S2", {"beats_json": beats})
    assert verdict.atomic_checks["beat_count_sufficient"] is False
    assert verdict.decision in ("retry", "abort")


# ---- 序列化与报告 ------------------------------------------------------------

def test_verdict_json_serializable(fixture_dir: Path) -> None:
    critic = StageCritic()
    critic.evaluate("S3", {"renders_list": [fixture_dir / "normal.mp4"]})
    reports = critic.export_reports()
    text = json.dumps(reports, ensure_ascii=False)
    parsed = json.loads(text)
    assert parsed[0]["stage"] == "S3"
    assert "atomic_checks" in parsed[0]
    assert "value_estimate" in parsed[0]


def test_verdict_dataclass_fields() -> None:
    v = CriticVerdict(stage="S3", value_estimate=0.8, decision="continue")
    assert v.alpha == 0.3
    assert v.atomic_checks == {}
