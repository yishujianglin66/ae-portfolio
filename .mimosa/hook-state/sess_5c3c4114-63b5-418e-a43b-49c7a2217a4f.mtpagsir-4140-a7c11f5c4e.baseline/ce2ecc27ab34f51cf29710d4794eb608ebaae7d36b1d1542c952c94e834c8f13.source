#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Premiere Pro 转场效果系统
==========================

提供丰富的高级转场效果，包括：
- 基础转场（淡入淡出、擦除、滑动等）
- 高级转场（拉镜、缩放、旋转、扭曲等）
- 动态转场（抖动、冲击、闪烁等）
- 自定义转场模板

架构设计：
1. TransitionType 枚举 - 转场类型定义
2. TransitionParam - 转场参数数据类
3. TransitionSystem - 转场系统核心
4. JSX 脚本生成器 - 生成 Premiere Pro ExtendScript
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Union


class TransitionType(str, Enum):
    """转场类型枚举。"""

    DISSOLVE = "dissolve"
    CROSS_DISSOLVE = "cross_dissolve"
    DIP_TO_BLACK = "dip_to_black"
    DIP_TO_WHITE = "dip_to_white"
    
    WIPE = "wipe"
    WIPE_LEFT = "wipe_left"
    WIPE_RIGHT = "wipe_right"
    WIPE_UP = "wipe_up"
    WIPE_DOWN = "wipe_down"
    WIPE_CENTER = "wipe_center"
    WIPE_IRIS = "wipe_iris"
    
    SLIDE = "slide"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    SLIDE_UP = "slide_up"
    SLIDE_DOWN = "slide_down"
    SLIDE_OVER = "slide_over"
    
    CUT = "cut"
    
    ZOOM = "zoom"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    ZOOM_BLUR = "zoom_blur"
    
    WHIP_PAN = "whip_pan"
    WHIP_PAN_LEFT = "whip_pan_left"
    WHIP_PAN_RIGHT = "whip_pan_right"
    
    SPIN = "spin"
    SPIN_CW = "spin_cw"
    SPIN_CCW = "spin_ccw"
    
    STRETCH = "stretch"
    STRETCH_IN = "stretch_in"
    STRETCH_OUT = "stretch_out"
    
    SWIRL = "swirl"
    TWIST = "twist"
    FOLD = "fold"
    PAGE_TURN = "page_turn"
    
    GLITCH = "glitch"
    STROBE = "strobe"
    FLASH = "flash"
    SHAKE = "shake"
    
    PUSH = "push"
    PUSH_LEFT = "push_left"
    PUSH_RIGHT = "push_right"
    
    SHRINK = "shrink"
    EXPAND = "expand"


class TransitionDirection(str, Enum):
    """转场方向枚举。"""
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"
    CENTER = "center"
    IN = "in"
    OUT = "out"
    CW = "cw"
    CCW = "ccw"


@dataclass
class TransitionParam:
    """转场参数数据类。"""
    
    transition_type: TransitionType = TransitionType.CROSS_DISSOLVE
    duration: float = 1.0
    direction: Optional[TransitionDirection] = None
    ease_in: float = 0.0
    ease_out: float = 1.0
    softness: float = 0.0
    border_width: float = 0.0
    border_color: List[float] = field(default_factory=lambda: [0, 0, 0])
    
    zoom_amount: float = 1.5
    rotation_angle: float = 360.0
    blur_amount: float = 20.0
    shake_intensity: float = 10.0
    glitch_amount: float = 5.0
    
    custom_settings: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["transition_type"] = self.transition_type.value
        if self.direction:
            result["direction"] = self.direction.value
        return result


