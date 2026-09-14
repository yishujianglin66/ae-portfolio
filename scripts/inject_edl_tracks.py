"""Step2: 把 run 的 effects/text_events 折回 edl.json（事后回填, 幂等）。

背景 (chicken-egg, 见 patches/Step2 草案 §〇):
  EDL 在剪切装配期 (unified_edit.py L525 build_edl) 构建, 只有 cuts;
  effects/text_events 是后续 polish/text 阶段 (build_master_polish/build_text_overlay)
  现场生成的。本脚本在那些阶段跑完后, 把结果折回 edl.json, 使 EDL 成为"已应用"的
  完整审计真源, 供两个消费端 --edl replay (可复现, 无现场重规划漂移)。

effects 权威源解析优先级 (消除 run53 有 3 个 *effects*.json 的歧义):
  1. --effects-file 显式指定 (最高)
  2. production_report.effects_source (若上游记录所用路径; 前向兼容 mastercut_agent 接线)
  3. run_dir 下自动探测 *effects*.json: 恰一个 → 用; 多个 → 告警并要求 --effects-file (不猜)
text_events ← run_dir/text_overlay/events.json 的 events 数组 (无歧义)。

用法:
  python scripts/inject_edl_tracks.py <run_dir> [--effects-file <path>] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.edl import (  # noqa: E402
    load_edl, save_edl, lint_edl, EDL_SCHEMA_VERSION,
)

RUN_DIR_PATTERN = r"unified_(?:run\d+|r1_fixed_v\d+)"   # 与两 build 脚本对齐


def _resolve_effects_file(run_dir: Path, explicit: str | None,
                          pr: dict) -> tuple[Path | None, str]:
    """返回 (effects_file | None, note)。优先级: 显式 > production_report > 自动探测(唯一才用)。"""
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = (run_dir / p) if (run_dir / p).exists() else (ROOT / p)
        return (p if p.exists() else None), f"--effects-file 显式: {p}"
    rec = pr.get("effects_source")
    if rec:
        p = Path(rec)
        if not p.is_absolute():
            p = run_dir / p
        return (p if p.exists() else None), f"production_report.effects_source: {p}"
    cands = sorted(run_dir.glob("*effects*.json"))
    if len(cands) == 1:
        return cands[0], f"自动探测唯一: {cands[0].name}"
    if len(cands) > 1:
        names = ", ".join(c.name for c in cands)
        return None, (f"[WARN] 探测到 {len(cands)} 个 effects 文件({names}) — 歧义; "
                      f"须 --effects-file 指定权威源, 本次不注入 effects 轨")
    return None, "[SKIP] run_dir 无 *effects*.json, 跳过 effects 轨"


def inject_edl_tracks(run_dir: Path, effects_file: str | None = None,
                      dry_run: bool = False) -> dict:
    """把 effects/text_events 折回 run_dir/edl.json (幂等: 覆盖轨道而非追加)。

    返回 report dict (effects_injected/text_events_injected/notes/lint_errors/saved)。
    dry_run=True 时只报告将注入什么, 不写盘。
    """
    run_dir = Path(run_dir)
    edl_p = run_dir / "edl.json"
    report: dict = {"run_dir": str(run_dir), "dry_run": dry_run, "saved": None,
                    "effects_injected": 0, "text_events_injected": 0,
                    "notes": [], "lint_errors": []}
    if not edl_p.exists():
        report["notes"].append(f"[SKIP] 缺 {edl_p.name} — 须先跑 unified_edit 生成 EDL")
        return report

    edl = load_edl(edl_p, run_lint=False)      # 读旧 (可能 1.0 / 无轨道)
    edl["schema_version"] = EDL_SCHEMA_VERSION  # 统一升到当前版本

    pr_p = run_dir / "production_report.json"
    pr = json.loads(pr_p.read_text(encoding="utf-8")) if pr_p.exists() else {}

    # text_events ← events.json 的 events 数组 (完整事件表, 无歧义)
    ev_p = run_dir / "text_overlay" / "events.json"
    if ev_p.exists():
        _ev = json.loads(ev_p.read_text(encoding="utf-8")).get("events", [])
        edl["text_events"] = _ev
        report["text_events_injected"] = len(_ev)
        report["notes"].append(f"text_events <- text_overlay/events.json ({len(_ev)} 条)")
    else:
        report["notes"].append("[SKIP] 无 text_overlay/events.json, 跳过 text_events 轨")

    # effects ← 权威源解析
    eff_p, eff_note = _resolve_effects_file(run_dir, effects_file, pr)
    report["notes"].append(eff_note)
    if eff_p:
        _eff = json.loads(eff_p.read_text(encoding="utf-8"))
        if isinstance(_eff, dict):
            _eff = _eff.get("effects") or _eff.get("effect_configs") or []
        edl["effects"] = _eff
        report["effects_injected"] = len(_eff)

    report["lint_errors"] = lint_edl(edl)       # 回填后过契约闸门
    if not dry_run:
        save_edl(edl, edl_p)
        report["saved"] = str(edl_p)
    return report


def main() -> int:
    # Windows GBK 下 print 中文/符号到管道会崩 → CLI 入口强制 UTF-8 (放 main 不改导入方全局)
    for _s in (sys.stdout, sys.stderr):
        reconfigure = getattr(_s, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except ValueError:
                pass
    ap = argparse.ArgumentParser(
        prog="inject_edl_tracks.py",
        description="把 run 的 effects/text_events 折回 edl.json (事后回填, 幂等)")
    ap.add_argument("run_dir", help="run 目录, 白名单 unified_run<N> | unified_r1_fixed_v<N>")
    ap.add_argument("--effects-file", dest="effects_file", default=None,
                    help="effects 轨权威源 (schema 格式 json); 多候选时必填以消歧义")
    ap.add_argument("--dry-run", action="store_true", help="只报告将注入什么, 不写 edl.json")
    a = ap.parse_args()

    raw = str(a.run_dir).replace("\\", "/").removeprefix("output/")
    if not re.fullmatch(RUN_DIR_PATTERN, raw):
        print(f"[ERR] 非法 run 目录名(白名单 unified_run<N> | unified_r1_fixed_v<N>): {raw}")
        return 2
    run_dir = ROOT / "output" / raw

    rep = inject_edl_tracks(run_dir, effects_file=a.effects_file, dry_run=a.dry_run)
    _lint = "PASS" if not rep["lint_errors"] else f"FAIL {len(rep['lint_errors'])}"
    _dr = " (dry-run, 未写)" if rep["dry_run"] else ""
    print(f"[inject] effects={rep['effects_injected']} "
          f"text_events={rep['text_events_injected']} lint={_lint}{_dr}")
    for n in rep["notes"]:
        print(f"  - {n}")
    for e in rep["lint_errors"][:8]:
        print(f"  [lint] {e}")
    return 1 if rep["lint_errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
