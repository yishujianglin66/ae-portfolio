"""
3 长视频 auto_frame + anime face / YOLO 分段重跑（方案 A v2）。

核心改进（相对 long_video_segment_rerun / 旧版 anime）：
1. 不做 ffmpeg 切段：直接把整视频路径 + start_frame + expected_frames 传给推理脚本，
   infer 内部用 cap.set(CAP_PROP_POS_FRAMES, start_frame) 跳转后读 expected 帧。
   完全避开 FFmpeg select filter 的 Windows PowerShell 转义地狱，且省 CPU/磁盘。
2. 段推理直接写 mask_<全局帧号>.png（start_frame + idx），无需 copy 阶段重编号。
3. QC gate：段复制验证 actual_count + 段内 10 帧抽样像素级 nonempty ratio。
   不达标则按 retry_cfg 逐次加强（low face_conf → small_model）。
4. 段合并 → BGRA PNG → ffmpeg qtrle MOV（子进程执行，避免 D 盘沙箱）。
5. 段 tmp 用完即时释放，整体峰值 C 盘占用 < 2 GB。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
PROJECT_OUTPUT = PROJECT_ROOT / "output"
PROJECT_OUTPUT.mkdir(parents=True, exist_ok=True)

WORK_ROOT = Path(r"D:\AE-Work")
# 沙箱限制：输出路径必须在 C 盘项目目录下（D 盘只读）
OUTPUT_ROOT = PROJECT_ROOT / "output" / "rerun_anime_autoframe"
TEMP_DIR = PROJECT_OUTPUT / "segment_tmp_anime_v2"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

VENV_PY = WORK_ROOT / "venv-sam2" / "Scripts" / "python.exe"
YOLOV8X_PATH = WORK_ROOT / "models" / "yolo" / "yolov8x.pt"
SAM2_CKPT_LARGE = WORK_ROOT / "models" / "sam2" / "sam2.1_hiera_large.pt"
SAM2_CKPT_SMALL = WORK_ROOT / "models" / "sam2" / "sam2.1_hiera_small.pt"
INFER_SCRIPT = SCRIPTS_DIR / "infer_segment_autoframe_anime.py"

SEG_LEN = 500
SEG_TIMEOUT_S = 3 * 3600
MAX_RETRY = 2
QC_THRESH = 0.18           # 段抽样平均 alpha 占比 ≥ 18% 算合格（人物动画 10-60% 正常范围）
QC_NONEMPTY_FRAMES = 0.50  # 段抽样非空帧 ≥ 50% 算合格（auto_frame 允许部分帧未检出）
PIXEL_QC_SAMPLE = 15

TARGET_VIDEOS: list[dict] = [
    {
        "name": "DL_黑岩射手_r924_BV1JW411s7GV",
        "src_mp4": r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\data\real_amv_test\DL_黑岩射手_r924_BV1JW411s7GV.mp4",
        "expected_frames": 4977,
    },
    {
        "name": "DL_黑岩射手_r924_BV1NL4y1H7u7",
        "src_mp4": r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\data\real_amv_test\DL_黑岩射手_r924_BV1NL4y1H7u7.mp4",
        "expected_frames": 8881,
    },
    {
        "name": "DL_海贼王_r84_BV14tZNYGEuV",
        "src_mp4": r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\data\real_amv_test\DL_海贼王_r84_BV14tZNYGEuV.mp4",
        "expected_frames": 10126,
    },
]


def _run_subprocess_code(code: str, *, timeout: int, label: str) -> tuple[int, str, str]:
    ts = int(time.time() * 1000)
    py = TEMP_DIR / f"_{label}_{ts}.py"
    with open(py, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        p = subprocess.run(
            [str(VENV_PY), str(py)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(PROJECT_ROOT),
        )
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired as e:
        return -99, e.stdout or "", (e.stderr or "") + f"\n[TIMEOUT {timeout}s]"
    finally:
        try:
            py.unlink(missing_ok=True)
        except Exception:
            pass


def run_segment_inference(params_path: Path, timeout: int) -> dict | None:
    marker_ok = str(params_path) + ".ok"
    marker_fail = str(params_path) + ".fail"
    for m in (marker_ok, marker_fail):
        if os.path.exists(m):
            try:
                os.remove(m)
            except Exception:
                pass
    try:
        p = subprocess.run(
            [str(VENV_PY), str(INFER_SCRIPT), str(params_path)],
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
    return {"status": "fail", "rc": rc, "error": "no result parsed", "stdout_tail": out[-500:], "stderr_tail": err[-500:]}


def copy_segment_masks_with_verify(
    src_mask_dir: Path, dst_mask_dir: Path, start_frame: int, expected: int
) -> tuple[int, float, int]:
    """直接复制（段 mask 已是全局命名）→ 子进程计数 + 像素抽样 QC。返回 (actual, avg_ratio, sample_ne_frames)。"""
    src_sorted = sorted(src_mask_dir.glob("mask_*.png"))
    src_paths = [str(p) for p in src_sorted]
    # 抽样：按 expected 均匀取 15 帧
    sample_idxs_global = np.linspace(start_frame, start_frame + expected - 1,
                                     min(PIXEL_QC_SAMPLE, expected), dtype=int).tolist()
    sample_src_map = {}
    for p in src_paths:
        try:
            gi = int(Path(p).stem.split("_")[1])
        except Exception:
            continue
        sample_src_map[gi] = p
    sample_src_paths = [sample_src_map[gi] for gi in sample_idxs_global if gi in sample_src_map]

    copy_code = f"""
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
    except Exception as e:
        copy_err += 1

