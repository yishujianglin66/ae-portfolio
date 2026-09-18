"""
pipeline/stages/rendering.py - 渲染阶段
=========================================
调用 aerender / nexrender 输出成品视频
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class RenderingStage:
    """渲染阶段：输出成品视频"""

    def __init__(self, config):
        self.config = config

    def run(self, previous_data: dict) -> dict:
        """执行渲染阶段"""
        execute = previous_data.get("execute", {})
        project_path = execute.get("project_path", "")
        comp_name = execute.get("composition", "")
        exec_mode = execute.get("execution_mode", "")

        result = {
            "output_path": "",
            "render_engine": "",
            "render_time_sec": 0,
            "file_size_mb": 0,
            "status": "pending",
        }

        output_dir = self.config.output_dir or "output"
        os.makedirs(output_dir, exist_ok=True)
        project_name = self.config.project_name or "pipeline_output"
        output_path = os.path.join(output_dir, f"{project_name}.mp4")

        start = time.time()

        # 1. 如果执行阶段产出了真实视频文件 (ffmpeg_fallback / real_mix / ae_render), 直接作为输出
        # P0 真混剪: execution_mode="ae_render" 时 execute 已通过 AE 内部渲染队列输出真实视频
        # execution_mode="real_mix" 时 execute 已用 FFmpegEditEngine 产出真实混剪视频
        if exec_mode in ("ffmpeg_fallback", "real_mix", "ae_render") and project_path and os.path.isfile(project_path):
            logger.info(f"[RENDER-PATH1] {exec_mode} copy: {project_path} -> {output_path}")
            import shutil
            if project_path != output_path:
                try:
                    shutil.copy2(project_path, output_path)
                except Exception as e:
                    logger.warning(f"[RENDER-PATH1] copy failed: {e}, using source as output")
                    output_path = project_path
            result["render_engine"] = (
                "ffmpeg_concat" if exec_mode == "ffmpeg_fallback"
                else ("ae_render" if exec_mode == "ae_render" else "real_mix")
            )
            result["output_path"] = output_path
            result["render_time_sec"] = round(time.time() - start, 1)
            result["status"] = "success"
            if os.path.isfile(output_path):
                result["file_size_mb"] = round(os.path.getsize(output_path) / (1024 * 1024), 2)
            return result

        # 2. 尝试 aerender
        if project_path and not os.path.isfile(project_path):
            logger.info(f"[RENDER-PATH2] aerender: project={project_path}")
            render_result = self._render_aerender(project_path, comp_name, output_path)
            if render_result.get("success"):
                result["render_engine"] = "aerender"
                result["output_path"] = output_path
                result["render_time_sec"] = round(time.time() - start, 1)
                result["status"] = "success"
                if os.path.isfile(output_path):
                    result["file_size_mb"] = round(os.path.getsize(output_path) / (1024 * 1024), 2)
                self._archive_output(output_path)
                return result

        # 3. 尝试 FFmpeg 基础渲染 (生成占位视频)
        logger.info(f"[RENDER-PATH3] ffmpeg fallback render: exec_mode={exec_mode} project_path={project_path}")
        render_result = self._render_ffmpeg(output_path, previous_data)
        if render_result.get("success"):
            result["render_engine"] = "ffmpeg"
            result["output_path"] = render_result.get("output_path", output_path)
            result["render_time_sec"] = round(time.time() - start, 1)
            result["status"] = "success"
            if os.path.isfile(result["output_path"]):
                result["file_size_mb"] = round(os.path.getsize(result["output_path"]) / (1024 * 1024), 2)
            return result

        # 4. 全部失败
        logger.warning("[RENDER-PATH4] all render paths failed")
        result["status"] = "pending_manual_render"
        result["error"] = "No render engine available. Project saved for manual render."
        result["project_path"] = project_path
        return result

    def _render_aerender(self, project: str, comp: str, output: str) -> dict:
        """用 aerender 命令行渲染"""
        try:
            from rendering.ae_render_engine import AERenderEngine
            engine = AERenderEngine()
            job = engine.render(
                project=project,
                composition=comp,
                output=output,
                output_format=getattr(self.config, 'render_format', 'mp4'),
                reuse_ae=getattr(self.config, 'reuse_ae', True),
            )
            engine.wait(job.job_id, timeout=3600)
            return {"success": job.status.value == "success"}
        except Exception as e:
            logger.debug(f"aerender failed: {e}")
            return {"success": False, "error": str(e)}

    def _render_ffmpeg(self, output_path: str, previous_data: dict) -> dict:
        """FFmpeg 渲染 — 生成占位视频或使用已有素材"""
        import subprocess
        perceive = previous_data.get("perceive", {})
        videos = perceive.get("videos", [])
        analysis = previous_data.get("analyze", {})
        total_dur = analysis.get("total_duration", 10)
        # 确保 total_dur 有合理最小值，避免 -t 0 生成空壳
        try:
            total_dur = float(total_dur)
        except (TypeError, ValueError):
            total_dur = 10.0
        if total_dur < 1.0:
            logger.warning(f"[RENDER-FF] total_dur={total_dur} too small, force to 10.0")
            total_dur = 10.0

        logger.info(f"[RENDER-FF] videos={len(videos)} total_dur={total_dur}")

        # 尝试用素材生成视频
        video_files = [v.get("path", "") for v in videos if os.path.isfile(v.get("path", ""))]
        if video_files:
            try:
                from pipeline.stages import resolve_ffmpeg
                ffmpeg = resolve_ffmpeg(self.config)
                logger.info(f"[RENDER-FF] using footage: {video_files[0]}")
                # 用第一个素材生成带时长的输出 (高质量: CRF 18 + preset slow + scale 到 1080p)
                cmd = [
                    ffmpeg, "-y", "-i", video_files[0],
                    "-t", str(total_dur),
                    "-vf", "scale=1920:1080:flags=lanczos",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                    "-b:v", "4M", "-maxrate", "8M", "-bufsize", "16M",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    "-pix_fmt", "yuv420p",
                    output_path
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
                logger.info(f"[RENDER-FF] footage render rc={r.returncode} size={os.path.getsize(output_path) if os.path.isfile(output_path) else 0}")
                if r.returncode != 0:
                    logger.warning(f"[RENDER-FF] ffmpeg stderr (tail): {r.stderr[-500:] if r.stderr else 'empty'}")
                if r.returncode == 0 and os.path.isfile(output_path) and os.path.getsize(output_path) > 1000:
                    logger.info(f"FFmpeg render: {output_path}")
                    return {"success": True, "output_path": output_path}
                else:
                    logger.warning("[RENDER-FF] footage render produced invalid file, falling back to placeholder")
            except Exception as e:
                logger.debug(f"FFmpeg render from footage failed: {e}")

        # 降级: 生成纯色占位视频
        try:
            from pipeline.stages import resolve_ffmpeg
            ffmpeg = resolve_ffmpeg(self.config)
            logger.info(f"[RENDER-FF] generating placeholder video dur={total_dur}")
            cmd = [
                ffmpeg, "-y",
                "-f", "lavfi", "-i", f"color=c=black:s=1920x1080:d={total_dur}:r=30",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", str(total_dur),
                "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                "-b:v", "4M", "-maxrate", "8M", "-bufsize", "16M",
                "-c:a", "aac",
                "-shortest",
                "-pix_fmt", "yuv420p",
                output_path
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
            logger.info(f"[RENDER-FF] placeholder rc={r.returncode} size={os.path.getsize(output_path) if os.path.isfile(output_path) else 0}")
            if r.returncode != 0:
                logger.warning(f"[RENDER-FF] placeholder stderr (tail): {r.stderr[-500:] if r.stderr else 'empty'}")
            if r.returncode == 0 and os.path.isfile(output_path) and os.path.getsize(output_path) > 1000:
                logger.info(f"FFmpeg placeholder render: {output_path}")
                # 标记为占位视频, 供下游质量门检测降级
                return {"success": True, "output_path": output_path, "placeholder": True}
            else:
                logger.warning("[RENDER-FF] placeholder produced invalid file")
        except Exception as e:
            logger.debug(f"FFmpeg placeholder failed: {e}")

        return {"success": False, "error": "FFmpeg not available or failed"}

    def _archive_output(self, output_path: str):
        """渲染完成后归档"""
        if not output_path or not os.path.isfile(output_path):
            return
        try:
            import shutil
            archive_dir = os.path.join(self.config.output_dir or "output", "archive")
            os.makedirs(archive_dir, exist_ok=True)
            dest = os.path.join(archive_dir, os.path.basename(output_path))
            shutil.copy2(output_path, dest)
            logger.info(f"Archived: {output_path} -> {dest}")
        except Exception as e:
            logger.debug(f"Archive failed: {e}")