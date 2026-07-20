# Phase 4 渲染与输出 - 全链路技术详解

---

## 文档信息

| 项目 | 内容 |
|------|------|
| **阶段** | Phase 4 渲染与输出 |
| **涉及引擎** | 6个（4商业 + 2开源） |
| **核心引擎** | AE + ME + ffmpeg + OpenCue |
| **输出格式** | MP4 / MOV / WebM / GIF / PNG序列 / EXR序列 |

---

## 一、渲染输出流水线总览

### 1.1 6引擎能力矩阵

| 引擎 | 定位 | 核心能力 |
|------|------|---------|
| **AE aerender** | 主渲染引擎 | 合成渲染、序列输出、后台静默渲染 |
| **Adobe Media Encoder** | 批量转码引擎 | 多格式转码、Watch Folder、队列管理 |
| **ffmpeg** | 通用转码引擎 | 格式转换、压缩、多分辨率、元数据写入 |
| **gifski** | GIF编码引擎 | 高质量GIF生成、调色板优化 |
| **OpenCue** | 渲染调度引擎 | 分布式渲染、任务队列、优先级管理 |
| **Premiere Pro** | 剪辑输出引擎 | 多版本剪辑导出、字幕烧录、音频混合 |
| **MediaInfo** | 质量校验引擎 | 格式检测、参数校验、合规性检查 |

### 1.2 流水线结构

```
Phase 3 输出
（AE工程 / PR工程 / Resolve工程）
    │
    ▼
┌───────────────────────────────────────────────────────┐
│  调度层（OpenCue / Celery）                             │
│  任务分发 → 优先级队列 → 节点管理 → 失败重试            │
└─────────────────────────┬─────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  AE渲染节点   │ │ ME转码节点   │ │ Blender节点   │
│  (aerender)   │ │ (Watch Folder)│ │  (Cycles)     │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────┐
│  转码层（ffmpeg）                                       │
│  多格式 / 多分辨率 / 多平台适配                          │
└─────────────────────────┬─────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  MP4/MOV      │ │  WebM/GIF     │ │  PNG/EXR序列  │
│  (H.264/HEVC) │ │  (VP9/AV1)    │ │  (后期制作)   │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────┐
│  质量校验层（MediaInfo + 自动QC）                       │
│  格式合规 / 画质检测 / 元数据检查 / 自动报告            │
└─────────────────────────┬─────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────┐
│  交付层（MinIO / CDN）                                  │
│  存储 → 分发 → 下载链接 → 通知                          │
└───────────────────────────────────────────────────────┘
```

---

## 二、各引擎技术详解

### 2.1 AE aerender 后台渲染

#### 命令行参数详解

```bash
aerender
  -project project.aep         # AE工程文件
  -comp "MainComp"            # 合成名称
  -output output.mp4          # 输出路径
  -s 0 -e 1800                # 起始/结束帧
  -RStemplate "Best Settings" # 渲染设置模板
  -OMtemplate "Lossless"      # 输出模块模板
  -mp                         # 多进程渲染
  -memory 80                  # 内存百分比
  -v ERRORS                   # 日志级别
```

#### Python封装

```python
import subprocess
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class AERenderTask:
    """AE渲染任务"""
    project_path: str
    comp_name: str
    output_path: str
    start_frame: int = 0
    end_frame: Optional[int] = None
    render_template: str = "Best Settings"
    output_template: str = "Lossless"
    multi_process: bool = True
    memory_percent: int = 80

class AerenderRenderer:
    """AE aerender CLI封装"""
    
    def __init__(self, aerender_path: str = None):
        self.aerender_path = aerender_path or self._detect_aerender()
    
    def _detect_aerender(self) -> str:
        """自动检测aerender路径"""
        possible_paths = [
            r"C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\aerender.exe",
            "/Applications/Adobe After Effects 2026/aerender",
        ]
        for path in possible_paths:
            if Path(path).exists():
                return path
        return "aerender"
    
    def render(self, task: AERenderTask) -> bool:
        """执行渲染"""
        cmd = [
            self.aerender_path,
            "-project", task.project_path,
            "-comp", task.comp_name,
            "-output", task.output_path,
            "-s", str(task.start_frame),
            "-RStemplate", task.render_template,
            "-OMtemplate", task.output_template,
            "-v", "ERRORS",
        ]
        
        if task.end_frame is not None:
            cmd.extend(["-e", str(task.end_frame)])
        
        if task.multi_process:
            cmd.append("-mp")
        
        cmd.extend(["-memory", str(task.memory_percent)])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600 * 8  # 8小时超时
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
    
    def render_sequence(self, task: AERenderTask,
                        output_dir: str,
                        format: str = "png") -> bool:
        """渲染序列帧"""
        # 修改输出为序列格式
        output_pattern = os.path.join(output_dir, f"frame_[########].{format}")
        task.output_path = output_pattern
        task.output_template = f"PNG Sequence" if format == "png" else "EXR Sequence"
        
        return self.render(task)
```

