"""scripts/grade_highlight_rolloff.py 的可复用 API 契约测试。

该模块已从"一次性脚本"提升为**管线可调用后级**（`apply_highlight_rolloff`），
此处只钉纯函数与参数校验（不跑 ffmpeg，CI 友好）；实际滤镜链的正确性由审计
实测数据与 docs/handoff §9.4 记录。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parent.parent / "scripts" / "grade_highlight_rolloff.py"
_spec = importlib.util.spec_from_file_location("grade_highlight_rolloff", _MOD)
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)


def test_gentle_chain_is_default_and_only_rolls_off_highlights() -> None:
    chain = g.build_filter_chain()
    assert chain.startswith("curves=")
    # 保中间调：0/0 与 0.5 不在链里被下压（gentle 档从 0.7 起才压）
    assert "0.7/0.7" in chain
    assert "cas=" not in chain and "eq=" not in chain


def test_chain_appends_optional_stages() -> None:
    assert "cas=strength=" in g.build_filter_chain(sharpen="light")
    assert "eq=saturation=0.97" in g.build_filter_chain(saturation=0.97)
    both = g.build_filter_chain(shoulder="strong", sharpen="medium", saturation=0.9)
    assert both.index("curves=") < both.index("cas=") < both.index("eq=")


def test_unknown_options_raise() -> None:
    with pytest.raises(ValueError):
        g.build_filter_chain(shoulder="nope")
    with pytest.raises(ValueError):
        g.build_filter_chain(sharpen="nope")


def test_apply_rejects_unknown_shoulder_before_touching_ffmpeg() -> None:
    with pytest.raises(ValueError):
        g.apply_highlight_rolloff("in.mp4", "out.mp4", shoulder="nope")
