# -*- coding: utf-8 -*-
"""run53v43 整片精修 — AE polish_pass 高效模式

使用 AERenderChannel.polish_pass 对整片应用 Glow + Noise 精修，
比逐镜AE快10-20倍，同时保持插件级质感。

用法: python scripts/auto_apply_run53v43_polish.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.ae_render_channel import AERenderChannel

ROOT = Path(__file__).resolve().parent.parent
VIDEO_IN = ROOT / "output" / "unified_run53" / "run53_final_v43.mp4"
OUT_DIR = ROOT / "output" / "unified_run53" / "run53v43_polished"


def main():
    if not VIDEO_IN.exists():
        print(f"[ERROR] Input video not found: {VIDEO_IN}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize AE render channel
    channel = AERenderChannel(out_dir=str(OUT_DIR))

    # Use polish_pass for efficient whole-video enhancement
    print("\n[AE Polish] Applying Glow + Noise to entire video...")
    print(f"  Input: {VIDEO_IN}")
    print(f"  Output: {OUT_DIR}")

    result = channel.polish_pass(video_in=str(VIDEO_IN), out_dir=str(OUT_DIR))

    if result:
        print(f"\n[OK] Polished video: {result}")
        from pathlib import Path
        p = Path(result)
        if p.exists():
            print(f"  File size: {p.stat().st_size / (1024*1024):.1f} MB")
        return 0
    else:
        print("\n[FAIL] Polish failed")
        failures = channel.get_failures()
        if failures:
            print("\nFailure details:")
            for f in failures:
                print(f"  - {f}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