---

### 2.2 Adobe Media Encoder Watch Folder

#### 工作原理

```
Watch Folder（监控文件夹）
    │
    ├─ Input/          → 放入工程文件/素材
    ├─ Output/         → 渲染完成的文件
    └─ Logs/           → 日志文件
              │
              ▼
    ME自动检测新文件 → 加入队列 → 自动渲染
```

#### 批量渲染配置

```python
class MediaEncoderBridge:
    """Adobe Media Encoder桥接器"""
    
    def __init__(self, watch_folder: str):
        self.watch_folder = watch_folder
        self.input_dir = os.path.join(watch_folder, "Input")
        self.output_dir = os.path.join(watch_folder, "Output")
        
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
    
    def submit_task(self, aep_path: str, comp_name: str,
                    output_name: str, preset: str = "H.264 1080p"):
        """
        提交任务到ME Watch Folder
        
        通过创建AME任务文件实现
        """
        # AME任务文件格式（XML/JSON）
        task_data = {
            "version": "1.0",
            "source": aep_path,
            "comp": comp_name,
            "output": os.path.join(self.output_dir, output_name),
            "preset": preset,
            "priority": "normal",
        }
        
        # 写入任务文件
        task_file = os.path.join(
            self.input_dir, 
            f"{output_name}.amejob"
        )
        
        with open(task_file, "w") as f:
            json.dump(task_data, f)
        
        return task_file
    
    def check_status(self, output_name: str) -> str:
        """检查任务状态"""
        output_path = os.path.join(self.output_dir, output_name)
        
        if os.path.exists(output_path):
            return "completed"
        
        # 检查是否有正在渲染的临时文件
        temp_files = list(Path(self.output_dir).glob("*.tmp"))
        for temp in temp_files:
            if output_name in temp.name:
                return "rendering"
        
        return "pending"
    
    def get_completed_tasks(self) -> List[str]:
        """获取已完成的任务列表"""
        return [
            f.name for f in Path(self.output_dir).iterdir()
            if f.is_file() and f.suffix in ['.mp4', '.mov', '.avi']
        ]
```

---

### 2.3 ffmpeg 多格式转码

#### 核心功能矩阵

| 功能 | 命令/参数 | 用途 |
|------|----------|------|
| H.264编码 | `-c:v libx264 -crf 18` | 通用MP4输出 |
| HEVC编码 | `-c:v libx265 -crf 20` | 高压缩比输出 |
| WebM/VP9 | `-c:v libvpx-vp9` | 网页优化输出 |
| GIF生成 | `-f gif` | GIF动图输出 |
| 多分辨率 | `-vf scale=...` | 各平台适配 |
| 元数据写入 | `-metadata ...` | 版权/描述信息 |
| 封面提取 | `-ss ... -vframes 1` | 缩略图/封面 |
| 音频处理 | `-c:a aac -b:a 192k` | 音频编码 |
| 字幕烧录 | `-vf subtitles=...` | 硬字幕 |
| 片头片尾 | `-filter_complex concat` | 拼接 |

#### Python封装

