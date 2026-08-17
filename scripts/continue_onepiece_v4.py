"""
海贼王 DL_海贼王_r84_BV14tZNYGEuV v4 批量续跑
- 直接调用 venv-sam2 python + params.json 路径（绕开老脚本）
- 每段 500 帧，段结束后直接 copy mask 到成品目录
- START_FRAME = 4500（seg009），END=10126
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
VENV_PY = Path(r"D:\AE-Work\venv-sam2\Scripts\python.exe")
INFER_SCRIPT = PROJECT_ROOT / "scripts" / "infer_segment_autoframe_anime.py"
SRC_MP4 = PROJECT_ROOT / "data" / "real_amv_test" / "DL_海贼王_r84_BV14tZNYGEuV.mp4"
MASK_DIR = PROJECT_ROOT / "output" / "rerun_anime_autoframe" / "DL_海贼王_r84_BV14tZNYGEuV" / "DL_海贼王_r84_BV14tZNYGEuV_masks"
TMP_ROOT = PROJECT_ROOT / "output" / "segment_tmp_anime_resume" / "DL_海贼王_r84_BV14tZNYGEuV"
YOLOV8X_PATH = Path(r"D:\AE-Work\models\yolo\yolov8x.pt")
SAM2_CKPT_LARGE = Path(r"D:\AE-Work\models\sam2\sam2.1_hiera_large.pt")
SEG_LEN = 500
START_FRAME = 4000
END_FRAME = 10126
MAX_ATTEMPT = 3
SEG_TIMEOUT_S = 2 * 3600  # 2h 一段（auto_frame 大模型 500 帧约 2-3 min）

RETRY_CFG: list[tuple[str, dict, str, str]] = [
    ("default", {
        "face_conf": 0.35, "face_expand": 4.0,
        "yolo_conf": 0.05, "max_boxes_per_frame": 10,
        "sam_variant": "large",
    }, str(SAM2_CKPT_LARGE), ""),
    ("low_face_conf", {
        "face_conf": 0.12, "face_expand": 5.5,
        "yolo_conf": 0.02, "max_boxes_per_frame": 15,
        "sam_variant": "large",
    }, str(SAM2_CKPT_LARGE), ""),
    ("small_model", {
        "face_conf": 0.08, "face_expand": 7.0,
        "yolo_conf": 0.01, "max_boxes_per_frame": 20,
        "sam_variant": "small",
    }, str(Path(r"D:\AE-Work\models\sam2\sam2.1_hiera_small.pt")), ""),
]


def count_existing_masks(mask_dir: Path) -> int:
    if not mask_dir.exists(): return 0
    return sum(1 for _ in mask_dir.glob("mask_*.png"))


def copy_segment_masks(seg_dir: Path, dst_dir: Path, expected: int) -> tuple[int, int]:
    """复制段目录里所有 mask_*.png 到 dst_dir，返回复制数 / 段内实际数"""
    dst_dir.mkdir(parents=True, exist_ok=True)
    seg_masks = sorted(seg_dir.glob("mask_*.png"))
    copied = 0
    for p in seg_masks:
        t = dst_dir / p.name
        if not t.exists():
            shutil.copy2(p, t)
        copied += 1
    return copied, len(seg_masks)


def build_segments(start: int, end: int, seg_len: int) -> list[tuple[int, int, int]]:
    segs = []
    idx = max(0, (start // seg_len))
    cur = start
    while cur < end:
        s = cur
        e = min(cur + seg_len, end)
        segs.append((idx, s, e))
        cur = e
        idx += 1
    return segs


def run_one(seg_dir: Path, params: dict, timeout: int) -> tuple[int, str, str]:
    params_path = seg_dir / "params.json"
    seg_dir.mkdir(parents=True, exist_ok=True)
    with open(params_path, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)
    for suf in (".ok", ".fail"):
        m = str(params_path) + suf
        if os.path.exists(m):
            try: os.remove(m)
            except Exception: pass
    try:
        p = subprocess.run(
            [str(VENV_PY), str(INFER_SCRIPT), str(params_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(PROJECT_ROOT),
        )
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired as e:
        return -99, e.stdout or "", (e.stderr or "") + f"\n[TIMEOUT {timeout}s]"


def main():
    if not SRC_MP4.exists():
        print(f"[FATAL] src mp4 not found: {SRC_MP4}"); sys.exit(1)
    MASK_DIR.mkdir(parents=True, exist_ok=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    segs = build_segments(START_FRAME, END_FRAME, SEG_LEN)
    exist_mask = count_existing_masks(MASK_DIR)
    log_file = PROJECT_ROOT / "output" / "continue_onepiece_v4.log"
    log_f = open(log_file, "w", encoding="utf-8", buffering=1)
    def L(msg: str): print(msg); log_f.write(msg + "\n"); log_f.flush()
    L("=" * 70)
    L(f"海贼王 v4 续跑：{SRC_MP4.name}")
    L(f"  START={START_FRAME} END={END_FRAME} 段数={len(segs)}")
    L(f"  现有成品 mask: {exist_mask}")
    L("=" * 70)
    all_ok = 0
    total_copied = 0
    t0 = time.time()
    for i, (seg_idx, sf, ef) in enumerate(segs):
        L(f"\n[{i+1}/{len(segs)}] seg{seg_idx:03d}_{sf}_{ef} (len={ef-sf})")
        seg_dir = TMP_ROOT / f"seg{seg_idx:03d}_{sf}_{ef}"
        # 若段里已有 500 mask → 视为之前已跑过，直接 copy
        pre_masks = sorted(seg_dir.glob("mask_*.png")) if seg_dir.exists() else []
        if len(pre_masks) >= (ef - sf) * 0.95:
            L(f"  段已完成，直接 copy: {len(pre_masks)}")
            cp, cnt = copy_segment_masks(seg_dir, MASK_DIR, ef - sf)
            total_copied += cp; all_ok += 1
            L(f"  copy: {cp}/{cnt} → all_ok={all_ok}")
            continue
        # 3 次尝试
        success = False
        for att in range(MAX_ATTEMPT):
            name, extra, ckpt, mcfg = RETRY_CFG[min(att, len(RETRY_CFG) - 1)]
            params = {
                "video_path": str(SRC_MP4),
                "start_frame": int(sf),
                "expected_frames": int(ef - sf),
                "mask_dir": str(seg_dir),
                "yolov8x_path": str(YOLOV8X_PATH),
                "sam2_checkpoint": ckpt,
            }
            if mcfg:
                params["model_cfg"] = mcfg
            params.update(extra)
            # 清理前一次 mask
            if seg_dir.exists():
                for old in seg_dir.glob("mask_*.png"):
                    try: old.unlink()
                    except Exception: pass
            t1 = time.time()
            rc, out, err = run_one(seg_dir, params, SEG_TIMEOUT_S)
            cost_s = round(time.time() - t1, 1)
            seg_cnt = len(sorted(seg_dir.glob("mask_*.png")))
            mark_ok = (seg_dir / "params.json.ok").exists()
            mark_fail = (seg_dir / "params.json.fail").exists()
            status = "ok" if (mark_ok and rc == 0) else "fail"
            L(f"    attempt {att+1}/{MAX_ATTEMPT} [{name}] status={status} in {cost_s}s rc={rc} masks={seg_cnt} ok={mark_ok} fail={mark_fail}")
            if rc != 0 and err:
                snippet = "\n".join((err.strip().splitlines()[-4:]))
                L(f"      stderr tail:\n{snippet}")
            if status == "ok" and seg_cnt >= max(1, int((ef - sf) * 0.2)):
                # copy to master
                cp, cnt = copy_segment_masks(seg_dir, MASK_DIR, ef - sf)
                total_copied += cp; all_ok += 1
                L(f"    copy master: {cp}/{cnt} → all_ok={all_ok} master_masks={count_existing_masks(MASK_DIR)}")
                success = True
                break
            # QC fail: 升级重试
        if not success:
            L(f"    [FATAL] 全部重试失败，跳到下一段")
    L(f"\n" + "=" * 70)
    L(f"结束：成功段 {all_ok}/{len(segs)}，累计 copy mask={total_copied}")
    L(f"最终成品 mask 数量：{count_existing_masks(MASK_DIR)} / {END_FRAME}")
    L(f"总耗时: {time.time()-t0:.0f}s")
    log_f.close()


if __name__ == "__main__":
    main()
