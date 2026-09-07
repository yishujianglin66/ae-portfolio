# -*- coding: utf-8 -*-
r"""T31: 多IP语料工厂 — 从视频到VLM标注的全自动多IP管线。

将现有的单IP管线(corpus_factory + t26c_vlm_concurrent)泛化为多IP版本:
  1. 读取IP配置(config/multi_ip_corpus.json)
  2. 对每个IP: 扫描视频→场景切镜头→关键帧提取
  3. 对每个IP: VLM并发标注(复用t26c逻辑)
  4. 合并所有IP的VLM标注数据→merged_vlm.jsonl

用法:
  # 步骤1: 生成配置模板
  python -m ai.t31_multi_ip_corpus --init-config

  # 步骤2: 帧提取(可断点续传)
  python -m ai.t31_multi_ip_corpus --extract-frames [--ip <ip_name>]

  # 步骤3: VLM标注(可断点续传, 建议独立进程)
  python -m ai.t31_multi_ip_corpus --vlm-annotate [--ip <ip_name>]

  # 步骤4: 合并所有IP数据
  python -m ai.t31_multi_ip_corpus --merge

  # 一键全流程(帧提取→VLM→合并)
  python -m ai.t31_multi_ip_corpus --all

数据布局:
  D:\multi_ip_corpus\
  ├── {ip_name}\
  │   ├── videos\       (符号链接或手动放入视频)
  │   ├── frames\       (提取的关键帧)
  │   ├── corpus_meta.json
  │   ├── state.json
  │   ├── vlm_results.jsonl
  │   └── vlm_ckpt.json
  └── merged_vlm.jsonl  (合并后)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"
CORPUS_BASE = Path(r"D:\multi_ip_corpus")
CONFIG_PATH = ROOT / "config" / "multi_ip_corpus.json"

# 推荐的新IP列表(按热度和画风多样性排序)
RECOMMENDED_IPS = {
    "chainsaw_man": {
        "name_cn": "电锯人",
        "name_en": "Chainsaw Man",
        "video_dirs": [],  # 用户填入视频目录
        "style": "dark_fantasy_modern",
    },
    "demon_slayer": {
        "name_cn": "鬼灭之刃",
        "name_en": "Demon Slayer",
        "video_dirs": [],
        "style": "taisho_romantic",
    },
    "jujutsu_kaisen": {
        "name_cn": "咒术回战",
        "name_en": "Jujutsu Kaisen",
        "video_dirs": [],
        "style": "dark_modern",
    },
    "spy_family": {
        "name_cn": "间谍过家家",
        "name_en": "Spy x Family",
        "video_dirs": [],
        "style": "comedy_soft",
    },
    "my_hero_academia": {
        "name_cn": "我的英雄学院",
        "name_en": "My Hero Academia",
        "video_dirs": [],
        "style": "shonen_bright",
    },
    "fate_stay_night": {
        "name_cn": "Fate/stay night",
        "name_en": "Fate/stay night",
        "video_dirs": [],
        "style": "fantasy_ufotable",
    },
    "one_piece": {
        "name_cn": "海贼王",
        "name_en": "One Piece",
        "video_dirs": [],
        "style": "adventure_shonen",
    },
    "blue_lock": {
        "name_cn": "蓝色监狱",
        "name_en": "Blue Lock",
        "video_dirs": [],
        "style": "sports_dynamic",
    },
    "oshi_no_ko": {
        "name_cn": "推しの子",
        "name_en": "Oshi no Ko",
        "video_dirs": [],
        "style": "idol_drama",
    },
}


def _log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[T31 {ts}] {msg}", flush=True)


# ── 配置管理 ──────────────────────────────────────────────

def init_config():
    """生成配置模板"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        _log(f"配置已存在: {CONFIG_PATH}")
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        _log(f"  已配置 {len(data.get('ips', {}))} 个IP")
        for k, v in data["ips"].items():
            n_dirs = len(v.get("video_dirs", []))
            _log(f"    {k}: {v.get('name_cn', '?')} ({n_dirs}个视频目录)")
        return data

    config = {"ips": RECOMMENDED_IPS, "settings": {
        "fps_thr": 0.35,       # 场景检测阈值
        "max_width": 640,      # 帧缩放宽度
        "jpeg_quality": 82,    # JPEG质量
        "vlm_workers": 16,     # VLM并发线程数
        "vlm_model": "Qwen/Qwen3-VL-8B-Instruct",
        "min_frames_per_ip": 1000,  # 最低帧数要求
    }}
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"配置模板已生成: {CONFIG_PATH}")
    _log(f"包含 {len(RECOMMENDED_IPS)} 个推荐IP")
    _log("请编辑配置文件, 填入各IP的视频目录路径")
    return config


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        _log("配置文件不存在, 先生成模板...")
        return init_config()
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


