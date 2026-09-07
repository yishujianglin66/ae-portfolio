r"""
海贼王_r84 (BV14tZNYGEuV) 断点续跑：从 frame=1500 继续到 10126（已完成前 1500 帧，mask 已存在）。
复用 long_video_autoframe_anime.py 的段推理循环、QC gate、三档 retry。
不清理已有 mask（跳过 seg000-002）。
段推理完成后，脚本末尾打印 MOV 合成提示（调用 redo_alpha_mov.py）。

运行：
  python scripts\continue_onepiece_v3.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import tempfile
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
PROJECT_OUTPUT = PROJECT_ROOT / "output"
PROJECT_OUTPUT.mkdir(parents=True, exist_ok=True)

WORK_ROOT = Path(r"D:\AE-Work")
D_OUTPUT_ROOT = WORK_ROOT / "output"  # D 盘只读（参考已有模型/环境/旧 mask）
OUTPUT_ROOT = PROJECT_OUTPUT  # 全流程改 C 盘，避免 TRAE 沙箱拦截 D 盘写操作
TEMP_DIR = PROJECT_OUTPUT / "segment_tmp_anime_resume"  # C 盘
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
QC_THRESH = 0.18
QC_NONEMPTY_FRAMES = 0.50
PIXEL_QC_SAMPLE = 15

NAME = "DL_海贼王_r84_BV14tZNYGEuV"
SRC_MP4 = PROJECT_ROOT / "data" / "real_amv_test" / f"{NAME}.mp4"
EXPECTED = 10126
START_FRAME = 1500  # 已完成前 1500 帧（mask 0-1499），从此帧继续

WORK_DIR = OUTPUT_ROOT / "rerun_anime_autoframe" / NAME  # C 盘
MASKS_DIR = WORK_DIR / f"{NAME}_masks"  # C 盘
SEG_TMP_ROOT = TEMP_DIR / NAME  # C 盘


def _ensure_existing_masks_copied():
    """前 1500 帧 mask 只在 D 盘有，将其复制到 C 盘 MASKS_DIR（从 D 盘读不经过沙箱）。"""
    D_MASKS_DIR = D_OUTPUT_ROOT / "rerun_anime_autoframe" / NAME / f"{NAME}_masks"
    if not D_MASKS_DIR.exists():
        return
    MASKS_DIR.mkdir(parents=True, exist_ok=True)
    c_count = len(list(MASKS_DIR.glob("mask_*.png")))
    if c_count >= 1500:
        return  # 已复制
    d_files = sorted(D_MASKS_DIR.glob("mask_*.png"))
    copied = 0
    for df in d_files:
        cf = MASKS_DIR / df.name
        if cf.exists() and cf.stat().st_size > 0:
            continue
        try:
            cf.write_bytes(df.read_bytes())
            copied += 1
        except Exception:
            pass
    print(f"[init] D盘→C盘 已复制前序mask: copied={copied}, C盘现有={len(list(MASKS_DIR.glob('mask_*.png')))}")


WORK_DIR.mkdir(parents=True, exist_ok=True)
MASKS_DIR.mkdir(parents=True, exist_ok=True)
SEG_TMP_ROOT.mkdir(parents=True, exist_ok=True)
_ensure_existing_masks_copied()


def _run_subprocess_code(code: str, timeout: int, label: str) -> tuple[int, str, str]:
    tmp = PROJECT_OUTPUT / "segment_tmp" / f"subp_{label}_{int(time.time()%100000)}.py"
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


def run_infer_segment(
    params_path: Path,
    src_mp4: Path,
    start_frame: int,
    expected_frames: int,
    out_mask_dir: Path,
    extra_cfg: dict,
    sam2_ckpt: str,
    model_cfg: str = "",
) -> dict:
    """params_path 是 seg_dir/params.json，先写入该文件，再直接调用 venv-sam2 跑 INFER_SCRIPT。
    marker 为 params.json.ok / params.json.fail（由 infer 脚本内部生成）。"""
    cfg = {
        "video_path": str(src_mp4),
        "start_frame": int(start_frame),
        "expected_frames": int(expected_frames),
        "mask_dir": str(out_mask_dir),
        "yolov8x_path": str(YOLOV8X_PATH),
        "sam2_checkpoint": sam2_ckpt,
    }
    if model_cfg:
        cfg["model_cfg"] = model_cfg
    cfg.update(extra_cfg)
    params_path.parent.mkdir(parents=True, exist_ok=True)
    with open(params_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
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
            timeout=SEG_TIMEOUT_S, cwd=str(PROJECT_ROOT),
        )
        rc, out, err = p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired as e:
        rc, out, err = -99, e.stdout or "", (e.stderr or "") + f"\n[TIMEOUT {SEG_TIMEOUT_S}s]"
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


def copy_segment_masks_with_verify(seg_out: Path, masks_dir: Path,
                                   start_global: int, seg_len: int,
                                   sample_count: int = 15
                                   ) -> dict:
    """直接复制 seg_out/mask_*.png（已是全局帧号命名 mask_<global_idx:05d>.png）→ masks_dir。
    子进程中完成：统计实际复制数量 + sample_count 均匀抽样像素 QC。"""
    src_files = sorted(seg_out.glob("mask_*.png"))
    src_paths = [str(p) for p in src_files]
    # 抽样：seg_len 范围内均匀（按 global_idx）
    sample_global_idxs = np.linspace(start_global, start_global + seg_len - 1,
                                     min(sample_count, seg_len), dtype=int).tolist()
    sample_src_paths = []
    for p in src_files:
        try:
            gi = int(Path(p).stem.split("_")[1])
        except Exception:
            continue
        if gi in sample_global_idxs:
            sample_src_paths.append(str(p))
    code = f"""
