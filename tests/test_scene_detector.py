"""tests/test_scene_detector.py - PySceneDetect 素材预处理测试

T5: PySceneDetect 接入素材预处理
- 镜头边界检测
- 镜头类型分类(静态/运动/快速切换)
- 素材结构摘要
"""
import shutil
import subprocess
from pathlib import Path

import pytest

HAS_FFMPEG = shutil.which("ffmpeg") is not None

try:
    from scenedetect import ContentDetector, detect
    HAS_SCENEDIRECT = True
except ImportError:
    HAS_SCENEDIRECT = False


@pytest.fixture(scope="module")
def multi_shot_video(tmp_path_factory) -> Path:
    """ffmpeg 合成 3 段不同亮度场景的测试视频(模拟 3 个镜头)"""
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")
    out = tmp_path_factory.mktemp("sd") / "multi_shot.mp4"
    # 3 段独立生成再 concat
    d = tmp_path_factory.mktemp("sd")
    segs = []
    for i, color in enumerate(["white", "black", "white"]):
        seg = d / f"seg_{i}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi",
             "-i", f"color=c={color}:size=320x240:rate=24:duration=1",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(seg)],
            check=True, timeout=120,
        )
        segs.append(str(seg))
    # 用 concat demuxer 拼接
    list_file = d / "concat.txt"
    list_file.write_text("\n".join(f"file '{s}'" for s in segs) + "\n", encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-f", "concat", "-safe", "0",
         "-i", str(list_file), "-c", "copy", str(out)],
        check=True, timeout=120,
    )
    return out


@pytest.fixture(scope="module")
def single_shot_video(tmp_path_factory) -> Path:
    """ffmpeg 合成单镜头测试视频(无场景切换)"""
    if not HAS_FFMPEG:
        pytest.skip("ffmpeg not available")
    out = tmp_path_factory.mktemp("sd") / "single_shot.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi",
         "-i", "testsrc2=size=320x240:rate=24:duration=3",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        check=True, timeout=120,
    )
    return out


def test_detect_shot_boundaries_multi_shot(multi_shot_video):
    """多镜头视频应检测到至少 2 个镜头边界"""
    from core.shot_detector import detect_shots
    shots = detect_shots(str(multi_shot_video), threshold=15.0)
    assert len(shots) >= 2, f"Expected >=2 shots, got {len(shots)}: {shots}"


def test_detect_shot_boundaries_single_shot(single_shot_video):
    """单镜头视频应只有 1 个镜头(无边界)"""
    from core.shot_detector import detect_shots
    shots = detect_shots(str(single_shot_video), threshold=15.0)
    assert len(shots) == 1, f"Expected 1 shot, got {len(shots)}: {shots}"


def test_shot_structure_has_start_end(multi_shot_video):
    """每个镜头必须有 start/end/duration"""
    from core.shot_detector import detect_shots
    shots = detect_shots(str(multi_shot_video), threshold=15.0)
    for s in shots:
        assert "start" in s and "end" in s and "duration" in s
        assert s["end"] > s["start"]
        assert abs(s["duration"] - (s["end"] - s["start"])) < 0.1


def test_material_summary(multi_shot_video):
    """素材结构摘要必须包含镜头数和总时长"""
    from core.shot_detector import material_summary
    summary = material_summary(str(multi_shot_video), threshold=15.0)
    assert summary["shot_count"] >= 2
    assert summary["total_duration"] > 0
    assert "avg_shot_duration" in summary


def test_missing_file():
    """不存在的文件应返回空列表而非崩溃"""
    from core.shot_detector import detect_shots
    shots = detect_shots("nonexistent_video.mp4")
    assert shots == []


def test_missing_file_summary():
    from core.shot_detector import material_summary
    s = material_summary("nonexistent_video.mp4")
    assert s["shot_count"] == 0
    assert s["total_duration"] == 0
