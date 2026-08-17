"""tests/test_camera_decision.py - 决策层强化测试 (T3 Step 2)

导演感知素材运镜:
  1. SourceCameraInventory: 分析素材已有运镜
  2. transition_compatibility: 运镜衔接平滑度
  3. emotion_camera_suggest: 情绪→运镜推荐
"""
from __future__ import annotations

import pytest


# ══════════════════════════════════════════════════════════════════════
# 1. SourceCameraInventory
# ══════════════════════════════════════════════════════════════════════

class TestSourceCameraInventory:
    """素材运镜库存: 告诉导演每段素材有什么运镜"""

    def test_analyze_returns_label_and_confidence(self):
        """analyze 返回 {label, confidence, flow_stats}"""
        from ai.camera_decision import SourceCameraInventory
        inv = SourceCameraInventory()
        # 空分析 (无视频路径) → unknown
        result = inv.analyze("nonexistent.mp4")
        assert result["label"] == "unknown"
        assert result["confidence"] == 0.0

    def test_get_source_movement_cached(self):
        """同一素材多次查询只分析一次"""
        from ai.camera_decision import SourceCameraInventory
        inv = SourceCameraInventory()
        r1 = inv.analyze("nonexistent.mp4")
        r2 = inv.analyze("nonexistent.mp4")
        assert r1 == r2  # 缓存命中

    def test_batch_analyze(self):
        """批量分析返回 dict[path → result]"""
        from ai.camera_decision import SourceCameraInventory
        inv = SourceCameraInventory()
        results = inv.batch_analyze(["a.mp4", "b.mp4"])
        assert len(results) == 2
        assert "a.mp4" in results

    def test_inject_external_labels(self):
        """允许外部注入运镜标签 (如人工标注 / MovieShots 预训练结果)"""
        from ai.camera_decision import SourceCameraInventory
        inv = SourceCameraInventory()
        inv.inject("source_a.mp4", label="pan_left", confidence=0.9)
        result = inv.analyze("source_a.mp4")
        assert result["label"] == "pan_left"
        assert result["confidence"] == 0.9

    def test_get_complementary_camera(self):
        """给定素材运镜, 推荐互补运镜 (素材 pan_left → 推荐 zoom_in 等)"""
        from ai.camera_decision import SourceCameraInventory
        inv = SourceCameraInventory()
        # 素材是 pan_left → 互补应该不是 pan_left
        comp = inv.complementary("pan_left")
        assert comp != "pan_left"
        assert comp in {
            "zoom_in", "zoom_out", "pan_right", "tilt_up", "tilt_down",
            "diag_pan", "static",
        }

    def test_complementary_static(self):
        """素材是 static → 互补推荐运动类运镜"""
        from ai.camera_decision import SourceCameraInventory
        inv = SourceCameraInventory()
        comp = inv.complementary("static")
        assert comp != "static"


# ══════════════════════════════════════════════════════════════════════
# 2. transition_compatibility
# ══════════════════════════════════════════════════════════════════════

class TestTransitionCompatibility:
    """运镜衔接平滑度: 两个相邻运镜是否适合直接切换"""

    def test_same_type_is_smooth(self):
        """同类型运镜衔接平滑 (zoom_in → zoom_in)"""
        from ai.camera_decision import transition_compatibility
        score = transition_compatibility("zoom_in", "zoom_in")
        assert score >= 0.7

    def test_opposite_pan_is_jarring(self):
        """反向平移衔接生硬 (pan_left → pan_right)"""
        from ai.camera_decision import transition_compatibility
        score = transition_compatibility("pan_left", "pan_right")
        assert score <= 0.3

    def test_static_to_any_is_ok(self):
        """static 到任何运镜都可以 (cut 即可)"""
        from ai.camera_decision import transition_compatibility
        assert transition_compatibility("static", "zoom_in") >= 0.5
        assert transition_compatibility("static", "pan_left") >= 0.5

    def test_zoom_in_to_pan_is_ok(self):
        """zoom → pan 是常见组合"""
        from ai.camera_decision import transition_compatibility
        score = transition_compatibility("zoom_in", "pan_left")
        assert score >= 0.5

    def test_symmetry(self):
        """衔接分数对称: score(A,B) == score(B,A)"""
        from ai.camera_decision import transition_compatibility
        pairs = [
            ("pan_left", "pan_right"),
            ("zoom_in", "zoom_out"),
            ("static", "pan_left"),
            ("zoom_in", "pan_right"),
        ]
        for a, b in pairs:
            assert abs(transition_compatibility(a, b) -
                       transition_compatibility(b, a)) < 0.01, (
                f"不对称: {a}→{b} vs {b}→{a}")


# ══════════════════════════════════════════════════════════════════════
# 3. emotion_camera_suggest
# ══════════════════════════════════════════════════════════════════════

