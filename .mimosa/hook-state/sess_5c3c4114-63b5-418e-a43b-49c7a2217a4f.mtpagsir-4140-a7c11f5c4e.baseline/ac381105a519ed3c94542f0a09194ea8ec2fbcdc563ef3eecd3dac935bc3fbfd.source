"""ae - AE/PR核心操作包

提供AE/PR项目管理、命令生成、合成预设、进程控制、AI分析等核心能力。

v2.0 — 集成感知层完整的自动化剪辑能力:
  - GPU转场渲染 (gl-transitions)
  - 场景检测 (PySceneDetect + TransNetV2)
  - 节拍检测 (librosa + madmom)
  - 字幕生成 (faster-whisper)
  - 智能时间线编排 (TimelineComposer)
  - AI帧插值 (RIFE)
  - 目标检测 (YOLOv8)
  - 分布式渲染
  - 实时预览
"""

# ================================================================
#  基础模块 (始终可用)
# ================================================================
from .preset_system import *
from .preset_executor import *

# ================================================================
#  感知层 (可选依赖)
# ================================================================
try:
    from .scene_detector import SceneDetector, SceneCut, SceneMetadata, DetectionMethod
except ImportError:
    pass

try:
    from .ai_scene_detector import AISceneDetector, Shot, ShotTransition, ShotType
except ImportError:
    pass

try:
    from .beat_detector import BeatDetector, BeatInfo, MusicStructure, ClipSuggestion
except ImportError:
    pass

try:
    from .whisper_subtitle import WhisperSubtitleEngine, TranscribeResult, SubtitleSegment, WordTiming
except ImportError:
    pass

# ================================================================
#  编排层
# ================================================================
try:
    from .timeline_composer import TimelineComposer, Timeline, Track, ClipItem, TimelineStyle, TrackType
except ImportError:
    pass

try:
    from .audio_processor import AudioProcessor, AudioFade, AudioTrackConfig, AudioMixResult
except ImportError:
    pass

# ================================================================
#  GPU渲染层
# ================================================================
try:
    from .gl_transition_renderer import GLTransitionRenderer, GLTransitionAdapter, GL_TRANSITION_TABLE
except ImportError:
    pass

# ================================================================
#  AI增强层
# ================================================================
try:
    from .frame_interpolator import FrameInterpolator, InterpolationResult, SlowMotionConfig, InterpolationMethod
except ImportError:
    pass

try:
    from .object_detector import ObjectDetector, DetectionBox, FrameDetection, VideoDetectionResult
except ImportError:
    pass

# ================================================================
#  基础设施层
# ================================================================
try:
    from .distributed_renderer import DistributedRenderer, RenderTask, RenderBatch, RenderFarmAdapter
except ImportError:
    pass

try:
    from .live_preview import LivePreview, PreviewMode, PreviewConfig, PreviewOverlay, FrameBuffer
except ImportError:
    pass

try:
    from .perception_pipeline_loader import inject_perception_layer, register_enhanced_perception, quick_init_perception
except ImportError:
    pass

# ================================================================
#  风格模板
# ================================================================
try:
    from .style_template_library import STYLE_TEMPLATES
except ImportError:
    pass

__all__ = [
    # 场景检测
    "SceneDetector", "SceneCut", "SceneMetadata", "DetectionMethod",
    # AI镜头分割
    "AISceneDetector", "Shot", "ShotTransition", "ShotType",
    # 节拍检测
    "BeatDetector", "BeatInfo", "MusicStructure", "ClipSuggestion",
    # 字幕
    "WhisperSubtitleEngine", "TranscribeResult", "SubtitleSegment", "WordTiming",
    # 时间线
    "TimelineComposer", "Timeline", "Track", "ClipItem", "TimelineStyle", "TrackType",
    # 音频
    "AudioProcessor", "AudioFade", "AudioTrackConfig", "AudioMixResult",
    # GPU转场
    "GLTransitionRenderer", "GLTransitionAdapter", "GL_TRANSITION_TABLE",
    # AI增强
    "FrameInterpolator", "InterpolationResult", "SlowMotionConfig", "InterpolationMethod",
    "ObjectDetector", "DetectionBox", "FrameDetection", "VideoDetectionResult",
    # 基础设施
    "DistributedRenderer", "RenderTask", "RenderBatch", "RenderFarmAdapter",
    "LivePreview", "PreviewMode", "PreviewConfig", "PreviewOverlay", "FrameBuffer",
    # Pipeline
    "inject_perception_layer", "register_enhanced_perception", "quick_init_perception",
    # 模板
    "STYLE_TEMPLATES",
]
