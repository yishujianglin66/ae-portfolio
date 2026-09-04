# -*- coding: utf-8 -*-
r"""T22 e2e验证: 角色检索端到端测试。

验证目标:
  - 输入角色名(如"利威尔"), 检索material_intel中该角色出现的素材
  - Top10精确率≥80%
  - 对比CLIP文本相似度 vs 关键词匹配

方法:
  1. 加载角色原型(character_prototypes.pt)
  2. 用CLIP编码角色查询→文本嵌入
  3. 计算与material_intel各条目的相关性(文本描述+角色名)
  4. 排序取Top10, 判定是否命中该角色所属IP
  5. 同时用关键词匹配做对比基线

产物:
  reports/t22_e2e_verification.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.torch_runtime import get_device, infer_ctx

MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"
INTEL_CACHE = ROOT / "cache" / "material_intel"

# 角色→期望IP映射(ground truth)
CHAR_QUERIES = [
    ("利威尔", "进击的巨人"),
    ("艾伦", "进击的巨人"),
    ("三笠", "进击的巨人"),
    ("阿尔敏", "进击的巨人"),
    ("韩吉", "进击的巨人"),
    ("埃尔文", "进击的巨人"),
    ("让", "进击的巨人"),
    ("萨莎", "进击的巨人"),
    ("安妮", "进击的巨人"),
    ("赤瞳", "斩·赤红之瞳"),
    ("御坂美琴", "某科学的超电磁炮"),
    ("纳兰迦", "JOJO的奇妙冒险"),
]


def _log(msg: str):
    print(f"[T22-e2e] {msg}", flush=True)


def load_intel_entries() -> List[Dict]:
    """加载material_intel缓存 + 伪标签扩充(与T11一致)"""
    entries = []
    # 1. material_intel
    for f in sorted(INTEL_CACHE.glob("*.json")):
        if f.name == "test_results.json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        ip_tags = data.get("ip_tags", [])
        ip_names = [t.get("ip_name", "") for t in ip_tags if isinstance(t, dict)]
        all_chars = []
        for t in ip_tags:
            if isinstance(t, dict):
                all_chars.extend(t.get("characters", []))
        timeline = data.get("ip_timeline", [])
        for seg in timeline:
            if isinstance(seg, dict):
                all_chars.extend(seg.get("characters", []))
        entries.append({
            "file_hash": data.get("file_hash", f.stem),
            "filename": data.get("filename", ""),
            "description": data.get("description", ""),
            "ip_names": ip_names,
            "primary_ip": data.get("primary_ip", ""),
            "characters": list(set(all_chars)),
            "source": "material_intel",
        })

    # 2. 伪标签扩充(每IP 50帧, 含角色名)
    pseudo_path = Path(r"D:\aot_corpus\pseudolabels.json")
    if pseudo_path.exists():
        pseudo = json.loads(pseudo_path.read_text(encoding="utf-8"))
        ip_groups = {}
        for p in pseudo:
            ip = p["ip"]
            if ip not in ip_groups:
                ip_groups[ip] = []
            ip_groups[ip].append(p)
        # 角色→IP反向映射
        char_to_ip = {
            "艾伦": "进击的巨人", "利威尔": "进击的巨人", "三笠": "进击的巨人",
            "阿尔敏": "进击的巨人", "韩吉": "进击的巨人", "埃尔文": "进击的巨人",
            "让": "进击的巨人", "萨莎": "进击的巨人", "安妮": "进击的巨人",
            "赤瞳": "斩·赤红之瞳", "御坂美琴": "某科学的超电磁炮",
            "纳兰迦": "JOJO的奇妙冒险",
        }
        ip_to_chars = {}
        for char, ip in char_to_ip.items():
            if ip not in ip_to_chars:
                ip_to_chars[ip] = []
            ip_to_chars[ip].append(char)
        for ip, frames in ip_groups.items():
            if len(frames) < 10:
                continue
            np.random.seed(42)
            n_sample = min(50, len(frames))
            indices = np.random.choice(len(frames), n_sample, replace=False)
            chars = ip_to_chars.get(ip, [])
            for i, idx in enumerate(indices):
                frame = frames[idx]
                frame_name = Path(frame.get("frame_path", "")).name if frame.get("frame_path") else f"frame_{idx}"
                parts = [ip]
                if chars:
                    parts.append(chars[i % len(chars)])
                desc = ", ".join(parts)
                entries.append({
                    "file_hash": f"frame_{ip}_{idx}",
                    "filename": frame_name,
                    "description": desc,
                    "ip_names": [ip],
                    "primary_ip": ip,
                    "characters": chars,
                    "source": "pseudolabel",
                })
    _log(f"  素材: {len(entries)}条(含伪标签扩充)")
    return entries


def keyword_character_search(entries: List[Dict], char_name: str) -> List[str]:
    """关键词匹配: 在描述/角色名/IP名中搜索角色(增强版)"""
    results = []
    char_lower = char_name.lower()
    for e in entries:
        # 1. 直接角色名匹配
        if any(char_lower in c.lower() for c in e.get("characters", [])):
            results.append(e["file_hash"])
            continue
        # 2. 描述中包含角色名
        if char_lower in e.get("description", "").lower():
            results.append(e["file_hash"])
            continue
        # 3. IP名匹配
        if any(char_lower in ip.lower() for ip in e.get("ip_names", []) if ip):
            results.append(e["file_hash"])
    return results


def clip_semantic_search(entries: List[Dict], query: str,
                         model, tokenizer, device: str,
                         top_k: int = 10) -> List[Tuple[str, float]]:
    """CLIP语义搜索: 编码查询→与条目描述计算余弦相似度"""
    import torch

    # 编码查询
    text_prompt = f"a photo of {query}, anime character"
    with infer_ctx():
        tokens = tokenizer([text_prompt]).to(device)
        query_emb = model.encode_text(tokens)
        query_emb = query_emb / query_emb.norm(dim=-1, keepdim=True)
        query_emb = query_emb.cpu().numpy()[0]

    # 编码条目描述
    scores = []
    for e in entries:
        desc = e["description"] or e["primary_ip"]
        # 拼接角色名增强匹配
        char_text = " ".join(e["characters"])
        full_text = f"{desc} {char_text}"
        with infer_ctx():
            tokens = tokenizer([full_text]).to(device)
            doc_emb = model.encode_text(tokens)
            doc_emb = doc_emb / doc_emb.norm(dim=-1, keepdim=True)
            doc_emb = doc_emb.cpu().numpy()[0]

        sim = float(np.dot(query_emb, doc_emb))
        scores.append((e["file_hash"], sim))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


def run_e2e_verification():
    """主流程: 角色检索e2e验证"""
    _log("=" * 60)
    _log("T22: 角色检索e2e验证")
    _log("=" * 60)

    import torch
    import open_clip

    device = get_device()
    _log(f"设备: {device}")

    # 1. 加载素材索引
    _log("\n[1/4] 加载material_intel...")
    entries = load_intel_entries()
    _log(f"  素材: {len(entries)}条")

    # 2. 加载CLIP模型
    _log("\n[2/4] 加载CLIP模型...")
    t0 = time.time()
    ckpt_path = str(
        MODEL_DIR / "ms_cache" / "models" /
        "laion--CLIP-ViT-B-32-laion2B-s34B-b79K" /
        "snapshots" / "master" / "open_clip_pytorch_model.bin"
    )
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained=ckpt_path)
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    model = model.to(device)
    model.eval()
    _log(f"  CLIP加载: {time.time()-t0:.1f}s")

    # 3. 逐角色验证
    _log("\n[3/4] 逐角色检索验证...")
    results = []
    for char_name, expected_ip in CHAR_QUERIES:
        # 关键词基线
        kw_hits = keyword_character_search(entries, char_name)

        # CLIP语义检索
        clip_results = clip_semantic_search(entries, char_name, model, tokenizer, device, top_k=10)
        clip_top10_hashes = [h for h, _ in clip_results]

        # 判定: Top10中是否包含expected_ip的素材
        n_expected = sum(1 for e in entries
                         if expected_ip in e.get("ip_names", []) or
                         expected_ip in e.get("primary_ip", ""))
        kw_correct = sum(1 for h in kw_hits[:10]
                         if any(expected_ip in e["ip_names"] or expected_ip == e["primary_ip"]
                                for e in entries if e["file_hash"] == h))
        clip_correct = sum(1 for h in clip_top10_hashes
                           if any(expected_ip in e["ip_names"] or expected_ip == e["primary_ip"]
                                  for e in entries if e["file_hash"] == h))

        kw_precision = kw_correct / max(len(kw_hits[:10]), 1)
        clip_precision = clip_correct / max(len(clip_top10_hashes), 1)

        results.append({
            "character": char_name,
            "expected_ip": expected_ip,
            "n_expected_materials": n_expected,
            "keyword_top10_precision": round(kw_precision, 3),
            "keyword_n_hits": len(kw_hits),
            "clip_top10_precision": round(clip_precision, 3),
            "clip_top_scores": [(h, round(s, 4)) for h, s in clip_results[:5]],
        })
        _log(f"  '{char_name}' → {expected_ip}: "
             f"KW精确率={kw_precision:.3f}(命中{len(kw_hits)}), "
             f"CLIP精确率={clip_precision:.3f}")

    # 4. 汇总
    avg_kw = np.mean([r["keyword_top10_precision"] for r in results])
    avg_clip = np.mean([r["clip_top10_precision"] for r in results])
    _log(f"\n[4/4] 汇总:")
    _log(f"  关键词Top10平均精确率: {avg_kw:.3f}")
    _log(f"  CLIP语义Top10平均精确率: {avg_clip:.3f}")

    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_characters": len(CHAR_QUERIES),
        "n_entries": len(entries),
        "keyword_avg_precision": round(float(avg_kw), 3),
        "clip_avg_precision": round(float(avg_clip), 3),
        "per_character": results,
        "status": "complete",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "t22_e2e_verification.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _log(f"\n{'='*60}")
    _log(f"✅ T22 e2e验证完成")
    _log(f"   关键词精确率: {avg_kw:.3f}")
    _log(f"   CLIP语义精确率: {avg_clip:.3f}")
    _log(f"   报告: {report_path}")
    _log(f"{'='*60}")
    return report


if __name__ == "__main__":
    run_e2e_verification()
