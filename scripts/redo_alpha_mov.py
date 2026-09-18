"""
独立脚本：合成前 2 已完成 mask 视频的 alpha qtrle MOV，并做像素级 QC。
修复：FFmpeg image2 默认从编号 1 开始，我们的 PNG 从 0 开始，加 -start_number 0
确保 masks 目录下已有 mask_<idx>.png（idx 从 0 开始）。

运行：
  python scripts\redo_alpha_mov.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

WORK_ROOT = Path(r"D:\AE-Work")
VENV_PY = WORK_ROOT / "venv-sam2" / "Scripts" / "python.exe"
DATA_SRC = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\data\real_amv_test")
D_OUTPUT_ROOT = WORK_ROOT / "output" / "rerun_anime_autoframe"  # D 盘 mask（只读）
PROJECT_OUTPUT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\output")
OUTPUT_ROOT = PROJECT_OUTPUT / "rerun_anime_autoframe"  # MOV 写 C 盘，避免沙箱
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

TARGETS = [
    {
        "name": "DL_黑岩射手_r924_BV1JW411s7GV",
        "src": DATA_SRC / "DL_黑岩射手_r924_BV1JW411s7GV.mp4",
        "expected": 4977,
    },
    {
        "name": "DL_黑岩射手_r924_BV1NL4y1H7u7",
        "src": DATA_SRC / "DL_黑岩射手_r924_BV1NL4y1H7u7.mp4",
        "expected": 8881,
    },
]


def _run_subprocess_code(code: str, timeout: int, label: str) -> tuple[int, str, str]:
    tmp = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\output\segment_tmp") / f"subp_{label}_{int(time.time()%100000)}.py"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(code, encoding="utf-8")
    p = subprocess.run(
        [str(VENV_PY), str(tmp)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )
    try:
        tmp.unlink()
    except Exception:
        pass
    return p.returncode, p.stdout, p.stderr


def merge_one(mask_dir: Path, src_mp4: Path, mov_path: Path, expected: int, work_dir: Path) -> dict:
    code = f"""
import os, sys, json, shutil, subprocess, cv2, numpy as np
from pathlib import Path

mask_dir = Path(r'{str(mask_dir)}')
src_mp4 = r'{str(src_mp4)}'
mov_path = r'{str(mov_path)}'
work_dir = Path(r'{str(work_dir)}')
expected = {expected}

os.makedirs(os.path.dirname(mov_path), exist_ok=True)
alpha_dir = work_dir / 'alpha_bgra_merge'  # 放 C 盘，避免沙箱写 D 盘
if alpha_dir.exists():
    shutil.rmtree(alpha_dir, ignore_errors=True)
alpha_dir.mkdir(parents=True, exist_ok=True)

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

pat = str(alpha_dir / 'frame_%05d.png')
FFMPEG = r'C:\ffmpeg\bin\ffmpeg.exe'
cmd = [
    FFMPEG, '-hide_banner', '-loglevel', 'error', '-y',
    '-framerate', str(fps),
    '-start_number', '0',
    '-i', pat,
    '-c:v', 'qtrle', '-pix_fmt', 'yuva444p10le',
    str(mov_path),
]
p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=6*3600)
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
    rc, out, err = _run_subprocess_code(code, timeout=8 * 3600, label=f"merge{int(time.time()%10000)}")
    result: dict = {}
    for line in out.strip().splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                result = json.loads(line)
            except Exception:
                pass
    result.setdefault("rc", rc)
    result.setdefault("err_tail", err.strip()[-300:])
    return result


def qc_mov(mov_path: Path, samples: int = 30) -> dict:
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
    rc, out, err = _run_subprocess_code(code, timeout=3600, label=f"qc{int(time.time()%1000)}")
    for line in out.strip().splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except Exception:
                pass
    return {"status": "fail", "rc": rc, "out_tail": out[-500:], "err_tail": err[-500:]}


