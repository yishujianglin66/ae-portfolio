# -*- coding: utf-8 -*-
"""分流检索路由逻辑单测（2026-09-08，基准 v2 证据驱动）。

只测纯逻辑（query_has_alias_hit / decide_route），不加载模型。
路由证据: output/evidence/r3_benchmark_v2_20260908/
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai.t11_hybrid_search import (  # noqa: E402
    RERANK_ENV, decide_route, query_has_alias_hit,
)


class TestQueryHasAliasHit(unittest.TestCase):
    """别名命中判定：CHAR_TO_IP 键 / IP 名双向子串。"""

    def test_char_alias_hit(self):
        self.assertTrue(query_has_alias_hit("艾伦变身"))
        self.assertTrue(query_has_alias_hit("利威尔兵长砍后颈"))
        self.assertTrue(query_has_alias_hit("御坂美琴"))

    def test_ip_name_hit(self):
        self.assertTrue(query_has_alias_hit("进击的巨人高燃混剪"))
        self.assertTrue(query_has_alias_hit("鬼灭之刃"))

    def test_reverse_substring_hit(self):
        # 查询是别名的子串（如"兵长"）
        self.assertTrue(query_has_alias_hit("兵长"))

    def test_natural_language_no_hit(self):
        # 基准 v2 held-out 风格：场景白描，不含任何别名/IP名
        self.assertFalse(query_has_alias_hit("体内封印九尾妖狐的孤儿"))
        self.assertFalse(query_has_alias_hit("召唤英灵争夺圣杯的战争"))
        self.assertFalse(query_has_alias_hit("蒙眼教师摘下眼罩的瞬间"))

    def test_empty_query(self):
        self.assertFalse(query_has_alias_hit(""))


class TestDecideRoute(unittest.TestCase):
    """分流决策：开关默认关；启用后按别名命中路由。"""

    def setUp(self):
        self._old = os.environ.pop(RERANK_ENV, None)

    def tearDown(self):
        if self._old is None:
            os.environ.pop(RERANK_ENV, None)
        else:
            os.environ[RERANK_ENV] = self._old

    def test_default_off_alias_query(self):
        self.assertEqual(decide_route("艾伦变身"), "hybrid")

    def test_default_off_natural_query(self):
        # 默认关：即使自然语言查询也走原链路
        self.assertEqual(decide_route("体内封印九尾妖狐的孤儿"), "hybrid")

    def test_enabled_alias_goes_hybrid(self):
        os.environ[RERANK_ENV] = "1"
        self.assertEqual(decide_route("利威尔兵长"), "hybrid")

    def test_enabled_natural_goes_rerank(self):
        os.environ[RERANK_ENV] = "1"
        self.assertEqual(decide_route("体内封印九尾妖狐的孤儿"), "semantic_rerank")

    def test_enabled_other_value_ignored(self):
        os.environ[RERANK_ENV] = "true"  # 非 "1" 不启用
        self.assertEqual(decide_route("体内封印九尾妖狐的孤儿"), "hybrid")


if __name__ == "__main__":
    unittest.main()
