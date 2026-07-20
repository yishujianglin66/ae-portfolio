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