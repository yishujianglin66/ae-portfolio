# Phase 1 素材预处理 - 全链路技术详解

---

## 文档信息

| 项目 | 内容 |
|------|------|
| **阶段** | Phase 1 素材预处理 |
| **涉及引擎** | 11个（3商业 + 8开源） |
| **处理时长** | 约为视频时长的 0.5-1.5倍 |
| **输出产物** | 增强视频 + 字幕 + 镜头列表 + 主体框 + 音频特征 + 初筛蒙版 + 场景元数据 |

---

## 一、预处理流水线总览

### 1.1 流水线结构

```
输入视频
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  步骤1：格式标准化与基础信息采集                       │
│  ffmpeg-python → 获取视频元数据 + 格式统一            │
└────────────────────────┬────────────────────────────┘
                         │
    ┌────────────────────┴────────────────────┐
    │                    │                    │
    ▼                    ▼                    ▼
┌──────────┐      ┌──────────┐        ┌──────────┐
│ 步骤2    │      │ 步骤3    │        │ 步骤4    │
│ 画质增强  │      │ 语音识别  │        │ 音频分析  │
│ Topaz    │      │ FunASR   │        │ librosa  │
│ Video AI │      │          │        │ +torchaudio│
└──────────┘      └──────────┘        └──────────┘
    │                    │                    │
    └────────────────────┬────────────────────┘
                         │
    ┌────────────────────┴────────────────────┐
    │                    │                    │
    ▼                    ▼                    ▼
┌──────────┐      ┌──────────┐        ┌──────────┐
│ 步骤5    │      │ 步骤6    │        │ 步骤7    │
│ 镜头分割  │      │ 主体检测  │        │ 人像初筛  │
│ PyScene  │      │ YOLO-    │        │ RVM      │
│ Detect   │      │ World    │        │          │
│ +TransNet│      │          │        │          │
│ V2双校验 │      │          │        │          │
└──────────┘      └──────────┘        └──────────┘
    │                    │                    │
    └────────────────────┬────────────────────┘
                         │
    ┌────────────────────┴────────────────────┐
    │                                         │
    ▼                                         ▼
┌──────────┐                            ┌──────────┐
│ 步骤8    │                            │ 步骤9    │
│ 画面语义 │                            │ 精细抠像  │
│ InternVL2│                            │ SAM2-    │
│ (可选P1) │                            │ Matting  │
│          │                            │ (可选P1) │
└──────────┘                            └──────────┘
    │                                         │
    └────────────────────┬────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  步骤10：数据融合与质量校验                           │
│  所有预处理结果整合 → 统一数据格式 → QC校验           │
└─────────────────────────────────────────────────────┘
```

### 1.2 并行执行策略

预处理阶段支持高度并行化，以下为推荐执行顺序：

| 批次 | 任务 | 执行模式 | 预计耗时（1分钟视频） |
|------|------|---------|---------------------|
| **批次1** | 格式标准化 + 画质增强 | 串行 | 20-60秒（取决于Topaz模型） |
| **批次2** | 语音识别 + 音频分析 + 镜头分割 + 主体检测 + 人像初筛 | 5任务并行 | 10-20秒 |
| **批次3** | 画面语义 + 精细抠像（P1可选） | 2任务并行 | 30-60秒 |
| **批次4** | 数据融合 + 质量校验 | 串行 | 2-5秒 |

---

## 二、各步骤技术详解

### 步骤1：格式标准化与基础信息采集

**引擎**：ffmpeg-python + ffprobe

#### 1.1 功能清单

| 功能 | 说明 |
|------|------|
| 视频元数据采集 | 分辨率、帧率、码率、编码格式、时长、色彩空间 |
| 音频元数据采集 | 采样率、声道数、编码格式、码率 |
| 格式标准化 | 统一转换为 MP4 (H.264 + AAC)，便于后续处理 |
| 代理文件生成 | 生成低分辨率代理视频，加速后续AI处理 |
| 帧提取 | 提取关键帧/缩略图，用于快速预览 |

#### 1.2 核心Python实现

```python
import ffmpeg
import json
from pathlib import Path
from dataclasses import dataclass

@dataclass
class VideoInfo:
    """视频信息数据类"""
    width: int
    height: int
    fps: float
    duration: float
    codec: str
    bitrate: int
    pix_fmt: str
    color_space: str
    has_audio: bool
    audio_codec: str = None
    audio_sample_rate: int = None
    audio_channels: int = None

class VideoStandardizer:
    """视频标准化处理器"""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
    
    def probe(self, input_path: str) -> VideoInfo:
        """探测视频信息"""
        probe = ffmpeg.probe(input_path)
        
        video_stream = next(s for s in probe["streams"] 
                          if s["codec_type"] == "video")
        audio_streams = [s for s in probe["streams"] 
                        if s["codec_type"] == "audio"]
        
        # 计算帧率
        fps_num, fps_den = map(int, video_stream["r_frame_rate"].split("/"))
        fps = fps_num / fps_den
        
        info = VideoInfo(
            width=video_stream["width"],
            height=video_stream["height"],
            fps=fps,
            duration=float(probe["format"]["duration"]),
            codec=video_stream["codec_name"],
            bitrate=int(probe["format"]["bit_rate"]),
            pix_fmt=video_stream.get("pix_fmt", "yuv420p"),
            color_space=video_stream.get("color_space", "bt709"),
            has_audio=len(audio_streams) > 0,
        )
        
        if audio_streams:
            audio = audio_streams[0]
            info.audio_codec = audio["codec_name"]
            info.audio_sample_rate = int(audio["sample_rate"])
            info.audio_channels = audio["channels"]
        
        return info
    
    def standardize(self, input_path: str, output_path: str,
                    target_resolution: tuple = (1920, 1080),
                    target_fps: float = 30.0,
                    target_bitrate: str = "20M") -> bool:
        """标准化视频格式"""
        try:
            (
                ffmpeg
                .input(input_path)
                .output(
                    output_path,
                    vcodec="libx264",
                    acodec="aac",
                    pix_fmt="yuv420p",
                    r=target_fps,
                    video_bitrate=target_bitrate,
                    preset="medium",
                    crf=18,
                    movflags="+faststart",
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            return True
        except ffmpeg.Error as e:
            print(f"标准化失败: {e.stderr.decode()}")
            return False
    
    def generate_proxy(self, input_path: str, proxy_path: str,
                      scale: float = 0.25) -> bool:
        """生成代理视频"""
        try:
            (
                ffmpeg
                .input(input_path)
                .output(
                    proxy_path,
                    vcodec="libx264",
                    acodec="aac",
                    vf=f"scale=iw*{scale:.2f}:ih*{scale:.2f}",
                    crf=28,
                    preset="fast",
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            return True
        except ffmpeg.Error:
            return False
    
    def extract_frames(self, input_path: str, output_dir: str,
                       fps: float = 1.0, format: str = "jpg") -> list:
        """提取帧"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        output_pattern = str(Path(output_dir) / "frame_%06d.{format}")
        
        try:
            (
                ffmpeg
                .input(input_path)
                .output(output_pattern, vf=f"fps={fps}")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            frames = sorted(Path(output_dir).glob(f"*.{format}"))
            return [str(f) for f in frames]
        except ffmpeg.Error:
            return []
```

#### 1.3 输出数据格式

```json
{
  "video_info": {
    "width": 1920,
    "height": 1080,
    "fps": 30.0,
    "duration": 60.5,
    "codec": "h264",
    "bitrate": 20000000,
    "pix_fmt": "yuv420p",
    "color_space": "bt709",
    "has_audio": true,
    "audio_codec": "aac",
    "audio_sample_rate": 48000,
    "audio_channels": 2
  },
  "standardized_path": "/path/to/std_video.mp4",
  "proxy_path": "/path/to/proxy.mp4",
  "thumbnail_path": "/path/to/thumbnails/",
  "quality_score": 0.85
}
```

