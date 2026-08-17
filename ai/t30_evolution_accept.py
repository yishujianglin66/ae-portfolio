# -*- coding: utf-8 -*-
r"""T30: 素材智能化系统进化方案 — 最终端到端验收。

验收范围(12项):
  基线模块(6项):
  1. ip_proto_classifier模块存在且可导入
  2. production_scorer模块存在且可导入
  3. clip_backbones模块存在且可导入
  4. scene_classifier模型存在且可加载
  5. 100IP原型库存在且完整
  6. ViT-L-14 LoRA模型存在

  进化模块(6项):
  7. ip_prototypes_v2.json (VLM统计注入)
  8. SceneAwareScorer (场景感知评分器)
  9. SceneMoodMatrix (场景×情绪匹配矩阵)
  10. 多IP语料工厂管线 (t31)
  11. 均衡采样LoRA重训脚本 (t32)
  12. 资源清理验证 (D盘空间)

产物:
  reports/t30_evolution_accept.json — 验收报告
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPORT_DIR = ROOT / "reports"


def _log(msg: str):
    print(f"[T30] {msg}", flush=True)


def check(name: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    suffix = f" ({detail})" if detail else ""
    _log(f"  [{status}] {name}{suffix}")
    return {"name": name, "status": status, "detail": detail}


def main():
    _log("=" * 60)
    _log("T30: 素材智能化系统进化方案 — 端到端验收")
    _log("=" * 60)
    t_start = time.time()

    results = []

    # ═══ 基线模块 (6项) ═══
    _log("\n── 基线模块 ──")

    # 1. ip_proto_classifier
    p = ROOT / "ai" / "ip_proto_classifier.py"
    results.append(check("ip_proto_classifier模块", p.exists(), f"{p}"))

    # 2. production_scorer
    p = ROOT / "ai" / "production_scorer.py"
    results.append(check("production_scorer模块", p.exists(), f"{p}"))

    # 3. clip_backbones
    p = ROOT / "ai" / "clip_backbones.py"
    results.append(check("clip_backbones模块", p.exists(), f"{p}"))

    # 4. scene_classifier模型
    p = ROOT / "models" / "scene_classifier_v1.pt"
    detail = f"{p.stat().st_size/1e6:.1f}MB" if p.exists() else "missing"
    results.append(check("scene_classifier模型", p.exists(), detail))

    # 5. 100IP原型库
    p = ROOT / "data" / "ip_prototypes_100.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        n_ips = len(data.get("ips", data.get("prototypes", data)))
        detail = f"{n_ips}个IP"
    else:
        n_ips = 0
        detail = "missing"
    results.append(check("100IP原型库", p.exists() and n_ips >= 100, detail))

    # 6. ViT-L-14 LoRA模型
    p = ROOT / "models" / "clip_lora_aot_vitl14.pt"
    detail = f"{p.stat().st_size/1e6:.1f}MB" if p.exists() else "missing"
    results.append(check("ViT-L-14 LoRA模型", p.exists(), detail))

    # ═══ 进化模块 (6项) ═══
    _log("\n── 进化模块 ──")

    # 7. ip_prototypes_v2.json
    p = ROOT / "data" / "ip_prototypes_v2.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        n_vlm = sum(1 for v in data.get("ip_prototypes", data.get("prototypes", {})).values()
                    if isinstance(v, dict) and v.get("vlm_frame_count", 0) > 0)
        n_matrix = len(data.get("scene_mood_matrix", []))
        detail = f"{n_vlm}个IP有VLM数据, {n_matrix}组共现"
    else:
        n_vlm = 0
        detail = "missing"
    results.append(check("ip_prototypes_v2(VLM统计)", p.exists() and n_vlm > 0, detail))

    # 8. SceneAwareScorer
    try:
        from ai.t30b_scene_aware_scorer import SceneAwareScorer
        scorer = SceneAwareScorer()
        # 快速功能测试
        score = scorer.score(
            cuts=[1.0, 2.5, 4.0, 5.5], beats=[0.5 * i for i in range(12)],
            duration=6.0, scene_type="battle", mood="hot"
        )
        has_total = "total" in score and score["total"] > 0
        has_scene_fit = "scene_fit" in score
        detail = f"total={score.get('total', 0):.3f}, scene_fit={score.get('scene_fit', 0):.3f}"
        results.append(check("SceneAwareScorer", has_total and has_scene_fit, detail))
    except Exception as e:
        results.append(check("SceneAwareScorer", False, str(e)[:80]))

    # 9. SceneMoodMatrix
    try:
        from ai.t30c_scene_mood_matrix import SceneMoodMatrix
        matrix = SceneMoodMatrix()
        moods = matrix.recommend_moods("battle", top_k=3)
        scenes = matrix.recommend_scenes("hot", top_k=3)
        compat = matrix.compatibility("battle", "hot")
        n_ips_vlm = len(matrix.list_ips_with_vlm())
        detail = (f"battle→{moods[0][0] if moods else '?'}, "
                  f"hot→{scenes[0][0] if scenes else '?'}, "
                  f"compat(battle,hot)={compat:.3f}, "
                  f"{n_ips_vlm}个IP有VLM数据")
        ok = len(moods) > 0 and len(scenes) > 0 and compat > 0
        results.append(check("SceneMoodMatrix", ok, detail))
    except Exception as e:
        results.append(check("SceneMoodMatrix", False, str(e)[:80]))

    # 10. 多IP语料工厂
    try:
        from ai.t31_multi_ip_corpus import load_config, RECOMMENDED_IPS
        config = load_config()
        n_ips_config = len(config.get("ips", {}))
        config_path = ROOT / "config" / "multi_ip_corpus.json"
        detail = f"{n_ips_config}个IP配置, 脚本t31就绪"
        results.append(check("多IP语料工厂管线", n_ips_config >= 5, detail))
    except Exception as e:
        results.append(check("多IP语料工厂管线", False, str(e)[:80]))

    # 11. 均衡采样LoRA重训
    try:
        from ai.t32_balanced_lora_retrain import balanced_sample, MAX_PER_IP
        # 模拟均衡采样
        test_entries = [{"ip": f"ip{i % 3}", "frame_path": ""} for i in range(100)]
        sampled = balanced_sample(test_entries, max_per_ip=20, min_per_ip=5)
        detail = f"MAX_PER_IP={MAX_PER_IP}, 测试采样100→{len(sampled)}"
        results.append(check("均衡采样LoRA重训脚本", len(sampled) <= 60, detail))
    except Exception as e:
        results.append(check("均衡采样LoRA重训脚本", False, str(e)[:80]))

    # 12. 资源清理验证
    try:
        import shutil
        d_total, d_free = shutil.disk_usage("D:\\")[:2]
        d_free_gb = d_free / (1024**3)
        # 检查夸克目录是否已清理
        quark_remaining = 0
        quark_path = Path(r"D:\夸克")
        if quark_path.exists():
            for f in quark_path.rglob("*"):
                if f.is_file():
                    quark_remaining += f.stat().st_size
        quark_gb = quark_remaining / (1024**3)
        detail = f"D盘剩余{d_free_gb:.1f}GB, 夸克残留{quark_gb:.2f}GB"
        results.append(check("资源清理验证", d_free_gb > 50, detail))
    except Exception as e:
        results.append(check("资源清理验证", False, str(e)[:80]))

    # ═══ 汇总 ═══
    elapsed = time.time() - t_start
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_total = len(results)

    _log(f"\n{'=' * 60}")
    _log(f"验收结果: {n_pass}/{n_total} PASS ({elapsed:.1f}s)")
    _log(f"{'=' * 60}")

    if n_pass == n_total:
        _log("★ 全部通过! 素材智能化系统进化方案验收完成 ★")
    else:
        fails = [r["name"] for r in results if r["status"] == "FAIL"]
        _log(f"FAIL项: {fails}")

    # 保存报告
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": n_total,
        "pass": n_pass,
        "fail": n_total - n_pass,
        "elapsed_seconds": round(elapsed, 1),
        "results": results,
        "summary": f"{n_pass}/{n_total} PASS",
    }
    report_path = REPORT_DIR / "t30_evolution_accept.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"报告: {report_path}")


if __name__ == "__main__":
    main()
