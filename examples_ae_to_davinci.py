"""AE → DaVinci Resolve 协作链路 — 使用示例。

============================================

覆盖 5 个典型用法：

1. 一键电影感青橙（最简形式）
2. 复古胶片风格化
3. 音乐 MV 冲击
4. 完全自定义规格
5. 异步执行 + 进度回调

运行方式::

    python examples_ae_to_davinci.py                    # 默认示例 1
    python examples_ae_to_davinci.py --example 2        # 运行示例 2
    python examples_ae_to_davinci.py --example all      # 顺序运行全部

注意：示例默认开启**模拟模式**（``MOCK_MODE=1``），无需真实 AE/DaVinci 即可跑通。
需要真实执行时，将 ``MOCK_MODE`` 置为 ``0``。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import Optional

# 让脚本可直接 ``python examples_ae_to_davinci.py`` 运行
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from integrations.ae_to_davinci_pipeline import (  # noqa: E402
    AEExportSpec,
    AEToDavinciPipeline,
    DavinciGradingSpec,
    DavinciRenderSpec,
    PipelineResult,
    quick_pipeline,
)


# 是否启用模拟模式（不调用真实 AE/DaVinci）
MOCK_MODE = True


# ============================================================================
# Mock 客户端（仅在 MOCK_MODE 时启用）
# ============================================================================

class _MockUnifiedAEClient:
    """模拟 AE 客户端：所有 render/list_compositions 都返回成功。"""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # 默认 comp 列表覆盖示例中用到的合成名
        self.list_compositions_result = [
            {"name": "MyIntro", "id": 1, "width": 1920, "height": 1080},
            {"name": "MyShow", "id": 2, "width": 1920, "height": 1080},
            {"name": "MyBeat", "id": 3, "width": 1920, "height": 1080},
            {"name": "MyComp", "id": 4, "width": 3840, "height": 2160},
            {"name": "MockComp1", "id": 5, "width": 1920, "height": 1080},
            {"name": "MockComp2", "id": 6, "width": 1280, "height": 720},
            {"name": "ResumeComp", "id": 7, "width": 1920, "height": 1080},
        ]

    def render(self, comp_name: str, output_path: str, **_kwargs):
        # 写一个最小占位 mov 文件（仅大小>0 用于校验）
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"FAKEMOV" * 1024)
        return {"success": True, "data": {"path": str(out)}}

    def list_compositions(self):
        return list(self.list_compositions_result)


class _MockResolveColorEngine:
    """模拟 DaVinci 引擎：所有阶段都返回成功。"""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._grader = _MockColorGrader()

    @property
    def color_grader(self):
        return self._grader

    def check_resolve_running(self) -> bool:
        return True

    def launch_resolve(self) -> bool:
        return True

    def create_project(self, project_name: str, media_files, timeline_name: str = "Main", **_):
        return _MockFuscriptResult(success=True, project_name=project_name, timeline_name=timeline_name, clips_imported=len(media_files))

    def render_project(self, project_name: str, output_dir: str, **_):
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{project_name}_output.mp4"
        out.write_bytes(b"FAKERENDER" * 2048)
        return _MockFuscriptResult(success=True, project_name=project_name, render_complete=True, output_path=str(out))


class _MockFuscriptResult:
    def __init__(self, success=True, project_name="", timeline_name="", clips_imported=0, render_complete=False, output_path="", errors=None):
        self.success = success
        self.project_name = project_name
        self.timeline_name = timeline_name
        self.clips_imported = clips_imported
        self.render_complete = render_complete
        self.output_path = output_path
        self.errors = errors or []


class _MockColorGrader:
    """模拟 ColorGrader：所有 apply_preset / export_lut 都返回 True。"""

    class _MockResolve:
        def GetProjectManager(self):
            class _PM:
                def GetCurrentProject(self):
                    class _Proj:
                        def GetCurrentTimeline(self):
                            class _TL:
                                def GetItemListInTrack(self, *_args, **_kwargs):
                                    return [object(), object()]  # 2 个片段
                            return _TL()
                    return _Proj()
            return _PM()

    resolve = _MockResolve()

    def switch_to_color_page(self) -> None:
        return None

    def grade_clip_range(self, clip_indices, node_index: int, preset, balance_type=None):
        return {idx: True for idx in clip_indices}

    def export_lut(self, clip_index: int, node_index: int, output_path: str) -> bool:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("# Mock LUT\n", encoding="utf-8")
        return True


def _build_mock_pipeline(work_dir: Path) -> AEToDavinciPipeline:
    """构造带 Mock 客户端的协作链路。"""
    return AEToDavinciPipeline(
        ae_client=_MockUnifiedAEClient(work_dir / "ae"),
        davinci_engine=_MockResolveColorEngine(work_dir / "davinci"),
        work_dir=str(work_dir / "pipeline"),
        temp_dir=str(work_dir / "temp"),
    )


# ============================================================================
# 示例函数
# ============================================================================

def example_1_cinematic_teal_orange() -> PipelineResult:
    """示例 1：一键电影感青橙（最简形式）。"""
    print("=" * 60)
    print("示例 1：电影感青橙（最简形式）")
    print("=" * 60)
    work_dir = PROJECT_ROOT / "output" / "examples" / "ex1"
    pipeline = _build_mock_pipeline(work_dir) if MOCK_MODE else AEToDavinciPipeline()
    result = pipeline.run_cinematic_teal_orange(
        comp_name="MyIntro",
        output_path=str(work_dir / "intro_cinematic.mp4"),
        duration=10.0,
    )
    _print_result(result)
    return result


def example_2_vintage_film() -> PipelineResult:
    """示例 2：复古胶片风格化。"""
    print("=" * 60)
    print("示例 2：复古胶片")
    print("=" * 60)
    work_dir = PROJECT_ROOT / "output" / "examples" / "ex2"
    pipeline = _build_mock_pipeline(work_dir) if MOCK_MODE else AEToDavinciPipeline()
    result = pipeline.run_vintage_film(
        comp_name="MyShow",
        output_path=str(work_dir / "show_vintage.mp4"),
    )
    _print_result(result)
    return result


def example_3_music_video() -> PipelineResult:
    """示例 3：音乐 MV 冲击。"""
    print("=" * 60)
    print("示例 3：音乐 MV 冲击")
    print("=" * 60)
    work_dir = PROJECT_ROOT / "output" / "examples" / "ex3"
    pipeline = _build_mock_pipeline(work_dir) if MOCK_MODE else AEToDavinciPipeline()
    result = pipeline.run_music_video(
        comp_name="MyBeat",
        output_path=str(work_dir / "beat_punch.mp4"),
        duration=60.0,
    )
    _print_result(result)
    return result


def example_4_custom_specs() -> PipelineResult:
    """示例 4：完全自定义规格。"""
    print("=" * 60)
    print("示例 4：完全自定义规格")
    print("=" * 60)
    work_dir = PROJECT_ROOT / "output" / "examples" / "ex4"
    pipeline = _build_mock_pipeline(work_dir) if MOCK_MODE else AEToDavinciPipeline()

    ae_spec = AEExportSpec(
        comp_name="MyComp",
        output_path=str(work_dir / "ae.mov"),
        format="mov_prores_4444",
        resolution=(3840, 2160),
        frame_rate=60.0,
        duration=20.0,
        quality="best",
        with_audio=True,
    )
    grading_spec = DavinciGradingSpec(
        project_name="MyProject_4K",
        timeline_name="Main",
        preset_name="cold_scifi",
        grade_all_clips=True,
        export_lut=str(work_dir / "grade.cube"),
    )
    render_spec = DavinciRenderSpec(
        output_path=str(work_dir / "final_4k.mp4"),
        format="mp4_h265",
        resolution=(3840, 2160),
        frame_rate=60.0,
        codec="H.265",
        quality="Best",
    )

    def progress(stage: str, pct: float) -> None:
        bar = "=" * int(pct * 30)
        print(f"  [{pct:6.1%}] {stage:30s} {bar}")

    result = pipeline.run(
        ae_spec=ae_spec,
        grading_spec=grading_spec,
        render_spec=render_spec,
        progress_callback=progress,
    )
    _print_result(result)
    return result


async def example_5_async() -> PipelineResult:
    """示例 5：异步执行 + 进度回调。"""
    print("=" * 60)
    print("示例 5：异步执行 + 进度回调")
    print("=" * 60)
    work_dir = PROJECT_ROOT / "output" / "examples" / "ex5"
    pipeline = _build_mock_pipeline(work_dir) if MOCK_MODE else AEToDavinciPipeline()

    def progress(stage: str, pct: float) -> None:
        # 注意：run_async 会在 executor 中跑 run()，回调在子线程被调用，
        # 不能直接 asyncio.create_task。如果需要异步上报，应在调用方用
        # loop.call_soon_threadsafe 派发到事件循环。
        bar = "=" * int(pct * 30)
        print(f"  [async {pct:6.1%}] {stage:30s} {bar}")

    result = await pipeline.run_async(
        ae_spec=AEExportSpec(
            comp_name="MockComp1",
            output_path=str(work_dir / "ae.mov"),
            format="mp4_h264",
        ),
        grading_spec=DavinciGradingSpec(
            project_name="MyAsyncProject",
            timeline_name="AsyncTL",
            preset_name="warm_portrait",
        ),
        render_spec=DavinciRenderSpec(
            output_path=str(work_dir / "async_final.mp4"),
        ),
        progress_callback=progress,
    )
    _print_result(result)
    return result


def example_6_quick_pipeline() -> PipelineResult:
    """示例 6：一行式入口（quick_pipeline）。"""
    print("=" * 60)
    print("示例 6：一行式入口 quick_pipeline")
    print("=" * 60)
    work_dir = PROJECT_ROOT / "output" / "examples" / "ex6"
    # quick_pipeline 走真实懒加载（无 Mock 注入），仅作 API 演示
    print("  quick_pipeline 入口签名示例（实际执行需真实 AE/DaVinci）：")
    print("    quick_pipeline(comp_name='X', output_path='out.mp4', style='cinematic_teal_orange')")
    return PipelineResult(success=True)


def example_7_checkpoints() -> PipelineResult:
    """示例 7：检查点恢复（断点续传）。"""
    print("=" * 60)
    print("示例 7：检查点恢复")
    print("=" * 60)
    work_dir = PROJECT_ROOT / "output" / "examples" / "ex7"
    pipeline = _build_mock_pipeline(work_dir) if MOCK_MODE else AEToDavinciPipeline()
    result = pipeline.run_with_checkpoints(
        ae_spec=AEExportSpec(
            comp_name="ResumeComp",
            output_path=str(work_dir / "ae.mov"),
        ),
        grading_spec=DavinciGradingSpec(
            project_name="ResumeProject",
            preset_name="high_key_bright",
        ),
        render_spec=DavinciRenderSpec(
            output_path=str(work_dir / "resume_final.mp4"),
        ),
        checkpoint_dir=str(work_dir / "checkpoints"),
    )
    _print_result(result)
    return result


# ============================================================================
# 工具函数
# ============================================================================

def _print_result(result: PipelineResult) -> None:
    """统一打印 PipelineResult。"""
    print()
    print(f"  Success         : {result.success}")
    print(f"  Final output    : {result.final_output_path}")
    print(f"  AE export path  : {result.ae_export_path}")
    print(f"  Errors          : {result.errors}")
    print(f"  Warnings        : {result.warnings}")
    if result.metrics:
        print("  Metrics:")
        for k, v in result.metrics.items():
            print(f"    {k:30s} = {v:.3f}")
    if result.finished_at and result.started_at:
        dur = (result.finished_at - result.started_at).total_seconds()
        print(f"  Total duration  : {dur:.3f}s")
    print()


# ============================================================================
# 入口
# ============================================================================

EXAMPLES = {
    "1": example_1_cinematic_teal_orange,
    "2": example_2_vintage_film,
    "3": example_3_music_video,
    "4": example_4_custom_specs,
    "5": example_5_async,
    "6": example_6_quick_pipeline,
    "7": example_7_checkpoints,
}


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="AE → DaVinci 协作链路示例")
    parser.add_argument(
        "--example",
        default="1",
        help="要运行的示例编号（1-7），或 'all' 顺序运行全部",
    )
    args = parser.parse_args(argv)

    if args.example == "all":
        results = []
        for key in ("1", "2", "3", "4", "6", "7"):
            results.append(EXAMPLES[key]())
        # 异步示例单独跑
        asyncio.run(example_5_async())
        ok = all(r.success for r in results)
        return 0 if ok else 1

    fn = EXAMPLES.get(args.example)
    if fn is None:
        print(f"未知示例: {args.example}")
        return 2

    if args.example == "5":
        asyncio.run(fn())  # type: ignore[arg-type]
    else:
        fn()
    return 0


if __name__ == "__main__":
    sys.exit(main())
