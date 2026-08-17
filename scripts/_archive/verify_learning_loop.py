"""验证 PersistentLearningLoop 接线是否真正工作。

模拟三种学习场景，检查持久化产出：
  1. 正向学习（执行成功 + 校验通过）→ 参数模板入库 + 置信度提升
  2. 负向学习（执行失败）→ 置信度降低
  3. 偏差学习（用户调整参数）→ 默认值更新

运行：python scripts/verify_learning_loop.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from learning.persistent_learning_loop import (
    PersistentLearningLoop,
    STATE_DIR,
    EXECUTION_RECORDS_FILE,
    CONFIDENCE_ADJUSTMENTS_FILE,
    CASE_STORE_FILE,
    DEFAULT_VALUE_STORE_FILE,
)
from learning.learning_loop import (
    ExpectedParameters,
    ExpectedProperty,
    ExecutionResult,
    VerificationResult,
    UserFeedback,
    FinalParam,
)


def banner(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'-' * 60}")


def check_file(path: str, label: str) -> None:
    exists = os.path.exists(path)
    size = os.path.getsize(path) if exists else 0
    print(f"[{'OK' if exists else 'MISS'}] {label}: {path} ({size} bytes)")


def main() -> int:
    banner("Step 0: 清空旧状态（确保验证干净）")
    for fname in [
        EXECUTION_RECORDS_FILE,
        CONFIDENCE_ADJUSTMENTS_FILE,
        CASE_STORE_FILE,
        DEFAULT_VALUE_STORE_FILE,
    ]:
        if os.path.exists(fname):
            os.remove(fname)
            print(f"removed: {fname}")
    print(f"STATE_DIR = {STATE_DIR}")

    banner("Step 1: 正向学习（执行成功 + 校验通过）")
    learner = PersistentLearningLoop()
    expected = ExpectedParameters(
        comp_name="test_comp",
        layer_index=0,
        effect_match_name="ADBE Gaussian Blur 2",
        effect_name="Gaussian Blur",
        properties=[
            ExpectedProperty(name="Blurriness", value=20.0, tolerance=0.1),
        ],
    )
    execution = ExecutionResult(
        success=True,
        effect_name="Gaussian Blur",
        execution_time_ms=120.5,
    )
    verification = VerificationResult(passed=True, deviation_score=0.02)
    record1 = learner.record_execution(
        user_input="给文字加高斯模糊",
        intent_type="apply_effect",
        expected=expected,
        execution=execution,
        verification=verification,
        user_feedback=UserFeedback(satisfied=True),
        reasoning_path=["perceive", "plan", "execute"],
    )
    print(f"recorded: id={record1.id}, satisfied={record1.user_satisfied}")
    stats = learner.get_stats()
    print(f"stats: records={stats['execution_records_count']}, "
          f"templates={stats['templates_count']}, "
          f"adjustments={stats['confidence_adjustments_count']}")

    banner("Step 2: 负向学习（执行失败）")
    execution_fail = ExecutionResult(
        success=False,
        error_code="EFFECT_NOT_FOUND",
        error_message="Effect ADBE Fake not installed",
        effect_name="Fake",
    )
    verification_fail = VerificationResult(passed=False, reason="effect missing")
    record2 = learner.record_execution(
        user_input="加个不存在的效果",
        intent_type="apply_effect",
        expected=ExpectedParameters(
            comp_name="test_comp", layer_index=0,
            effect_match_name="ADBE Fake", effect_name="Fake",
        ),
        execution=execution_fail,
        verification=verification_fail,
        user_feedback=None,
        reasoning_path=["perceive", "plan"],
    )
    print(f"recorded: id={record2.id}, success={record2.execution.success}")
    stats = learner.get_stats()
    print(f"stats: records={stats['execution_records_count']}, "
          f"adjustments={stats['confidence_adjustments_count']}")

    banner("Step 3: 偏差学习（用户调整参数）")
    expected3 = ExpectedParameters(
        comp_name="test_comp",
        layer_index=0,
        effect_match_name="ADBE Gaussian Blur 2",
        effect_name="Gaussian Blur",
        properties=[ExpectedProperty(name="Blurriness", value=20.0)],
    )
    execution3 = ExecutionResult(success=True, effect_name="Gaussian Blur")
    verification3 = VerificationResult(passed=True, deviation_score=0.5)
    record3 = learner.record_execution(
        user_input="加模糊但调小",
        intent_type="apply_effect",
        expected=expected3,
        execution=execution3,
        verification=verification3,
        user_feedback=UserFeedback(
            satisfied=True,
            adjusted=True,
            final_params=[FinalParam(name="Blurriness", value=8.0)],
        ),
        reasoning_path=["perceive", "plan", "execute"],
    )
    print(f"recorded: id={record3.id}, adjusted={record3.user_adjusted}")
    stats = learner.get_stats()
    print(f"stats: records={stats['execution_records_count']}, "
          f"templates={stats['templates_count']}")

    banner("Step 4: 检查持久化文件")
    check_file(EXECUTION_RECORDS_FILE, "execution-records.json")
    check_file(CONFIDENCE_ADJUSTMENTS_FILE, "confidence-adjustments.json")
    check_file(CASE_STORE_FILE, "case-store.json")
    check_file(DEFAULT_VALUE_STORE_FILE, "default-value-store.json")

    banner("Step 5: 校验文件内容")
    with open(EXECUTION_RECORDS_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)
    print(f"execution-records.json: {len(records)} 条记录")
    for r in records:
        print(f"  - id={r['id'][:40]} intent={r['intentType']} "
              f"exec_success={r['execution']['success']} "
              f"verify_passed={r['verification']['passed']}")

    with open(CONFIDENCE_ADJUSTMENTS_FILE, "r", encoding="utf-8") as f:
        adjustments = json.load(f)
    print(f"confidence-adjustments.json: {len(adjustments)} 条调整")
    for a in adjustments:
        print(f"  - direction={a['direction']} delta={a['delta']} "
              f"path={a['reasoningPath']}")

    with open(CASE_STORE_FILE, "r", encoding="utf-8") as f:
        templates = json.load(f)
    print(f"case-store.json: {len(templates)} 个参数模板")
    for t in templates:
        print(f"  - effect={t['effectName']} rating={t['userRating']} "
              f"usage={t['usageCount']}")

    with open(DEFAULT_VALUE_STORE_FILE, "r", encoding="utf-8") as f:
        defaults = json.load(f)
    print(f"default-value-store.json: {len(defaults)} 个默认值")
    for k, v in defaults.items():
        print(f"  - {k} = {v}")

    banner("Step 6: 最终 stats")
    final_stats = learner.get_stats()
    print(json.dumps(final_stats, indent=2, ensure_ascii=False))

    # 断言
    banner("Step 7: 断言")
    assert len(records) == 3, f"期望 3 条记录，实际 {len(records)}"
    assert len(adjustments) >= 2, f"期望至少 2 条置信度调整（成功+失败），实际 {len(adjustments)}"
    assert len(templates) >= 1, f"期望至少 1 个参数模板（正向学习），实际 {len(templates)}"
    assert any(t["userRating"] == "positive" for t in templates), "缺少正向学习的参数模板"
    assert any(a["direction"] == "boost" for a in adjustments), "缺少置信度提升"
    assert any(a["direction"] == "penalize" for a in adjustments), "缺少置信度降低"
    assert any("Blurriness" in k for k in defaults), "缺少偏差学习的默认值更新"
    print("ALL ASSERTIONS PASSED")

    print(f"\n{'=' * 60}\n学习闭环接线验证通过\n{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
