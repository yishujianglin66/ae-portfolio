# -*- coding: utf-8 -*-
"""词级粗剪链路（core/word_rough_cut.py）单元测试。

不依赖 whisper/媒体：用构造词表锁定三个核心不变式——
 1) plan_phrases 断句规则（停顿/超长/句末标点）
 2) 口播模式 EDL 时间轴与词级时间戳绝对一致（L7 错位 bug 回归锁）
 3) 生成的 EDL 必过 scripts.edl.lint_edl
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.word_rough_cut import build_word_edl, plan_phrases  # noqa: E402
from scripts.edl import lint_edl  # noqa: E402

WORDS = [
    {"start": 0.0, "end": 0.4, "word": "你好"},
    {"start": 0.4, "end": 0.8, "word": "世界"},          # 句末无标点，下一词 gap 1.2s
    {"start": 2.0, "end": 2.5, "word": "这是"},
    {"start": 2.5, "end": 3.0, "word": "第二句。"},       # 句末标点断
    {"start": 3.6, "end": 4.0, "word": "超长"},
    {"start": 4.0, "end": 4.4, "word": "短语"},
    {"start": 4.4, "end": 4.8, "word": "测试"},
    {"start": 4.8, "end": 5.2, "word": "字符"},
    {"start": 5.2, "end": 5.6, "word": "长度"},
    {"start": 5.6, "end": 6.0, "word": "截断"},
    {"start": 6.0, "end": 6.4, "word": "上限"},
    {"start": 6.4, "end": 6.8, "word": "生效"},
    {"start": 6.8, "end": 7.2, "word": "验证"},
    {"start": 7.2, "end": 7.6, "word": "收尾"},
]


def test_plan_breaks_on_gap_and_punct():
    phrases = plan_phrases(WORDS, max_gap=0.65, max_chars=16)
    texts = [p["text"] for p in phrases]
    # 停顿 1.2s 处必须断开（"你好世界" 独立成短语）
    assert texts[0] == "你好世界"
    # 句末标点断（"这是第二句。"）
    assert any(t.endswith("。") for t in texts)
    # 短语区间不重叠且升序
    for a, b in zip(phrases, phrases[1:]):
        assert a["end"] <= b["start"]


def _dummy_media(tmp_path) -> Path:
    """build_word_edl 要算输入指纹（诚实要求文件存在），测试用占位音频文件。"""
    m = tmp_path / "vo.wav"
    m.write_bytes(b"RIFF")
    return m


def test_vo_mode_absolute_alignment(tmp_path):
    """口播模式：cut.start/end == 短语绝对时间，timeline 覆盖末词 t_out。"""
    phrases = plan_phrases(WORDS)
    edl = build_word_edl(_dummy_media(tmp_path), WORDS, phrases)
    assert edl["cuts"][0]["start_time"] == WORDS[0]["start"]
    assert edl["render"]["duration"] >= WORDS[-1]["end"]
    last_te = edl["text_events"][-1]
    assert last_te["t_out"] <= edl["render"]["duration"] + 1e-6


def test_broll_mode_compact(tmp_path):
    """B-roll 模式：紧凑排布，短语间停顿不留白。"""
    phrases = plan_phrases(WORDS)
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    edl = build_word_edl(_dummy_media(tmp_path), WORDS, phrases, footage=[str(a), str(b)])
    # 第一个 cut 从 0 开始（非绝对时间）
    assert edl["cuts"][0]["start_time"] == 0.0
    # 素材轮询分配
    assert edl["cuts"][0]["source_file"].endswith("a.mp4")
    assert edl["cuts"][1]["source_file"].endswith("b.mp4")


def test_edl_passes_lint(tmp_path):
    phrases = plan_phrases(WORDS)
    media = tmp_path / "vo.wav"
    media.write_bytes(b"RIFF")  # lint 不读媒体内容，只需路径存在算指纹
    edl = build_word_edl(media, WORDS, phrases)
    errs = lint_edl(edl)
    assert errs == [], f"lint 未过: {errs}"


def test_text_events_word_level(tmp_path):
    phrases = plan_phrases(WORDS)
    edl = build_word_edl(_dummy_media(tmp_path), WORDS, phrases)
    assert len(edl["text_events"]) == len(WORDS)
    te = edl["text_events"][0]
    assert set(te) >= {"t_in", "t_out", "word", "style_id"}
