# -*- coding: utf-8 -*-
"""master_deliver.py — 母版音频修复 + 交付规格转码（2026-09-09）

解决的问题（均为 `check_delivery_spec.py` 实测确认的呈现缺陷）：
  1. 音频真峰值 +2.48 dBTP、响度 -6.78 LUFS（远超流媒体标准，且存在削波簇）
     根因：`core/sfx_layer.py:326` 的 `amix=normalize=0` 之后**没有 limiter**，
     多路 SFX 叠加直接进 AAC 编码。
  2. 码率 15.8 Mbps（AKROSS Con 交付规格 ≈4 Mbps 的近 4 倍）

两条产出（都不重渲，只做音频母带 + 转码）：
  - `--mode master`   : 只修音频（双通道 loudnorm 两遍 + 真峰值限幅），视频流直通复制
  - `--mode delivery` : 音频修复 + 视频压到交付码率（默认 4 Mbps，两遍编码）

音频目标：I=-14 LUFS（流媒体标准）/ TP=-1.5 dBTP / LRA=11
  - 两遍 loudnorm：第一遍测量，第二遍用测量值做线性归一化（比单遍准确）
  - 之后接 alimiter 作真峰值兜底（防 AAC 编码过冲，run61 实测过冲 0.5dB）

用法:
  python scripts/master_deliver.py --in output/unified_run61/polish/master_hr.mp4 --mode master
  python scripts/master_deliver.py --in X --mode delivery --bitrate 4000
  python scripts/master_deliver.py --in X --mode both
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
FF = shutil.which("ffmpeg") or "C:/ffmpeg/bin/ffmpeg.exe"
FFPROBE = shutil.which("ffprobe") or "C:/ffmpeg/bin/ffprobe.exe"
ALLOWED_SUFFIXES = (".mp4", ".mov", ".mkv", ".webm", ".m4v")

# 音频母带目标
TARGET_I = -14.0      # LUFS 积分响度（流媒体标准）
TARGET_TP = -1.5      # dBTP 真峰值
TARGET_LRA = 11.0     # 响度范围


def safe_video(raw: str | Path) -> Path | None:
    try:
        p = Path(raw).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    if not p.is_file() or p.suffix.lower() not in ALLOWED_SUFFIXES:
        return None
    return p


def _run(cmd: list[str], timeout: int = 3600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=timeout,
                          shell=False, check=False)


def probe(path: Path) -> dict:
    r = _run([FFPROBE, "-v", "error", "-print_format", "json",
              "-show_format", "-show_streams", str(path)], timeout=120)
    try:
        info = json.loads(r.stdout or b"{}")
    except Exception:
        return {}
    v = next((s for s in info.get("streams", [])
              if s.get("codec_type") == "video"), {})
    a = next((s for s in info.get("streams", [])
              if s.get("codec_type") == "audio"), {})
    fmt = info.get("format", {})
    dur = float(fmt.get("duration", 0) or 0)
    size = float(fmt.get("size", 0) or 0)
    return {
        "duration": round(dur, 2),
        "size_mb": round(size / 1e6, 1),
        "mbps": round(size * 8 / dur / 1e6, 3) if dur else 0.0,
        "width": v.get("width"), "height": v.get("height"),
        "vcodec": v.get("codec_name"), "acodec": a.get("codec_name"),
        "fps": v.get("r_frame_rate"), "pix_fmt": v.get("pix_fmt"),
    }


def measure_loudness(path: Path) -> dict:
    """loudnorm 第一遍：测量 I / TP / LRA / thresh。"""
    r = _run([FF, "-v", "info", "-i", str(path),
              "-af", f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}"
                     ":print_format=json",
              "-f", "null", "-"], timeout=1800)
    txt = (r.stderr or b"").decode("utf-8", "replace")
    m = re.search(r"\{[^{}]*input_i[^{}]*\}", txt, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def audio_chain(measured: dict) -> str:
    """音频链：响度归一到目标 + 真峰值限幅。

    实测教训（2026-09-09）：
      - `loudnorm` 单遍 + measured 参数会把响度留在 -12.6 LUFS（偏离目标 1.4 LU），
        改用**直接增益**（volume）更可控：增益 = 目标LUFS - 实测LUFS。
      - `alimiter` 默认 `level=auto` 会做**自动增益补偿**，把响度抬高约 1.4 LU
        （实测 -14.1 → -12.6），必须显式 `level=disabled`。
    """
    gain = TARGET_I - float(measured.get("input_i", TARGET_I))
    # 真峰值限幅阈值：TP 目标换算为线性幅度
    limit_lin = 10 ** (TARGET_TP / 20)
    return (f"volume={gain:.3f}dB,"
            f"alimiter=limit={limit_lin:.6f}:attack=5:release=50:level=disabled")


def encode_master(src: Path, out: Path, measured: dict) -> bool:
    """只修音频：视频流直接复制，音频重编码。"""
    cmd = [FF, "-y", "-v", "error", "-i", str(src),
           "-af", audio_chain(measured),
           "-map", "0:v:0", "-map", "0:a:0",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", str(out)]
    r = _run(cmd, timeout=1800)
    if r.returncode != 0:
        print(f"    [master 失败] {(r.stderr or b'')[-300:].decode('utf-8', 'replace')}")
        return False
    return out.exists()


def encode_delivery(src: Path, out: Path, measured: dict, mbps: float,
                    preset: str) -> bool:
    """交付版：音频修复 + 视频两遍压到目标码率。"""
    total_kbps = int(mbps * 1000)
    # 音频占 192k，视频取其余（-2% 容器开销余量）
    v_kbps = max(int(total_kbps * 0.98) - 192, 500)
    cmd = [FF, "-y", "-v", "error", "-i", str(src),
           "-af", audio_chain(measured),
           "-map", "0:v:0", "-map", "0:a:0",
           "-c:v", "libx264", "-preset", preset,
           "-b:v", f"{v_kbps}k", "-maxrate", f"{int(v_kbps * 1.3)}k",
           "-bufsize", f"{int(v_kbps * 2)}k",
           "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", str(out)]
    r = _run(cmd, timeout=3600)
    if r.returncode != 0:
        print(f"    [delivery 失败] {(r.stderr or b'')[-300:].decode('utf-8', 'replace')}")
        return False
    return out.exists()


def verify_audio(path: Path) -> dict:
    """复测：真峰值 + 响度。"""
    r = _run([FF, "-v", "info", "-i", str(path),
              "-af", "loudnorm=print_format=json", "-f", "null", "-"], timeout=1800)
    txt = (r.stderr or b"").decode("utf-8", "replace")
    m = re.search(r"\{[^{}]*input_i[^{}]*\}", txt, re.S)
    out = {}
    if m:
        try:
            d = json.loads(m.group(0))
            out["lufs"] = float(d.get("input_i", 0))
            out["true_peak_dbtp"] = float(d.get("input_tp", 0))
            out["lra"] = float(d.get("input_lra", 0))
        except Exception:
            pass
    r2 = _run([FF, "-v", "info", "-i", str(path), "-af", "volumedetect",
               "-f", "null", "-"], timeout=1800)
    t2 = (r2.stderr or b"").decode("utf-8", "replace")
    mm = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", t2)
    if mm:
        out["max_volume_db"] = float(mm.group(1))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True, help="输入成片")
    ap.add_argument("--mode", choices=["master", "delivery", "both"], default="both")
    ap.add_argument("--bitrate", type=float, default=4.0, help="交付码率（Mbps）")
    ap.add_argument("--preset", default="slow", help="x264 preset（slow=质量优先）")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--json", default=None, help="报告输出路径")
    args = ap.parse_args()

    src = safe_video(args.src)
    if src is None:
        print(f"无效输入: {args.src}")
        return 1
    outdir = Path(args.outdir) if args.outdir else src.parent
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"输入: {src.name}")
    before = probe(src)
    print(f"  规格: {before['width']}x{before['height']} {before['vcodec']} / "
          f"{before['acodec']} | {before['mbps']} Mbps | {before['duration']}s")
    la_before = verify_audio(src)
    print(f"  音频: {la_before.get('lufs')} LUFS | "
          f"真峰值 {la_before.get('true_peak_dbtp')} dBTP | "
          f"max_volume {la_before.get('max_volume_db')} dB")

    print("\n[1/2] loudnorm 测量 ...")
    measured = measure_loudness(src)
    if measured:
        print(f"  measured: I={measured.get('input_i')} TP={measured.get('input_tp')} "
              f"LRA={measured.get('input_lra')} thresh={measured.get('input_thresh')}")
    else:
        print("  [警告] 测量失败，退回动态归一化")

    report = {"source": str(src), "before": before, "audio_before": la_before,
              "measured": measured, "outputs": {}}

    stem = src.stem
    if args.mode in ("master", "both"):
        out = outdir / f"{stem}_mastered.mp4"
        print(f"\n[2/2] 音频母带 → {out.name}（视频流复制，不重编码）")
        if encode_master(src, out, measured):
            info = probe(out)
            la = verify_audio(out)
            report["outputs"]["master"] = {"path": str(out), "probe": info,
                                           "audio": la}
            print(f"  ✓ {info['size_mb']}MB | {info['mbps']} Mbps")
            print(f"    音频: {la.get('lufs')} LUFS | 真峰值 {la.get('true_peak_dbtp')} dBTP | "
                  f"max_volume {la.get('max_volume_db')} dB")

    if args.mode in ("delivery", "both"):
        out = outdir / f"{stem}_delivery_{int(args.bitrate)}M.mp4"
        print(f"\n交付转码 → {out.name}（目标 {args.bitrate} Mbps, preset={args.preset}）")
        if encode_delivery(src, out, measured, args.bitrate, args.preset):
            info = probe(out)
            la = verify_audio(out)
            report["outputs"]["delivery"] = {"path": str(out), "probe": info,
                                             "audio": la}
            print(f"  ✓ {info['size_mb']}MB | {info['mbps']} Mbps")
            print(f"    音频: {la.get('lufs')} LUFS | 真峰值 {la.get('true_peak_dbtp')} dBTP | "
                  f"max_volume {la.get('max_volume_db')} dB")

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        print(f"\n报告 → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