---

### 步骤2：画质增强

**引擎**：Topaz Video AI + Real-ESRGAN（备用）

#### 2.1 功能清单

| 功能 | 说明 | 模型 |
|------|------|------|
| 超分辨率 | 提升分辨率（2x/4x） | Proteus / Gaia / Real-ESRGAN |
| 帧插值 | 提升帧率（24→60/120fps） | Theia / RIFE |
| 降噪 | 去除视频噪点 | Artemis / BM3D |
| 去模糊 | 修复运动模糊/失焦 | Proteus / Real-ESRGAN |
| 去隔行 | 隔行扫描转逐行 | Topaz Deinterlace |
| 防抖 | 电子防抖稳定 | Topaz Stabilization |

#### 2.2 Topaz Video AI CLI封装

```python
import subprocess
import json
from pathlib import Path
from enum import Enum
from dataclasses import dataclass

class EnhanceModel(str, Enum):
    PROTEUS = "Proteus"      # 综合画质增强
    ARTEMIS = "Artemis"      # 降噪为主
    GAIA = "Gaia"            # 超分辨率
    THEIA = "Theia"          # 帧插值

@dataclass
class EnhanceConfig:
    """增强配置"""
    model: EnhanceModel = EnhanceModel.PROTEUS
    scale: float = 2.0
    target_fps: int = None
    denoise: int = 50       # 0-100
    deblur: int = 30        # 0-100
    deblock: int = 20       # 0-100
    dehalo: int = 10        # 0-100
    recover_detail: int = 40  # 0-100
    sharpen: int = 30       # 0-100

class TopazEnhancer:
    """Topaz Video AI 增强器"""
    
    def __init__(self, topaz_cli_path: str = None):
        self.cli_path = topaz_cli_path or self._detect_topaz()
    
    def _detect_topaz(self) -> str:
        """检测Topaz安装路径"""
        possible_paths = [
            r"C:\Program Files\Topaz Labs LLC\Topaz Video AI\Topaz Video AI.exe",
            r"C:\Program Files (x86)\Topaz Labs LLC\Topaz Video AI\TVAI.exe",
            "/Applications/Topaz Video AI.app/Contents/MacOS/Topaz Video AI",
        ]
        for path in possible_paths:
            if Path(path).exists():
                return path
        return "topaz-video-ai"
    
    def enhance(self, input_path: str, output_path: str,
                config: EnhanceConfig = None) -> bool:
        """增强视频"""
        config = config or EnhanceConfig()
        
        cmd = [
            self.cli_path,
            "-i", input_path,
            "-o", output_path,
            "-m", config.model.value,
            "-s", str(config.scale),
        ]
        
        if config.target_fps:
            cmd.extend(["-f", str(config.target_fps)])
        
        # 高级参数
        cmd.extend([
            "--denoise", str(config.denoise),
            "--deblur", str(config.deblur),
            "--deblock", str(config.deblock),
            "--dehalo", str(config.dehalo),
            "--recover-detail", str(config.recover_detail),
            "--sharpen", str(config.sharpen),
            "--auto", "true",
        ])
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3600  # 1小时超时
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
    
    def batch_enhance(self, tasks: list, max_workers: int = 2) -> list:
        """批量增强"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for task in tasks:
                future = executor.submit(
                    self.enhance,
                    task["input"],
                    task["output"],
                    task.get("config")
                )
                futures[future] = task
            
            for future in as_completed(futures):
                task = futures[future]
                results.append({
                    "input": task["input"],
                    "output": task["output"],
                    "success": future.result()
                })
        
        return results
```

#### 2.3 输出数据格式

```json
{
  "enhanced_path": "/path/to/enhanced.mp4",
  "model": "Proteus",
  "scale": 2.0,
  "target_fps": 60,
  "original_resolution": [1920, 1080],
  "enhanced_resolution": [3840, 2160],
  "processing_time": 120.5,
  "quality_improvement": 0.35,
  "fallback_used": false
}
```

---

### 步骤3：语音识别与字幕生成

**引擎**：FunASR（阿里开源）

#### 3.1 功能清单

| 功能 | 说明 | 模型 |
|------|------|------|
| 语音转文字 | 中文长视频语音识别 | paraformer-large |
| 时间戳对齐 | 逐字/逐句时间戳 | 自带时间戳模型 |
| 标点符号恢复 | 自动添加标点符号 | ct-punctuator |
| 说话人分离 | 多人对话识别 | cam++ |
| 字幕生成 | SRT/VTT/ASS格式输出 | 后处理生成 |

#### 3.2 FunASR Python封装

