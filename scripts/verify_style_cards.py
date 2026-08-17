# -*- coding: utf-8 -*-
"""批量风格卡验证 — 依次跑 4 张卡, 每张保存独立报告 (production_report 会被覆盖)

用法: python scripts/verify_style_cards.py [style_id ...]
默认: emotional_lyric vintage_film cinematic_film high_key_bright
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.production_director import ProductionDirector  # noqa: E402

SOURCES = [
    r"D:\AE-Work\resources\video\猫猫（一般）\素材\猫1.mp4",
    r"D:\AE-Work\resources\video\猫猫（一般）\素材\猫2.mp4",
    r"D:\AE-Work\resources\video\美人鱼（较难）\素材\alya-05.mp4",
    r"D:\AE-Work\resources\video\初音（简单）\Hatsune Miku Twixtor 4K.mp4",
    r"D:\BaiduNetdiskDownload\AE新手10套\五条悟（一般）\素材\五条悟第二季.mp4",
    r"D:\BaiduNetdiskDownload\AE新手10套\独自升级（一般）\独自升级2.mp4",
    r"D:\BaiduNetdiskDownload\AE新手10套\独自升级（一般）\独自升级5.mp4",
]
BGM = r"D:\AE-Work\音频素材库\BGM\独自升级.mp3"
OUT_DIR = r"D:\output_director\solo_pilot\v23"
THEME = "我独自升级题材的燃向战斗混剪，铺垫-蓄力-爆发-收尾的情绪递进，爆发段必须是激烈战斗画面"
REPORT = Path(OUT_DIR) / "production_report.json"

STYLES = sys.argv[1:] or [
    "emotional_lyric", "vintage_film", "cinematic_film", "high_key_bright",
]


def main():
    summary = {}
    for style in STYLES:
        print(f"\n{'='*60}\n风格卡: {style}\n{'='*60}", flush=True)
        t0 = time.time()
        director = ProductionDirector()
        try:
            output = director.render(
                video_sources=SOURCES, bgm_path=BGM, output_dir=OUT_DIR,
                output_name=f"v23_style_{style}.mp4",
                bgm_start_sec=0.0, target_duration=None,
                resolution=(1920, 1080), fps=24, target_ip="", strict=False,
                allow_mixed=True, verify_content=False, use_speed_ramp=True,
                style_id=style, bpm_override=None, theme=THEME,
                enable_ae_channel=False,
            )
            elapsed = time.time() - t0
            # 保存独立报告 (production_report.json 会被下一轮覆盖)
            if REPORT.exists():
                dst = Path(OUT_DIR) / f"report_style_{style}.json"
                shutil.copy(REPORT, dst)
                rep = json.loads(REPORT.read_text(encoding="utf-8"))
                tp = rep.get("taste_profile", {})
                from collections import Counter
                cams = Counter(
                    s["zoompan_effect"] for s in rep["script"]["segments"])
                viols = len(tp.get("anti_default_violations", []))
                summary[style] = {
                    "ok": True, "elapsed_min": round(elapsed / 60, 1),
                    "taste": (tp.get("visual_variance"),
                              tp.get("motion_intensity"),
                              tp.get("information_density")),
                    "n_camera_types": len(cams),
                    "violations": viols,
                }
                print(f"[{style}] 完成 {elapsed/60:.1f}min | 报告 -> {dst.name}",
                      flush=True)
        except Exception as e:  # noqa: BLE001
            summary[style] = {"ok": False, "error": str(e)[:200]}
            print(f"[{style}] 失败: {e}", flush=True)

    out = Path(OUT_DIR) / "style_matrix_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n汇总 -> {out}")
    for k, v in summary.items():
        print(f"  {k:20s} {v}")


if __name__ == "__main__":
    main()
