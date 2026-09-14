"""build_text_overlay run_dir/tag 白名单 + --edl 注册测试（§4/Step1.5）。

与 test_master_polish_whitelist.py 对齐：验证文字链消费端也放宽接受 R1 修复run，
且防遍历语义不变。text_events 真实数据消费见 patches/Step1 草案 §八（一次性实证）。
"""
import re
import subprocess
import sys
from pathlib import Path

from scripts.build_text_overlay import RUN_DIR_PATTERN, TAG_PATTERN

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
                "unified_run53;rm", "unified_run53 x"]:
        assert not re.fullmatch(RUN_DIR_PATTERN, bad), f"应拒绝 {bad}"


def test_tag_pattern():
    assert re.fullmatch(TAG_PATTERN, "run53")
    assert re.fullmatch(TAG_PATTERN, "run7")
    assert not re.fullmatch(TAG_PATTERN, "run")
    assert not re.fullmatch(TAG_PATTERN, "../x")


def test_cli_rejects_invalid_run_dir_before_side_effects():
    """非法 run_dir → exit 2，在任何 tmp/output 副作用前拦截。断言 ASCII 标记(locale 无关)。"""
    r = subprocess.run(
        [sys.executable, str(PROJECT / "scripts" / "build_text_overlay.py"),
         "../etc", "run7", "--dry-run"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60, cwd=str(PROJECT))
    assert r.returncode == 2
    assert "unified_run<N>" in r.stdout and "../etc" in r.stdout
