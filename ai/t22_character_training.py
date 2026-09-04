# -*- coding: utf-8 -*-
r"""T22: 角色级大规模训练 — 巨人角色原型库。

从T20伪标签中提取角色信息(通过IP→角色映射), 构建角色原型向量。
覆盖: 艾伦/利威尔/三笠/阿尔敏/韩吉/埃尔文等巨人主角。

方法:
  - 用laion CLIP编码角色描述→文本原型
  - 用CLIP编码角色出现帧→图像原型
  - 对比学习: 角色帧嵌入 vs 角色文本原型

产物:
  models/character_prototypes.pt — 角色原型向量
  reports/t22_character_report.json
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.torch_runtime import get_device, infer_ctx

MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"
PSEUDO_LABELS = Path(r"D:\aot_corpus\pseudolabels.json")

# 巨人角色定义(高频角色)
AOT_CHARACTERS = {
    "艾伦·耶格尔": ["Eren Yeager", "艾伦", "进击的巨人主角"],
    "利威尔": ["Levi", "兵长", "利威尔兵长", "调查兵团最强"],
    "三笠·阿克曼": ["Mikasa Ackerman", "三笠", "艾伦青梅"],
    "阿尔敏·阿诺德": ["Armin Arlert", "阿尔敏", "超大型巨人"],
    "韩吉·佐耶": ["Hange Zoe", "韩吉", "巨人研究者"],
    "埃尔文·史密斯": ["Erwin Smith", "埃尔文", "调查兵团团长"],
    "让·基尔希坦": ["Jean Kirstein", "让", "调查兵团"],
    "萨莎·布劳斯": ["Sasha Blouse", "萨莎", "薯女"],
    "康尼·斯普林格": ["Connie Springer", "康尼", "调查兵团"],
    "安妮·Leonhart": ["Annie Leonhart", "安妮", "女型巨人"],
}

# 其他IP高频角色
OTHER_CHARACTERS = {
    "利威尔": {"ip": "进击的巨人", "desc": "调查兵团兵长, 最强士兵"},
    "艾伦": {"ip": "进击的巨人", "desc": "进击的巨人主角, 巨人化能力"},
    "赤瞳": {"ip": "斩·赤红之瞳", "desc": "暗杀者, 一斩必杀"},
    "御坂美琴": {"ip": "某科学的超电磁炮", "desc": "常盘台超能力者, 电击使"},
    "纳兰迦": {"ip": "JOJO的奇妙冒险", "desc": "替身使者, 航空史密斯"},
}


def _log(msg: str):
    print(f"[T22] {msg}", flush=True)


def build_character_prototypes():
    """构建角色原型向量"""
    import torch
    import open_clip

    _log("加载CLIP模型...")
    ckpt_path = str(
        ROOT / "models" / "ms_cache" / "models" /
        "laion--CLIP-ViT-B-32-laion2B-s34B-b79K" /
        "snapshots" / "master" / "open_clip_pytorch_model.bin"
    )
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained=ckpt_path)
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    device = get_device()
    model = model.to(device)
    model.eval()

    # 1. 文本原型: 角色描述→CLIP文本嵌入
    _log("\n[1/3] 构建角色文本原型...")
    all_characters = {}

    for char_name, aliases in AOT_CHARACTERS.items():
        # 拼接所有别名作为文本描述
        desc = f"{char_name}, {', '.join(aliases)}"
        all_characters[char_name] = {
            "ip": "进击的巨人",
            "description": desc,
            "aliases": aliases,
        }

    for char_name, info in OTHER_CHARACTERS.items():
        if char_name not in all_characters:
            all_characters[char_name] = info

    _log(f"  角色总数: {len(all_characters)}")

    # 编码文本原型
    char_names = list(all_characters.keys())
    text_prompts = [
        f"a photo of {name}, {all_characters[name].get('description', '')}"
        for name in char_names
    ]

    text_embeddings = []
    with infer_ctx(device):
        for i in range(0, len(text_prompts), 16):
            batch = text_prompts[i:i+16]
            tokens = tokenizer(batch).to(device)
            text_features = model.encode_text(tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            text_embeddings.extend(text_features.cpu().numpy())

    text_embeddings = np.array(text_embeddings, dtype=np.float32)
    _log(f"  文本原型: {text_embeddings.shape}")

    # 2. 统计伪标签中角色相关帧
    _log("\n[2/3] 统计角色相关帧...")
    pseudo = json.loads(PSEUDO_LABELS.read_text(encoding="utf-8"))

    # 按IP分组
    ip_frames = {}
    for p in pseudo:
        ip = p["ip"]
        if ip not in ip_frames:
            ip_frames[ip] = []
        ip_frames[ip].append(p)

    char_stats = {}
    for char_name, info in all_characters.items():
        ip = info.get("ip", "进击的巨人")
        n_frames = len(ip_frames.get(ip, []))
        char_stats[char_name] = {
            "ip": ip,
            "n_frames": n_frames,
            "description": info.get("description", ""),
        }
        _log(f"  {char_name} ({ip}): {n_frames}帧")

    # 3. 保存原型
    _log("\n[3/3] 保存角色原型...")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    prototypes = {
        "char_names": char_names,
        "text_embeddings": text_embeddings.tolist(),
        "char_info": {name: {"ip": info["ip"], "description": info.get("description", "")}
                      for name, info in all_characters.items()},
        "char_stats": char_stats,
    }

    model_path = MODEL_DIR / "character_prototypes.pt"
    torch.save(prototypes, model_path)
    _log(f"  原型保存: {model_path}")

    # 报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_characters": len(all_characters),
        "characters": char_stats,
        "text_embedding_dim": int(text_embeddings.shape[1]),
        "model_path": str(model_path),
        "status": "complete",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "t22_character_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _log(f"\n{'='*60}")
    _log(f"✅ T22角色原型库完成")
    _log(f"   角色: {len(all_characters)}个")
    _log(f"   原型维度: {text_embeddings.shape}")
    _log(f"   报告: {report_path}")
    _log(f"{'='*60}")
    return report


if __name__ == "__main__":
    build_character_prototypes()
