"""sfx_layer.py — 卡点音效层（beat_events → SFX 混音）

卡点链路音频半环: kick 撞击 / snare 转场 / build 段 Riser 上升 / glitch 故障音。
实现路线与 LUT 管线同构 (2026-08-17): AE 音频图层脚本化不可靠 → ffmpeg 后混音。
渲染管线: aerender avi → ffmpeg 转码(+LUT) → +SFX 混音 → 成片。

⚠ 2026-08-27 事故: 本文件曾被 "rebuilt baseline" 残废版覆盖
  (_load_index 返回 [] / mix_sfx 退化为 shutil.copy2), 卡点音效静默失效。
  本版从开发会话记录完整重建。

资源池 (语义分类, data/sfx/index.json 由 build_sfx_index.py 生成):
  impact ← 击打/Trailer Hit/Code Black (撞拍重音)
  whoosh ← whoosh/转场环绕 (切点划过)
  riser  ← 上升 Risers (build 段张力铺垫)
  glitch ← 信号干扰故障 (故障转场)

v2 音乐性增强 (2026-09-02):
  ① 瞬态前置补偿: impact -45ms / whoosh -300ms / riser -350ms / glitch -60ms
  ② onset 细分层: 弱onset(strength<0.3) → light SFX @ -12dB
  ③ 重拍双层: kick/drop + is_downbeat → 叠加 sub-boom (70Hz, 150ms 衰减)
  ④ 力度曲线: 段落能量 → SFX 增益缩放 (high=boost, low=attenuate)

用法:
  from core.sfx_layer import plan_sfx, mix_sfx
  plan = plan_sfx(beat_events, seed=42)                    # 基础
  plan = plan_sfx(beat_events, sections=sections,           # 带力度曲线
                  onset_events=onsets)                      # +onset 细分
  mix_sfx(mp4_in, mp4_out, plan)                            # 混音落盘
"""
from __future__ import annotations

import json
import logging
import random
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger("sfx_layer")

PROJECT = Path(__file__).resolve().parent.parent
SFX_INDEX = PROJECT / "data" / "sfx" / "index.json"

# beat_type → SFX 池名 + 基准增益
BEAT_SFX_MAP = {
    "kick":   ("impact", 0.9),
    "snare":  ("whoosh", 0.6),
    "drop":   ("impact", 1.0),
    "build":  ("riser", 0.5),
    "glitch": ("glitch", 0.5),
}

# ① 瞬态前置补偿 (ms): 音效类型 → 提前量
# impact 瞬态快, 只需微提前; whoosh/riser 需要铺垫时间
PRE_COMP_MS: Dict[str, float] = {
    "impact": 45,
    "whoosh": 300,
    "riser":  350,
    "glitch": 60,
}

# ② onset 细分层: 弱 onset 增益 (-12dB ≈ 0.25)
WEAK_ONSET_GAIN = 0.25
WEAK_ONSET_THRESHOLD = 0.3
ONSET_COVER_RADIUS = 0.15  # 150ms 内视为已被 beat 覆盖

# ③ 重拍双层: sub-boom 参数
SUB_BOOM_FREQ = 70       # Hz
SUB_BOOM_DUR = 0.17      # 秒 (20ms attack + 150ms decay)
SUB_BOOM_GAIN = 0.55     # 相对主 impact 的比例
SUB_BOOM_LEAD_MS = 20    # sub-boom 比主 impact 提前 20ms

# ⑤ 智能裁短 (2026-09-02 音墙修复): SFX 池多为 5-20s trailer 素材,
# adelay 不截尾 → 几十条长尾全程叠加成"持续音墙": 掩蔽 BGM 鼓点 +
# 峰值持续撞限幅器把鼓瞬态压平 (实测终版打击乐占比 0.056→0.003)。
# 修复: 找文件能量峰, 只取 [峰前 head_s, 峰后 tail_s]。
SFX_TAIL_S: Dict[str, float] = {
    "impact": 1.2,   # 撞击+自然衰减尾
    "whoosh": 0.9,   # 划过+短尾
    "riser":  1.5,   # 上升需要完整铺垫
    "glitch": 0.45,  # 短促故障点
}
_SHORT_HEAD_S = 0.06
_SHORT_CACHE = PROJECT / "cache" / "sfx_short"
# 裁短同时归一化 (2026-09-02 v2.2): 峰区裁剪的短片比全文件平均响得多
# (实测能量超预算 ~7 倍 → 持续撞限幅器 → 鼓瞬态被压平)。归一到基准
# RMS 后, plan 里的 volume 增益才是真实幅度, 能量预算可预测。
SFX_REF_RMS = 0.22


