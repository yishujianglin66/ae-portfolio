"""separate_drums.py — E0-1 鼓点 stem 锚定链路（MasterCut 开源增强方案）

三阶段：
  Stage 1  MelBand RoFormer 4-stem（SYH99999 finetune, drums SDR 10.43）→ drums.wav
  Stage 2  drumsep（Hybrid Demucs 49469ca8, inagoy 2022）→ kick/snare/cymbals/toms.wav
  Stage 3  kick/snare onset 检测 → anchors.json（v23 编排引擎切点锚定原料）

用法：
  python scripts/separate_drums.py --bgm "D:/AE-Work/音频素材库/BGM/1_from10s.mp3"
  python scripts/separate_drums.py --bgm <path> --skip-stage2   # 只到 4-stem
  python scripts/separate_drums.py --bgm <path> --anchors-only  # 复用已有 stems 只算锚点

产物：cache/stems/<bgm_sha12>/  下 stems wav + anchors.json + provenance.json
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

MSST_DIR = Path(__file__).resolve().parent.parent / "tmp" / "msst" / "Music-Source-Separation-Training-main"
CKPT = Path("models/separation/MelBandRoformer4StemFTLarge.ckpt")  # 官方 LFS sha256=590358e6...4506 已终验
CFG = Path("models/separation/melband_4stem_config.yaml")
DRUMSEP_REPO = Path("models/separation/drumsep_repo")
MODEL_TYPE = "mel_band_roformer"
STEMS_4 = ["drums", "bass", "other", "vocals"]
STEMS_DRUM = ["kick", "snare", "cymbals", "toms"]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cache_dir_for(bgm: Path) -> Path:
    key = sha256_file(bgm)[:12]
    d = Path("cache/stems") / key
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- Stage 1
def run_stage1(bgm: Path, out_dir: Path, device_str: str) -> Path:
    drums_wav = out_dir / "drums.wav"
    if all((out_dir / f"{n}.wav").exists() and
           (out_dir / f"{n}.wav").stat().st_size > 44100 * 4 * 2 for n in STEMS_4):
        print(f"[stage1] 命中缓存: {out_dir}")
        return drums_wav
    assert MSST_DIR.exists(), f"MSST 代码缺失: {MSST_DIR}"
    assert CKPT.exists() and CFG.exists(), "melband ckpt/config 缺失（闸门1：存在性）"
    sys.path.insert(0, str(MSST_DIR))
    import librosa
    import numpy as np
    import soundfile as sf
    import torch
    import yaml
    from utils.model_utils import demix
    from utils.settings import get_model_from_config

    t0 = time.time()
    # config 含 !!python/tuple 标签，safe_load 不支持，MSST 官方同样用 full_load
    config = yaml.full_load(CFG.read_text(encoding="utf-8"))
    model, config = get_model_from_config(MODEL_TYPE, str(CFG))
    ckpt = torch.load(str(CKPT), map_location="cpu", weights_only=False)
    state = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else ckpt
    model.load_state_dict(state, strict=True)  # fail-loud：架构不匹配立即报错
    model = model.to(device_str).eval()
    print(f"[stage1] 模型加载 {time.time() - t0:.1f}s, device={device_str}")

    mix, sr = librosa.load(str(bgm), sr=44100, mono=False)
    if mix.ndim == 1:
        mix = np.stack([mix, mix])
    mix_t = torch.tensor(mix, dtype=torch.float32)
    with torch.no_grad():
        stems = demix(config=config, model=model, mix=mix_t,
                      device=torch.device(device_str), model_type=MODEL_TYPE, pbar=True)
    for name in STEMS_4:
        arr = stems[name] if isinstance(stems, dict) else stems[STEMS_4.index(name)]
        sf.write(str(out_dir / f"{name}.wav"),
                 arr.T if arr.shape[0] == 2 else arr, 44100)
        print(f"[stage1] {name}.wav 写出 ({(out_dir / f'{name}.wav').stat().st_size / 1e6:.1f}MB)")
    print(f"[stage1] 四声部完成, 耗时 {time.time() - t0:.0f}s")
    del model, stems
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return out_dir / "drums.wav"


# ---------------------------------------------------------------- Stage 2
def run_stage2(drums_wav: Path, out_dir: Path, device_str: str) -> dict:
    th = DRUMSEP_REPO / "49469ca8.th"
    assert th.exists(), f"drumsep 权重缺失: {th}（闸门1：存在性）"
    import librosa
    import numpy as np
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model as demucs_get_model

    out = {}
    if all((out_dir / f"{s}.wav").exists() for s in STEMS_DRUM):
        print("[stage2] 命中缓存")
        return {s: out_dir / f"{s}.wav" for s in STEMS_DRUM}
    t0 = time.time()
    # torch 2.6+ 默认 weights_only=True，而 drumsep 2022 权重是整对象 pickle。
    # 信任依据：SHA-256=aefaa854...（来源 inagoy/drumsep，已在 anchors.json 溯源登记）
    _orig_torch_load = torch.load

    def _load_trusted(*a, **kw):
        kw["weights_only"] = False
        return _orig_torch_load(*a, **kw)

    torch.load = _load_trusted
    try:
        model = demucs_get_model(name="49469ca8", repo=DRUMSEP_REPO)
    finally:
        torch.load = _orig_torch_load
    model.to(device_str).eval()
    audio, sr = librosa.load(str(drums_wav), sr=model.samplerate, mono=False)
    if audio.ndim == 1:
        audio = np.stack([audio, audio])
    wav = torch.tensor(audio, dtype=torch.float32)[None].to(device_str)
    scale = wav.abs().max().clamp_min(1e-6)
    with torch.no_grad():
        sources = apply_model(model, wav / scale,
                              device=device_str, shifts=0, overlap=0.25, progress=True)[0]
    sources = sources * scale
    for i, name in enumerate(STEMS_DRUM):
        p = out_dir / f"{name}.wav"
        sf.write(str(p), sources[i].cpu().numpy().T, model.samplerate)
        out[name] = p
    print(f"[stage2] 四分轨写出: {list(out)} (耗时 {time.time() - t0:.0f}s)")
    del model, sources
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return out


# ---------------------------------------------------------------- Stage 3
def extract_anchors(drum_stems: dict, out_dir: Path, bgm: Path) -> Path:
    import librosa
    import numpy as np

    sr = 44100
    anchors = {"schema": "drum_anchors_v2", "bgm": str(bgm), "sr": sr,
               "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
               "models": {
                   "melband_4stem": {"sha256": sha256_file(CKPT)[:16],
                                     "source": "hf:SYH99999/MelBandRoformer4StemFTLarge", "license": "apache-2.0"},
                   "drumsep": {"sha256": sha256_file(DRUMSEP_REPO / "49469ca8.th")[:16],
                               "source": "inagoy/drumsep (gdrive 1-Dm666ScPkg8Gt2-lK3Ua0xOudWHZBGC)", "license": "MIT"}},
               }
    for name in ("kick", "snare"):
        y, _ = librosa.load(str(drum_stems[name]), sr=sr, mono=True)
        env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=256)
        peaks = librosa.util.peak_pick(
            env, pre_max=8, post_max=8, pre_avg=20, post_avg=20, delta=0.6, wait=8)
        times = librosa.frames_to_time(peaks, sr=sr, hop_length=256)
        strengths = [round(float(env[p] / (env.max() + 1e-9)), 3) for p in peaks]
        anchors[f"{name}_onsets"] = [[round(float(t), 3), s] for t, s in zip(times, strengths)]
        anchors[f"num_{name}"] = len(times)
        print(f"[stage3] {name}: {len(times)} 个重音 onset")

    # ── v2 旋律锚 (2026-09-05 用户听感反馈: 高潮段没卡小提琴节奏变换/重音) ──
    # other 声部 = 干净的旋律乐器(小提琴)，混音里低音主导的问题被 stem 分离
    # 根除——v9 时代 pyin F0 被低音淹没("检测路线全堵死"注释)。旋律锚 =
    # 攻击音(onset) + 音高变化点(pyin ≥35 音分，v9 同款阈值) 合并去重。
    try:
        yo, _ = librosa.load(str(out_dir / "other.wav"), sr=sr, mono=True)
        # 攻击音
        menv = librosa.onset.onset_strength(y=yo, sr=sr, hop_length=256)
        mpeaks = librosa.util.peak_pick(
            menv, pre_max=6, post_max=6, pre_avg=16, post_avg=16, delta=0.35, wait=6)
        mtimes = librosa.frames_to_time(mpeaks, sr=sr, hop_length=256)
        mrms = librosa.feature.rms(y=yo, frame_length=2048, hop_length=256)[0]
        mrms_t = librosa.frames_to_time(np.arange(len(mrms)), sr=sr, hop_length=256)
        m_strength = []
        for t in mtimes:
            _i = min(int(t * sr / 256), len(mrms) - 1)
            _win = mrms[max(0, _i - 40):_i + 40]
            m_strength.append(round(float(mrms[_i] / (_win.max() + 1e-9)), 3))
        # 音高变化点 (pyin, 小提琴频段, v9 同款 35 音分阈值)
        f0, _, _ = librosa.pyin(yo, fmin=196, fmax=2000, sr=sr,
                                frame_length=2048, hop_length=256)
        from scipy.signal import medfilt
        f0s = medfilt(np.nan_to_num(f0, nan=0.0), 5)
        voiced = f0s > 150
        cents = np.full(len(f0s), 0.0)
        ok = voiced[1:] & voiced[:-1] & (f0s[:-1] > 150)
        cents[1:][ok] = 1200 * np.log2(f0s[1:][ok] / f0s[:-1][ok])
        chg = np.where(np.abs(cents) >= 35)[0]
        ptimes = [float(c * 256 / sr) for c in chg]
        # 攻击 + 音变合并去重 (80ms)
        allm = sorted(set([round(float(t), 3) for t in mtimes] +
                          [round(t, 3) for t in ptimes]))
        merged, prev = [], -1.0
        for m3 in allm:
            if m3 - prev >= 0.08:
                merged.append(m3)
                prev = m3
        s_lookup = dict(zip([round(float(t), 3) for t in mtimes], m_strength))
        anchors["melody_onsets"] = [[t, s_lookup.get(t, 0.5)] for t in merged
                                    if t < 30.5]
        anchors["num_melody"] = len(merged)
        anchors["melody_env"] = [[round(float(t), 2), round(float(v), 4)]
                                 for t, v in zip(mrms_t[::40], mrms[::40])]
        anchors["schema_note"] = ("v2: +melody_onsets(小提琴攻击音+pyin音变点, "
                                  "other声部)/melody_env(谐波RMS包络)")
        print(f"[stage3] melody: 攻击{len(mtimes)} + 音变{len(ptimes)}"
              f" = {len(merged)} 个（other 声部 pyin，无低音污染）")
    except Exception as exc:  # noqa: BLE001
        anchors["melody_onsets"] = []
        print(f"[stage3] 旋律锚提取失败(管线回退纯鼓锚): {exc}")

    p = out_dir / "anchors.json"
    p.write_text(json.dumps(anchors, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage3] 锚点写入: {p}")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bgm", required=True)
    ap.add_argument("--skip-stage2", action="store_true")
    ap.add_argument("--anchors-only", action="store_true")
    ap.add_argument("--device", default=None, help="cuda / cpu，缺省自动")
    args = ap.parse_args()

    bgm = Path(args.bgm)
    assert bgm.exists(), f"BGM 不存在: {bgm}"
    import torch
    device_str = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    out_dir = cache_dir_for(bgm)
    print(f"[main] bgm={bgm.name} cache={out_dir} device={device_str}")

    t0 = time.time()
    if args.anchors_only:
        drum_stems = {s: out_dir / f"{s}.wav" for s in STEMS_DRUM}
        missing = [s for s, p in drum_stems.items() if not p.exists()]
        assert not missing, f"anchors-only 但缺 stems: {missing}"
    else:
        drums_wav = run_stage1(bgm, out_dir, device_str)
        drum_stems = run_stage2(drums_wav, out_dir, device_str) if not args.skip_stage2 else {}
    if drum_stems:
        extract_anchors(drum_stems, out_dir, bgm)
    print(f"[main] 完成, 总耗时 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
