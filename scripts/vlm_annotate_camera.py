#!/usr/bin/env python3
"""
Step 4 A3: VLM 运镜预标注 (SiliconFlow Qwen3-VL-8B)

对 A2 切出的镜头候选 (shots_manifest.jsonl) 逐镜头做运镜预标注:
  - 每个镜头抽 4 帧 (0%/33%/66%/100%), 让 VLM 感知运动方向
  - 输出三维标签 (A3 CameraBench 校准结论): direction + speed + stability
  - 置信度 < 0.7 或 direction=complex 的镜头进人工复核队列 (主动学习)

成本 (SiliconFlow Qwen3-VL-8B): ~¥0.001/镜头, 5,000 镜头 ≈ ¥5
方向约定 (与 core/camera_movement_classifier.py 光流规则一致, 2026-08-15 修订):
  画面向右移动 → pan_left (相机左摇); 画面放大/从中心向外扩散 → zoom_in (推近);
  画面缩小/从四周向中心收缩 → zoom_out (拉远); 画面上移 → tilt_down (相机下摇)

用法:
  py -3.12 scripts/vlm_annotate_camera.py --limit 20      # 冒烟
  py -3.12 scripts/vlm_annotate_camera.py                 # 全量 (A2 完成后)
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.camera_vocabulary import ANNOTATION_LABEL_SCHEMA  # noqa: E402

DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")
SHOTS_MANIFEST = DATA_ROOT / "shots_manifest.jsonl"
LABELS_OUT = DATA_ROOT / "vlm_labels.jsonl"
HUMAN_QUEUE = DATA_ROOT / "human_review_queue.jsonl"
FFMPEG = "ffmpeg"
# 跨平台: Windows 用 CREATE_NO_WINDOW 隐藏黑窗, Linux 无此属性用 0
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

VLM_BASE_URL = "https://api.siliconflow.cn/v1"
VLM_MODEL = "Qwen/Qwen3-VL-30B-A3B-Instruct"  # MoE 30B/3B激活, 项目网关标注"视觉标注最省"
# 第二通道: ModelScope 免费 Qwen3-VL-235B (质量更高, 独立限流, 双通道分流翻倍吞吐)
MS_BASE_URL = "https://api-inference.modelscope.cn/v1"
MS_MODEL = "Qwen/Qwen3-VL-235B-A22B-Instruct"
# 第三通道: 阿里云百炼 (DashScope OpenAI 兼容端点; 模型回退链共享同一账户额度池)
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_MODELS = ["qwen-vl-max", "qwen3-vl-plus", "qwen-omni-turbo"]
# 第四通道: 千问AI平台 (MaaS 端点, omni 多模态免费额度 100% 剩余)
QWEN_AI_BASE_URL = "https://ws-a1owuyh7kmtkx1hc.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
QWEN_AI_MODEL = "qwen3.5-omni-plus"
MAX_RETRIES = 3
CONFIDENCE_FLOOR = 0.7          # 低于此置信度进人工队列
FRAMES_PER_SHOT = 4

PROMPT = """你是专业的运镜分析专家。下面按时间顺序给出了同一镜头的 %d 帧画面，请判断这个镜头的相机运动。

方向选项 (direction, 单选):
  static(静止) / pan_left(左摇) / pan_right(右摇) / tilt_up(上摇) / tilt_down(下摇) /
  zoom_in(推近变焦) / zoom_out(拉远变焦) / push(物理推近) / zoom_back(物理拉远) /
  orbit(环绕/旋转) / complex(复杂多轴)
速度 (speed, 单选): regular-speed(常规) / slow-speed(慢速) / fast-speed(快速)
稳定 (stability, 单选): no-shaking(稳定) / minimal-shaking(轻微晃动) / unsteady(晃动) / very-unsteady(剧烈晃动)

判定约定 (关键, 画面特征方向与相机方向相反):
  画面内容整体向右移动 → 相机左摇 → pan_left
  画面内容整体向左移动 → 相机右摇 → pan_right
  画面从中心向外扩散/放大 → zoom_in; 画面从四周向中心收缩/缩小 → zoom_out
  画面上移 → tilt_down; 画面下移 → tilt_up
  明显透视变化+前后移动 → push/zoom_back; 绕主体旋转 → orbit
  多轴复合运动或方向不定 → complex

