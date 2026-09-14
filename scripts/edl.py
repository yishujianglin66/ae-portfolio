"""edl.py — EDL(编辑决策清单)构建与渲染前 lint (P0 确定性渲染框架)

来源: 2026-09-09 四竞品调研报告 §2.2/§3.3 —— 吸收 HyperFrames "渲染清单" 与
video-use "EDL 中间表示" 两家设计, 把 unified_edit 的切割方案从"流程内嵌状态"
变为"可落盘、可审计、可回归比对"的声明式产物。

产物 schema (edl.json):
  {
    "schema_version": "1.0",
    "generated_at": "...",
    "render": {"style","theme","duration","fps","resolution"},
    "inputs":  [{"path","sha1","size_bytes"}],       # 素材+BGM 内容指纹
    "cuts":     [{"index","start_time","end_time","source_file",
                   "source_start","speed","transition","mood","energy"}],
    "cut_points": [t1, t2, ...],                      # 供 P2 切点级 self-eval
    "toolchain": {"ffmpeg","python","edl_schema"}
  }

用法:
  from scripts.edl import build_edl, save_edl, lint_edl
  edl = build_edl(pr_path, bgm_path=..., sources=[...], style=..., theme=...)
  errs = lint_edl(edl)          # 空 list = 通过
  save_edl(edl, out_dir / "edl.json")
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

EDL_SCHEMA_VERSION = "1.1"                       # 1.0→1.1: 新增 effects/text_events/overlays 三轨(FORWARD 兼容)
SUPPORTED_EDL_SCHEMA_VERSIONS = {"1.0", "1.1"}   # lint L1 接受的历史版本(BACKWARD 兼容旧 edl.json)
HASH_CHUNK = 1 << 20  # 1MB 分块读文件算 SHA1


def _sha1_of(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            b = f.read(HASH_CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _ffmpeg_version() -> str:
    try:
        out = subprocess.run(["ffmpeg", "-version"], capture_output=True,
                             text=True, timeout=15)
        return (out.stdout or "").splitlines()[0].strip()
    except Exception as e:  # noqa: BLE001 — 版本探测失败不致命
        return f"unknown ({e})"


def build_edl(
    production_report_path: str | Path,
    *,
    bgm_path: str | None = None,
    sources: list | None = None,
    style: str | None = None,
    theme: str | None = None,
    duration: float | None = None,
    fps: int = 24,
    resolution=(1920, 1080),
    effects: list | None = None,       # v1.1 视觉特效轨(对齐 schemas/visual_effect_schema.json)
    text_events: list | None = None,   # v1.1 文字事件轨(对齐 text_overlay/events.json)
    overlays: list | None = None,      # v1.1 覆盖层轨(独立渲染的效果/木偶 alpha; video-use 式)
) -> dict:
    """从 production_report.json 构建 EDL。

    素材哈希只对 EDL 实际引用的 unique 源文件计算(含 BGM),
    大文件 SHA1 走 1MB 分块, 不整读内存。
    """
    pr_path = Path(production_report_path)
    pr = json.loads(pr_path.read_text(encoding="utf-8"))
    segments = pr.get("script", {}).get("segments", []) or []

    cuts = []
    referenced: dict[str, None] = {}  # ordered set
    for s in segments:
        src = s.get("source_file")
        if src:
            referenced.setdefault(src, None)
        cuts.append({
            "index": s.get("index"),
            "start_time": round(float(s.get("start_time", 0.0)), 4),
            "end_time": round(float(s.get("end_time", 0.0)), 4),
            "source_file": src,
            "source_start": s.get("source_start"),
            "speed": s.get("speed"),
            "transition": s.get("transition"),
            "mood": s.get("mood"),
            "energy": s.get("energy"),
        })
    cut_points = [c["start_time"] for c in cuts[1:]]

    # duration 未显式传入 → 从 cuts 末帧自动推导(避免 render.duration=None 传下游; Step1 实证发现#1)
    if duration is None and cuts:
        duration = round(max(c["end_time"] for c in cuts), 4)

    if bgm_path:
        referenced.setdefault(bgm_path, None)
    for s in sources or []:
        referenced.setdefault(s, None)

    inputs = []
    for p in referenced:
        if not p or not Path(p).exists():
            inputs.append({"path": p, "sha1": None, "size_bytes": None,
                           "missing": True})
        else:
            inputs.append({"path": p, "sha1": _sha1_of(p),
                          "size_bytes": Path(p).stat().st_size})

    edl = {
        "schema_version": EDL_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "production_report": str(pr_path),
        "render": {
            "style": style,
            "theme": theme,
            "duration": duration,
            "fps": fps,
            "resolution": list(resolution),
        },
        "inputs": inputs,
        "cuts": cuts,
        "cut_points": [round(t, 4) for t in cut_points],
        "toolchain": {
            "ffmpeg": _ffmpeg_version(),
            "python": sys.version.split()[0],
            "edl_schema": EDL_SCHEMA_VERSION,
        },
    }
    # v1.1 三轨：仅当调用方显式传入才写入 —— 旧调用产出与 1.0 结构一致(最小惊讶 + FORWARD 兼容)
    if effects is not None:
        edl["effects"] = effects
    if text_events is not None:
        edl["text_events"] = text_events
    if overlays is not None:
        edl["overlays"] = overlays
    return edl


def save_edl(edl: dict, path: str | Path) -> Path:
    p = Path(path)
    p.write_text(json.dumps(edl, ensure_ascii=False, indent=1),
                 encoding="utf-8")
    return p


def lint_edl(edl: dict, *, duration_tolerance: float = 1.5) -> list:
    """渲染前 lint — 返回错误清单(空 = 通过)。

    校验项 (对齐报告 §5.2 pre-render lint 设计):
      L1 schema 版本受支持        L2 输入文件全部在盘
      L3 切点时间单调不重叠        L4 每切 source_file 已在 inputs 引用且存在
      L5 时长声明与最后切点吻合    L6 source_start 非负
    """
    errs: list[str] = []

    _sv = edl.get("schema_version")
    if _sv not in SUPPORTED_EDL_SCHEMA_VERSIONS:
        errs.append(f"L1 schema_version {_sv!r} not in "
                    f"{sorted(SUPPORTED_EDL_SCHEMA_VERSIONS)}")

    for inp in edl.get("inputs", []):
        if inp.get("missing") or inp.get("sha1") is None:
            errs.append(f"L2 input missing/unreadable: {inp.get('path')}")
    on_disk = {i["path"] for i in edl.get("inputs", []) if i.get("sha1")}

    prev_end = 0.0
    for c in edl.get("cuts", []):
        st, en = c.get("start_time", 0), c.get("end_time", 0)
        if not (0 <= st < en):
            errs.append(f"L3 invalid times cut#{c.get('index')}: [{st},{en})")
        elif st < prev_end - 1e-6:
            errs.append(f"L3 overlap cut#{c.get('index')}: start {st} "
                        f"< prev_end {prev_end}")
        prev_end = max(prev_end, en)
        if c.get("source_start") is not None and c["source_start"] < 0:
            errs.append(f"L6 negative source_start cut#{c.get('index')}")
        src = c.get("source_file")
        if src and src not in on_disk:
            errs.append(f"L4 source not in inputs/on-disk: {src}")

    declared = (edl.get("render") or {}).get("duration")
    if declared is not None and prev_end > 0:
        if abs(declared - prev_end) > duration_tolerance:
            errs.append(f"L5 duration mismatch: declared {declared} "
                        f"vs timeline end {round(prev_end, 3)}")

    # --- L7 (v1.1): 三轨校验 —— 时间不越界 + 必备字段 + effect.skill_id 必填 ---
    _tend = prev_end  # cuts 循环后的时间线末端
    _tol = duration_tolerance
    for i, ov in enumerate(edl.get("overlays") or []):
        st, du = ov.get("start_in_output"), ov.get("duration")
        if not ov.get("file"):
            errs.append(f"L7 overlay#{i} missing file")
        if st is None or du is None:
            errs.append(f"L7 overlay#{i} missing start_in_output/duration")
            continue
        if st < -1e-6 or du <= 0:
            errs.append(f"L7 overlay#{i} invalid start/duration [{st},+{du}]")
        elif _tend > 0 and st + du > _tend + _tol:
            errs.append(f"L7 overlay#{i} exceeds timeline {st}+{du}>{round(_tend, 3)}")
    for i, ef in enumerate(edl.get("effects") or []):
        tr = ef.get("time_range") or {}
        s, e = tr.get("start_sec"), tr.get("end_sec")
        if s is None or e is None or not (s < e):
            errs.append(f"L7 effect#{i} invalid time_range [{s},{e})")
        elif _tend > 0 and e > _tend + _tol:
            errs.append(f"L7 effect#{i} end {e} exceeds timeline {round(_tend, 3)}")
        if not (ef.get("evidence_chain") or {}).get("skill_id"):
            errs.append(f"L7 effect#{i} missing evidence_chain.skill_id")
    for i, te in enumerate(edl.get("text_events") or []):
        ti, to = te.get("t_in"), te.get("t_out")
        if ti is None or to is None or not (ti < to):
            errs.append(f"L7 text_event#{i} invalid t_in/t_out [{ti},{to})")
        elif _tend > 0 and to > _tend + _tol:
            errs.append(f"L7 text_event#{i} t_out {to} exceeds timeline {round(_tend, 3)}")

    return errs


def load_edl(path: str | Path, *, run_lint: bool = True) -> dict:
    """读取 edl.json 并跑 lint 契约闸门(fail-fast)。

    数据契约"管线内嵌校验"(DEEP_RESEARCH [28]): 违约不向下游传播。
    run_lint=False 仅用于调试/迁移期读旧文件。
    """
    p = Path(path)
    edl = json.loads(p.read_text(encoding="utf-8"))
    if run_lint:
        errs = lint_edl(edl)
        if errs:
            raise ValueError(f"EDL lint FAIL ({len(errs)}): " + "; ".join(errs[:8]))
    return edl


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="EDL 构建/lint CLI")
    ap.add_argument("production_report")
    ap.add_argument("--bgm", default=None)
    ap.add_argument("--sources", nargs="*", default=None)
    ap.add_argument("--style", default=None)
    ap.add_argument("--theme", default=None)
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("-o", "--out", default=None, help="edl.json 输出路径")
    a = ap.parse_args()
    edl = build_edl(a.production_report, bgm_path=a.bgm, sources=a.sources,
                    style=a.style, theme=a.theme, duration=a.duration)
    errs = lint_edl(edl)
    out = Path(a.out) if a.out else Path(a.production_report).parent / "edl.json"
    save_edl(edl, out)
    print(f"EDL: {out}  cuts={len(edl['cuts'])}  inputs={len(edl['inputs'])}")
    if errs:
        print(f"LINT FAIL ({len(errs)}):")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("LINT PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
