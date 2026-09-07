"""
core/evolution/run_evolution.py — 评测驱动的进化主循环 (P1)
=============================================================

借鉴 PenguinHarness 的多智能体自进化闭环:
    评测(Evaluator) → 分析失分(Optimizer) → 修改配置 → 再评测 → 严格对比(accept/rollback)

用法:
    python -m core.evolution.run_evolution --task style_transfer --iterations 3
    python -m core.evolution.run_evolution --task style_transfer --iterations 2 --execute
    python -m core.evolution.run_evolution --task style_transfer --iterations 1 --dry-run

模式说明:
    - 默认 dry-run: 用确定性模拟执行验证闭环机制（不依赖 AE/Bridge，零成本）
    - --execute: 真实运行 UnifiedPipeline（需要环境支持，耗时较长）

防过拟合机制:
    - Optimizer 只看训练集(train)结果
    - 每轮结束在验证集(val)上盲测，对比训练集分数
    - 测试集(test)仅最终验收使用（本循环不读取）

成本约束:
    单轮进化 token 总量受 COST_LIMITS["evolution_cycle"] 约束，超限熔断
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.evolution.evaluator import EvolutionEvaluator
from core.evolution.optimizer_agent import OptimizerAgent, get_optimizer_agent
from core.evolution.protocol import (
    COST_LIMITS,
    EvolutionMessage,
    EvolutionMsgType,
    append_jsonl,
    write_json,
)
from core.evolution.version_manager import VersionManager, get_version_manager

logger = logging.getLogger(__name__)

# 项目根目录（core/evolution/run_evolution.py → 上三级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 每 N 轮在验证集盲测一次
BLIND_TEST_EVERY = 5


# ============================================================================
#  进化主循环
# ============================================================================

class EvolutionLoop:
    """评测驱动的多轮进化循环"""

    def __init__(
        self,
        evaluator: EvolutionEvaluator,
        optimizer: OptimizerAgent,
        version_manager: VersionManager,
        task_type: str,
        execute_real: bool = False,
        messages_log: str = str(PROJECT_ROOT / "data" / "evolution" / "messages.jsonl"),
    ):
        self._evaluator = evaluator
        self._optimizer = optimizer
        self._vm = version_manager
        self._task_type = task_type
        self._execute_real = execute_real
        self._messages_log = Path(messages_log)
        self._cycle_tokens = 0
        self._cycle_cost = 0.0
        # P2: 渲染引擎使用分布追踪（ae_render/aerender/real_mix/ffmpeg...）
        self._engine_usage: Dict[str, int] = {}

    # ----------------------------------------------------------------
    #  主入口
    # ----------------------------------------------------------------

    def run(self, iterations: int = 3, blind_test: bool = True) -> Dict[str, Any]:
        """运行进化循环

        Args:
            iterations: 迭代轮数
            blind_test: 结束后是否在验证集盲测

        Returns:
            循环总结报告
        """
        scope = self._task_type
        train_tasks = self._evaluator.load_benchmark_tasks("train", self._task_type)
        if not train_tasks:
            logger.error("[EvolutionLoop] no train tasks for task_type=%s", self._task_type)
            return {"status": "no_tasks", "task_type": self._task_type}

        working_config: Dict[str, Any] = {}
        history: List[Dict[str, Any]] = []
        start = time.time()

        for it in range(iterations):
            print(f"\n=== Evolution iteration {it + 1}/{iterations} (scope={scope}) ===")

            # 成本熔断
            if self._cycle_tokens > COST_LIMITS["evolution_cycle"]:
                print(f"[!] cycle token budget exceeded ({self._cycle_tokens}), stopping")
                break

            # 1. 在训练集上执行 + 评测
            iter_records = self._run_iteration(train_tasks, scope, working_config, it)
            history.extend(iter_records)

            if not iter_records:
                print("[!] iteration produced no evaluation records, stopping")
                break

            avg = sum(r["score"] for r in iter_records) / len(iter_records)
            print(f"    train avg score: {avg:.1f} ({len(iter_records)} tasks)")

            # 2. Optimizer 分析失分 → 提案（只看训练集；P2: 注入知识库经验）
            experience_context = ""
            try:
                from core.evolution.knowledge_sink import get_knowledge_sink
                experience_context = get_knowledge_sink().experience_text(scope, limit=5)
            except Exception:
                pass
            proposal = self._optimizer.propose_improvements(
                eval_records=iter_records,
                current_config=working_config,
                scope=scope,
                experience_context=experience_context,
            )
            self._cycle_tokens += proposal.tokens_used
            self._cycle_cost += proposal.cost_usd

            if proposal.needs_human_review:
                print(f"    [!] proposal needs human review: {proposal.adjustments}")

            # 3. 应用自动批准的调整（人工确认项跳过）
            applied_adj: Dict[str, Any] = {}
            if proposal.auto_approved and proposal.adjustments:
                working_config.update(proposal.adjustments)
                applied_adj = dict(proposal.adjustments)
                print(f"    applied adjustments: {proposal.adjustments}")
            elif not proposal.adjustments:
                print("    no adjustments proposed")

            # 4. P2: 知识沉淀 — 本轮决策提炼为经验（供后续轮次消费）
            try:
                from core.evolution.knowledge_sink import get_knowledge_sink
                last_decision = iter_records[0].get("decision", "") if iter_records else ""
                get_knowledge_sink().record_lesson(
                    scope=scope,
                    decision=last_decision or "hold",
                    score=avg,
                    adjustments=applied_adj,
                    run_id=f"evo_{scope}_{it + 1}",
                )
            except Exception:
                pass

            self._log_message(EvolutionMessage(
                msg_type=EvolutionMsgType.OPTIMIZE.value,
                run_id=f"iter_{it + 1}",
                scope=scope,
                payload=proposal.to_dict(),
                tokens_used=proposal.tokens_used,
                cost_usd=proposal.cost_usd,
            ))

        # 4. 验证集盲测（防过拟合）
        val_summary: Dict[str, Any] = {}
        if blind_test:
            val_summary = self._blind_test(scope, working_config)

        report = {
            "task_type": self._task_type,
            "iterations": iterations,
            "execute_real": self._execute_real,
            "duration_sec": round(time.time() - start, 2),
            "train_history": history,
            "validation": val_summary,
            "current_version": self._vm.get_current_version(scope),
            "cycle_tokens_used": self._cycle_tokens,
            "cycle_cost_usd": round(self._cycle_cost, 6),
            "engine_usage": dict(self._engine_usage),
            "timestamp": time.time(),
        }
        self._save_report(report)
        self._print_summary(report)
        return report

    # ----------------------------------------------------------------
    #  单轮迭代: 执行 → 评测 → 版本决策
    # ----------------------------------------------------------------

    def _run_iteration(
        self,
        tasks: List[Dict[str, Any]],
        scope: str,
        config: Dict[str, Any],
        iteration: int,
    ) -> List[Dict[str, Any]]:
        """单轮迭代: 全部任务执行+评测 → 按轮均分做一次版本决策

        设计: 版本对比以「轮」为单位（均分），避免单题波动触发误回退。
        """
        records: List[Dict[str, Any]] = []
        eval_details: List[Any] = []

        for task in tasks:
            task_id = str(task.get("id", "unknown"))
            run_id = f"evo_{scope}_{iteration + 1}_{task_id}"

            # 执行（dry-run 模拟 or 真实管线）
            if self._execute_real:
                pr = self._execute_real_pipeline(task, config, run_id)
            else:
                pr = self._simulate_pipeline_run(task, config, run_id)
            if pr is None:
                continue

            # 独立评测
            eval_result = self._evaluator.evaluate_pipeline_result(pr, scope=scope)
            self._cycle_tokens += eval_result.tokens_used
            self._cycle_cost += eval_result.cost_usd

            # P2: 追踪真实渲染引擎分布（优先 execution_mode，能区分 ae_render/ae_bridge）
            engine = str(pr.get("execution_mode") or pr.get("render_engine") or "")
            if engine:
                self._engine_usage[engine] = self._engine_usage.get(engine, 0) + 1

            records.append({
                "task_id": task_id,
                "run_id": run_id,
                "iteration": iteration + 1,
                "score": eval_result.score,
                "deterministic": eval_result.deterministic_score,
                "rubric": eval_result.rubric_score,
                "checks": eval_result.checks,
                "notes": eval_result.notes,
                "render_engine": str(pr.get("render_engine", "")),
                "execution_mode": str(pr.get("execution_mode", "")),
                "decision": "",      # 轮结束后统一填写
                "version_id": "",
            })
            eval_details.append(eval_result)
            print(f"    [{task_id}] score={eval_result.score:.1f}")

        if not records:
            return records

        # 按轮均分做一次版本决策（严格更高才接受）
        avg_score = sum(r["score"] for r in records) / len(records)
        version_id = self._vm.create_version(
            scope=scope,
            config_snapshot={"config": config, "iteration": iteration + 1},
            source_run_id=f"evo_{scope}_{iteration + 1}",
            parent_version=self._vm.get_current_version(scope),
        )
        decision = self._vm.record_and_decide(
            version_id=version_id,
            score=avg_score,
            run_id=f"evo_{scope}_{iteration + 1}",
            breakdown={
                "per_task": {
                    r["task_id"]: r["score"] for r in records
                },
                "task_count": len(records),
            },
        )
        for r in records:
            r["decision"] = decision.decision
            r["version_id"] = version_id
        print(
            f"    iteration avg={avg_score:.1f} best={decision.best_score:.1f} "
            f"→ {decision.decision} ({version_id})"
        )
        return records

    # ----------------------------------------------------------------
    #  执行器
    # ----------------------------------------------------------------

    def _simulate_pipeline_run(
        self, task: Dict[str, Any], config: Dict[str, Any], run_id: str
    ) -> Dict[str, Any]:
        """dry-run 模拟执行 — 确定性伪结果，用于验证闭环机制

        模拟规则（对 Optimizer 可改进的敏感项）:
        - 基线分由任务 ID 哈希确定（稳定可复现）
        - max_quality_iterations / use_compiler / enable_feedback_loop 可提升质量分
        """
        seed = int(hashlib.md5(str(task.get("id", "")).encode("utf-8")).hexdigest()[:6], 16)
        base_quality = 45 + (seed % 30)  # 45-74

        quality = float(base_quality)
        if config.get("max_quality_iterations"):
            quality += min(15.0, 3.0 * (int(config["max_quality_iterations"]) - 1))
        if config.get("use_compiler"):
            quality += 8.0
        if config.get("enable_feedback_loop"):
            quality += 4.0
        quality = max(0.0, min(100.0, quality))

        return {
            "run_id": run_id,
            "status": "success",
            "mode": "text_topic",
            "output_path": "",
            "project_path": "",
            "total_duration_sec": 1.0,
            "quality_score": quality,
            "iterations": int(config.get("max_quality_iterations", 1) or 1),
            "stages": {
                "perceive": {"status": "done", "data": {}, "error": ""},
                "execute": {"status": "done", "data": {}, "error": ""},
                "render": {"status": "done", "data": {}, "error": ""},
                "verify": {"status": "done", "data": {"score": quality}, "error": ""},
                "learn": {"status": "done", "data": {}, "error": ""},
            },
            "_simulated": True,
            "_task_input": str(task.get("input", "")),
            # P3-C: 供评测器消费的题目信息
            "_task_id": str(task.get("id", "")),
            "_expected_output": task.get("expected_output", {}) or {},
        }

    def _execute_real_pipeline(
        self, task: Dict[str, Any], config: Dict[str, Any], run_id: str
    ) -> Optional[Dict[str, Any]]:
        """真实运行 UnifiedPipeline（--execute 模式）"""
        try:
            from pipeline.unified_pipeline import PipelineConfig, UnifiedPipeline

            field_names = set(PipelineConfig.__dataclass_fields__.keys())  # type: ignore[attr-defined]
            kwargs = {k: v for k, v in config.items() if k in field_names}
            kwargs.update({
                "input_topic": str(task.get("input", "")),
                "output_dir": str(Path("output") / "evolution" / run_id),
                "enable_evolution": False,   # 防止双重记录（本循环自行记录）
                "auto_render": False,        # 评测循环默认不真渲染
            })
            pipeline = UnifiedPipeline(PipelineConfig(**kwargs))
            result = pipeline.run_all()
            pr = result.to_dict()
            # P3-C: 注入题目信息供评测器消费 expected_output 断言
            pr["_task_id"] = str(task.get("id", ""))
            pr["_expected_output"] = task.get("expected_output", {}) or {}
            return pr
        except Exception as e:
            logger.error("[EvolutionLoop] real pipeline execution failed: %s", e)
            return None

    # ----------------------------------------------------------------
    #  验证集盲测（防过拟合）
    # ----------------------------------------------------------------

    def _blind_test(self, scope: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """在验证集上盲测 — Optimizer 不可见，用于确认改进是否真实"""
        val_tasks = self._evaluator.load_benchmark_tasks("val", self._task_type)
        if not val_tasks:
            return {"status": "no_val_tasks"}
        print(f"\n--- Blind test on validation set ({len(val_tasks)} tasks) ---")
        scores: List[float] = []
        for task in val_tasks:
            task_id = str(task.get("id", "unknown"))
            run_id = f"evo_blind_{scope}_{task_id}"
            if self._execute_real:
                pr = self._execute_real_pipeline(task, config, run_id)
            else:
                pr = self._simulate_pipeline_run(task, config, run_id)
            if pr is None:
                continue
            eval_result = self._evaluator.evaluate_pipeline_result(pr, scope=f"{scope}_val")
            self._cycle_tokens += eval_result.tokens_used
            self._cycle_cost += eval_result.cost_usd
            scores.append(eval_result.score)
            print(f"    [val:{task_id}] score={eval_result.score:.1f}")

        if not scores:
            return {"status": "all_failed"}

        avg_val = sum(scores) / len(scores)
        train_records = [
            r for r in self._vm.history(scope) if r.get("status") == "accepted"
        ]
        summary = {
            "status": "ok",
            "val_tasks": len(val_tasks),
            "val_avg_score": round(avg_val, 2),
            "accepted_versions": len(train_records),
        }
        # 过拟合告警: 验证集显著低于训练基线
        best_train = max((v.get("best_score", 0) for v in train_records), default=0.0)
        if best_train > 0 and avg_val < best_train - 10.0:
            summary["overfitting_warning"] = (
                f"val({avg_val:.1f}) 显著低于 train best({best_train:.1f})，疑似过拟合"
            )
            print(f"    [!] {summary['overfitting_warning']}")
        return summary

    # ----------------------------------------------------------------
    #  持久化与日志
    # ----------------------------------------------------------------

    def _save_report(self, report: Dict[str, Any]) -> None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        results_dir = PROJECT_ROOT / "data" / "benchmark" / "results"
        write_json(results_dir / f"evolution_run_{ts}.json", report)
        append_jsonl(PROJECT_ROOT / "data" / "evolution" / "cycle_history.jsonl", {
            "task_type": report["task_type"],
            "iterations": report["iterations"],
            "cycle_tokens_used": report["cycle_tokens_used"],
            "cycle_cost_usd": report["cycle_cost_usd"],
            "timestamp": report["timestamp"],
        })

    def _log_message(self, msg: EvolutionMessage) -> None:
        try:
            append_jsonl(self._messages_log, msg.to_dict())
        except Exception as e:
            logger.debug("[EvolutionLoop] message log failed: %s", e)

    def _print_summary(self, report: Dict[str, Any]) -> None:
        print("\n" + "=" * 60)
        print(f"Evolution summary: task_type={report['task_type']}")
        history = report.get("train_history", [])
        if history:
            first = history[0]["score"]
            last_avg = sum(r["score"] for r in history) / len(history)
            print(f"  runs={len(history)} first_score={first:.1f} avg_score={last_avg:.1f}")
            accepted = sum(1 for r in history if r["decision"] == "accept")
            print(f"  accepted={accepted} rollback={len(history) - accepted}")
        val = report.get("validation", {})
        if val.get("status") == "ok":
            print(f"  validation avg={val.get('val_avg_score', 0):.1f}")
        print(
            f"  tokens={report['cycle_tokens_used']} "
            f"cost=${report['cycle_cost_usd']:.4f} "
            f"duration={report['duration_sec']}s"
        )
        engines = report.get("engine_usage", {})
        if engines:
            print(f"  render engines: {engines}")
            if not any(k.startswith("ae") for k in engines):
                print("  [hint] no AE render used (bridge listener not loaded? fallback engines only)")
        print("=" * 60)


# ============================================================================
#  CLI 入口
# ============================================================================

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="core.evolution.run_evolution",
        description="评测驱动的自进化循环 (P1)",
    )
    parser.add_argument("--task", default="style_transfer", help="任务类型 (默认 style_transfer)")
    parser.add_argument("--iterations", type=int, default=3, help="迭代轮数 (默认 3)")
    parser.add_argument("--execute", action="store_true", help="真实运行 UnifiedPipeline (默认 dry-run 模拟)")
    parser.add_argument("--no-rubrics", action="store_true", help="禁用 LLM Rubrics 评分 (仅确定性指标)")
    parser.add_argument("--no-blind-test", action="store_true", help="跳过验证集盲测")
    parser.add_argument("--benchmark-dir", default="data/benchmark", help="评测基准目录")
    parser.add_argument("--versions-dir", default="data/versions", help="版本管理目录")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    evaluator = EvolutionEvaluator(
        benchmark_dir=args.benchmark_dir,
        enable_rubrics=not args.no_rubrics,
    )
    loop = EvolutionLoop(
        evaluator=evaluator,
        optimizer=get_optimizer_agent(),
        version_manager=get_version_manager(data_dir=args.versions_dir),
        task_type=args.task,
        execute_real=args.execute,
    )
    report = loop.run(iterations=args.iterations, blind_test=not args.no_blind_test)
    return 0 if report.get("status") != "no_tasks" else 1


if __name__ == "__main__":
    sys.exit(main())
