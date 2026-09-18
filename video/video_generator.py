import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from training_logger import VideoGenerationLogger

MUSIC_DIR = r"D:\AE-Work\视频素材库"
CLIP_DIR = r"D:\AE-Work\视频素材库"
OUTPUT_DIR = r"D:\AE-Work\成品库"
COMMAND_FILE = r"C:\Users\Administrator\Documents\ae-mcp-bridge\ae_command.json"
RESULT_FILE = r"C:\Users\Administrator\Documents\ae-mcp-bridge\ae_mcp_result.json"

_ENGINES = {}
_ENGINES_INITIALIZED = False


def _get_engine(name: str):
    global _ENGINES_INITIALIZED
    if name not in _ENGINES:
        try:
            if name == "text":
                from text_animation_engine import UnifiedTextAPI
                _ENGINES["text"] = UnifiedTextAPI()
            elif name == "transition":
                from transition_engine import UnifiedTransitionAPI
                _ENGINES["transition"] = UnifiedTransitionAPI()
            elif name == "filter":
                from filter_engine import UnifiedFilterAPI
                _ENGINES["filter"] = UnifiedFilterAPI()
            elif name == "asset":
                from unified_asset_manager import UnifiedAssetManager
                _ENGINES["asset"] = UnifiedAssetManager()
            elif name == "bridge":
                from software_sdk import SoftwareRegistry
                _ENGINES["bridge"] = SoftwareRegistry()
        except ImportError as e:
            print(f"⚠️  引擎加载失败 {name}: {e}")
            return None
    return _ENGINES.get(name)


def ensure_engines():
    global _ENGINES_INITIALIZED
    if _ENGINES_INITIALIZED:
        return
    for name in ["text", "transition", "filter", "asset"]:
        _get_engine(name)
    _ENGINES_INITIALIZED = True


class AECommandClient:
    def __init__(self):
        self.command_id = 0

    def send_command(self, command: str, args: dict) -> dict:
        self.command_id += 1
        
        cmd_data = {
            "command": command,
            "args": args,
            "timestamp": datetime.now().isoformat(),
            "status": "pending",
            "commandId": self.command_id
        }
        
        with open(COMMAND_FILE, "w", encoding="utf-8") as f:
            json.dump(cmd_data, f, ensure_ascii=False, indent=2)
        
        time.sleep(1.5)
        
        max_wait = 30
        wait_interval = 1
        waited = 0
        
        while waited < max_wait:
            try:
                if os.path.exists(RESULT_FILE):
                    with open(RESULT_FILE, "r", encoding="utf-8") as f:
                        result = json.load(f)
                    
                    if result.get("status") == "success" or result.get("status") == "error":
                        return result
            except (json.JSONDecodeError, IOError, OSError) as e:
                print(f"Warning: read result failed at {waited}s: {e}")
            
            time.sleep(wait_interval)
            waited += wait_interval
        
        return {"status": "timeout", "message": "Command timed out"}


