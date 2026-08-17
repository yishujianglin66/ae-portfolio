"""Tests for Director content metrics submission (Task 4)

验证导演把卡点/运镜/素材窗口/能量序列提交给自进化引擎。
"""
from ai.production_director import ProductionDirector


def test_collect_content_metrics_from_script():
    """导演必须从 script + _beats + _used_windows 组装内容指标"""
    d = ProductionDirector.__new__(ProductionDirector)  # 绕过重初始化

    # 模拟 _beats (BeatInfo 对象列表)
    d._beats = [type("B", (), {"time": t})() for t in (1.0, 2.0, 3.0)]
    # 模拟 _used_windows
    d._used_windows = {"src_a.mp4": [[0.0, 2.5], [6.0, 8.0]]}

    # 模拟 script.segments (DirectorSegment-like)
    seg1 = type("Seg", (), {
        "start_time": 1.02, "zoompan_effect": "pan_left",
        "source_file": "src_a.mp4", "energy": 0.8,
    })()
    seg2 = type("Seg", (), {
        "start_time": 2.01, "zoompan_effect": "zoom_in",
        "source_file": "src_b.mp4", "energy": 0.6,
    })()
    script = type("Script", (), {"segments": [seg1, seg2]})()

    content = d._collect_content_metrics(script)

    assert content["beat_times"] == [1.0, 2.0, 3.0]
    assert content["cut_times"] == [1.02, 2.01]
    assert content["camera_moves"] == ["pan_left", "zoom_in"]
    assert ("src_a.mp4", 0.0, 2.5) in content["material_windows"]
    assert ("src_a.mp4", 6.0, 8.0) in content["material_windows"]
    assert content["energy_series"] == [0.8, 0.6]


def test_collect_content_metrics_empty_script():
    """空 script → 空列表, 不崩溃"""
    d = ProductionDirector.__new__(ProductionDirector)
    d._beats = []
    d._used_windows = {}
    script = type("Script", (), {"segments": []})()

    content = d._collect_content_metrics(script)

    assert content["beat_times"] == []
    assert content["cut_times"] == []
    assert content["camera_moves"] == []
    assert content["material_windows"] == []
    assert content["energy_series"] == []


def test_collect_content_metrics_none_beats():
    """_beats 为 None → 空列表"""
    d = ProductionDirector.__new__(ProductionDirector)
    d._beats = None
    d._used_windows = {}
    script = type("Script", (), {"segments": []})()

    content = d._collect_content_metrics(script)
    assert content["beat_times"] == []


def test_collect_content_metrics_no_camera():
    """segment 无 zoompan_effect → camera_moves 跳过该段"""
    d = ProductionDirector.__new__(ProductionDirector)
    d._beats = []
    d._used_windows = {}
    seg = type("Seg", (), {
        "start_time": 1.0, "zoompan_effect": None,
        "source_file": "src.mp4", "energy": 0.5,
    })()
    script = type("Script", (), {"segments": [seg]})()

    content = d._collect_content_metrics(script)
    assert content["camera_moves"] == []
    assert content["cut_times"] == [1.0]
