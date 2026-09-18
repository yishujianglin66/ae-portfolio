"""pipeline/pipeline_watcher.py — 无人值守管线调度器 (Loop Engineering 调度层)

补齐语义评判闭环之外的另一半: 无人值守批量执行。

工作方式 (文件队列, 零外部依赖, 离线可用):
  data/watcher_queue/
    pending/   ← 每个任务一个 JSON 规格文件 (PipelineConfig 可序列化字段)
    running/   ← 正在执行的任务 (进程崩溃时可被认领恢复)
    done/      ← 成功完成 (附 result_*.json)
    failed/    ← 失败任务 (附错误原因, 同时写入 ErrorMemory 错误记忆)

用法:
    # 单轮: 处理当前 pending 中所有任务后退出
    python -m pipeline.pipeline_watcher --once
    # 常驻: 每 --interval 秒轮询一次, 直到 --max-runs 次执行或手动停止
    python -m pipeline.pipeline_watcher --loop --interval 60 --max-runs 10

任务规格示例 (pending/task_001.json):
    {
      "input_topic": "高燃动漫混剪",
      "materials_dir": "temp/e2e_materials",
      "output_dir": "output/watcher_batch",
      "visual_judge_backend": "auto",
      "max_quality_iterations": 2
    }
  规格中任意 PipelineConfig 字段均可覆盖; 非法字段忽略并记录警告。

串行执行原因: 本地仅 8GB 显存, VLM 评判与渲染引擎独占, 并行无收益且会 OOM。
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_ROOT = Path("data") / "watcher_queue"


class PipelineWatcher:
    """文件队列调度器: pending → running → done/failed, 串行执行"""

    def __init__(
        self,
        queue_root: str | Path | None = None,
        max_retries: int = 1,
    ):
        self.root = Path(queue_root) if queue_root else DEFAULT_QUEUE_ROOT
        self.pending = self.root / "pending"
        self.running = self.root / "running"
        self.done = self.root / "done"
        self.failed = self.root / "failed"
        for d in (self.pending, self.running, self.done, self.failed):
            d.mkdir(parents=True, exist_ok=True)
        self.max_retries = max(0, int(max_retries))
        self.ledger: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    #  队列操作
    # ------------------------------------------------------------------

    def submit(self, spec: dict[str, Any], task_id: str = "") -> Path:
        """提交任务规格到 pending 队列, 返回规格文件路径"""
        tid = task_id or f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        path = self.pending / f"{tid}.json"
        path.write_text(
            json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(f"[Watcher] submitted {tid}")
        return path

    def _pending_tasks(self) -> list[Path]:
        return sorted(self.pending.glob("*.json"))

    def _load_spec(self, path: Path) -> dict[str, Any]:
        # utf-8-sig: 兼容 Windows 工具写出的带 BOM 规格文件
        return json.loads(path.read_text(encoding="utf-8-sig"))

    # ------------------------------------------------------------------
    #  执行
    # ------------------------------------------------------------------

    def _build_config(self, spec: dict[str, Any]):
        """规格 → PipelineConfig; 未知字段忽略 (防规格文件写坏导致调度器崩溃)"""
        from pipeline.unified_pipeline import PipelineConfig

        valid = {f.name for f in fields(PipelineConfig)}
        kwargs = {k: v for k, v in spec.items() if k in valid}
        skipped = [k for k in spec if k not in valid]
        if skipped:
            logger.warning(f"[Watcher] spec unknown fields ignored: {skipped}")
        return PipelineConfig(**kwargs)

    def _record_failure_to_memory(self, task_id: str, error: Exception, spec: dict):
        """失败写入错误记忆 (复用 feedback_loop.ErrorPatternMemory), 失败不阻塞调度"""
        try:
            from pipeline.feedback_loop import ErrorPatternMemory
            ErrorPatternMemory().record_error(
                error,
                context={
                    "source": "pipeline_watcher",
                    "task_id": task_id,
                    "input_topic": str(spec.get("input_topic", ""))[:100],
                },
                fix_applied="task moved to failed queue for manual inspection",
            )
        except Exception as e:
            logger.warning(f"[Watcher] ErrorMemory write failed: {e}")

    def _run_one(self, spec_path: Path) -> dict[str, Any]:
        """执行单个任务: pending → running → done/failed"""
        from pipeline.unified_pipeline import UnifiedPipeline

        task_id = spec_path.stem
        running_path = self.running / spec_path.name
        spec_path.replace(running_path)

        entry: dict[str, Any] = {
            "task_id": task_id,
            "started_at": datetime.now().isoformat(),
        }
        try:
            spec = self._load_spec(running_path)
            config = self._build_config(spec)
            pipe = UnifiedPipeline(config)
            t0 = time.time()
            result = pipe.run_all()
            entry.update({
                "status": result.status,
                "quality_score": result.quality_score,
                "iterations": result.iterations,
                "output_path": result.output_path,
                "duration_sec": round(time.time() - t0, 1),
                "errors": result.errors[:5],
            })
            # 管线返回 failed / 无输出 → 归入 failed 队列
            ok = result.status == "success" and result.output_path \
                and Path(result.output_path).exists()
            dest = self.done if ok else self.failed
            entry["finished_at"] = datetime.now().isoformat()
            result_file = dest / f"result_{task_id}.json"
            result_file.write_text(
                json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            running_path.replace(dest / running_path.name)
            if not ok:
                logger.warning(f"[Watcher] {task_id} finished but not ok: {entry.get('errors')}")
                self._record_failure_to_memory(
                    task_id, RuntimeError(f"pipeline status={result.status}"), spec
                )
        except Exception as e:
            logger.error(f"[Watcher] {task_id} crashed: {type(e).__name__}: {e}")
            entry.update({
                "status": "crashed",
                "error": f"{type(e).__name__}: {str(e)[:300]}",
                "finished_at": datetime.now().isoformat(),
            })
            result_file = self.failed / f"result_{task_id}.json"
            result_file.write_text(
                json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            running_path.replace(self.failed / running_path.name)
            try:
                spec = self._load_spec(self.failed / running_path.name)
            except Exception:
                spec = {}
            self._record_failure_to_memory(task_id, e, spec)

        self.ledger.append(entry)
        return entry

    def drain_pending(self) -> list[dict[str, Any]]:
        """处理当前 pending 队列中的全部任务 (串行)"""
        results = []
        for spec_path in self._pending_tasks():
            results.append(self._run_one(spec_path))
        return results

    def run_loop(self, interval_sec: float = 60.0, max_runs: int = 0) -> None:
        """常驻轮询: 每 interval_sec 秒检查一次; max_runs>0 时执行满后退出"""
        executed = 0
        logger.info(f"[Watcher] loop started (interval={interval_sec}s, max_runs={max_runs or 'inf'})")
        while True:
            batch = self.drain_pending()
            executed += len(batch)
            if batch:
                logger.info(f"[Watcher] batch done: {len(batch)} tasks, total={executed}")
            if max_runs and executed >= max_runs:
                logger.info(f"[Watcher] max_runs={max_runs} reached, exiting")
                break
            time.sleep(max(1.0, float(interval_sec)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AE-Knowledge-Vault 无人值守管线调度器")
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE_ROOT), help="队列根目录")
    parser.add_argument("--loop", action="store_true", help="常驻轮询模式")
    parser.add_argument("--once", action="store_true", help="处理完当前队列即退出")
    parser.add_argument("--interval", type=float, default=60.0, help="轮询间隔秒数")
    parser.add_argument("--max-runs", type=int, default=0, help="最多执行任务数 (0=不限)")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    watcher = PipelineWatcher(queue_root=args.queue)
    if args.loop and not args.once:
        watcher.run_loop(interval_sec=args.interval, max_runs=args.max_runs)
    else:
        results = watcher.drain_pending()
        logger.info(f"[Watcher] drained {len(results)} tasks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
