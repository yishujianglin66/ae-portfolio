#!/usr/bin/env python3
"""
盲评金标准评分引擎 (红线内置)。

裁决红线 (2026-08-31):
  1. 镜头级评估 (本集 91 条均为独立镜头, 时间反转孪生对强制同侧 —— 抽样时已保证)
  2. 必须存在人工核验 hold-out 集 —— 本脚本只在该集上评分
  3. 指标捆绑: 原始准确率 + 平衡准确率 + 0.4387 多数类基线 + 0.3058 标注者一致率,
     永远同屏展示, 缺一即违规。

子命令:
  import <answers.csv> [--force]     合并作答 CSV 到 gold CSV (校验+备份)
  report                             gold 集完整性 / Gate A (unsure<=20%) / 分布
  eval <pred.csv> --name X           对预测评分 (bootstrap CI + 混淆矩阵 + 强制参考线)
  vlm                                用 gold CSV 的 vlm_direction 列作为预测自评
  consistency <r1.csv> <r2.csv>      两轮作答自一致率 (人工上限代理)
  consensus <r1.csv> <r2.csv> --out C [--mode abstain|strict]
                                     两轮作答合成共识 CSV (默认弃权口径, 可直接 import)

所有子命令支持 --gold PATH 覆盖 gold CSV (测试时勿碰真实数据)。

用法:
  py -3.12 scripts/score_blind_gold.py report
  py -3.12 scripts/score_blind_gold.py eval preds.csv --name v3b_lora
"""
from __future__ import annotations

import argparse
import csv
import random
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")
DEFAULT_GOLD = DATA_ROOT / "blind_review" / "blind_answers.csv"

CLASSES = ["static", "zoom_in", "zoom_out",
           "pan_left", "pan_right", "tilt_up", "tilt_down"]
VALID_LABELS = set(CLASSES) | {"unsure"}

# 分类法 v2 (2026-09-02 裁决): 废 orbit(转 unsure), push 并入 zoom_in, zoom_back 并入 zoom_out。
# gold CSV 的 vlm_direction 列封存 10 类原始值, 只在读取时按此表归一化, 不回写。
V1_TO_V2 = {"push": "zoom_in", "zoom_back": "zoom_out", "orbit": "unsure"}


def normalize_v1(label: str) -> str:
    return V1_TO_V2.get(label, label)

# 裁决红线 3: 强制同屏参考线 (历史全量标签集裁决值)
REF_MAJORITY_FLOOR = 0.4387
REF_ANNOTATOR_AGREE = 0.3058

