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

用法:
  from core.sfx_layer import plan_sfx, mix_sfx
  plan = plan_sfx(beat_events, seed=42)          # [(file, t, gain)]
  mix_sfx(mp4_in, mp4_out, plan)                 # 混音落盘
"""
from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

PROJECT = Path(__file__).resolve().parent.parent
SFX_INDEX = PROJECT / "data" / "sfx" / "index.json"

# beat_type → SFX 池名 + 增益
BEAT_SFX_MAP = {
    "kick":   ("impact", 0.9),   # kick 撞拍 → 重击
    "snare":  ("whoosh", 0.6),   # snare 切点 → 划过
    "drop":   ("impact", 1.0),   # drop 爆发 → 最强
    "build":  ("riser", 0.5),    # build 铺垫 → 上升
    "glitch": ("glitch", 0.5),   # 故障转场
}


def _load_index() -> dict:
    """池名 → [文件路径]"""
    if not SFX_INDEX.exists():
        return {}
    return json.loads(SFX_INDEX.read_text(encoding="utf-8"))


def plan_sfx(beat_events: List[dict], seed: int = 42,
             pools_override: Optional[dict] = None) -> List[Tuple[str, float, float]]:
    """节拍事件 → SFX 计划 [(file, t_start, gain)]。

    同池文件轮换 (避免连续同一音效); 无池资源时跳过该事件。
    """
    pools = pools_override or _load_index()
    rng = random.Random(seed)
    plan = []
    last_pick: dict = {}
    for ev in beat_events:
        t = float(ev.get("time", 0))
        bt = str(ev.get("beat_type", "snare")).lower()
        pool_name, gain = BEAT_SFX_MAP.get(bt, ("whoosh", 0.5))
        files = pools.get(pool_name, [])
        if not files:
            continue
        # 轮换: 优先选与上次不同的
        pick = rng.choice(files)
        for _ in range(3):
            if pick != last_pick.get(pool_name) or len(files) == 1:
                break
            pick = rng.choice(files)
        last_pick[pool_name] = pick
        plan.append((pick, t, gain))
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
    parts.append("".join(mix_labels) + f"amix=inputs={len(mix_labels)}:normalize=0[outa]")

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


__all__ = ["plan_sfx", "mix_sfx", "BEAT_SFX_MAP"]
