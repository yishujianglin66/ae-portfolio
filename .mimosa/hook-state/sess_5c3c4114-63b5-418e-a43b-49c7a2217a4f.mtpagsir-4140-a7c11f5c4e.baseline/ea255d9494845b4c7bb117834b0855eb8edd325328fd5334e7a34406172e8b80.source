"""P1 反馈闭环验证: verify→execute 回环机制

验证目标:
  1. _check_quality_gate 在分数不达标时正确触发 retry
  2. _adjust_params_for_retry 正确调整转场/效果/段时长参数
  3. 优化后分数达标时不触发 retry
  4. 重试调整参数被 _run_execute_real_mix 正确消费
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.unified_pipeline import UnifiedPipeline, PipelineConfig, StageResult, StageStatus


def test_quality_gate_triggers_retry():
    """测试: 分数不达标 + 优化失败 → 触发 retry"""
    print("=" * 60)
    print("Test 1: Quality gate triggers retry when score < threshold")
    print("=" * 60)

    config = PipelineConfig(
        input_topic="feedback_loop_test",
        output_dir="output/test_feedback",
        enable_feedback_loop=True,
        min_quality_score=70.0,
        max_quality_iterations=3,
    )
    pipeline = UnifiedPipeline(config)
    pipeline._iteration = 0

    # 模拟 verify 结果: 分数不达标, 优化已执行但仍不达标
    pipeline._results["verify"] = StageResult(
        stage="verify",
        status=StageStatus.DONE,
        data={
            "verified": False,
            "score": 45.0,
            "final_score": 52.0,  # 优化后仍 < 70
            "optimization_applied": True,
            "optimization_passes": 3,
            "recommendations": ["increase_contrast", "add_sharpen"],
        }
    )
    # 模拟 plan 结果 (供 _adjust_params_for_retry 修改)
    pipeline._results["plan"] = StageResult(
        stage="plan",
        status=StageStatus.DONE,
        data={
            "transition_plan": [
                {"from": 0, "to": 1, "type": "dissolve", "duration": 0.5},
                {"from": 1, "to": 2, "type": "fade", "duration": 0.5},
            ],
            "effect_stack": [
                {"name": "color_grade", "params": {"contrast": 1.2, "saturation": 1.3}},
            ],
        }
    )

    should_retry = pipeline._check_quality_gate()

    checks = []
    checks.append(("should_retry == True", should_retry is True))

    # 验证 retry adjustments 被创建
    adj = pipeline._results.get("_retry_adjustments")
    checks.append(("_retry_adjustments exists", adj is not None))
    if adj:
        checks.append(("adj has new_transitions", "new_transitions" in adj.data))
        checks.append(("adj has effects_boosted", adj.data.get("effects_boosted") is True))
        checks.append(("adj has seg_dur_boost", adj.data.get("segment_duration_boost", 0) > 1.0))

    # 验证 plan 中的转场被修改
    plan_data = pipeline._results["plan"].data
    new_types = [t["type"] for t in plan_data.get("transition_plan", [])]
    checks.append(("transitions changed", new_types != ["dissolve", "fade"]))

    # 验证效果参数被增强
    eff_params = plan_data["effect_stack"][0]["params"]
    checks.append(("contrast boosted > 1.2", eff_params["contrast"] > 1.2))
    checks.append(("saturation boosted > 1.3", eff_params["saturation"] > 1.3))

    print("\nResults:")
    all_pass = True
    for desc, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {desc}")

    return all_pass


def test_quality_gate_skips_when_passed():
    """测试: 优化后分数达标 → 不触发 retry"""
    print("\n" + "=" * 60)
    print("Test 2: Quality gate skips retry when optimization succeeded")
    print("=" * 60)

    config = PipelineConfig(
        input_topic="feedback_loop_test",
        output_dir="output/test_feedback",
        enable_feedback_loop=True,
        min_quality_score=70.0,
        max_quality_iterations=3,
    )
    pipeline = UnifiedPipeline(config)
    pipeline._iteration = 0

    # 模拟 verify 结果: 优化后分数达标
    pipeline._results["verify"] = StageResult(
        stage="verify",
        status=StageStatus.DONE,
        data={
            "verified": True,
            "score": 75.0,
            "final_score": 75.0,
            "optimization_applied": True,
            "optimization_passes": 2,
        }
    )

    should_retry = pipeline._check_quality_gate()

    checks = []
    checks.append(("should_retry == False", should_retry is False))

    print("\nResults:")
    all_pass = True
    for desc, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {desc}")

    return all_pass


def test_quality_gate_max_iterations():
    """测试: 达到最大迭代次数 → 不触发 retry"""
    print("\n" + "=" * 60)
    print("Test 3: Quality gate respects max_iterations limit")
    print("=" * 60)

    config = PipelineConfig(
        input_topic="feedback_loop_test",
        output_dir="output/test_feedback",
        enable_feedback_loop=True,
        min_quality_score=70.0,
        max_quality_iterations=3,
    )
    pipeline = UnifiedPipeline(config)
    pipeline._iteration = 2  # 最后一轮 (0-indexed, max=3)

    # 模拟 verify 结果: 分数不达标, 无优化
    pipeline._results["verify"] = StageResult(
        stage="verify",
        status=StageStatus.DONE,
        data={
            "verified": False,
            "score": 40.0,
            "optimization_applied": False,
        }
    )

    should_retry = pipeline._check_quality_gate()

    checks = []
    checks.append(("should_retry == False (max iter)", should_retry is False))

    print("\nResults:")
    all_pass = True
    for desc, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {desc}")

    return all_pass


def main():
    results = []
    results.append(("Test 1: retry on low score", test_quality_gate_triggers_retry()))
    results.append(("Test 2: skip on pass", test_quality_gate_skips_when_passed()))
    results.append(("Test 3: max iterations", test_quality_gate_max_iterations()))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {name}")

    print(f"\n[RESULT] P1 Feedback Loop: {'PASS' if all_pass else 'FAIL'}")
    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
