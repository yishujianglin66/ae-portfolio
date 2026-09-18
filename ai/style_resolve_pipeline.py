#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风格复刻完整管线 — StyleSpec 驱动的 Resolve + AE + ffmpeg 串联
================================================================

将 ProductionDirector 的编辑决策（切点、转场、变速）通过 StyleBridge
转换为 DaVinci Resolve Engine / AE Bridge 可执行的参数，实现风格复刻管线的
完整软件管线串联。

架构:
    StyleSpec + DirectorScript
         |
    StyleBridge (ai/style_bridge.py)
         |
    ResolveTimelinePlan (色彩/转场/变速/片段序列)
         |
    ResolveEngine (Stage A: 剪辑+变速+调色)
         |
    AE Bridge (Stage B: 文字动画) -- 可选
         |
    Resolve/ffmpeg (Stage C: 最终调色+混音)
         |
    最终成片

降级策略:
    Resolve 离线 → ffmpeg 管线 (ProductionDirector 原路径)
    AE 离线 → ffmpeg drawtext 降级
    Resolve 渲染超时 → 原生渲染 + ffmpeg 转码

用法:
    from ai.style_resolve_pipeline import StyleResolvePipeline
    pipeline = StyleResolvePipeline()
    result = pipeline.run_with_style(
        video_sources=[...],
        bgm_path="...",
        style_spec_path="reports/solo_leveling_style_report.json",
        output_path="tmp/renders/solo_resolve.mp4",
    )
