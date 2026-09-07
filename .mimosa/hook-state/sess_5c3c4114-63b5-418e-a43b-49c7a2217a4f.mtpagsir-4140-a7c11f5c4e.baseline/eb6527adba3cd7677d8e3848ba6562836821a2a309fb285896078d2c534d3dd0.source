#!/usr/bin/env python3
"""dev_scripts/download_weights_modelscope.py — ModelScope 权重批量下载

离线可达线路: modelscope.cn (GitHub/HuggingFace 本机不可达)
下载清单:
  1. AI-ModelScope/MuseTalk 全量 → external/musetalk/models/
  2. ZhipuAI/SCAIL-2 推理小件 → external/scail2/weights/
     (VAE + 文本编码器 + CLIP + LoRA, 约 15.5GB)
  3. ZhipuAI/SCAIL-2 主 DiT 权重 (62.5GB) → 需 --big 参数, 磁盘充足时执行

用法:
  python dev_scripts/download_weights_modelscope.py          # 下载 1+2
  python dev_scripts/download_weights_modelscope.py --big    # 追加下载 3
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modelscope.hub.snapshot_download import snapshot_download

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def step(name, fn):
    print("=" * 60)
    print(f"[{name}] 开始...")
    try:
        path = fn()
        print(f"[{name}] ✅ 完成 → {path}")
        return True
    except Exception as e:
        print(f"[{name}] ❌ 失败: {e}")
        return False

# 1. MuseTalk 全量
def dl_musetalk():
    return snapshot_download(
        "AI-ModelScope/MuseTalk",
        local_dir=os.path.join(ROOT, "external", "musetalk", "models", "musetalk_ms"),
    )

# 2. SCAIL-2 小件 (排除 62.5GB 训练 checkpoint)
def dl_scail2_small():
    return snapshot_download(
        "ZhipuAI/SCAIL-2",
        local_dir=os.path.join(ROOT, "external", "scail2", "weights"),
        ignore_file_pattern=[
            "model/1/*",                                    # 62.5GB 训练 checkpoint
            "model/bias-aware-dpo-lora.pt",                 # 与 relighting-lora 重复
        ],
    )

# 3. SCAIL-2 主 DiT 权重 (需磁盘 >70GB 空闲)
def dl_scail2_big():
    return snapshot_download(
        "ZhipuAI/SCAIL-2",
        local_dir=os.path.join(ROOT, "external", "scail2", "weights"),
        allow_file_pattern=["model/1/*"],
    )

if __name__ == "__main__":
    results = {}
    results["musetalk"] = step("MuseTalk 6.3GB", dl_musetalk)
    results["scail2_small"] = step("SCAIL-2 小件 ~15.5GB", dl_scail2_small)
    if "--big" in sys.argv:
        results["scail2_big"] = step("SCAIL-2 主权重 62.5GB", dl_scail2_big)
    print("=" * 60)
    print("汇总:", results)
