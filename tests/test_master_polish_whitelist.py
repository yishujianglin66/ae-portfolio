"""build_master_polish run_dir/tag 白名单测试（Step1.5：放宽接受 R1 修复run）。

验证:
  (1) RUN_DIR_PATTERN 接受 unified_runN + unified_r1_fixed_vN（R1 修复run）;
  (2) 拒绝路径遍历 / 垃圾 / 带 output 前缀 / 非数字 / _BAD 后缀;
  (3) CLI 对非法 run_dir exit 2（白名单在任何 tmp/output 副作用前拦截）。
"""
import re
import subprocess
import sys
from pathlib import Path

from scripts.build_master_polish import RUN_DIR_PATTERN, TAG_PATTERN

PROJECT = Path(__file__).resolve().parent.parent


def test_run_dir_accepts_valid_shapes():
    """既有 run53 系列 + 新放宽的 R1 修复run 都应通过。"""
    for name in ["unified_run53", "unified_run2", "unified_run100",
                 "unified_r1_fixed_v7", "unified_r1_fixed_v1", "unified_r1_fixed_v8"]:
        assert re.fullmatch(RUN_DIR_PATTERN, name), f"应接受 {name}"


def test_run_dir_rejects_traversal_and_junk():
    """路径遍历 / 注入 / 带前缀 / _BAD / 非数字 一律拒绝（防遍历语义不变）。"""
    for bad in ["../etc", "unified_run53/../x", "unified_r1_fixed_v7_BAD",
                "unified_r1_fixed_vX", "unified_foo", "unified_run",
                "output/unified_run53", "/abs/unified_run53", "r1_fixed_v7",
                "unified_run53;rm", "unified_run53 x", "unified_r1_fixed_v"]:
        assert not re.fullmatch(RUN_DIR_PATTERN, bad), f"应拒绝 {bad}"


def test_tag_pattern():
    assert re.fullmatch(TAG_PATTERN, "run53")
    assert re.fullmatch(TAG_PATTERN, "run7")
    assert not re.fullmatch(TAG_PATTERN, "run")
    assert not re.fullmatch(TAG_PATTERN, "r1_fixed_v7")
    assert not re.fullmatch(TAG_PATTERN, "../x")


def test_cli_rejects_invalid_run_dir_before_side_effects():
    """非法 run_dir → exit 2，且在任何 tmp/output 写入前拦截（安全前置）。"""
    r = subprocess.run(
        [sys.executable, str(PROJECT / "scripts" / "build_master_polish.py"),
         "../etc", "run7", "--dry-run"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60, cwd=str(PROJECT))
    assert r.returncode == 2
    # 断言 ASCII 标记(子进程中文输出在 GBK locale 下被 utf-8 捕获会 mojibake, 故只验 ASCII):
    # "unified_run<N>" 是 run_dir 白名单错误独有提示, "../etc" 是被拒的值
    assert "unified_run<N>" in r.stdout and "../etc" in r.stdout
