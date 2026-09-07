"""MatAnyone 抠像一键链路（2026-08-14 定案）

流程: 分段独立抠像(48帧/段,锚定约束) → alpha 曲线增强 → 光流空洞填充 → MED5 → MOV+QC

用法:
  py -3.12 scripts/matanyone_pipeline.py --video <mp4> --start <锚定起始帧> --frames <N> \
      [--outdir <dir>] [--max_size 512] [--seg-len 48] [--manual-anchors '帧:x1,y1,x2,y2;...']
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
VIDEO_DEFAULT = PROJECT / "data" / "real_amv_test" / "DL_FATE_r978_BV1qb411C79B_p1.mp4"


def run(cmd: list[str], desc: str) -> bool:
    print(f"\n[PIPE] {desc}", file=sys.stderr)
    r = subprocess.run(cmd, cwd=str(PROJECT))
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(VIDEO_DEFAULT))
    ap.add_argument("--start", type=int, default=100)
    ap.add_argument("--frames", type=int, default=292)
    ap.add_argument("--outdir", default="output/one_pipeline/matanyone")
    ap.add_argument("--max_size", type=int, default=512)
    ap.add_argument("--seg-len", type=int, default=48)
    ap.add_argument("--manual-anchors", default="")
    ap.add_argument("--motion_levels", default=r"D:\AE-Work\output\segment_tmp_pipeline\fate_motion\motion_levels.json",
                    help="现成 motion_levels.json（填充/合成用 flow_cache）")
    args = ap.parse_args()

    work = Path(args.outdir) / "_work"
    work.mkdir(parents=True, exist_ok=True)
    alpha_dir = work / "alpha"
    boost_dir = work / "boost"
    filled_dir = work / "filled"
    final_dir = work / "final"

    # 1. 分段 MatAnyone 抠像
    if not run([sys.executable, "scripts/matanyone_segments.py",
                "--video", args.video, "--start", str(args.start), "--frames", str(args.frames),
                "--outdir", str(work), "--max_size", str(args.max_size),
                "--seg-len", str(args.seg_len), "--manual-anchors", args.manual_anchors],
               "分段 MatAnyone 抠像"):
        return 1

    # 2. alpha 曲线增强
    subprocess.run([sys.executable, "output/step2_locator/_alpha_boost.py"], cwd=str(PROJECT))
    shutil.rmtree(boost_dir, ignore_errors=True)
    shutil.move(str(Path("output/step2_locator/matanyone_seg_boost")), str(boost_dir))
    # 3. 空洞填充
    subprocess.run([sys.executable, "output/step2_locator/_fate_fill_holes.py"], cwd=str(PROJECT))
    # 4. MED5
    if not run([sys.executable, "scripts/median_smooth_masks.py",
                "--maskdir", str(Path("output/step2_locator/matanyone_seg_filled")),
                "--outdir", str(final_dir), "--window", "5"], "MED5 平滑"):
        return 1

    # 5. MOV 合成（复用 make_one_mov_pipeline 的 MOV 段）
    slug = f"DL_{Path(args.video).stem}"
    mov_dir = Path(args.outdir)
    mask_dir = mov_dir / f"{slug}_masks"
    mask_dir.mkdir(parents=True, exist_ok=True)
    for p in final_dir.glob("mask_*.png"):
        shutil.copy(str(p), str(mask_dir / p.name))
    if not run([sys.executable, "scripts/make_one_mov_pipeline.py",
                "--input", args.video, "--engine", "enhanced",
                "--start_frame", str(args.start), "--frames", str(args.frames),
                "--motion_levels", args.motion_levels,
                "--output_dir", str(mov_dir)], "MOV 合成 + QC"):
        return 1

    print(f"\n[PIPE] 完成: MOV -> {mov_dir / (slug + '_alpha.mov')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
