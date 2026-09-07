#!/usr/bin/env python3
"""端到端一键渲染流水线 CLI.

将素材分析→风格匹配→AE 合成→PR 剪辑→DaVinci 调色→渲染输出串联为单一命令。

使用方式:
    python scripts/pipeline_cli.py \\
        --input D:/素材/raw_clips/ \\
        --style "日系动漫" \\
        --output D:/output/final.mp4 \\
        --dry-run  # 仅预览，不执行
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# 阶段定义
# ---------------------------------------------------------------------------

@dataclass
class PipelineStage:
    name: str
    engine: str
    command: list[str]
    depends_on: list[str] = field(default_factory=list)
    skip_on_error: bool = False


STAGES: list[PipelineStage] = [
    PipelineStage(
        name="素材扫描",
        engine="ffmpeg",
        command=["python", "scripts/pipeline_cli.py", "--stage", "scan"],
    ),
    PipelineStage(
        name="风格分析",
        engine="ai",
        command=["python", "scripts/pipeline_cli.py", "--stage", "analyze"],
        depends_on=["素材扫描"],
    ),
    PipelineStage(
        name="Silhouette Roto",
        engine="silhouette",
        command=["python", "scripts/pipeline_cli.py", "--stage", "silhouette_roto"],
        depends_on=["风格分析"],
        skip_on_error=True,  # 非必须步骤
    ),
    PipelineStage(
        name="AE 合成",
        engine="ae",
        command=["python", "scripts/pipeline_cli.py", "--stage", "ae_compose"],
        depends_on=["风格分析"],
    ),
    PipelineStage(
        name="PR 剪辑",
        engine="premiere",
        command=["python", "scripts/pipeline_cli.py", "--stage", "pr_edit"],
        depends_on=["AE 合成", "Silhouette Roto"],
    ),
    PipelineStage(
        name="DaVinci 调色",
        engine="davinci",
        command=["python", "scripts/pipeline_cli.py", "--stage", "davinci_grade"],
        depends_on=["PR 剪辑"],
    ),
    PipelineStage(
        name="渲染输出",
        engine="ffmpeg",
        command=["python", "scripts/pipeline_cli.py", "--stage", "render"],
        depends_on=["DaVinci 调色"],
    ),
    PipelineStage(
        name="质量检查",
        engine="ffmpeg",
        command=["python", "scripts/pipeline_cli.py", "--stage", "qc"],
        depends_on=["渲染输出"],
    ),
]


# ---------------------------------------------------------------------------
# 阶段执行器
# ---------------------------------------------------------------------------

class StageResult:
    def __init__(self, name: str, success: bool, duration: float, output: str = ""):
        self.name = name
        self.success = success
        self.duration = duration
        self.output = output


async def execute_stage(
    stage: PipelineStage,
    input_dir: str,
    style: str,
    output: str,
    dry_run: bool = False,
) -> StageResult:
    """执行单个流水线阶段."""
    print(f"\n{'=' * 50}")
    print(f"  [{stage.engine.upper()}] {stage.name}")
    print(f"{'=' * 50}")

    if dry_run:
        print(f"  [DRY-RUN] 将执行: {' '.join(stage.command)}")
        return StageResult(stage.name, True, 0, "[dry-run]")

    start = time.perf_counter()
    try:
        env = {
            **dict(subprocess.os.environ),
            "PIPELINE_INPUT": input_dir,
            "PIPELINE_STYLE": style,
            "PIPELINE_OUTPUT": output,
        }
        proc = await asyncio.create_subprocess_exec(
            *stage.command,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        elapsed = time.perf_counter() - start

        success = proc.returncode == 0
        output_text = stdout.decode(errors="replace")[:500]

        status = "PASS" if success else "FAIL"
        print(f"  [{status}] {stage.name} ({elapsed:.1f}s)")
        if not success and stderr:
            print(f"  Error: {stderr.decode(errors='replace')[:200]}")

        return StageResult(stage.name, success, elapsed, output_text)

    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"  [FAIL] {stage.name}: {e}")
        return StageResult(stage.name, False, elapsed, str(e))


async def run_pipeline(
    input_dir: str,
    style: str,
    output: str,
    dry_run: bool = False,
    stages_filter: Optional[list[str]] = None,
) -> dict[str, Any]:
    """运行完整流水线（依赖驱动 DAG）."""
    results: dict[str, StageResult] = {}
    start_time = time.perf_counter()

    # 过滤阶段
    to_run = STAGES
    if stages_filter:
        to_run = [s for s in STAGES if s.name in stages_filter]

    print("=" * 60)
    print("  AE-Knowledge-Vault 一键渲染流水线")
    print("=" * 60)
    print(f"  输入:  {input_dir}")
    print(f"  风格:  {style}")
    print(f"  输出:  {output}")
    print(f"  阶段:  {len(to_run)} 个")
    print(f"  模式:  {'DRY-RUN' if dry_run else 'LIVE'}")
    print()

    for stage in to_run:
        # 检查依赖是否通过
        deps_failed = False
        for dep in stage.depends_on:
            dep_result = results.get(dep)
            if dep_result and not dep_result.success:
                deps_failed = True
                break

        if deps_failed and not stage.skip_on_error:
            print(f"  [SKIP] {stage.name}: 依赖失败")
            results[stage.name] = StageResult(stage.name, False, 0, "dependency_failed")
            continue
        elif deps_failed and stage.skip_on_error:
            print(f"  [SKIP] {stage.name}: 依赖失败（允许跳过）")
            results[stage.name] = StageResult(stage.name, False, 0, "dependency_failed_skipped")
            continue

        result = await execute_stage(stage, input_dir, style, output, dry_run)
        results[stage.name] = result

        # 非必须步骤失败不中断
        if not result.success and not stage.skip_on_error:
            print(f"\n  ABORT: {stage.name} 失败，停止流水线")
            break

    elapsed = time.perf_counter() - start_time

    # 汇总
    passed = sum(1 for r in results.values() if r.success)
    total = len(results)
    failed = total - passed

    print()
    print("=" * 60)
    print("  流水线执行完成")
    print("=" * 60)
    for r in results.values():
        icon = "✅" if r.success else "❌"
        print(f"  {icon} {r.name:<20s} {r.duration:6.1f}s")
    print("-" * 60)
    print(f"  总计: {total}  |  通过: {passed}  |  失败: {failed}  |  耗时: {elapsed:.1f}s")
    print("=" * 60)

    return {
        "status": "completed" if failed == 0 else "partial" if passed > 0 else "failed",
        "total": total,
        "passed": passed,
        "failed": failed,
        "elapsed_s": elapsed,
        "results": {
            name: {"success": r.success, "duration": r.duration, "output": r.output[:200]}
            for name, r in results.items()
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="AE-Knowledge-Vault 端到端渲染流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/pipeline_cli.py --input D:/素材/ --style 日系动漫 --output D:/output.mp4
  python scripts/pipeline_cli.py --input D:/素材/ --style 赛博朋克 --output D:/output.mp4 --dry-run
  python scripts/pipeline_cli.py --input D:/素材/ --style 日系动漫 --output D:/output.mp4 --stages "AE 合成,DaVinci 调色"
        """,
    )
    parser.add_argument("--input", required=True, help="素材目录")
    parser.add_argument("--style", required=True, help="目标风格（日系动漫/赛博朋克/电影感/纪录片/等）")
    parser.add_argument("--output", required=True, help="输出文件路径")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际执行")
    parser.add_argument("--stages", type=str, help="仅执行指定阶段（逗号分隔）")
    parser.add_argument("--output-report", type=str, help="输出 JSON 报告路径")
    args = parser.parse_args()

    stages_filter = None
    if args.stages:
        stages_filter = [s.strip() for s in args.stages.split(",")]

    result = asyncio.run(
        run_pipeline(
            input_dir=args.input,
            style=args.style,
            output=args.output,
            dry_run=args.dry_run,
            stages_filter=stages_filter,
        )
    )

    if args.output_report:
        report_path = Path(args.output_report)
        report_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n报告已保存: {report_path}")

    sys.exit(0 if result["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