# count actual in dst range
actual = 0
for p in Path(dsts_dir).glob('mask_*.png'):
    try:
        idx = int(p.stem.split('_')[1])
    except Exception:
        continue
    if start <= idx < end and p.stat().st_size >= 10:
        actual += 1

# pixel QC on samples
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
    except Exception as e:
        pass
ratio = (sample_ne / sample_total) if sample_total > 0 else 0.0
ne_frac = (sample_ne_frames / sample_frames_run) if sample_frames_run > 0 else 0.0
print(f"RESULT copied={{copied}} actual={{actual}} copy_err={{copy_err}} expected={{expected}}"
      f" sample_frames={{sample_frames_run}} sample_ratio={{ratio:.6f}} sample_ne_frames={{sample_ne_frames}} sample_ne_frac={{ne_frac:.3f}}")
if actual <= 0:
    sys.exit(2)
"""
    rc, out, err = _run_subprocess_code(copy_code, timeout=1800, label=f"cpv{int(time.time()*1000)}")
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
    if err:
        print(f"    [copy stderr 预览] {err.strip()[:250]}")
    return actual, ratio, sample_ne_frames


def merge_masks_to_mov(mask_dir: Path, src_mp4: Path, mov_path: Path, expected: int) -> bool:
    """子进程执行：读源 mp4 帧 + 配对 mask → 写 BGRA PNG 序列 → ffmpeg qtrle mov → 清理。"""
    code = f"""
import os, sys, json, shutil, subprocess, cv2, numpy as np
from pathlib import Path

mask_dir = Path(r'{str(mask_dir)}')
src_mp4 = r'{str(src_mp4)}'
mov_path = r'{str(mov_path)}'
expected = {expected}

os.makedirs(os.path.dirname(mov_path), exist_ok=True)
alpha_dir = mask_dir.parent / 'alpha_bgra_merge'
if alpha_dir.exists():
    shutil.rmtree(alpha_dir, ignore_errors=True)
alpha_dir.mkdir(parents=True, exist_ok=True)

# load mask idx → path
mask_paths_sorted = sorted(mask_dir.glob('mask_*.png'))
mask_by_idx = {{}}
for p in mask_paths_sorted:
    try:
        idx = int(p.stem.split('_')[1])
    except Exception:
        continue
    mask_by_idx[idx] = str(p)

cap = cv2.VideoCapture(str(src_mp4))
fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)

max_idx = expected if expected > 0 else (max(mask_by_idx.keys()) + 1 if mask_by_idx else 0)
written = 0
missing_mask = 0
empty_mask = 0
nonempty_frames = 0
for i in range(max_idx):
    ret, frame = cap.read()
    if not ret or frame is None:
        break
    h, w = frame.shape[:2]
    mask_path = mask_by_idx.get(i)
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
    out = alpha_dir / f'frame_{{i:05d}}.png'
    ok, buf = cv2.imencode('.png', bgra, [int(cv2.IMWRITE_PNG_COMPRESSION), 1])
    if ok:
        buf.tofile(str(out))
        written += 1
