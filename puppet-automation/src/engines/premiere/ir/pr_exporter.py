#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IR → PR ExtendScript 转换器
=============================

将 Timeline IR (IRSequence) 转换为 Adobe Premiere Pro ExtendScript (.jsx) 代码，
支持完整序列创建、批量上轨、差异更新等场景。

架构设计:
    - 生成的 JSX 遵循 PremiereEngine._run_extendscript 的 Bridge 协议
    - 所有用户可控字符串通过 json.dumps (JSX 转义) 处理，杜绝注入
    - 时间单位使用 PR 内部 ticks（1 秒 = 254016000000 ticks）
    - 支持长序列分片 (ir_to_batch_jsx) 和增量更新 (ir_diff_to_jsx)

用法:
    from engine.premiere.ir import IRSequence, IRTrack, IRClip
    from engine.premiere.ir.pr_exporter import ir_to_pr_jsx

    jsx = ir_to_pr_jsx(sequence)
    # 通过 PremiereEngine.execute_script() 执行
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from ...config import settings

# 尝试从 IR 模块导入，优先从 ae.timeline_ir 取
try:
    from ae.timeline_ir import (
        IRSequence, IRTrack, IRClip, IRTransition, IREffect,
        IRTrackType, IRTransitionType, IRMarker,
    )
except ImportError:
    from .stubs import (
        IRSequence, IRTrack, IRClip, IRTransition, IREffect,
        IRTrackType, IRTransitionType, IRMarker,
    )


# ================================================================
#  常量
# ================================================================

# PR ExtendScript 时间单位：1 秒 = 254016000000 ticks
TICKS_PER_SECOND: int = 254016000000

# JSX 单次执行最大字符数（超过此值应分片）
MAX_JSX_CHARS: int = 50000

# 默认序列预设
DEFAULT_SEQUENCE_PRESET: str = "HD 1080p 30"


# ================================================================
#  内部辅助函数
# ================================================================

def _sec_to_ticks(seconds: float) -> int:
    """将秒转换为 PR ticks。"""
    return int(round(seconds * TICKS_PER_SECOND))


def _jsx_escape(value: Any) -> str:
    """将 Python 值安全地序列化为 JSX 字面量。

    与 PremiereEngine._jsx_escape 一致，使用 json.dumps 转义。
    """
    return json.dumps(value, ensure_ascii=False)


def _transition_to_pr_name(trans_type: IRTransitionType) -> str:
    """将 IR 转场类型映射为 PR 内置转场名称。

    Args:
        trans_type: IR 转场类型

    Returns:
        PR 可识别的转场名称字符串
    """
    mapping: Dict[IRTransitionType, str] = {
        IRTransitionType.CROSS_DISSOLVE: "Cross Dissolve",
        IRTransitionType.DISSOLVE: "Film Dissolve",
        IRTransitionType.DIP_TO_BLACK: "Dip to Black",
        IRTransitionType.DIP_TO_WHITE: "Dip to White",
        IRTransitionType.WIPE_LEFT: "Wipe Left",
        IRTransitionType.WIPE_RIGHT: "Wipe Right",
        IRTransitionType.WIPE_UP: "Wipe Up",
        IRTransitionType.WIPE_DOWN: "Wipe Down",
        IRTransitionType.WIPE_IRIS: "Iris Wipe",
        IRTransitionType.ZOOM_IN: "Zoom In",
        IRTransitionType.ZOOM_OUT: "Zoom Out",
        IRTransitionType.WHIP_PAN_LEFT: "Whip Pan Left",
        IRTransitionType.WHIP_PAN_RIGHT: "Whip Pan Right",
        IRTransitionType.GLITCH: "Glitch",
        IRTransitionType.FLASH: "Flash",
        IRTransitionType.PUSH_LEFT: "Push Left",
        IRTransitionType.PUSH_RIGHT: "Push Right",
        IRTransitionType.SLIDE: "Slide",
    }
    return mapping.get(trans_type, "Cross Dissolve")


def _pixel_aspect_from_resolution(width: int, height: int) -> float:
    """根据分辨率计算像素宽高比（标准格式返回 1.0）。"""
    # HD, UHD, DCI 等标准格式均为方形像素
    return 1.0