class PremiereTransitionSystem:
    """Premiere Pro 转场效果系统。"""

    def __init__(self, pr_client=None):
        self.pr_client = pr_client

    def get_transition_info(self, transition_type: TransitionType) -> Dict[str, Any]:
        """获取转场效果信息。"""
        info = {
            TransitionType.CROSS_DISSOLVE: {
                "name": "交叉溶解",
                "category": "基础转场",
                "description": "两段剪辑平滑过渡，第一段淡出，第二段淡入",
                "premiere_name": "Cross Dissolve",
                "icon": "◯",
            },
            TransitionType.DIP_TO_BLACK: {
                "name": "淡入黑场",
                "category": "基础转场",
                "description": "画面淡出至黑色，再淡入下一段",
                "premiere_name": "Dip to Black",
                "icon": "⬛",
            },
            TransitionType.DIP_TO_WHITE: {
                "name": "淡入白场",
                "category": "基础转场",
                "description": "画面淡出至白色，再淡入下一段",
                "premiere_name": "Dip to White",
                "icon": "⬜",
            },
            TransitionType.WIPE_LEFT: {
                "name": "向左擦除",
                "category": "擦除转场",
                "description": "画面从右向左擦除，露出下一段",
                "premiere_name": "Wipe Left",
                "icon": "◀",
            },
            TransitionType.WIPE_RIGHT: {
                "name": "向右擦除",
                "category": "擦除转场",
                "description": "画面从左向右擦除，露出下一段",
                "premiere_name": "Wipe Right",
                "icon": "▶",
            },
            TransitionType.WIPE_UP: {
                "name": "向上擦除",
                "category": "擦除转场",
                "description": "画面从下向上擦除，露出下一段",
                "premiere_name": "Wipe Up",
                "icon": "▲",
            },
            TransitionType.WIPE_DOWN: {
                "name": "向下擦除",
                "category": "擦除转场",
                "description": "画面从上向下擦除，露出下一段",
                "premiere_name": "Wipe Down",
                "icon": "▼",
            },
            TransitionType.WIPE_CENTER: {
                "name": "中心辐射",
                "category": "擦除转场",
                "description": "画面从中心向四周辐射擦除",
                "premiere_name": "Iris Round",
                "icon": "◎",
            },
            TransitionType.SLIDE_LEFT: {
                "name": "向左滑动",
                "category": "滑动转场",
                "description": "下一段画面从右侧滑入，覆盖当前画面",
                "premiere_name": "Slide Left",
                "icon": "➡◀",
            },
            TransitionType.SLIDE_RIGHT: {
                "name": "向右滑动",
                "category": "滑动转场",
                "description": "下一段画面从左侧滑入，覆盖当前画面",
                "premiere_name": "Slide Right",
                "icon": "⬅➡",
            },
            TransitionType.SLIDE_UP: {
                "name": "向上滑动",
                "category": "滑动转场",
                "description": "下一段画面从下方滑入，覆盖当前画面",
                "premiere_name": "Slide Up",
                "icon": "⬇⬆",
            },
            TransitionType.SLIDE_DOWN: {
                "name": "向下滑动",
                "category": "滑动转场",
                "description": "下一段画面从上方滑入，覆盖当前画面",
                "premiere_name": "Slide Down",
                "icon": "⬆⬇",
            },
            TransitionType.ZOOM: {
                "name": "缩放转场",
                "category": "高级转场",
                "description": "画面放大并模糊，切换后缩小恢复",
                "premiere_name": "Zoom",
                "icon": "🔍",
            },
            TransitionType.ZOOM_IN: {
                "name": "放大转场",
                "category": "高级转场",
                "description": "画面快速放大，产生冲击感",
                "premiere_name": "Zoom In",
                "icon": "🔍+",
            },
            TransitionType.ZOOM_OUT: {
                "name": "缩小转场",
                "category": "高级转场",
                "description": "画面快速缩小，产生远离感",
                "premiere_name": "Zoom Out",
                "icon": "🔍-",
            },
            TransitionType.WHIP_PAN: {
                "name": "快速摇摄",
                "category": "高级转场",
                "description": "模拟摄像机快速摇摄效果，带有运动模糊",
                "premiere_name": "Whip Pan",
                "icon": "〰",
            },
            TransitionType.WHIP_PAN_LEFT: {
                "name": "快速左摇",
                "category": "高级转场",
                "description": "画面快速向左摇摄切换",
                "premiere_name": "Whip Pan Left",
                "icon": "〰◀",
            },
            TransitionType.WHIP_PAN_RIGHT: {
                "name": "快速右摇",
                "category": "高级转场",
                "description": "画面快速向右摇摄切换",
                "premiere_name": "Whip Pan Right",
                "icon": "〰▶",
            },
            TransitionType.SPIN: {
                "name": "旋转转场",
                "category": "高级转场",
                "description": "画面旋转切换",
                "premiere_name": "Spin",
                "icon": "🌀",
            },
            TransitionType.STRETCH: {
                "name": "拉伸转场",
                "category": "高级转场",
                "description": "画面拉伸变形切换",
                "premiere_name": "Stretch",
                "icon": "↔",
            },
            TransitionType.SWIRL: {
                "name": "漩涡转场",
                "category": "创意转场",
                "description": "画面呈漩涡状扭曲切换",
                "premiere_name": "Swirl",
                "icon": "🌪",
            },
            TransitionType.PAGE_TURN: {
                "name": "翻页转场",
                "category": "创意转场",
                "description": "模拟书页翻页效果",
                "premiere_name": "Page Turn",
                "icon": "📖",
            },
            TransitionType.GLITCH: {
                "name": "故障转场",
                "category": "创意转场",
                "description": "数字故障风格转场",
                "premiere_name": "Glitch",
                "icon": "⚠",
            },
            TransitionType.STROBE: {
                "name": "频闪转场",
                "category": "创意转场",
                "description": "快速黑白闪烁切换",
                "premiere_name": "Strobe",
                "icon": "⚡",
            },
            TransitionType.SHAKE: {
                "name": "抖动转场",
                "category": "创意转场",
                "description": "画面抖动切换，模拟手持拍摄",
                "premiere_name": "Shake",
                "icon": "📸",
            },
            TransitionType.PUSH_LEFT: {
                "name": "左推转场",
                "category": "滑动转场",
                "description": "下一段画面将当前画面向左推出",
                "premiere_name": "Push Left",
                "icon": "➡▶",
            },
            TransitionType.PUSH_RIGHT: {
                "name": "右推转场",
                "category": "滑动转场",
                "description": "下一段画面将当前画面向右推出",
                "premiere_name": "Push Right",
                "icon": "◀⬅",
            },
            TransitionType.CUT: {
                "name": "硬切",
                "category": "基础转场",
                "description": "无过渡直接切换",
                "premiere_name": "Cut",
                "icon": "┼",
            },
        }
        return info.get(transition_type, {
            "name": "未知转场",
            "category": "其他",
            "description": "",
            "premiere_name": transition_type.value.replace("_", " ").title(),
            "icon": "❓",
        })

    def list_transitions(self) -> List[Dict[str, Any]]:
        """列出所有可用转场效果。"""
        transitions = []
        for t_type in TransitionType:
            info = self.get_transition_info(t_type)
            transitions.append({
                "type": t_type.value,
                "name": info["name"],
                "category": info["category"],
                "description": info["description"],
                "premiere_name": info["premiere_name"],
                "icon": info["icon"],
            })
        return transitions

    def list_categories(self) -> List[str]:
        """列出转场分类。"""
        categories = set()
        for t_type in TransitionType:
            info = self.get_transition_info(t_type)
            categories.add(info["category"])
        return sorted(list(categories))

    def get_transitions_by_category(self, category: str) -> List[Dict[str, Any]]:
        """按分类获取转场效果。"""
        transitions = []
        for t_type in TransitionType:
            info = self.get_transition_info(t_type)
            if info["category"] == category:
                transitions.append({
                    "type": t_type.value,
                    "name": info["name"],
                    "category": info["category"],
                    "description": info["description"],
                    "premiere_name": info["premiere_name"],
                    "icon": info["icon"],
                })
        return transitions

    def generate_transition_script(
        self,
        track_index: int,
        clip_index: int,
        params: TransitionParam,
    ) -> str:
        """生成转场效果的 ExtendScript 脚本。"""
        info = self.get_transition_info(params.transition_type)
        premiere_name = info["premiere_name"]

        script_params = {
            "track_index": track_index,
            "clip_index": clip_index,
            "transition_name": premiere_name,
            "duration": params.duration,
            "direction": params.direction.value if params.direction else None,
            "ease_in": params.ease_in,
            "ease_out": params.ease_out,
            "softness": params.softness,
            "border_width": params.border_width,
            "border_color": params.border_color,
            "zoom_amount": params.zoom_amount,
            "rotation_angle": params.rotation_angle,
            "blur_amount": params.blur_amount,
            "shake_intensity": params.shake_intensity,
            "glitch_amount": params.glitch_amount,
        }

        script = f'''
(function() {{
    try {{
        var trackIndex = {script_params["track_index"]};
        var clipIndex = {script_params["clip_index"]};
        var transitionName = "{script_params["transition_name"]}";
        var duration = {script_params["duration"]};
        
        if (!app.project || !app.project.activeSequence) {{
            return JSON.stringify({{error: true, message: "没有打开的项目或活动序列"}});
        }}
        
        var seq = app.project.activeSequence;
        var videoTrack = seq.videoTracks[trackIndex];
        
        if (!videoTrack) {{
            return JSON.stringify({{error: true, message: "轨道不存在: " + trackIndex}});
        }}
        
        var clips = videoTrack.clips;
        if (clipIndex < 0 || clipIndex >= clips.numItems) {{
            return JSON.stringify({{error: true, message: "剪辑索引无效: " + clipIndex}});
        }}
        
        var clip = clips[clipIndex];
        
        app.beginUndoGroup("Apply Transition: " + transitionName);
        
        var transition = clip.applyTransition(transitionName);
        
        if (transition) {{
            transition.duration = duration;
            
            {"transition.softness = " + str(params.softness) + ";" if params.softness > 0 else ""}
            
            {"transition.borderWidth = " + str(params.border_width) + ";" if params.border_width > 0 else ""}
            
            if ({params.border_width} > 0) {{
                var bc = new RGBColor();
                bc.red = {params.border_color[0]};
                bc.green = {params.border_color[1]};
                bc.blue = {params.border_color[2]};
                transition.borderColor = bc;
            }}
            
            app.endUndoGroup();
            
            return JSON.stringify({{
                success: true,
                transitionName: transitionName,
                duration: duration,
                clipName: clip.name,
                trackIndex: trackIndex,
                clipIndex: clipIndex
            }});
        }} else {{
            app.endUndoGroup();
            return JSON.stringify({{error: true, message: "无法应用转场: " + transitionName}});
        }}
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString(), line: e.line || 0}});
    }}
}})();
'''
        return script.strip()

    def generate_advanced_transition_script(
        self,
        track_index: int,
        clip_index: int,
        params: TransitionParam,
    ) -> str:
        """生成高级转场效果的 ExtendScript 脚本（自定义实现）。"""
        transition_type = params.transition_type
        script = ""

        if transition_type in [TransitionType.WHIP_PAN, TransitionType.WHIP_PAN_LEFT, TransitionType.WHIP_PAN_RIGHT]:
            direction = "left" if transition_type == TransitionType.WHIP_PAN_LEFT else "right"
            script = self._generate_whip_pan_script(track_index, clip_index, params, direction)

        elif transition_type in [TransitionType.ZOOM, TransitionType.ZOOM_IN, TransitionType.ZOOM_OUT]:
            script = self._generate_zoom_transition_script(track_index, clip_index, params)

        elif transition_type == TransitionType.GLITCH:
            script = self._generate_glitch_transition_script(track_index, clip_index, params)

        elif transition_type == TransitionType.SHAKE:
            script = self._generate_shake_transition_script(track_index, clip_index, params)

        elif transition_type == TransitionType.SPIN:
            script = self._generate_spin_transition_script(track_index, clip_index, params)

        elif transition_type == TransitionType.SWIRL:
            script = self._generate_swirl_transition_script(track_index, clip_index, params)

        else:
            script = self.generate_transition_script(track_index, clip_index, params)

        return script

    def _generate_whip_pan_script(
        self,
        track_index: int,
        clip_index: int,
        params: TransitionParam,
        direction: str,
    ) -> str:
        """生成拉镜转场脚本。"""
        direction_factor = -1 if direction == "left" else 1
        script = f'''
(function() {{
    try {{
        var trackIndex = {track_index};
        var clipIndex = {clip_index};
        var duration = {params.duration};
        var directionFactor = {direction_factor};
        
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
        
        app.beginUndoGroup("Whip Pan Transition");
        
        var effectName = "Transform";
        
        if (nextClip) {{
            var transformIn = clip.effects.addVideoEffect(effectName);
            var transformOut = nextClip.effects.addVideoEffect(effectName);
            
            var startTime = clip.outPoint - duration * 0.5;
            var endTime = clip.outPoint + duration * 0.5;
            
            transformIn.property("Position").setValueAtTime(startTime, [seq.width / 2, seq.height / 2]);
            transformIn.property("Position").setValueAtTime(clip.outPoint, [seq.width / 2 + directionFactor * seq.width * 0.3, seq.height / 2]);
            
            transformIn.property("Scale").setValueAtTime(startTime, [100, 100]);
            transformIn.property("Scale").setValueAtTime(clip.outPoint, [110, 110]);
            
            var motionBlurIn = clip.effects.addVideoEffect("Directional Blur");
            motionBlurIn.property("Direction").setValueAtTime(startTime, 0);
            motionBlurIn.property("Blur Length").setValueAtTime(startTime, 0);
            motionBlurIn.property("Blur Length").setValueAtTime(clip.outPoint, 30);
            
            transformOut.property("Position").setValueAtTime(clip.outPoint, [seq.width / 2 - directionFactor * seq.width * 0.3, seq.height / 2]);
            transformOut.property("Position").setValueAtTime(endTime, [seq.width / 2, seq.height / 2]);
            
            transformOut.property("Scale").setValueAtTime(clip.outPoint, [110, 110]);
            transformOut.property("Scale").setValueAtTime(endTime, [100, 100]);
            
            var motionBlurOut = nextClip.effects.addVideoEffect("Directional Blur");
            motionBlurOut.property("Blur Length").setValueAtTime(clip.outPoint, 30);
            motionBlurOut.property("Blur Length").setValueAtTime(endTime, 0);
        }}
        
        app.endUndoGroup();
        
        return JSON.stringify({{
            success: true,
            transitionType: "whip_pan",
            direction: "{direction}",
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

    def _generate_zoom_transition_script(
        self,
        track_index: int,
        clip_index: int,
        params: TransitionParam,
    ) -> str:
        """生成缩放转场脚本。"""
        zoom_amount = params.zoom_amount
        blur_amount = params.blur_amount
        script = f'''