# ── 帧提取 ────────────────────────────────────────────────

def probe_duration(path: str) -> float:
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30
        )
        return float(r.stdout.strip()) if r.returncode == 0 else 0
    except Exception:
        return 0


def detect_scenes(video_path: str, thr: float = 0.35) -> List[float]:
    try:
        r = subprocess.run(
            [FFMPEG, "-i", video_path, "-vf", f"select='gt(scene,{thr})'",
             "-show_entries", "frame=pts_time", "-of", "csv=p=0",
             "-loglevel", "error"],
            capture_output=True, text=True, timeout=300
        )
        times = [float(l.strip()) for l in r.stdout.strip().split("\n") if l.strip()]
        return sorted(times)
    except Exception:
        return []


def extract_keyframes(video_path: str, shots: List[tuple], vid_id: str,
                      ip_dir: Path, settings: dict) -> List[dict]:
    """从镜头段提取关键帧"""
    frames_dir = ip_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    max_w = settings.get("max_width", 640)
    q = settings.get("jpeg_quality", 82)
    frames = []

    for si, (t_in, t_out) in enumerate(shots):
        dur = t_out - t_in
        if dur < 0.4:
            continue
        for frac in (0.33, 0.67):
            t = t_in + dur * frac
            fname = f"{vid_id}_s{si:03d}_{int(frac*100)}.jpg"
            fpath = frames_dir / fname
            if fpath.exists():
                continue
            try:
                subprocess.run(
                    [FFMPEG, "-y", "-loglevel", "error", "-ss", f"{t:.3f}",
                     "-i", video_path, "-frames:v", "1",
                     "-vf", f"scale={max_w}:-1", "-q:v", str(q),
                     str(fpath)],
                    capture_output=True, timeout=60
                )
                if fpath.exists() and fpath.stat().st_size > 500:
                    frames.append({
                        "frame": str(fpath), "shot": si,
                        "t": round(t, 3), "t_in": round(t_in, 3),
                        "t_out": round(t_out, 3),
                    })
            except Exception:
                pass
    return frames