def _load_index() -> dict:
    """池名 → [文件路径]"""
    if not SFX_INDEX.exists():
        return {}
    return json.loads(SFX_INDEX.read_text(encoding="utf-8"))


def shorten_sfx(path: str, tail_s: float, head_s: float = _SHORT_HEAD_S,
                pool: str = "") -> Optional[str]:
    """裁出音效能量峰片段 (峰前 head_s → 峰后 tail_s), 缓存复用。

    返回 44.1k 双声道 wav 路径; 失败返回 None (调用方回退原文件)。
    """
    p = Path(path)
    if not p.exists():
        return None
    out = _SHORT_CACHE / f"{pool}_{p.stem}_{int(tail_s * 1000)}.wav"
    if out.exists() and out.stat().st_size > 200:
        return str(out)
    try:
        import io

        import numpy as np
        import soundfile as _sf
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(p), "-vn", "-ac", "1", "-ar", "22050",
             "-f", "wav", "-"], capture_output=True, timeout=60)
        y, sr = _sf.read(io.BytesIO(r.stdout), dtype="float32")
        if y.ndim > 1:
            y = y.mean(axis=1)
        if len(y) < sr * 0.1:
            return None
        # 10ms 帧能量包络 + 50ms 平滑 → 找峰
        hop = max(1, int(sr * 0.01))
        n = len(y) // hop
        if n < 2:
            return None
        env = (y[: n * hop].reshape(n, hop) ** 2).mean(axis=1)
        k = min(5, n)
        env_s = np.convolve(env, np.ones(k) / k, mode="same")
        peak_t = float(np.argmax(env_s)) * hop / sr
        start = max(0.0, peak_t - head_s)
        dur = head_s + tail_s
        # 裁剪窗口实测 RMS → 归一化系数 (过静的适度提升, 过响的压到基准)
        i0 = int(start * sr)
        i1 = min(len(y), int((start + dur) * sr))
        win_rms = float(np.sqrt(np.mean(y[i0:i1] ** 2))) if i1 > i0 else 0.0
        norm = float(np.clip(SFX_REF_RMS / max(win_rms, 1e-4), 0.25, 3.0))
        out.parent.mkdir(parents=True, exist_ok=True)
        r2 = subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(p),
             "-af", f"volume={norm:.3f}",
             "-ar", "44100", "-ac", "2", str(out)], capture_output=True, timeout=60)
        if out.exists() and out.stat().st_size > 200:
            return str(out)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"shorten_sfx({path}) 失败: {e}")
    return None


def _ensure_sub_boom() -> Optional[str]:
    """生成 70Hz sub-boom (20ms attack + 150ms exp decay), 缓存到 data/sfx/_sub_boom.wav。"""
    path = PROJECT / "data" / "sfx" / "_sub_boom.wav"
    if path.exists():
        return str(path)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i",
             f"sine=frequency={SUB_BOOM_FREQ}:duration={SUB_BOOM_DUR}:"
             f"sample_rate=44100,afade=t=out:st=0.02:d=0.15",
             "-ar", "44100", "-ac", "1", str(path)],
            capture_output=True, timeout=10)
        if path.exists() and path.stat().st_size > 100:
            return str(path)
    except Exception:
        pass
    return None


