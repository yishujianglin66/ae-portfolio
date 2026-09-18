"""生成文字遮挡用的 ISNet mask 序列 — 按事件窗 + 置信门控。

流程: 读 events.json → 对每个事件的字期窗逐帧跑 ISNet(onnx) → 置信门控
      (窗内中位覆盖率 ≥ 阈值 且 帧间稳定) → 通过的窗写出 mask PNG 序列 + manifest.json。

用法: python scripts/generate_occlusion_masks.py <run_dir>
输出: <run_dir>/text_overlay/occlusion/mask_<id>/f_###.png + manifest.json
      manifest: {"<event_id>": {"dir": "...", "start": t_in, "end": t_out, "median_cov": ...}}
环境: OCCLUSION_MIN_COV=0.08   窗内中位覆盖率门限(默认 8%)
      OCCLUSION_STABILITY=0.5  帧间稳定度门限(中位/最大 ≥ 此值, 防闪烁)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FPS = 24
S = 1024
ISNET = ROOT / "models" / "occlusion" / "isnetis.onnx"
BASE_VIDEO = ROOT / "output" / "unified_run53" / "run53_premium_final.mp4"


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="generate_occlusion_masks.py")
    ap.add_argument("run_dir", help="run 目录 (白名单 unified_run\\d+)")
    ap.add_argument("--min-cov", type=float,
                    default=float(os.environ.get("OCCLUSION_MIN_COV", 0.08)))
    ap.add_argument("--stability", type=float,
                    default=float(os.environ.get("OCCLUSION_STABILITY", 0.50)))
    ap.add_argument("--pad", type=float, default=0.08, help="事件窗前后各留的余量(秒)")
    ap.add_argument("--coh", type=float, default=0.35,
                    help="mask 成团度门限: 白像素/包围盒面积 (越接近1越像'一个人')")
    ap.add_argument("--min-floor", type=float, default=0.01,
                    help="窗内最小覆盖率下限 (低于此值说明该帧完全没检出, 会闪)")
    args = ap.parse_args()

    import re
    raw = str(args.run_dir).replace("\\", "/").removeprefix("output/")
    if not re.fullmatch(r"unified_run\d+", raw):
        print(f"[ERR] 非法 run 目录: {raw}")
        return 2
    run = ROOT / "output" / raw
    ev_p = run / "text_overlay" / "events.json"
    if not ev_p.exists():
        print(f"[ERR] 缺 {ev_p}")
        return 2

    if not ISNET.exists():
        print(f"[ERR] 缺 ISNet 模型: {ISNET} (先跑调研下载)")
        return 2
    if not BASE_VIDEO.exists():
        print(f"[ERR] 缺底片: {BASE_VIDEO}")
        return 2

    import onnxruntime as ort
    sess = ort.InferenceSession(str(ISNET), providers=["CPUExecutionProvider"])
    iname = sess.get_inputs()[0].name

    events = json.loads(ev_p.read_text(encoding="utf-8"))["events"]
    out_root = run / "text_overlay" / "occlusion"
    out_root.mkdir(parents=True, exist_ok=True)
    manifest = {}
    t0 = time.time()
    n_gen = n_pass = 0

    for e in events:
        eid = e["id"]
        t_in = max(0.0, e["t_in"] - args.pad)
        t_out = e["t_out"] + args.pad
        nfr = int(round((t_out - t_in) * FPS))
        if nfr < 3:
            continue
        # 1) 抽帧到临时目录
        tmp = out_root / f"tmp_{eid}"
        tmp.mkdir(exist_ok=True)
        for i in range(nfr):
            t = t_in + i / FPS
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.4f}",
                            "-i", str(BASE_VIDEO), "-frames:v", "1", "-update", "1",
                            str(tmp / f"s_{i:03d}.png")], capture_output=True)

        # 2) 逐帧 ISNet → 覆盖率 + mask
        covs = []
        mdir = out_root / f"mask_{eid}"
        mdir.mkdir(exist_ok=True)
        for i in range(nfr):
            sp = tmp / f"s_{i:03d}.png"
            if not sp.exists():
                covs.append(0.0)
                (mdir / f"f_{i:03d}.png").write_bytes(
                    (mdir / f"f_{i:03d}.png").read_bytes()
                    if (mdir / f"f_{i:03d}.png").exists() else b"")
                continue
            img = Image.open(sp).convert("RGB")
            W, H = img.size
            x = np.asarray(img.resize((S, S)), dtype=np.float32) / 255.0 - 0.5
            x = x.transpose(2, 0, 1)[None]
            y = sess.run(None, {iname: x})[0][0, 0]
            y = np.maximum(y, 0)
            if y.max() > 0:
                y = y / y.max()
            m = (y > 0.3).astype(np.uint8)
            mask = Image.fromarray((m * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
            mask.save(mdir / f"f_{i:03d}.png")
            covs.append(float((np.asarray(mask) > 127).mean()))
            sp.unlink(missing_ok=True)
        tmp.rmdir()

        med = float(np.median(covs)) if covs else 0.0
        mx = max(covs) if covs else 0.0
        mn = min(covs) if covs else 0.0
        stab = med / mx if mx > 0 else 0.0
        # v52 加两条硬判据 (v51 实测教训: 单靠"中位覆盖+稳定度"会放行**误判型** mask):
        #   ③ mask 必须是"成团的一个人" → 白像素/(包围盒面积) ≥ COH_MIN。
        #      实测 v51 放行的 #5: 逐帧 白/bbox 在 0.00-0.73 之间跳, 是 ISNet 把大片
        #      高饱和背景判成前景, 不是人物剪影 —— 用这种 mask 做反相遮罩, 文字会忽隐忽现。
        #   ④ 窗内**最小**覆盖不能塌到 0 (塌 0 = 该帧完全没检出, 反相后文字全露,
        #      与相邻帧反差极大 → 观感是"闪")。
        coh = []
        for i in range(nfr):
            mp = mdir / f"f_{i:03d}.png"
            if not mp.exists():
                continue
            m = np.asarray(Image.open(mp).convert("L")) > 127
            if m.sum() < 50:
                coh.append(0.0)
                continue
            ys, xs = np.where(m)
            bb = (xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1)
            coh.append(float(m.sum()) / max(bb, 1))
        coh_med = float(np.median(coh)) if coh else 0.0
        passed = (med >= args.min_cov and stab >= args.stability
                  and coh_med >= args.coh and mn >= args.min_floor)
        n_gen += 1
        if passed:
            n_pass += 1
            manifest[str(eid)] = {
                "dir": mdir.relative_to(run).as_posix(),
                "start": round(t_in, 4), "end": round(t_out, 4),
                "n_frames": nfr, "median_cov": round(med, 4),
                "stability": round(stab, 3),
            }
        else:
            # 未通过 → 删除 mask 目录避免误导
            for p in mdir.glob("*.png"):
                p.unlink()
            mdir.rmdir()
        print(f"  #{eid:>2} {e['word'][:6]:<6} {t_in:6.2f}-{t_out:6.2f}s frames={nfr:>3} "
              f"cov中位={med:.1%} 最小={mn:.1%} 稳定={stab:.2f} 成团={coh_med:.2f} "
              f"{'✓遮挡' if passed else '✗跳过'}")

    (out_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[OK] {n_pass}/{n_gen} 个事件窗通过门控, 用时 {time.time()-t0:.0f}s")
    print(f"     manifest: {out_root / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
