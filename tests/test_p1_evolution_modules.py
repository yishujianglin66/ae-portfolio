"""
tests/test_p1_evolution_modules.py — P1 自进化模块单元测试
==========================================================
覆盖: RubricsScorer / BenchmarkBuilder / OptimizerAgent / EvolutionLoop
全部不依赖真实 LLM（只测解析/校验/启发式/模拟逻辑）
"""
import inspect
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASS = 0
FAIL = 0
RESULTS = []


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}")


# ============================================================
# Test 1: RubricsScorer 解析与加载
# ============================================================
def test_rubrics_scorer():
    print("\n[Test 1: RubricsScorer]")
    from core.evolution.rubrics import RubricsScorer

    with tempfile.TemporaryDirectory() as tmp:
        bench = Path(tmp) / "benchmark"
        (bench / "rubrics").mkdir(parents=True)
        (bench / "rubrics" / "style_transfer.md").write_text("scope级rubrics", encoding="utf-8")
        (bench / "rubrics" / "default.md").write_text("默认rubrics", encoding="utf-8")

        scorer = RubricsScorer(benchmark_dir=str(bench))

        # rubrics 加载优先级: 任务级 > 作用域级 > default
        check("task rubrics 优先", scorer.load_rubrics("style_transfer", "任务rubrics") == "任务rubrics")
        check("scope rubrics 次之", scorer.load_rubrics("style_transfer") == "scope级rubrics")
        check("default 回退", scorer.load_rubrics("unknown_scope") == "默认rubrics")

        # 解析: 标准 JSON
        score, reason = scorer._parse_response('{"score": 82, "reason": "不错"}')
        check("JSON 解析 score", score == 82.0)
        check("JSON 解析 reason", reason == "不错")

        # 解析: 带 markdown 包裹的数字兜底
        parsed = scorer._parse_response("综合得分 75 分")
        check("数字兜底解析", parsed is not None and parsed[0] == 75.0)

        # 解析: 越界裁剪
        parsed = scorer._parse_response('{"score": 150}')
        check("越界裁剪到100", parsed is not None and parsed[0] == 100.0)

        # 解析: 垃圾输入
        check("垃圾输入返回None", scorer._parse_response("abc") is None)
        check("空输入返回None", scorer._parse_response("") is None)


# ============================================================
# Test 2: BenchmarkBuilder 校验与隔离
# ============================================================
def test_benchmark_builder():
    print("\n[Test 2: BenchmarkBuilder]")
    from core.evolution.benchmark_builder import BenchmarkBuilder

    with tempfile.TemporaryDirectory() as tmp:
        bench = Path(tmp) / "benchmark"
        builder = BenchmarkBuilder(benchmark_dir=str(bench))

        # 校验
        good = {"id": "t1", "task_type": "style_transfer", "input": "测试任务"}
        check("合法题目通过校验", builder.validate_task(good))
        check("缺 input 不通过", not builder.validate_task({"id": "t2", "task_type": "x", "input": ""}))

        # 规范化: 空 input 拒绝
        check("空input规范化拒绝", builder._normalize_task({"input": ""}, "x", set(), 0) is None)
        norm = builder._normalize_task({"input": "做特效"}, "style_transfer", set(), 0)
        check("规范化补全id", norm is not None and norm["id"])
        check("规范化task_type", norm["task_type"] == "style_transfer")

        # ID 唯一生成
        ids = set()
        for i in range(3):
            tid = builder._make_unique_id("style_transfer", ids, i)
            check(f"唯一ID #{i}", tid not in ids)
            ids.add(tid)

        # 隔离: test 集已有 ID 不得写入 train
        (bench / "test").mkdir(parents=True, exist_ok=True)
        with open(bench / "test" / "x.json", "w", encoding="utf-8") as f:
            json.dump([{"id": "leak_001", "task_type": "style_transfer", "input": "测试"}], f)
        check("跨集ID被检出", not builder.check_isolation([{"id": "leak_001"}], exclude_split="train"))
        check("无冲突ID通过", builder.check_isolation([{"id": "fresh_001"}], exclude_split="train"))
        check("all_task_ids 收集", "leak_001" in builder.all_task_ids())

        # list_tasks
        with open(bench / "train" / "m.json", "w", encoding="utf-8") as f:
            json.dump([
                {"id": "a1", "task_type": "style_transfer", "input": "1"},
                {"id": "a2", "task_type": "effect_apply", "input": "2"},
            ], f, ensure_ascii=False)
        tasks = builder.list_tasks("train", "style_transfer")
        check("list_tasks 类型过滤", len(tasks) == 1 and tasks[0]["id"] == "a1")

        # generate_from_trajectory 最小实现
        generated = builder.generate_from_trajectory(
            {"task_type": "style_transfer", "input": "从轨迹生成的任务"}, split="train"
        )
        check("轨迹生成题目", len(generated) == 1 and generated[0]["task_type"] == "style_transfer")
        check("轨迹题目落盘", any(t["id"] == generated[0]["id"] for t in builder.list_tasks("train")))


