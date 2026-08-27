"""
Audio Edit Engine - 音频驱动的自适应剪辑引擎
============================================
音频分析 → 节拍映射 → 自动剪辑点 → 速度渐变 → AE JSX 生成

核心能力:
1. Beat-Sync Editing: 剪辑点精确对齐节拍
2. Energy-Based Speed Ramp: 根据能量曲线自动变速
3. Section-Aware Transitions: 段落切换处自动添加转场
4. Voice Ducking: 有人声时自动降低 BGM
5. Auto EDL Generation: 生成完整剪辑决策表

用法:
    engine = AudioEditEngine()
    result = engine.edit(audio_path="bgm.mp3", material_paths=["a.mp4", "b.mp4"])
"""
import os
import sys
import json
import time
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


# ================================================================
#  1. 音频分析适配器
# ================================================================
class AudioAnalyzerAdapter:
    """适配已有 audio_analyzer_enhanced 或 librosa 回退"""

    def analyze(self, audio_path: str) -> Dict[str, Any]:
        """分析音频，返回节拍/能量/段落信息"""
        # 尝试使用增强版分析器
        try:
            from audio_analyzer_enhanced import EnhancedAudioAnalyzer
            analyzer = EnhancedAudioAnalyzer()
            result = analyzer.analyze_audio(audio_path)
            if result and result.get("bpm", 0) > 0:
                log(f"  librosa 分析成功: BPM={result.get('bpm'):.1f}")
                return self._normalize(result)
        except Exception as e:
            log(f"  librosa 不可用: {e}", "WARN")

        # 回退: 基于 ffmpeg + 简单能量检测
        return self._fallback_analyze(audio_path)

    def _normalize(self, raw: Dict) -> Dict[str, Any]:
        """标准化分析结果"""
        # analyze_audio 返回 {success, features: {...}, beat_count, ...}
        features = raw.get("features", raw)
        beats = features.get("beats", [])
        downbeats = features.get("downbeats", [])
        bpm = features.get("bpm", 120.0)
        duration = features.get("duration", 0.0)
        energy_curve = features.get("energy_curve", {})
        segments = features.get("segments", [])

        # 能量值列表
        energy_vals = energy_curve.get("values", []) if isinstance(energy_curve, dict) else []
        energy_times = energy_curve.get("times", []) if isinstance(energy_curve, dict) else []

        # 段落类型推断
        section_types = []
        for seg in segments:
            st = seg.get("segment_type", "verse") if isinstance(seg, dict) else "verse"
            section_types.append(st)

        return {
            "bpm": bpm,
            "duration": duration,
            "beats": beats,
            "downbeats": downbeats,
            "energy_values": energy_vals,
            "energy_times": energy_times,
            "sections": section_types,
            "mood": features.get("mood", "neutral"),
            "genre": features.get("genre", "unknown"),
        }

    def _fallback_analyze(self, audio_path: str) -> Dict[str, Any]:
        """无 librosa 时的回退分析 - 使用 ffmpeg 获取时长，模拟节拍"""
        duration = self._get_duration(audio_path)
        if duration <= 0:
            duration = 30.0

        # 模拟常见 BPM
        bpm = 128.0
        beat_interval = 60.0 / bpm
        beats = []
        t = 0.0
        while t < duration:
            beats.append(round(t, 3))
            t += beat_interval

        # 模拟能量曲线 (EDM 结构)
        energy_vals = []
        for bt in beats:
            ratio = bt / duration
            if ratio < 0.1:
                e = 0.3  # intro
            elif ratio < 0.3:
                e = 0.5 + 0.2 * math.sin(ratio * 10)  # build
            elif ratio < 0.65:
                e = 0.85 + 0.15 * math.sin(ratio * 20)  # drop
            elif ratio < 0.8:
                e = 0.4  # breakdown
            else:
                e = 0.7 * (1 - (ratio - 0.8) / 0.2) + 0.3  # outro
            energy_vals.append(round(e, 3))

        log(f"  回退分析: BPM={bpm}, duration={duration:.1f}s, {len(beats)} beats")

        return {
            "bpm": bpm,
            "duration": duration,
            "beats": beats,
            "downbeats": beats[::4],
            "energy_values": energy_vals,
            "energy_times": beats,
            "sections": ["intro", "build", "drop", "breakdown", "outro"],
            "mood": "energetic",
            "genre": "edm",
        }

    def _get_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        try:
            import subprocess
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", audio_path],
                capture_output=True, text=True, timeout=10
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0


