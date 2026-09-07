"""tests/test_style_card.py - 风格知识卡 schema 测试"""
import json
from knowledge.style_card import StyleCard, load_card, list_cards, get_taste_profile


def test_load_amv_highenergy():
    card = load_card("amv_highenergy")
    assert card is not None
    assert card.style_id == "amv_highenergy"
    assert card.name == "高燃混剪"
    assert card.motion_intensity == 8
    assert card.target_beat_alignment == 0.8
    assert "static" in card.forbidden_cameras


def test_load_cyberpunk():
    card = load_card("cyberpunk")
    assert card is not None
    assert card.visual_variance == 8
    assert card.motion_intensity == 7


def test_load_ambient_calm():
    card = load_card("ambient_calm")
    assert card is not None
    assert card.motion_intensity == 2
    assert card.information_density == 2


def test_load_nonexistent():
    assert load_card("nonexistent_style") is None


def test_list_cards():
    cards = list_cards()
    assert len(cards) >= 3
    assert "amv_highenergy" in cards
    assert "cyberpunk" in cards
    assert "ambient_calm" in cards


def test_get_taste_profile():
    taste = get_taste_profile("amv_highenergy")
    assert taste["motion_intensity"] == 8
    assert taste["visual_variance"] == 7


def test_get_taste_profile_fallback():
    taste = get_taste_profile("nonexistent")
    assert taste["motion_intensity"] == 5  # 中性默认


def test_to_dict_roundtrip():
    card = load_card("amv_highenergy")
    d = card.to_dict()
    assert d["style_id"] == "amv_highenergy"
    assert d["taste_profile"]["motion_intensity"] == 8
    assert d["quality_targets"]["beat_alignment"] == 0.8
    assert len(d["anti_patterns"]) >= 2


# ── 消费桥: 卡片 → 导演输入 (2026-08-14 接线) ──

def test_card_to_director_inputs():
    from knowledge.style_card import card_to_director_inputs
    inputs = card_to_director_inputs("amv_highenergy")
    assert inputs, "amv_highenergy 卡片必须可转换为导演输入"
    tp = inputs["taste_profile"]
    assert tp["visual_variance"] == 7
    assert tp["motion_intensity"] == 8
    assert tp["information_density"] == 4
    assert "same_camera_3x" in tp["anti_patterns"]
    ss = inputs["style_spec"]
    cam = ss["camera_preferences"]
    assert "static" in cam["forbidden"]
    assert len(cam["preferred"]) >= 3
    assert ss["color_grade_params"]


def test_card_to_director_inputs_missing_card():
    from knowledge.style_card import card_to_director_inputs
    assert card_to_director_inputs("nonexistent_style") == {}


def test_director_consumes_card_forbidden_cameras():
    """导演 render(style_id=...) 后 _forbidden_cameras 生效且 taste 被覆盖。"""
    from ai.production_director import ProductionDirector
    from ai.taste_contract import TasteProfile
    d = ProductionDirector.__new__(ProductionDirector)
    d.taste = TasteProfile()  # 中性默认

    # 直接复刻 render() 里的消费桥逻辑 (render 全链路依赖真实素材, 单测只验桥)
    from knowledge.style_card import card_to_director_inputs
    _card_inputs = card_to_director_inputs("amv_highenergy")
    assert _card_inputs
    d.taste = TasteProfile.from_dict(_card_inputs["taste_profile"])
    d._forbidden_cameras = list(
        _card_inputs["style_spec"]["camera_preferences"]["forbidden"])

    assert d.taste.motion_intensity == 8
    assert "static" in d._forbidden_cameras
    pool = d.taste.camera_pool()
    assert "static" not in [c for c in pool if c in d._forbidden_cameras]
