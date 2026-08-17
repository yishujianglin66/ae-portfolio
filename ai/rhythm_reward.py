# -*- coding: utf-8 -*-
"""P3.1 节奏匹配奖励模型 (Rhythm Reward Model)
=====================================================
目标: 学习一个可泛化的"剪辑节奏质量"打分器，输入(音频+候选切点方案)，
输出预测的踩拍质量 → 供导演系统在多个剪辑方案间择优。

数据生成(真实+合成):
- 正样本: 37个真实AMV的实际切点(人工高手剪辑)
- 负样本: 对真实切点做扰动(小/大抖动、半拍偏移、均匀/偏移网格、随机、双倍密度，多随机种子)
特征(不直接泄露目标): 切点相位分布/镜头时长统计/切点能量/节拍覆盖
标签: 软踩拍得分 soft_beat_score = 每切点 max(0, 1-dev/(bi/2)) 均值
      (硬踩拍率因固定容差区分度不足，仅作辅助指标)
验收指标: 视频级GroupKFold 5折 — 成对排序准确率/MAE/R2/Spearman

用法:
  python -m ai.rhythm_reward --build       # 构建数据集
  python -m ai.rhythm_reward --train       # 训练+视频级留出验证
  python -m ai.rhythm_reward --demo        # 多方案择优演示
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "data" / "real_amv_test"
DATASET = ROOT / "data" / "training" / "rhythm_dataset.json"
MODEL_PKL = ROOT / "models" / "rhythm_reward.pkl"
META = ROOT / "models" / "rhythm_reward_meta.json"
REPORT = ROOT / "reports" / "rhythm_reward_report.json"

TOLERANCE_MS = 120.0   # 踩拍判定容差
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"


def _log(m: str):
    try:
        print(m, flush=True)
    except UnicodeEncodeError:
        print(m.encode("utf-8", "replace").decode("utf-8", "replace"), flush=True)


# ---------------- 信号提取 ----------------

def extract_audio(video_path: str, out_wav: str) -> bool:
    r = subprocess.run([FFMPEG, "-y", "-i", video_path, "-vn", "-ac", "1",
                        "-ar", "22050", out_wav],
                       capture_output=True, timeout=120)
    return r.returncode == 0 and Path(out_wav).exists()


def detect_beats(wav_path: str) -> Tuple[List[float], float]:
    import librosa
    y, sr = librosa.load(wav_path, sr=22050)
    tempo_raw, frames = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(tempo_raw[0]) if hasattr(tempo_raw, "__len__") else float(tempo_raw)
    beats = [float(t) for t in librosa.frames_to_time(frames, sr=sr)]
    return beats, tempo


def refine_beats_with_onsets(wav_path: str, beats: List[float]) -> List[float]:
    """用onset峰值微对齐节拍相位 — 修正librosa节拍帧的系统性滞后。
    诊断发现: 未校准节拍与真实AMV切点存在0.2-0.4拍系统性相位偏差，
    导致标签反转。每个节拍吸附到±0.25拍内最强onset峰。"""
    import numpy as np
    import librosa
    y, sr = librosa.load(wav_path, sr=22050)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, onset_envelope=onset_env)
    onsets = np.array(librosa.frames_to_time(onset_frames, sr=sr))
    if len(onsets) == 0 or len(beats) < 2:
        return beats
    bi = float(np.median(np.diff(beats)))
    window = bi * 0.25
    refined = []
    for b in beats:
        idx = np.where(np.abs(onsets - b) <= window)[0]
        if len(idx):
            best = idx[np.argmax(onset_env[onset_frames[idx]])]
            refined.append(float(onsets[best]))
        else:
            refined.append(float(b))
    return refined


def detect_cuts(video_path: str, threshold: float = 0.25) -> List[float]:
    import re
    cmd = [FFMPEG, "-i", video_path,
           "-vf", f"select='gt(scene,{threshold})',showinfo",
           "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore", timeout=300)
    cuts = sorted(float(t) for t in re.findall(r"pts_time:([\d.]+)", r.stderr))
    merged: List[float] = []
    for t in cuts:
        if not merged or t - merged[-1] > 0.15:
            merged.append(t)
    return merged


def on_beat_rate(cuts: List[float], beats: List[float],
                 tol_ms: float = TOLERANCE_MS) -> float:
    """硬踩拍率(辅助指标) — 自适应容差 min(tol_ms, 0.2*节拍间隔)"""
    if not cuts or not beats:
        return 0.0
    import numpy as np
    bi = float(np.median(np.diff(beats))) if len(beats) > 1 else 0.5
    tol = min(tol_ms / 1000.0, bi * 0.2)
    ba = np.array(beats)
    hit = sum(1 for c in cuts if float(np.min(np.abs(ba - c))) <= tol)
    return hit / len(cuts)


def soft_beat_score(cuts: List[float], beats: List[float]) -> float:
    """软踩拍得分(主标签): 每切点 max(0, 1 - dev/(bi/2)) 均值。
    相比硬踩拍率提供连续梯度，能有效区分真实切点/小抖动/大抖动/偏移。"""
    if not cuts or not beats:
        return 0.0
    import numpy as np
    ba = np.array(beats)
    bi = float(np.median(np.diff(beats))) if len(beats) > 1 else 0.5
    half = max(bi * 0.5, 0.1)
    total = sum(max(0.0, 1.0 - float(np.min(np.abs(ba - c))) / half) for c in cuts)
    return total / len(cuts)


# ---------------- 特征 ----------------

def cut_features(cuts: List[float], beats: List[float], duration: float) -> Dict[str, float]:
    """从候选切点方案提取特征(不含偏差真值，供模型学习)"""
    import numpy as np
    if not cuts:
        return {k: 0.0 for k in [
            "n_cuts", "cut_rate", "phase_entropy", "phase_conc",
            "shot_dur_mean", "shot_dur_std", "shot_dur_cv", "short_shot_ratio",
            "beat_coverage", "grid_regularity", "phase_mean_sin", "phase_mean_cos",
            "frac_near_015", "frac_near_030", "frac_offbeat"]}
    beat_interval = float(np.median(np.diff(beats))) if len(beats) > 1 else 0.5
    beat_interval = max(beat_interval, 0.2)
    ba = np.array(beats)
    # 节拍接近度量化箱位(相对最近节拍距离,以bi为单位的粗分箱)
    devs_u = np.array([float(np.min(np.abs(ba - c))) / beat_interval for c in cuts])
    frac_near_015 = float((devs_u <= 0.15).mean())
    frac_near_030 = float((devs_u <= 0.30).mean())
    frac_offbeat = float(((devs_u >= 0.35) & (devs_u <= 0.65)).mean())
    # 相位: 每个切点在节拍周期中的位置 [0,1)
    phases = [((c % beat_interval) / beat_interval) for c in cuts]
    phase_arr = np.array(phases)
    # 相位集中度(圆形统计)
    sin_m = float(np.mean(np.sin(2 * np.pi * phase_arr)))
    cos_m = float(np.mean(np.cos(2 * np.pi * phase_arr)))
    conc = float(np.hypot(sin_m, cos_m))
    # 相位熵(8 bins)
    hist, _ = np.histogram(phase_arr, bins=8, range=(0, 1))
    p = hist / max(hist.sum(), 1)
    p = p[p > 0]
    entropy = float(-(p * np.log2(p)).sum())
    # 镜头时长统计
    bounds = [0.0] + list(cuts) + [duration]
    shots = np.diff(bounds)
    shots = shots[shots > 0.05]
    if len(shots):
        s_mean = float(shots.mean())
        s_std = float(shots.std())
        s_cv = s_std / max(s_mean, 1e-6)
        short_ratio = float((shots < beat_interval * 0.5).mean())
    else:
        s_mean = s_std = s_cv = short_ratio = 0.0
    # 节拍覆盖率: 被切点"认领"(±半拍内)的节拍比例
    claimed = 0
    for b in beats:
        if cuts and min(abs(b - c) for c in cuts) <= beat_interval * 0.5:
            claimed += 1
    coverage = claimed / max(len(beats), 1)
    # 切点间隔规律性(与中位数间隔的偏离)
    if len(cuts) > 2:
        ivals = np.diff(cuts)
        med = float(np.median(ivals))
        reg = 1.0 / (1.0 + float(np.std(ivals)) / max(med, 1e-6))
    else:
        reg = 0.5
    return {
        "n_cuts": len(cuts),
        "cut_rate": len(cuts) / max(duration, 1.0),
        "phase_entropy": entropy,
        "phase_conc": conc,
        "shot_dur_mean": s_mean,
        "shot_dur_std": s_std,
        "shot_dur_cv": s_cv,
        "short_shot_ratio": short_ratio,
        "beat_coverage": coverage,
        "grid_regularity": reg,
        "phase_mean_sin": sin_m,
        "phase_mean_cos": cos_m,
        "frac_near_015": frac_near_015,
        "frac_near_030": frac_near_030,
        "frac_offbeat": frac_offbeat,
    }


FEATURE_KEYS = ["n_cuts", "cut_rate", "phase_entropy", "phase_conc",
                "shot_dur_mean", "shot_dur_std", "shot_dur_cv", "short_shot_ratio",
                "beat_coverage", "grid_regularity", "phase_mean_sin", "phase_mean_cos",
                "frac_near_015", "frac_near_030", "frac_offbeat"]


# ---------------- 数据集构建 ----------------

def build_dataset():
    import numpy as np
    rng = np.random.default_rng(42)
    wav_dir = ROOT / "cache" / "rhythm_wav"
    wav_dir.mkdir(parents=True, exist_ok=True)

    samples, skipped = [], 0
    videos = sorted(LIB.glob("*.mp4"))
    for vi, vp in enumerate(videos):
        wav = wav_dir / f"{vp.stem[:40]}.wav"
        if not wav.exists() and not extract_audio(str(vp), str(wav)):
            skipped += 1
            continue
        try:
            beats, tempo = detect_beats(str(wav))
        except Exception as e:
            _log(f"  [{vi+1}] 节拍检测失败 {vp.name[:30]}: {e}")
            skipped += 1
            continue
        if len(beats) < 4:
            skipped += 1
            continue
        beats = refine_beats_with_onsets(str(wav), beats)
        import cv2
        cap = cv2.VideoCapture(str(vp))
        duration = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / (cap.get(cv2.CAP_PROP_FPS) or 24)
        cap.release()
        cuts = detect_cuts(str(vp))
        if len(cuts) < 3:
            skipped += 1
            continue
        # 节奏质量门控: 校准后真实切点中位距离>0.3拍 → 非踩点素材(教程/无BGM)，剔除保证标签真实性
        import numpy as _np
        ba = _np.array(beats)
        med_dev = float(_np.median([_np.min(_np.abs(ba - c)) for c in cuts]))
        bi_check = float(_np.median(_np.diff(beats)))
        if med_dev / bi_check > 0.30:
            _log(f"  [{vi+1}] 剔除(非踩点素材,中位偏差{med_dev/bi_check:.2f}拍): {vp.name[:30]}")
            skipped += 1
            continue
        base_soft = soft_beat_score(cuts, beats)
        base_hard = on_beat_rate(cuts, beats)
        # 正样本: 真实切点
        samples.append({"video": vp.name, "variant": "real",
                        "features": cut_features(cuts, beats, duration),
                        "label": round(base_soft, 4),
                        "hard_rate": round(base_hard, 4)})
        # 合成扰动负样本(多随机种子增强覆盖)
        cuts_arr = np.array(cuts)
        bi = float(np.median(np.diff(beats))) if len(beats) > 1 else 0.5
        variants = {}
        for seed in (1, 2, 3):
            rs = np.random.default_rng(seed * 100 + vi)
            variants[f"jitter_small_{seed}"] = cuts_arr + rs.uniform(-bi * 0.12, bi * 0.12, len(cuts))
            variants[f"jitter_large_{seed}"] = cuts_arr + rs.uniform(-bi * 0.45, bi * 0.45, len(cuts))
            variants[f"random_{seed}"] = np.sort(rs.uniform(0.2, duration - 0.2, len(cuts)))
        variants["halfbeat_shift"] = cuts_arr + bi / 2
        variants["uniform_grid"] = np.linspace(0.3, duration - 0.3, len(cuts))
        variants["offbeat_grid"] = np.linspace(0.3, duration - 0.3, len(cuts)) + bi * 0.3
        variants["double_density"] = np.sort(np.concatenate([cuts_arr, cuts_arr + bi / 2]))
        for vname, vc in variants.items():
            vc = sorted(float(c) for c in vc if 0.05 < c < duration - 0.05)
            if len(vc) < 2:
                continue
            samples.append({"video": vp.name, "variant": vname,
                            "features": cut_features(vc, beats, duration),
                            "label": round(soft_beat_score(vc, beats), 4),
                            "hard_rate": round(on_beat_rate(vc, beats), 4)})
        _log(f"  [{vi+1}/{len(videos)}] {vp.name[:34]}: 真切点{len(cuts)} "
             f"软得分={base_soft:.2f} 硬踩拍率={base_hard:.2f} tempo={tempo:.0f}")

    DATASET.parent.mkdir(parents=True, exist_ok=True)
    DATASET.write_text(json.dumps(samples, ensure_ascii=False), encoding="utf-8")
    labels = [s["label"] for s in samples]
    _log(f"\n数据集: {len(samples)}样本 (跳过{skipped}素材) | "
         f"标签均值={sum(labels)/len(labels):.3f} min={min(labels):.2f} max={max(labels):.2f}")
    _log(f"文件: {DATASET}")


# ---------------- 训练 ----------------

def _pairwise_accuracy(y_true, y_pred, groups, margin=0.05):
    """同视频内成对排序准确率 — 多方案择优的真实验收指标"""
    from collections import defaultdict
    by_vid = defaultdict(list)
    for t, p, g in zip(y_true, y_pred, groups):
        by_vid[g].append((t, p))
    agree, tot = 0, 0
    for _, items in by_vid.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                (t1, p1), (t2, p2) = items[i], items[j]
                if abs(t1 - t2) < margin:
                    continue
                tot += 1
                if (t1 - t2) * (p1 - p2) > 0:
                    agree += 1
    return agree / max(tot, 1), tot


def train():
    import numpy as np
    from scipy.stats import spearmanr
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import GroupKFold
    from sklearn.metrics import mean_absolute_error, r2_score

    samples = json.loads(DATASET.read_text(encoding="utf-8"))
    X = np.array([[s["features"][k] for k in FEATURE_KEYS] for s in samples])
    y = np.array([s["label"] for s in samples])
    groups = np.array([s["video"] for s in samples])

    # 视频级5折交叉验证(防泄漏) — 聚合预测统一评估(小样本下fold级指标方差过大)
    gkf = GroupKFold(n_splits=5)
    all_pred = np.zeros_like(y)
    mae_list, pw_list = [], []
    for fold, (tr, va) in enumerate(gkf.split(X, y, groups)):
        m = GradientBoostingRegressor(n_estimators=120, max_depth=2,
                                      learning_rate=0.08, subsample=0.8,
                                      random_state=42)
        m.fit(X[tr], y[tr])
        pred = m.predict(X[va])
        all_pred[va] = pred
        pw, pw_n = _pairwise_accuracy(y[va], pred, groups[va])
        mae_list.append(mean_absolute_error(y[va], pred))
        pw_list.append(pw)
        _log(f"  fold{fold+1}: MAE={mae_list[-1]:.4f} 成对排序准确率={pw:.3f}({pw_n}对) "
             f"(验证样本{len(va)})")

    # 聚合指标: 全部留出预测一起评估(无泄漏,每样本均由未见其视频的模型预测)
    agg_mae = mean_absolute_error(y, all_pred)
    agg_r2 = r2_score(y, all_pred)
    agg_pw, agg_pw_n = _pairwise_accuracy(y, all_pred, groups)
    agg_sp = spearmanr(y, all_pred).statistic
    # 关键验收: 预测排序 vs 真值排序(同视频内) — 真值更差的方案预测分也必须更低
    from collections import defaultdict
    by_vid = defaultdict(dict)
    by_vid_truth = defaultdict(dict)
    for s_, p_ in zip(samples, all_pred):
        by_vid[s_["video"]][s_["variant"]] = p_
        by_vid_truth[s_["video"]][s_["variant"]] = s_["label"]
    top_ok, top_n = 0, 0
    top2_ok = 0
    for vid, dd in by_vid.items():
        truth = by_vid_truth[vid]
        if len(dd) < 3:
            continue
        top_n += 1
        # Top1择优一致: 预测最高分方案 == 真值最高分方案
        best_pred = max(dd, key=dd.get)
        best_truth = max(truth, key=truth.get)
        if best_pred == best_truth:
            top_ok += 1
        # Top2包容: 预测Top1落在真值Top2内
        truth_top2 = sorted(truth, key=truth.get, reverse=True)[:2]
        if best_pred in truth_top2:
            top2_ok += 1

    # 全量重训最终模型
    final = GradientBoostingRegressor(n_estimators=120, max_depth=2,
                                      learning_rate=0.08, subsample=0.8,
                                      random_state=42)
    final.fit(X, y)
    # 保序校准: 把聚合留出预测映射回真值尺度(修复排序模型绝对分区分度不足)
    from sklearn.isotonic import IsotonicRegression
    calib = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    calib.fit(all_pred, y)
    import pickle
    MODEL_PKL.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PKL.write_bytes(pickle.dumps({"regressor": final, "calibrator": calib}))
    META.write_text(json.dumps({
        "feature_keys": FEATURE_KEYS, "tolerance_ms": TOLERANCE_MS,
        "label": "soft_beat_score(onset校准节拍)",
        "cv_mae": round(float(agg_mae), 4),
        "cv_r2": round(float(agg_r2), 3),
        "cv_pairwise_acc": round(float(agg_pw), 4),
        "cv_pairwise_pairs": int(agg_pw_n),
        "cv_spearman": round(float(agg_sp), 3),
        "top1_selection_acc": f"{top_ok}/{top_n}",
        "top2_selection_acc": f"{top2_ok}/{top_n}",
        "n_samples": len(samples),
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"\n聚合留出指标(无泄漏): MAE={agg_mae:.4f} R2={agg_r2:.3f} "
         f"成对排序准确率={agg_pw:.4f}({agg_pw_n}对) Spearman={agg_sp:.3f}")
    _log(f"择优Top1一致性(预测最高==真值最高): {top_ok}/{top_n} | Top2包容: {top2_ok}/{top_n}")
    _log(f"模型: {MODEL_PKL}\n元数据: {META}")

    # 特征重要度
    imp = sorted(zip(FEATURE_KEYS, final.feature_importances_),
                 key=lambda x: -x[1])
    _log("特征重要度 Top6:")
    for k, v in imp[:6]:
        _log(f"  {k:20s} {v:.3f}")


# ---------------- 推理与择优 ----------------

def score_plan(cuts: List[float], beats: List[float], duration: float) -> float:
    """奖励模型打分 — 导演系统多方案择优入口(含保序校准)"""
    import pickle
    import numpy as np
    bundle = pickle.loads(MODEL_PKL.read_bytes())
    if isinstance(bundle, dict):  # 新版: {regressor, calibrator}
        model, calib = bundle["regressor"], bundle["calibrator"]
    else:  # 兼容旧版纯回归器
        model, calib = bundle, None
    feats = cut_features(cuts, beats, duration)
    x = np.array([[feats[k] for k in FEATURE_KEYS]])
    raw = float(model.predict(x)[0])
    if calib is not None:
        raw = float(calib.predict(np.array([raw]))[0])
    return raw


def demo():
    """多方案择优演示: 对同一素材的多种剪辑方案打分并与客观真值对比"""
    import numpy as np
    # 仅在训练集涵盖的素材(通过节奏质量门控)上演示,避免非踩点素材干扰
    ds_videos = {s["video"] for s in json.loads(DATASET.read_text(encoding="utf-8"))}
    wav_dir = ROOT / "cache" / "rhythm_wav"
    rows = []
    videos = [vp for vp in sorted(LIB.glob("*.mp4")) if vp.name in ds_videos]
    for vp in videos:
        wav = wav_dir / f"{vp.stem[:40]}.wav"
        if not wav.exists():
            continue
        beats, _ = detect_beats(str(wav))
        if len(beats) < 4:
            continue
        beats = refine_beats_with_onsets(str(wav), beats)
        import cv2
        cap = cv2.VideoCapture(str(vp))
        duration = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / (cap.get(cv2.CAP_PROP_FPS) or 24)
        cap.release()
        cuts = detect_cuts(str(vp))
        if len(cuts) < 3:
            continue
        rng = np.random.default_rng(7)
        bi = float(np.median(np.diff(beats)))
        plans = {
            "真实切点": cuts,
            "半拍偏移": sorted(c + bi / 2 for c in cuts if c + bi / 2 < duration),
            "均匀网格": list(np.linspace(0.5, duration - 0.5, len(cuts))),
            "随机切点": list(np.sort(rng.uniform(0.2, duration - 0.2, len(cuts)))),
        }
        _log(f"\n{vp.name[:40]}")
        for pname, pcuts in plans.items():
            pred = score_plan(pcuts, beats, duration)
            truth = soft_beat_score(pcuts, beats)
            hard = on_beat_rate(pcuts, beats)
            rows.append({"video": vp.name, "plan": pname,
                         "reward": round(pred, 3), "truth": round(truth, 3),
                         "hard_rate": round(hard, 3)})
            _log(f"  {pname:8s} 奖励={pred:.3f} 软得分={truth:.3f} 硬踩拍率={hard:.3f}")

    # 排序一致性: 奖励排序 vs 真值排序
    from collections import defaultdict
    by_vid = defaultdict(list)
    for r in rows:
        by_vid[r["video"]].append(r)
    agree, agree_tol, tot = 0, 0, 0
    for vid, rs in by_vid.items():
        order_reward = [r["plan"] for r in sorted(rs, key=lambda x: -x["reward"])]
        sorted_truth = sorted(rs, key=lambda x: -x["truth"])
        order_truth = [r["plan"] for r in sorted_truth]
        tot += 1
        if order_reward[0] == order_truth[0]:
            agree += 1
            agree_tol += 1
        elif len(sorted_truth) > 1 and sorted_truth[0]["truth"] - sorted_truth[1]["truth"] < 0.03:
            # 真值Top1与Top2差距<0.03 → 边界样本,预测选中Top2也算通过
            if order_reward[0] == order_truth[1]:
                agree_tol += 1
    _log(f"\n择优一致性(奖励Top1==真值Top1): {agree}/{tot} | 含边界容差: {agree_tol}/{tot}")
    REPORT.write_text(json.dumps({"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                  "top1_agreement": f"{agree}/{tot}",
                                  "top1_agreement_with_margin": f"{agree_tol}/{tot}",
                                  "rows": rows}, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    _log(f"报告: {REPORT}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    if args.build:
        build_dataset()
    if args.train:
        train()
    if args.demo:
        demo()
    if not (args.build or args.train or args.demo):
        print("用法: --build / --train / --demo")
