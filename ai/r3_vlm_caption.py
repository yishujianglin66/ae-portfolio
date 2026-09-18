# -*- coding: utf-8 -*-
r"""R3 VLM 帧级 caption（2026-09-08 深夜启动）。

动机（r3_doc_rewrite 实验结论）：模板改写零收益，检索瓶颈在文档侧信息量。
本脚本给检索索引内的 1075 帧（与 t11 enrich 同 seed42 采样）生成真实画面描述，
文档侧首次拥有场景级语义。

模型: chancharikm/qwen2.5-vl-7b-cam-motion（项目运镜专家，4bit nf4，≈6GB 显存）
产出: cache/bge_m3_index/frame_captions.jsonl  # 每行 {"file_hash","caption"}
断点续传: 已有 file_hash 直接跳过（中断重跑只补缺）。
评测: 跑完后由 r3_vlm_benchmark.py 消费 caption 做对照实验。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("HF_HUB_CACHE", r"D:\hf_cache\hub")

CAPTION_CACHE = ROOT / "cache" / "bge_m3_index" / "frame_captions.jsonl"
VLM_MODEL = "chancharikm/qwen2.5-vl-7b-cam-motion"
BATCH_PROMPT = (
    "用一两句中文描述这个动画画面：出现哪些角色（发色、服装、显著外貌特征）、"
    "他们在做什么动作、周围场景与氛围。只描述看得见的内容，50字以内。"
)


def _log(msg: str):
    print(f"[R3-CAP] {msg}", flush=True)


def collect_index_frames():
    """与 t11 enrich_with_pseudolabels 完全相同的采样（seed42, max_per_ip=50）。"""
    import numpy as np

    from ai.t11_hybrid_search import CHAR_TO_IP

    pseudo = json.loads(Path(r"D:\aot_corpus\pseudolabels.json").read_text(encoding="utf-8"))
    ip_groups: dict = {}
    for p in pseudo:
        ip_groups.setdefault(p["ip"], []).append(p)

    frames_out = []  # (file_hash, frame_path)
    for ip, frames in ip_groups.items():
        if len(frames) < 10:
            continue
        np.random.seed(42)
        n_sample = min(50, len(frames))
        indices = np.random.choice(len(frames), n_sample, replace=False)
        for idx in indices:
            frame = frames[idx]
            fp = frame.get("frame_path", "")
            if fp and Path(fp).exists():
                frames_out.append((f"frame_{ip}_{idx}", fp))
    return frames_out


def load_done() -> set:
    done = set()
    if CAPTION_CACHE.exists():
        for line in CAPTION_CACHE.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["file_hash"])
            except Exception:
                continue
    return done


def run_caption():
    import torch
    from qwen_vl_utils import process_vision_info
    from transformers import (
        AutoModelForImageTextToText,
        AutoProcessor,
        BitsAndBytesConfig,
    )

    _log("=" * 60)
    _log("R3 VLM 帧级 caption（qwen2.5-vl-7b-cam-motion, 4bit nf4）")
    _log("=" * 60)
    if not torch.cuda.is_available():
        raise SystemExit("CUDA 不可用，中止（需要 CUDA 版 torch + 4bit 量化）")

    _log("[1/3] 加载 VLM...")
    t0 = time.time()
    qconfig = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_type="nf4",
    )
    model = AutoModelForImageTextToText.from_pretrained(
        VLM_MODEL, quantization_config=qconfig, device_map="cuda",
    )
    model.eval()
    processor = AutoProcessor.from_pretrained(VLM_MODEL)
    _log(f"  加载 {time.time()-t0:.0f}s")

    _log("[2/3] 收集待 caption 帧（与 t11 索引同采样）...")
    frames = collect_index_frames()
    done = load_done()
    todo = [(h, p) for h, p in frames if h not in done]
    _log(f"  索引帧 {len(frames)}，已完成 {len(done)}，待做 {len(todo)}")

    CAPTION_CACHE.parent.mkdir(parents=True, exist_ok=True)
    _log("[3/3] 逐帧 caption（断点续传，每 50 条刷盘一次）...")
    t0 = time.time()
    n = 0
    with open(CAPTION_CACHE, "a", encoding="utf-8") as f:
        for fh, fp in todo:
            try:
                messages = [{
                    "role": "user",
                    "content": [
                        {"type": "image", "image": fp},
                        {"type": "text", "text": BATCH_PROMPT},
                    ],
                }]
                text = processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True)
                image_inputs, video_inputs = process_vision_info(messages)
                inputs = processor(
                    text=[text], images=image_inputs, videos=video_inputs,
                    return_tensors="pt",
                ).to("cuda")
                with torch.inference_mode():
                    out = model.generate(
                        **inputs, max_new_tokens=80,
                        do_sample=False, temperature=1.0,
                    )
                # 去掉 prompt 部分
                gen = out[:, inputs["input_ids"].shape[1]:]
                caption = processor.batch_decode(
                    gen, skip_special_tokens=True,
                    clean_up_tokenization_spaces=False)[0].strip()
            except Exception as e:  # noqa: BLE001 单帧失败不中断全量
                caption = ""
                _log(f"  [WARN] {fh}: {type(e).__name__} {e}")
            f.write(json.dumps(
                {"file_hash": fh, "caption": caption},
                ensure_ascii=False) + "\n")
            n += 1
            if n % 50 == 0:
                f.flush()
                rate = n / (time.time() - t0)
                _log(f"  {n}/{len(todo)} ({rate:.2f} 帧/s, "
                     f"剩余 {(len(todo)-n)/rate/60:.0f} 分钟)")
    _log(f"完成: 新增 {n} 条 caption -> {CAPTION_CACHE}")
    _log(f"总耗时 {(time.time()-t0)/60:.1f} 分钟")


if __name__ == "__main__":
    run_caption()
