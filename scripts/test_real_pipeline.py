"""
Phase 3.2: 全管线真实视频测试

对下载的真实B站AMV视频执行完整管线:
VRS分析 → 24维特征提取 → 风格分类 → 参数映射 → JSX生成

验收标准:
- 分类准确率 >= 70% (对比ground_truth)
- 无单一类预测占比 > 40%
- 所有JSX无 "ADBE Style Preset"
- 平均延迟 < 15秒/视频
"""
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data" / "real_amv_test"
OUTPUT_DIR = PROJECT_ROOT / "output" / "real_video_test"
JSX_DIR = OUTPUT_DIR / "jsx"


def find_videos() -> list:
    """找到所有下载的视频文件"""
    videos = []
    for f in DATA_DIR.iterdir():
        if f.suffix in (".mp4", ".mkv", ".webm") and f.stat().st_size > 50000:
            videos.append(f)
    return sorted(videos)


def load_ground_truth() -> dict:
    """加载 ground truth 标注"""
    gt_path = DATA_DIR / "ground_truth.json"
    if not gt_path.exists():
        return {}
    with open(gt_path, encoding="utf-8") as f:
        data = json.load(f)
    # bv_id → expected_style
    return {v["bv_id"]: v["expected_style"] for v in data.get("videos", [])}


async def run_pipeline(video_path: Path) -> dict:
    """对单个视频运行完整管线"""
    from core.style_pipeline import analyze_video_style
    from core.style_preset_adapter import style_to_atomic_params
    from core.jsx_generator import style_result_to_jsx

    start = time.time()

    # Step 1+2+3: VRS分析 + 特征提取 + 风格分类
    # enable_vision=False 跳过慢速LLM视觉分析，仅用OpenCV层
    style_result = await analyze_video_style(str(video_path), enable_vision=False)

    classify_time = time.time() - start

    # Step 4: 参数映射
    style = style_result.get("style", "cinematic")
    confidence = style_result.get("confidence", 0.5)
    atomic_params = style_to_atomic_params(style, confidence)

    # Step 5: JSX生成
    jsx_path = style_result_to_jsx(
        style_result=style_result,
        atomic_params=atomic_params,
        output_dir=str(JSX_DIR),
        video_path=str(video_path),
    )

    total_time = time.time() - start

    # 验证JSX内容
    jsx_content = Path(jsx_path).read_text(encoding="utf-8")
    has_bad_matchname = "ADBE Style Preset" in jsx_content

    return {
        "video": video_path.name,
        "predicted_style": style,
        "confidence": confidence,
        "classify_time": classify_time,
        "total_time": total_time,
        "jsx_path": jsx_path,
        "has_bad_matchname": has_bad_matchname,
        "features": style_result.get("features", []),
    }


async def main():
    print("=" * 70)
    print("Phase 3.2: 全管线真实视频测试")
    print("=" * 70)

    videos = find_videos()
    ground_truth = load_ground_truth()

    if not videos:
        print("错误: 未找到测试视频! 请先运行 scripts/download_real_amv.py")
        return

    print(f"测试视频: {len(videos)} 个")
    print(f"Ground truth: {len(ground_truth)} 个标注")
    print()

    results = []
    for i, video in enumerate(videos, 1):
        print(f"[{i}/{len(videos)}] 分析: {video.name}...")
        try:
            result = await run_pipeline(video)
            results.append(result)

            # 判断正确性
            bv_id = video.stem.split("_")[0]
            expected = ground_truth.get(bv_id, "?")
            correct = "✓" if result["predicted_style"] == expected else "✗"
            print(f"    预测: {result['predicted_style']} ({result['confidence']:.2%}) | "
                  f"期望: {expected} | {correct} | "
                  f"耗时: {result['total_time']:.1f}s")
        except Exception as e:
            print(f"    错误: {e}")
            results.append({"video": video.name, "error": str(e)})

    # 统计
    print(f"\n{'=' * 70}")
    print("测试结果汇总")
    print(f"{'=' * 70}")

    valid_results = [r for r in results if "predicted_style" in r]
    if not valid_results:
        print("无有效结果!")
        return

    # 准确率
    correct_count = 0
    for r in valid_results:
        bv_id = r["video"].split("_")[0]
        expected = ground_truth.get(bv_id, "")
        if r["predicted_style"] == expected:
            correct_count += 1

    accuracy = correct_count / len(valid_results) if valid_results else 0
    print(f"  分类准确率: {correct_count}/{len(valid_results)} = {accuracy:.1%}")

    # 预测分布
    pred_counter = Counter(r["predicted_style"] for r in valid_results)
    max_pred_ratio = max(pred_counter.values()) / len(valid_results)
    print(f"  最大单类占比: {max_pred_ratio:.1%} (阈值: <40%)")
    print(f"  预测分布: {dict(pred_counter)}")

    # JSX质量
    bad_jsx = sum(1 for r in valid_results if r.get("has_bad_matchname"))
    print(f"  错误matchName JSX: {bad_jsx}/{len(valid_results)}")

    # 延迟
    times = [r["total_time"] for r in valid_results]
    avg_time = sum(times) / len(times)
    print(f"  平均延迟: {avg_time:.1f}s (阈值: <15s)")

    # 验收判定
    print(f"\n验收标准:")
    print(f"  [{'PASS' if accuracy >= 0.7 else 'FAIL'}] 准确率 >= 70%: {accuracy:.1%}")
    print(f"  [{'PASS' if max_pred_ratio <= 0.4 else 'FAIL'}] 无单类 > 40%: {max_pred_ratio:.1%}")
    print(f"  [{'PASS' if bad_jsx == 0 else 'FAIL'}] 无错误matchName: {bad_jsx} 个")
    print(f"  [{'PASS' if avg_time < 15 else 'FAIL'}] 延迟 < 15s: {avg_time:.1f}s")

    # 保存报告
    report_path = OUTPUT_DIR / "real_video_test_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_videos": len(videos),
            "valid_results": len(valid_results),
            "accuracy": accuracy,
            "max_class_ratio": max_pred_ratio,
            "bad_jsx_count": bad_jsx,
            "avg_latency": avg_time,
            "results": valid_results,
        }, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
