"""
Subtitle Burner - 字幕烧录引擎
==============================
支持:
1. SRT/ASS 字幕文件 → AE JSX 文字层
2. Whisper 自动转录 → SRT → AE JSX
3. 多种字幕动画样式 (淡入/打字机/卡拉OK/弹跳)
4. 智能排版 (位置/大小/描边/阴影)

用法:
    burner = SubtitleBurner()
    # 从 SRT 文件
    jsx = burner.from_srt("subs.srt", video_duration=30)
    # 从 Whisper 自动转录
    jsx = burner.from_audio("video.mp4")
    # 手动字幕
    jsx = burner.from_text([{"start": 0, "end": 3, "text": "Hello"}])
"""
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


# ================================================================
#  1. 字幕解析器
# ================================================================
class SubtitleParser:
    """解析 SRT/ASS 字幕文件"""

    def parse_srt(self, srt_path: str) -> list[dict[str, Any]]:
        """解析 SRT 文件"""
        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()

        entries = []
        blocks = re.split(r'\n\s*\n', content.strip())

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue

            # 第一行: 序号
            # 第二行: 时间轴
            time_match = re.match(
                r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})',
                lines[1].strip()
            )
            if not time_match:
                continue

            g1, m1, s1, ms1, g2, m2, s2, ms2 = [int(x) for x in time_match.groups()]
            start = g1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
            end = g2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0

            # 剩余行: 字幕文本
            text = '\n'.join(lines[2:]).strip()
            # 清除 HTML/ASS 标签
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'\{[^}]+\}', '', text)

            entries.append({
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
                "text": text,
            })

        log(f"  SRT 解析: {len(entries)} 条字幕")
        return entries

    def parse_ass(self, ass_path: str) -> list[dict[str, Any]]:
        """解析 ASS 文件"""
        with open(ass_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        entries = []
        for line in lines:
            if line.startswith("Dialogue:"):
                parts = line.split(",", 9)
                if len(parts) < 10:
                    continue
                start = self._ass_time_to_sec(parts[1].strip())
                end = self._ass_time_to_sec(parts[2].strip())
                text = parts[9].strip()
                text = re.sub(r'\{[^}]+\}', '', text)

                if text and start < end:
                    entries.append({
                        "start": round(start, 3),
                        "end": round(end, 3),
                        "duration": round(end - start, 3),
                        "text": text,
                    })

        log(f"  ASS 解析: {len(entries)} 条字幕")
        return entries

    def _ass_time_to_sec(self, time_str: str) -> float:
        """ASS 时间格式 H:MM:SS.CC → 秒"""
        m = re.match(r'(\d+):(\d{2}):(\d{2})\.(\d{2})', time_str)
        if m:
            h, mi, s, cs = [int(x) for x in m.groups()]
            return h * 3600 + mi * 60 + s + cs / 100.0
        return 0.0


# ================================================================
#  2. Whisper 自动转录
# ================================================================
class WhisperTranscriber:
    """Whisper 自动语音转录"""

    def transcribe(self, audio_or_video_path: str) -> list[dict[str, Any]]:
        """使用 Whisper 转录音频/视频"""
        # 尝试导入 whisper
        try:
            import whisper
            log("  Whisper 可用, 开始转录...")
        except ImportError:
            log("  Whisper 不可用, 尝试 faster-whisper", "WARN")
            try:
                from faster_whisper import WhisperModel
                return self._transcribe_faster(audio_or_video_path)
            except ImportError:
                log("  所有 Whisper 实现不可用", "ERROR")
                return []

        model = whisper.load_model("base")
        result = model.transcribe(audio_or_video_path, language="zh")

        entries = []
        for seg in result.get("segments", []):
            entries.append({
                "start": round(seg["start"], 3),
                "end": round(seg["end"], 3),
                "duration": round(seg["end"] - seg["start"], 3),
                "text": seg["text"].strip(),
            })

        log(f"  Whisper 转录: {len(entries)} 段")
        return entries

    def _transcribe_faster(self, path: str) -> list[dict[str, Any]]:
        """使用 faster-whisper"""
        from faster_whisper import WhisperModel
        model = WhisperModel("base", compute_type="int8")
        segments, info = model.transcribe(path, language="zh")

        entries = []
        for seg in segments:
            entries.append({
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "duration": round(seg.end - seg.start, 3),
                "text": seg.text.strip(),
            })

        log(f"  faster-whisper 转录: {len(entries)} 段")
        return entries


# ================================================================
#  3. 字幕 JSX 生成器
# ================================================================
class SubtitleJSXGenerator:
    """将字幕数据转为 AE JSX"""

    # 字幕样式预设
    STYLE_PRESETS = {
        "standard": {
            "font_size": 36,
            "font_family": "Source Han Sans CN",
            "fill_color": [1, 1, 1],
            "stroke_color": [0, 0, 0],
            "stroke_width": 2,
            "position": "bottom",  # bottom/center/top
            "bg_opacity": 60,
            "animation": "fade_in",
        },
        "cinematic": {
            "font_size": 42,
            "font_family": "Source Han Sans CN",
            "fill_color": [1, 0.95, 0.85],
            "stroke_color": [0, 0, 0],
            "stroke_width": 0,
            "position": "bottom",
            "bg_opacity": 0,
            "animation": "fade_in",
            "letter_spacing": 5,
        },
        "karaoke": {
            "font_size": 48,
            "font_family": "Source Han Sans CN",
            "fill_color": [1, 1, 1],
            "stroke_color": [0.2, 0.5, 1],
            "stroke_width": 3,
            "position": "bottom",
            "bg_opacity": 40,
            "animation": "karaoke",
        },
        "typewriter": {
            "font_size": 32,
            "font_family": "Source Han Sans CN",
            "fill_color": [0.9, 0.9, 0.9],
            "stroke_color": [0, 0, 0],
            "stroke_width": 1,
            "position": "center",
            "bg_opacity": 0,
            "animation": "typewriter",
        },
        "title": {
            "font_size": 72,
            "font_family": "Source Han Sans CN",
            "fill_color": [1, 1, 1],
            "stroke_color": [0.8, 0.2, 0.2],
            "stroke_width": 3,
            "position": "center",
            "bg_opacity": 0,
            "animation": "scale_in",
        },
    }

    def generate(self, subtitles: list[dict], style: str = "standard",
                 comp_width: int = 1920, comp_height: int = 1080) -> str:
        """生成字幕 JSX"""
        preset = self.STYLE_PRESETS.get(style, self.STYLE_PRESETS["standard"])
        lines = []

        lines.append(f"// === Subtitles ({len(subtitles)} entries, style={style}) ===")
        lines.append("")

        for i, sub in enumerate(subtitles):
            text = sub["text"].replace("'", "\\'")
            start = sub["start"]
            end = sub["end"]
            dur = sub.get("duration", end - start)

            # 位置计算
            pos = self._calc_position(preset["position"], comp_width, comp_height, i)

            # 创建文字层
            lines.append(f"// Sub {i+1}: [{start:.1f}s - {end:.1f}s] {sub['text'][:20]}")
            lines.append(f"var sub_{i} = comp.layers.addText('{text}');")
            lines.append(f"sub_{i}.name = 'Sub_{i+1}';")

            # 文字样式
            lines.append(f"var tdp_{i} = sub_{i}.property('ADBE Text Properties').property('ADBE Text Document');")
            lines.append(f"var td_{i} = tdp_{i}.value;")
            lines.append(f"td_{i}.fontSize = {preset['font_size']};")
            lines.append(f"td_{i}.fillColor = [{', '.join(str(c) for c in preset['fill_color'])}];")
            lines.append(f"td_{i}.justification = ParagraphJustification.CENTER_JUSTIFY;")
            if preset.get("font_family"):
                lines.append(f"try {{ td_{i}.font = '{preset['font_family']}'; }} catch(e) {{}}")
            lines.append(f"tdp_{i}.setValue(td_{i});")

            # 位置
            lines.append(f"sub_{i}.property('ADBE Transform Group').property('ADBE Position').setValue([{pos[0]}, {pos[1]}, 0]);")

            # 描边 (通过 Layer Style)
            if preset["stroke_width"] > 0:
                sc = preset["stroke_color"]
                lines.append("try {")
                lines.append(f"  sub_{i}.property('ADBE Text Properties').property('ADBE Text Document').setValue(td_{i});")
                lines.append("} catch(e) {}")

            # 动画
            animation = preset.get("animation", "fade_in")
            self._add_animation(lines, i, start, end, dur, animation)

            lines.append("")

        return "\n".join(lines)

    def _calc_position(self, position: str, w: int, h: int, idx: int) -> tuple[int, int]:
        """计算字幕位置"""
        if position == "bottom":
            return (w // 2, h - 80)
        elif position == "center":
            return (w // 2, h // 2)
        elif position == "top":
            return (w // 2, 80)
        return (w // 2, h - 80)

    def _add_animation(self, lines: list[str], idx: int,
                       start: float, end: float, dur: float,
                       animation: str):
        """添加字幕动画"""
        op = f"sub_{idx}.property('ADBE Transform Group').property('ADBE Opacity')"
        scale = f"sub_{idx}.property('ADBE Transform Group').property('ADBE Scale')"

        if animation == "fade_in":
            lines.append(f"  {op}.setValueAtTime({start}, 0);")
            lines.append(f"  {op}.setValueAtTime({start + 0.3}, 100);")
            lines.append(f"  {op}.setValueAtTime({end - 0.3}, 100);")
            lines.append(f"  {op}.setValueAtTime({end}, 0);")

        elif animation == "typewriter":
            # 模拟打字机: 逐字显示通过 source text 关键帧
            lines.append(f"  {op}.setValueAtTime({start}, 100);")
            lines.append(f"  {op}.setValueAtTime({end - 0.2}, 100);")
            lines.append(f"  {op}.setValueAtTime({end}, 0);")

        elif animation == "scale_in":
            lines.append(f"  {op}.setValueAtTime({start}, 0);")
            lines.append(f"  {op}.setValueAtTime({start + 0.4}, 100);")
            lines.append(f"  {scale}.setValueAtTime({start}, [50, 50]);")
            lines.append(f"  {scale}.setValueAtTime({start + 0.4}, [100, 100]);")
            lines.append(f"  {op}.setValueAtTime({end - 0.3}, 100);")
            lines.append(f"  {op}.setValueAtTime({end}, 0);")
            lines.append(f"  {scale}.setValueAtTime({end}, [80, 80]);")

        elif animation == "karaoke":
            # 卡拉OK: 整行淡入 + 颜色变化
            lines.append(f"  {op}.setValueAtTime({start}, 0);")
            lines.append(f"  {op}.setValueAtTime({start + 0.2}, 100);")
            lines.append(f"  {op}.setValueAtTime({end - 0.2}, 100);")
            lines.append(f"  {op}.setValueAtTime({end}, 0);")

        else:
            # 默认淡入淡出
            lines.append(f"  {op}.setValueAtTime({start}, 0);")
            lines.append(f"  {op}.setValueAtTime({start + 0.3}, 100);")
            lines.append(f"  {op}.setValueAtTime({end - 0.3}, 100);")
            lines.append(f"  {op}.setValueAtTime({end}, 0);")


# ================================================================
#  4. 主编排器: SubtitleBurner
# ================================================================
class SubtitleBurner:
    """字幕烧录引擎"""

    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir) if output_dir else Path(
            r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_director")
        self.parser = SubtitleParser()
        self.transcriber = WhisperTranscriber()
        self.jsx_gen = SubtitleJSXGenerator()

    def from_srt(self, srt_path: str, style: str = "standard",
                 comp_width: int = 1920, comp_height: int = 1080) -> str:
        """从 SRT 文件生成字幕 JSX"""
        subtitles = self.parser.parse_srt(srt_path)
        return self.jsx_gen.generate(subtitles, style, comp_width, comp_height)

    def from_ass(self, ass_path: str, style: str = "standard",
                 comp_width: int = 1920, comp_height: int = 1080) -> str:
        """从 ASS 文件生成字幕 JSX"""
        subtitles = self.parser.parse_ass(ass_path)
        return self.jsx_gen.generate(subtitles, style, comp_width, comp_height)

    def from_audio(self, audio_or_video_path: str, style: str = "standard",
                   comp_width: int = 1920, comp_height: int = 1080) -> str:
        """从音频自动转录并生成字幕 JSX"""
        subtitles = self.transcriber.transcribe(audio_or_video_path)
        if not subtitles:
            log("  转录失败, 返回空 JSX", "WARN")
            return "// No subtitles transcribed"
        return self.jsx_gen.generate(subtitles, style, comp_width, comp_height)

    def from_text(self, entries: list[dict], style: str = "standard",
                  comp_width: int = 1920, comp_height: int = 1080) -> str:
        """从手动字幕列表生成 JSX"""
        return self.jsx_gen.generate(entries, style, comp_width, comp_height)

    def burn(self, source: str, source_type: str = "auto",
             style: str = "standard",
             comp_width: int = 1920, comp_height: int = 1080) -> dict[str, Any]:
        """
        完整字幕烧录流程。

        Args:
            source: 字幕源 (文件路径/音频路径)
            source_type: srt/ass/audio/auto
            style: 字幕样式
        """
        start_time = time.time()
        print("\n--- Subtitle Burner ---")

        # 自动检测类型
        if source_type == "auto":
            if source.endswith(".srt"):
                source_type = "srt"
            elif source.endswith(".ass") or source.endswith(".ssa"):
                source_type = "ass"
            else:
                source_type = "audio"

        # 生成 JSX
        if source_type == "srt":
            jsx = self.from_srt(source, style, comp_width, comp_height)
        elif source_type == "ass":
            jsx = self.from_ass(source, style, comp_width, comp_height)
        elif source_type == "audio":
            jsx = self.from_audio(source, style, comp_width, comp_height)
        else:
            jsx = "// Unknown source type"

        # 保存
        jsx_path = self.output_dir / "subtitles.jsx"
        with open(jsx_path, "w", encoding="utf-8") as f:
            f.write(jsx)

        elapsed = time.time() - start_time
        log(f"  字幕 JSX: {len(jsx.splitlines())} 行, 耗时 {elapsed:.1f}s")

        return {
            "source": source,
            "source_type": source_type,
            "style": style,
            "jsx_lines": len(jsx.splitlines()),
            "jsx_path": str(jsx_path),
            "elapsed": round(elapsed, 1),
        }


# ================================================================
#  主入口
# ================================================================
if __name__ == "__main__":
    burner = SubtitleBurner()

    # 测试: 手动字幕
    test_subs = [
        {"start": 0.0, "end": 3.0, "text": "冰海战记"},
        {"start": 3.5, "end": 7.0, "text": "命运的开始"},
        {"start": 7.5, "end": 11.0, "text": "战斗的意志觉醒"},
        {"start": 11.5, "end": 16.0, "text": "血与火的洗礼"},
        {"start": 16.5, "end": 20.0, "text": "寂静的时刻"},
        {"start": 20.5, "end": 25.0, "text": "不屈之魂"},
        {"start": 25.5, "end": 30.0, "text": "破晓之光"},
    ]

    for style in ["standard", "cinematic", "karaoke", "typewriter", "title"]:
        jsx = burner.from_text(test_subs, style=style)
        print(f"\n[{style}] {len(jsx.splitlines())} lines")

    # 保存 cinematic 样式
    jsx = burner.from_text(test_subs, style="cinematic")
    out_path = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_director\subtitles.jsx")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(jsx)
    print(f"\n已保存: {out_path}")