# ============================================================
# Test 3: OptimizerAgent 启发式与安全边界
# ============================================================
def test_optimizer_agent():
    print("\n[Test 3: OptimizerAgent]")
    from core.evolution.optimizer_agent import OptimizerAgent, SAFE_ADJUSTABLE_PARAMS

    with tempfile.TemporaryDirectory() as tmp:
        opt = OptimizerAgent(proposals_dir=str(Path(tmp) / "proposals"))

        # 低分启发式: 应提出 max_quality_iterations 提升
        low_records = [{"run_id": "r1", "score": 55.0, "checks": {"quality_score": 40, "pipeline_success": 100, "output_exists": 0}}]
        prop = opt._propose_heuristic(low_records, {"enable_feedback_loop": False}, "style_transfer")
        check("低分有提案", len(prop.adjustments) > 0)
        check("严重失分开feedback", prop.adjustments.get("enable_feedback_loop") is True)
        check("严重失分开compiler", prop.adjustments.get("use_compiler") is True)

        # 中度失分: 只动一个旋钮
        mid_records = [{"run_id": "r2", "score": 65.0, "checks": {"quality_score": 65, "pipeline_success": 100, "output_exists": 100}}]
        prop = opt._propose_heuristic(mid_records, {}, "style_transfer")
        check("中度失分只动一个", len(prop.adjustments) == 1)
        check("中度失分加迭代", prop.adjustments.get("max_quality_iterations") == 2)

        # 高分无提案
        high_records = [{"run_id": "r3", "score": 85.0, "checks": {"quality_score": 85, "pipeline_success": 100, "output_exists": 100}}]
        prop = opt._propose_heuristic(high_records, {"max_quality_iterations": 5, "use_compiler": True}, "style_transfer")
        check("高分无提案", len(prop.adjustments) == 0)

        # 安全边界: 未知键剔除 + 越界裁剪
        clipped = opt._clip_to_safe_bounds({
            "max_quality_iterations": 99,       # 越界 → 裁剪到5
            "hacker_key": "rm -rf",             # 未知键 → 剔除
            "min_quality_score": 999,           # 越界 → 裁剪到90
            "style_match": 1,                   # bool 开关
        })
        check("越界裁剪iterations", clipped.get("max_quality_iterations") == 5)
        check("未知键剔除", "hacker_key" not in clipped)
        check("越界裁剪min_score", clipped.get("min_quality_score") == 90.0)
        check("bool开关转换", clipped.get("style_match") is True)

        # 白名单内自动批准
        check("白名单自动批准", opt._is_within_safe_bounds({"max_quality_iterations": 3}))
        check("空提案自动批准", opt._is_within_safe_bounds({}))

        # propose_improvements 端到端（LLM 不可用 → 启发式兜底，不抛异常）
        proposal = opt.propose_improvements(mid_records, {}, "style_transfer")
        check("端到端提案不抛异常", proposal is not None)
        check("提案已持久化", opt.load_proposal(proposal.proposal_id) is not None)
        check("提案source标记", proposal.source in ("llm", "heuristic"))


# ============================================================
# Test 4: EvolutionLoop 模拟执行与配置敏感性
# ============================================================
def test_evolution_loop_simulation():
    print("\n[Test 4: EvolutionLoop simulation]")
    from core.evolution.run_evolution import EvolutionLoop
    from core.evolution.evaluator import EvolutionEvaluator
    from core.evolution.optimizer_agent import OptimizerAgent
    from core.evolution.version_manager import VersionManager

    with tempfile.TemporaryDirectory() as tmp:
        bench = Path(tmp) / "benchmark"
        (bench / "results").mkdir(parents=True)
        evaluator = EvolutionEvaluator(benchmark_dir=str(bench), enable_rubrics=False)
        loop = EvolutionLoop(
            evaluator=evaluator,
            optimizer=OptimizerAgent(proposals_dir=str(Path(tmp) / "p")),
            version_manager=VersionManager(data_dir=str(Path(tmp) / "v")),
            task_type="style_transfer",
            execute_real=False,
        )
        task = {"id": "style_sim", "input": "模拟任务"}

        # 确定性: 同配置同任务分数一致
        pr1 = loop._simulate_pipeline_run(task, {}, "r1")
        pr2 = loop._simulate_pipeline_run(task, {}, "r2")
        check("模拟确定性", pr1["quality_score"] == pr2["quality_score"])

        # 配置敏感性: 加迭代/compiler/feedback 提升质量分
        base = loop._simulate_pipeline_run(task, {}, "r3")["quality_score"]
        better = loop._simulate_pipeline_run(task, {
            "max_quality_iterations": 4, "use_compiler": True, "enable_feedback_loop": True,
        }, "r4")["quality_score"]
        check("配置改进提升分数", better > base)
        check("模拟结果结构完整", base is not None and "verify" in pr1["stages"])


# ============================================================
# Test 5: AgenticPlanner evolution 模式
# ============================================================
def test_planner_evolution_mode():
    print("\n[Test 5: AgenticPlanner evolution mode]")
    from core.multi_agent_orchestrator import AgenticPlanner

    check("进化模式指令存在", "进化模式" in AgenticPlanner._EVOLUTION_PROMPT_SUFFIX)
    check("进化模式要求质量验收", "QUALITY_REVIEW" in AgenticPlanner._EVOLUTION_PROMPT_SUFFIX)

    sig = inspect.signature(AgenticPlanner.plan)
    check("plan 支持 mode 参数", "mode" in sig.parameters)
    check("mode 默认 default", sig.parameters["mode"].default == "default")


if __name__ == "__main__":
    print("=" * 60)
    print("P1 自进化模块单元测试")
    print("=" * 60)

    test_rubrics_scorer()
    test_benchmark_builder()
    test_optimizer_agent()
    test_evolution_loop_simulation()
    test_planner_evolution_mode()

    print("\n" + "=" * 60)
    print(f"PASS: {PASS}  FAIL: {FAIL}")
    if FAIL == 0:
        print("[RESULT] P1 Evolution Modules: PASS")
    else:
        print("[RESULT] P1 Evolution Modules: FAIL")
        sys.exit(1)