import sys, json, shutil, cv2, numpy as np
from pathlib import Path

src_paths = {src_paths!r}
dst_dir = Path(r'{str(masks_dir)}')
sample_src_paths = {sample_src_paths!r}
expected_copy = len(src_paths)

# 1. 复制（覆盖）
actual = 0
for s in src_paths:
    try:
        shutil.copy2(s, dst_dir / Path(s).name)
        actual += 1
    except Exception as e:
        pass

# 2. QC：抽样 seg 范围内的 global_idx，到 dst_dir 读对应的 mask
ratios = []
nonempty = 0
sample_count = len(sample_src_paths)
for s in sample_src_paths:
    dst = dst_dir / Path(s).name
    if not dst.exists():
        ratios.append(0.0)
        continue
    buf = np.fromfile(str(dst), dtype=np.uint8)
    if buf.size == 0:
        ratios.append(0.0)
        continue
    alpha = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    if alpha is None:
        ratios.append(0.0)
        continue
    nz = int(np.count_nonzero(alpha))
    total_px = int(alpha.shape[0] * alpha.shape[1])
    r = nz / total_px if total_px > 0 else 0.0
    ratios.append(r)
    if r > 1e-4:
        nonempty += 1
qc_r = float(np.mean(ratios)) if ratios else 0.0