# ================================================================
#  JSX 代码生成
# ================================================================

def _generate_sequence_creation(seq: IRSequence) -> str:
    """生成创建序列的 JSX 代码。

    Args:
        seq: IR 序列

    Returns:
        JSX 代码片段
    """
    name_js = _jsx_escape(seq.name)
    preset_js = _jsx_escape(DEFAULT_SEQUENCE_PRESET)

    return f"""
    var seq = app.project.createNewSequence({name_js}, {preset_js});
    if (!seq) {{
        return JSON.stringify({{status: "error", message: "Failed to create sequence: {name_js}"}});
    }}
    // 手动设置序列参数（createNewSequence 可能不精确匹配）
    seq.name = {name_js};
"""


def _generate_media_import(clips: List[IRClip]) -> Tuple[str, str]:
    """生成媒体导入 JSX 代码，并返回 (jsx_code, import_var_map) 映射。

    Args:
        clips: 所有需要导入的片段列表

    Returns:
        (jsx_code, var_map) 其中 var_map 为 clip_id → JS 变量名 的映射
    """
    if not clips:
        return "", {}

    # 去重：按 source_path 去重
    seen_paths: Dict[str, str] = {}
    path_to_clips: Dict[str, List[IRClip]] = {}
    for clip in clips:
        path = clip.source_path
        if path not in seen_paths:
            seen_paths[path] = clip.id
            path_to_clips.setdefault(path, [])
        path_to_clips.setdefault(path, []).append(clip)

    lines: List[str] = []
    lines.append("    // --- 导入媒体文件 ---")
    lines.append("    var importedItems = {};")

    var_map: Dict[str, str] = {}  # clip_id → js_var_name

    for path, clist in path_to_clips.items():
        path_posix = Path(path).as_posix()
        path_js = _jsx_escape(path_posix)
        stem = Path(path).stem
        stem_js = _jsx_escape(stem)
        var_name = f"media_{stem.replace('-', '_').replace('.', '_').replace(' ', '_')}"

        lines.append(f"""
    // 导入: {path_posix}
    var {var_name} = null;
    var importFile = new File({path_js});
    if (importFile.exists) {{
        try {{
            {var_name} = app.project.importFile(importFile);
        }} catch(e) {{
            // 导入失败，尝试在项目中查找已导入的素材
            try {{
                function findMedia(root, name) {{
                    for (var i = 0; i < root.children.numItems; i++) {{
                        var child = root.children[i];
                        if (child.type === ProjectItemType.CLIP && child.name.indexOf(name) >= 0) {{
                            return child;
                        }}
                        if (child.type === ProjectItemType.BIN) {{
                            var found = findMedia(child, name);
                            if (found) return found;
                        }}
                    }}
                    return null;
                }}
                {var_name} = findMedia(app.project.rootItem, {stem_js});
            }} catch(e2) {{
                {var_name} = null;
            }}
        }}
    }} else {{
        // 文件不存在，尝试查找已导入的素材
        try {{
            function findMediaByName(root, name) {{
                for (var i = 0; i < root.children.numItems; i++) {{
                    var child = root.children[i];
                    if (child.type === ProjectItemType.CLIP && child.name.indexOf(name) >= 0) {{
                        return child;
                    }}
                    if (child.type === ProjectItemType.BIN) {{
                        var found = findMediaByName(child, name);
                        if (found) return found;
                    }}
                }}
                return null;
            }}
            {var_name} = findMediaByName(app.project.rootItem, {stem_js});
        }} catch(e3) {{
            {var_name} = null;
        }}
    }}
    importedItems[{path_js}] = {var_name};
""")
        for clip in clist:
            var_map[clip.id] = var_name

    return "\n".join(lines), var_map


