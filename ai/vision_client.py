#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉模型客户端 - Vision Client
=============================

支持硅基流动(SiliconFlow)多模态视觉模型。

核心功能：
1. 视觉理解（VLM）：图像描述、关键帧分析、效果识别
2. 图像生成：图生图、文生图
3. 多模型智能路由

可用模型：
- 视觉理解: Qwen/Qwen2.5-VL-7B-Instruct (免费)
- 视觉理解: Qwen/Qwen2.5-VL-72B-Instruct (专业)
- 图像生成: Kwai-Kolors/Kolors (免费)

配置方式：
    环境变量: SILICONFLOW_API_KEY
    或直接传入 api_key 参数

使用方式：
    from vision_client import VisionClient
    
    client = VisionClient()
    
    # 图像理解
    result = client.analyze_image("图片路径或URL", "描述一下这张图")
    
    # 生成图像
    result = client.generate_image("一个美丽的风景")
    
    # AE效果识别
    result = client.analyze_ae_effect("关键帧图片路径")

注意（DeprecationWarning）：
    自 2026-08 起，所有 LLM 调用应统一走 core/llm_gateway 网关（自动适配/路由/
    降级/成本追踪）。本客户端仅作为网关内部实现细节或历史脚本兼容保留，
    新代码请勿直接 import，请改用 core.llm_gateway.llm_gateway.chat()。
"""

import os
import sys
import base64
from enum import Enum
from typing import Optional, Dict, Any, List, Union
from pathlib import Path

try:
    import requests
except ImportError:
    # 不在导入期 sys.exit(1)：否则 import 本模块的上层（ai_agent / 测试套件）
    # 会在收集阶段直接崩溃。改为标记不可用，仅在实际发起请求时再报错。
    requests = None  # type: ignore[assignment]
    REQUESTS_AVAILABLE = False
    print(
        "[vision_client] 警告: 未安装 requests，网络相关功能将不可用；"
        "请运行 `py -3.11 -m pip install requests`"
    )
else:
    REQUESTS_AVAILABLE = True


class VisionModel(Enum):
    """视觉模型枚举"""
    QWEN25_VL_7B = "Qwen/Qwen2.5-VL-7B-Instruct"
    QWEN25_VL_72B = "Qwen/Qwen2.5-VL-72B-Instruct"
    KOLORS = "Kwai-Kolors/Kolors"


class VisionTask(Enum):
    """视觉任务类型"""
    IMAGE_DESCRIPTION = "image_description"
    AE_EFFECT_ANALYSIS = "ae_effect_analysis"
    KEYFRAME_ANALYSIS = "keyframe_analysis"
    SCENE_DETECTION = "scene_detection"
    COLOR_ANALYSIS = "color_analysis"
    IMAGE_GENERATION = "image_generation"


class VisionClient:
    """视觉模型客户端（硅基流动）"""
    
    BASE_URL = "https://api.siliconflow.cn/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SILICONFLOW_API_KEY", "")
        if not self.api_key:
            print("警告: 未设置 SILICONFLOW_API_KEY，视觉功能不可用")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    def _encode_image(self, image_path: str) -> str:
        """将本地图片编码为base64"""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"图片不存在: {image_path}")
        
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    def _build_image_content(self, image_input: str) -> Dict[str, Any]:
        """构建图像内容（支持URL和本地路径）"""
        if image_input.startswith("http://") or image_input.startswith("https://"):
            return {"type": "image_url", "image_url": {"url": image_input}}
        else:
            b64 = self._encode_image(image_input)
            return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
    
    def analyze_image(self, 
                     image: str, 
                     prompt: str = "请详细描述这张图片的内容",
                     model: str = VisionModel.QWEN25_VL_7B.value) -> str:
        """分析图片内容
        
        Args:
            image: 图片路径或URL
            prompt: 分析提示词
            model: 使用的模型
        
        Returns:
            分析结果文本

        注意：多模态视觉分析为临时直连硅基流动 Provider API，待统一网关扩展多模态后迁移。
        """
        if not self.is_available():
            raise RuntimeError("视觉模型未配置，请设置 SILICONFLOW_API_KEY")
        
        image_content = self._build_image_content(image)
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        image_content,
                        {"type": "text", "text": prompt}
                    ]
                }
            ],
            "max_tokens": 2048,
            "temperature": 0.7
        }
        
        response = requests.post(
            f"{self.BASE_URL}/chat/completions",
            headers=self.headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        
        if "choices" in result and result["choices"]:
            return result["choices"][0]["message"]["content"]
        return f"API异常: {result}"
    
    def analyze_ae_effect(self, image: str) -> str:
        """分析AE特效关键帧
        
        用于识别关键帧中的AE效果类型、参数等。
        """
        prompt = """请仔细分析这张AE合成的关键帧截图，回答以下问题：

