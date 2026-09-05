# -*- coding: utf-8 -*-
"""谱通量真实 onset 检测 — 供 build_master_polish 锚定 TWX 冻结点

引擎切点网格来自 0.6s 平滑的能量包络, 峰值可偏离真实 kick ±0.3s;
本脚本用谱通量 (无平滑滞后) 检出真实 onset + 强度, 存 tmp/true_onsets.json。
"""
import json
import subprocess
import sys

import numpy as np

SR, HOP = 22050, 256


def detect_onsets(bgm):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', bgm, '-ac', '1', '-ar', str(SR),
                        '-f', 'f32le', '-'], capture_output=True, timeout=120)
    y = np.frombuffer(r.stdout, dtype=np.float32)
    n = len(y) // HOP
    S = np.abs(np.stack([np.abs(np.fft.rfft(y[i*HOP:(i+1)*HOP] * np.hanning(HOP)))
                         for i in range(n)]))
    flux = np.maximum(0, np.diff(S, axis=0)).sum(axis=1)
    flux = np.convolve(flux, np.ones(5) / 5, mode='same')
    th = flux.mean() + 1.2 * flux.std()
    out = []
    for i in range(2, len(flux) - 2):
        if flux[i] > th and flux[i] >= flux[i-1] and flux[i] >= flux[i+1]:
            t = i * HOP / SR
            if not out or t - out[-1][0] > 0.12:
                out.append((round(t, 3), round(float(flux[i]), 1)))
    return out


if __name__ == '__main__':
    bgm = sys.argv[1] if len(sys.argv) > 1 else 'D:/AE-Work/音频素材库/BGM/1_from10s.mp3'
    ons = detect_onsets(bgm)
    json.dump([{'t': t, 's': s} for t, s in ons],
              open('tmp/true_onsets.json', 'w'))
    print(f'onsets: {len(ons)} ({len(ons)/30:.1f}/s) -> tmp/true_onsets.json')
    for t, s in ons:
        if 18.9 <= t <= 27.6:
            print(f'  {t:7.3f}  flux={s}')
