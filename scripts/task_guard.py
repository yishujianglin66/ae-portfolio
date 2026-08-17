# -*- coding: utf-8 -*-
"""任务守卫 — 多 agent 共享工作树的暂存/提交安全检查 (2026-08-14)

背景: 两个 agent 在同一工作树 + 同一分支并行, 已踩过 4 类冲突
(见 docs/process/2026-08-14-multi-agent-coordination.md)。

重要: 两 agent 共用同一 git identity (user.name 相同), "按提交者判归属"不可靠。
本工具改为【纯清单驱动】: 你声明本任务的文件清单, 工具保证暂存区只含清单内文件。

用法:
  py -3.12 scripts/task_guard.py status          # 列出全部改动 (信息性)
  py -3.12 scripts/task_guard.py stage <f...>    # 释放暂存区清单外文件, 仅暂存清单内文件
  py -3.12 scripts/task_guard.py check <f...>    # 提交前核对: 暂存区 == 清单 (不一致非零退出)

约定:
  - 禁止 git add -A / -u / .  (全量暂存会把他人改动卷进来)
  - 提交流程 = stage <清单> → check <清单> → commit
"""
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def _git(args):
    r = subprocess.run(["git", "-C", str(ROOT)] + args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout, r.returncode


def _parse_status():
    """返回 [(staged_col, path)] — staged_col 为 XY 首列字符, 空=未暂存。"""
    out, _ = _git(["status", "--porcelain"])
    items = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        # porcelain 格式固定: XY path (X 未暂存列, Y 暂存列, 索引 3 起为路径)
        flag = line[:2]
        path = line[3:].strip().strip('"')
        if " -> " in path:  # 重命名
            path = path.split(" -> ")[-1]
        items.append((flag, path))
    return items


def _last_commit_hint(path: str) -> str:
    out, _ = _git(["log", "-1", "--format=%s", "--", path])
    return (out or "(未跟踪/无历史)")[:60]


def cmd_status():
    print("工作树全部改动 (暂存列 X/Y: 首列非空=已暂存):\n")
    print(f"{'暂存':<4} 文件")
    print("-" * 76)
    for flag, path in _parse_status():
        staged = flag[0] if flag[0].strip() else "-"
        print(f"{staged:<4} {path}")
        hint = _last_commit_hint(path)
        print(f"     └─ 最近提交: {hint}")
    print("-" * 76)
    print("提示: 两个 agent 共用 git identity, 归属无法自动判定; "
          "请按你的任务清单手动核对。")


def cmd_stage(files):
    # 1. 释放暂存区中清单外文件 (他人文件绝不随提交带走)
    staged_now = [p for f, p in _parse_status() if f[0].strip() and f[0] != "?"]
    extra = [p for p in staged_now if p not in files]
    if extra:
        print("⚠️ 暂存区含清单外文件, 自动释放:")
        for p in extra:
            _git(["reset", "-q", "--", p])
            print(f"   git reset {p}")
    # 2. 仅暂存清单内文件
    missing = []
    for f in files:
        _, rc = _git(["add", "--", f])
        if rc != 0:
            missing.append(f)
    if missing:
        print(f"⚠️ 暂存失败(路径不存在?): {missing}")
        sys.exit(1)
    # 3. 复核
    staged_after = [p for f, p in _parse_status() if f[0].strip() and f[0] != "?"]
    not_in = [p for p in staged_after if p not in files]
    if not_in:
        print(f"⚠️ 暂存区仍含清单外文件: {not_in}")
        sys.exit(1)
    print(f"✅ 已暂存 {len(files)} 个文件, 暂存区与清单一致, 可提交。")


def cmd_check(files):
    staged = [p for f, p in _parse_status() if f[0].strip() and f[0] != "?"]
    if not staged:
        print("暂存区为空, 无提交内容。")
        sys.exit(1)
    not_in = [p for p in staged if p not in files]
    missing = [p for p in files if p not in staged]
    if not_in:
        print(f"⚠️ 暂存区含清单外文件 ({len(not_in)} 个):")
        for p in not_in:
            print(f"   - {p}")
        sys.exit(1)
    if missing:
        print(f"⚠️ 清单内有 {len(missing)} 个文件未暂存: {missing}")
        sys.exit(1)
    print(f"✅ 暂存区 {len(staged)} 个文件与清单完全一致, 可提交。")


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "status":
        cmd_status()
    elif sys.argv[1] == "stage":
        if len(sys.argv) < 3:
            print("用法: py -3.12 scripts/task_guard.py stage <file...>")
            sys.exit(1)
        cmd_stage(sys.argv[2:])
    elif sys.argv[1] == "check":
        if len(sys.argv) < 3:
            print("用法: py -3.12 scripts/task_guard.py check <file...>")
            sys.exit(1)
        cmd_check(sys.argv[2:])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
