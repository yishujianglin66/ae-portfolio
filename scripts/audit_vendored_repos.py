"""审计工作树内的嵌套 git 仓库：找出"公网拉不到"的提交与未备份的本地改动。

背景：external/ 下的 vendored 克隆长期以 gitlink 形式挂在索引里，但 gitlink 指向的
sha 未必能从该仓库自己的 remote 拉到。2026-08-29 实测 `external/rife` 的 HEAD 就是
本项目作者的私有提交（克隆还是 shallow），一旦换机器或误删目录即永久丢失。

三类判定：
1. **FAIL（孤本）**：嵌套仓库 HEAD 不被任何 refs/remotes/* 包含。此时必须在 docs/vendor/
   下有一个文件名含该仓库名的 .patch 真正兜得住：受 git 跟踪、工作树里存在、非空、
   且首行 `From <sha>` 与该仓库 HEAD 一致（无 From 行则须含 `diff --git`）。
   早期版本只按"索引里有这个名字"判定，补丁文件被删或被清空时仍判通过——反向验证
   没能失败，正是这个缺陷，故现改为实质核验并逐项报出不成立原因。
2. **FAIL（断链 gitlink）**：该路径在索引里是 mode 160000，但 pin 的 sha 无法从子仓库
   远端拉到——`git submodule update` 之类操作必然失败。（gitlink 的语义是 pin，
   不是本地 HEAD，所以两者都要判。）
3. **WARN（未备份的本地改动）**：子仓库对已跟踪文件有未提交 diff。不设为致命——
   否则闸门会因长期存在的实验性改动而被人在 CI/提交前直接跳过，反而失效。

只读，不改动任何仓库。扫描深度上限 3 层（见 find_nested_repos），超出范围的嵌套
仓库不会被本闸门覆盖。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PATCH_DIR = REPO / "docs" / "vendor"
MAX_DEPTH = 3

# 这些目录要么是产物、要么是第三方依赖树，不在此寻找需要保护的嵌套仓库
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "models", "output", "output_production", "tmp", "reports",
    "data", ".cache", "dist", "build", ".pytest_cache",
}


def run(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.stdout.strip() if proc.returncode == 0 else ""


def find_nested_repos() -> list[Path]:
    """返回深度 <= MAX_DEPTH 的嵌套 git 仓库根目录（不含本仓库自身）。"""
    found: list[Path] = []
    frontier = [REPO]
    for _ in range(MAX_DEPTH):
        next_frontier: list[Path] = []
        for base in frontier:
            try:
                children = [c for c in base.iterdir()
                            if c.is_dir() and c.name not in SKIP_DIRS]
            except (OSError, PermissionError):
                continue
            for child in children:
                if (child / ".git").exists():
                    found.append(child)
                else:
                    next_frontier.append(child)
        frontier = next_frontier
    return sorted(set(found))


def index_gitlinks() -> dict[str, str]:
    """返回被索引为 gitlink(160000) 的路径 -> pin sha。"""
    out = run(["git", "ls-tree", "-r", "HEAD"], REPO)
    links: dict[str, str] = {}
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) >= 2 and parts[0] == "160000" and parts[1] == "commit":
            links[path] = parts[2]
    return links


def tracked_patches() -> list[str]:
    out = run(["git", "ls-files", "--", str(PATCH_DIR.relative_to(REPO))], REPO)
    return [line for line in out.splitlines() if line.strip()]


def patch_verdict(rel_path: str, head_sha: str) -> str:
    """返回 '' 表示该补丁确实兜住了 head_sha；否则返回不成立的原因。"""
    path = REPO / rel_path
    if run(["git", "ls-files", "--error-unmatch", rel_path], REPO) == "":
        return "未被 git 跟踪（仅存在于本机）"
    if not path.is_file():
        return "索引里有但工作树缺文件"
    data = path.read_bytes()
    if not data.strip():
        return "文件为空"
    text = data.decode("utf-8", "replace")
    first = text.splitlines()[0] if text.splitlines() else ""
    if first.startswith("From "):
        sha = first[len("From "):].split()[0].strip()
        if not head_sha.startswith(sha[:12]) and not sha.startswith(head_sha[:12]):
            return f"补丁记录的 sha {sha[:7]} 与该仓库 HEAD {head_sha[:7]} 不符"
        return ""
    if "diff --git" not in text:
        return "既无 format-patch 头也无 diff --git，不像是补丁"
    return ""


def is_fetchable(root: Path, sha: str) -> bool:
    """sha 是否被子仓库某个远端分支包含（--contains 对不完整 sha 需可解析）。"""
    return bool(run(["git", "-C", str(root), "branch", "-r", "--contains", sha], root).strip())


def main() -> int:
    repos = find_nested_repos()
    patches = tracked_patches()
    gitlinks = index_gitlinks()
    problems: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    for root in repos:
        rel = root.relative_to(REPO).as_posix()
        head = run(["git", "-C", str(root), "rev-parse", "HEAD"], root)
        if not head:
            problems.append(f"{rel}: 无法解析 HEAD（子仓库损坏？）")
            continue
        short = head[:7]

        # 判定 2：断链 gitlink
        pin = gitlinks.get(rel)
        if pin and not is_fetchable(root, pin):
            problems.append(
                f"{rel}: 索引 gitlink pin {pin[:7]} 无法从子仓库任何远端分支拉取（断链）"
            )

        # 判定 1：HEAD 孤本
        if is_fetchable(root, head):
            ref = "远端分支已含" + (f"，gitlink pin {pin[:7]}" if pin else "")
            notes.append(f"{rel}@{short}: pin 可拉取{ref}")
        else:
            needle = root.name.lower()
            candidates = [p for p in patches if needle in p.lower() and p.endswith(".patch")]
            good = [p for p in candidates if patch_verdict(p, head) == ""]
            if good:
                notes.append(f"{rel}@{short}: 私有提交，已由 {good[0]} 兜底")
            elif candidates:
                reasons = "；".join(
                    f"{Path(p).name}: {patch_verdict(p, head)}" for p in candidates
                )
                problems.append(
                    f"{rel}@{short}: HEAD 为孤本，候选补丁不可用 —— {reasons}"
                )
            else:
                problems.append(
                    f"{rel}@{short}: HEAD 不被任何远端分支包含（孤本），"
                    f"且 docs/vendor/ 下无匹配的受跟踪 .patch"
                )

        # 判定 3：未备份的本地改动（只看已跟踪文件的 diff，不管未跟踪新文件）
        dirty = run(["git", "-C", str(root), "diff", "--name-only"], root)
        changed = [l for l in dirty.splitlines() if l.strip()]
        if changed:
            warnings.append(
                f"{rel}: 子仓库有 {len(changed)} 个已跟踪文件被本地修改且未提交"
                f"（{', '.join(changed[:3])}{' 等' if len(changed) > 3 else ''}）"
            )

    print(f"扫描 {len(repos)} 个嵌套仓库，深度上限 {MAX_DEPTH} 层；索引 gitlink {len(gitlinks)} 个")
    for n in notes:
        print(f"  OK   {n}")
    for w in warnings:
        print(f"  警告 {w}")
    for p in problems:
        print(f"  风险 {p}")
    print(f"\n结论：致命 {len(problems)} 项 / 警告 {len(warnings)} 项 / 正常 {len(notes)} 项")
    if warnings:
        print("备份本地改动：git -C <子仓> diff > docs/vendor/<name>-local-edits.patch")
    if problems:
        print("处置：git -C <子仓> format-patch -1 HEAD --stdout > docs/vendor/<name>-<主题>.patch")
        print("      然后在上游基线 worktree 里 git am 验证还原文件 sha256 与在用版本一致")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