"""
from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from ai.style_bridge import ColorBridgeResult, SpeedBridgeResult, StyleBridge, TransitionBridgeResult

logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class ResolveTimelineItem:
    """Resolve 时间线片段 — 完整参数集"""
    index: int = 0
    source_file: str = ""
    source_start: float = 0.0          # 素材内起始时间
    duration: float = 0.0              # 段落时长（变速后）
    speed: float = 1.0                 # 播放速度
    speed_curve: list[tuple[float, float]] | None = None
    retime_process: int = 0            # 0=Project, 1=Nearest, 2=OpticalFlow
    transition: str = ""               # Resolve 转场名
    transition_duration: float = 0.0
    color_cdl: dict[str, float] = field(default_factory=lambda: {"saturation": 1.0, "contrast": 1.0, "brightness": 0.0})
    mood: str = "build"
    energy: float = 0.5
    text_overlay: str = ""

    @property
    def source_duration(self) -> float:
        """素材内原始时长（变速前）"""
        return self.duration / max(self.speed, 0.01)


@dataclass
class ResolveTimelinePlan:
    """完整时间线计划"""
    title: str = ""
    total_duration: float = 0.0
    bgm_path: str = ""
    bgm_start_sec: float = 0.0
    items: list[ResolveTimelineItem] = field(default_factory=list)
    color_profile: dict[str, float] = field(default_factory=dict)
    style_source: str = ""             # "style_spec" / "director_script"


# ============================================================================
# 核心管线
# ============================================================================

class StyleResolvePipeline:
    """StyleSpec 驱动的 Resolve + AE + ffmpeg 串联管线。

    三级降级:
    1. Resolve 在线 + AE 在线 → 完整三段式 (Resolve→AE→Resolve)
    2. Resolve 在线 + AE 离线 → Resolve + ffmpeg drawtext
    3. Resolve 离线 → ffmpeg only (ProductionDirector 原路径)
    """

    def __init__(self):
        self.bridge = StyleBridge()
        self._resolve_available: bool | None = None
        self._ae_available: bool | None = None
        self.last_report: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 环境检测
    # ------------------------------------------------------------------
    def check_resolve(self) -> bool:
        """检测 DaVinci Resolve 是否可用"""
        if self._resolve_available is not None:
            return self._resolve_available
        try:
            from integrations.resolve_engine import FUSCRIPT_PATH, ResolveAutomationEngine
            self._resolve_available = os.path.exists(FUSCRIPT_PATH)
            logger.info(f"Resolve 检测: {'在线' if self._resolve_available else '离线'} "
                        f"(fuscript: {FUSCRIPT_PATH})")
        except Exception as e:
            self._resolve_available = False
            logger.warning(f"Resolve 检测异常: {e}")
        return self._resolve_available

    def check_ae(self) -> bool:
        """检测 AE Bridge 是否可用"""
        if self._ae_available is not None:
            return self._ae_available
        try:
            from integrations.resolve_ae_resolve_pipeline import AEBridgeLite
            ae = AEBridgeLite()
            self._ae_available = ae.is_online()
            logger.info(f"AE Bridge 检测: {'在线' if self._ae_available else '离线'}")
        except Exception as e:
            self._ae_available = False
            logger.warning(f"AE Bridge 检测异常: {e}")
        return self._ae_available

    # ------------------------------------------------------------------
    # StyleSpec 加载
    # ------------------------------------------------------------------
    def load_style_spec(self, style_spec_path: str) -> dict[str, Any]:
        """加载风格规格书 JSON。

        支持两种格式:
        1. StyleSpec JSON（含 cut_rate, color_profile 顶层字段）→ 直接使用
        2. 结题报告 JSON（含 iteration_results, final_metrics）→ 从参考视频重新提取
        """
        with open(style_spec_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 检测是否为报告格式（缺少 cut_rate/color_profile 顶层字段）
        if "cut_rate" not in data and "color_profile" not in data:
            # 报告格式 → 尝试从参考视频重新提取
            source_video = ""
            materials = data.get("materials", [])
            if materials:
                source_video = materials[0] if isinstance(materials[0], str) else materials[0].get("path", "")
            if source_video and os.path.exists(source_video):
                logger.info(f"检测到报告格式，从参考视频重新提取 StyleSpec: {source_video}")
                from core.style_spec_extractor import StyleSpecExtractor
                ext = StyleSpecExtractor()
                spec = ext.extract(source_video)
                data = spec.to_dict()
                # 保存提取的 StyleSpec 供后续使用
                spec_out = style_spec_path.replace(".json", "_extracted.json")
                with open(spec_out, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"  StyleSpec 已保存到: {spec_out}")
            else:
                logger.warning("报告格式但无法找到参考视频，style_spec 将为空")
                return {}

        logger.info(f"加载风格规格书: {style_spec_path}")
        logger.info(f"  色彩: {data.get('color_profile', {})}")
        logger.info(f"  切率: {data.get('cut_rate', 0):.2f} cuts/s")
        logger.info(f"  BPM: {data.get('bpm', 0)}")
        return data

    # ------------------------------------------------------------------
    # 时间线计划生成
    # ------------------------------------------------------------------
    def build_timeline_plan(
        self,
        video_sources: list[str],
        bgm_path: str,
        style_spec: dict[str, Any] | None = None,
        target_duration: float | None = None,
        fps: int = 30,
    ) -> ResolveTimelinePlan:
        """从 StyleSpec + 素材列表生成 Resolve 时间线计划。

        流程:
        1. 用 ProductionDirector 生成编辑决策（切点、转场、变速）
        2. 用 StyleBridge 将决策转换为 Resolve 参数
        3. 组装完整时间线计划
        """
        from ai.production_director import ProductionDirector

        # Step 1: 用 ProductionDirector 生成编辑决策（不渲染）
        logger.info("Step 1: 生成编辑决策 (ProductionDirector)...")
        director = ProductionDirector()

        # 获取 BGM 时长作为目标时长
        bgm_dur = self._get_media_duration(bgm_path) or 19.0
        if target_duration is None:
            target_duration = bgm_dur

        # 调用 _analyze + _plan 获取剧本（跳过渲染）
        director._analyze(
            bgm_path=bgm_path,
            video_sources=video_sources,
            bgm_start_sec=0.0,
            target_duration=target_duration,
        )
        script = director._plan(
            video_sources=video_sources,
            bgm_path=bgm_path,
            bgm_start_sec=0.0,
            duration=target_duration,
            lyrics=None,
            style_spec=style_spec,
            use_speed_ramp=True,
        )

        if not script:
            raise RuntimeError("ProductionDirector 无法生成编辑剧本")

        script_dict = script.to_dict()
        logger.info(f"  剧本: {len(script_dict['segments'])} 个段落, "
                    f"总时长 {script_dict['total_duration']:.1f}s")

        # Step 2: 用 StyleBridge 转换
        logger.info("Step 2: 转换风格参数 (StyleBridge)...")
        timeline_items = self.bridge.script_to_resolve_timeline(script_dict, style_spec)

        # Step 3: 组装时间线计划
        plan = ResolveTimelinePlan(
            title=script_dict.get("title", "Style Clone"),
            total_duration=script_dict.get("total_duration", 0.0),
            bgm_path=bgm_path,
            bgm_start_sec=script_dict.get("bgm_start_sec", 0.0),
            style_source="style_spec" if style_spec else "director_only",
        )

        for item_data in timeline_items:
            item = ResolveTimelineItem(
                index=item_data["index"],
                source_file=item_data["source_file"],
                source_start=item_data["source_start"],
                duration=item_data["source_duration"],
                speed=item_data["speed"],
                speed_curve=item_data.get("speed_curve"),
                retime_process=item_data.get("retime_process", 0),
                transition=item_data.get("transition", ""),
                transition_duration=item_data.get("transition_duration", 0.0),
                color_cdl=item_data.get("color_cdl", {}),
                mood=item_data.get("mood", "build"),
                energy=item_data.get("energy", 0.5),
            )
            plan.items.append(item)

        if style_spec:
            plan.color_profile = style_spec.get("color_profile", {})

        # 统计
        speeds = [it.speed for it in plan.items if it.speed != 1.0]
        transitions = [it for it in plan.items if it.transition]
        logger.info(f"  时间线: {len(plan.items)} 个片段, "
                    f"{len(speeds)} 个变速, {len(transitions)} 个转场")

        return plan

    # ------------------------------------------------------------------
    # 主入口: StyleSpec 驱动渲染
    # ------------------------------------------------------------------
    def run_with_style(
        self,
        video_sources: list[str],
        bgm_path: str,
        style_spec_path: str | None = None,
        output_path: str = "",
        target_duration: float | None = None,
        fps: int = 30,
        force_ffmpeg: bool = False,
    ) -> str:
        """StyleSpec 驱动的完整渲染管线。

        Args:
            video_sources: 素材视频路径列表
            bgm_path: BGM 音频路径
            style_spec_path: 风格规格书 JSON 路径（可选）
            output_path: 输出路径（空则自动生成）
            target_duration: 目标时长（None 则用 BGM 时长）
            fps: 帧率
            force_ffmpeg: 强制使用 ffmpeg 管线（跳过 Resolve）

        Returns:
            输出视频路径
        """
        t0 = time.time()

        # 加载 StyleSpec
        style_spec = None
        if style_spec_path and os.path.exists(style_spec_path):
            style_spec = self.load_style_spec(style_spec_path)

        # 确定输出路径
        if not output_path:
            output_dir = os.path.join(str(_PROJECT_ROOT), "tmp", "renders", "style_resolve")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"style_{uuid.uuid4().hex[:8]}.mp4")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 环境检测
        resolve_ok = False if force_ffmpeg else self.check_resolve()
        ae_ok = self.check_ae()

        logger.info(f"管线启动: Resolve={'ON' if resolve_ok else 'OFF'}, "
                    f"AE={'ON' if ae_ok else 'OFF'}, "
                    f"StyleSpec={'YES' if style_spec else 'NO'}")

        # 生成时间线计划
        plan = self.build_timeline_plan(
            video_sources=video_sources,
            bgm_path=bgm_path,
            style_spec=style_spec,
            target_duration=target_duration,
            fps=fps,
        )

        # 执行渲染
        if resolve_ok:
            result = self._run_resolve_pipeline(plan, output_path, ae_ok, fps)
        else:
            logger.info("Resolve 离线 → ffmpeg 降级管线")
            result = self._run_ffmpeg_pipeline(plan, output_path, style_spec, fps)

        elapsed = time.time() - t0
        file_size = os.path.getsize(result) / (1024 * 1024) if os.path.exists(result) else 0

        self.last_report = {
            "output": result,
            "elapsed_s": round(elapsed, 1),
            "file_size_mb": round(file_size, 1),
            "pipeline_mode": "resolve" if resolve_ok else "ffmpeg",
            "ae_used": ae_ok and resolve_ok,
            "style_spec": style_spec_path,
            "timeline_items": len(plan.items),
            "total_duration": plan.total_duration,
        }

        logger.info(f"管线完成: {result} ({file_size:.1f}MB, {elapsed:.1f}s)")
        return result

    # ------------------------------------------------------------------
    # Resolve 管线 (完整三段式)
    # ------------------------------------------------------------------
    def _run_resolve_pipeline(
        self,
        plan: ResolveTimelinePlan,
        output_path: str,
        ae_online: bool,
        fps: int,
    ) -> str:
        """Resolve 三段式管线: Resolve(剪辑+变速) → AE(文字) → Resolve(调色+混音)"""
        from integrations.resolve_engine import CDLConfig, ResolveAutomationEngine

        engine = ResolveAutomationEngine(timeout=600)
        work = os.path.join(tempfile.gettempdir(), f"style_resolve_{uuid.uuid4().hex[:8]}")
        os.makedirs(work, exist_ok=True)

        project_name = f"style_clone_{uuid.uuid4().hex[:6]}"
        timeline_name = "main_timeline"

        try:
            # ---- Stage A: Resolve 剪辑 + 变速 ----
            logger.info("Stage A: Resolve 剪辑 + 变速...")

            # 创建项目
            lua_create = engine._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    pm:CreateProject("{project_name}")
    emit_ok({{project = "{project_name}"}})
            ''')
            engine._execute_lua(lua_create)

            # 导入素材（去重）
            unique_sources = list(set(it.source_file for it in plan.items))
            engine.import_media(project_name, unique_sources)

            # 创建时间线并添加片段
            for item in plan.items:
                lua_append = engine._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    local proj = pm:LoadProject("{project_name}")
    local mp = proj:GetMediaPool()
    local tl = mp:CreateEmptyTimeline("{timeline_name}")
    local items = mp:GetRootFolder():GetClipList()
    for _, clip in ipairs(items) do
        if clip:GetName() == "{os.path.basename(item.source_file)}" then
            tl:AppendToTimeline({{clip}})
        end
    end
    proj:SetCurrentTimeline(tl)
    emit_ok({{timeline = "{timeline_name}"}})
                ''')
                try:
                    engine._execute_lua(lua_append)
                except Exception as e:
                    logger.warning(f"  片段 {item.index} 添加失败: {e}")

            # 应用变速
            for item in plan.items:
                if item.speed != 1.0:
                    try:
                        engine.set_speed(project_name, item.index + 1,
                                        item.speed, item.retime_process)
                        logger.info(f"  片段 {item.index}: speed={item.speed:.2f}x")
                    except Exception as e:
                        logger.warning(f"  变速失败 {item.index}: {e}")

            # 应用 CDL 调色
            color_result = self.bridge.color_to_cdl(plan.color_profile)
            for item in plan.items:
                cdl = CDLConfig(
                    saturation=color_result.cdl_saturation,
                    contrast=color_result.cdl_contrast,
                    brightness=color_result.cdl_brightness,
                )
                try:
                    engine.apply_cdl(project_name, timeline_name,
                                    item.index + 1, cdl)
                except Exception as e:
                    logger.warning(f"  CDL 失败 {item.index}: {e}")

            # Stage A 渲染到中间文件
            stage_a_path = os.path.join(work, "stage_a.mp4")
            try:
                engine.render_project(project_name, stage_a_path)
                logger.info(f"Stage A 完成: {stage_a_path}")
            except Exception as e:
                logger.warning(f"Resolve 渲染失败: {e}, 用 ffmpeg 重建 Stage A")
                stage_a_path = self._ffmpeg_build_stage_a(plan, work, fps)

            # ---- Stage B: AE 文字动画 ----
            stage_b_path = stage_a_path
            if ae_online:
                logger.info("Stage B: AE 文字动画...")
                try:
                    stage_b_path = self._ae_title_pass(stage_a_path, work, plan, fps)
                    logger.info(f"Stage B 完成: {stage_b_path}")
                except Exception as e:
                    logger.warning(f"AE 文字失败: {e}, 跳过 Stage B")
            else:
                logger.info("Stage B: AE 离线, 跳过文字动画")

            # ---- Stage C: 混音 + 最终输出 ----
            logger.info("Stage C: 混音 + 最终输出...")
            self._ffmpeg_mix_audio(stage_b_path, plan.bgm_path,
                                   plan.bgm_start_sec, output_path)

        except Exception as e:
            logger.error(f"Resolve 管线异常: {e}, 降级 ffmpeg")
            return self._run_ffmpeg_pipeline(plan, output_path, None, fps)

        return output_path

    # ------------------------------------------------------------------
    # ffmpeg 降级管线
    # ------------------------------------------------------------------
    def _run_ffmpeg_pipeline(
        self,
        plan: ResolveTimelinePlan,
        output_path: str,
        style_spec: dict[str, Any] | None,
        fps: int,
    ) -> str:
        """ffmpeg 降级管线 — 使用 ProductionDirector 原路径"""
        from ai.production_director import ProductionDirector

        director = ProductionDirector()

        # 提取素材路径
        video_sources = list(set(it.source_file for it in plan.items))
        output_dir = os.path.dirname(output_path)
        output_name = os.path.basename(output_path)

        result = director.render(
            video_sources=video_sources,
            bgm_path=plan.bgm_path,
            output_dir=output_dir,
            output_name=output_name,
            bgm_start_sec=plan.bgm_start_sec,
            target_duration=plan.total_duration,
            fps=fps,
            style_spec=style_spec,
        )

        return result

    # ------------------------------------------------------------------
    # ffmpeg Stage A 重建（Resolve 渲染失败时）
    # ------------------------------------------------------------------
    def _ffmpeg_build_stage_a(
        self,
        plan: ResolveTimelinePlan,
        work_dir: str,
        fps: int,
    ) -> str:
        """用 ffmpeg 从时间线计划重建 Stage A（含变速+调色）"""
        color = self.bridge.color_to_cdl(plan.color_profile)

        # 逐片段处理
        seg_files = []
        for item in plan.items:
            seg_out = os.path.join(work_dir, f"seg_{item.index:03d}.mp4")

            # 构建滤镜链
            vf_parts = []

            # 变速
            if item.speed != 1.0:
                vf_parts.append(f"setpts={1.0/item.speed:.4f}*PTS")

            # 调色 (CDL → ffmpeg eq)
            eq_parts = []
            if abs(color.cdl_saturation - 1.0) > 0.01:
                eq_parts.append(f"saturation={color.cdl_saturation:.3f}")
            if abs(color.cdl_contrast - 1.0) > 0.01:
                eq_parts.append(f"contrast={color.cdl_contrast:.3f}")
            if abs(color.cdl_brightness) > 0.001:
                eq_parts.append(f"brightness={color.cdl_brightness:.3f}")
            if eq_parts:
                vf_parts.append("eq=" + ":".join(eq_parts))

            # 构建命令
            cmd = ["ffmpeg", "-y",
                   "-ss", f"{item.source_start:.3f}",
                   "-i", item.source_file,
                   "-t", f"{item.duration:.3f}"]

            if vf_parts:
                cmd += ["-vf", ",".join(vf_parts)]

            codec_args = ["-c:v", "libx264", "-preset", "fast",
                         "-crf", "18", "-pix_fmt", "yuv420p"]
            cmd += codec_args + ["-an", seg_out]

            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=300)
                seg_files.append(seg_out)
            except Exception as e:
                logger.warning(f"  片段 {item.index} ffmpeg 失败: {e}")

        if not seg_files:
            raise RuntimeError("所有片段处理失败")

        # 拼接
        concat_file = os.path.join(work_dir, "concat.txt")
        with open(concat_file, "w") as f:
            for sf in seg_files:
                f.write(f"file '{sf}'\n")

        stage_a = os.path.join(work_dir, "stage_a.mp4")
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
               "-i", concat_file, "-c", "copy", stage_a]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)

        return stage_a

    # ------------------------------------------------------------------
    # AE 文字动画
    # ------------------------------------------------------------------
    def _ae_title_pass(
        self,
        src: str,
        work: str,
        plan: ResolveTimelinePlan,
        fps: int,
    ) -> str:
        """AE 文字动画 pass"""
        from integrations.resolve_ae_resolve_pipeline import ResolveAeResolvePipeline
        pipe = ResolveAeResolvePipeline()
        duration = self._get_media_duration(src) or plan.total_duration

        # 检测切点
        cut_times = [0.0]
        for item in plan.items[1:]:
            cut_times.append(cut_times[-1] + item.duration)

        return pipe._ffmpeg_title_pass(
            src, work, plan.title, "", duration, fps)

    # ------------------------------------------------------------------
    # 混音
    # ------------------------------------------------------------------
    def _ffmpeg_mix_audio(
        self,
        video_path: str,
        bgm_path: str,
        bgm_start_sec: float,
        output_path: str,
    ) -> None:
        """ffmpeg 混音输出"""
        total_dur = self._get_media_duration(video_path) or 20.0
        fade_start = max(0.0, total_dur - 1.5)

        cmd = ["ffmpeg", "-y",
               "-i", video_path,
               "-ss", f"{bgm_start_sec:.3f}",
               "-i", bgm_path,
               "-filter_complex",
               f"[1:a]afade=t=out:st={fade_start:.2f}:d=1.5[a]",
               "-map", "0:v", "-map", "[a]",
               "-c:v", "copy",
               "-c:a", "aac", "-b:a", "192k",
               "-shortest",
               output_path]
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    def _get_media_duration(self, path: str) -> float | None:
        """获取媒体文件时长"""
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=10)
            return float(r.stdout.strip())
        except Exception:
            return None


# ============================================================================
# CLI 入口
# ============================================================================

def _main():
    import argparse
    parser = argparse.ArgumentParser(description="StyleSpec 驱动 Resolve 管线")
    parser.add_argument("--sources", required=True, help="素材文件逗号分隔")
    parser.add_argument("--bgm", required=True, help="BGM 路径")
    parser.add_argument("--style-spec", default=None, help="风格规格书 JSON")
    parser.add_argument("--output", default="", help="输出路径")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--force-ffmpeg", action="store_true", help="强制 ffmpeg")
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    pipeline = StyleResolvePipeline()
    result = pipeline.run_with_style(
        video_sources=sources,
        bgm_path=args.bgm,
        style_spec_path=args.style_spec,
        output_path=args.output,
        fps=args.fps,
        force_ffmpeg=args.force_ffmpeg,
    )
    print(f"DONE: {result}")
    print(json.dumps(pipeline.last_report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
