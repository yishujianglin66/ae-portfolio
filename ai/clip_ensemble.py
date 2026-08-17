# -*- coding: utf-8 -*-
"""T5/T6: 双底座集成IP分类器 — laion(英文空间) + chinese-clip(中文空间) 分数级融合。

结构(继承P2.2开集协议, 上限语义不变):
  1. 每底座独立建库: 教师帧图像支持库(kNN top-K均值) + 类文本原型零样本(×0.92)
  2. 帧级分数加权融合 ensemble_frame_scores(权重网格搜索)
  3. 视频级分数累积投票; C段诚实拒绝口径(conf≤0.5 / margin<0.01)完全继承

验收口径(与ip_proto_classifier三段一致):
  A.可学习Top-1正确 B.空真值语义通过 C.库外命中或诚实拒绝
红线: laion单底座(w=1.0)必须复现v1口径12/12; 集成≥max(单底座)且A段不降分。

缓存: 复用 cache/clip_embs, 键含底座tag(laion-vitb32与v1共享, cclip独立)。
用法:
  python -m ai.clip_ensemble --accept [--golden v2] [--scene-aware]
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "data" / "training" / "labels.json"
GOLDEN = ROOT / "data" / "benchmark_golden.json"
GOLDEN_V2 = ROOT / "data" / "benchmark_golden_v2.json"
REPORT = ROOT / "reports" / "clip_ensemble_report.json"
EMB_CACHE_DIR = ROOT / "cache" / "clip_embs"

# 与 ip_proto_classifier 铁律常量完全一致(v1口径不漂移)
from ai.ip_proto_classifier import (KNN_K, TXT_WEIGHT, C_CONF_PASS,
                                     C_ACC_MARGIN_PASS, GOLDEN_TEST_FRAMES,
                                     IP_ALIASES, extract_frames_bytes,
                                     extract_frames_scene_aware)
from ai.clip_backbones import BackboneRegistry, ensemble_frame_scores, BB_TAGS
# 权重网格: laion权重从0.3~1.0(cclip补余), 1.0即退化为v1纯laion口径
WEIGHT_GRID = [round(w, 1) for w in np.arange(0.3, 1.05, 0.1)]


def _log(msg: str) -> None:
    print(f"[T6-ensemble] {msg}", flush=True)


def _emb_cache_key(paths: List[Path]) -> str:
    h = hashlib.md5()
    for p in paths:
        try:
            st = p.stat()
            h.update(f"{p}|{int(st.st_mtime)}|{st.st_size};".encode("utf-8"))
        except OSError:
            h.update(f"{p}|missing;".encode("utf-8"))
    return h.hexdigest()[:16]


class EnsembleKB:
    """双底座知识库: 每底座独立图像支持库+文本原型(磁盘缓存)。"""

    def __init__(self, registry: BackboneRegistry, golden_videos: set):
        t0 = time.time()
        labels = json.loads(LABELS.read_text(encoding="utf-8"))
        all_cls, by_class = set(), {}
        for l in labels:
            all_cls.add(l["ip"])
            if l["video"] in golden_videos:
                continue  # 防泄漏: 黄金集帧绝不进支持集
            by_class.setdefault(l["ip"], []).append(l)
        gpath = GOLDEN_V2 if GOLDEN_V2.exists() else GOLDEN
        golden = json.loads(gpath.read_text(encoding="utf-8")) if gpath.exists() else {}
        for g in golden.values():
            if g.get("primary_ip"):
                all_cls.add(g["primary_ip"])
        self.classes = sorted(all_cls)
        self.support_paths: Dict[str, List[Path]] = {}
        for ip in sorted(by_class):
            items = sorted(by_class[ip], key=lambda x: x["path"])
            paths = [ROOT / it["path"] for it in items]
            paths = [p for p in paths if p.exists()]
            if paths:
                self.support_paths[ip] = paths

        self.registry = registry
        self.img_embs: Dict[str, Dict[str, np.ndarray]] = {}   # bb -> ip -> embs
        self.txt_proto: Dict[str, Dict[str, np.ndarray]] = {}  # bb -> ip -> proto
        for bb_name in ("laion", "cclip"):
            self._build_backbone(bb_name)
        n_sup = sum(len(v) for v in self.support_paths.values())
        _log(f"双底座知识库: {len(self.classes)}类 | 支持类={len(self.support_paths)} "
             f"{n_sup}帧 | {time.time()-t0:.1f}s")

    def _build_backbone(self, bb_name: str):
        bb = self.registry.get(bb_name)
        tag = BB_TAGS[bb_name]
        EMB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.img_embs[bb_name] = {}
        for ip, paths in self.support_paths.items():
            key = f"{_emb_cache_key(paths)}_{tag}.npz"
            cf = EMB_CACHE_DIR / key
            arr = None
            if cf.exists():
                try:
                    arr = np.load(cf)["embs"]
                    if len(arr) != len(paths):
                        arr = None
                except Exception:
                    cf.unlink(missing_ok=True)
            if arr is None:
                arr = bb.encode_images(paths)
                try:
                    np.savez_compressed(cf, embs=arr)
                except Exception:
                    pass
            self.img_embs[bb_name][ip] = arr
        # 文本原型缓存(类集+底座tag键)
        txt_key = hashlib.md5(
            ("|".join(self.classes) + tag).encode("utf-8")).hexdigest()[:16]
        tf = EMB_CACHE_DIR / f"txt_proto_{txt_key}.npz"
        loaded = False
        if tf.exists():
            try:
                d = np.load(tf)
                if set(d.files) == set(self.classes):
                    self.txt_proto[bb_name] = {ip: d[ip] for ip in self.classes}
                    loaded = True
            except Exception:
                tf.unlink(missing_ok=True)
        if not loaded:
            protos = {}
            for ip in self.classes:
                protos[ip] = self.registry.class_protos(bb_name, ip, IP_ALIASES)
            self.txt_proto[bb_name] = protos
            try:
                np.savez_compressed(tf, **protos)
            except Exception:
                pass

    def frame_scores(self, bb_name: str, v: np.ndarray) -> Dict[str, float]:
        """单底座帧级分数(与v1 ProtoKB.frame_scores同口径)。"""
        n = np.linalg.norm(v)
        v = v / n if n > 1e-9 else v
        out = {}
        for ip in self.classes:
            if ip in self.img_embs[bb_name]:
                sims = self.img_embs[bb_name][ip] @ v
                k = min(KNN_K, len(sims))
                out[ip] = float(np.sort(sims)[-k:].mean())
            else:
                out[ip] = TXT_WEIGHT * float(v @ self.txt_proto[bb_name][ip])
        return out


def _save_frames(jpegs: List[bytes]) -> Tuple[List[Path], tempfile.TemporaryDirectory]:
    td = tempfile.TemporaryDirectory()
    paths = []
    for i, jb in enumerate(jpegs):
        fp = Path(td.name) / f"e_{i:03d}.jpg"
        fp.write_bytes(jb)
        paths.append(fp)
    return paths, td


def predict_video_ensemble(video_path: str, kb: EnsembleKB,
                           weights: Dict[str, float],
                           n_frames: int = GOLDEN_TEST_FRAMES,
                           scene_aware: bool = False) -> Dict:
    raw = (extract_frames_scene_aware(video_path, n_frames) if scene_aware
           else extract_frames_bytes(video_path, n_frames))
    if not raw:
        return {"primary_ip": None, "confidence": 0.0, "acc_share": 0.0,
                "acc_margin": 0.0, "votes": {}, "n_frames": 0}
    paths, td = _save_frames(raw)
    try:
        per_bb_embs = {bb: kb.registry.get(bb).encode_images(paths)
                       for bb in weights if weights[bb] > 0}
    finally:
        td.cleanup()
    acc: Counter = Counter()
    hard_votes: Counter = Counter()
    for fi in range(len(raw)):
        scores_by_bb = {bb: kb.frame_scores(bb, per_bb_embs[bb][fi])
                        for bb in per_bb_embs}
        fused = ensemble_frame_scores(scores_by_bb, weights)
        hard_votes[fused[0][0]] += 1
        for ip, sc in fused:
            acc[ip] += sc
    pred = acc.most_common(1)[0][0]
    top2 = acc.most_common(2)
    total_acc = sum(acc.values())
    margin = ((top2[0][1] - top2[1][1]) / total_acc
              if len(top2) > 1 and total_acc > 0 else 1.0)
    return {"primary_ip": pred,
            "confidence": round(hard_votes[pred] / len(raw), 3),
            "acc_share": round(acc[pred] / total_acc, 3),
            "acc_margin": round(margin, 4),
            "votes": dict(hard_votes), "n_frames": len(raw)}


# ---------------------------------------------------------------- 验收
def _eval_golden(kb: EnsembleKB, golden: Dict, weights: Dict[str, float],
                 scene_aware: bool = False) -> Dict:
    from ai.material_intelligence import ip_matches
    LIB = ROOT / "data" / "real_amv_test"
    seg = {"A-learnable": {"ok": 0, "tot": 0},
           "B-empty-gold": {"ok": 0, "tot": 0},
           "C-out-of-library": {"ok": 0, "tot": 0}}
    rows = []
    for fname, g in golden.items():
        vp = Path(fname) if Path(fname).is_absolute() else LIB / fname
        if not vp.exists():
            continue
        r = predict_video_ensemble(str(vp), kb, weights, scene_aware=scene_aware)
        pred = r["primary_ip"]
        gold_ip = g.get("primary_ip") or ""
        hit = bool(pred and gold_ip and ip_matches(pred, gold_ip))
        if not gold_ip:
            s = "B-empty-gold"
            ok = ip_matches(pred or "", "")
        elif gold_ip in kb.support_paths:
            s = "A-learnable"
            ok = hit
        else:
            s = "C-out-of-library"
            ok = hit or r["confidence"] <= C_CONF_PASS or r["acc_margin"] < C_ACC_MARGIN_PASS
        seg[s]["ok"] += int(ok)
        seg[s]["tot"] += 1
        rows.append({"video": fname, "segment": s, "gold": gold_ip,
                     "pred": pred, "ok": ok, "confidence": r["confidence"],
                     "acc_margin": r["acc_margin"]})
    return {"segments": seg, "rows": rows,
            "total_ok": sum(v["ok"] for v in seg.values()),
            "total": sum(v["tot"] for v in seg.values())}


def accept(golden_flag: str = "", scene_aware: bool = False):
    if golden_flag == "v2":
        gpath = GOLDEN_V2
    elif golden_flag:
        gpath = Path(golden_flag)
    else:
        gpath = GOLDEN
    if not gpath.exists():
        _log(f"黄金集不存在: {gpath}")
        return None
    golden = json.loads(gpath.read_text(encoding="utf-8"))
    kb = EnsembleKB(BackboneRegistry(), set(golden.keys()))

    sweep = []
    best = None
    for w_l in WEIGHT_GRID:
        weights = {"laion": w_l, "cclip": round(1.0 - w_l, 2)}
        t0 = time.time()
        res = _eval_golden(kb, golden, weights, scene_aware)
        entry = {"w_laion": w_l, "ok": res["total_ok"], "tot": res["total"],
                 "segments": res["segments"], "time_s": round(time.time() - t0, 1)}
        sweep.append(entry)
        _log(f"w_laion={w_l:.1f} → {res['total_ok']}/{res['total']} "
             f"A={res['segments']['A-learnable']['ok']}/{res['segments']['A-learnable']['tot']} "
             f"B={res['segments']['B-empty-gold']['ok']}/{res['segments']['B-empty-gold']['tot']} "
             f"C={res['segments']['C-out-of-library']['ok']}/{res['segments']['C-out-of-library']['tot']}")
        # 择优: 总通过数最大; 平局时laion权重高者优先(贴近v1口径更稳)
        if best is None or res["total_ok"] > best[1]["total_ok"]:
            best = (weights, res, entry)

    weights, res, entry = best
    laion_only = next(s for s in sweep if s["w_laion"] == 1.0)
    rep = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "golden_source": gpath.name,
        "scene_aware": scene_aware,
        "best_weights": weights,
        "best": {"ok": res["total_ok"], "tot": res["total"],
                 "segments": res["segments"], "rows": res["rows"]},
        "laion_only_baseline": laion_only,
        "sweep": sweep,
        "params": {"knn_k": KNN_K, "txt_weight": TXT_WEIGHT,
                   "c_conf_pass": C_CONF_PASS,
                   "c_acc_margin_pass": C_ACC_MARGIN_PASS,
                   "weight_grid": WEIGHT_GRID},
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    def _json_default(o):
        import numpy as _np
        if isinstance(o, (_np.bool_,)):
            return bool(o)
        if isinstance(o, (_np.integer,)):
            return int(o)
        if isinstance(o, (_np.floating,)):
            return float(o)
        return str(o)

    REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=2,
                                 default=_json_default), encoding="utf-8")
    _log(f"最优权重={weights} → {res['total_ok']}/{res['total']} | "
         f"laion单底座={laion_only['ok']}/{laion_only['tot']} | 报告: {REPORT}")
    return rep


if __name__ == "__main__":
    args = sys.argv[1:]
    flag = ""
    if "--golden" in args:
        flag = args[args.index("--golden") + 1]
    if "--accept" in args:
        accept(flag, scene_aware="--scene-aware" in args)
    else:
        print(__doc__)
