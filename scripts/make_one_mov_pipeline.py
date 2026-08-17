"""
一键漫剪抠像流水线：单 MP4 → mask 推理 (HAAR+YOLOv8x+LAB+SAM2.1) → BGRA PNG → qtrle argb MOV → 快速 QC。

严格复用已验证资产：
- 推理链路：long_video_autoframe_anime.py（venv-sam2 子进程 + params.json + 500帧分段 + retry_cfg 三档回退 + QC gate）
- MOV 合成 ：build_onepiece_mov.py（cv2 中文路径兼容 + FFmpeg qtrle yuva444p10le）
- 快速 QC ：output/_qc_onepiece_fast.py（ffprobe meta + -ss seek 抽帧 alpha 校验）
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "output" / "one_pipeline"
WORK_ROOT = Path(r"D:\AE-Work")
TEMP_ROOT = WORK_ROOT / "output" / "segment_tmp_pipeline"

VENV_PY = WORK_ROOT / "venv-sam2" / "Scripts" / "python.exe"
DEFAULT_YOLO_PT = WORK_ROOT / "models" / "yolo" / "yolov8x.pt"
DEFAULT_SAM_CKPT = {
    "large": WORK_ROOT / "models" / "sam2" / "sam2.1_hiera_large.pt",
    "base_plus": WORK_ROOT / "models" / "sam2" / "sam2.1_hiera_base_plus.pt",
    "small": WORK_ROOT / "models" / "sam2" / "sam2.1_hiera_small.pt",
}
INFER_SCRIPT = SCRIPTS_DIR / "infer_segment_autoframe_anime.py"
INFER_SCRIPT_ENHANCED = SCRIPTS_DIR / "infer_segment_video_enhanced.py"  # M4-C: 4层链路引擎
MOTION_CLASSIFIER = SCRIPTS_DIR / "motion_classifier.py"  # M4-C: L0 运动分级前置
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"

SEG_LEN = 500
SEG_TIMEOUT_S = 3 * 3600
MAX_RETRY = 2
QC_THRESH = 0.18
QC_NONEMPTY_FRAMES = 0.50
PIXEL_QC_SAMPLE = 15


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="make_one_mov_pipeline.py",
        description="一键漫剪抠像流水线：MP4 → mask(SAM2.1 auto_frame) → BGRA PNG → qtrle argb MOV → 快速 QC",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--input", required=True, help="输入 MP4 路径（支持中文）")
    p.add_argument("--output_dir", default=None, help="输出目录，默认 output/one_pipeline/{slug}")
    p.add_argument("--variant", choices=["small", "base_plus", "large"], default="large", help="SAM2.1 模型规格")
    p.add_argument("--yolo_conf", type=float, default=0.3, help="fallback YOLOv8x conf 阈值（0.3=精度优先，2026-08-14 校准）")
    p.add_argument("--face_conf", type=float, default=0.35, help="anime face detector conf 阈值")
    p.add_argument("--yolo_pt", default=str(DEFAULT_YOLO_PT), help="YOLOv8x 权重路径")
    p.add_argument("--sam_ckpt", default=None, help="SAM2.1 checkpoint 路径（默认按 variant 自动选）")
    p.add_argument("--no_skip", action="store_true", help="强制重跑，不跳过已有 mask/mov")
    # M4-C: 4层链路引擎（运动分级路由 + 光流时序稳定 + 自适应边缘精修）
    p.add_argument("--engine", choices=["auto_frame", "enhanced"], default="auto_frame",
                   help="推理引擎：auto_frame=老链路；enhanced=4层链路(L0运动分级→L1分层路由→L2时序稳定→L3自适应边缘)")
    p.add_argument("--start_frame", type=int, default=0, help="enhanced: 起始全局帧号（默认 0）")
    p.add_argument("--frames", type=int, default=0, help="enhanced: 帧数（0=到视频尾）")
    p.add_argument("--motion_levels", default="", help="enhanced: 现成 motion_levels.json（不给则自动跑 motion_classifier）")
    p.add_argument("--keyframe_interval", type=int, default=6, help="enhanced: keyframe_interval")
    p.add_argument("--max_segs", type=int, default=0, help="enhanced 全片模式最多跑 N 段（0=全部；用于分段验证）")
    return p.parse_args()


def ffprobe_video_info(path: Path) -> dict:
    cmd = [FFPROBE, "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
           "-of", "json", str(path)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    try:
        s = json.loads(p.stdout)["streams"][0]
        w, h = int(s.get("width", 0)), int(s.get("height", 0))
        rf = s.get("r_frame_rate", "24/1").split("/")
        fps = round(int(rf[0]) / max(1, int(rf[1])), 2)
        nf = int(s.get("nb_frames") or 0)
        return {"width": w, "height": h, "fps": fps, "nb_frames": nf}
    except Exception as e:
        return {"error": str(e), "width": 0, "height": 0, "fps": 24.0, "nb_frames": 0}


def cv2_imread_gray(p: str) -> np.ndarray | None:
    if not Path(p).exists():
        return None
    buf = np.fromfile(p, dtype=np.uint8)
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)


def cv2_imread_bgr(p: str) -> np.ndarray | None:
    if not Path(p).exists():
        return None
    buf = np.fromfile(p, dtype=np.uint8)
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def cv2_imwrite_png(p: str, img: np.ndarray, compress: int = 1) -> bool:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", img, [int(cv2.IMWRITE_PNG_COMPRESSION), compress])
    if not ok:
        return False
    buf.tofile(p)
    return True


def run_segment_inference(params_path: Path, timeout: int,
                          python: str | None = None, script: Path | None = None) -> dict | None:
    marker_ok = str(params_path) + ".ok"
    marker_fail = str(params_path) + ".fail"
    for m in (marker_ok, marker_fail):
        if os.path.exists(m):
            try:
                os.remove(m)
            except Exception:
                pass
    py = python or str(VENV_PY)
    sc = script or INFER_SCRIPT
    try:
        p = subprocess.run(
            [py, str(sc), str(params_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(PROJECT_ROOT),
        )
        rc, out, err = p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired as e:
        rc, out, err = -99, e.stdout or "", (e.stderr or "") + f"\n[TIMEOUT {timeout}s]"
    if os.path.exists(marker_ok):
        try:
            with open(marker_ok, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            pass
    if os.path.exists(marker_fail):
        try:
            with open(marker_fail, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            pass
    for line in (out + "\n" + err).splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except Exception:
                pass
    return {"status": "fail", "rc": rc, "error": "no result parsed",
            "stdout_tail": out[-500:], "stderr_tail": err[-500:]}


def copy_segment_masks_with_verify(
    src_mask_dir: Path, dst_mask_dir: Path, start_frame: int, expected: int
) -> tuple[int, float, int]:
    src_sorted = sorted(src_mask_dir.glob("mask_*.png"))
    src_paths = [str(p) for p in src_sorted]
    sample_idxs_global = np.linspace(start_frame, start_frame + expected - 1,
                                     min(PIXEL_QC_SAMPLE, expected), dtype=int).tolist()
    sample_src_map: dict[int, str] = {}
    for p in src_paths:
        try:
            gi = int(Path(p).stem.split("_")[1])
        except Exception:
            continue
        sample_src_map[gi] = p
    sample_src_paths = [sample_src_map[gi] for gi in sample_idxs_global if gi in sample_src_map]

    copy_script = f"""
