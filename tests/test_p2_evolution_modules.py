"""
tests/test_p2_evolution_modules.py — P2 自进化模块验收测试
===========================================================

覆盖:
1. AgentAssetManager — Prompt 外置/小 diff 自动应用/大 diff 人工确认/快照恢复
2. KnowledgeSink — 知识沉淀/去重/经验消费
3. AutoBenchmark — 轨迹出题/题目轮换统计
4. Agent 真实执行路径开关（默认 fallback 不破坏既有行为）
5. Evolution API 路由（文件即真相，空数据返回空结构）
"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RESULTS = {"pass": 0, "fail": 0}


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        RESULTS["pass"] += 1
        print(f"  [PASS] {name}")
    else:
        RESULTS["fail"] += 1
        print(f"  [FAIL] {name} {detail}")


# ============================================================
# Test 1: AgentAssetManager
# ============================================================
def test_agent_assets():
    print("\n--- Test 1: AgentAssetManager ---")
    from core.evolution.agent_assets import AgentAssetManager

    with tempfile.TemporaryDirectory() as tmp:
        mgr = AgentAssetManager(prompts_dir=tmp)

        # 1.1 内置兜底
        prompt = mgr.load_prompt("style_analysis")
        check("内置 Prompt 兜底", "风格" in prompt and len(prompt) > 20)
        check("prompt_source=builtin", mgr.prompt_source("style_analysis") == "builtin")

        # 1.2 小 diff 自动应用（追加一句话）
        new_text = prompt + "\n补充: 输出必须包含置信度。"
        r = mgr.update_prompt("style_analysis", new_text)
        check("小 diff 自动应用", r.applied and not r.needs_human_review,
              f"diff={r.diff_ratio}")
        check("文件已写入", mgr.prompt_source("style_analysis") == "file")
        check("重新加载生效", "置信度" in mgr.load_prompt("style_analysis"))

        # 1.3 大 diff → 人工确认
        r2 = mgr.update_prompt("style_analysis", "完全不同的全新提示词，与原文无关。")
        check("大 diff 不自动应用", not r2.applied and r2.needs_human_review,
              f"diff={r2.diff_ratio}")
        check("待审文件已暂存", len(mgr.list_pending()) == 1)
        check("当前 Prompt 未变", "置信度" in mgr.load_prompt("style_analysis"))

        # 1.4 人工批准后应用
        r3 = mgr.approve_pending("style_analysis")
        check("批准后应用", r3.applied and "全新提示词" in mgr.load_prompt("style_analysis"))
        check("待审清空", len(mgr.list_pending()) == 0)

        # 1.5 快照/恢复
        snap = mgr.snapshot_assets()
        check("快照含全部角色", set(snap.keys()) >= {"style_analysis", "code_generation",
                                                       "param_optim", "quality_review"})
        mgr.update_prompt("quality_review", snap["quality_review"] + " 追加。", force=True)
        restored = mgr.restore_assets(snap)
        check("快照恢复", restored >= 4 and mgr.load_prompt("quality_review") == snap["quality_review"])


# ============================================================
# Test 2: KnowledgeSink
# ============================================================
def test_knowledge_sink():
    print("\n--- Test 2: KnowledgeSink ---")
    from core.evolution.knowledge_sink import KnowledgeSink

    with tempfile.TemporaryDirectory() as tmp:
        sink = KnowledgeSink(data_dir=tmp)

        e1 = sink.record_lesson(
            scope="style_transfer", decision="accept", score=72.5,
            adjustments={"max_quality_iterations": 3}, run_id="r1",
        )
        check("accept 经验写入", e1["lesson"].startswith("[style_transfer]") and "被接受" in e1["lesson"])

        e2 = sink.record_lesson(
            scope="style_transfer", decision="rollback", score=58.0,
            adjustments={"min_quality_score": 90}, run_id="r2",
        )
        check("rollback 经验写入", "被回退" in e2["lesson"])
        check("rollback 价值更高", e2["value"] > e1["value"])

        # 去重: 同 scope+adjustments+decision
        before = sink.stats()["total_lessons"]
        sink.record_lesson(scope="style_transfer", decision="rollback", score=57.0,
                           adjustments={"min_quality_score": 90}, run_id="r3")
        check("重复经验被跳过", sink.stats()["total_lessons"] == before)

        # 消费
        lessons = sink.load_relevant_experience("style_transfer", limit=5)
        check("经验可消费", len(lessons) == 2)
        text = sink.experience_text("style_transfer")
        check("经验文本注入格式", text.startswith("【历史进化经验") and "被回退" in text)
        check("无匹配 scope 返回空", sink.experience_text("nonexistent") == "")

        # 统计文件（Dashboard 数据源）
        stats = sink.stats()
        check("统计正确", stats["total_lessons"] == 2
              and stats["by_decision"].get("accept") == 1
              and stats["by_decision"].get("rollback") == 1)
        stats_file = Path(tmp) / "knowledge_stats.json"
        check("knowledge_stats.json 存在", stats_file.exists())


# ============================================================
# Test 3: AutoBenchmark
# ============================================================
def test_auto_benchmark():
    print("\n--- Test 3: AutoBenchmark ---")
    from core.evolution.auto_benchmark import AutoBenchmark
    from core.evolution.benchmark_builder import BenchmarkBuilder

    with tempfile.TemporaryDirectory() as tmp:
        builder = BenchmarkBuilder(benchmark_dir=tmp)
        ab = AutoBenchmark(builder=builder)

        # 3.1 从管线运行提炼题目
        tasks = ab.harvest_from_pipeline_run({
            "run_id": "run_p2_test",
            "mode": "reference_video",
            "input_topic": "赛博朋克城市夜景",
        }, split="train")
        check("轨迹出题成功", len(tasks) >= 1)
        check("题目映射 style_transfer", tasks and tasks[0].get("task_type") == "style_transfer")

        # 3.2 无 input_topic 时跳过
        none_tasks = ab.harvest_from_pipeline_run({"mode": "mixed"}, split="train")
        check("无主题跳过", none_tasks == [])

        # 3.3 已落盘可列出
        listed = builder.list_tasks("train", "style_transfer")
        check("题目已落盘", len(listed) >= 1)

        # 3.4 stats
        stats = ab.stats()
        check("stats 含三分集", set(stats.keys()) == {"train", "val", "test"})
        check("train 计数正确", stats["train"]["total"] >= 1)


# ============================================================
# Test 4: Agent 执行路径开关
# ============================================================
def test_agent_execution_paths():
    print("\n--- Test 4: Agent 真实执行路径开关 ---")
    import asyncio
    import os
    from core.style_transfer_agents import (
        QualityReviewAgent, StyleAnalysisAgent, TaskDefinition,
        _task_llm_enabled, _load_agent_prompt,
    )

    # 默认关闭
    os.environ.pop("AE_AGENTS_USE_LLM", None)
    task = TaskDefinition(
        task_id="t1", task_type="style_transfer",
        description="测试", input_data={},
    )

    check("默认不走 LLM", not _task_llm_enabled(task))
    task.input_data["_use_llm"] = True
    check("任务级开关生效", _task_llm_enabled(task))

    prompt, source = _load_agent_prompt("quality_review")
    check("外置 Prompt 可加载", len(prompt) > 0 and source in ("file", "builtin"))

    # QualityReviewAgent 兜底路径不变（确定性规则仍工作）
    agent = QualityReviewAgent()
    t2 = TaskDefinition(
        task_id="t2", task_type="quality_review",
        description="测试", input_data={"jsx_code": "var x = 1;" * 3 + " eval('bad')"},
    )
    result = asyncio.run(agent.execute(t2))
    check("兜底执行成功", result.success or result.error == "")
    check("检出 eval 问题", any("eval" in i for i in result.data.get("issues", [])))
    check("execution_path=fallback", result.metadata.get("execution_path") == "fallback")

    # StyleAnalysisAgent 兜底仍可用
    sa = StyleAnalysisAgent()
    t3 = TaskDefinition(
        task_id="t3", task_type="style_analysis",
        description="测试", input_data={"reference_video": "test.mp4"},
    )
    r3 = asyncio.run(sa.execute(t3))
    check("StyleAnalysis 兜底可用", r3.metadata.get("execution_path") == "fallback")


# ============================================================
# Test 5: Evolution API 路由
# ============================================================
def test_evolution_routes():
    print("\n--- Test 5: Evolution API 路由 ---")
    import asyncio
    import importlib.util
    # 直载模块文件，避开 api/__init__.py 的全量 app 加载
    route_file = (Path(__file__).resolve().parent.parent
                  / "puppet-automation" / "src" / "api" / "evolution_routes.py")
    try:
        spec = importlib.util.spec_from_file_location("evolution_routes", route_file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        evolution_summary, evolution_cost, evolution_knowledge = (
            mod.evolution_summary, mod.evolution_cost, mod.evolution_knowledge,
        )
    except Exception as e:
        check("evolution_routes 可导入", False, str(e))
        return
    check("evolution_routes 可导入", True)

    summary = asyncio.run(evolution_summary())
    check("summary 结构完整", all(k in summary for k in
          ("score_trend", "decisions", "cost", "versions", "knowledge", "avg_score")))
    check("decisions 统计字段", all(k in summary["decisions"] for k in
          ("total", "accept", "rollback", "rollback_rate")))
    check("cost 观测字段", all(k in summary["cost"] for k in
          ("total_tokens", "total_cost_usd", "evolution_cycles")))

    cost = asyncio.run(evolution_cost(limit=10))
    check("cost 端点可用", "total_tokens" in cost and "cycles" in cost)

    knowledge = asyncio.run(evolution_knowledge(limit=10))
    check("knowledge 端点可用", "lessons" in knowledge and "stats" in knowledge)


# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("P2 Evolution Modules Test")
    print("=" * 60)
    test_agent_assets()
    test_knowledge_sink()
    test_auto_benchmark()
    test_agent_execution_paths()
    test_evolution_routes()
    print()
    print("=" * 60)
    print(f"PASS: {RESULTS['pass']}  FAIL: {RESULTS['fail']}")
    if RESULTS["fail"] == 0:
        print("[RESULT] P2 Evolution Modules: PASS")
    else:
        print("[RESULT] P2 Evolution Modules: FAIL")
        sys.exit(1)