class TestEmotionCameraSuggest:
    """情绪→运镜推荐: 不同情绪弧段推荐不同运镜"""

    def test_intro_suggests_gentle(self):
        """intro 推荐温和运镜 (zoom_in / static)"""
        from ai.camera_decision import emotion_camera_suggest
        suggestions = emotion_camera_suggest("intro")
        assert len(suggestions) >= 2
        # 不应包含激烈运镜
        assert "orbit" not in suggestions
        assert "push" not in suggestions

    def test_climax_suggests_strong(self):
        """climax 推荐强烈运镜 (zoom_in / push / orbit)"""
        from ai.camera_decision import emotion_camera_suggest
        suggestions = emotion_camera_suggest("climax")
        assert "zoom_in" in suggestions or "push" in suggestions

    def test_outro_suggests_zoom_out(self):
        """outro 推荐 zoom_out (拉远收尾)"""
        from ai.camera_decision import emotion_camera_suggest
        suggestions = emotion_camera_suggest("outro")
        assert "zoom_out" in suggestions

    def test_unknown_mood_returns_mid_pool(self):
        """未知情绪返回中性运镜池"""
        from ai.camera_decision import emotion_camera_suggest
        suggestions = emotion_camera_suggest("nonexistent_mood")
        assert len(suggestions) >= 3

    def test_all_labels_are_valid_camera_labels(self):
        """推荐结果必须在 CAMERA_LABELS 词汇表中"""
        from ai.camera_decision import emotion_camera_suggest
        from core.camera_movement_classifier import CAMERA_LABELS
        for mood in ["intro", "build", "drop", "climax", "break", "outro"]:
            for label in emotion_camera_suggest(mood):
                assert label in CAMERA_LABELS, (
                    f"mood={mood} 推荐的 '{label}' 不在 CAMERA_LABELS 中")


# ══════════════════════════════════════════════════════════════════════
# 4. 集成: suggest_camera_for_shot (综合决策)
# ══════════════════════════════════════════════════════════════════════

class TestSuggestCameraForShot:
    """综合决策: 情绪 + 素材运镜 + 前一镜运镜 → 最终推荐"""

    def test_avoids_repeating_source_camera(self):
        """素材已有 pan_left → 不推荐叠加 pan_left"""
        from ai.camera_decision import suggest_camera_for_shot
        result = suggest_camera_for_shot(
            mood="build",
            source_camera="pan_left",
            prev_camera="zoom_in",
        )
        assert result != "pan_left"

    def test_avoids_jarring_transition(self):
        """前一镜是 pan_left → 不推荐 pan_right (生硬)"""
        from ai.camera_decision import suggest_camera_for_shot
        result = suggest_camera_for_shot(
            mood="build",
            source_camera="zoom_in",
            prev_camera="pan_left",
        )
        assert result != "pan_right"

    def test_returns_valid_label(self):
        """返回值必须在 CAMERA_LABELS 中"""
        from ai.camera_decision import suggest_camera_for_shot
        from core.camera_movement_classifier import CAMERA_LABELS
        result = suggest_camera_for_shot(
            mood="climax",
            source_camera="static",
            prev_camera="zoom_in",
        )
        assert result in CAMERA_LABELS

    def test_handles_unknown_source(self):
        """素材运镜 unknown 时正常降级"""
        from ai.camera_decision import suggest_camera_for_shot
        result = suggest_camera_for_shot(
            mood="drop",
            source_camera="unknown",
            prev_camera="zoom_out",
        )
        assert result in {
            "static", "pan_left", "pan_right", "zoom_in", "zoom_out",
            "tilt_up", "tilt_down", "zoom_back", "diag_pan", "orbit",
            "push", "complex", "unknown",
        }

    # ── 反锁死 (2026-08-14 修复: v23 build 段 23 镜全 pan_left) ──

    def test_no_same_camera_lock_in(self):
        """连续决策不得锁死在同一种运镜上 (根因: 同运镜衔接 0.85 高分)"""
        from ai.camera_decision import suggest_camera_for_shot
        seq: list = []
        for _ in range(8):
            prev = seq[-1] if seq else "unknown"
            pick = suggest_camera_for_shot(
                mood="build",
                source_camera="zoom_in",
                prev_camera=prev,
                recent=seq,
                max_repeat=2,
            )
            assert pick is not None
            seq.append(pick)
        # 8 镜不得全部同一种
        assert len(set(seq)) >= 3, f"运镜锁死: {seq}"

    def test_recent_window_excludes_previous_two(self):
        """最近 2 镜用过的运镜不在候选内 (有剩余候选时)"""
        from ai.camera_decision import suggest_camera_for_shot
        pick = suggest_camera_for_shot(
            mood="build",
            source_camera="zoom_in",
            prev_camera="pan_left",
            recent=["pan_left", "diag_pan"],
            max_repeat=2,
        )
        assert pick not in ("pan_left", "diag_pan")
        assert pick == "pan_right"

    def test_backward_compat_without_recent(self):
        """不传 recent 时保持旧行为 (不破坏既有调用方)"""
        from ai.camera_decision import suggest_camera_for_shot
        result = suggest_camera_for_shot(
            mood="build",
            source_camera="zoom_in",
            prev_camera="pan_left",
        )
        assert result in {"pan_left", "pan_right", "diag_pan", "zoom_in",
                          "zoom_out", "static"}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])