(function() {{
    try {{
        var trackIndex = {track_index};
        var clipIndex = {clip_index};
        var duration = {params.duration};
        var zoomAmount = {zoom_amount};
        var blurAmount = {blur_amount};
        
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
        
        app.beginUndoGroup("Zoom Transition");
        
        if (nextClip) {{
            var transformIn = clip.effects.addVideoEffect("Transform");
            var transformOut = nextClip.effects.addVideoEffect("Transform");
            
            var startTime = clip.outPoint - duration;
            
            transformIn.property("Scale").setValueAtTime(startTime, [100, 100]);
            transformIn.property("Scale").setValueAtTime(clip.outPoint, [100 * zoomAmount, 100 * zoomAmount]);
            
            var blurIn = clip.effects.addVideoEffect("Gaussian Blur");
            blurIn.property("Blurriness").setValueAtTime(startTime, 0);
            blurIn.property("Blurriness").setValueAtTime(clip.outPoint, blurAmount);
            
            transformOut.property("Scale").setValueAtTime(clip.outPoint, [100 * zoomAmount, 100 * zoomAmount]);
            transformOut.property("Scale").setValueAtTime(clip.outPoint + duration, [100, 100]);
            
            var blurOut = nextClip.effects.addVideoEffect("Gaussian Blur");
            blurOut.property("Blurriness").setValueAtTime(clip.outPoint, blurAmount);
            blurOut.property("Blurriness").setValueAtTime(clip.outPoint + duration, 0);
        }}
        
        app.endUndoGroup();
        
        return JSON.stringify({{
            success: true,
            transitionType: "zoom",
            zoomAmount: zoomAmount,
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

    def _generate_glitch_transition_script(
        self,
        track_index: int,
        clip_index: int,
        params: TransitionParam,
    ) -> str:
        """生成故障转场脚本。"""
        glitch_amount = params.glitch_amount
        script = f'''
(function() {{
    try {{
        var trackIndex = {track_index};
        var clipIndex = {clip_index};
        var duration = {params.duration};
        var glitchAmount = {glitch_amount};
        
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
        
        app.beginUndoGroup("Glitch Transition");
        
        if (nextClip) {{
            var startTime = clip.outPoint - duration;
            
            var rgbIn = clip.effects.addVideoEffect("RGB Channel");
            var rgbOut = nextClip.effects.addVideoEffect("RGB Channel");
            
            var displacementIn = clip.effects.addVideoEffect("Displacement Map");
            var displacementOut = nextClip.effects.addVideoEffect("Displacement Map");
            
            rgbIn.property("Red Shift").setValueAtTime(startTime, [0, 0]);
            rgbIn.property("Red Shift").setValueAtTime(clip.outPoint, [glitchAmount * 5, 0]);
            rgbIn.property("Green Shift").setValueAtTime(startTime, [0, 0]);
            rgbIn.property("Green Shift").setValueAtTime(clip.outPoint, [0, glitchAmount * 5]);
            
            rgbOut.property("Red Shift").setValueAtTime(clip.outPoint, [glitchAmount * 5, 0]);
            rgbOut.property("Red Shift").setValueAtTime(clip.outPoint + duration, [0, 0]);
            rgbOut.property("Green Shift").setValueAtTime(clip.outPoint, [0, glitchAmount * 5]);
            rgbOut.property("Green Shift").setValueAtTime(clip.outPoint + duration, [0, 0]);
            
            var strobeIn = clip.effects.addVideoEffect("Strobe Light");
            strobeIn.property("Strobe Duration").setValueAtTime(startTime, 0.9);
            strobeIn.property("Strobe Duration").setValueAtTime(clip.outPoint, 0.1);
            
            var strobeOut = nextClip.effects.addVideoEffect("Strobe Light");
            strobeOut.property("Strobe Duration").setValueAtTime(clip.outPoint, 0.1);
            strobeOut.property("Strobe Duration").setValueAtTime(clip.outPoint + duration, 0.9);
        }}
        
        app.endUndoGroup();
        
        return JSON.stringify({{
            success: true,
            transitionType: "glitch",
            glitchAmount: glitchAmount,
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

    def _generate_shake_transition_script(
        self,
        track_index: int,
        clip_index: int,
        params: TransitionParam,
    ) -> str:
        """生成抖动转场脚本。"""
        shake_intensity = params.shake_intensity
        script = f'''
(function() {{
    try {{
        var trackIndex = {track_index};
        var clipIndex = {clip_index};
        var duration = {params.duration};
        var shakeIntensity = {shake_intensity};
        
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
        
        app.beginUndoGroup("Shake Transition");
        
        if (nextClip) {{
            var startTime = clip.outPoint - duration;
            
            var transformIn = clip.effects.addVideoEffect("Transform");
            var transformOut = nextClip.effects.addVideoEffect("Transform");
            
            var posKeyframesIn = transformIn.property("Position");
            var posKeyframesOut = transformOut.property("Position");
            
            var centerX = seq.width / 2;
            var centerY = seq.height / 2;
            
            var numKeyframes = Math.floor(duration * 2);
            for (var i = 0; i <= numKeyframes; i++) {{
                var tIn = startTime + (i / numKeyframes) * duration;
                var tOut = clip.outPoint + (i / numKeyframes) * duration;
                
                var progress = i / numKeyframes;
                var amplitude = shakeIntensity * (1 - progress);
                
                posKeyframesIn.setValueAtTime(tIn, [
                    centerX + (Math.random() - 0.5) * amplitude * 2,
                    centerY + (Math.random() - 0.5) * amplitude * 2
                ]);
                
                posKeyframesOut.setValueAtTime(tOut, [
                    centerX + (Math.random() - 0.5) * amplitude * 2,
                    centerY + (Math.random() - 0.5) * amplitude * 2
                ]);
            }}
            
            posKeyframesIn.setValueAtTime(clip.outPoint, [centerX, centerY]);
            posKeyframesOut.setValueAtTime(clip.outPoint + duration, [centerX, centerY]);
        }}
        
        app.endUndoGroup();
        
        return JSON.stringify({{
            success: true,
            transitionType: "shake",
            shakeIntensity: shakeIntensity,
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

    def _generate_spin_transition_script(
        self,
        track_index: int,
        clip_index: int,
        params: TransitionParam,
    ) -> str:
        """生成旋转转场脚本。"""
        rotation_angle = params.rotation_angle
        script = f'''
(function() {{
    try {{
        var trackIndex = {track_index};
        var clipIndex = {clip_index};
        var duration = {params.duration};
        var rotationAngle = {rotation_angle};
        
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
        
        app.beginUndoGroup("Spin Transition");
        
        if (nextClip) {{
            var startTime = clip.outPoint - duration;
            
            var transformIn = clip.effects.addVideoEffect("Transform");
            var transformOut = nextClip.effects.addVideoEffect("Transform");
            
            transformIn.property("Rotation").setValueAtTime(startTime, 0);
            transformIn.property("Rotation").setValueAtTime(clip.outPoint, rotationAngle);
            transformIn.property("Scale").setValueAtTime(startTime, [100, 100]);
            transformIn.property("Scale").setValueAtTime(clip.outPoint, [0, 0]);
            
            transformOut.property("Rotation").setValueAtTime(clip.outPoint, -rotationAngle);
            transformOut.property("Rotation").setValueAtTime(clip.outPoint + duration, 0);
            transformOut.property("Scale").setValueAtTime(clip.outPoint, [0, 0]);
            transformOut.property("Scale").setValueAtTime(clip.outPoint + duration, [100, 100]);
        }}
        
        app.endUndoGroup();
        
        return JSON.stringify({{
            success: true,
            transitionType: "spin",
            rotationAngle: rotationAngle,
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

    def _generate_swirl_transition_script(
        self,
        track_index: int,
        clip_index: int,
        params: TransitionParam,
    ) -> str:
        """生成漩涡转场脚本。"""
        script = f'''
(function() {{
    try {{
        var trackIndex = {track_index};
        var clipIndex = {clip_index};
        var duration = {params.duration};
        
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
        
        app.beginUndoGroup("Swirl Transition");
        
        if (nextClip) {{
            var startTime = clip.outPoint - duration;
            
            var twirlIn = clip.effects.addVideoEffect("Twirl");
            var twirlOut = nextClip.effects.addVideoEffect("Twirl");
            
            twirlIn.property("Angle").setValueAtTime(startTime, 0);
            twirlIn.property("Angle").setValueAtTime(clip.outPoint, 720);
            twirlIn.property("Radius").setValueAtTime(startTime, 0);
            twirlIn.property("Radius").setValueAtTime(clip.outPoint, Math.max(seq.width, seq.height));
            
            twirlOut.property("Angle").setValueAtTime(clip.outPoint, -720);
            twirlOut.property("Angle").setValueAtTime(clip.outPoint + duration, 0);
            twirlOut.property("Radius").setValueAtTime(clip.outPoint, Math.max(seq.width, seq.height));
            twirlOut.property("Radius").setValueAtTime(clip.outPoint + duration, 0);
        }}
        
        app.endUndoGroup();
        
        return JSON.stringify({{
            success: true,
            transitionType: "swirl",
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

    async def apply_transition(
        self,
        track_index: int,
        clip_index: int,
        params: TransitionParam,
    ) -> Dict[str, Any]:
        """应用转场效果。"""
        script = self.generate_advanced_transition_script(track_index, clip_index, params)
        
        if self.pr_client:
            result = self.pr_client.execute_script(script)
            return result
        
        return {
            "success": True,
            "status": "dry_run",
            "transition_type": params.transition_type.value,
            "track_index": track_index,
            "clip_index": clip_index,
        }

    async def apply_transitions_batch(
        self,
        transitions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """批量应用转场效果。"""
        results = []
        for t in transitions:
            params = TransitionParam(**t.get("params", {}))
            result = await self.apply_transition(
                track_index=t["track_index"],
                clip_index=t["clip_index"],
                params=params,
            )
            results.append(result)
        return results


__all__ = [
    "TransitionType",
    "TransitionDirection",
    "TransitionParam",
    "PremiereTransitionSystem",
]