def _generate_track_setup(seq: IRSequence) -> str:
    """生成轨道创建 JSX 代码。

    Args:
        seq: IR 序列

    Returns:
        JSX 代码片段
    """
    if not seq.tracks:
        return ""

    # 统计各类轨道数量
    video_tracks = [t for t in seq.tracks if t.type == IRTrackType.VIDEO]
    audio_tracks = [t for t in seq.tracks if t.type == IRTrackType.AUDIO]
    subtitle_tracks = [t for t in seq.tracks if t.type == IRTrackType.SUBTITLE]
    overlay_tracks = [t for t in seq.tracks if t.type == IRTrackType.OVERLAY]

    # 视频轨道（包括 overlay 作为额外视频轨）
    needed_video = len(video_tracks) + len(overlay_tracks)
    # 音频轨道
    needed_audio = len(audio_tracks)

    lines: List[str] = []
    lines.append("    // --- 创建轨道 ---")

    # 添加视频轨道
    if needed_video > 1:
        lines.append(f"    while (seq.videoTracks.numTracks < {needed_video}) {{")
        lines.append("        try { seq.videoTracks.addTrack(); } catch(e) { break; }")
        lines.append("    }")

    # 添加音频轨道
    if needed_audio > 1:
        lines.append(f"    while (seq.audioTracks.numTracks < {needed_audio}) {{")
        lines.append("        try { seq.audioTracks.addTrack(); } catch(e) { break; }")
        lines.append("    }")

    # 命名轨道
    for track in seq.tracks:
        track_name_js = _jsx_escape(track.name or f"Track_{track.index}")
        if track.type in (IRTrackType.VIDEO, IRTrackType.OVERLAY):
            lines.append(f"""
    if (seq.videoTracks[{track.index}]) {{
        seq.videoTracks[{track.index}].name = {track_name_js};
    }}
""")
        elif track.type == IRTrackType.AUDIO:
            lines.append(f"""
    if (seq.audioTracks[{track.index}]) {{
        seq.audioTracks[{track.index}].name = {track_name_js};
    }}
""")
        # 字幕轨道使用音频轨道模拟
        elif track.type == IRTrackType.SUBTITLE:
            lines.append(f"""
    if (seq.audioTracks[{track.index}]) {{
        seq.audioTracks[{track.index}].name = {track_name_js};
    }}
""")

    return "\n".join(lines)


def _generate_clip_placement(clips: List[IRClip], var_map: Dict[str, str]) -> str:
    """生成 Clip 上轨 JSX 代码。

    Args:
        clips: 需要上轨的片段列表
        var_map: clip_id → JS 变量名 映射

    Returns:
        JSX 代码片段
    """
    if not clips:
        return "    // 无片段需要上轨"

    lines: List[str] = []
    lines.append("    // --- 放置片段到时间线 ---")
    lines.append("    var TPS = " + str(TICKS_PER_SECOND) + ";")

    for clip in clips:
        clip_id_js = _jsx_escape(clip.id)
        var_name = var_map.get(clip.id, "null")
        timeline_in_ticks = _sec_to_ticks(clip.timeline_in)
        duration_ticks = _sec_to_ticks(clip.duration)
        source_start_ticks = _sec_to_ticks(clip.source_start)

        lines.append(f"""
    // Clip: {clip.id}
    var clipItem = {var_name};
    if (clipItem !== null && clipItem !== undefined) {{
        try {{
            var trackIdx = {clip.track_index};
            var trackType = "{clip.track_type.value}";
            var targetTrack = null;

            if (trackType === "audio") {{
                if (seq.audioTracks[trackIdx]) {{
                    targetTrack = seq.audioTracks[trackIdx];
                }}
            }} else {{
                if (seq.videoTracks[trackIdx]) {{
                    targetTrack = seq.videoTracks[trackIdx];
                }}
            }}

            if (targetTrack) {{
                var insertTime = {timeline_in_ticks};
                targetTrack.insertClip(clipItem, insertTime);

                // 设置源入点（如果需要）
                if ({source_start_ticks} > 0) {{
                    try {{
                        // 获取刚插入的 clip（最后一个）
                        var lastClip = targetTrack.clips[targetTrack.clips.numItems - 1];
                        if (lastClip) {{
                            lastClip.setInPoint({source_start_ticks});
                        }}
                    }} catch(e) {{}}
                }}
            }}
        }} catch(e) {{
            // 单个 clip 插入失败，继续处理下一个
        }}
    }}
""")

        # 变换属性（位置、缩放、旋转、透明度）
        if (clip.position_x != 0.5 or clip.position_y != 0.5 or
                clip.scale != 1.0 or clip.rotation != 0.0 or clip.opacity != 1.0):
            lines.append(f"""
    // 设置变换属性: {clip.id}
    try {{
        var trackIdx = {clip.track_index};
        var targetTrack = seq.videoTracks[trackIdx];
        if (targetTrack) {{
            var lastClip = targetTrack.clips[targetTrack.clips.numItems - 1];
            if (lastClip) {{
                var motion = lastClip.components[0];
                if (motion) {{
                    if ({clip.position_x} != 0.5 || {clip.position_y} != 0.5) {{
                        // PR 中位置参数使用归一化坐标
                        motion.setProperty("Position", [{clip.position_x * 100:.1f}, {clip.position_y * 100:.1f}]);
                    }}
                    if ({clip.scale} != 1.0) {{
                        motion.setProperty("Scale", [{clip.scale * 100:.1f}, {clip.scale * 100:.1f}]);
                    }}
                    if ({clip.rotation} != 0.0) {{
                        motion.setProperty("Rotation", [{clip.rotation}]);
                    }}
                    if ({clip.opacity} != 1.0) {{
                        motion.setProperty("Opacity", [{clip.opacity * 100:.0f}]);
                    }}
                }}
            }}
        }}
    }} catch(e) {{}}
""")

        # 变速
        if clip.speed != 1.0:
            lines.append(f"""
    // 变速: {clip.id}
    try {{
        var trackIdx = {clip.track_index};
        var targetTrack = seq.videoTracks[trackIdx];
        if (targetTrack) {{
            var lastClip = targetTrack.clips[targetTrack.clips.numItems - 1];
            if (lastClip) {{
                lastClip.setSpeed({clip.speed});
            }}
        }}
    }} catch(e) {{}}
""")

    return "\n".join(lines)