GATE_A_UNSURE_MAX = 0.20
BOOT_N = 2000
BOOT_SEED = 20260901


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    sys.exit(1)


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    if not path.exists():
        fail(f"文件不存在: {path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        if rd.fieldnames is None:
            fail(f"空文件: {path}")
        return list(rd.fieldnames), list(rd)


def load_gold(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    cols, rows = read_csv(path)
    for need in ("index", "shot_id", "human_direction"):
        if need not in cols:
            fail(f"gold CSV 缺列 {need}: {path} (实有 {cols})")
    return cols, rows


def answered_stats(rows: List[Dict[str, str]]) -> Tuple[int, int, int]:
    """返回 (已答数, unsure 数, 总数)。"""
    answered = [r for r in rows if r["human_direction"].strip()]
    unsure = sum(1 for r in answered if r["human_direction"].strip() == "unsure")
    return len(answered), unsure, len(rows)


def print_ref_lines() -> None:
    print("  ── 强制参考线 (红线规定, 必须同屏) ──")
    print(f"  历史多数类基线  : {REF_MAJORITY_FLOOR:.4f} (全量标签集裁决值)")
    print(f"  历史标注者一致率: {REF_ANNOTATOR_AGREE:.4f} (人工上限代理)")


def gate_a_verdict(unsure_rate: float) -> str:
    if unsure_rate > GATE_A_UNSURE_MAX:
        return (f"[Gate A 未通过] unsure 率 {unsure_rate:.1%} > {GATE_A_UNSURE_MAX:.0%}"
                " → 先修分类法 (合并模糊类), 再评估")
    return f"[Gate A 通过] unsure 率 {unsure_rate:.1%} <= {GATE_A_UNSURE_MAX:.0%}, 分类法可用"


def cmd_import(args: argparse.Namespace) -> int:
    cols, rows = load_gold(args.gold)
    by_idx = {r["index"]: r for r in rows}

    acols, arows = read_csv(args.answers)
    for need in ("index", "shot_id", "human_direction"):
        if need not in acols:
            fail(f"作答 CSV 缺列 {need} (实有 {acols})")

    errors, seen = [], set()
    plan: List[Tuple[Dict[str, str], str, str]] = []
    for i, a in enumerate(arows, 2):
        idx, shot, label = a["index"].strip(), a["shot_id"].strip(), a["human_direction"].strip()
        if idx in seen:
            errors.append(f"行{i}: index 重复 {idx}")
            continue
        seen.add(idx)
        if label not in VALID_LABELS:
            errors.append(f"行{i}: 非法标签 '{label}' (允许: {sorted(VALID_LABELS)})")
            continue
        g = by_idx.get(idx)
        if g is None:
            errors.append(f"行{i}: index {idx} 不在 gold 集")
            continue
        if g["shot_id"] != shot:
            errors.append(f"行{i}: shot_id 不匹配 (gold[{idx}]={g['shot_id']}, 输入={shot})")
            continue
        old = g["human_direction"].strip()
        if old and old != label and not args.force:
            errors.append(f"行{i}: index {idx} 已有答案 '{old}', 新值 '{label}' 冲突 (需 --force)")
            continue
        plan.append((g, old, label))

    if errors:
        print(f"[FAIL] 作答 CSV 校验失败 ({len(errors)} 处):")
        for e in errors:
            print(f"  {e}")
        return 1

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = args.gold.with_name(f"{args.gold.stem}.backup_{ts}{args.gold.suffix}")
    shutil.copy2(args.gold, backup)

    for g, _, label in plan:
        g["human_direction"] = label
    with args.gold.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    n_ans, n_unsure, n_total = answered_stats(rows)
    print(f"导入完成: {len(plan)} 条写入 | 备份 -> {backup.name}")
    print(f"进度: {n_ans}/{n_total} 已答 (其中 unsure {n_unsure})")
    if n_ans:
        print(gate_a_verdict(n_unsure / n_ans))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    _, rows = load_gold(args.gold)
    n_ans, n_unsure, n_total = answered_stats(rows)
    print(f"Gold 集: {args.gold}")
    print(f"  总数 {n_total} | 已答 {n_ans} | 未答 {n_total - n_ans} | unsure {n_unsure}")
    if not n_ans:
        print("  [状态] 尚无作答, 无法评估。先用 blind_answer_app.html 作答。")
        print_ref_lines()
        return 0

    dist = Counter(r["human_direction"].strip() for r in rows
                   if r["human_direction"].strip())
    print("  金标准分布:")
    for c in CLASSES:
        print(f"    {c:<10} {dist.get(c, 0):>3}")
    print(f"    {'unsure':<10} {dist.get('unsure', 0):>3}")

    decisive = n_ans - n_unsure
    if decisive > 0:
        top, cnt = Counter(r["human_direction"].strip() for r in rows
                           if r["human_direction"].strip()
                           and r["human_direction"].strip() != "unsure").most_common(1)[0]
        print(f"  本 gold 集多数类基线: {cnt}/{decisive} = {cnt / decisive:.4f} (类={top})")
    print(gate_a_verdict(n_unsure / n_ans))
    print_ref_lines()
    print("  注: n=91 时准确率 95% CI 约 ±10pp, 两模型 CI 重叠即无显著差异。")
    return 0


def _pairs(gold_rows: List[Dict[str, str]],
           preds: Dict[str, str]) -> Tuple[List[Tuple[str, str]], int, int]:
    """返回 ([(gold, pred)] 已答且非unsure且预测覆盖, unsure 数, 未覆盖数)。"""
    pairs, n_unsure, n_missing = [], 0, 0
    for r in gold_rows:
        label = r["human_direction"].strip()
        if not label:
            continue
        if label == "unsure":
            n_unsure += 1
            continue
        p = preds.get(r["shot_id"])
        if p is None:
            n_missing += 1
            continue
        pairs.append((label, p))
    return pairs, n_unsure, n_missing


def _bootstrap_ci(pairs: List[Tuple[str, str]]) -> Tuple[float, float, float]:
    acc = sum(1 for g, p in pairs if g == p) / len(pairs)
    rng = random.Random(BOOT_SEED)
    n = len(pairs)
    stats = []
    for _ in range(BOOT_N):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        stats.append(sum(1 for g, p in sample if g == p) / n)
    stats.sort()
    lo, hi = stats[int(0.025 * BOOT_N)], stats[int(0.975 * BOOT_N)]
    return acc, lo, hi


def _eval_pairs(name: str, pairs: List[Tuple[str, str]],
                n_unsure: int, n_missing: int, n_gold_decisive: int) -> None:
    print(f"评估对象: {name}")
    print(f"  样本: gold 决定性 {n_gold_decisive} | 参与评估 {len(pairs)}"
          f" | unsure 排除 {n_unsure} | 预测缺失 {n_missing}")
    if len(pairs) < 20:
        fail(f"可评估样本 {len(pairs)} < 20, 不足以出指标。")

    acc, lo, hi = _bootstrap_ci(pairs)
    recalls: Dict[str, List[float]] = {}
    per_gold = Counter(g for g, _ in pairs)
    for c in per_gold:
        hits = sum(1 for g, p in pairs if g == c and p == c)
        recalls[c] = [hits / per_gold[c]]
    bal_acc = sum(v[0] for v in recalls.values()) / len(recalls)

    print(f"  原始准确率   : {acc:.4f}  (bootstrap 95% CI [{lo:.4f}, {hi:.4f}], "
          f"{BOOT_N} 次, seed {BOOT_SEED})")
    print(f"  平衡准确率   : {bal_acc:.4f}  (少数类召回均值; 多数类基线高时只看原始准确率会被"
          "「一律猜 static」蒙混)")
    print_ref_lines()
    majority_here = max(per_gold.values()) / len(pairs)
    print(f"  本集多数类基线: {majority_here:.4f} —— 准确率低于此值 = 不如猜多数类")
    if acc - majority_here < 0.05:
        print("  [警告] 准确率距多数类基线 < 5pp, 该模型在此集上无实质判别力。")

    pred_cnt = Counter(p for _, p in pairs)
    disp_cols = CLASSES + (["unsure"] if pred_cnt.get("unsure") else [])
    if pred_cnt.get("unsure"):
        print(f"  [弃权] 预测含 unsure {pred_cnt['unsure']} 条; 对决定性 gold 一律计为错,"
              " 已计入分母, 下方单列显示以免行和对不上")

    print("  逐类 P/R (gold 中出现的类):")
    for c in CLASSES:
        if c not in per_gold:
            continue
        tp = sum(1 for g, p in pairs if g == c and p == c)
        rec = tp / per_gold[c]
        pre = tp / pred_cnt[c] if pred_cnt.get(c) else 0.0
        print(f"    {c:<10} n={per_gold[c]:>3}  P={pre:.3f}  R={rec:.3f}")

    print("  混淆矩阵 (行=gold, 列=pred):")
    mat = Counter(pairs)
    header = " " * 12 + "".join(f"{c[:6]:>7}" for c in disp_cols)
    print(header)
    for g in CLASSES:
        if g not in per_gold:
            continue
        line = f"{g:<12}" + "".join(f"{mat.get((g, p), 0):>7}" for p in disp_cols)
        print(line)
    print(f"  [提示] n={len(pairs)}, CI 约 ±{1.96 * (acc * (1 - acc) / len(pairs)) ** 0.5:.2f}"
          " (正态近似), 两模型 CI 重叠 → 无显著差异, 不得宣布胜者。")


def cmd_eval(args: argparse.Namespace) -> int:
    _, gold_rows = load_gold(args.gold)
    pcols, prows = read_csv(args.pred)
    if "shot_id" not in pcols:
        fail(f"预测 CSV 需含 shot_id 列 (实有 {pcols})")
    if args.pred_col not in pcols:
        fail(f"预测列 '{args.pred_col}' 不存在 (实有 {pcols})")

    preds: Dict[str, str] = {}
    bad: Counter = Counter()
    for r in prows:
        v = r[args.pred_col].strip()
        if v not in VALID_LABELS:
            bad[v] += 1
        preds[r["shot_id"]] = v
    if bad:
        fail(f"预测值含非法标签 (须为 v2 的 {len(CLASSES)} 类之一或 unsure): {dict(bad)}。"
             "旧 10 类预测请先归一化 (push→zoom_in, zoom_back→zoom_out, orbit→unsure)。")
    n_abstain = sum(1 for v in preds.values() if v == "unsure")
    if n_abstain:
        print(f"[说明] 预测含 unsure(弃权) {n_abstain} 条, 对决定性 gold 一律计为错。")

    pairs, n_unsure, n_missing = _pairs(gold_rows, preds)
    n_decisive = sum(1 for r in gold_rows
                     if r["human_direction"].strip() not in ("", "unsure"))
    _eval_pairs(args.name, pairs, n_unsure, n_missing, n_decisive)
    return 0


def cmd_vlm(args: argparse.Namespace) -> int:
    cols, gold_rows = load_gold(args.gold)
    if "vlm_direction" not in cols:
        fail("gold CSV 无 vlm_direction 列, 无法自评。")

    preds: Dict[str, str] = {}
    remapped: Counter = Counter()
    bad: Counter = Counter()
    for r in gold_rows:
        raw = r["vlm_direction"].strip()
        v2 = normalize_v1(raw)
        if v2 not in VALID_LABELS:
            bad[raw] += 1
            continue
        if v2 != raw:
            remapped[f"{raw}→{v2}"] += 1
        preds[r["shot_id"]] = v2
    if bad:
        fail(f"vlm_direction 含无法归一化到 v2 的值: {dict(bad)}。"
             f"合法 v2 标签: {sorted(VALID_LABELS)}")

    print("[说明] 以 vlm_direction 为预测、人工答案为 gold, 衡量 VLM 标注与人工的一致性。")
    print("[说明] vlm_direction 封存的是旧 10 类原始值, 此处按 v2 机械归一化后比对 (不回写 gold):")
    if remapped:
        for k in sorted(remapped):
            print(f"    重映射 {k}: {remapped[k]} 条")
        if remapped.get("orbit→unsure"):
            print(f"    其中 orbit→unsure 的 {remapped['orbit→unsure']} 条在 v2 下结构性不可能命中,"
                  " 一律计为错 —— 这部分损失来自分类法变更, 不是 VLM 判错。")
    else:
        print("    无需重映射 (vlm_direction 已全部落在 v2 标签内)。")

    pairs, n_unsure, n_missing = _pairs(gold_rows, preds)
    n_decisive = sum(1 for r in gold_rows
                     if r["human_direction"].strip() not in ("", "unsure"))
    _eval_pairs("vlm_direction (VLM 自评, v2 归一化后)", pairs, n_unsure, n_missing, n_decisive)
    return 0


def cmd_consistency(args: argparse.Namespace) -> int:
    _, r1 = read_csv(args.r1)
    _, r2 = read_csv(args.r2)
    m1 = {r["shot_id"]: r["human_direction"].strip() for r in r1 if r["human_direction"].strip()}
    m2 = {r["shot_id"]: r["human_direction"].strip() for r in r2 if r["human_direction"].strip()}
    common = sorted(set(m1) & set(m2))
    if len(common) < 20:
        fail(f"两轮共同作答仅 {len(common)} 条 < 20, 无法计算自一致率。")
    agree = sum(1 for s in common if m1[s] == m2[s])
    flips = [(s, m1[s], m2[s]) for s in common if m1[s] != m2[s]]
    rate = agree / len(common)
    print(f"两轮自一致率: {agree}/{len(common)} = {rate:.4f}")
    print(f"  (人工上限代理; 历史参考 {REF_ANNOTATOR_AGREE:.4f}。一致率越高, 模型可达上限越高)")
    if flips:
        print(f"  翻转 {len(flips)} 处:")
        for s, a, b in flips:
            print(f"    {s}: {a} -> {b}")
    return 0


def cmd_consensus(args: argparse.Namespace) -> int:
    """把两轮作答合成一份可直接 import 的共识 CSV。

    abstain (默认): unsure 是弃权, 不是反对票 —— 一轮判定 + 一轮弃权 → 取判定值;
                    两轮都判定但不同 → unsure。
    strict        : 两轮不完全相同即 unsure (第一/二轮的历史口径, 会把弃权算成反对)。
    """
    acols, arows = read_csv(args.r1)
    bcols, brows = read_csv(args.r2)
    for path, cols in ((args.r1, acols), (args.r2, bcols)):
        for need in ("index", "shot_id", "human_direction"):
            if need not in cols:
                fail(f"{path} 缺列 {need} (实有 {cols})")

    def keyed(rows: List[Dict[str, str]], path: Path) -> Dict[str, Tuple[str, str]]:
        d: Dict[str, Tuple[str, str]] = {}
        for r in rows:
            idx, lab = r["index"].strip(), r["human_direction"].strip()
            if not lab:
                fail(f"{path} index {idx} 未作答, 无法参与共识")
            if lab not in VALID_LABELS:
                fail(f"{path} index {idx} 非法标签 '{lab}'")
            if idx in d:
                fail(f"{path} index {idx} 重复")
            d[idx] = (r["shot_id"].strip(), lab)
        return d

    ra, rb = keyed(arows, args.r1), keyed(brows, args.r2)
    if set(ra) != set(rb):
        diff = sorted(set(ra) ^ set(rb), key=int)
        fail(f"两轮 index 集不一致, 差 {len(diff)} 条: {diff[:10]}")
    mismatched = [i for i in ra if ra[i][0] != rb[i][0]]
    if mismatched:
        fail(f"两轮 shot_id 不匹配 {len(mismatched)} 处: {mismatched[:5]}")

    rows_out, audit = [], []
    for i in sorted(ra, key=int):
        a, b = ra[i][1], rb[i][1]
        if a == b:
            lab, why = a, ""
        elif args.mode == "strict":
            lab, why = "unsure", f"严格口径不一致: {a} vs {b}"
        elif a == "unsure":
            lab, why = b, f"前轮弃权, 取后轮 {b}"
        elif b == "unsure":
            lab, why = a, f"后轮弃权, 取前轮 {a}"
        else:
            lab, why = "unsure", f"两轮判定冲突 {a} vs {b}"
        rows_out.append({"index": i, "shot_id": ra[i][0], "human_direction": lab})
        if why:
            audit.append((ra[i][0], why))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["index", "shot_id", "human_direction"])
        w.writeheader()
        w.writerows(rows_out)

    dist = Counter(r["human_direction"] for r in rows_out)
    n, n_unsure = len(rows_out), dist.get("unsure", 0)
    decisive = n - n_unsure
    print(f"共识 CSV -> {args.out}")
    print(f"  口径 {args.mode} | 条目 {n} | 决定性 {decisive} | unsure {n_unsure}")
    print("  分布:")
    for c in CLASSES:
        if dist.get(c):
            print(f"    {c:<10} {dist[c]:>3}")
    print(f"    {'unsure':<10} {n_unsure:>3}")
    if decisive:
        top, cnt = max(((c, dist[c]) for c in CLASSES if dist.get(c)), key=lambda x: x[1])
        print(f"  多数类基线 (决定性): {cnt}/{decisive} = {cnt / decisive:.4f} (类={top})")
    print(gate_a_verdict(n_unsure / n))
    print_ref_lines()
    if audit:
        print(f"  非平凡裁决 {len(audit)} 处:")
        for shot, why in audit:
            print(f"    {shot}: {why}")
    print(f"  下一步: import {args.out} --force")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="盲评金标准评分引擎 (红线内置)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("import", help="合并作答 CSV 到 gold CSV")
    p.add_argument("answers", type=Path)
    p.add_argument("--force", action="store_true", help="允许覆盖已有答案")
    p.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    p.set_defaults(fn=cmd_import)

    p = sub.add_parser("report", help="gold 集完整性报告")
    p.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("eval", help="评估预测 CSV")
    p.add_argument("pred", type=Path)
    p.add_argument("--name", required=True)
    p.add_argument("--pred-col", default="pred_direction")
    p.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    p.set_defaults(fn=cmd_eval)

    p = sub.add_parser("vlm", help="用 vlm_direction 自评")
    p.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    p.set_defaults(fn=cmd_vlm)

    p = sub.add_parser("consistency", help="两轮作答自一致率")
    p.add_argument("r1", type=Path)
    p.add_argument("r2", type=Path)
    p.set_defaults(fn=cmd_consistency)

    p = sub.add_parser("consensus", help="两轮作答合成共识 CSV (可直接 import)")
    p.add_argument("r1", type=Path)
    p.add_argument("r2", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--mode", choices=["abstain", "strict"], default="abstain",
                   help="abstain=unsure 视为弃权(默认); strict=两轮不同即 unsure")
    p.set_defaults(fn=cmd_consensus)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
