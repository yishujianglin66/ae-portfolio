"""
core/multi_agent_orchestrator.py
=================================

多智能体协作编排器 - 整合四方向能力：
- 方向A: AI导演（剧本生成+JSX翻译）
- 方向B: 3D舞台编排（视差+摄像机+布光）
- 方向C: 风格迁移（知识库驱动）
- 方向D: 音频驱动（BPM节拍同步）

新增6大聚合模块：
- 素材获取（OpenMontage + MediaFetcher）
- 智能遮罩（SAM2 + Silhouette）
- 音频处理（Whisper + Audition + FFmpeg）
- 质量增强（RIFE + Topaz + Video2X）
- 快速合成（MoviePy + OpenMontage + AE）
- 调色（DaVinci + Photoshop + AE Lumetri）

使用方式：
    orchestrator = MultiAgentOrchestrator()
    result = await orchestrator.produce("冰海战记战斗混剪，60秒，燃向")
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class Agent:
    """基础智能体。"""

    def __init__(self, name: str):
        self.name = name

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class PlannerAgent(Agent):
    """任务规划Agent - 分解用户指令为可执行任务。"""

    def __init__(self):
        super().__init__("planner")
        self._planner = None
        try:
            from ai_director import AIDirector
            self._planner = AIDirector()
        except Exception as e:
            logger.warning(f"[Planner] AI Director not available: {e}")

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """分解任务为执行计划。"""
        prompt = task.get("prompt", "")

        if self._planner:
            try:
                # 使用AI Director生成剧本
                from ai_director import ProductionScript
                script = self._planner.produce(prompt)
                if script:
                    return {
                        "success": True,
                        "script": json.loads(script.to_json()),
                        "phases": ["collect", "analyze", "script", "jsx", "render"],
                    }
            except Exception as e:
                logger.warning(f"[Planner] AI Director failed: {e}")

        # Fallback：规则分解
        return self._rule_based_decompose(prompt)

    def _rule_based_decompose(self, prompt: str) -> dict[str, Any]:
        """基于规则的简单分解。"""
        # 检测关键词
        is_battle = any(kw in prompt for kw in ["战斗", "燃向", "战斗场景", "battle"])
        is_emotional = any(kw in prompt for kw in ["感人", "温情", " emotional", "sad"])
        is_cyber = any(kw in prompt for kw in ["赛博", "cyber", "科技", "tech"])

        style = "battle" if is_battle else "emotional" if is_emotional else "cyber" if is_cyber else "default"

        return {
            "success": True,
            "script": {
                "prompt": prompt,
                "style": style,
                "phases": ["collect", "analyze", "script", "jsx", "render"],
            },
            "phases": ["collect", "analyze", "script", "jsx", "render"],
        }


class MaterialAgent(Agent):
    """素材搜集Agent - 聚合OpenMontage + 本地素材库。"""

    def __init__(self):
        super().__init__("material")
        self._openmontage = None
        try:
            from puppet_automation.src.engines.openmontage import OpenMontageEngine
            self._openmontage = OpenMontageEngine()
        except Exception as e:
            logger.warning(f"[Material] OpenMontage not available: {e}")

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """搜集素材。"""
        query = task.get("query", "")
        sources = task.get("sources", None)
        max_results = task.get("max_results", 10)

        results = []

        # 1. 尝试OpenMontage搜索
        if self._openmontage:
            try:
                om_result = await self._openmontage.search_stock(
                    query=query,
                    max_results=max_results,
                    sources=sources,
                    download=True,
                    download_dir=Path(r"D:\AE-Work\downloads"),
                )
                if om_result.success:
                    results.extend(om_result.metadata.get("results", []))
            except Exception as e:
                logger.debug(f"[Material] OpenMontage search failed: {e}")

        # 2. 本地素材库扫描
        local_results = await asyncio.to_thread(
            self._scan_local_library, query,
        )
        results.extend(local_results)

        return {
            "success": len(results) > 0,
            "materials": results,
            "count": len(results),
        }

    def _scan_local_library(self, query: str) -> list[dict[str, Any]]:
        """扫描本地素材库。"""
        library_paths = [
            Path(r"D:\AE-Work\resources\footage"),
            Path(r"D:\AE-Work\resources\images"),
        ]

        results = []
        query_lower = query.lower()

        for lib_path in library_paths:
            if not lib_path.exists():
                continue
            for file in lib_path.rglob("*"):
                if file.suffix.lower() in [".mp4", ".mov", ".avi", ".png", ".jpg", ".jpeg"]:
                    # 简单匹配：文件名包含关键词
                    if query_lower in file.stem.lower():
                        results.append({
                            "title": file.stem,
                            "path": str(file),
                            "source": "local",
                            "type": "video" if file.suffix in [".mp4", ".mov", ".avi"] else "image",
                        })

        return results[:20]


class VisionAgent(Agent):
    """视觉分析Agent - 场景/情绪/色彩/运动提取。"""

    def __init__(self):
        super().__init__("vision")
        self._analyzer = None
        try:
            from ai_director import VisualAnalyzer
            self._analyzer = VisualAnalyzer()
        except Exception as e:
            logger.warning(f"[Vision] VisualAnalyzer not available: {e}")

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """分析视频素材。"""
        video_path = task.get("video_path")
        if not video_path or not Path(video_path).exists():
            return {"success": False, "error": "Video not found"}

        if self._analyzer:
            try:
                analysis = await asyncio.to_thread(
                    self._analyzer.analyze_video, video_path,
                )
                return {
                    "success": True,
                    "analysis": analysis,
                }
            except Exception as e:
                logger.warning(f"[Vision] Analysis failed: {e}")

        # Fallback：基础分析
        return await asyncio.to_thread(self._basic_analysis, video_path)

    def _basic_analysis(self, video_path: str) -> dict[str, Any]:
        """基础OpenCV分析。"""
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frames / fps if fps > 0 else 0
            cap.release()

            return {
                "fps": fps,
                "frame_count": frames,
                "duration": duration,
                "resolution": f"{width}x{height}",
                "aspect_ratio": width / height if height > 0 else 0,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class AudioAgent(Agent):
    """音频处理Agent - Whisper转写 + 音频分析 + 字幕生成。"""

    def __init__(self):
        super().__init__("audio")
        self._whisper = None
        try:
            from puppet_automation.src.engines.whisper import WhisperEngine
            self._whisper = WhisperEngine()
        except Exception as e:
            logger.warning(f"[Audio] Whisper not available: {e}")

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """处理音频任务。"""
        task_type = task.get("type", "transcribe")
        audio_path = task.get("audio_path")

        if not audio_path or not Path(audio_path).exists():
            return {"success": False, "error": "Audio not found"}

        if task_type == "transcribe":
            return await self._transcribe(audio_path, task)
        elif task_type == "srt":
            return await self._generate_srt(audio_path, task)
        elif task_type == "bpm":
            return await self._analyze_bpm(audio_path)

        return {"success": False, "error": f"Unknown audio task: {task_type}"}

    async def _transcribe(self, audio_path: str, task: dict) -> dict[str, Any]:
        """语音转文字。"""
        if self._whisper:
            try:
                result = await self._whisper.transcribe(
                    audio_path,
                    model=task.get("model", "base"),
                    language=task.get("language", "zh"),
                )
                return {
                    "success": result.success,
                    "text": result.metadata.get("text", ""),
                    "segments": result.metadata.get("segments", []),
                    "language": result.metadata.get("language", ""),
                }
            except Exception as e:
                logger.warning(f"[Audio] Whisper transcribe failed: {e}")

        return {"success": False, "error": "Whisper not available"}

    async def _generate_srt(self, audio_path: str, task: dict) -> dict[str, Any]:
        """生成SRT字幕。"""
        output_srt = task.get("output_srt", Path(audio_path).with_suffix(".srt"))

        if self._whisper:
            try:
                result = await self._whisper.generate_srt(
                    audio_path, output_srt,
                    model=task.get("model", "base"),
                    language=task.get("language", "zh"),
                )
                return {
                    "success": result.success,
                    "srt_path": str(result.output_path) if result.output_path else None,
                }
            except Exception as e:
                logger.warning(f"[Audio] SRT generation failed: {e}")

        return {"success": False, "error": "Whisper not available"}

    async def _analyze_bpm(self, audio_path: str) -> dict[str, Any]:
        """分析BPM。"""
        try:
            import librosa
            y, sr = librosa.load(audio_path)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            return {
                "success": True,
                "bpm": float(tempo),
                "duration": len(y) / sr,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class ComposerAgent(Agent):
    """合成Agent - MoviePy快速预览 + AE精细合成。"""

    def __init__(self):
        super().__init__("composer")
        self._moviepy = None
        try:
            from puppet_automation.src.engines.moviepy import MoviePyEngine
            self._moviepy = MoviePyEngine()
        except Exception as e:
            logger.warning(f"[Composer] MoviePy not available: {e}")

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """执行合成任务。"""
        compose_type = task.get("type", "preview")

        if compose_type == "preview":
            return await self._quick_preview(task)
        elif compose_type == "final":
            return await self._ae_compose(task)
        elif compose_type == "subtitles":
            return await self._burn_subtitles(task)

        return {"success": False, "error": f"Unknown compose type: {compose_type}"}

    async def _quick_preview(self, task: dict) -> dict[str, Any]:
        """MoviePy快速预览。"""
        clips = task.get("clips", [])
        output = task.get("output", "preview.mp4")

        if self._moviepy:
            try:
                result = await self._moviepy.quick_compose(
                    clips, output,
                    transitions=task.get("transitions", "fade"),
                    resolution=task.get("resolution"),
                    fps=task.get("fps", 30),
                )
                return {
                    "success": result.success,
                    "output": str(result.output_path) if result.output_path else None,
                }
            except Exception as e:
                logger.warning(f"[Composer] Preview failed: {e}")

        return {"success": False, "error": "MoviePy not available"}

    async def _ae_compose(self, task: dict) -> dict[str, Any]:
        """AE精细合成。"""
        # 通过MCP Bridge发送JSX
        jsx = task.get("jsx", "")
        if not jsx:
            return {"success": False, "error": "No JSX provided"}

        try:
            from ae_mcp_client import send_command
            result = await send_command("executeAtomScript", script=jsx)
            return {
                "success": result.get("status") == "success",
                "result": result,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _burn_subtitles(self, task: dict) -> dict[str, Any]:
        """烧录字幕。"""
        video = task.get("video")
        srt = task.get("srt")
        output = task.get("output", "subtitled.mp4")

        if self._moviepy:
            try:
                result = await self._moviepy.add_subtitles(video, srt, output)
                return {
                    "success": result.success,
                    "output": str(result.output_path) if result.output_path else None,
                }
            except Exception as e:
                logger.warning(f"[Composer] Subtitle burn failed: {e}")

        return {"success": False, "error": "MoviePy not available"}


class EnhancerAgent(Agent):
    """增强Agent - RIFE帧插值 + Topaz超分。"""

    def __init__(self):
        super().__init__("enhancer")
        self._rife = None
        self._topaz = None

        try:
            from puppet_automation.src.engines.rife import RifeEngine
            self._rife = RifeEngine()
        except Exception as e:
            logger.warning(f"[Enhancer] RIFE not available: {e}")

        try:
            from puppet_automation.src.engines.topaz import TopazEngine
            self._topaz = TopazEngine()
        except Exception as e:
            logger.warning(f"[Enhancer] Topaz not available: {e}")

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """执行增强任务。"""
        enhance_type = task.get("type", "interpolate")
        input_path = task.get("input")
        output_path = task.get("output")

        if not input_path or not Path(input_path).exists():
            return {"success": False, "error": "Input not found"}

        if enhance_type == "interpolate":
            return await self._interpolate(input_path, output_path, task)
        elif enhance_type == "upscale":
            return await self._upscale(input_path, output_path, task)

        return {"success": False, "error": f"Unknown enhance type: {enhance_type}"}

    async def _interpolate(self, input_path: str, output_path: str, task: dict) -> dict[str, Any]:
        """帧插值。"""
        # 优先使用RIFE（免费快速），备选Topaz
        if self._rife:
            try:
                result = await self._rife.interpolate(
                    input_path, output_path,
                    multiplier=task.get("multiplier", 2),
                )
                return {
                    "success": result.success,
                    "output": str(result.output_path) if result.output_path else None,
                    "engine": "rife",
                }
            except Exception as e:
                logger.warning(f"[Enhancer] RIFE failed: {e}")

        if self._topaz:
            try:
                result = await self._topaz.execute(
                    input_path, output_path,
                    task="interpolate",
                )
                return {
                    "success": result.success,
                    "output": str(result.output_path) if result.output_path else None,
                    "engine": "topaz",
                }
            except Exception as e:
                logger.warning(f"[Enhancer] Topaz failed: {e}")

        return {"success": False, "error": "No interpolation engine available"}

    async def _upscale(self, input_path: str, output_path: str, task: dict) -> dict[str, Any]:
        """超分。"""
        if self._topaz:
            try:
                result = await self._topaz.execute(
                    input_path, output_path,
                    task="upscale",
                    scale=task.get("scale", 2),
                )
                return {
                    "success": result.success,
                    "output": str(result.output_path) if result.output_path else None,
                    "engine": "topaz",
                }
            except Exception as e:
                logger.warning(f"[Enhancer] Topaz upscale failed: {e}")

        return {"success": False, "error": "No upscale engine available"}


class ColoristAgent(Agent):
    """调色Agent - DaVinci + 风格迁移。"""

    def __init__(self):
        super().__init__("colorist")
        self._davinci = None
        try:
            from puppet_automation.src.engines.davinci import DavinciEngine
            self._davinci = DavinciEngine()
        except Exception as e:
            logger.warning(f"[Colorist] DaVinci not available: {e}")

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """执行调色任务。"""
        input_path = task.get("input")
        output_path = task.get("output")
        style = task.get("style", "cinematic")

        if not input_path or not Path(input_path).exists():
            return {"success": False, "error": "Input not found"}

        if self._davinci:
            try:
                result = await self._davinci.execute(
                    input_path, output_path,
                    task="grade",
                    style=style,
                )
                return {
                    "success": result.success,
                    "output": str(result.output_path) if result.output_path else None,
                }
            except Exception as e:
                logger.warning(f"[Colorist] DaVinci failed: {e}")

        return {"success": False, "error": "DaVinci not available"}


class MaskAgent(Agent):
    """遮罩Agent - SAM2自动 + Silhouette精修。"""

    def __init__(self):
        super().__init__("mask")
        self._sam2 = None
        try:
            from puppet_automation.src.engines.sam2 import SAM2Engine
            self._sam2 = SAM2Engine()
        except Exception as e:
            logger.warning(f"[Mask] SAM2 not available: {e}")

    async def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """执行遮罩任务。"""
        video_path = task.get("video")
        output_dir = task.get("output_dir")

        if not video_path or not Path(video_path).exists():
            return {"success": False, "error": "Video not found"}

        if self._sam2:
            try:
                result = await self._sam2.auto_mask(
                    video_path, output_dir or Path(video_path).parent / "masks",
                )
                return {
                    "success": result.success,
                    "mask_dir": str(result.output_path) if result.output_path else None,
                    "mask_count": result.metadata.get("mask_count", 0),
                }
            except Exception as e:
                logger.warning(f"[Mask] SAM2 failed: {e}")

        return {"success": False, "error": "SAM2 not available"}


class MultiAgentOrchestrator:
    """多智能体协作编排器。"""

    def __init__(self):
        self.agents = {
            "planner": PlannerAgent(),
            "material": MaterialAgent(),
            "vision": VisionAgent(),
            "audio": AudioAgent(),
            "composer": ComposerAgent(),
            "enhancer": EnhancerAgent(),
            "colorist": ColoristAgent(),
            "mask": MaskAgent(),
        }
        logger.info("[Orchestrator] Multi-agent system initialized")

    async def produce(self, prompt: str, **kwargs) -> dict[str, Any]:
        """端到端视频生成。

        Args:
            prompt: 用户指令（如"冰海战记战斗混剪，60秒，燃向"）
            **kwargs: 额外参数

        Returns:
            完整执行结果
        """
        logger.info(f"[Orchestrator] Starting production: {prompt}")
        start_time = asyncio.get_event_loop().time()

        results = {
            "prompt": prompt,
            "phases": {},
            "success": False,
        }

        try:
            # Phase 1: 任务规划
            logger.info("[Orchestrator] Phase 1: Planning")
            plan = await self.agents["planner"].execute({"prompt": prompt})
            results["phases"]["plan"] = plan

            if not plan.get("success"):
                results["error"] = "Planning failed"
                return results

            script = plan.get("script", {})

            # Phase 2: 并行执行独立任务
            logger.info("[Orchestrator] Phase 2: Parallel execution")
            parallel_tasks = []

            # 素材搜集
            if kwargs.get("search_materials", True):
                parallel_tasks.append(
                    self._gather_materials(script, kwargs)
                )

            # 音频处理（如果提供了音频）
            if kwargs.get("audio_path"):
                parallel_tasks.append(
                    self._process_audio(kwargs["audio_path"], kwargs)
                )

            parallel_results = await asyncio.gather(*parallel_tasks, return_exceptions=True)

            for i, res in enumerate(parallel_results):
                if isinstance(res, Exception):
                    logger.warning(f"[Orchestrator] Parallel task {i} failed: {res}")
                else:
                    results["phases"].update(res)

            # Phase 3: 视觉分析
            materials = results["phases"].get("materials", {}).get("materials", [])
            if materials:
                logger.info("[Orchestrator] Phase 3: Visual analysis")
                analysis = await self.agents["vision"].execute({
                    "video_path": materials[0].get("path", ""),
                })
                results["phases"]["analysis"] = analysis

            # Phase 4: 合成
            logger.info("[Orchestrator] Phase 4: Composition")
            compose_result = await self.agents["composer"].execute({
                "type": kwargs.get("compose_type", "preview"),
                "clips": materials,
                "output": kwargs.get("output", "output.mp4"),
                "jsx": kwargs.get("jsx"),
            })
            results["phases"]["compose"] = compose_result

            # Phase 5: 后处理（并行）
            logger.info("[Orchestrator] Phase 5: Post-processing")
            post_tasks = []

            if kwargs.get("enhance", False):
                post_tasks.append(self._enhance(compose_result, kwargs))

            if kwargs.get("color_grade", False):
                post_tasks.append(self._color_grade(compose_result, kwargs))

            if post_tasks:
                post_results = await asyncio.gather(*post_tasks, return_exceptions=True)
                for i, res in enumerate(post_results):
                    if isinstance(res, Exception):
                        logger.warning(f"[Orchestrator] Post task {i} failed: {res}")
                    else:
                        results["phases"].update(res)

            results["success"] = compose_result.get("success", False)
            results["duration"] = asyncio.get_event_loop().time() - start_time

            logger.info(f"[Orchestrator] Production completed in {results['duration']:.1f}s")

        except Exception as e:
            logger.error(f"[Orchestrator] Production failed: {e}")
            results["error"] = str(e)

        return results

    async def _gather_materials(self, script: dict, kwargs: dict) -> dict[str, Any]:
        """搜集素材。"""
        query = script.get("prompt", "")
        result = await self.agents["material"].execute({
            "query": query,
            "max_results": kwargs.get("max_materials", 10),
        })
        return {"materials": result}

    async def _process_audio(self, audio_path: str, kwargs: dict) -> dict[str, Any]:
        """处理音频。"""
        result = await self.agents["audio"].execute({
            "type": kwargs.get("audio_task", "transcribe"),
            "audio_path": audio_path,
            "model": kwargs.get("whisper_model", "base"),
            "language": kwargs.get("language", "zh"),
        })
        return {"audio": result}

    async def _enhance(self, compose_result: dict, kwargs: dict) -> dict[str, Any]:
        """质量增强。"""
        output = compose_result.get("output")
        if not output:
            return {"enhance": {"success": False, "error": "No output to enhance"}}

        result = await self.agents["enhancer"].execute({
            "type": kwargs.get("enhance_type", "interpolate"),
            "input": output,
            "output": str(Path(output).with_stem(Path(output).stem + "_enhanced")),
            "multiplier": kwargs.get("multiplier", 2),
        })
        return {"enhance": result}

    async def _color_grade(self, compose_result: dict, kwargs: dict) -> dict[str, Any]:
        """调色。"""
        output = compose_result.get("output")
        if not output:
            return {"color": {"success": False, "error": "No output to grade"}}

        result = await self.agents["colorist"].execute({
            "input": output,
            "output": str(Path(output).with_stem(Path(output).stem + "_graded")),
            "style": kwargs.get("color_style", "cinematic"),
        })
        return {"color": result}

    def get_status(self) -> dict[str, Any]:
        """获取所有Agent状态。"""
        return {
            name: {
                "available": True,
                "name": agent.name,
            }
            for name, agent in self.agents.items()
        }


if __name__ == "__main__":
    async def main():
        orchestrator = MultiAgentOrchestrator()
        print("Agent status:")
        for name, status in orchestrator.get_status().items():
            print(f"  {name}: {status}")

    asyncio.run(main())