```python
from funasr import AutoModel
from dataclasses import dataclass, field
from typing import List, Optional
import json
import srt
from datetime import timedelta

@dataclass
class WordTimestamp:
    """单字时间戳"""
    text: str
    start: float  # 秒
    end: float
    confidence: float

@dataclass
class SentenceTimestamp:
    """句子时间戳"""
    text: str
    start: float
    end: float
    speaker: int = 0
    words: List[WordTimestamp] = field(default_factory=list)

@dataclass
class ASRResult:
    """ASR识别结果"""
    full_text: str
    sentences: List[SentenceTimestamp]
    language: str = "zh-CN"
    processing_time: float = 0.0
    confidence: float = 0.0

class FunASRProcessor:
    """FunASR语音识别处理器"""
    
    def __init__(self, model_dir: str = None, device: str = "cuda"):
        """
        初始化FunASR
        model_dir: 模型缓存目录，None则使用默认
        device: cuda / cpu
        """
        # 初始化语音识别模型（带时间戳）
        self.asr_model = AutoModel(
            model="paraformer-zh",
            model_revision="v2.0.4",
            device=device,
            disable_update=True,
        )
        
        # 初始化标点模型
        self.punc_model = AutoModel(
            model="ct-punc",
            device=device,
            disable_update=True,
        )
        
        # 初始化说话人分离模型（可选）
        self.speaker_model = AutoModel(
            model="cam++",
            device=device,
            disable_update=True,
        )
    
    def transcribe(self, audio_path: str, 
                   with_timestamps: bool = True,
                   with_punctuation: bool = True,
                   with_speaker: bool = False) -> ASRResult:
        """
        语音识别
        
        Args:
            audio_path: 音频文件路径（支持wav/mp3/m4a等）
            with_timestamps: 是否返回时间戳
            with_punctuation: 是否添加标点
            with_speaker: 是否说话人分离
        """
        import time
        start_time = time.time()
        
        # 第一步：基础识别
        asr_result = self.asr_model.generate(
            input=audio_path,
            batch_size_s=300,
            cache={},
        )
        
        if not asr_result:
            return ASRResult(full_text="", sentences=[])
        
        # 提取结果
        result_data = asr_result[0]
        full_text = result_data.get("text", "")
        
        # 第二步：时间戳处理
        sentences = []
        if with_timestamps and "timestamp" in result_data:
            sentences = self._parse_timestamps(result_data["timestamp"])
        else:
            # 无时间戳时，整句作为一个句子
            sentences = [SentenceTimestamp(
                text=full_text,
                start=0.0,
                end=0.0,
            )]
        
        # 第三步：标点恢复
        if with_punctuation:
            full_text, sentences = self._add_punctuation(full_text, sentences)
        
        # 第四步：说话人分离
        if with_speaker:
            sentences = self._speaker_diarization(audio_path, sentences)
        
        # 计算置信度
        confidence = self._calculate_confidence(sentences)
        
        processing_time = time.time() - start_time
        
        return ASRResult(
            full_text=full_text,
            sentences=sentences,
            processing_time=processing_time,
            confidence=confidence,
        )
    
    def _parse_timestamps(self, timestamp_data) -> List[SentenceTimestamp]:
        """解析时间戳数据"""
        sentences = []
        
        # FunASR返回的是逐字时间戳，需要合并为句子
        words = []
        for item in timestamp_data:
            words.append(WordTimestamp(
                text=item[0],
                start=item[1] / 1000.0,  # ms → s
                end=item[2] / 1000.0,
                confidence=item[3] if len(item) > 3 else 1.0,
            ))
        
        # 简单的句子分割（按标点或停顿）
        current_sentence_words = []
        current_sentence_start = words[0].start if words else 0.0
        
        for i, word in enumerate(words):
            current_sentence_words.append(word)
            
            # 判断是否句子结束（标点或长停顿）
            is_pause = False
            if i < len(words) - 1:
                gap = words[i+1].start - word.end
                is_pause = gap > 0.3  # 300ms以上停顿
            
            is_end_punct = word.text in "。！？.!?"
            
            if is_pause or is_end_punct or i == len(words) - 1:
                sentence = SentenceTimestamp(
                    text="".join(w.text for w in current_sentence_words),
                    start=current_sentence_start,
                    end=word.end,
                    words=current_sentence_words.copy(),
                )
                sentences.append(sentence)
                current_sentence_words = []
                if i < len(words) - 1:
                    current_sentence_start = words[i+1].start
        
        return sentences
    
    def _add_punctuation(self, text: str, sentences: List[SentenceTimestamp]):
        """添加标点符号"""
        punc_result = self.punc_model.generate(input=text)
        
        if punc_result and "text" in punc_result[0]:
            punctuated_text = punc_result[0]["text"]
            
            # 简单策略：把标点插入到对应的句子末尾
            # 更复杂的实现需要字级对齐
            return punctuated_text, sentences
        
        return text, sentences
    
    def _speaker_diarization(self, audio_path: str, 
                            sentences: List[SentenceTimestamp]) -> List[SentenceTimestamp]:
        """说话人分离"""
        spk_result = self.speaker_model.generate(
            input=audio_path,
            cache={},
        )
        
        if spk_result and "spk" in spk_result[0]:
            spk_info = spk_result[0]["spk"]
            # 将说话人信息映射到句子
            # 此处为简化实现，实际需要时间对齐
            for i, sentence in enumerate(sentences):
                sentence.speaker = i % 2  # 占位
        
        return sentences
    
    def _calculate_confidence(self, sentences: List[SentenceTimestamp]) -> float:
        """计算整体置信度"""
        if not sentences:
            return 0.0
        
        all_confidences = []
        for sentence in sentences:
            for word in sentence.words:
                all_confidences.append(word.confidence)
        
        return sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
    
    def export_srt(self, result: ASRResult, output_path: str,
                   max_chars_per_line: int = 20) -> bool:
        """导出SRT字幕"""
        srt_subtitles = []
        index = 1
        
        for sentence in result.sentences:
            # 长句分行
            text = sentence.text
            lines = []
            while len(text) > max_chars_per_line:
                # 在最近的标点或空格处断行
                split_pos = max_chars_per_line
                for i in range(max_chars_per_line, max_chars_per_line // 2, -1):
                    if text[i] in "，。、；：！？,.;:!？ ":
                        split_pos = i + 1
                        break
                lines.append(text[:split_pos])
                text = text[split_pos:]
            if text:
                lines.append(text)
            
            subtitle = srt.Subtitle(
                index=index,
                start=timedelta(seconds=sentence.start),
                end=timedelta(seconds=sentence.end),
                content="\n".join(lines),
            )
            srt_subtitles.append(subtitle)
            index += 1
        
        try:
            srt_content = srt.compose(srt_subtitles)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            return True
        except Exception:
            return False
    
    def export_vtt(self, result: ASRResult, output_path: str) -> bool:
        """导出WebVTT字幕"""
        # 转换为VTT格式
        ...
```

#### 3.3 输出数据格式

```json
{
  "asr_result": {
    "full_text": "这是完整的识别文本...",
    "language": "zh-CN",
    "confidence": 0.92,
    "processing_time": 15.3,
    "sentences": [
      {
        "text": "第一句话",
        "start": 0.5,
        "end": 3.2,
        "speaker": 0,
        "words": [
          {"text": "第", "start": 0.5, "end": 0.7, "confidence": 0.95},
          {"text": "一", "start": 0.7, "end": 0.9, "confidence": 0.93},
        ]
      }
    ]
  },
  "srt_path": "/path/to/subtitle.srt",
  "vtt_path": "/path/to/subtitle.vtt"
}
```

---

### 步骤4：音频分析

**引擎**：librosa + torchaudio

#### 4.1 功能清单

| 功能 | 说明 | 算法 |
|------|------|------|
| BPM检测 | 每分钟节拍数 | librosa.beat.beat_track |
| 节拍网格 | 精确的节拍位置 | librosa.beat.beat_track + 后处理 |
| 段落分割 | 副歌/主歌/间奏等 | 结构分析算法 |
| 能量曲线 | 逐帧响度/能量 | RMS / 频谱质心 |
| 频谱特征 | 梅尔频谱/色度/对比度 | librosa.feature.* |
| 情绪分析 | Valence-Arousal模型 | 预训练模型 + 规则 |
| 关键节拍点 | 重音/转场点检测 | Onset detection + 峰值检测 |
| 人声检测 | 人声/伴奏分离 | HPSS / 预训练模型 |

#### 4.2 核心实现

