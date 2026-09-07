"""批量生成显著性 prompt 可视化图（CPU 操作，不调用 SAM2）。

用途：为 0% 检出率的视频生成显著性分析图，帮助选择最佳 prompt 点。
     不占用 GPU，可与 Step 3 并行运行。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from saliency_prompt import find_prompts_with_visualization

SRC_DIR = PROJECT_ROOT / "data" / "real_amv_test"
VIS_DIR = Path(r"D:\AE-Work\saliency_vis")
VIS_DIR.mkdir(parents=True, exist_ok=True)

LOW_VIDEOS_FILE = Path(r"D:\AE-Work\low_detection_videos.json")


def main():
    if not LOW_VIDEOS_FILE.exists():
        print(f"文件不存在: {LOW_VIDEOS_FILE}")
        return

    videos = json.loads(LOW_VIDEOS_FILE.read_text(encoding="utf-8-sig"))
    print(f"共 {len(videos)} 个视频需要生成显著性可视化图")
    print()

    results = []
    for i, v in enumerate(videos):
        stem = v["Stem"] if isinstance(v, dict) else v
        src = SRC_DIR / f"{stem}.mp4"
        if not src.exists():
            print(f"[{i+1}/{len(videos)}] SKIP (源不存在): {stem[:50]}")
            continue

        vis_png = VIS_DIR / f"{stem}_saliency.png"
        prompts, _ = find_prompts_with_visualization(src, vis_png, num_points=3)

        print(f"[{i+1}/{len(videos)}] {stem[:50]}")
        if prompts:
            for j, p in enumerate(prompts):
                print(f"    [{j+1}] x={p['x']}, y={p['y']}, score={p['score']}")
        else:
            print(f"    未找到候选点")

        results.append({"stem": stem, "prompts": prompts, "vis_png": str(vis_png)})

    # 保存 prompt 列表
    out_file = VIS_DIR / "saliency_prompts.json"
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"完成: {len(results)}/{len(videos)}")
    print(f"可视化图目录: {VIS_DIR}")
    print(f"Prompt 列表: {out_file}")


if __name__ == "__main__":
    main()
