"""Silhouette → After Effects 抠像链路桥接器 (P2-03)

核心链路：
  Silhouette (Roto/Tracker) → Shape/Mask 数据 → AE Mask 路径图层

支持场景：
  1. Silhouette Roto 抠像 → 导出 Shape 数据 → AE 创建 Mask
  2. Silhouette Tracker 追踪 → 导出追踪点 → AE 摄像机/图层追踪
  3. Silhouette Keying → 合成前景/背景分离
"""
from __future__ import annotations

import asyncio
import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


def _ensure_puppet_automation_shim() -> None:
    """注册 puppet_automation 包别名 (实际目录是 puppet-automation 含连字符)。"""
    if "puppet_automation" in sys.modules and "puppet_automation.src" in sys.modules:
        return
    _project_root = Path(__file__).resolve().parent.parent
    _pa_dir = _project_root / "puppet-automation"
    _src_dir = _pa_dir / "src"
    if "puppet_automation" not in sys.modules:
        _pkg = importlib.util.module_from_spec(
            importlib.machinery.ModuleSpec("puppet_automation", loader=None, is_package=True)
        )
        _pkg.__path__ = [str(_pa_dir)]
        sys.modules["puppet_automation"] = _pkg
    if "puppet_automation.src" not in sys.modules:
        _src_init = _src_dir / "__init__.py"
        if _src_init.exists():
            _spec = importlib.util.spec_from_file_location(
                "puppet_automation.src", _src_init,
                submodule_search_locations=[str(_src_dir)]
            )
        else:
            _spec = importlib.machinery.ModuleSpec(
                "puppet_automation.src", loader=None, is_package=True
            )
            _spec.submodule_search_locations = [str(_src_dir)]
        _src_pkg = importlib.util.module_from_spec(_spec)
        sys.modules["puppet_automation.src"] = _src_pkg
        if _spec.loader is not None:
            _spec.loader.exec_module(_src_pkg)


class SilhouetteAEBridge:
    """Silhouette → AE 抠像桥接器。"""

    def __init__(self) -> None:
        self._silhouette_engine = None
        self._ae_engine = None

    @property
    def silhouette_engine(self):
        if self._silhouette_engine is None:
            _ensure_puppet_automation_shim()
            from puppet_automation.src.engines.silhouette import SilhouetteEngine
            self._silhouette_engine = SilhouetteEngine()
        return self._silhouette_engine

    @property
    def ae_engine(self):
        if self._ae_engine is None:
            _ensure_puppet_automation_shim()
            from puppet_automation.src.engines.ae import AEEngine
            self._ae_engine = AEEngine()
        return self._ae_engine

    async def roto_to_ae_mask(
        self,
        video_path: Path | str,
        output_dir: Path | str,
        ae_project_path: Path | str,
        comp_name: str = "Roto Comp",
        roto_mode: str = "foreground",
        frame_count: int = 100,
        frame_rate: float = 25.0,
    ) -> Dict[str, Any]:
        """Silhouette Roto 抠像 → AE Mask 链路。

        Args:
            video_path: 输入视频路径
            output_dir: 输出目录（mask 数据 + 中间文件）
            ae_project_path: AE 工程路径
            comp_name: AE 合成名称
            roto_mode: 抠像模式 (foreground/background)
            frame_count: 处理帧数
            frame_rate: 帧率
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        ae_project_path = Path(ae_project_path)

        result: Dict[str, Any] = {
            "roto_completed": False,
            "mask_data_exported": False,
            "ae_project_created": False,
            "mask_applied_to_ae": False,
            "errors": [],
        }

        # Step 1: Silhouette Roto 抠像
        if self.silhouette_engine.available:
            logger.info(f"[SilhouetteAE] Step 1: Silhouette Roto (mode={roto_mode})")
            roto_result = await self.silhouette_engine.create_roto_session(
                video_path=video_path,
                output_dir=output_dir,
                roto_mode=roto_mode,
                frame_count=frame_count,
                frame_rate=frame_rate,
            )

            if roto_result.success:
                result["roto_completed"] = True
                result["roto_output"] = str(output_dir)
                result["roto_metadata"] = roto_result.metadata

                # 导出 mask 数据
                mask_data_path = output_dir / "roto_shapes.json"
                export_result = await self.silhouette_engine.export_shapes(
                    output_path=mask_data_path,
                )
                if export_result.success and mask_data_path.exists():
                    result["mask_data_exported"] = True
                    result["mask_data_path"] = str(mask_data_path)
                else:
                    result["errors"].append(f"Shape export failed: {export_result.error}")
            else:
                result["errors"].append(f"Roto failed: {roto_result.error}")
        else:
            result["errors"].append("Silhouette not available — manual roto required")

        # Step 2: AE 创建合成 + 导入素材
        if self.ae_engine.available and video_path.exists():
            ae_result = await self.ae_engine.create_project(
                project_path=ae_project_path,
                comp_name=comp_name,
                duration=frame_count / frame_rate,
                fps=frame_rate,
            )
            if ae_result.success:
                result["ae_project_created"] = True

                # 导入原视频作为背景层
                import_result = await self.ae_engine.import_footage(
                    footage_path=video_path,
                    comp_name=comp_name,
                    project_path=ae_project_path,
                )
                if import_result.success:
                    result["video_layer_index"] = import_result.metadata.get("layerIndex")
                else:
                    result["errors"].append(f"Video import failed: {import_result.error}")
        elif not self.ae_engine.available:
            result["errors"].append("AE not available — mask data ready for manual import")

        return result

    async def track_to_ae(
        self,
        video_path: Path | str,
        output_dir: Path | str,
        ae_project_path: Path | str,
        comp_name: str = "Tracker Comp",
        tracker_type: str = "planar",
        track_points: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Silhouette Tracker → AE 追踪链路。"""
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result: Dict[str, Any] = {
            "tracking_completed": False,
            "track_data_exported": False,
            "ae_project_created": False,
            "errors": [],
        }

        if self.silhouette_engine.available:
            logger.info(f"[SilhouetteAE] Tracking (type={tracker_type})")
            track_result = await self.silhouette_engine.run_tracker(
                video_path=video_path,
                output_dir=output_dir,
                tracker_type=tracker_type,
                track_points=track_points or [],
            )
            if track_result.success:
                result["tracking_completed"] = True
                track_data_path = output_dir / "tracks.json"
                result["track_data_exported"] = track_data_path.exists()
                result["track_data_path"] = str(track_data_path)
            else:
                result["errors"].append(f"Tracking failed: {track_result.error}")
        else:
            result["errors"].append("Silhouette not available")

        return result
