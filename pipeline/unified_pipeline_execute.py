"""pipeline/unified_pipeline_execute.py — 真实混合执行阶段 (从 unified_pipeline 拆出)

2026-08-14 从 pipeline/unified_pipeline.py 拆出的 _run_execute_real_mix
方法体。原方法薄委托: UnifiedPipeline._run_execute_real_mix() ->
run_execute_real_mix(self), 行为等价。
"""
from __future__ import annotations

from typing import Any, Dict



def run_execute_real_mix(self) -> Dict:
    """P1 真混剪: 用 FFmpegEditEngine 按 effect_stack 把素材分段应用滤镜并拼接成新视频。

    流程:
      1. 收集素材源 (plan.shot_list.source / perceive.videos / reference_video / materials_dir)
      2. 准备 effect_stack (空则用默认 cyberpunk 风格, 至少 2 个效果)
      3. 把源视频按 seg_dur 切成 N 段, 每段应用不同效果滤镜 (eq+unsharp+vignette)
      4. 用 concat demuxer 拼接所有片段 (失败则降级 filter_complex concat)
      5. 输出 H.264 MP4 到 output/p1_execute_mix/

    失败时返回 error_code + error, 不再降级到参考视频截取。
    """
    import subprocess
    import shutil
    from pipeline.ffmpeg_edit_engine import (
        FFmpegEditEngine, FFmpegFilterBuilder,
        ColorGradeParams, SharpenParams, VignetteParams, BlurParams,
    )

    prev = self._get_previous_data()
    plan = prev.get("plan", {})
    perceive = prev.get("perceive", {})

    # ---- 1. 收集素材源 ----
    sources: List[str] = []
    # a. plan.shot_list 中带真实路径的 source
    for shot in plan.get("shot_list", []):
        src = shot.get("source", "") or ""
        if src and Path(src).is_file() and src not in sources:
            sources.append(src)
    # b. perceive.videos
    for v in perceive.get("videos", []):
        p = v.get("path", "") if isinstance(v, dict) else str(v)
        if p and Path(p).is_file() and p not in sources:
            sources.append(p)
    # c. config.reference_video
    if self.config.reference_video and Path(self.config.reference_video).is_file():
        if self.config.reference_video not in sources:
            sources.append(self.config.reference_video)
    # d. materials_dir 下的视频
    if self.config.materials_dir and Path(self.config.materials_dir).exists():
        for f in sorted(Path(self.config.materials_dir).rglob("*")):
            if f.suffix.lower() in {".mp4", ".mov", ".mkv", ".avi"} and str(f) not in sources:
                sources.append(str(f))

    if not sources:
        return {
            "project_path": "", "composition": "real_mix_no_source",
            "execution_mode": "real_mix_failed",
            "error_code": "NO_SOURCE", "error": "无可用素材源",
            "layers_created": 0, "effects_applied": 0,
        }

    # ---- 2. 准备 effect_stack ----
    effect_stack = plan.get("effect_stack", []) or []
    if not effect_stack:
        effect_stack = self._build_default_effect_stack()
        self._log(
            f"[EXEC-MIX] effect_stack empty, using default cyberpunk stack "
            f"({len(effect_stack)} effects)"
        )

    # ---- 3. 准备输出目录 ----
    output_dir = Path(self.config.output_dir) / "p1_execute_mix"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = self.run_id
    final_output = str(output_dir / f"mix_{run_id}.mp4")

    # P1 反馈闭环: 读取 retry 调整参数 (verify→execute 回环时注入)
    seg_dur_boost = 1.0
    retry_adj = self._results.get("_retry_adjustments")
    if retry_adj and retry_adj.status == StageStatus.DONE:
        seg_dur_boost = float(retry_adj.data.get("segment_duration_boost", 1.0))
        if seg_dur_boost > 1.0:
            self._log(
                f"[EXEC-MIX] Retry adjustment: seg_dur_boost={seg_dur_boost}x "
                f"reason={retry_adj.data.get('reason', '')}"
            )

    # ---- 4. 初始化 FFmpeg 引擎 ----
    ffmpeg_bin = self.config.ffmpeg_bin or _paths_ffmpeg()
    if not Path(ffmpeg_bin).exists():
        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    engine = FFmpegEditEngine(ffmpeg_bin=ffmpeg_bin)

    # ---- 5. 多素材分段策略 (P2: 按 plan.shot_list 混剪, 不再用单素材分段) ----
    # 预计算每个 source 的时长
    source_durations: Dict[str, float] = {}
    for _s in sources:
        try:
            source_durations[_s] = engine._get_duration(_s)
        except Exception:
            source_durations[_s] = 0.0

    # 至少一个 source 时长 >= 2s 才能继续
    max_src_dur = max(source_durations.values()) if source_durations else 0.0
    if max_src_dur < 2.0:
        return {
            "project_path": "", "composition": "real_mix_short_source",
            "execution_mode": "real_mix_failed",
            "error_code": "SOURCE_TOO_SHORT",
            "error": f"所有源视频时长过短: max={max_src_dur:.2f}s",
            "layers_created": 0, "effects_applied": 0,
            "source_count": len(sources),
            "mix_mode": "single_source_segmented",
        }

    # 解析 plan.shot_list (P2: 每个 shot 决定 source + start_time + end_time + effect)
    shot_list = plan.get("shot_list", []) or []
    # segment_plan: list of (source_path, seg_start, seg_dur, effect_dict)
    segment_plan: List[tuple] = []
    used_sources: set = set()

    def _match_shot_source(shot_src: str) -> str:
        """shot.source 归一化匹配到 sources 中的真实路径, 失败返回 ""。"""
        if not shot_src:
            return ""
        shot_name = Path(shot_src).name
        for s in sources:
            if s == shot_src or s.endswith(shot_src) or shot_src.endswith(s) \
                    or Path(s).name == shot_name:
                return s
        return ""

    if shot_list:
        # 路径 A: 按 plan.shot_list 混剪 (P2 核心路径)
        for shot_idx, shot in enumerate(shot_list):
            if len(segment_plan) >= 6:
                break  # 限制最多 6 段, 保证渲染速度
            # 选 source: shot.source 优先匹配 sources, 否则轮询 sources
            matched = _match_shot_source(shot.get("source", "") or "")
            if not matched:
                matched = sources[shot_idx % len(sources)]
            used_sources.add(matched)
            src_dur = source_durations.get(matched, 0.0)

            # 选 start/end: shot.start_time/end_time 优先, 否则 shot.start/end
            seg_start = float(shot.get("start_time", shot.get("start", 0.0)) or 0.0)
            seg_end_raw = shot.get("end_time", shot.get("end", None))
            if seg_end_raw is not None:
                seg_end = float(seg_end_raw)
            else:
                seg_end = seg_start + 3.0
            # 钳制到 source 时长
            if src_dur > 0:
                seg_start = max(0.0, min(seg_start, max(src_dur - 0.5, 0.0)))
                seg_end = min(seg_end, src_dur)
            seg_dur = max(0.5, seg_end - seg_start)
            # 至少 2s 保证总时长 >5s
            if seg_dur < 2.0 and src_dur >= 2.0:
                seg_end = min(seg_start + 2.0, src_dur)
                seg_dur = seg_end - seg_start

            eff = effect_stack[shot_idx % len(effect_stack)]
            segment_plan.append((matched, seg_start, seg_dur, eff))

    # 路径 B: 无 shot_list OR shot_list 产生的段数不足 -> 轮询 sources 切 N 段 (多素材混剪)
    # P2 核心: 保证至少 min(len(effect_stack), 4) 段, 且轮询不同 source
    min_segments = min(max(len(effect_stack), 2), 4)
    if not shot_list or len(segment_plan) < min_segments:
        if shot_list:
            self._log(
                f"[EXEC-MIX] shot_list only produced {len(segment_plan)} segments, "
                f"topping up to {min_segments} via round-robin (multi-source)"
            )
        # 重置为轮询路径 (保证多素材多段, 不用单素材分段)
        segment_plan = []
        used_sources = set()
        for seg_idx in range(min_segments):
            # 轮询 sources: 每段用不同 source (真正多素材混剪)
            src = sources[seg_idx % len(sources)]
            used_sources.add(src)
            src_dur = source_durations.get(src, 0.0)
            seg_dur = max(3.0, min(5.0, src_dur / max(min_segments, 1))) if src_dur > 0 else 3.0
            seg_dur *= seg_dur_boost  # P1 反馈闭环: 重试时增加段时长
            # 错开采样起点, 体现"混剪"
            if src_dur > seg_dur * 2:
                seg_start = (seg_idx * seg_dur * 1.2) % max(src_dur - seg_dur, 0.1)
            else:
                seg_start = 0.0
            seg_start = max(0.0, seg_start)
            eff = effect_stack[seg_idx % len(effect_stack)]
            segment_plan.append((src, seg_start, seg_dur, eff))

    if not segment_plan:
        return {
            "project_path": "", "composition": "real_mix_no_segment_plan",
            "execution_mode": "real_mix_failed",
            "error_code": "NO_SEGMENT_PLAN",
            "error": "段落计划为空",
            "layers_created": 0, "effects_applied": 0,
            "source_count": len(sources),
            "mix_mode": "single_source_segmented",
        }

    # mix_mode: 用了 >=2 个不同 source 才算 multi_source
    source_count = len(used_sources)
    mix_mode = "multi_source" if source_count >= 2 else "single_source_segmented"
    total_target = sum(sp[2] for sp in segment_plan)
    self._log(
        f"[EXEC-MIX] P2 multi-source: sources={source_count}/{len(sources)} mode={mix_mode} "
        f"segments={len(segment_plan)} effects={len(effect_stack)} "
        f"target_total={total_target:.1f}s "
        f"used={[Path(s).name for s in used_sources]}"
    )

    # ---- 6. 为每段构建滤镜并渲染 ----
    tmp_dir = output_dir / f"_tmp_{run_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:

        # P1 转场库: 预解析 transition_plan, 决定段间拼接策略
        transition_plan = plan.get("transition_plan", []) or []
        # 映射 plan 转场类型 → FFmpeg xfade 类型
        _XFADE_MAP = {
            "dissolve": "dissolve", "crossfade": "fade", "cross_fade": "fade",
            "fade": "fade", "fade_in": "fade", "fade_out": "fade",
            "wipe": "wipeleft", "wipeleft": "wipeleft", "wiperight": "wiperight",
            "wipeup": "wipeup", "wipedown": "wipedown",
            "slide": "slideleft", "slideleft": "slideleft", "slideright": "slideright",
            "smoothleft": "smoothleft", "smoothright": "smoothright",
            "circlecrop": "circlecrop", "radial": "radial",
        }
        # 构建有效转场列表 (跳过 "cut" = 硬切无转场)
        xfade_types: List[str] = []
        xfade_durs: List[float] = []
        for t in transition_plan:
            t_type = (t.get("type", "") or "").lower().strip()
            mapped = _XFADE_MAP.get(t_type, "")
            if mapped:  # 非 cut 且有映射
                xfade_types.append(mapped)
                xfade_durs.append(float(t.get("duration", 0.5) or 0.5))
        # 如果 plan 无转场数据但有多段, 使用默认转场策略 (交替 dissolve/fade)
        if not xfade_types and len(segment_plan) >= 2:
            _default_types = ["dissolve", "fade", "smoothleft", "wipeleft", "radial"]
            for i in range(len(segment_plan) - 1):
                xfade_types.append(_default_types[i % len(_default_types)])
                xfade_durs.append(0.5)
        use_xfade = len(xfade_types) >= 1 and len(segment_plan) >= 2
        if use_xfade:
            self._log(
                f"[EXEC-MIX] P1 transitions: {len(xfade_types)} xfade "
                f"types={xfade_types} durs={xfade_durs}"
            )

        segment_files: List[str] = []
        segment_durations: List[float] = []  # 记录每段真实时长 (xfade offset 计算用)
        effects_applied = 0
        for seg_idx, (src_path, seg_start, seg_dur, eff) in enumerate(segment_plan):
            fb = FFmpegFilterBuilder()
            applied = self._apply_effect_to_filter_builder(fb, eff, seg_dur)
            if applied:
                effects_applied += 1
            # 段间过渡: 使用 xfade 时不加 per-segment fade (xfade 自带过渡)
            # 仅首段加 fade_in, 末段加 fade_out
            if not use_xfade:
                fb.fade_in(0.3)
                fb.fade_out(0.3, seg_dur)
            else:
                if seg_idx == 0:
                    fb.fade_in(0.3)
                if seg_idx == len(segment_plan) - 1:
                    fb.fade_out(0.3, seg_dur)

            seg_out = str(tmp_dir / f"seg_{seg_idx:02d}.mp4")
            # 段渲染: 在滤镜链末尾追加 scale+fps+setsar 统一参数 (xfade 要求一致)
            _seg_vf = fb.build()
            _normalize = "scale=1920:1080:flags=lanczos,fps=30,setsar=1"
            _seg_vf = f"{_seg_vf},{_normalize}" if _seg_vf else _normalize
            cmd = [
                ffmpeg_bin, "-y", "-hide_banner",
                "-ss", f"{seg_start:.3f}",
                "-i", src_path,
                "-t", f"{seg_dur:.3f}",
                "-vf", _seg_vf,
                "-r", "30",
                "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                "-b:v", "4M", "-maxrate", "8M", "-bufsize", "16M",
                "-pix_fmt", "yuv420p",
            ]
            if engine._has_audio_stream(src_path):
                cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"])
            else:
                cmd.append("-an")
            cmd.append(seg_out)

            try:
                r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
            except subprocess.TimeoutExpired:
                self._log(f"[EXEC-MIX] seg {seg_idx} TIMEOUT", "WARN")
                continue
            if r.returncode == 0 and Path(seg_out).is_file() and Path(seg_out).stat().st_size > 1024:
                segment_files.append(seg_out)
                segment_durations.append(seg_dur)
                self._log(
                    f"[EXEC-MIX] seg {seg_idx}: src={Path(src_path).name} "
                    f"start={seg_start:.1f}s dur={seg_dur:.1f}s "
                    f"effect={eff.get('name', 'default')} -> {Path(seg_out).name} "
                    f"({Path(seg_out).stat().st_size // 1024}KB)"
                )
            else:
                self._log(
                    f"[EXEC-MIX] seg {seg_idx} FAILED rc={r.returncode} "
                    f"stderr={r.stderr[-300:] if r.stderr else ''}", "WARN"
                )

        if not segment_files:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return {
                "project_path": "", "composition": "real_mix_no_segments",
                "execution_mode": "real_mix_failed",
                "error_code": "ALL_SEGMENTS_FAILED",
                "error": "所有片段渲染失败",
                "layers_created": 0, "effects_applied": 0,
            }

        # ---- 7. 拼接所有片段 (P1: xfade 转场优先) ----
        concat_method = "unknown"
        if len(segment_files) == 1:
            shutil.copy2(segment_files[0], final_output)
            concat_method = "single_segment"
        elif use_xfade and len(segment_files) >= 2:
            # P1 转场库: 单次 filter_complex 多段 xfade (避免 chain_transitions 多次重编码)
            n_segs = len(segment_files)
            n_trans = min(len(xfade_types), n_segs - 1)
            inputs: List[str] = []
            for sf in segment_files:
                inputs.extend(["-i", sf])
    
            # 探测每段真实时长 (xfade offset 计算必须精确)
            actual_durs: List[float] = []
            for sf in segment_files:
                d = engine._get_duration(sf)
                actual_durs.append(d if d > 0 else 3.0)
    
            # 构建视频 xfade 链 (单次 filter_complex, 标签顺序链接)
            vf_parts: List[str] = []
            offset = 0.0
            for i in range(n_trans):
                if i == 0:
                    offset = max(0.0, actual_durs[0] - xfade_durs[0])
                else:
                    offset = max(0.0, offset + actual_durs[i] - xfade_durs[i])
                t = xfade_types[i]
                d = xfade_durs[i]
                in_label = f"[{i}:v]" if i == 0 else f"[xf{i}]"
                out_label = "[vxf]" if i == n_trans - 1 else f"[xf{i+1}]"
                next_input = f"[{i+1}:v]"
                vf_parts.append(
                    f"{in_label}{next_input}xfade=transition={t}:duration={d:.3f}:offset={offset:.3f}{out_label}"
                )
    
            # 构建音频 acrossfade 链 (同样顺序链接)
            af_parts: List[str] = []
            for i in range(n_trans):
                d = xfade_durs[i]
                in_label = f"[{i}:a]" if i == 0 else f"[af{i}]"
                out_label = "[axf]" if i == n_trans - 1 else f"[af{i+1}]"
                next_input = f"[{i+1}:a]"
                af_parts.append(
                    f"{in_label}{next_input}acrossfade=d={d:.3f}:c1=tri:c2=tri{out_label}"
                )
    
            # 如果某些段无音频, 跳过音频滤镜
            has_all_audio = all(engine._has_audio_stream(sf) for sf in segment_files)
    
            filter_complex = ";".join(vf_parts)
            if has_all_audio and af_parts:
                filter_complex += ";" + ";".join(af_parts)
    
            self._log(
                f"[EXEC-MIX] xfade filter_complex ({len(filter_complex)} chars): "
                f"{filter_complex[:300]}{'...' if len(filter_complex) > 300 else ''}"
            )
    
            cmd = [
                ffmpeg_bin, "-y", "-hide_banner",
                *inputs,
                "-filter_complex", filter_complex,
                "-map", "[vxf]",
            ]
            if has_all_audio and af_parts:
                cmd.extend(["-map", "[axf]"])
            cmd.extend([
                "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                "-b:v", "4M", "-maxrate", "8M", "-bufsize", "16M",
            ])
            if has_all_audio and af_parts:
                cmd.extend(["-c:a", "aac", "-b:a", "128k"])
            cmd.extend([
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                final_output,
            ])
    
            xfade_timeout = max(180, n_segs * 60)
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=xfade_timeout)
                if r.returncode == 0 and Path(final_output).is_file() and Path(final_output).stat().st_size > 1024:
                    concat_method = f"xfade_{n_trans}trans"
                    self._log(
                        f"[EXEC-MIX] P1 xfade SUCCESS: {n_trans} transitions "
                        f"types={xfade_types[:n_trans]} output={Path(final_output).stat().st_size // 1024}KB"
                    )
                else:
                    self._log(
                        f"[EXEC-MIX] xfade failed rc={r.returncode}, "
                        f"falling back to concat. "
                        f"stderr={r.stderr[-500:] if r.stderr else ''}", "WARN"
                    )
            except subprocess.TimeoutExpired:
                self._log("[EXEC-MIX] xfade TIMEOUT, falling back to concat", "WARN")
            except Exception as e:
                self._log(f"[EXEC-MIX] xfade exception: {e}", "WARN")
    
            # xfade 失败降级: concat demuxer
            if concat_method == "unknown":
                list_path = str(tmp_dir / "concat_list.txt")
                with open(list_path, "w", encoding="utf-8") as f:
                    for sf in segment_files:
                        esc = sf.replace("'", r"'\''")  
                        f.write(f"file '{esc}'\n")
                cmd = [
                    ffmpeg_bin, "-y", "-hide_banner",
                    "-f", "concat", "-safe", "0",
                    "-i", list_path,
                    "-c", "copy",
                    "-movflags", "+faststart",
                    final_output,
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
                if r.returncode == 0 and Path(final_output).is_file() and Path(final_output).stat().st_size > 1024:
                    concat_method = "concat_demuxer_fallback"
                else:
                    self._log(f"[EXEC-MIX] concat fallback also failed rc={r.returncode}", "ERROR")
        else:
            # 无转场数据: 直接 concat demuxer
            list_path = str(tmp_dir / "concat_list.txt")
            with open(list_path, "w", encoding="utf-8") as f:
                for sf in segment_files:
                    esc = sf.replace("'", r"'\''")  
                    f.write(f"file '{esc}'\n")
            cmd = [
                ffmpeg_bin, "-y", "-hide_banner",
                "-f", "concat", "-safe", "0",
                "-i", list_path,
                "-c", "copy",
                "-movflags", "+faststart",
                final_output,
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
            if r.returncode == 0 and Path(final_output).is_file() and Path(final_output).stat().st_size > 1024:
                concat_method = "concat_demuxer"
            else:
                # 方案 B: filter_complex concat (重新编码, 兆底)
                self._log(
                    f"[EXEC-MIX] concat demuxer failed (rc={r.returncode}), "
                    f"trying filter_complex", "WARN"
                )
                inputs = []
                for sf in segment_files:
                    inputs.extend(["-i", sf])
                filter_parts = []
                for i in range(len(segment_files)):
                    filter_parts.append(f"[{i}:v:0][{i}:a:0]")
                filter_complex = (
                    "".join(filter_parts)
                    + f"concat=n={len(segment_files)}:v=1:a=1[v_pre][a];"
                    + f"[v_pre]scale=1920:1080:flags=lanczos[v]"
                )
                cmd = [
                    ffmpeg_bin, "-y", "-hide_banner",
                    *inputs,
                    "-filter_complex", filter_complex,
                    "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                    "-b:v", "4M", "-maxrate", "8M", "-bufsize", "16M",
                    "-c:a", "aac", "-b:a", "128k",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    final_output,
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
                if r.returncode == 0 and Path(final_output).is_file():
                    concat_method = "filter_complex"
                else:
                    self._log(
                        f"[EXEC-MIX] filter_complex also failed: "
                        f"{r.stderr[-400:] if r.stderr else ''}", "ERROR"
                    )

        # ---- 8. 验证最终输出 ----
        if not Path(final_output).is_file() or Path(final_output).stat().st_size < 1024:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return {
                "project_path": "", "composition": "real_mix_output_invalid",
                "execution_mode": "real_mix_failed",
                "error_code": "OUTPUT_INVALID",
                "error": f"最终输出文件无效: {final_output}",
                "layers_created": len(segment_files),
                "effects_applied": effects_applied,
            }

        # ---- 9. 输出元数据 ----
        file_size_mb = round(Path(final_output).stat().st_size / (1024 * 1024), 2)
        final_dur = engine._get_duration(final_output)
        # 取已渲染段的平均时长作为 segment_duration (循环内 seg_dur 已出作用域)
        avg_seg_dur = (
            round(sum(sp[2] for sp in segment_plan) / max(len(segment_plan), 1), 2)
            if segment_plan else 0.0
        )
        self._log(
            f"[EXEC-MIX] SUCCESS output={final_output} "
            f"dur={final_dur:.1f}s size={file_size_mb}MB "
            f"segments={len(segment_files)} effects={effects_applied} "
            f"sources={source_count} mode={mix_mode} "
            f"concat={concat_method} "
            f"transitions={xfade_types if use_xfade else 'none'}"
        )

        # ---- 清理临时目录（段渲染文件+concat_list.txt）防止磁盘空间泄漏 ----
        shutil.rmtree(tmp_dir, ignore_errors=True)

        return {
            "project_path": final_output,
            "composition": f"real_mix_{len(segment_files)}seg_{effects_applied}eff_{source_count}src",
            "execution_mode": "real_mix",
            "layers_created": len(segment_files),
            "effects_applied": effects_applied,
            "output_path": final_output,
            "mix_method": concat_method,
            "source_file": sources[0],
            "source_files": list(used_sources),
            "source_count": source_count,
            "mix_mode": mix_mode,
            "segment_duration": avg_seg_dur,
            "total_duration": final_dur,
            "file_size_mb": file_size_mb,
            "transitions_applied": xfade_types if use_xfade else [],
            "transition_count": len(xfade_types) if use_xfade and "xfade" in concat_method else 0,
        }
    finally:
        # 确保异常路径也清理临时目录，防止磁盘空间泄漏
        shutil.rmtree(tmp_dir, ignore_errors=True)