```python
import librosa
import numpy as np
import torchaudio
from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class AudioFeatures:
    """音频特征数据类"""
    duration: float
    sample_rate: int
    bpm: float
    beat_times: List[float]
    downbeats: List[float]
    energy_curve: np.ndarray  # 逐帧能量
    energy_frame_times: List[float]
    segments: List[dict]  # 段落分割
    valence: float  # 情绪效价 0-1
    arousal: float  # 情绪唤起度 0-1
    key: str  # 调性
    tempo_confidence: float
    vocal_segments: List[Tuple[float, float]]  # 人声片段

class AudioAnalyzer:
    """音频分析器"""
    
    def __init__(self, sample_rate: int = 22050, hop_length: int = 512):
        self.sample_rate = sample_rate
        self.hop_length = hop_length
    
    def load_audio(self, audio_path: str, 
                   mono: bool = True) -> Tuple[np.ndarray, int]:
        """加载音频"""
        y, sr = librosa.load(audio_path, sr=self.sample_rate, mono=mono)
        return y, sr
    
    def analyze_full(self, audio_path: str) -> AudioFeatures:
        """完整音频分析"""
        y, sr = self.load_audio(audio_path)
        duration = librosa.get_duration(y=y, sr=sr)
        
        # 1. BPM和节拍检测
        tempo, beat_frames = librosa.beat.beat_track(
            y=y, sr=sr, hop_length=self.hop_length
        )
        beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
        
        # 2. 重拍检测（简化：每4拍为重拍）
        downbeat_indices = list(range(0, len(beat_times), 4))
        downbeats = [beat_times[i] for i in downbeat_indices 
                    if i < len(beat_times)]
        
        # 3. 能量曲线（RMS）
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)[0]
        energy_frame_times = librosa.frames_to_time(
            range(len(rms)), sr=sr, hop_length=self.hop_length
        ).tolist()
        
        # 4. 调性检测
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        key = self._detect_key(chroma)
        
        # 5. 段落分割（简化：基于能量变化）
        segments = self._segment_audio(y, sr, rms, beat_times)
        
        # 6. 情绪分析（Valence-Arousal）
        valence, arousal = self._analyze_emotion(y, sr)
        
        # 7. 人声检测（HPSS简单分离）
        vocal_segments = self._detect_vocal(y, sr)
        
        # 8. 节拍置信度
        tempo_confidence = self._calculate_tempo_confidence(y, sr, tempo)
        
        return AudioFeatures(
            duration=duration,
            sample_rate=sr,
            bpm=float(tempo),
            beat_times=beat_times,
            downbeats=downbeats,
            energy_curve=rms,
            energy_frame_times=energy_frame_times,
            segments=segments,
            valence=valence,
            arousal=arousal,
            key=key,
            tempo_confidence=tempo_confidence,
            vocal_segments=vocal_segments,
        )
    
    def _detect_key(self, chroma: np.ndarray) -> str:
        """检测调性（简化版）"""
        # 计算平均色度
        avg_chroma = np.mean(chroma, axis=1)
        
        # 12个大调音阶模板
        major_template = np.array([1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1])
        # 12个小调音阶模板
        minor_template = np.array([1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0])
        
        note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 
                      'F#', 'G', 'G#', 'A', 'A#', 'B']
        
        best_key = ""
        best_score = -1
        
        for i in range(12):
            # 旋转模板
            major_rotated = np.roll(major_template, i)
            minor_rotated = np.roll(minor_template, i)
            
            major_score = np.corrcoef(avg_chroma, major_rotated)[0, 1]
            minor_score = np.corrcoef(avg_chroma, minor_rotated)[0, 1]
            
            if major_score > best_score:
                best_score = major_score
                best_key = f"{note_names[i]} Major"
            if minor_score > best_score:
                best_score = minor_score
                best_key = f"{note_names[i]} Minor"
        
        return best_key
    
    def _segment_audio(self, y: np.ndarray, sr: int,
                       rms: np.ndarray, beat_times: List[float]) -> List[dict]:
        """音频段落分割（简化版）"""
        # 基于能量变化的简单分割
        # 实际项目可使用更复杂的算法（如结构相似性矩阵）
        
        # 计算能量的一阶差分
        energy_diff = np.diff(rms)
        energy_diff = np.abs(energy_diff)
        
        # 找峰值（段落变化点）
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(energy_diff, height=np.mean(energy_diff) * 2, 
                              distance=sr // self.hop_length * 5)  # 最小5秒间隔
        
        segments = []
        prev_time = 0.0
        
        for peak in peaks:
            peak_time = peak * self.hop_length / sr
            if peak_time - prev_time > 5:  # 至少5秒一段
                # 计算该段落的平均能量和类型
                segment_rms = rms[int(prev_time * sr / self.hop_length):
                                 int(peak_time * sr / self.hop_length)]
                avg_energy = float(np.mean(segment_rms))
                
                segment_type = self._classify_segment(avg_energy, rms)
                
                segments.append({
                    "start": prev_time,
                    "end": peak_time,
                    "type": segment_type,  # intro/verse/chorus/outro等
                    "avg_energy": avg_energy,
                    "beats": self._count_beats_in_range(beat_times, prev_time, peak_time),
                })
                prev_time = peak_time
        
        # 最后一段
        duration = len(y) / sr
        if duration - prev_time > 3:
            segment_rms = rms[int(prev_time * sr / self.hop_length):]
            avg_energy = float(np.mean(segment_rms))
            segment_type = self._classify_segment(avg_energy, rms)
            
            segments.append({
                "start": prev_time,
                "end": duration,
                "type": segment_type,
                "avg_energy": avg_energy,
                "beats": self._count_beats_in_range(beat_times, prev_time, duration),
            })
        
        # 标记首尾
        if segments:
            segments[0]["type"] = "intro" if segments[0]["avg_energy"] < np.mean(rms) else "verse"
            segments[-1]["type"] = "outro"
        
        return segments
    
    def _classify_segment(self, avg_energy: float, 
                         all_energy: np.ndarray) -> str:
        """分类段落类型"""
        energy_min = np.min(all_energy)
        energy_max = np.max(all_energy)
        energy_range = energy_max - energy_min
        
        if energy_range == 0:
            return "verse"
        
        normalized = (avg_energy - energy_min) / energy_range
        
        if normalized < 0.2:
            return "intro"
        elif normalized < 0.5:
            return "verse"
        elif normalized < 0.8:
            return "chorus"
        else:
            return "drop"
    
    def _count_beats_in_range(self, beat_times: List[float],
                              start: float, end: float) -> int:
        """计算范围内的节拍数"""
        return sum(1 for t in beat_times if start <= t < end)
    
    def _analyze_emotion(self, y: np.ndarray, sr: int) -> Tuple[float, float]:
        """情绪分析（简化版，基于声学特征）"""
        # 提取特征
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        
        # 简单的规则映射
        # Valence（效价）：基于音色明亮度
        avg_centroid = np.mean(spectral_centroid)
        max_centroid = 8000  # 典型最大值
        valence = min(1.0, max(0.0, avg_centroid / max_centroid))
        
        # Arousal（唤起度）：基于能量和节奏
        rms = librosa.feature.rms(y=y)[0]
        avg_energy = np.mean(rms)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        
        energy_norm = min(1.0, avg_energy * 50)  # 经验系数
        tempo_norm = min(1.0, tempo / 180.0)
        arousal = (energy_norm * 0.6 + tempo_norm * 0.4)
        
        return float(valence), float(arousal)
    
    def _detect_vocal(self, y: np.ndarray, sr: int) -> List[Tuple[float, float]]:
        """人声检测（简化版，使用HPSS）"""
        # 谐波-冲击分离
        y_harmonic, y_percussive = librosa.effects.hpss(y)
        
        # 计算谐波部分的能量变化
        harmonic_rms = librosa.feature.rms(y=y_harmonic, 
                                           hop_length=self.hop_length)[0]
        
        # 简单阈值：谐波能量高于某个阈值且持续一定时间 → 可能有人声
        threshold = np.mean(harmonic_rms) * 0.5
        
        vocal_frames = harmonic_rms > threshold
        
        # 找连续的人声段
        segments = []
        in_vocal = False
        start_frame = 0
        
        for i, is_vocal in enumerate(vocal_frames):
            if is_vocal and not in_vocal:
                start_frame = i
                in_vocal = True
            elif not is_vocal and in_vocal:
                duration = (i - start_frame) * self.hop_length / sr
                if duration > 0.5:  # 至少0.5秒
                    start_time = start_frame * self.hop_length / sr
                    end_time = i * self.hop_length / sr
                    segments.append((start_time, end_time))
                in_vocal = False
        
        return segments
    
    def _calculate_tempo_confidence(self, y: np.ndarray, sr: int,
                                    tempo: float) -> float:
        """计算节拍检测置信度"""
        # 基于节拍自相关的强度
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        tempo_scores = librosa.feature.tempogram(
            onset_envelope=onset_env, sr=sr
        )
        
        # 找到对应tempo的分数
        # 简化：返回归一化分数
        return 0.85  # 占位值
```

#### 4.3 输出数据格式

```json
{
  "audio_features": {
    "duration": 180.5,
    "sample_rate": 22050,
    "bpm": 128.5,
    "tempo_confidence": 0.91,
    "key": "A Minor",
    "beat_times": [0.5, 1.0, 1.5, ...],
    "downbeats": [0.5, 2.5, 4.5, ...],
    "valence": 0.65,
    "arousal": 0.78,
    "segments": [
      {"start": 0.0, "end": 15.0, "type": "intro", "avg_energy": 0.02, "beats": 19},
      {"start": 15.0, "end": 45.0, "type": "verse", "avg_energy": 0.08, "beats": 38},
    ],
    "vocal_segments": [[10.0, 45.0], [60.0, 90.0]],
    "energy_curve_url": "/api/audio/energy?id=xxx"
  }
}
```

---

### 步骤5：镜头分割（双校验）

**引擎**：PySceneDetect + TransNetV2

