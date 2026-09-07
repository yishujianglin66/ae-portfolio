#!/usr/bin/env python3
"""多视频批量对比测试 - 验证分类多样性与JSX生成质量"""
import asyncio
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "tests"))

from test_real_amv import test_real_video

VIDEOS = [
    ("output_director/style_renders/render_cyberpunk.mp4", "cyberpunk"),
    ("output_director/style_renders/render_ghibli.mp4",    "ghibli"),
    ("output_director/style_renders/render_cinematic.mp4", "cinematic"),
    ("output_director/style_renders/render_neon.mp4",      "neon"),
    ("output_director/style_renders/render_vintage.mp4",   "vintage"),
]

async def main():
    print("=" * 80)
    print(" 漫剪视频批量分类对比测试")
    print("=" * 80)
    print()

    results_summary = []

    for video_path, expected in VIDEOS:
        vp = Path(video_path)
        if not vp.exists():
            print(f"  ⚠ 视频缺失: {video_path}")
            continue

        # 读取已保存的结果
        result_file = Path("output/real_video_test") / f"{vp.stem}_result.json"
        if not result_file.exists():
            print(f"  ⚠ 结果文件缺失: {result_file}")
            continue

        with open(result_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        style = data["style_result"]["style"]
        confidence = data["style_result"]["confidence"]
        probs = data["style_result"].get("probabilities", {})

        # 风格预期与实际对比
        is_match = expected.lower() in style.lower() or style.lower() in expected.lower()
        marker = "✓" if is_match else "✗"

        print(f"  {marker} {vp.name:35s} → {style:25s} ({confidence:5.1%})  expected={expected}")

        # Top-3 概率
        sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:3]
        for s, p in sorted_probs:
            print(f"        {'':35s}   {s:25s} {p:6.2%}")

        print()

        results_summary.append({
            "video": vp.name,
            "expected": expected,
            "actual": style,
            "confidence": confidence,
            "match": is_match,
            "top3": sorted_probs,
            "n_effects": len(data.get("atomic_params", {}).get("effects", [])),
            "jsx": data.get("jsx_path"),
        })

    # 汇总报告
    print("=" * 80)
    print(" 汇总报告")
    print("=" * 80)

    n = len(results_summary)
    n_match = sum(1 for r in results_summary if r["match"])
    n_diverse = len(set(r["actual"] for r in results_summary))
    avg_conf = sum(r["confidence"] for r in results_summary) / n if n else 0
    avg_effects = sum(r["n_effects"] for r in results_summary) / n if n else 0

    print(f"  视频总数:   {n}")
    print(f"  风格匹配:   {n_match}/{n} ({n_match/n*100:.0f}%)")
    print(f"  风格多样性: {n_diverse} 个不同风格")
    print(f"  平均置信度: {avg_conf:.1%}")
    print(f"  平均效果数: {avg_effects:.1f}")
    print()

    # 各视频分类详情
    print(f"  {'视频':35s} {'预期':15s} {'实际':25s} {'置信度':>8s} {'效果':>5s}  匹配")
    print(f"  {'-'*35} {'-'*15} {'-'*25} {'-'*8} {'-'*5}  ----")
    for r in results_summary:
        m = "✓" if r["match"] else "✗"
        print(f"  {r['video']:35s} {r['expected']:15s} {r['actual']:25s} {r['confidence']:7.1%} {r['n_effects']:>5d}  {m}")

    # 保存汇总
    summary_file = Path("output/real_video_test/batch_summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({
            "total": n,
            "matched": n_match,
            "diversity": n_diverse,
            "avg_confidence": avg_conf,
            "avg_effects": avg_effects,
            "results": results_summary,
        }, f, indent=2, ensure_ascii=False)

    print()
    print(f"  汇总已保存: {summary_file}")
    print("=" * 80)
    print(" ✓ 批量测试完成")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
