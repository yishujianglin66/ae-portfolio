"""
魔搭社区 ModelScope Skills 集成模块
=====================================
提供视频分析、风格识别、文生图等AI能力，与AE自动化管线无缝对接。

功能列表：
- 视频内容分析（镜头类型、节奏、色彩）
- 风格识别与分类
- 文生图/文生视频素材生成
- 音频特征分析

使用示例：
    from integrations.modelscope_skills import ModelScopeSkillsClient

    client = ModelScopeSkillsClient()
    result = client.analyze_video("path/to/video.mp4")
    print(result)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


@dataclass
class VideoAnalysisResult:
    """视频分析结果"""
    video_path: str
    duration: float = 0.0
    scene_count: int = 0
    avg_shot_duration: float = 0.0
    style_tags: List[str] = field(default_factory=list)
    color_palette: List[str] = field(default_factory=list)
    motion_intensity: str = "medium"  # low/medium/high
    scene_types: List[str] = field(default_factory=list)  # closeup/wide/action/dialogue
    raw_response: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_path": self.video_path,
            "duration": self.duration,
            "scene_count": self.scene_count,
            "avg_shot_duration": self.avg_shot_duration,
            "style_tags": self.style_tags,
            "color_palette": self.color_palette,
            "motion_intensity": self.motion_intensity,
            "scene_types": self.scene_types,
        }


@dataclass
class StyleMatchResult:
    """风格匹配结果"""
    input_style: str
    matched_templates: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    suggestions: List[str] = field(default_factory=list)


class ModelScopeSkillsClient:
    """
    魔搭社区Skills客户端
    
    通过ModelScope OpenAPI调用视频分析、风格识别等AI技能。
    """

    BASE_URL = "https://modelscope.cn/openapi/v1"
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get("MODELSCOPE_API_KEY", "")
        self.base_url = (base_url or os.environ.get("MODELSCOPE_BASE_URL", self.BASE_URL)).rstrip("/")
        
        if not self.api_key:
            raise ValueError(
                "未找到MODELSCOPE_API_KEY。请在.env文件中设置，或作为参数传入。"
            )
        
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送API请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, timeout=60, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "status": getattr(e.response, 'status_code', 0)}
    
    def analyze_video(
        self, 
        video_path: str, 
        analysis_type: str = "comprehensive"
    ) -> VideoAnalysisResult:
        """
        分析视频内容
        
        Args:
            video_path: 视频文件路径或URL
            analysis_type: 分析类型 (comprehensive/scene/style/motion)
        
        Returns:
            VideoAnalysisResult 分析结果
        """
        path = Path(video_path)
        
        # 如果是本地文件，先检查是否存在
        if not video_path.startswith(("http://", "https://")):
            if not path.exists():
                return VideoAnalysisResult(
                    video_path=video_path,
                    raw_response={"error": f"文件不存在: {video_path}"}
                )
        
        # 调用魔搭视频分析API
        # 注意：实际API端点需要根据魔搭官方文档调整
        endpoint = "/skills/video-analysis"
        
        payload = {
            "input": {
                "video": video_path,
                "analysis_type": analysis_type,
            },
            "parameters": {
                "return_scene_info": True,
                "return_style_tags": True,
                "return_color_palette": True,
                "return_motion_analysis": True,
            }
        }
        
        result = self._request("POST", endpoint, json=payload)
        
        if "error" in result:
            return VideoAnalysisResult(
                video_path=video_path,
                raw_response=result
            )
        
        # 解析响应
        data = result.get("data", result.get("output", {}))
        
        return VideoAnalysisResult(
            video_path=video_path,
            duration=data.get("duration", 0.0),
            scene_count=data.get("scene_count", 0),
            avg_shot_duration=data.get("avg_shot_duration", 0.0),
            style_tags=data.get("style_tags", []),
            color_palette=data.get("color_palette", []),
            motion_intensity=data.get("motion_intensity", "medium"),
            scene_types=data.get("scene_types", []),
            raw_response=result,
        )
    
    def recognize_style(
        self, 
        image_path: str, 
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        识别图片/视频帧的风格
        
        Args:
            image_path: 图片路径或URL
            top_k: 返回最匹配的top_k个风格
        
        Returns:
            风格识别结果
        """
        endpoint = "/skills/style-recognition"
        
        payload = {
            "input": {
                "image": image_path,
            },
            "parameters": {
                "top_k": top_k,
                "return_confidence": True,
            }
        }
        
        return self._request("POST", endpoint, json=payload)
    
    def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        size: str = "1024x1024",
        style: str = "auto",
    ) -> Dict[str, Any]:
        """
        文生图
        
        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词
            size: 图片尺寸
            style: 风格预设
        
        Returns:
            生成结果（包含图片URL）
        """
        endpoint = "/skills/text-to-image"
        
        payload = {
            "input": {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
            },
            "parameters": {
                "size": size,
                "style": style,
                "num_images": 1,
            }
        }
        
        return self._request("POST", endpoint, json=payload)
    
    def analyze_audio(
        self,
        audio_path: str,
    ) -> Dict[str, Any]:
        """
        音频分析（BGM识别、节奏检测）
        
        Args:
            audio_path: 音频文件路径或URL
        
        Returns:
            音频分析结果
        """
        endpoint = "/skills/audio-analysis"
        
        payload = {
            "input": {
                "audio": audio_path,
            },
            "parameters": {
                "detect_rhythm": True,
                "detect_genre": True,
                "detect_mood": True,
            }
        }
        
        return self._request("POST", endpoint, json=payload)
    
    def batch_analyze_videos(
        self,
        video_paths: List[str],
        output_dir: Optional[str] = None,
    ) -> List[VideoAnalysisResult]:
        """
        批量分析视频
        
        Args:
            video_paths: 视频路径列表
            output_dir: 结果输出目录（可选）
        
        Returns:
            分析结果列表
        """
        results = []
        
        for i, path in enumerate(video_paths):
            print(f"[{i+1}/{len(video_paths)}] 分析中: {path}")
            result = self.analyze_video(path)
            results.append(result)
            
            # 避免请求过快
            if i < len(video_paths) - 1:
                time.sleep(1)
        
        # 保存结果
        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            
            for result in results:
                safe_name = Path(result.video_path).stem
                result_file = out_path / f"{safe_name}_analysis.json"
                with open(result_file, "w", encoding="utf-8") as f:
                    json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
                print(f"  结果已保存: {result_file}")
        
        return results
    
    def match_style_to_templates(
        self,
        style_tags: List[str],
        template_db_path: Optional[str] = None,
    ) -> StyleMatchResult:
        """
        根据风格标签匹配AE特效模板
        
        Args:
            style_tags: 风格标签列表
            template_db_path: 模板数据库路径
        
        Returns:
            匹配结果
        """
        # 这里可以对接你的风格化剪辑知识库
        # 暂时返回模拟结果，实际使用时需要接入知识库
        
        return StyleMatchResult(
            input_style=", ".join(style_tags),
            matched_templates=[],
            confidence=0.0,
            suggestions=[
                f"找到 {len(style_tags)} 个风格标签",
                "建议接入风格化剪辑知识库进行精确匹配"
            ]
        )


# 便捷函数
def create_client(api_key: Optional[str] = None) -> ModelScopeSkillsClient:
    """创建魔搭Skills客户端"""
    return ModelScopeSkillsClient(api_key=api_key)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("魔搭社区 ModelScope Skills 集成测试")
    print("=" * 60)
    
    try:
        client = create_client()
        print(f"✓ 客户端创建成功")
        print(f"  API Base URL: {client.base_url}")
        
        # 测试视频分析（需要实际视频文件）
        test_video = "test_video.mp4"
        print(f"\n测试视频分析: {test_video}")
        result = client.analyze_video(test_video)
        print(f"  结果: {result.to_dict()}")
        
    except ValueError as e:
        print(f"✗ 错误: {e}")
        print("  请确保已设置 MODELSCOPE_API_KEY 环境变量")
    except Exception as e:
        print(f"✗ 未知错误: {e}")
