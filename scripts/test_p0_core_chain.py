#!/usr/bin/env python3
"""P0 核心链路简化测试: execute → render → verify
跳过 perceive/analyze/plan 的耗时操作，直接测试核心执行链路。
"""
import sys
import os
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['PYTHONIOENCODING'] = 'utf-8'

def main():
    print("=" * 60)
    print("P0 CORE CHAIN TEST: execute → render → verify")
    print("=" * 60)
    
    # 1. 找到测试素材
    materials_dir = ROOT / "data" / "real_amv_test"
    mp4s = list(materials_dir.glob("*.mp4"))[:3] if materials_dir.exists() else []
    if not mp4s:
        print("ERROR: No test videos found")
        return 1
    print(f"\n[1] Found {len(mp4s)} test videos")
    for m in mp4s:
        print(f"    - {m.name} ({m.stat().st_size // 1024}KB)")
    
    # 2. 导入管线
    print("\n[2] Importing pipeline...")
    from pipeline.unified_pipeline import UnifiedPipeline, PipelineConfig
    
    # 3. 配置 (跳过 perceive/analyze/plan)
    config = PipelineConfig(
        input_topic="P0核心链路测试",
        materials_dir=str(materials_dir),
        output_dir=str(ROOT / "output" / "p0_core_test"),
        ffmpeg_bin=r"C:\ffmpeg\bin\ffmpeg.exe",
        enable_feedback_loop=False,  # 简化: 不启用反馈闭环
        enable_vrs=False,
        use_knowledge=False,
        use_compiler=False,
        enable_multi_agent=False,  # 关键: 跳过多智能体
        skip_stages=["perceive", "analyze"],  # 跳过耗时阶段
    )
    
    # 4. 运行管线
    print("\n[3] Running pipeline (plan→execute→render→verify→learn)...")
    print("-" * 60)
    start = time.time()
    
    try:
        pipe = UnifiedPipeline(config)
        result = pipe.run_all()
        elapsed = time.time() - start
        print("-" * 60)
        print(f"\n[4] Pipeline completed in {elapsed:.1f}s")
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n    CRASHED after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 5. 验证结果
    print("\n[5] Validating results...")
    result_dict = result.to_dict() if hasattr(result, 'to_dict') else {}
    status = result_dict.get("status", "unknown")
    output_path = result_dict.get("output_path", "")
    quality_score = result_dict.get("quality_score", 0)
    
    print(f"    Status: {status}")
    print(f"    Output: {output_path}")
    print(f"    Quality: {quality_score}")
    
    if output_path and Path(output_path).exists():
        size_mb = Path(output_path).stat().st_size / (1024 * 1024)
        print(f"    Size: {size_mb:.2f} MB")
        if size_mb > 0.1:
            print("\n    RESULT: PASS")
            return 0
    
    print("\n    RESULT: FAIL")
    return 1

if __name__ == "__main__":
    sys.exit(main())