import shutil, sys, os, json, cv2, numpy as np
from pathlib import Path

srcs = {src_paths!r}
dsts_dir = r'{str(dst_mask_dir)}'
samples = {sample_src_paths!r}
expected = {expected}
start = {start_frame}
end = start + expected

os.makedirs(dsts_dir, exist_ok=True)
copied = 0
copy_err = 0
for s in srcs:
    try:
        d = os.path.join(dsts_dir, os.path.basename(s))
        shutil.copy2(s, d)
        copied += 1
    except Exception:
        copy_err += 1

actual = 0
for p in Path(dsts_dir).glob('mask_*.png'):
    try:
        idx = int(p.stem.split('_')[1])
    except Exception:
        continue
    if start <= idx < end and p.stat().st_size >= 10:
        actual += 1

sample_ne = 0
sample_total = 0
sample_ne_frames = 0
sample_frames_run = 0
for sp in samples:
    try:
        buf = np.fromfile(sp, dtype=np.uint8)
        if buf.size == 0: continue
        img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
        if img is None: continue
        nz = int(np.count_nonzero(img))
        total_px = int(img.shape[0] * img.shape[1])
        sample_ne += nz
        sample_total += total_px
        sample_frames_run += 1
        if nz / total_px > 1e-4:
            sample_ne_frames += 1
    except Exception:
        pass
ratio = (sample_ne / sample_total) if sample_total > 0 else 0.0
ne_frac = (sample_ne_frames / sample_frames_run) if sample_frames_run > 0 else 0.0
print(f"RESULT copied={{copied}} actual={{actual}} copy_err={{copy_err}} expected={{expected}}"
      f" sample_frames={{sample_frames_run}} sample_ratio={{ratio:.6f}} sample_ne_frames={{sample_ne_frames}} sample_ne_frac={{ne_frac:.3f}}")