# ────────────────────────────────────────────────────────────────
# 力度曲线: 段落能量 → 增益缩放
# ────────────────────────────────────────────────────────────────
def _velocity_scale(sections: Optional[Sequence[dict]], t: float,
                    base_gain: float) -> float:
    """④ 根据段落能量缩放增益。

    sections: [{start, end, level, energy_mean}] (from MusicDynamicsAnalyzer)
    high段: base * (0.85 + 0.3 * energy)  → 最高 ~1.15x
    mid段:  base * (0.65 + 0.3 * energy)  → 0.65-0.95x
    low段:  base * (0.45 + 0.3 * energy)  → 0.45-0.75x
    """
    if not sections:
        return base_gain
    sec = None
    for s in sections:
        if s["start"] <= t < s["end"]:
            sec = s
            break
    if sec is None:
        return base_gain
    energy = float(sec.get("energy_mean", 0.5))
    level = sec.get("level", "mid")
    if level == "high":
        factor = 0.85 + 0.3 * energy
    elif level == "low":
        factor = 0.45 + 0.3 * energy
    else:
        factor = 0.65 + 0.3 * energy
    return base_gain * factor


def _pick_file(pool: list, last_pick: dict, pool_name: str,
               rng: random.Random) -> Optional[str]:
    """从池中选文件, 轮换避免连续重复。"""
    if not pool:
        return None
    pick = rng.choice(pool)
    for _ in range(3):
        if pick != last_pick.get(pool_name) or len(pool) == 1:
            break
        pick = rng.choice(pool)
    last_pick[pool_name] = pick
    return pick


def plan_sfx(beat_events: List[dict], seed: int = 42,
             pools_override: Optional[dict] = None,
             sections: Optional[Sequence[dict]] = None,
             onset_events: Optional[Sequence[dict]] = None) -> List[Tuple[str, float, float]]:
    """节拍事件 → SFX 计划 [(file, t_start, gain)]。

    增强版 (v2):
      ① 瞬态前置补偿: 按 SFX 类型提前 adelay
      ② onset 细分层: 弱 onset 补 light SFX @ -12dB
      ③ 重拍双层: downbeat kick/drop 叠加 sub-boom
      ④ 力度曲线: 段落能量缩放增益

    Args:
        beat_events: [{time, beat_type, is_downbeat?}]
        sections: MusicDynamicsAnalyzer 输出 [{start, end, level, energy_mean}]
        onset_events: [{time, strength}] 全部 onset (函数内部筛选弱 onset)
    """
    pools = pools_override or _load_index()
    rng = random.Random(seed)
    plan: List[Tuple[str, float, float]] = []
    last_pick: dict = {}
    sub_boom_path: Optional[str] = None

    beat_times = [float(ev.get("time", 0)) for ev in beat_events]

    for ev in beat_events:
        t = float(ev.get("time", 0))
        bt = str(ev.get("beat_type", "snare")).lower()
        pool_name, base_gain = BEAT_SFX_MAP.get(bt, ("whoosh", 0.5))
        files = pools.get(pool_name, [])
        if not files:
            continue

        # ④ 力度曲线
        gain = _velocity_scale(sections, t, base_gain)

        # ① 瞬态前置补偿
        pre_ms = PRE_COMP_MS.get(pool_name, 0)
        t_adj = max(0.0, t - pre_ms / 1000.0)

        pick = _pick_file(files, last_pick, pool_name, rng)
        if pick is None:
            continue
        plan.append((pick, t_adj, gain))

        # ③ 重拍双层: downbeat 的 kick/drop 叠加 sub-boom
        is_downbeat = bool(ev.get("is_downbeat", False))
        if is_downbeat and bt in ("kick", "drop"):
            if sub_boom_path is None:
                sub_boom_path = _ensure_sub_boom()
            if sub_boom_path:
                sub_gain = _velocity_scale(sections, t, SUB_BOOM_GAIN)
                sub_t = max(0.0, t - SUB_BOOM_LEAD_MS / 1000.0)
                plan.append((sub_boom_path, sub_t, sub_gain))

    # ② onset 细分层: 弱 onset 补 light SFX
    if onset_events:
        light_pool = pools.get("glitch", [])
        if light_pool:
            for oe in onset_events:
                ot = float(oe.get("time", 0))
                strength = float(oe.get("strength", 0.5))
                if strength >= WEAK_ONSET_THRESHOLD:
                    continue
                # 跳过已被 beat 覆盖的 onset
                if any(abs(ot - bt) < ONSET_COVER_RADIUS for bt in beat_times):
                    continue
                pre_ms = PRE_COMP_MS.get("glitch", 60)
                t_adj = max(0.0, ot - pre_ms / 1000.0)
                pick = _pick_file(light_pool, last_pick, "glitch", rng)
                if pick is None:
                    continue
                plan.append((pick, t_adj, WEAK_ONSET_GAIN))

    logger.info(f"plan_sfx: {len(beat_events)} beats → {len(plan)} SFX events"
                + (f" (+{len(plan) - len(beat_events)} onset/sub-boom)" if len(plan) > len(beat_events) else ""))
    return plan


