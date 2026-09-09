# -*- coding: utf-8 -*-
"""audio_budget.py — 混音能量预算（2026-09-09）

问题：链路各阶段独立加增益，没有全局响度目标。实测 run61：
  run61_final  -9.1 LUFS / TP +0.2 dBFS   （底轨已无余量）
  master       -5.1 LUFS / TP +2.4 dBFS   （polish 又推高）
  master_hr    -6.7 LUFS / TP +2.5 dBFS   （削波）
即 SFX 叠加时底轨本身已贴近 0 dBFS，任何附加能量必然削波。

本模块提供**可测量的能量预算**：
  1. measure()      测底轨 LUFS / 真峰值 / LRA
  2. budget()       按目标真峰值算出"可安全叠加的增益上限"
  3. scale_plan()   把 SFX 计划的增益整体缩放到预算内
  4. verify()       对成品复测，确认落在目标区间

设计原则：预算由**实测**得出，不靠经验常数；缩放后再复测闭环。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

FF = shutil.which("ffmpeg") or "C:/ffmpeg/bin/ffmpeg.exe"

# 交付目标（与 master_deliver.py 一致）
TARGET_LUFS = -14.0
TARGET_TP_DBTP = -1.5
# AAC 编码过冲余量：实测衰减到底轨合规后，解码真峰值仍会高出约 0.3dB
ENCODE_MARGIN_DB = 0.3
# SFX 相对底轨的安全叠加上限（保守：即使多路叠加也不易过冲）
MAX_SFX_GAIN_DB = 0.0


def _run(cmd: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=timeout,
                          shell=False, check=False)


def measure(path: str | Path) -> dict:
    """测量音频：集成响度 LUFS / 真峰值 dBTP / 响度范围 LRA。

    用 ebur128（与 loudnorm 交叉验证一致），peak=true 取真峰值。

    注意：ebur128 的进度输出里也含 "I: xxx LUFS"（瞬时值，开头常为 -70），
    必须只解析 **Summary:** 之后的段落，否则会取到瞬时值。
    """
    p = Path(path)
    if not p.exists():
        return {}
    r = _run([FF, "-v", "info", "-i", str(p), "-af", "ebur128=peak=true",
              "-f", "null", "-"], timeout=1800)
    txt = (r.stderr or b"").decode("utf-8", "replace")
    # 只取 Summary 段
    idx = txt.rfind("Summary:")
    block = txt[idx:] if idx >= 0 else ""
    out: dict = {}
    m = re.search(r"Integrated loudness:\s*\n\s*I:\s*(-?[\d.]+)\s*LUFS", block)
    if m:
        out["lufs"] = round(float(m.group(1)), 2)
    m = re.search(r"Loudness range:\s*\n\s*LRA:\s*(-?[\d.]+)\s*LU", block)
    if m:
        out["lra"] = round(float(m.group(1)), 2)
    m = re.search(r"True peak:\s*\n\s*Peak:\s*(-?[\d.]+)\s*dBFS", block)
    if m:
        out["tp_dbfs"] = round(float(m.group(1)), 2)
    return out


def budget(base: dict, target_tp: float = TARGET_TP_DBTP,
           n_sfx: int = 1) -> dict:
    """按底轨实测值算可安全叠加的增益预算。

    返回:
      headroom_db    底轨真峰值到目标的余量（已扣编码余量；负值=底轨已超目标）
      sfx_scale      建议的 SFX 增益缩放系数（1.0=不缩）
      base_gain_db   建议的底轨增益（负值=需衰减底轨）
      verdict        ok / attenuate_base / reduce_sfx

    规则（保守、可解释）：
      - 余量 ≥ 0：SFX 可保持原增益，底轨不动 → ok
      - 余量 < 0：按余量衰减底轨（保证底轨自身合规），SFX 缩放 0.5 避免叠加
      - 多路 SFX（n_sfx > 8）时额外降 SFX 缩放（能量叠加更易过冲）
    编码余量：target_tp 再预留 ENCODE_MARGIN_DB，抵消 AAC 解码过冲。
    """
    tp = base.get("tp_dbfs")
    if tp is None:
        return {"headroom_db": None, "sfx_scale": 1.0, "base_gain_db": 0.0,
                "verdict": "unknown", "note": "底轨真峰值测量失败"}
    effective_target = target_tp - ENCODE_MARGIN_DB
    headroom = round(effective_target - tp, 2)
    if headroom >= 0:
        sfx_scale = 1.0 if n_sfx <= 8 else 0.85
        return {"headroom_db": headroom, "sfx_scale": sfx_scale,
                "base_gain_db": 0.0, "verdict": "ok",
                "note": f"余量 {headroom:+.2f}dB（含编码余量 {ENCODE_MARGIN_DB}dB），SFX 可原增益"}
    # 底轨已超目标
    base_gain = round(headroom, 2)          # 衰减到底轨自身合规
    sfx_scale = 0.5 if n_sfx > 4 else 0.7   # 叠加部分保守降幅
    return {"headroom_db": headroom, "sfx_scale": sfx_scale,
            "base_gain_db": base_gain, "verdict": "attenuate_base",
            "note": f"底轨超目标 {abs(headroom):.2f}dB（含编码余量），"
                    f"衰减底轨并降 SFX 至 {sfx_scale}"}


def scale_plan(plan: list, scale: float) -> list:
    """把 SFX 计划 [(file, t_ms, gain)] 的增益整体缩放。

    保持结构不变（文件与时间点不动），只改增益，便于对照验证。
    """
    if scale == 1.0:
        return list(plan)
    out = []
    for item in plan:
        f, t, g = item
        out.append((f, t, round(max(0.0, float(g) * scale), 4)))
    return out


def verify(path: str | Path, target_lufs: float = TARGET_LUFS,
           target_tp: float = TARGET_TP_DBTP) -> dict:
    """成品复测：是否落在目标区间。"""
    m = measure(path)
    if not m:
        return {"verdict": "unknown"}
    lufs = m.get("lufs")
    tp = m.get("tp_dbfs")
    issues = []
    if tp is not None and tp > target_tp:
        issues.append(f"真峰值 {tp} > 目标 {target_tp}")
    if lufs is not None and abs(lufs - target_lufs) > 3.0:
        issues.append(f"响度 {lufs} 偏离目标 {target_lufs} 超过 3 LU")
    return {
        "measured": m,
        "verdict": "PASS" if not issues else "FAIL",
        "issues": issues,
    }


def cli() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="混音能量预算")
    ap.add_argument("--measure", help="测量音频（LUFS/TP/LRA）")
    ap.add_argument("--budget-for", help="为某底轨算 SFX 预算")
    ap.add_argument("--n-sfx", type=int, default=1, help="SFX 数量")
    ap.add_argument("--verify", help="成品复测")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    result: dict = {}
    if args.measure:
        result["measure"] = measure(args.measure)
        print(json.dumps(result["measure"], ensure_ascii=False, indent=1))
    if args.budget_for:
        base = measure(args.budget_for)
        b = budget(base, n_sfx=args.n_sfx)
        result["budget"] = b
        print(json.dumps(b, ensure_ascii=False, indent=1))
    if args.verify:
        v = verify(args.verify)
        result["verify"] = v
        print(json.dumps(v, ensure_ascii=False, indent=1))
    if args.json and result:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(cli())
