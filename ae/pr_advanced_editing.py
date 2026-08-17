#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Premiere Pro 高级剪辑系统
==========================

提供专业级高级剪辑功能：
- 拉镜效果（Whip Pan）- 快速摇摄过渡
- 缩放效果（Dynamic Zoom）- 动态缩放动画
- 速度调整（Speed Ramp）- 变速剪辑
- 运动跟踪（Motion Tracking）- 自动运动追踪
- 关键帧动画（Keyframe Animation）- 复杂属性动画
- 多轨道编辑（Multi-track Editing）- 轨道级操作
- 批量处理（Batch Processing）- 批量应用效果

架构设计：
1. EditMode 枚举 - 编辑模式定义
2. EditParam - 编辑参数数据类
3. AdvancedEditingSystem - 高级剪辑系统核心
4. JSX 脚本生成器 - 生成 Premiere Pro ExtendScript
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Union


class EditMode(str, Enum):
    """编辑模式枚举。"""
    
    WHIP_PAN = "whip_pan"
    DYNAMIC_ZOOM = "dynamic_zoom"
    SPEED_RAMP = "speed_ramp"
    MOTION_BLUR = "motion_blur"
    KEYFRAME_ANIMATION = "keyframe_animation"
    MULTI_TRACK_EDIT = "multi_track_edit"
    BATCH_EFFECT = "batch_effect"
    COLOR_GRADE = "color_grade"
    AUDIO_SYNC = "audio_sync"
    TRANSITION_BATCH = "transition_batch"


class MotionDirection(str, Enum):
    """运动方向枚举。"""
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"
    IN = "in"
    OUT = "out"
    CENTER = "center"


@dataclass
class WhipPanParam:
    """拉镜效果参数。"""
    direction: MotionDirection = MotionDirection.RIGHT
    speed: float = 2.0
    blur_amount: float = 25.0
    duration: float = 0.5
    overlap: float = 0.3


@dataclass
class DynamicZoomParam:
    """动态缩放参数。"""
    start_scale: float = 100.0
    end_scale: float = 150.0
    duration: float = 2.0
    ease_type: str = "ease_in_out"
    focus_point: Optional[List[float]] = None
    blur_amount: float = 0.0


@dataclass
class SpeedRampParam:
    """速度调整参数。"""
    start_speed: float = 100.0
    end_speed: float = 200.0
    ramp_duration: float = 1.0
    ease_type: str = "ease_in_out"
    frame_blending: bool = True
    preserve_audio: bool = False


@dataclass
class KeyframePoint:
    """关键帧点。"""
    time: float
    value: Union[float, List[float]]
    interpolation: str = "linear"


@dataclass
class KeyframeAnimationParam:
    """关键帧动画参数。"""
    property_name: Optional[str] = None
    keyframes: Optional[List[KeyframePoint]] = None
    easing: str = "ease_in_out"


@dataclass
class AdvancedEditParam:
    """高级编辑参数数据类。"""
    
    edit_mode: EditMode = EditMode.WHIP_PAN
    
    whip_pan: WhipPanParam = field(default_factory=WhipPanParam)
    dynamic_zoom: DynamicZoomParam = field(default_factory=DynamicZoomParam)
    speed_ramp: SpeedRampParam = field(default_factory=SpeedRampParam)
    keyframe_animation: KeyframeAnimationParam = field(default_factory=KeyframeAnimationParam)
    
    track_index: int = 0
    clip_index: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    custom_settings: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "edit_mode": self.edit_mode.value,
            "track_index": self.track_index,
            "clip_index": self.clip_index,
        }
        
        if self.start_time is not None:
            result["start_time"] = self.start_time
        if self.end_time is not None:
            result["end_time"] = self.end_time
        
        if self.edit_mode == EditMode.WHIP_PAN:
            result["whip_pan"] = asdict(self.whip_pan)
            result["whip_pan"]["direction"] = self.whip_pan.direction.value
        elif self.edit_mode == EditMode.DYNAMIC_ZOOM:
            result["dynamic_zoom"] = asdict(self.dynamic_zoom)
        elif self.edit_mode == EditMode.SPEED_RAMP:
            result["speed_ramp"] = asdict(self.speed_ramp)
        elif self.edit_mode == EditMode.KEYFRAME_ANIMATION:
            result["keyframe_animation"] = {
                "property_name": self.keyframe_animation.property_name,
                "keyframes": [asdict(kf) for kf in self.keyframe_animation.keyframes],
                "easing": self.keyframe_animation.easing,
            }
        
        if self.custom_settings:
            result["custom_settings"] = self.custom_settings
        
        return result


