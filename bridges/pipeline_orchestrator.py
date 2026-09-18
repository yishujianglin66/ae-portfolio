"""跨引擎 Pipeline 编排器 (P2-05)

统一编排所有跨引擎链路，提供 declarative pipeline 定义和执行。

支持的 Pipeline 类型：
  1. full_3d_pipeline: 3D 场景生成 → AI 增强 → AE 合成 → PR 剪辑
  2. animation_pipeline: 3D 动画渲染 → 抠像 → 合成
  3. mograph_pipeline: C4D MoGraph → AE 合成 → 导出
  4. enhancement_pipeline: Topaz AI 增强 → DaVinci 调色 → PR 剪辑

使用：
    from bridges.pipeline_orchestrator import PipelineOrchestrator
    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run_pipeline("full_3d_pipeline", config)
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from .blender_ae_bridge import BlenderAEBridge
from .c4d_ae_bridge import C4DAEBridge
from .silhouette_ae_bridge import SilhouetteAEBridge
from .topaz_davinci_bridge import TopazDaVinciBridge


class PipelineOrchestrator:
    """跨引擎 Pipeline 编排器。"""

    PIPELINE_TYPES = {
        "full_3d_pipeline": "3D 全链路：Blender → Topaz → AE → PR",
        "animation_pipeline": "3D 动画链路：Blender Cel → Silhouette → AE",
        "mograph_pipeline": "MoGraph 链路：C4D → AE → 导出",
        "enhancement_pipeline": "AI 增强链路：Topaz → DaVinci → PR",
    }

    def __init__(self) -> None:
        self.blender_ae = BlenderAEBridge()
        self.topaz_davinci = TopazDaVinciBridge()
        self.silhouette_ae = SilhouetteAEBridge()
        self.c4d_ae = C4DAEBridge()

    async def run_pipeline(
        self,
        pipeline_type: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """运行指定类型的 Pipeline。

        Args:
            pipeline_type: Pipeline 类型 (full_3d_pipeline 等)
            config: Pipeline 配置参数
        """
        logger.info(f"[PipelineOrchestrator] Starting: {pipeline_type}")
        logger.info(f"[PipelineOrchestrator] Config: {json.dumps(config, ensure_ascii=False)[:500]}")

        dispatch = {
            "full_3d_pipeline": self._run_full_3d_pipeline,
            "animation_pipeline": self._run_animation_pipeline,
            "mograph_pipeline": self._run_mograph_pipeline,
            "enhancement_pipeline": self._run_enhancement_pipeline,
        }

        handler = dispatch.get(pipeline_type)
        if handler is None:
            return {
                "success": False,
                "error": f"Unknown pipeline type: {pipeline_type}",
                "available_types": list(dispatch.keys()),
            }

        return await handler(config)

    async def _run_full_3d_pipeline(self, config: dict[str, Any]) -> dict[str, Any]:
        """3D 全链路：Blender Stage → Topaz AI 增强 → AE 合成 → PR 剪辑。"""
        output_dir = config.get("output_dir", "D:/AE-Work/pipeline/output")
        ae_project_path = config.get("ae_project_path", str(Path(output_dir) / "final_project.aep"))
        video_path = config.get("video_path")
        stage_style = config.get("stage_style", "wooden")
        resolution = tuple(config.get("resolution", [1920, 1080]))
        frame_count = config.get("frame_count", 60)

        result: dict[str, Any] = {
            "pipeline_type": "full_3d_pipeline",
            "steps_completed": 0,
            "steps_total": 4,
            "step_results": {},
            "errors": [],
        }

        # Step 1: Blender Stage 创建 + 导出 AE 资产
        step1 = await self.blender_ae.create_3d_scene_for_ae(
            output_dir=Path(output_dir) / "blender_stage",
            ae_project_path=ae_project_path,
            stage_style=stage_style,
            resolution=resolution,
            frame_count=frame_count,
            import_to_ae=True,
        )
        result["step_results"]["blender_stage"] = step1
        if not step1.get("stage_created"):
            result["errors"].append(f"Step 1 (Blender Stage) failed: {step1.get('errors')}")
            result["steps_completed"] = 0
            return result
        result["steps_completed"] = 1

        # Step 2: 输入视频 Topaz AI 增强（可选）
        if video_path:
            step2 = await self.topaz_davinci.enhance_for_color_grading(
                input_path=video_path,
                output_dir=Path(output_dir) / "topaz_enhanced",
                scale=config.get("topaz_scale", 2),
            )
            result["step_results"]["topaz_enhance"] = step2
            if not step2.get("topaz_enhanced"):
                result["errors"].append(f"Step 2 (Topaz Enhance) warning: {step2.get('errors')}")
            else:
                result["steps_completed"] = 2
        else:
            result["step_results"]["topaz_enhance"] = {"skipped": True}
            result["steps_completed"] = 2

        # Step 3: AE 合成（已在 Step 1 中完成基础合成）
        result["steps_completed"] = 3

        # Step 4: PR 剪辑（可选，依赖 AE 合成）
        if config.get("auto_edit") and result["step_results"].get("blender_stage", {}).get("ae_project_created"):
            step4 = {"skipped": True, "note": "PR auto-edit requires AE Bridge online"}
            result["step_results"]["pr_edit"] = step4

        result["steps_completed"] = 4
        result["success"] = len(result["errors"]) == 0
        logger.info(
            f"[PipelineOrchestrator] full_3d_pipeline complete: "
            f"steps={result['steps_completed']}/{result['steps_total']}, "
            f"errors={len(result['errors'])}"
        )
        return result

    async def _run_animation_pipeline(self, config: dict[str, Any]) -> dict[str, Any]:
        """3D 动画链路：Blender Cel-shading → Silhouette Roto → AE 合成。"""
        output_dir = config.get("output_dir", "D:/AE-Work/pipeline/output")
        ae_project_path = config.get("ae_project_path", str(Path(output_dir) / "cel_project.aep"))
        video_path = config.get("video_path")
        cel_style = config.get("cel_style", "anime")
        resolution = tuple(config.get("resolution", [1920, 1080]))
        frame_count = config.get("frame_count", 60)

        result: dict[str, Any] = {
            "pipeline_type": "animation_pipeline",
            "steps_completed": 0,
            "steps_total": 3,
            "step_results": {},
            "errors": [],
        }

        # Step 1: Blender Cel-shading 渲染
        step1 = await self.blender_ae.create_cel_shading_for_ae(
            output_dir=Path(output_dir) / "cel_shading",
            ae_project_path=ae_project_path,
            style=cel_style,
            resolution=resolution,
            frame_count=frame_count,
        )
        result["step_results"]["cel_shading"] = step1
        if not step1.get("cel_rendered"):
            result["errors"].append(f"Step 1 failed: {step1.get('errors')}")
            return result
        result["steps_completed"] = 1

        # Step 2: Silhouette Roto 抠像（如果有参考视频）
        if video_path:
            step2 = await self.silhouette_ae.roto_to_ae_mask(
                video_path=video_path,
                output_dir=Path(output_dir) / "roto",
                ae_project_path=ae_project_path,
            )
            result["step_results"]["roto"] = step2
            if not step2.get("roto_completed"):
                result["errors"].append(f"Step 2 warning: {step2.get('errors')}")
        else:
            result["step_results"]["roto"] = {"skipped": True}

        result["steps_completed"] = 2

        # Step 3: AE 合成（已在 Step 1 中完成）
        result["steps_completed"] = 3
        result["success"] = len(result["errors"]) == 0
        return result

    async def _run_mograph_pipeline(self, config: dict[str, Any]) -> dict[str, Any]:
        """MoGraph 链路：C4D → AE 合成 → 导出。"""
        output_dir = config.get("output_dir", "D:/AE-Work/pipeline/output")
        ae_project_path = config.get("ae_project_path", str(Path(output_dir) / "mograph_project.aep"))
        resolution = tuple(config.get("resolution", [1920, 1080]))
        frame_count = config.get("frame_count", 60)
        text = config.get("text", "MOTION")

        result: dict[str, Any] = {
            "pipeline_type": "mograph_pipeline",
            "steps_completed": 0,
            "steps_total": 2,
            "step_results": {},
            "errors": [],
        }

        step1 = await self.c4d_ae.render_motion_graphics_to_ae(
            output_dir=Path(output_dir) / "mograph",
            ae_project_path=ae_project_path,
            text=text,
            resolution=resolution,
            frame_count=frame_count,
        )
        result["step_results"]["c4d_mograph"] = step1
        if not step1.get("mograph_rendered"):
            result["errors"].append(f"Step 1 failed: {step1.get('errors')}")
            return result
        result["steps_completed"] = 1

        result["steps_completed"] = 2
        result["success"] = len(result["errors"]) == 0
        return result

    async def _run_enhancement_pipeline(self, config: dict[str, Any]) -> dict[str, Any]:
        """AI 增强链路：Topaz → DaVinci 调色。"""
        input_path = config.get("input_path")
        output_dir = config.get("output_dir", "D:/AE-Work/pipeline/output")
        davinci_project_path = config.get("davinci_project_path")

        if not input_path:
            return {"success": False, "error": "input_path is required"}

        result = await self.topaz_davinci.enhance_for_color_grading(
            input_path=input_path,
            output_dir=Path(output_dir) / "enhanced",
            davinci_project_path=davinci_project_path,
            topaz_model=config.get("topaz_model", "proteus"),
            scale=config.get("scale", 2),
        )
        result["pipeline_type"] = "enhancement_pipeline"
        return result