print(json.dumps({{
    'actual_count': actual,
    'expected_copy': expected_copy,
    'avg_alpha_ratio': qc_r,
    'sample_nonempty_frames': nonempty,
    'sample_count': len(ratios),
    'ne_frac': (nonempty / len(ratios) if ratios else 0.0),
    'ratios': ratios,
}}, ensure_ascii=False))
sys.exit(0)
"""
    rc, out, err = _run_subprocess_code(code, timeout=1800, label=f"cpy{start_global}")
    result: dict = {"copy_rc": rc, "copy_err_tail": err.strip()[-300:]}
    for line in out.strip().splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                result.update(json.loads(line))
            except Exception:
                pass
    return result


def main():
    print("=" * 70)
    print(f"海贼王续跑：{NAME}")
    print(f"  src: {SRC_MP4} (exists={SRC_MP4.exists()})")
    print(f"  START_FRAME={START_FRAME}, EXPECTED_TOTAL={EXPECTED}")
    print(f"  现有 mask 数量: {len(list(MASKS_DIR.glob('mask_*.png')))}")
    print("=" * 70)

    default_ckpt = str(SAM2_CKPT_LARGE if SAM2_CKPT_LARGE.exists() else SAM2_CKPT_SMALL)
    default_variant = "large" if "large" in default_ckpt else "small"
    default_cfg = ""

    retry_cfg: list[tuple[str, dict, str, str]] = [
        ("default", {
            "face_conf": 0.35, "face_expand": 4.0,
            "yolo_conf": 0.05, "max_boxes_per_frame": 10,
            "sam_variant": default_variant,
        }, default_ckpt, default_cfg),
        ("low_face_conf", {
            "face_conf": 0.12, "face_expand": 5.5,
            "yolo_conf": 0.02, "max_boxes_per_frame": 15,
            "sam_variant": default_variant,
        }, default_ckpt, default_cfg),
        ("small_model", {
            "face_conf": 0.08, "face_expand": 7.0,
            "yolo_conf": 0.01, "max_boxes_per_frame": 20,
            "sam_variant": "small",
        }, str(SAM2_CKPT_SMALL), ""),
    ]

    # 构造从 START_FRAME 开始的段列表
    segs: list[tuple[int, int, int]] = []  # (seg_idx, start, end_exclusive)
    start = START_FRAME
    idx = START_FRAME // SEG_LEN
    while start < EXPECTED:
        end = min(start + SEG_LEN, EXPECTED)
        segs.append((idx, start, end))
        start = end
        idx += 1
    total_segs = len(segs)
    print(f"  剩余段数: {total_segs}, 每段 ≤ {SEG_LEN} 帧")

    summary_segments: list[dict] = []
    t0 = time.time()
    for pos, (seg_idx, start, end) in enumerate(segs, 1):
        slen = end - start
        name_s = f"seg{seg_idx:03d}_{start}_{end}"
        print(f"\n  [{pos}/{total_segs}] {name_s} (len={slen})")
        seg_dir = SEG_TMP_ROOT / name_s
        if seg_dir.exists():
            shutil.rmtree(seg_dir, ignore_errors=True)
        seg_dir.mkdir(parents=True, exist_ok=True)
        success = False
        att_res = None
        for attempt_i, (label, ext, ckpt, mcfg) in enumerate(retry_cfg, 1):
            print(f"    attempt {attempt_i}/3 [{label}] start...")
            t_att = time.time()
            for old in seg_dir.glob("mask_*.png"):
                try:
                    old.unlink()
                except Exception:
                    pass
            for extra in [seg_dir / "_result_marker.json"]:
                try:
                    extra.unlink()
                except Exception:
                    pass
            params_path = seg_dir / "params.json"
            res = run_infer_segment(
                params_path, SRC_MP4, start, slen, seg_dir, ext, ckpt, mcfg,
            )
            dt = time.time() - t_att
            st = res.get("status", "?")
            if st == "ok":
                print(f"    attempt {attempt_i} status={st} in {dt:.1f}s: {res}")
            else:
                tail = (res.get("stderr_tail", "") or res.get("error", ""))[:200]
                print(f"    attempt {attempt_i} status={st} in {dt:.1f}s rc={res.get('rc','?')}: {tail}")
            # 段 QC gate
            qc = copy_segment_masks_with_verify(seg_dir, MASKS_DIR, start, slen, sample_count=PIXEL_QC_SAMPLE)
            actual = qc.get("actual_count", 0)
            avg_a = float(qc.get("avg_alpha_ratio", 0.0))
            ne_frac = float(qc.get("ne_frac", 0.0))
            ok_count = (actual >= slen * 0.99)
            ok_qc = (avg_a >= QC_THRESH and ne_frac >= QC_NONEMPTY_FRAMES)
            ok = ok_count and ok_qc
            print(f"    copy→master: actual={actual}/{slen}, avg_alpha_ratio={avg_a:.4f}, "
                  f"sample_nonempty_frames={qc.get('sample_nonempty_frames', 0)}/{qc.get('sample_count', 0)} (ne_frac={ne_frac:.2f})")
            if ok:
                success = True
                att_res = {"attempt": attempt_i, "label": label, "seg_sec": round(dt, 1),
                           "infer": res, "qc": qc}
                break
            else:
                print(f"    QC FAIL → 升级重试: count_ok={ok_count} qc_ok={ok_qc}")
        # 即时清理段 tmp
        shutil.rmtree(seg_dir, ignore_errors=True)
        if not success:
            # 失败也保留 master 中已经复制的部分 mask
            summary_segments.append({"seg": name_s, "status": "fail", "qc_last": qc})
            print(f"    [FATAL] {name_s} 全部重试失败，跳到下一段")
            continue
        summary_segments.append({"seg": name_s, "status": "ok", **(att_res or {})})
        # 磁盘监控
        try:
            cu = shutil.disk_usage(r"C:")
            print(f"    [DISK C 剩余] {cu.free/1024**3:.1f} GB")
        except Exception:
            pass
        # 每 10 段写一次增量 summary
        if pos % 10 == 0 or pos == total_segs:
            inc = {
                "name": NAME,
                "elapsed_h": round((time.time() - t0) / 3600, 3),
                "progress": f"{pos}/{total_segs}",
                "segments": summary_segments,
            }
            p = WORK_DIR / "progress.json"
            with open(p, "w", encoding="utf-8") as f:
                json.dump(inc, f, ensure_ascii=False, indent=2)

    total_dt = time.time() - t0
    total_masks_now = len(list(MASKS_DIR.glob("mask_*.png")))
    print(f"\n\n  推理完成！当前 mask 数量: {total_masks_now}/{EXPECTED}")
    print(f"  总耗时: {total_dt/3600:.2f} 小时")
    print(f"\n下一步：将海贼王加入 redo_alpha_mov.py 的 TARGETS 并运行，合成透明 MOV + QC")
    final = {
        "name": NAME,
        "expected": EXPECTED,
        "mask_count": total_masks_now,
        "total_dt_h": round(total_dt / 3600, 3),
        "segments": summary_segments,
    }
    with open(WORK_DIR / "infer_summary.json", "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
