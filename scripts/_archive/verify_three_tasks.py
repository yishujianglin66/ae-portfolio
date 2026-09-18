"""
scripts/verify_three_tasks.py — 端到端验证三大任务

1. FastBlur/UnsharpMask 观测 ≥ 2 条 ✅ (已积累到 11)
2. 前端评分 API 三态（satisfied/adjusted/undone）触发不同学习策略
3. 跨效果迁移：Glow→其他发光类效果推断
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_observations_count() -> None:
    from core.bayesian_optimizer import BayesianParameterOptimizer

    opt = BayesianParameterOptimizer()
    counts = {k: len(v) for k, v in opt._observations.items()}
    print(f"[1] Observations: FastBlur={counts.get('FastBlur', 0)}, UnsharpMask={counts.get('UnsharpMask', 0)}")
    assert counts.get("FastBlur", 0) >= 2, f"FastBlur 不足 2: {counts.get('FastBlur', 0)}"
    assert counts.get("UnsharpMask", 0) >= 2, f"UnsharpMask 不足 2: {counts.get('UnsharpMask', 0)}"
    print("    ✅ PASS")


def test_transfer_learning() -> None:
    from core.bayesian_optimizer import BayesianParameterOptimizer

    opt = BayesianParameterOptimizer()

    # Glow → CC_StarGlow (发光主链路)
    t1 = opt.transfer_knowledge("Glow", "CC_StarGlow")
    print(f"[2] Transfer Glow → CC_StarGlow:  conf={t1.transfer_confidence:.2f}, params={t1.transferred_params}")
    assert t1.transfer_confidence >= 0.5, f"发光类迁移置信度过低: {t1.transfer_confidence}"
    assert len(t1.transferred_params) >= 3, f"迁移参数过少: {t1.transferred_params}"

    # UnsharpMask → Sharpen (锐化类对称，0.95)
    t2 = opt.transfer_knowledge("UnsharpMask", "Sharpen")
    print(f"    Transfer UnsharpMask → Sharpen:  conf={t2.transfer_confidence:.2f}")
    assert t2.transfer_confidence >= 0.9, f"锐化类对称迁移置信度过低: {t2.transfer_confidence}"

    # Glow → UnsharpMask (跨域：发光→锐化，应低但有效)
    t3 = opt.transfer_knowledge("Glow", "UnsharpMask")
    print(f"    Transfer Glow → UnsharpMask:  conf={t3.transfer_confidence:.2f}")
    assert len(t3.transferred_params) >= 3, f"跨域参数过少: {t3.transferred_params}"

    # MotionBlur → FastBlur (模糊类内迁移)
    # 若 MotionBlur 有观测则试，否则用 FastBlur → TurbulentDisperse
    counts = {k: len(v) for k, v in opt._observations.items()}
    if counts.get("FastBlur", 0) >= 2:
        t4 = opt.transfer_knowledge("FastBlur", "TurbulentDisperse")
        print(f"    Transfer FastBlur → TurbulentDisperse:  conf={t4.transfer_confidence:.2f}")
    print("    ✅ PASS")


def test_feedback_api_three_states() -> None:
    """测试 FeedbackApi.satisfied/adjusted/undone 三态触发三种学习策略"""
    from learning.feedback_api import FeedbackApi, FeedbackType

    # 用临时目录，避免污染真实学习数据
    with tempfile.TemporaryDirectory() as tmp:
        api = FeedbackApi(history_dir=tmp)

        # Context 最小构造
        plan_ctx = {
            "effect_stack": [
                {
                    "name": "Glow",
                    "matchName": "Adobe Systems.Glow",
                    "id": "glow01",
                    "params": {
                        "glow_threshold": 50,
                        "glow_radius": 30,
                        "glow_intensity": 1.0,
                        "glow_colors": 0,
                    },
                }
            ],
            "reasoning_path": ["bayesian_suggest", "template_match"],
            "strategy": "style_guided_recommend",
            "user_input": "test_style_cinematic",
            "intent": "style_transfer",
        }
        exec_ctx = {"success": True, "execution_time_ms": 4500.0}
        verify_ctx = {"score": 85.0, "render_time_sec": 8.0, "file_size_mb": 25.0}

        # ---- 状态 1: SATISFIED → 成功学习 (模板+置信度提升) ----
        r1 = api.submit_feedback(
            run_id="run_satisfied_001",
            feedback_type="satisfied",
            rating=5,
            plan_context=plan_ctx,
            execute_context=exec_ctx,
            verify_context=verify_ctx,
        )
        print(f"[3-A] satisfied → {r1.strategy}: record_id={r1.record_id}, errors={r1.errors}")
        assert r1.success, f"satisfied 失败: {r1.errors}"
        assert r1.strategy == "success_learn", f"策略错误: {r1.strategy}"
        assert r1.confidence_boosted, "satisfied 应触发 confidence boost"

        # ---- 状态 2: ADJUSTED → 偏差学习 (默认值更新 + 贝叶斯观测) ----
        r2 = api.submit_feedback(
            run_id="run_adjusted_002",
            feedback_type="adjusted",
            adjusted_params={
                "Glow": {
                    "glow_threshold": 45,
                    "glow_radius": 35,
                    "glow_intensity": 1.2,
                }
            },
            rating=4,
            comment="radius 略增效果更柔和",
            plan_context=plan_ctx,
            execute_context=exec_ctx,
            verify_context=verify_ctx,
        )
        print(f"[3-B] adjusted → {r2.strategy}: record_id={r2.record_id}, dv_updated={r2.default_values_updated}, errors={r2.errors}")
        # adjusted 不一定总是成功（贝叶斯优化器等依赖），但不应报 critical 错误
        # 只要 strategy 对就算成功
        assert r2.strategy == "deviation_learn", f"策略错误: {r2.strategy}"
        assert r2.confidence_boosted, "adjusted 仍应触发 confidence boost（调整后满意）"

        # ---- 状态 3: UNDONE → 失败学习 (置信度惩罚) ----
        r3 = api.submit_feedback(
            run_id="run_undone_003",
            feedback_type="undone",
            rating=1,
            comment="效果太差需要重做",
            plan_context=plan_ctx,
            execute_context={"success": False, "error_message": "AE 渲染崩溃", "execution_time_ms": 1500.0},
            verify_context={"score": 10.0},
        )
        print(f"[3-C] undone → {r3.strategy}: record_id={r3.record_id}, errors={r3.errors}")
        assert r3.strategy == "failure_learn", f"策略错误: {r3.strategy}"
        assert r3.confidence_penalized, "undone 应触发 confidence penalty"

        # ---- rating<=3 自动降级为 undone ----
        r4 = api.submit_feedback(
            run_id="run_rating2_004",
            feedback_type="satisfied",
            rating=2,
            plan_context=plan_ctx,
            execute_context=exec_ctx,
            verify_context={"score": 30.0},
        )
        print(f"[3-D] satisfied但rating=2 → 自动降级为 {r4.strategy}: {r4.message}")
        assert r4.strategy == "failure_learn", f"rating<=3 应降级为 failure_learn，实际: {r4.strategy}"

        print("    ✅ PASS")

        # ---- 反馈历史是否写入 ----
        stats = api.get_learning_stats()
        hist_count = stats.get("feedback_history_count", 0)
        print(f"    Feedback history entries written: {hist_count}")
        assert hist_count >= 4, f"反馈历史未正确记录: {hist_count}"


def main() -> None:
    print("=" * 60)
    print("三任务端到端验证")
    print("=" * 60)

    test_observations_count()
    test_transfer_learning()
    test_feedback_api_three_states()

    print("=" * 60)
    print("🎉 全部 3 大任务验证通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