def extract_frames_for_ip(ip_name: str, ip_config: dict, settings: dict):
    """为单个IP提取关键帧"""
    ip_dir = CORPUS_BASE / ip_name
    ip_dir.mkdir(parents=True, exist_ok=True)

    state_path = ip_dir / "state.json"
    meta_path = ip_dir / "corpus_meta.json"

    # 断点续传
    state = {"done": {}, "frames_total": 0}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))

    meta = {"ip": ip_name, "name_cn": ip_config.get("name_cn", ip_name),
            "videos": [], "frames_total": 0}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    video_dirs = ip_config.get("video_dirs", [])
    if not video_dirs:
        _log(f"  [{ip_name}] 无视频目录, 跳过")
        return

    # 扫描视频
    vids = []
    for vd in video_dirs:
        vd_p = Path(vd)
        if not vd_p.exists():
            _log(f"  目录不存在: {vd}")
            continue
        for p in sorted(vd_p.rglob("*")):
            if p.suffix.lower() in (".mkv", ".mp4", ".mov") and p.is_file():
                vids.append({"path": str(p), "name": p.stem})

    _log(f"  [{ip_name}] 扫描到 {len(vids)} 个视频")

    thr = settings.get("fps_thr", 0.35)
    new_frames = 0

    for vi, v in enumerate(vids):
        if v["name"] in state["done"]:
            continue

        duration = probe_duration(v["path"])
        if duration <= 0:
            _log(f"  [{vi+1}] 无法探测时长: {v['name'][:50]}")
            continue

        scenes = detect_scenes(v["path"], thr)
        # 构建镜头段
        boundaries = [0.0] + scenes + [duration]
        shots = []
        for j in range(len(boundaries) - 1):
            t0, t1 = boundaries[j], boundaries[j + 1]
            if t1 - t0 >= 0.4 and t1 - t0 <= 20:
                shots.append((t0, t1))
            elif t1 - t0 > 20:
                # 长镜头细分
                for k in range(int((t1 - t0) // 10)):
                    shots.append((t0 + k * 10, min(t0 + (k + 1) * 10, t1)))

        vid_id = f"{ip_name[:3]}_{vi:03d}"
        frames = extract_keyframes(v["path"], shots, vid_id, ip_dir, settings)

        meta["videos"].append({
            "vid": vid_id, "name": v["name"], "path": v["path"],
            "duration": round(duration, 2), "n_shots": len(shots),
            "frames": len(frames),
        })
        state["done"][v["name"]] = {"frames": len(frames)}
        new_frames += len(frames)
        state["frames_total"] = state.get("frames_total", 0) + len(frames)
        meta["frames_total"] = state["frames_total"]

        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        _log(f"  [{vi+1}/{len(vids)}] {v['name'][:40]} | {duration:.0f}s | "
             f"镜头{len(shots)} | 帧{len(frames)} | 累计{state['frames_total']}")

    _log(f"  [{ip_name}] 帧提取完成: 新增{new_frames}帧, 总计{state['frames_total']}帧")


def extract_all(config: dict, ip_filter: str = ""):
    """为所有配置的IP提取帧"""
    settings = config.get("settings", {})
    ips = config.get("ips", {})

    for ip_name, ip_cfg in ips.items():
        if ip_filter and ip_name != ip_filter:
            continue
        _log(f"\n=== 帧提取: {ip_name} ({ip_cfg.get('name_cn', '')}) ===")
        extract_frames_for_ip(ip_name, ip_cfg, settings)


# ── VLM标注 ───────────────────────────────────────────────

def vlm_annotate_ip(ip_name: str, config: dict):
    """为单个IP启动VLM标注(复用t26c逻辑)"""
    ip_dir = CORPUS_BASE / ip_name
    frames_dir = ip_dir / "frames"

    if not frames_dir.exists():
        _log(f"  [{ip_name}] 帧目录不存在: {frames_dir}")
        return

    frame_files = sorted(frames_dir.glob("*.jpg"))
    if not frame_files:
        _log(f"  [{ip_name}] 无帧文件")
        return

    _log(f"  [{ip_name}] {len(frame_files)}帧待标注")

    # 生成独立启动脚本
    bat_path = ROOT / "scripts" / f"run_vlm_{ip_name}.bat"
    log_path = ROOT / "logs" / f"vlm_{ip_name}.log"

    bat_content = f"""@echo off
cd /d {ROOT}
:loop
{sys.executable} -m ai.t26c_vlm_concurrent --corpus-dir "{ip_dir}" --log "{log_path}"
echo [%date% %time%] VLM exited with code %errorlevel%, restarting in 5s...
timeout /t 5 /nobreak >nul
goto loop
"""
    bat_path.write_text(bat_content, encoding="utf-8")
    _log(f"  启动脚本: {bat_path}")
    _log(f"  日志: {log_path}")
    _log(f"  运行: Start-Process -FilePath '{bat_path}' -WindowStyle Minimized")

    # 自动启动
    try:
        subprocess.Popen(
            ["powershell", "-Command",
             f"Start-Process -FilePath '{bat_path}' -WindowStyle Minimized"],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        _log(f"  VLM标注已后台启动: {ip_name}")
    except Exception as e:
        _log(f"  启动失败: {e}, 请手动运行: {bat_path}")


def vlm_annotate_all(config: dict, ip_filter: str = ""):
    """为所有IP启动VLM标注"""
    ips = config.get("ips", {})
    for ip_name in ips:
        if ip_filter and ip_name != ip_filter:
            continue
        _log(f"\n=== VLM标注: {ip_name} ===")
        vlm_annotate_ip(ip_name, config)


# ── 数据合并 ──────────────────────────────────────────────

def merge_all(config: dict):
    """合并所有IP的VLM标注数据"""
    ips = config.get("ips", {})
    merged_path = CORPUS_BASE / "merged_vlm.jsonl"
    CORPUS_BASE.mkdir(parents=True, exist_ok=True)

    total_lines = 0
    ip_stats = {}

    with open(merged_path, "w", encoding="utf-8") as out_f:
        # 先写入AoT数据(如果存在)
        aot_jsonl = Path(r"D:\aot_corpus\vlm_full\results.jsonl")
        if aot_jsonl.exists():
            aot_count = 0
            with open(aot_jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        out_f.write(line + "\n")
                        aot_count += 1
            ip_stats["attack_on_titan"] = aot_count
            total_lines += aot_count
            _log(f"  AoT: {aot_count}帧")

        # 合并新IP
        for ip_name in ips:
            ip_jsonl = CORPUS_BASE / ip_name / "vlm_results.jsonl"
            if not ip_jsonl.exists():
                continue
            count = 0
            with open(ip_jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        # 注入ip_name字段
                        try:
                            rec = json.loads(line)
                            rec["source_ip"] = ip_name
                            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            count += 1
                        except json.JSONDecodeError:
                            pass
            if count > 0:
                ip_stats[ip_name] = count
                total_lines += count
                _log(f"  {ip_name}: {count}帧")

    _log(f"\n合并完成: {merged_path}")
    _log(f"  总帧数: {total_lines}")
    _log(f"  IP分布: {ip_stats}")

    # 生成统计报告
    report = {
        "merged_path": str(merged_path),
        "total_frames": total_lines,
        "ip_distribution": ip_stats,
        "n_ips": len(ip_stats),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    report_path = ROOT / "reports" / "t31_merge_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"  报告: {report_path}")


# ── 状态总览 ──────────────────────────────────────────────

def show_status(config: dict):
    """显示所有IP的语料状态"""
    ips = config.get("ips", {})
    _log("=" * 60)
    _log("多IP语料工厂状态总览")
    _log("=" * 60)

    for ip_name, ip_cfg in ips.items():
        ip_dir = CORPUS_BASE / ip_name
        name_cn = ip_cfg.get("name_cn", ip_name)

        # 帧数
        frames_dir = ip_dir / "frames"
        n_frames = len(list(frames_dir.glob("*.jpg"))) if frames_dir.exists() else 0

        # VLM标注数
        vlm_path = ip_dir / "vlm_results.jsonl"
        n_vlm = 0
        if vlm_path.exists():
            with open(vlm_path, "r", encoding="utf-8") as f:
                n_vlm = sum(1 for l in f if l.strip())

        # 视频目录
        video_dirs = ip_cfg.get("video_dirs", [])
        n_vids = 0
        for vd in video_dirs:
            vd_p = Path(vd)
            if vd_p.exists():
                n_vids += len([f for f in vd_p.rglob("*") if f.suffix.lower() in (".mkv", ".mp4", ".mov")])

        status = "✅" if n_vlm > 0 else ("📦" if n_frames > 0 else ("📁" if n_vids > 0 else "⬜"))
        _log(f"  {status} {ip_name:20s} ({name_cn:8s}) | "
             f"视频:{n_vids:3d} 帧:{n_frames:5d} VLM:{n_vlm:5d}")


# ── 入口 ──────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="T31 多IP语料工厂")
    ap.add_argument("--init-config", action="store_true", help="生成配置模板")
    ap.add_argument("--extract-frames", action="store_true", help="提取关键帧")
    ap.add_argument("--vlm-annotate", action="store_true", help="VLM标注")
    ap.add_argument("--merge", action="store_true", help="合并所有IP数据")
    ap.add_argument("--status", action="store_true", help="显示状态")
    ap.add_argument("--all", action="store_true", help="全流程")
    ap.add_argument("--ip", type=str, default="", help="指定单个IP")
    args = ap.parse_args()

    if args.init_config:
        init_config()
        return

    config = load_config()

    if args.status or (not args.extract_frames and not args.vlm_annotate
                       and not args.merge and not args.all):
        show_status(config)
        return

    if args.extract_frames or args.all:
        extract_all(config, ip_filter=args.ip)

    if args.vlm_annotate or args.all:
        vlm_annotate_all(config, ip_filter=args.ip)

    if args.merge or args.all:
        merge_all(config)


if __name__ == "__main__":
    main()
