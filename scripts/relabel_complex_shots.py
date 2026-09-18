#!/usr/bin/env python3
"""
Step 4 精度优化: complex 标签二次清洗 (VLM 严格重标)

背景: 首次预标注里 VLM 对风格化推镜有 complex 误判倾向 (人工复核+光流对照发现)。
清洗策略: 对 direction=complex 的镜头做二次标注, prompt 强制"单一方向优先,
仅真多轴复合才判 complex"。二次结果若是单一方向且置信 >= 0.7 → 覆盖原标签
(标记 relabeled_by=pass2), 否则保留 complex。

成本: ~60 镜头 × ¥0.0002 ≈ ¥0.02, 本机 API 调用无需 GPU。

用法:
  py -3.12 scripts/relabel_complex_shots.py [--dry-run]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")
LABELS_FILE = DATA_ROOT / "vlm_labels.jsonl"
OUT_FILE = DATA_ROOT / "vlm_labels_v2.jsonl"

VLM_BASE_URL = "https://api.siliconflow.cn/v1"
VLM_MODEL = "Qwen/Qwen3-VL-8B-Instruct"
FRAMES_PER_SHOT = 4
MIN_CONF = 0.7
FFMPEG = "ffmpeg"

# 严格 prompt: 单一方向优先, 只有真复合才 complex
PROMPT = """你是专业的运镜分析专家。下面按时间顺序给出了同一镜头的 %d 帧画面, 请判断相机运动方向。

规则 (严格):
1. 绝大多数镜头只有一种主要运动, 请优先判为单一方向; 只有明确存在两种以上
   同时发生的主要运动(如边摇边推)才能判 complex
2. 画面运动方向与相机方向相反: 画面右移=pan_left, 画面扩散放大=zoom_in,
   画面收缩=zoom_out, 画面上移=tilt_down, 绕主体转=orbit
3. 若运动幅度极小几乎静止 → static

方向选项: static / pan_left / pan_right / tilt_up / tilt_down /
          zoom_in / zoom_out / push / zoom_back / orbit / complex

严格只返回 JSON:
{"direction": "zoom_in", "confidence": 0.9}""" % FRAMES_PER_SHOT


def extract_frames(clip_path: str) -> list[str]:
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="relabel_"))
    r = subprocess.run([FFMPEG, "-i", clip_path], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    dur = 0.0
    for line in r.stderr.decode("utf-8", errors="replace").splitlines():
        if "Duration" in line:
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", line)
            if m:
                dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                break
    if dur <= 0:
        dur = 2.0
    ts = [dur * min(0.98, i / (FRAMES_PER_SHOT - 1)) for i in range(FRAMES_PER_SHOT)]
    frames = []
    for i, t in enumerate(ts):
        out = tmp / f"f{i}.jpg"
        subprocess.run([FFMPEG, "-y", "-ss", f"{t:.3f}", "-i", clip_path,
                        "-frames:v", "1", "-vf", "scale=512:-2", str(out)],
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if out.exists():
            frames.append(base64.b64encode(out.read_bytes()).decode())
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return frames


def relabel(client, frames_b64: list[str]) -> tuple[dict[str, Any] | None, float]:
    content: list[dict[str, Any]] = [{"type": "text", "text": PROMPT}]
    for fb in frames_b64:
        content.append({"type": "image_url", "image_url": {
            "url": f"data:image/jpeg;base64,{fb}", "detail": "low"}})
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=VLM_MODEL,
                messages=[{"role": "user", "content": content}],
                max_tokens=200, temperature=0.1)
            text = resp.choices[0].message.content.strip()
            usage = resp.usage
            cost = (usage.prompt_tokens * 0.15 + usage.completion_tokens * 0.60) / 1e6
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
            m = re.search(r"\{.*\}", text, re.S)
            result = json.loads(m.group(0) if m else text)
            return result, cost
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                return None, 0.0
            time.sleep(2 * (attempt + 1))
    return None, 0.0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="complex 标签二次清洗")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = [json.loads(l) for l in LABELS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    complex_rows = [r for r in rows if r.get("movement_label") == "complex"]
    print(f"总标注 {len(rows)} | complex {len(complex_rows)} 条待清洗")

    if args.dry_run:
        for r in complex_rows[:3]:
            print("  抽帧", r["shot_id"])
        return 0

    api_key = os.environ.get("SILICONFLOW_API_KEY", "")
    if not api_key:
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("SILICONFLOW_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not api_key:
        print("无 API key, 退出")
        return 1
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=VLM_BASE_URL)

    total_cost = 0.0
    n_relabeled = 0
    n_kept = 0
    t0 = time.time()
    for i, r in enumerate(complex_rows):
        try:
            frames = extract_frames(r["clip_path"])
            result, cost = relabel(client, frames)
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i + 1}] {r['shot_id']} 异常: {str(exc)[:40]}")
            continue
        total_cost += cost
        if not result:
            continue
        d = result.get("direction", "")
        conf = float(result.get("confidence", 0.5))
        if d != "complex" and conf >= MIN_CONF and d in (
                "static", "pan_left", "pan_right", "tilt_up", "tilt_down",
                "zoom_in", "zoom_out", "push", "zoom_back", "orbit"):
            r["movement_label"] = d
            r["confidence"] = conf
            r["relabeled_by"] = "pass2_strict"
            n_relabeled += 1
            print(f"  [{i + 1}/{len(complex_rows)}] {r['shot_id']} complex -> {d} (conf {conf:.2f})")
        else:
            n_kept += 1
            print(f"  [{i + 1}/{len(complex_rows)}] {r['shot_id']} 维持 complex (conf {conf:.2f})")

    OUT_FILE.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                        encoding="utf-8")
    print(f"\n=== 清洗完成 === 改标 {n_relabeled} / 维持 {n_kept} | 成本 ¥{total_cost:.3f} "
          f"| {time.time() - t0:.0f}s")
    print(f"输出 -> {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
