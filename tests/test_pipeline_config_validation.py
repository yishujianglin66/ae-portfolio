"""
回归测试: PipelineConfig 配置边界校验 (Bug4)

修复前的 Bug:
  1. max_quality_iterations = 0 / 负数 / False → 主循环 `for _ in range(0)` 空循环,
     用户在无任何报错的情况下得不到输出 (静默功能退化)。
  2. max_quality_iterations = 2.7 等浮点数 / 数字字符串 → range(float) 抛 TypeError。
  3. max_quality_iterations = 1000000 → 超大值虽然被部分使用点 min(x, 5) 限制,
     但主循环缺乏一致的上限。
  4. min_quality_score < 0 或 > 100 → 导致质量门控逻辑比较失效。

修复方式: PipelineConfig 增加 __post_init__ 方法, 将:
    max_quality_iterations 钳制到 int ∈ [1, 5]
    min_quality_score     钳制到 float ∈ [0.0, 100.0]
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestPipelineConfigValidation:
    """PipelineConfig.__post_init__ 边界校验回归测试。"""

    def _make_config(self, **overrides):
        """创建一个纯配置 (不触发 pipeline 初始化)。"""
        from pipeline.unified_pipeline import PipelineConfig
        return PipelineConfig(**overrides)

    # ----------------------------------------------------------
    # max_quality_iterations
    # ----------------------------------------------------------

    def test_zero_iterations_clamped_to_1_regression(self):
        """max_quality_iterations=0 时必须被钳制到 1 (修复前 range(0) 导致空循环无输出)。"""
        cfg = self._make_config(max_quality_iterations=0)
        assert cfg.max_quality_iterations == 1, (
            f"0 应被钳制为 1, 实际={cfg.max_quality_iterations}"
        )

    def test_negative_iterations_clamped_to_1_regression(self):
        """负数 (如 -5) 必须钳制到 1 (修复前 range(-5) 空循环)。"""
        cfg = self._make_config(max_quality_iterations=-5)
        assert cfg.max_quality_iterations == 1, (
            f"-5 应被钳制为 1, 实际={cfg.max_quality_iterations}"
        )

    def test_false_iterations_clamped_to_3_regression(self):
        """bool=False 是 int 的子类 (等于 0), 必须被识别为非法值 → 回退默认 3。"""
        cfg = self._make_config(max_quality_iterations=False)
        # False 走 bool 分支 → 默认 3
        assert cfg.max_quality_iterations == 3, (
            f"bool False 应回退默认值 3, 实际={cfg.max_quality_iterations}"
        )

    def test_float_iterations_converted_to_int_regression(self):
        """max_quality_iterations=2.7 浮点数 → 转换为 int=2 (修复前 range(2.7) 抛 TypeError)。"""
        cfg = self._make_config(max_quality_iterations=2.7)
        assert isinstance(cfg.max_quality_iterations, int), (
            f"转换后类型应为 int, 实际={type(cfg.max_quality_iterations)}"
        )
        assert cfg.max_quality_iterations == 2, (
            f"2.7 应被截断为 int=2, 实际={cfg.max_quality_iterations}"
        )

    def test_numeric_string_iterations_coerced(self):
        """数字字符串 "4" 应能被 int() 转换为 4。"""
        cfg = self._make_config(max_quality_iterations="4")
        assert cfg.max_quality_iterations == 4

    def test_invalid_string_iterations_fallback_to_default(self):
        """非数字字符串 "abc" 应回退到默认值 3 (不抛异常)。"""
        cfg = self._make_config(max_quality_iterations="abc")
        assert cfg.max_quality_iterations == 3

    def test_none_iterations_fallback_to_default(self):
        """None 应回退默认值 3。"""
        cfg = self._make_config(max_quality_iterations=None)
        assert cfg.max_quality_iterations == 3

    def test_large_iterations_clamped_to_5_regression(self):
        """超大值 (100 / 1e9) 必须钳制到上限 5。"""
        cfg = self._make_config(max_quality_iterations=100)
        assert cfg.max_quality_iterations == 5, (
            f"100 应被钳制为 5, 实际={cfg.max_quality_iterations}"
        )
        cfg2 = self._make_config(max_quality_iterations=1_000_000)
        assert cfg2.max_quality_iterations == 5

    def test_within_range_values_preserved(self):
        """[1, 5] 范围内的值应原样保留 (int)。"""
        for v in [1, 2, 3, 4, 5]:
            cfg = self._make_config(max_quality_iterations=v)
            assert cfg.max_quality_iterations == v, f"v={v} 被错误地改变"

    def test_main_loop_uses_int_cannot_crash_with_typeerror(self):
        """纵深防御: 主循环入口 max_iterations 必须可被 range() 接受 (即 int)。

        这是对 pipeline 主循环入口处 int() 调用的间接验证 (参见 unified_pipeline.py ~L925)。
        """
        for bad_input in [0, -1, 2.7, "3", "not-a-number", None]:
            cfg = self._make_config(max_quality_iterations=bad_input)
            # 模拟主循环: range(int(max_iterations))
            n = cfg.max_quality_iterations
            assert isinstance(n, int), f"输入={bad_input} → 结果类型={type(n)}, 非 int"
            # 至少能安全构造 range 对象不抛 TypeError
            loop_iters = range(n)
            assert len(loop_iters) >= 1, (
                f"输入={bad_input} 钳制后迭代数={len(loop_iters)} < 1, 会导致空循环无输出"
            )

    # ----------------------------------------------------------
    # min_quality_score
    # ----------------------------------------------------------

    def test_min_quality_score_negative_clamped(self):
        """负质量分钳制到 0.0。"""
        cfg = self._make_config(min_quality_score=-10.0)
        assert cfg.min_quality_score == 0.0

    def test_min_quality_score_over_100_clamped(self):
        """超过 100 的质量分钳制到 100.0。"""
        cfg = self._make_config(min_quality_score=150)
        assert cfg.min_quality_score == 100.0

    def test_min_quality_score_invalid_type_fallback(self):
        """None / 非法字符串 → 默认值 60.0。"""
        cfg = self._make_config(min_quality_score=None)
        assert cfg.min_quality_score == 60.0
        cfg2 = self._make_config(min_quality_score="high")
        assert cfg2.min_quality_score == 60.0

    def test_min_quality_score_bool_not_allowed(self):
        """bool True/False → 默认值 60.0 (不被解释为 0/1 分)。"""
        cfg = self._make_config(min_quality_score=False)
        assert cfg.min_quality_score == 60.0
        cfg2 = self._make_config(min_quality_score=True)
        assert cfg2.min_quality_score == 60.0