sys.exit(0 if actual > 0 else 2)
"""
    ts = int(time.time() * 1000)
    tmp_py = TEMP_ROOT / f"_cpv_{ts}.py"
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    with open(tmp_py, "w", encoding="utf-8") as f:
        f.write(copy_script)
    try:
        p = subprocess.run(
            [str(sys.executable), str(tmp_py)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=1800, cwd=str(PROJECT_ROOT),
        )
        out, err, rc = p.stdout or "", p.stderr or "", p.returncode
    except subprocess.TimeoutExpired as e:
        out, err, rc = e.stdout or "", (e.stderr or "") + "\n[TIMEOUT 1800s]", -99
    finally:
        try:
            tmp_py.unlink(missing_ok=True)
        except Exception:
            pass

    actual = 0
    ratio = 0.0
    sample_ne_frames = 0
    try:
        for line in out.strip().splitlines():
            if line.startswith("RESULT"):
                for part in line.split():
                    if "=" in part:
                        k, v = part.split("=", 1)
                        if k == "actual": actual = int(v)
                        elif k == "sample_ratio": ratio = float(v)
                        elif k == "sample_ne_frames": sample_ne_frames = int(v)
    except Exception:
        pass
    return actual, ratio, sample_ne_frames


def step2_mask_inference(
    input_mp4: Path,
    mask_dir: Path,
    total_frames: int,
    variant: str,
    sam_ckpt: Path,
    yolo_pt: Path,
    face_conf: float,
    yolo_conf: float,
    no_skip: bool,
    seg_tmp_root: Path,
    engine: str = "auto_frame",
    motion_levels: str = "",
    start_frame: int = 0,
    frames: int = 0,
    keyframe_interval: int = 6,
    max_segs: int = 0,
) -> dict:
    print("\n" + "=" * 70)
    print(f"STEP 2: mask 推理 → {mask_dir}")
    print(f"  总帧数={total_frames}, 每段≤{SEG_LEN}, variant={variant}, MAX_RETRY={MAX_RETRY}")
    print(f"  SAM_CKPT={sam_ckpt} (exists={sam_ckpt.exists()})")
    print(f"  YOLO_PT={yolo_pt} (exists={yolo_pt.exists()})")
    print(f"  VENV_PY={VENV_PY} (exists={VENV_PY.exists()})")
    print(f"  INFER_SCRIPT={INFER_SCRIPT} (exists={INFER_SCRIPT.exists()})")
    print("=" * 70)

    t0 = time.time()
    mask_dir.mkdir(parents=True, exist_ok=True)
    seg_tmp_root.mkdir(parents=True, exist_ok=True)
    if no_skip:
        for old in mask_dir.glob("mask_*.png"):
            try:
                old.unlink()
            except Exception:
                pass

    existing_count = 0
    if not no_skip:
        existing_count = sum(1 for _ in mask_dir.glob("mask_*.png"))
        need_frames = frames if (engine == "enhanced" and frames) else total_frames
        if engine == "enhanced" and max_segs > 0:
            need_frames = min(need_frames, max_segs * SEG_LEN)
        if existing_count >= int(need_frames * 0.95):
            dt = time.time() - t0
            print(f"  [SKIP] 已有 mask {existing_count}/{need_frames}，跳过推理")
            return {"status": "skip", "existing_masks": existing_count, "total_frames": total_frames,
                    "mask_count": existing_count, "coverage": 1.0,
                    "elapsed_s": round(dt, 1), "segments": []}

    sam_ckpt_str = str(sam_ckpt)
    default_variant = variant
    default_cfg = ""
    full_levels: dict | None = None
    full_levels_path = ""
    if engine == "enhanced":
        # 4层链路：--start_frame/--frames 指定单段；否则全片自动分段（每段 SEG_LEN）
        if start_frame or frames:
            seg_starts = [start_frame]
            seg_lens = [frames if frames else (total_frames - start_frame)]
        else:
            seg_starts = [seg_i * SEG_LEN for seg_i in range((total_frames + SEG_LEN - 1) // SEG_LEN)]
            seg_lens = [min(SEG_LEN, total_frames - s) for s in seg_starts]
        # L0 运动分级：优先现成全片 levels；否则全片跑一次（8881 帧 CPU ~4min）
        if motion_levels and os.path.exists(motion_levels):
            full_levels_path = motion_levels
        else:
            ml_out = seg_tmp_root / "motion_levels_full"
            ml_out.mkdir(parents=True, exist_ok=True)
            full_levels_path = str(ml_out / "motion_levels.json")
            print(f"  [L0] 全片运动分级 motion_classifier --frames {total_frames} ...")
            r_mc = subprocess.run(
                [sys.executable, str(MOTION_CLASSIFIER), "--video", str(input_mp4),
                 "--start", "0", "--frames", str(total_frames),
                 "--outdir", str(ml_out)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=3600, cwd=str(PROJECT_ROOT))
            if r_mc.returncode != 0 or not os.path.exists(full_levels_path):
                return {"status": "fail", "error": "motion_classifier failed", "stderr": r_mc.stderr[-500:]}
        with open(full_levels_path, "r", encoding="utf-8") as _f:
            full_levels = json.load(_f)
        full_motion = full_levels.get("motion_level") or []
        flow_cache_dir = full_levels.get("flow_cache_dir") or ""
    else:
        seg_starts = [seg_i * SEG_LEN for seg_i in range((total_frames + SEG_LEN - 1) // SEG_LEN)]
        seg_lens = [min(SEG_LEN, total_frames - s) for s in seg_starts]
    if engine == "enhanced" and max_segs > 0 and len(seg_starts) > max_segs:
        seg_starts = seg_starts[:max_segs]
        seg_lens = seg_lens[:max_segs]
        print(f"  [ENHANCED] 限量验证模式：只跑前 {max_segs} 段")
    total_segs = len(seg_starts)
    summary_segments: list[dict] = []

    for seg_i, (start_frame, seg_len) in enumerate(zip(seg_starts, seg_lens)):
        seg_name = f"seg{seg_i:03d}_{start_frame}_{start_frame + seg_len}"
        seg_dir = seg_tmp_root / seg_name
        seg_mask_dir = seg_dir / "masks"
        params_path = seg_dir / "params.json"
        seg_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n  [{seg_i + 1}/{total_segs}] {seg_name} (len={seg_len})")
        # enhanced: 段级 levels 切片（infer 脚本按段内 idx 索引，需段视角文件 + flow 全局偏移）
        seg_ml_path = ""
        if engine == "enhanced" and full_levels is not None:
            seg_ml = dict(full_levels)
            seg_ml["start_frame"] = start_frame
            seg_ml["expected_frames"] = seg_len
            seg_ml["motion_level"] = full_motion[start_frame:start_frame + seg_len]
            if not seg_ml.get("flow_cache_dir"):
                seg_ml["flow_cache_dir"] = flow_cache_dir
            seg_ml["flow_offset"] = start_frame  # 全片 flow_cache 全局帧号命名 → 段内 idx + offset
            seg_ml_path = str(seg_dir / "motion_levels_seg.json")
            with open(seg_ml_path, "w", encoding="utf-8") as _f:
                json.dump(seg_ml, _f, ensure_ascii=False, indent=2)

        small_ckpt = str(DEFAULT_SAM_CKPT["small"])
        if engine == "enhanced":
            retry_cfg: list[tuple[str, dict, str, str]] = [
                ("enhanced", {
                    "keyframe_interval": keyframe_interval,
                    "enable_edge_refine": True,
                    "enable_temporal_stabilize": True,
                    "motion_levels_path": seg_ml_path or motion_levels,
                    "face_conf": face_conf, "face_expand": 4.0,
                    "yolo_conf": yolo_conf, "max_boxes_per_frame": 10,
                    "sam_variant": default_variant,
                }, sam_ckpt_str, default_cfg),
            ]
        else:
            retry_cfg: list[tuple[str, dict, str, str]] = [
                ("default", {
                    "face_conf": face_conf, "face_expand": 4.0,
                    "yolo_conf": yolo_conf, "max_boxes_per_frame": 10,
                    "sam_variant": default_variant,
                }, sam_ckpt_str, default_cfg),
                ("low_face_conf", {
                    "face_conf": max(0.08, face_conf * 0.35), "face_expand": 5.5,
                    "yolo_conf": max(0.01, yolo_conf * 0.4), "max_boxes_per_frame": 15,
                    "sam_variant": default_variant,
                }, sam_ckpt_str, default_cfg),
                ("small_model", {
                    "face_conf": 0.08, "face_expand": 7.0,
                    "yolo_conf": 0.01, "max_boxes_per_frame": 20,
                    "sam_variant": "small",
                }, small_ckpt, ""),
            ]
        best_result: dict | None = None
        best_metrics = (-1, 0.0, 0)
        best_label = ""
        attempt = 0
        for label, overrides, ck, cn in retry_cfg[: MAX_RETRY + 1]:
            attempt += 1
            if engine == "enhanced":
                params = {
                    "video_path": str(input_mp4),
                    "start_frame": start_frame,
                    "expected_frames": seg_len,
                    "output_dir": str(seg_dir),
                    "mask_dir": str(seg_mask_dir),
                    "sam2_checkpoint": ck,
                    "model_cfg": cn,
                    "yolov8x_path": str(yolo_pt),
                    **overrides,
                }
            else:
                params = {
                    "video_path": str(input_mp4),
                    "start_frame": start_frame,
                    "expected_frames": seg_len,
                    "mask_dir": str(seg_mask_dir),
                    "sam2_checkpoint": ck,
                    "model_cfg": cn,
                    "yolov8x_path": str(yolo_pt),
                    **overrides,
                }
            if seg_mask_dir.exists():
                shutil.rmtree(seg_mask_dir, ignore_errors=True)
            seg_mask_dir.mkdir(parents=True, exist_ok=True)
            with open(params_path, "w", encoding="utf-8") as f:
                json.dump(params, f, ensure_ascii=False, indent=2)
            print(f"    attempt {attempt}/{MAX_RETRY + 1} [{label}] start...")
            t_a = time.time()
            if engine == "enhanced":
                # 用当前解释器（py -3.12，已验证 torch/CUDA/warplayer）跑 4 层脚本
                result = run_segment_inference(params_path, timeout=SEG_TIMEOUT_S,
                                               python=sys.executable, script=INFER_SCRIPT_ENHANCED)
            else:
                result = run_segment_inference(params_path, timeout=SEG_TIMEOUT_S)
            dt_a = time.time() - t_a
            status = (result or {}).get("status", "fail")
            short_res = json.dumps(result or {}, ensure_ascii=False)[:200]
            print(f"    attempt {attempt} status={status} in {dt_a:.1f}s: {short_res}")
            if status != "ok":
                continue
            actual, ratio, sample_ne = copy_segment_masks_with_verify(
                seg_mask_dir, mask_dir, start_frame, seg_len,
            )
            sample_total_for_frac = min(PIXEL_QC_SAMPLE, seg_len)
            ne_frac = (sample_ne / sample_total_for_frac) if sample_total_for_frac > 0 else 0.0
            print(f"    copy→master: actual={actual}/{seg_len}, avg_alpha_ratio={ratio:.4f}, "
                  f"sample_nonempty_frames={sample_ne}/{sample_total_for_frac} (ne_frac={ne_frac:.2f})")
            metrics = (actual, ratio, sample_ne)
            pass_qc = (actual >= int(seg_len * 0.95) and
                       (ratio >= QC_THRESH or ne_frac >= QC_NONEMPTY_FRAMES or actual >= seg_len * 0.99))
            if metrics > best_metrics:
                best_metrics = metrics
                best_result = dict(result or {})
                best_result.update({
                    "copy_actual": actual, "sample_ratio": ratio,
                    "sample_ne_frames": sample_ne, "ne_frac": ne_frac,
                    "attempt_label": label, "seg_dt_sec": dt_a,
                })
                best_label = label
            if pass_qc:
                break
        if best_result is None:
            summary_segments.append({
                "seg": seg_i, "status": "fail_all_attempts",
                "start": start_frame, "len": seg_len,
                "attempt_label": best_label or "none",
                "last_result": json.dumps(result or {}, ensure_ascii=False)[:300],
            })
            print(f"    [WARN] 段 {seg_i} 全部尝试失败，可能导致该段 mask 缺失")
            continue
        actual_good = best_result.get("copy_actual", 0) >= int(seg_len * 0.95)
        qc_ok = ((best_result.get("sample_ratio", 0) >= QC_THRESH) or
                 (best_result.get("ne_frac", 0) >= QC_NONEMPTY_FRAMES))
        summary_segments.append({
            "seg": seg_i,
            "status": "ok" if (actual_good and qc_ok) else "qc_warn",
            "start": start_frame, "len": seg_len,
            "attempt": best_result.get("attempt_label"),
            "processed": best_result.get("processed"),
            "nonempty": best_result.get("nonempty"),
            "copy_actual": best_result.get("copy_actual"),
            "sample_ratio": round(best_result.get("sample_ratio", 0), 4),
            "sample_ne_frames": best_result.get("sample_ne_frames"),
            "ne_frac": round(best_result.get("ne_frac", 0), 3),
            "fps": round(best_result.get("fps", 0), 2),
            "dt_sec": round(best_result.get("seg_dt_sec", 0), 1),
        })
        shutil.rmtree(seg_mask_dir, ignore_errors=True)

    mask_count = sum(1 for _ in mask_dir.glob("mask_*.png"))
    dt = time.time() - t0
    result = {
        "status": "ok" if mask_count >= int(total_frames * 0.8) else "warn",
        "mask_dir": str(mask_dir),
        "mask_count": mask_count,
        "total_frames": total_frames,
        "coverage": round(mask_count / max(1, total_frames), 4),
        "segments": summary_segments,
        "elapsed_s": round(dt, 1),
    }
    print(f"\n  STEP 2 DONE: {mask_count}/{total_frames} mask, coverage={result['coverage']:.2%}, elapsed={dt:.0f}s")
    return result


def step3_build_mov(
    input_mp4: Path,
    mask_dir: Path,
    mov_path: Path,
    total_frames: int,
    fps: float,
    no_skip: bool,
    alpha_dir: Path,
    start_frame: int = 0,
) -> dict:
    print("\n" + "=" * 70)
    print(f"STEP 3: MOV 合成 → {mov_path}")
    print(f"  total_frames={total_frames}, fps={fps}")
    print("=" * 70)
    t0 = time.time()

    if not no_skip and mov_path.exists() and mov_path.stat().st_size > 1024:
        dt = time.time() - t0
        size_mb = round(mov_path.stat().st_size / 1024 / 1024, 1)
        print(f"  [SKIP] MOV 已存在: {mov_path} ({size_mb} MB)")
        return {"status": "skip", "mov_path": str(mov_path), "size_mb": size_mb,
                "elapsed_s": round(dt, 1)}

    Path(mov_path).parent.mkdir(parents=True, exist_ok=True)
    if alpha_dir.exists():
        shutil.rmtree(alpha_dir, ignore_errors=True)
    alpha_dir.mkdir(parents=True, exist_ok=True)

    mask_paths_sorted = sorted(mask_dir.glob("mask_*.png"))
    mask_by_idx: dict[int, str] = {}
    for p in mask_paths_sorted:
        try:
            idx = int(p.stem.split("_")[1])
        except Exception:
            continue
        mask_by_idx[idx] = str(p)
    print(f"  加载 mask 索引: {len(mask_by_idx)} 个文件")

    cap = cv2.VideoCapture(str(input_mp4))
    if not cap.isOpened():
        return {"status": "fail", "error": f"无法打开源视频: {input_mp4}", "elapsed_s": round(time.time() - t0, 1)}
    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    max_idx = total_frames if total_frames > 0 else (max(mask_by_idx.keys()) + 1 if mask_by_idx else 0)
    written = 0
    missing_mask = 0
    empty_mask = 0
    nonempty_frames = 0
    log_every = 500
    t_b = time.time()
    for i in range(max_idx):
        ret, frame = cap.read()
        if not ret or frame is None:
            print(f"  [WARN] src EOF at fi={i}/{max_idx}")
            break
        h, w = frame.shape[:2]
        mask_path = mask_by_idx.get(start_frame + i)
        if mask_path is None:
            missing_mask += 1
            alpha = np.zeros((h, w), dtype=np.uint8)
        else:
            buf = np.fromfile(mask_path, dtype=np.uint8)
            if buf.size == 0:
                alpha = np.zeros((h, w), dtype=np.uint8)
                empty_mask += 1
            else:
                alpha = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
                if alpha is None:
                    alpha = np.zeros((h, w), dtype=np.uint8)
                    empty_mask += 1
        if np.count_nonzero(alpha) > 10:
            nonempty_frames += 1
        if alpha.shape[:2] != (h, w):
            alpha = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_NEAREST)
        b, g, r = cv2.split(frame)
        bgra = cv2.merge([b, g, r, alpha])
        out_p = alpha_dir / f"frame_{i:05d}.png"
        ok, buf = cv2.imencode(".png", bgra, [int(cv2.IMWRITE_PNG_COMPRESSION), 1])
        if ok:
            buf.tofile(str(out_p))
            written += 1
        if (i + 1) % log_every == 0:
            print(f"  BGRA: {i + 1}/{max_idx}  written={written}  missing={missing_mask}  empty={empty_mask}  "
                  f"elapsed={time.time() - t_b:.0f}s  fps={(i + 1) / max(0.01, time.time() - t_b):.1f}")
    cap.release()
    bgra_dt = time.time() - t_b
    print(f"  BGRA 序列完成: {written}/{max_idx}  elapsed={bgra_dt:.0f}s  "
          f"(missing={missing_mask}, empty={empty_mask}, nonempty={nonempty_frames})")

    if mov_path.exists():
        try:
            mov_path.unlink()
        except Exception:
            pass
    pat = str(alpha_dir / "frame_%05d.png")
    cmd = [
        FFMPEG, "-hide_banner", "-loglevel", "error", "-stats", "-y",
        "-framerate", str(fps),
        "-start_number", "0",
        "-i", pat,
        "-c:v", "qtrle", "-pix_fmt", "yuva444p10le",
        str(mov_path),
    ]
    print(f"  FFmpeg 合成: qtrle + yuva444p10le ...")
    t_f = time.time()
    p = subprocess.run(cmd, capture_output=False, timeout=4 * 3600)
    ffmpeg_dt = time.time() - t_f
    rc = p.returncode
    size_mb = int(mov_path.stat().st_size / 1024 / 1024) if mov_path.exists() else 0
    ok = (rc == 0 and size_mb > 0 and written >= max_idx * 0.9)
    print(f"  FFmpeg rc={rc} size={size_mb}MB elapsed={ffmpeg_dt:.0f}s  → {'OK' if ok else 'FAIL'}")

    shutil.rmtree(alpha_dir, ignore_errors=True)
    dt = time.time() - t0
    if not ok:
        return {"status": "fail", "ffmpeg_rc": rc, "bgra_written": written,
                "missing_mask": missing_mask, "empty_mask": empty_mask,
                "size_mb": size_mb, "elapsed_s": round(dt, 1)}
    return {
        "status": "ok",
        "mov_path": str(mov_path),
        "size_mb": size_mb,
        "bgra_written": written,
        "total_frames": max_idx,
        "missing_mask": missing_mask,
        "empty_mask": empty_mask,
        "nonempty_frames": nonempty_frames,
        "bgra_elapsed_s": round(bgra_dt, 1),
        "ffmpeg_elapsed_s": round(ffmpeg_dt, 1),
        "elapsed_s": round(dt, 1),
    }


def ffprobe_mov_meta(mov: Path) -> dict:
    r = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,pix_fmt,width,height,nb_frames,r_frame_rate",
         "-of", "json", str(mov)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    try:
        s = json.loads(r.stdout)["streams"][0]
        rf = s.get("r_frame_rate", "0/1").split("/")
        fps = round(int(rf[0]) / max(1, int(rf[1])), 2)
        pix_fmt = s.get("pix_fmt") or ""
        has_alpha = any(k in pix_fmt for k in ["argb", "rgba", "bgra", "abgr", "yuva"])
        codec_ok = (s.get("codec_name") or "") == "qtrle"
        return {
            "codec": s.get("codec_name"),
            "pix_fmt": pix_fmt,
            "width": int(s.get("width", 0)),
            "height": int(s.get("height", 0)),
            "nb_frames": int(s.get("nb_frames") or 0),
            "fps": fps,
            "has_alpha": has_alpha,
            "codec_ok": codec_ok,
            "meta_ok": (codec_ok and has_alpha),
        }
    except Exception as e:
        return {"error": str(e), "meta_ok": False}


def sample_fast_qc(mov: Path, frame_idxs: list[int], fps: float, tmp_root: Path) -> list[tuple[int, float]]:
    tmpd = Path(tempfile.mkdtemp(prefix="qcpipe_", dir=str(tmp_root)))
    results: list[tuple[int, float]] = []
    try:
        for idx in frame_idxs:
            t_sec = max(0.0, (idx - 1) / max(1, fps))
            out = tmpd / f"f{idx:05d}.png"
            if out.exists():
                out.unlink()
            cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                   "-ss", f"{t_sec:.3f}",
                   "-i", str(mov),
                   "-frames:v", "2",
                   "-pix_fmt", "rgba",
                   str(tmpd / f"tmp{idx:05d}_%03d.png")]
            subprocess.run(cmd, capture_output=True, timeout=120)
            cands = sorted(tmpd.glob(f"tmp{idx:05d}_*.png"))
            pick = cands[-1] if cands else None
            if pick is None or not pick.exists():
                results.append((idx, 0.0))
                continue
            try:
                pick.rename(out)
            except Exception:
                out = pick
            buf = np.fromfile(str(out), dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
            if img is None or img.ndim < 3 or img.shape[2] < 4:
                results.append((idx, 0.0))
                continue
            a = img[:, :, 3]
            nz = int((a > 0).sum())
            tot = int(a.size)
            r = nz / tot if tot else 0
            results.append((idx, r))
            print(f"    frame #{idx:5d}  alpha_ratio={r:.4f}  (nz={nz}/{tot} max={int(a.max())})", flush=True)
        return results
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


def step4_fast_qc(mov_path: Path, qc_json_path: Path, tmp_root: Path) -> dict:
    print("\n" + "=" * 70)
    print(f"STEP 4: 快速 QC → {qc_json_path}")
    print("=" * 70)
    t0 = time.time()
    if not mov_path.exists():
        dt = time.time() - t0
        res = {"status": "fail", "error": f"MOV 不存在: {mov_path}", "elapsed_s": round(dt, 1)}
        with open(qc_json_path, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        return res

    meta = ffprobe_mov_meta(mov_path)
    print(f"  ffprobe meta: {json.dumps(meta, ensure_ascii=False)}")
    fps = meta.get("fps") or 24.0
    total = meta.get("nb_frames") or 1
    frame_idxs = [
        0, round(total * 0.2), round(total * 0.4),
        round(total * 0.6), round(total * 0.8), max(0, total - 1),
    ]
    frame_idxs = sorted(set(max(0, min(total - 1, int(x))) for x in frame_idxs))
    print(f"\n  抽样 {len(frame_idxs)} 帧 (全范围): {frame_idxs}")
    ratios_raw = sample_fast_qc(mov_path, frame_idxs, fps, tmp_root)
    ratios_vals = [r for _, r in ratios_raw]
    while len(ratios_vals) < len(frame_idxs):
        ratios_vals.append(0.0)
    ne = sum(1 for r in ratios_vals if r > 1e-4)
    avg = float(np.mean(ratios_vals)) if ratios_vals else 0.0
    size_mb = round(mov_path.stat().st_size / 1024 / 1024, 1) if mov_path.exists() else 0
    qc_pass = bool(meta.get("meta_ok", False)) and (avg >= 0.03) and (ne / max(1, len(ratios_vals)) >= 0.5)
    report = {
        "path": str(mov_path),
        "size_mb": size_mb,
        "meta": meta,
        "sampled_alpha_fast": {
            "method": "ffmpeg -ss seek + frames:v 2 + pix_fmt rgba (fast)",
            "frames_sampled": len(ratios_raw),
            "nonempty_frames": f"{ne}/{len(ratios_raw)}",
            "avg_alpha_ratio": round(avg, 4),
            "per_frame": [{"frame": idx, "alpha_ratio": round(r, 4)} for (idx, r) in ratios_raw],
        },
        "QC_PASS": qc_pass,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(qc_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  QC: {'✅ PASS' if qc_pass else '❌ FAIL'}  |  "
          f"codec_ok={meta.get('codec_ok')}  has_alpha={meta.get('has_alpha')}  "
          f"nonempty={ne}/{len(ratios_vals)}  avg_alpha={avg:.4f}")
    print(f"  写入: {qc_json_path}")
    return report


def save_pipeline_report(report_path: Path, report: dict) -> None:
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def main() -> int:
    args = parse_args()
    t_start = time.time()
    try:  # GBK 控制台避免 Unicode 打印崩溃（如 QC ✅/❌）
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    input_mp4 = Path(args.input)
    if not input_mp4.exists():
        print(f"[FATAL] 输入文件不存在: {input_mp4}")
        print(f"  建议：检查 --input 路径拼写，确保 MP4 文件存在。")
        return 2

    slug = f"DL_{input_mp4.stem}"
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = DEFAULT_OUTPUT_ROOT / slug
    output_dir.mkdir(parents=True, exist_ok=True)
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)

    mask_dir = output_dir / f"{slug}_masks"
    mov_path = output_dir / f"{slug}_alpha.mov"
    alpha_dir = output_dir / "alpha_bgra_merge"
    qc_json_path = output_dir / f"QC_{slug}.json"
    report_path = output_dir / f"pipeline_report_{slug}.json"
    seg_tmp_root = TEMP_ROOT / slug

    sam_ckpt = Path(args.sam_ckpt) if args.sam_ckpt else DEFAULT_SAM_CKPT.get(args.variant, DEFAULT_SAM_CKPT["large"])
    yolo_pt = Path(args.yolo_pt)

    print("\n" + "=" * 70)
    print("make_one_mov_pipeline  一键抠像流水线")
    print("=" * 70)
    print(f"  INPUT     : {input_mp4}")
    print(f"  slug      : {slug}")
    print(f"  output_dir: {output_dir}")
    print(f"  mask_dir  : {mask_dir}")
    print(f"  mov_path  : {mov_path}")
    print(f"  qc_json   : {qc_json_path}")
    print(f"  report    : {report_path}")
    print(f"  variant   : {args.variant}  face_conf={args.face_conf}  yolo_conf={args.yolo_conf}")
    print(f"  SAM_CKPT  : {sam_ckpt}")
    print(f"  YOLO_PT   : {yolo_pt}")
    print(f"  no_skip   : {args.no_skip}")

    # STEP 1: 元数据探测
    t1 = time.time()
    print("\n" + "=" * 70)
    print("STEP 1: 探测输入视频元数据")
    print("=" * 70)
    info = ffprobe_video_info(input_mp4)
    if "error" in info:
        print(f"  [WARN] ffprobe 失败: {info['error']}")
    width, height, fps = info.get("width", 0), info.get("height", 0), info.get("fps") or 24.0
    nb_frames = info.get("nb_frames") or 0
    if nb_frames <= 0:
        cap = cv2.VideoCapture(str(input_mp4))
        nb_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.release()
    if fps <= 0:
        fps = 24.0
    step1 = {
        "input": str(input_mp4),
        "slug": slug,
        "output_dir": str(output_dir),
        "width": width,
        "height": height,
        "fps": fps,
        "nb_frames": nb_frames,
        "elapsed_s": round(time.time() - t1, 1),
    }
    print(f"  分辨率: {width}x{height}  fps={fps}  frames={nb_frames}")
    if nb_frames <= 0:
        print(f"[FATAL] 无法获取帧数，建议用 ffprobe 手动检查: {input_mp4}")
        save_pipeline_report(report_path, {"steps": {"step1": step1},
                                           "total_status": "fail",
                                           "error": "无法获取视频帧数",
                                           "total_elapsed_s": round(time.time() - t_start, 1)})
        return 3

    pipeline_steps: dict[str, dict] = {"step1_metadata": step1}

    # STEP 2: mask 推理
    try:
        step2 = step2_mask_inference(
            input_mp4=input_mp4, mask_dir=mask_dir, total_frames=nb_frames,
            variant=args.variant, sam_ckpt=sam_ckpt, yolo_pt=yolo_pt,
            face_conf=args.face_conf, yolo_conf=args.yolo_conf,
            no_skip=args.no_skip, seg_tmp_root=seg_tmp_root,
            engine=args.engine, motion_levels=args.motion_levels,
            start_frame=args.start_frame, frames=args.frames,
            keyframe_interval=args.keyframe_interval,
            max_segs=args.max_segs,
        )
    except Exception as e:
        traceback.print_exc()
        step2 = {"status": "exception", "error": str(e), "elapsed_s": 0}
    pipeline_steps["step2_mask_inference"] = step2
    need_total = args.frames if (args.engine == "enhanced" and args.frames) else nb_frames
    if args.engine == "enhanced" and args.max_segs > 0:
        need_total = min(need_total, args.max_segs * SEG_LEN)
    if step2.get("status") not in ("ok", "skip") and step2.get("mask_count", 0) < int(need_total * 0.5):
        print(f"\n[FATAL] STEP 2 mask 推理失败或覆盖率过低: {json.dumps(step2, ensure_ascii=False)[:300]}")
        print(f"  建议排查：1) VENV_PY={VENV_PY} 是否存在且 SAM2 环境完整；2) SAM_CKPT={sam_ckpt} 是否存在；")
        print(f"          3) YOLO_PT={yolo_pt} 是否存在；4) 查看段 seg_tmp_root={seg_tmp_root} 下 params.json 手动跑一次。")
        save_pipeline_report(report_path, {"steps": pipeline_steps,
                                           "total_status": "fail_step2",
                                           "total_elapsed_s": round(time.time() - t_start, 1)})
        return 4

    # STEP 3: MOV 合成
    try:
        step3 = step3_build_mov(
            input_mp4=input_mp4, mask_dir=mask_dir, mov_path=mov_path,
            total_frames=need_total, fps=fps, no_skip=args.no_skip, alpha_dir=alpha_dir,
            start_frame=(args.start_frame if args.engine == "enhanced" else 0),
        )
    except Exception as e:
        traceback.print_exc()
        step3 = {"status": "exception", "error": str(e), "elapsed_s": 0}
    pipeline_steps["step3_build_mov"] = step3
    if step3.get("status") not in ("ok", "skip") or not mov_path.exists() or mov_path.stat().st_size < 1024:
        print(f"\n[FATAL] STEP 3 MOV 合成失败: {json.dumps(step3, ensure_ascii=False)[:300]}")
        print(f"  建议排查：1) FFMPEG={FFMPEG} 是否存在且为完整版；2) mask_dir={mask_dir} 下 mask_*.png 是否命名为 mask_00000 起；")
        print(f"          3) 磁盘空间是否充足；4) 手动运行 FFmpeg 命令看错误信息。")
        save_pipeline_report(report_path, {"steps": pipeline_steps,
                                           "total_status": "fail_step3",
                                           "total_elapsed_s": round(time.time() - t_start, 1)})
        return 5

    # STEP 4: 快速 QC
    try:
        step4 = step4_fast_qc(mov_path, qc_json_path, TEMP_ROOT)
    except Exception as e:
        traceback.print_exc()
        step4 = {"status": "exception", "error": str(e), "elapsed_s": 0}
    pipeline_steps["step4_fast_qc"] = step4

    # 清理段临时
    try:
        shutil.rmtree(seg_tmp_root, ignore_errors=True)
    except Exception:
        pass

    # STEP 5: pipeline report
    total_elapsed = time.time() - t_start
    qc_pass = step4.get("QC_PASS", False)
    mov_size_mb = step3.get("size_mb", 0)
    avg_alpha = step4.get("sampled_alpha_fast", {}).get("avg_alpha_ratio", 0)
    overall_status = "ok" if (step3.get("status") in ("ok", "skip") and qc_pass) else (
        "qc_warn" if step3.get("status") in ("ok", "skip") else "fail"
    )
    report = {
        "pipeline": "make_one_mov_pipeline",
        "pipeline_version": "1.0",
        "slug": slug,
        "input": str(input_mp4),
        "output_dir": str(output_dir),
        "mask_dir": str(mask_dir),
        "mov_path": str(mov_path),
        "qc_json": str(qc_json_path),
        "params": {
            "variant": args.variant,
            "yolo_conf": args.yolo_conf,
            "face_conf": args.face_conf,
            "sam_ckpt": str(sam_ckpt),
            "yolo_pt": str(yolo_pt),
            "no_skip": args.no_skip,
        },
        "video_meta": {"width": width, "height": height, "fps": fps, "frames": nb_frames},
        "steps": pipeline_steps,
        "summary": {
            "total_status": overall_status,
            "QC_PASS": qc_pass,
            "mov_size_mb": mov_size_mb,
            "mask_count": step2.get("mask_count", 0),
            "mask_coverage": step2.get("coverage", 0),
            "avg_alpha_ratio": avg_alpha,
            "meta_ok": step4.get("meta", {}).get("meta_ok", False),
            "codec": step4.get("meta", {}).get("codec"),
            "pix_fmt": step4.get("meta", {}).get("pix_fmt"),
            "mov_frames": step4.get("meta", {}).get("nb_frames", 0),
        },
        "total_elapsed_s": round(total_elapsed, 1),
        "total_elapsed_h": round(total_elapsed / 3600, 3),
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_pipeline_report(report_path, report)

    print("\n\n" + "=" * 70)
    print("PIPELINE FINISHED")
    print("=" * 70)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"\n  报告 → {report_path}")
    print(f"  MOV  → {mov_path}")
    print(f"  QC   → {qc_json_path}")
    print(f"  总耗时: {total_elapsed / 60:.1f} 分钟  ({total_elapsed:.0f} 秒)")
    return 0 if overall_status == "ok" else (1 if overall_status == "qc_warn" else 6)


if __name__ == "__main__":
    sys.exit(main())
