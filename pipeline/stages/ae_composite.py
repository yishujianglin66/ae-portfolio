"""
pipeline/stages/ae_composite.py — S3 AE 木偶风格化合成阶段
============================================================

通过 AE 真实 Bridge 创建 3 个合成（Intro/Main/Outro）并渲染为 .mov。
3 段并行执行（asyncio.gather），每段执行前进行 bridge_smoke_probe。

集成方式::

    from pipeline.stages.ae_composite import AECompositeStage

    stage = AECompositeStage()
    result = await stage.run(
        source_videos=["clip1.mp4", "clip2.mp4", "clip3.mp4"],
        output_dir=Path("output/flagship_001/S3_ae"),
    )
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 三段合成定义
COMP_DEFINITIONS = [
    {"id": "Comp_Intro", "duration_s": 4.0, "label": "开场"},
    {"id": "Comp_Main", "duration_s": 7.0, "label": "主体"},
    {"id": "Comp_Outro", "duration_s": 4.0, "label": "收尾"},
]


@dataclass
class AECompositeResult:
    """S3 AE 合成结果"""
    success: bool
    aep_path: Optional[str] = None
    renders: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    bridge_available: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class AECompositeStage:
    """S3 AE 木偶风格化合成阶段

    通过 AE 真实 Bridge 创建 3 个合成并渲染为 .mov。
    零 mock：Bridge 不可用时直接 fail，不降级。
    """

    def __init__(self, engine=None):
        """初始化。

        Args:
            engine: AEEngine 实例（可选，默认自动创建）
        """
        self._engine = engine

    @property
    def engine(self):
        """延迟加载 AE 引擎"""
        if self._engine is None:
            try:
                import sys
                project_root = Path(__file__).resolve().parent.parent.parent
                pa_src = project_root / "puppet-automation" / "src"
                if str(pa_src) not in sys.path:
                    sys.path.insert(0, str(pa_src))
                from engines.ae.engine import AEEngine
                self._engine = AEEngine()
            except Exception as e:
                logger.error(f"[S3] AE 引擎初始化失败: {e}")
                raise
        return self._engine

    async def run(
        self,
        source_videos: List[str | Path],
        output_dir: str | Path,
        preset_dir: Optional[str | Path] = None,
        comp_definitions: Optional[List[Dict]] = None,
    ) -> AECompositeResult:
        """执行 S3 AE 合成。

        Args:
            source_videos: 3 条规范化后的视频路径
            output_dir: 输出目录（S3_ae/）
            preset_dir: AE 预设目录（可选）
            comp_definitions: 合成定义列表（可选，默认 3 段）

        Returns:
            AECompositeResult
        """
        start = time.time()
        output_dir = Path(output_dir)
        renders_dir = output_dir / "renders"
        renders_dir.mkdir(parents=True, exist_ok=True)

        comps = comp_definitions or COMP_DEFINITIONS
        errors: List[str] = []
        renders: List[str] = []

        # Step 0: Bridge 探测
        try:
            probe_result = await self.engine.bridge_smoke_probe()
            if not probe_result.success:
                return AECompositeResult(
                    success=False,
                    errors=[f"Bridge 探测失败: {probe_result.error}"],
                    elapsed_s=time.time() - start,
                    bridge_available=False,
                )
            bridge_available = True
            logger.info("[S3] Bridge 探测通过")
        except Exception as e:
            return AECompositeResult(
                success=False,
                errors=[f"Bridge 探测异常: {e}"],
                elapsed_s=time.time() - start,
                bridge_available=False,
            )

        # Step 1: 3 段并行渲染
        tasks = []
        for i, comp_def in enumerate(comps):
            comp_name = comp_def["id"]
            duration_s = comp_def.get("duration_s", 3.0)
            source = source_videos[i] if i < len(source_videos) else None
            out_mov = renders_dir / f"{comp_name}.mov"

            # 查找预设
            preset_path = None
            if preset_dir:
                preset_dir_p = Path(preset_dir)
                candidates = list(preset_dir_p.glob(f"*{comp_name}*.ffx"))
                if candidates:
                    preset_path = candidates[0]

            tasks.append(
                self._render_single_comp(
                    comp_name=comp_name,
                    output_path=out_mov,
                    duration_s=duration_s,
                    source_video=source,
                    preset_path=preset_path,
                )
            )

        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, (comp_def, result) in enumerate(zip(comps, results)):
            comp_name = comp_def["id"]
            if isinstance(result, Exception):
                errors.append(f"{comp_name}: 异常 {result}")
            elif result.success:
                renders.append(str(result.output_path))
            else:
                errors.append(f"{comp_name}: {result.error}")

        # 查找 .aep 工程文件
        aep_files = list(renders_dir.glob("*.aep")) + list(output_dir.glob("*.aep"))
        aep_path = str(aep_files[0]) if aep_files else None

        elapsed = time.time() - start
        success = len(errors) == 0 and len(renders) == len(comps)

        result = AECompositeResult(
            success=success,
            aep_path=aep_path,
            renders=renders,
            errors=errors,
            elapsed_s=elapsed,
            bridge_available=bridge_available,
            metadata={"comp_count": len(comps)},
        )

        level = logging.INFO if success else logging.ERROR
        logger.log(
            level,
            f"[S3] AE 合成{'成功' if success else '失败'}: "
            f"{len(renders)}/{len(comps)} 段渲染, 耗时 {elapsed:.1f}s"
        )
        return result

    async def _render_single_comp(
        self,
        comp_name: str,
        output_path: Path,
        duration_s: float,
        source_video: Optional[str | Path],
        preset_path: Optional[Path],
    ):
        """渲染单个合成"""
        logger.info(f"[S3] 开始渲染 {comp_name} ({duration_s}s)")
        return await self.engine.render_comp_bridge(
            comp_name=comp_name,
            output_path=output_path,
            duration_s=duration_s,
            source_video=source_video,
            preset_path=preset_path,
        )
