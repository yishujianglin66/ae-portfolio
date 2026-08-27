#!/usr/bin/env python3
"""
DaVinci Resolve Pipeline 集成适配器
====================================

将 DaVinci Resolve 调色引擎集成到 UnifiedPipeline 中。

Usage:
    from integrations.resolve_pipeline_adapter import ResolvePipelineStage
    
    pipeline = UnifiedPipeline()
    pipeline.add_stage("color_grade", ResolvePipelineStage(preset="cinematic"))
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class ResolveStageConfig:
    """Resolve 调色阶段配置"""
    preset: str = "cinematic"
    lut_path: Optional[str] = None
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    lut_intensity: float = 1.0
    render: bool = False
    output_dir: Optional[str] = None
    close_after: bool = True
    # 智能调色
    auto_detect_scene: bool = False
    auto_match_audio: bool = False


class ResolvePipelineStage:
    """Resolve 调色 Pipeline 阶段
    
    集成到 UnifiedPipeline 中作为调色阶段。
    """
    
    def __init__(self, config: Optional[ResolveStageConfig] = None, **kwargs):
        if config is None:
            config = ResolveStageConfig(**kwargs)
        self.config = config
        self._engine = None
    
    @property
    def engine(self):
        if self._engine is None:
            from integrations.davinci_fuscript import ResolveColorEngine
            self._engine = ResolveColorEngine()
        return self._engine
    
    def execute(self, context: Dict[str, Any], callback: Optional[Callable] = None) -> Dict[str, Any]:
        """执行调色阶段
        
        Args:
            context: Pipeline 上下文，包含 media_files, project_name 等
            callback: 进度回调 callback(progress, message)
        
        Returns:
            更新后的 context
        """
        def _cb(progress: float, msg: str):
            if callback:
                callback(progress, msg)
        
        # 从 context 获取参数
        media_files = context.get("media_files", [])
        project_name = context.get("project_name", f"Pipeline_{id(self)}")
        
        if not media_files:
            _cb(0, "No media files in context")
            return context
        
        # 智能调色
        color_config = self._build_color_config(media_files, context, callback)
        
        # 执行调色
        _cb(0.2, "Starting Resolve color grade...")
        result = self.engine.auto_grade(
            project_name=project_name,
            media_files=media_files,
            color_config=color_config,
            render=self.config.render,
            output_dir=self.config.output_dir,
            close_after=self.config.close_after,
            callback=callback,
        )
        
        # 更新 context
        context["resolve_result"] = {
            "success": result.success,
            "project_name": result.project_name,
            "timeline_name": result.timeline_name,
            "clips_graded": result.clips_graded,
            "duration": result.duration,
        }
        
        if result.success:
            _cb(1.0, "Color grade completed")
        else:
            _cb(1.0, f"Color grade failed: {result.errors}")
        
        return context
    
    def _build_color_config(
        self,
        media_files: List[str],
        context: Dict[str, Any],
        callback: Optional[Callable] = None,
    ):
        """构建调色配置（支持智能调色 + v4.0 预设系统）"""
        from integrations.davinci_fuscript import (
            ColorGradeConfig, find_lut_for_preset,
            RESOLVE_PRESETS, preset_to_color_grade_config,
        )
        
        preset = self.config.preset
        segment_presets = None
        
        # 智能场景检测
        if self.config.auto_detect_scene:
            segment_presets = self._detect_scenes(media_files, callback)
            if segment_presets:
                preset = list(segment_presets.values())[0]  # 使用第一个场景的预设作为默认
        
        # 智能音频匹配
        if self.config.auto_match_audio and not segment_presets:
            audio_preset = self._match_audio_mood(media_files[0], callback)
            if audio_preset:
                preset = audio_preset
        
        # v4.0: 优先使用 RESOLVE_PRESETS 的色轮参数
        if preset in RESOLVE_PRESETS:
            config = preset_to_color_grade_config(preset)
            config.lut_path = self.config.lut_path or find_lut_for_preset(preset)
            config.segment_presets = segment_presets
            return config
        
        # 回退到基础配置
        lut_path = self.config.lut_path or find_lut_for_preset(preset)
        return ColorGradeConfig(
            preset=preset,
            lut_path=lut_path,
            brightness=self.config.brightness,
            contrast=self.config.contrast,
            saturation=self.config.saturation,
            lut_intensity=self.config.lut_intensity,
            segment_presets=segment_presets,
        )
    
    def _detect_scenes(
        self,
        media_files: List[str],
        callback: Optional[Callable] = None,
    ) -> Optional[Dict[str, str]]:
        """检测场景类型并返回分段预设"""
        try:
            from integrations.scene_detector import SceneDetector
            detector = SceneDetector()
            
            segment_presets = {}
            for i, media_file in enumerate(media_files):
                if callback:
                    callback(0.1 + i * 0.02, f"Detecting scene {i+1}/{len(media_files)}...")
                
                scenes = detector.detect(media_file)
                if scenes:
                    # 使用主要场景类型推荐预设
                    main_scene = scenes[0]
                    scene_type = main_scene.get("type", "")
                    rec = self.engine.get_recommendation(scene_type)
                    segment_presets[os.path.basename(media_file)] = rec["preset"]
            
            return segment_presets if segment_presets else None
        except ImportError:
            return None
        except Exception as e:
            if callback:
                callback(0.1, f"Scene detection failed: {e}")
            return None
    
    def _match_audio_mood(
        self,
        media_file: str,
        callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """根据音频情绪匹配预设"""
        try:
            from integrations.audio_analyzer import AudioAnalyzer
            analyzer = AudioAnalyzer()
            
            if callback:
                callback(0.1, "Analyzing audio mood...")
            
            bpm, energy, mood = analyzer.analyze(media_file)
            
            # 情绪→预设映射
            mood_map = {
                "energetic": "dramatic",
                "happy": "warm",
                "sad": "memories",
                "dark": "noir",
                "calm": "cinematic",
                "intense": "rogue",
                "romantic": "wedding",
            }
            
            preset = mood_map.get(mood, "cinematic")
            if callback:
                callback(0.15, f"Audio mood: {mood} → preset: {preset}")
            
            return preset
        except ImportError:
            return None
        except Exception as e:
            if callback:
                callback(0.1, f"Audio analysis failed: {e}")
            return None


# ============================================================================
# 便捷函数
# ============================================================================

def create_resolve_stage(
    preset: str = "cinematic",
    auto_detect_scene: bool = False,
    auto_match_audio: bool = False,
    **kwargs,
) -> ResolvePipelineStage:
    """创建 Resolve 调色阶段"""
    config = ResolveStageConfig(
        preset=preset,
        auto_detect_scene=auto_detect_scene,
        auto_match_audio=auto_match_audio,
        **kwargs,
    )
    return ResolvePipelineStage(config)