#### 5.1 功能清单

| 功能 | 说明 | 引擎 |
|------|------|------|
| 阈值检测 | 基于帧差的简单检测 | PySceneDetect ContentDetector |
| 内容检测 | 基于内容相似度的检测 | PySceneDetect ThresholdDetector |
| 深度学习检测 | CNN-based转场检测 | TransNetV2 |
| 双校验融合 | 两种方法结果融合，提高准确率 | 融合算法 |
| 转场类型识别 | 切/叠化/淡入淡出/闪白 | TransNetV2 |
| 关键帧提取 | 每个镜头提取代表帧 | ffmpeg + 帧选择算法 |

#### 5.2 核心实现

```python
from scenedetect import open_video, SceneManager, ContentDetector, ThresholdDetector
import numpy as np
import cv2
from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum

class TransitionType(str, Enum):
    CUT = "cut"           # 硬切
    DISSOLVE = "dissolve"  # 叠化
    FADE_IN = "fade_in"    # 淡入
    FADE_OUT = "fade_out"  # 淡出
    FLASH = "flash"        # 闪白
    WIPE = "wipe"          # 擦除
    UNKNOWN = "unknown"

@dataclass
class Scene:
    """镜头数据类"""
    index: int
    start_time: float
    end_time: float
    duration: float
    start_frame: int
    end_frame: int
    frame_count: int
    transition_type: TransitionType
    transition_confidence: float
    keyframe_time: float  # 代表帧时间
    keyframe_path: str = ""
    avg_brightness: float = 0.0
    motion_intensity: float = 0.0

@dataclass
class SceneDetectionResult:
    """镜头分割结果"""
    scenes: List[Scene]
    total_scenes: int
    method: str  # pyscene / transnet / fusion
    processing_time: float
    average_scene_duration: float

class SceneDetector:
    """镜头分割器（双校验模式）"""
    
    def __init__(self, use_transnet: bool = True,
                 use_pyscenedetect: bool = True):
        self.use_transnet = use_transnet
        self.use_pyscenedetect = use_pyscenedetect
    
    def detect(self, video_path: str,
               threshold: float = 27.0,
               min_scene_len: float = 0.5) -> SceneDetectionResult:
        """
        检测镜头
        
        Args:
            video_path: 视频路径
            threshold: 检测阈值
            min_scene_len: 最小镜头长度（秒）
        """
        import time
        start_time = time.time()
        
        # 并行运行两种检测方法
        pyscene_scenes = []
        transnet_scenes = []
        
        if self.use_pyscenedetect:
            pyscene_scenes = self._detect_pyscenedetect(
                video_path, threshold, min_scene_len
            )
        
        if self.use_transnet:
            transnet_scenes = self._detect_transnet(video_path, min_scene_len)
        
        # 融合结果
        if self.use_pyscenedetect and self.use_transnet:
            fused_scenes = self._fuse_results(
                pyscene_scenes, transnet_scenes, video_path
            )
            method = "fusion"
        elif self.use_pyscenedetect:
            fused_scenes = pyscene_scenes
            method = "pyscenedetect"
        else:
            fused_scenes = transnet_scenes
            method = "transnet"
        
        # 计算统计
        if fused_scenes:
            avg_duration = np.mean([s.duration for s in fused_scenes])
        else:
            avg_duration = 0.0
        
        processing_time = time.time() - start_time
        
        return SceneDetectionResult(
            scenes=fused_scenes,
            total_scenes=len(fused_scenes),
            method=method,
            processing_time=processing_time,
            average_scene_duration=float(avg_duration),
        )
    
    def _detect_pyscenedetect(self, video_path: str,
                               threshold: float,
                               min_scene_len: float) -> List[Scene]:
        """PySceneDetect检测"""
        video = open_video(video_path)
        scene_manager = SceneManager()
        
        # 添加内容检测器
        scene_manager.add_detector(ContentDetector(
            threshold=threshold,
            min_scene_len=int(min_scene_len * video.frame_rate),
        ))
        
        # 添加阈值检测器（淡入淡出检测）
        scene_manager.add_detector(ThresholdDetector(
            threshold=12.0,
            min_scene_len=int(min_scene_len * video.frame_rate),
        ))
        
        # 执行检测
        scene_manager.detect_scenes(video=video)
        scene_list = scene_manager.get_scene_list()
        
        # 转换为Scene对象
        scenes = []
        for i, (start, end) in enumerate(scene_list):
            scene = Scene(
                index=i,
                start_time=start.get_seconds(),
                end_time=end.get_seconds(),
                duration=end.get_seconds() - start.get_seconds(),
                start_frame=start.get_frames(),
                end_frame=end.get_frames(),
                frame_count=end.get_frames() - start.get_frames(),
                transition_type=TransitionType.CUT,  # 简化
                transition_confidence=0.8,
                keyframe_time=start.get_seconds() + (end.get_seconds() - start.get_seconds()) / 2,
            )
            scenes.append(scene)
        
        return scenes
    
    def _detect_transnet(self, video_path: str,
                          min_scene_len: float) -> List[Scene]:
        """TransNetV2深度学习检测"""
        # TransNetV2集成
        # 实际使用需要安装transnetv2库
        try:
            from transnetv2 import TransNetV2
            
            model = TransNetV2()
            _, single_frame_predictions, _ = model.predict_video(video_path)
            
            # 找峰值
            predictions = self._find_peaks(single_frame_predictions)
            
            # 转换为镜头
            scenes = []
            prev_frame = 0
            
            # 获取视频信息
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            
            for frame_num, conf in predictions:
                duration_sec = (frame_num - prev_frame) / fps
                
                if duration_sec >= min_scene_len:
                    scene = Scene(
                        index=len(scenes),
                        start_time=prev_frame / fps,
                        end_time=frame_num / fps,
                        duration=duration_sec,
                        start_frame=prev_frame,
                        end_frame=frame_num,
                        frame_count=frame_num - prev_frame,
                        transition_type=TransitionType.CUT if conf > 0.7 else TransitionType.DISSOLVE,
                        transition_confidence=float(conf),
                        keyframe_time=(prev_frame + frame_num) / (2 * fps),
                    )
                    scenes.append(scene)
                    prev_frame = frame_num
            
            # 最后一段
            if total_frames - prev_frame > min_scene_len * fps:
                duration_sec = (total_frames - prev_frame) / fps
                scenes.append(Scene(
                    index=len(scenes),
                    start_time=prev_frame / fps,
                    end_time=total_frames / fps,
                    duration=duration_sec,
                    start_frame=prev_frame,
                    end_frame=total_frames,
                    frame_count=total_frames - prev_frame,
                    transition_type=TransitionType.UNKNOWN,
                    transition_confidence=0.5,
                    keyframe_time=(prev_frame + total_frames) / (2 * fps),
                ))
            
            return scenes
            
        except ImportError:
            # TransNetV2未安装，返回空
            return []
    
    def _find_peaks(self, predictions: np.ndarray,
                    threshold: float = 0.5,
                    min_distance: int = 10) -> List[Tuple[int, float]]:
        """找预测峰值"""
        from scipy.signal import find_peaks
        
        peaks, properties = find_peaks(
            predictions,
            height=threshold,
            distance=min_distance,
        )
        
        return [(int(p), float(properties["peak_heights"][i])) 
                for i, p in enumerate(peaks)]
    
    def _fuse_results(self, pyscene_scenes: List[Scene],
                      transnet_scenes: List[Scene],
                      video_path: str) -> List[Scene]:
        """融合两种检测结果"""
        # 如果只有一种结果，直接返回
        if not pyscene_scenes:
            return transnet_scenes
        if not transnet_scenes:
            return pyscene_scenes
        
        # 简单融合策略：
        # 1. 以TransNet结果为基础（更准确）
        # 2. 用PySceneDetect结果验证，补充遗漏的镜头
        # 3. 时间差在阈值内的合并
        
        time_threshold = 0.1  # 100ms以内视为同一转场
        
        # 收集所有转场点
        all_transitions = []
        
        for scene in pyscene_scenes[1:]:  # 第一个不是转场
            all_transitions.append(("pyscene", scene.start_time, scene.transition_confidence))
        
        for scene in transnet_scenes[1:]:
            all_transitions.append(("transnet", scene.start_time, scene.transition_confidence))
        
        # 按时间排序
        all_transitions.sort(key=lambda x: x[1])
        
        # 合并相近的转场点
        merged_transitions = []
        for source, time, conf in all_transitions:
            if not merged_transitions:
                merged_transitions.append([time, conf, source])
            else:
                last_time, last_conf, last_source = merged_transitions[-1]
                if abs(time - last_time) < time_threshold:
                    # 合并：取置信度高的
                    if conf > last_conf:
                        merged_transitions[-1] = [time, conf, f"{last_source}+{source}"]
                else:
                    merged_transitions.append([time, conf, source])
        
        # 生成最终镜头列表
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        total_duration = total_frames / fps
        cap.release()
        
        final_scenes = []
        prev_time = 0.0
        
        for i, (time, conf, source) in enumerate(merged_transitions):
            duration = time - prev_time
            
            scene = Scene(
                index=i,
                start_time=prev_time,
                end_time=time,
                duration=duration,
                start_frame=int(prev_time * fps),
                end_frame=int(time * fps),
                frame_count=int(duration * fps),
                transition_type=TransitionType.CUT,
                transition_confidence=float(conf),
                keyframe_time=prev_time + duration / 2,
            )
            final_scenes.append(scene)
            prev_time = time
        
        # 最后一段
        if total_duration - prev_time > 0.3:
            duration = total_duration - prev_time
            final_scenes.append(Scene(
                index=len(final_scenes),
                start_time=prev_time,
                end_time=total_duration,
                duration=duration,
                start_frame=int(prev_time * fps),
                end_frame=total_frames,
                frame_count=total_frames - int(prev_time * fps),
                transition_type=TransitionType.UNKNOWN,
                transition_confidence=0.5,
                keyframe_time=prev_time + duration / 2,
            ))
        
        return final_scenes
    
    def extract_keyframes(self, video_path: str, scenes: List[Scene],
                          output_dir: str) -> List[str]:
        """提取每个镜头的关键帧"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        keyframe_paths = []
        cap = cv2.VideoCapture(video_path)
        
        for i, scene in enumerate(scenes):
            # 跳到中间帧
            mid_frame = int((scene.start_frame + scene.end_frame) / 2)
            cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
            
            ret, frame = cap.read()
            if ret:
                path = os.path.join(output_dir, f"scene_{i:04d}.jpg")
                cv2.imwrite(path, frame)
                keyframe_paths.append(path)
                scene.keyframe_path = path
            else:
                keyframe_paths.append("")
        
        cap.release()
        return keyframe_paths
```

