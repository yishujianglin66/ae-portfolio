#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风格智能复制 MVP 端到端入口（离线可跑，无需外部 V4）

流程:
  提示词 -> 离线风格分析(LocalStyleAnalyzer) -> 规则编排(ToolOrchestrator) -> Phase1 ToolchainManager 真实执行(ffmpeg 带风格滤镜) -> 成片

用法:
  py -3.12 style_copy/style_copy_mvp.py --prompt "电影感暖色调快节奏胶片颗粒" --output output/style_out.mp4
  py -3.12 style_copy/style_copy_mvp.py --prompt "..." --input 源视频.mp4 --output 输出.mp4
"""
import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import bootstrap  # noqa: E402

from style_copy.style_analyzer import get_analyzer  # noqa: E402
from style_copy.tool_orchestrator import ToolOrchestrator  # noqa: E402
from style_copy.ffmpeg_generator import FFmpegCommandGenerator  # noqa: E402


def _ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe") or "ffmpeg"


_ff_filter_cache = None


def supported_ff_filters() -> set:
    """查询本机 ffmpeg 支持的滤镜集合（缓存）

    注意：本机构建将 `ffmpeg -filters` 输出到 **stderr**（非 stdout），
    仅读 stdout 会得到空集 → 剪枝形同虚设。此处合并 stdout+stderr，
    并以「标志位列 + 滤镜名」格式解析（标志符合 [TSCf.|+-]{2,6}）。
    """
    import re
    global _ff_filter_cache
    if _ff_filter_cache is not None:
        return _ff_filter_cache
    names = set()
    flag_re = re.compile(r"^[TSCf\.|+-]{2,6}$")
    try:
        r = subprocess.run([_ffmpeg_bin(), "-filters", "-hide_banner"],
                           capture_output=True, text=True, timeout=30)
        out = (r.stdout or "") + (r.stderr or "")
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and flag_re.match(parts[0]):
                names.add(parts[1])
    except Exception:
        pass
    _ff_filter_cache = names
    return names


def prune_filters(filters: list) -> list:
    """剪枝掉本机 ffmpeg 不支持的滤镜（如 glow），保证命令可执行"""
    if not filters:
        return filters
    ok = supported_ff_filters()
    if not ok:  # 查询失败则保守保留全部
        return filters
    kept = []
    for f in filters:
        name = f.split("=")[0].split(":")[0].strip()
        if name in ok:
            kept.append(f)
        else:
            print(f"    [prune] 跳过不支持滤镜: {name}")
    return kept


def ensure_source(input_path: str, fallback: str) -> str:
    """无输入视频时，用 ffmpeg lavfi 生成 1s 测试源（真实二进制，证明闭环）"""
    if input_path and Path(input_path).exists():
        return input_path
    Path(fallback).parent.mkdir(parents=True, exist_ok=True)
    cmd = [_ffmpeg_bin(), "-y", "-f", "lavfi",
           "-i", "testsrc=duration=2:size=640x360:rate=24", fallback]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not Path(fallback).exists():
        raise RuntimeError(f"测试源生成失败: {r.stderr[-300:]}")
    return fallback


def main():
    ap = argparse.ArgumentParser(description="风格智能复制 MVP")
    ap.add_argument("--prompt", required=True, help="风格描述提示词")
    ap.add_argument("--input", default="", help="输入视频(可选, 缺省自动生成测试源)")
    ap.add_argument("--output", default="output/style_out.mp4", help="输出视频")
    ap.add_argument("--mode", default="auto", help="执行模式: real / simulate / auto")
    args = ap.parse_args()

    # Step 1: 离线风格分析
    analyzer = get_analyzer()
    ar = analyzer.analyze_from_prompt(args.prompt)
    assert ar.get("success"), f"分析失败: {ar.get('error')}"
    style = ar["style"]
    print(f"[1] 风格分析({ar.get('source')}): "
          f"temp={style['color_temperature']} contrast={style['contrast']} "
          f"pace={style['pace']} effects={style['effects']}")

    # Step 2: 规则编排 (DAG)
    src = ensure_source(args.input, "output/_mvp_src.mp4")
    orch = ToolOrchestrator(mode=args.mode)
    seq = orch.generate_tool_sequence(style, src)
    assert seq.get("success"), f"编排失败: {seq.get('error')}"
    steps = seq["steps"]
    print(f"[2] 编排 DAG: {len(steps)} 步")
    for s in steps:
        print(f"    - {s['tool']}.{s['operation']} -> {s['params'].get('output_file') or s['params'].get('output_path')}")

    # Step 3: 经 Phase1 ToolchainManager 真实执行 (颜色/对比/节奏滤镜)
    res = orch.execute_via_toolchain(steps, src, mode=args.mode)
    print(f"[3] Phase1 引擎执行: success={res['success']} engine={res['engine']}")
    pass1_out = None
    for f in res.get("output_files", []):
        if f.endswith(".mp4"):
            pass1_out = f
            break

    # Step 4: 用 FFmpegCommandGenerator 应用完整风格滤镜(含特效) 二次真实转码
    final_out = args.output
    Path(final_out).parent.mkdir(parents=True, exist_ok=True)
    gen = FFmpegCommandGenerator()
    base = pass1_out or src
    gen.generate_command(base, final_out, style)
    filters = prune_filters(gen.filters)
    print(f"[4] 风格滤镜(已剪枝): {filters}")
    if filters:
        cmd = [_ffmpeg_bin(), "-y", "-i", base, "-vf", ",".join(filters),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", final_out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and Path(final_out).exists():
            size = Path(final_out).stat().st_size
            print(f"[4] 成片生成: {final_out} ({size} bytes)")
        else:
            print(f"[4] 二次转码失败(降级使用一次转码产物): {r.stderr[-300:]}")
            if pass1_out:
                final_out = pass1_out
    else:
        print("[4] 无可用风格滤镜，直接使用一次转码产物")
        if pass1_out:
            final_out = pass1_out

    print("\n=== MVP 完成 ===")
    print(f"风格: {json.dumps(style, ensure_ascii=False)}")
    print(f"成片: {final_out}  exists={Path(final_out).exists()}")
    print(f"运行清单: {[f for f in res.get('output_files', []) if f.endswith('.json')]}")


if __name__ == "__main__":
    main()
