#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕系统 - 支持 SRT/VTT/ASS 字幕格式的解析、导入和导出
集成 Whisper 语音识别生成字幕，并通过 LLM 网关进行智能优化
"""

import asyncio
import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SubtitleItem:
    """字幕条目"""
    index: int
    start_time: float
    end_time: float
    text: str


@dataclass
class SubtitleStyle:
    """字幕样式"""
    font_family: str = "Arial"
    font_size: int = 48
    font_color: list[float] = None
    stroke_color: list[float] = None
    stroke_width: float = 2.0
    glow_enabled: bool = True
    glow_color: list[float] = None
    glow_radius: float = 15.0
    position_y: float = 0.85
    alignment: str = "center"
    line_spacing: float = 1.5

    def __post_init__(self):
        if self.font_color is None:
            self.font_color = [1.0, 1.0, 1.0]
        if self.stroke_color is None:
            self.stroke_color = [0.0, 0.0, 0.0]
        if self.glow_color is None:
            self.glow_color = [0.0, 0.5, 1.0]


class SubtitleParser:
    """字幕解析器 - 支持 SRT/VTT/ASS 格式"""

    @staticmethod
    def parse_srt(content: str) -> list[SubtitleItem]:
        """解析 SRT 字幕格式"""
        items = []
        blocks = content.strip().split('\n\n')
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.split('\n')
            if len(lines) < 3:
                continue
            try:
                index = int(lines[0].strip())
                time_range = lines[1].strip()
                text = '\n'.join(lines[2:]).strip()
                if '-->' in time_range:
                    start_str, end_str = time_range.split('-->')
                    start_time = SubtitleParser._parse_timecode(start_str.strip())
                    end_time = SubtitleParser._parse_timecode(end_str.strip())
                    items.append(SubtitleItem(index, start_time, end_time, text))
            except (ValueError, IndexError):
                continue
        return items

    @staticmethod
    def parse_vtt(content: str) -> list[SubtitleItem]:
        """解析 WebVTT 字幕格式"""
        items = []
        lines = content.split('\n')
        i = 0
        index = 1
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('WEBVTT') or line.startswith('NOTE') or line.startswith('STYLE'):
                i += 1
                continue
            if '-->' in line:
                time_range = line
                i += 1
                text = ''
                while i < len(lines) and lines[i].strip() != '':
                    text += lines[i].strip() + ' '
                    i += 1
                start_str, end_str = time_range.split('-->')
                start_time = SubtitleParser._parse_timecode(start_str.strip())
                end_time = SubtitleParser._parse_timecode(end_str.strip())
                items.append(SubtitleItem(index, start_time, end_time, text.strip()))
                index += 1
            i += 1
        return items

    @staticmethod
    def parse_ass(content: str) -> list[SubtitleItem]:
        """解析 ASS 字幕格式（简化版）"""
        items = []
        events_start = False
        index = 1
        for line in content.split('\n'):
            line = line.strip()
            if line == '[Events]':
                events_start = True
                continue
            if events_start and line.startswith('Dialogue:'):
                parts = line.split(',')
                if len(parts) >= 10:
                    layer = parts[0].replace('Dialogue:', '').strip()
                    start_time = SubtitleParser._parse_ass_timecode(parts[1].strip())
                    end_time = SubtitleParser._parse_ass_timecode(parts[2].strip())
                    text = ','.join(parts[9:]).strip()
                    text = SubtitleParser._strip_ass_tags(text)
                    items.append(SubtitleItem(index, start_time, end_time, text))
                    index += 1
        return items

    @staticmethod
    def _parse_timecode(timecode: str) -> float:
        """解析时间码为秒"""
        timecode = timecode.replace(',', '.')
        parts = timecode.split(':')
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        return float(timecode)

    @staticmethod
    def _parse_ass_timecode(timecode: str) -> float:
        """解析 ASS 时间码"""
        parts = timecode.split(':')
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        return 0.0

    @staticmethod
    def _strip_ass_tags(text: str) -> str:
        """移除 ASS 格式标签"""
        return re.sub(r'\{[^}]*\}', '', text)

    @staticmethod
    def detect_format(content: str) -> str:
        """自动检测字幕格式"""
        content = content.strip()
        if content.startswith('WEBVTT'):
            return 'vtt'
        if content.startswith('[Script Info]'):
            return 'ass'
        return 'srt'

    @staticmethod
    def parse(content: str, format_type: str = None) -> list[SubtitleItem]:
        """解析字幕内容"""
        if format_type is None:
            format_type = SubtitleParser.detect_format(content)
        parsers = {
            'srt': SubtitleParser.parse_srt,
            'vtt': SubtitleParser.parse_vtt,
            'ass': SubtitleParser.parse_ass,
        }
        return parsers[format_type](content)


class SubtitleGenerator:
    """字幕生成器 - 导出字幕为 SRT/VTT/ASS 格式"""

    @staticmethod
    def to_srt(items: list[SubtitleItem]) -> str:
        """导出为 SRT 格式"""
        lines = []
        for item in items:
            start = SubtitleGenerator._format_timecode(item.start_time)
            end = SubtitleGenerator._format_timecode(item.end_time)
            lines.append(f"{item.index}")
            lines.append(f"{start} --> {end}")
            lines.append(item.text)
            lines.append("")
        return '\n'.join(lines)

    @staticmethod
    def to_vtt(items: list[SubtitleItem]) -> str:
        """导出为 WebVTT 格式"""
        lines = ["WEBVTT", ""]
        for item in items:
            start = SubtitleGenerator._format_timecode(item.start_time)
            end = SubtitleGenerator._format_timecode(item.end_time)
            lines.append(f"{start} --> {end}")
            lines.append(item.text)
            lines.append("")
        return '\n'.join(lines)

    @staticmethod
    def to_ass(items: list[SubtitleItem]) -> str:
        """导出为 ASS 格式"""
        lines = [
            "[Script Info]",
            "Title: Generated Subtitles",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Arial,48,&HFFFFFF,&HFFFFFF,&H000000,&H000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        for item in items:
            start = SubtitleGenerator._format_ass_timecode(item.start_time)
            end = SubtitleGenerator._format_ass_timecode(item.end_time)
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{item.text}")
        return '\n'.join(lines)

    @staticmethod
    def _format_timecode(seconds: float) -> str:
        """格式化时间码为 HH:MM:SS,mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')

    @staticmethod
    def _format_ass_timecode(seconds: float) -> str:
        """格式化时间码为 ASS 格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:01d}:{minutes:02d}:{secs:06.2f}"


class SubtitleSystem:
    """字幕管理系统"""

    def __init__(self, ae_client=None, llm_api_url: str = "", llm_api_key: str = "", model: str = ""):
        self.ae_client = ae_client
        self.llm_api_url = llm_api_url
        self.llm_api_key = llm_api_key
        self.model = model

    async def parse_file(self, file_path: Path | str) -> list[SubtitleItem]:
        """解析字幕文件"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"字幕文件不存在: {file_path}")
        
        content = file_path.read_text(encoding='utf-8')
        ext = file_path.suffix.lower()
        format_type = ext[1:] if ext in ('.srt', '.vtt', '.ass') else None
        return SubtitleParser.parse(content, format_type)

    async def import_subtitle_to_ae(
        self,
        comp_name: str,
        subtitle_items: list[SubtitleItem],
        style: SubtitleStyle | None = None,
        project_path: Path | str | None = None,
    ) -> dict[str, Any]:
        """将字幕导入 AE 合成"""
        if style is None:
            style = SubtitleStyle()

        style_dict = asdict(style)
        subtitles_json = json.dumps([asdict(item) for item in subtitle_items], ensure_ascii=False)
        
        script = f'''
(function() {{
    var subtitles = {subtitles_json};
    var style = {json.dumps(style_dict, ensure_ascii=False)};
    
    try {{
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === "{comp_name}") {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到: {comp_name}"}});
        }}
        
        app.beginUndoGroup("Import Subtitles");
        
        var importedCount = 0;
        var layerNames = [];
        
        for (var j = 0; j < subtitles.length; j++) {{
            var sub = subtitles[j];
            var startTime = sub.start_time;
            var endTime = sub.end_time;
            var text = sub.text;
            
            var textLayer = comp.layers.addText(text);
            textLayer.name = "Subtitle_" + sub.index;
            textLayer.inPoint = startTime;
            textLayer.outPoint = endTime;
            
            var sourceText = textLayer.property("Source Text");
            var textDoc = sourceText.value;
            textDoc.fontSize = style.font_size;
            textDoc.fontFamily = style.font_family;
            textDoc.fillColor = new RGBColor();
            textDoc.fillColor.red = style.font_color[0];
            textDoc.fillColor.green = style.font_color[1];
            textDoc.fillColor.blue = style.font_color[2];
            sourceText.setValue(textDoc);
            
            var position = textLayer.property("Position");
            var posVal = position.value;
            posVal[0] = comp.width * 0.5;
            posVal[1] = comp.height * style.position_y;
            position.setValue(posVal);
            
            textLayer.property("Anchor Point").setValue([comp.width * 0.5, comp.height * 0.1]);
            
            if (style.stroke_width > 0) {{
                var stroke = textLayer.Effects.addProperty("ADBE Stroke");
                stroke.property("ADBE Stroke-0001").setValue(new RGBColor());
                stroke.property("ADBE Stroke-0001").value.red = style.stroke_color[0];
                stroke.property("ADBE Stroke-0001").value.green = style.stroke_color[1];
                stroke.property("ADBE Stroke-0001").value.blue = style.stroke_color[2];
                stroke.property("ADBE Stroke-0002").setValue(style.stroke_width);
            }}
            
            if (style.glow_enabled) {{
                var glow = textLayer.Effects.addProperty("ADBE Glow");
                glow.property("ADBE Glow-0001").setValue(new RGBColor());
                glow.property("ADBE Glow-0001").value.red = style.glow_color[0];
                glow.property("ADBE Glow-0001").value.green = style.glow_color[1];
                glow.property("ADBE Glow-0001").value.blue = style.glow_color[2];
                glow.property("ADBE Glow-0002").setValue(style.glow_radius);
                glow.property("ADBE Glow-0003").setValue(1.0);
            }}
            
            importedCount++;
            layerNames.push(textLayer.name);
        }}
        
        app.endUndoGroup();
        
        return JSON.stringify({{
            success: true,
            importedCount: importedCount,
            layerNames: layerNames,
            totalSubtitles: subtitles.length
        }});
    }} catch (e) {{
        try {{ app.endUndoGroup(); }} catch (err) {{}}
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        if self.ae_client:
            result = await self.ae_client.run_script(script, project_path)
            return result
        return {"success": True, "importedCount": len(subtitle_items), "status": "dry_run"}

    async def import_srt_to_ae(
        self,
        comp_name: str,
        srt_path: Path | str,
        style: SubtitleStyle | None = None,
        project_path: Path | str | None = None,
    ) -> dict[str, Any]:
        """导入 SRT 文件到 AE"""
        items = await self.parse_file(srt_path)
        return await self.import_subtitle_to_ae(comp_name, items, style, project_path)

    async def export_subtitle_from_ae(
        self,
        comp_name: str,
        output_path: Path | str,
        format_type: str = "srt",
        project_path: Path | str | None = None,
    ) -> dict[str, Any]:
        """从 AE 导出字幕"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        script = f'''