---

### 步骤6：主体检测（YOLO-World）

**引擎**：YOLO-World

#### 6.1 功能清单

| 功能 | 说明 | 模型 |
|------|------|------|
| 人物检测 | 检测视频中的人体框 | YOLO-World v2 xl |
| 开放词汇检测 | 自定义类别检测（指定任意词汇） | YOLO-World |
| 批量处理 | 逐帧/抽帧检测 | 优化推理 |
| 跟踪关联 | 跨帧ID关联（简单卡尔曼） | SORT/ByteTrack |
| 关键人物识别 | 选择最大/中心人物 | 后处理 |
| 数据格式转换 | 输出COCO/VOC/自定义格式 | 格式转换 |

#### 6.2 核心实现

```python
import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Tuple
from ultralytics import YOLO

@dataclass
class BoundingBox:
    """边界框"""
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_name: str
    track_id: int = -1

@dataclass
class FrameDetections:
    """帧检测结果"""
    frame_index: int
    timestamp: float
    boxes: List[BoundingBox]

@dataclass
class DetectionResult:
    """检测结果"""
    video_path: str
    total_frames: int
    detections: List[FrameDetections]
    classes: List[str]
    processing_time: float
    avg_detections_per_frame: float

class YOLOWorldDetector:
    """YOLO-World开放词汇目标检测器"""
    
    def __init__(self, model_path: str = "yolov8x-worldv2.pt",
                 device: str = "cuda",
                 conf_threshold: float = 0.3):
        self.model = YOLO(model_path)
        self.device = device
        self.conf_threshold = conf_threshold
    
    def set_classes(self, classes: List[str]):
        """设置检测类别（开放词汇）"""
        # YOLO-World支持设置自定义类别
        self.model.set_classes(classes)
    
    def detect_video(self, video_path: str,
                     classes: List[str] = None,
                     sample_fps: float = 5.0,
                     track: bool = True) -> DetectionResult:
        """
        检测视频中的目标
        
        Args:
            video_path: 视频路径
            classes: 检测类别列表（None则使用默认）
            sample_fps: 采样帧率（每秒检测多少帧）
            track: 是否启用跟踪
        """
        import time
        start_time = time.time()
        
        if classes:
            self.set_classes(classes)
        
        cap = cv2.VideoCapture(video_path)
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # 计算采样间隔
        sample_interval = max(1, int(video_fps / sample_fps))
        
        all_detections = []
        frame_idx = 0
        
        # 跟踪器初始化（如果启用）
        tracker = self._init_tracker() if track else None
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 采样检测
            if frame_idx % sample_interval == 0:
                timestamp = frame_idx / video_fps
                
                # YOLO推理
                results = self.model.predict(
                    frame,
                    conf=self.conf_threshold,
                    device=self.device,
                    verbose=False,
                )
                
                # 解析结果
                boxes = []
                for result in results:
                    for box in result.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        cls_name = result.names[cls_id]
                        
                        boxes.append(BoundingBox(
                            x1=float(x1),
                            y1=float(y1),
                            x2=float(x2),
                            y2=float(y2),
                            confidence=confidence,
                            class_name=cls_name,
                        ))
                
                # 如果启用跟踪
                if track and tracker is not None:
                    boxes = self._update_tracker(tracker, boxes, frame)
                
                all_detections.append(FrameDetections(
                    frame_index=frame_idx,
                    timestamp=timestamp,
                    boxes=boxes,
                ))
            
            frame_idx += 1
        
        cap.release()
        
        # 统计
        total_detections = sum(len(d.boxes) for d in all_detections)
        avg_detections = total_detections / len(all_detections) if all_detections else 0
        
        processing_time = time.time() - start_time
        
        return DetectionResult(
            video_path=video_path,
            total_frames=total_frames,
            detections=all_detections,
            classes=classes or [],
            processing_time=processing_time,
            avg_detections_per_frame=avg_detections,
        )
    
    def _init_tracker(self):
        """初始化跟踪器（ByteTrack）"""
        try:
            from norfair import Tracker
            return Tracker(
                distance_function="iou",
                distance_threshold=0.3,
            )
        except ImportError:
            return None
    
    def _update_tracker(self, tracker, boxes: List[BoundingBox],
                        frame: np.ndarray) -> List[BoundingBox]:
        """更新跟踪器"""
        # 简化：不集成完整的ByteTrack，直接给每个框分配临时ID
        # 实际项目建议使用ByteTrack/SORT等专业跟踪器
        
        # 简单的帧间关联（基于IOU）
        if not hasattr(self, '_prev_boxes'):
            self._prev_boxes = []
            self._next_id = 0
        
        # 为每个当前框找最近的上一帧框
        for box in boxes:
            best_iou = 0
            best_id = -1
            
            for prev_box in self._prev_boxes:
                iou = self._calculate_iou(box, prev_box)
                if iou > best_iou and iou > 0.3:
                    best_iou = iou
                    best_id = prev_box.track_id
            
            if best_id >= 0:
                box.track_id = best_id
            else:
                box.track_id = self._next_id
                self._next_id += 1
        
        self._prev_boxes = boxes
        return boxes
    
    def _calculate_iou(self, box1: BoundingBox, box2: BoundingBox) -> float:
        """计算IOU"""
        x1 = max(box1.x1, box2.x1)
        y1 = max(box1.y1, box2.y1)
        x2 = min(box1.x2, box2.x2)
        y2 = min(box1.y2, box2.y2)
        
        if x2 <= x1 or y2 <= y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        area1 = (box1.x2 - box1.x1) * (box1.y2 - box1.y1)
        area2 = (box2.x2 - box2.x1) * (box2.y2 - box2.y1)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def get_person_boxes(self, result: DetectionResult,
                          person_class: str = "person") -> List[FrameDetections]:
        """提取人物检测结果"""
        person_detections = []
        
        for frame_det in result.detections:
            person_boxes = [
                box for box in frame_det.boxes
                if box.class_name.lower() == person_class.lower()
            ]
            if person_boxes:
                person_detections.append(FrameDetections(
                    frame_index=frame_det.frame_index,
                    timestamp=frame_det.timestamp,
                    boxes=person_boxes,
                ))
        
        return person_detections
    
    def get_main_person(self, result: DetectionResult,
                        frame_width: int,
                        frame_height: int) -> List[Tuple[int, BoundingBox]]:
        """获取每帧的主要人物（最大/最中心）"""
        main_persons = []
        
        for frame_det in result.detections:
            person_boxes = [
                box for box in frame_det.boxes
                if box.class_name.lower() == "person"
            ]
            
            if person_boxes:
                # 选择面积最大的
                main_box = max(person_boxes, 
                             key=lambda b: (b.x2 - b.x1) * (b.y2 - b.y1))
                main_persons.append((frame_det.frame_index, main_box))
        
        return main_persons
    
    def export_for_roto(self, result: DetectionResult,
                        output_path: str,
                        class_name: str = "person") -> bool:
        """导出为Roto可用的格式（JSON边界框序列）"""
        import json
        
        roto_data = {
            "type": "bounding_box_sequence",
            "class": class_name,
            "frames": []
        }
        
        for frame_det in result.detections:
            target_boxes = [
                {
                    "x1": box.x1,
                    "y1": box.y1,
                    "x2": box.x2,
                    "y2": box.y2,
                    "confidence": box.confidence,
                    "track_id": box.track_id,
                }
                for box in frame_det.boxes
                if box.class_name.lower() == class_name.lower()
            ]
            
            if target_boxes:
                roto_data["frames"].append({
                    "frame_index": frame_det.frame_index,
                    "timestamp": frame_det.timestamp,
                    "boxes": target_boxes,
                })
        
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(roto_data, f, indent=2)
            return True
        except Exception:
            return False
```

