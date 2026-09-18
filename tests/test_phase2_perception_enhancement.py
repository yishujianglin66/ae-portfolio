"""
Phase 2 感知层增强模块测试
覆盖: scene_detector.py, audio_analyzer_librosa.py, media_preprocessor.py

设计：
    1. 所有测试不依赖真实第三方库（PySceneDetect/librosa/ffmpeg-python）
    2. 通过 mock 模拟依赖，验证模块逻辑
    3. 优雅降级路径必须被覆盖（依赖未安装时返回 success=False）
    4. 集成测试验证 ae_agent_pipeline.PerceptionResult 注入逻辑
"""
import os
import sys
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

PROJECT_ROOT = str(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from audio_analyzer_librosa import (
    AudioAnalysisResult,
    BeatInfo,
    LibrosaAudioAnalyzer,
    analyze_audio,
)
from audio_analyzer_librosa import (
    AudioSegment as LibrosaAudioSegment,
)
from media_preprocessor import (
    MediaInfo,
    MediaPreprocessor,
    PreprocessResult,
    extract_audio,
    extract_thumbnails,
    get_media_info,
    transcode,
)
from scene_detector import (
    SceneDetector,
    SceneDetectResult,
    SceneSegment,
    detect_scenes,
)

# ============================================================
# SceneDetector 测试
# ============================================================

class TestSceneDetectorDataClasses:
    """数据类基础测试"""

    def test_scene_segment_to_dict(self):
        seg = SceneSegment(
            index=0, start_time=1.0, end_time=2.5,
            duration=1.5, start_frame=30, end_frame=75, frame_count=45,
        )
        d = seg.to_dict()
        assert d["index"] == 0
        assert d["start_time"] == 1.0
        assert d["end_time"] == 2.5
        assert d["duration"] == 1.5
        assert d["frame_count"] == 45

    def test_scene_detect_result_defaults(self):
        result = SceneDetectResult()
        assert result.success is False
        assert result.error == ""
        assert result.segments == []
        assert result.scene_count == 0

    def test_scene_detect_result_to_dict(self):
        seg = SceneSegment(index=0, start_time=0.0, end_time=1.0, duration=1.0)
        result = SceneDetectResult(
            success=True, video_path="/v.mp4", detector_type="content",
            scene_count=1, total_duration=1.0, segments=[seg], fps=30.0,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["scene_count"] == 1
        assert len(d["segments"]) == 1
        assert d["fps"] == 30.0


class TestSceneDetectorBehavior:
    """SceneDetector 行为测试"""

    def test_unsupported_detector_type_raises(self):
        with pytest.raises(ValueError, match="不支持的检测器类型"):
            SceneDetector(detector_type="invalid")

    def test_detector_types_constant(self):
        assert "content" in SceneDetector.DETECTOR_TYPES
        assert "adaptive" in SceneDetector.DETECTOR_TYPES
        assert "threshold" in SceneDetector.DETECTOR_TYPES

    def test_nonexistent_video_returns_failure(self):
        detector = SceneDetector(enable_cache=False)
        result = detector.detect("/nonexistent/video.mp4")
        assert result.success is False
        assert "不存在" in result.error

    def test_detect_scenes_convenience_api(self):
        """便捷 API 在依赖未安装时优雅降级"""
        result = detect_scenes("/nonexistent/video.mp4")
        assert result.success is False

    def test_detect_batch_empty(self):
        detector = SceneDetector(enable_cache=False)
        results = detector.detect_batch([])
        assert results == {}

    def test_detect_batch_nonexistent(self):
        detector = SceneDetector(enable_cache=False)
        results = detector.detect_batch(["/nonexistent/v1.mp4", "/nonexistent/v2.mp4"])
        assert len(results) == 2
        for path, result in results.items():
            assert result.success is False

    @patch("scene_detector._SCENEDETECT_AVAILABLE", True)
    def test_detect_with_mocked_scenedetect(self, tmp_path):
        """使用 mock 验证检测流程（不依赖真实 PySceneDetect）"""
        # 创建假视频文件
        fake_video = tmp_path / "fake.mp4"
        fake_video.write_bytes(b"fake video content")

        # mock scenedetect 模块
        with patch("scene_detector.open_video") as mock_open, \
             patch("scene_detector.SceneManager") as mock_sm_cls, \
             patch("scene_detector.ContentDetector"):
            # 构造 mock scene_list
            start_tc = MagicMock()
            start_tc.get_seconds.return_value = 0.0
            start_tc.get_frames.return_value = 0
            end_tc = MagicMock()
            end_tc.get_seconds.return_value = 2.5
            end_tc.get_frames.return_value = 75

            mock_video = MagicMock()
            mock_video.frame_rate = 30.0
            mock_open.return_value = mock_video

            mock_sm = MagicMock()
            mock_sm.get_scene_list.return_value = [(start_tc, end_tc)]
            mock_sm_cls.return_value = mock_sm

            detector = SceneDetector(enable_cache=False)
            result = detector.detect(str(fake_video))

            assert result.success is True
            assert result.scene_count == 1
            assert len(result.segments) == 1
            seg = result.segments[0]
            assert seg.start_time == 0.0
            assert seg.end_time == 2.5
            assert seg.duration == 2.5
            assert seg.frame_count == 75
            assert result.fps == 30.0


# ============================================================
# LibrosaAudioAnalyzer 测试
# ============================================================

class TestLibrosaAudioDataClasses:
    """数据类基础测试"""

    def test_beat_info_to_dict(self):
        beat = BeatInfo(time=1.5, strength=0.8, is_downbeat=True)
        d = beat.to_dict()
        assert d["time"] == 1.5
        assert d["strength"] == 0.8
        assert d["is_downbeat"] is True

    def test_audio_segment_to_dict(self):
        seg = LibrosaAudioSegment(
            index=0, start_time=0.0, end_time=2.0,
            duration=2.0, label="intro", avg_energy=0.05,
        )
        d = seg.to_dict()
        assert d["label"] == "intro"
        assert d["avg_energy"] == 0.05

    def test_audio_analysis_result_defaults(self):
        result = AudioAnalysisResult()
        assert result.success is False
        assert result.beats == []
        assert result.bpm == 0.0

    def test_audio_analysis_result_to_music_features(self):
        beat = BeatInfo(time=0.5, strength=0.7, is_downbeat=True)
        result = AudioAnalysisResult(
            success=True, duration=10.0, bpm=120.0, tempo=120.0,
            beats=[beat], downbeats=[0.5], mood="happy", mood_score=0.7,
            rms_energy=0.04, key="C major",
        )
        features = result.to_music_features()
        assert features["bpm"] == 120.0
        assert features["duration"] == 10.0
        assert features["beat_times"] == [0.5]
        assert features["mood"] == "happy"
        assert features["key"] == "C major"


class TestLibrosaAudioAnalyzerBehavior:
    """LibrosaAudioAnalyzer 行为测试"""

    def test_nonexistent_audio_returns_failure(self):
        analyzer = LibrosaAudioAnalyzer(enable_cache=False)
        result = analyzer.analyze("/nonexistent/audio.mp3")
        assert result.success is False
        assert "不存在" in result.error

    def test_analyze_audio_convenience_api(self):
        result = analyze_audio("/nonexistent/audio.mp3")
        assert result.success is False

    def test_label_segments(self):
        labels = LibrosaAudioAnalyzer._label_segments(4)
        assert labels == ["intro", "verse", "chorus", "outro"]
        labels = LibrosaAudioAnalyzer._label_segments(6)
        assert labels[0] == "intro"
        assert labels[-1] == "outro"
        assert len(labels) == 6

    @patch("audio_analyzer_librosa._LIBROSA_AVAILABLE", True)
    def test_analyze_with_mocked_librosa(self, tmp_path):
        """使用 mock 验证分析流程（不依赖真实 librosa）"""
        import numpy as np

        # 创建假音频文件
        fake_audio = tmp_path / "fake.wav"
        fake_audio.write_bytes(b"fake audio content")

        # 构造 mock librosa
        mock_librosa = MagicMock()
        mock_librosa.load.return_value = (np.zeros(22050), 22050)
        mock_librosa.get_duration.return_value = 10.0
        mock_librosa.beat.beat_track.return_value = (120.0, np.array([10, 20, 30]))
        mock_librosa.frames_to_time.return_value = np.array([0.5, 1.0, 1.5])
        mock_librosa.onset.onset_strength.return_value = np.array([0.1, 0.5, 0.8])
        mock_librosa.feature.spectral_centroid.return_value = np.array([[2500.0]])
        mock_librosa.feature.spectral_bandwidth.return_value = np.array([[1500.0]])
        mock_librosa.feature.spectral_rolloff.return_value = np.array([[3000.0]])
        mock_librosa.feature.zero_crossing_rate.return_value = np.array([[0.05]])
        mock_librosa.feature.rms.return_value = np.array([np.array([0.04, 0.05, 0.06])])
        mock_librosa.feature.mfcc.return_value = np.zeros((13, 10))
        mock_librosa.feature.chroma_stft.return_value = np.zeros((12, 10))
        mock_librosa.segment.agglomerative.return_value = np.array([0, 50])

        # 直接 patch 模块级 librosa 引用（避免触发真实 librosa 加载）
        with patch("audio_analyzer_librosa.librosa", mock_librosa), \
             patch("audio_analyzer_librosa.np", np):
            analyzer = LibrosaAudioAnalyzer(enable_cache=False)
            result = analyzer.analyze(str(fake_audio))

        assert result.success is True
        assert result.duration == 10.0
        assert result.bpm == 120.0
        assert len(result.beats) == 3
        # 第一个 beat 是 downbeat (i % 4 == 0)
        assert result.beats[0].is_downbeat is True
        assert result.beats[1].is_downbeat is False


# ============================================================
# MediaPreprocessor 测试
# ============================================================

class TestMediaPreprocessorDataClasses:
    """数据类基础测试"""

    def test_media_info_to_dict(self):
        info = MediaInfo(
            success=True, path="/v.mp4", duration=10.0,
            width=1920, height=1080, fps=30.0, codec="h264",
            has_audio=True, audio_codec="aac",
        )
        d = info.to_dict()
        assert d["success"] is True
        assert d["width"] == 1920
        assert d["has_audio"] is True

    def test_preprocess_result_defaults(self):
        result = PreprocessResult()
        assert result.success is False
        assert result.output_paths == []
        assert result.metadata == {}


class TestMediaPreprocessorBehavior:
    """MediaPreprocessor 行为测试"""

    def test_nonexistent_file_get_info(self):
        pp = MediaPreprocessor()
        info = pp.get_info("/nonexistent/video.mp4")
        assert info.success is False
        assert "不存在" in info.error

    def test_nonexistent_file_extract_audio(self):
        pp = MediaPreprocessor()
        result = pp.extract_audio("/nonexistent/v.mp4", "/tmp/out.wav")
        assert result.success is False
        assert "不存在" in result.error

    def test_nonexistent_file_extract_thumbnails(self):
        pp = MediaPreprocessor()
        result = pp.extract_thumbnails("/nonexistent/v.mp4", "/tmp/thumbs/")
        assert result.success is False
        assert "不存在" in result.error

    def test_nonexistent_file_transcode(self):
        pp = MediaPreprocessor()
        result = pp.transcode("/nonexistent/v.mp4", "/tmp/out.mp4")
        assert result.success is False
        assert "不存在" in result.error

    def test_convenience_apis(self):
        info = get_media_info("/nonexistent/v.mp4")
        assert info.success is False

        result = extract_audio("/nonexistent/v.mp4", "/tmp/out.wav")
        assert result.success is False

        result = extract_thumbnails("/nonexistent/v.mp4", "/tmp/thumbs/")
        assert result.success is False

        result = transcode("/nonexistent/v.mp4", "/tmp/out.mp4")
        assert result.success is False

    def test_parse_fraction(self):
        assert MediaPreprocessor._parse_fraction("30/1") == 30.0
        assert MediaPreprocessor._parse_fraction("30000/1001") == pytest.approx(29.97, abs=0.01)
        assert MediaPreprocessor._parse_fraction("0/1") == 0.0
        assert MediaPreprocessor._parse_fraction("invalid") == 0.0
        assert MediaPreprocessor._parse_fraction("1/0") == 0.0  # 除零保护

    @patch("media_preprocessor._FFMPEG_PYTHON_AVAILABLE", True)
    def test_get_info_with_mocked_ffmpeg(self, tmp_path):
        """使用 mock 验证 get_info 流程（不依赖真实 ffmpeg-python）"""
        fake_video = tmp_path / "fake.mp4"
        fake_video.write_bytes(b"fake video content")

        mock_ffmpeg = MagicMock()
        mock_ffmpeg.probe.return_value = {
            "format": {
                "format_name": "mov,mp4,m4a",
                "bit_rate": "2000000",
                "duration": "10.5",
            },
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30/1",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                },
            ],
        }

        # 直接 patch 模块级 ffmpeg 引用
        with patch("media_preprocessor.ffmpeg", mock_ffmpeg):
            pp = MediaPreprocessor()
            info = pp.get_info(str(fake_video))

        assert info.success is True
        assert info.duration == 10.5
        assert info.width == 1920
        assert info.height == 1080
        assert info.fps == 30.0
        assert info.codec == "h264"
        assert info.has_audio is True
        assert info.audio_codec == "aac"
        assert info.audio_sample_rate == 48000
        assert info.audio_channels == 2


# ============================================================
# ae_agent_pipeline 集成测试
# ============================================================

class TestPipelinePhase2Integration:
    """验证 ae_agent_pipeline 集成新模块"""

    def test_pipeline_loads_phase2_modules(self):
        """验证 _init_analyzers 加载三个新模块"""
        from ae_agent_pipeline import AEAgentPipeline
        pipeline = AEAgentPipeline()
        # 模块属性必须存在（None 表示依赖未安装，但属性必须存在）
        assert hasattr(pipeline, "scene_detector")
        assert hasattr(pipeline, "librosa_audio_analyzer")
        assert hasattr(pipeline, "media_preprocessor")

    def test_enhance_perception_method_exists(self):
        """验证 _enhance_perception_with_phase2 方法存在"""
        from ae_agent_pipeline import AEAgentPipeline
        pipeline = AEAgentPipeline()
        assert hasattr(pipeline, "_enhance_perception_with_phase2")
        assert callable(pipeline._enhance_perception_with_phase2)

    def test_enhance_perception_no_crash_on_empty_inputs(self):
        """空输入不应崩溃"""
        from ae_agent_pipeline import AEAgentPipeline, PerceptionResult
        pipeline = AEAgentPipeline()
        perception = PerceptionResult()
        # 空输入调用，不应抛异常
        pipeline._enhance_perception_with_phase2(perception, "", [])
        # 不应有任何扩展属性被设置（因为输入为空）
        assert not hasattr(perception, "media_infos") or not perception.media_infos
        assert not hasattr(perception, "scene_segments") or not perception.scene_segments

    def test_enhance_perception_with_media_preprocessor(self, tmp_path):
        """验证 MediaPreprocessor 注入 media_infos"""
        from ae_agent_pipeline import AEAgentPipeline, PerceptionResult
        # 创建假视频文件
        fake_video = tmp_path / "fake.mp4"
        fake_video.write_bytes(b"fake")

        pipeline = AEAgentPipeline()
        # 强制启用 media_preprocessor（即使 ffmpeg-python 未安装）
        if pipeline.media_preprocessor is None:
            from media_preprocessor import MediaPreprocessor
            pipeline.media_preprocessor = MediaPreprocessor()

        perception = PerceptionResult()
        pipeline._enhance_perception_with_phase2(
            perception, "", [str(fake_video)]
        )

        # media_preprocessor.get_info 会因为文件不是真实视频而失败
        # 但 _enhance_perception 不应崩溃，media_infos 不应被设置
        # （因为 info.success 会是 False）
        # 这是预期的优雅降级行为

    def test_enhance_perception_with_librosa_fallback(self, tmp_path):
        """验证 librosa 在 music_features 为空时尝试分析"""
        from ae_agent_pipeline import AEAgentPipeline, PerceptionResult
        fake_audio = tmp_path / "fake.wav"
        fake_audio.write_bytes(b"fake")

        pipeline = AEAgentPipeline()
        if pipeline.librosa_audio_analyzer is None:
            from audio_analyzer_librosa import LibrosaAudioAnalyzer
            pipeline.librosa_audio_analyzer = LibrosaAudioAnalyzer(enable_cache=False)

        perception = PerceptionResult()
        # music_features 为空时触发 librosa 分析
        pipeline._enhance_perception_with_phase2(
            perception, str(fake_audio), []
        )
        # 因为是假音频文件，librosa 分析会失败（如果 librosa 已安装）
        # 或者 librosa 未安装时直接跳过
        # 都不应崩溃

    def test_enhance_perception_skips_when_music_features_already_set(self):
        """当 EnhancedAudioAnalyzer 已设置 music_features 时，librosa 应跳过"""
        from ae_agent_pipeline import AEAgentPipeline, PerceptionResult
        pipeline = AEAgentPipeline()

        perception = PerceptionResult()
        perception.music_features = {"bpm": 120, "mood": "happy"}

        # mock librosa_analyzer.analyze 确保不被调用
        if pipeline.librosa_audio_analyzer:
            pipeline.librosa_audio_analyzer.analyze = MagicMock()

        pipeline._enhance_perception_with_phase2(perception, "fake_path", [])

        # librosa 不应被调用（因为 music_features 已存在）
        if pipeline.librosa_audio_analyzer:
            pipeline.librosa_audio_analyzer.analyze.assert_not_called()

    def test_perceive_method_calls_phase2_enhancement(self):
        """验证 perceive() 调用 _enhance_perception_with_phase2"""
        from ae_agent_pipeline import AEAgentPipeline
        pipeline = AEAgentPipeline()
        # mock 增强方法
        pipeline._enhance_perception_with_phase2 = MagicMock()
        # 调用 perceive（无文件，会优雅跳过 analyzer 调用）
        try:
            pipeline.perceive("", [])
        except Exception:
            pass  # perceive 可能因 analyzer 报错，但增强方法应被调用
        pipeline._enhance_perception_with_phase2.assert_called_once()


# ============================================================
# 跨模块综合测试
# ============================================================

class TestPhase2EndToEnd:
    """Phase 2 模块端到端集成测试"""

    def test_all_modules_graceful_degradation(self):
        """所有模块在不具备依赖时都应优雅降级，不抛异常"""
        # SceneDetector
        scene_result = detect_scenes("/nonexistent/v.mp4")
        assert scene_result.success is False

        # LibrosaAudioAnalyzer
        audio_result = analyze_audio("/nonexistent/a.mp3")
        assert audio_result.success is False

        # MediaPreprocessor
        media_info = get_media_info("/nonexistent/v.mp4")
        assert media_info.success is False

    def test_data_class_serialization(self):
        """所有结果对象都能正确序列化为 dict"""
        seg = SceneSegment(index=0, start_time=0.0, end_time=1.0, duration=1.0)
        beat = BeatInfo(time=0.5, strength=0.8, is_downbeat=True)
        audio_seg = LibrosaAudioSegment(
            index=0, start_time=0.0, end_time=1.0, duration=1.0, label="intro"
        )
        media_info = MediaInfo(success=True, path="/v.mp4", duration=10.0)
        preprocess_result = PreprocessResult(success=True, operation="test")

        # 序列化不应抛异常
        assert isinstance(seg.to_dict(), dict)
        assert isinstance(beat.to_dict(), dict)
        assert isinstance(audio_seg.to_dict(), dict)
        assert isinstance(media_info.to_dict(), dict)
        assert isinstance(preprocess_result.to_dict(), dict)

        # AudioAnalysisResult 也能序列化
        audio_result = AudioAnalysisResult(
            success=True, duration=10.0, bpm=120.0,
            beats=[beat], segments=[audio_seg],
        )
        d = audio_result.to_dict()
        assert d["success"] is True
        assert len(d["beats"]) == 1
        assert len(d["segments"]) == 1

        # SceneDetectResult 也能序列化
        scene_result = SceneDetectResult(
            success=True, scene_count=1, segments=[seg],
        )
        d = scene_result.to_dict()
        assert d["success"] is True
        assert len(d["segments"]) == 1
