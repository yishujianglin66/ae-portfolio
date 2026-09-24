# -*- coding: utf-8 -*-
"""check_delivery_spec.py — 交付规格自检（AKROSS Con 口径，2026-09-09）

把"大师级不靠高码率、靠抗压缩的视觉设计"这条调研结论落成可执行自检：
对成片逐项核对 AKROSS Con 公开交付规格，输出 PASS / WARN / FAIL 与修复建议。

五项硬指标（依据 03-阶段报告/风格化制作深度调研与推进方案_2026-09-08.md §2.3）：
  1. 容器/编码  mp4 / H.264 / AAC
  2. 帧率       ≤ 30 fps
  3. 位深       8 bit
  4. 码率       ≈ 4 Mbps（允许区间，默认 2.5-6.0 Mbps）
  5. 时长       1-15 分钟（AMV 单曲域；短样片可 --min-duration 放宽）
另含两项工程检查：
  6. 台标/水印  边缘固定区域时序稳定性检测（HEURISTIC，非版权级识别）
  7. 音频       采样率/声道/削波峰值

安全约束：
  - 待检路径先经 resolve 校验：必须是已存在的普通文件、后缀 .mp4/.mov/.mkv/.webm；
  - 所有外部命令均以**参数列表 + shell=False** 调用，不经 shell 解析；
  - 路径作为独立 argv 元素传入，不作为命令字符串拼接。

设计取舍：
  - 只读探测，不改文件；退出码 0=全过 / 1=有 FAIL（可接 CI）。
  - 台标检测是启发式：真实台标是"固定位置、跨帧几乎不变"的叠加层，
    用边缘带的帧间方差 + 边缘能量双重判据；**会漏检半透明/动画水印**，
    结果标注 confidence，不宣称版权级判定。
  - 位深判定：ffprobe 的 pix_fmt 后缀（yuv420p=8bit / yuv420p10le=10bit）。

用法:
  python scripts/check_delivery_spec.py output/unified_run53/run53_MASTER_ACCEPTED.mp4
  python scripts/check_delivery_spec.py --glob "output/unified_run*/**/*.mp4" --summary
  python scripts/check_delivery_spec.py <file> --json reports/spec_run53.json
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parent.parent
FFPROBE = shutil.which("ffprobe") or "C:/ffmpeg/bin/ffprobe.exe"
FFMPEG = shutil.which("ffmpeg") or "C:/ffmpeg/bin/ffmpeg.exe"

ALLOWED_SUFFIXES = (".mp4", ".mov", ".mkv", ".webm", ".m4v")

# ---- AKROSS Con 交付规格（可调） ----
SPEC = {
    "container": "mp4",
    "vcodec": "h264",
    "acodec": "aac",
    "max_fps": 30.0,
    "bit_depth": 8,
    "bitrate_mbps": (2.5, 6.0),   # ≈4Mbps 的工程容差
    "bitrate_target": 4.0,
    "duration_sec": (60.0, 900.0),  # 1-15 分钟
}

# pix_fmt → 位深
_BIT_DEPTH = {
    "yuv420p": 8, "yuvj420p": 8, "yuv422p": 8, "yuv444p": 8,
    "yuv420p10le": 10, "yuv422p10le": 10, "yuv444p10le": 10,
    "yuv420p12le": 12, "gray": 8, "gray10le": 10, "gray12le": 12,
}


def safe_media_path(raw: str | Path) -> Path | None:
    """校验待检媒体路径：存在、普通文件、后缀白名单，返回 resolve 后的绝对路径。"""
    try:
        p = Path(raw).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    if not p.is_file():
        return None
    if p.suffix.lower() not in ALLOWED_SUFFIXES:
        return None
    return p


@dataclass
class Check:
    name: str
    status: str          # PASS / WARN / FAIL
    detail: str
    value: object = None
    expected: object = None
    mitigation: str = ""

    def as_dict(self) -> dict:
        d = {"name": self.name, "status": self.status, "detail": self.detail}
        if self.value is not None:
            d["value"] = self.value
        if self.expected is not None:
            d["expected"] = self.expected
        if self.mitigation:
            d["mitigation"] = self.mitigation
        return d


@dataclass
class Report:
    path: str
    checks: list = field(default_factory=list)
    probe: dict = field(default_factory=dict)

    @property
    def status(self) -> str:
        if any(c.status == "FAIL" for c in self.checks):
            return "FAIL"
        if any(c.status == "WARN" for c in self.checks):
            return "WARN"
        return "PASS"

    def as_dict(self) -> dict:
        return {"path": self.path, "status": self.status,
                "probe": self.probe,
                "checks": [c.as_dict() for c in self.checks]}


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    """统一的外部命令调用：参数列表 + 显式 shell=False，不经 shell 解析。"""
    return subprocess.run(cmd, capture_output=True, timeout=timeout,
                          shell=False, check=False)


def ffprobe(path: Path) -> dict:
    cmd = [FFPROBE, "-v", "error", "-print_format", "json",
           "-show_format", "-show_streams", str(path)]
    r = _run(cmd, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe 失败: {(r.stderr or b'')[:200]}")
    return json.loads(r.stdout or b"{}")


def parse_fps(s: str) -> float:
    try:
        num, den = s.split("/")
        return float(num) / float(den) if float(den) else 0.0
    except Exception:
        return 0.0


def bit_depth_of(pix_fmt: str) -> int | None:
    if not pix_fmt:
        return None
    if pix_fmt in _BIT_DEPTH:
        return _BIT_DEPTH[pix_fmt]
    m = re.search(r"(9|10|12|14|16)le|(9|10|12|14|16)be", pix_fmt)
    if m:
        return int(m.group(1) or m.group(2))
    return 8  # 默认 8bit 平面格式


def sample_frames(path: Path, n: int = 24, scale: int = 160) -> np.ndarray | None:
    """均匀抽 n 帧（灰度、缩小）用于台标检测。返回 (n, h, w)。"""
    try:
        dur = float(ffprobe(path).get("format", {}).get("duration", 0) or 0)
    except Exception:
        return None
    if dur <= 0:
        return None
    step = max(dur / (n + 1), 0.05)
    frames = []
    for i in range(1, n + 1):
        t = min(step * i, max(dur - 0.05, 0))
        cmd = [FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", str(path),
               "-frames:v", "1", "-vf", f"scale={scale}:-2", "-pix_fmt", "gray",
               "-f", "rawvideo", "-"]
        r = _run(cmd, timeout=60)
        if r.returncode != 0 or not r.stdout:
            continue
        arr = np.frombuffer(r.stdout, dtype=np.uint8)
        side = int(np.sqrt(arr.size))
        if side * side != arr.size:
            continue
        frames.append(arr.reshape(side, side))
    if len(frames) < 6:
        return None
    h = min(f.shape[0] for f in frames)
    w = min(f.shape[1] for f in frames)
    return np.stack([f[:h, :w] for f in frames]).astype(np.float32)


def detect_watermark(path: Path) -> tuple[str, str, dict]:
    """启发式台标检测：边缘固定区域时序稳定性 + 边缘能量。

    真实台标 = 固定位置、跨帧几乎不变的叠加层 → 帧间方差极低但梯度能量不低。
    返回 (status, detail, metrics)。
    """
    frames = sample_frames(path)
    if frames is None:
        return "WARN", "抽帧失败，跳过台标检测", {}
    n, h, w = frames.shape
    ch, cw = max(h // 6, 4), max(w // 6, 4)
    regions = {
        "tl": (slice(0, ch), slice(0, cw)),
        "tr": (slice(0, ch), slice(w - cw, w)),
        "bl": (slice(h - ch, h), slice(0, cw)),
        "br": (slice(h - ch, h), slice(w - cw, w)),
    }
    hits = {}
    for name, (ys, xs) in regions.items():
        sub = frames[:, ys, xs]
        temporal_std = float(sub.std(axis=0).mean())
        gy, gx = np.gradient(sub.mean(axis=0))
        edge_energy = float(np.sqrt(gy ** 2 + gx ** 2).mean())
        hits[name] = {"temporal_std": round(temporal_std, 2),
                      "edge_energy": round(edge_energy, 2)}
    mean_frame = frames.mean(axis=0)
    gy, gx = np.gradient(mean_frame)
    base_edge = float(np.hypot(gy, gx).mean())
    suspicious = [k for k, v in hits.items()
                  if v["temporal_std"] < 2.0 and v["edge_energy"] > base_edge * 0.5]
    metrics = {"base_edge_energy": round(base_edge, 2), "corners": hits,
               "suspicious_corners": suspicious}
    if suspicious:
        return ("WARN",
                f"边缘 {','.join(suspicious)} 区域疑似固定叠加层（启发式，需人工确认）",
                metrics)
    return "PASS", "边缘区域未见固定叠加层特征", metrics


def audio_levels_db(path: Path, duration: float) -> dict:
    """读音频电平（dBFS）。

    用 volumedetect 而非 astats：astats 的 "Peak level dB" 字段实测是**线性幅度**
    （0.0968 表示 -20dBFS 附近），命名有误导性；volumedetect 的 max_volume 才是
    真正的 dBFS 峰值，削波判定必须用它。
    """
    if duration <= 0:
        return {}
    cmd = [FFMPEG, "-v", "info", "-i", str(path), "-af", "volumedetect",
           "-f", "null", "-"]
    r = _run(cmd, timeout=300)
    txt = (r.stderr or b"").decode("utf-8", "replace")
    out = {}
    m = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", txt)
    if m:
        out["peak_dbfs"] = round(float(m.group(1)), 2)
    m = re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB", txt)
    if m:
        out["mean_dbfs"] = round(float(m.group(1)), 2)
    return out


def check_one(path: Path, spec: dict) -> Report:
    rep = Report(path=str(path))
    try:
        info = ffprobe(path)
    except Exception as e:
        rep.checks.append(Check("probe", "FAIL", str(e)))
        return rep

    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = info.get("format", {})
    dur = float(fmt.get("duration", 0) or 0)
    size_mb = float(fmt.get("size", 0) or 0) / 1024 / 1024
    fps = parse_fps(v.get("r_frame_rate", "0/1")) if v else 0.0
    vbps = float(v.get("bit_rate", 0) or 0) if v else 0.0
    if vbps <= 0 and dur > 0:
        vbps = size_mb * 8 * 1024 * 1024 / dur
    abps = float(a.get("bit_rate", 0) or 0) if a else 0.0
    total_mbps = (vbps + abps) / 1e6 if (vbps or abps) else 0.0
    depth = bit_depth_of(v.get("pix_fmt", "")) if v else None

    rep.probe = {
        "container": fmt.get("format_name", ""),
        "vcodec": (v or {}).get("codec_name"),
        "acodec": (a or {}).get("codec_name"),
        "width": (v or {}).get("width"), "height": (v or {}).get("height"),
        "fps": round(fps, 3), "pix_fmt": (v or {}).get("pix_fmt"),
        "bit_depth": depth,
        "video_mbps": round(vbps / 1e6, 3),
        "audio_kbps": round(abps / 1000, 1),
        "total_mbps": round(total_mbps, 3),
        "duration_sec": round(dur, 2), "size_mb": round(size_mb, 1),
        "sample_rate": (a or {}).get("sample_rate"),
        "channels": (a or {}).get("channels"),
    }

    # 1. 容器/编码
    cname = fmt.get("format_name", "")
    ok_c = spec["container"] in cname
    ok_v = (v or {}).get("codec_name") == spec["vcodec"]
    ok_a = (a or {}).get("codec_name") == spec["acodec"]
    rep.checks.append(Check(
        "容器/编码", "PASS" if (ok_c and ok_v and ok_a) else "FAIL",
        f"{cname} / {rep.probe['vcodec']} / {rep.probe['acodec']}",
        value=f"{rep.probe['vcodec']}+{rep.probe['acodec']}",
        expected=f"{spec['container']}/{spec['vcodec']}/{spec['acodec']}",
        mitigation="" if (ok_c and ok_v and ok_a) else
        "统一转封装: ffmpeg -i in -c:v libx264 -c:a aac -movflags +faststart out.mp4"))

    # 2. 帧率
    ok_fps = 0 < fps <= spec["max_fps"] + 0.01
    rep.checks.append(Check(
        "帧率", "PASS" if ok_fps else "FAIL", f"{fps:g} fps",
        value=round(fps, 3), expected=f"≤ {spec['max_fps']:g} fps",
        mitigation="" if ok_fps else "降帧: ffmpeg -i in -r 30 ..."))

    # 3. 位深
    ok_depth = depth == spec["bit_depth"]
    rep.checks.append(Check(
        "位深", "PASS" if ok_depth else "FAIL",
        f"{rep.probe['pix_fmt']} → {depth}bit" if depth else "未知",
        value=depth, expected=f"{spec['bit_depth']}bit",
        mitigation="" if ok_depth else "转 8bit: ffmpeg -i in -pix_fmt yuv420p ..."))

    # 4. 码率
    lo, hi = spec["bitrate_mbps"]
    if total_mbps <= 0:
        st, det = "WARN", "码率未知"
    elif lo <= total_mbps <= hi:
        st, det = "PASS", f"{total_mbps:.2f} Mbps（目标 {spec['bitrate_target']}）"
    elif total_mbps < lo:
        st, det = "WARN", f"{total_mbps:.2f} Mbps 低于 {lo} Mbps（抗压缩风险）"
    else:
        st, det = "WARN", f"{total_mbps:.2f} Mbps 高于 {hi} Mbps（AKROSS 口径：大师级不靠高码率）"
    rep.checks.append(Check(
        "码率", st, det, value=round(total_mbps, 3),
        expected=f"{lo}-{hi} Mbps",
        mitigation="" if st == "PASS" else
        f"两遍编码压到 ~{spec['bitrate_target']} Mbps: "
        f"ffmpeg -i in -c:v libx264 -b:v {int(spec['bitrate_target']*1000)}k -maxrate ..."))

    # 5. 时长
    dlo, dhi = spec["duration_sec"]
    ok_dur = dlo <= dur <= dhi
    rep.checks.append(Check(
        "时长", "PASS" if ok_dur else "WARN", f"{dur:.2f}s",
        value=round(dur, 2), expected=f"{dlo:g}-{dhi:g}s",
        mitigation="" if ok_dur else
        f"AKROSS 要求 1-15 分钟；短样片可用 --min-duration {int(dur)} 放宽"))

    # 5b. 音视频等长 (2026-09-19)
    # 事故背景: 20s/27s 集成片视频流分别只有 19.79s/25.33s, 而音轨为
    # 20.02s/27.00s。容器时长 = max(视频流, 音轨) 恰好达标, 五项硬指标全过,
    # 画面却在音乐结束前 1.67s 就没了 —— 本检查专门堵这个盲区。
    vdur = float((v or {}).get("duration", 0) or 0)
    adur = float((a or {}).get("duration", 0) or 0)
    gap = (adur - vdur) if (vdur > 0 and adur > 0) else 0.0
    if not a or vdur <= 0 or adur <= 0:
        av_status, av_detail = "WARN", "音/视频流时长不可测，跳过等长核对"
    elif abs(gap) <= spec.get("av_sync_tol", 0.15):
        av_status, av_detail = "PASS", f"视频 {vdur:.2f}s ≈ 音频 {adur:.2f}s"
    elif gap > 0:
        av_status = "FAIL"
        av_detail = (f"视频流 {vdur:.2f}s 短于音轨 {adur:.2f}s "
                     f"(差 {gap:.2f}s ≈ {round(gap * max(fps, 24))} 帧): "
                     f"画面提前结束")
    else:
        av_status = "WARN"
        av_detail = (f"视频流 {vdur:.2f}s 长于音轨 {adur:.2f}s "
                     f"(差 {-gap:.2f}s): 尾部无音乐")
    rep.probe["video_duration_sec"] = round(vdur, 2)
    rep.probe["audio_duration_sec"] = round(adur, 2)
    rep.checks.append(Check(
        "音视频等长", av_status, av_detail,
        value=round(gap, 3), expected=f"|Δ| ≤ {spec.get('av_sync_tol', 0.15)}s",
        mitigation="" if av_status == "PASS" else
        "查合成环节帧数: production_director 会打印 [帧数核对]/[拼接核对]; "
        "-f concat 流拷贝在输入参数不一致时会静默截断, 走 _concat_filter 兜底"))

    # 6. 台标/水印（启发式）
    wm_status, wm_detail, wm_metrics = detect_watermark(path)
    rep.checks.append(Check(
        "台标/水印(启发式)", wm_status, wm_detail,
        value=wm_metrics.get("suspicious_corners"),
        mitigation="" if wm_status == "PASS" else
        "人工复核四角；确认为台标则用 delogo/crop 去除"))

    # 7. 音频
    levels = audio_levels_db(path, dur) if a else {}
    peak = levels.get("peak_dbfs")
    a_issues = []
    if not a:
        a_issues.append("无音轨")
    if peak is not None and peak >= -0.1:
        a_issues.append(f"峰值 {peak} dBFS 削波")
    rep.probe["peak_dbfs"] = peak
    rep.probe["mean_dbfs"] = levels.get("mean_dbfs")
    rep.checks.append(Check(
        "音频", "PASS" if not a_issues else "WARN",
        (f"{rep.probe['sample_rate']}Hz/{rep.probe['channels']}ch, "
         f"峰值 {peak} dBFS" if a else "无音轨")
        + ("" if not a_issues else f" | {'; '.join(a_issues)}"),
        value=peak,
        mitigation="" if not a_issues else
        "削波: 混音 limiter 降到 0.88 并留 1dB headroom（run61 已定位真修点）"))

    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="待检视频（可多个）")
    ap.add_argument("--glob", default=None, help="glob 模式批量")
    ap.add_argument("--json", default=None, help="JSON 报告输出路径")
    ap.add_argument("--summary", action="store_true", help="只打印汇总表")
    ap.add_argument("--min-duration", type=float, default=None,
                    help="放宽时长下限（短样片用）")
    ap.add_argument("--bitrate-tolerance", type=float, default=None,
                    help="码率上界（Mbps），覆盖默认 6.0")
    args = ap.parse_args()

    spec = dict(SPEC)
    if args.min_duration is not None:
        spec["duration_sec"] = (args.min_duration, spec["duration_sec"][1])
    if args.bitrate_tolerance is not None:
        spec["bitrate_mbps"] = (spec["bitrate_mbps"][0], args.bitrate_tolerance)

    raw_targets: list[str] = list(args.paths)
    for p in args.paths:
        if Path(p).is_dir():
            raw_targets += [str(x) for x in sorted(Path(p).rglob("*.mp4"))]
    if args.glob:
        raw_targets += glob.glob(args.glob, recursive=True)

    targets: list[Path] = []
    skipped = 0
    for raw in raw_targets:
        p = safe_media_path(raw)
        if p is None:
            skipped += 1
            continue
        if p not in targets:
            targets.append(p)
    if skipped:
        print(f"[跳过] {skipped} 个路径未通过校验（不存在/非媒体后缀）")
    if not targets:
        print("无待检视频")
        return 1

    reports = []
    for t in targets:
        rep = check_one(t, spec)
        reports.append(rep)
        if not args.summary:
            print("=" * 78)
            print(f"{rep.status:>4}  {t}")
            print("-" * 78)
            for c in rep.checks:
                mark = {"PASS": "✓", "WARN": "!", "FAIL": "✗"}.get(c.status, "?")
                print(f"  [{mark}] {c.name:<18} {c.detail}")
                if c.mitigation and c.status != "PASS":
                    print(f"      → {c.mitigation}")
            print()

    if args.summary or len(reports) > 1:
        print("=" * 78)
        print(f"{'状态':<6}{'文件':<52}{'码率':>8}{'时长':>8}")
        print("-" * 78)
        for r in reports:
            p = r.probe
            print(f"{r.status:<6}{r.path[-50:]:<52}"
                  f"{p.get('total_mbps', 0):>8}{p.get('duration_sec', 0):>8}")
        n_pass = sum(1 for r in reports if r.status == "PASS")
        n_warn = sum(1 for r in reports if r.status == "WARN")
        n_fail = sum(1 for r in reports if r.status == "FAIL")
        print("-" * 78)
        print(f"PASS {n_pass} / WARN {n_warn} / FAIL {n_fail}（共 {len(reports)}）")

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "spec": spec,
            "results": [r.as_dict() for r in reports],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nJSON → {out}")

    return 1 if any(r.status == "FAIL" for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