#### 6.3 输出数据格式

```json
{
  "detection_result": {
    "video_path": "/path/to/video.mp4",
    "total_frames": 1800,
    "classes": ["person", "face", "hand"],
    "processing_time": 15.2,
    "avg_detections_per_frame": 2.3,
    "detections": [
      {
        "frame_index": 0,
        "timestamp": 0.0,
        "boxes": [
          {
            "x1": 100.5,
            "y1": 50.2,
            "x2": 300.8,
            "y2": 450.3,
            "confidence": 0.92,
            "class_name": "person",
            "track_id": 0
          }
        ]
      }
    ]
  },
  "main_person_track_id": 0,
  "roto_boxes_path": "/path/to/roto_boxes.json"
}
```

---

### 步骤7：人像初筛抠像（RVM）

**引擎**：Robust Video Matting (RVM)

#### 7.1 功能清单

| 功能 | 说明 | 模型 |
|------|------|------|
| 人像抠图 | 视频人物Alpha通道提取 | rvm_resnet50 / mobilenetv3 |
| 时序稳定 | 利用视频时序减少闪烁 | RVM循环结构 |
| 批量处理 | GPU加速批量推理 | PyTorch DataLoader |
| 多格式输出 | PNG序列 / EXR序列 / 视频Alpha通道 | ffmpeg后处理 |
| 边缘优化 | 可选边缘后处理 | 形态学操作 + 模糊 |
| 质量评估 | 自动评估蒙版质量 | 边缘锐度 + 时序稳定性 |

#### 7.2 核心实现

```python
import torch
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class MatteResult:
    """抠图结果"""
    video_path: str
    output_path: str
    output_format: str  # png_sequence / exr_sequence / video_with_alpha
    total_frames: int
    processing_time: float
    quality_score: float
    edge_quality: float
    temporal_stability: float

class RVMMatting:
    """RVM视频抠图处理器"""
    
    def __init__(self, model_type: str = "mobilenetv3",
                 device: str = "cuda",
                 dtype: torch.dtype = torch.float16):
        """
        初始化RVM模型
        
        Args:
            model_type: resnet50 / mobilenetv3
            device: cuda / cpu
            dtype: float32 / float16
        """
        self.device = device
        self.dtype = dtype
        
        # 加载模型
        # 实际使用需要从robust-video-matting导入
        # 这里是简化实现
        self.model = self._load_model(model_type)
        self.model.eval().to(device=device, dtype=dtype)
    
    def _load_model(self, model_type: str):
        """加载RVM模型"""
        try:
            from rvm import MattingNetwork
            model = MattingNetwork(model_type).eval()
            
            # 加载权重
            model.load_state_dict(torch.load(
                f"rvm_{model_type}.pth", 
                map_location="cpu"
            ))
            return model
        except ImportError:
            # 如果没有RVM库，返回占位
            print("警告：RVM库未安装，使用模拟模式")
            return None
    
    def matting_video(self, video_path: str,
                      output_dir: str,
                      output_format: str = "png_sequence",
                      downsample_ratio: float = 1.0,
                      batch_size: int = 1) -> MatteResult:
        """
        视频抠像
        
        Args:
            video_path: 输入视频路径
            output_dir: 输出目录
            output_format: png_sequence / exr_sequence / video_with_alpha
            downsample_ratio: 下采样比例（加速）
            batch_size: 批处理大小
        """
        import time
        start_time = time.time()
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 读取视频
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # RVM的循环状态
        rec = [None] * 4
        
        frame_idx = 0
        quality_scores = []
        prev_alpha = None
        stability_scores = []
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 预处理
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb = torch.from_numpy(rgb).permute(2, 0, 1).float() / 255.0
            rgb = rgb.unsqueeze(0).to(device=self.device, dtype=self.dtype)
            
            # 推理
            if self.model is not None:
                with torch.no_grad():
                    fgr, pha, *rec = self.model(
                        rgb, *rec, downsample_ratio
                    )
                
                alpha = pha[0, 0].cpu().numpy()
            else:
                # 模拟模式：返回简单的中心渐变
                alpha = np.zeros((height, width), dtype=np.float32)
                center_y, center_x = height // 2, width // 2
                Y, X = np.ogrid[:height, :width]
                dist = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
                max_dist = min(height, width) / 2
                alpha = np.clip(1 - dist / max_dist, 0, 1)
            
            # 保存
            if output_format == "png_sequence":
                output_path = str(Path(output_dir) / f"alpha_{frame_idx:06d}.png")
                
                # 保存为RGBA或单独的Alpha图
                alpha_uint8 = (alpha * 255).astype(np.uint8)
                cv2.imwrite(output_path, alpha_uint8)
            
            elif output_format == "video_with_alpha":
                # 将Alpha合成到视频中
                output_frame = frame.copy()
                output_frame[:, :, 3] = alpha_uint8  # 需要4通道
                # ... 写入视频
            
            # 质量评估
            edge_quality = self._evaluate_edge_quality(alpha)
            quality_scores.append(edge_quality)
            
            # 时序稳定性
            if prev_alpha is not None:
                stability = 1.0 - np.mean(np.abs(alpha - prev_alpha))
                stability_scores.append(stability)
            prev_alpha = alpha.copy()
            
            frame_idx += 1
        
        cap.release()
        
        # 计算综合质量分数
        avg_quality = np.mean(quality_scores) if quality_scores else 0.0
        avg_stability = np.mean(stability_scores) if stability_scores else 0.0
        overall_score = avg_quality * 0.6 + avg_stability * 0.4
        
        processing_time = time.time() - start_time
        
        return MatteResult(
            video_path=video_path,
            output_path=output_dir,
            output_format=output_format,
            total_frames=total_frames,
            processing_time=processing_time,
            quality_score=float(overall_score),
            edge_quality=float(avg_quality),
            temporal_stability=float(avg_stability),
        )
    
    def _evaluate_edge_quality(self, alpha: np.ndarray) -> float:
        """评估边缘质量"""
        # 计算梯度（边缘清晰度）
        grad_x = cv2.Sobel(alpha, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(alpha, cv2.CV_32F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
        
        # 边缘区域的平均梯度（越锐利越好，但不能有锯齿）
        edge_mask = (alpha > 0.05) & (alpha < 0.95)
        
        if np.sum(edge_mask) == 0:
            return 0.5
        
        avg_edge_grad = np.mean(gradient_magnitude[edge_mask])
        
        # 归一化：0.01以下很差，0.1以上很好
        quality = min(1.0, max(0.0, avg_edge_grad / 0.1))
        
        return float(quality)
    
    def refine_edge(self, alpha: np.ndarray, 
                    method: str = "guided_filter") -> np.ndarray:
        """边缘优化"""
        if method == "guided_filter":
            # 引导滤波（需要原图作为引导）
            # 简化实现
            from scipy.ndimage import gaussian_filter
            smoothed = gaussian_filter(alpha, sigma=1.0)
            return np.clip(smoothed, 0, 1)
        
        elif method == "morphology":
            # 形态学操作
            kernel = np.ones((3, 3), np.uint8)
            refined = cv2.morphologyEx(
                alpha.astype(np.float32),
                cv2.MORPH_CLOSE,
                kernel,
            )
            return refined
        
        return alpha
    
    def generate_composite(self, video_path: str,
                           alpha_dir: str,
                           background_color: Tuple[int, int, int] = (0, 255, 0),
                           output_path: str = None) -> str:
        """生成合成预览视频（绿幕/纯色背景）"""
        # 读取Alpha序列，和原视频合成
        ...
```

