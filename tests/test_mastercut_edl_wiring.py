"""mastercut_agent §4 EDL 接线测试（Step2b）：白名单放宽 + tag 派生守卫。

_apply_effects_to_video 的 run_dir 白名单/tag 派生在 lut 检查之前，故可无重夹具、
无 subprocess、无 AE 地轻量验证（直接函数调用返回 dict）。inject 接线本体见
tests/test_inject_edl_tracks.py（7 测）；完整 AE e2e 待真实 run 顺带验证。
"""
from agents.mastercut_agent import _apply_effects_to_video


def test_r1_fixed_without_tag_requires_explicit(tmp_path):
    """r1_fixed run 过白名单, 但 removeprefix 得 'r1_fixed_v7' 非法 tag → 明确要求显式 tag。"""
    out = tmp_path / "unified_r1_fixed_v7"
    res = _apply_effects_to_video(effects=[], output_dir=str(out),
                                  run_dir_name="unified_r1_fixed_v7", tag=None, dry_run=True)
    assert res["success"] is False
    assert "tag" in res["error"] and "r1_fixed_v7" in res["error"]


def test_rejects_invalid_run_dir(tmp_path):
    """非法 run_dir → 白名单拒绝(在任何副作用前)。"""
    res = _apply_effects_to_video(effects=[], output_dir=str(tmp_path / "etc"),
                                  run_dir_name="../etc", tag="run7", dry_run=True)
    assert res["success"] is False
    assert "白名单" in res["error"]


def test_r1_fixed_with_explicit_tag_passes_whitelist(tmp_path):
    """r1_fixed + 显式合法 tag → 过白名单+tag, 卡在 lut 缺失(证明 K3 编排器路径已放行)。"""
    out = tmp_path / "unified_r1_fixed_v7"
    res = _apply_effects_to_video(effects=[], output_dir=str(out),
                                  run_dir_name="unified_r1_fixed_v7", tag="run7", dry_run=True)
    assert res["success"] is False           # 卡在后续 lut 缺失(无真实底片)
    assert "底片" in res["error"] or "lut" in res["error"].lower()
