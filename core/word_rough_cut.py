# -*- coding: utf-8 -*-
"""word_rough_cut.py — 词级粗剪链路（P1：Whisper→EDL）

把"口播/对白音频"转成词级时间轴，再按停顿切短语、生成可落盘可 lint 的
EDL 1.1（cuts=短语级剪切单元，text_events=词级字幕/文字轨），供下游
unified_edit / 文字动画系统消费。与 beat_anchors（节拍驱动）并列，构成
"音乐节拍驱动 + 语音词级驱动"双入口。

链路:  口播媒体 --whisper(word_timestamps)--> 词时间轴 --plan_phrases--> 短语
       --build_word_edl--> EDL 1.1 --lint_edl--> 可渲染

用法:
  python core/word_rough_cut.py <media> [--out DIR] [--model small]
  from core.word_rough_cut import rough_cut
  summary = rough_cut("vo.mp4", out_dir="output/word_cut")
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.edl import EDL_SCHEMA_VERSION, _ffmpeg_version, _sha1_of  # noqa: E402

DEFAULT_MODEL = "small"          # 461MB，cuda 实测 30s 音频 1.4s 转写
DEFAULT_MAX_GAP = 0.65           # 停顿 >0.65s 断短语（口播自然停顿阈值）
DEFAULT_MAX_CHARS = 16           # 单短语字数上限（CJK 显示友好）
DEFAULT_MAX_WORDS = 8            # 单短语词数上限（非 CJK 兜底）


def transcribe_words(media: str | Path, model_name: str = DEFAULT_MODEL,
                     language: str | None = None, use_cache: bool = True) -> list[dict]:
    """Whisper 词级转写。返回 [{start,end,word}]，按时间升序。

    缓存：媒体同目录 `<stem>.words.json`（媒体指纹相同才复用，防止改稿后陈旧）。
    """
    media = Path(media)
    if not media.exists():
        raise FileNotFoundError(f"媒体不存在: {media}")
    cache = media.with_suffix(".words.json")
    fp = _sha1_of(str(media))
    if use_cache and cache.exists():
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            if cached.get("source_sha1") == fp:
                return cached["words"]
        except (ValueError, KeyError):
            pass  # 缓存坏损则重转

    import whisper  # 延迟导入：未装环境也能 import 本模块看接口
    model = whisper.load_model(model_name)
    result = model.transcribe(str(media), language=language,
                              word_timestamps=True, verbose=False)
    words: list[dict] = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            words.append({"start": round(float(w["start"]), 3),
                          "end": round(float(w["end"]), 3),
                          "word": str(w["word"]).strip()})
    words.sort(key=lambda w: w["start"])
    cache.write_text(json.dumps({
        "source": str(media), "source_sha1": fp,
        "model": model_name, "language": result.get("language"),
        "words": words,
    }, ensure_ascii=False), encoding="utf-8")
    return words


def _phrase_len(words: list[dict]) -> int:
    """CJK 按字符数、其余按词数折中：取 max(字符数//2, 词数)。"""
    chars = sum(len(w["word"]) for w in words)
    return max(chars // 2, len(words))


def plan_phrases(words: list[dict], max_gap: float = DEFAULT_MAX_GAP,
                 max_chars: int = DEFAULT_MAX_CHARS,
                 max_words: int = DEFAULT_MAX_WORDS) -> list[dict]:
    """词时间轴 → 短语单元。断开条件：停顿>max_gap / 超长 / 句末标点。"""
    if not words:
        return []
    sentences_end = ("。", "？", "！", "!", "?", ".", "…")
    phrases: list[dict] = []
    buf: list[dict] = []

    def flush() -> None:
        if not buf:
            return
        phrases.append({
            "start": buf[0]["start"], "end": buf[-1]["end"],
            "text": "".join(w["word"] for w in buf).strip(),
            "words": [dict(w) for w in buf],
        })
        buf.clear()

    for i, w in enumerate(words):
        buf.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap_break = nxt is not None and (nxt["start"] - w["end"]) > max_gap
        size_break = _phrase_len(buf) >= max_words or sum(len(x["word"]) for x in buf) >= max_chars
        punct_break = w["word"].rstrip().endswith(sentences_end)
        if gap_break or size_break or punct_break or nxt is None:
            flush()
    return phrases


def build_word_edl(media: str | Path, words: list[dict], phrases: list[dict],
                   *, footage: list[str] | None = None, fps: int = 30,
                   theme: str = "", style: str = "word_cut") -> dict:
    """短语+词级 → EDL 1.1（cuts 短语级；text_events 词级；可选 B-roll 素材轮询）。

    footage 为空：cuts 直接引用口播媒体本身（对口型/字幕场景）；
    footage 非空：每条短语轮询分配一个素材段（词级驱动的画面对位粗剪）。
    """
    media = Path(media)
    footage = [Path(f) for f in (footage or [])]
    cuts, cut_points = [], []
    cursor = 0.0
    for i, ph in enumerate(phrases):
        dur = round(ph["end"] - ph["start"], 3)
        src = footage[i % len(footage)] if footage else media
        if footage:
            # B-roll 对位模式：紧凑排布，短语间停顿不留白
            start_t, end_t = cursor, round(cursor + dur, 3)
            cursor = end_t
            source_start = 0.0
        else:
            # 口播驱动模式：cut 时间轴必须与音频绝对时间一致，
            # 否则 text_events 词级时间戳与 timeline 错位（lint L7 拦截）
            start_t, end_t = ph["start"], ph["end"]
            cursor = max(cursor, end_t)
            source_start = ph["start"]
        cuts.append({
            "index": i, "start_time": start_t, "end_time": end_t,
            "source_file": str(src), "source_start": source_start,
            "speed": 1.0, "transition": "cut", "mood": "word_sync",
            "energy": 0, "phrase_text": ph["text"],
        })
        cut_points.append(start_t)
    edl: dict[str, Any] = {
        "schema_version": EDL_SCHEMA_VERSION,
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "render": {"style": style, "theme": theme, "duration": round(cursor, 3),
                   "fps": fps, "resolution": "1920x1080"},
        "inputs": [{"path": str(media), "sha1": _sha1_of(str(media)), "size_bytes": media.stat().st_size}]
                  + [{"path": str(f), "sha1": _sha1_of(str(f)), "size_bytes": Path(f).stat().st_size}
                     for f in footage],
        "cuts": cuts,
        "cut_points": cut_points,
        "text_events": [{"t_in": w["start"], "t_out": w["end"], "word": w["word"],
                         "style_id": "default", "skill_id": ""} for w in words],
        "toolchain": {"ffmpeg": _ffmpeg_version(), "python": sys.version.split()[0],
                      "edl_schema": EDL_SCHEMA_VERSION, "driver": "word_rough_cut"},
    }
    return edl


def rough_cut(media: str | Path, out_dir: str | Path, *, model_name: str = DEFAULT_MODEL,
              language: str | None = None, footage: list[str] | None = None,
              theme: str = "", **plan_kwargs) -> dict:
    """端到端入口：转写→短语→EDL→lint。返回产物路径与统计。"""
    media = Path(media)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    words = transcribe_words(media, model_name=model_name, language=language)
    phrases = plan_phrases(words, **plan_kwargs)
    edl = build_word_edl(media, words, phrases, footage=footage, theme=theme)

    from scripts.edl import lint_edl, save_edl
    errors = lint_edl(edl)
    edl_path = save_edl(edl, out / "edl.json")

    summary = {
        "media": str(media), "edl": str(edl_path),
        "words_json": str(media.with_suffix(".words.json")),
        "n_words": len(words), "n_phrases": len(phrases),
        "duration": edl["render"]["duration"], "lint_errors": errors,
    }
    (out / "word_cut_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="词级粗剪链路（Whisper→EDL）")
    ap.add_argument("media", help="口播/对白媒体文件")
    ap.add_argument("--out", default="output/word_cut", help="产物目录")
    ap.add_argument("--model", default=DEFAULT_MODEL, choices=["tiny", "base", "small", "medium", "large-v3"])
    ap.add_argument("--language", default=None)
    ap.add_argument("--footage", nargs="*", default=None, help="B-roll 素材池（可选）")
    a = ap.parse_args()
    s = rough_cut(a.media, a.out, model_name=a.model, language=a.language, footage=a.footage)
    ok = not s["lint_errors"]
    print(f"词 {s['n_words']} | 短语 {s['n_phrases']} | 时长 {s['duration']}s | "
          f"lint: {'PASS' if ok else s['lint_errors']}")
    print(f"EDL: {s['edl']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
