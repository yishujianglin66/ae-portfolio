"""
core/evolution/benchmark_builder.py — Benchmark Builder 自动出题 (P1)
=======================================================================

借鉴 PenguinHarness 的 Benchmark Builder:
1. 用 LLM 自动生成评测题目（替代手动编写）
2. 训练/验证/测试集隔离 — 生成时校验 ID 不跨集重复（防偷看答案）
3. 从历史轨迹生成题目（P2 预留接口 generate_from_trajectory）
4. 文件即真相 — 题目写入 data/benchmark/{split}/generated_{ts}.json

用法:
    from core.evolution.benchmark_builder import get_benchmark_builder

    builder = get_benchmark_builder()
    tasks = builder.generate_tasks(task_type="style_transfer", count=3, split="train")

降级策略:
    LLM 不可用 → 返回空列表（不影响已有手动题目）
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.evolution.protocol import append_jsonl, read_json, write_json, within_cost_limit

logger = logging.getLogger(__name__)


# ============================================================================
#  Benchmark Builder
# ============================================================================

class BenchmarkBuilder:
    """评测基准自动构建器

    职责:
    1. generate_tasks — LLM 生成评测题目并校验后落盘
    2. validate_task — 结构校验（必填字段 + ID 唯一性）
    3. check_isolation — 训练/验证/测试集 ID 隔离校验
    4. list_tasks / all_task_ids — 查询已有题目
    """

    DEFAULT_BENCHMARK_DIR = "data/benchmark"
    VALID_SPLITS = ("train", "val", "test")
    REQUIRED_FIELDS = ("id", "task_type", "input")

    def __init__(self, benchmark_dir: str = DEFAULT_BENCHMARK_DIR):
        self._benchmark_dir = Path(benchmark_dir)
        for split in self.VALID_SPLITS:
            (self._benchmark_dir / split).mkdir(parents=True, exist_ok=True)
        self._gen_log = self._benchmark_dir / "generation_log.jsonl"

    # ----------------------------------------------------------------
    #  主入口: LLM 生成题目
    # ----------------------------------------------------------------

    def generate_tasks(
        self,
        task_type: str,
        count: int = 3,
        split: str = "train",
        seed_topics: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """用 LLM 自动生成评测题目

        Args:
            task_type: 题目类型（如 style_transfer / effect_apply / color_grade）
            count: 生成数量（1-10）
            split: 目标数据集（train/val/test）
            seed_topics: 可选的主题种子（引导多样性）

        Returns:
            通过校验并落盘的题目列表；LLM 失败返回空列表
        """
        if split not in self.VALID_SPLITS:
            raise ValueError(f"invalid split: {split}, must be one of {self.VALID_SPLITS}")
        count = max(1, min(10, int(count)))

        existing_ids = self.all_task_ids()
        prompt = self._build_generation_prompt(task_type, count, seed_topics)

        raw_tasks: List[Dict[str, Any]] = []
        try:
            raw_tasks = self._call_llm(prompt)
        except Exception as e:
            logger.warning("[BenchmarkBuilder] LLM generation failed: %s", e)
            return []

        # 校验 + 去重 + 分配唯一 ID
        accepted: List[Dict[str, Any]] = []
        for i, task in enumerate(raw_tasks):
            if not isinstance(task, dict):
                continue
            task = self._normalize_task(task, task_type, existing_ids, index=i)
            if task is None:
                continue
            if not self.validate_task(task):
                continue
            if task["id"] in existing_ids:
                task["id"] = self._make_unique_id(task_type, existing_ids)
            existing_ids.add(task["id"])
            task["generated"] = True
            task["generated_at"] = time.time()
            accepted.append(task)
            if len(accepted) >= count:
                break

        if not accepted:
            logger.warning("[BenchmarkBuilder] no valid tasks generated for %s", task_type)
            return []

        # 隔离校验（防偷看答案）
        if not self.check_isolation(accepted, exclude_split=split):
            logger.error("[BenchmarkBuilder] isolation violation, aborting write")
            return []

        self._save_tasks(accepted, split, task_type)
        append_jsonl(self._gen_log, {
            "task_type": task_type,
            "split": split,
            "count": len(accepted),
            "task_ids": [t["id"] for t in accepted],
            "timestamp": time.time(),
        })
        logger.info(
            "[BenchmarkBuilder] generated %d %s tasks → split=%s",
            len(accepted), task_type, split,
        )
        return accepted

    # ----------------------------------------------------------------
    #  LLM 调用
    # ----------------------------------------------------------------

    def _build_generation_prompt(
        self, task_type: str, count: int, seed_topics: Optional[List[str]]
    ) -> str:
        seeds = f"\n可选主题参考: {', '.join(seed_topics)}" if seed_topics else ""
        return (
            f"你是视频制作管线的评测基准出题专家。请为任务类型 '{task_type}' 生成 "
            f"{count} 个高质量评测题目。\n\n"
            "要求:\n"
            "1. 每个题目包含具体的任务描述(input)，描述要清晰、可执行、无歧义\n"
            "2. 预期输出(expected_output)写成可检查的 JSON 键值对（如色彩倾向/对比度/特效存在性）\n"
            "3. rubrics 写明隐藏评分要点（检查哪些视觉/结构特征）\n"
            "4. 题目之间要有多样性，覆盖不同风格/难度\n"
            "5. 面向 AE(After Effects) 视频特效制作场景"
            f"{seeds}\n\n"
            "只输出严格 JSON 数组，每个元素格式:\n"
            '{"task_type": "...", "input": "...", "expected_output": {...}, '
            '"rubrics": "...", "tags": ["..."]}\n'
            "不要输出 id 字段（系统自动分配），不要 markdown，不要任何额外文字。"
        )

    def _call_llm(self, prompt: str) -> List[Dict[str, Any]]:
        """调用 LLM 生成题目（带成本熔断）"""
        import asyncio
        from core.llm_gateway import LLMGateway, TaskType

        gateway = LLMGateway()
        coro = gateway.chat_with_routing(
            message=prompt,
            task_type=TaskType.GENERAL,
            system_prompt="你是严格的 JSON 输出器，只输出 JSON 数组。",
            temperature=0.8,
            max_tokens=4096,
        )
        try:
            resp = asyncio.run(coro)
        except RuntimeError:
            import concurrent.futures

            def _worker():
                return asyncio.run(gateway.chat_with_routing(
                    message=prompt,
                    task_type=TaskType.GENERAL,
                    system_prompt="你是严格的 JSON 输出器，只输出 JSON 数组。",
                    temperature=0.8,
                    max_tokens=4096,
                ))

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                resp = pool.submit(_worker).result(timeout=180)

        if resp is None or not getattr(resp, "success", False):
            return []
        tokens = getattr(resp, "tokens_input", 0) + getattr(resp, "tokens_output", 0)
        if not within_cost_limit("single_optimization", tokens):
            logger.warning("[BenchmarkBuilder] generation tokens exceeded limit")
        return self._parse_tasks_json(getattr(resp, "content", "") or "")

    def _parse_tasks_json(self, content: str) -> List[Dict[str, Any]]:
        """从 LLM 输出中解析 JSON 数组（容忍 markdown 包裹）"""
        if not content:
            return []
        content = content.strip()
        # 去除 markdown 代码块
        fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", content, re.DOTALL)
        if fence:
            content = fence.group(1)
        try:
            data = json.loads(content)
            return data if isinstance(data, list) else []
        except Exception:
            pass
        # 提取首个 JSON 数组子串
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, list) else []
            except Exception:
                pass
        return []

    # ----------------------------------------------------------------
    #  校验与隔离
    # ----------------------------------------------------------------

    def _normalize_task(
        self,
        task: Dict[str, Any],
        task_type: str,
        existing_ids: set,
        index: int,
    ) -> Optional[Dict[str, Any]]:
        """规范化单个题目（补全字段）"""
        input_text = str(task.get("input", "")).strip()
        if not input_text:
            return None
        tid = str(task.get("id", "")).strip()
        if not tid or tid in existing_ids:
            tid = self._make_unique_id(task_type, existing_ids, index)
        expected = task.get("expected_output", {})
        if not isinstance(expected, dict):
            expected = {}
        tags = task.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        return {
            "id": tid,
            "task_type": str(task.get("task_type", "") or task_type),
            "input": input_text,
            "expected_output": expected,
            "rubrics": str(task.get("rubrics", "")).strip(),
            "tags": [str(t) for t in tags],
        }

    def validate_task(self, task: Dict[str, Any]) -> bool:
        """结构校验：必填字段非空"""
        for field_name in self.REQUIRED_FIELDS:
            if not str(task.get(field_name, "")).strip():
                return False
        return True

    def _make_unique_id(self, task_type: str, existing_ids: set, index: int = 0) -> str:
        prefix = task_type.split("_")[0] if task_type else "task"
        ts = time.strftime("%y%m%d%H%M%S")
        candidate = f"{prefix}_gen_{ts}_{index:02d}"
        n = 0
        while candidate in existing_ids:
            n += 1
            candidate = f"{prefix}_gen_{ts}_{index:02d}_{n}"
        return candidate

    def all_task_ids(self, split: str = "") -> set:
        """收集指定 split（默认全部）的已有题目 ID"""
        ids = set()
        splits = [split] if split else list(self.VALID_SPLITS)
        for s in splits:
            split_dir = self._benchmark_dir / s
            if not split_dir.exists():
                continue
            for json_file in split_dir.glob("*.json"):
                data = read_json(json_file, [])
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("id"):
                            ids.add(str(item["id"]))
        return ids

    def check_isolation(
        self,
        new_tasks: List[Dict[str, Any]],
        exclude_split: str = "train",
    ) -> bool:
        """训练/验证/测试集隔离校验 — 新题目 ID 不得出现在其他 split

        Args:
            new_tasks: 待写入的新题目
            exclude_split: 目标 split（自身不算冲突）

        Returns:
            True = 无冲突
        """
        other_ids = set()
        for s in self.VALID_SPLITS:
            if s != exclude_split:
                other_ids |= self.all_task_ids(split=s)
        for task in new_tasks:
            if str(task.get("id", "")) in other_ids:
                logger.warning(
                    "[BenchmarkBuilder] task id %s leaks across splits", task.get("id")
                )
                return False
        return True

    # ----------------------------------------------------------------
    #  查询与落盘
    # ----------------------------------------------------------------

    def list_tasks(self, split: str = "train", task_type: str = "") -> List[Dict[str, Any]]:
        """列出某 split 的全部题目（含手动 + 生成）"""
        split_dir = self._benchmark_dir / split
        if not split_dir.exists():
            return []
        tasks: List[Dict[str, Any]] = []
        for json_file in sorted(split_dir.glob("*.json")):
            data = read_json(json_file, [])
            if not isinstance(data, list):
                continue
            for item in data:
                if isinstance(item, dict) and (
                    not task_type or item.get("task_type") == task_type
                ):
                    tasks.append(item)
        return tasks

    def _save_tasks(
        self, tasks: List[Dict[str, Any]], split: str, task_type: str
    ) -> Path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        safe_type = re.sub(r"[^\w-]", "_", task_type) or "tasks"
        path = self._benchmark_dir / split / f"generated_{safe_type}_{ts}.json"
        write_json(path, tasks)
        return path

    # ----------------------------------------------------------------
    #  P2 预留: 从历史轨迹自动生成题目
    # ----------------------------------------------------------------

    def generate_from_trajectory(
        self,
        trajectory: Dict[str, Any],
        split: str = "train",
    ) -> List[Dict[str, Any]]:
        """从历史执行轨迹提炼新题目（P2 阶段实现完整逻辑）

        当前为最小实现：轨迹含 task_type + input 时直接转题目。
        """
        task_type = str(trajectory.get("task_type", "") or trajectory.get("scope", ""))
        input_text = str(trajectory.get("input", "") or trajectory.get("input_topic", ""))
        if not task_type or not input_text:
            return []
        task = {
            "id": self._make_unique_id(task_type, self.all_task_ids()),
            "task_type": task_type,
            "input": input_text,
            "expected_output": trajectory.get("expected_output", {}) or {},
            "rubrics": str(trajectory.get("rubrics", "")),
            "tags": ["from_trajectory"],
            "generated": True,
            "generated_at": time.time(),
        }
        if not self.validate_task(task):
            return []
        if not self.check_isolation([task], exclude_split=split):
            return []
        self._save_tasks([task], split, task_type)
        return [task]


# ============================================================================
#  全局单例
# ============================================================================

_global_builder: Optional[BenchmarkBuilder] = None


def get_benchmark_builder(
    benchmark_dir: str = BenchmarkBuilder.DEFAULT_BENCHMARK_DIR,
) -> BenchmarkBuilder:
    """获取全局 BenchmarkBuilder 单例"""
    global _global_builder
    if _global_builder is None:
        _global_builder = BenchmarkBuilder(benchmark_dir=benchmark_dir)
    return _global_builder