请严格只返回 JSON (不要其他文字, 不要 markdown):
{"direction": "pan_left", "speed": "regular-speed", "stability": "no-shaking", "confidence": 0.85}

confidence 要求: 非常确定=0.9+, 比较确定=0.7-0.9, 不确定=0.5-0.7, 完全看不出=0.3-0.5""" % FRAMES_PER_SHOT


def _load_done() -> set:
    done = set()
    if LABELS_OUT.exists():
        for line in LABELS_OUT.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["shot_id"])
            except (json.JSONDecodeError, KeyError):
                pass
    return done


def stratified_sample(shots: List[Dict[str, Any]], n_total: int,
                      seed: int = 42, oped_weight: float = 1.5) -> List[Dict[str, Any]]:
    """按 (anime, source_type) 加权分层抽样。

    oped 权重 1.5 (OP/ED 镜头语言规范, 是金标准素材);
    组内等概率抽样, 确定性 seed (可复现)。
    """
    import collections
    import random
    if n_total >= len(shots):
        return shots
    rng = random.Random(seed)
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = collections.defaultdict(list)
    for s in shots:
        groups[(s.get("anime", ""), s.get("source_type", ""))].append(s)

    weights = {g: (oped_weight if g[1] == "oped" else 1.0) for g in groups}
    w_total = sum(len(v) * weights[g] for g, v in groups.items())

    # 加权比例分配 (floor + 按小数部分补足)
    alloc: Dict[Tuple[str, str], int] = {}
    fracs: List[Tuple[float, Tuple[str, str]]] = []
    assigned = 0
    for g, v in groups.items():
        exact = len(v) * weights[g] / w_total * n_total
        alloc[g] = min(len(v), int(exact))
        assigned += alloc[g]
        fracs.append((exact - int(exact), g))
    for _, g in sorted(fracs, reverse=True):
        if assigned >= n_total:
            break
        if alloc[g] < len(groups[g]):
            alloc[g] += 1
            assigned += 1

    picked: List[Dict[str, Any]] = []
    for g, v in groups.items():
        k = min(alloc[g], len(v))
        picked.extend(rng.sample(v, k))
    rng.shuffle(picked)
    return picked


def extract_frames(clip_path: str, dur_sec: Optional[float] = None,
                   n: int = FRAMES_PER_SHOT) -> List[str]:
    """从镜头切片抽 n 帧 (单次 ffmpeg 调用, fps 滤镜均匀采样), 返回 base64 JPEG。

    性能: 原来 5 次 ffmpeg 调用 (探测+逐帧), 云上并发时磁盘打架;
    现在 1 次调用, dur 优先用清单 duration_sec (免探测)。
    """
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="vlm_frames_"))
    dur = dur_sec
    if not dur or dur <= 0:
        dur = 2.0
    fps = n / max(dur, 0.5)
    # 单次调用: fps 滤镜均匀抽 n 帧
    r = subprocess.run(
        [FFMPEG, "-y", "-i", clip_path,
         "-vf", f"fps={fps:.4f},scale=512:-2",
         "-frames:v", str(n), str(tmp / "f%d.jpg")],
        capture_output=True, creationflags=_NO_WINDOW)
    frames = []
    for out in sorted(tmp.glob("f*.jpg")):
        frames.append(base64.b64encode(out.read_bytes()).decode())
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    # 帧数不足 n (超短镜头): 循环补齐
    while frames and len(frames) < n:
        frames.append(frames[len(frames) % len(frames)])
    return frames[:n] if frames else []


def annotate_shot(client, frames_b64: List[str],
                  model: Any = VLM_MODEL) -> Tuple[Optional[Dict[str, Any]], float]:
    """调 VLM 标注单镜头, 返回 (结果, 成本)。model 可为 str 或列表 (回退链)。"""
    models = model if isinstance(model, (list, tuple)) else [model]
    content: List[Dict[str, Any]] = [{"type": "text", "text": PROMPT}]
    for fb in frames_b64:
        content.append({"type": "image_url", "image_url": {
            "url": f"data:image/jpeg;base64,{fb}", "detail": "low"}})

    for m in models:
        for attempt in range(MAX_RETRIES):
            try:
                resp = client.chat.completions.create(
                    model=m,
                    messages=[{"role": "user", "content": content}],
                    max_tokens=300,
                    temperature=0.1,
                )
                text = resp.choices[0].message.content.strip()
                usage = resp.usage
                cost = (usage.prompt_tokens * 0.15 + usage.completion_tokens * 0.60) / 1e6 \
                    if usage and usage.prompt_tokens else 0.0
                # 剥离 markdown 代码块
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
                m2 = re.search(r"\{.*\}", text, re.S)
                if m2:
                    text = m2.group(0)
                result = json.loads(text)
                return result, cost
            except json.JSONDecodeError:
                if attempt == MAX_RETRIES - 1:
                    break  # 换下一个模型
            except Exception as exc:  # noqa: BLE001
                if attempt == MAX_RETRIES - 1:
                    print(f"    VLM 失败 ({m}): {str(exc)[:50]}")
                    break  # 换下一个模型
                time.sleep(2 * (attempt + 1))
    return None, 0.0


def _validate(result: Dict[str, Any]) -> bool:
    if result.get("direction") not in ANNOTATION_LABEL_SCHEMA["direction"]:
        return False
    if result.get("speed") not in ANNOTATION_LABEL_SCHEMA["speed"]:
        result["speed"] = "regular-speed"
    if result.get("stability") not in ANNOTATION_LABEL_SCHEMA["stability"]:
        result["stability"] = "no-shaking"
    return True


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Step 4 A3: VLM 运镜预标注")
    parser.add_argument("--limit", type=int, default=0, help="只标注前 N 个镜头 (0=全部)")
    parser.add_argument("--sample", type=int, default=0,
                        help="分层抽样 N 个镜头再标注 (oped 加权 1.5x, seed 42)")
    parser.add_argument("--dry-run", action="store_true", help="只抽帧不调 API (验证抽取)")
    parser.add_argument("--data-root", default=str(DATA_ROOT),
                        help="数据根目录 (云训练时传 /root/autodl-tmp)")
    parser.add_argument("--workers", type=int, default=1,
                        help="并发标注路数 (云端多核 8-12, 本机默认 1)")
    parser.add_argument("--channel", default="auto",
                        choices=["auto", "siliconflow", "modelscope", "bailian", "qwenai"],
                        help="标注通道 (auto=四通道分流)")
    args = parser.parse_args()

    global SHOTS_MANIFEST, LABELS_OUT, HUMAN_QUEUE
    root = Path(args.data_root)
    is_local = root == Path(DATA_ROOT)
    SHOTS_MANIFEST = root / "shots_manifest.jsonl"
    LABELS_OUT = root / ("vlm_labels.jsonl" if is_local else "vlm_labels_cloud.jsonl")
    HUMAN_QUEUE = root / ("human_review_queue.jsonl" if is_local else "human_review_queue_cloud.jsonl")

    if not SHOTS_MANIFEST.exists():
        print(f"[A3] shots_manifest 不存在: {SHOTS_MANIFEST} (先跑 A2 切镜头)")
        return 1

    shots = [json.loads(l) for l in SHOTS_MANIFEST.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.sample > 0:
        shots = stratified_sample(shots, args.sample)
        print(f"[A3] 分层抽样: {len(shots)} / 全量候选")
    if args.limit > 0:
        shots = shots[:args.limit]
    done = _load_done()
    pending = [s for s in shots if s["shot_id"] not in done]
    print(f"[A3] 总镜头 {len(shots)}, 已标注 {len(done)}, 待标注 {len(pending)}")

    if args.dry_run:
        for s in pending[:3]:
            frames = extract_frames(s["clip_path"])
            print(f"  抽帧 {s['shot_id']}: {len(frames)} 帧")
        return 0

    import os
    from openai import OpenAI
    api_key = os.environ.get("SILICONFLOW_API_KEY", "")
    ms_key = os.environ.get("MODELSCOPE_API_KEY", "")
    qwen_key = os.environ.get("QWEN_API_KEY", "")
    qwenai_key = os.environ.get("QWEN_AI_API_KEY", "")
    if not api_key or not ms_key or not qwen_key or not qwenai_key:
        # 从 .env 读取
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not api_key and line.startswith("SILICONFLOW_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if not ms_key and line.startswith("MODELSCOPE_API_KEY="):
                    ms_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if not qwen_key and line.startswith("QWEN_API_KEY="):
                    qwen_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if not qwenai_key and line.startswith("QWEN_AI_API_KEY="):
                    qwenai_key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not api_key:
        print("[A3] 无 SILICONFLOW_API_KEY, 跳过 (检查 .env)")
        return 1
    client = OpenAI(api_key=api_key, base_url=VLM_BASE_URL, timeout=90, max_retries=2)
    # 多通道分流: SiliconFlow + ModelScope(235B) + 百炼(qwen-vl-max) + 千问AI(omni), 各独立限流
    channels = [("siliconflow", client, VLM_MODEL)]
    if ms_key and args.channel in ("auto", "modelscope"):
        ms_client = OpenAI(api_key=ms_key, base_url=MS_BASE_URL, timeout=120, max_retries=2)
        channels.append(("modelscope", ms_client, MS_MODEL))
    if qwen_key and args.channel in ("auto", "bailian"):
        qwen_client = OpenAI(api_key=qwen_key, base_url=QWEN_BASE_URL, timeout=90, max_retries=2)
        channels.append(("bailian", qwen_client, QWEN_MODELS))
    if qwenai_key and args.channel in ("auto", "qwenai"):
        qwenai_client = OpenAI(api_key=qwenai_key, base_url=QWEN_AI_BASE_URL,
                               timeout=90, max_retries=2)
        channels.append(("qwenai", qwenai_client, QWEN_AI_MODEL))
    print(f"[A3] 通道: {[c[0] for c in channels]}")
    if args.channel != "auto" and len(channels) == 1:
        print(f"[A3] 指定通道 {args.channel} 不可用")
        return 1

    # 并发标注 (云上多核提速: --workers 8-12; 本机默认 1)
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    write_lock = threading.Lock()
    total_cost = 0.0
    cost_lock = threading.Lock()
    n_ok = 0
    n_fail = 0
    n_human = 0
    t0 = time.time()
    done_count = 0
    count_lock = threading.Lock()

    def _annotate_one(args_i: Tuple[int, Dict[str, Any]]) -> None:
        nonlocal total_cost, n_ok, n_fail, n_human, done_count
        i, shot = args_i
        ch_name, ch_client, ch_model = channels[i % len(channels)]
        try:
            frames = extract_frames(shot["clip_path"],
                                    dur_sec=float(shot.get("duration_sec", 0) or 0))
            if not frames:
                with count_lock:
                    n_fail += 1
                    done_count += 1
                return
            result, cost = annotate_shot(ch_client, frames, model=ch_model)
        except Exception:  # noqa: BLE001
            with count_lock:
                n_fail += 1
                done_count += 1
            return
        with cost_lock:
            total_cost += cost
        if result and _validate(result):
            conf = float(result.get("confidence", 0.5))
            entry = {k: shot[k] for k in (
                "shot_id", "video_id", "shot_idx", "start_sec", "end_sec",
                "duration_sec", "source_type", "anime", "clip_path")}
            entry.update({
                "movement_label": result["direction"],
                "speed": result["speed"],
                "stability": result["stability"],
                "confidence": conf,
                "vlm_model": ch_name,
                "annotated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            with write_lock:
                with LABELS_OUT.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                if conf < CONFIDENCE_FLOOR or result["direction"] == "complex":
                    with HUMAN_QUEUE.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            with count_lock:
                n_ok += 1
                n_human += int(conf < CONFIDENCE_FLOOR or result["direction"] == "complex")
                done_count += 1
                cur = done_count
            print(f"  [{cur}/{len(pending)}] {shot['shot_id']} -> {result['direction']:12s} "
                  f"conf={conf:.2f}{' [人工]' if conf < CONFIDENCE_FLOOR else ''}")
        else:
            with count_lock:
                n_fail += 1
                done_count += 1
                cur = done_count
            print(f"  [{cur}/{len(pending)}] {shot['shot_id']} 解析失败")

    workers = min(args.workers, len(pending)) if len(pending) else 1
    print(f"[A3] 并发 {workers} 路 x {len(channels)} 通道标注中...")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(_annotate_one, enumerate(pending)))

    print(f"\n=== A3 汇总 === 标注 {n_ok} / 失败 {n_fail} / 人工队列 {n_human}")
    print(f"  成本 ¥{total_cost:.3f} | 耗时 {time.time() - t0:.0f}s | 并发 {workers} 路")
    print(f"  标签 -> {LABELS_OUT}\n  人工队列 -> {HUMAN_QUEUE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
