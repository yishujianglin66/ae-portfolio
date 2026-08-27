"""Topaz → DaVinci 跨引擎 AI 增强链路桥接器 (P2-02)

核心链路：
  Topaz Video AI Pro (增强/超分/插帧) → 输出增强视频 → DaVinci Resolve 调色

使用：
    from bridges.topaz_davinci_bridge import TopazDaVinciBridge
    bridge = TopazDaVinciBridge()
    result = await bridge.enhance_and_color_grade(...)
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


class TopazDaVinciBridge:
    """Topaz → DaVinci AI 增强 + 调色桥接器。"""

    def __init__(self) -> None:
        self._topaz_engine = None
        self._davinci_engine = None

    @property
    def topaz_engine(self):
        if self._topaz_engine is None:
            _ensure_puppet_automation_shim()
            from puppet_automation.src.engines.topaz import TopazEngine
            self._topaz_engine = TopazEngine()
        return self._topaz_engine

    @property
    def davinci_engine(self):
        if self._davinci_engine is None:
            _ensure_puppet_automation_shim()
            from puppet_automation.src.engines.davinci import DavinciEngine
            self._davinci_engine = DavinciEngine()
        return self._davinci_engine

    async def enhance_for_color_grading(
        self,
        input_path: Path | str,
        output_dir: Path | str,
        topaz_model: str = "proteus",
        scale: int = 2,
        use_video_ai: bool = True,
        davinci_project_path: Optional[Path | str] = None,
        timeline_name: str = "Enhanced Timeline",
    ) -> Dict[str, Any]:
        """AI 增强 → DaVinci 调色完整链路。

        Args:
            input_path: 输入视频路径
            output_dir: 输出目录
            topaz_model: Topaz 增强模型 (proteus/artemis/gaia 等)
            scale: 超分倍数 (2/4)
            use_video_ai: 是否使用 Topaz Video AI
            davinci_project_path: DaVinci 工程路径
            timeline_name: DaVinci 时间线名称
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result: Dict[str, Any] = {
            "topaz_enhanced": False,
            "davinci_project_created": False,
            "timeline_created": False,
            "clips_added_to_timeline": False,
            "errors": [],
        }

        enhanced_path = output_dir / f"enhanced_{input_path.stem}_{scale}x.mp4"

        # Step 1: Topaz AI 增强
        if use_video_ai and self.topaz_engine.available:
            logger.info(f"[TopazDaVinci] Step 1: Topaz enhance (model={topaz_model}, scale={scale}x)")
            topaz_result = await self.topaz_engine.enhance(
                input_path=input_path,
                output_path=enhanced_path,
                model=topaz_model,
                scale=scale,
            )
            if topaz_result.success:
                result["topaz_enhanced"] = True
                result["enhanced_path"] = str(enhanced_path)
                result["topaz_metadata"] = topaz_result.metadata
            else:
                result["errors"].append(f"Topaz enhance failed: {topaz_result.error}")
                # 降级：直接使用原视频
                result["enhanced_path"] = str(input_path)
        else:
            result["enhanced_path"] = str(input_path)
            if use_video_ai:
                result["errors"].append("Topaz not available — using original video")

        # Step 2: DaVinci 调色
        if davinci_project_path and self.davinci_engine.available:
            try:
                davinci_result = await self.davinci_engine.import_media_and_create_timeline(
                    media_paths=[Path(result["enhanced_path"])],
                    project_path=davinci_project_path,
                    timeline_name=timeline_name,
                )
                if davinci_result.success:
                    result["davinci_project_created"] = True
                    result["timeline_created"] = True
                    result["clips_added_to_timeline"] = True
                    result["davinci_metadata"] = davinci_result.metadata
                else:
                    result["errors"].append(f"DaVinci import failed: {davinci_result.error}")
            except AttributeError:
                # DavinciEngine 可能尚未实现 import_media_and_create_timeline
                result["errors"].append("DaVinciEngine.import_media_and_create_timeline not available yet")
        elif not self.davinci_engine.available:
            result["errors"].append("DaVinci not available — enhanced video ready for manual import")

        return result

    async def batch_enhance_for_color_grading(
        self,
        input_paths: List[Path | str],
        output_dir: Path | str,
        topaz_model: str = "proteus",
        scale: int = 2,
    ) -> List[Dict[str, Any]]:
        """批量 AI 增强（不经过 DaVinci 编排，仅 Topaz 批处理）。"""
        results: List[Dict[str, Any]] = []
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for input_path in input_paths:
            input_path = Path(input_path)
            enhanced_path = output_dir / f"enhanced_{input_path.stem}_{scale}x.mp4"
            entry = {
                "input_path": str(input_path),
                "enhanced_path": str(enhanced_path),
                "success": False,
            }

            if self.topaz_engine.available:
                topaz_result = await self.topaz_engine.enhance(
                    input_path=input_path,
                    output_path=enhanced_path,
                    model=topaz_model,
                    scale=scale,
                )
                entry["success"] = topaz_result.success
                if topaz_result.error:
                    entry["error"] = topaz_result.error
            else:
                entry["error"] = "Topaz not available"

            results.append(entry)

        return results