cap.release()

# ffmpeg（用完整版，避免 TRAE 裁剪版缺模块）
FFMPEG_BIN = r'C:\ffmpeg\bin\ffmpeg.exe'
pat = str(alpha_dir / 'frame_%05d.png')
cmd = [
    FFMPEG_BIN, '-hide_banner', '-loglevel', 'error', '-y',
    '-framerate', str(fps),
    '-start_number', '0',
    '-i', pat,
    '-c:v', 'qtrle', '-pix_fmt', 'yuva444p10le',
    str(mov_path),
]
p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=4*3600)
rc = p.returncode
err = p.stderr or ''
shutil.rmtree(alpha_dir, ignore_errors=True)
size = os.path.getsize(mov_path) if os.path.exists(mov_path) else 0
ok = (rc == 0 and size > 1024)
print(json.dumps({{
    'status': 'ok' if ok else 'fail',
    'frames_written': written, 'missing_mask': missing_mask,
    'empty_mask': empty_mask, 'nonempty_frames': nonempty_frames,
    'mov_size': size, 'ff_rc': rc, 'ff_err_tail': err[-500:],
}}, ensure_ascii=False))
sys.exit(0 if ok else 1)
"""
    rc, out, err = _run_subprocess_code(code, timeout=6 * 3600, label=f"merge{int(time.time()%10000)}")
    result: dict = {}
    for line in out.strip().splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                result = json.loads(line)
            except Exception:
                pass
    ok = result.get("status") == "ok"
    if not ok:
        print(f"  [MOV FAIL] rc={rc} result={result} err={err.strip()[:300]}")
    return ok


def pixel_qc_mov(mov_path: Path, samples: int = 25) -> dict:
    code = f"""
import os, sys, json, cv2, numpy as np
p = r'{str(mov_path)}'
samples = {samples}
if not os.path.exists(p):
    print(json.dumps({{'status':'fail','error':'not exists'}}))
    sys.exit(1)
cap = cv2.VideoCapture(p)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
if total <= 0:
    print(json.dumps({{'status':'fail','error':'0 frames'}}))
    sys.exit(1)
idxs = np.linspace(0, total - 1, samples, dtype=int).tolist()
ratios = []
ne_frames = 0
for idx in idxs:
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ret, frame = cap.read()
    if not ret or frame is None:
        continue
    if frame.shape[2] < 4:
        ratios.append(0.0)
        continue
    a = frame[:, :, 3]
    nz = int(np.count_nonzero(a))
    total_px = int(a.shape[0] * a.shape[1])
    r = nz / total_px if total_px > 0 else 0.0
    ratios.append(r)
    if r > 1e-4:
        ne_frames += 1