---

### 步骤8-9：进阶功能（P1）

#### InternVL2 画面语义理解

```python
# 功能：场景描述、主体属性识别、画面风格分析
# 输出：每镜头的文本描述、标签、属性
# 用于：风格化参数自动推荐、场景分类
```

#### SAM2Matting 精细抠像

```python
# 功能：通用视频精细抠图（支持任意类别，不限于人像）
# 优势：发丝级精度、半透明物体支持
# 用途：复杂场景的蒙版精修，作为Silhouette前置
```

---

### 步骤10：数据融合与质量校验

#### 10.1 统一输出格式

```python
import json
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class PreprocessResult:
    """预处理最终结果（统一格式）"""
    # 基础信息
    video_path: str
    standardized_path: str
    proxy_path: str
    video_info: dict
    
    # 画质增强
    enhanced: bool
    enhanced_path: str = None
    enhance_config: dict = None
    
    # 语音识别
    asr_result: dict = None
    srt_path: str = None
    
    # 音频分析
    audio_features: dict = None
    
    # 镜头分割
    scene_result: dict = None
    keyframes_dir: str = None
    
    # 目标检测
    detection_result: dict = None
    main_person_track_id: int = -1
    roto_boxes_path: str = None
    
    # 人像初筛
    matte_result: dict = None
    alpha_dir: str = None
    
    # 画面语义（P1）
    scene_descriptions: List[dict] = None
    
    # 质量指标
    quality_scores: dict = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "video_path": self.video_path,
            "standardized_path": self.standardized_path,
            "proxy_path": self.proxy_path,
            "video_info": self.video_info,
            "enhanced": self.enhanced,
            "enhanced_path": self.enhanced_path,
            "asr_result": self.asr_result,
            "audio_features": self.audio_features,
            "scene_result": self.scene_result,
            "detection_result": self.detection_result,
            "matte_result": self.matte_result,
            "quality_scores": self.quality_scores,
        }
    
    def save(self, output_path: str):
        """保存为JSON"""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
```

---

## 三、性能优化策略

### 3.1 GPU内存优化

| 优化手段 | 说明 | 效果 |
|---------|------|------|
| 混合精度推理 | FP16/BF16替代FP32 | 显存减少50%，速度提升1.5-2倍 |
| 模型集成 | 多个模型共享GPU内存 | 减少模型加载开销 |
| 批处理大小调整 | 根据显存调整batch size | 最大化GPU利用率 |
| 流式处理 | 逐帧/逐段处理，不加载全视频 | 内存占用降低80%+ |
| 代理视频推理 | 用低分辨率代理做AI处理 | 速度提升4-16倍 |

### 3.2 并行处理策略

```
任务调度器（Celery）
    │
    ├── 视频解码线程（CPU）
    │
    ├── GPU推理池
    │   ├── FunASR（GPU 0）
    │   ├── YOLO-World（GPU 0）
    │   ├── RVM（GPU 0）
    │   └── MediaPipe（GPU 1）
    │
    ├── CPU处理池
    │   ├── PySceneDetect
    │   ├── librosa音频分析
    │   └── 数据格式转换
    │
    └── 结果融合（主线程）
```

---

## 四、质量校验标准

| 检查项 | 标准 | 检测方法 |
|--------|------|---------|
| 视频格式 | H.264 + AAC, 1920x1080, 30fps | MediaInfo自动检测 |
| 语音识别准确率 | > 90%（中文） | 与人工标注对比 / 置信度阈值 |
| 镜头分割准确率 | > 95% | 双校验一致性 / 人工抽检 |
| 人物检测准确率 | > 90% | 置信度阈值 / 人工抽检 |
| 蒙版质量（RVM） | 边缘质量 > 0.7，稳定性 > 0.8 | 自动评估 + 人工抽检 |
| 画质增强 | 无明显劣化，PSNR提升 > 3dB | VMAF/PSNR客观测量 |
| 音频分析BPM误差 | < 2 BPM | 与人工标注对比 |

---

## 五、与Phase 2的接口规范

预处理输出的标准数据结构，直接喂给Phase 2抠像跟踪模块：

```json
{
  "input_for_phase2": {
    "video_path": "/path/to/enhanced.mp4",
    "alpha_preview_dir": "/path/to/rvm_alpha/",
    "person_boxes_path": "/path/to/roto_boxes.json",
    "scene_list": [...],
    "main_person_track": {
      "track_id": 0,
      "first_frame": 0,
      "last_frame": 1800,
      "avg_confidence": 0.93
    },
    "audio_beats": [0.5, 1.0, 1.5, ...],
    "quality_report": {
      "overall": 0.88,
      "details": {...}
    }
  }
}
```

---

> **关联文档**：
> - [[Phase 2 抠像跟踪全链路详解]]
> - [[木偶视频自动化流水线-全软件最高配置落地总计划]]
> - [[CV计算机视觉深度研究报告]]
> - [[MIR音乐信息检索深度研究报告]]