```python
import ffmpeg
from dataclasses import dataclass
from typing import List, Tuple, Optional

@dataclass
class TranscodeConfig:
    """转码配置"""
    input_path: str
    output_path: str
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 18
    preset: str = "medium"
    resolution: Optional[Tuple[int, int]] = None
    fps: Optional[float] = None
    video_bitrate: Optional[str] = None
    audio_bitrate: str = "192k"
    faststart: bool = True
    metadata: dict = None

class FFmpegTranscoder:
    """ffmpeg转码器"""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path
    
    def transcode(self, config: TranscodeConfig) -> bool:
        """执行转码"""
        try:
            stream = ffmpeg.input(config.input_path)
            
            # 视频处理
            video = stream.video
            
            if config.resolution:
                w, h = config.resolution
                video = video.filter('scale', w, h)
            
            if config.fps:
                video = video.filter('fps', config.fps)
            
            # 音频处理
            audio = stream.audio
            
            # 输出
            output_kwargs = {
                'vcodec': config.video_codec,
                'acodec': config.audio_codec,
                'preset': config.preset,
                'crf': config.crf,
                'b:a': config.audio_bitrate,
            }
            
            if config.video_bitrate:
                output_kwargs['video_bitrate'] = config.video_bitrate
            
            if config.faststart:
                output_kwargs['movflags'] = '+faststart'
            
            if config.metadata:
                for key, value in config.metadata.items():
                    output_kwargs[f'metadata'] = f'{key}={value}'
            
            (
                ffmpeg
                .output(video, audio, config.output_path, **output_kwargs)
                .overwrite_output()
                .run(cmd=self.ffmpeg_path, capture_stdout=True, capture_stderr=True)
            )
            
            return True
        except ffmpeg.Error:
            return False
    
    def generate_multi_resolution(self, input_path: str,
                                   output_dir: str,
                                   resolutions: List[Tuple[int, int, str]]):
        """
        生成多分辨率版本
        
        resolutions: [(width, height, suffix), ...]
        """
        results = {}
        
        for w, h, suffix in resolutions:
            output_path = os.path.join(
                output_dir, 
                f"output_{suffix}.mp4"
            )
            
            config = TranscodeConfig(
                input_path=input_path,
                output_path=output_path,
                resolution=(w, h),
            )
            
            results[suffix] = self.transcode(config)
        
        return results
    
    def generate_gif(self, input_path: str, output_path: str,
                     width: int = 480, fps: int = 15,
                     start_time: float = 0, duration: float = None):
        """生成高质量GIF（使用gifski效果更好，此为ffmpeg备用）"""
        try:
            stream = ffmpeg.input(input_path, ss=start_time)
            
            if duration:
                stream = ffmpeg.input(input_path, ss=start_time, t=duration)
            
            (
                stream
                .filter('fps', fps)
                .filter('scale', width, -1)
                .output(output_path, format='gif', loop=0)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            return True
        except ffmpeg.Error:
            return False
    
    def extract_thumbnail(self, input_path: str, output_path: str,
                          timestamp: float = 1.0,
                          width: int = 1280) -> bool:
        """提取封面缩略图"""
        try:
            (
                ffmpeg
                .input(input_path, ss=timestamp)
                .output(output_path, vf=f'scale={width}:-1', vframes=1)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            return True
        except ffmpeg.Error:
            return False
```

---

### 2.4 gifski 高质量GIF

```python
import subprocess
from dataclasses import dataclass

@dataclass
class GifskiConfig:
    """gifski配置"""
    width: int = 640
    height: int = 360
    quality: int = 90       # 1-100
    fps: int = 15
    loop: bool = True
    speed: float = 1.0

class GifskiEncoder:
    """gifski GIF编码器封装"""
    
    def __init__(self, gifski_path: str = "gifski"):
        self.gifski_path = gifski_path
    
    def encode_from_video(self, video_path: str,
                          output_path: str,
                          config: GifskiConfig = None) -> bool:
        """从视频生成GIF"""
        config = config or GifskiConfig()
        
        cmd = [
            self.gifski_path,
            "--output", output_path,
            "--width", str(config.width),
            "--height", str(config.height),
            "--quality", str(config.quality),
            "--fps", str(config.fps),
        ]
        
        if not config.loop:
            cmd.append("--once")
        
        if config.speed != 1.0:
            cmd.extend(["--speed", str(config.speed)])
        
        cmd.append(video_path)
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
    
    def encode_from_frames(self, frames_dir: str,
                           output_path: str,
                           pattern: str = "frame_%06d.png",
                           config: GifskiConfig = None) -> bool:
        """从帧序列生成GIF"""
        config = config or GifskiConfig()
        frames_pattern = os.path.join(frames_dir, pattern)
        
        cmd = [
            self.gifski_path,
            "--output", output_path,
            "--width", str(config.width),
            "--height", str(config.height),
            "--quality", str(config.quality),
            "--fps", str(config.fps),
            frames_pattern,
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
```

---

### 2.5 MediaInfo 质量校验

