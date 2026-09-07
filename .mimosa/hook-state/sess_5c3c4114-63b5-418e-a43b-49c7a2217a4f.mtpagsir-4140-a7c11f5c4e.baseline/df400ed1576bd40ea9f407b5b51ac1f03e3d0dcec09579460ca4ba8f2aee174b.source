#!/usr/bin/env python3
"""JSX (ExtendScript) 语法门禁.

用 node --check 校验仓库内 *.jsx 语法, 防止再出现 D-24 那种
"候选路径数组未加引号导致整个监听器解析失败" 的事故
(2026-08-14 commit 2aa33fe 引入, 2026-08-16 体检发现, 详见
docs/research/2026-08-16-full-project-audit.md P0-1).

ExtendScript 特有的预处理指令 (#target/#include/#strict 等) 与
@JSXBIN 二进制文件 node 无法解析, 校验前剥离/跳过。

用法:
    python scripts/check_jsx_syntax.py            # 扫描全仓库
    python scripts/check_jsx_syntax.py path ...    # 只查指定文件/目录

退出码: 0 全部通过 / 1 存在语法错误 / 2 node 不可用
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 第三方/生成目录不参与门禁
EXCLUDE_PARTS = {".git", "node_modules", "external", "archive", "build",
                 "__pycache__", "_archive", ".cache", "cache"}
DIRECTIVE_RE = re.compile(r"^\s*#(?:target|targetengine|include|includepath"
                          r"|strict|error|pragma|onerror|filepath)\b")
# ExtendScript 预处理指令行, 剥离后不影响其余语法
TEMPLATE_RE = re.compile(r"\{\{[A-Za-z_][A-Za-z0-9_]*\}\}")
# {{PLACEHOLDER}} 渲染模板 (如 ae/scripts/amv/*.jsx), 渲染前本就不是合法 JS


def _is_runtime_dir(part: str) -> bool:
    """根目录下 .*-bridge* 运行时目录里会有监听器落盘的临时 JSX。"""
    return part.startswith(".") and "bridge" in part.lower()


def _preprocess(text: str) -> str | None:
    """剥离 ExtendScript 指令; 返回 None 表示跳过该文件。"""
    if "@JSXBIN@" in text[:4096]:
        return None
    if TEMPLATE_RE.search(text):
        return None
    lines = [ln for ln in text.splitlines(keepends=True)
             if not DIRECTIVE_RE.match(ln)]
    return "".join(lines)


def check_file(jsx: Path, node_bin: str) -> tuple[bool, str]:
    """返回 (通过?, 错误信息)。"""
    try:
        raw = jsx.read_bytes()
        # 少数历史文件是 UTF-16 (如曾被记事本保存), 按 BOM 识别
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            text = raw.decode("utf-16")
        else:
            text = raw.decode("utf-8", errors="replace")
    except OSError as exc:
        return False, f"读取失败: {exc}"
    code = _preprocess(text)
    if code is None:
        return True, "SKIP"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as tmp:
        tmp.write(code)
        tmp_path = tmp.name
    try:
        proc = subprocess.run(
            [node_bin, "--check", tmp_path],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"node 调用失败: {exc}"
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
    if proc.returncode != 0:
        # tmp 文件名替换回原路径, 方便定位
        msg = (proc.stderr or proc.stdout).replace(tmp_path, str(jsx))
        return False, msg.strip()
    return True, ""


def iter_jsx(targets: list[Path]):
    for t in targets:
        if t.is_file():
            if t.suffix == ".jsx":
                yield t
        else:
            for p in t.rglob("*.jsx"):
                if set(p.parts) & EXCLUDE_PARTS:
                    continue
                if any(_is_runtime_dir(part) for part in p.parts):
                    continue
                yield p


def main() -> int:
    node_bin = shutil.which("node")
    if not node_bin:
        print("ERROR: 未找到 node, 无法做 JSX 语法检查", file=sys.stderr)
        return 2
    targets = [Path(a).resolve() for a in sys.argv[1:]] or [PROJECT_ROOT]
    files = sorted(set(iter_jsx(targets)))
    failed = 0
    for f in files:
        ok, err = check_file(f, node_bin)
        if err == "SKIP":
            print(f"SKIP {f.relative_to(PROJECT_ROOT)} (模板/二进制)")
            continue
        status = "OK  " if ok else "FAIL"
        print(f"{status} {f.relative_to(PROJECT_ROOT)}")
        if not ok:
            failed += 1
            print(f"      {err}\n")
    print(f"\n共 {len(files)} 个 JSX, 失败 {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
