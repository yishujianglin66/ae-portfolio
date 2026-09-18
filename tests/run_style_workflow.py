#!/usr/bin/env python3
"""端到端验证：workflow_tasks_video.build_style_pipeline 注册后能完整跑通。

支持 Agent-Reach 联网搜索集成测试。

用法：
    python tests/run_style_workflow.py <video_path> [--workers 8] [--no-web-search]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=str)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--sample-interval", type=int, default=10)
    parser.add_argument("--no-web-search", action="store_true", help="禁用联网搜索")
    parser.add_argument("--search-keywords", nargs="*", default=[], help="附加搜索关键词")
    args = parser.parse_args()

    from core.workflow_tasks_video import build_style_pipeline

    from core.workflow_orchestrator import WorkflowContext, WorkflowOrchestrator

    video = Path(args.video)
    if not video.exists():
        print(f"视频不存在: {video}")
        return 2

    ctx = WorkflowContext(workflow_id="style-pipeline-test")
    orch = WorkflowOrchestrator(max_concurrent_tasks=4)
    orch._context = ctx  # 直接绑定 context（避免公开 set_context 接口变更）
    build_style_pipeline(
        orch,
        str(video),
        sample_interval=args.sample_interval,
        num_workers=args.workers,
        use_gpu=True,
        enable_web_search=not args.no_web_search,
        search_keywords=args.search_keywords or None,
    )

    print(f"[INFO] Pipeline 已注册 {len(orch._tasks_def)} 个任务节点")
    print(f"[INFO] 任务ID列表: {[t.task_id for t in orch._tasks_def]}")
    print(f"[INFO] 联网搜索: {'开启' if not args.no_web_search else '关闭'}")

    t0 = time.perf_counter()
    result_ctx = await orch.run(workflow_id="style-pipeline-test")
    elapsed = time.perf_counter() - t0

    # Use the returned context (not the one we passed, since run() creates a new one)
    ctx = result_ctx
    status = orch.get_stats()
    print(f"\n{'='*60}")
    print(f"[RESULT] 流水线状态: {status.get('status')}")
    print(f"{'='*60}")
    print(json.dumps(status, ensure_ascii=False, indent=2, default=str))

    for task_id, inst in ctx.tasks.items():
        print(f"\n--- [{task_id}] status={inst.status.value}  dur={inst.duration:.2f}s ---")
        result = inst.result
        if isinstance(result, dict):
            if "frames_data" in result:
                print(f"  total frames: {result.get('total_frames_sampled')}")
                perf = result.get("_perf", {})
                if perf:
                    print(f"  perf: {json.dumps(perf, ensure_ascii=False)}")
            elif "external_references" in result:
                refs = result.get("external_references", {})
                source_count = result.get("source_count", 0)
                print(f"  style_label: {result.get('style_label')}")
                print(f"  source_count: {source_count}")
                print(f"  summary: {result.get('reference_summary', '')[:200]}")
                for platform, items in refs.items():
                    print(f"  [{platform}] ({len(items)} results):")
                    for item in items[:2]:
                        print(f"    - {item.get('title', 'N/A')[:80]}")
            elif "style_label" in result:
                print(f"  style: {result.get('style_label')}, conf: {result.get('confidence')}")
                if "features" in result:
                    feats = result["features"]
                    if isinstance(feats, dict):
                        for k in list(feats.keys())[:5]:
                            print(f"    {k}: {feats[k]}")
            elif "jsx_path" in result:
                print(f"  jsx_path: {result.get('jsx_path')}")
                if result.get("atomic_params"):
                    effects = result["atomic_params"].get("effects", [])
                    print(f"  atomic effects count: {len(effects)}")
            else:
                effects = result.get("effects") or []
                print(f"  atomic effects count: {len(effects)}")
        if inst.error:
            print(f"  [ERROR] {inst.error}")

    print(f"\n总耗时: {elapsed:.2f}s")
    return 0 if status.get("status") == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
