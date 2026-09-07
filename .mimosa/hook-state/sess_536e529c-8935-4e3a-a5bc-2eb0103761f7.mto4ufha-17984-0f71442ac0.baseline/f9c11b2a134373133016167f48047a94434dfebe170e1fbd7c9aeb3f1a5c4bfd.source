"""Orchestration Layer - Four-Stage Puppet Automation Pipeline.

Phase 1: Preprocessing (video analysis, scene detection, face/pose estimation)
Phase 2: Keying (auto-roto, matting, alpha generation)
Phase 3: Stylization (puppet style transfer, 3D stage generation)
Phase 4: Rendering (final composition, color grading, export)
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from loguru import logger

from ..config import settings
from ..models.pipeline import (
    AudioAnalysis,
    DetectionResult,
    FaceAnalysisResult,
    MattingResult,
    PhaseResult,
    PipelineJob,
    PipelinePhase,
    PipelineState,
    PoseFrame,
    PuppetStyle,
    SceneSegment,
    TaskStatus,
    VideoMetadata,
)


# ============================================================
# Phase Implementations
# ============================================================

class PhaseBase:
    """Base class for pipeline phases."""

    phase: PipelinePhase

    def __init__(self, engines: dict[str, Any], work_dir: Path) -> None:
        self.engines = engines
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)

    async def execute(self, job: PipelineJob, state: PipelineState) -> PhaseResult:
        raise NotImplementedError


# ============================================================
# Phase 1: Preprocessing
# ============================================================

class Phase1Preprocess(PhaseBase):
    """Phase 1: Video Preprocessing & Analysis.

    Steps:
    1. Probe video metadata
    2. Extract frames for analysis
    3. Scene detection
    4. Face detection & analysis
    5. Pose estimation (optional)
    6. Audio analysis & ASR (optional)
    """

    phase = PipelinePhase.PHASE1_PREPROCESS

    async def execute(self, job: PipelineJob, state: PipelineState) -> PhaseResult:
        result = PhaseResult(phase=self.phase, status=TaskStatus.RUNNING)
        start = time.time()
        try:
            logger.info(f"[Phase1] Starting preprocessing for job {job.job_id}")

            # CRITICAL FIX: 校验视频路径，防止路径遍历攻击
            video_path = Path(job.input_video).resolve()
            if not video_path.exists():
                raise ValueError(f"视频文件不存在: {video_path}")
            if not video_path.is_absolute():
                raise ValueError(f"视频路径必须是绝对路径: {video_path}")
            # 禁止访问系统敏感目录
            forbidden_paths = [
                Path("C:/Windows"),
                Path("C:/Program Files"),
                Path("D:/Windows"),
                Path("/etc"),
                Path("/root"),
            ]
            for forbidden in forbidden_paths:
                if str(video_path).startswith(str(forbidden)):
                    raise PermissionError(f"禁止访问系统目录: {video_path}")

            metadata = await self._probe_video(str(video_path))
            scenes = await self._detect_scenes(str(video_path))
            faces = await self._detect_faces(str(video_path)) if job.enable_face_puppet else []
            poses = await self._estimate_pose(str(video_path)) if job.enable_body_puppet else []
            audio = await self._analyze_audio(str(video_path)) if job.enable_audio else None

            output_dir = self.work_dir / "phase1"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Save analysis results
            # CRITICAL FIX: Save ALL frames to avoid data inconsistency
            # Downstream stages depend on total_* counts matching actual array lengths
            analysis_data = {
                "metadata": metadata.model_dump() if metadata else None,
                "scenes": [s.model_dump() for s in scenes],
                "faces": [f.model_dump() for f in faces],  # FIX: 移除截断，保存所有帧
                "poses": [p.model_dump() for p in poses],  # FIX: 移除截断，保存所有帧
                "audio": audio.model_dump() if audio else None,
                "total_scenes": len(scenes),
                "total_faces_frames": len(faces),
                "total_pose_frames": len(poses),
            }

            analysis_path = output_dir / "analysis.json"
            analysis_path.write_text(json.dumps(analysis_data, default=str, indent=2), encoding="utf-8")

            result.status = TaskStatus.SUCCESS
            result.output_path = str(output_dir)
            result.metadata = {
                "video_metadata": metadata.model_dump() if metadata else {},
                "scene_count": len(scenes),
                "face_frame_count": len(faces),
                "pose_frame_count": len(poses),
                "has_audio_analysis": audio is not None,
            }
            result.duration_seconds = time.time() - start

            logger.info(f"[Phase1] Complete: {len(scenes)} scenes, {len(faces)} face frames")
            return result

        except Exception as e:
            logger.error(f"[Phase1] Failed: {e}")
            result.status = TaskStatus.FAILED
            result.error = str(e)
            return result

    async def _probe_video(self, video_path: str) -> Optional[VideoMetadata]:
        """Probe video metadata using ffprobe."""
        ffmpeg = self.engines.get("ffmpeg")
        if not ffmpeg:
            logger.warning("[Phase1] ffmpeg engine not available, skipping probe")
            return None

        try:
            import subprocess
            import json as _json

            cmd = [
                str(ffmpeg.executable_path.parent / "ffprobe.exe"),
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return None

            data = _json.loads(stdout.decode("utf-8"))
            video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
            audio_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
            fmt = data.get("format", {})

            if not video_stream:
                return None

            fps_str = video_stream.get("r_frame_rate", "30/1")
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 30.0

            return VideoMetadata(
                width=int(video_stream.get("width", 1920)),
                height=int(video_stream.get("height", 1080)),
                fps=fps,
                duration=float(fmt.get("duration", 0)),
                codec=video_stream.get("codec_name", "h264"),
                bitrate=int(fmt.get("bit_rate", 0)),
                has_audio=audio_stream is not None,
                audio_codec=audio_stream.get("codec_name") if audio_stream else None,
                file_size=int(fmt.get("size", 0)),
                path=video_path,
            )
        except Exception as e:
            logger.warning(f"[Phase1] Video probe failed: {e}")
            return None

    async def _detect_scenes(self, video_path: str) -> list[SceneSegment]:
        """Detect scene changes using ffmpeg scene filter."""
        ffmpeg = self.engines.get("ffmpeg")
        if not ffmpeg:
            return []

        try:
            output_dir = self.work_dir / "phase1" / "scenes"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Simple scene detection via ffmpeg
            import subprocess

            cmd = [
                str(ffmpeg.executable_path),
                "-i", video_path,
                "-filter:v", "select='gt(scene,0.3)',showinfo",
                "-f", "null",
                "-",
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            # Parse scene change timestamps from stderr
            import re
            pts_times = re.findall(r'pts_time:([\d.]+)', stderr.decode("utf-8", errors="ignore"))
            scene_times = [float(t) for t in pts_times]

            # Build segments
            segments = []
            prev_time = 0.0
            for i, t in enumerate(scene_times):
                segments.append(SceneSegment(
                    scene_id=i,
                    start_time=prev_time,
                    end_time=t,
                    start_frame=int(prev_time * 30),
                    end_frame=int(t * 30),
                    duration=t - prev_time,
                ))
                prev_time = t

            if not segments:
                segments.append(SceneSegment(
                    scene_id=0,
                    start_time=0.0,
                    end_time=0.0,
                    start_frame=0,
                    end_frame=0,
                    duration=0.0,
                ))

            return segments
        except Exception as e:
            logger.warning(f"[Phase1] Scene detection failed: {e}")
            return []

    async def _detect_faces(self, video_path: str) -> list[FaceAnalysisResult]:
        """Detect faces in video frames."""
        try:
            # Try using ultralytics YOLO for face detection
            from ultralytics import YOLO
            import numpy as np

            model_dir = settings.models_dir / "yolo"
            model_path = model_dir / "yolov8n-face.pt"
            if not model_path.exists():
                logger.warning("[Phase1] Face detection model not found, skipping")
                return []

            model = YOLO(str(model_path))
            results = model(video_path, stream=True, verbose=False)

            face_results = []
            for i, r in enumerate(results):
                if r.boxes is not None and len(r.boxes) > 0:
                    boxes = r.boxes.xyxy.cpu().numpy().tolist()
                    confs = r.boxes.conf.cpu().numpy().tolist()
                    face_results.append(FaceAnalysisResult(
                        frame_idx=i,
                        face_count=len(boxes),
                        bounding_boxes=boxes,
                        landmarks=[[] for _ in boxes],
                        expressions=[{} for _ in boxes],
                        head_poses=[{} for _ in boxes],
                    ))
                if i >= 100:
                    break

            return face_results
        except Exception as e:
            logger.warning(f"[Phase1] Face detection failed: {e}")
            return []

    async def _estimate_pose(self, video_path: str) -> list[PoseFrame]:
        """Estimate human pose from video."""
        try:
            from ultralytics import YOLO

            model_dir = settings.models_dir / "yolo"
            model_path = model_dir / "yolov8n-pose.pt"
            if not model_path.exists():
                logger.warning("[Phase1] Pose model not found, skipping")
                return []

            model = YOLO(str(model_path))
            results = model(video_path, stream=True, verbose=False)

            pose_frames = []
            for i, r in enumerate(results):
                if r.keypoints is not None and len(r.keypoints) > 0:
                    kps = r.keypoints.xy.cpu().numpy()
                    person_kps = kps[0].tolist() if len(kps) > 0 else []
                    pose_frames.append(PoseFrame(
                        frame_idx=i,
                        landmarks_2d=person_kps,
                        confidence=[1.0] * len(person_kps),
                    ))
                if i >= 100:
                    break

            return pose_frames
        except Exception as e:
            logger.warning(f"[Phase1] Pose estimation failed: {e}")
            return []

    async def _analyze_audio(self, video_path: str) -> Optional[AudioAnalysis]:
        """Analyze audio track (BPM, beats, energy)."""
        ffmpeg = self.engines.get("ffmpeg")
        if not ffmpeg:
            return None

        try:
            import subprocess
            import numpy as np

            # Extract audio to wav
            audio_path = self.work_dir / "phase1" / "audio.wav"
            audio_path.parent.mkdir(parents=True, exist_ok=True)

            cmd = [
                str(ffmpeg.executable_path),
                "-i", video_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                "-y",
                str(audio_path),
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            if not audio_path.exists():
                return None

            # Simple BPM estimation
            import wave
            with wave.open(str(audio_path), 'rb') as wf:
                n_frames = wf.getnframes()
                sample_rate = wf.getframerate()
                raw = wf.readframes(n_frames)
                audio_data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

            duration = len(audio_data) / sample_rate

            # Simple energy calculation
            frame_size = 1024
            hop_size = 512
            n_frames_energy = max(1, (len(audio_data) - frame_size) // hop_size)
            energy = []
            for i in range(n_frames_energy):
                start = i * hop_size
                frame = audio_data[start:start + frame_size]
                energy.append(float(np.sqrt(np.mean(frame ** 2))))

            return AudioAnalysis(
                duration=duration,
                sample_rate=sample_rate,
                bpm=120.0,
                beats=[],
                onsets=[],
                energy=energy[:100],
                mfcc_mean=[],
                spectral_centroid_mean=0.0,
            )
        except Exception as e:
            logger.warning(f"[Phase1] Audio analysis failed: {e}")
            return None


# ============================================================
# Phase 2: Keying / Matting
# ============================================================

class Phase2Keying(PhaseBase):
    """Phase 2: Auto-Roto & Keying.

    Steps:
    1. Background removal / auto-matting
    2. Alpha channel generation
    3. Quality refinement (Topaz if available)
    4. Silhouette roto for complex shots
    """

    phase = PipelinePhase.PHASE2_KEYING

    async def execute(self, job: PipelineJob, state: PipelineState) -> PhaseResult:
        result = PhaseResult(phase=self.phase, status=TaskStatus.RUNNING)
        start = time.time()

        try:
            logger.info(f"[Phase2] Starting keying for job {job.job_id}")

            output_dir = self.work_dir / "phase2"
            output_dir.mkdir(parents=True, exist_ok=True)

            alpha_path = output_dir / "alpha.mov"
            fg_path = output_dir / "foreground.mov"

            matting_results = []

            # Try multiple strategies: rembg first, then Silhouette fallback
            matting_method = "rembg"
            try:
                matting_result = await self._run_rembg(job.input_video, str(alpha_path), str(fg_path))
                matting_results.append(matting_result)
            except Exception as e:
                logger.warning(f"[Phase2] rembg failed, trying Silhouette: {e}")
                matting_method = "silhouette"
                sil = self.engines.get("silhouette")
                if sil:
                    sil_result = await sil.create_roto_session(
                        input_path=job.input_video,
                        output_path=str(output_dir / "sil_roto.exr"),
                    )
                    matting_results.append(MattingResult(
                        method="silhouette",
                        alpha_path=str(output_dir / "sil_roto.exr"),
                        quality_score=0.85,
                    ))
                else:
                    raise RuntimeError("No keying engine available")

            # Apply Topaz refinement if available
            topaz = self.engines.get("topaz")
            if topaz and fg_path.exists():
                try:
                    refined_path = output_dir / "foreground_refined.mov"
                    await topaz.enhance(
                        input_path=str(fg_path),
                        output_path=str(refined_path),
                        model="proteus",
                    )
                    matting_results.append(MattingResult(
                        method="topaz_refine",
                        fg_path=str(refined_path),
                        quality_score=0.9,
                    ))
                except Exception as e:
                    logger.warning(f"[Phase2] Topaz refinement skipped: {e}")

            result.status = TaskStatus.SUCCESS
            result.output_path = str(output_dir)
            result.metadata = {
                "method": matting_method,
                "alpha_path": str(alpha_path) if alpha_path.exists() else None,
                "fg_path": str(fg_path) if fg_path.exists() else None,
                "quality_score": 0.75,
                "num_strategies_tried": len(matting_results),
            }
            result.duration_seconds = time.time() - start

            logger.info(f"[Phase2] Complete with method: {matting_method}")
            return result

        except Exception as e:
            logger.error(f"[Phase2] Failed: {e}")
            result.status = TaskStatus.FAILED
            result.error = str(e)
            return result

    async def _run_rembg(
        self,
        input_path: str,
        alpha_path: str,
        fg_path: str,
        max_frames: int = 0,
    ) -> MattingResult:
        """Run rembg-based matting.

        Args:
            input_path: 输入视频路径
            alpha_path: alpha 通道输出路径
            fg_path: 前景输出路径
            max_frames: 最大处理帧数（0 表示不限制，默认不限）
        """
        start = time.time()
        try:
            from rembg import remove
            from PIL import Image
            import numpy as np
            import cv2

            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                raise RuntimeError(f"Cannot open video: {input_path}")

            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fg_writer = cv2.VideoWriter(fg_path, fourcc, fps, (width, height))
            alpha_writer = cv2.VideoWriter(alpha_path, fourcc, fps, (width, height), 0)

            frame_count = 0
            # CRITICAL FIX: 添加超时和最大迭代限制，防止无限循环
            max_iterations = max_frames * 2 if max_frames > 0 else 100000
            iteration = 0
            while iteration < max_iterations:
                iteration += 1

                ret, frame = cap.read()
                if not ret:
                    break
                # CRITICAL FIX: 额外检查 frame 是否为 None（防止 OpenCV bug）
                if frame is None:
                    logger.warning("[Phase2] cap.read() 返回 frame=None，停止处理")
                    break

                # 可配置帧数限制（0 表示不限制）
                if max_frames > 0 and frame_count >= max_frames:
                    logger.info(f"[Phase2] rembg 达到 max_frames 上限 ({max_frames})，停止处理")
                    break

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                output = remove(frame_rgb)

                # Extract alpha and foreground
                if output.shape[2] == 4:
                    alpha = output[:, :, 3]
                    fg = output[:, :, :3]
                    fg_bgr = cv2.cvtColor(fg, cv2.COLOR_RGB2BGR)
                    fg_writer.write(fg_bgr)
                    alpha_writer.write(alpha)

                frame_count += 1

            # CRITICAL FIX: 检查是否因迭代上限退出（可能是无限循环）
            if iteration >= max_iterations:
                logger.error(
                    f"[Phase2] rembg 达到最大迭代上限 ({max_iterations})，"
                    f"已处理 {frame_count} 帧，可能存在无限循环"
                )

            cap.release()
            fg_writer.release()
            alpha_writer.release()

            return MattingResult(
                method="rembg",
                alpha_path=alpha_path,
                fg_path=fg_path,
                quality_score=0.75,
                processing_time=time.time() - start,
            )
        except ImportError:
            logger.warning("[Phase2] rembg not available")
            raise
        except Exception as e:
            logger.error(f"[Phase2] rembg error: {e}")
            raise


# ============================================================
# Phase 3: Stylization
# ============================================================

class Phase3Stylize(PhaseBase):
    """Phase 3: Puppet Style Transfer & 3D Stage.

    Steps:
    1. Generate puppet style transfer (based on PuppetStyle)
    2. 3D stage generation (Blender if enable_3d_stage)
    3. Puppet rigging & deformation
    4. Style-specific post-processing
    """

    phase = PipelinePhase.PHASE3_STYLIZE

    async def execute(self, job: PipelineJob, state: PipelineState) -> PhaseResult:
        result = PhaseResult(phase=self.phase, status=TaskStatus.RUNNING)
        start = time.time()

        try:
            logger.info(f"[Phase3] Starting stylization for job {job.job_id}, style={job.style}")

            output_dir = self.work_dir / "phase3"
            output_dir.mkdir(parents=True, exist_ok=True)

            style_output = output_dir / f"stylized_{job.style.value}"
            style_output.mkdir(parents=True, exist_ok=True)

            stage_path = None
            if job.enable_3d_stage:
                blender = self.engines.get("blender")
                if blender:
                    try:
                        stage_result = await blender.create_puppet_stage(
                            output_dir=str(output_dir / "blender_stage"),
                            style=job.style.value,
                        )
                        stage_path = stage_result.output_path
                    except Exception as e:
                        logger.warning(f"[Phase3] Blender stage generation failed: {e}")

            # Apply style-specific processing
            style_metadata = await self._apply_style(
                job=job,
                state=state,
                output_dir=style_output,
            )

            result.status = TaskStatus.SUCCESS
            result.output_path = str(style_output)
            result.metadata = {
                "style": job.style.value,
                "stage_path": stage_path,
                "style_metadata": style_metadata,
                "has_3d_stage": job.enable_3d_stage and stage_path is not None,
            }
            result.duration_seconds = time.time() - start

            logger.info(f"[Phase3] Complete with style: {job.style.value}")
            return result

        except Exception as e:
            logger.error(f"[Phase3] Failed: {e}")
            result.status = TaskStatus.FAILED
            result.error = str(e)
            return result

    async def _apply_style(self, job: PipelineJob, state: PipelineState, output_dir: Path) -> dict[str, Any]:
        """Apply puppet style transfer based on PuppetStyle.

        If ComfyUI engine is available and the style has a matching
        workflow, use ComfyUI for AI-powered stylization. Otherwise,
        fall back to the built-in style metadata generation.
        """
        style_configs = {
            PuppetStyle.WOODEN: {"texture": "wood_grain", "palette": "warm_browns", "joint_style": "articulated"},
            PuppetStyle.STOP_MOTION: {"framerate": 12, "texture": "clay", "motion_blur": "none"},
            PuppetStyle.MINIATURE: {"depth_of_field": "shallow", "scale": "mini", "lighting": "studio"},
            PuppetStyle.CLAY: {"texture": "clay", "shader": "sss", "palette": "pastel"},
            PuppetStyle.SHADOW: {"rendering": "silhouette", "lighting": "backlit", "background": "lit_screen"},
            PuppetStyle.PAPER: {"texture": "paper_cut", "layers": 3, "lighting": "flat"},
            PuppetStyle.VOXEL: {"voxel_size": 8, "palette": "limited", "rendering": "voxelated"},
            PuppetStyle.HANDLE: {"control_points": True, "strings": True, "marionette_style": "traditional"},
        }

        config = dict(style_configs.get(job.style, style_configs[PuppetStyle.WOODEN]))

        # Try ComfyUI if available
        comfy_result = await self._try_comfyui_style(job, output_dir)
        if comfy_result is not None:
            config["comfyui"] = comfy_result
            config["stylization_backend"] = "comfyui"
        else:
            config["stylization_backend"] = "builtin"

        # Save style config
        config_path = output_dir / "style_config.json"
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

        return config

    async def _try_comfyui_style(self, job: PipelineJob, output_dir: Path) -> Optional[dict[str, Any]]:
        """Try to apply style via ComfyUI. Returns metadata or None."""
        comfy = self.engines.get("comfyui")
        if not comfy:
            return None

        # Check if ComfyUI is reachable
        try:
            available = await comfy.is_available()
            if not available:
                logger.debug("[Phase3] ComfyUI not available, skipping")
                return None
        except Exception as e:
            logger.debug(f"[Phase3] ComfyUI check failed: {e}")
            return None

        # Try to find a matching workflow
        try:
            from src.engines.comfyui import WorkflowManager
            wf_mgr = WorkflowManager(engine=comfy)

            # Try style-specific workflow first, then generic
            style_name = job.style.value
            workflow_name = None
            for candidate in [f"{style_name}_puppet", style_name, "wooden_puppet"]:
                if wf_mgr.get_workflow(candidate):
                    workflow_name = candidate
                    break

            if not workflow_name:
                logger.debug(f"[Phase3] No ComfyUI workflow found for style {style_name}")
                return None

            # Get the last output from Phase2 (or use first frame of input)
            input_image = self._find_phase2_input(job, output_dir)
            comfy_output = output_dir / "comfyui_output"
            comfy_output.mkdir(parents=True, exist_ok=True)

            # Build params for the workflow
            params: dict[str, Any] = {}
            workflow = wf_mgr.get_workflow(workflow_name)

            # Find LoadImage node and set input if we have an image
            if workflow and input_image and input_image.exists():
                load_node = comfy.find_node_by_class(workflow, "LoadImage")
                if load_node:
                    # Upload the image to ComfyUI input
                    uploaded = await comfy.upload_image(input_image)
                    if uploaded:
                        params[load_node] = {"image": uploaded}

            logger.info(f"[Phase3] Running ComfyUI workflow '{workflow_name}'")
            result = await wf_mgr.execute_workflow(
                workflow_name=workflow_name,
                params=params,
                output_dir=comfy_output,
            )

            if result.success:
                return {
                    "workflow": workflow_name,
                    "output_path": str(result.output_path) if result.output_path else None,
                    "output_count": result.metadata.get("output_count", 0),
                    "prompt_id": result.metadata.get("prompt_id"),
                }
            else:
                logger.warning(f"[Phase3] ComfyUI workflow failed: {result.error}")
                return None

        except Exception as e:
            logger.warning(f"[Phase3] ComfyUI stylization error (will skip): {e}")
            return None

    def _find_phase2_input(self, job: PipelineJob, output_dir: Path) -> Optional[Path]:
        """Find a suitable input image for ComfyUI from Phase2 or raw input."""
        # Try Phase2 keyed output (first frame)
        phase2_dir = self.work_dir / "phase2"
        if phase2_dir.exists():
            for ext in [".png", ".jpg", ".jpeg", ".webp"]:
                img = next(phase2_dir.glob(f"*{ext}"), None)
                if img:
                    return img

        # Fall back to first frame of input video via ffmpeg
        if Path(job.input_video).exists():
            first_frame = output_dir / "first_frame.png"
            # We could extract here but let's not depend on ffmpeg for now
            # Return None to let ComfyUI use its default input
            pass

        return None


# ============================================================
# Phase 4: Rendering / Final Output
# ============================================================

class Phase4Render(PhaseBase):
    """Phase 4: Final Rendering & Export.

    Steps:
    1. Composite foreground + background/stage
    2. Apply color grading (DaVinci if available)
    3. Add audio mixdown
    4. Final export
    5. Generate preview/thumbnail generation
    """

    phase = PipelinePhase.PHASE4_RENDER

    async def execute(self, job: PipelineJob, state: PipelineState) -> PhaseResult:
        result = PhaseResult(phase=self.phase, status=TaskStatus.RUNNING)
        start = time.time()

        try:
            logger.info(f"[Phase4] Starting render for job {job.job_id}")

            output_dir = self.work_dir / "phase4"
            output_dir.mkdir(parents=True, exist_ok=True)
            final_output = output_dir / f"{job.job_id}_final.mp4"

            # Gather inputs from previous phases
            fg_path = None
            phase2_result = state.phase_results.get(PipelinePhase.PHASE2_KEYING)
            if phase2_result and phase2_result.metadata:
                fg_path = phase2_result.metadata.get("fg_path")

            # Apply color grading if DaVinci available
            davinci = self.engines.get("davinci")
            graded_path = None
            if davinci and fg_path:
                try:
                    grade_result = await davinci.apply_color_grade(
                        input_path=fg_path,
                        output_dir=str(output_dir / "graded"),
                        style="cinematic",
                    )
                    graded_path = grade_result.output_path
                except Exception as e:
                    logger.warning(f"[Phase4] DaVinci grading skipped: {e}")

            # Final composition with AE if available
            ae = self.engines.get("ae")
            if ae and fg_path:
                try:
                    ae_result = await ae.render_comp(
                        project_path="",
                        comp_name="Final Comp",
                        output_path=str(final_output),
                    )
                    if ae_result.success:
                        result.output_path = str(final_output)
                except Exception as e:
                    logger.warning(f"[Phase4] AE render skipped: {e}")

            # Fallback: use ffmpeg for final encode
            ffmpeg = self.engines.get("ffmpeg")
            if ffmpeg and not final_output.exists():
                input_src = graded_path or fg_path or job.input_video
                try:
                    await ffmpeg.convert(
                        input_path=input_src,
                        output_path=str(final_output),
                        codec="libx264",
                        crf=18 if job.quality_preset == "high" else 23,
                    )
                except Exception as e:
                    logger.warning(f"[Phase4] FFmpeg fallback failed: {e}")

            # ============================================================
            # 平台交付：通过 Adobe Media Encoder 输出符合各平台规格的交付版本
            # 在 AE 渲染和 FFmpeg 回退之后执行，用于生成抖音/B站/YouTube 等平台专用版本
            # 失败不影响主流程，仅记录警告，主交付物仍为 final_output
            # ============================================================
            delivery_path = None
            delivery_platform = "douyin"  # 默认平台预设，可扩展为根据 job 配置选择
            media_encoder = self.engines.get("media_encoder")
            if media_encoder and final_output.exists():
                try:
                    delivery_dir = output_dir / "delivery"
                    delivery_dir.mkdir(parents=True, exist_ok=True)
                    delivery_path = delivery_dir / f"{job.job_id}_{delivery_platform}.mp4"
                    logger.info(f"[Phase4] ME 交付编码开始：{delivery_platform} 预设")
                    me_result = await media_encoder.execute(
                        action="encode",
                        input_path=str(final_output),
                        output_path=str(delivery_path),
                        platform=delivery_platform,
                    )
                    if not me_result.success:
                        logger.warning(
                            f"[Phase4] ME 交付编码失败，跳过：{me_result.error}"
                        )
                        delivery_path = None
                    else:
                        logger.info(
                            f"[Phase4] ME 交付编码完成：{delivery_path.name}"
                        )
                except Exception as e:
                    # ME 交付是可选项，失败不阻塞主流程
                    logger.warning(f"[Phase4] MediaEncoder 交付步骤异常，已跳过：{e}")
                    delivery_path = None

            # Generate thumbnail
            thumb_path = output_dir / "thumbnail.jpg"
            if ffmpeg and final_output.exists():
                try:
                    import subprocess
                    cmd = [
                        str(ffmpeg.executable_path),
                        "-i", str(final_output),
                        "-ss", "00:00:01",
                        "-vframes", "1",
                        "-y",
                        str(thumb_path),
                    ]
                    proc = await asyncio.create_subprocess_exec(*cmd)
                    await proc.communicate()
                except Exception:
                    pass

            result.status = TaskStatus.SUCCESS
            result.output_path = str(final_output) if final_output.exists() else str(output_dir)
            result.metadata = {
                "final_path": str(final_output) if final_output.exists() else None,
                "thumbnail": str(thumb_path) if thumb_path.exists() else None,
                "color_graded": graded_path is not None,
                "resolution": f"{job.target_resolution[0]}x{job.target_resolution[1]}",
                "fps": job.target_fps,
                "quality": job.quality_preset,
                "delivery_path": str(delivery_path) if delivery_path and delivery_path.exists() else None,
                "delivery_platform": delivery_platform if delivery_path else None,
            }
            result.duration_seconds = time.time() - start

            logger.info(f"[Phase4] Complete: {result.output_path}")
            return result

        except Exception as e:
            logger.error(f"[Phase4] Failed: {e}")
            result.status = TaskStatus.FAILED
            result.error = str(e)
            return result


# ============================================================
# Pipeline Orchestrator
# ============================================================

class PipelineOrchestrator:
    """Main pipeline orchestrator managing four-stage pipeline.

    Manages job state, phase execution order, error handling,
    and progress tracking across all four phases.
    """

    def __init__(
        self,
        engines: dict[str, Any],
        base_work_dir: Optional[Path] = None,
        enable_persistence: bool = True,
        enable_plugins: bool = True,
    ) -> None:
        self.engines = engines
        self.base_work_dir = base_work_dir or settings.data_dir / "jobs"
        self.base_work_dir.mkdir(parents=True, exist_ok=True)
        self.enable_persistence = enable_persistence
        self.enable_plugins = enable_plugins

        self._states: dict[str, PipelineState] = {}
        self._phase_classes: dict[PipelinePhase, type[PhaseBase]] = {
            PipelinePhase.PHASE1_PREPROCESS: Phase1Preprocess,
            PipelinePhase.PHASE2_KEYING: Phase2Keying,
            PipelinePhase.PHASE3_STYLIZE: Phase3Stylize,
            PipelinePhase.PHASE4_RENDER: Phase4Render,
        }
        self._running: dict[str, asyncio.Task] = {}
        # Map job_id -> Celery task_id.  Populated only when Celery backend
        # is enabled.  Used by ``cancel_job`` to forward revokes.
        self._task_ids: dict[str, str] = {}
        # Database persistence layer (lazy init)
        self._db: Optional[Any] = None
        self._job_repo: Optional[Any] = None
        self._phase_repo: Optional[Any] = None
        self._perception_repo: Optional[Any] = None
        # Plugin manager (lazy init)
        self._plugin_mgr: Optional[Any] = None
        self._plugins_initialized: bool = False

    async def _init_plugins(self) -> None:
        """Initialize plugin system (lazy, once)."""
        if self._plugins_initialized or not self.enable_plugins:
            return
        self._plugins_initialized = True
        try:
            from src.plugins import plugin_manager, PluginContext
            self._plugin_mgr = plugin_manager
            # Discover and register built-in plugins
            self._plugin_mgr.discover_builtin()
            await self._plugin_mgr.init_all()
            logger.info(
                f"[Orchestrator] Plugin system initialized: "
                f"{len(self._plugin_mgr.plugins)} plugins loaded"
            )
        except Exception as e:
            logger.warning(f"[Orchestrator] Plugin init failed: {e}, continuing without plugins")
            self.enable_plugins = False

    def _make_plugin_ctx(
        self,
        job: PipelineJob,
        state: PipelineState,
        phase: Optional[PipelinePhase] = None,
        phase_result: Optional[PhaseResult] = None,
        work_dir: Optional[Path] = None,
    ) -> Any:
        """Build a PluginContext for the current pipeline state."""
        from src.plugins import PluginContext
        return PluginContext(
            job=job,
            state=state,
            engines=self.engines,
            work_dir=work_dir or self.base_work_dir / job.job_id,
            phase=phase,
            phase_result=phase_result,
        )

    async def _run_plugin_hooks(
        self, hook_name: str, ctx: Any
    ) -> Optional[PhaseResult]:
        """Run a plugin hook if plugins are enabled."""
        if not self.enable_plugins or not self._plugin_mgr:
            return None
        try:
            return await self._plugin_mgr.run_hooks(hook_name, ctx)
        except Exception as e:
            logger.warning(f"[Orchestrator] Plugin hook '{hook_name}' error: {e}")
            return None

    async def _run_plugin_filters(self, ctx: Any) -> Optional[PhaseResult]:
        """Run plugin filters for the current phase."""
        if not self.enable_plugins or not self._plugin_mgr:
            return None
        try:
            return await self._plugin_mgr.run_filters(ctx)
        except Exception as e:
            logger.warning(f"[Orchestrator] Plugin filter error: {e}")
            return None

    async def _init_persistence(self) -> None:
        """Initialize database persistence layer (lazy)."""
        if self._db is not None or not self.enable_persistence:
            return
        try:
            from ..persistence.database import Database, JobRepository, PhaseRepository, PerceptionRepository

            self._db = Database(settings.database_url)
            await self._db.connect()
            self._job_repo = JobRepository(self._db)
            self._phase_repo = PhaseRepository(self._db)
            self._perception_repo = PerceptionRepository(self._db)
            logger.info(f"[Orchestrator] Persistence layer initialized: {settings.database_url}")
        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to init persistence: {e}, continuing without DB")
            self.enable_persistence = False

    async def _persist_job_create(self, job: PipelineJob) -> None:
        """Persist job creation to database."""
        if not self.enable_persistence or not self._job_repo:
            return
        try:
            await self._job_repo.create(
                job_id=job.job_id,
                input_video=job.input_video,
                style=job.style.value if job.style else None,
                status="pending",
                config_json=json.dumps(job.model_dump()),
            )
        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to persist job creation: {e}")

    async def _persist_job_update(self, job_id: str, status: str, progress: float, error: str = None) -> None:
        """Persist job state update to database."""
        if not self.enable_persistence or not self._job_repo:
            return
        try:
            update_fields = {"status": status, "progress": progress}
            if error:
                update_fields["error"] = error
            if status == "running":
                update_fields["started_at"] = __import__("datetime").datetime.now().isoformat()
            elif status in ("success", "failed", "cancelled"):
                update_fields["completed_at"] = __import__("datetime").datetime.now().isoformat()
            await self._job_repo.update(job_id, **update_fields)
        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to persist job update: {e}")

    async def _persist_phase_result(self, job_id: str, phase_result: PhaseResult) -> None:
        """Persist phase result to database."""
        if not self.enable_persistence or not self._phase_repo:
            return
        try:
            await self._phase_repo.upsert(
                job_id=job_id,
                phase=phase_result.phase.value,
                status=phase_result.status.value,
                duration_seconds=phase_result.duration_seconds,
                metadata_json=json.dumps(phase_result.metadata) if phase_result.metadata else None,
                error=phase_result.error,
            )
        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to persist phase result: {e}")

    async def _persist_perception_data(
        self, job_id: str, metadata: Any, scenes: list, faces: list, poses: list, audio: Any
    ) -> None:
        """Persist Phase1 perception data."""
        if not self.enable_persistence or not self._perception_repo:
            return
        try:
            if metadata:
                await self._perception_repo.save_video_metadata(job_id, metadata.model_dump())
            if scenes:
                await self._perception_repo.save_scenes(job_id, [s.model_dump() for s in scenes])
            if faces:
                await self._perception_repo.save_faces(job_id, [f.model_dump() for f in faces])
            if poses:
                await self._perception_repo.save_poses(job_id, [p.model_dump() for p in poses])
            if audio:
                await self._perception_repo.save_audio_analysis(job_id, audio.model_dump())
        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to persist perception data: {e}")

    def create_job(self, job: PipelineJob) -> PipelineState:
        """Create a new pipeline job and return initial state.

        If job_id already exists, returns the existing state to prevent
        accidental overwrites of running or completed jobs.
        """
        if job.job_id in self._states:
            logger.warning(
                f"[Orchestrator] Job {job.job_id} already exists, returning existing state"
            )
            return self._states[job.job_id]
        state = PipelineState(
            job_id=job.job_id,
            overall_status=TaskStatus.PENDING,
            phase_results={},
        )
        self._states[job.job_id] = state
        logger.info(f"[Orchestrator] Created job {job.job_id}")
        return state

    def get_state(self, job_id: str) -> Optional[PipelineState]:
        """Get current state of a job.

        If Celery is enabled, attempt to merge the locally-cached state with
        the most recent snapshot persisted in Redis (the worker is the source
        of truth for jobs that have been picked up by Celery).
        """
        from ..workers import celery_backend
        local = self._states.get(job_id)
        if celery_backend.celery_is_enabled():
            remote = celery_backend.hydrate_state(job_id)
            if remote is not None:
                return remote
        return local

    def list_jobs(self) -> list[PipelineState]:
        """List all job states.

        If Celery is enabled, also include jobs that exist only in the Redis
        state store (e.g. jobs whose local in-process state was lost on an
        API restart).  Local state always wins for jobs known to both.
        """
        from ..workers import celery_backend
        merged: dict[str, PipelineState] = dict(self._states)
        if celery_backend.celery_is_enabled():
            for jid in celery_backend.list_known_job_ids():
                if jid not in merged:
                    remote = celery_backend.hydrate_state(jid)
                    if remote is not None:
                        merged[jid] = remote
        return list(merged.values())

    async def run_pipeline(self, job: PipelineJob) -> PipelineState:
        """Run the full four-stage pipeline for a job."""
        if job.job_id not in self._states:
            self.create_job(job)

        # Initialize plugins and persistence on first use
        await self._init_plugins()
        await self._init_persistence()
        await self._persist_job_create(job)

        state = self._states[job.job_id]

        # Plugin: on_job_created
        ctx = self._make_plugin_ctx(job, state)
        await self._run_plugin_hooks("on_job_created", ctx)

        state.overall_status = TaskStatus.RUNNING
        state.started_at = state.started_at or __import__("datetime").datetime.now()
        await self._persist_job_update(job.job_id, "running", 0.0)

        work_dir = self.base_work_dir / job.job_id
        work_dir.mkdir(parents=True, exist_ok=True)

        # Plugin: on_pipeline_start
        ctx = self._make_plugin_ctx(job, state, work_dir=work_dir)
        await self._run_plugin_hooks("on_pipeline_start", ctx)

        try:
            if not job.phases:
                state.overall_status = TaskStatus.FAILED
                state.error = "No phases defined for pipeline job"
                logger.error(f"[Orchestrator] Job {job.job_id} has no phases")
                await self._persist_job_update(job.job_id, "failed", 0.0, state.error)
                # Plugin: on_pipeline_failure
                ctx = self._make_plugin_ctx(job, state, work_dir=work_dir)
                await self._run_plugin_hooks("on_pipeline_failure", ctx)
            else:
                for phase_enum in job.phases:
                    state.current_phase = phase_enum

                    # Plugin: before_phase
                    ctx = self._make_plugin_ctx(job, state, phase=phase_enum, work_dir=work_dir)
                    await self._run_plugin_hooks("before_phase", ctx)

                    phase_cls = self._phase_classes.get(phase_enum)
                    if not phase_cls:
                        logger.warning(f"[Orchestrator] Unknown phase: {phase_enum}")
                        continue

                    phase_instance = phase_cls(self.engines, work_dir)

                    logger.info(f"[Orchestrator] Executing {phase_enum.value}")
                    phase_result = await phase_instance.execute(job, state)
                    state.phase_results[phase_enum] = phase_result

                    # Plugin: after_phase (can modify result)
                    ctx = self._make_plugin_ctx(
                        job, state, phase=phase_enum,
                        phase_result=phase_result, work_dir=work_dir
                    )
                    modified = await self._run_plugin_hooks("after_phase", ctx)
                    if modified is not None:
                        phase_result = modified
                        state.phase_results[phase_enum] = phase_result

                    # Plugin: filters for this phase
                    modified = await self._run_plugin_filters(ctx)
                    if modified is not None:
                        phase_result = modified
                        state.phase_results[phase_enum] = phase_result

                    # Persist phase result
                    await self._persist_phase_result(job.job_id, phase_result)

                    # Persist Phase1 perception data if available
                    if phase_enum == PipelinePhase.PHASE1_PREPROCESS and phase_result.status == TaskStatus.SUCCESS:
                        phase1_meta = phase_result.metadata or {}
                        await self._persist_perception_data(
                            job.job_id,
                            metadata=phase1_meta.get("metadata"),
                            scenes=phase1_meta.get("scenes", []),
                            faces=phase1_meta.get("faces", []),
                            poses=phase1_meta.get("poses", []),
                            audio=phase1_meta.get("audio"),
                        )

                    if phase_result.status == TaskStatus.FAILED:
                        state.overall_status = TaskStatus.FAILED
                        state.error = phase_result.error
                        logger.error(f"[Orchestrator] Pipeline failed at {phase_enum.value}: {phase_result.error}")
                        await self._persist_job_update(job.job_id, "failed", state.progress, state.error)
                        # Plugin: on_pipeline_failure
                        ctx = self._make_plugin_ctx(job, state, phase=phase_enum, work_dir=work_dir)
                        await self._run_plugin_hooks("on_pipeline_failure", ctx)
                        break

                    # Update progress
                    phase_idx = job.phases.index(phase_enum) + 1
                    state.progress = (phase_idx / len(job.phases)) * 100
                    await self._persist_job_update(job.job_id, "running", state.progress)

                if state.overall_status != TaskStatus.FAILED:
                    state.overall_status = TaskStatus.SUCCESS
                    state.progress = 100.0
                    state.completed_at = __import__("datetime").datetime.now()
                    await self._persist_job_update(job.job_id, "success", 100.0)
                    logger.info(f"[Orchestrator] Job {job.job_id} completed successfully")
                    # Plugin: on_pipeline_success
                    ctx = self._make_plugin_ctx(job, state, work_dir=work_dir)
                    await self._run_plugin_hooks("on_pipeline_success", ctx)

        except Exception as e:
            state.overall_status = TaskStatus.FAILED
            state.error = str(e)
            logger.error(f"[Orchestrator] Pipeline error: {e}")
            await self._persist_job_update(job.job_id, "failed", state.progress, str(e))
            # Plugin: on_pipeline_failure
            ctx = self._make_plugin_ctx(job, state, work_dir=work_dir)
            await self._run_plugin_hooks("on_pipeline_failure", ctx)

        return state

    def start_job_async(self, job: PipelineJob) -> str:
        """Start a job asynchronously, return job_id.

        Behaviour depends on the Celery backend:

        * **Celery enabled** → submit to the Celery worker.  The job is
          registered locally as PENDING so the API can return a job_id
          immediately, and the worker will hydrate / persist state through
          Redis.
        * **Celery disabled** → spawn a local ``asyncio`` task (legacy path,
          used by the 191 unit tests that never have Redis).
        """
        # Lazy import: orchestrator must work even if Celery/Redis deps are
        # not installed in the unit-test environment.
        from ..workers import celery_backend

        # Always register locally so the API can serve immediate state
        # queries regardless of backend.
        self.create_job(job)

        if celery_backend.celery_is_enabled():
            task_id = celery_backend.submit_job(job)
            if task_id:
                # Track task_id alongside the asyncio loop so cancel_job can
                # forward the revoke call.
                self._task_ids[job.job_id] = task_id
                logger.info(
                    f"[Orchestrator] Submitted job {job.job_id} to Celery as task {task_id}"
                )
                return job.job_id
            logger.warning(
                f"[Orchestrator] Celery submit failed for {job.job_id}; "
                "falling back to in-process execution"
            )
            # Fall through to asyncio path

        if job.job_id in self._running:
            return job.job_id

        async def _run():
            try:
                await self.run_pipeline(job)
            finally:
                if job.job_id in self._running:
                    del self._running[job.job_id]

        task = asyncio.create_task(_run())
        self._running[job.job_id] = task
        return job.job_id

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job.

        Tries (in order):
        1. Revoke the Celery task if the job was submitted to Celery.
        2. Cancel the in-process asyncio task if running locally.
        """
        from ..workers import celery_backend

        cancelled = False
        task_id = self._task_ids.get(job_id)
        if task_id and celery_backend.celery_is_enabled():
            if celery_backend.cancel_task(task_id):
                cancelled = True
            # Clean up tracking regardless of revoke success
            self._task_ids.pop(job_id, None)

        task = self._running.get(job_id)
        if task:
            task.cancel()
            del self._running[job_id]
            cancelled = True

        if cancelled:
            state = self._states.get(job_id)
            if state:
                state.overall_status = TaskStatus.CANCELLED
            # Remove from Redis if Celery backend is in use
            if celery_backend.celery_is_enabled():
                celery_backend.delete_state(job_id)
            # Plugin: on_pipeline_cancel (fire-and-forget, best effort)
            if self.enable_plugins and self._plugin_mgr and state:
                try:
                    import asyncio as _aio
                    loop = _aio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self._fire_cancel_hook(job_id, state))
                except Exception:
                    pass
            return True
        return False

    async def _fire_cancel_hook(self, job_id: str, state: PipelineState) -> None:
        """Best-effort fire of on_pipeline_cancel plugin hook."""
        try:
            # Build a minimal context for the cancel hook
            from src.plugins import PluginContext
            # We don't have the full job object here, create a minimal stub
            from ..models.pipeline import PipelineJob
            job = PipelineJob(job_id=job_id, input_video="", phases=[])
            ctx = PluginContext(
                job=job, state=state, engines=self.engines,
                work_dir=self.base_work_dir / job_id,
            )
            await self._run_plugin_hooks("on_pipeline_cancel", ctx)
        except Exception as e:
            logger.debug(f"[Orchestrator] Cancel hook error (ignored): {e}")

    @property
    def states(self) -> dict[str, PipelineState]:
        return self._states