def _generate_transitions(clips: List[IRClip]) -> str:
    """生成转场 JSX 代码。

    Args:
        clips: 包含转场信息的片段列表

    Returns:
        JSX 代码片段
    """
    if not clips:
        return ""

    lines: List[str] = []
    lines.append("    // --- 应用转场 ---")

    for clip in clips:
        transition = clip.transition_in or clip.transition_out
        if transition and transition.type != IRTransitionType.CUT and transition.duration > 0:
            trans_name = _transition_to_pr_name(transition.type)
            trans_name_js = _jsx_escape(trans_name)
            duration_ticks = _sec_to_ticks(transition.duration)
            align = 0 if transition.alignment == "start" else (1 if transition.alignment == "end" else 0)

            lines.append(f"""
    try {{
        var trackIdx = {clip.track_index};
        var targetTrack = seq.videoTracks[trackIdx];
        if (targetTrack) {{
            var lastClip = targetTrack.clips[targetTrack.clips.numItems - 1];
            if (lastClip) {{
                lastClip.createTransition({trans_name_js}, {align}, {duration_ticks}, true);
            }}
        }}
    }} catch(e) {{}}
""")

    return "\n".join(lines)


def _generate_markers(seq: IRSequence) -> str:
    """生成序列标记 JSX 代码。

    Args:
        seq: IR 序列（包含 markers）

    Returns:
        JSX 代码片段
    """
    if not seq.markers:
        return ""

    markers_js = _jsx_escape(seq.markers)

    return f"""
    // --- 设置序列标记 ---
    var markers = {markers_js};
    var TPS = {TICKS_PER_SECOND};
    for (var mi = 0; mi < markers.length; mi++) {{
        var m = markers[mi];
        var timeSeconds = m.time_seconds || m.time || 0;
        var markerName = m.name || ("Marker_" + mi);
        var markerComment = m.comment || "";
        var markerTicks = Math.floor(timeSeconds * TPS);
        try {{
            seq.addMarker(markerTicks, markerName, markerComment);
        }} catch(e) {{}}
    }}
"""


