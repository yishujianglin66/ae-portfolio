import pytest
#!/usr/bin/env python3
"""P0 完整七阶段 E2E: perceive(Stock)→analyze→plan→execute→render→verify→learn
验证从素材获取到成片输出的完整生产能力。
"""
import sys, os, time, json
from pathlib import Path
pytestmark = pytest.mark.real_e2e


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['PYTHONIOENCODING'] = 'utf-8'

def main():
    print("=" * 60)
    print("P0 FULL 7-STAGE E2E (with Stock Footage)")
    print("=" * 60)
    
    from pipeline.unified_pipeline import UnifiedPipeline, PipelineConfig
    
    # 不指定 materials_dir，让 perceive 阶段自动从 Pexels 获取
    config = PipelineConfig(
        input_topic="cinematic nature aerial",
        materials_dir="",  # 空 → 触发 Stock 自动获取
        output_dir=str(ROOT / "output" / "p0_full_7stage"),
        ffmpeg_bin=r"C:\ffmpeg\bin\ffmpeg.exe",
        enable_feedback_loop=True,
        max_quality_iterations=2,
        min_quality_score=60.0,
        enable_multi_agent=False,
        enable_vrs=False,
        use_knowledge=True,
    )
    
    pipe = UnifiedPipeline(config)
    t0 = time.time()
    result = pipe.run_all()
    elapsed = time.time() - t0
    
    print("\n" + "=" * 60)
    print(f"PIPELINE COMPLETE ({elapsed:.1f}s)")
    print("=" * 60)
    
    # 提取结果
    status = getattr(result, 'status', 'unknown')
    if hasattr(status, 'value'):
        status = status.value
    quality = getattr(result, 'quality_score', 0)
    output_path = getattr(result, 'output_path', '')
    
    # 如果 output_path 为空，尝试从 results 中获取
    if not output_path:
        render_data = getattr(result, 'stage_results', {}).get('render', {})
        if isinstance(render_data, dict):
            output_path = render_data.get('output_path', '')
    
    # 最终 fallback: 检查标准输出路径
    if not output_path or not os.path.isfile(str(output_path)):
        candidate = ROOT / "output" / "p0_full_7stage" / "pipeline_output.mp4"
        if candidate.exists():
            output_path = str(candidate)
    
    print(f"  Status: {status}")
    print(f"  Quality: {quality}")
    print(f"  Output: {output_path}")
    
    # ffprobe 验证
    if output_path and os.path.isfile(str(output_path)):
        size_mb = os.path.getsize(output_path) / (1024*1024)
        print(f"  Size: {size_mb:.2f} MB")
        
        import subprocess
        probe_cmd = [
            r"C:\ffmpeg\bin\ffprobe.exe", "-v", "quiet",
            "-print_format", "json", "-show_format", "-show_streams",
            str(output_path)
        ]
        try:
            probe = subprocess.run(probe_cmd, capture_output=True, text=True, 
                                   timeout=10, encoding='utf-8', errors='replace')
            probe_data = json.loads(probe.stdout)
            fmt = probe_data.get("format", {})
            streams = probe_data.get("streams", [])
            vs = next((s for s in streams if s.get("codec_type") == "video"), {})
            
            duration = float(fmt.get('duration', 0))
            width = vs.get('width', 0)
            height = vs.get('height', 0)
            codec = vs.get('codec_name', '')
            fps = vs.get('r_frame_rate', '')
            bitrate = int(fmt.get('bit_rate', 0))
            
            print(f"\n  [ffprobe]")
            print(f"    Codec: {codec}")
            print(f"    Resolution: {width}x{height}")
            print(f"    Duration: {duration:.1f}s")
            print(f"    FPS: {fps}")
            print(f"    Bitrate: {bitrate//1000} kbps")
            
            has_audio = any(s.get("codec_type") == "audio" for s in streams)
            print(f"    Audio: {'Yes' if has_audio else 'No'}")
            
            # 验收判定
            checks = []
            checks.append(("MP4 exists", size_mb > 0.5))
            checks.append(("H.264 codec", codec == "h264"))
            checks.append(("1080P+", height >= 1080))
            checks.append(("Duration > 5s", duration > 5))
            checks.append(("Quality > 60", quality > 60))
            checks.append(("Status success", str(status) in ("success", "done")))
            
            print(f"\n  [Acceptance]")
            all_pass = True
            for name, passed in checks:
                mark = "PASS" if passed else "FAIL"
                print(f"    {mark}: {name}")
                if not passed:
                    all_pass = False
            
            if all_pass:
                print(f"\n  RESULT: PASS - Production-ready output!")
                return 0
            else:
                print(f"\n  RESULT: PARTIAL - Some checks failed")
                return 1
                
        except Exception as e:
            print(f"    ffprobe error: {e}")
    else:
        print(f"  ERROR: No output file found")
    
    return 1

if __name__ == "__main__":
    sys.exit(main())