def mix_sfx(video_in: str, video_out: str, sfx_plan: List[Tuple[str, float, float]],
            bgm: Optional[str] = None, bgm_gain: float = 0.7,
            lut: Optional[dict] = None, crf: int = 17) -> bool:
    """视频 + SFX (+可选 BGM) (+可选 LUT) 一次合成输出。

    每个音效 adelay 定位 + volume 增益, amix 归一混合; 视频流直通(可叠 LUT)。
    """
    if not sfx_plan and not bgm:
        # 纯视频 (可仍挂 LUT)
        if lut and lut.get("cube"):
            from core.lut_pipeline import transcode_with_lut
            return transcode_with_lut(video_in, video_out, lut["cube"],
                                      float(lut.get("strength", 1.0)), crf=crf)
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", video_in, "-c:v", "libx264", "-preset", "medium",
             "-crf", str(crf), "-pix_fmt", "yuv420p", video_out],
            capture_output=True, timeout=300)
        return Path(video_out).exists() and r.returncode == 0

    # 构造 filter_complex: 视频流(可挂LUT) + 各音效 adelay/volume + amix 归一混合
    parts = []
    mix_labels = []
    n_inputs = 1  # 0 = 视频
    for i, (f, t, g) in enumerate(sfx_plan, start=1):
        parts.append(f"[{i}:a]adelay={int(t * 1000)}|{int(t * 1000)},volume={g:.2f}[s{i}]")
        mix_labels.append(f"[s{i}]")
        n_inputs += 1
    if bgm:
        parts.append(f"[{n_inputs}:a]volume={bgm_gain:.2f}[bgm]")
        mix_labels.append("[bgm]")
        n_inputs += 1
    # amix 后必须接限幅器：多路 SFX + BGM 叠加常超过 0 dBFS。
    # 实测（2026-09-09, run61）：无 limiter 时真峰值 +2.48 dBTP、-6.78 LUFS，
    # 存在 6 处削波簇。limit=0.8414(-1.5dBFS) 留编码过冲余量；
    # level=disabled 是关键——默认 auto 会做自动增益补偿，把响度抬高约 1.4 LU。
    parts.append("".join(mix_labels)
                 + f"amix=inputs={len(mix_labels)}:normalize=0,"
                   "alimiter=limit=0.8414:attack=5:release=50:level=disabled[outa]")

    # 视频链 (可选 LUT)
    vchain = "[0:v]"
    if lut and lut.get("cube"):
        from core.lut_pipeline import _ff_escape
        s = max(0.0, min(1.0, float(lut.get("strength", 1.0))))
        vchain = (f"[0:v]split=2[a][b];[a]lut3d='{_ff_escape(lut['cube'])}'[l];"
                  f"[b][l]blend=all_expr='A*(1-{s:.3f})+B*{s:.3f}'[vout]")
    else:
        vchain = "[0:v]null[vout]"

    fc = vchain + ";" + ";".join(parts)
    cmd = ["ffmpeg", "-y", "-i", video_in]
    for f, _, _ in sfx_plan:
        cmd += ["-i", f]
    if bgm:
        cmd += ["-i", bgm]
    cmd += ["-filter_complex", fc, "-map", "[vout]", "-map", "[outa]",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", video_out]
    r = subprocess.run(cmd, capture_output=True, timeout=600)
    return Path(video_out).exists() and r.returncode == 0


__all__ = [
    "plan_sfx", "mix_sfx", "BEAT_SFX_MAP",
    "PRE_COMP_MS", "WEAK_ONSET_GAIN", "WEAK_ONSET_THRESHOLD",
    "SUB_BOOM_FREQ", "SUB_BOOM_GAIN",
]
