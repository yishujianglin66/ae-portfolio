#!/usr/bin/env python3
"""CI 端到端质量门 runner — 合成素材 → 跑 UnifiedPipeline v2 → 产出可被质量门消费的结果。

供 CI/CD（GitHub Actions）自动运行。用 ffmpeg 合成带音频的确定性测试素材，
不依赖本地素材库 / AE / LLM key（管线内置降级路径），验证「管线可端到端跑通 +
产物通过 QualityGate」这条链路。

用法:
    python scripts/ci_e2e_pipeline.py \\
        [--topic "CI 合成素材质量门验证"] \\
        [--segments 4] [--output-dir output/ci/e2e]

成功后打印 pipeline_result.json 绝对路径（供 ci_quality_gate.py 消费）。
退出码: 0 = 成功  2 = 失败（含 ffmpeg 缺失 / 管线未产出 result）
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# CI 测试模式：fallback_history 等写临时目录，避免污染生产数据
os.environ.setdefault("AEK_ENVIRONMENT", "test")


def ensure_ffmpeg() -> str:
    """检查 ffmpeg/ffprobe 可用，返回 ffmpeg 路径。CI 的 windows-latest runner 预装。"""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        print("[CI-E2E] FAIL: 未找到 ffmpeg/ffprobe，请安装并加入 PATH", file=sys.stderr)
        sys.exit(2)
    return ffmpeg


def synth_material(ffmpeg: str, out_dir: Path, segments: int) -> None:
    """用 lavfi 合成 N 段 1920x1080@30fps 带音调音频的短视频。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = [
        ("testsrc2", 440), ("smptebars", 523), ("gradients", 587), ("rgbtestsrc", 659),
        ("testsrc2", 698), ("smptebars", 784),
    ]
    for i in range(segments):
        src, freq = specs[i % len(specs)]
        out = out_dir / f"seg_{i:02d}.mp4"
        if out.exists() and out.stat().st_size > 0:
            continue
        cmd = [
            ffmpeg, "-y", "-v", "error",
            "-f", "lavfi", "-i", f"{src}=size=1920x1080:rate=30:duration=4",
            "-f", "lavfi", "-i", f"sine=frequency={freq}:duration=4",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-shortest", str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"[CI-E2E] 合成素材 {out.name} ({src}, {freq}Hz)")


def main() -> int:
    ap = argparse.ArgumentParser(description="CI 端到端质量门 runner")
    ap.add_argument("--topic", default="CI 合成素材质量门验证")
    ap.add_argument("--segments", type=int, default=4)
    ap.add_argument("--output-dir", default="output/ci/e2e")
    args = ap.parse_args()

    ffmpeg = ensure_ffmpeg()
    out_root = ROOT / args.output_dir
    materials = out_root / "materials"
    synth_material(ffmpeg, materials, args.segments)

    # 管线配置：CI 最小化 —— 单轮质量迭代、关闭自进化（避免 LLM 评分阻塞）
    from pipeline.unified_pipeline import PipelineConfig, UnifiedPipeline

    config = PipelineConfig(
        input_topic=args.topic,
        materials_dir=str(materials),
        output_dir=str(out_root),
        max_quality_iterations=1,
        enable_evolution=False,
        min_quality_score=40.0,
        enable_feedback_loop=False,
    )
    print(f"[CI-E2E] 启动 UnifiedPipeline: topic={args.topic}, materials={materials}")
    pipeline = UnifiedPipeline(config)
    result = pipeline.run_all()

    result_json = pipeline._persist_dir / "pipeline_result.json"
    if not result_json.exists():
        print("[CI-E2E] FAIL: 管线未产出 pipeline_result.json", file=sys.stderr)
        return 2

    # 复制到固定路径，供 workflow 后续步骤（ci_quality_gate.py）直接消费
    latest = out_root / "latest_pipeline_result.json"
    latest.write_text(result_json.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"[CI-E2E] result={result_json.resolve()}")
    print(f"[CI-E2E] latest={latest.resolve()}")
    print(f"[CI-E2E] status={result.status} quality_score={result.quality_score} "
          f"output={result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