(function() {{
    try {{
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var item = app.project.item(i);
            if (item instanceof CompItem && item.name === "{comp_name}") {{
                comp = item;
                break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{error: true, message: "合成未找到: {comp_name}"}});
        }}
        
        var subtitles = [];
        var index = 1;
        
        for (var j = 1; j <= comp.numLayers; j++) {{
            var layer = comp.layer(j);
            if (layer instanceof TextLayer) {{
                var text = "";
                try {{
                    var sourceText = layer.property("Source Text");
                    text = sourceText.value.getText();
                }} catch (e) {{
                    text = layer.name.replace("Subtitle_", "");
                }}
                
                subtitles.push({{
                    index: index,
                    start_time: layer.inPoint,
                    end_time: layer.outPoint,
                    text: text
                }});
                index++;
            }}
        }}
        
        subtitles.sort(function(a, b) {{
            return a.start_time - b.start_time;
        }});
        
        return JSON.stringify({{
            success: true,
            subtitles: subtitles,
            count: subtitles.length
        }});
    }} catch (e) {{
        return JSON.stringify({{error: true, message: e.toString()}});
    }}
}})();
'''
        if self.ae_client:
            result = await self.ae_client.run_script(script, project_path)
            if result.get("success"):
                items = [SubtitleItem(**s) for s in result["subtitles"]]
                if format_type == "srt":
                    content = SubtitleGenerator.to_srt(items)
                elif format_type == "vtt":
                    content = SubtitleGenerator.to_vtt(items)
                elif format_type == "ass":
                    content = SubtitleGenerator.to_ass(items)
                else:
                    content = SubtitleGenerator.to_srt(items)
                output_path.write_text(content, encoding='utf-8')
                result["output_path"] = str(output_path)
            return result
        return {"success": True, "status": "dry_run"}

    async def generate_subtitles_from_audio(
        self,
        audio_path: Path | str,
        language: str = "zh",
        use_llm: bool = True,
    ) -> list[SubtitleItem]:
        """从音频生成字幕（使用 Whisper + LLM 优化）"""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        try:
            import whisper
        except ImportError:
            raise ImportError("需要安装 whisper 库: pip install openai-whisper")

        model = whisper.load_model("base")
        result = model.transcribe(str(audio_path), language=language)
        
        subtitles = []
        index = 1
        for segment in result["segments"]:
            subtitles.append(SubtitleItem(
                index=index,
                start_time=segment["start"],
                end_time=segment["end"],
                text=segment["text"].strip()
            ))
            index += 1

        if use_llm:
            subtitles = await self._optimize_subtitles_with_llm(subtitles, language)

        return subtitles

    async def _optimize_subtitles_with_llm(
        self,
        subtitles: list[SubtitleItem],
        language: str = "zh",
        style: SubtitleStyle | None = None,
    ) -> list[SubtitleItem]:
        """使用 LLM 优化字幕质量"""
        try:
            from core.llm_gateway import LLMGateway
            
            gateway = LLMGateway()
            
            subtitle_texts = "\n".join([f"{s.index}. {s.text}" for s in subtitles])
            
            prompt = f"""请优化以下字幕文本，确保：
1. 标点符号正确
2. 口语化表达转为书面语
3. 修正识别错误的字词
4. 保持原意不变
5. 每行字幕不超过20字

语言：{language}

字幕内容：
{subtitle_texts}

请返回优化后的字幕列表，格式为：
序号. 优化后的文本
"""
            
            response = await gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                task_type="translation"
            )
            
            if response.success and response.content:
                lines = response.content.strip().split('\n')
                for line in lines:
                    match = re.match(r'(\d+)\.\s*(.+)', line)
                    if match:
                        idx = int(match.group(1)) - 1
                        if idx < len(subtitles):
                            subtitles[idx].text = match.group(2).strip()
            
        except Exception as e:
            logger.warning(
                "LLM 字幕优化失败，保留原始字幕 (degraded=True): %s", e
            )

        return subtitles

    def batch_import_subtitles(
        self,
        comp_name: str,
        subtitle_files: list[Path | str],
        style: SubtitleStyle | None = None,
        project_path: Path | str | None = None,
    ):
        """批量导入字幕文件"""
        async def import_one(file_path):
            return await self.import_srt_to_ae(comp_name, file_path, style, project_path)
        
        return asyncio.gather(*[import_one(f) for f in subtitle_files])