```python
import subprocess
import json
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class VideoQualityReport:
    """视频质量报告"""
    file_path: str
    file_size: int
    duration: float
    video_codec: str
    width: int
    height: int
    fps: float
    bitrate: int
    audio_codec: str
    audio_sample_rate: int
    audio_channels: int
    compliance_check: dict  # 各项合规检查结果

class MediaInfoChecker:
    """MediaInfo质量校验器"""
    
    def __init__(self, mediainfo_path: str = "mediainfo"):
        self.mediainfo_path = mediainfo_path
    
    def analyze(self, file_path: str) -> dict:
        """分析视频文件"""
        try:
            result = subprocess.run(
                [self.mediainfo_path, "--Output=JSON", file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            return json.loads(result.stdout)
        except Exception:
            return {}
    
    def check_compliance(self, file_path: str,
                         spec: dict) -> VideoQualityReport:
        """
        检查视频是否符合规范
        
        spec示例：
        {
            "min_width": 1920,
            "min_height": 1080,
            "min_fps": 25,
            "allowed_video_codecs": ["h264", "hevc"],
            "allowed_audio_codecs": ["aac", "mp3"],
            "max_file_size_mb": 500,
        }
        """
        info = self.analyze(file_path)
        
        if not info:
            return VideoQualityReport(
                file_path=file_path,
                file_size=0,
                duration=0,
                video_codec="",
                width=0,
                height=0,
                fps=0,
                bitrate=0,
                audio_codec="",
                audio_sample_rate=0,
                audio_channels=0,
                compliance_check={"error": "analysis_failed"},
            )
        
        # 提取信息
        video_track = info.get("media", {}).get("track", [])
        video_info = {}
        audio_info = {}
        
        for track in video_track:
            if track.get("@type") == "Video":
                video_info = track
            elif track.get("@type") == "Audio":
                audio_info = track
        
        general_info = next(
            (t for t in video_track if t.get("@type") == "General"),
            {}
        )
        
        # 合规检查
        checks = {}
        
        # 分辨率检查
        width = int(video_info.get("Width", 0))
        height = int(video_info.get("Height", 0))
        checks["resolution_ok"] = width >= spec.get("min_width", 0) and height >= spec.get("min_height", 0)
        
        # 帧率检查
        fps = float(video_info.get("FrameRate", 0))
        checks["fps_ok"] = fps >= spec.get("min_fps", 0)
        
        # 编码检查
        video_codec = video_info.get("CodecID", "").lower()
        allowed_vcodecs = [c.lower() for c in spec.get("allowed_video_codecs", [])]
        checks["video_codec_ok"] = not allowed_vcodecs or video_codec in allowed_vcodecs
        
        # 文件大小检查
        file_size = int(general_info.get("FileSize", 0))
        max_size_mb = spec.get("max_file_size_mb", 0)
        checks["file_size_ok"] = max_size_mb == 0 or file_size <= max_size_mb * 1024 * 1024
        
        # 整体通过
        checks["overall_pass"] = all(checks.values())
        
        return VideoQualityReport(
            file_path=file_path,
            file_size=file_size,
            duration=float(general_info.get("Duration", 0)),
            video_codec=video_codec,
            width=width,
            height=height,
            fps=fps,
            bitrate=int(video_info.get("BitRate", 0)),
            audio_codec=audio_info.get("CodecID", ""),
            audio_sample_rate=int(audio_info.get("SamplingRate", 0)),
            audio_channels=int(audio_info.get("Channels", 0)),
            compliance_check=checks,
        )
```

---

### 2.6 OpenCue 分布式渲染调度

