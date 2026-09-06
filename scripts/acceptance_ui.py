"""acceptance_ui.py — 母版验收回路 UI（E0-4）

目的：把"用户逐版肉眼对比 v2→v7"变成结构化验收数据，作为规则蒸馏引擎（E1-1）的一级原料。
- 多版本并排 A/B 对比（来自 output/unified_run*/）
- 每版本 1-5 分评分
- 问题结构化采集：镜头号 / 问题类型（卡点/切点/变速/调色/效果/叙事/其他）/ 描述
- 验收结论：采纳 / 需修改 / 拒绝
- 落盘 data/evolution/acceptance_log.jsonl，与 render_history.jsonl 以 run_tag+version 共键

用法：
    python scripts/acceptance_ui.py                 # 默认输出 data/evolution/acceptance_log.jsonl
    python scripts/acceptance_ui.py --output-root output --log data/evolution/acceptance_log.jsonl
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import List

import gradio as gr

PROBLEM_TYPES = ["卡点", "切点", "变速", "调色", "效果", "叙事", "素材", "其他"]
VERDICTS = ["采纳", "需修改", "拒绝"]


def discover_runs(output_root: str) -> List[str]:
    """枚举 output/ 下的 unified_run* 目录（按修改时间倒序）。"""
    root = Path(output_root)
    if not root.exists():
        return []
    runs = [d for d in root.glob("unified_run*") if d.is_dir()]
    runs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return [str(d) for d in runs]


def discover_versions(run_dir: str) -> List[str]:
    """枚举 run 目录顶层 mp4 成片（按修改时间倒序，最新版本在前）。"""
    if not run_dir:
        return []
    files = list(Path(run_dir).glob("*.mp4"))
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return [str(f) for f in files]


def submit_acceptance(run_tag: str, version_a: str, version_b: str,
                      rating_a: int, rating_b: int, issues: List[List],
                      verdict: str, notes: str, log_path: str) -> str:
    """写入一条结构化验收记录（蒸馏引擎的数据接口，字段稳定勿改）。"""
    record = {
        "schema": "acceptance_v1",
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "run_tag": run_tag,
        "versions": [Path(version_a).name if version_a else None,
                     Path(version_b).name if version_b else None],
        "ratings": {"a": rating_a, "b": rating_b},
        "issues": [
            {"shot": int(row[0]) if row[0] not in (None, "") else None,
             "problem_type": row[1],
             "comment": row[2]}
            for row in (issues or [])
        ],
        "verdict": verdict,
        "notes": notes,
        "source": "acceptance_ui",
    }
    log = Path(log_path)
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    n_issues = len(record["issues"])
    return (f"✅ 已写入 {log}\n"
            f"run={run_tag} verdict={verdict} "
            f"评分 A={rating_a}/B={rating_b} 问题 {n_issues} 条\n"
            f"记录键: {run_tag} + {record['versions']}")


def load_history(log_path: str) -> List[List]:
    """读取验收历史（最近 50 条，倒序）供 Dataframe 展示。"""
    log = Path(log_path)
    if not log.exists():
        return []
    rows = []
    with open(log, "r", encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            rows.append([r.get("ts"), r.get("run_tag"),
                         " / ".join(v or "-" for v in r.get("versions", [])),
                         r.get("ratings", {}).get("a"), r.get("ratings", {}).get("b"),
                         len(r.get("issues", [])), r.get("verdict")])
    return list(reversed(rows[-50:]))


def build_ui(output_root: str, log_path: str) -> gr.Blocks:
    with gr.Blocks(title="MasterCut 母版验收") as demo:
        gr.Markdown("## 🎬 MasterCut 母版验收回路\n"
                    "A/B 对比两个版本 → 打分 → 结构化记录问题 → 给出结论。"
                    "数据直接进入规则蒸馏原料库。")
        with gr.Row():
            run_dd = gr.Dropdown(choices=discover_runs(output_root),
                                 label="Run 目录", interactive=True)
            refresh_btn = gr.Button("🔄 刷新 run 列表")
        with gr.Row():
            with gr.Column():
                ver_a = gr.Dropdown(label="版本 A（旧）", choices=[], interactive=True)
                video_a = gr.Video(label="版本 A")
                rating_a = gr.Slider(1, 5, value=3, step=1, label="版本 A 评分")
            with gr.Column():
                ver_b = gr.Dropdown(label="版本 B（新）", choices=[], interactive=True)
                video_b = gr.Video(label="版本 B")
                rating_b = gr.Slider(1, 5, value=3, step=1, label="版本 B 评分")

        def on_run_change(run_dir):
            versions = discover_versions(run_dir)
            a = versions[1] if len(versions) > 1 else (versions[0] if versions else None)
            b = versions[0] if versions else None
            run_tag = Path(run_dir).name if run_dir else ""
            return (gr.update(choices=versions, value=a),
                    gr.update(choices=versions, value=b),
                    run_tag, a, b)

        run_tag_tb = gr.Textbox(label="run_tag", interactive=False)
        # run 目录选择 → 填充版本下拉与播放器
        ver_a.change(lambda p: p or None, inputs=ver_a, outputs=video_a)
        ver_b.change(lambda p: p or None, inputs=ver_b, outputs=video_b)
        run_dd.change(on_run_change, inputs=run_dd,
                      outputs=[ver_a, ver_b, run_tag_tb, video_a, video_b])
        refresh_btn.click(lambda: gr.update(choices=discover_runs(output_root)),
                          outputs=run_dd)

        gr.Markdown("### 问题记录（逐条添加）")
        with gr.Row():
            shot_no = gr.Number(label="镜头号（可选）", precision=0)
            ptype = gr.Radio(PROBLEM_TYPES, value="卡点", label="问题类型")
        issue_comment = gr.Textbox(label="问题描述", placeholder="例：drop 段第 2 次变速后卡点慢半拍")
        add_btn = gr.Button("➕ 添加问题")
        issues_df = gr.Dataframe(headers=["镜头号", "问题类型", "问题描述"],
                                 datatype=["number", "str", "str"],
                                 value=[], label="已记录问题", interactive=False)
        issue_state = gr.State([])

        def add_issue(shot, pt, comment, state):
            row = [int(shot) if shot not in (None, "") else None, pt, comment or ""]
            state = list(state) + [row]
            return state, gr.update(value=state)

        add_btn.click(add_issue, inputs=[shot_no, ptype, issue_comment, issue_state],
                      outputs=[issue_state, issues_df])

        with gr.Row():
            verdict = gr.Radio(VERDICTS, value="需修改", label="验收结论")
            notes = gr.Textbox(label="总体备注（可选）")
        submit_btn = gr.Button("📝 提交验收记录", variant="primary")
        result_tb = gr.Textbox(label="提交结果", interactive=False)
        submit_btn.click(submit_acceptance,
                         inputs=[run_tag_tb, ver_a, ver_b, rating_a, rating_b,
                                 issue_state, verdict, notes,
                                 gr.State(log_path)],
                         outputs=result_tb)

        gr.Markdown("### 验收历史（最近 50 条）")
        history_df = gr.Dataframe(
            headers=["时间", "run", "版本", "评分A", "评分B", "问题数", "结论"],
            value=load_history(log_path), interactive=False)
        submit_btn.click(lambda: load_history(log_path), outputs=history_df)
    return demo


def main():
    parser = argparse.ArgumentParser(description="MasterCut 母版验收回路 UI")
    parser.add_argument("--output-root", default="output")
    parser.add_argument("--log", default="data/evolution/acceptance_log.jsonl")
    parser.add_argument("--port", type=int, default=7862)
    args = parser.parse_args()
    demo = build_ui(args.output_root, args.log)
    demo.launch(server_name="127.0.0.1", server_port=args.port, inbrowser=True)


if __name__ == "__main__":
    main()