def main():
    print("=" * 70)
    print("MOV 重合成 + alpha QC (修复 FFmpeg -start_number 0)")
    print(f"TARGETS: {len(TARGETS)} 个视频")
    print("=" * 70)
    results = []
    t0 = time.time()
    for idx, t in enumerate(TARGETS, 1):
        name = t["name"]
        src = t["src"]
        expected = t["expected"]
        work_dir = OUTPUT_ROOT / name  # C 盘（写 MOV、临时 alpha_dir）
        masks_dir = D_OUTPUT_ROOT / name / f"{name}_masks"  # D 盘只读（mask 源）
        mov_path = work_dir / f"{name}_alpha.mov"  # C 盘
        qc_path = PROJECT_OUTPUT / f"{name}_qc.json"  # C 盘，主进程写
        print(f"\n[{idx}/{len(TARGETS)}] {name}")
        print(f"    src exists: {src.exists()}")
        if not masks_dir.exists():
            print("    SKIP: masks_dir missing")
            results.append({"name": name, "status": "skip", "reason": "masks_dir missing"})
            continue
        mask_count = len(list(masks_dir.glob("mask_*.png")))
        print(f"    mask count: {mask_count} / expected {expected}")
        if mask_count < int(expected * 0.9):
            print(f"    SKIP: 仅 {mask_count}/{expected} mask")
            results.append({"name": name, "status": "skip", "mask_count": mask_count, "expected": expected})
            continue
        if mov_path.exists() and mov_path.stat().st_size > 10 * 1024 * 1024:
            quick = qc_mov(mov_path, samples=10)
            if quick.get("avg_alpha_ratio", 0) >= 0.10 and quick.get("nonempty_sample_frames", 0) >= 8:
                size_mb = round(mov_path.stat().st_size / 1024 / 1024, 1)
                print(f"    MOV 已存在且 QC 通过（{quick.get('avg_alpha_ratio'):.3f}, {size_mb} MB），跳过重合成")
                qc = quick
                with open(qc_path, "w", encoding="utf-8") as f:
                    json.dump(qc, f, ensure_ascii=False, indent=2)
                results.append({"name": name, "status": "ok", "merge": "skip_existing", "mov_size_mb": size_mb, "qc": qc})
                continue
        print(f"  → 合成 MOV (BGRA {expected} frames → qtrle)...")
        t_merge = time.time()
        merge_res = merge_one(masks_dir, src, mov_path, expected, work_dir)
        size_mb = round(merge_res.get("mov_size", 0) / 1024 / 1024, 1)
        dt_merge = time.time() - t_merge
        print(f"    status={merge_res.get('status')} size={size_mb} MB "
              f"written={merge_res.get('frames_written')} nonempty={merge_res.get('nonempty_frames')} "
              f"dt={dt_merge:.0f}s")
        if merge_res.get("status") != "ok":
            print(f"    FAIL: ff_rc={merge_res.get('ff_rc')} rc={merge_res.get('rc')} "
                  f"ff_err={merge_res.get('ff_err_tail','')[:300]}")
            if merge_res.get("err_tail"):
                print(f"    SUBPROCESS_ERR: {merge_res.get('err_tail')[-600:]}")
            results.append({"name": name, "status": "fail_merge", "merge": merge_res})
            continue
        print("  → 像素级 QC (30 samples)...")
        qc = qc_mov(mov_path, samples=30)
        print(f"    QC: avg_alpha={qc.get('avg_alpha_ratio', 0):.4f} "
              f"ne={qc.get('nonempty_sample_frames')}/{qc.get('sampled')} "
              f"total_frames={qc.get('total_frames')}")
        with open(qc_path, "w", encoding="utf-8") as f:
            json.dump(qc, f, ensure_ascii=False, indent=2)
        results.append({
            "name": name, "status": "ok",
            "merge": merge_res, "qc": qc, "mov_size_mb": size_mb,
            "merge_dt_s": round(dt_merge, 0),
        })
    summary = {
        "total_dt_h": round((time.time() - t0) / 3600, 3),
        "results": results,
    }
    out_path = PROJECT_OUTPUT / "redo_mov_summary.json"  # C 盘，避免沙箱
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    for r in results:
        st = r.get("status")
        name = r.get("name")
        if st == "ok":
            qc = r.get("qc", {})
            print(f"  [OK]  {name}: MOV {r.get('mov_size_mb')} MB, avg_alpha={qc.get('avg_alpha_ratio', 0):.4f}, ne={qc.get('nonempty_sample_frames')}/{qc.get('sampled')}")
        else:
            print(f"  [{st.upper()}] {name}: {r.get('reason') or str(r.get('merge',''))[:100]}")
    print(f"\nsummary -> {out_path}")
    print(f"总耗时: {summary['total_dt_h']} 小时")


if __name__ == "__main__":
    main()
