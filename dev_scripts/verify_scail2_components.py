# -*- coding: utf-8 -*-
"""SCAIL-2 组件加载验证 + 显存边界记录（RTX 4060 Laptop 8GB）。

逐组件真实加载 + 真实前向：
  1. WanVAE   (GPU fp32) : 合成视频 encode→decode，校验重建误差
  2. CLIPModel(GPU fp16) : 合成帧过 visual 编码器，校验输出形状
  3. T5Encoder(CPU bf16) : 权重 10.8GB > 8GB 显存 → CPU 加载 + 短序列前向
  4. DiT 14B  : 权重 62.5GB 未下载，按 config 估算显存边界

flash_attn 本机未安装 → 补丁为 PyTorch sdpa 回退。
用法：python ../../dev_scripts/verify_scail2_components.py
"""
import gc
import json
import os
import sys
import time

import torch

from core.torch_runtime import get_device, infer_ctx

S2_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "external", "scail2"))
sys.path.insert(0, S2_ROOT)
os.chdir(S2_ROOT)

WEIGHTS = os.path.join(S2_ROOT, "weights")
VAE_PTH = os.path.join(WEIGHTS, "Wan2.1_VAE.pth")
CLIP_PTH = os.path.join(WEIGHTS, "models_clip_open-clip-xlm-roberta-large-vit-huge-14-onlyvisual.pth")
T5_PTH = os.path.join(WEIGHTS, "umt5-xxl", "models_t5_umt5-xxl-enc-bf16.pth")
T5_TOK = os.path.join(WEIGHTS, "umt5-xxl")

import wan.modules.attention as attn_mod  # noqa: E402
import wan.modules.clip as clip_mod  # noqa: E402


def _sdpa_flash(q, k, v, q_lens=None, k_lens=None, dropout_p=0.,
                softmax_scale=None, q_scale=None, causal=False,
                window_size=(-1, -1), deterministic=False,
                dtype=torch.bfloat16, version=None):
    """flash_attn 不可用时的回退：走 attention() 的 sdpa 分支，并还原输入 dtype。"""
    out = attn_mod.attention(
        q, k, v, dropout_p=dropout_p, softmax_scale=softmax_scale,
        q_scale=q_scale, causal=causal, window_size=window_size, dtype=dtype)
    return out.to(q.dtype)


def free_gpu():
    gc.collect()
    torch.cuda.empty_cache()


def verify_vae(device):
    from wan.modules.vae import WanVAE
    torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    vae = WanVAE(vae_pth=VAE_PTH, device=device)
    # 合成视频 [C,T,H,W]，范围 [-1,1]
    video = torch.rand(3, 5, 256, 256, device=device) * 2 - 1
    z = vae.encode([video])[0]
    recon = vae.decode([z])[0]
    mse = (recon - video).pow(2).mean().item()
    peak = torch.cuda.max_memory_allocated() / 1024**2
    print(f"[VAE] 加载+前向 = {time.time() - t0:.1f}s, latent={tuple(z.shape)}, "
          f"重建MSE={mse:.4f}, 显存峰值={peak:.0f} MiB")
    assert z.shape[0] == 16 and mse < 1.0, "VAE latent/MSE 异常"
    del vae, video, z, recon
    free_gpu()
    return peak


def verify_clip(device):
    from wan.configs.scail_config_14B import scail_14B
    from wan.modules.clip import CLIPModel
    torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    clip = CLIPModel(
        dtype=scail_14B.clip_dtype, device=device,
        checkpoint_path=CLIP_PTH, tokenizer_path=None)
    frames = torch.rand(3, 1, 224, 224, device=device) * 2 - 1  # [C,T,H,W]
    out = clip.visual([frames])
    peak = torch.cuda.max_memory_allocated() / 1024**2
    print(f"[CLIP] 加载+前向 = {time.time() - t0:.1f}s, 视觉特征={tuple(out.shape)}, "
          f"显存峰值={peak:.0f} MiB")
    assert out.shape[-1] == 1280, f"CLIP 特征维度异常: {out.shape}"
    del clip, frames, out
    free_gpu()
    return peak


def verify_t5():
    from wan.modules.t5 import T5EncoderModel
    size_gb = os.path.getsize(T5_PTH) / 1024**3
    t0 = time.time()
    # 官方流水线即支持 t5_cpu=True；bf16 权重 10.8GB 超 8GB 显存，必须 CPU 驻留
    t5 = T5EncoderModel(
        text_len=512, dtype=torch.bfloat16, device=torch.device("cpu"),
        checkpoint_path=T5_PTH, tokenizer_path=T5_TOK)
    ids, mask = t5.tokenizer(["a girl dancing on stage"], return_mask=True)
    ids, mask = ids[:, :64], mask[:, :64]  # 截短序列加速 CPU 前向
    with infer_ctx("cpu"):
        ctx = t5.model(ids, mask)
    print(f"[T5] CPU 加载+前向 = {time.time() - t0:.1f}s, 权重={size_gb:.1f}GB(bf16), "
          f"context={tuple(ctx.shape)}, dtype={ctx.dtype}")
    assert ctx.shape[:2] == (1, 64) and torch.isfinite(ctx).all(), "T5 输出异常"
    del t5, ctx
    gc.collect()
    return size_gb


def dit_boundary():
    cfg = json.load(open(os.path.join(S2_ROOT, "configs", "config-14b.json")))
    dim, ffn, layers, heads = cfg["dim"], cfg["ffn_dim"], cfg["num_layers"], cfg["num_heads"]
    # 粗估：每层 self-attn(4d²) + cross-attn(6d²) + ffn(2·d·ffn)
    per_layer = 10 * dim * dim + 2 * dim * ffn
    total = per_layer * layers
    bf16_gb = total * 2 / 1024**3
    print(f"[DiT-14B] config: dim={dim}, layers={layers}, heads={heads}, ffn={ffn}")
    print(f"[DiT-14B] 参数估算 ≈ {total / 1e9:.1f}B, bf16 权重 ≈ {bf16_gb:.1f} GB")
    print("[DiT-14B] 边界: 权重文件 62.5GB 未下载(网络/磁盘限制)；"
          "即使有也远超 8GB 显存 -> 完整推理需多卡/分片或 1.3B 蒸馏权重")


def run():
    device = torch.device(get_device())
    assert device.type == "cuda", "未检测到 CUDA"
    print(f"device = {device} ({torch.cuda.get_device_name(0)}, "
          f"总显存 {torch.cuda.get_device_properties(0).total_memory / 1024**2:.0f} MiB)")
    # flash_attn 缺失 → sdpa 回退补丁
    clip_mod.flash_attention = _sdpa_flash

    vae_peak = verify_vae(device)
    clip_peak = verify_clip(device)
    t5_gb = verify_t5()
    dit_boundary()

    print("\n===== 显存边界汇总（单卡 8GB）=====")
    print(f"  WanVAE   : {vae_peak:.0f} MiB [OK] GPU 可驻留")
    print(f"  CLIP     : {clip_peak:.0f} MiB [OK] GPU 可驻留")
    print(f"  T5(bf16) : 权重 {t5_gb:.1f} GB > 8 GB -> 必须 t5_cpu=True 或分片")
    print("  DiT-14B  : 权重缺失且 >8GB 显存 -> 完整推理不可行（已记录边界）")
    assert vae_peak < 8 * 1024 and clip_peak < 8 * 1024, "组件显存峰值超 8GB"
    print("VERIFY OK")


if __name__ == "__main__":
    run()
