"""collect_gold_missing.py — 定向补采黄金集缺失参数组合

从 GOLD dict 找 train_samples 未覆盖的参数组合, 逐一渲染+评分+留帧。
采集后 calibrate_gold_set 参数降级匹配自动补全 frame_dir/cnn/gbdt。

用法:
  python scripts/collect_gold_missing.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from core.visual_scorer import score_video  # noqa: E402
from scripts.calibrate_gold_set import GOLD, PK  # noqa: E402
from scripts.collect_tuning_data import FRAME_ROOT, SAMPLES, build_tree_with_params, render_tree  # noqa: E402
from scripts.m2_auto_iterate import _param_snapshot  # noqa: E402


def main() -> int:
    rows = [json.loads(l) for l in SAMPLES.read_text(encoding="utf-8").splitlines() if l.strip()]
    have_pk = set()
    for r in rows:
        try:
            have_pk.add(tuple(float(r.get(k, 0)) for k in PK))
        except (TypeError, ValueError):
            continue

    missing = [pk for pk in GOLD if pk not in have_pk]
    print(f"黄金参数组合: {len(GOLD)} | 已有 {len(GOLD) - len(missing)} | 补采 {len(missing)}")
    if not missing:
        return 0

    run_id = "G" + time.strftime("%H%M%S")
    t0 = time.time()
    n_ok = 0
    for i, pk in enumerate(missing):
        combo = dict(zip(PK, pk))
        combo["glow_mult"] = combo.pop("_glow_mult")  # GRID 键名无下划线
        combo["lut_theme"] = "none"
        combo["lut_strength"] = 1.0
        print(f"\n=== [{i + 1}/{len(missing)}] {combo}")
        tree = build_tree_with_params(combo)
        tag = f"g{run_id}_{i:03d}"
        out_mp4 = SAMPLES.parent / "tmp_gold" / f"{tag}.mp4"
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        if not render_tree(tree, str(out_mp4), f"gold_{i:03d}.aep"):
            print("  渲染失败, 跳过")
            continue
        score = None
        for _retry in range(3):
            score = score_video(str(out_mp4), n_frames=4)
            if not score.get("error"):
                break
            print(f"  评分失败重试: {score['error'][:40]}")
            time.sleep(30)
        if not score or score.get("error"):
            print("  评分最终失败, 跳过")
            continue
        frame_dir = FRAME_ROOT / f"{run_id}_{n_ok:03d}"
        if frame_dir.exists():
            raise RuntimeError(f"帧目录冲突 {frame_dir}")
        frame_dir.mkdir(parents=True)
        import cv2 as cv2
        cap = cv2.VideoCapture(str(out_mp4))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        n = min(4, max(total, 1))
        for fi in range(n):
            gi = int(fi * (total - 1) / max(n - 1, 1)) if total > 1 else 0
            cap.set(cv2.CAP_PROP_POS_FRAMES, gi)
            ret, f = cap.read()
            if ret:
                cv2.imwrite(str(frame_dir / f"frame_{fi:02d}.jpg"), f,
                            [cv2.IMWRITE_JPEG_QUALITY, 85])
        cap.release()
        row = _param_snapshot(tree)
        row.update({f"score_{k}": v for k, v in score.get("scores", {}).items()})
        row["score_overall"] = score.get("overall", 0)
        row["frame_dir"] = str(frame_dir)
        row["lut_theme"] = "none"
        with open(SAMPLES, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        n_ok += 1
        out_mp4.unlink(missing_ok=True)
        print(f"  落盘 overall={row['score_overall']} | {time.time() - t0:.0f}s")

    print(f"\n补采完成: {n_ok}/{len(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
