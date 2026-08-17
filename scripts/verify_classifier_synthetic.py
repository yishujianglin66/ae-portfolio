#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_classifier_synthetic.py — 合成视频直验 (替代沙箱内不可用的 pytest tmp)

复用 tests/test_camera_classifier.py 的夹具生成器, 断言:
  static/pan_left/pan_right/zoom_in/zoom_out/complex 六类合成视频的
  分类器输出 (不经过 pytest, 视频写入 analysis_out/synthetic)。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载测试模块 (不执行 pytest)
spec = importlib.util.spec_from_file_location(
    "tc", PROJECT_ROOT / "tests" / "test_camera_classifier.py")
tc = importlib.util.module_from_spec(spec)
sys.modules["tc"] = tc
spec.loader.exec_module(tc)  # type: ignore[union-attr]

from core.camera_movement_classifier import classify_video  # noqa: E402

OUT = PROJECT_ROOT / "analysis_out" / "synthetic"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cases = [
        ("static", tc._gen_static(), "static"),
        ("pan_left", tc._gen_pan_left(), "pan_left"),
        ("pan_right", tc._gen_pan_right(), "pan_right"),
        ("zoom_in", tc._gen_zoom_in(), "zoom_in"),
        ("zoom_out", tc._gen_zoom_out(), "zoom_out"),
    ]
    ok = True
    for name, frames, expect in cases:
        path = tc._gen_video(frames, OUT / f"{name}.mp4")
        r = classify_video(str(path))
        fs = r["flow_stats"]
        got = r["dominant"]
        good = got == expect
        ok &= good
        print(f"{'PASS' if good else 'FAIL'} {name:<10} expect={expect:<10} "
              f"got={got:<10} conf={r['confidence']:.2f} "
              f"dx={fs['mean_dx']:+.1f} dy={fs['mean_dy']:+.1f} "
              f"rad={fs['mean_radial']:+.1f} rad_con={fs['radial_consistency']:.2f} "
              f"h_con={fs['h_consistency']:.2f} v_con={fs['v_consistency']:.2f} "
              f"disp={fs['total_disp']:.1f}")
    # complex 不应判 static (平移+缩放同时, 复刻测试 fixture 逻辑)
    import numpy as np
    src = tc._make_source_image()
    sh, sw = tc._SRC_SIZE[1], tc._SRC_SIZE[0]
    cx_s, cy_s = sw / 2.0, sh / 2.0
    cframes = []
    for i in range(tc._N_FRAMES):
        t = i / max(tc._N_FRAMES - 1, 1)
        scale = 1.0 + 0.2 * t
        ww, wh = int(tc._W * scale), int(tc._H * scale)
        offset_x = int(80 * t)
        x0 = max(0, min(int(cx_s - ww / 2) + offset_x, sw - ww))
        y0 = max(0, min(int(cy_s - wh / 2), sh - wh))
        roi = src[y0:y0 + wh, x0:x0 + ww]
        cframes.append(cv2.resize(roi, (tc._W, tc._H), interpolation=cv2.INTER_LINEAR))
    cpath = tc._gen_video(cframes, OUT / "complex.mp4")
    r = classify_video(str(cpath))
    good = r["dominant"] != "static"
    ok &= good
    print(f"{'PASS' if good else 'FAIL'} complex     expect!=static     "
          f"got={r['dominant']} conf={r['confidence']:.2f}")
    # 结构完整性
    assert "dominant" in r and "confidence" in r and "flow_stats" in r \
        and "per_segment" in r and len(r["per_segment"]) >= 1
    assert 0.0 <= r["confidence"] <= 1.0
    missing = classify_video(str(OUT / "nope.mp4"))
    assert missing["dominant"] == "unknown" and missing["confidence"] == 0.0
    print("PASS 结构完整性 + 缺文件安全默认")
    print(f"\n{'全部通过' if ok else '存在失败'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
