# -*- coding: utf-8 -*-
r"""T32: 均衡采样LoRA重训 — 解决单IP数据失衡问题。

核心改进(vs t23b):
  1. 均衡采样: 每个IP最多取 max_per_ip 帧, 防止单IP过拟合
  2. 多源合并: 支持 AoT伪标签 + VLM标注 + 多IP语料 合并
  3. WeightedRandomSampler: DataLoader按IP权重采样, 每batch IP分布均匀
  4. 场景感知对比学习: 用VLM的scene_type增强文本描述, 提升场景区分力
  5. 自动检测: 如果多IP数据可用则使用, 否则回退到AoT数据+均衡采样

数据源优先级:
  1. D:\multi_ip_corpus\merged_vlm.jsonl (多IP合并, 最优)
  2. D:\aot_corpus\vlm_full\results.jsonl (VLM全量标注, 单IP)
  3. D:\aot_corpus\pseudolabels.json (伪标签, 兜底)

用法:
  # 预览数据分布(不训练)
  python -m ai.t32_balanced_lora_retrain --dry-run

  # 启动训练(建议独立进程)
  python -m ai.t32_balanced_lora_retrain --train

  # 独立进程启动(防IDE关闭中断)
  python -m ai.t32_balanced_lora_retrain --launch

产物:
  models/clip_lora_balanced_v1.pt — 均衡采样LoRA权重
  reports/t32_balanced_retrain_report.json — 训练报告
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 数据源路径
MERGED_VLM = Path(r"D:\multi_ip_corpus\merged_vlm.jsonl")
VLM_FULL = Path(r"D:\aot_corpus\vlm_full\results.jsonl")
PSEUDO_LABELS = Path(r"D:\aot_corpus\pseudolabels.json")
TEACHER_LABELS = ROOT / "data" / "training" / "labels.json"
GOLDEN_V2 = ROOT / "data" / "benchmark_golden_v2.json"

MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"

# 超参
LORA_RANK = 16
LORA_ALPHA = 32
EPOCHS = 25          # 均衡数据后需更多轮
LR = 2e-5
BATCH_SIZE = 4       # ViT-L-14显存约束(OOM修复: 16→8→4)
GRAD_ACCUM = 4       # 梯度累积步数(等效batch=16)
TEMPERATURE = 0.07
IMG_SIZE = 224
MAX_PER_IP = 3000    # 每IP最多帧数(防过拟合)
MIN_PER_IP = 50      # 每IP最少帧数(太低不可靠)


def _log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[T32 {ts}] {msg}", flush=True)


# ── 数据加载(多源合并) ────────────────────────────────────

def load_merged_vlm(golden_videos: set) -> List[dict]:
    """从多IP合并VLM数据加载"""
    entries = []
    if not MERGED_VLM.exists():
        return entries
    with open(MERGED_VLM, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                fp = rec.get("frame_path", rec.get("path", ""))
                ip = rec.get("source_ip", rec.get("vlm_ip", rec.get("ip", "")))
                scene = rec.get("scene_type", "")
                mood = rec.get("mood", "")
                if fp and ip and Path(fp).exists():
                    # 排除黄金集
                    fname = Path(fp).name
                    vid = Path(fp).parent.parent.name
                    if fname not in golden_videos and vid not in golden_videos:
                        entries.append({
                            "frame_path": fp, "ip": ip,
                            "scene_type": scene, "mood": mood,
                            "source": "merged_vlm",
                        })
            except (json.JSONDecodeError, KeyError):
                pass
    _log(f"多IP合并VLM: {len(entries)}帧")
    return entries


def load_vlm_full(golden_videos: set) -> List[dict]:
    """从AoT VLM全量标注加载"""
    entries = []
    if not VLM_FULL.exists():
        return entries
    with open(VLM_FULL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                fp = rec.get("frame_path", "")
                ip = rec.get("vlm_ip", rec.get("ip", ""))
                scene = rec.get("scene_type", "")
                mood = rec.get("mood", "")
                if fp and ip and Path(fp).exists():
                    fname = Path(fp).name
                    vid = Path(fp).parent.parent.name
                    if fname not in golden_videos and vid not in golden_videos:
                        entries.append({
                            "frame_path": fp, "ip": ip,
                            "scene_type": scene, "mood": mood,
                            "source": "vlm_full",
                        })
            except (json.JSONDecodeError, KeyError):
                pass
    _log(f"AoT VLM全量: {len(entries)}帧")
    return entries


def load_pseudolabels(golden_videos: set) -> List[dict]:
    """从伪标签加载(兜底)"""
    entries = []
    if not PSEUDO_LABELS.exists():
        return entries
    pseudo = json.loads(PSEUDO_LABELS.read_text(encoding="utf-8"))
    for p in pseudo:
        if p.get("confidence", 0) >= 0.5:
            fp = p.get("frame_path", "")
            ip = p.get("ip", "")
            if fp and ip and Path(fp).exists():
                fname = Path(fp).name
                vid = Path(fp).parent.parent.name
                if fname not in golden_videos and vid not in golden_videos:
                    entries.append({
                        "frame_path": fp, "ip": ip,
                        "scene_type": "", "mood": "",
                        "source": "pseudolabel",
                    })
    _log(f"伪标签: {len(entries)}帧")
    return entries


def load_teacher(golden_videos: set) -> List[dict]:
    """加载教师标签数据"""
    entries = []
    if not TEACHER_LABELS.exists():
        return entries
    teacher = json.loads(TEACHER_LABELS.read_text(encoding="utf-8"))
    for t in teacher:
        fp = t.get("path", "")
        ip = t.get("ip", "")
        if fp and ip and Path(fp).exists():
            fname = Path(fp).name
            vid = Path(fp).parent.name
            if fname not in golden_videos and vid not in golden_videos:
                entries.append({
                    "frame_path": fp, "ip": ip,
                    "scene_type": "", "mood": "",
                    "source": "teacher",
                })
    _log(f"教师数据: {len(entries)}帧")
    return entries


def balanced_sample(entries: List[dict], max_per_ip: int = MAX_PER_IP,
                    min_per_ip: int = MIN_PER_IP) -> List[dict]:
    """均衡采样: 每个IP最多取max_per_ip帧, 低于min_per_ip的IP丢弃。

    采样策略: 如果某IP帧数 > max_per_ip, 随机下采样到max_per_ip。
    这确保了没有任何一个IP主导训练。
    """
    ip_groups = defaultdict(list)
    for e in entries:
        ip_groups[e["ip"]].append(e)

    # 过滤低帧数IP
    valid_ips = {ip for ip, group in ip_groups.items() if len(group) >= min_per_ip}
    _log(f"IP过滤: {len(ip_groups)}→{len(valid_ips)} (min={min_per_ip}帧)")

    sampled = []
    for ip in sorted(valid_ips):
        group = ip_groups[ip]
        if len(group) > max_per_ip:
            random.seed(42)
            group = random.sample(group, max_per_ip)
        sampled.extend(group)

    # 统计
    ip_counts = Counter(e["ip"] for e in sampled)
    _log(f"均衡采样: {len(entries)}→{len(sampled)}帧")
    _log(f"  IP分布: {len(ip_counts)}个IP, "
         f"min={min(ip_counts.values())}, max={max(ip_counts.values())}, "
         f"mean={np.mean(list(ip_counts.values())):.0f}")
    top5 = ip_counts.most_common(5)
    for ip, cnt in top5:
        _log(f"    {ip}: {cnt}帧 ({100*cnt/len(sampled):.1f}%)")

    return sampled


# ── 数据集 ────────────────────────────────────────────────

class BalancedContrastiveDataset(Dataset):
    """均衡对比学习数据集: 支持场景感知文本增强"""

    def __init__(self, entries: List[dict], ip2idx: Dict[str, int],
                 transform=None, scene_enhance: bool = True):
        self.entries = entries
        self.ip2idx = ip2idx
        self.transform = transform
        self.scene_enhance = scene_enhance

    def __len__(self):
        return len(self.entries)

    def __getitem__(self, idx):
        entry = self.entries[idx]
        from PIL import Image
        try:
            img = Image.open(entry["frame_path"]).convert("RGB")
        except Exception:
            img = Image.new("RGB", (IMG_SIZE, IMG_SIZE), (128, 128, 128))
        if self.transform:
            img = self.transform(img)
        label = self.ip2idx[entry["ip"]]
        return img, label


def build_text_embeds_with_scene(class_names: List[str], entries: List[dict],
                                 ip2idx: Dict[str, int],
                                 clip_model, tokenizer, device: str) -> np.ndarray:
    """构建文本嵌入: 用VLM场景/情绪信息增强IP描述。

    对有VLM数据的IP: "a {scene} scene of {ip}, {mood} mood"
    对无VLM数据的IP: "a promotional image of {ip}" (原始模板)
    """
    # 获取正确的文本tokenizer (open_clip返回的tokenizer可能是图像transform)
    import open_clip as _oc
    try:
        text_tokenizer = _oc.get_tokenizer("ViT-L-14")
    except Exception:
        text_tokenizer = tokenizer  # fallback
    
    # 统计每个IP的主要场景和情绪
    ip_scenes = defaultdict(list)
    ip_moods = defaultdict(list)
    for e in entries:
        if e.get("scene_type"):
            ip_scenes[e["ip"]].append(e["scene_type"])
        if e.get("mood"):
            ip_moods[e["ip"]].append(e["mood"])

    text_embeds = np.zeros((len(class_names), 768), dtype=np.float32)  # ViT-L-14 = 768dim
    clip_model.eval()

    with torch.no_grad():
        for i, ip_name in enumerate(class_names):
            # 场景感知文本增强
            scenes = Counter(ip_scenes.get(ip_name, []))
            moods = Counter(ip_moods.get(ip_name, []))

            if scenes and moods:
                top_scene = scenes.most_common(1)[0][0]
                top_mood = moods.most_common(1)[0][0]
                text = f"a {top_scene} scene of {ip_name}, {top_mood} mood"
            else:
                text = f"a promotional image of {ip_name}"

            tokens = text_tokenizer([text]).to(device)
            features = clip_model.encode_text(tokens)
            text_embeds[i] = features.cpu().numpy()[0]

    _log(f"文本嵌入: {text_embeds.shape}, 场景增强{sum(1 for ip in class_names if ip_scenes.get(ip))}个IP")
    return text_embeds


# ── 训练 ──────────────────────────────────────────────────

def train_balanced_lora(clip_model, lora_model, train_loader,
                        text_embeds: np.ndarray, device: str):
    """训练LoRA (均衡采样版)"""
    import torch.optim as optim

    optimizer = optim.AdamW(
        [p for p in lora_model.parameters() if p.requires_grad],
        lr=LR, weight_decay=1e-4
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    # 冻结CLIP
    for p in clip_model.parameters():
        p.requires_grad = False
    for name, p in lora_model.named_parameters():
        if "lora_" in name:
            p.requires_grad = True

    history = []
    best_loss = float("inf")

    for epoch in range(EPOCHS):
        lora_model.train()
        epoch_loss = 0.0
        n_batches = 0
        t0 = time.time()

        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)

            with torch.autocast(device, dtype=torch.float16):
                img_features = lora_model(images)
                if isinstance(img_features, tuple):
                    img_features = img_features[0]
                batch_text = torch.from_numpy(
                    text_embeds[labels.cpu().numpy()]
                ).float().to(device)
                loss = F.cross_entropy(
                    (F.normalize(img_features, dim=-1) @
                     F.normalize(batch_text, dim=-1).T) / TEMPERATURE,
                    torch.arange(len(img_features), device=device)
                )
                loss = loss / GRAD_ACCUM  # 梯度累积缩放

            loss.backward()

            if (n_batches + 1) % GRAD_ACCUM == 0 or (n_batches + 1) == len(train_loader):
                optimizer.step()
                optimizer.zero_grad()

            epoch_loss += loss.item() * GRAD_ACCUM
            n_batches += 1

            if n_batches % 100 == 0:
                eta = (time.time() - t0) / n_batches * (len(train_loader) - n_batches)
                _log(f"  [E{epoch+1}] batch {n_batches}/{len(train_loader)} | "
                     f"loss={loss.item()*GRAD_ACCUM:.4f} | ETA {eta/60:.0f}min")

        scheduler.step()
        avg_loss = epoch_loss / max(n_batches, 1)
        history.append({"epoch": epoch + 1, "loss": round(avg_loss, 4),
                        "lr": round(scheduler.get_last_lr()[0], 8)})
        elapsed = time.time() - t0
        _log(f"  Epoch {epoch+1}/{EPOCHS} | loss={avg_loss:.4f} | {elapsed/60:.1f}min")

        if avg_loss < best_loss:
            best_loss = avg_loss
            _log(f"  ★ 新最佳loss, 保存中间权重")
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            torch.save({
                "lora_state": lora_model.state_dict(),
                "config": {"rank": LORA_RANK, "alpha": LORA_ALPHA},
            }, MODEL_DIR / "clip_lora_balanced_best.pt")

    return history


# ── 主流程 ────────────────────────────────────────────────

def dry_run():
    """预览数据分布(不训练)"""
    _log("=" * 60)
    _log("T32: 均衡采样LoRA重训 — 数据分布预览")
    _log("=" * 60)

    golden_videos = set()
    if GOLDEN_V2.exists():
        golden = json.loads(GOLDEN_V2.read_text(encoding="utf-8"))
        if isinstance(golden, dict):
            golden_videos = set(golden.keys())

    # 按优先级加载数据
    entries = load_merged_vlm(golden_videos)
    if not entries:
        _log("多IP合并数据不可用, 回退到VLM全量...")
        entries = load_vlm_full(golden_videos)
    if not entries:
        _log("VLM数据不可用, 回退到伪标签...")
        entries = load_pseudolabels(golden_videos)
    entries.extend(load_teacher(golden_videos))

    _log(f"\n原始数据: {len(entries)}帧")
    raw_counts = Counter(e["ip"] for e in entries)
    _log(f"  IP数: {len(raw_counts)}")
    _log(f"  Top5: {raw_counts.most_common(5)}")

    # 均衡采样
    _log(f"\n均衡采样(max_per_ip={MAX_PER_IP}):")
    sampled = balanced_sample(entries)

    # 场景分布
    scene_counts = Counter(e.get("scene_type", "") for e in sampled if e.get("scene_type"))
    if scene_counts:
        _log(f"\n场景分布:")
        for scene, cnt in scene_counts.most_common():
            _log(f"  {scene}: {cnt} ({100*cnt/len(sampled):.1f}%)")

    _log(f"\n数据源: {Counter(e['source'] for e in sampled)}")
    _log("预览完成, 使用 --train 启动训练")


def main_train():
    """主训练流程"""
    _log("=" * 60)
    _log("T32: 均衡采样LoRA重训")
    _log("=" * 60)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    _log(f"设备: {device}")
    if device != "cuda":
        _log("WARNING: 无GPU, 训练将极慢")
        return

    # 1. 加载CLIP
    _log("\n[1/6] 加载CLIP ViT-L-14...")
    import open_clip
    t0 = time.time()
    clip_model, preprocess, tokenizer = open_clip.create_model_and_transforms(
        "ViT-L-14", pretrained="openai")
    clip_model = clip_model.to(device)
    _log(f"  CLIP加载: {time.time()-t0:.1f}s")

    # 2. 加载数据
    _log("\n[2/6] 加载多源数据...")
    golden_videos = set()
    if GOLDEN_V2.exists():
        golden = json.loads(GOLDEN_V2.read_text(encoding="utf-8"))
        if isinstance(golden, dict):
            golden_videos = set(golden.keys())
        elif isinstance(golden, list):
            golden_videos = set(g.get("video", g.get("filename", "")) for g in golden)

    entries = load_merged_vlm(golden_videos)
    source_used = "merged_vlm"
    if not entries:
        entries = load_vlm_full(golden_videos)
        source_used = "vlm_full"
    if not entries:
        entries = load_pseudolabels(golden_videos)
        source_used = "pseudolabel"
    entries.extend(load_teacher(golden_videos))
    _log(f"  数据源: {source_used}, 总帧数: {len(entries)}")

    # 3. 均衡采样
    _log("\n[3/6] 均衡采样...")
    sampled = balanced_sample(entries)
    ip_counter = Counter(e["ip"] for e in sampled)
    valid_ips = sorted(ip for ip, cnt in ip_counter.items() if cnt >= MIN_PER_IP)
    ip2idx = {ip: i for i, ip in enumerate(valid_ips)}
    filtered = [e for e in sampled if e["ip"] in ip2idx]
    _log(f"  训练样本: {len(filtered)}, IP类: {len(valid_ips)}")

    # 4. 构建数据集
    _log("\n[4/6] 构建数据集...")
    from torchvision import transforms
    transform_train = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(0.1, 0.1, 0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])

    dataset = BalancedContrastiveDataset(filtered, ip2idx, transform_train)

    # WeightedRandomSampler: 确保每batch IP分布均匀
    sample_weights = []
    ip_sample_count = Counter(e["ip"] for e in filtered)
    for e in filtered:
        w = 1.0 / ip_sample_count[e["ip"]]
        sample_weights.append(w)
    sampler = WeightedRandomSampler(sample_weights, num_samples=len(filtered),
                                    replacement=True)

    train_loader = DataLoader(dataset, batch_size=BATCH_SIZE, sampler=sampler,
                              num_workers=0, pin_memory=True)
    _log(f"  Dataset: {len(dataset)}样本, WeightedRandomSampler启用")

    # 5. 文本嵌入(场景增强)
    _log("\n[5/6] 构建场景增强文本嵌入...")
    text_embeds = build_text_embeds_with_scene(
        valid_ips, filtered, ip2idx, clip_model, tokenizer, device)

    # 6. LoRA训练
    _log("\n[6/6] 添加LoRA并训练...")
    from peft import LoraConfig, get_peft_model
    lora_config = LoraConfig(
        r=LORA_RANK, lora_alpha=LORA_ALPHA,
        target_modules=["out_proj", "c_fc", "c_proj"],
        lora_dropout=0.1, bias="none",
    )
    lora_model = get_peft_model(clip_model.visual, lora_config)
    lora_model = lora_model.to(device)
    n_trainable = sum(p.numel() for p in lora_model.parameters() if p.requires_grad)
    n_total = sum(p.numel() for p in lora_model.parameters())
    _log(f"  LoRA: {n_trainable/1e6:.2f}M / {n_total/1e6:.1f}M ({100*n_trainable/n_total:.2f}%)")

    t0 = time.time()
    history = train_balanced_lora(clip_model, lora_model, train_loader,
                                  text_embeds, device)
    _log(f"  训练耗时: {time.time()-t0:.1f}s ({(time.time()-t0)/3600:.1f}h)")

    # 保存
    _log("\n保存模型...")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "clip_lora_balanced_v1.pt"
    torch.save({
        "lora_state": lora_model.state_dict(),
        "class_names": valid_ips,
        "ip2idx": ip2idx,
        "config": {
            "rank": LORA_RANK, "alpha": LORA_ALPHA,
            "epochs": EPOCHS, "max_per_ip": MAX_PER_IP,
            "data_source": source_used,
            "n_samples": len(filtered),
            "n_ips": len(valid_ips),
        },
    }, model_path)
    _log(f"  模型: {model_path} ({model_path.stat().st_size/1e6:.1f}MB)")

    # 报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": source_used,
        "n_samples": len(filtered),
        "n_ips": len(valid_ips),
        "ip_distribution": dict(ip_counter.most_common()),
        "max_per_ip": MAX_PER_IP,
        "epochs": EPOCHS,
        "final_loss": history[-1]["loss"] if history else 0,
        "history": history,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "t32_balanced_retrain_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"  报告: {report_path}")
    _log("训练完成!")


def launch_independent():
    """以独立进程启动训练(防IDE关闭中断)"""
    bat_path = ROOT / "scripts" / "run_t32_balanced_lora.bat"
    log_path = ROOT / "logs" / "t32_balanced_lora.log"
    bat_path.parent.mkdir(parents=True, exist_ok=True)

    bat_content = f"""@echo off
cd /d {ROOT}
echo [%date% %time%] T32 balanced LoRA retrain started >> "{log_path}"
{sys.executable} -m ai.t32_balanced_lora_retrain --train >> "{log_path}" 2>&1
echo [%date% %time%] T32 exited with code %errorlevel% >> "{log_path}"
"""
    bat_path.write_text(bat_content, encoding="utf-8")
    _log(f"启动脚本: {bat_path}")
    _log(f"日志: {log_path}")

    import subprocess
    subprocess.Popen(
        ["powershell", "-Command",
         f"Start-Process -FilePath '{bat_path}' -WindowStyle Minimized"],
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    _log("训练已后台启动, 关闭IDE不会中断")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="预览数据分布")
    ap.add_argument("--train", action="store_true", help="启动训练")
    ap.add_argument("--launch", action="store_true", help="独立进程启动")
    args = ap.parse_args()

    if args.dry_run:
        dry_run()
    elif args.launch:
        launch_independent()
    elif args.train:
        main_train()
    else:
        dry_run()
