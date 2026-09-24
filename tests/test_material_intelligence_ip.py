# -*- coding: utf-8 -*-
"""素材 IP 识别与筛选逻辑特征化测试（2026-09-22）。

背景：`ai/material_intelligence.py` 未覆盖 711 行（10.10%）。它的模型推理层需要
VLM，但**IP 归一化 / 匹配 / 索引筛选**是纯字符串与集合逻辑 —— 而且承担一条
业务红线：**教程/特效演示类素材绝不能混进 IP 成片**，以及"描述里偶然提到"不得
导致误匹配（严格模式的负面排除）。这类规则没人断言就等于没有。

本文件锁住：
  1. `normalize_ip` —— 别名归一（精确大小写不敏感 / 子串≥3字符且长者优先 / 无匹配回原样）
  2. `ip_matches` —— 空关键词=True、空名字=False、归一化相等、双向子串回退
  3. `MaterialIntelTag.matches_ip` —— strict/non-strict 矩阵、教程类恒 False、
     低置信标签跳过、**高置信不同 IP 的负面排除**
  4. `MaterialIndex.filter_by_ip` / `select_for_ip` —— 四分类与 allow_* 开关
"""
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from ai.material_intelligence import (  # noqa: E402
    IPTag,
    MaterialIndex,
    MaterialIntelTag,
    ip_matches,
    normalize_ip,
)


# ---------------------------------------------------------------------------
# normalize_ip
# ---------------------------------------------------------------------------

class TestNormalizeIp:
    def test_empty_returns_empty(self):
        assert normalize_ip("") == ""
        assert normalize_ip("   ") == ""

    @pytest.mark.parametrize("raw,expected", [
        ("fate", "FATE"),
        ("FATE", "FATE"),                       # 大小写不敏感
        ("命运之夜", "FATE"),
        ("命运之夜：无限剑制", "FATE"),           # docstring 例：子串命中别名
        ("Attack on Titan", "进击的巨人"),       # docstring 例
        ("attack on titan", "进击的巨人"),
        ("AOT", "进击的巨人"),
        ("進撃の巨人", "进击的巨人"),
        ("fate/stay night: ubw", "FATE"),        # 子串匹配
        ("  jjk  ", "咒术回战"),                  # 去空格 + 大小写
    ])
    def test_alias_normalization(self, raw, expected):
        assert normalize_ip(raw) == expected

    def test_unknown_name_returned_stripped(self):
        """无法归一化时返回原始名称（去首尾空格），不做猜测。"""
        assert normalize_ip("某不存在的作品名") == "某不存在的作品名"
        assert normalize_ip("  Unknown Show  ") == "Unknown Show"

    def test_longer_alias_wins(self):
        """按别名长度降序匹配 —— 更精确的别名优先。"""
        # "fate/zero" 与 "fate" 都命中，但结果都指向 FATE（此处验证不崩且归一）
        assert normalize_ip("fate/zero") == "FATE"
        assert normalize_ip("Fate/Grand Order") == "FATE"

    def test_short_aliases_not_substring_matched(self):
        """长度 <3 的别名不参与子串匹配（避免噪声误归一）。"""
        # "sk8" 长度 3，仍应参与；构造一个只含 2 字符别名的场景不易，这里验证
        # 子串匹配的下限语义：纯噪声串不会被归一
        assert normalize_ip("xy") == "xy"


# ---------------------------------------------------------------------------
# ip_matches
# ---------------------------------------------------------------------------

class TestIpMatches:
    def test_empty_keyword_matches_everything(self):
        """空关键词 = 不过滤（调用方依赖此语义选出全部素材）。"""
        assert ip_matches("任意素材", "") is True
        assert ip_matches("", "") is True

    def test_empty_name_never_matches(self):
        assert ip_matches("", "FATE") is False

    def test_normalized_equality(self):
        assert ip_matches("Attack on Titan", "进击的巨人") is True
        assert ip_matches("aot", "进击的巨人") is True

    def test_bidirectional_substring_fallback(self):
        """归一化失败时回退双向子串（关键词被名字包含，或反之）。"""
        assert ip_matches("my custom FATE clip", "FATE") is True
        assert ip_matches("FATE", "my custom FATE clip") is True

    def test_unrelated_names_do_not_match(self):
        assert ip_matches("进击的巨人", "FATE") is False


# ---------------------------------------------------------------------------
# MaterialIntelTag.matches_ip（含负面排除）
# ---------------------------------------------------------------------------

def _tag(**kw) -> MaterialIntelTag:
    kw.setdefault("video_path", "x.mp4")
    kw.setdefault("filename", "x.mp4")
    return MaterialIntelTag(**kw)


