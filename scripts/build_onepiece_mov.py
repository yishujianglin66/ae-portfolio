"""海贼王 mask → BGRA 序列 → qtrle MOV + QC。单文件脚本。"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
PROJECT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
WORK_DIR = PROJECT / "output" / "rerun_anime_autoframe" / "DL_海贼王_r84_BV14tZNYGEuV"
MASK_DIR = WORK_DIR / "DL_海贼王_r84_BV14tZNYGEuV_masks"
SRC_MP4 = PROJECT / "data" / "real_amv_test" / "DL_海贼王_r84_BV14tZNYGEuV.mp4"
ALPHA_DIR = WORK_DIR / "alpha_bgra_merge"
MOV_OUT = WORK_DIR / "DL_海贼王_r84_BV14tZNYGEuV_alpha.mov"
QC_JSON = PROJECT / "output" / "DL_海贼王_r84_BV14tZNYGEuV_qc_v2.json"
FPS = 24  # 先用 24，若视频不同再调
EXPECTED_FRAMES = 10126


def count_masks() -> int:
    if not MASK_DIR.exists(): return 0
    return sum(1 for _ in MASK_DIR.glob("mask_*.png"))


def get_source_res():
    cmd = [FFMPEG.replace('ffmpeg.exe','ffprobe.exe'), '-v','error',
           '-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_read_frames',
           '-of','json', str(SRC_MP4)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    try:
        d = json.loads(p.stdout)
        s = d['streams'][0]
        w, h = int(s.get('width',0)), int(s.get('height',0))
        rf = s.get('r_frame_rate','24/1')
        a,b = rf.split('/')
        fps = round(int(a)/max(1,int(b)), 2)
        nf = int(s.get('nb_read_frames') or 0)
        return w, h, fps, nf
    except Exception as e:
        print(f"[WARN] ffprobe 失败: {e}", file=sys.stderr)
        return 0, 0, 24.0, 0


def gen_bgra(expected: int, w: int, h: int, log_every: int = 500) -> tuple[int, float]:
    ALPHA_DIR.mkdir(parents=True, exist_ok=True)
    # 清理已有
    for old in ALPHA_DIR.glob("frame_*.png"):
        try: old.unlink()
        except Exception: pass
    t0 = time.time()
    ok = 0
    src_cap = cv2.VideoCapture(str(SRC_MP4))
    if not src_cap.isOpened():
        print(f"[FATAL] 无法打开 src: {SRC_MP4}"); return 0, 0
    fi = 0
    while fi < expected:
        ret, frame = src_cap.read()
        if not ret or frame is None:
            print(f"[WARN] src read EOF at fi={fi}")
            break
        mp = MASK_DIR / f"mask_{fi:05d}.png"
        mask = None
        if mp.exists():
            buf = np.fromfile(str(mp), dtype=np.uint8)
            if buf.size > 0:
                mask = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            mask = np.zeros((frame.shape[0], frame.shape[1]), dtype=np.uint8)
        if mask.shape[:2] != frame.shape[:2]:
            mask = cv2.resize(mask, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_NEAREST)
        bgr = frame
        a = mask.astype(np.uint8)
        bgra = np.dstack([bgr, a])  # H,W,4 (B,G,R,A)
        out_p = ALPHA_DIR / f"frame_{fi:05d}.png"
        ok_enc, buf = cv2.imencode(".png", bgra, [int(cv2.IMWRITE_PNG_COMPRESSION), 1])
        if ok_enc:
            buf.tofile(str(out_p))
            ok += 1
        fi += 1
        if fi % log_every == 0:
            print(f"  BGRA: {fi}/{expected}  ok={ok}  elapsed={time.time()-t0:.0f}s  fps={fi/max(0.01,time.time()-t0):.1f}")
    src_cap.release()
    print(f"BGRA 完成: {ok}/{expected}  elapsed={time.time()-t0:.0f}s")
    return ok, time.time() - t0


def encode_mov(total_frames: int, fps: float) -> tuple[int, int]:
    if MOV_OUT.exists():
        try: MOV_OUT.unlink()
        except Exception: pass
    cmd = [
        FFMPEG, '-hide_banner', '-loglevel', 'error', '-stats', '-y',
        '-framerate', str(fps),
        '-start_number', '0',
        '-i', str(ALPHA_DIR / 'frame_%05d.png'),
        '-c:v', 'qtrle', '-pix_fmt', 'yuva444p10le',
        str(MOV_OUT),
    ]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=False, timeout=4*3600)
    elapsed = time.time() - t0
    size_mb = int(MOV_OUT.stat().st_size/1024/1024) if MOV_OUT.exists() else 0
    print(f"FFmpeg qtrle: rc={p.returncode} size_mb={size_mb} elapsed={elapsed:.0f}s")
    return p.returncode, size_mb


def sample_qc_mov(samples: int = 30) -> dict:
    """FFmpeg 抽 30 PNG → cv2 imdecode alpha 求非空率。"""
    meta = {}
    # stream info
    info = subprocess.run([FFMPEG, '-hide_banner', '-i', str(MOV_OUT)], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60).stderr or ''
    for line in info.splitlines():
        if 'Stream #0:' in line and 'Video:' in line:
            meta['video_stream'] = line.strip()
            for key in ['argb','rgba','yuva','bgra','abgr']:
                if key in line.lower():
                    meta['has_alpha_pixfmt'] = True
                    break
    # 抽帧样本
    import tempfile
    tmpd = Path(tempfile.mkdtemp(prefix="qconepiece_", dir=str(PROJECT / "output")))
    # 等间距 sample 帧号（0..N-1）
    total = EXPECTED_FRAMES
    idxs = np.linspace(0, total - 1, min(samples, total), dtype=int).tolist()
    ratios = []
    ne = 0
    try:
        for i, idx in enumerate(idxs):
            out = tmpd / f"s{i:02d}_idx{idx:05d}.png"
            cmd = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y',
                   '-vf', f"select=eq(n\\,{idx})", '-frames:v', '1',
                   '-i', str(MOV_OUT), str(out)]
            r = subprocess.run(cmd, capture_output=True, timeout=120)
            if r.returncode != 0 or not out.exists(): continue
            buf = np.fromfile(str(out), dtype=np.uint8)
            if buf.size == 0: continue
            img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
            if img is None or img.ndim<3 or img.shape[2]<4:
                ratios.append(0.0); continue
            a = img[:, :, 3]
            nz = int(np.count_nonzero(a))
            total_px = int(a.shape[0]*a.shape[1])
            r = nz/total_px if total_px>0 else 0.0
            ratios.append(r)
            if r > 1e-4: ne += 1
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)
    while len(ratios) < len(idxs):
        ratios.append(0.0)
    avg = float(np.mean(ratios)) if ratios else 0.0
    return {
        "sampled": len(ratios),
        "nonempty_sample_frames": ne,
        "avg_alpha_ratio": avg,
        "per_frame": ratios,
        "meta": meta,
    }


def main():
    print("="*70)
    print("海贼王 MOV 合成 + QC")
    print("="*70)
    masks = count_masks()
    print(f"mask count: {masks} / {EXPECTED_FRAMES}")
    if masks < int(EXPECTED_FRAMES * 0.95):
        print(f"[WARN] mask 不足，继续？ masks={masks}")
    w, h, fps, nf = get_source_res()
    print(f"src: {w}x{h} fps={fps} ffprobe_frames={nf}")
    if fps <= 0: fps = 24.0
    total = nf if nf > EXPECTED_FRAMES * 0.8 else EXPECTED_FRAMES
    print(f"expected_total_frames (use): {total}")
    # Step 1: BGRA 序列
    t1 = time.time()
    bgra_ok, bgra_s = gen_bgra(total, w, h)
    # Step 2: qtrle MOV
    rc, mb = encode_mov(total, fps)
    # Step 3: QC
    qc = {"status": "skip"}
    if rc == 0 and MOV_OUT.exists() and bgra_ok >= total*0.9:
        qc = sample_qc_mov(30)
        report = {
            "name": "DL_海贼王_r84_BV14tZNYGEuV",
            "src": str(SRC_MP4),
            "masks": masks,
            "bgra_frames": bgra_ok,
            "expected_frames": total,
            "resolution": f"{w}x{h}",
            "fps": fps,
            "mov_path": str(MOV_OUT),
            "mov_size_mb": mb,
            "mov_rc": rc,
            "qtrle_pixfmt_ok": qc.get("meta", {}).get("has_alpha_pixfmt", False),
            "avg_alpha_ratio": qc.get("avg_alpha_ratio", 0),
            "nonempty_samples": f"{qc.get('nonempty_sample_frames',0)}/{qc.get('sampled',0)}",
            "per_frame_alpha_ratio_first6": [round(r,4) for r in qc.get("per_frame",[])[:6]],
            "per_frame_alpha_ratio_last6": [round(r,4) for r in qc.get("per_frame",[])[-6:]],
            "timing_s": {"bgra_gen": round(bgra_s,1), "total_elapsed": round(time.time()-t1,1)},
        }
        with open(QC_JSON, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 报告已保存 -> {QC_JSON}")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[FAIL] MOV 失败: rc={rc} bgra={bgra_ok}/{total}")
    print(f"\n总耗时: {time.time()-t1:.0f}s")


if __name__ == "__main__":
    main()