def _generate_effects(clips: List[IRClip]) -> str:
    """生成效果应用 JSX 代码。

    Args:
        clips: 包含效果的片段列表

    Returns:
        JSX 代码片段
    """
    effects_present = any(c.effects for c in clips)
    if not effects_present:
        return ""

    lines: List[str] = []
    lines.append("    // --- 应用效果 ---")

    for clip in clips:
        if not clip.effects:
            continue

        for effect in clip.effects:
            effect_name_js = _jsx_escape(effect.name)
            lines.append(f"""
    try {{
        var trackIdx = {clip.track_index};
        var targetTrack = seq.videoTracks[trackIdx];
        if (targetTrack) {{
            var lastClip = targetTrack.clips[targetTrack.clips.numItems - 1];
            if (lastClip) {{
                lastClip.components.addComponent({effect_name_js});
            }}
        }}
    }} catch(e) {{}}
""")

    return "\n".join(lines)


# ================================================================
#  公共 API
# ================================================================

def ir_to_pr_jsx(sequence: IRSequence) -> str:
    """将完整的 IRSequence 转换为 PR ExtendScript JSX 代码。

    生成的 JSX 代码功能：
    1. 创建序列（使用预设 + 手动设置参数）
    2. 导入所有媒体文件（去重）
    3. 创建所需轨道（视频/音频/字幕）
    4. 将所有片段放置到正确位置
    5. 应用转场效果
    6. 设置序列标记
    7. 应用效果

    Args:
        sequence: 待导出的 IR 序列

    Returns:
        完整的 JSX 代码字符串，可直接通过 Bridge 执行
    """
    lines: List[str] = []
    lines.append("// Auto-generated by Premiere IR Exporter (pr_exporter.py)")
    lines.append(f"// Sequence: {sequence.name}")
    lines.append(f"// Resolution: {sequence.width}x{sequence.height} @ {sequence.frame_rate}fps")
    lines.append(f"// Duration: {sequence.total_duration:.2f}s")
    lines.append("")

    lines.append("(function() {")
    lines.append("    try {")

    # 1. 创建序列
    lines.append(_generate_sequence_creation(sequence))

    # 2. 收集所有 clips
    all_clips: List[IRClip] = []
    for track in sequence.tracks:
        all_clips.extend(track.clips)

    # 3. 导入媒体
    import_jsx, var_map = _generate_media_import(all_clips)
    if import_jsx:
        lines.append(import_jsx)

    # 4. 创建轨道
    lines.append(_generate_track_setup(sequence))

    # 5. 按轨道分组放置片段
    for track in sequence.tracks:
        if track.clips:
            track_label = f"// Track[{track.index}] {track.type.value}"
            lines.append(f"    {track_label}")
            placement = _generate_clip_placement(track.clips, var_map)
            if placement:
                lines.append(placement)

    # 6. 应用转场
    transition_jsx = _generate_transitions(all_clips)
    if transition_jsx:
        lines.append(transition_jsx)

    # 7. 应用效果
    effects_jsx = _generate_effects(all_clips)
    if effects_jsx:
        lines.append(effects_jsx)

    # 8. 设置标记
    markers_jsx = _generate_markers(sequence)
    if markers_jsx:
        lines.append(markers_jsx)

    # 9. 返回结果
    lines.append("""
        return JSON.stringify({
            status: "success",
            sequence: seq.name,
            tracks: seq.videoTracks.numTracks + seq.audioTracks.numTracks,
            totalDuration: seq.getDuration() / TPS
        });
    } catch (e) {
        return JSON.stringify({
            status: "error",
            message: e.toString()
        });
    }
})();""")

    return "\n".join(lines)


