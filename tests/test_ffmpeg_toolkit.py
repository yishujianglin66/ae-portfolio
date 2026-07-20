"""FFmpeg工具包单元测试"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from ffmpeg_toolkit import FFmpegToolkit
except ImportError:
    # 如果从根目录导入失败，尝试直接运行
    import importlib.util
    spec = importlib.util.spec_from_file_location("ffmpeg_toolkit", Path(__file__).resolve().parent.parent / "ffmpeg-toolkit.py")
    ffmpeg_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ffmpeg_module)
    FFmpegToolkit = ffmpeg_module.FFmpegToolkit


class TestFFmpegToolkitInit(unittest.TestCase):
    """初始化测试"""

    def test_init_with_default_config(self):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
                "audio": {"default_bitrate": "192k"}
            })
            toolkit = FFmpegToolkit()
            self.assertEqual(toolkit.ffmpeg, "ffmpeg")
            self.assertEqual(toolkit.ffprobe, "ffprobe")

    def test_config_has_required_keys(self):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
                "audio": {"default_bitrate": "192k"}
            })
            toolkit = FFmpegToolkit()
            self.assertIn("tools", toolkit.config)
            self.assertIn("audio", toolkit.config)


class TestFFmpegToolkitExtractAudio(unittest.TestCase):
    """音频提取测试"""

    def setUp(self):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
                "audio": {"default_bitrate": "192k"}
            })
            self.toolkit = FFmpegToolkit()

    def test_extract_audio_nonexistent_file(self):
        result = self.toolkit.extract_audio("/nonexistent/file.mp4")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result.get("error", ""))

    def test_extract_audio_with_custom_output(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video data")
            input_file = f.name
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                output_file = f.name
            try:
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value.returncode = 0
                    result = self.toolkit.extract_audio(input_file, output_file)
                    self.assertTrue(result["success"])
                    self.assertEqual(result["output_file"], output_file)
            finally:
                if os.path.exists(output_file):
                    os.remove(output_file)
        finally:
            os.remove(input_file)

    def test_extract_audio_bitrate_default(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video data")
            input_file = f.name
        try:
            # 创建输出文件以通过存在性检查
            output_file = os.path.splitext(input_file)[0] + ".mp3"
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stderr = ""
                # 同时 mock os.path.exists 以通过输出文件检查
                with patch('os.path.exists') as mock_exists:
                    mock_exists.side_effect = lambda p: p == input_file or p == output_file
                    with patch('os.path.getsize') as mock_size:
                        mock_size.return_value = 1024
                        result = self.toolkit.extract_audio(input_file)
                        self.assertTrue(result["success"])
        finally:
            os.remove(input_file)

    def test_extract_audio_ffmpeg_failure(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video data")
            input_file = f.name
        try:
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 1
                mock_run.return_value.stderr = "error message"
                result = self.toolkit.extract_audio(input_file)
                self.assertFalse(result["success"])
                self.assertIn("error", result.get("error", ""))
        finally:
            os.remove(input_file)

    def test_extract_audio_timeout(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video data")
            input_file = f.name
        try:
            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("cmd", 120)
                result = self.toolkit.extract_audio(input_file)
                self.assertFalse(result["success"])
        finally:
            os.remove(input_file)


class TestFFmpegToolkitExtractVideoSegment(unittest.TestCase):
    """视频片段截取测试"""

    def setUp(self):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
                "audio": {"default_bitrate": "192k"}
            })
            self.toolkit = FFmpegToolkit()

    def test_extract_video_segment_nonexistent_file(self):
        result = self.toolkit.extract_video_segment("/nonexistent/file.mp4", 0, 10)
        self.assertFalse(result["success"])
        self.assertIn("不存在", result.get("error", ""))

    def test_extract_video_segment_with_audio(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video data")
            input_file = f.name
        try:
            output_file = os.path.splitext(input_file)[0] + "_segment_0.0_10.0.mp4"
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stderr = ""
                with patch('os.path.exists') as mock_exists:
                    mock_exists.side_effect = lambda p: p == input_file or p == output_file
                    with patch('os.path.getsize') as mock_size:
                        mock_size.return_value = 1024
                        result = self.toolkit.extract_video_segment(input_file, 0, 10, preserve_audio=True)
                        self.assertTrue(result["success"])
        finally:
            os.remove(input_file)

    def test_extract_video_segment_no_audio(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video data")
            input_file = f.name
        try:
            output_file = os.path.splitext(input_file)[0] + "_segment_0.0_10.0.mp4"
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stderr = ""
                with patch('os.path.exists') as mock_exists:
                    mock_exists.side_effect = lambda p: p == input_file or p == output_file
                    with patch('os.path.getsize') as mock_size:
                        mock_size.return_value = 1024
                        result = self.toolkit.extract_video_segment(input_file, 0, 10, preserve_audio=False)
                        self.assertTrue(result["success"])
        finally:
            os.remove(input_file)


class TestFFmpegToolkitExtractAudioSegment(unittest.TestCase):
    """音频片段截取测试"""

    def setUp(self):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
                "audio": {"default_bitrate": "192k"}
            })
            self.toolkit = FFmpegToolkit()

    def test_extract_audio_segment_nonexistent_file(self):
        result = self.toolkit.extract_audio_segment("/nonexistent/file.mp3", 0, 10)
        self.assertFalse(result["success"])
        self.assertIn("不存在", result.get("error", ""))

    def test_extract_audio_segment_valid(self):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake audio data")
            input_file = f.name
        try:
            output_file = os.path.splitext(input_file)[0] + "_segment_0.0_10.0.mp3"
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stderr = ""
                with patch('os.path.exists') as mock_exists:
                    mock_exists.side_effect = lambda p: p == input_file or p == output_file
                    with patch('os.path.getsize') as mock_size:
                        mock_size.return_value = 1024
                        result = self.toolkit.extract_audio_segment(input_file, 0, 10)
                        self.assertTrue(result["success"])
        finally:
            os.remove(input_file)


class TestFFmpegToolkitGetMediaInfo(unittest.TestCase):
    """媒体信息获取测试"""

    def setUp(self):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
                "audio": {"default_bitrate": "192k"}
            })
            self.toolkit = FFmpegToolkit()

    def test_get_media_info_nonexistent_file(self):
        result = self.toolkit.get_media_info("/nonexistent/file.mp4")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result.get("error", ""))

    def test_get_media_info_valid_output(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video data")
            input_file = f.name
        try:
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = json.dumps({
                    "format": {"duration": "60.0", "size": "1000000"},
                    "streams": [{}, {}]
                })
                result = self.toolkit.get_media_info(input_file)
                self.assertTrue(result["success"])
                self.assertEqual(result["duration"], 60.0)
                self.assertEqual(result["size"], 1000000)
                self.assertEqual(result["streams"], 2)
        finally:
            os.remove(input_file)

    def test_get_media_info_ffprobe_error(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video data")
            input_file = f.name
        try:
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 1
                mock_run.return_value.stderr = "error"
                result = self.toolkit.get_media_info(input_file)
                self.assertFalse(result["success"])
        finally:
            os.remove(input_file)


class TestFFmpegToolkitConvertVideoFormat(unittest.TestCase):
    """视频格式转换测试"""

    def setUp(self):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
                "audio": {"default_bitrate": "192k"}
            })
            self.toolkit = FFmpegToolkit()

    def test_convert_video_nonexistent_file(self):
        result = self.toolkit.convert_video_format("/nonexistent/file.avi", "/tmp/out.mp4")
        self.assertFalse(result["success"])
        self.assertIn("不存在", result.get("error", ""))

    def test_convert_video_success(self):
        with tempfile.NamedTemporaryFile(suffix=".avi", delete=False) as f:
            f.write(b"fake video data")
            input_file = f.name
        output_file = "/tmp/out.mp4"
        try:
            with patch('subprocess.run') as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stderr = ""
                with patch('os.path.exists') as mock_exists:
                    mock_exists.side_effect = lambda p: p == input_file or p == output_file
                    with patch('os.path.getsize') as mock_size:
                        mock_size.return_value = 1024
                        result = self.toolkit.convert_video_format(input_file, output_file)
                        self.assertTrue(result["success"])
        finally:
            os.remove(input_file)


class TestFFmpegToolkitHelpers(unittest.TestCase):
    """辅助方法测试"""

    def setUp(self):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
                "audio": {"default_bitrate": "192k"}
            })
            self.toolkit = FFmpegToolkit()

    def test_get_audio_codec_mp3(self):
        self.assertEqual(self.toolkit._get_audio_codec("mp3"), "libmp3lame")

    def test_get_audio_codec_wav(self):
        self.assertEqual(self.toolkit._get_audio_codec("wav"), "pcm_s16le")

    def test_get_audio_codec_m4a(self):
        self.assertEqual(self.toolkit._get_audio_codec("m4a"), "aac")

    def test_get_audio_codec_flac(self):
        self.assertEqual(self.toolkit._get_audio_codec("flac"), "flac")

    def test_get_audio_codec_unknown(self):
        self.assertEqual(self.toolkit._get_audio_codec("unknown"), "libmp3lame")


class TestFFmpegToolkitTestFFmpeg(unittest.TestCase):
    """FFmpeg可用性测试"""

    def setUp(self):
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
                "audio": {"default_bitrate": "192k"}
            })
            self.toolkit = FFmpegToolkit()

    def test_test_ffmpeg_both_available(self):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            result = self.toolkit.test_ffmpeg()
            self.assertTrue(result["ffmpeg_available"])
            self.assertTrue(result["ffprobe_available"])

    def test_test_ffmpeg_both_unavailable(self):
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("not found")
            result = self.toolkit.test_ffmpeg()
            self.assertFalse(result["ffmpeg_available"])
            self.assertFalse(result["ffprobe_available"])

    def test_test_ffmpeg_ffmpeg_only(self):
        call_count = 0

        def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(returncode=0)
            else:
                raise FileNotFoundError("not found")

        with patch('subprocess.run', side_effect=mock_run):
            result = self.toolkit.test_ffmpeg()
            self.assertTrue(result["ffmpeg_available"])
            self.assertFalse(result["ffprobe_available"])


if __name__ == "__main__":
    unittest.main(verbosity=2)