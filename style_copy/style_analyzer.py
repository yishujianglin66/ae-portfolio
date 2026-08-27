#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
style_copy/style_analyzer.py
风格分析引擎 - 使用DeepSeek V4多模态分析视频风格

输入:
  - 视频路径 / 关键帧图像序列 / 提示词文本

输出:
  - 结构化风格描述JSON（色彩、节奏、转场、特效、字幕等）

复用项目:
  - ai_agent.py 的 V4 API 客户端
"""

import os
import json
import base64
from typing import Dict, List, Optional

try:
    from ai_agent import V4Agent
    V4_AVAILABLE = True
except ImportError:
    V4_AVAILABLE = False


STYLE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "color_palette": {"type": "string"},
        "color_temperature": {"type": "string", "enum": ["warm", "cool", "neutral"]},
        "contrast": {"type": "string", "enum": ["low", "medium", "high"]},
        "pace": {"type": "string", "enum": ["slow", "medium", "fast", "very_fast"]},
        "avg_shot_duration": {"type": "number"},
        "bpm": {"type": "number"},
        "transitions": {"type": "array", "items": {"type": "string"}},
        "effects": {"type": "array", "items": {"type": "string"}},
        "camera_movements": {"type": "array", "items": {"type": "string"}},
        "text_style": {
            "type": "object",
            "properties": {
                "font": {"type": "string"},
                "color": {"type": "string"},
                "position": {"type": "string"},
                "animation": {"type": "string"}
            }
        },
        "audio_mood": {"type": "string"},
        "mood_keywords": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["color_palette", "pace"]
}


class StyleAnalyzer:
    """视频风格分析器"""
    
    def __init__(self, api_key: Optional[str] = None):
        if not V4_AVAILABLE:
            raise ImportError("ai_agent模块不可用")
        self.agent = V4Agent(api_key=api_key)
    
    def analyze_from_video(self, video_path: str, keyframe_paths: List[str]) -> Dict:
        """从视频分析风格"""
        if not keyframe_paths:
            return self._analyze_without_frames(video_path)
        
        # 采样关键帧（最多10帧）
        sample_frames = keyframe_paths[:10]
        
        # 构建分析提示词
        prompt = self._build_video_analysis_prompt(sample_frames)
        
        try:
            result = self.agent.ask(prompt, model="pro", max_tokens=8192)
            return self._parse_result(result)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def analyze_from_prompt(self, prompt: str) -> Dict:
        """从提示词生成风格描述"""
        system_prompt = f"""你是视频风格专家。请根据以下描述生成结构化风格JSON。

用户描述: {prompt}

请输出符合以下Schema的JSON:
{json.dumps(STYLE_JSON_SCHEMA, indent=2, ensure_ascii=False)}

输出要求:
1. 仅输出JSON，不要其他文字
2. 使用中文描述
3. 确保所有字段都有合理值
4. transitions、effects、camera_movements数组至少包含2个元素
"""
        
        try:
            result = self.agent.ask(system_prompt, model="pro")
            return self._parse_result(result)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _analyze_without_frames(self, video_path: str) -> Dict:
        """没有关键帧时的简化分析"""
        prompt = f"""请分析视频风格，输出结构化JSON。

视频路径: {video_path}

请基于一般视频分析经验，推断该视频可能的风格特征。

输出JSON格式（仅JSON）:
{json.dumps(STYLE_JSON_SCHEMA, indent=2, ensure_ascii=False)}
"""
        
        try:
            result = self.agent.ask(prompt, model="pro")
            return self._parse_result(result)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _build_video_analysis_prompt(self, frame_paths: List[str]) -> str:
        """构建视频分析提示词"""
        prompt = """你是专业视频风格分析师。请分析以下视频帧，提取视觉风格特征。

分析要求:
1. 色彩分析: 主色调、色板、对比度、色温
2. 节奏分析: 镜头切换频率、BPM推断
3. 转场分析: 识别转场类型（硬切、溶解、缩放、晃动等）
4. 特效分析: 识别视觉特效（光晕、胶片颗粒、模糊、调色等）
5. 运镜分析: 摄像机运动类型（推、拉、摇、手持等）
6. 字幕风格: 字体、颜色、位置、动画类型
7. 音频情绪: BGM风格、整体情绪