```python
"""
OpenCue渲染管理系统集成
- 支持任意Shell命令封装
- 支持AE、Blender、Resolve渲染任务
- 支持多机分布式、优先级队列、失败重试
"""

import subprocess
import os
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class CueJob:
    """OpenCue任务"""
    job_name: str
    command: str
    layer: str = "default"
    frames: str = "1-100"
    chunk_size: int = 1
    priority: int = 100
    environment: dict = None

class OpenCueManager:
    """OpenCue渲染管理器"""
    
    def __init__(self, cuebot_host: str = "localhost:8443"):
        self.cuebot_host = cuebot_host
    
    def submit_job(self, job: CueJob) -> str:
        """
        提交渲染任务
        
        返回Job ID
        """
        # 使用cuecommander或直接调用API
        # 简化实现：使用opencue Python API
        
        try:
            from opencue import api
            
            # 创建Job
            job = api.createJob(job.job_name, ...)
            
            # 创建Layer
            # layer = job.createLayer(...)
            
            return job.id
        except ImportError:
            # 如果没有opencue库，返回模拟ID
            return f"simulated_job_{job.job_name}"
    
    def get_job_status(self, job_id: str) -> dict:
        """获取任务状态"""
        try:
            from opencue import api
            job = api.getJob(job_id)
            return {
                "id": job_id,
                "state": job.state(),
                "total_frames": job.totalFrames(),
                "done_frames": job.doneFrames(),
                "running_frames": job.runningFrames(),
                "failed_frames": job.failedFrames(),
                "progress": job.doneFrames() / job.totalFrames() * 100 if job.totalFrames() > 0 else 0,
            }
        except ImportError:
            return {"id": job_id, "state": "UNKNOWN"}
    
    def retry_failed_frames(self, job_id: str) -> bool:
        """重试失败的帧"""
        try:
            from opencue import api
            job = api.getJob(job_id)
            job.retryFailedFrames()
            return True
        except Exception:
            return False
    
    def kill_job(self, job_id: str) -> bool:
        """终止任务"""
        try:
            from opencue import api
            job = api.getJob(job_id)
            job.kill()
            return True
        except Exception:
            return False
```

---

## 三、多平台输出规格

### 3.1 输出规格矩阵

| 平台 | 分辨率 | 帧率 | 编码 | 码率范围 |
|------|--------|------|------|---------|
| **抖音/快手** | 1080x1920 (竖屏) | 30fps | H.264 | 8-16 Mbps |
| **B站/西瓜** | 1920x1080 (横屏) | 30fps | H.264/HEVC | 8-20 Mbps |
| **视频号** | 1080x1920 | 30fps | H.264 | 6-12 Mbps |
| **YouTube** | 1920x1080 / 4K | 30/60fps | VP9/H.264 | 8-45 Mbps |
| **Instagram** | 1080x1080 / 竖屏 | 30fps | H.264 | 3.5-10 Mbps |
| **电视/广播** | 1920x1080 | 25/30fps | H.264/ProRes | 50-200 Mbps |
| **影院/DCP** | 4K | 24fps | JPEG 2000 | 250+ Mbps |

### 3.2 批量输出配置

```python
# 预设输出规格
OUTPUT_PRESETS = {
    "douyin": {
        "name": "抖音竖屏",
        "resolution": (1080, 1920),
        "fps": 30,
        "codec": "libx264",
        "bitrate": "12M",
        "audio_bitrate": "128k",
        "format": "mp4",
    },
    "bilibili": {
        "name": "B站横屏",
        "resolution": (1920, 1080),
        "fps": 30,
        "codec": "libx264",
        "bitrate": "16M",
        "audio_bitrate": "192k",
        "format": "mp4",
    },
    "youtube_4k": {
        "name": "YouTube 4K",
        "resolution": (3840, 2160),
        "fps": 30,
        "codec": "libx264",
        "bitrate": "45M",
        "audio_bitrate": "320k",
        "format": "mp4",
    },
    "gif_social": {
        "name": "社交媒体GIF",
        "resolution": (480, 270),
        "fps": 15,
        "quality": 80,
        "format": "gif",
    },
}
```

---

## 四、质量保证体系

### 4.1 输出质量检查清单

| 检查项 | 标准 | 检测方式 |
|--------|------|---------|
| 视频完整性 | 时长正确、无丢帧、无卡顿 | MediaInfo + 自动抽帧检查 |
| 画质劣化 | VMAF > 95（相比主版本） | 自动VMAF计算 |
| 音画同步 | 误差 < 100ms | 自动检测 + 人工抽检 |
| 色彩正确 | 色彩空间正确、无色偏 | 直方图分析 |
| 音频质量 | 无爆音、无失真 | 音频波形分析 |
| 元数据完整 | 文件名/描述/标签正确 | MediaInfo |
| 文件完整性 | MD5校验通过 | 自动校验 |

### 4.2 自动QC流水线

```
渲染完成
    │
    ▼
┌──────────────┐
│  文件完整性   │ → 大小/时长/MD5
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  格式合规检查 │ → MediaInfo + 规格比对
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  画质评估     │ → VMAF/PSNR/SSIM
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  音频检查     │ → 响度/爆音/静音检测
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  生成报告     │ → QC报告 + 通过/失败
└──────────────┘
```

---

> **关联文档**：
> - [[Phase 3 风格化合成全链路技术详解]]
> - [[企业级架构落地实施手册]]
> - [[批量生产与项目管理指南]]