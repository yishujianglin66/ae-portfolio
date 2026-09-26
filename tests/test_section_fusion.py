# -*- coding: utf-8 -*-
"""段落边界融合转场 (2026-09-25, "高级剪辑技巧融合镜头") 的单元测试。

规则出处: ProductionDirector._section_fusion / SECTION_FUSION_MAP。
设计意图: 弧切换点用融合转场标记章节感, 同弧内保持硬切节奏;
进入喘息(break)一律硬切(瞬间静止是节奏设计); 白闪/叠化各有密度预算。
"""
import pytest

from ai.production_director import ProductionDirector


F = ProductionDirector._section_fusion


class TestSectionFusionVocabulary:
    """词典: 按能量走向选型, 未列出的一律真叠化。"""

    @pytest.mark.parametrize("prev,cur,tag", [
        ("build", "drop", "flash"),      # 蓄力→爆发: 白闪
        ("intro", "drop", "flash"),
        ("break", "drop", "flash"),      # 喘息→爆发
        ("drop", "climax", "flash"),
        ("intro", "build", "zoom"),      # 铺垫→蓄力: zoom 上升感
        ("break", "build", "zoom"),
        ("drop", "outro", "fade"),       # →尾声: fadeblack 收
        ("climax", "outro", "fade"),
        ("intro", "break", None),        # →喘息: 硬切(突然安静是设计)
        ("drop", "break", None),
        ("drop", "drop", "cross_dissolve"),   # 未列出的边界: 真叠化
        ("intro", "outro", "cross_dissolve"),
    ])
    def test_pair_mapping(self, prev, cur, tag):
        assert F(prev, cur, 100.0, -99.0, -99.0) == tag


class TestSectionFusionBudgets:
    """密度预算: 融合至少隔 3s; 段落白闪至少隔 8s(降级为叠化不丢边界感)。"""

    def test_fusion_gap_blocks(self):
        # 距上次融合仅 1.5s → 不融合
        assert F("build", "drop", 10.0, 8.5, -99.0) is None

    def test_fusion_gap_exact_boundary(self):
        # 恰好 3.0s → 放行(预算语义是"至少间隔")
        assert F("build", "drop", 10.0, 7.0, -99.0) == "flash"

    def test_section_flash_gap_downgrades_to_dissolve(self):
        # 距上次段落白闪 5s(<8s) → 白闪降级为叠化, 边界感保留
        assert F("break", "drop", 10.0, -99.0, 5.0) == "cross_dissolve"

    def test_section_flash_gap_ok_keeps_flash(self):
        assert F("break", "drop", 10.0, -99.0, 2.0) == "flash"

    def test_flash_downgrade_still_respects_fusion_gap(self):
        # 融合预算先判: 间隔不足直接 None, 不会降级出叠化
        assert F("break", "drop", 10.0, 8.5, 5.0) is None

    def test_dissolve_not_subject_to_flash_budget(self):
        # 叠化不受白闪预算约束(白闪预算只管白闪)
        assert F("intro", "outro", 10.0, -99.0, 1.0) == "cross_dissolve"


class TestXfadeForSpeedGateLifted:
    """变速禁令解除(2026-09-25 受控实验: 漂移 ≤2帧, 帧守恒精确)。"""

    def test_speed_changed_segment_gets_transition(self):
        d = ProductionDirector.__new__(ProductionDirector)
        name, dur = d._xfade_for(type("S", (), {
            "transition": "fade", "transition_params": {}, "speed": 0.55})())
        assert (name, dur) == ("fadeblack", 8 / 24)  # 0.35s 帧量化 → 8帧


class TestAnchorHitPicking:
    """小提琴重拍对齐 (2026-09-25, "镜头没精确卡点小提琴重拍")。

    数据(cache/stems/*/anchors.json): melody_onsets(小提琴攻击音+音变点,
    带强度) + kick/snare_onsets(鼓点相位)。强锚=强度≥0.85;
    "在鼓点相位上"=±65ms 内有 kick/snare — 离格装饰音不跟(R-0001 教训:
    切点跟离格事件走会被判"完全不在点上")。
    """

    @pytest.fixture()
    def director(self):
        d = ProductionDirector.__new__(ProductionDirector)
        # 小型号锚表: 两个强锚(一个在相位一个离格) + 一个弱锚(在相位)
        d._grid_melody_anchors = [
            (1.000, 0.90),   # 强锚, 在相位
            (2.000, 0.95),   # 强锚, 离格(距鼓点 200ms)
            (3.000, 0.50),   # 弱锚, 在相位
        ]
        d._strong_melody_anchors = [(t, s) for t, s in d._grid_melody_anchors
                                    if s >= 0.85]
        d._anchor_drums = [0.95, 2.200, 3.020]  # 稀疏鼓点相位(3.0 弱锚在相位)
        return d

    def test_strongest_on_grid_anchor_wins(self, director):
        # ±0.5s 内唯一强锚且在相位 → 命中
        assert director._pick_anchor_hit(1.05, 0.5, min_strength=0.85) == 1.000

    def test_off_grid_strong_anchor_rejected(self, director):
        # 2.000 强锚但离格(距 2.200 鼓点 200ms > 65ms) → 拒绝
        assert director._pick_anchor_hit(2.0, 0.5, min_strength=0.85) is None

    def test_weak_anchor_only_for_unfiltered_tier(self, director):
        # 强锚档排除弱锚; 全量档(帧级校准)允许
        assert director._pick_anchor_hit(3.0, 0.5, min_strength=0.85) is None
        assert director._pick_anchor_hit(3.0, 0.5) == 3.000

    def test_strength_beats_proximity(self, director):
        # 同窗内强锚优先于更近的弱锚
        director._grid_melody_anchors = [(1.000, 0.86), (1.040, 0.99)]
        director._strong_melody_anchors = list(director._grid_melody_anchors)
        director._anchor_drums = [1.000, 1.040]
        assert director._pick_anchor_hit(1.02, 0.5, min_strength=0.85) == 1.040

    def test_grid_tolerance_boundary(self, director):
        # 恰好 65ms 视为在相位(≤语义), 66ms 视为离格
        director._grid_melody_anchors = [(5.000, 0.9), (6.000, 0.9)]
        director._strong_melody_anchors = list(director._grid_melody_anchors)
        director._anchor_drums = [5.065, 6.066]
        assert director._anchor_on_grid(5.000) is True
        assert director._anchor_on_grid(6.000) is False
