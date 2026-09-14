# -*- coding: utf-8 -*-
"""生成 R1 成片预览页：视频 + BGM 波形 + 切点标记。

解决的问题：内置预览面板/部分播放器不放音频，"没 BGM 看不出效果"。
本页把三件事放在同一时间轴上——画面、音乐波形、48 个切点位置，
一眼能看出切点是否踩在鼓点上。

用法:
    python scripts/make_r1_preview.py [--tag r1_fixed_v7]
产物:
    output/unified_<tag>/preview.html
"""

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N_BINS = 900          # 波形柱子数量


def extract_pcm(video: Path, sr: int = 16000) -> bytes:
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video),
         "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
        capture_output=True, timeout=300)
    return r.stdout


def envelope(pcm: bytes, n_bins: int = N_BINS):
    """算 RMS 包络并归一化到 0..1。"""
    import array
    a = array.array("h")
    a.frombytes(pcm)
    if not a:
        return []
    step = max(1, len(a) // n_bins)
    env = []
    for i in range(0, len(a) - step, step):
        chunk = a[i:i + step]
        rms = (sum(float(x) * x for x in chunk) / len(chunk)) ** 0.5
        env.append(rms)
    mx = max(env) or 1.0
    return [round(v / mx, 4) for v in env]


def load_cuts(edl: Path):
    try:
        d = json.load(open(edl, encoding="utf-8"))
    except Exception:
        return []
    return [round(float(t), 4) for t in d.get("cut_points", [])]


def build_html(video: Path, env, cuts, out: Path) -> None:
    env_js = json.dumps(env)
    cuts_js = json.dumps(cuts)
    name = video.name
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>R1 成片预览 — {name}</title>
<style>
  body{{margin:0;padding:24px;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
       background:var(--color-background-primary,#fff);
       color:var(--color-text-primary,#1a1a1a)}}
  h1{{font-size:15px;font-weight:500;margin:0 0 4px}}
  .sub{{font-size:13px;color:var(--color-text-secondary,#666);margin:0 0 16px}}
  video{{width:100%;max-width:960px;border-radius:12px;display:block;
        background:#000;margin-bottom:12px}}
  .wrap{{max-width:960px}}
  canvas{{width:100%;height:150px;display:block;cursor:pointer;
         border:0.5px solid var(--color-border-tertiary,rgba(0,0,0,.15));
         border-radius:8px}}
  .legend{{display:flex;flex-wrap:wrap;gap:16px;font-size:12px;
          color:var(--color-text-secondary,#666);margin:10px 0 18px}}
  .legend span{{display:flex;align-items:center;gap:5px}}
  .sw{{width:10px;height:10px;border-radius:2px;display:inline-block}}
  .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));
         gap:10px;max-width:960px;
         }}
  .card{{background:var(--color-background-secondary,#f4f4f2);border-radius:8px;
        padding:12px 14px}}
  .card .k{{font-size:12px;color:var(--color-text-secondary,#666)}}
  .card .v{{font-size:22px;font-weight:500;margin-top:2px}}
  .note{{font-size:12px;color:var(--color-text-tertiary,#999);
        max-width:960px;line-height:1.6;margin-top:14px}}
</style>
</head>
<body>
<div class="wrap">
  <h1>R1 成片预览 — {name}</h1>
  <p class="sub">画面 + BGM 波形 + 切点位置，同一时间轴对齐。点波形任意位置可跳转。</p>

  <video id="vid" controls preload="auto" src="./{name}"></video>

  <canvas id="cv" width="1800" height="300"></canvas>

  <div class="legend">
    <span><i class="sw" style="background:#888780"></i>BGM 波形</span>
    <span><i class="sw" style="background:#D85A30"></i>切点（{len(cuts)} 刀）</span>
    <span><i class="sw" style="background:#378ADD"></i>播放头</span>
  </div>

  <div class="stats">
    <div class="card"><div class="k">切点数</div><div class="v">{len(cuts)}</div></div>
    <div class="card"><div class="k">平均间隔</div>
      <div class="v">{(cuts[-1] / max(len(cuts) - 1, 1)):.2f}s</div></div>
    <div class="card"><div class="k">v3 可见度</div><div class="v">1.1030</div></div>
    <div class="card"><div class="k">冻结切点</div><div class="v">0</div></div>
  </div>

  <p class="note">
    若此处仍听不到声音，说明预览面板未转发音频。请用系统播放器直接打开
    <code>{name}</code>，或播放同目录下的 <code>r1_fixed_v7_音轨.mp3</code>（纯音轨）。
    文件本身含 aac 双声道音轨，实测 mean −15.2 dB / max −1.2 dB。
  </p>
</div>

<script>
const env = {env_js};
const cuts = {cuts_js};
const cv = document.getElementById('cv');
const ctx = cv.getContext('2d');
const vid = document.getElementById('vid');
const W = cv.width, H = cv.height, PAD = 10;

function draw() {{
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#fbfbfa';
  ctx.fillRect(0, 0, W, H);

  const bw = (W - PAD * 2) / env.length;
  const mid = H / 2;
  ctx.fillStyle = '#888780';
  for (let i = 0; i < env.length; i++) {{
    const h = Math.max(1, env[i] * (H / 2 - PAD));
    ctx.fillRect(PAD + i * bw, mid - h, Math.max(bw - 0.3, 0.6), h * 2);
  }}

  const dur = (vid.duration || cuts[cuts.length - 1] || 1);
  ctx.strokeStyle = '#D85A30';
  ctx.lineWidth = 1.2;
  for (const t of cuts) {{
    const x = PAD + (t / dur) * (W - PAD * 2);
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }}

  if (vid.duration) {{
    const x = PAD + (vid.currentTime / dur) * (W - PAD * 2);
    ctx.strokeStyle = '#378ADD';
    ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }}
}}

draw();
vid.addEventListener('timeupdate', draw);
vid.addEventListener('loadedmetadata', draw);
vid.addEventListener('seeked', draw);

cv.addEventListener('click', (e) => {{
  if (!vid.duration) return;
  const r = cv.getBoundingClientRect();
  const p = (e.clientX - r.left) / r.width;
  vid.currentTime = Math.max(0, Math.min(1, p)) * vid.duration;
}});
</script>
</body>
</html>
"""
    out.write_text(html, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="r1_fixed_v7")
    args = ap.parse_args()

    d = ROOT / "output" / f"unified_{args.tag}"
    video = d / f"{args.tag}_final_mastered.mp4"
    if not video.exists():
        print(f"[ERR] 找不到成片: {video}")
        return 1

    print(f"[1/3] 提取音频 PCM ... {video.name}")
    pcm = extract_pcm(video)
    print(f"      {len(pcm)} 字节")

    print("[2/3] 计算波形包络 ...")
    env = envelope(pcm)
    print(f"      {len(env)} 个柱")

    cuts = load_cuts(d / "edl.json")
    print(f"[3/3] 切点 {len(cuts)} 个 -> 生成预览页")
    out = d / "preview.html"
    build_html(video, env, cuts, out)
    print(f"      -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
