# -*- coding: utf-8 -*-
"""r5_i2v_generate.py — R5 生成能力最小闭环（Wan2.1 I2V GGUF @ ComfyUI）

链路：ComfyUI(127.0.0.1:8188) + ComfyUI-GGUF 节点
  UnetLoaderGGUF(wan2.1-i2v-14b-480p-Q3_K_M)
  + lightx2v I2V 480p 蒸馏 LoRA（4-8 步 cfg=1 可出片）
  + umt5_xxl fp8 text encoder + clip_vision_h + Wan2.1 VAE

实现约束：HTTP 全部复用 ai/aigc_generator.ComfyUIAdapter 既有方法
（_queue_prompt / _wait_for_completion / _download_output，内部走
_safe_urlopen 白名单校验），本脚本不新增网络代码。

验收（方案 R5）：
  ① 生成 2-4s 空镜/转场素材；② 显存峰值实测 <8GB 落盘；
  ③ 非劣检验：混入成片后语义分不低于纯素材版。

用法:
  # 起始图先经 /upload/image 上传（或放 ComfyUI/input/）
  python scripts/r5_i2v_generate.py --image start_image.png --frames 48
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))

from ai.aigc_generator import ComfyUIAdapter  # noqa: E402

POSITIVE = (
    "cinematic anime scenery, soft volumetric light, gentle camera drift, "
    "high detail, smooth motion, atmospheric"
)
NEGATIVE = (
    "blurry, low quality, distorted, watermark, text, jpeg artifacts, "
    "flickering, deformed"
)


def build_workflow(image: str, frames: int, width: int, height: int,
                   seed: int, steps: int) -> dict:
    """Wan2.1 I2V 工作流（GGUF 加载 + 蒸馏 LoRA 少步采样）。"""
    return {"prompt": {
        "1": {"class_type": "UnetLoaderGGUF",
              "inputs": {"unet_name": "wan2.1-i2v-14b-480p-Q3_K_M.gguf"}},
        "2": {"class_type": "LoraLoaderModelOnly",
              "inputs": {"model": ["1", 0],
                         "lora_name": "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
                         "strength_model": 1.0}},
        "3": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                         "type": "wan", "device": "default"}},
        "4": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["3", 0], "text": POSITIVE}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["3", 0], "text": NEGATIVE}},
        "6": {"class_type": "CLIPVisionLoader",
              "inputs": {"clip_name": "clip_vision_h.safetensors"}},
        "7": {"class_type": "CLIPVisionEncode",
              "inputs": {"clip_vision": ["6", 0], "image": ["8", 0],
                         "crop": "center"}},
        "8": {"class_type": "LoadImage", "inputs": {"image": image}},
        "9": {"class_type": "VAELoader",
              "inputs": {"vae_name": "Wan2_1_VAE_bf16.safetensors"}},
        "10": {"class_type": "WanImageToVideo",
               "inputs": {"positive": ["4", 0], "negative": ["5", 0],
                          "vae": ["9", 0], "width": width, "height": height,
                          "length": frames, "batch_size": 1,
                          "clip_vision_output": ["7", 0],
                          "start_image": ["8", 0]}},
        "11": {"class_type": "KSampler",
               "inputs": {"model": ["2", 0], "seed": seed, "steps": steps,
                          "cfg": 1.0, "sampler_name": "euler",
                          "scheduler": "simple",
                          "positive": ["10", 0], "negative": ["10", 1],
                          "latent_image": ["10", 2], "denoise": 1.0}},
        "12": {"class_type": "VAEDecode",
               "inputs": {"samples": ["11", 0], "vae": ["9", 0]}},
        "13": {"class_type": "CreateVideo",
               "inputs": {"images": ["12", 0], "fps": 24}},
        "14": {"class_type": "SaveVideo",
               "inputs": {"video": ["13", 0], "filename_prefix": "r5_gen"}},
    }, "client_id": "r5_gen"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="start_image.png",
                    help="ComfyUI input 内的起始图文件名")
    ap.add_argument("--frames", type=int, default=48, help="帧数（24fps，48=2s）")
    ap.add_argument("--width", type=int, default=832)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--max-wait", type=int, default=3600)
    ap.add_argument("--out", default="output/r5_gen")
    args = ap.parse_args()

    adapter = ComfyUIAdapter()
    if not adapter.is_available():
        print("ComfyUI 未运行（需 127.0.0.1:8188）")
        return 1
    print("ComfyUI 可达")

    wf = build_workflow(args.image, args.frames, args.width, args.height,
                        args.seed, args.steps)
    print(f"提交: {args.frames}帧@{args.width}x{args.height} "
          f"steps={args.steps} seed={args.seed}")
    t0 = time.time()
    pid = adapter._queue_prompt(wf["prompt"])
    if not pid:
        print("提交失败（队列未返回 prompt_id）")
        return 1
    print(f"prompt_id = {pid}")

    # 显存采样：ComfyUI /system_stats 含 VRAM 信息，轮询时一并记录
    vram_peak = 0.0
    result = None
    while time.time() - t0 < args.max_wait:
        time.sleep(20)
        try:
            stats = adapter._safe_system_stats() if hasattr(
                adapter, "_safe_system_stats") else None
            if stats is None:
                stats = json.loads(adapter._poll_system_stats()) \
                    if hasattr(adapter, "_poll_system_stats") else None
        except Exception:
            stats = None
        try:
            import urllib.request
            req = urllib.request.Request(adapter.comfyui_url + "/system_stats")
            from ai.aigc_generator import _safe_urlopen
            with _safe_urlopen(req, timeout=20) as r:
                stats = json.loads(r.read())
            vram = (stats.get("devices") or [{}])[0].get("vram_free")
            if vram:
                used_gb = (stats["devices"][0].get("vram_total", 0) - vram) / 2**30
                vram_peak = max(vram_peak, used_gb)
                print(f"  [{time.time() - t0:>5.0f}s] 显存占用 ~{used_gb:.2f}GB",
                      flush=True)
        except Exception:
            pass
        try:
            result = adapter._wait_for_completion(pid, max_wait=25)
        except Exception:
            result = None
        if result:
            break
        print(f"  ... 生成中 {time.time() - t0:.0f}s", flush=True)

    if not result:
        print("超时")
        return 2

    print(f"\n完成（{time.time() - t0:.0f}s）")
    outdir = PROJ / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    saved = []
    for node_id, node_out in (result.get("outputs") or {}).items():
        for key in ("videos", "gifs", "images"):
            for item in node_out.get(key, []):
                fname = Path(item.get("filename", "")).name
                if not fname:
                    continue
                dst = outdir.resolve() / fname
                if dst.parent != outdir.resolve():
                    print(f"  [拒绝越界产物名] {fname!r}")
                    continue
                r = adapter._download_output(item, str(dst), POSITIVE)
                if r.get("success"):
                    saved.append(dst)
                    print(f"  ↓ {dst}")
    meta = {
        "prompt_id": pid, "frames": args.frames,
        "size": [args.width, args.height], "seed": args.seed,
        "steps": args.steps, "elapsed_s": round(time.time() - t0, 1),
        "vram_used_gb_peak_sampled": round(vram_peak, 2),
        "outputs": [str(s) for s in saved],
    }
    (outdir / "gen_meta.json").write_text(json.dumps(
        meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nmeta → {outdir / 'gen_meta.json'}")
    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())