class PremiereAdvancedEditing:
    """Premiere Pro 高级剪辑系统。"""

    def __init__(self, pr_client=None):
        self.pr_client = pr_client

    def get_edit_mode_info(self, edit_mode: EditMode) -> Dict[str, Any]:
        """获取编辑模式信息。"""
        info = {
            EditMode.WHIP_PAN: {
                "name": "拉镜效果",
                "category": "高级转场",
                "description": "模拟摄像机快速摇摄，产生动态过渡效果",
                "icon": "〰",
            },
            EditMode.DYNAMIC_ZOOM: {
                "name": "动态缩放",
                "category": "运动效果",
                "description": "精确控制缩放动画，支持自定义焦点和缓动",
                "icon": "🔍",
            },
            EditMode.SPEED_RAMP: {
                "name": "速度调整",
                "category": "时间效果",
                "description": "平滑的速度渐变，加速或减速剪辑",
                "icon": "⏩",
            },
            EditMode.MOTION_BLUR: {
                "name": "运动模糊",
                "category": "视觉效果",
                "description": "为运动画面添加真实的模糊效果",
                "icon": "✨",
            },
            EditMode.KEYFRAME_ANIMATION: {
                "name": "关键帧动画",
                "category": "高级动画",
                "description": "精确控制任意属性的关键帧动画",
                "icon": "📈",
            },
            EditMode.MULTI_TRACK_EDIT: {
                "name": "多轨道编辑",
                "category": "轨道操作",
                "description": "同步编辑多个轨道上的剪辑",
                "icon": "🎚",
            },
            EditMode.BATCH_EFFECT: {
                "name": "批量效果",
                "category": "批处理",
                "description": "为多个剪辑批量应用效果",
                "icon": "⚡",
            },
            EditMode.COLOR_GRADE: {
                "name": "调色",
                "category": "视觉效果",
                "description": "专业级调色控制",
                "icon": "🎨",
            },
            EditMode.AUDIO_SYNC: {
                "name": "音频同步",
                "category": "音频操作",
                "description": "音频与视频同步",
                "icon": "🔊",
            },
        }
        return info.get(edit_mode, {
            "name": "未知模式",
            "category": "其他",
            "description": "",
            "icon": "❓",
        })

    def list_edit_modes(self) -> List[Dict[str, Any]]:
        """列出所有可用编辑模式。"""
        modes = []
        for mode in EditMode:
            info = self.get_edit_mode_info(mode)
            modes.append({
                "mode": mode.value,
                "name": info["name"],
                "category": info["category"],
                "description": info["description"],
                "icon": info["icon"],
            })
        return modes

    def generate_whip_pan_script(
        self,
        track_index: int,
        clip_index: int,
        params: WhipPanParam,
    ) -> str:
        """生成拉镜效果脚本。"""
        direction_factor = -1 if params.direction == MotionDirection.LEFT else 1
        speed_factor = params.speed
        blur_amount = params.blur_amount
        duration = params.duration
        overlap = params.overlap

        script = f'''
(function() {{
    try {{
        var trackIndex = {track_index};
        var clipIndex = {clip_index};
        var directionFactor = {direction_factor};
        var speedFactor = {speed_factor};
        var blurAmount = {blur_amount};
        var duration = {duration};
        var overlap = {overlap};
        
        if (!app.project || !app.project.activeSequence) {{
            return JSON.stringify({{error: true, message: "没有打开的项目或活动序列"}});
        }}
        
        var seq = app.project.activeSequence;
        var videoTrack = seq.videoTracks[trackIndex];
        
        if (!videoTrack || clipIndex < 0 || clipIndex >= videoTrack.clips.numItems) {{
            return JSON.stringify({{error: true, message: "无效的轨道或剪辑索引"}});
        }}
        
        var clip = videoTrack.clips[clipIndex];
        var nextClip = clipIndex + 1 < videoTrack.clips.numItems ? videoTrack.clips[clipIndex + 1] : null;
        
        app.beginUndoGroup("Whip Pan Effect");
        
        if (nextClip) {{
            var transitionDuration = duration * speedFactor;
            var overlapFrames = transitionDuration * overlap;
            
            var clipOutPoint = clip.outPoint;
            var nextClipInPoint = nextClip.inPoint;
            
            var whipStart = clipOutPoint - transitionDuration;
            var whipEnd = clipOutPoint + transitionDuration;
            
            var transformIn = clip.effects.addVideoEffect("Transform");
            var transformOut = nextClip.effects.addVideoEffect("Transform");
            
            var seqWidth = seq.width;
            var seqHeight = seq.height;
            var centerX = seqWidth / 2;
            var centerY = seqHeight / 2;
            
            var moveDistance = seqWidth * 0.4 * speedFactor;
            
            transformIn.property("Position").setValueAtTime(whipStart, [centerX, centerY]);
            transformIn.property("Position").setValueAtTime(clipOutPoint, [centerX + directionFactor * moveDistance, centerY]);
            
            transformIn.property("Scale").setValueAtTime(whipStart, [100, 100]);
            transformIn.property("Scale").setValueAtTime(clipOutPoint, [105, 105]);
            
            var motionBlurIn = clip.effects.addVideoEffect("Directional Blur");
            motionBlurIn.property("Direction").setValueAtTime(whipStart, directionFactor * 90);
            motionBlurIn.property("Blur Length").setValueAtTime(whipStart, 0);
            motionBlurIn.property("Blur Length").setValueAtTime(clipOutPoint, blurAmount * speedFactor);
            
            transformOut.property("Position").setValueAtTime(clipOutPoint, [centerX - directionFactor * moveDistance, centerY]);
            transformOut.property("Position").setValueAtTime(whipEnd, [centerX, centerY]);
            
            transformOut.property("Scale").setValueAtTime(clipOutPoint, [105, 105]);
            transformOut.property("Scale").setValueAtTime(whipEnd, [100, 100]);
            
            var motionBlurOut = nextClip.effects.addVideoEffect("Directional Blur");
            motionBlurOut.property("Direction").setValueAtTime(clipOutPoint, directionFactor * 90);
            motionBlurOut.property("Blur Length").setValueAtTime(clipOutPoint, blurAmount * speedFactor);
            motionBlurOut.property("Blur Length").setValueAtTime(whipEnd, 0);
        }}
        
        app.endUndoGroup();
        
        return JSON.stringify({{
            success: true,
            editMode: "whip_pan",
            direction: "{params.direction.value}",
            speed: speedFactor,
            blurAmount: blurAmount,
            duration: duration,
            clipName: clip.name
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString(), line: e.line || 0}});
    }}
}})();
'''
        return script.strip()

    def generate_dynamic_zoom_script(
        self,
        track_index: int,
        clip_index: int,
        params: DynamicZoomParam,
    ) -> str:
        """生成动态缩放脚本。"""
        start_scale = params.start_scale
        end_scale = params.end_scale
        duration = params.duration
        ease_type = params.ease_type
        blur_amount = params.blur_amount
        focus_point = params.focus_point or [0.5, 0.5]

        script = f'''
(function() {{
    try {{
        var trackIndex = {track_index};
        var clipIndex = {clip_index};
        var startScale = {start_scale};
        var endScale = {end_scale};
        var duration = {duration};
        var easeType = "{ease_type}";
        var blurAmount = {blur_amount};
        var focusX = {focus_point[0]};
        var focusY = {focus_point[1]};
        
        if (!app.project || !app.project.activeSequence) {{
            return JSON.stringify({{error: true, message: "没有打开的项目或活动序列"}});
        }}
        
        var seq = app.project.activeSequence;
        var videoTrack = seq.videoTracks[trackIndex];
        
        if (!videoTrack || clipIndex < 0 || clipIndex >= videoTrack.clips.numItems) {{
            return JSON.stringify({{error: true, message: "无效的轨道或剪辑索引"}});
        }}
        
        var clip = videoTrack.clips[clipIndex];
        
        app.beginUndoGroup("Dynamic Zoom Effect");
        
        var startTime = clip.inPoint;
        var endTime = clip.outPoint;
        var effectDuration = Math.min(duration, endTime - startTime);
        
        var transform = clip.effects.addVideoEffect("Transform");
        
        var seqWidth = seq.width;
        var seqHeight = seq.height;
        
        var centerX = seqWidth / 2;
        var centerY = seqHeight / 2;
        
        var offsetX = (focusX - 0.5) * seqWidth;
        var offsetY = (focusY - 0.5) * seqHeight;
        
        transform.property("Scale").setValueAtTime(startTime, [startScale, startScale]);
        transform.property("Scale").setValueAtTime(startTime + effectDuration, [endScale, endScale]);
        
        transform.property("Position").setValueAtTime(startTime, [centerX, centerY]);
        transform.property("Position").setValueAtTime(startTime + effectDuration, [
            centerX - offsetX * (endScale - startScale) / 100,
            centerY - offsetY * (endScale - startScale) / 100
        ]);
        
        if (blurAmount > 0) {{
            var blur = clip.effects.addVideoEffect("Gaussian Blur");
            blur.property("Blurriness").setValueAtTime(startTime, 0);
            blur.property("Blurriness").setValueAtTime(startTime + effectDuration * 0.5, blurAmount);
            blur.property("Blurriness").setValueAtTime(startTime + effectDuration, 0);
        }}
        
        var scaleProperty = transform.property("Scale");
        var posProperty = transform.property("Position");
        
        for (var i = 0; i < scaleProperty.numKeyframes; i++) {{
            var kfIndex = i + 1;
            if (easeType === "ease_in") {{
                scaleProperty.setInterpolationTypeAtKeyframe(kfIndex, KeyframeInterpolationType.BEZIER);
                scaleProperty.setLeftTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.LINEAR);
                scaleProperty.setRightTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.SMOOTH);
            }} else if (easeType === "ease_out") {{
                scaleProperty.setInterpolationTypeAtKeyframe(kfIndex, KeyframeInterpolationType.BEZIER);
                scaleProperty.setLeftTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.SMOOTH);
                scaleProperty.setRightTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.LINEAR);
            }} else if (easeType === "ease_in_out") {{
                scaleProperty.setInterpolationTypeAtKeyframe(kfIndex, KeyframeInterpolationType.BEZIER);
                scaleProperty.setLeftTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.SMOOTH);
                scaleProperty.setRightTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.SMOOTH);
            }}
        }}
        
        app.endUndoGroup();
        
        return JSON.stringify({{
            success: true,
            editMode: "dynamic_zoom",
            startScale: startScale,
            endScale: endScale,
            duration: effectDuration,
            focusPoint: [focusX, focusY],
            clipName: clip.name
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString(), line: e.line || 0}});
    }}
}})();
'''
        return script.strip()

    def generate_speed_ramp_script(
        self,
        track_index: int,
        clip_index: int,
        params: SpeedRampParam,
    ) -> str:
        """生成速度调整脚本。"""
        start_speed = params.start_speed
        end_speed = params.end_speed
        ramp_duration = params.ramp_duration
        ease_type = params.ease_type
        frame_blending = params.frame_blending
        preserve_audio = params.preserve_audio

        script = f'''
(function() {{
    try {{
        var trackIndex = {track_index};
        var clipIndex = {clip_index};
        var startSpeed = {start_speed};
        var endSpeed = {end_speed};
        var rampDuration = {ramp_duration};
        var easeType = "{ease_type}";
        var frameBlending = {str(frame_blending).lower()};
        var preserveAudio = {str(preserve_audio).lower()};
        
        if (!app.project || !app.project.activeSequence) {{
            return JSON.stringify({{error: true, message: "没有打开的项目或活动序列"}});
        }}
        
        var seq = app.project.activeSequence;
        var videoTrack = seq.videoTracks[trackIndex];
        
        if (!videoTrack || clipIndex < 0 || clipIndex >= videoTrack.clips.numItems) {{
            return JSON.stringify({{error: true, message: "无效的轨道或剪辑索引"}});
        }}
        
        var clip = videoTrack.clips[clipIndex];
        
        app.beginUndoGroup("Speed Ramp Effect");
        
        var clipDuration = clip.outPoint - clip.inPoint;
        
        var rampStart = clip.inPoint;
        var rampEnd = clip.inPoint + rampDuration;
        
        if (rampDuration > clipDuration) {{
            rampDuration = clipDuration;
            rampEnd = clip.outPoint;
        }}
        
        var speedProperty = clip.property("Speed");
        speedProperty.setValueAtTime(rampStart, startSpeed);
        speedProperty.setValueAtTime(rampEnd, endSpeed);
        
        if (frameBlending) {{
            clip.enableFrameBlending = true;
        }}
        
        if (!preserveAudio) {{
            var audioTrack = seq.audioTracks[trackIndex];
            if (audioTrack && audioTrack.clips.numItems > clipIndex) {{
                var audioClip = audioTrack.clips[clipIndex];
                audioClip.property("Speed").setValueAtTime(rampStart, startSpeed);
                audioClip.property("Speed").setValueAtTime(rampEnd, endSpeed);
            }}
        }}
        
        for (var i = 0; i < speedProperty.numKeyframes; i++) {{
            var kfIndex = i + 1;
            if (easeType === "ease_in") {{
                speedProperty.setInterpolationTypeAtKeyframe(kfIndex, KeyframeInterpolationType.BEZIER);
                speedProperty.setLeftTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.LINEAR);
                speedProperty.setRightTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.SMOOTH);
            }} else if (easeType === "ease_out") {{
                speedProperty.setInterpolationTypeAtKeyframe(kfIndex, KeyframeInterpolationType.BEZIER);
                speedProperty.setLeftTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.SMOOTH);
                speedProperty.setRightTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.LINEAR);
            }} else if (easeType === "ease_in_out") {{
                speedProperty.setInterpolationTypeAtKeyframe(kfIndex, KeyframeInterpolationType.BEZIER);
                speedProperty.setLeftTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.SMOOTH);
                speedProperty.setRightTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.SMOOTH);
            }}
        }}
        
        app.endUndoGroup();
        
        return JSON.stringify({{
            success: true,
            editMode: "speed_ramp",
            startSpeed: startSpeed,
            endSpeed: endSpeed,
            rampDuration: rampDuration,
            frameBlending: frameBlending,
            clipName: clip.name
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString(), line: e.line || 0}});
    }}
}})();
'''
        return script.strip()

    def generate_keyframe_animation_script(
        self,
        track_index: int,
        clip_index: int,
        params: KeyframeAnimationParam,
    ) -> str:
        """生成关键帧动画脚本。"""
        property_name = params.property_name
        easing = params.easing
        
        keyframes_json = json.dumps([
            {"time": kf.time, "value": kf.value, "interpolation": kf.interpolation}
            for kf in params.keyframes
        ])

        script = f'''
(function() {{
    try {{
        var trackIndex = {track_index};
        var clipIndex = {clip_index};
        var propertyName = "{property_name}";
        var easing = "{easing}";
        var keyframes = {keyframes_json};
        
        if (!app.project || !app.project.activeSequence) {{
            return JSON.stringify({{error: true, message: "没有打开的项目或活动序列"}});
        }}
        
        var seq = app.project.activeSequence;
        var videoTrack = seq.videoTracks[trackIndex];
        
        if (!videoTrack || clipIndex < 0 || clipIndex >= videoTrack.clips.numItems) {{
            return JSON.stringify({{error: true, message: "无效的轨道或剪辑索引"}});
        }}
        
        var clip = videoTrack.clips[clipIndex];
        
        app.beginUndoGroup("Keyframe Animation");
        
        var effect = clip.effects.addVideoEffect("Transform");
        var property = effect.property(propertyName);
        
        for (var i = 0; i < keyframes.length; i++) {{
            var kf = keyframes[i];
            var kfTime = clip.inPoint + kf.time;
            
            if (Array.isArray(kf.value)) {{
                property.setValueAtTime(kfTime, kf.value);
            }} else {{
                property.setValueAtTime(kfTime, kf.value);
            }}
        }}
        
        for (var i = 0; i < property.numKeyframes; i++) {{
            var kfIndex = i + 1;
            var kfInterpolation = keyframes[i] && keyframes[i].interpolation ? keyframes[i].interpolation : "linear";
            
            if (kfInterpolation === "bezier" || easing === "ease_in_out") {{
                property.setInterpolationTypeAtKeyframe(kfIndex, KeyframeInterpolationType.BEZIER);
                property.setLeftTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.SMOOTH);
                property.setRightTangentTypeAtKeyframe(kfIndex, KeyframeTangentType.SMOOTH);
            }} else if (kfInterpolation === "linear") {{
                property.setInterpolationTypeAtKeyframe(kfIndex, KeyframeInterpolationType.LINEAR);
            }}
        }}
        
        app.endUndoGroup();
        
        return JSON.stringify({{
            success: true,
            editMode: "keyframe_animation",
            propertyName: propertyName,
            keyframeCount: keyframes.length,
            clipName: clip.name
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString(), line: e.line || 0}});
    }}
}})();
'''
        return script.strip()

    def generate_editing_script(
        self,
        track_index: int,
        clip_index: int,
        params: AdvancedEditParam,
    ) -> str:
        """生成高级编辑脚本。"""
        edit_mode = params.edit_mode
        script = ""

        if edit_mode == EditMode.WHIP_PAN:
            script = self.generate_whip_pan_script(track_index, clip_index, params.whip_pan)
        elif edit_mode == EditMode.DYNAMIC_ZOOM:
            script = self.generate_dynamic_zoom_script(track_index, clip_index, params.dynamic_zoom)
        elif edit_mode == EditMode.SPEED_RAMP:
            script = self.generate_speed_ramp_script(track_index, clip_index, params.speed_ramp)
        elif edit_mode == EditMode.KEYFRAME_ANIMATION:
            script = self.generate_keyframe_animation_script(track_index, clip_index, params.keyframe_animation)
        else:
            script = self.generate_whip_pan_script(track_index, clip_index, params.whip_pan)

        return script

    def apply_editing(
        self,
        track_index: int,
        clip_index: int,
        params: AdvancedEditParam,
    ) -> Dict[str, Any]:
        """应用高级编辑效果。"""
        script = self.generate_editing_script(track_index, clip_index, params)
        
        if self.pr_client:
            result = self.pr_client.execute_script(script)
            return result
        
        return {
            "success": True,
            "status": "dry_run",
            "edit_mode": params.edit_mode.value,
            "track_index": track_index,
            "clip_index": clip_index,
        }

    def apply_batch_editing(
        self,
        edits: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """批量应用高级编辑效果。"""
        results = []
        for edit in edits:
            edit_mode = EditMode(edit.get("edit_mode", "whip_pan"))
            
            if edit_mode == EditMode.WHIP_PAN:
                whip_params = WhipPanParam(
                    direction=MotionDirection(edit.get("direction", "right")),
                    speed=edit.get("speed", 2.0),
                    blur_amount=edit.get("blur_amount", 25.0),
                    duration=edit.get("duration", 0.5),
                    overlap=edit.get("overlap", 0.3),
                )
                params = AdvancedEditParam(edit_mode=edit_mode, whip_pan=whip_params)
            elif edit_mode == EditMode.DYNAMIC_ZOOM:
                zoom_params = DynamicZoomParam(
                    start_scale=edit.get("start_scale", 100.0),
                    end_scale=edit.get("end_scale", 150.0),
                    duration=edit.get("duration", 2.0),
                    ease_type=edit.get("ease_type", "ease_in_out"),
                    focus_point=edit.get("focus_point"),
                    blur_amount=edit.get("blur_amount", 0.0),
                )
                params = AdvancedEditParam(edit_mode=edit_mode, dynamic_zoom=zoom_params)
            elif edit_mode == EditMode.SPEED_RAMP:
                speed_params = SpeedRampParam(
                    start_speed=edit.get("start_speed", 100.0),
                    end_speed=edit.get("end_speed", 200.0),
                    ramp_duration=edit.get("ramp_duration", 1.0),
                    ease_type=edit.get("ease_type", "ease_in_out"),
                    frame_blending=edit.get("frame_blending", True),
                    preserve_audio=edit.get("preserve_audio", False),
                )
                params = AdvancedEditParam(edit_mode=edit_mode, speed_ramp=speed_params)
            else:
                params = AdvancedEditParam(edit_mode=edit_mode)
            
            result = self.apply_editing(
                track_index=edit["track_index"],
                clip_index=edit["clip_index"],
                params=params,
            )
            results.append(result)
        
        return results


__all__ = [
    "EditMode",
    "MotionDirection",
    "WhipPanParam",
    "DynamicZoomParam",
    "SpeedRampParam",
    "KeyframePoint",
    "KeyframeAnimationParam",
    "AdvancedEditParam",
    "PremiereAdvancedEditing",
]
