"""Blender → After Effects 跨引擎 3D 合成桥接器 (P2-01)

核心链路：
  Blender (Stage/Cel-shading/Element) → FBX + PNG序列帧 → AE 合成

支持场景：
  1. 生成 Blender 舞台 → 导出 FBX → AE Element 3D 合成
  2. Cel-shading 渲染 → PNG 序列 → AE 作为 3D 背景层
  3. 3D 前景元素（Logo/Text/Particles）→ Alpha 序列帧 → AE 叠加合成
  4. 相机数据 JSON → AE 重建 3D 摄像机运动

使用：
    from bridges.blender_ae_bridge import BlenderAEBridge
    bridge = BlenderAEBridge()
    result = await bridge.create_3d_scene_for_ae(...)
"""
from __future__ import annotations

import asyncio
import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger


def _ensure_puppet_automation_shim() -> None:
    """注册 puppet_automation 包别名 (实际目录是 puppet-automation 含连字符)。

    目录改名 puppet_automation → puppet-automation 后，Python 无法将连字符目录
    识别为合法包名。但引擎代码内部使用了 3 级相对导入
    `from ...config import settings`，要求模块路径前缀必须是
    `puppet_automation.src.engines.xxx`。本函数通过 importlib 在运行时
    将 puppet_automation/src 注册到 sys.modules，解决 ImportError。
    """
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