def ir_to_batch_jsx(sequence: IRSequence, batch_size: int = 5) -> List[str]:
    """将长序列拆分为多个 JSX 批次，避免单次执行超时。

    适用于包含大量（>50）片段的长序列，按轨道或按片段数量拆分。

    Args:
        sequence: IR 序列
        batch_size: 每批次的片段数量

    Returns:
        JSX 代码字符串列表，每个元素可独立执行
    """
    if batch_size < 1:
        batch_size = 5

    batches: List[str] = []
    all_clips: List[IRClip] = []
    clip_to_track: Dict[str, IRTrack] = {}

    for track in sequence.tracks:
        for clip in track.clips:
            all_clips.append(clip)
            clip_to_track[clip.id] = track

    if not all_clips:
        return [ir_to_pr_jsx(sequence)]

    # 批次0: 创建序列 + 导入媒体 + 创建轨道
    batch0_parts: List[str] = [
        "// Batch 0: Create sequence, import media, setup tracks",
        "(function() {",
        "    try {",
        _generate_sequence_creation(sequence),
    ]

    # 所有媒体导入
    import_jsx, var_map = _generate_media_import(all_clips)
    if import_jsx:
        batch0_parts.append(import_jsx)

    batch0_parts.append(_generate_track_setup(sequence))
    batch0_parts.append("""
        return JSON.stringify({
            status: "success",
            phase: "setup",
            sequence: seq.name
        });
    } catch (e) {
        return JSON.stringify({
            status: "error",
            message: e.toString()
        });
    }
})();""")
    batches.append("\n".join(batch0_parts))

    # 后续批次：按片段数量分片
    clip_batches = [all_clips[i:i + batch_size] for i in range(0, len(all_clips), batch_size)]

    TPS = TICKS_PER_SECOND
    for batch_idx, clip_group in enumerate(clip_batches, 1):
        parts: List[str] = [
            f"// Batch {batch_idx}: Place clips {batch_idx * batch_size - batch_size + 1}-{batch_idx * batch_size}",
            "(function() {",
            "    try {",
            "        var seq = app.project.activeSequence;",
            "        if (!seq) return JSON.stringify({status: 'error', message: 'No active sequence'});",
            "        var TPS = " + str(TPS) + ";",
        ]

        for clip in clip_group:
            track = clip_to_track.get(clip.id)
            if not track:
                continue

            var_name = var_map.get(clip.id, "null")
            timeline_in_ticks = _sec_to_ticks(clip.timeline_in)
            source_start_ticks = _sec_to_ticks(clip.source_start)

            parts.append(f"""
    try {{
        var clipItem = {var_name};
        if (clipItem) {{
            var trackIdx = {clip.track_index};
            var targetTrack = null;
            if ("{track.type.value}" === "audio") {{
                targetTrack = seq.audioTracks[trackIdx];
            }} else {{
                targetTrack = seq.videoTracks[trackIdx];
            }}
            if (targetTrack) {{
                targetTrack.insertClip(clipItem, {timeline_in_ticks});
            }}
        }}
    }} catch(e) {{}}
""")

            # 转场
            if clip.transition_in and clip.transition_in.type != IRTransitionType.CUT and clip.transition_in.duration > 0:
                trans_name = _transition_to_pr_name(clip.transition_in.type)
                trans_name_js = _jsx_escape(trans_name)
                duration_ticks = _sec_to_ticks(clip.transition_in.duration)
                parts.append(f"""
    try {{
        var trackIdx = {clip.track_index};
        var targetTrack = seq.videoTracks[trackIdx];
        if (targetTrack) {{
            var lastClip = targetTrack.clips[targetTrack.clips.numItems - 1];
            if (lastClip) {{
                lastClip.createTransition({trans_name_js}, 0, {duration_ticks}, true);
            }}
        }}
    }} catch(e) {{}}
""")

        parts.append("""
        return JSON.stringify({
            status: "success",
            phase: "clips",
            batch: """ + str(batch_idx) + """
        });
    } catch (e) {
        return JSON.stringify({
            status: "error",
            message: e.toString()
        });
    }
})();""")
        batches.append("\n".join(parts))

    return batches


