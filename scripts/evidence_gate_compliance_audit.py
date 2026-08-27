#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evidence_gate_compliance_audit.py — 证据闸门合规自检工具链

将项目五道证据闸门 (铁律来源: commit f4f738c, 定义见
03-阶段报告/2026-08-24_运镜v6交接归档/v6_transition_report_20260824.md §8)
机器化, 并映射到国标锚点:

  - GB/T 47507-2026 《人工智能 可信赖 通则》(2026-04-30 发布, 2026-08-01 实施)
    可信赖特性维度: 透明性/可解释、稳健性、安全性、可问责/可追溯
  - GB/T 45652-2025 《网络安全技术 生成式人工智能预训练和优化训练数据安全规范》
    训练数据环节: 数据来源合法真实、标注质量、清洗过滤、数据可追溯

五道闸门:
  🚪1 存在性          声明的全部产物文件必须真实存在 (大小/行数实测)
  🚪2 首行证据        数据决策基于真实首行字段 + 实测分布, 禁止凭文件名推测
  🚪3 三对齐          模型签名(类数) × 数据签名(类名集合) × 类名清单严格一致
  🚪4 快照失效        结论需时间戳; 产物哈希变化 → 相关结论自动降级为"待重测"
  🚪5 PLAN/READY 分级 清单条目必须显式分级, 禁止混用

诚实声明: 国标全文离线不可得, 条款映射基于标准公开披露的维度框架,
报告中逐条标注映射依据; 拿到标准全文后可在 STANDARD_MAP 中细化到条款号。

用法:
  # 按规格文件审计
  python -m scripts.evidence_gate_compliance_audit --config audit_spec.json --out reports/compliance
  # 快速示例 (运镜 4 元类标签集)
  python -m scripts.evidence_gate_compliance_audit --example camera4 --out reports/compliance

规格文件 (JSON) 字段:
  title            报告标题
  files            [str] 必须存在的产物路径 (闸门1)
  label_file       str  jsonl 标签文件 (闸门2/3)
  label_field      str  标签字段名 (默认 label)
  expected_classes [str] 预期类名清单 (闸门3)
  num_classes      int  模型签名类数 (闸门3, 与 expected_classes 长度比对)
  manifest         [{"item","level","file"?}] PLAN/READY 分级清单 (闸门5)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ────────────────────────────────────────────────────────────────────────────
# 国标映射表 (诚实声明: 基于公开披露维度框架, 非全文逐条对照)
# ────────────────────────────────────────────────────────────────────────────
STD_47507 = "GB/T 47507-2026《人工智能 可信赖 通则》"
STD_45652 = "GB/T 45652-2025《网络安全技术 生成式人工智能预训练和优化训练数据安全规范》"

STANDARD_MAP: Dict[str, List[Dict[str, str]]] = {
    "gate1": [
        {"standard": STD_47507, "dimension": "可问责/可追溯",
         "basis": "结论所依赖产物必须可核验存在, 支撑事后追溯"},
        {"standard": STD_45652, "dimension": "训练数据来源真实性",
         "basis": "数据收集环节要求来源真实可查, 不得以虚构数据入库"},
    ],
    "gate2": [
        {"standard": STD_45652, "dimension": "数据预处理/标注质量",
         "basis": "预处理与标注环节要求基于真实数据内容做质量判断"},
        {"standard": STD_47507, "dimension": "透明性/可解释",
         "basis": "数据决策依据须可见(首行+分布), 结论才可解释"},
    ],
    "gate3": [
        {"standard": STD_45652, "dimension": "模型训练数据一致性",
         "basis": "训练配置与数据集(类别空间)必须一致, 防止口径漂移"},
        {"standard": STD_47507, "dimension": "稳健性",
         "basis": "签名不一致的训练产物不可稳健复现"},
    ],
    "gate4": [
        {"standard": STD_47507, "dimension": "可问责/可追溯(版本)",
         "basis": "结论必须绑定时间戳与数据快照, 数据变更则结论失效"},
        {"standard": STD_45652, "dimension": "数据更新环节",
         "basis": "数据更新后需重新评估, 旧评估结论不得沿用"},
    ],
    "gate5": [
        {"standard": STD_47507, "dimension": "透明性/可解释",
         "basis": "PLAN(计划)与READY(已验证)混用会误导使用者, 违背透明性"},
    ],
}