请输出符合以下Schema的JSON（仅JSON）:
"""
        
        prompt += json.dumps(STYLE_JSON_SCHEMA, indent=2, ensure_ascii=False)
        
        return prompt
    
    def _parse_result(self, result: str) -> Dict:
        """解析V4返回结果"""
        try:
            json_start = result.find("{")
            json_end = result.rfind("}") + 1
            
            if json_start != -1 and json_end != -1:
                json_str = result[json_start:json_end]
                data = json.loads(json_str)
                return {"success": True, "style": data}
            else:
                return {"success": False, "error": "无法提取JSON", "raw": result}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"JSON解析失败: {e}", "raw": result}


class LocalStyleAnalyzer:
    """离线风格分析器（不依赖外部 V4 API）

    通过关键词启发式将提示词 / 本地视频特征映射为符合 STYLE_JSON_SCHEMA 的结构化风格。
    作为 V4 不可用时的降级分析器，保证风格复制管线可离线端到端运行。
    """

    # 关键词 -> 风格字段映射
    _COLOR_TEMP = {
        "warm": ["暖", "暖色", "夕阳", "橙", "金黄", "warm", "橙色"],
        "cool": ["冷", "冷色", "蓝", "科技", "cool", "青", "蓝调"],
    }
    _CONTRAST = {
        "high": ["高对比", "强烈", "硬", "high", "强烈对比"],
        "low": ["柔和", "低对比", "柔", "low"],
    }
    _PACE = {
        "very_fast": ["极快", "极速", "very_fast"],
        "fast": ["快", "快节奏", "动感", "卡点", "快剪", "fast", "节奏快"],
        "slow": ["慢", "慢节奏", "舒缓", "慢镜", "slow", "节奏慢"],
    }
    _EFFECTS = {
        "glow": ["光晕", "发光", "glow"],
        "film_grain": ["胶片", "颗粒", "胶片感", "film", "grain"],
        "vintage": ["复古", "怀旧", "vintage", "老"],
        "cinematic": ["电影感", "电影", "cinematic", "影院"],
        "dreamy": ["梦幻", "dreamy", "朦胧"],
        "dramatic": ["戏剧", "强烈", "dramatic"],
        "lens_flare": ["镜头光晕", "光斑", "lens", "flare"],
    }
    _TRANSITIONS = {
        "dissolve": ["溶解", "淡入淡出", "渐变", "dissolve"],
        "fade": ["淡入", "淡出", "fade"],
        "zoom": ["缩放", "推近", "zoom"],
        "whip_pan": ["甩镜", "横移", "快速移动", "whip"],
        "slide": ["滑动", "slide"],
    }

    def analyze_from_prompt(self, prompt: str) -> Dict:
        """从提示词生成风格描述（离线）"""
        text = (prompt or "").lower()

        color_temperature = self._match_first(text, self._COLOR_TEMP, "neutral")
        contrast = self._match_first(text, self._CONTRAST, "medium")
        pace = self._match_first(text, self._PACE, "medium")

        effects = self._match_all(text, self._EFFECTS)
        if not effects:
            effects = ["cinematic"]

        transitions = self._match_all(text, self._TRANSITIONS)
        if not transitions:
            transitions = ["hard_cut", "dissolve"]

        text_style = {"font": "粗体无衬线", "color": "#FFFFFF",
                      "position": "底部居中", "animation": "typewriter"}
        if any(k in text for k in ["字幕", "标题", "text", "caption"]):
            text_style["animation"] = "typewriter"
        else:
            text_style["animation"] = "none"

        if color_temperature == "warm":
            color_palette = "暖色调，橙黄为主"
        elif color_temperature == "cool":
            color_palette = "冷色调，青蓝为主"
        else:
            color_palette = "中性色调，平衡对比"

        mood_keywords = [color_temperature, pace, "cinematic"]
        audio_mood = "energetic" if pace in ("fast", "very_fast") else "calm"

        style = {
            "color_palette": color_palette,
            "color_temperature": color_temperature,
            "contrast": contrast,
            "pace": pace,
            "avg_shot_duration": 1.5 if pace in ("fast", "very_fast") else 3.0,
            "bpm": 128 if pace in ("fast", "very_fast") else 90,
            "transitions": transitions,
            "effects": effects,
            "camera_movements": ["push_in"] if "推" in text or "push" in text else ["static"],
            "text_style": text_style,
            "audio_mood": audio_mood,
            "mood_keywords": mood_keywords,
        }
        return {"success": True, "style": style, "source": "local_heuristic"}

    def analyze_from_video(self, video_path: str, keyframe_paths: List[str] = None) -> Dict:
        """从本地视频生成风格描述（离线，基于 ffprobe 特征启发式）"""
        features = self._probe_video(video_path)
        fps = features.get("fps", 0)
        pace = "fast" if fps >= 30 else "medium"
        style = {
            "color_palette": "中性色调（基于源视频）",
            "color_temperature": "neutral",
            "contrast": "medium",
            "pace": pace,
            "avg_shot_duration": round(1.0 / fps, 2) if fps else 2.0,
            "bpm": 120 if pace == "fast" else 90,
            "transitions": ["hard_cut"],
            "effects": ["cinematic"],
            "camera_movements": ["static"],
            "text_style": {"font": "粗体无衬线", "color": "#FFFFFF",
                           "position": "底部居中", "animation": "none"},
            "audio_mood": "calm",
            "mood_keywords": ["source-based", pace],
            "_probe": features,
        }
        return {"success": True, "style": style, "source": "local_probe"}

    @staticmethod
    def _probe_video(path: str) -> Dict:
        """用 ffprobe 探测视频基础特征（失败则返回空）"""
        try:
            import shutil, subprocess, json as _json
            ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
            if not ffprobe or not path:
                return {}
            out = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height,r_frame_rate",
                 "-of", "json", path],
                capture_output=True, text=True, timeout=30,
            )
            data = _json.loads(out.stdout or "{}")
            st = (data.get("streams") or [{}])[0]
            fr = st.get("r_frame_rate", "0/1")
            num, den = (fr.split("/") + ["1", "1"])[:2]
            fps = float(num) / float(den) if float(den) else 0
            return {"width": st.get("width"), "height": st.get("height"), "fps": round(fps, 2)}
        except Exception:
            return {}

    @staticmethod
    def _match_first(text: str, mapping: Dict[str, List[str]], default: str) -> str:
        for key, kws in mapping.items():
            if any(kw in text for kw in kws):
                return key
        return default

    @staticmethod
    def _match_all(text: str, mapping: Dict[str, List[str]]) -> List[str]:
        return [key for key, kws in mapping.items() if any(kw in text for kw in kws)]


def get_analyzer(api_key: Optional[str] = None):
    """分析器工厂：优先 V4，不可用则降级到本地离线分析器"""
    if V4_AVAILABLE:
        try:
            return StyleAnalyzer(api_key=api_key)
        except Exception:
            pass
    return LocalStyleAnalyzer()


def main():
    import sys
    
    if not V4_AVAILABLE:
        print("错误: ai_agent模块不可用")
        return
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  py -3.11 style_analyzer.py --video <视频路径>")
        print("  py -3.11 style_analyzer.py --prompt <提示词>")
        return
    
    analyzer = StyleAnalyzer()
    
    if sys.argv[1] == "--video":
        video_path = sys.argv[2]
        frames_dir = os.path.join(os.path.dirname(video_path), "frames")
        keyframe_paths = sorted([os.path.join(frames_dir, f) 
                                for f in os.listdir(frames_dir) 
                                if f.startswith("frame_")]) if os.path.exists(frames_dir) else []
        
        result = analyzer.analyze_from_video(video_path, keyframe_paths)
    
    elif sys.argv[1] == "--prompt":
        prompt = " ".join(sys.argv[2:])
        result = analyzer.analyze_from_prompt(prompt)
    
    else:
        print("未知参数")
        return
    
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()