class VideoGenerator:
    def __init__(self):
        self.client = AECommandClient()

    def analyze_music(self, music_path: str) -> dict:
        import librosa
        y, sr = librosa.load(music_path, sr=None)
        
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
        spectral_flatness = librosa.feature.spectral_flatness(y=y)
        
        energy = librosa.feature.rms(y=y)
        energy_times = librosa.frames_to_time(range(len(energy[0])), sr=sr)
        
        segments = librosa.segment.agglomerative(chroma, k=8)
        
        return {
            "music_path": music_path,
            "filename": os.path.basename(music_path),
            "duration": len(y) / sr,
            "sample_rate": sr,
            "tempo": float(tempo),
            "beat_times": beat_times.tolist(),
            "num_beats": len(beat_times),
            "energy_curve": {
                "times": energy_times.tolist(),
                "values": energy[0].tolist()
            },
            "chroma_features": chroma.mean(axis=1).tolist(),
            "spectral_contrast": spectral_contrast.mean(axis=1).tolist(),
            "spectral_flatness": float(spectral_flatness.mean()),
            "segments": segments.tolist()
        }

    def analyze_clips(self, clip_paths: list[str]) -> list[dict]:
        import cv2
        import numpy as np
        
        clip_atoms = []
        
        for clip_path in clip_paths:
            cap = cv2.VideoCapture(clip_path)
            try:
                if not cap.isOpened():
                    continue
                
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration = frame_count / fps if fps > 0 else 0
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                frames = []
                for _ in range(min(10, frame_count)):
                    ret, frame = cap.read()
                    if ret:
                        frames.append(frame)
                
                if frames:
                    avg_frame = np.mean(frames, axis=0).astype(np.uint8)
                    hsv = cv2.cvtColor(avg_frame, cv2.COLOR_BGR2HSV)
                    avg_hue = np.mean(hsv[:, :, 0])
                    avg_saturation = np.mean(hsv[:, :, 1])
                    avg_value = np.mean(hsv[:, :, 2])
                    
                    gray_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
                    motion_scores = []
                    for i in range(len(gray_frames) - 1):
                        diff = cv2.absdiff(gray_frames[i], gray_frames[i+1])
                        motion_scores.append(np.mean(diff))
                    avg_motion = np.mean(motion_scores) if motion_scores else 0
                else:
                    avg_hue = avg_saturation = avg_value = avg_motion = 0
                
                clip_atoms.append({
                    "clip_path": clip_path,
                    "filename": os.path.basename(clip_path),
                    "duration": duration,
                    "fps": fps,
                    "width": width,
                    "height": height,
                    "frame_count": frame_count,
                    "avg_hue": float(avg_hue),
                    "avg_saturation": float(avg_saturation),
                    "avg_brightness": float(avg_value),
                    "avg_motion": float(avg_motion),
                    "aspect_ratio": width / height if height > 0 else 16/9
                })
            except Exception as e:
                print(f"Error analyzing {clip_path}: {e}")
            finally:
                cap.release()
        
        return clip_atoms

    def match_audio_video(self, music_analysis: dict, clip_atoms: list[dict]) -> dict:
        beat_times = music_analysis["beat_times"]
        tempo = music_analysis["tempo"]
        
        clip_order = []
        current_time = 0
        
        energy_peaks = sorted(
            [(t, e) for t, e in zip(music_analysis["energy_curve"]["times"], 
                                    music_analysis["energy_curve"]["values"])],
            key=lambda x: -x[1]
        )[:10]
        
        sorted_clips = sorted(clip_atoms, key=lambda x: x["avg_motion"], reverse=True)
        
        beat_index = 0
        for i, clip in enumerate(sorted_clips):
            clip_start = current_time
            
            if beat_index < len(beat_times) and beat_times[beat_index] > clip_start:
                clip_start = beat_times[beat_index]
            
            clip_order.append({
                "clip": clip,
                "start_time": clip_start,
                "end_time": clip_start + clip["duration"],
                "beat_sync": beat_index < len(beat_times),
                "motion_level": "high" if clip["avg_motion"] > 30 else "medium" if clip["avg_motion"] > 10 else "low"
            })
            
            current_time = clip_start + clip["duration"]
            beat_index += 1
        
        return {
            "music_tempo": tempo,
            "total_duration": current_time,
            "clip_order": clip_order,
            "num_clips": len(clip_order),
            "beat_sync_points": [c["start_time"] for c in clip_order if c["beat_sync"]]
        }

    def generate_timeline_plan(self, match_result: dict, music_analysis: dict) -> dict:
        plan = {
            "composition": {
                "name": "AI Generated Video",
                "width": 1920,
                "height": 1080,
                "duration": match_result["total_duration"] + 2,
                "frameRate": 30
            },
            "layers": [],
            "effects": [],
            "keyframes": []
        }
        
        for i, clip_entry in enumerate(match_result["clip_order"]):
            clip = clip_entry["clip"]
            layer_name = f"Clip_{i+1}_{clip['filename']}"
            
            plan["layers"].append({
                "name": layer_name,
                "type": "footage",
                "source": clip["clip_path"],
                "startTime": clip_entry["start_time"],
                "duration": clip["duration"],
                "motionLevel": clip_entry["motion_level"]
            })
            
            if clip_entry["motion_level"] == "high":
                plan["effects"].append({
                    "layerName": layer_name,
                    "effectName": "ADBE Gaussian Blur 2",
                    "settings": {"Blurriness": 2}
                })
                plan["effects"].append({
                    "layerName": layer_name,
                    "effectName": "ADBE Glo2",
                    "settings": {"Glow Radius": 10, "Glow Intensity": 1.5}
                })
            
            if clip_entry["beat_sync"]:
                plan["keyframes"].append({
                    "layerName": layer_name,
                    "propertyName": "Scale",
                    "time": clip_entry["start_time"],
                    "value": [105, 105]
                })
                plan["keyframes"].append({
                    "layerName": layer_name,
                    "propertyName": "Scale",
                    "time": clip_entry["start_time"] + 0.1,
                    "value": [100, 100]
                })
        
        plan["layers"].append({
            "name": "Music Track",
            "type": "audio",
            "source": music_analysis["music_path"],
            "startTime": 0,
            "duration": music_analysis["duration"]
        })
        
        return plan

    def execute_in_ae(self, timeline_plan: dict) -> dict:
        logger = VideoGenerationLogger(
            music_path=timeline_plan["layers"][-1]["source"],
            clip_paths=[l["source"] for l in timeline_plan["layers"] if l["type"] == "footage"],
            output_path=os.path.join(OUTPUT_DIR, f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        )
        
        logger.log_stage("Step 1", "Creating composition")
        
        comp_result = self.client.send_command("createComposition", {
            "name": timeline_plan["composition"]["name"],
            "width": timeline_plan["composition"]["width"],
            "height": timeline_plan["composition"]["height"],
            "duration": timeline_plan["composition"]["duration"],
            "frameRate": timeline_plan["composition"]["frameRate"]
        })
        
        if comp_result.get("status") != "success":
            logger.complete(False, comp_result.get("message", "Unknown error"))
            return comp_result
        
        logger.log_stage("Step 2", "Importing footage")

        layer_stack = []
        for layer in timeline_plan["layers"]:
            if layer["type"] in ["footage", "audio"]:
                import_result = self.client.send_command("importFootage", {
                    "filePath": layer["source"]
                })

                if import_result.get("status") == "success":
                    logger.log_stage("Step 3", f"Placing {layer['filename']}")

                    place_result = self.client.send_command("placeFootageInComp", {
                        "compIndex": 1,
                        "footageName": layer["filename"] if "filename" in layer else os.path.basename(layer["source"]),
                        "startTime": layer["startTime"],
                        "layerName": layer["name"]
                    })
                    layer_stack.insert(0, layer["name"])

        layer_index_map = {name: idx + 1 for idx, name in enumerate(layer_stack)}

        def _resolve_layer_index(effect_or_kf: dict) -> int:
            ln = effect_or_kf.get("layerName")
            if ln and ln in layer_index_map:
                return layer_index_map[ln]
            return 1

        logger.log_stage("Step 4", "Applying effects")

        for effect in timeline_plan["effects"]:
            effect_result = self.client.send_command("applyEffect", {
                "compIndex": 1,
                "layerIndex": _resolve_layer_index(effect),
                "effectMatchName": effect["effectName"],
                "effectSettings": effect["settings"]
            })

        logger.log_stage("Step 5", "Setting keyframes")

        for keyframe in timeline_plan["keyframes"]:
            keyframe_result = self.client.send_command("setLayerKeyframe", {
                "compIndex": 1,
                "layerIndex": _resolve_layer_index(keyframe),
                "propertyName": keyframe["propertyName"],
                "timeInSeconds": keyframe["time"],
                "value": keyframe["value"]
            })
        
        logger.complete(True)
        return {"status": "success", "message": "Video generation completed"}

    def generate_enhanced_timeline_plan(
        self,
        match_result: dict,
        music_analysis: dict,
        style: str = "cinematic",
        include_text: bool = True,
        include_transitions: bool = True,
        include_filters: bool = True
    ) -> dict:
        ensure_engines()
        
        base_plan = self.generate_timeline_plan(match_result, music_analysis)
        
        transition_engine = _get_engine("transition")
        filter_engine = _get_engine("filter")
        text_engine = _get_engine("text")
        
        if include_transitions and transition_engine and hasattr(transition_engine, 'transition_ai'):
            try:
                ai = transition_engine.transition_ai
                recs = []
                if hasattr(ai, 'beat_sync_transitions'):
                    recs = ai.beat_sync_transitions(style=style)
                elif hasattr(ai, 'auto_pick_transition'):
                    recs = [ai.auto_pick_transition(style=style)]
                elif hasattr(ai, 'recommend_by_genre'):
                    recs = ai.recommend_by_genre(genre=style)
                
                if recs and isinstance(recs, list):
                    for i, preset in enumerate(recs[:5]):
                        base_plan["effects"].append({
                            "layerName": f"Transition_{i+1}",
                            "effectName": "transition",
                            "transitionType": getattr(preset, 'name', 'crossfade'),
                            "preset": str(preset),
                            "index": i
                        })
            except Exception as e:
                print(f"⚠️  转场推荐失败: {e}")
        
        if include_filters and filter_engine and hasattr(filter_engine, 'get_ai'):
            try:
                ai = filter_engine.get_ai()
                if hasattr(ai, 'filter_chain_suggest'):
                    try:
                        recs = ai.filter_chain_suggest(scene_type="general", length=3)
                    except TypeError:
                        recs = ai.filter_chain_suggest("general", length=3)
                    if recs and isinstance(recs, list):
                        for rec in recs[:3]:
                            base_plan["effects"].append({
                                "layerName": "Global Style Adjustment",
                                "effectName": "filter",
                                "filterName": str(rec),
                                "style": style,
                                "adjustmentLayer": True
                            })
            except Exception as e:
                print(f"⚠️  滤镜推荐失败: {e}")
        
        if include_text and text_engine:
            tempo = music_analysis.get("tempo", 120)
            duration = music_analysis.get("duration", 60)
            base_plan["effects"].append({
                "layerName": "Title",
                "effectName": "text_animation",
                "text": f"BPM {tempo:.0f}",
                "animationType": "fade_in",
                "startTime": 0,
                "duration": min(3, duration * 0.1),
                "style": style
            })
        
        return base_plan

    def apply_text_overlay(
        self,
        timeline_plan: dict,
        text_items: list[dict]
    ) -> dict:
        """应用文字叠加层 - 支持标题、字幕、角标等多种文字元素"""
        text_engine = _get_engine("text")
        if not text_engine:
            return timeline_plan
        
        for item in text_items:
            text_type = item.get("type", "title")
            content = item.get("content", "")
            start_time = item.get("start_time", 0)
            duration = item.get("duration", 3)
            style = item.get("style", "modern")
            
            try:
                result = text_engine.create_text(
                    software="after_effects",
                    text=content,
                    position=item.get("position", (0.5, 0.5)),
                    params={
                        "font_size": item.get("font_size", 48),
                        "font_color": item.get("font_color", (1, 1, 1)),
                        "animation": item.get("animation", "fade_in"),
                        "style": style
                    }
                )
                
                timeline_plan["layers"].append({
                    "name": f"Text_{text_type}_{len([l for l in timeline_plan['layers'] if l['type']=='text'])+1}",
                    "type": "text",
                    "content": content,
                    "startTime": start_time,
                    "duration": duration,
                    "style": style,
                    "anim_type": item.get("animation", "fade_in"),
                    "generated_jsx": result.get("jsx", "") if isinstance(result, dict) else ""
                })
            except Exception as e:
                print(f"⚠️  文字生成失败: {content} - {e}")
        
        return timeline_plan

    def apply_smart_transitions(
        self,
        timeline_plan: dict,
        transition_style: str = "cinematic",
        beat_synced: bool = True
    ) -> dict:
        transition_engine = _get_engine("transition")
        if not transition_engine:
            return timeline_plan
        
        clip_layers = [l for l in timeline_plan["layers"] if l["type"] == "footage"]
        
        ai_available = hasattr(transition_engine, 'transition_ai')
        preset_lib = hasattr(transition_engine, 'preset_library')
        
        for i in range(len(clip_layers) - 1):
            try:
                preset_name = "crossfade"
                preset_info = {}
                
                if ai_available:
                    recs = transition_engine.transition_ai.smart_match(
                        style=transition_style,
                        beat_sync=beat_synced
                    )
                    if recs and isinstance(recs, list) and len(recs) > 0:
                        preset = recs[i % len(recs)]
                        preset_name = getattr(preset, 'name', 'crossfade')
                        preset_info = {"source": "ai", "preset": str(preset)}
                elif preset_lib:
                    try:
                        preset_list = transition_engine.preset_library.list_presets()
                        if preset_list and len(preset_list) > 0:
                            preset_name = getattr(preset_list[i % len(preset_list)], 'name', 'crossfade')
                    except (AttributeError, IndexError, TypeError) as e:
                        print(f"Warning: preset lookup failed: {e}")
                
                cut_time = clip_layers[i].get("endTime", 
                    clip_layers[i].get("startTime", 0) + clip_layers[i].get("duration", 3))
                
                timeline_plan["effects"].append({
                    "layerName": f"Transition_{i+1}",
                    "effectName": "transition",
                    "fromLayer": clip_layers[i]["name"],
                    "toLayer": clip_layers[i+1]["name"],
                    "startTime": cut_time - 0.25,
                    "duration": 0.5,
                    "transitionType": preset_name,
                    **preset_info
                })
            except Exception as e:
                print(f"⚠️  转场生成失败 ({i}): {e}")
        
        return timeline_plan

    def apply_style_filter_chain(
        self,
        timeline_plan: dict,
        style: str = "cinematic",
        intensity: float = 0.7
    ) -> dict:
        filter_engine = _get_engine("filter")
        if not filter_engine:
            return timeline_plan
        
        try:
            chain = []
            ai_available = hasattr(filter_engine, 'get_ai')
            
            if ai_available:
                ai = filter_engine.get_ai()
                if hasattr(ai, 'filter_chain_suggest'):
                    try:
                        chain = ai.filter_chain_suggest(scene_type="general", length=5)
                    except TypeError:
                        chain = ai.filter_chain_suggest("general", length=5)
                    if not isinstance(chain, list):
                        chain = []
            
            if not chain:
                chain = [
                    f"{style}_color_grade",
                    f"{style}_contrast",
                    f"{style}_vignette"
                ]
            
            timeline_plan["effects"].append({
                "layerName": "Global Style Adjustment",
                "effectName": "filter_chain",
                "style": style,
                "intensity": intensity,
                "filters": chain,
                "adjustmentLayer": True
            })
        except Exception as e:
            print(f"⚠️  滤镜链生成失败: {e}")
        
        return timeline_plan

    def run_enhanced_pipeline(
        self,
        music_path: str,
        clip_paths: list[str],
        style: str = "cinematic",
        include_text: bool = True,
        include_transitions: bool = True,
        include_filters: bool = True,
        text_overlays: list[dict] | None = None
    ) -> dict:
        """增强版流水线 - 集成四大引擎"""
        print("="*70)
        print("🚀 AI 增强视频生成流水线 (四引擎集成版)")
        print("="*70)
        
        base_result = self.run_full_pipeline(music_path, clip_paths)
        
        timeline_plan = base_result.get("timeline_plan", {})
        
        print("\n" + "="*70)
        print("🎨 Step 6/8: 智能转场应用")
        if include_transitions:
            timeline_plan = self.apply_smart_transitions(
                timeline_plan,
                transition_style=style,
                beat_synced=True
            )
            transition_count = len([e for e in timeline_plan.get("effects", []) 
                                   if e.get("effectName") == "transition"])
            print(f"  ✓ 应用了 {transition_count} 个智能转场")
        else:
            print("  ○ 跳过转场")
        
        print("\n🎨 Step 7/8: 风格化滤镜链")
        if include_filters:
            timeline_plan = self.apply_style_filter_chain(
                timeline_plan,
                style=style
            )
            filter_count = len([e for e in timeline_plan.get("effects", [])
                               if e.get("effectName") in ("filter_chain", "filter")])
            print(f"  ✓ 应用了 {filter_count} 组滤镜链")
        else:
            print("  ○ 跳过滤镜")
        
        print("\n🎨 Step 8/8: 文字动画叠加")
        if include_text:
            if text_overlays is None:
                text_overlays = [
                    {"type": "title", "content": "AI Generated", "start_time": 0, 
                     "duration": 3, "style": style, "animation": "fade_in"},
                    {"type": "watermark", "content": "AutoEdit", "start_time": 0,
                     "duration": base_result.get("music_analysis", {}).get("duration", 60),
                     "style": "minimal", "animation": "fade_in"}
                ]
            timeline_plan = self.apply_text_overlay(timeline_plan, text_overlays)
            text_count = len([l for l in timeline_plan.get("layers", []) if l["type"] == "text"])
            print(f"  ✓ 叠加了 {text_count} 个文字元素")
        else:
            print("  ○ 跳过文字")
        
        print("\n" + "="*70)
        print("✨ 增强流水线完成!")
        print("="*70)
        
        enhanced_result = {
            **base_result,
            "timeline_plan": timeline_plan,
            "enhanced": True,
            "style": style,
            "stats": {
                "total_layers": len(timeline_plan.get("layers", [])),
                "total_effects": len(timeline_plan.get("effects", [])),
                "text_layers": len([l for l in timeline_plan.get("layers", []) if l["type"] == "text"]),
                "transitions": len([e for e in timeline_plan.get("effects", []) if e.get("effectName") == "transition"]),
                "filter_chains": len([e for e in timeline_plan.get("effects", []) if e.get("effectName") == "filter_chain"])
            }
        }
        
        return enhanced_result

    def run_full_pipeline(self, music_path: str, clip_paths: list[str]) -> dict:
        print("="*60)
        print("🎬 AI 辅助视频生成端到端流程")
        print("="*60)
        
        print("\n📊 Step 1/5: 音乐分析")
        music_analysis = self.analyze_music(music_path)
        print(f"  ✓ 节拍数: {music_analysis['num_beats']}")
        print(f"  ✓ BPM: {music_analysis['tempo']:.1f}")
        print(f"  ✓ 时长: {music_analysis['duration']:.2f}s")
        
        print("\n📊 Step 2/5: 片段分析")
        clip_atoms = self.analyze_clips(clip_paths)
        print(f"  ✓ 分析了 {len(clip_atoms)} 个片段")
        
        print("\n🎯 Step 3/5: 音画匹配")
        match_result = self.match_audio_video(music_analysis, clip_atoms)
        print(f"  ✓ 匹配完成，共 {match_result['num_clips']} 个片段")
        print(f"  ✓ 总时长: {match_result['total_duration']:.2f}s")
        
        print("\n📝 Step 4/5: 生成时间轴计划")
        timeline_plan = self.generate_timeline_plan(match_result, music_analysis)
        print(f"  ✓ 生成了 {len(timeline_plan['layers'])} 个图层")
        print(f"  ✓ 应用 {len(timeline_plan['effects'])} 个效果")
        print(f"  ✓ 设置 {len(timeline_plan['keyframes'])} 个关键帧")
        
        print("\n🎬 Step 5/5: AE执行")
        ae_result = self.execute_in_ae(timeline_plan)
        print(f"  ✓ AE执行完成: {ae_result.get('status')}")
        
        print("\n" + "="*60)
        print("🎉 流程完成!")
        print("="*60)
        
        return {
            "music_analysis": music_analysis,
            "clip_atoms": clip_atoms,
            "match_result": match_result,
            "timeline_plan": timeline_plan,
            "ae_result": ae_result
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="AI 视频生成器")
    parser.add_argument("--mode", choices=["basic", "enhanced"], default="basic",
                        help="运行模式: basic(基础) / enhanced(增强)")
    parser.add_argument("--style", default="cinematic",
                        help="视觉风格: cinematic/vintage/cyberpunk/dreamy/glitch")
    parser.add_argument("--no-text", action="store_true", help="禁用文字动画")
    parser.add_argument("--no-transitions", action="store_true", help="禁用智能转场")
    parser.add_argument("--no-filters", action="store_true", help="禁用滤镜链")
    args = parser.parse_args()
    
    generator = VideoGenerator()
    
    music_path = os.path.join(MUSIC_DIR, "demo_music.mp3")
    clip_paths = [
        os.path.join(CLIP_DIR, "clip1.mp4"),
        os.path.join(CLIP_DIR, "clip2.mp4"),
        os.path.join(CLIP_DIR, "clip3.mp4")
    ]
    
    existing_clips = [c for c in clip_paths if os.path.exists(c)]
    
    if not os.path.exists(music_path):
        print(f"❌ 音乐文件不存在: {music_path}")
        print("请将音乐文件放入 D:\\AE-Work\\视频素材库\\")
        music_exists = False
    else:
        music_exists = True
    
    if not existing_clips:
        print("⚠️  未找到视频片段，将以演示模式运行")
        clips_exist = False
    else:
        clips_exist = True
    
    if args.mode == "enhanced" or not music_exists or not clips_exist:
        print("="*70)
        print("🧪 引擎加载与功能演示")
        print("="*70)
        
        try:
            ensure_engines()
            text_engine = _get_engine("text")
            transition_engine = _get_engine("transition")
            filter_engine = _get_engine("filter")
            asset_engine = _get_engine("asset")
            
            engines_loaded = sum(1 for e in [text_engine, transition_engine, filter_engine, asset_engine] if e)
            print(f"\n📦 已加载引擎: {engines_loaded}/4")
            
            if text_engine:
                print("  ✓ 文字动画引擎 (TextAnimationEngine)")
            if transition_engine:
                print("  ✓ 转场效果引擎 (TransitionEngine)")
            if filter_engine:
                print("  ✓ 滤镜效果引擎 (FilterEngine)")
            if asset_engine:
                print("  ✓ 素材管理引擎 (UnifiedAssetManager)")
            
            print(f"\n🎨 当前风格: {args.style}")
            print(f"📝 文字动画: {'禁用' if args.no_text else '启用'}")
            print(f"🔄 智能转场: {'禁用' if args.no_transitions else '启用'}")
            print(f"✨ 滤镜链:    {'禁用' if args.no_filters else '启用'}")
            
            if not music_exists or not clips_exist:
                print("\n💡 提示：准备好素材后可使用以下命令运行完整流程：")
                print(f"   python video_generator.py --mode enhanced --style {args.style}")
                print("\n可用风格: cinematic, vintage, cyberpunk, dreamy, glitch, warm, cool, film")
            
        except Exception as e:
            print(f"❌ 引擎初始化错误: {e}")
            import traceback
            traceback.print_exc()
        return
    
    if args.mode == "enhanced":
        result = generator.run_enhanced_pipeline(
            music_path,
            existing_clips,
            style=args.style,
            include_text=not args.no_text,
            include_transitions=not args.no_transitions,
            include_filters=not args.no_filters
        )
    else:
        result = generator.run_full_pipeline(music_path, existing_clips)
    
    output_file = os.path.join(OUTPUT_DIR, f"pipeline_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n📄 结果已保存: {output_file}")


if __name__ == "__main__":
    main()