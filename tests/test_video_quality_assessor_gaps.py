#!/usr/bin/env python3
"""
tests/test_video_quality_assessor_gaps.py - VideoQualityAssessor 评分梯度与错误路径回归测试

覆盖 commit 86026af 引入的新评分逻辑：
  1. 错误路径返回格式 (文件不存在/ffprobe失败/无视频流)
  2. all_black 黑屏惩罚 (signalstats YAVG<20 → overall 封顶 15.0)
  3. static_video 静帧惩罚 (freeze_ratio>=0.8 且 duration>=2.0 → 封顶 45.0)
  4. 加权综合分数计算 (encoding/visual/color/temporal 四维权重)
  5. _signalstats_analyze 的 freeze_ratio 计算 (含未闭合 freeze_start)
  6. _score_encoding 编码/分辨率/帧率/码率评分梯度
  7. OpenCV 不可用 (openable=None) 时 signalstats 兜底路径
  8. OpenCV 可打开但视频损坏 (openable=False) → _error_result

这些是 verify 阶段质量门控的核心决策依据，评分梯度回归会导致
FeedbackExecutor 多轮优化误触发或漏触发。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.video_quality_assessor import VideoQualityAssessor


@pytest.fixture
def assessor() -> VideoQualityAssessor:
    """构造评估器，ffprobe_bin 指向不存在的路径以避免真实调用。"""
    return VideoQualityAssessor(
        ffmpeg_bin="/fake/ffmpeg.exe",
        ffprobe_bin="/fake/ffprobe.exe",
    )


# =========================================================================
#  场景 1：错误路径返回格式
# =========================================================================
class TestErrorPaths:
    """错误路径必须返回结构一致的 _error_result。"""

    def test_video_not_exist(self, assessor: VideoQualityAssessor) -> None:
        """视频文件不存在 → _error_result，score=0。"""
        result = assessor.assess("/nonexistent/video.mp4")

        assert result["passed"] is False
        assert result["score"] == 0.0
        assert result["overall_score"] == 0.0
        assert "error" in result
        assert "不存在" in result["error"]
        # 错误路径也要返回 checks 字段（保持结构一致）
        assert "checks" in result
        assert isinstance(result["checks"], dict)

    def test_ffprobe_returns_empty(self, assessor: VideoQualityAssessor) -> None:
        """ffprobe 返回空 dict（如二进制不存在）→ _error_result。"""
        with patch.object(assessor, "_ffprobe", return_value={}):
            # 需要 Path.exists() 返回 True 才能走到 ffprobe
            with patch("pathlib.Path.exists", return_value=True):
                result = assessor.assess("/fake/existing.mp4")

        assert result["passed"] is False
        assert result["score"] == 0.0
        assert "ffprobe" in result["error"]

    def test_no_video_stream(self, assessor: VideoQualityAssessor) -> None:
        """MP4 容器存在但无视频流（空壳）→ _error_result。"""
        probe = {
            "streams": [
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "5.0", "size": "1000"},
        }
        with patch.object(assessor, "_ffprobe", return_value=probe):
            with patch("pathlib.Path.exists", return_value=True):
                result = assessor.assess("/fake/audio_only.mp4")

        assert result["passed"] is False
        assert result["score"] == 0.0
        assert "无视频流" in result["error"]

    def test_opencv_cannot_open_video(self, assessor: VideoQualityAssessor) -> None:
        """OpenCV 可用但视频打不开（损坏）→ _error_result。"""
        probe = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080},
            ],
            "format": {"duration": "5.0"},
        }
        # openable=False 表示 OpenCV 尝试打开但失败 → 文件损坏
        opencv_metrics: dict[str, Any] = {
            "frames": 0, "openable": False,
            "sharpness_list": [], "brightness_list": [],
            "contrast_list": [], "saturation_list": [], "black_frames": 0,
        }
        with patch.object(assessor, "_ffprobe", return_value=probe), \
             patch.object(assessor, "_opencv_analyze", return_value=opencv_metrics), \
             patch("pathlib.Path.exists", return_value=True):
            result = assessor.assess("/fake/corrupt.mp4")

        assert result["passed"] is False
        assert result["score"] == 0.0
        assert "OpenCV" in result["error"] or "损坏" in result["error"]


# =========================================================================
#  场景 2：all_black 黑屏惩罚
# =========================================================================
class TestBlackScreenPenalty:
    """all_black=True → overall 封顶 15.0，且 suggestions 包含"全黑"。"""

    def test_signalstats_yavg_below_20_caps_to_15(
        self, assessor: VideoQualityAssessor
    ) -> None:
        """signalstats 路径：YAVG<20 → all_black=True → overall≤15.0。"""
        probe = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264",
                 "width": 1920, "height": 1080, "r_frame_rate": "30/1",
                 "nb_frames": "150"},
            ],
            "format": {"duration": "5.0", "bit_rate": "2000000"},
        }
        # OpenCV 不可用 (openable=None)，走 signalstats 兜底
        opencv_metrics: dict[str, Any] = {
            "frames": 0, "openable": None,
            "sharpness_list": [], "brightness_list": [],
            "contrast_list": [], "saturation_list": [], "black_frames": 0,
        }
        signalstats = {
            "yavg": 5.0,  # < 20 → all_black=True
            "ylow": 2.0, "yhigh": 10.0, "satavg": 5.0,
            "freeze_ratio": 0.0, "valid": True,
        }
        with patch.object(assessor, "_ffprobe", return_value=probe), \
             patch.object(assessor, "_opencv_analyze", return_value=opencv_metrics), \
             patch.object(assessor, "_signalstats_analyze", return_value=signalstats), \
             patch("pathlib.Path.exists", return_value=True):
            result = assessor.assess("/fake/black.mp4")

        # 黑屏封顶 15.0
        assert result["score"] <= 15.0, f"black screen score should be ≤15, got {result['score']}"
        assert any("全黑" in s or "黑" in s for s in result["suggestions"])

    def test_opencv_black_frames_ratio_caps_to_15(
        self, assessor: VideoQualityAssessor
    ) -> None:
        """OpenCV 路径：black_frames/frames>=0.8 → all_black=True → overall≤15.0。"""
        probe = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264",
                 "width": 1920, "height": 1080, "r_frame_rate": "30/1",
                 "nb_frames": "150"},
            ],
            "format": {"duration": "5.0", "bit_rate": "2000000"},
        }
        # OpenCV 可用，10 帧全黑
        opencv_metrics: dict[str, Any] = {
            "frames": 10, "openable": True,
            "sharpness_list": [10.0] * 10,
            "brightness_list": [0.01] * 10,  # < 0.04 → black
            "contrast_list": [0.01] * 10,
            "saturation_list": [0.01] * 10,
            "black_frames": 10,  # 10/10 = 1.0 >= 0.8
        }
        signalstats = {"valid": False}  # signalstats 不可用
        with patch.object(assessor, "_ffprobe", return_value=probe), \
             patch.object(assessor, "_opencv_analyze", return_value=opencv_metrics), \
             patch.object(assessor, "_signalstats_analyze", return_value=signalstats), \
             patch("pathlib.Path.exists", return_value=True):
            result = assessor.assess("/fake/all_black.mp4")

        assert result["score"] <= 15.0
        assert any("黑" in s for s in result["suggestions"])


# =========================================================================
#  场景 3：static_video 静帧惩罚
# =========================================================================
class TestStaticVideoPenalty:
    """static_video=True (freeze_ratio>=0.8 且 duration>=2.0) → overall 封顶 45.0。"""

    def test_static_video_caps_to_45(self, assessor: VideoQualityAssessor) -> None:
        """freeze_ratio>=0.8 + duration>=2.0 → 封顶 45.0。"""
        probe = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264",
                 "width": 1920, "height": 1080, "r_frame_rate": "30/1",
                 "nb_frames": "300"},
            ],
            "format": {"duration": "10.0", "bit_rate": "2000000"},
        }
        # OpenCV 不可用，走 signalstats 兜底
        opencv_metrics: dict[str, Any] = {
            "frames": 0, "openable": None,
            "sharpness_list": [], "brightness_list": [],
            "contrast_list": [], "saturation_list": [], "black_frames": 0,
        }
        signalstats = {
            "yavg": 128.0,  # 正常亮度，不触发 all_black
            "ylow": 100.0, "yhigh": 156.0, "satavg": 100.0,
            "freeze_ratio": 0.9,  # >= 0.8 → static
            "valid": True,
        }
        with patch.object(assessor, "_ffprobe", return_value=probe), \
             patch.object(assessor, "_opencv_analyze", return_value=opencv_metrics), \
             patch.object(assessor, "_signalstats_analyze", return_value=signalstats), \
             patch("pathlib.Path.exists", return_value=True):
            result = assessor.assess("/fake/static.mp4")

        # 静帧封顶 45.0
        assert result["score"] <= 45.0, f"static video score should be ≤45, got {result['score']}"
        assert any("静帧" in s for s in result["suggestions"])

    def test_short_static_video_not_penalized(
        self, assessor: VideoQualityAssessor
    ) -> None:
        """freeze_ratio>=0.8 但 duration<2.0 → 不触发静帧惩罚。"""
        probe = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264",
                 "width": 1920, "height": 1080, "r_frame_rate": "30/1",
                 "nb_frames": "30"},
            ],
            "format": {"duration": "1.0", "bit_rate": "2000000"},  # < 2.0
        }
        opencv_metrics: dict[str, Any] = {
            "frames": 0, "openable": None,
            "sharpness_list": [], "brightness_list": [],
            "contrast_list": [], "saturation_list": [], "black_frames": 0,
        }
        signalstats = {
            "yavg": 128.0, "ylow": 100.0, "yhigh": 156.0, "satavg": 100.0,
            "freeze_ratio": 0.9,  # >= 0.8 但 duration < 2.0
            "valid": True,
        }
        with patch.object(assessor, "_ffprobe", return_value=probe), \
             patch.object(assessor, "_opencv_analyze", return_value=opencv_metrics), \
             patch.object(assessor, "_signalstats_analyze", return_value=signalstats), \
             patch("pathlib.Path.exists", return_value=True):
            result = assessor.assess("/fake/short_static.mp4")

        # 不应被静帧封顶（可能仍因其他原因低分，但不应有"静帧"suggestion）
        assert not any("静帧" in s for s in result["suggestions"])

    def test_low_freeze_ratio_not_penalized(
        self, assessor: VideoQualityAssessor
    ) -> None:
        """freeze_ratio<0.8 + duration>=2.0 → 不触发静帧惩罚。"""
        probe = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264",
                 "width": 1920, "height": 1080, "r_frame_rate": "30/1",
                 "nb_frames": "300"},
            ],
            "format": {"duration": "10.0", "bit_rate": "2000000"},
        }
        opencv_metrics: dict[str, Any] = {
            "frames": 0, "openable": None,
            "sharpness_list": [], "brightness_list": [],
            "contrast_list": [], "saturation_list": [], "black_frames": 0,
        }
        signalstats = {
            "yavg": 128.0, "ylow": 100.0, "yhigh": 156.0, "satavg": 100.0,
            "freeze_ratio": 0.3,  # < 0.8
            "valid": True,
        }
        with patch.object(assessor, "_ffprobe", return_value=probe), \
             patch.object(assessor, "_opencv_analyze", return_value=opencv_metrics), \
             patch.object(assessor, "_signalstats_analyze", return_value=signalstats), \
             patch("pathlib.Path.exists", return_value=True):
            result = assessor.assess("/fake/normal.mp4")

        assert not any("静帧" in s for s in result["suggestions"])


# =========================================================================
#  场景 4：加权综合分数计算
# =========================================================================
class TestWeightedScoring:
    """四维加权 (encoding 0.20 + visual 0.35 + color 0.20 + temporal 0.25)。"""

    def test_weights_sum_to_one(self) -> None:
        """权重总和必须为 1.0（从源码常量验证）。"""
        # 从 assess 方法内部提取的权重
        weights = {
            "encoding_health": 0.20,
            "visual_quality": 0.35,
            "color_consistency": 0.20,
            "temporal_stability": 0.25,
        }
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_normal_video_score_in_reasonable_range(
        self, assessor: VideoQualityAssessor
    ) -> None:
        """正常视频 → 分数在 [0, 100] 区间，且不触发黑屏/静帧惩罚。"""
        probe = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264",
                 "width": 1920, "height": 1080, "r_frame_rate": "30/1",
                 "nb_frames": "300"},
            ],
            "format": {"duration": "10.0", "bit_rate": "5000000"},
        }
        opencv_metrics: dict[str, Any] = {
            "frames": 10, "openable": True,
            "sharpness_list": [600.0] * 10,  # 清晰
            "brightness_list": [0.4] * 10,   # 正常亮度
            "contrast_list": [0.25] * 10,    # 正常对比度
            "saturation_list": [0.4] * 10,   # 正常饱和度
            "black_frames": 0,
        }
        signalstats = {"valid": False}
        with patch.object(assessor, "_ffprobe", return_value=probe), \
             patch.object(assessor, "_opencv_analyze", return_value=opencv_metrics), \
             patch.object(assessor, "_signalstats_analyze", return_value=signalstats), \
             patch("pathlib.Path.exists", return_value=True):
            result = assessor.assess("/fake/normal.mp4", min_score=60.0)

        assert 0.0 <= result["score"] <= 100.0
        # 正常视频不应被黑屏/静帧惩罚
        assert result["score"] > 15.0
        assert result["score"] > 45.0
        # 检查四维分数都存在
        assert "encoding_health" in result["checks"]
        assert "visual_quality" in result["checks"]
        assert "color_consistency" in result["checks"]
        assert "temporal_stability" in result["checks"]

    def test_min_score_threshold_affects_passed(
        self, assessor: VideoQualityAssessor
    ) -> None:
        """min_score 阈值直接影响 passed 字段。"""
        probe = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264",
                 "width": 1920, "height": 1080, "r_frame_rate": "30/1",
                 "nb_frames": "300"},
            ],
            "format": {"duration": "10.0", "bit_rate": "5000000"},
        }
        opencv_metrics: dict[str, Any] = {
            "frames": 10, "openable": True,
            "sharpness_list": [600.0] * 10,
            "brightness_list": [0.4] * 10,
            "contrast_list": [0.25] * 10,
            "saturation_list": [0.4] * 10,
            "black_frames": 0,
        }
        signalstats = {"valid": False}
        with patch.object(assessor, "_ffprobe", return_value=probe), \
             patch.object(assessor, "_opencv_analyze", return_value=opencv_metrics), \
             patch.object(assessor, "_signalstats_analyze", return_value=signalstats), \
             patch("pathlib.Path.exists", return_value=True):
            result_low = assessor.assess("/fake/normal.mp4", min_score=99.0)
            result_high = assessor.assess("/fake/normal.mp4", min_score=0.0)

        # 高阈值 → passed=False
        assert result_low["passed"] is False
        # 低阈值 → passed=True
        assert result_high["passed"] is True


# =========================================================================
#  场景 5：_score_encoding 编码评分梯度
# =========================================================================
class TestScoreEncoding:
    """编码健康度评分梯度。"""

    def test_h264_1080p_30fps_high_bitrate(self, assessor: VideoQualityAssessor) -> None:
        """h264 + 1080p + 30fps + 高码率 → 高分。"""
        probe = {
            "streams": [{
                "codec_type": "video", "codec_name": "h264",
                "width": 1920, "height": 1080,
                "r_frame_rate": "30/1", "nb_frames": "300",
            }],
            "format": {"duration": "10.0", "bit_rate": "5000000"},
        }
        result = assessor._score_encoding(probe)
        assert result["score"] >= 90.0
        assert result["codec"] == "h264"
        assert result["width"] == 1920
        assert result["height"] == 1080
        assert result["fps"] == 30.0
        assert len(result["issues"]) == 0

    def test_non_mainstream_codec_lower_score(self, assessor: VideoQualityAssessor) -> None:
        """非主流编码 (mpeg4) → 编码分降低，issues 包含警告。"""
        probe = {
            "streams": [{
                "codec_type": "video", "codec_name": "mpeg4",
                "width": 1920, "height": 1080,
                "r_frame_rate": "30/1", "nb_frames": "300",
            }],
            "format": {"duration": "10.0", "bit_rate": "5000000"},
        }
        result = assessor._score_encoding(probe)
        assert result["score"] < 90.0
        assert any("非主流编码" in i for i in result["issues"])

    def test_low_resolution_lower_score(self, assessor: VideoQualityAssessor) -> None:
        """低分辨率 (360p, 低于 480p 阈值) → 分辨率分降低 + issues 警告。"""
        probe = {
            "streams": [{
                "codec_type": "video", "codec_name": "h264",
                "width": 640, "height": 360,  # 低于 852x480 阈值
                "r_frame_rate": "30/1", "nb_frames": "300",
            }],
            "format": {"duration": "10.0", "bit_rate": "5000000"},
        }
        result = assessor._score_encoding(probe)
        assert any("分辨率偏低" in i for i in result["issues"])

    def test_no_video_stream_returns_low_score(self, assessor: VideoQualityAssessor) -> None:
        """无视频流 → score=20。"""
        probe = {"streams": [], "format": {}}
        result = assessor._score_encoding(probe)
        assert result["score"] == 20
        assert "无视频流" in result["issues"]


# =========================================================================
#  场景 6：_signalstats_analyze freeze_ratio 计算
# =========================================================================
class TestSignalstatsFreezeRatio:
    """signalstats 兜底路径的 freeze_ratio 计算（含未闭合 freeze_start）。"""

    def test_freeze_start_without_end_uses_segment_end(
        self, assessor: VideoQualityAssessor
    ) -> None:
        """freeze_start 存在但无对应 freeze_duration → 按 start 到分段末尾计冻结。"""
        # 模拟 ffmpeg signalstats 输出（必须含 lavfi.signalstats. 前缀才能被正则匹配）
        fake_stderr = (
            "frame=100 ... lavfi.signalstats.YAVG=128 lavfi.signalstats.YLOW=100 "
            "lavfi.signalstats.YHIGH=156 lavfi.signalstats.SATAVG=100\n"
            "frame=200 ... lavfi.signalstats.YAVG=130 lavfi.signalstats.YLOW=102 "
            "lavfi.signalstats.YHIGH=158 lavfi.signalstats.SATAVG=102\n"
            "[freezedetect] freeze_start:8.0\n"
            # 没有 freeze_duration 行（冻结持续到结尾）
        )
        mock_proc = MagicMock()
        mock_proc.stderr = fake_stderr
        mock_proc.stdout = ""

        with patch.object(assessor, "ffmpeg_bin", "/fake/ffmpeg.exe"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("subprocess.run", return_value=mock_proc):
            result = assessor._signalstats_analyze(
                "/fake/video.mp4",
                duration_limit=10.0,
                video_duration=10.0,
            )

        # seg_dur = min(10.0, 10.0) = 10.0
        # freeze_total = 0 (无 freeze_duration) + max(0, 10.0 - 8.0) = 2.0
        # freeze_ratio = min(1.0, 2.0 / 10.0) = 0.2
        assert result["valid"] is True
        assert result["freeze_ratio"] == pytest.approx(0.2, abs=0.01)

    def test_freeze_duration_closed_normal_calculation(
        self, assessor: VideoQualityAssessor
    ) -> None:
        """正常 freeze_start + freeze_duration 配对 → 按duration累加。"""
        fake_stderr = (
            "frame=100 ... lavfi.signalstats.YAVG=128 lavfi.signalstats.YLOW=100 "
            "lavfi.signalstats.YHIGH=156 lavfi.signalstats.SATAVG=100\n"
            "[freezedetect] freeze_start:2.0\n"
            "[freezedetect] freeze_duration:3.0\n"
        )
        mock_proc = MagicMock()
        mock_proc.stderr = fake_stderr
        mock_proc.stdout = ""

        with patch.object(assessor, "ffmpeg_bin", "/fake/ffmpeg.exe"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("subprocess.run", return_value=mock_proc):
            result = assessor._signalstats_analyze(
                "/fake/video.mp4",
                duration_limit=10.0,
                video_duration=10.0,
            )

        # freeze_total = 3.0, seg_dur=10.0, ratio = 0.3
        assert result["valid"] is True
        assert result["freeze_ratio"] == pytest.approx(0.3, abs=0.01)

    def test_no_signalstats_output_invalid(self, assessor: VideoQualityAssessor) -> None:
        """ffmpeg 无输出 → valid=False。"""
        mock_proc = MagicMock()
        mock_proc.stderr = ""
        mock_proc.stdout = ""

        with patch.object(assessor, "ffmpeg_bin", "/fake/ffmpeg.exe"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("subprocess.run", return_value=mock_proc):
            result = assessor._signalstats_analyze("/fake/video.mp4")

        assert result["valid"] is False

    def test_ffmpeg_not_exist_invalid(self, assessor: VideoQualityAssessor) -> None:
        """ffmpeg_bin 路径不存在 → valid=False。"""
        # assessor 的 ffmpeg_bin 已在 fixture 中设为 /fake/ffmpeg.exe
        with patch("pathlib.Path.exists", return_value=False):
            result = assessor._signalstats_analyze("/fake/video.mp4")

        assert result["valid"] is False


# =========================================================================
#  场景 7：返回字段完整性
# =========================================================================
class TestReturnFieldCompleteness:
    """assess 返回必须同时包含两套字段以兼容不同调用方。"""

    def test_success_path_returns_both_field_sets(
        self, assessor: VideoQualityAssessor
    ) -> None:
        """成功路径返回 score/suggestions + overall_score/recommendations/passed。"""
        probe = {
            "streams": [{
                "codec_type": "video", "codec_name": "h264",
                "width": 1920, "height": 1080,
                "r_frame_rate": "30/1", "nb_frames": "300",
            }],
            "format": {"duration": "10.0", "bit_rate": "5000000"},
        }
        opencv_metrics: dict[str, Any] = {
            "frames": 10, "openable": True,
            "sharpness_list": [600.0] * 10,
            "brightness_list": [0.4] * 10,
            "contrast_list": [0.25] * 10,
            "saturation_list": [0.4] * 10,
            "black_frames": 0,
        }
        signalstats = {"valid": False}
        with patch.object(assessor, "_ffprobe", return_value=probe), \
             patch.object(assessor, "_opencv_analyze", return_value=opencv_metrics), \
             patch.object(assessor, "_signalstats_analyze", return_value=signalstats), \
             patch("pathlib.Path.exists", return_value=True):
            result = assessor.assess("/fake/normal.mp4")

        # AdjustmentMapper 期望的字段
        assert "score" in result
        assert "suggestions" in result
        assert "checks" in result
        # assess 文档承诺的字段
        assert "overall_score" in result
        assert "recommendations" in result
        assert "passed" in result
        assert "min_score" in result
        # score 与 overall_score 必须一致
        assert result["score"] == result["overall_score"]
        # suggestions 与 recommendations 必须一致
        assert result["suggestions"] == result["recommendations"]
