"""Cinema 4D → After Effects 3D 场景链路桥接器 (P2-04)

核心链路：
  Cinema 4D (c4dpy) → PNG 序列帧 + 相机数据 → AE 合成

与 Blender→AE 的区别：
  - C4D 擅长 MoGraph 运动图形和复杂 3D 场景
  - C4D 可通过 c4dpy 无界面脚本执行
  - C4D 输出更适合 AE 的 Element 3D / Cineware 联动
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


class C4DAEBridge:
    """Cinema 4D → AE 3D 场景桥接器。"""

    def __init__(self) -> None:
        self._c4d_engine = None
        self._ae_engine = None

    @property
    def c4d_engine(self):
        if self._c4d_engine is None:
            _ensure_puppet_automation_shim()
            from puppet_automation.src.engines.cinema4d import Cinema4DEngine
            self._c4d_engine = Cinema4DEngine()
        return self._c4d_engine

    @property
    def ae_engine(self):
        if self._ae_engine is None:
            _ensure_puppet_automation_shim()
            from puppet_automation.src.engines.ae import AEEngine
            self._ae_engine = AEEngine()
        return self._ae_engine

    async def render_c4d_scene_to_ae(
        self,
        output_dir: Path | str,
        ae_project_path: Path | str,
        comp_name: str = "C4D Stage Comp",
        scene_type: str = "stage",
        resolution: tuple[int, int] = (1920, 1080),
        frame_count: int = 60,
        render_engine: str = "standard",
        import_to_ae: bool = True,
    ) -> dict[str, Any]:
        """C4D 场景渲染 → AE 合成链路。"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result: dict[str, Any] = {
            "c4d_rendered": False,
            "ae_project_created": False,
            "asset_imported_to_ae": False,
            "errors": [],
        }

        # Step 1: C4D 场景渲染
        logger.info(f"[C4DAEBridge] Step 1: C4D render (scene={scene_type}, frames={frame_count})")
        render_result = await self.c4d_engine.render_scene(
            output_dir=output_dir,
            scene_type=scene_type,
            resolution=resolution,
            frame_start=1,
            frame_end=frame_count,
            engine=render_engine,
        )

        if not render_result.success:
            result["errors"].append(f"C4D render failed: {render_result.error}")
            return result

        result["c4d_rendered"] = True
        metadata = render_result.metadata or {}
        result["frames_dir"] = str(output_dir / "frames")
        result["frame_count"] = metadata.get("frame_count", 0)

        # Step 2: 相机数据导出
        try:
            camera_result = await self.c4d_engine.export_camera_data(
                output_dir=output_dir,
            )
            if camera_result.success:
                result["camera_data_path"] = str(output_dir / "camera_data.json")
        except Exception as e:
            result["errors"].append(f"Camera data export warning: {e}")

        # Step 3: 导入到 AE
        if not import_to_ae:
            return result

        if not self.ae_engine.available:
            result["errors"].append("AE not available — C4D frames ready for manual import")
            return result

        ae_result = await self.ae_engine.create_project(
            project_path=ae_project_path,
            comp_name=comp_name,
            width=resolution[0],
            height=resolution[1],
            duration=frame_count / 30.0,
        )

        if not ae_result.success:
            result["errors"].append(f"AE project creation failed: {ae_result.error}")
            return result

        result["ae_project_created"] = True

        # 导入 PNG 序列帧
        frames_dir = Path(result["frames_dir"])
        if frames_dir.exists():
            png_files = sorted(frames_dir.glob("*.png"))
            if png_files:
                import_result = await self.ae_engine.import_footage(
                    footage_path=png_files[0],
                    comp_name=comp_name,
                    as_sequence=True,
                    project_path=ae_project_path,
                )
                if import_result.success:
                    result["asset_imported_to_ae"] = True
                    result["frames_layer_index"] = import_result.metadata.get("layerIndex")
                else:
                    result["errors"].append(f"AE frames import failed: {import_result.error}")

        return result

    async def render_motion_graphics_to_ae(
        self,
        output_dir: Path | str,
        ae_project_path: Path | str,
        comp_name: str = "MoGraph Comp",
        text: str = "MOTION",
        resolution: tuple[int, int] = (1920, 1080),
        frame_count: int = 60,
    ) -> dict[str, Any]:
        """C4D MoGraph 运动图形 → AE 合成链路。"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result: dict[str, Any] = {
            "mograph_rendered": False,
            "ae_project_created": False,
            "asset_imported_to_ae": False,
            "errors": [],
        }

        # Step 1: C4D MoGraph 渲染（引擎按 preset 契约生成动画，
        # text 参数保留在桥接层签名供 AE 文字图层使用）
        render_result = await self.c4d_engine.render_motion_graphics(
            output_dir=output_dir,
            preset="lower_third",
            resolution=resolution,
            frame_range=(1, frame_count),
        )

        if not render_result.success:
            result["errors"].append(f"MoGraph render failed: {render_result.error}")
            return result

        result["mograph_rendered"] = True
        metadata = render_result.metadata or {}
        result["frames_dir"] = metadata.get("frames_dir", str(output_dir / "frames"))

        # Step 2: 导入到 AE
        if self.ae_engine.available:
            ae_result = await self.ae_engine.create_project(
                project_path=ae_project_path,
                comp_name=comp_name,
                width=resolution[0],
                height=resolution[1],
                duration=frame_count / 30.0,
            )
            if ae_result.success:
                result["ae_project_created"] = True

                frames_dir = Path(result["frames_dir"])
                if frames_dir.exists():
                    png_files = sorted(frames_dir.glob("*.png"))
                    if png_files:
                        import_result = await self.ae_engine.import_footage(
                            footage_path=png_files[0],
                            comp_name=comp_name,
                            as_sequence=True,
                            project_path=ae_project_path,
                        )
                        if import_result.success:
                            result["asset_imported_to_ae"] = True

        return result