GATE_NAMES = {
    "gate1": "🚪1 存在性",
    "gate2": "🚪2 首行证据",
    "gate3": "🚪3 三对齐",
    "gate4": "🚪4 快照失效",
    "gate5": "🚪5 PLAN/READY 分级",
}

VALID_LEVELS = {"PLAN", "READY"}


# ────────────────────────────────────────────────────────────────────────────
# 数据结构
# ────────────────────────────────────────────────────────────────────────────
@dataclass
class GateResult:
    gate: str                     # gate1..gate5
    name: str
    passed: bool
    checks: List[Dict[str, Any]] = field(default_factory=list)
    standards: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.gate, "name": self.name, "passed": self.passed,
            "checks": self.checks, "standards": self.standards,
        }


@dataclass
class AuditSpec:
    title: str = "证据闸门合规审计"
    files: List[str] = field(default_factory=list)
    label_file: str = ""
    label_field: str = "label"
    expected_classes: List[str] = field(default_factory=list)
    num_classes: int = 0
    manifest: List[Dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuditSpec":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


# ────────────────────────────────────────────────────────────────────────────
# 工具函数
# ────────────────────────────────────────────────────────────────────────────
def _sha256(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _count_lines(path: Path) -> int:
    n = 0
    with path.open("rb") as f:
        for _ in f:
            n += 1
    return n


def _load_jsonl_labels(path: Path, label_field: str) -> List[str]:
    labels: List[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            v = r.get(label_field)
            if v is not None:
                labels.append(str(v))
    return labels


# ────────────────────────────────────────────────────────────────────────────
# 五道闸门
# ────────────────────────────────────────────────────────────────────────────
def gate1_existence(spec: AuditSpec) -> GateResult:
    """🚪1 存在性: 声明的全部产物必须存在 (大小/行数实测)"""
    checks: List[Dict[str, Any]] = []
    ok = True
    for fp in spec.files:
        p = Path(fp)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if p.exists():
            entry: Dict[str, Any] = {"file": str(p.name), "status": "OK",
                                     "size_bytes": p.stat().st_size}
            if p.suffix == ".jsonl":
                entry["lines"] = _count_lines(p)
            checks.append(entry)
        else:
            checks.append({"file": str(p), "status": "MISS"})
            ok = False
    if not spec.files:
        checks.append({"file": "(none declared)", "status": "SKIP"})
    return GateResult("gate1", GATE_NAMES["gate1"], ok or not spec.files,
                      checks, STANDARD_MAP["gate1"])


def gate2_first_line(spec: AuditSpec) -> GateResult:
    """🚪2 首行证据: 真实首行字段 + 实测分布"""
    checks: List[Dict[str, Any]] = []
    if not spec.label_file:
        return GateResult("gate2", GATE_NAMES["gate2"], True,
                          [{"status": "SKIP", "reason": "no label_file"}],
                          STANDARD_MAP["gate2"])
    p = Path(spec.label_file)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    if not p.exists():
        return GateResult("gate2", GATE_NAMES["gate2"], False,
                          [{"status": "MISS", "file": str(p)}],
                          STANDARD_MAP["gate2"])

    first_line: Optional[str] = None
    fields: List[str] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            first_line = line[:400]
            try:
                fields = list(json.loads(line).keys())
            except json.JSONDecodeError:
                fields = []
            break

    labels = _load_jsonl_labels(p, spec.label_field)
    dist = Counter(labels)
    total = sum(dist.values()) or 1
    checks.append({
        "status": "OK", "file": p.name, "first_line": first_line,
        "fields": fields, "n_rows": len(labels),
        "distribution": {k: {"count": v, "pct": round(100 * v / total, 2)}
                         for k, v in dist.most_common()},
    })
    if first_line is None:
        checks.append({"status": "FAIL", "reason": "标签文件为空, 无首行证据"})
        return GateResult("gate2", GATE_NAMES["gate2"], False,
                          checks, STANDARD_MAP["gate2"])
    return GateResult("gate2", GATE_NAMES["gate2"], True,
                      checks, STANDARD_MAP["gate2"])


def gate3_alignment(spec: AuditSpec) -> GateResult:
    """🚪3 三对齐: 模型签名(类数) × 数据签名(类名集合) × 类名清单"""
    checks: List[Dict[str, Any]] = []
    if not spec.expected_classes or not spec.label_file:
        return GateResult("gate3", GATE_NAMES["gate3"], True,
                          [{"status": "SKIP",
                            "reason": "no expected_classes/label_file"}],
                          STANDARD_MAP["gate3"])
    p = Path(spec.label_file)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    if not p.exists():
        return GateResult("gate3", GATE_NAMES["gate3"], False,
                          [{"status": "MISS", "file": str(p)}],
                          STANDARD_MAP["gate3"])

    got = set(_load_jsonl_labels(p, spec.label_field))
    expected = set(spec.expected_classes)
    aligned = (expected == got)
    checks.append({"signature": "类名清单(预期)", "value": sorted(expected)})
    checks.append({"signature": "数据签名(实测)", "value": sorted(got)})
    checks.append({"signature": "交集", "value": sorted(expected & got)})
    if spec.num_classes:
        checks.append({"signature": "模型签名(num_classes)",
                       "value": spec.num_classes,
                       "match": spec.num_classes == len(expected)})
        aligned = aligned and spec.num_classes == len(expected)
    checks.append({"status": "CHECK 三签名完全一致" if aligned
                   else "CROSS 签名不匹配, 禁止启动训练"})
    return GateResult("gate3", GATE_NAMES["gate3"], aligned,
                      checks, STANDARD_MAP["gate3"])


def gate4_snapshot(spec: AuditSpec, out_dir: Path,
                   prev: Optional[Dict[str, Any]]) -> GateResult:
    """🚪4 快照失效: 产物哈希 + 时间戳; 哈希变化 → 旧结论待重测"""
    checks: List[Dict[str, Any]] = []
    now = datetime.now().isoformat(timespec="seconds")
    hashes: Dict[str, str] = {}
    changed: List[str] = []
    prev_hashes = (prev or {}).get("hashes", {})

    for fp in spec.files:
        p = Path(fp)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if not p.exists():
            continue
        digest = _sha256(p)
        hashes[p.name] = digest
        if p.name in prev_hashes and prev_hashes[p.name] != digest:
            changed.append(p.name)

    snapshot = {"timestamp": now, "hashes": hashes}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    checks.append({"status": "OK", "timestamp": now,
                   "n_files_hashed": len(hashes)})
    if prev:
        if changed:
            checks.append({
                "status": "STALE",
                "changed_files": changed,
                "action": "以下产物自上次审计后已变化, 依赖它们的结论自动降级为【待重测】",
            })
        else:
            checks.append({
                "status": "FRESH",
                "prev_timestamp": prev.get("timestamp", ""),
                "action": "产物哈希未变化, 既有结论仍有效",
            })
    else:
        checks.append({"status": "BASELINE", "action": "首次审计, 建立快照基线"})
    # 快照闸门本身: 只要能产出带时间戳的快照即通过 (失效检测是信息, 不是失败)
    return GateResult("gate4", GATE_NAMES["gate4"], True,
                      checks, STANDARD_MAP["gate4"])


def gate5_manifest(spec: AuditSpec) -> GateResult:
    """🚪5 PLAN/READY 分级: 清单条目必须显式分级, 禁止混用"""
    checks: List[Dict[str, Any]] = []
    if not spec.manifest:
        return GateResult("gate5", GATE_NAMES["gate5"], True,
                          [{"status": "SKIP", "reason": "no manifest"}],
                          STANDARD_MAP["gate5"])
    ok = True
    for entry in spec.manifest:
        item = entry.get("item", "(unnamed)")
        level = str(entry.get("level", "")).upper()
        if level not in VALID_LEVELS:
            checks.append({"item": item, "status": "FAIL",
                           "reason": f"level={level!r} 非法, 必须为 PLAN/READY"})
            ok = False
            continue
        row: Dict[str, Any] = {"item": item, "level": level, "status": "OK"}
        # READY 条目若附文件, 必须存在 (与闸门1交叉核验)
        if level == "READY" and entry.get("file"):
            p = Path(entry["file"])
            if not p.is_absolute():
                p = PROJECT_ROOT / p
            if not p.exists():
                row["status"] = "FAIL"
                row["reason"] = f"READY 声明但文件不存在: {p}"
                ok = False
        checks.append(row)
    return GateResult("gate5", GATE_NAMES["gate5"], ok,
                      checks, STANDARD_MAP["gate5"])


# ────────────────────────────────────────────────────────────────────────────
# 主流程与报告
# ────────────────────────────────────────────────────────────────────────────
def run_audit(spec: AuditSpec, out_dir: Path) -> Dict[str, Any]:
    """执行五道闸门审计, 写报告到 out_dir, 返回汇总 dict"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prev_snapshot: Optional[Dict[str, Any]] = None
    prev_path = out_dir / "snapshot.json"
    if prev_path.exists():
        try:
            prev_snapshot = json.loads(prev_path.read_text(encoding="utf-8"))
        except Exception:
            prev_snapshot = None

    results = [
        gate1_existence(spec),
        gate2_first_line(spec),
        gate3_alignment(spec),
        gate4_snapshot(spec, out_dir, prev_snapshot),
        gate5_manifest(spec),
    ]
    all_passed = all(r.passed for r in results)

    report = {
        "title": spec.title,
        "audited_at": datetime.now().isoformat(timespec="seconds"),
        "overall": "PASS" if all_passed else "FAIL",
        "gates": [r.to_dict() for r in results],
        "standards_anchored": [STD_47507, STD_45652],
        "honesty_note": (
            "国标全文离线不可得; 条款映射基于标准公开披露的维度框架,"
            " 非全文逐条对照。取得全文后在 STANDARD_MAP 细化到条款号。"
        ),
        "iron_rule": "commit f4f738c: 「已完成」结论必须五道闸门验证后才可登记",
    }

    (out_dir / "compliance_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "compliance_report.md").write_text(
        _render_markdown(report), encoding="utf-8")
    return report


def _render_markdown(report: Dict[str, Any]) -> str:
    lines = [
        f"# {report['title']} — 证据闸门合规报告",
        "",
        f"- 审计时间: {report['audited_at']}",
        f"- 总体结论: **{report['overall']}**",
        f"- 国标锚点: {'; '.join(report['standards_anchored'])}",
        f"- 诚实声明: {report['honesty_note']}",
        "",
        "| 闸门 | 结论 | 国标映射 |",
        "|---|---|---|",
    ]
    for g in report["gates"]:
        stds = "; ".join(
            f"{s['standard']}({s['dimension']})" for s in g["standards"]) or "-"
        mark = "✅" if g["passed"] else "❌"
        lines.append(f"| {g['name']} | {mark} | {stds} |")

    for g in report["gates"]:
        lines.append("")
        lines.append(f"## {g['name']}  {'✅' if g['passed'] else '❌'}")
        for c in g["checks"]:
            lines.append(f"- {json.dumps(c, ensure_ascii=False)}")
    lines.append("")
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────────────
# 内置示例规格
# ────────────────────────────────────────────────────────────────────────────
EXAMPLE_SPECS: Dict[str, Dict[str, Any]] = {
    "camera4": {
        "title": "运镜分类 v6 4元类标签集合规审计",
        "files": [
            "tmp/cloud_labels/v6_meta_4class.jsonl",
            "tmp/cloud_labels/v5_6_labels_final.jsonl",
            "tmp/cloud_labels/vlm_labels_v2new.jsonl",
        ],
        "label_file": "tmp/cloud_labels/v6_meta_4class.jsonl",
        "label_field": "label",
        "expected_classes": [
            "meta-static", "meta-pan", "meta-tilt-orbit", "meta-zoom"],
        "num_classes": 4,
        "manifest": [
            {"item": "v6_meta_4class.jsonl 训练标签", "level": "READY",
             "file": "tmp/cloud_labels/v6_meta_4class.jsonl"},
            {"item": "CameraBench 专家标注训练集", "level": "PLAN"},
        ],
    },
}


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="证据闸门合规自检工具链 (GB/T 47507-2026 + GB/T 45652-2025 锚点)")
    parser.add_argument("--config", type=str, default="",
                        help="审计规格 JSON 文件路径")
    parser.add_argument("--example", type=str, default="",
                        choices=list(EXAMPLE_SPECS.keys()),
                        help="使用内置示例规格")
    parser.add_argument("--out", type=str, default="reports/compliance",
                        help="报告输出目录")
    args = parser.parse_args(argv)

    if args.config:
        spec = AuditSpec.from_dict(
            json.loads(Path(args.config).read_text(encoding="utf-8-sig")))
    elif args.example:
        spec = AuditSpec.from_dict(EXAMPLE_SPECS[args.example])
    else:
        parser.error("需指定 --config 或 --example")
        return 2  # pragma: no cover

    report = run_audit(spec, Path(args.out))
    print(f"总体结论: {report['overall']}")
    for g in report["gates"]:
        print(f"  {'[OK]' if g['passed'] else '[FAIL]'} {g['name']}")
    print(f"报告: {Path(args.out) / 'compliance_report.md'}")
    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