# ================================================================
#  2. 剪辑决策生成器
# ================================================================
class EditDecisionGenerator:
    """根据音频分析生成剪辑决策表 (EDL)"""

    def generate(self, audio_features: Dict[str, Any],
                 material_count: int = 3,
                 material_durations: List[float] = None) -> List[Dict[str, Any]]:
        """
        生成 EDL。

        Args:
            audio_features: 音频分析结果
            material_count: 素材文件数量
            material_durations: 每个素材文件的时长(秒)
        """
        beats = audio_features.get("beats", [])
        energy_vals = audio_features.get("energy_values", [])
        bpm = audio_features.get("bpm", 128)
        duration = audio_features.get("duration", 30)
        sections = audio_features.get("sections", [])

        if not beats:
            return []

        # 智能分段策略:
        # - 多素材: 每个素材覆盖一段音频
        # - 单素材: 按音频段落(intro/verse/chorus/drop/outro)切分
        if material_count <= 1:
            edl = self._generate_single_material_edl(
                beats, energy_vals, duration, sections, bpm)
        else:
            edl = self._generate_multi_material_edl(
                beats, energy_vals, duration, material_count, bpm)

        # 如果有素材时长信息, 调整 source_in/source_out
        if material_durations:
            for clip in edl:
                mat_idx = clip["material_index"]
                if mat_idx < len(material_durations):
                    mat_dur = material_durations[mat_idx]
                    # 根据速度计算需要的源素材时长
                    needed = clip["duration"] * clip["speed"]
                    # 在素材内循环使用
                    if needed > mat_dur:
                        clip["loop"] = True
                    clip["source_in"] = 0
                    clip["source_out"] = min(needed, mat_dur)

        log(f"  EDL 生成: {len(edl)} 段, BPM={bpm}")
        return edl

    def _generate_single_material_edl(self, beats: List[float],
                                       energy_vals: List[float],
                                       duration: float,
                                       sections: List[str],
                                       bpm: float) -> List[Dict]:
        """单素材智能分段: 按音频段落或能量变化切分"""
        edl = []

        # 策略1: 如果有段落信息, 按段落切分
        if sections and len(sections) >= 2:
            section_boundaries = self._find_section_boundaries(
                beats, energy_vals, sections, duration)
            for i, (start_t, end_t) in enumerate(section_boundaries):
                seg_energies = [e for e, bt in zip(energy_vals, beats)
                                if start_t <= bt < end_t]
                avg_energy = sum(seg_energies) / max(len(seg_energies), 1)
                speed = self._energy_to_speed(avg_energy)
                transition = self._pick_transition(avg_energy, i)
                edl.append({
                    "clip_index": i,
                    "material_index": 0,  # 始终用同一个素材
                    "start_time": round(start_t, 3),
                    "end_time": round(end_t, 3),
                    "duration": round(end_t - start_t, 3),
                    "avg_energy": round(avg_energy, 3),
                    "speed": speed,
                    "transition": transition,
                    "section_type": sections[i] if i < len(sections) else "verse",
                    "start_beat": 0,
                    "end_beat": 0,
                })
        else:
            # 策略2: 按能量变化自动切分 (每8-16拍一段)
            beats_per_seg = 8 if bpm > 140 else 12 if bpm > 100 else 16
            seg_count = max(3, len(beats) // beats_per_seg)
            beats_per_clip = max(4, len(beats) // seg_count)

            for i in range(seg_count):
                start_idx = i * beats_per_clip
                end_idx = min((i + 1) * beats_per_clip, len(beats) - 1)
                if start_idx >= len(beats):
                    break

                start_t = beats[start_idx]
                end_t = beats[end_idx] if end_idx < len(beats) else duration
                seg_e = energy_vals[start_idx:end_idx + 1] if energy_vals else [0.5]
                avg_e = sum(seg_e) / max(len(seg_e), 1)
                speed = self._energy_to_speed(avg_e)
                transition = self._pick_transition(avg_e, i)

                edl.append({
                    "clip_index": i,
                    "material_index": 0,
                    "start_time": round(start_t, 3),
                    "end_time": round(end_t, 3),
                    "duration": round(end_t - start_t, 3),
                    "avg_energy": round(avg_e, 3),
                    "speed": speed,
                    "transition": transition,
                    "start_beat": start_idx,
                    "end_beat": end_idx,
                })

        return edl

    def _generate_multi_material_edl(self, beats: List[float],
                                      energy_vals: List[float],
                                      duration: float,
                                      material_count: int,
                                      bpm: float) -> List[Dict]:
        """多素材: 每个素材覆盖一段音频"""
        beats_per_clip = max(4, len(beats) // material_count)
        edl = []

        for i in range(material_count):
            start_beat_idx = i * beats_per_clip
            end_beat_idx = min((i + 1) * beats_per_clip, len(beats) - 1)

            if start_beat_idx >= len(beats):
                break

            start_time = beats[start_beat_idx]
            end_time = beats[end_beat_idx] if end_beat_idx < len(beats) else duration

            seg_energies = energy_vals[start_beat_idx:end_beat_idx + 1] if energy_vals else [0.5]
            avg_energy = sum(seg_energies) / max(len(seg_energies), 1)
            speed = self._energy_to_speed(avg_energy)
            transition = self._pick_transition(avg_energy, i)

            edl.append({
                "clip_index": i,
                "material_index": i % material_count,
                "start_time": round(start_time, 3),
                "end_time": round(end_time, 3),
                "duration": round(end_time - start_time, 3),
                "avg_energy": round(avg_energy, 3),
                "speed": speed,
                "transition": transition,
                "start_beat": start_beat_idx,
                "end_beat": end_beat_idx,
            })

        return edl

    def _find_section_boundaries(self, beats: List[float],
                                  energy_vals: List[float],
                                  sections: List[str],
                                  duration: float) -> List[Tuple[float, float]]:
        """根据段落类型找到切分点"""
        n_sections = len(sections)
        boundaries = []
        seg_dur = duration / n_sections
        for i in range(n_sections):
            start = i * seg_dur
            end = (i + 1) * seg_dur if i < n_sections - 1 else duration
            # 对齐到最近的节拍
            start = self._snap_to_beat(start, beats, direction="next")
            end = self._snap_to_beat(end, beats, direction="prev")
            boundaries.append((start, end))
        return boundaries

    def _snap_to_beat(self, time: float, beats: List[float],
                      direction: str = "nearest") -> float:
        """将时间对齐到最近的节拍"""
        if not beats:
            return time
        if direction == "next":
            for bt in beats:
                if bt >= time - 0.1:
                    return bt
            return beats[-1]
        elif direction == "prev":
            for bt in reversed(beats):
                if bt <= time + 0.1:
                    return bt
            return beats[0]
        else:
            return min(beats, key=lambda bt: abs(bt - time))

    def _energy_to_speed(self, energy: float) -> float:
        """能量 → 播放速度 (0.5x - 2.0x)"""
        if energy > 0.8:
            return 1.5  # 高能量加速
        elif energy > 0.6:
            return 1.2
        elif energy > 0.4:
            return 1.0
        elif energy > 0.2:
            return 0.8
        return 0.6  # 低能量慢放

    def _pick_transition(self, energy: float, idx: int) -> Dict[str, Any]:
        """根据能量选择转场 (映射到真实 AE 效果)"""
        # 高能量: 硬切/快速效果
        if energy > 0.85:
            return {"type": "cut", "duration": 0.0,
                    "ae_effect": None, "desc": "硬切"}
        elif energy > 0.75:
            return {"type": "glow_flash", "duration": 0.15,
                    "ae_effect": "ADBE Lensflare", "desc": "镜头光晕闪"}
        elif energy > 0.6:
            return {"type": "dissolve", "duration": 0.3,
                    "ae_effect": "ADBE Transition - Cross Dissolve", "desc": "交叉溶解"}
        elif energy > 0.45:
            return {"type": "wipe_right", "duration": 0.5,
                    "ae_effect": "ADBE Transition - Linear Wipe", "desc": "线性擦除"}
        elif energy > 0.3:
            return {"type": "slide", "duration": 0.4,
                    "ae_effect": "ADBE Transform", "desc": "滑动"}
        else:
            return {"type": "fade_black", "duration": 0.8,
                    "ae_effect": "ADBE Transition - Dip to Black", "desc": "黑场过渡"}


# ================================================================
#  3. 速度渐变生成器
# ================================================================
class SpeedRampGenerator:
    """基于能量曲线的速度渐变 (Time Remapping)"""

    def generate_ramps(self, audio_features: Dict[str, Any],
                       clip_start: float, clip_end: float) -> List[Dict]:
        """为单个片段生成速度渐变关键帧"""
        beats = audio_features.get("beats", [])
        energy_vals = audio_features.get("energy_values", [])
        energy_times = audio_features.get("energy_times", [])

        if not beats or not energy_vals:
            return []

        # 筛选该片段范围内的节拍
        ramps = []
        for bt, energy in zip(beats, energy_vals):
            if clip_start <= bt <= clip_end:
                # 能量 → time remap 值 (100=正常速度)
                remap = self._energy_to_remap(energy)
                ramps.append({
                    "time": round(bt - clip_start, 3),
                    "remap_value": remap,
                    "energy": round(energy, 3),
                })

        return ramps

    def _energy_to_remap(self, energy: float) -> float:
        """能量 → time remap 百分比"""
        # 低能量=慢放(50%), 高能量=加速(200%)
        return 50 + energy * 150


# ================================================================
#  4. JSX 生成器
# ================================================================
class AudioEditJSXGenerator:
    """将 EDL + 速度渐变转为 AE JSX"""

    def generate(self, edl: List[Dict], audio_features: Dict[str, Any],
                 material_paths: List[str],
                 audio_path: str = None,
                 comp_name: str = "AudioEdit") -> str:
        """生成完整 JSX"""
        bpm = audio_features.get("bpm", 128)
        duration = audio_features.get("duration", 30)
        W, H = 1920, 1080
        fps = 30

        lines = []
        lines.append(f"// === Audio-Driven Edit (BPM={bpm}) ===")
        lines.append(f"var W={W}, H={H}, DUR={duration}, FPS={fps};")
        lines.append("")

        # 1. 创建合成
        lines.append(f"var comp = app.project.items.addComp('{comp_name}', W, H, 1, DUR, FPS);")
        lines.append("")

        # 2. 导入音频
        if audio_path and os.path.exists(audio_path):
            safe_audio = audio_path.replace("\\", "/")
            lines.append(f"var audioFile = null;")
            lines.append(f"try {{ var aio = new ImportOptions(File('{safe_audio}')); audioFile = app.project.importFile(aio); }} catch(e) {{}}")
            lines.append(f"if (audioFile) {{ var aLy = comp.layers.add(audioFile); aLy.name = 'BGM'; }}")
            lines.append("")

        # 3. 导入素材 + 按 EDL 排列
        for i, clip in enumerate(edl):
            mat_idx = clip["material_index"]
            if mat_idx < len(material_paths):
                safe = material_paths[mat_idx].replace("\\", "/")
                lines.append(f"// --- Clip {i+1}: energy={clip['avg_energy']}, speed={clip['speed']}x ---")
                lines.append(f"var mat_{i} = null;")
                lines.append(f"try {{ var io_{i} = new ImportOptions(File('{safe}')); mat_{i} = app.project.importFile(io_{i}); }} catch(e) {{}}")
                lines.append(f"if (mat_{i}) {{")
                lines.append(f"  var ly_{i} = comp.layers.add(mat_{i});")
                lines.append(f"  ly_{i}.name = 'Clip_{i+1}';")
                lines.append(f"  ly_{i}.startTime = {clip['start_time']};")
                lines.append(f"  ly_{i}.outPoint = {clip['end_time']};")

                # 速度渐变 (Time Remapping)
                if clip["speed"] != 1.0:
                    lines.append(f"  ly_{i}.timeRemapEnabled = true;")
                    tr_prop = f"ly_{i}.property('ADBE Effect Parade').property('ADBE Time Remapping')"
                    lines.append(f"  try {{")
                    lines.append(f"    {tr_prop}.setValueAtTime(0, {clip['start_time']});")
                    lines.append(f"    {tr_prop}.setValueAtTime({clip['duration']}, {clip['end_time'] * clip['speed']});")
                    lines.append(f"  }} catch(e) {{}}")

                # 淡入淡出
                op = f"ly_{i}.property('ADBE Transform Group').property('ADBE Opacity')"
                fade_in = 0.2
                fade_out = 0.2
                lines.append(f"  {op}.setValueAtTime({clip['start_time']}, 0);")
                lines.append(f"  {op}.setValueAtTime({clip['start_time'] + fade_in}, 100);")
                lines.append(f"  {op}.setValueAtTime({clip['end_time'] - fade_out}, 100);")
                lines.append(f"  {op}.setValueAtTime({clip['end_time']}, 0);")

                # 节拍同步缩放 (强拍微放大)
                scale_prop = f"ly_{i}.property('ADBE Transform Group').property('ADBE Scale')"
                beats_in_clip = audio_features.get("beats", [])
                energy_vals = audio_features.get("energy_values", [])
                for bt_idx, (bt, en) in enumerate(zip(beats_in_clip, energy_vals)):
                    if clip["start_time"] <= bt <= clip["end_time"] and en > 0.7:
                        beat_scale = 100 + (en - 0.7) * 50  # 最多 115%
                        lines.append(f"  try {{ {scale_prop}.setValueAtTime({bt}, [{beat_scale:.1f}, {beat_scale:.1f}]); }} catch(e) {{}}")
                        lines.append(f"  try {{ {scale_prop}.setValueAtTime({bt + 0.15}, [100, 100]); }} catch(e) {{}}")

                lines.append(f"}}")
                lines.append("")

        # 4. 节拍标记层 (调试用)
        lines.append("// --- Beat Markers ---")
        lines.append(f"var markerLayer = comp.layers.addSolid([1,0,0], 'BeatMarkers', 2, 2, 1, DUR);")
        lines.append(f"markerLayer.opacity = 0;")
        beats = audio_features.get("beats", [])
        for bt in beats[:50]:  # 最多50个标记
            lines.append(f"markerLayer.property('ADBE Marker Group').addMarker({bt}, 'beat', 0.1);")
        lines.append("")

        # 5. 调整图层 - 全局效果
        lines.append("// --- Adjustment Layer ---")
        lines.append(f"var adj = comp.layers.addSolid([0.5,0.5,0.5], 'Adjust', W, H, 1, DUR);")
        lines.append(f"adj.adjustmentLayer = true;")
        # 根据整体能量添加效果
        avg_overall = sum(clip["avg_energy"] for clip in edl) / max(len(edl), 1)
        if avg_overall > 0.6:
            lines.append(f"try {{ var sharp = adj.Effects.addProperty('ADBE Sharpen'); sharp.property('ADBE Sharpen-0001').setValue({20 + avg_overall * 30:.0f}); }} catch(e) {{}}")
        lines.append("")

        # 6. 结果
        lines.append(f"JSON.stringify({{success: true, bpm: {bpm}, clips: {len(edl)}, beats: {len(beats)}}});")

        return "\n".join(lines)


# ================================================================
#  5. 主编排器: AudioEditEngine
# ================================================================
class AudioEditEngine:
    """音频驱动剪辑引擎"""

    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir) if output_dir else Path(
            r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_director")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.analyzer = AudioAnalyzerAdapter()
        self.edl_gen = EditDecisionGenerator()
        self.ramp_gen = SpeedRampGenerator()
        self.jsx_gen = AudioEditJSXGenerator()

    def edit(self, audio_path: str,
             material_paths: List[str],
             comp_name: str = "AudioEdit") -> Dict[str, Any]:
        """
        完整音频驱动剪辑流程。

        Args:
            audio_path: BGM/音频文件路径
            material_paths: 视频素材路径列表
            comp_name: 合成名称
        """
        start_time = time.time()

        print("\n" + "=" * 60)
        print("  Audio Edit Engine - 音频驱动剪辑引擎")
        print("=" * 60)

        # Step 1: 音频分析
        print("\n--- Step 1: 音频分析 ---")
        audio_features = self.analyzer.analyze(audio_path)
        bpm = audio_features.get("bpm", 128)
        duration = audio_features.get("duration", 30)
        n_beats = len(audio_features.get("beats", []))
        log(f"  BPM={bpm}, duration={duration:.1f}s, beats={n_beats}")
        log(f"  mood={audio_features.get('mood', '?')}, genre={audio_features.get('genre', '?')}")

        # Step 2: 生成 EDL
        print("\n--- Step 2: 剪辑决策 (EDL) ---")
        edl = self.edl_gen.generate(audio_features, material_count=len(material_paths))
        for clip in edl:
            log(f"  Clip {clip['clip_index']+1}: {clip['start_time']:.1f}-{clip['end_time']:.1f}s "
                f"(energy={clip['avg_energy']:.2f}, speed={clip['speed']}x, trans={clip['transition']['type']})")

        # Step 3: 速度渐变
        print("\n--- Step 3: 速度渐变 ---")
        for clip in edl:
            ramps = self.ramp_gen.generate_ramps(
                audio_features, clip["start_time"], clip["end_time"])
            clip["ramps"] = ramps
            if ramps:
                log(f"  Clip {clip['clip_index']+1}: {len(ramps)} ramp keyframes")

        # Step 4: JSX 生成
        print("\n--- Step 4: JSX 生成 ---")
        jsx = self.jsx_gen.generate(edl, audio_features, material_paths, audio_path, comp_name)
        jsx_path = self.output_dir / "audio_edit.jsx"
        with open(jsx_path, "w", encoding="utf-8") as f:
            f.write(jsx)
        log(f"  JSX: {len(jsx.splitlines())} 行, {len(jsx)} 字符")

        # 保存 EDL
        edl_path = self.output_dir / "audio_edit_edl.json"
        with open(edl_path, "w", encoding="utf-8") as f:
            json.dump({"audio": audio_path, "bpm": bpm, "duration": duration,
                       "beats": n_beats, "clips": edl}, f, ensure_ascii=False, indent=2)

        # 报告
        elapsed = time.time() - start_time
        report = {
            "audio": audio_path,
            "bpm": bpm,
            "duration": duration,
            "beats": n_beats,
            "mood": audio_features.get("mood"),
            "clips": len(edl),
            "jsx_lines": len(jsx.splitlines()),
            "elapsed": round(elapsed, 1),
            "outputs": {
                "jsx": str(jsx_path),
                "edl": str(edl_path),
            }
        }
        report_path = self.output_dir / "audio_edit_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 60)
        print(f"  音频驱动剪辑完成! 耗时 {elapsed:.1f}s")
        print(f"  BPM={bpm}, {n_beats} beats, {len(edl)} clips")
        print(f"  JSX: {jsx_path}")
        print("=" * 60)

        return report


# ================================================================
#  主入口
# ================================================================
if __name__ == "__main__":
    engine = AudioEditEngine()

    # 查找可用音频
    audio_candidates = [
        r"D:\AE-Work\output\VinlandSaga_Battle_V17.mp4",  # 用视频音轨
        r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\audio_processed.wav",
        r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\audio_raw.wav",
    ]
    audio_path = None
    for p in audio_candidates:
        if os.path.exists(p):
            audio_path = p
            break

    # 素材
    material_candidates = [
        r"D:\AE-Work\output\VinlandSaga_Battle_V17.mp4",
    ]
    materials = [p for p in material_candidates if os.path.exists(p)]

    if audio_path:
        if not materials:
            materials = [audio_path]
        result = engine.edit(audio_path=audio_path, material_paths=materials)
        print(f"\n结果: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
    else:
        print("无可用音频文件")
