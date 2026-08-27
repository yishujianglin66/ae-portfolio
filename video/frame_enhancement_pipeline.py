"""
V3 视频补帧超分全链路实战脚本（追求最高上限效果）
=====================================================
流水线:
  原始 720p@60fps (h264+AAC, 11.17s)
    → Step 0: 降帧 60→30fps            [FFmpeg, CRF 16, 高质量]
    → Step 1: RIFE 2x 补帧 30→60fps     [RIFE HDv3, fp32, scale=1.0]
    → Step 2: RIFE 2x 补帧 60→120fps    [RIFE HDv3, fp32, scale=1.0]
    → Step 3: Topaz 超分 720→1080p      [tvai_up, ahq-2 动漫模型, estimate=30]
    → Step 4: 伪补帧增强 + 锐化 + 色彩  [FFmpeg, gblur+tblend+unsharp+eq]
    → Step 5: 音频混入 (原始 AAC)       [FFmpeg, copy]

输出: 1080p@120fps Enhanced MP4
"""
from __future__ import annotations

import os
import sys
import time
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# === 路径配置 ===
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"
PYTHON = r"D:\夸克\ComfyUI-aki\python\python.exe"
RIFE_ROOT = r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\external\rife"
RIFE_SCRIPT = os.path.join(RIFE_ROOT, "inference_video.py")
# Topaz 自带的 ffmpeg 支持 tvai_up / tvai_fi 滤镜（模型未下载，作为备选）
TOPAZ_FFMPEG = r"D:\top\Topaz Video AI Pro\ffmpeg.exe"
# Real-ESRGAN ncnn-vulkan 命令行工具（AI 超分，支持动漫视频模型）
REALESRGAN = r"D:\AE-Work\realesrgan-ncnn-vulkan\realesrgan-ncnn-vulkan.exe"

INPUT_VIDEO = r"D:\AE-Work\output\独自升级_复刻V3.mp4"
# 输出目录改到工作目录内，避免 TRAE 沙箱限制 D 盘写入
OUTPUT_DIR = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\temp\frame_enhancement")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
# 复用 D 盘已存在的 Step 0 结果（避免重新降帧）
STEP0_D_DRIVE = r"D:\AE-Work\output\frame_enhancement\v3_30fps.mp4"

# 报告文件
REPORT_FILE = OUTPUT_DIR / "pipeline_report.json"


