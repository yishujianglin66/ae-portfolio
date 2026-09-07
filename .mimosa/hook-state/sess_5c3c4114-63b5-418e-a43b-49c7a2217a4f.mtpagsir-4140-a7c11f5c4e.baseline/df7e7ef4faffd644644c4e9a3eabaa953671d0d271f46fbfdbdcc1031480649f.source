"""
core/evolution/auto_benchmark.py — 从历史执行自动生成/轮换评测题目 (P2)
==========================================================================

借鉴 PenguinHarness「Benchmark Builder 每 10 轮生成新题目替换旧题目」:
1. harvest_from_pipeline_run — 从一次真实管线运行提炼新题目
2. harvest_from_trajectory — 从执行轨迹提炼新题目
3. refresh_benchmark — 定期轮换：生成新题 + 退役最旧的生成题（防止题目老化/过拟合）

用法:
    from core.evolution.auto_benchmark import get_auto_benchmark

    ab = get_auto_benchmark()
    ab.harvest_from_pipeline_run(pipeline_result_dict)
    ab.refresh_benchmark(task_type="style_transfer")
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.evolution.benchmark_builder import BenchmarkBuilder, get_benchmark_builder
from core.evolution.protocol import read_json, write_json

logger = logging.getLogger(__name__)


# 每个 split 中「生成题目」的保留上限，超出则轮换退役
MAX_GENERATED_TASKS_PER_SPLIT = 20
# 每 N 轮进化触发一次题目轮换
REFRESH_EVERY_CYCLES = 10


class AutoBenchmark:
    """自动评测基准维护器"""

    # 管线 mode → benchmark task_type 映射
    MODE_TO_TASK_TYPE = {
        "reference_video": "style_transfer",
        "mixed": "style_transfer",
        "text_topic": "effect_apply",
    }

    def __init__(self, builder: Optional[BenchmarkBuilder] = None):
        self._builder = builder or get_benchmark_builder()
        self._benchmark_dir = self._builder._benchmark_dir
        self._retired_dir = self._benchmark_dir / "retired"

    # ----------------------------------------------------------------
    #  从管线运行/轨迹提炼题目
    # ----------------------------------------------------------------

    def harvest_from_pipeline_run(
        self,
        pipeline_result: Dict[str, Any],
        split: str = "train",
    ) -> List[Dict[str, Any]]:
        """从一次管线运行提炼新题目（P2 知识反哺评测集）

        仅当运行含有效输入主题时提炼；去重由 BenchmarkBuilder 隔离校验保证。
        """
        input_topic = str(pipeline_result.get("input_topic", "")
                          or pipeline_result.get("_task_input", "")
                          or pipeline_result.get("config_summary", {}).get("input_topic", ""))
        mode = str(pipeline_result.get("mode", "")).lower()
        task_type = self.MODE_TO_TASK_TYPE.get(mode, "effect_apply")

        if not input_topic.strip():
            logger.debug("[AutoBenchmark] no input_topic, skip harvest")
            return []

        trajectory = {
            "task_type": task_type,
            "input": input_topic,
            "expected_output": {},
            "rubrics": f"源自真实运行 run_id={pipeline_result.get('run_id', '?')}",
        }
        tasks = self._builder.generate_from_trajectory(trajectory, split=split)
        if tasks:
            logger.info("[AutoBenchmark] harvested %d task(s) from pipeline run", len(tasks))
        return tasks

    def harvest_from_trajectory(
        self,
        trajectory: Dict[str, Any],
        split: str = "train",
    ) -> List[Dict[str, Any]]:
        """从执行轨迹提炼题目（透传到 BenchmarkBuilder）"""
        return self._builder.generate_from_trajectory(trajectory, split=split)

    # ----------------------------------------------------------------
    #  题目轮换（防老化/防过拟合）
    # ----------------------------------------------------------------

    def refresh_benchmark(
        self,
        task_type: str,
        split: str = "train",
        new_count: int = 2,
    ) -> Dict[str, Any]:
        """轮换评测题目: 生成新题 + 退役最旧的生成题

        Returns:
            {"generated": [...], "retired": [...], "total_active": int}
        """
        # 1. 生成新题（LLM 失败时为空，不影响退役逻辑）
        generated = self._builder.generate_tasks(
            task_type=task_type, count=new_count, split=split
        )

        # 2. 统计生成题数量，超出上限则退役最旧的
        retired = self._retire_overflow(task_type, split)

        total_active = len(self._builder.list_tasks(split, task_type))
        summary = {
            "task_type": task_type,
            "split": split,
            "generated": [t.get("id") for t in generated],
            "retired": [t.get("id") for t in retired],
            "total_active": total_active,
            "timestamp": time.time(),
        }
        logger.info(
            "[AutoBenchmark] refresh %s/%s: +%d -%d active=%d",
            split, task_type, len(generated), len(retired), total_active,
        )
        return summary

    def _retire_overflow(self, task_type: str, split: str) -> List[Dict[str, Any]]:
        """将超出上限的最旧「生成题目」移入 retired/（手动题目永不移除）"""
        split_dir = self._benchmark_dir / split
        generated_files = sorted(split_dir.glob("generated_*.json"))
        retired: List[Dict[str, Any]] = []

        # 统计当前生成题总数
        total_generated = 0
        file_tasks: List[tuple] = []   # (path, tasks)
        for path in generated_files:
            tasks = read_json(path, [])
            if isinstance(tasks, list) and tasks:
                file_tasks.append((path, tasks))
                total_generated += len(tasks)

        if total_generated <= MAX_GENERATED_TASKS_PER_SPLIT:
            return retired

        # 从最旧文件开始退役，直到回到上限
        self._retired_dir.mkdir(parents=True, exist_ok=True)
        overflow = total_generated - MAX_GENERATED_TASKS_PER_SPLIT
        for path, tasks in file_tasks:
            if overflow <= 0:
                break
            take = min(len(tasks), overflow)
            to_retire = tasks[:take]
            remaining = tasks[take:]
            retired.extend(to_retire)
            overflow -= take
            if remaining:
                write_json(path, remaining)
            else:
                # 整个文件退役
                retired_path = self._retired_dir / f"{split}_{path.name}"
                try:
                    path.rename(retired_path)
                except Exception as e:
                    logger.warning("[AutoBenchmark] retire move failed: %s", e)
        return retired

    # ----------------------------------------------------------------
    #  统计
    # ----------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """评测基准库统计（供 Dashboard 展示）"""
        result: Dict[str, Any] = {}
        for split in BenchmarkBuilder.VALID_SPLITS:
            tasks = self._builder.list_tasks(split)
            result[split] = {
                "total": len(tasks),
                "generated": sum(1 for t in tasks if t.get("generated")),
                "by_type": {},
            }
            for t in tasks:
                tt = t.get("task_type", "unknown")
                result[split]["by_type"][tt] = result[split]["by_type"].get(tt, 0) + 1
        return result


# ============================================================================
#  全局单例
# ============================================================================

_global_auto: Optional[AutoBenchmark] = None


def get_auto_benchmark() -> AutoBenchmark:
    """获取全局 AutoBenchmark 单例"""
    global _global_auto
    if _global_auto is None:
        _global_auto = AutoBenchmark()
    return _global_auto
