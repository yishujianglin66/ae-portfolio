# -*- coding: utf-8 -*-
"""BGM 音频体检 — 定位"杂音"来源 (2026-08-15 用户反馈).

用法: python scripts/audio_health_check.py <bgm.mp3> [out_dir]
输出: 每1秒 RMS/峰值/频谱平坦度/过零率统计 + 异常段落报告 (JSON)。
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


def ffmpeg_here():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.paths import ffmpeg_bin
    return ffmpeg_bin()


def main():
    bgm, out_dir = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
    out_dir = Path(out_dir) if out_dir else Path(bgm).parent
    ffmpeg = ffmpeg_here()
    raw = Path(tempfile.gettempdir()) / "bgm_check_f32.raw"
    subprocess.run(
        [ffmpeg, "-y", "-i", bgm, "-ac", "1", "-ar", "44100",
         "-f", "f32le", str(raw)],
        capture_output=True, check=True, timeout=300)
    x = np.fromfile(raw, dtype=np.float32)
    sr = 44100
    n = len(x) // sr
    rows = []
    for i in range(n):
        seg = x[i * sr:(i + 1) * sr]
        rms = float(np.sqrt(np.mean(seg ** 2)) + 1e-12)
        peak = float(np.max(np.abs(seg)))
        # 频谱平坦度 (越高越像噪声/嘶声)
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        geo = np.exp(np.mean(np.log(spec[10:] + 1e-12)))
        ari = np.mean(spec[10:])
        flatness = float(geo / (ari + 1e-12))
        zcr = float(np.mean(np.abs(np.diff(np.sign(seg)))) / 2)
        rows.append({
            "t": i,
            "rms_db": round(20 * np.log10(rms), 1),
            "peak_db": round(20 * np.log10(peak + 1e-12), 1),
            "flatness": round(flatness, 3),
            "zcr": round(zcr, 4),
        })
    rms_db = np.array([r["rms_db"] for r in rows])
    flat = np.array([r["flatness"] for r in rows])
    zcr = np.array([r["zcr"] for r in rows])
    anomalies = []
    # 1) 静音段 (RMS < -50dB 持续)
    for r in rows:
        if r["rms_db"] < -50:
            anomalies.append({"type": "near_silence", "t": r["t"],
                              "rms_db": r["rms_db"]})
    # 2) 嘶声/噪声段 (RMS 中等 -35~-20dB 但平坦度异常高)
    flat_thr = float(np.percentile(flat, 90)) + 0.05
    for r in rows:
        if r["rms_db"] > -45 and r["flatness"] > flat_thr:
            anomalies.append({"type": "hiss_like", "t": r["t"],
                              "flatness": r["flatness"],
                              "rms_db": r["rms_db"]})
    # 3) 爆音/削波 (peak >= -0.3dB)
    for r in rows:
        if r["peak_db"] >= -0.3:
            anomalies.append({"type": "near_clip", "t": r["t"],
                              "peak_db": r["peak_db"]})
    result = {
        "file": str(Path(bgm).name),
        "duration_sec": round(n, 1),
        "mean_rms_db": round(float(np.mean(rms_db)), 1),
        "flatness_p90": round(float(np.percentile(flat, 90)), 3),
        "anomalies": anomalies,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    (out_dir / "bgm_health.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    raw.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
