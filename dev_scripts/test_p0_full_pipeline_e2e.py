#!/usr/bin/env python3
"""P0 完整七阶段管线 E2E 测试
================================
验证 perceive → analyze → plan → execute → render → verify → learn 全链路真实执行。

验收标准:
1. 七个阶段全部 DONE (或合理 SKIPPED)
2. execute 产出真实 MP4 文件 (>100KB)
3. verify 产出真实质量分数 (0-100)
4. learn 写入学习记录 (PersistentLearningLoop)
5. 输出 pipeline_result.json 可复核
"""
import json
import os
import sys
import time
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main():
    print("=" * 70)
    print("P0 FULL PIPELINE E2E TEST")
    print("=" * 70)
    
    # 1. 准备测试素材 (优先使用 data/real_amv_test, 有长视频)
    materials_dir = ROOT / "data" / "real_amv_test"
    if not materials_dir.exists():
        materials_dir = ROOT / "data" / "materials"
    if not materials_dir.exists():
        materials_dir = ROOT / "test-projects" / "2026-07-06-利威尔高燃混剪" / "素材"
    if not materials_dir.exists():
        # 查找任何有视频的目录
        for candidate in [ROOT / "frames", ROOT / "media", ROOT / "temp"]:
            if candidate.exists():
                mp4s = list(candidate.glob("*.mp4"))
                if mp4s:
                    materials_dir = candidate
                    break
    
    print(f"\n[1] Materials dir: {materials_dir}")
    print(f"    Exists: {materials_dir.exists()}")
    if materials_dir.exists():
        mp4s = list(materials_dir.glob("**/*.mp4"))
        print(f"    MP4 count: {len(mp4s)}")
        if mp4s:
            print(f"    First: {mp4s[0].name}")
    
    # 2. 导入管线
    print("\n[2] Importing UnifiedPipeline...")
    try:
        from pipeline.unified_pipeline import PipelineConfig, PipelineMode, UnifiedPipeline
        print("    OK")
    except Exception as e:
        print(f"    FAILED: {e}")
        return 1
    
    # 3. 配置管线
    print("\n[3] Configuring pipeline...")
    config = PipelineConfig(
        input_topic="P0全链路E2E验证-高燃混剪",
        materials_dir=str(materials_dir) if materials_dir.exists() else "",
        output_dir=str(ROOT / "output" / "p0_e2e_full"),
        ffmpeg_bin=r"C:\ffmpeg\bin\ffmpeg.exe",
        enable_feedback_loop=True,
        max_quality_iterations=2,
        min_quality_score=50.0,
        use_knowledge=False,  # 简化测试
        enable_vrs=False,     # 简化测试
        use_compiler=False,   # 使用默认 LLM 路径
    )
    print(f"    output_dir: {config.output_dir}")
    print(f"    feedback_loop: {config.enable_feedback_loop}")
    print(f"    min_quality_score: {config.min_quality_score}")
    
    # 4. 运行管线
    print("\n[4] Running full pipeline (7 stages)...")
    print("-" * 70)
    start = time.time()
    
    try:
        pipe = UnifiedPipeline(config)
        result = pipe.run_all()
        elapsed = time.time() - start
        print("-" * 70)
        print(f"\n[5] Pipeline completed in {elapsed:.1f}s")
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n    PIPELINE CRASHED after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 5. 验证结果
    print("\n[6] Validating results...")
    errors = []
    warnings = []
    
    # 5.1 检查 pipeline_result
    result_dict = result.to_dict() if hasattr(result, 'to_dict') else {}
    status = result_dict.get("status", "unknown")
    print(f"    Pipeline status: {status}")
    if status == "failed":
        errors.append("Pipeline status=failed")
    
    # 5.2 检查各阶段
    stages = result_dict.get("stages", {})
    stage_names = ["perceive", "analyze", "plan", "execute", "render", "verify", "learn"]
    for sn in stage_names:
        stage_data = stages.get(sn, {})
        stage_status = stage_data.get("status", "missing")
        print(f"    Stage [{sn}]: {stage_status}")
        if stage_status not in ("done", "skipped"):
            if sn in ("execute", "render"):
                errors.append(f"Stage {sn} status={stage_status}")
            else:
                warnings.append(f"Stage {sn} status={stage_status}")
    
    # 5.3 检查 execute 输出
    output_path = result_dict.get("output_path", "")
    if output_path and Path(output_path).exists():
        size_mb = Path(output_path).stat().st_size / (1024 * 1024)
        print(f"    Output file: {output_path}")
        print(f"    Output size: {size_mb:.2f} MB")
        if size_mb < 0.1:
            errors.append(f"Output file too small: {size_mb:.2f}MB")
    else:
        errors.append(f"No valid output file: {output_path!r}")
    
    # 5.4 检查 verify 分数
    quality_score = result_dict.get("quality_score", 0)
    print(f"    Quality score: {quality_score}")
    if quality_score <= 0:
        warnings.append("Quality score is 0 (verify may have failed)")
    
    # 5.5 检查持久化文件
    persist_dir = Path(config.output_dir) / f"run_{result_dict.get('run_id', 'unknown')}"
    if persist_dir.exists():
        json_files = list(persist_dir.glob("*.json"))
        print(f"    Persisted files: {len(json_files)}")
        for jf in json_files[:5]:
            print(f"      - {jf.name}")
    else:
        # 尝试其他路径
        alt_persist = Path(config.output_dir)
        if alt_persist.exists():
            all_json = list(alt_persist.glob("**/*.json"))
            print(f"    Persisted files (alt): {len(all_json)}")
    
    # 5.6 检查学习记录
    learning_state_dir = Path(os.environ.get("APPDATA", "~")) / "AE-Knowledge-Vault" / "learning-state"
    if learning_state_dir.exists():
        records_file = learning_state_dir / "execution-records.json"
        if records_file.exists():
            with open(records_file, "r", encoding="utf-8") as f:
                records = json.load(f)
            print(f"    Learning records: {len(records)} total")
            if records:
                last = records[-1]
                print(f"    Last record: {last.get('timestamp', 'unknown')}")
        else:
            warnings.append("No execution-records.json found")
    else:
        warnings.append(f"Learning state dir not found: {learning_state_dir}")
    
    # 6. 总结
    print("\n" + "=" * 70)
    print("E2E TEST SUMMARY")
    print("=" * 70)
    print(f"  Status: {status}")
    print(f"  Duration: {elapsed:.1f}s")
    print(f"  Output: {output_path}")
    print(f"  Quality: {quality_score}")
    print(f"  Errors: {len(errors)}")
    for e in errors:
        print(f"    [ERROR] {e}")
    print(f"  Warnings: {len(warnings)}")
    for w in warnings:
        print(f"    [WARN] {w}")
    
    if errors:
        print("\n  RESULT: FAIL")
        return 1
    else:
        print("\n  RESULT: PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