1. 画面中可以看到哪些视觉效果？（如：辉光、模糊、粒子、调色、3D等）
2. 文字的样式是什么？（字体、大小、颜色、动画效果）
3. 整体色彩风格是什么？
4. 可能使用了哪些AE内置效果或插件？
5. 画面的构图和层次感如何？

请用中文回答，结构化输出。"""
        
        return self.analyze_image(image, prompt, model=VisionModel.QWEN25_VL_72B.value)
    
    def analyze_keyframe(self, image: str) -> str:
        """分析关键帧的视觉元素
        
        用于音画匹配、剪辑分析等场景。
        """
        prompt = """请分析这张关键帧图片，提取以下信息：

1. 主要视觉元素（人物、物体、文字、背景）
2. 画面情绪氛围（明亮/暗淡、欢快/压抑、动感/静态）
3. 色彩主色调
4. 运动感强弱
5. 视觉焦点位置

用中文简洁回答。"""
        
        return self.analyze_image(image, prompt)
    
    def generate_image(self, 
                      prompt: str,
                      size: str = "1024x1024",
                      model: str = VisionModel.KOLORS.value) -> Dict[str, Any]:
        """生成图片
        
        Args:
            prompt: 图像描述
            size: 尺寸 (如 1024x1024)
            model: 使用的模型
        
        Returns:
            { "url": "...", "seed": ... }

        注意：图像生成为临时直连硅基流动 Provider API，待统一网关扩展图像生成后迁移。
        """
        if not self.is_available():
            raise RuntimeError("视觉模型未配置，请设置 SILICONFLOW_API_KEY")
        
        payload = {
            "model": model,
            "prompt": prompt,
            "image_size": size,
            "batch_size": 1,
            "num_inference_steps": 20,
            "guidance_scale": 7.5
        }
        
        response = requests.post(
            f"{self.BASE_URL}/images/generations",
            headers=self.headers,
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        result = response.json()
        
        if "images" in result and result["images"]:
            return {
                "url": result["images"][0]["url"],
                "seed": result.get("seed"),
                "raw": result
            }
        raise RuntimeError(f"图像生成失败: {result}")
    
    def batch_analyze(self, images: List[str], prompt: str) -> List[str]:
        """批量分析多张图片"""
        results = []
        for img in images:
            try:
                result = self.analyze_image(img, prompt)
                results.append(result)
            except Exception as e:
                results.append(f"分析失败: {e}")
        return results


def is_available() -> bool:
    """检查视觉模型是否可用"""
    api_key = os.environ.get("SILICONFLOW_API_KEY", "")
    return bool(api_key)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: py -3.11 vision_client.py <图片路径>")
        sys.exit(1)
    
    client = VisionClient()
    if not client.is_available():
        print("错误: 请设置 SILICONFLOW_API_KEY 环境变量")
        sys.exit(1)
    
    image_path = sys.argv[1]
    print(f"分析图片: {image_path}")
    result = client.analyze_image(image_path)
    print(f"\n结果:\n{result}")