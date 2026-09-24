# -*- coding: utf-8 -*-
"""llm_gateway：既有测试未断言的语义边界（2026-09-22）。

⚠️ 本文件存在一个**必须先说清楚的事实**：`core/llm_gateway.py` 的这层逻辑
**行覆盖早已存在** —— `tests/test_llm_gateway.py`（含 `TestSanitizeLogText`、
TokenCompressor 用例）、`tests/test_llm_gateway_regression_gaps.py`（PEM/JWT）、
`tests/test_llm_gateway_failover.py` 等 4 个文件已把 `_sanitize_log_text` /
`TokenCompressor` 跑过。实测：新增本文件后该项目**未覆盖行数一字未减**
（743 → 743）。

所以本文件的价值**不是覆盖率**，而是补上"被执行但未被断言"的语义边界：

  1. `_parse_env_flag` —— 无任何既有测试直接断言其真值表与**空串=未设置**语义，
     而本项目大量开关依赖它（空格串 vs 空串 vs 未设置，三态不同）；
  2. 脱敏的**幂等性** —— 二次脱敏不得改写已生成的 `***REDACTED***` 标记
     （值字符类排除 `*` 正是为此），否则日志被反复处理后会出现嵌套改写；
  3. 脱敏的**多行结构保持** —— 逐行处理，换行与普通行不得被吃掉；
  4. 一行多密钥 —— 单次调用要处理多个敏感字段，不能只替第一处；
  5. `LLMConfig()` 默认值**不得自带密钥**（配置漂移哨兵）。

刻意**不**重复既有测试已覆盖的：sk-/api_key/password/secret/token/Bearer 的
基础脱敏、PEM/JWT 掩码、TokenCompressor 的替换与截断长度。
"""
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from core.llm_gateway import (  # noqa: E402
    LLMConfig,
    _parse_env_flag,
    _sanitize_log_text,
)


# ---------------------------------------------------------------------------
# _parse_env_flag —— 三态语义（未设置 / 空串 / 值）
# ---------------------------------------------------------------------------

class TestParseEnvFlag:
    @pytest.mark.parametrize("value,expected", [
        ("1", True), ("true", True), ("TRUE", True), ("Yes", True), ("on", True),
        ("0", False), ("false", False), ("no", False), ("off", False),
        ("anything-else", False), ("  true  ", True),      # 去空格
    ])
    def test_truthy_truth_table(self, monkeypatch, value, expected):
        monkeypatch.setenv("AEKV_TEST_FLAG", value)
        # default 取反，确保测的是"值"而非默认分支
        assert _parse_env_flag("AEKV_TEST_FLAG", not expected) is expected

    def test_unset_returns_default(self, monkeypatch):
        monkeypatch.delenv("AEKV_TEST_FLAG", raising=False)
        assert _parse_env_flag("AEKV_TEST_FLAG", True) is True
        assert _parse_env_flag("AEKV_TEST_FLAG", False) is False

    def test_whitespace_only_is_treated_as_unset(self, monkeypatch):
        """空白串按"未设置"处理（返回默认值），**不是** falsy。

        三态差异会直接影响开关默认行为：``FLAG=" "`` 与 ``FLAG=""`` 都走默认，
        而 ``FLAG="0"`` 是显式关闭。
        """
        monkeypatch.setenv("AEKV_TEST_FLAG", "   ")
        assert _parse_env_flag("AEKV_TEST_FLAG", True) is True


# ---------------------------------------------------------------------------
# 脱敏的边界语义（既有测试未断言的部分）
# ---------------------------------------------------------------------------

class TestRedactionEdgeSemantics:
    def test_redaction_is_idempotent(self):
        """二次脱敏不得改写已生成的标记。

        值字符类排除 `*` 就是为此：否则 `token=***REDACTED***` 会被再吃一遍。
        """
        once = _sanitize_log_text("token=just-a-test-value")
        assert "***REDACTED***" in once
        assert _sanitize_log_text(once) == once

    def test_multiline_structure_preserved(self):
        """多行日志逐行脱敏：换行数不变，普通行原样保留。"""
        txt = "line1 ok\ntoken=just-a-test-value\nline3 ok"
        out = _sanitize_log_text(txt)
        assert out.count("\n") == 2
        assert "line1 ok" in out and "line3 ok" in out
        assert "just-a-test-value" not in out

    def test_multiple_secrets_in_one_line_all_redacted(self):
        """一行多个敏感字段要全部脱敏，不能只替第一处。"""
        out = _sanitize_log_text("api_key=test-value-aaaa password=test-value-bbbb")
        assert "test-value-aaaa" not in out and "test-value-bbbb" not in out
        assert out.count("***REDACTED***") >= 2

    def test_empty_and_none_passthrough(self):
        assert _sanitize_log_text("") == ""
        assert _sanitize_log_text(None) is None

    def test_plain_text_untouched(self):
        """误伤检查：不含敏感内容的日志（含中文/数字/单位）必须原样返回。"""
        txt = "渲染完成: 648 帧 / 27.00s，码率 7.7Mbps"
        assert _sanitize_log_text(txt) == txt


# ---------------------------------------------------------------------------
# 配置漂移哨兵
# ---------------------------------------------------------------------------

class TestConfigDefaults:
    def test_llm_config_defaults_carry_no_secret_value(self):
        """默认配置不得自带密钥 —— 密钥只能来自环境或显式配置。

        这条不是覆盖率而是**红线**：默认值里出现密钥字面量 = 泄漏进仓库。
        """
        cfg = LLMConfig()
        for name in ("api_key", "api_keys", "api_key_env", "token"):
            if hasattr(cfg, name):
                v = getattr(cfg, name)
                assert not v or v in ({}, []), f"{name} 默认值非空: {v!r}"
