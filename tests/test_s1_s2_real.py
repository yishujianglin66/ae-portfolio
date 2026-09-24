"""
tests/test_s1_s2_real.py — S1 素材规范化 + S2 节拍分析 真实执行测试
====================================================================

标记：@pytest.mark.real_ffmpeg（需要本地 FFmpeg 可用）
运行：pytest tests/test_s1_s2_real.py -m real_ffmpeg -v
"""
import json
import subprocess
from pathlib import Path

import pytest

# ============================================================================
#  Markers
# ============================================================================

pytestmark = pytest.mark.real_ffmpeg

# 测试素材目录（使用项目中已有的真实视频）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REAL_AMV_DIR = DATA_DIR / "real_amv_test"


def _find_test_videos(count: int = 3) -> list[Path]:
    """查找可用的测试视频"""
    candidates = []
    # 优先从 real_amv_test 目录找
    if REAL_AMV_DIR.exists():
        for f in REAL_AMV_DIR.iterdir():
            if f.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv"):
                candidates.append(f)
    # 回退到 data 目录
    if len(candidates) < count and DATA_DIR.exists():
        for f in DATA_DIR.rglob("*.mp4"):
            if f not in candidates:
                candidates.append(f)
            if len(candidates) >= count:
                break
    return candidates[:count]


def _find_test_audio() -> Path | None:
    """查找可用的测试音频"""
    # 从 real_amv_test 找 wav/mp3
    if REAL_AMV_DIR.exists():
        for f in REAL_AMV_DIR.iterdir():
            if f.suffix.lower() in (".wav", ".mp3", ".aac", ".m4a"):
                return f
    # 从视频提取（用第一个视频作为音频源）
    videos = _find_test_videos(1)
    if videos:
        return videos[0]
    return None


def _ffmpeg_available() -> bool:
    """检查 FFmpeg 是否可用"""
    ffmpeg = Path("C:/ffmpeg/bin/ffmpeg.exe")
    return ffmpeg.exists()


# ============================================================================
#  S1 素材规范化测试
# ============================================================================

class TestS1AssetNormalize:
    """S1 素材规范化"""

    @pytest.fixture(autouse=True)
    def skip_if_no_ffmpeg(self):
        if not _ffmpeg_available():
            pytest.skip("FFmpeg 不可用")

    def test_import_and_init(self):
        """AssetNormalizeStage 可导入并初始化"""
        from pipeline.stages.asset_normalize import AssetNormalizeStage
        stage = AssetNormalizeStage()
        assert stage.ffmpeg_path.exists()
        assert stage.ffprobe_path.exists()

    def test_missing_ffmpeg_raises(self, tmp_path):
        """FFmpeg 不存在时抛异常（零 fallback）"""
        from pipeline.stages.asset_normalize import AssetNormalizeStage
        with pytest.raises(FileNotFoundError, match="FFmpeg"):
            AssetNormalizeStage(ffmpeg_path=tmp_path / "nonexist.exe")

    def test_wrong_video_count(self, tmp_path):
        """视频数量不是 3 → 失败"""
        from pipeline.stages.asset_normalize import AssetNormalizeStage
        stage = AssetNormalizeStage()
        result = stage.run(
            source_videos=["a.mp4", "b.mp4"],  # 只有 2 条
            source_audio="c.wav",
            output_dir=tmp_path / "S1",
        )
        assert result.success is False
        assert "3" in result.errors[0]

    # 真实规范化很重（实测单例 ~160s，含 3 视频 1080p 重编码）：全类**共享一次**执行。
    # 原先两个用例各编码一遍 = 重复劳动，既拖慢全量，又让单例逼近 pytest --timeout 上限
    # （全量冷缓存下曾越过 300s → xdist worker 被杀 → 控制器死锁，见 handoff §9.5）。
    @pytest.fixture(scope="class")
    def normalized(self, tmp_path_factory):
        videos = _find_test_videos(3)
        audio = _find_test_audio()
        if len(videos) < 3 or audio is None:
            pytest.skip("测试素材不足（需要 3 视频 + 1 音频）")

        from pipeline.stages.asset_normalize import AssetNormalizeStage
        stage = AssetNormalizeStage()
        out_dir = tmp_path_factory.mktemp("S1_assets")
        result = stage.run(
            source_videos=[str(v) for v in videos],
            source_audio=str(audio),
            output_dir=out_dir,
        )
        return stage, result

    # 超时预算：本用例的 fixture 要真实重编码 3 段 1080p（实测 setup 单例 163.78s），
    # 全量冷缓存 + 机器有其他负载时（实测：Resolve 常驻、并行跑别的 pytest）
    # 会越过全局 --timeout=300 → pytest-timeout 直接杀掉整个会话、**连汇总行都不出**。
    # 这已发生 2 次（2026-09-23），代价是每次丢掉一整轮 15 分钟的回归结果。
    # 故显式给 900s：不是"放过慢测试"，而是让"它就该慢"这件事在代码里留痕，
    # 且避免用超时把**别的**用例的结果一起牺牲掉。
    @pytest.mark.timeout(900)
    def test_normalize_real_videos(self, normalized):
        """真实视频规范化（需要测试素材）"""
        _stage, result = normalized

        # 验证结果
        assert result.success is True, f"errors: {result.errors}"
        assert len(result.output_videos) == 3
        assert result.output_audio is not None

        # 验证产物存在
        for vp in result.output_videos:
            p = Path(vp)
            assert p.exists()
            assert p.stat().st_size > 0

        # 验证 MD5 文件
        assert result.md5sums_path is not None
        md5_file = Path(result.md5sums_path)
        assert md5_file.exists()
        lines = md5_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 4  # 3 视频 + 1 音频

    def test_output_is_1080p_h264(self, normalized):
        """输出视频确实是 1920x1080 H.264"""
        stage, result = normalized
        if not result.success:
            pytest.skip(f"S1 失败: {result.errors}")

        # 用 stage 自带的 ffprobe（原先硬编码 C:/ffmpeg/... 换机即碎）
        out_video = Path(result.output_videos[0])
        cmd = [
            str(stage.ffprobe_path), "-v", "quiet",
            "-print_format", "json",
            "-show_streams", str(out_video),
        ]
        r = subprocess.run(  # noqa: S603 - 参数列表 + shell=False，无 shell 解析
            cmd, capture_output=True, text=True, timeout=30, shell=False
        )
        info = json.loads(r.stdout)
        video_stream = next(
            s for s in info["streams"] if s["codec_type"] == "video"
        )
        assert video_stream["codec_name"] == "h264"
        assert int(video_stream["width"]) == 1920
        assert int(video_stream["height"]) == 1080


