"""scripts/verify_learning_real_signals.py - 学习系统真实信号验收

验收标准(全部满足才算 D1-D4 修复成功):
  A1 质量分布有区分度: AutoQualityEvaluator 对不同视频产生不同分(差>5.0)
  A2 反馈管线畅通: record_director_feedback 能写入 director_v23 记录
  A3 知识积累恢复: evolution_knowledge.jsonl 行数增长(基线 3)
  A4 TS 提取腿: default-value-store 条目数增长(基线 4)
"""
import asyncio
import json
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def check(name: str, ok: bool, detail: str) -> bool:
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {name}: {detail}")
    return ok


def _make_video(path: Path, src: str, duration: float = 2.0):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi",
         "-i", f"{src}=size=320x240:rate=10:duration={duration}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )


def check_a1_quality_discrimination() -> bool:
    """A1: AutoQualityEvaluator 对不同内容产生不同分数"""
    from core.self_evolution_engine import AutoQualityEvaluator

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        dynamic = td / "dynamic.mp4"
        static = td / "static.mp4"
        _make_video(dynamic, "testsrc2")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "quiet", "-f", "lavfi",
             "-i", "color=c=black:size=320x240:rate=10:duration=2",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(static)],
            check=True,
        )
        ev = AutoQualityEvaluator()
        loop = asyncio.new_event_loop()
        try:
            s_dyn = loop.run_until_complete(
                ev.evaluate(str(dynamic), {}, {"target_resolution": (320, 240)}, {})
            )
            s_sta = loop.run_until_complete(
                ev.evaluate(str(static), {}, {"target_resolution": (320, 240)}, {})
            )
        finally:
            loop.close()

        diff = abs(s_dyn.overall_score - s_sta.overall_score)
        vis_diff = s_dyn.visual_quality - s_sta.visual_quality
        return check(
            "A1 质量区分度",
            diff > 5.0,
            f"动态={s_dyn.overall_score:.1f} vs 黑屏={s_sta.overall_score:.1f}, "
            f"Δ={diff:.1f} (要求>5.0); 视觉分 Δ={vis_diff:.1f}",
        )


def check_a2_feedback_pipeline() -> bool:
    """A2: director_feedback_hook 能写入 director_v23 记录"""
    from ai.director_feedback_hook import record_director_feedback

    with tempfile.TemporaryDirectory() as td:
        store = Path(td) / "param_feedback.json"
        store.write_text(json.dumps({"records": []}), encoding="utf-8")

        import os
        old = os.environ.get("PARAM_FEEDBACK_PATH")
        os.environ["PARAM_FEEDBACK_PATH"] = str(store)
        try:
            record_director_feedback({
                "run_id": "acceptance_test_001",
                "quality": 75.0,
                "ramps": [{"type": "speed_ramp", "peak_speed": 2.5, "beat_aligned": True}],
                "style": "高燃",
            })
        finally:
            if old is None:
                os.environ.pop("PARAM_FEEDBACK_PATH", None)
            else:
                os.environ["PARAM_FEEDBACK_PATH"] = old

        data = json.loads(store.read_text(encoding="utf-8"))
        real = [r for r in data["records"]
                if r.get("metadata", {}).get("source") == "director_v23"]
        return check(
            "A2 反馈管线",
            len(real) > 0,
            f"写入 {len(real)} 条 director_v23 记录",
        )


def check_a3_knowledge_growth() -> bool:
    """A3: evolution_knowledge.jsonl 行数增长"""
    try:
        from core.paths import self_evolution_dir as _paths_evo_dir
        kl = Path(_paths_evo_dir()) / "evolution_knowledge.jsonl"
    except ImportError:
        kl = ROOT / "data" / "self_evolution" / "evolution_knowledge.jsonl"
    n = len(kl.read_text(encoding="utf-8").splitlines()) if kl.exists() else 0
    return check("A3 知识积累", n > 3, f"evolution_knowledge.jsonl {n} 行 (基线 3)")


def check_a4_ts_consolidate() -> bool:
    """A4: TS default-value-store 条目数增长"""
    import os
    appdata = os.environ.get("APPDATA", "")
    dvs_path = Path(appdata) / "AE-Knowledge-Vault" / "learning-state" / "default-value-store.json"
    if not dvs_path.exists():
        return check("A4 TS提取腿", False, "default-value-store.json 不存在")
    data = json.loads(dvs_path.read_text(encoding="utf-8"))
    n = sum(len(v) for v in data.values()) if isinstance(data, dict) else len(data)
    return check("A4 TS提取腿", n > 4, f"default-value-store {n} 条目 (基线 4)")


def check_a5_evolution_state_diversity() -> bool:
    """A5: evolution_state 中 quality 分布有区分度(非全常数)"""
    try:
        from core.paths import self_evolution_dir as _paths_evo_dir
        state_file = Path(_paths_evo_dir()) / "evolution_state.json"
    except ImportError:
        state_file = ROOT / "data" / "self_evolution" / "evolution_state.json"
    if not state_file.exists():
        return check("A5 质量分布", False, "evolution_state.json 不存在")
    state = json.loads(state_file.read_text(encoding="utf-8"))
    qs = [r.get("quality") for r in state.get("review_history", [])
          if isinstance(r.get("quality"), (int, float))]
    if len(qs) < 2:
        return check("A5 质量分布", False, f"仅 {len(qs)} 条记录")
    sigma = statistics.pstdev(qs)
    unique = len(set(qs))
    return check(
        "A5 质量分布",
        unique > 3 or sigma > 1.0,
        f"{len(qs)} 条, {unique} 个不同值, σ={sigma:.2f}",
    )


def main():
    print("=" * 60)
    print("学习系统真实信号验收 (D1-D4)")
    print("=" * 60)

    results = []
    results.append(check_a1_quality_discrimination())
    results.append(check_a2_feedback_pipeline())
    results.append(check_a3_knowledge_growth())
    results.append(check_a4_ts_consolidate())
    results.append(check_a5_evolution_state_diversity())

    ok = all(results)
    passed = sum(results)
    total = len(results)
    verdict = "ALL PASS" if ok else "FAIL"
    print(f"\n{'=' * 60}")
    print(f"验收结果: {verdict}  ({passed}/{total})")
    print(f"{'=' * 60}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
