#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务数据扁平化导出工具
====================

将 data/tasks/tasks.json 中的嵌套工作流记录扁平化为 CSV/JSONL，
便于使用 Excel / DuckDB / pandas 进行定期分析。

使用方式:
    # 默认导出 CSV 到 data/tasks/tasks_flat.csv
    python tasks_to_csv.py

    # 指定输入输出
    python tasks_to_csv.py --input data/tasks/tasks.json --output report.csv

    # 导出 JSONL 格式
    python tasks_to_csv.py --format jsonl --output tasks.jsonl

字段说明:
    task_id, name, workflow_type, status, priority, mode, style,
    duration, total_stages, current_stage, progress,
    input_path, output_dir,
    scenes, has_audio, bgm_bpm, video_width, video_height, fps,
    persons_detected, joints_detected, face_detected, tracking_confidence,
    effects_applied, keyframes_generated, layer_count,
    script_generated, script_size, effects_count,
    output_resolution, output_file_size_kb,
    success, error,
    created_at, started_at, completed_at, last_updated,
    created_at_iso, completed_at_iso
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# 北京时区（项目本地时区）
CN_TZ = timezone(timedelta(hours=8))


def _to_iso(ts: float | None) -> str:
    """Unix 时间戳转 ISO8601 字符串（北京时区）"""
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(ts, tz=CN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return ""


def _safe_get(d: dict[str, Any] | None, *keys, default: Any = "") -> Any:
    """安全嵌套取值"""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def flatten_task(task: dict[str, Any]) -> dict[str, Any]:
    """将单条嵌套任务记录扁平化为单行字典"""
    result = task.get("result", {}) or {}
    stages_results = result.get("stage_results", {}) or {}

    media = stages_results.get("media_analysis", {}) or {}
    pose = stages_results.get("pose_detection", {}) or {}
    style_gen = stages_results.get("style_generation", {}) or {}
    ae_int = stages_results.get("ae_integration", {}) or {}
    render = stages_results.get("output_render", {}) or {}

    config = task.get("config", {}) or {}

    return {
        # —— 基本元信息 ——
        "task_id": task.get("task_id", ""),
        "name": task.get("name", ""),
        "workflow_type": task.get("workflow_type", ""),
        "status": task.get("status", ""),
        "priority": task.get("priority", ""),
        "mode": task.get("mode", config.get("mode", "")),
        "style": config.get("style", result.get("style", "")),
        # —— 进度信息 ——
        "duration": task.get("duration", 0.0),
        "total_stages": task.get("total_stages", 0),
        "current_stage": task.get("current_stage", 0),
        "progress": task.get("progress", 0.0),
        # —— 输入输出路径 ——
        "input_path": task.get("input_path", ""),
        "output_dir": task.get("output_dir", ""),
        # —— 媒体分析阶段 ——
        "scenes": _safe_get(media, "scenes"),
        "has_audio": _safe_get(media, "has_audio", default=""),
        "bgm_bpm": _safe_get(media, "bgm_bpm"),
        "video_width": _safe_get(media, "width"),
        "video_height": _safe_get(media, "height"),
        "fps": _safe_get(media, "fps"),
        # —— 姿态检测阶段 ——
        "persons_detected": _safe_get(pose, "persons_detected"),
        "joints_detected": _safe_get(pose, "joints_detected"),
        "face_detected": _safe_get(pose, "face_detected", default=""),
        "tracking_confidence": _safe_get(pose, "tracking_confidence"),
        # —— 风格化生成阶段 ——
        "effects_applied": _safe_get(style_gen, "effects_applied"),
        "keyframes_generated": _safe_get(style_gen, "keyframes_generated"),
        "layer_count": _safe_get(style_gen, "layer_count"),
        # —— AE 集成阶段 ——
        "script_generated": _safe_get(ae_int, "script_generated", default=""),
        "script_size": _safe_get(ae_int, "script_size"),
        "effects_count": _safe_get(ae_int, "effects_count"),
        # —— 渲染输出阶段 ——
        "output_resolution": _safe_get(render, "resolution"),
        "output_file_size_kb": _safe_get(render, "file_size_kb"),
        # —— 结果汇总 ——
        "success": _safe_get(result, "success", default=""),
        "error": task.get("error", "") or "",
        # —— 时间戳 ——
        "created_at": task.get("created_at", 0.0),
        "started_at": task.get("started_at", 0.0),
        "completed_at": task.get("completed_at", 0.0),
        "last_updated": task.get("last_updated", 0.0),
        "created_at_iso": _to_iso(task.get("created_at")),
        "completed_at_iso": _to_iso(task.get("completed_at")),
    }


def load_tasks(input_path: str) -> list[dict[str, Any]]:
    """加载 tasks.json，返回任务列表"""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"任务文件不存在: {input_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # tasks.json 可能是 {task_id: task_obj} 或 [task_obj, ...]
    if isinstance(data, dict):
        return list(data.values())
    elif isinstance(data, list):
        return data
    else:
        raise ValueError(f"无法识别的任务数据格式: {type(data)}")


def export_csv(rows: list[dict[str, Any]], output_path: str) -> int:
    """导出 CSV 文件，返回写入的行数"""
    if not rows:
        # 仍创建空文件带表头
        fieldnames = list(flatten_task({}).keys())
    else:
        fieldnames = list(rows[0].keys())

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return len(rows)


def export_jsonl(rows: list[dict[str, Any]], output_path: str) -> int:
    """导出 JSONL 文件（每行一个 JSON 对象），返回写入的行数"""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    return len(rows)


def export_markdown_summary(rows: list[dict[str, Any]], output_path: str) -> int:
    """导出 Markdown 摘要报告（含基础统计），返回任务数"""
    from collections import Counter

    total = len(rows)
    if total == 0:
        summary_lines = ["# 任务数据摘要", "", "暂无任务记录。"]
    else:
        status_count = Counter(r["status"] for r in rows)
        wf_count = Counter(r["workflow_type"] for r in rows)
        style_count = Counter(r["style"] for r in rows if r["style"])
        mode_count = Counter(r["mode"] for r in rows if r["mode"])
        success_count = sum(1 for r in rows if r["success"] is True)

        durations = [r["duration"] for r in rows if r["duration"] > 0]
        avg_dur = sum(durations) / len(durations) if durations else 0

        summary_lines = [
            "# 任务数据摘要",
            "",
            f"- **总任务数**: {total}",
            f"- **成功率**: {success_count}/{total} ({success_count/total*100:.1f}%)" if total else "",
            f"- **平均耗时**: {avg_dur:.2f} 秒" if durations else "",
            "",
            "## 状态分布",
            "",
            "| 状态 | 数量 |",
            "|------|------|",
        ]
        for s, c in status_count.most_common():
            summary_lines.append(f"| {s} | {c} |")

        summary_lines += ["", "## 工作流类型分布", "", "| 类型 | 数量 |", "|------|------|"]
        for s, c in wf_count.most_common():
            summary_lines.append(f"| {s} | {c} |")

        summary_lines += ["", "## 风格分布", "", "| 风格 | 数量 |", "|------|------|"]
        for s, c in style_count.most_common():
            summary_lines.append(f"| {s} | {c} |")

        summary_lines += ["", "## 执行模式分布", "", "| 模式 | 数量 |", "|------|------|"]
        for s, c in mode_count.most_common():
            summary_lines.append(f"| {s} | {c} |")

        summary_lines += [
            "",
            "## 时间范围",
            "",
            f"- 最早创建: {min(r['created_at_iso'] for r in rows if r['created_at_iso']) or 'N/A'}",
            f"- 最近完成: {max(r['completed_at_iso'] for r in rows if r['completed_at_iso']) or 'N/A'}",
        ]

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    return total


def main():
    parser = argparse.ArgumentParser(
        description="将 tasks.json 扁平化导出为 CSV/JSONL/Markdown，便于定期分析"
    )
    parser.add_argument(
        "--input", "-i",
        default="data/tasks/tasks.json",
        help="tasks.json 输入路径（默认 data/tasks/tasks.json）",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出文件路径（默认根据格式自动生成）",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["csv", "jsonl", "md"],
        default="csv",
        help="输出格式: csv / jsonl / md（markdown 摘要）",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="同时导出 csv + jsonl + md 三种格式",
    )
    args = parser.parse_args()

    input_path = args.input
    if not os.path.isabs(input_path):
        # 以脚本所在项目根目录为基准
        project_root = Path(__file__).parent
        input_path = str(project_root / input_path)

    try:
        tasks = load_tasks(input_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"[错误] 加载任务数据失败: {e}", file=sys.stderr)
        sys.exit(1)

    rows = [flatten_task(t) for t in tasks]
    print(f"[信息] 已加载 {len(rows)} 条任务记录（来源: {input_path}）")

    if args.all:
        # 同时导出三种格式
        base = Path(input_path).stem
        out_dir = Path(input_path).parent
        n1 = export_csv(rows, str(out_dir / f"{base}.csv"))
        n2 = export_jsonl(rows, str(out_dir / f"{base}.jsonl"))
        n3 = export_markdown_summary(rows, str(out_dir / f"{base}_summary.md"))
        print(f"[完成] CSV: {out_dir / f'{base}.csv'} ({n1} 行)")
        print(f"[完成] JSONL: {out_dir / f'{base}.jsonl'} ({n2} 行)")
        print(f"[完成] MD摘要: {out_dir / f'{base}_summary.md'} ({n3} 行)")
        return

    # 单格式导出
    if args.output is None:
        base = Path(input_path).stem
        ext = {"csv": ".csv", "jsonl": ".jsonl", "md": "_summary.md"}[args.format]
        output_path = str(Path(input_path).parent / f"{base}{ext}")
    else:
        output_path = args.output

    if args.format == "csv":
        n = export_csv(rows, output_path)
    elif args.format == "jsonl":
        n = export_jsonl(rows, output_path)
    else:
        n = export_markdown_summary(rows, output_path)

    print(f"[完成] 已导出 {n} 条记录 → {output_path}")


if __name__ == "__main__":
    main()
