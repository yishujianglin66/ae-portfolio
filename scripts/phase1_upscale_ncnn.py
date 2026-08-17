# -*- coding: utf-8 -*-
"""Phase 1 低清段增强 — ncnn-vulkan 超分集成脚本 (科研验证版)

流程: 抽帧(ffmpeg) -> 逐帧/目录 realesrgan-ncnn-vulkan 超分 -> 拼回(ffmpeg image2 -> mp4) -> 音频透传(可选)

CLI:
    py -3.12 scripts/phase1_upscale_ncnn.py --input <视频> --output <视频> --scale 2/3/4 [--model animevideov3]

示例:
    py -3.12 scripts/phase1_upscale_ncnn.py --input input_480p.mp4 --output out_1080p.mp4 --scale 4 --model animevideov3

依赖: 仅标准库 + 磁盘上的 ffmpeg / realesrgan-ncnn-vulkan.exe (无 pip 依赖)
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

FFMPEG_DEFAULT = r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"
NCNN_DIR_DEFAULT = r"D:\output_director\solo_pilot\v23\upscale_test\ncnn"
EXE_NAME = "realesrgan-ncnn-vulkan.exe"

# 模型名 -> 该模型支持的 scale
MODEL_SCALES = {
    "realesr-animevideov3": (2, 3, 4),
    "realesrgan-x4plus": (4,),
    "realesrgan-x4plus-anime": (4,),
    "realesrnet-x4plus": (4,),
}


def run(cmd, timeout=None, capture=False):
    """运行命令, 返回 (returncode, stdout_text, stderr_text)."""
    t0 = time.time()
    if capture:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out_lines = []
    try:
        for line in p.stdout:
            line = line.rstrip("\n")
            # 进度条 \r 覆盖式输出 -> 只保留每行最后一段
            seg = line.split("\r")[-1].strip()
            if seg:
                out_lines.append(seg)
                print("    | " + seg, flush=True)
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        raise
    return p.returncode, "\n".join(out_lines), ""


def probe_video(ffmpeg, path):
    """无 ffprobe 环境下用 ffmpeg -i 的 stderr 解析 WxH/SAR/fps/时长/是否有音频."""
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", path],
                       capture_output=True, text=True)
    text = r.stderr
    m = re.search(r"(\d{3,4})x(\d{3,4})", text)
    W, H = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    msar = re.search(r"SAR (\d+):(\d+)", text)
    sar = (int(msar.group(1)), int(msar.group(2))) if msar else (1, 1)
    mf = re.search(r"(\d+(?:\.\d+)?) fps", text)
    fps = float(mf.group(1)) if mf else None
    md = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    dur = None
    if md:
        hh, mm, ss = int(md.group(1)), int(md.group(2)), float(md.group(3))
        dur = hh * 3600 + mm * 60 + ss
    has_audio = bool(re.search(r"Stream #\d+:\d+.*Audio:", text))
    return W, H, sar, fps, dur, has_audio


def target_dims(W, H, sar, target_height):
    """按输入 DAR (含 SAR) 计算精确目标尺寸, 宽度取最近偶数."""
    dar = (W * sar[0]) / float(H * sar[1])
    tw = int(round(target_height * dar / 2.0) * 2)
    return max(tw, 2), target_height


def validate_toolchain(ncnn_dir, model, scale):
    exe = os.path.join(ncnn_dir, EXE_NAME)
    if not os.path.isfile(exe):
        raise SystemExit("ncnn exe 不存在: %s" % exe)
    param = os.path.join(ncnn_dir, "models", "%s-x%d.param" % (model, scale))
    binf = os.path.join(ncnn_dir, "models", "%s-x%d.bin" % (model, scale))
    if not (os.path.isfile(param) and os.path.isfile(binf)):
        raise SystemExit("模型文件缺失: %s / %s (可用模型: %s)"
                         % (param, binf, ", ".join(MODEL_SCALES)))
    print("[toolchain] %s" % exe)
    print("[toolchain] model=%s scale=%d  param=%s" % (model, scale, os.path.basename(param)))
    print("[toolchain] models available: %s"
          % ", ".join(sorted(f for f in os.listdir(os.path.join(ncnn_dir, "models")) if f.endswith(".param"))))


def stage_extract(ffmpeg, video, frames_dir, fps, frame_format="png"):
    """抽帧 -> 无损 PNG 或高质量 JPG, 返回帧数."""
    t0 = time.time()
    if frame_format == "png":
        cmd = [ffmpeg, "-y", "-v", "error", "-i", video,
               "-vsync", "0", "-start_number", "0",
               "-f", "image2", os.path.join(frames_dir, "%08d.png")]
        ext = "png"
    else:
        cmd = [ffmpeg, "-y", "-v", "error", "-i", video,
               "-vsync", "0", "-start_number", "0", "-qscale:v", "2",
               "-f", "image2", os.path.join(frames_dir, "%08d.jpg")]
        ext = "jpg"
    rc, out, err = run(cmd)
    if rc != 0:
        raise SystemExit("抽帧失败 rc=%d: %s" % (rc, err or out))
    n = len([f for f in os.listdir(frames_dir) if f.endswith("." + ext)])
    dt = time.time() - t0
    print("[extract] %d frames (%s) in %.2fs (%.1f fps)" % (n, ext, dt, n / max(dt, 1e-9)))
    return n, dt


def stage_upscale(ncnn_dir, frames_in, frames_out, model, scale, gpu_id, tile, threads):
    """目录模式调用 realesrgan-ncnn-vulkan.exe, 返回 (耗时, 输出帧数)."""
    exe = os.path.join(ncnn_dir, EXE_NAME)
    cmd = [exe, "-i", frames_in, "-o", frames_out,
           "-n", model, "-s", str(scale), "-f", "png",
           "-t", str(tile), "-j", threads]
    if gpu_id != "auto":
        cmd += ["-g", str(gpu_id)]
    t0 = time.time()
    rc, out, err = run(cmd, timeout=None)
    dt = time.time() - t0
    if rc != 0:
        raise SystemExit("ncnn 超分失败 rc=%d\n%s" % (rc, err or out))
    files = [f for f in os.listdir(frames_out) if f.endswith(".png")]
    print("[upscale] %d frames in %.2fs (%.2f fps, scale=%d model=%s)"
          % (len(files), dt, len(files) / max(dt, 1e-9), scale, model))
    return dt, len(files)


def stage_stitch(ffmpeg, frames_dir, audio_path, fps, out_path, target_w, target_h, crf, preset):
    """拼回 + (可选)音频 + 缩放到精确目标尺寸 (lanczos)."""
    t0 = time.time()
    cmd = [ffmpeg, "-y", "-v", "error",
           "-framerate", str(fps), "-i", os.path.join(frames_dir, "%08d.png")]
    if audio_path:
        cmd += ["-i", audio_path]
    vf = "scale=%d:%d:flags=lanczos,format=yuv420p" % (target_w, target_h)
    cmd += ["-vf", vf, "-c:v", "libx264", "-crf", str(crf), "-preset", preset]
    if audio_path:
        cmd += ["-map", "0:v:0", "-map", "1:a:0?", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", out_path]
    rc, out, err = run(cmd)
    if rc != 0:
        raise SystemExit("拼回失败 rc=%d: %s" % (rc, err or out))
    dt = time.time() - t0
    size = os.path.getsize(out_path)
    print("[stitch] %s (%.2f MB) in %.2fs" % (out_path, size / 1048576.0, dt))
    return dt, size


def main():
    ap = argparse.ArgumentParser(description="Phase1 ncnn-vulkan 超分集成 (抽帧->超分->拼回)")
    ap.add_argument("--input", required=True, help="输入低清视频")
    ap.add_argument("--output", required=True, help="输出视频 (mp4)")
    ap.add_argument("--scale", type=int, default=4, choices=[2, 3, 4], help="超分倍数 (默认 4)")
    ap.add_argument("--model", default="realesr-animevideov3",
                    help="模型 (默认 realesr-animevideov3)")
    ap.add_argument("--target-height", type=int, default=1080, help="输出目标高度 (默认 1080)")
    ap.add_argument("--gpu-id", default="auto", help="ncnn -g 参数 (默认 auto)")
    ap.add_argument("--tile-size", type=int, default=0, help="ncnn tile 大小 (默认 0=auto)")
    ap.add_argument("--threads", default="1:2:2", help="ncnn -j load:proc:save (默认 1:2:2)")
    ap.add_argument("--ncnn-dir", default=NCNN_DIR_DEFAULT, help="ncnn 工具目录")
    ap.add_argument("--ffmpeg", default=FFMPEG_DEFAULT, help="ffmpeg 路径")
    ap.add_argument("--crf", type=int, default=18, help="x264 CRF (默认 18)")
    ap.add_argument("--preset", default="medium", help="x264 preset (默认 medium)")
    ap.add_argument("--tmpdir", default=None, help="临时目录 (默认系统 temp; 与 --keep-frames 配合)")
    ap.add_argument("--keep-frames", action="store_true", help="保留临时帧目录")
    ap.add_argument("--no-audio", action="store_true", help="禁止音频透传")
    ap.add_argument("--frame-format", choices=["png", "jpg"], default="png",
                    help="抽帧格式: png 无损(慢) / jpg 高速(默认 png)")
    ap.add_argument("--json", action="store_true", help="结尾输出 JSON 汇总")
    args = ap.parse_args()

    if args.scale not in MODEL_SCALES[args.model]:
        raise SystemExit("模型 %s 不支持 scale %d (支持: %s)"
                         % (args.model, args.scale, MODEL_SCALES[args.model]))

    if not os.path.isfile(args.input):
        raise SystemExit("输入不存在: %s" % args.input)
    if not os.path.isfile(args.ffmpeg):
        raise SystemExit("ffmpeg 不存在: %s" % args.ffmpeg)

    summary = {"input": args.input, "output": args.output, "scale": args.scale,
               "model": args.model, "target_height": args.target_height,
               "gpu_id": args.gpu_id, "stages": {}, "ok": False}

    print("=" * 64)
    print("Phase1 ncnn-vulkan 超分集成")
    print("  input : %s" % args.input)
    print("  output: %s" % args.output)
    print("=" * 64)

    validate_toolchain(args.ncnn_dir, args.model, args.scale)

    W, H, sar, fps, dur, has_audio = probe_video(args.ffmpeg, args.input)
    print("[probe] %dx%d sar=%d:%d fps=%.3f dur=%.2fs audio=%s"
          % (W, H, sar[0], sar[1], fps, dur or -1, has_audio))
    if fps is None:
        fps = 30.0
    tw, th = target_dims(W, H, sar, args.target_height)
    print("[target] %dx%d (DAR-aware, exact)" % (tw, th))
    summary["input_res"] = "%dx%d" % (W, H)
    summary["fps"] = fps
    summary["duration_sec"] = dur

    tmp_root = args.tmpdir or tempfile.mkdtemp(prefix="phase1_ncnn_")
    frames_in = os.path.join(tmp_root, "frames_in")
    frames_out = os.path.join(tmp_root, "frames_out")
    os.makedirs(frames_in)
    os.makedirs(frames_out)
    print("[tmp] %s" % tmp_root)

    try:
        t_all = time.time()
        n_frames, dt_extract = stage_extract(args.ffmpeg, args.input, frames_in, fps,
                                             args.frame_format)
        dt_up, n_out = stage_upscale(args.ncnn_dir, frames_in, frames_out,
                                     args.model, args.scale, args.gpu_id,
                                     args.tile_size, args.threads)
        if n_out != n_frames:
            raise SystemExit("输出帧数 %d != 输入帧数 %d" % (n_out, n_frames))
        use_audio = has_audio and not args.no_audio
        dt_stitch, size = stage_stitch(args.ffmpeg, frames_out,
                                       args.input if use_audio else None,
                                       fps, args.output, tw, th,
                                       args.crf, args.preset)
        dt_total = time.time() - t_all
        summary["stages"] = {"extract_sec": round(dt_extract, 2),
                             "upscale_sec": round(dt_up, 2),
                             "stitch_sec": round(dt_stitch, 2),
                             "total_sec": round(dt_total, 2)}
        summary["frames"] = n_frames
        summary["upscale_fps"] = round(n_frames / max(dt_up, 1e-9), 2)
        summary["output_bytes"] = size
        summary["output_res"] = "%dx%d" % (tw, th)
        summary["frame_format"] = args.frame_format
        summary["audio_passthrough"] = use_audio
        summary["ok"] = True
        print("[done] total %.2fs" % dt_total)
    finally:
        if not args.keep_frames and args.tmpdir is None:
            shutil.rmtree(tmp_root, ignore_errors=True)
            print("[cleanup] removed %s" % tmp_root)
        elif args.keep_frames:
            print("[keep] frames kept at %s (in=%s out=%s)" % (tmp_root, frames_in, frames_out))

    if args.json:
        print("PHASE1_JSON_START")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print("PHASE1_JSON_END")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
