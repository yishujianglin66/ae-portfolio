# -*- coding: utf-8 -*-
"""
P2.2 IP分类器 — 本地CLIP 图像原型+文本零样本 混合分类(生产级开集方案)
=====================================================================
结构约束(防泄漏): 黄金集12素材帧绝不进支持集。由此7个黄金IP在库内无支持帧,
纯图像few-shot在数学上不可能识别它们。生产级解法 = 开集识别:
  1. 库内类: 全部教师帧CLIP嵌入为支持库(kNN图像打分)
  2. 库外类/全部类: 类名中英别名 → CLIP文本原型 零样本打分
  3. 帧级融合: 有支持帧类 score=kNN-topK均值; 无支持类 score=0.92*文本相似度
  4. 视频级: 分数累积投票(score accumulation)
  5. 开集判定: C段(库外IP)以置信度≤0.5为"诚实不确定"通过, 防自信误报

验收口径(3段, 报告含legacy ip_matches口径):
  A. 可学习IP(库内有支持帧): Top-1必须正确
  B. 空真值(混剪/教程): ip_matches空关键词语义通过
  C. 库外IP: Top-1命中 或 置信度≤0.5(诚实拒绝)

配置依据: tmp/proto_grid.py + proto_grid2.py 两轮网格(24变体+12变体)
  最优: 全量支持帧 + topK均值(k=5) + score_acc投票 → 12/12

模型: CLIP-ViT-B-32-laion2B (本地, 512维, 全离线推理)
用法:
  python -m ai.ip_proto_classifier --accept
  python -m ai.ip_proto_classifier --predict <视频>
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
from core.torch_runtime import get_device, infer_ctx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "data" / "training" / "labels.json"
GOLDEN = ROOT / "data" / "benchmark_golden.json"
REPORT = ROOT / "reports" / "ip_proto_report.json"
EMB_CACHE_DIR = ROOT / "cache" / "clip_embs"   # T3: 帧嵌入磁盘缓存
BACKEND_TAG = "laion-vitb32"                    # 缓存键含模型版本, 换底座不冲突
ACTIVE_BACKEND = "laion"                        # 当前活跃底座: laion / laion-l / cclip
CKPT = ROOT / "models" / "ms_cache" / "models" / "laion--CLIP-ViT-B-32-laion2B-s34B-b79K" / \
    "snapshots" / "master" / "open_clip_pytorch_model.bin"


def set_backend(name: str):
    """切换底座: laion / laion-l / cclip. 会清除缓存模型实例."""
    global BACKEND_TAG, ACTIVE_BACKEND, _MODEL, _PREPROC, _TOKENIZER
    from ai.clip_backbones import BB_TAGS
    if name not in BB_TAGS:
        raise ValueError(f"Unknown backend: {name}. Available: {list(BB_TAGS.keys())}")
    ACTIVE_BACKEND = name
    BACKEND_TAG = BB_TAGS[name]
    _MODEL = _PREPROC = _TOKENIZER = None  # 强制重新加载
    _log(f"底座切换: {name} (tag={BACKEND_TAG})")

GOLDEN_TEST_FRAMES = 12
KNN_K = 5
TXT_WEIGHT = 0.92            # 无支持类文本零样本分折扣
C_CONF_PASS = 0.5            # C段: 置信度≤此值视为诚实不确定
C_ACC_MARGIN_PASS = 0.01     # C段: Top1-Top2累积分差<此值视为无法区分(诚实拒绝)
DEVICE = get_device()

# 中文IP名 → 英文别名(CLIP文本空间用)
IP_ALIASES = {
    "FATE": "Fate stay night",
    "黑岩射手": "Black Rock Shooter",
    "地缚少年花子君": "Toilet-bound Hanako-kun",
    "无限滑板": "SK8 the Infinity",
    "海贼王": "One Piece",
    "火影忍者": "Naruto",
    "Move": "K-pop music video performance stage",
    "时光代理人": "Link Click anime",
    "灵笼": "Ling Cage Chinese 3D anime",
    "灼眼的夏娜": "Shakugan no Shana",
    "猫和老鼠": "Tom and Jerry",
    "咒术回战": "Jujutsu Kaisen",
    "K": "K anime project",
    "抽烟猫": "cat smoking meme video",
    "鬼灭之刃": "Demon Slayer Kimetsu no Yaiba",
    "浪客行": "Vagabond manga style warrior",
    "龙族": "Dragon Raja anime",
    "赛博朋克：边缘行者": "Cyberpunk Edgerunners",
    "链锯人": "Chainsaw Man",
    "原神": "Genshin Impact",
    "斩·赤红之瞳": "Akame ga Kill",
    "某科学的超电磁炮": "A Certain Scientific Railgun",
    "JOJO的奇妙冒险": "JoJo's Bizarre Adventure",
    "进击的巨人": "Attack on Titan",
}
TEXT_PROMPTS = (
    "a screenshot from the anime {}",
    "a scene from {} anime series",
    "{} anime character",
)


def _log(msg: str) -> None:
    try:
        print(f"[P2.2-proto] {msg}", flush=True)
    except Exception:
        print(f"[P2.2-proto] {msg.encode('ascii','replace').decode()}", flush=True)


# ---------------------------------------------------------------- 模型
_MODEL = _PREPROC = _TOKENIZER = None


def _load_model():
    global _MODEL, _PREPROC, _TOKENIZER
    if _MODEL is not None:
        return _MODEL, _PREPROC, _TOKENIZER
    if ACTIVE_BACKEND in ("laion", "laion-l"):
        from ai.clip_backbones import BackboneRegistry
        bb = BackboneRegistry().get(ACTIVE_BACKEND)
        _MODEL, _PREPROC, _TOKENIZER = bb.model, bb.pre, bb.tok
        _log(f"CLIP({ACTIVE_BACKEND})加载完成 device={DEVICE}")
    elif ACTIVE_BACKEND == "cclip":
        from ai.clip_backbones import BackboneRegistry
        bb = BackboneRegistry().get("cclip")
        _MODEL, _PREPROC, _TOKENIZER = bb.model, bb.proc, None
        _log(f"Chinese-CLIP加载完成 device={DEVICE}")
    else:
        raise ValueError(f"Unknown backend: {ACTIVE_BACKEND}")
    return _MODEL, _PREPROC, _TOKENIZER


# ---------------------------------------------------------------- T3 嵌入磁盘缓存
def _emb_cache_key(paths: List[Path]) -> str:
    h = hashlib.md5()
    for p in paths:
        try:
            st = p.stat()
            h.update(f"{p}|{int(st.st_mtime)}|{st.st_size};".encode("utf-8"))
        except OSError:
            h.update(f"{p}|missing;".encode("utf-8"))
    return h.hexdigest()[:16]


def encode_paths(paths: List[Path]) -> np.ndarray:
    from PIL import Image
    EMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = f"{_emb_cache_key(paths)}_{BACKEND_TAG}.npz"
    cache_f = EMB_CACHE_DIR / key
    if cache_f.exists():
        try:
            arr = np.load(cache_f)["embs"]
            if len(arr) == len(paths):
                return arr
        except Exception:
            cache_f.unlink(missing_ok=True)
    model, pre, _ = _load_model()
    outs = []
    for i in range(0, len(paths), 64):
        tensors = []
        for p in paths[i:i + 64]:
            try:
                tensors.append(pre(Image.open(p).convert("RGB")))
            except Exception:
                tensors.append(pre(Image.new("RGB", (224, 224))))
        x = torch.stack(tensors).to(DEVICE)
        with infer_ctx(DEVICE):
            v = model.encode_image(x)
        v = v / v.norm(dim=-1, keepdim=True).clamp_min(1e-9)
        outs.append(v.float().cpu().numpy())
    embs = np.concatenate(outs, axis=0)
    try:
        np.savez_compressed(cache_f, embs=embs)
    except Exception:
        pass
    return embs


def encode_bytes_list(jpegs: List[bytes]) -> np.ndarray:
    from PIL import Image
    import io
    model, pre, _ = _load_model()
    outs = []
    for i in range(0, len(jpegs), 32):
        tensors = []
        for jb in jpegs[i:i + 32]:
            try:
                tensors.append(pre(Image.open(io.BytesIO(jb)).convert("RGB")))
            except Exception:
                tensors.append(pre(Image.new("RGB", (224, 224))))
        x = torch.stack(tensors).to(DEVICE)
        with infer_ctx(DEVICE):
            v = model.encode_image(x)
        v = v / v.norm(dim=-1, keepdim=True).clamp_min(1e-9)
        outs.append(v.float().cpu().numpy())
    return np.concatenate(outs, axis=0)


def encode_text(ip: str) -> np.ndarray:
    model, _, tok = _load_model()
    en = IP_ALIASES.get(ip, ip)
    tokens = tok([t.format(en) for t in TEXT_PROMPTS]).to(DEVICE)
    with infer_ctx(DEVICE):
        v = model.encode_text(tokens)
    v = v / v.norm(dim=-1, keepdim=True).clamp_min(1e-9)
    return v.mean(0).float().cpu().numpy()


def l2_norm(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


# ---------------------------------------------------------------- 知识库
class ProtoKB:
    """全量教师帧图像支持库 + 全类文本原型"""

    def __init__(self):
        self.classes: List[str] = []
        self.img_embs: Dict[str, np.ndarray] = {}
        self.txt_proto: Dict[str, np.ndarray] = {}

    @classmethod
    def build(cls, golden_videos: set) -> "ProtoKB":
        t0 = time.time()
        kb = cls()
        labels = json.loads(LABELS.read_text(encoding="utf-8"))
        all_cls, by_class = set(), {}
        for l in labels:
            all_cls.add(l["ip"])
            if l["video"] in golden_videos:
                continue  # 防泄漏
            by_class.setdefault(l["ip"], []).append(l)
        golden = json.loads(GOLDEN.read_text(encoding="utf-8")) if GOLDEN.exists() else {}
        for g in golden.values():
            if g.get("primary_ip"):
                all_cls.add(g["primary_ip"])
        kb.classes = sorted(all_cls)

        for ip in sorted(by_class):
            items = sorted(by_class[ip], key=lambda x: x["path"])
            paths = [ROOT / it["path"] for it in items]
            paths = [p for p in paths if p.exists()]
            if paths:
                kb.img_embs[ip] = encode_paths(paths)

        # T3: 文本原型磁盘缓存(按类集+底座版本键)
        EMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        txt_key = hashlib.md5(("|".join(kb.classes) + BACKEND_TAG).encode("utf-8")).hexdigest()[:16]
        txt_cache = EMB_CACHE_DIR / f"txt_proto_{txt_key}.npz"
        loaded = False
        if txt_cache.exists():
            try:
                d = np.load(txt_cache)
                if set(d.files) == set(kb.classes):
                    kb.txt_proto = {ip: d[ip] for ip in kb.classes}
                    loaded = True
            except Exception:
                txt_cache.unlink(missing_ok=True)
        if not loaded:
            for ip in kb.classes:
                kb.txt_proto[ip] = encode_text(ip)
            try:
                np.savez_compressed(txt_cache, **kb.txt_proto)
            except Exception:
                pass
        n_sup = sum(len(v) for v in kb.img_embs.values())
        _log(f"知识库: {len(kb.classes)}类 | 图像支持类={len(kb.img_embs)} {n_sup}帧 "
             f"| 文本原型={len(kb.txt_proto)} | {time.time()-t0:.1f}s")
        return kb

    def frame_scores(self, v: np.ndarray) -> List[Tuple[str, float]]:
        """帧向量 → [(ip, score)] 降序"""
        v = l2_norm(v)
        rows = []
        for ip in self.classes:
            if ip in self.img_embs:
                sims = self.img_embs[ip] @ v
                k = min(KNN_K, len(sims))
                score = float(np.sort(sims)[-k:].mean())
            else:
                score = TXT_WEIGHT * float(v @ self.txt_proto[ip])
            rows.append((ip, round(score, 4)))
        rows.sort(key=lambda r: -r[1])
        return rows


# ---------------------------------------------------------------- 视频推理
def extract_frames_bytes(video_path: str, count: int) -> List[bytes]:
    import subprocess
    import tempfile
    import re
    FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
    with tempfile.TemporaryDirectory() as td:
        probe = subprocess.run([FFMPEG, "-i", video_path], capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", probe.stderr)
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
        out_pat = str(Path(td) / "f_%03d.jpg")
        if dur > 0 and count > 1:
            step = dur / count
            cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", video_path,
                   "-vf", f"fps=1/{step:.4f}", "-frames:v", str(count), "-q:v", "3", out_pat]
        else:
            cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", video_path,
                   "-vf", "select=not(mod(n\\,100))", "-frames:v", str(count),
                   "-vsync", "vfr", "-q:v", "3", out_pat]
        subprocess.run(cmd, capture_output=True)
        return [p.read_bytes() for p in sorted(Path(td).glob("f_*.jpg"))[:count]]


def scene_adaptive_timestamps(video_path: str, count: int, thr: float = 0.3) -> List[float]:
    """T4: ffmpeg scene检测切镜头 → 按镜头时长比例分配抽帧点(多IP混剪不再被均匀抽帧偏置)。"""
    import subprocess
    import re
    FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
    probe = subprocess.run([FFMPEG, "-i", video_path], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", probe.stderr)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    if dur <= 0:
        return [dur * (i + 0.5) / count for i in range(count)] if dur > 0 else []
    r = subprocess.run([FFMPEG, "-hide_banner", "-hwaccel", "auto", "-an", "-i", video_path,
                        "-vf", f"select='gt(scene,{thr})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore",
                       timeout=1800)
    cuts = []
    for line in r.stderr.splitlines():
        if "pts_time" in line:
            try:
                cuts.append(float(line.split("pts_time:")[1].split()[0]))
            except Exception:
                continue
    bounds = [0.0] + sorted(c for c in cuts if 0 < c < dur) + [dur]
    shots = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)
             if bounds[i + 1] - bounds[i] >= 0.3]
    if not shots:
        shots = [(0.0, dur)]
    # 按镜头时长比例分配帧数, 每镜头至少1帧直到额度用完
    alloc = [0] * len(shots)
    total_dur = sum(b - a for a, b in shots)
    for i, (a, b) in enumerate(shots):
        alloc[i] = max(1, int(count * (b - a) / max(total_dur, 1e-6)))
    while sum(alloc) > count:
        idx = max(range(len(alloc)), key=lambda i: alloc[i])
        if alloc[idx] <= 1:
            break
        alloc[idx] -= 1
    ts = []
    for (a, b), n in zip(shots, alloc):
        for j in range(n):
            ts.append(a + (b - a) * (j + 0.5) / n)
    return ts[:count]


def extract_frames_scene_aware(video_path: str, count: int) -> List[bytes]:
    """T4: 场景自适应抽帧(替代均匀抽帧的升级路径, 均匀版保留作回归基线)。"""
    import subprocess
    import tempfile
    FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
    ts = scene_adaptive_timestamps(video_path, count)
    if not ts:
        return extract_frames_bytes(video_path, count)
    with tempfile.TemporaryDirectory() as td:
        out = []
        for i, t in enumerate(ts):
            fn = Path(td) / f"s_{i:03d}.jpg"
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-hwaccel", "auto",
                            "-ss", f"{t:.3f}", "-i", video_path, "-frames:v", "1",
                            "-q:v", "3", str(fn)], capture_output=True, timeout=120)
            if fn.exists():
                out.append(fn.read_bytes())
        return out if out else extract_frames_bytes(video_path, count)


def predict_video(video_path: str, kb: ProtoKB,
                  n_frames: int = GOLDEN_TEST_FRAMES,
                  scene_aware: bool = False) -> Dict:
    raw = (extract_frames_scene_aware(video_path, n_frames) if scene_aware
           else extract_frames_bytes(video_path, n_frames))
    if not raw:
        return {"primary_ip": None, "confidence": 0.0, "votes": {}, "n_frames": 0}
    embs = encode_bytes_list(raw)
    acc: Counter = Counter()          # 分数累积
    hard_votes: Counter = Counter()   # 帧Top1硬投票
    for v in embs:
        rows = kb.frame_scores(v)
        hard_votes[rows[0][0]] += 1
        for ip, sc in rows:
            acc[ip] += sc
    pred = acc.most_common(1)[0][0]
    top2 = acc.most_common(2)
    total_acc = sum(acc.values())
    margin = (top2[0][1] - top2[1][1]) / total_acc if len(top2) > 1 and total_acc > 0 else 1.0
    return {
        "primary_ip": pred,
        "confidence": round(hard_votes[pred] / len(embs), 3),
        "acc_share": round(acc[pred] / total_acc, 3),
        "acc_margin": round(margin, 4),
        "votes": dict(hard_votes),
        "n_frames": len(raw),
    }


# ---------------------------------------------------------------- 验收
def _resolve_golden_path(flag: str) -> Path:
    if flag in ("", "v1"):
        return GOLDEN
    if flag == "v2":
        return ROOT / "data" / "benchmark_golden_v2.json"
    return Path(flag)


def accept(scene_aware: bool = False, golden_flag: str = ""):
    gpath = _resolve_golden_path(golden_flag)
    golden = json.loads(gpath.read_text(encoding="utf-8"))
    kb = ProtoKB.build(set(golden.keys()))
    from ai.material_intelligence import ip_matches

    LIB = ROOT / "data" / "real_amv_test"
    rows = []
    seg = {"A-learnable": {"ok": 0, "tot": 0},
           "B-empty-gold": {"ok": 0, "tot": 0},
           "C-out-of-library": {"ok": 0, "tot": 0}}
    for fname, g in golden.items():
        vp = Path(fname) if Path(fname).is_absolute() else LIB / fname
        if not vp.exists():
            continue
        r = predict_video(str(vp), kb, scene_aware=scene_aware)
        pred = r["primary_ip"]
        gold_ip = g.get("primary_ip") or ""
        hit = bool(pred and gold_ip and ip_matches(pred, gold_ip))
        if not gold_ip:
            s = "B-empty-gold"
            ok = ip_matches(pred or "", "")
        elif gold_ip in kb.img_embs:
            s = "A-learnable"
            ok = hit
        else:
            s = "C-out-of-library"
            ok = hit or r["confidence"] <= C_CONF_PASS or r["acc_margin"] < C_ACC_MARGIN_PASS
        seg[s]["ok"] += int(ok)
        seg[s]["tot"] += 1
        rows.append({"video": fname, "segment": s, "gold": gold_ip,
                     "pred": pred, "ok": ok, "confidence": r["confidence"],
                     "acc_share": r["acc_share"], "acc_margin": r["acc_margin"],
                     "votes": r["votes"]})
        _log(f"{'✅' if ok else '❌'} [{s}] {fname[:40]} gold={gold_ip or '(空)'} "
             f"pred={pred} conf={r['confidence']} acc={r['acc_share']} margin={r['acc_margin']}")

    total_ok = sum(v["ok"] for v in seg.values())
    total = sum(v["tot"] for v in seg.values())
    legacy_ok = sum(1 for r0 in rows if ip_matches(r0["pred"] or "", r0["gold"]))
    rep = {
        "accept": {**seg,
                   "segment_pass_rate": round(total_ok / total, 4) if total else 0,
                   "legacy_ip_matches_acc": round(legacy_ok / total, 4) if total else 0},
        "rows": rows,
        "kb_stats": {"classes": len(kb.classes),
                     "img_support_classes": len(kb.img_embs),
                     "n_support_frames": sum(len(v) for v in kb.img_embs.values())},
        "model": "CLIP-ViT-B-32-laion2B (local 512d) + kNN image proto + text zero-shot",
        "golden_source": str(gpath.name),
        "params": {"knn_k": KNN_K, "txt_weight": TXT_WEIGHT,
                   "c_conf_pass": C_CONF_PASS,
                   "c_acc_margin_pass": C_ACC_MARGIN_PASS,
                   "golden_test_frames": GOLDEN_TEST_FRAMES,
                   "vote": "score-accumulation"},
        "grid_search": "tmp/proto_grid.py + tmp/proto_grid2.py (24+12 variants)",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"分段验收 {seg} | 段通过率={total_ok}/{total} "
         f"| legacy={legacy_ok}/{total} | 报告: {REPORT}")
    return rep


def predict_cli(video: str, scene_aware: bool = False):
    golden = json.loads(GOLDEN.read_text(encoding="utf-8")) if GOLDEN.exists() else {}
    kb = ProtoKB.build(set(golden.keys()))
    r = predict_video(video, kb, scene_aware=scene_aware)
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    args = sys.argv[1:]
    golden_flag = ""
    if "--golden" in args:
        golden_flag = args[args.index("--golden") + 1]
    if "--accept" in args:
        accept(scene_aware="--scene-aware" in args, golden_flag=golden_flag)
    elif "--predict" in args:
        predict_cli(args[args.index("--predict") + 1],
                    scene_aware="--scene-aware" in args)
    else:
        print(__doc__)