class BlenderAEBridge:
    """Blender → AE 跨引擎 3D 资产桥接器。"""

    def __init__(self) -> None:
        # 延迟导入避免循环依赖
        self._blender_engine = None
        self._ae_engine = None

    @property
    def blender_engine(self):
        if self._blender_engine is None:
            _ensure_puppet_automation_shim()
            from puppet_automation.src.engines.blender import BlenderEngine
            self._blender_engine = BlenderEngine()
        return self._blender_engine

    @property
    def ae_engine(self):
        if self._ae_engine is None:
            _ensure_puppet_automation_shim()
            from puppet_automation.src.engines.ae import AEEngine
            self._ae_engine = AEEngine()
        return self._ae_engine

    async def create_3d_scene_for_ae(
        self,
        output_dir: Path | str,
        ae_project_path: Path | str,
        comp_name: str = "3D Stage Comp",
        stage_style: str = "wooden",
        resolution: tuple[int, int] = (1920, 1080),
        frame_count: int = 60,
        render_engine: str = "BLENDER_EEVEE",
        import_to_ae: bool = True,
    ) -> dict[str, Any]:
        """全链路：Blender 生成舞台 → 导出 AE 资产 → AE 合成。

        Args:
            output_dir: Blender 产物输出目录
            ae_project_path: AE 工程文件路径 (.aep)
            comp_name: AE 合成名称
            stage_style: 舞台风格 (wooden/minimal/vintage)
            resolution: 渲染分辨率
            frame_count: 帧数
            render_engine: Blender 渲染引擎
            import_to_ae: 是否自动导入到 AE

        Returns:
            包含全链路状态的字典
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result: dict[str, Any] = {
            "stage_created": False,
            "fbx_exported": False,
            "frames_exported": False,
            "ae_project_created": False,
            "asset_imported_to_ae": False,
            "errors": [],
        }

        # Step 1: Blender 创建舞台 + 导出 AE 资产
        logger.info(f"[BlenderAEBridge] Step 1: Creating Blender stage (style={stage_style})")
        stage_result = await self.blender_engine.create_puppet_stage(
            output_dir=output_dir,
            style=stage_style,
            resolution=resolution,
            render_engine=render_engine,
            export_ae=True,
            ae_frame_start=1,
            ae_frame_end=frame_count,
        )

        if not stage_result.success:
            result["errors"].append(f"Blender stage creation failed: {stage_result.error}")
            return result

        result["stage_created"] = True
        metadata = stage_result.metadata or {}
        result["fbx_exported"] = bool(metadata.get("fbx_path") and Path(metadata["fbx_path"]).exists())
        result["frames_exported"] = bool(metadata.get("frames_dir") and Path(metadata["frames_dir"]).exists())
        result["frame_count"] = metadata.get("frame_count", 0)

        fbx_path = metadata.get("fbx_path")
        frames_dir = metadata.get("frames_dir")

        # Step 2: 可选 — 导入到 AE
        if not import_to_ae:
            result["stage_result"] = metadata
            return result

        if not self.ae_engine.available:
            result["errors"].append("AE not available — FBX and frames are ready but not imported")
            result["fbx_path"] = fbx_path
            result["frames_dir"] = frames_dir
            return result

        # Step 2a: 创建 AE 工程和合成
        logger.info("[BlenderAEBridge] Step 2a: Creating AE project + comp")
        ae_result = await self.ae_engine.create_project(
            project_path=ae_project_path,
            comp_name=comp_name,
            width=resolution[0],
            height=resolution[1],
            fps=30.0,
            duration=frame_count / 30.0,
        )

        if not ae_result.success:
            result["errors"].append(f"AE project creation failed: {ae_result.error}")
            return result

        result["ae_project_created"] = True

        # Step 2b: 导入 PNG 序列帧到 AE 合成（作为 3D 背景层）
        if frames_dir:
            frames_path = Path(frames_dir)
            png_files = sorted(frames_path.glob("*.png"))
            if png_files:
                # 导入第一帧作为序列引用（AE 会自动识别为序列）
                first_frame = png_files[0]
                import_result = await self.ae_engine.import_footage(
                    footage_path=first_frame,
                    comp_name=comp_name,
                    as_sequence=True,
                    project_path=ae_project_path,
                )
                if import_result.success:
                    result["asset_imported_to_ae"] = True
                    result["frames_layer_index"] = import_result.metadata.get("layerIndex")
                else:
                    result["errors"].append(f"AE frames import failed: {import_result.error}")

        # Step 2c: 导入 FBX（作为 Element 3D 或 3D Layer）
        if fbx_path:
            fbx_file = Path(fbx_path)
            if fbx_file.exists():
                fbx_import_result = await self.ae_engine.import_footage(
                    footage_path=fbx_file,
                    comp_name=comp_name,
                    project_path=ae_project_path,
                )
                if fbx_import_result.success:
                    result["fbx_layer_index"] = fbx_import_result.metadata.get("layerIndex")
                else:
                    result["errors"].append(f"AE FBX import failed: {fbx_import_result.error}")

        logger.info(
            f"[BlenderAEBridge] Pipeline complete: stage={result['stage_created']}, "
            f"fbx={result['fbx_exported']}, frames={result['frames_exported']}, "
            f"ae_import={result['asset_imported_to_ae']}, errors={len(result['errors'])}"
        )

        return result

    async def create_cel_shading_for_ae(
        self,
        output_dir: Path | str,
        ae_project_path: Path | str,
        comp_name: str = "Cel-Shading Comp",
        style: str = "anime",
        resolution: tuple[int, int] = (1920, 1080),
        frame_count: int = 60,
        model_path: Path | str | None = None,
        outline_mode: str = "lineart",
    ) -> dict[str, Any]:
        """Cel-shading 3渲2 → AE 合成链路。"""
        output_dir = Path(output_dir)
        result: dict[str, Any] = {
            "cel_rendered": False,
            "fbx_exported": False,
            "ae_project_created": False,
            "asset_imported_to_ae": False,
            "errors": [],
        }

        # Step 1: Blender Cel-shading 渲染
        cel_result = await self.blender_engine.render_cel_animation(
            output_dir=output_dir,
            style=style,
            model_path=model_path,
            resolution=resolution,
            frame_start=1,
            frame_end=frame_count,
            outline_mode=outline_mode,
            export_fbx=True,
        )

        if not cel_result.success:
            result["errors"].append(f"Cel-shading render failed: {cel_result.error}")
            return result

        result["cel_rendered"] = True
        metadata = cel_result.metadata or {}
        result["fbx_exported"] = bool(metadata.get("fbx_path"))
        result["frames_dir"] = metadata.get("frames_dir")
        result["frame_count"] = metadata.get("frame_count", 0)

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

                # 导入 Cel-shading PNG 序列
                frames_dir = metadata.get("frames_dir")
                if frames_dir:
                    png_files = sorted(Path(frames_dir).glob("*.png"))
                    if png_files:
                        import_result = await self.ae_engine.import_footage(
                            footage_path=png_files[0],
                            comp_name=comp_name,
                            as_sequence=True,
                            project_path=ae_project_path,
                        )
                        if import_result.success:
                            result["asset_imported_to_ae"] = True
                        else:
                            result["errors"].append(f"AE import failed: {import_result.error}")
        else:
            result["errors"].append("AE not available — Cel frames ready but not imported")

        return result

    async def create_foreground_element_for_ae(
        self,
        output_dir: Path | str,
        element_type: str = "logo",
        element_params: dict[str, Any] | None = None,
        resolution: tuple[int, int] = (1920, 1080),
        frame_count: int = 60,
        ae_project_path: Path | str | None = None,
        comp_name: str = "Foreground Comp",
    ) -> dict[str, Any]:
        """3D 前景元素 → AE 叠加合成。"""
        output_dir = Path(output_dir)
        result: dict[str, Any] = {
            "element_rendered": False,
            "ae_project_created": False,
            "asset_imported_to_ae": False,
            "errors": [],
        }

        # Step 1: Blender 渲染前景元素（带 Alpha）
        render_result = await self.blender_engine.render_foreground_element(
            output_dir=output_dir,
            element_type=element_type,
            element_params=element_params,
            resolution=resolution,
            frame_start=1,
            frame_end=frame_count,
            transparent_background=True,
        )

        if not render_result.success:
            result["errors"].append(f"Foreground element render failed: {render_result.error}")
            return result

        result["element_rendered"] = True
        metadata = render_result.metadata or {}
        result["frames_dir"] = metadata.get("frames_dir")
        result["frame_count"] = metadata.get("frame_count", 0)

        # Step 2: 导入到 AE（可选）
        if ae_project_path and self.ae_engine.available:
            ae_result = await self.ae_engine.create_project(
                project_path=ae_project_path,
                comp_name=comp_name,
                width=resolution[0],
                height=resolution[1],
                duration=frame_count / 30.0,
            )
            if ae_result.success:
                result["ae_project_created"] = True

                frames_dir = metadata.get("frames_dir")
                if frames_dir:
                    png_files = sorted(Path(frames_dir).glob("*.png"))
                    if png_files:
                        import_result = await self.ae_engine.import_footage(
                            footage_path=png_files[0],
                            comp_name=comp_name,
                            as_sequence=True,
                            project_path=ae_project_path,
                        )
                        if import_result.success:
                            result["asset_imported_to_ae"] = True
                        else:
                            result["errors"].append(f"AE import failed: {import_result.error}")

        return result
