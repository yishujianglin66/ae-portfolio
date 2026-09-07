"""
M4-C: 一键管线 make_one_mov_pipeline_m4.py（4 层增强版）
========================================================
输入视频段 → L0 运动分级 → L1 分层路由 + L2 光流warp稳定 + L3 自适应精修 →
统一 QC 报告 → alpha BGRA → qtrle MOV + 彩色底预览 mp4。

注: scripts/make_one_mov_pipeline.py 是旧版 autoframe 管线（非 4 层），
本脚本是方案 M4-C 的 4 层能力集成版。

CLI:
  py -3.12 scripts/make_one_mov_pipeline_m4.py \
      --video <path> --start 2000 --frames 500 --outdir <dir> [--stabilize]

子步骤:
  1. motion_classifier (py -3.12)           → {outdir}/motion_levels.json
  2. infer_segment_video_enhanced (venv)    → {outdir}/mask_*.png
  3. benchmark_qc_matting (py -3.12)        → {outdir}/qc_report.json
  4. BGRA + qtrle MOV + 彩色底预览 mp4      → {outdir}/alpha_{frames}f.mov 等
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
VENV_PY = r"D:\AE-Work\venv-sam2\Scripts\python.exe"
PY312 = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"
SAM2_CKPT = r"D:\AE-Work\models\sam2\sam2.1_hiera_large.pt"
YOLO_PATH = str(ROOT / "models" / "yolov8x.pt")


def run(cmd: list[str], cwd: str, log: Path, timeout: int = 5400) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["TQDM_DISABLE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    with open(str(log), "w", encoding="utf-8") as f:
        p = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, env=env, timeout=timeout)
    return p.returncode


def step1_motion_classifier(video, start, frames, outdir) -> Path:
    ml_json = outdir / "motion_levels.json"
    if not ml_json.exists():
        cmd = [PY312, str(ROOT / "scripts" / "motion_classifier.py"),
               "--video", str(video), "--start", str(start), "--frames", str(frames),
               "--outdir", str(outdir)]
        rc = run(cmd, str(ROOT), outdir / "_step1_motion.log")
        if rc != 0:
            raise RuntimeError(f"motion_classifier failed rc={rc}")
    return ml_json


def step2_infer(video, start, frames, outdir, ml_json, stabilize: bool) -> Path:
    payload = {
        "video_path": str(video), "start_frame": start, "expected_frames": frames,
        "keyframe_interval": 6, "enable_edge_refine": True,
        "enable_temporal_stabilize": stabilize,
        "motion_levels_path": str(ml_json),
        "sam2_checkpoint": SAM2_CKPT, "model_cfg": "sam2.1_hiera_l.yaml", "sam_variant": "large",
        "yolov8x_path": YOLO_PATH,
        "face_conf": 0.35, "face_expand": 4.0, "yolo_conf": 0.05,
        "max_boxes_per_frame": 10, "device": "cuda", "haar_path": None, "lbp_path": None,
    }
    params_json = outdir / "_pipeline_infer.json"
    params_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    rc = run([VENV_PY, "-u", str(ROOT / "scripts" / "infer_segment_video_enhanced.py"), str(params_json)],
             str(ROOT), outdir / "_step2_infer.log")
    if rc != 0:
        raise RuntimeError(f"infer failed rc={rc}")
    ok = Path(str(params_json) + ".ok")
    if not ok.exists():
        raise RuntimeError("infer finished without .ok")
    return ok


def step3_qc(mask_dir, result_ok, outdir) -> Path:
    rep = outdir / "qc_report.json"
    cmd = [PY312, str(ROOT / "scripts" / "benchmark_qc_matting.py"),
           "--masks", str(mask_dir), "--result", str(result_ok), "--out", str(rep)]
    run(cmd, str(ROOT), outdir / "_step3_qc.log")
    return rep


def step4_mov(mask_dir, video, start, frames, outdir) -> dict:
    bgra_dir = outdir / "bgra_frames"
    bgra_dir.mkdir(parents=True, exist_ok=True)
    mov_out = outdir / f"alpha_{frames}f.mov"
    prev_out = outdir / "alpha_preview_colored_bg.mp4"
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    nonempty = 0
    t0 = time.time()
    preview_dir = outdir / "_preview_frames"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for fi in range(frames):
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        gi = start + fi
        mp = mask_dir / f"mask_{gi:05d}.png"
        mask = np.zeros(frame.shape[:2], np.uint8)
        if mp.exists():
            buf = np.fromfile(str(mp), dtype=np.uint8)
            if buf.size:
                mask = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
                if mask.shape[:2] != frame.shape[:2]:
                    mask = cv2.resize(mask, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_NEAREST)
        if np.count_nonzero(mask) > 100:
            nonempty += 1
        cv2.imencode(".png", np.dstack([frame, mask]), [int(cv2.IMWRITE_PNG_COMPRESSION), 1])[1].tofile(
            str(bgra_dir / f"frame_{fi:05d}.png"))
        bg = np.full(frame.shape, (80, 180, 255), np.uint8)  # BGR 橙黄底
        alpha3 = (mask.astype(np.float32) / 255.0)[..., None]
        comp = (frame.astype(np.float32) * alpha3 + bg.astype(np.float32) * (1 - alpha3)).astype(np.uint8)
        cv2.imencode(".png", comp)[1].tofile(str(preview_dir / f"p_{fi:05d}.png"))
        if (fi + 1) % 100 == 0:
            print(f"  [MOV] {fi+1}/{frames} nonempty={nonempty} {time.time()-t0:.0f}s", file=sys.stderr)
    cap.release()
    fps = _probe_fps(video)
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(fps),
                    "-start_number", "0", "-i", str(bgra_dir / "frame_%05d.png"),
                    "-c:v", "qtrle", "-pix_fmt", "yuva444p10le", "-movflags", "+faststart", str(mov_out)],
                   check=False)
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(fps),
                    "-start_number", "0", "-i", str(preview_dir / "p_%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(prev_out)], check=False)
    return {"mov": str(mov_out), "mov_size_mb": round(mov_out.stat().st_size / 1048576, 2) if mov_out.exists() else 0,
            "preview": str(prev_out), "nonempty": nonempty, "frames": frames}


def _probe_fps(video: Path) -> float:
    try:
        p = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(video)],
                           capture_output=True, text=True, timeout=60)
        a, b = p.stdout.strip().split("/")
        return round(int(a) / max(1, int(b)), 3)
    except Exception:
        return 30.0


def main() -> int:
    ap = argparse.ArgumentParser(description="M4-C 一键管线：视频段 → MOV + QC 报告（4 层增强版）")
    ap.add_argument("--video", required=True)
    ap.add_argument("--start", type=int, default=2000)
    ap.add_argument("--frames", type=int, default=500)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--stabilize", action="store_true", help="启用 Layer2A 光流warp稳定")
    ap.add_argument("--skip-infer", action="store_true", help="mask 已存在，跳过步骤1-2")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    ml_json = step1_motion_classifier(args.video, args.start, args.frames, outdir)
    print(f"[PIPE] L0 motion_levels: {ml_json}", file=sys.stderr)
    if not args.skip_infer:
        result_ok = step2_infer(args.video, args.start, args.frames, outdir, ml_json, args.stabilize)
        print(f"[PIPE] L1+L2+L3 infer done: {result_ok}", file=sys.stderr)
    else:
        result_ok = outdir / "_pipeline_infer.json.ok"
    qc_rep = step3_qc(outdir, result_ok, outdir)
    print(f"[PIPE] QC: {qc_rep}", file=sys.stderr)
    mov = step4_mov(outdir, args.video, args.start, args.frames, outdir)
    summary = {"ok": True, "elapsed_s": round(time.time() - t_start, 1), "outdir": str(outdir),
               "motion_levels": str(ml_json), "qc_report": str(qc_rep), "mov": mov}
    (outdir / "pipeline_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