# ============================================================================
#  S2 节拍分析测试
# ============================================================================

class TestS2BeatAnalysis:
    """S2 节拍分析"""

    def test_import(self):
        """BeatAnalysisStage 可导入"""
        from pipeline.stages.analysis import BeatAnalysisStage
        stage = BeatAnalysisStage()
        assert stage.sr == 22050

    def test_missing_audio_fails(self, tmp_path):
        """音频不存在 → 失败"""
        from pipeline.stages.analysis import BeatAnalysisStage
        stage = BeatAnalysisStage()
        result = stage.run(
            audio_path=tmp_path / "nonexist.wav",
            output_dir=tmp_path / "S2",
        )
        assert result.success is False
        assert "不存在" in result.errors[0]

    def test_real_beat_analysis(self, tmp_path):
        """真实音频节拍分析"""
        audio = _find_test_audio()
        if audio is None:
            pytest.skip("无测试音频")

        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa 不可用")

        from pipeline.stages.analysis import BeatAnalysisStage
        stage = BeatAnalysisStage()
        out_dir = tmp_path / "S2_beat"

        result = stage.run(audio_path=audio, output_dir=out_dir)

        # 基本验证
        assert result.elapsed_s > 0
        if not result.success:
            # 可能是 drop 不够（短视频），但不应崩溃
            assert result.bpm > 0 or len(result.errors) > 0
            return

        # 成功时的完整验证
        assert result.bpm > 0
        assert len(result.beats) > 0
        assert len(result.drops) >= 4

        # beats.json 落盘
        assert result.beats_json_path is not None
        beats_file = Path(result.beats_json_path)
        assert beats_file.exists()
        data = json.loads(beats_file.read_text(encoding="utf-8"))
        assert data["bpm"] > 0
        assert len(data["drops"]) >= 4

        # waveform.png 落盘
        if result.waveform_png_path:
            assert Path(result.waveform_png_path).exists()

    def test_beats_json_structure(self, tmp_path):
        """beats.json 结构合规"""
        audio = _find_test_audio()
        if audio is None:
            pytest.skip("无测试音频")
        try:
            import librosa  # noqa: F401
        except ImportError:
            pytest.skip("librosa 不可用")

        from pipeline.stages.analysis import BeatAnalysisStage
        stage = BeatAnalysisStage()
        out_dir = tmp_path / "S2_beat"
        result = stage.run(audio_path=audio, output_dir=out_dir)

        if not result.beats_json_path:
            pytest.skip("未生成 beats.json")

        data = json.loads(Path(result.beats_json_path).read_text(encoding="utf-8"))
        # 必需字段
        assert "bpm" in data
        assert "beats" in data
        assert "drops" in data
        assert "duration_s" in data
        # 类型检查
        assert isinstance(data["bpm"], (int, float))
        assert isinstance(data["beats"], list)
        assert isinstance(data["drops"], list)
        assert isinstance(data["duration_s"], (int, float))
