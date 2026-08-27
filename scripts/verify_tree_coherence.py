"""校验提交后的 HEAD 树是否自洽：重建跟踪文件清单，检查导入重定向目标与测试导入是否都在库内。

只读校验：把 HEAD 的跟踪清单与仓库中实际被 import 的模块名做集合比对。
"""
import ast
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

tracked = set(
    subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD"],
                   capture_output=True).stdout.decode("utf-8", "replace").splitlines()
)
print(f"HEAD 跟踪文件数: {len(tracked)}")


def module_to_path(mod):
    base = mod.replace(".", "/")
    return (base + ".py", base + "/__init__.py")


def exists_in_head(mod):
    return any(p in tracked for p in module_to_path(mod))


# ---------- 1. _import_redirect 规则目标 ----------
redirect_src = open("_import_redirect.py", encoding="utf-8").read()
rules = re.findall(r'["\']([a-zA-Z_][\w.]*)["\']\s*:\s*["\']([a-zA-Z_][\w.]*)["\']',
                   redirect_src)
missing_target = [(src, dst) for src, dst in rules if not exists_in_head(dst)]
print(f"\n[1] 重定向规则 {len(rules)} 条，目标缺失 {len(missing_target)} 条")
for src, dst in missing_target[:15]:
    print(f"    {src} -> {dst}   <-- HEAD 中不存在")

# ---------- 2. 生产代码内部 import 的项目顶层模块 ----------
PROJECT_ROOTS = {
    "core", "pipeline", "config", "utils", "integrations", "bridges", "effects",
    "knowledge", "ae", "ai", "api", "audio", "analysis", "media", "models",
    "rendering", "scene", "silhouette", "style", "tasks", "tools", "transition",
    "video", "vrs", "auth", "feedback", "monitoring", "validation", "aep_analyzer",
    "dev_scripts", "scripts", "style_copy",
}
absent = {}
for path in sorted(tracked):
    if not path.endswith(".py") or path.startswith(("tests/", "scripts/", "dev_scripts/")):
        continue
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (SyntaxError, UnicodeDecodeError, OSError):
        continue
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods = [node.module]
        for mod in mods:
            root = mod.split(".")[0]
            if root not in PROJECT_ROOTS:
                continue
            if exists_in_head(mod):
                continue
            # 顶层包本身存在即可（子模块可能在函数内动态构造）
            if exists_in_head(root):
                continue
            absent.setdefault(mod, []).append(path)

print(f"\n[2] 生产代码引用但 HEAD 中缺失的项目模块: {len(absent)} 个")
for mod, where in sorted(absent.items())[:25]:
    print(f"    {mod}   <- {', '.join(where[:3])}")

# ---------- 3. 测试文件的顶层 import ----------
test_mods = {}
for path in sorted(tracked):
    if not path.startswith("tests/") or not path.endswith(".py"):
        continue
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (SyntaxError, UnicodeDecodeError, OSError):
        continue
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods = [node.module]
        for mod in mods:
            root = mod.split(".")[0]
            if root not in PROJECT_ROOTS:
                continue
            if exists_in_head(mod) or exists_in_head(root):
                continue
            test_mods.setdefault(mod, []).append(path)

print(f"\n[3] 测试引用但 HEAD 中缺失的项目模块: {len(test_mods)} 个")
for mod, where in sorted(test_mods.items())[:25]:
    print(f"    {mod}   <- {', '.join(where[:3])}")
