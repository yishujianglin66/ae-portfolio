"""
tests/test_p0_evolution_loop.py — P0 自进化闭环验证
====================================================

验证目标（对应计划 P0 验收标准）:
1. 运行一次管线 → 自动产生评分并保存到 data/benchmark/results/
2. 第二次运行 → 能对比上一次的分数并决定接受/回退
3. 严格更高才接受（score > best + epsilon），否则回退
4. 决策日志可审计（decision_log.jsonl）
5. 连续回退计数正确

运行方式:
    python tests/test_p0_evolution_loop.py
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def make_pipeline_result(run_id: str, status: str, quality_score: float,
                         mode: str = "text_topic") -> dict:
    """构造模拟管线结果（PipelineResult.to_dict() 等效格式）"""
    return {
        "run_id": run_id,
        "status": status,
        "mode": mode,
        "output_path": "",
        "project_path": "",
        "total_duration_sec": 120.5,
        "quality_score": quality_score,
        "iterations": 1,
        "stages": {
            "verify": {
                "status": "done",
                "data": {"score": quality_score, "verified": quality_score >= 60},
                "error": "",
            },
            "render": {
                "status": "done",
                "data": {"output_path": ""},
                "error": "",
            },
        },
    }


def build_runner(tmp_dir: Path, enable_rubrics: bool = False):
    """构建使用临时目录的 EvolutionRunner（隔离测试，不污染真实数据）"""
    from core.evolution.evaluator import EvolutionEvaluator
    from core.evolution.runner import EvolutionRunner
    from core.evolution.version_manager import VersionManager

    evaluator = EvolutionEvaluator(
        benchmark_dir=str(PROJECT_ROOT / "data" / "benchmark"),
        results_dir=str(tmp_dir / "benchmark_results"),
        enable_rubrics=enable_rubrics,  # 测试默认关闭 LLM 通道（确定性验证）
    )
    vm = VersionManager(data_dir=str(tmp_dir / "versions"), epsilon=0.5)
    return EvolutionRunner(
        evaluator=evaluator,
        version_manager=vm,
        messages_log=str(tmp_dir / "messages.jsonl"),
    )


def test_baseline_accepted():
    """Test 1: 首次运行建立基线 → accept"""
    tmp = Path(tempfile.mkdtemp(prefix="evo_test1_"))
    try:
        runner = build_runner(tmp)
        pr = make_pipeline_result("run_001", "success", 65.0)
        decision = runner.record_pipeline_run(pr)

        checks = []
        checks.append(("decision not None", decision is not None))
        checks.append(("decision == accept (baseline)", decision.decision == "accept"))
        checks.append(("reason == no_baseline", "no_baseline" in decision.reason))
        # 综合分 = 0.6*质检分(65) + 0.25*成功(100) + 0.15*输出存在(0) = 64
        checks.append(("score ≈ 64 (weighted)", abs(decision.score - 64.0) < 0.5))

        # 评测结果已持久化
        results_dir = tmp / "benchmark_results"
        eval_files = list(results_dir.glob("eval_*.json"))
        checks.append(("eval result persisted", len(eval_files) >= 1))

        history = runner._vm.history(scope="text_topic")
        checks.append(("version created", len(history) == 1))
        checks.append(("version accepted", history[0]["status"] == "accepted"))
        return checks
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_strictly_higher_accepted():
    """Test 2: 严格更高分 → accept"""
    tmp = Path(tempfile.mkdtemp(prefix="evo_test2_"))
    try:
        runner = build_runner(tmp)
        d1 = runner.record_pipeline_run(make_pipeline_result("run_001", "success", 65.0))
        d2 = runner.record_pipeline_run(make_pipeline_result("run_002", "success", 72.0))

        checks = []
        checks.append(("run1 accepted", d1.decision == "accept"))
        checks.append(("run2 accepted (strictly higher)", d2.decision == "accept"))
        checks.append(("current version updated",
                       runner._vm.get_current_version("text_topic") == d2.version_id))
        return checks
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_not_higher_rollback():
    """Test 3: 分数持平/下降 → rollback（PenguinHarness 核心机制）"""
    tmp = Path(tempfile.mkdtemp(prefix="evo_test3_"))
    try:
        runner = build_runner(tmp)
        d1 = runner.record_pipeline_run(make_pipeline_result("run_001", "success", 70.0))
        # 70.2 - 70.0 = 0.2 < epsilon(0.5) → 视为持平 → rollback
        d2 = runner.record_pipeline_run(make_pipeline_result("run_002", "success", 70.2))
        d3 = runner.record_pipeline_run(make_pipeline_result("run_003", "success", 60.0))

        checks = []
        checks.append(("run1 accepted", d1.decision == "accept"))
        checks.append(("run2 rollback (margin < epsilon)", d2.decision == "rollback"))
        checks.append(("run3 rollback (lower)", d3.decision == "rollback"))
        checks.append(("consecutive rollbacks == 2", d3.consecutive_rollbacks == 2))
        checks.append(("current stays at v001",
                       runner._vm.get_current_version("text_topic") == d1.version_id))
        return checks
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_decision_log_audit():
    """Test 4: 决策日志可审计"""
    tmp = Path(tempfile.mkdtemp(prefix="evo_test4_"))
    try:
        runner = build_runner(tmp)
        runner.record_pipeline_run(make_pipeline_result("run_001", "success", 70.0))
        runner.record_pipeline_run(make_pipeline_result("run_002", "success", 60.0))

        log_path = tmp / "versions" / "decision_log.jsonl"
        checks = []
        checks.append(("decision log exists", log_path.exists()))

        records = []
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))

        checks.append(("2 decisions logged", len(records) == 2))
        checks.append(("first is accept", records[0]["decision"] == "accept"))
        checks.append(("second is rollback", records[1]["decision"] == "rollback"))
        checks.append(("scope recorded", records[0].get("scope") == "text_topic"))
        return checks
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_deterministic_scoring():
    """Test 5: 确定性评分分项正确"""
    tmp = Path(tempfile.mkdtemp(prefix="evo_test5_"))
    try:
        runner = build_runner(tmp)
        # 成功 + 80分质检 + 无输出文件
        # det = 0.6*80 + 0.25*100 + 0.15*0 = 48+25+0 = 73
        pr = make_pipeline_result("run_001", "success", 80.0)
        decision = runner.record_pipeline_run(pr)

        checks = []
        checks.append(("score ≈ 73", abs(decision.score - 73.0) < 0.5))

        # 失败管线 → 低分
        pr_fail = make_pipeline_result("run_002", "failed", 0.0)
        eval_fail = runner._evaluator.evaluate_pipeline_result(pr_fail, scope="text_topic")
        # det = 0.6*0 + 0.25*0 + 0.15*0 = 0
        checks.append(("failed pipeline score ≈ 0", eval_fail.score < 5.0))
        checks.append(("failed not passed", not eval_fail.passed))
        return checks
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_benchmark_tasks_loaded():
    """Test 6: 评测基准题目加载 + 训练/测试集隔离"""
    tmp = Path(tempfile.mkdtemp(prefix="evo_test6_"))
    try:
        runner = build_runner(tmp)
        train = runner._evaluator.load_benchmark_tasks(split="train")
        val = runner._evaluator.load_benchmark_tasks(split="val")
        test = runner._evaluator.load_benchmark_tasks(split="test")

        checks = []
        checks.append(("train tasks >= 5", len(train) >= 5))
        checks.append(("val tasks >= 2", len(val) >= 2))
        checks.append(("test tasks >= 2", len(test) >= 2))

        # 训练/测试集 ID 不重叠（防止偷看答案）
        train_ids = {t["id"] for t in train}
        test_ids = {t["id"] for t in test}
        checks.append(("no overlap train/test", len(train_ids & test_ids) == 0))

        # 按类型过滤
        style_only = runner._evaluator.load_benchmark_tasks(
            split="train", task_type="style_transfer"
        )
        checks.append(("type filter works",
                       all(t["task_type"] == "style_transfer" for t in style_only)))
        return checks
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    tests = [
        ("Test 1: baseline accepted", test_baseline_accepted),
        ("Test 2: strictly higher accepted", test_strictly_higher_accepted),
        ("Test 3: not higher rollback", test_not_higher_rollback),
        ("Test 4: decision log audit", test_decision_log_audit),
        ("Test 5: deterministic scoring", test_deterministic_scoring),
        ("Test 6: benchmark tasks loaded", test_benchmark_tasks_loaded),
    ]

    print("=" * 60)
    print("P0 自进化闭环验证")
    print("=" * 60)

    summary = []
    for name, fn in tests:
        print(f"\n[{name}]")
        try:
            checks = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            checks = [(f"exception: {e}", False)]

        all_ok = True
        for desc, ok in checks:
            status = "PASS" if ok else "FAIL"
            if not ok:
                all_ok = False
            print(f"  [{status}] {desc}")
        summary.append((name, all_ok))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, ok in summary:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {name}")

    print(f"\n[RESULT] P0 Evolution Loop: {'PASS' if all_pass else 'FAIL'}")
    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