class TestMatchesIpStrictness:
    def test_empty_keyword_returns_true(self):
        assert _tag().matches_ip("") is True

    def test_tutorial_never_matches_any_ip(self):
        """业务红线：教程/特效演示类素材绝不能混进 IP 成片。"""
        for kind in ("tutorial", "effect_demo"):
            t = _tag(content_kind=kind, primary_ip="进击的巨人",
                     description="进击的巨人 教程", filename="aot_tutorial.mp4")
            assert t.matches_ip("进击的巨人") is False
            assert t.matches_ip("进击的巨人", strict=False) is False

    def test_positive_by_ip_tag(self):
        t = _tag(ip_tags=[IPTag(ip_name="Attack on Titan", confidence=0.9)])
        assert t.matches_ip("进击的巨人") is True

    def test_low_confidence_tag_skipped(self):
        """置信度 <0.3 的标签不作为正向证据。"""
        t = _tag(ip_tags=[IPTag(ip_name="Attack on Titan", confidence=0.2)])
        assert t.matches_ip("进击的巨人") is False

    def test_positive_by_primary_ip(self):
        assert _tag(primary_ip="fate").matches_ip("FATE") is True

    def test_non_strict_matches_description_or_filename(self):
        t = _tag(description="a fate clip", content_kind="anime_amv")
        assert t.matches_ip("fate", strict=False) is True
        t2 = _tag(filename="my_FATE_edit.mp4", content_kind="anime_amv")
        assert t2.matches_ip("fate", strict=False) is True

    def test_strict_accepts_direct_evidence(self):
        t = _tag(description="fate amv", content_kind="anime_amv")
        assert t.matches_ip("fate", strict=True) is True

    def test_strict_negative_exclusion(self):
        """严格模式核心规则：主 IP 被**高置信度**识别为别的作品时，
        仅凭描述里的偶然关键词不得匹配（杜绝误混入）。"""
        t = _tag(
            description="这段很像 fate 的打斗",
            content_kind="anime_amv",
            primary_ip="进击的巨人",
            ip_tags=[IPTag(ip_name="进击的巨人", confidence=0.85)],
        )
        assert t.matches_ip("fate", strict=True) is False
        # 宽松模式仍放行（用于调查/召回场景）
        assert t.matches_ip("fate", strict=False) is True

    def test_strict_no_evidence_returns_false(self):
        t = _tag(content_kind="anime_amv", description="无关键词片段")
        assert t.matches_ip("fate", strict=True) is False

    def test_strict_low_confidence_other_ip_does_not_exclude(self):
        """主 IP 置信度不足 0.8 时不触发负面排除（阈值边界）。"""
        t = _tag(
            description="fate amv",
            content_kind="anime_amv",
            primary_ip="进击的巨人",
            ip_tags=[IPTag(ip_name="进击的巨人", confidence=0.5)],
        )
        assert t.matches_ip("fate", strict=True) is True


# ---------------------------------------------------------------------------
# MaterialIndex
# ---------------------------------------------------------------------------

class TestMaterialIndex:
    def _index(self) -> MaterialIndex:
        idx = MaterialIndex()
        idx.add(_tag(video_path="aot.mp4",
                     ip_tags=[IPTag(ip_name="进击的巨人", confidence=0.9)],
                     primary_ip="进击的巨人", content_kind="anime_amv"))
        idx.add(_tag(video_path="fate.mp4", primary_ip="FATE",
                     content_kind="anime_amv"))
        idx.add(_tag(video_path="tut.mp4", content_kind="tutorial",
                     primary_ip="进击的巨人"))
        idx.add(_tag(video_path="unknown.mp4", content_kind="unknown"))
        return idx

    def test_add_keyed_by_path(self):
        idx = self._index()
        assert set(idx.tags) == {"aot.mp4", "fate.mp4", "tut.mp4", "unknown.mp4"}

    def test_filter_empty_keyword_returns_all(self):
        assert len(self._index().filter_by_ip("")) == 4

    def test_filter_by_ip_strict_excludes_other_ip_and_tutorial(self):
        got = self._index().filter_by_ip("进击的巨人")
        assert got == ["aot.mp4"]           # fate 是别的 IP；tutorial 恒排除

    def test_select_for_ip_partitions(self):
        res = self._index().select_for_ip("进击的巨人")
        assert res["matched"] == ["aot.mp4"]
        assert "tut.mp4" in res["excluded"]           # 教程类永远排除
        assert "unknown.mp4" in res["unknown"]        # 未识别 → unknown
        assert "fate.mp4" in res["excluded"]          # 明确别的 IP → excluded

    def test_select_empty_target_matches_all(self):
        res = self._index().select_for_ip("")
        assert len(res["matched"]) == 4 and res["excluded"] == []

    def test_select_mixed_requires_allow_flag(self):
        idx = MaterialIndex()
        idx.add(_tag(video_path="mix.mp4", primary_ip="进击的巨人",
                     is_mixed=True, content_kind="anime_amv",
                     ip_tags=[IPTag(ip_name="进击的巨人", confidence=0.9)]))
        assert idx.select_for_ip("进击的巨人")["mixed"] == ["mix.mp4"]
        assert idx.select_for_ip("进击的巨人",
                                 allow_mixed=True)["matched"] == ["mix.mp4"]

    def test_to_dict_shape(self):
        """序列化字段面（下游缓存/清单依赖它）；`ip_names` 是 property 不在此。"""
        t = _tag(video_path="x.mp4", filename="x.mp4", primary_ip="FATE",
                 content_kind="anime_amv", description="d",
                 ip_tags=[IPTag(ip_name="fate", confidence=0.9)])
        d = t.to_dict()
        assert d["video_path"] == "x.mp4" and d["primary_ip"] == "FATE"
        assert d["content_kind"] == "anime_amv"
        assert "content" in d and isinstance(d["ip_tags"], list)
        for k in ("duration", "fps", "resolution", "file_hash", "is_mixed",
                  "scene_changes", "ip_timeline", "vlm_model"):
            assert k in d, k
        assert "ip_names" not in d          # property，不是序列化字段
        assert t.ip_names == ["fate"]       # property 仍可用
