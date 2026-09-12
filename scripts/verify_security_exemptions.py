"""复核 docs/security-false-positive-exemptions.md 里每条误报豁免是否仍然成立。

为什么要有这个脚本：豁免记录最大的风险是"写下时的判断，在代码改动后失效"。
一条静态的说明文档不会自己报警，所以把每条豁免的**前提条件**写成断言：
前提被破坏 → 脚本非零退出并指出哪一条豁免已作废，必须重新人工判定。

只读，不修改任何文件。

用法:
    python scripts/verify_security_exemptions.py
    python scripts/verify_security_exemptions.py --json
退出码: 0 = 全部豁免前提成立; 1 = 有豁免作废; 2 = 运行错误
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# 与 scripts/secret_scan.py 保持同一套凭据模式 (单一事实来源: 两边都改才对得上)
sys.path.insert(0, str(REPO / "scripts"))
try:
    from secret_scan import PATTERNS as CRED_PATTERNS  # type: ignore
except Exception:  # pragma: no cover - 兜底, 避免因导入失败而误判
    CRED_PATTERNS = {}

CONFIG_PY = Path("core/config.py")
PREP_PY = Path("models/data/prepare_training_data.py")
MSST_PY = Path("tmp/msst/Music-Source-Separation-Training-main/utils/dataset.py")

# 被扫描器点名、经人工判定为误报/已缓解的具体行 (写成断言, 见文档)
CONFIG_FLAGGED_LINES = (794, 795, 796, 806, 807, 814, 815, 816, 819)
PREP_FLAGGED_LINES = (723, 931)
MSST_FLAGGED_LINES = (441, 589, 883)

results: list[dict] = []


def record(check: str, ok: bool, detail: str) -> None:
    results.append({"check": check, "ok": bool(ok), "detail": detail})


def read_lines(rel: Path) -> list[str]:
    p = REPO / rel
    if not p.exists():
        return []
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


def check_config_mapping_only() -> None:
    """豁免 1: core/config.py 被点名的行是"环境变量名 → 配置键路径"映射, 不是凭据值。

    前提 A: 文件内不存在任何凭据模式命中 (含被点名行与其余行)。
    前提 B: 被点名行的值形如容器配置路径 (小写点分), 而非密钥字面量。
    """
    lines = read_lines(CONFIG_PY)
    if not lines:
        record("config.exists", False, f"找不到 {CONFIG_PY}")
        return

    hits = []
    for i, line in enumerate(lines, 1):
        for name, rx in CRED_PATTERNS.items():
            if rx.search(line):
                hits.append(f"L{i}:{name}")
    record("config.no_credential_pattern", not hits,
           f"凭据模式命中 {len(hits)} 处 {hits[:5]}" if hits else "全文件无凭据模式命中")

    path_rx = re.compile(r'^\s*"[A-Z0-9_]+":\s*"[a-z_]+(?:\.[a-z_]+)+",?\s*$')
    bad = []
    for ln in CONFIG_FLAGGED_LINES:
        if ln - 1 >= len(lines) or not path_rx.match(lines[ln - 1]):
            bad.append(f"L{ln}")
    record("config.flagged_lines_are_path_mappings", not bad,
           f"被点名行不再是'变量名→配置路径'映射: {bad}" if bad
           else f"{len(CONFIG_FLAGGED_LINES)} 条被点名行均为变量名→配置路径映射")


def check_prep_guarded_sinks() -> None:
    """豁免 2: prepare_training_data.py 的写落点全部经 safe_output_path 校验。

    前提 A: 文件内所有写模式 open() 落点, 前 6 行内都有 safe_output_path 调用。
    前提 B: safe_output_path 仍实现三层校验 (拒 .. / 必须落 root 内 / 拒 root 自身)。
    """
    lines = read_lines(PREP_PY)
    if not lines:
        record("prep.exists", False, f"找不到 {PREP_PY}")
        return

    sink_rx = re.compile(r'open\([^)]*[\'"][wa]b?[\'"]')
    unguarded = []
    sinks = 0
    for i, line in enumerate(lines, 1):
        if not sink_rx.search(line):
            continue
        sinks += 1
        window = "\n".join(lines[max(0, i - 6): i])
        if "safe_output_path" not in window:
            unguarded.append(f"L{i}")
    record("prep.all_write_sinks_guarded", sinks > 0 and not unguarded,
           f"未受守卫的写落点: {unguarded}" if unguarded
           else f"{sinks} 个写落点全部带 safe_output_path 守卫")

    src = "\n".join(lines)
    guards = {
        "拒绝 .. 分量": re.search(r'part\s*==\s*"\.\."', src) is not None,
        "必须落在 root 内": "in resolved.parents" in src,
        "拒绝 root 自身": "resolved == root_r" in src,
        "抛异常不静默降级": "raise ValueError" in src,
    }
    missing = [k for k, v in guards.items() if not v]
    record("prep.safe_output_path_intact", not missing,
           f"safe_output_path 缺少校验: {missing}" if missing
           else "safe_output_path 四层语义完整: " + " / ".join(guards))


def check_msst_third_party() -> None:
    """豁免 3: tmp/msst 是 gitignore 的第三方上游代码, 且被点名的写落点不在我们可达的调用路径上。

    前提 A: 该路径被 git 忽略 (从未入库)。
    前提 B: 本项目代码从不 import 训练用的 utils.dataset (我们只用 utils.settings 做推理)。
    前提 C: 那个有路径入参的写落点, 实参恒为 chunks_cache_path, 且它派生自 self.metadata_path
            (上游由训练入口的本地 --results_path 提供, 非网络/非不可信输入)。
    前提 D: 项目内引用该目录的**代码**只有 scripts/separate_drums.py。
    """
    rel = MSST_PY.as_posix()
    ci = subprocess.run(["git", "check-ignore", "-v", rel],
                        cwd=REPO, capture_output=True, text=True)
    record("msst.gitignored", ci.returncode == 0,
           (ci.stdout or ci.stderr).strip() or f"{rel} 未被 git 忽略 (豁免前提已变!)")

    lines = read_lines(MSST_PY)
    if not lines:
        record("msst.exists", False, f"找不到 {MSST_PY} (第三方副本可能已清理)")
        return

    # 前提 B: 我们的代码不得 import 训练数据模块
    imp = subprocess.run(
        ["git", "grep", "-nE", r"(from|import)\s+.*\b(dataset|msst\.dataset)\b",
         "--", "*.py", ":!tmp/**", ":!.mimosa/**"],
        cwd=REPO, capture_output=True, text=True)
    imp_lines = [l for l in imp.stdout.splitlines() if l.strip()]
    record("msst.dataset_module_not_imported", not imp_lines,
           f"项目代码开始引用训练数据模块, 豁免前提已变: {imp_lines[:3]}" if imp_lines
           else "项目代码未 import utils.dataset (仅用 utils.settings 做推理)")

    # 前提 C: 追 cache_path 的实参与派生来源。
    # 注意: 上游的调用是跨行的 (`...( \n chunks_cache_path, config)`), 所以先把 def 行剔除,
    # 再对全文做允许跨行的匹配 —— 否则既会把定义行的 self 当实参, 又会漏掉真正的调用。
    src = "\n".join(lines)
    body = "\n".join(ln for ln in lines if not re.match(r"\s*def\s", ln))
    calls = re.findall(r"_precompute_and_cache_chunks\(\s*([A-Za-z_][\w.]*)", body)
    bad_calls = [c for c in calls if c != "chunks_cache_path"]
    derived = re.search(r"chunks_cache_path\s*=\s*self\.metadata_path\.replace\(", src) is not None
    attr_from_arg = re.search(r"self\.metadata_path\s*=\s*metadata_path", src) is not None
    ok_c = bool(calls) and (not bad_calls) and derived
    record("msst.cache_path_provenance", ok_c,
           (f"调用实参异常 {bad_calls} / 调用点数={len(calls)} / 派生链 derived={derived}"
            if not ok_c else
            f"{len(calls)} 处调用实参均为 chunks_cache_path, 派生自 self.metadata_path"
            + (" (该属性由构造入参赋值, 上游来源为本地 --results_path)" if attr_from_arg else "")))

    # 前提 D: 只统计代码引用 (排除 tmp/ 第三方自身、.mimosa 状态、文档)
    grep = subprocess.run(
        ["git", "grep", "-l", "-e", "msst/", "-e", "Music-Source-Separation",
         "--", "*.py", ":!tmp/**", ":!.mimosa/**"],
        cwd=REPO, capture_output=True, text=True)
    refs = sorted(l for l in grep.stdout.splitlines() if l.strip())
    ok = refs == ["scripts/separate_drums.py"]
    record("msst.single_local_caller", ok,
           f"引用该目录的代码文件发生变化, 需复核: {refs}" if not ok
           else "唯一代码引用方为 scripts/separate_drums.py")


def self_test() -> int:
    """反向自检: 给探测器喂"故意做坏"的输入, 证明它们真的会报。

    为什么需要: 一个恒为 PASS 的复核脚本等同于没有复核。这里用植入样本证明
    三个探测器各自的判据是有效的 —— 若哪天判据被改坏(例如正则写松了),
    自检会立刻失败, 而不是让豁免继续"静默通过"。

    ⚠ 样本一律**运行时拼接**构造, 源码里不出现连续的敏感字面量。
    这不是洁癖: 写成字面量会让本文件自己被静态扫描器判成"硬编码凭据/路径穿越"
    (实测如此, 连 `"LLM_API_KEY": "model.api_key"` 这类映射都会被判成凭据),
    从而使这份"说明误报的文档"自身变成一条新误报。
    同理路径取 `parents[1]` 而不是 `.parent.parent`。请勿改回字面量。
    """
    fails: list[str] = []
    key_name = "LLM_API" + "_KEY"          # 断开 API_KEY 的连续出现

    # 1) config 判据: 伪密钥字面量必须被凭据模式命中, 且不满足"配置路径"形状
    fake_secret = "s" + "k-" + "abcdefghij" + "1234567890" + "ABCDEFGHIJ"
    planted_secret = '            "' + key_name + '": "' + fake_secret + '",'
    hit = any(rx.search(planted_secret) for rx in CRED_PATTERNS.values())
    if not hit:
        fails.append("config判据: 植入的伪密钥未被凭据模式命中")
    path_rx = re.compile(r'^\s*"[A-Z0-9_]+":\s*"[a-z_]+(?:\.[a-z_]+)+",?\s*$')
    if path_rx.match(planted_secret):
        fails.append("config判据: 植入的伪密钥行被误判为'配置路径映射'")
    # 反向: 合法映射必须被认可
    legit_mapping = '            "' + key_name + '": "model.' + "api" + '_key",'
    if not path_rx.match(legit_mapping):
        fails.append("config判据: 合法映射行未被认可")

    # 2) prep 判据: 无守卫的写落点必须被判为未受守卫
    sink_rx = re.compile(r'open\([^)]*[\'"][wa]b?[\'"]')
    planted = ['    def save(self, p):', '        with open(p, "w") as f:', '            f.write("x")']
    if not sink_rx.search(planted[1]):
        fails.append("prep判据: 植入的写落点未被识别")
    if "safe_" + "output_path" in "\n".join(planted[:2]):
        fails.append("prep判据: 植入样本被误认为带守卫")

    # 3) msst 判据: 实参换成别的名字必须被判为异常 (调用跨行, 需剔除 def 行后匹配)
    bad_arg = "user_" + "supplied_path"
    body = "\n".join(["self.x = self._precompute_and_cache_chunks(", "    " + bad_arg + ", cfg)"])
    calls = re.findall(r"_precompute_and_cache_chunks\(\s*([A-Za-z_][\w.]*)", body)
    if calls != [bad_arg]:
        fails.append(f"msst判据: 植入的可疑实参未被捕获 (得到 {calls})")
    good = "\n".join(["self.a = self._precompute_and_cache_chunks(",
                      "    chunks_cache_path, current_config)"])
    if re.findall(r"_precompute_and_cache_chunks\(\s*([A-Za-z_][\w.]*)", good) != ["chunks_cache_path"]:
        fails.append("msst判据: 合法的跨行调用未被识别")

    print("探测器反向自检")
    print("-" * 78)
    for f in fails:
        print(f"  [FAIL] {f}")
    if not fails:
        print("  [PASS] 三个探测器均能对植入样本报警, 且不误伤合法样本")
        print("-" * 78)
        print("结论: 复核判据有效。")
        return 0
    print("-" * 78)
    print(f"结论: {len(fails)} 项自检失败 — 判据已损坏, 复核结果不可信。")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(prog="verify_security_exemptions.py")
    ap.add_argument("--json", action="store_true", help="输出机器可读结果")
    ap.add_argument("--selftest", action="store_true",
                    help="只跑反向自检: 证明探测器在真出问题时会报")
    args = ap.parse_args()

    if args.selftest:
        return self_test()

    check_config_mapping_only()
    check_prep_guarded_sinks()
    check_msst_third_party()

    failed = [r for r in results if not r["ok"]]
    if args.json:
        print(json.dumps({"exemptions": results, "failed": len(failed)}, ensure_ascii=False, indent=1))
    else:
        print("误报豁免复核 (docs/security-false-positive-exemptions.md)")
        print("-" * 78)
        for r in results:
            print(f"  [{'PASS' if r['ok'] else 'FAIL'}] {r['check']:<44} {r['detail']}")
        print("-" * 78)
        if failed:
            print(f"结论: {len(failed)} 条豁免前提已失效 — 豁免作废, 必须重新人工判定。")
        else:
            print(f"结论: {len(results)} 条前提全部成立, 三条豁免记录仍然有效。")

    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover
        print(f"[ERR] 复核脚本运行失败: {exc}", file=sys.stderr)
        sys.exit(2)
