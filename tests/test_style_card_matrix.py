"""tests/test_style_card_matrix.py — 风格卡矩阵 quick 冒烟 (无渲染/无GPU)

对全部风格卡做决策级验证 (CI 可跑):
  1. 卡片加载 + 消费桥转换
  2. 品味旋钮 → 运镜池 → 禁忌过滤后非空
  3. 模拟 20 镜 T4 轮转: 无超过 2 连重复运镜 (视觉变化度卡)
  4. 高视觉变化度卡 (>=7) 模拟产生 >= 5 种运镜
"""
from __future__ import annotations

import pytest

from ai.camera_decision import suggest_camera_for_shot
from ai.taste_contract import TasteProfile
from knowledge.style_card import card_to_director_inputs, list_cards


@pytest.mark.parametrize("style_id", list_cards())
def test_card_loads_and_bridges(style_id):
    inputs = card_to_director_inputs(style_id)
    assert inputs, f"{style_id} 卡片桥接失败"
    tp = inputs["taste_profile"]
    for key in ("visual_variance", "motion_intensity", "information_density"):
        assert 1 <= tp[key] <= 10, f"{style_id} {key}={tp[key]} 越界"
    ss = inputs["style_spec"]
    cam = ss["camera_preferences"]
    assert isinstance(cam["preferred"], list)
    assert isinstance(cam["forbidden"], list)


@pytest.mark.parametrize("style_id", list_cards())
def test_camera_pool_nonempty_after_forbidden_filter(style_id):
    inputs = card_to_director_inputs(style_id)
    taste = TasteProfile.from_dict(inputs["taste_profile"])
    forbidden = inputs["style_spec"]["camera_preferences"]["forbidden"]
    pool = [c for c in taste.camera_pool() if c not in forbidden]
    assert pool, f"{style_id} 过滤禁忌后运镜池为空 (forbidden={forbidden})"


@pytest.mark.parametrize("style_id", list_cards())
def test_rotation_no_3x_repeat(style_id):
    """T4 轮转模拟: 20 镜不得出现 3 连同一运镜 (所有卡通用铁律)。"""
    inputs = card_to_director_inputs(style_id)
    taste = TasteProfile.from_dict(inputs["taste_profile"])
    forbidden = inputs["style_spec"]["camera_preferences"]["forbidden"]
    pool = [c for c in taste.camera_pool() if c not in forbidden]

    recent: list = []
    picks = []
    for i in range(20):
        pick = suggest_camera_for_shot(
            mood="build", source_camera="zoom_in",
            prev_camera=picks[-1] if picks else "unknown",
            recent=recent, max_repeat=2)
        # T4: 池内轮转 (复刻导演逻辑)
        if taste.visual_variance >= 7 and len(pool) > 1:
            pick = pool[i % len(pool)]
        picks.append(pick)
        recent.append(pick)
        if len(recent) > 2:
            recent.pop(0)
    # 无 3 连重复
    for i in range(2, len(picks)):
        assert not (picks[i] == picks[i-1] == picks[i-2]), (
            f"{style_id} 出现 3 连同一运镜: {picks[i-2:i+1]}")


def test_high_variance_cards_produce_diverse_cameras():
    """视觉变化度 >=7 的卡在模拟中必须产生 >=5 种运镜。"""
    for style_id in list_cards():
        inputs = card_to_director_inputs(style_id)
        taste = TasteProfile.from_dict(inputs["taste_profile"])
        if taste.visual_variance < 7:
            continue
        forbidden = inputs["style_spec"]["camera_preferences"]["forbidden"]
        pool = [c for c in taste.camera_pool() if c not in forbidden]
        picks = {pool[i % len(pool)] for i in range(20)}
        assert len(picks) >= 5, f"{style_id} 高变化度卡仅产生 {len(picks)} 种运镜"


def test_low_variance_cards_use_calm_pool():
    """低运动强度卡 (<=3) 的池不含 push/orbit 等激烈运镜。"""
    for style_id in list_cards():
        inputs = card_to_director_inputs(style_id)
        taste = TasteProfile.from_dict(inputs["taste_profile"])
        if taste.motion_intensity > 3:
            continue
        pool = taste.camera_pool()
        assert not {"push", "orbit", "zoom_back"} & set(pool), (
            f"{style_id} (mi={taste.motion_intensity}) 池含激烈运镜: {pool}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])