def log(msg: str, level: str = "INFO") -> None:
    """带时间戳的日志输出（强制 flush 避免缓冲）。"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


def should_skip(output_path: str, min_size_kb: int = 100) -> bool:
    """断点续跑: 检查输出文件是否已存在且大于阈值（避免 stub 残留）。"""
    if not os.path.exists(output_path):
        return False
    size_kb = os.path.getsize(output_path) / 1024
    if size_kb < min_size_kb:
        log(f"[RESUME] {os.path.basename(output_path)} 仅 {size_kb:.1f}KB < {min_size_kb}KB，视为损坏，重跑")
        try:
            os.remove(output_path)
        except Exception as e:
            log(f"[RESUME] 删除失败: {e}", "WARN")
        return False
    log(f"[SKIP] {os.path.basename(output_path)} 已存在 ({size_kb:.1f}KB)，跳过此步骤")
    return True


def skip_result(step_name: str, output_path: str) -> dict:
    """构造跳过步骤的结果。"""
    info = get_video_info(output_path)
    return {
        "step": step_name,
        "success": True,
        "output": output_path,
        "elapsed_sec": 0.0,
        "skipped": True,
        "width": info.get("width", "?"),
        "height": info.get("height", "?"),
        "fps": info.get("r_frame_rate", "?"),
        "duration": info.get("duration", "?"),
        "size_mb": round(get_file_size_mb(output_path), 2),
    }


def run(cmd: list[str], timeout: int = 7200, cwd: str = None, label: str = "",
        capture: bool = False, env: dict = None) -> tuple[int, str, str]:
    """运行命令并返回 (返回码, stdout, stderr)。

    capture=False (默认): 子进程直接输出到终端，适合长时间运行命令（RIFE/Topaz）
    capture=True: 捕获输出，适合需要解析输出的短命令（ffprobe）
    env: 自定义环境变量（None 表示继承当前环境）
    """
    log(f"{'='*60}")
    log(f"[CMD] {label or ' '.join(cmd[:6])}")
    log(f"[FULL] {' '.join(cmd)}", )
    start = time.time()
    try:
        if capture:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env)
        else:
            # 不捕获输出，直接显示在终端（实时进度条可见）
            r = subprocess.run(cmd, timeout=timeout, cwd=cwd, env=env)
            return r.returncode, "", ""
    except subprocess.TimeoutExpired:
        log(f"[TIMEOUT] 超过 {timeout}s", "ERROR")
        return -1, "", "timeout"
    elapsed = time.time() - start
    log(f"[TIME] {elapsed:.1f}s | [RC] {r.returncode}")
    if r.returncode != 0 and r.stderr:
        log(f"[ERR] {r.stderr[-800:]}", "ERROR")
    return r.returncode, r.stdout, r.stderr


def make_rife_env() -> dict:
    """构建 RIFE 子进程环境变量：把 C:\\ffmpeg\\bin 放在 PATH 最前。

    skvideo 库依赖 PATH 中的 ffmpeg/ffprobe，TRAE 内置的 FFmpeg 可能版本不兼容，
    这里强制使用系统 FFmpeg (C:\\ffmpeg\\bin)。
    """
    env = os.environ.copy()
    ffmpeg_bin = r"C:\ffmpeg\bin"
    # 把系统 FFmpeg 放在 PATH 最前面，确保 skvideo 优先找到它
    env["PATH"] = ffmpeg_bin + os.pathsep + env.get("PATH", "")
    return env


def get_video_info(path: str) -> dict:
    """获取视频信息（ffprobe 默认输出格式，避免 JSON 转义问题）。"""
    cmd = [FFPROBE, "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height,r_frame_rate,codec_name,duration,nb_frames,pix_fmt",
           "-show_entries", "format=duration,size,bit_rate",
           "-of", "default=noprint_wrappers=1", path]
    rc, out, _ = run(cmd, timeout=30, label="ffprobe", capture=True)
    info = {}
    for line in out.strip().split("\n"):
        if "=" in line:
            k, v = line.split("=", 1)
            info[k] = v
    return info


def get_file_size_mb(path: str) -> float:
    """获取文件大小（MB）。"""
    if not os.path.exists(path):
        return 0.0
    return os.path.getsize(path) / 1024 / 1024


def step0_reduce_fps(input_path: str, output_path: str, target_fps: int = 30) -> dict:
    """Step 0: 降帧 60fps → 30fps。
    
    使用 select 滤镜丢弃偶数帧，保留奇数帧，实现精确降帧。
    CRF 16 保证近乎无损质量。
    """
    log("#" * 60)
    log("# Step 0: 降帧到 {}fps".format(target_fps))
    log("#" * 60)
    
    start = time.time()
    # select=not(mod(n\,2)) 保留奇数帧 (n=1,3,5,...)
    # setpts 调整时间戳
    cmd = [FFMPEG, "-y", "-i", input_path,
           "-vf", f"select=not(mod(n\\,2)),setpts=N/({target_fps}*TB)",
           "-r", str(target_fps),
           "-c:v", "libx264", "-preset", "slow", "-crf", "16",
           "-pix_fmt", "yuv420p",
           "-an",  # 先去掉音频，最后再混入
           output_path]
    rc, _, _ = run(cmd, timeout=300, label="Step 0 降帧")
    
    if rc != 0:
        log("[FALLBACK] 尝试简单降帧 (-r only)...")
        cmd = [FFMPEG, "-y", "-i", input_path,
               "-r", str(target_fps),
               "-c:v", "libx264", "-preset", "slow", "-crf", "16",
               "-pix_fmt", "yuv420p", "-an",
               output_path]
        rc, _, _ = run(cmd, timeout=300, label="Step 0 简单降帧")
    
    elapsed = time.time() - start
    info = get_video_info(output_path) if os.path.exists(output_path) else {}
    success = rc == 0 and os.path.exists(output_path)
    result = {
        "step": "step0_reduce_fps",
        "success": success,
        "output": output_path,
        "elapsed_sec": round(elapsed, 2),
        "width": info.get("width", "?"),
        "height": info.get("height", "?"),
        "fps": info.get("r_frame_rate", "?"),
        "duration": info.get("duration", "?"),
        "size_mb": round(get_file_size_mb(output_path), 2),
    }
    log(f"[RESULT] {json.dumps(result, ensure_ascii=False)}")
    return result


def step1_rife_interpolate(input_path: str, output_path: str, exp: int = 1, 
                            label: str = "Step 1") -> dict:
    """RIFE 补帧。
    
    exp=1: 2x 补帧 (30→60)
    exp=2: 4x 补帧 (30→120)
    
    使用 fp16 加速（RTX 系列 GPU 有 Tensor Core）。
    scale=1.0 在原始分辨率处理（720p 不会爆显存）。
    """
    log("#" * 60)
    log(f"# {label}: RIFE 补帧 exp={exp} (2^{exp}x)")
    log("#" * 60)
    
    start = time.time()
    cmd = [PYTHON, RIFE_SCRIPT,
           "--video", input_path,
           "--output", output_path,
           "--exp", str(exp),
           "--scale", "1.0",
           # 不使用 --fp16，使用 fp32 追求最高质量（720p 显存足够）
           "--ext", "mp4"]

    # 使用自定义环境变量，确保 skvideo 找到系统 FFmpeg
    rife_env = make_rife_env()
    rc, out, err = run(cmd, timeout=7200, cwd=RIFE_ROOT, label=label, env=rife_env)

    # RIFE 可能生成 _noaudio 版本（音频源无音频时）
    if not os.path.exists(output_path):
        noaudio = output_path.replace(".mp4", "_noaudio.mp4")
        if os.path.exists(noaudio):
            shutil.move(noaudio, output_path)
            log(f"[FIX] 重命名 {os.path.basename(noaudio)} → {os.path.basename(output_path)}")

    # RIFE 的 transferAudio 在源视频无音频时可能返回非 0 退出码，
    # 但视频本身已成功生成。这里基于输出文件有效性判定成功。
    elapsed = time.time() - start
    info = get_video_info(output_path) if os.path.exists(output_path) else {}
    # 成功条件: 文件存在 + 大小 > 500KB + ffprobe 能读出宽高和帧率
    file_size_ok = get_file_size_mb(output_path) > 0.5
    info_ok = info.get("width") and info.get("height") and info.get("r_frame_rate")
    success = file_size_ok and bool(info_ok)
    if success and rc != 0:
        log(f"[NOTE] RIFE 退出码非 0 (rc={rc})，但输出文件有效，视为成功")
    result = {
        "step": label.lower().replace(" ", "_"),
        "success": success,
        "output": output_path,
        "elapsed_sec": round(elapsed, 2),
        "width": info.get("width", "?"),
        "height": info.get("height", "?"),
        "fps": info.get("r_frame_rate", "?"),
        "duration": info.get("duration", "?"),
        "size_mb": round(get_file_size_mb(output_path), 2),
    }
    log(f"[RESULT] {json.dumps(result, ensure_ascii=False)}")
    return result


def step3_ai_upscale(input_path: str, output_path: str, target_height: int = 1080) -> dict:
    """Step 3: AI 超分 (Real-ESRGAN 帧序列 + 降采样)。

    三阶段流程 (ncnn-vulkan 只支持图片，需逐帧处理):
      1. FFmpeg 提取视频帧为 PNG 序列 (720p)
      2. Real-ESRGAN 2x AI 超分帧序列 (720p → 1440p)
      3. FFmpeg 重组装 + lanczos 降采样 (1440p → 1080p)

    超采样 (supersampling) 比直接插值质量更高: AI 先恢复细节，再降采样消除锯齿。
    使用 realesr-animevideov3-x2 模型 (专为动漫视频设计的 GAN 模型)。
    """
    import tempfile
    log("#" * 60)
    log(f"# Step 3: AI 超分 (Real-ESRGAN animevideov3-x2, target={target_height}p)")
    log("#" * 60)

    start = time.time()
    model_used = "realesr-animevideov3-x2"
    out_w = int(target_height * 16 / 9)

    # 获取输入视频信息
    in_info = get_video_info(input_path)
    in_fps = eval(in_info.get("r_frame_rate", "30/1"))  # e.g. "120/1" → 120.0
    in_frames = int(float(in_info.get("nb_frames", "0")) or 0)
    log(f"[INFO] 输入: {in_info.get('width')}x{in_info.get('height')} @ {in_fps}fps, {in_frames} 帧")

    # 使用临时目录存放帧序列
    frames_dir = tempfile.mkdtemp(prefix="esrgan_frames_")
    in_frames_dir = os.path.join(frames_dir, "input")
    out_frames_dir = os.path.join(frames_dir, "output")
    os.makedirs(in_frames_dir, exist_ok=True)
    os.makedirs(out_frames_dir, exist_ok=True)
    log(f"[TEMP] 帧序列目录: {frames_dir}")

    try:
        # --- 阶段 1: FFmpeg 提取帧为 PNG ---
        log("[Phase 1] FFmpeg 提取帧 → PNG 序列...")
        cmd = [FFMPEG, "-y", "-i", input_path,
               "-q:v", "1",  # PNG 无损质量
               "-vsync", "0",  # 保留所有帧
               os.path.join(in_frames_dir, "frame_%08d.png")]
        rc, _, _ = run(cmd, timeout=600, label="Step 3 提取帧")
        if rc != 0:
            raise RuntimeError(f"帧提取失败 rc={rc}")

        frame_count = len([f for f in os.listdir(in_frames_dir) if f.endswith(".png")])
        log(f"[OK] 提取 {frame_count} 帧")
        if frame_count == 0:
            raise RuntimeError("未提取到任何帧")

        # --- 阶段 2: Real-ESRGAN AI 超分 ---
        if os.path.exists(REALESRGAN):
            log(f"[Phase 2] Real-ESRGAN 2x AI 超分 ({frame_count} 帧)...")
            cmd = [REALESRGAN, "-i", in_frames_dir, "-o", out_frames_dir,
                   "-n", "realesr-animevideov3-x2", "-s", "2",
                   "-g", "1", "-j", "2:4:2", "-v"]
            rc, _, _ = run(cmd, timeout=14400, label="Step 3 Real-ESRGAN 超分")
            if rc != 0:
                log("[ESRGAN FAILED] 尝试 Topaz...", "WARN")
                model_used = "topaz_attempt"
                rc = -1
        else:
            log("[SKIP] Real-ESRGAN 未找到", "WARN")
            rc = -1

        # --- 阶段 2 备选: Topaz ---
        if rc != 0 and os.path.exists(TOPAZ_FFMPEG):
            log("[Phase 2b] Topaz Video AI 超分 (帧模式)...")
            model_used = "topaz_ahq-12"
            tvai_filter = (f"tvai_up=model=ahq-12:h={target_height*2}:estimate=30:"
                           f"compression=0.3:details=0.2:blur=0.1:vram=0.9:download=1")
            topaz_enc = ["-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq",
                         "-rc", "vbr", "-cq", "16", "-pix_fmt", "yuv420p"]
            intermediate = output_path.replace(".mp4", "_topaz_intermediate.mp4")
            cmd = [TOPAZ_FFMPEG, "-y", "-i", input_path,
                   "-vf", tvai_filter, *topaz_enc, "-an", intermediate]
            rc, _, _ = run(cmd, timeout=14400, label="Step 3 Topaz 超分")
            if rc == 0 and os.path.exists(intermediate):
                # Topaz 成功，直接降采样
                log("[Phase 3b] Topaz 输出降采样 → 1080p...")
                cmd = [FFMPEG, "-y", "-i", intermediate,
                       "-vf", f"scale={out_w}:{target_height}:flags=lanczos:out_range=tv",
                       "-c:v", "libx264", "-preset", "slow", "-crf", "14",
                       "-pix_fmt", "yuv420p", "-an", output_path]
                rc, _, _ = run(cmd, timeout=600, label="Step 3 降采样")
                try: os.remove(intermediate)
                except: pass
                elapsed = time.time() - start
                info = get_video_info(output_path) if os.path.exists(output_path) else {}
                success = rc == 0 and os.path.exists(output_path)
                result = {
                    "step": "step3_ai_upscale", "success": success, "output": output_path,
                    "elapsed_sec": round(elapsed, 2),
                    "width": info.get("width", "?"), "height": info.get("height", "?"),
                    "fps": info.get("r_frame_rate", "?"), "duration": info.get("duration", "?"),
                    "size_mb": round(get_file_size_mb(output_path), 2),
                    "model_used": model_used,
                }
                log(f"[RESULT] {json.dumps(result, ensure_ascii=False)}")
                return result

        # --- 阶段 2 最终回退: lanczos ---
        if rc != 0 or not os.listdir(out_frames_dir):
            log("[FALLBACK] AI 全部失败，lanczos 直接超分...", "WARN")
            model_used = "lanczos_fallback"
            cmd = [FFMPEG, "-y", "-i", input_path,
                   "-vf", f"scale={out_w}:{target_height}:flags=lanczos:out_range=tv",
                   "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                   "-pix_fmt", "yuv420p", "-an", output_path]
            rc, _, _ = run(cmd, timeout=600, label="Step 3 lanczos 回退")
        else:
            # --- 阶段 3: 重组装 + 降采样 (1440p → 1080p) ---
            out_frame_count = len([f for f in os.listdir(out_frames_dir) if f.endswith(".png")])
            log(f"[Phase 3] 重组装 + 降采样 {out_frame_count} 帧 → 1080p MP4...")
            cmd = [FFMPEG, "-y",
                   "-framerate", str(in_fps),
                   "-i", os.path.join(out_frames_dir, "frame_%08d.png"),
                   "-vf", f"scale={out_w}:{target_height}:flags=lanczos:out_range=tv",
                   "-c:v", "libx264", "-preset", "slow", "-crf", "14",
                   "-pix_fmt", "yuv420p",
                   "-r", str(in_fps),
                   "-an", output_path]
            rc, _, _ = run(cmd, timeout=1200, label="Step 3 重组装+降采样")

    except Exception as e:
        log(f"[ERROR] Step 3 异常: {e}", "ERROR")
        # 最终回退
        model_used = "lanczos_fallback"
        cmd = [FFMPEG, "-y", "-i", input_path,
               "-vf", f"scale={out_w}:{target_height}:flags=lanczos:out_range=tv",
               "-c:v", "libx264", "-preset", "slow", "-crf", "16",
               "-pix_fmt", "yuv420p", "-an", output_path]
        rc, _, _ = run(cmd, timeout=600, label="Step 3 异常回退")
    finally:
        # 清理临时帧目录
        try:
            shutil.rmtree(frames_dir, ignore_errors=True)
            log(f"[CLEAN] 已清理临时目录")
        except Exception:
            pass

    elapsed = time.time() - start
    info = get_video_info(output_path) if os.path.exists(output_path) else {}
    success = rc == 0 and os.path.exists(output_path)
    result = {
        "step": "step3_ai_upscale",
        "success": success,
        "output": output_path,
        "elapsed_sec": round(elapsed, 2),
        "width": info.get("width", "?"),
        "height": info.get("height", "?"),
        "fps": info.get("r_frame_rate", "?"),
        "duration": info.get("duration", "?"),
        "size_mb": round(get_file_size_mb(output_path), 2),
        "model_used": model_used,
    }
    log(f"[RESULT] {json.dumps(result, ensure_ascii=False)}")
    return result


def step4_fake_hfr_enhance(input_path: str, output_path: str) -> dict:
    """Step 4: 伪补帧增强。
    
    视觉增强组合：
    1. gblur sigma=0.3: 极轻微高斯模糊（模拟胶片质感，对抗数字锐化伪影）
    2. tblend all_mode=lighten: 帧混合（前一帧与当前帧取亮值，增加光感）
    3. unsharp 5:5:1.0: 锐化（补偿模糊）
    4. eq contrast=1.04:saturation=1.06:brightness=0.01:gamma=0.98: 
       轻微色彩增强（对比度+4%, 饱和度+6%, 伽马-2%）
    
    CRF 14 保证高质量输出。
    """
    log("#" * 60)
    log("# Step 4: 伪补帧增强 (帧混合+锐化+色彩)")
    log("#" * 60)
    
    start = time.time()
    vf_parts = [
        "gblur=sigma=0.3:steps=4",                    # 极轻微模糊
        "tblend=all_mode=lighten:all_opacity=0.15",   # 帧混合（增亮）
        "unsharp=5:5:1.0:5:5:0.5",                    # 锐化
        "eq=contrast=1.04:saturation=1.06:brightness=0.01:gamma=0.98",  # 色彩
    ]
    vf = ",".join(vf_parts)
    
    cmd = [FFMPEG, "-y", "-i", input_path,
           "-vf", vf,
           "-c:v", "libx264", "-preset", "slow", "-crf", "14",
           "-pix_fmt", "yuv420p",
           "-an",
           output_path]
    rc, _, _ = run(cmd, timeout=1800, label="Step 4 伪补帧增强")
    
    elapsed = time.time() - start
    info = get_video_info(output_path) if os.path.exists(output_path) else {}
    success = rc == 0 and os.path.exists(output_path)
    result = {
        "step": "step4_fake_hfr_enhance",
        "success": success,
        "output": output_path,
        "elapsed_sec": round(elapsed, 2),
        "width": info.get("width", "?"),
        "height": info.get("height", "?"),
        "fps": info.get("r_frame_rate", "?"),
        "duration": info.get("duration", "?"),
        "size_mb": round(get_file_size_mb(output_path), 2),
    }
    log(f"[RESULT] {json.dumps(result, ensure_ascii=False)}")
    return result


def step5_merge_audio(video_path: str, audio_source: str, output_path: str) -> dict:
    """Step 5: 音频混入。
    
    从原始视频提取 AAC 音频，无损混入最终视频。
    """
    log("#" * 60)
    log("# Step 5: 音频混入")
    log("#" * 60)
    
    start = time.time()
    cmd = [FFMPEG, "-y",
           "-i", video_path,        # 视频（无音频）
           "-i", audio_source,      # 原始视频（含音频）
           "-map", "0:v:0",         # 取第一个输入的视频
           "-map", "1:a:0",         # 取第二个输入的音频
           "-c:v", "copy",          # 视频流直接复制
           "-c:a", "aac", "-b:a", "192k",  # 音频重编码 AAC 192kbps
           "-shortest",
           output_path]
    rc, _, _ = run(cmd, timeout=300, label="Step 5 音频混入")
    
    elapsed = time.time() - start
    info = get_video_info(output_path) if os.path.exists(output_path) else {}
    success = rc == 0 and os.path.exists(output_path)
    result = {
        "step": "step5_merge_audio",
        "success": success,
        "output": output_path,
        "elapsed_sec": round(elapsed, 2),
        "width": info.get("width", "?"),
        "height": info.get("height", "?"),
        "fps": info.get("r_frame_rate", "?"),
        "duration": info.get("duration", "?"),
        "size_mb": round(get_file_size_mb(output_path), 2),
    }
    log(f"[RESULT] {json.dumps(result, ensure_ascii=False)}")
    return result


def main():
    log("=" * 60)
    log("V3 视频补帧超分全链路实战（追求最高上限效果）")
    log("=" * 60)
    
    # 检查依赖
    for name, path in [("FFmpeg", FFMPEG), ("FFprobe", FFPROBE),
                        ("Python", PYTHON), ("RIFE", RIFE_SCRIPT),
                        ("Real-ESRGAN", REALESRGAN),
                        ("Topaz FFmpeg", TOPAZ_FFMPEG), ("Input", INPUT_VIDEO)]:
        exists = os.path.exists(path)
        log(f"[CHECK] {name}: {'OK' if exists else 'MISSING'} - {path}")
        if not exists and name in ("Topaz FFmpeg",):  # Topaz 和 Real-ESRGAN 可选（有回退）
            continue
        if not exists and name == "Real-ESRGAN":
            log(f"[WARN] Real-ESRGAN 未找到，将使用 Topaz 或 lanczos 回退", "WARN")
            continue
        if not exists:
            log(f"[FATAL] {name} 不存在", "ERROR")
            return
    
    # 原始视频信息
    log("\n[原始视频信息]")
    orig_info = get_video_info(INPUT_VIDEO)
    log(f"  分辨率: {orig_info.get('width','?')}x{orig_info.get('height','?')}")
    log(f"  帧率: {orig_info.get('r_frame_rate','?')}")
    log(f"  时长: {float(orig_info.get('duration','0')):.2f}s")
    log(f"  编码: {orig_info.get('codec_name','?')}")
    log(f"  大小: {get_file_size_mb(INPUT_VIDEO):.2f}MB")
    
    # 文件路径定义
    paths = {
        "step0": str(OUTPUT_DIR / "v3_30fps.mp4"),
        "step1": str(OUTPUT_DIR / "v3_rife_60fps.mp4"),
        "step2": str(OUTPUT_DIR / "v3_rife_120fps.mp4"),
        "step3": str(OUTPUT_DIR / "v3_topaz_1080p.mp4"),
        "step4": str(OUTPUT_DIR / "v3_enhanced_1080p.mp4"),
        "step5": str(OUTPUT_DIR / "v3_final_1080p_120fps.mp4"),
    }

    # 复用 D 盘已存在的 Step 0 结果（避免重新降帧，D 盘只读访问不受沙箱限制）
    if not os.path.exists(paths["step0"]) and os.path.exists(STEP0_D_DRIVE):
        import shutil as _shutil
        log(f"[REUSE] 从 D 盘复制 Step 0 结果: {STEP0_D_DRIVE}")
        _shutil.copy2(STEP0_D_DRIVE, paths["step0"])
        log(f"[REUSE] 已复制到: {paths['step0']}")
    
    report = {
        "start_time": datetime.now().isoformat(),
        "input": {
            "path": INPUT_VIDEO,
            "info": orig_info,
            "size_mb": round(get_file_size_mb(INPUT_VIDEO), 2),
        },
        "steps": {},
    }
    
    total_start = time.time()
    
    # Step 0: 降帧 60→30
    if should_skip(paths["step0"], min_size_kb=500):
        report["steps"]["step0"] = skip_result("step0_reduce_fps", paths["step0"])
    else:
        report["steps"]["step0"] = step0_reduce_fps(INPUT_VIDEO, paths["step0"], target_fps=30)
    if not report["steps"]["step0"]["success"]:
        log("[FATAL] Step 0 失败，终止", "ERROR")
        _save_report(report, total_start)
        return
    
    # Step 1: RIFE 2x 补帧 30→60
    if should_skip(paths["step1"], min_size_kb=500):
        report["steps"]["step1"] = skip_result("step1_rife_30_to_60", paths["step1"])
    else:
        report["steps"]["step1"] = step1_rife_interpolate(
            paths["step0"], paths["step1"], exp=1, label="Step 1 RIFE 30→60")
    
    if not report["steps"]["step1"]["success"]:
        log("[WARNING] RIFE Step 1 失败，用 FFmpeg minterpolate 回退...")
        cmd = [FFMPEG, "-y", "-i", paths["step0"],
               "-vf", "minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:vsbmc=1:me_mode=bidir:me=epzs",
               "-r", "60", "-c:v", "libx264", "-preset", "fast", "-crf", "16",
               "-pix_fmt", "yuv420p", "-an", paths["step1"]]
        rc, _, _ = run(cmd, timeout=3600, label="Step 1 minterpolate 回退")
        report["steps"]["step1"]["fallback"] = "minterpolate"
        report["steps"]["step1"]["success"] = rc == 0 and os.path.exists(paths["step1"])
    
    if not report["steps"]["step1"]["success"]:
        log("[FATAL] Step 1 失败", "ERROR")
        _save_report(report, total_start)
        return
    
    # Step 2: RIFE 2x 补帧 60→120
    if should_skip(paths["step2"], min_size_kb=500):
        report["steps"]["step2"] = skip_result("step2_rife_60_to_120", paths["step2"])
    else:
        report["steps"]["step2"] = step1_rife_interpolate(
            paths["step1"], paths["step2"], exp=1, label="Step 2 RIFE 60→120")
    
    if not report["steps"]["step2"]["success"]:
        log("[WARNING] RIFE Step 2 失败，用 FFmpeg minterpolate 回退...")
        cmd = [FFMPEG, "-y", "-i", paths["step1"],
               "-vf", "minterpolate=fps=120:mi_mode=mci:mc_mode=aobmc:vsbmc=1:me_mode=bidir:me=epzs",
               "-r", "120", "-c:v", "libx264", "-preset", "fast", "-crf", "16",
               "-pix_fmt", "yuv420p", "-an", paths["step2"]]
        rc, _, _ = run(cmd, timeout=3600, label="Step 2 minterpolate 回退")
        report["steps"]["step2"]["fallback"] = "minterpolate"
        report["steps"]["step2"]["success"] = rc == 0 and os.path.exists(paths["step2"])
    
    if not report["steps"]["step2"]["success"]:
        log("[FATAL] Step 2 失败", "ERROR")
        _save_report(report, total_start)
        return
    
    # Step 3: AI 超分 720→1080 (Real-ESRGAN + 降采样)
    if should_skip(paths["step3"], min_size_kb=500):
        report["steps"]["step3"] = skip_result("step3_ai_upscale", paths["step3"])
    else:
        report["steps"]["step3"] = step3_ai_upscale(
            paths["step2"], paths["step3"], target_height=1080)
    
    if not report["steps"]["step3"]["success"]:
        log("[FATAL] Step 3 失败", "ERROR")
        _save_report(report, total_start)
        return
    
    # Step 4: 伪补帧增强
    if should_skip(paths["step4"], min_size_kb=500):
        report["steps"]["step4"] = skip_result("step4_fake_hfr_enhance", paths["step4"])
    else:
        report["steps"]["step4"] = step4_fake_hfr_enhance(paths["step3"], paths["step4"])

    if not report["steps"]["step4"]["success"]:
        log("[WARNING] Step 4 失败，直接使用 Step 3 输出")
        paths["step4"] = paths["step3"]

    # Step 5: 音频混入
    if should_skip(paths["step5"], min_size_kb=500):
        report["steps"]["step5"] = skip_result("step5_merge_audio", paths["step5"])
    else:
        report["steps"]["step5"] = step5_merge_audio(
            paths["step4"], INPUT_VIDEO, paths["step5"])
    
    # 最终报告
    _save_report(report, total_start)
    
    # 打印最终摘要
    log("\n" + "=" * 60)
    log("实战结果摘要")
    log("=" * 60)
    for step_name, step_result in report["steps"].items():
        status = "✅ 成功" if step_result.get("success") else "❌ 失败"
        size = step_result.get("size_mb", 0)
        elapsed = step_result.get("elapsed_sec", 0)
        res = f"{step_result.get('width','?')}x{step_result.get('height','?')}"
        fps = step_result.get("fps", "?")
        log(f"  {step_name}: {status} | {res}@{fps} | {size}MB | {elapsed}s")
    
    if report["steps"].get("step5", {}).get("success"):
        final = report["steps"]["step5"]
        log(f"\n[最终输出]")
        log(f"  路径: {final['output']}")
        log(f"  分辨率: {final.get('width','?')}x{final.get('height','?')}")
        log(f"  帧率: {final.get('fps','?')}")
        log(f"  时长: {final.get('duration','?')}s")
        log(f"  大小: {final.get('size_mb',0)}MB")
        log(f"\n[原始]")
        log(f"  分辨率: {orig_info.get('width','?')}x{orig_info.get('height','?')}")
        log(f"  帧率: {orig_info.get('r_frame_rate','?')}")
        log(f"  大小: {get_file_size_mb(INPUT_VIDEO):.2f}MB")
    
    total_elapsed = time.time() - total_start
    log(f"\n[总耗时] {total_elapsed:.1f}s ({total_elapsed/60:.1f}min)")


def _save_report(report: dict, total_start: float) -> None:
    """保存报告到 JSON 文件。"""
    report["end_time"] = datetime.now().isoformat()
    report["total_elapsed_sec"] = round(time.time() - total_start, 2)
    try:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        log(f"[REPORT] 已保存: {REPORT_FILE}")
    except Exception as e:
        log(f"[REPORT] 保存失败: {e}", "ERROR")


if __name__ == "__main__":
    main()