cap.release()
avg = float(np.mean(ratios)) if ratios else 0.0
print(json.dumps({{
    'status':'ok', 'total_frames': total, 'sampled': len(ratios),
    'nonempty_sample_frames': ne_frames, 'avg_alpha_ratio': avg, 'per_frame': ratios,
}}, ensure_ascii=False))
"""
    rc, out, err = _run_subprocess_code(code, timeout=3600, label="qcmov")
    for line in out.strip().splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except Exception:
                pass
    return {"status": "fail", "rc": rc, "out_tail": out[-500:], "err_tail": err[-500:]}


def process_one_video(video_cfg: dict) -> dict:
    name = video_cfg["name"]
    src_mp4 = Path(video_cfg["src_mp4"])
    expected = int(video_cfg["expected_frames"])
    print("\n" + "=" * 70)
    print(f"VIDEO: {name}  |  expected_frames={expected}")
    print(f"  src: {src_mp4} (exists={src_mp4.exists()})")
    print("=" * 70)
    if not src_mp4.exists():
        return {"name": name, "status": "skip", "reason": "src mp4 missing"}

    work_dir = OUTPUT_ROOT / name
    seg_tmp_root = TEMP_DIR / name
    masks_dir = work_dir / f"{name}_masks"
    mov_path = work_dir / f"{name}_alpha.mov"
    qc_path = work_dir / "qc.json"
    work_dir.mkdir(parents=True, exist_ok=True)
    seg_tmp_root.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)
    for old in masks_dir.glob("mask_*.png"):
        try:
            old.unlink()
        except Exception:
            pass

    total_segs = (expected + SEG_LEN - 1) // SEG_LEN
    print(f"  分段数: {total_segs}, 每段 ≤ {SEG_LEN} 帧, QC_THRESH={QC_THRESH}, NE_FRAC={QC_NONEMPTY_FRAMES}")

    summary_segments: list[dict] = []
    default_ckpt = str(SAM2_CKPT_LARGE if SAM2_CKPT_LARGE.exists() else SAM2_CKPT_SMALL)
    # 为空时由 factory 按 checkpoint 名+variant 自动选正确的 sam2.1/sam2 子目录 config
    default_cfg = ""
    default_variant = "large" if "large" in default_ckpt else "small"

    for seg_i in range(total_segs):
        start_frame = seg_i * SEG_LEN
        seg_len = min(SEG_LEN, expected - start_frame)
        seg_name = f"seg{seg_i:03d}_{start_frame}_{start_frame + seg_len}"
        seg_dir = seg_tmp_root / seg_name
        seg_mask_dir = seg_dir / "masks"
        params_path = seg_dir / "params.json"
        seg_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n  [{seg_i + 1}/{total_segs}] {seg_name} (len={seg_len})")

        retry_cfg: list[tuple[str, dict, str, str]] = [
            ("default", {
                "face_conf": 0.35, "face_expand": 4.0,
                "yolo_conf": 0.05, "max_boxes_per_frame": 10,
                "sam_variant": default_variant,
            }, default_ckpt, default_cfg),
            # B档（D1漏洞修复实验实锤验证：修复率51-89%，副作用0）
            ("B_lowconf_large", {
                "face_conf": 0.08, "face_expand": 7.0,
                "yolo_conf": 0.01, "max_boxes_per_frame": 20,
                "sam_variant": default_variant,
            }, default_ckpt, default_cfg),
            ("small_model", {
                "face_conf": 0.08, "face_expand": 7.0,
                "yolo_conf": 0.01, "max_boxes_per_frame": 20,
                "sam_variant": "small",
            }, str(SAM2_CKPT_SMALL), ""),
        ]
        best_result: dict | None = None
        best_metrics = (-1, 0.0, 0)  # (actual, ratio, sample_ne)
        best_label = ""
        attempt = 0
        for label, overrides, ck, cn in retry_cfg[:MAX_RETRY + 1]:
            attempt += 1
            params = {
                "video_path": str(src_mp4),
                "start_frame": start_frame,
                "expected_frames": seg_len,
                "mask_dir": str(seg_mask_dir),
                "sam2_checkpoint": ck,
                "model_cfg": cn,
                "yolov8x_path": str(YOLOV8X_PATH),
                **overrides,
            }
            if seg_mask_dir.exists():
                shutil.rmtree(seg_mask_dir, ignore_errors=True)
            seg_mask_dir.mkdir(parents=True, exist_ok=True)
            with open(params_path, "w", encoding="utf-8") as f:
                json.dump(params, f, ensure_ascii=False, indent=2)
            print(f"    attempt {attempt}/{MAX_RETRY + 1} [{label}] start...")
            t0 = time.time()
            result = run_segment_inference(params_path, timeout=SEG_TIMEOUT_S)
            dt = time.time() - t0
            status = (result or {}).get("status", "fail")
            short_res = json.dumps(result or {}, ensure_ascii=False)[:200]
            print(f"    attempt {attempt} status={status} in {dt:.1f}s: {short_res}")
            if status != "ok":
                continue
            actual, ratio, sample_ne = copy_segment_masks_with_verify(
                seg_mask_dir, masks_dir, start_frame, seg_len,
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
                    "attempt_label": label, "seg_dt_sec": dt,
                })
                best_label = label
            if pass_qc:
                break
        if best_result is None:
            summary_segments.append({
                "seg": seg_i, "status": "fail_all_attempts",
                "start": start_frame, "len": seg_len,
                "attempt_label": best_label or "none",
                "last_result": result,
            })
            continue
        # 段结果判定：actual 齐 + QC 达标 → ok；否则 qc_warn
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
        # 释放段临时空间
        shutil.rmtree(seg_mask_dir, ignore_errors=True)
        try:
            usage = shutil.disk_usage(PROJECT_ROOT.drive + "\\")
            print(f"    [DISK C 剩余] {usage.free / (1024**3):.1f} GB")
        except Exception:
            pass

    # 合成 MOV
    print(f"\n  合成 MOV → {mov_path}")
    merge_ok = merge_masks_to_mov(masks_dir, src_mp4, mov_path, expected)
    qc_res = {"status": "skip"}
    mov_size_mb = 0
    if mov_path.exists():
        mov_size_mb = mov_path.stat().st_size / (1024 * 1024)
        qc_res = pixel_qc_mov(mov_path, samples=25)
    with open(qc_path, "w", encoding="utf-8") as f:
        json.dump({
            "video": name,
            "segments": summary_segments,
            "merge_mov_ok": merge_ok,
            "mov_size_mb": round(mov_size_mb, 1),
            "mov_alpha_qc": qc_res,
        }, f, ensure_ascii=False, indent=2)
    print(f"  DONE {name}: merge_ok={merge_ok}, MOV={mov_size_mb:.1f} MB, "
          f"alpha_qc={json.dumps(qc_res, ensure_ascii=False)[:240]}")
    shutil.rmtree(seg_tmp_root, ignore_errors=True)
    avg_alpha = qc_res.get("avg_alpha_ratio", 0) if isinstance(qc_res, dict) else 0
    ne_f = qc_res.get("nonempty_sample_frames", 0) if isinstance(qc_res, dict) else 0
    sampled = qc_res.get("sampled", 1) if isinstance(qc_res, dict) else 1
    status = "ok" if (merge_ok and avg_alpha >= 0.02 and ne_f >= int(sampled * 0.7)) else "qc_warn"
    return {
        "name": name,
        "status": status,
        "mov_size_mb": round(mov_size_mb, 1),
        "avg_alpha_ratio": round(avg_alpha, 4),
        "nonempty_sample_frames": f"{ne_f}/{sampled}",
        "qc_path": str(qc_path),
    }


def main():
    print("=" * 70)
    print("方案 A v2：auto_frame + anime face detector + YOLO fallback 重跑 3 长视频")
    print("  - 直接在整视频上 seek 段范围，不依赖 FFmpeg select 切段（避 Windows 转义坑）")
    print("  - 段 mask 直接写全局帧号，复制阶段无需重命名")
    print("=" * 70)
    print(f"  SEG_LEN={SEG_LEN}, QC_THRESH={QC_THRESH}, MAX_RETRY={MAX_RETRY}")
    print(f"  VENV_PY={VENV_PY}")
    print(f"  YOLOV8X exists={YOLOV8X_PATH.exists()}")
    print(f"  SAM2 large={SAM2_CKPT_LARGE.exists()}, small={SAM2_CKPT_SMALL.exists()}")
    print(f"  INFER_SCRIPT exists={INFER_SCRIPT.exists()}")
    print()
    for v in TARGET_VIDEOS:
        mp = Path(v["src_mp4"])
        print(f"  TARGET: {v['name']:<40} exists={mp.exists()}  expected={v['expected_frames']}")
    t0 = time.time()
    results = []
    for v in TARGET_VIDEOS:
        try:
            r = process_one_video(v)
        except Exception as e:
            import traceback
            traceback.print_exc()
            r = {"name": v["name"], "status": "exception", "error": str(e)}
        results.append(r)
        # 每完成一个视频立即写增量 summary
        with open(OUTPUT_ROOT / "rerun_anime_autoframe_summary.json", "w", encoding="utf-8") as f:
            json.dump({"total_dt_h": round((time.time() - t0) / 3600, 3), "results": results},
                      f, ensure_ascii=False, indent=2)
    total_dt = time.time() - t0
    summary = {
        "total_dt_h": round(total_dt / 3600, 3),
        "results": results,
    }
    out_path = OUTPUT_ROOT / "rerun_anime_autoframe_summary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\n\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n写入 {out_path}")


if __name__ == "__main__":
    main()
