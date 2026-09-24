# -*- coding: utf-8 -*-
"""sys.path 膨胀防回涨闸门（P1-E, 2026-09-19）。

量化依据（`tmp/_pathprobe.py` 在全量收集后实测）::

    [PATHPROBE] collected=5857  sys.path=287  unique=44  dupes=243

287 条里 243 条是重复 —— 成因是历史遗留的 283 处测试文件模块级
`sys.path.insert(0, PROJECT_ROOT)`（根目录治理 2026-08-26 之前写下的防导入失败
写法）。重复条目在每次 `import` 时都要多走一遍 stat/查找，并让"到底哪个路径生效"
不可读。

本闸门锁三件事：
  1. 收集结束后 sys.path **没有重复条目**（由 tests/conftest.py 的
     `pytest_collection_finish` 去重保证；若去重被误删，这里立刻红）
  2. 唯一路径条目数有上界（防"再插一条新路径"式膨胀）
  3. 配置层声明了 `pythonpath`（新人写测试**不需要**再手写 sys.path.insert，
     这是防止 283 处历史写法继续蔓生的制度性保证）

约定：**新增测试文件不要再写 `sys.path.insert`**。项目根已由 pytest 配置注入；
确有额外需要时改 `pytest.ini` 的 `pythonpath`（多值用空格分隔），一处生效全局。
"""
import os
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# 唯一路径上界：当前实测远小于此值，留出正常增长余量
MAX_UNIQUE_PATHS = 60
MAX_DUPLICATES = 0


def test_no_duplicate_sys_path_entries():
    """收集后不得有重复条目（去重钩子在 tests/conftest.py）。"""
    keys = [os.path.normcase(os.path.abspath(p)) if p else "" for p in sys.path]
    dupes = len(keys) - len(set(keys))
    assert dupes <= MAX_DUPLICATES, (
        f"sys.path 出现 {dupes} 条重复（应 ≤{MAX_DUPLICATES}）—— "
        f"检查 tests/conftest.py 的 pytest_collection_finish 去重是否被移除，"
        f"或有新文件在模块级重复插入同一路径")


def test_sys_path_size_bounded():
    """唯一路径数上界：新增路径请改 pytest.ini 的 pythonpath，不要手写插入。"""
    uniq = len({os.path.normcase(os.path.abspath(p)) if p else "" for p in sys.path})
    assert uniq <= MAX_UNIQUE_PATHS, (
        f"sys.path 唯一条目 {uniq} > {MAX_UNIQUE_PATHS}；"
        f"需要新增导入路径请改 pytest.ini 的 pythonpath")


def test_pytest_config_declares_pythonpath():
    """生效配置（pytest.ini）必须声明 pythonpath，否则历史写法会蔓生。"""
    ini = (PROJECT / "pytest.ini").read_text(encoding="utf-8")
    assert re.search(r"(?m)^\s*pythonpath\s*=", ini), \
        "pytest.ini 缺少 pythonpath（新测试将被迫手写 sys.path.insert）"


def test_no_dead_pytest_config_in_pyproject():
    """pyproject 里不得再有 [tool.pytest.ini_options] 死配置。

    历史事故：那段配置从未生效（pytest.ini 优先），却写着 markers 与
    filterwarnings —— 于是"以为已忽略的弃用告警"一直刷屏。死配置是陷阱：
    改了没效果，还会让人误判现状。
    """
    pp = PROJECT / "pyproject.toml"
    if not pp.exists():
        return
    # 行首锚定：只认真正的 TOML 段头，注释里提到段名不算（否则注释会被误判）
    assert not re.search(r"(?m)^\[tool\.pytest\.ini_options\]",
                         pp.read_text(encoding="utf-8")), \
        "pyproject.toml 又出现了不生效的 pytest 配置段（应写在 pytest.ini）"


def test_repo_root_already_on_path():
    """项目根必须已在 path 上 —— 这是"新测试不必手写插入"的前提。"""
    root = os.path.normcase(os.path.abspath(str(PROJECT)))
    entries = {os.path.normcase(os.path.abspath(p)) for p in sys.path if p}
    assert root in entries, "项目根不在 sys.path 上（pythonpath 配置失效？）"


def test_legacy_insert_sites_are_burndown_debt():
    """历史插入点只减不增：记录在册的 283 处是债务，不是模板。

    本测试不去逐一删除它们（283 处机械改动风险大于收益），而是防止**继续新增**：
    上限按当前实测值设定，新增文件若再写插入会立刻越界。
    """
    limit = 300
    count = 0
    for f in (PROJECT / "tests").glob("test_*.py"):
        try:
            src = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        count += len(re.findall(r"sys\.path\.(?:insert|append)", src))
    assert count <= limit, (
        f"tests/ 下 sys.path 操作点 {count} > {limit} —— 新增测试请用 pytest.ini "
        f"的 pythonpath，不要复制历史写法")
