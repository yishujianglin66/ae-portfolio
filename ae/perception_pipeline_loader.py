"""
Perception Pipeline Loader — 感知层模块加载与初始化
===================================================
为 AEAgentPipeline 提供 Layer 1 感知层的完整性初始化，
将新创建的模块（SceneDetector、BeatDetector、AISceneDetector、
WhisperSubtitleEngine 等）注入到现有 Pipeline 中。

用法（在 AEAgentPipeline.__init__ 或 _init_analyzers 中调用）:
    from ae.perception_pipeline_loader import inject_perception_layer
    inject_perception_layer(pipeline_instance)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("perception_loader")


def inject_perception_layer(pipeline: Any) -> None:
    """
    将完整的感知层模块注入到 AEAgentPipeline 实例中。

    通过 setattr 注入，支持优雅降级：
    - 模块加载成功 → setattr(pipeline, attr_name, instance)
    - 模块加载失败 → setattr(pipeline, attr_name, None) + warning log
    """
    # 1. SceneDetector (PySceneDetect 场景分割)
    try:
        from ae.scene_detector import DetectionMethod, SceneDetector
        pipeline.scene_detector = SceneDetector(method=DetectionMethod.ADAPTIVE)
        pipeline._has_scene_detector = True
        logger.info("✓ SceneDetector (PySceneDetect) 已注入")
    except Exception as e:
        pipeline.scene_detector = None
        pipeline._has_scene_detector = False
        logger.warning(f"✗ SceneDetector 注入失败: {e}")

    # 2. AISceneDetector (TransNetV2 AI镜头分割)
    try:
        from ae.ai_scene_detector import AISceneDetector
        pipeline.ai_scene_detector = AISceneDetector(use_transnet_v2=True)
        pipeline._has_ai_scene_detector = True
        logger.info("✓ AISceneDetector (TransNetV2) 已注入")
    except Exception as e:
        pipeline.ai_scene_detector = None
        pipeline._has_ai_scene_detector = False
        logger.warning(f"✗ AISceneDetector 注入失败: {e}")

    # 3. BeatDetector (librosa + madmom 节拍检测)
    try:
        from ae.beat_detector import BeatDetector
        pipeline.beat_detector = BeatDetector(use_madmom=True)
        # 同时设置原有的 beat_mapper 属性
        pipeline.beat_mapper = pipeline.beat_detector
        pipeline._has_beat_detector = True
        logger.info("✓ BeatDetector (librosa/madmom) 已注入")
    except Exception as e:
        pipeline.beat_detector = None
        pipeline._has_beat_detector = False
        logger.warning(f"✗ BeatDetector 注入失败: {e}")

    # 4. WhisperSubtitleEngine (faster-whisper 字幕生成)
    try:
        from ae.whisper_subtitle import WhisperSubtitleEngine
        pipeline.whisper_subtitle = WhisperSubtitleEngine(model_size="medium", word_timestamps=True)
        pipeline._has_whisper = True
        logger.info("✓ WhisperSubtitleEngine (faster-whisper) 已注入")
    except Exception as e:
        pipeline.whisper_subtitle = None
        pipeline._has_whisper = False
        logger.warning(f"✗ WhisperSubtitleEngine 注入失败: {e}")

    # 5. GLTransitionRenderer (GPU转场渲染)
    try:
        from ae.gl_transition_renderer import GLTransitionAdapter, GLTransitionRenderer
        pipeline.gl_transition_renderer = GLTransitionRenderer()
        pipeline.gl_transition_adapter = GLTransitionAdapter()
        pipeline._has_gl_transitions = True
        logger.info("✓ GLTransitionRenderer (GPU转场) 已注入")
    except Exception as e:
        pipeline.gl_transition_renderer = None
        pipeline._has_gl_transitions = False
        logger.warning(f"✗ GLTransitionRenderer 注入失败: {e}")

    # 6. TimelineComposer (时间线编排)
    try:
        from ae.timeline_composer import TimelineComposer
        pipeline.timeline_composer = TimelineComposer()
        pipeline._has_timeline_composer = True
        logger.info("✓ TimelineComposer (时间线编排) 已注入")
    except Exception as e:
        pipeline.timeline_composer = None
        pipeline._has_timeline_composer = False
        logger.warning(f"✗ TimelineComposer 注入失败: {e}")

    # 7. AudioProcessor (音频处理)
    try:
        from ae.audio_processor import AudioProcessor
        pipeline.audio_processor = AudioProcessor()
        pipeline._has_audio_processor = True
        logger.info("✓ AudioProcessor (音频处理) 已注入")
    except Exception as e:
        pipeline.audio_processor = None
        pipeline._has_audio_processor = False
        logger.warning(f"✗ AudioProcessor 注入失败: {e}")

    # 8. librosa 深度音频分析（如果 pipeline 中的为空）
    if not getattr(pipeline, "librosa_audio_analyzer", None):
        try:
            from ae.beat_detector import BeatDetector
            pipeline.librosa_audio_analyzer = BeatDetector()
            logger.info("✓ librosa_audio_analyzer (BeatDetector fallback) 已注入")
        except Exception:
            pass

    # 打印感知层状态摘要
    _print_injection_summary(pipeline)


def _print_injection_summary(pipeline: Any) -> None:
    """打印感知层模块注入状态摘要"""
    modules = {
        "场景检测 (PySceneDetect)": getattr(pipeline, "_has_scene_detector", False),
        "AI镜头分割 (TransNetV2)": getattr(pipeline, "_has_ai_scene_detector", False),
        "节拍检测 (librosa/madmom)": getattr(pipeline, "_has_beat_detector", False),
        "字幕生成 (faster-whisper)": getattr(pipeline, "_has_whisper", False),
        "GPU转场 (gl-transitions)": getattr(pipeline, "_has_gl_transitions", False),
        "时间线编排 (TimelineComposer)": getattr(pipeline, "_has_timeline_composer", False),
        "音频处理 (AudioProcessor)": getattr(pipeline, "_has_audio_processor", False),
    }

    ready_count = sum(1 for v in modules.values() if v)
    total = len(modules)

    print(f"\n{'='*60}")
    print(f"  AE Agent Pipeline - 感知层状态: {ready_count}/{total} 模块就绪")
    print(f"{'='*60}")
    for name, status in modules.items():
        icon = "✓" if status else "✗"
        print(f"  {icon} {name}")
    print(f"{'='*60}\n")


# ================================================================
#  Pipeline 增强方法注册
# ================================================================
def register_enhanced_perception(pipeline: Any) -> None:
    """
    为 AEAgentPipeline 注册增强的感知方法。

    这个方法会在 pipeline 实例上动态绑定新的感知层功能：
    - perceive_enhanced(): 使用所有可用模块的增强版感知
    - transcribe_subtitles(): 生成字幕
    - render_gl_preview(): GPU 转场预览
    - compose_timeline(): 智能时间线编排
    """

    def perceive_enhanced(self, music_path: str = None, clip_paths: list = None) -> dict:
        """增强版感知：使用全部可用模块进行深度分析"""
        result = {
            "audio": {},
            "video": {},
            "scenes": {},
            "subtitles": None,
            "metadata": {},
        }

        # === 音频分析 ===
        if self._has_beat_detector and music_path:
            try:
                beats = self.beat_detector.detect_beats(music_path)
                bpm, bpm_conf = self.beat_detector.detect_bpm(music_path)
                structure = self.beat_detector.analyze_structure(music_path)
                result["audio"] = {
                    "bpm": bpm,
                    "bpm_confidence": bpm_conf,
                    "beat_count": len(beats),
                    "beats": [b.time for b in beats[:100]],  # Top 100 节拍
                    "downbeats": [b.time for b in beats if b.is_downbeat][:50],
                    "key": structure.key,
                    "sections": structure.sections,
                    "climax_regions": structure.climax_regions,
                    "quiet_regions": structure.quiet_regions,
                    "duration": beats[-1].time if beats else 0,
                }
            except Exception as e:
                result["audio"]["error"] = str(e)

        # === 视频分析 ===
        if clip_paths:
            if self._has_scene_detector:
                try:
                    all_scenes = []
                    for cp in clip_paths:
                        cuts = self.scene_detector.detect(cp)
                        all_scenes.append({
                            "video": cp,
                            "scene_count": len(cuts),
                            "scenes": [c.to_dict() for c in cuts],
                        })
                    result["scenes"] = all_scenes
                except Exception as e:
                    result["scenes"]["error"] = str(e)

            if self._has_ai_scene_detector:
                try:
                    ai_scenes = []
                    for cp in clip_paths:
                        shots = self.ai_scene_detector.detect(cp)
                        ai_scenes.append({
                            "video": cp,
                            "shot_count": len(shots),
                            "shots": [s.to_dict() for s in shots],
                        })
                    result["video"]["ai_shots"] = ai_scenes
                except Exception as e:
                    result["video"]["ai_shots_error"] = str(e)

        # === 字幕生成 ===
        if self._has_whisper and music_path:
            try:
                transcribe_result = self.whisper_subtitle.transcribe(music_path)
                result["subtitles"] = {
                    "language": transcribe_result.language,
                    "language_probability": transcribe_result.language_probability,
                    "segments": [
                        {"start": s.start, "end": s.end, "text": s.text, "confidence": s.confidence}
                        for s in transcribe_result.segments
                    ],
                    "duration": transcribe_result.duration,
                }
            except Exception as e:
                result["subtitles"] = {"error": str(e)}

        return result

    def compose_timeline_from_perception(
        self,
        clips: list,
        audio: str = None,
        style: str = "dynamic_cut",
        output_json: str = None,
    ):
        """基于感知结果智能编排时间线"""
        if not self._has_timeline_composer:
            return None

        from ae.timeline_composer import TimelineStyle

        style_map = {
            "dynamic_cut": TimelineStyle.DYNAMIC_CUT,
            "smooth_flow": TimelineStyle.SMOOTH_FLOW,
            "fast_beat": TimelineStyle.FAST_BEAT,
            "slow_cinematic": TimelineStyle.SLOW_CINEMATIC,
            "glitch_style": TimelineStyle.GLITCH_STYLE,
            "vlog": TimelineStyle.VLOG,
        }

        tl_style = style_map.get(style, TimelineStyle.DYNAMIC_CUT)
        timeline = self.timeline_composer.build_timeline(
            clips=clips,
            audio=audio,
            style=tl_style,
        )

        if output_json:
            self.timeline_composer.export_timeline_json(timeline, output_json)

        return timeline

    # 绑定到 pipeline 实例
    import types
    pipeline.perceive_enhanced = types.MethodType(perceive_enhanced, pipeline)
    pipeline.compose_timeline_from_perception = types.MethodType(compose_timeline_from_perception, pipeline)


def quick_init_perception() -> dict:
    """
    快速创建独立的感知层组件（不依赖 Pipeline）。

    Returns:
        modules: 所有可用感知模块的字典
    """
    modules = {}

    for name, class_path in [
        ("scene_detector", "ae.scene_detector.SceneDetector"),
        ("ai_scene_detector", "ae.ai_scene_detector.AISceneDetector"),
        ("beat_detector", "ae.beat_detector.BeatDetector"),
        ("whisper_subtitle", "ae.whisper_subtitle.WhisperSubtitleEngine"),
        ("gl_renderer", "ae.gl_transition_renderer.GLTransitionRenderer"),
        ("timeline_composer", "ae.timeline_composer.TimelineComposer"),
        ("audio_processor", "ae.audio_processor.AudioProcessor"),
    ]:
        try:
            mod_name, cls_name = class_path.rsplit(".", 1)
            mod = __import__(mod_name, fromlist=[cls_name])
            cls = getattr(mod, cls_name)
            modules[name] = cls()
        except Exception as e:
            modules[name] = None
            logger.debug(f"快速初始化 {name} 失败: {e}")

    return modules


__all__ = [
    "inject_perception_layer",
    "register_enhanced_perception",
    "quick_init_perception",
]
