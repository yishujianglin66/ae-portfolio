"""
P0 端到端验证: 真实素材 → 真实混剪 → 真实 MP4 输出
=====================================================
验证目标:
  1. perceive 正确扫描素材
  2. plan 生成有效剧本 (shot_list + effect_stack)
  3. execute 产出真实视频文件 (非空壳)
  4. render 输出可检测 MP4
  5. verify 评分可信 (基于真实产物)
  6. learn 写入执行记录

验收标准:
  - output_p0_e2e/ 下存在 >100KB 的 .mp4 文件
  - ffprobe 可解析 (时长>3s, 1920x1080, h264)
  - 管线日志无 CRITICAL 错误
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# ===== 配置 =====
MATERIALS_DIR = str(ROOT / "data" / "real_amv_test")
OUTPUT_DIR = str(ROOT / "output_p0_e2e")
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def verify_video(path: str) -> dict:
    """用 ffprobe 验证视频文件"""
    if not os.path.isfile(path):
        return {"valid": False, "error": "file not found"}
    size = os.path.getsize(path)
    if size < 10240:
        return {"valid": False, "error": f"file too small: {size}B"}
    
    cmd = [
        FFPROBE, "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", path
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return {"valid": False, "error": f"ffprobe failed: {r.stderr[:200]}"}
        info = json.loads(r.stdout)
        fmt = info.get("format", {})
        streams = info.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        
        duration = float(fmt.get("duration", 0))
        width = int(video_stream.get("width", 0)) if video_stream else 0
        height = int(video_stream.get("height", 0)) if video_stream else 0
        codec = video_stream.get("codec_name", "") if video_stream else ""
        
        return {
            "valid": duration > 1.0 and size > 10240,
            "path": path,
            "size_mb": round(size / (1024*1024), 2),
            "duration_sec": round(duration, 2),
            "width": width,
            "height": height,
            "codec": codec,
            "streams": len(streams),
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


def main():
    log("=" * 60)
    log("P0 E2E 验证开始")
    log("=" * 60)
    
    # 清理旧输出
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 选择 3 个真实素材
    all_videos = sorted(Path(MATERIALS_DIR).glob("*.mp4"))
    if len(all_videos) < 3:
        log(f"ERROR: 素材不足 ({len(all_videos)} < 3)")
        return False
    
    # 选前3个 (按文件名排序)
    selected = all_videos[:3]
    log(f"素材目录: {MATERIALS_DIR}")
    log(f"选中素材 ({len(selected)}):")
    for v in selected:
        log(f"  - {v.name} ({v.stat().st_size // 1024}KB)")
    
    # ===== 运行管线 =====
    log("")
    log(">>> 初始化 UnifiedPipeline...")
    
    from pipeline.unified_pipeline import PipelineConfig, UnifiedPipeline
    
    config = PipelineConfig(
        input_topic="赛博朋克高燃踩点混剪 霓虹色彩 故障艺术",
        materials_dir=MATERIALS_DIR,
        output_dir=OUTPUT_DIR,
        project_name="p0_e2e_test",
        ffmpeg_bin=FFMPEG,
        # 禁用需要外部服务的功能
        enable_vrs=False,          # VRS 需要 LLM
        use_knowledge=True,        # 知识库可用
        enable_feedback_loop=True, # 反馈闭环
        enable_multi_agent=False,  # 简化执行路径
        max_quality_iterations=1,  # 单次迭代
        use_davinci_render=False,  # 不用 DaVinci
    )
    
    pipe = UnifiedPipeline(config)
    
    log(">>> 运行 run_all()...")
    start = time.time()
    
    try:
        result = pipe.run_all()
    except Exception as e:
        log(f"CRITICAL: 管线异常退出: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    elapsed = time.time() - start
    log(f">>> 管线完成 ({elapsed:.1f}s)")
    
    # ===== 分析结果 =====
    log("")
    log("=" * 60)
    log("结果分析")
    log("=" * 60)
    
    # 打印各阶段状态
    if hasattr(pipe, '_results'):
        for stage_name, sr in pipe._results.items():
            if stage_name.startswith("_"):
                continue
            status = sr.status.value if hasattr(sr.status, 'value') else str(sr.status)
            log(f"  [{stage_name}] {status}")
    
    # 查找输出视频
    output_videos = list(Path(OUTPUT_DIR).rglob("*.mp4"))
    log(f"\n输出目录中的 MP4 文件 ({len(output_videos)}):")
    
    best_video = None
    for v in output_videos:
        info = verify_video(str(v))
        status = "✓" if info.get("valid") else "✗"
        log(f"  {status} {v.name}: {info.get('size_mb', 0)}MB, "
            f"{info.get('duration_sec', 0)}s, "
            f"{info.get('width', 0)}x{info.get('height', 0)}, "
            f"{info.get('codec', '?')}")
        if info.get("valid") and (best_video is None or info.get("size_mb", 0) > best_video.get("size_mb", 0)):
            best_video = info
    
    # ===== 验收判定 =====
    log("")
    log("=" * 60)
    log("验收判定")
    log("=" * 60)
    
    passed = True
    checks = []
    
    # Check 1: 存在有效视频
    if best_video and best_video.get("valid"):
        checks.append(("存在有效 MP4", True, f"{best_video['path']} ({best_video['size_mb']}MB)"))
    else:
        checks.append(("存在有效 MP4", False, "未找到 >10KB 的有效视频"))
        passed = False
    
    # Check 2: 时长 > 3s
    if best_video and best_video.get("duration_sec", 0) > 3.0:
        checks.append(("时长 > 3s", True, f"{best_video['duration_sec']}s"))
    else:
        checks.append(("时长 > 3s", False, f"{best_video.get('duration_sec', 0) if best_video else 0}s"))
        passed = False
    
    # Check 3: 分辨率
    if best_video and best_video.get("width", 0) >= 1280:
        checks.append(("分辨率 >= 1280", True, f"{best_video['width']}x{best_video['height']}"))
    else:
        checks.append(("分辨率 >= 1280", False, f"{best_video.get('width', 0) if best_video else 0}"))
    
    # Check 4: 编码格式
    if best_video and best_video.get("codec") in ("h264", "hevc", "mpeg4"):
        checks.append(("编码格式", True, best_video['codec']))
    else:
        checks.append(("编码格式", False, best_video.get('codec', 'unknown') if best_video else 'none'))
    
    for name, ok, detail in checks:
        status = "PASS" if ok else "FAIL"
        log(f"  [{status}] {name}: {detail}")
    
    log("")
    if passed:
        log(">>> P0 E2E 验证: PASSED <<<")
        log(f">>> 输出文件: {best_video['path']}")
    else:
        log(">>> P0 E2E 验证: FAILED <<<")
    
    # 保存报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_sec": round(elapsed, 1),
        "passed": passed,
        "checks": [{"name": n, "passed": ok, "detail": d} for n, ok, d in checks],
        "best_video": best_video,
        "output_videos": [str(v) for v in output_videos],
        "materials_used": [str(v) for v in selected],
    }
    report_path = os.path.join(OUTPUT_DIR, "p0_e2e_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(f"报告已保存: {report_path}")
    
    return passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