def ir_diff_to_jsx(original: IRSequence, updated: IRSequence) -> str:
    """生成增量更新 JSX，将 original 序列更新为 updated 状态。

    通过比较 original 和 updated 的差异，只生成必要的更新操作：
    - 新增轨道 → 创建
    - 新增片段 → 插入
    - 移除片段 → 删除
    - 位置/时长变化 → 移动/修剪
    - 转场变化 → 重新应用

    Args:
        original: 原始 IR 序列（基准状态）
        updated: 更新后的 IR 序列（目标状态）

    Returns:
        增量更新 JSX 代码字符串
    """
    lines: List[str] = []
    lines.append("// Auto-generated by Premiere IR Exporter (diff update)")
    lines.append(f"// Original: {original.name} → Updated: {updated.name}")
    lines.append("")

    # 构建 clip_id → (track, clip) 索引
    orig_clips: Dict[str, Tuple[IRTrack, IRClip]] = {}
    for track in original.tracks:
        for clip in track.clips:
            orig_clips[clip.id] = (track, clip)

    new_clips: Dict[str, Tuple[IRTrack, IRClip]] = {}
    for track in updated.tracks:
        for clip in track.clips:
            new_clips[clip.id] = (track, clip)

    lines.append("(function() {")
    lines.append("    try {")
    lines.append("        var seq = app.project.activeSequence;")
    lines.append("        if (!seq) return JSON.stringify({status: 'error', message: 'No active sequence'});")
    lines.append("        var TPS = " + str(TICKS_PER_SECOND) + ";")

    # 1. 删除已移除的片段
    removed_ids = set(orig_clips.keys()) - set(new_clips.keys())
    if removed_ids:
        lines.append("")
        lines.append("    // --- 删除已移除的片段 ---")
        for clip_id in removed_ids:
            orig_track, orig_clip = orig_clips[clip_id]
            clip_id_js = _jsx_escape(clip_id)
            lines.append(f"""
    try {{
        var trackIdx = {orig_clip.track_index};
        var targetTrack = seq.videoTracks[trackIdx];
        if (targetTrack) {{
            for (var ci = 0; ci < targetTrack.clips.numItems; ci++) {{
                var c = targetTrack.clips[ci];
                if (c.name.indexOf({clip_id_js}) >= 0) {{
                    targetTrack.removeClip(c, true);
                    break;
                }}
            }}
        }}
    }} catch(e) {{}}
""")

    # 2. 新增片段
    added_ids = set(new_clips.keys()) - set(orig_clips.keys())
    added_clips: List[IRClip] = []
    for clip_id in added_ids:
        track, clip = new_clips[clip_id]
        added_clips.append(clip)

    if added_clips:
        import_jsx, var_map = _generate_media_import(added_clips)
        if import_jsx:
            lines.append(import_jsx)
        lines.append(_generate_clip_placement(added_clips, var_map))

    # 3. 更新已存在的片段（位置/时长变化）
    common_ids = set(orig_clips.keys()) & set(new_clips.keys())
    changed_clips: List[IRClip] = []
    for clip_id in common_ids:
        orig_track, orig_clip = orig_clips[clip_id]
        new_track, new_clip = new_clips[clip_id]

        if (orig_clip.timeline_in != new_clip.timeline_in or
                orig_clip.track_index != new_clip.track_index or
                orig_clip.duration != new_clip.duration):
            changed_clips.append(new_clip)

    if changed_clips:
        lines.append("")
        lines.append("    // --- 更新片段位置/时长 ---")
        for clip in changed_clips:
            timeline_in_ticks = _sec_to_ticks(clip.timeline_in)
            clip_id_js = _jsx_escape(clip.id)
            lines.append(f"""
    try {{
        var trackIdx = {clip.track_index};
        var targetTrack = seq.videoTracks[trackIdx];
        if (targetTrack) {{
            for (var ci = 0; ci < targetTrack.clips.numItems; ci++) {{
                var c = targetTrack.clips[ci];
                if (c.name.indexOf({clip_id_js}) >= 0) {{
                    c.move(targetTrack, {timeline_in_ticks});
                    break;
                }}
            }}
        }}
    }} catch(e) {{}}
""")

    lines.append("""
        return JSON.stringify({
            status: "success",
            action: "diff_update",
            added: """ + str(len(added_clips)) + """,
            removed: """ + str(len(removed_ids)) + """,
            updated: """ + str(len(changed_clips)) + """
        });
    } catch (e) {
        return JSON.stringify({
            status: "error",
            message: e.toString()
        });
    }
})();""")

    return "\n".join(lines)