#!/usr/bin/env python3
"""
RunwayML / Pika AI 视频生成集成模块 v1.0
=========================================

通过 REST API 集成 RunwayML Gen-2 和 Pika 1.0 两大 AI 视频生成平台，
支持文生视频、图生视频、视频延伸等功能，提供真实模式、模拟模式
和自动降级模式。

支持的提供商:
- RunwayML : Gen-2 文生视频、图生视频
- Pika     : Pika 1.0 文生视频、图生视频、视频延伸

支持的生成类型:
- text_to_video  : 文生视频
- image_to_video : 图生视频
- video_extend   : 视频延伸（Pika 专属）

执行模式:
- real    : 通过 requests 调用真实 REST API（需要配置 API Key）
- simulate: 模拟执行，生成模拟结果（用于测试和流程验证）
- auto    : 优先真实模式，失败自动降级到模拟模式
"""
import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

OUTPUT_BASE = Path(os.environ.get("AE_WORK_DIR", r"D:\AE-Work"))

RUNWAY_API_KEY = os.environ.get("RUNWAY_API_KEY", "")
PIKA_API_KEY = os.environ.get("PIKA_API_KEY", "")

RUNWAY_API_BASE = "https://api.runwayml.com/v1"
PIKA_API_BASE = "https://api.pika.art/v1"

AVAILABLE_PROVIDERS = ["runway", "pika"]
AVAILABLE_GENERATION_TYPES = ["text_to_video", "image_to_video", "video_extend"]
AVAILABLE_ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:5"]


@dataclass
class AIVideoConfig:
    """AI 视频生成配置数据类。

    Attributes:
        provider: 提供商（runway / pika / auto）默认 auto
        mode: 运行模式（real / simulate / auto）默认 simulate
        api_key: API Key（默认从环境变量读取）
        generation_type: 生成类型（text_to_video / image_to_video / video_extend）
        prompt: 文本提示词
        negative_prompt: 负面提示词（可选）
        input_image: 输入图片路径（图生视频时用）
        input_video: 输入视频路径（视频延伸时用）
        duration: 视频时长（秒，默认 4.0）
        fps: 帧率（默认 24）
        width: 宽度（默认 1024）
        height: 高度（默认 576）
        seed: 随机种子（-1=随机）
        aspect_ratio: 宽高比（16:9 / 9:16 / 1:1 / 4:5）
        motion_bucket: 运动强度（Runway 用，1-255）
        camera_motion: 摄像机运动配置（pan/tilt/zoom/roll）
        output_dir: 输出目录
        poll_interval: 轮询间隔（秒，默认 5）
        max_wait_time: 最大等待时间（秒，默认 600）
    """
    provider: str = "auto"
    mode: str = "simulate"
    api_key: str = ""
    generation_type: str = "text_to_video"
    prompt: str = ""
    negative_prompt: str = ""
    input_image: str = ""
    input_video: str = ""
    duration: float = 4.0
    fps: int = 24
    width: int = 1024
    height: int = 576
    seed: int = -1
    aspect_ratio: str = "16:9"
    motion_bucket: int = 127
    camera_motion: dict[str, Any] = field(default_factory=dict)
    output_dir: str = str(OUTPUT_BASE / "ai_video_output")
    poll_interval: int = 5
    max_wait_time: int = 600


@dataclass
class AIVideoResult:
    """AI 视频生成结果数据类。

    Attributes:
        success: 是否成功
        provider: 实际使用的提供商
        generation_type: 生成类型
        prompt: 使用的提示词
        output_path: 输出视频路径
        task_id: 任务 ID
        duration: 生成耗时（秒）
        video_url: 视频 URL（如果有）
        width: 输出视频宽度
        height: 输出视频高度
        fps: 输出视频帧率
        error: 错误信息（如果失败）
        seed: 使用的种子
    """
    success: bool = False
    provider: str = ""
    generation_type: str = ""
    prompt: str = ""
    output_path: str = ""
    task_id: str = ""
    duration: float = 0.0
    video_url: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    error: str | None = None
    seed: int = -1


AI_VIDEO_PRESETS: dict[str, dict[str, dict[str, Any]]] = {
    "runway": {
        "cinematic": {
            "prompt_template": "cinematic film, {prompt}, shot on Arri Alexa, 35mm film grain, shallow depth of field, dramatic lighting, color graded, movie scene",
            "negative_prompt": "blurry, low quality, distorted, ugly, cartoon, anime, text, watermark",
            "motion_bucket": 120,
            "duration": 4.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "电影级风格，胶片质感，浅景深，戏剧性打光",
        },
        "anime": {
            "prompt_template": "anime style, {prompt}, studio ghibli inspired, vibrant colors, detailed background, smooth animation, 2d animation",
            "negative_prompt": "realistic, photorealistic, 3d render, blurry, low quality, text, watermark",
            "motion_bucket": 100,
            "duration": 4.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "动漫风格，吉卜力风格，鲜艳色彩，流畅动画",
        },
        "realistic": {
            "prompt_template": "photorealistic, {prompt}, ultra detailed, 8k, hdr, natural lighting, real world photography, sharp focus",
            "negative_prompt": "cartoon, anime, drawing, painting, illustration, blurry, distorted, ugly",
            "motion_bucket": 80,
            "duration": 4.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "写实风格，超精细，8K 画质，自然光线",
        },
        "3d_render": {
            "prompt_template": "3d render, {prompt}, octane render, unreal engine 5, cinematic lighting, highly detailed, pixar style, 3d animation",
            "negative_prompt": "realistic, photo, 2d, flat, blurry, low quality, text, watermark",
            "motion_bucket": 130,
            "duration": 4.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "3D 渲染风格，Octane 渲染，皮克斯风格",
        },
        "watercolor": {
            "prompt_template": "watercolor painting style, {prompt}, soft brush strokes, pastel colors, artistic, hand painted, dreamy atmosphere",
            "negative_prompt": "photorealistic, 3d render, sharp focus, realistic, text, watermark, blurry",
            "motion_bucket": 60,
            "duration": 4.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "水彩画风格，柔和笔触，梦幻氛围",
        },
        "oil_painting": {
            "prompt_template": "oil painting style, {prompt}, impasto technique, rich colors, classical art, rembrandt lighting, masterpiece",
            "negative_prompt": "photorealistic, 3d render, modern, cartoon, blurry, low quality, text, watermark",
            "motion_bucket": 70,
            "duration": 4.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "油画风格，厚涂技法，古典艺术，伦勃朗打光",
        },
        "puppet_stop_motion": {
            "prompt_template": "stop motion puppet animation, {prompt}, claymation style, detailed puppets, practical effects, laika studios style, tactile texture",
            "negative_prompt": "cg, 3d render, smooth animation, realistic, blurry, low quality, text",
            "motion_bucket": 90,
            "duration": 4.0,
            "fps": 12,
            "width": 1024,
            "height": 576,
            "description": "木偶定格动画，黏土风格，实体特效",
        },
        "miniature": {
            "prompt_template": "miniature diorama, {prompt}, tilt shift, small scale model, detailed miniature, shallow depth of field, hobbyist model",
            "negative_prompt": "full size, realistic, life size, blurry, low quality, distorted, text, watermark",
            "motion_bucket": 50,
            "duration": 4.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "微缩场景，移轴效果，比例模型",
        },
    },
    "pika": {
        "cinematic": {
            "prompt_template": "cinematic, {prompt}, film grain, dynamic camera movement, dramatic lighting, movie scene, high production value",
            "negative_prompt": "blurry, low quality, distorted, ugly, text, watermark, static camera",
            "camera_motion": {"pan": 0.3, "zoom": 0.2},
            "duration": 3.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "电影级风格，动态摄像机，戏剧性打光",
        },
        "anime": {
            "prompt_template": "anime, {prompt}, japanese animation, vibrant colors, detailed art style, dynamic action, anime aesthetic",
            "negative_prompt": "realistic, photorealistic, 3d, ugly, blurry, low quality, text, watermark",
            "camera_motion": {"pan": 0.2},
            "duration": 3.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "动漫风格，日式动画，鲜艳色彩",
        },
        "realistic": {
            "prompt_template": "photorealistic, {prompt}, ultra detailed, realistic textures, natural lighting, high quality, sharp",
            "negative_prompt": "cartoon, anime, drawing, painting, illustration, blurry, distorted, ugly",
            "camera_motion": {},
            "duration": 3.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "写实风格，超精细，真实材质",
        },
        "3d_render": {
            "prompt_template": "3d render, {prompt}, cinematic lighting, highly detailed 3d assets, disney pixar style, computer animation",
            "negative_prompt": "realistic, photo, 2d, flat, blurry, low quality, text, watermark",
            "camera_motion": {"orbit": 0.3},
            "duration": 3.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "3D 渲染风格，迪士尼皮克斯风格",
        },
        "watercolor": {
            "prompt_template": "watercolor style, {prompt}, soft watercolor washes, artistic, hand painted, dreamy, ethereal",
            "negative_prompt": "photorealistic, 3d render, sharp, realistic, text, watermark, blurry",
            "camera_motion": {"zoom": -0.1},
            "duration": 3.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "水彩画风格，柔和晕染，梦幻飘逸",
        },
        "oil_painting": {
            "prompt_template": "oil painting, {prompt}, thick brushstrokes, rich oil colors, classical painting style, fine art",
            "negative_prompt": "photorealistic, 3d render, modern, cartoon, blurry, low quality, text, watermark",
            "camera_motion": {},
            "duration": 3.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "油画风格，厚重笔触，古典绘画",
        },
        "puppet_stop_motion": {
            "prompt_template": "stop motion, {prompt}, clay animation, puppet animation, stop motion style, tactile, physical animation",
            "negative_prompt": "cg, 3d render, smooth, realistic, blurry, low quality, text",
            "camera_motion": {"pan": 0.1},
            "duration": 3.0,
            "fps": 15,
            "width": 1024,
            "height": 576,
            "description": "木偶定格动画，黏土动画，实体动画",
        },
        "miniature": {
            "prompt_template": "miniature, {prompt}, tilt shift effect, small scale, model diorama, tiny world, macro",
            "negative_prompt": "full size, realistic, life size, blurry, low quality, distorted, text, watermark",
            "camera_motion": {"zoom": 0.2},
            "duration": 3.0,
            "fps": 24,
            "width": 1024,
            "height": 576,
            "description": "微缩场景，移轴效果，迷你世界",
        },
    },
}


class AIVideoGenerator:
    """AI 视频生成器。

    封装 RunwayML 和 Pika 两大 AI 视频生成平台的 REST API 调用，
    提供文生视频、图生视频、视频延伸等功能的统一接口。
    支持真实模式、模拟模式和自动降级模式。
    """

    def __init__(self, config: AIVideoConfig | None = None):
        """初始化 AIVideoGenerator。

        Args:
            config: AI 视频生成配置对象，为 None 时使用默认配置
        """
        self.config = config or AIVideoConfig()
        self._runway_available = self._check_provider_available("runway")
        self._pika_available = self._check_provider_available("pika")
        print(f"[AIVideoGenerator] Mode: {self.config.mode}")
        print(f"[AIVideoGenerator] Runway available: {self._runway_available}")
        print(f"[AIVideoGenerator] Pika available: {self._pika_available}")

    def _check_provider_available(self, provider: str) -> bool:
        """检查指定提供商是否可用（有 API Key）。

        Args:
            provider: 提供商名称（runway / pika）

        Returns:
            True 表示可用，False 表示不可用
        """
        if self.config.api_key:
            return True
        if provider == "runway":
            return bool(RUNWAY_API_KEY)
        elif provider == "pika":
            return bool(PIKA_API_KEY)
        return False

    def is_available(self, provider: str | None = None) -> bool:
        """检查指定提供商是否可用。

        Args:
            provider: 提供商名称（runway / pika / None=检查任意一个可用）

        Returns:
            True 表示可用，False 表示不可用
        """
        if provider is None:
            return self._runway_available or self._pika_available
        if provider == "runway":
            return self._runway_available
        elif provider == "pika":
            return self._pika_available
        return False

    def _resolve_provider(self, config: AIVideoConfig) -> str:
        """解析实际使用的提供商。

        Args:
            config: 配置对象

        Returns:
            实际使用的提供商名称
        """
        provider = config.provider
        if provider == "auto":
            if self._pika_available:
                return "pika"
            if self._runway_available:
                return "runway"
            return "pika"
        return provider

    def _get_api_key(self, provider: str, config: AIVideoConfig) -> str:
        """获取指定提供商的 API Key。

        Args:
            provider: 提供商名称
            config: 配置对象

        Returns:
            API Key
        """
        if config.api_key:
            return config.api_key
        if provider == "runway":
            return RUNWAY_API_KEY
        elif provider == "pika":
            return PIKA_API_KEY
        return ""

    def _resolve_mode(self, config: AIVideoConfig, provider: str) -> str:
        """解析实际运行模式。

        Args:
            config: 配置对象
            provider: 实际使用的提供商

        Returns:
            实际运行模式（real / simulate）
        """
        mode = config.mode
        if mode == "auto":
            return "real" if self.is_available(provider) else "simulate"
        return mode

    def get_provider_presets(self, provider: str) -> dict[str, dict[str, Any]]:
        """获取提供商的风格预设。

        Args:
            provider: 提供商名称（runway / pika）

        Returns:
            预设字典，key 为预设名称，value 为预设配置
        """
        return AI_VIDEO_PRESETS.get(provider, {})

    def _apply_preset_to_config(
        self,
        preset_name: str,
        config: AIVideoConfig,
        provider: str,
    ) -> AIVideoConfig:
        """将预设应用到配置对象。

        Args:
            preset_name: 预设名称
            config: 基础配置
            provider: 提供商

        Returns:
            应用预设后的配置
        """
        presets = self.get_provider_presets(provider)
        if preset_name not in presets:
            return config

        preset = presets[preset_name]
        new_config = AIVideoConfig()
        for attr in config.__dataclass_fields__:
            if hasattr(config, attr):
                setattr(new_config, attr, getattr(config, attr))

        new_config.provider = provider

        if "duration" in preset:
            new_config.duration = preset["duration"]
        if "fps" in preset:
            new_config.fps = preset["fps"]
        if "width" in preset:
            new_config.width = preset["width"]
        if "height" in preset:
            new_config.height = preset["height"]
        if "motion_bucket" in preset:
            new_config.motion_bucket = preset["motion_bucket"]
        if "camera_motion" in preset:
            new_config.camera_motion = dict(preset["camera_motion"])
        if "negative_prompt" in preset and not new_config.negative_prompt:
            new_config.negative_prompt = preset["negative_prompt"]

        if "prompt_template" in preset and new_config.prompt:
            template = preset["prompt_template"]
            new_config.prompt = template.format(prompt=new_config.prompt)

        return new_config

    def generate(
        self,
        config: AIVideoConfig | None = None,
        callback: Callable[[float, str], None] | None = None,
    ) -> AIVideoResult:
        """主方法：生成视频。

        根据配置调用相应的生成方法。

        Args:
            config: 配置（可选，默认使用实例配置）
            callback: 进度回调函数 (progress 0-1, message)

        Returns:
            AIVideoResult 生成结果对象
        """
        cfg = config or self.config
        start_time = time.time()

        if not cfg.prompt and cfg.generation_type == "text_to_video":
            return AIVideoResult(
                success=False,
                error="Prompt is required for text_to_video generation",
                generation_type=cfg.generation_type,
            )

        provider = self._resolve_provider(cfg)
        mode = self._resolve_mode(cfg, provider)

        if callback:
            callback(0.0, f"Starting {cfg.generation_type} with {provider} in {mode} mode...")

        result = AIVideoResult(
            success=False,
            provider=provider,
            generation_type=cfg.generation_type,
            prompt=cfg.prompt,
            width=cfg.width,
            height=cfg.height,
            fps=float(cfg.fps),
            seed=cfg.seed,
        )

        if mode == "real":
            real_result = self._run_real_mode(cfg, provider, callback)
            result = real_result
            if not real_result.success and cfg.mode == "auto":
                print("[AIVideoGenerator] Real mode failed, falling back to simulate")
                if callback:
                    callback(0.2, "Real mode failed, falling back to simulate mode...")
                sim_result = self._run_simulate_mode(cfg, provider, callback)
                result = sim_result
        else:
            sim_result = self._run_simulate_mode(cfg, provider, callback)
            result = sim_result

        result.duration = time.time() - start_time
        return result

    def text_to_video(
        self,
        prompt: str,
        config: AIVideoConfig | None = None,
        callback: Callable[[float, str], None] | None = None,
    ) -> AIVideoResult:
        """文生视频。

        Args:
            prompt: 文本提示词
            config: 配置（可选，默认使用实例配置）
            callback: 进度回调函数 (progress 0-1, message)

        Returns:
            AIVideoResult 生成结果对象
        """
        cfg = config or AIVideoConfig()
        cfg.prompt = prompt
        cfg.generation_type = "text_to_video"
        return self.generate(cfg, callback)

    def image_to_video(
        self,
        image_path: str,
        prompt: str,
        config: AIVideoConfig | None = None,
        callback: Callable[[float, str], None] | None = None,
    ) -> AIVideoResult:
        """图生视频。

        Args:
            image_path: 输入图片路径
            prompt: 文本提示词
            config: 配置（可选，默认使用实例配置）
            callback: 进度回调函数 (progress 0-1, message)

        Returns:
            AIVideoResult 生成结果对象
        """
        cfg = config or AIVideoConfig()
        cfg.prompt = prompt
        cfg.input_image = image_path
        cfg.generation_type = "image_to_video"

        if not Path(image_path).exists():
            return AIVideoResult(
                success=False,
                error=f"Input image not found: {image_path}",
                generation_type="image_to_video",
                prompt=prompt,
            )

        return self.generate(cfg, callback)

    def video_extend(
        self,
        video_path: str,
        prompt: str,
        config: AIVideoConfig | None = None,
        callback: Callable[[float, str], None] | None = None,
    ) -> AIVideoResult:
        """视频延伸。

        Args:
            video_path: 输入视频路径
            prompt: 文本提示词
            config: 配置（可选，默认使用实例配置）
            callback: 进度回调函数 (progress 0-1, message)

        Returns:
            AIVideoResult 生成结果对象
        """
        cfg = config or AIVideoConfig()
        cfg.prompt = prompt
        cfg.input_video = video_path
        cfg.generation_type = "video_extend"

        if not Path(video_path).exists():
            return AIVideoResult(
                success=False,
                error=f"Input video not found: {video_path}",
                generation_type="video_extend",
                prompt=prompt,
            )

        return self.generate(cfg, callback)

    def batch_generate(
        self,
        configs: list[AIVideoConfig],
        callback: Callable[[int, int, AIVideoResult], None] | None = None,
    ) -> list[AIVideoResult]:
        """批量生成视频。

        Args:
            configs: 配置列表
            callback: 进度回调函数 (current_index, total, current_result)

        Returns:
            AIVideoResult 列表
        """
        results = []
        total = len(configs)

        for idx, cfg in enumerate(configs):
            result = self.generate(config=cfg, callback=None)
            results.append(result)

            if callback:
                callback(idx + 1, total, result)

        return results

    def _run_real_mode(
        self,
        config: AIVideoConfig,
        provider: str,
        callback: Callable[[float, str], None] | None = None,
    ) -> AIVideoResult:
        """真实模式：通过 requests 调用 REST API。

        注意：此为基础框架，真实 API 调用需根据官方文档完善。

        Args:
            config: 生成配置
            provider: 提供商
            callback: 进度回调函数

        Returns:
            AIVideoResult 生成结果
        """
        result = AIVideoResult(
            success=False,
            provider=provider,
            generation_type=config.generation_type,
            prompt=config.prompt,
            width=config.width,
            height=config.height,
            fps=float(config.fps),
            seed=config.seed,
        )

        api_key = self._get_api_key(provider, config)
        if not api_key:
            result.error = f"No API key available for {provider}"
            return result

        try:
            import requests
        except ImportError:
            result.error = "requests library not installed"
            return result

        try:
            task_id = self._create_task(config, provider, api_key)
            result.task_id = task_id

            if callback:
                callback(0.1, f"Task created: {task_id}")

            video_url = self._poll_task(task_id, config, provider, api_key, callback)

            if video_url:
                output_path = self._download_video(video_url, config, provider)
                result.output_path = output_path
                result.video_url = video_url
                result.success = True

                if callback:
                    callback(1.0, "Generation complete")
            else:
                result.error = "Task failed or timed out"

            return result

        except Exception as e:
            result.error = str(e)
            return result

    def _create_task(
        self,
        config: AIVideoConfig,
        provider: str,
        api_key: str,
    ) -> str:
        """创建生成任务。

        Args:
            config: 生成配置
            provider: 提供商
            api_key: API Key

        Returns:
            任务 ID
        """
        import requests

        if provider == "runway":
            url = f"{RUNWAY_API_BASE}/image_to_video"
            if config.generation_type == "text_to_video":
                url = f"{RUNWAY_API_BASE}/text_to_video"

            payload = {
                "prompt": config.prompt,
                "duration": config.duration,
                "aspect_ratio": config.aspect_ratio,
                "seed": config.seed if config.seed != -1 else None,
                "motion_bucket_id": config.motion_bucket,
            }

            if config.negative_prompt:
                payload["negative_prompt"] = config.negative_prompt

            if config.generation_type == "image_to_video" and config.input_image:
                payload["input_image"] = config.input_image

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("id", data.get("task_id", str(uuid.uuid4())))

        elif provider == "pika":
            url = f"{PIKA_API_BASE}/generations"

            payload = {
                "prompt": config.prompt,
                "aspect_ratio": config.aspect_ratio,
                "frames": int(config.duration * config.fps),
                "fps": config.fps,
                "seed": config.seed if config.seed != -1 else None,
            }

            if config.negative_prompt:
                payload["negative_prompt"] = config.negative_prompt

            if config.camera_motion:
                payload["camera_motion"] = config.camera_motion

            if config.generation_type == "image_to_video" and config.input_image:
                payload["image"] = config.input_image
            elif config.generation_type == "video_extend" and config.input_video:
                payload["video"] = config.input_video

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("id", data.get("generation_id", str(uuid.uuid4())))

        return str(uuid.uuid4())

    def _poll_task(
        self,
        task_id: str,
        config: AIVideoConfig,
        provider: str,
        api_key: str,
        callback: Callable[[float, str], None] | None = None,
    ) -> str | None:
        """轮询任务状态直到完成或超时。

        Args:
            task_id: 任务 ID
            config: 生成配置
            provider: 提供商
            api_key: API Key
            callback: 进度回调函数

        Returns:
            视频 URL（成功时），None（失败或超时时）
        """
        import requests

        start_time = time.time()
        poll_count = 0

        while time.time() - start_time < config.max_wait_time:
            try:
                if provider == "runway":
                    url = f"{RUNWAY_API_BASE}/tasks/{task_id}"
                    headers = {"Authorization": f"Bearer {api_key}"}
                    response = requests.get(url, headers=headers, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    status = data.get("status", "pending")

                    if status == "succeeded":
                        return data.get("output", {}).get("video_url", "")
                    elif status == "failed":
                        return None

                    progress = data.get("progress", 0)
                    overall_progress = 0.1 + (progress / 100) * 0.7

                elif provider == "pika":
                    url = f"{PIKA_API_BASE}/generations/{task_id}"
                    headers = {"Authorization": f"Bearer {api_key}"}
                    response = requests.get(url, headers=headers, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    status = data.get("status", "pending")

                    if status == "completed":
                        videos = data.get("videos", [])
                        if videos:
                            return videos[0].get("url", "")
                        return data.get("video_url", "")
                    elif status == "failed":
                        return None

                    progress_ratio = min(1.0, poll_count * config.poll_interval / 60.0)
                    overall_progress = 0.1 + progress_ratio * 0.7

                if callback:
                    callback(overall_progress, f"Generating... ({status})")

                time.sleep(config.poll_interval)
                poll_count += 1

            except Exception as e:
                print(f"[AIVideoGenerator] Poll error: {e}")
                time.sleep(config.poll_interval)
                poll_count += 1

        return None

    def _download_video(
        self,
        video_url: str,
        config: AIVideoConfig,
        provider: str,
    ) -> str:
        """下载生成的视频。

        Args:
            video_url: 视频 URL
            config: 生成配置
            provider: 提供商

        Returns:
            本地保存路径
        """
        import requests

        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        ts = int(time.time())
        output_path = output_dir / f"{provider}_{config.generation_type}_{ts}.mp4"

        response = requests.get(video_url, stream=True, timeout=60)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return str(output_path)

    def _run_simulate_mode(
        self,
        config: AIVideoConfig,
        provider: str,
        callback: Callable[[float, str], None] | None = None,
    ) -> AIVideoResult:
        """模拟模式：不真正调用 API，生成模拟结果。

        Args:
            config: 生成配置
            provider: 提供商
            callback: 进度回调函数

        Returns:
            AIVideoResult 生成结果
        """
        task_id = f"sim_{provider}_{config.generation_type}_{uuid.uuid4().hex[:8]}"

        sim_duration = min(config.duration * 0.5 + 1.0, 5.0)

        phases = [
            (0.1, "Initializing..."),
            (0.25, "Processing prompt..."),
            (0.5, f"Generating frames with {provider}..."),
            (0.75, "Rendering video..."),
            (0.9, "Finalizing..."),
        ]

        start_time = time.time()
        last_progress = 0.0

        for target_progress, message in phases:
            if callback:
                callback(target_progress, message)
            last_progress = target_progress
            time.sleep(sim_duration / len(phases))

        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        ts = int(time.time())
        output_filename = f"{provider}_{config.generation_type}_{ts}.mp4"
        output_path = output_dir / output_filename

        if config.input_video and Path(config.input_video).exists():
            try:
                shutil.copy2(config.input_video, output_path)
            except Exception:
                self._create_simulated_video(output_path, config)
        elif config.input_image and Path(config.input_image).exists():
            self._create_simulated_video(output_path, config)
        else:
            self._create_simulated_video(output_path, config)

        actual_seed = config.seed if config.seed != -1 else int(time.time())

        result = AIVideoResult(
            success=True,
            provider=provider,
            generation_type=config.generation_type,
            prompt=config.prompt,
            output_path=str(output_path),
            task_id=task_id,
            duration=time.time() - start_time,
            video_url="",
            width=config.width,
            height=config.height,
            fps=float(config.fps),
            seed=actual_seed,
        )

        if callback:
            callback(1.0, "Simulation complete")

        return result

    def _create_simulated_video(
        self,
        output_path: Path,
        config: AIVideoConfig,
    ) -> None:
        """创建模拟视频文件。

        Args:
            output_path: 输出路径
            config: 生成配置
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        estimated_size = int(config.width * config.height * config.fps * config.duration * 0.01)
        estimated_size = max(1024, min(estimated_size, 50 * 1024 * 1024))

        with open(output_path, "wb") as f:
            f.write(b"AI_VIDEO_SIMULATED_OUTPUT")
            f.write(f"\nProvider: {config.provider}".encode())
            f.write(f"\nType: {config.generation_type}".encode())
            f.write(f"\nPrompt: {config.prompt}".encode())
            f.write(f"\nResolution: {config.width}x{config.height}".encode())
            f.write(f"\nFPS: {config.fps}".encode())
            f.write(f"\nDuration: {config.duration}s".encode())
            f.write(b"\n" + b"=" * 40 + b"\n")
            if estimated_size > 1024:
                f.seek(estimated_size - 1)
                f.write(b"\0")


def create_config_from_preset(
    preset_name: str,
    provider: str = "auto",
) -> AIVideoConfig:
    """从预设创建 AIVideoConfig 配置对象。

    Args:
        preset_name: 预设名称
        provider: 提供商（runway / pika / auto）

    Returns:
        AIVideoConfig 配置对象

    Raises:
        ValueError: 预设不存在时抛出
    """
    actual_provider = provider if provider != "auto" else "pika"
    presets = AI_VIDEO_PRESETS.get(actual_provider, {})

    if preset_name not in presets:
        raise ValueError(
            f"Unknown preset: {preset_name} for provider {actual_provider}. "
            f"Available presets: {list(presets.keys())}"
        )

    preset = presets[preset_name]
    config = AIVideoConfig()
    config.provider = actual_provider

    if "duration" in preset:
        config.duration = preset["duration"]
    if "fps" in preset:
        config.fps = preset["fps"]
    if "width" in preset:
        config.width = preset["width"]
    if "height" in preset:
        config.height = preset["height"]
    if "motion_bucket" in preset:
        config.motion_bucket = preset["motion_bucket"]
    if "camera_motion" in preset:
        config.camera_motion = dict(preset["camera_motion"])
    if "negative_prompt" in preset:
        config.negative_prompt = preset["negative_prompt"]

    return config


def _run_self_tests():
    """自测函数：验证 AI 视频生成集成模块的所有功能。"""
    print("=" * 60)
    print("RunwayML / Pika AI 视频生成集成模块 - 自测")
    print("=" * 60)

    results = []

    test_dir = Path(tempfile.mkdtemp(prefix="ai_video_test_"))

    test_image = test_dir / "test_input.png"
    try:
        with open(test_image, "wb") as f:
            f.write(b"FAKE_IMAGE_HEADER")
            f.seek(100 * 1024)
            f.write(b"\0")
    except Exception:
        pass

    test_video = test_dir / "test_input.mp4"
    try:
        with open(test_video, "wb") as f:
            f.write(b"FAKE_VIDEO_HEADER")
            f.seek(1024 * 1024)
            f.write(b"\0")
    except Exception:
        pass

    print("\n[测试 1/10] 检查 AI_VIDEO_PRESETS 预设配置...")
    runway_expected = [
        "cinematic", "anime", "realistic", "3d_render",
        "watercolor", "oil_painting", "puppet_stop_motion", "miniature",
    ]
    pika_expected = runway_expected

    runway_ok = all(p in AI_VIDEO_PRESETS.get("runway", {}) for p in runway_expected)
    pika_ok = all(p in AI_VIDEO_PRESETS.get("pika", {}) for p in pika_expected)

    if runway_ok and pika_ok:
        print(f"  ✓ Runway 预设: {len(runway_expected)} 个")
        print(f"  ✓ Pika 预设: {len(pika_expected)} 个")
        results.append(("presets", True))
    else:
        print(f"  ✗ 预设不完整 (runway: {runway_ok}, pika: {pika_ok})")
        results.append(("presets", False))

    print("\n[测试 2/10] 检查 AIVideoConfig 数据类...")
    try:
        config = AIVideoConfig()
        required_attrs = [
            "provider", "mode", "api_key", "generation_type",
            "prompt", "negative_prompt", "input_image", "input_video",
            "duration", "fps", "width", "height", "seed",
            "aspect_ratio", "motion_bucket", "camera_motion",
            "output_dir", "poll_interval", "max_wait_time",
        ]
        attrs_ok = all(hasattr(config, attr) for attr in required_attrs)
        if attrs_ok:
            print(f"  ✓ AIVideoConfig 包含所有必需属性 ({len(required_attrs)} 个)")
        else:
            print("  ✗ AIVideoConfig 缺少必需属性")
        results.append(("config_dataclass", attrs_ok))
    except Exception as e:
        print(f"  ✗ AIVideoConfig 错误: {e}")
        results.append(("config_dataclass", False))

    print("\n[测试 3/10] 检查 AIVideoResult 数据类...")
    try:
        result = AIVideoResult()
        required_attrs = [
            "success", "provider", "generation_type", "prompt",
            "output_path", "task_id", "duration", "video_url",
            "width", "height", "fps", "error", "seed",
        ]
        attrs_ok = all(hasattr(result, attr) for attr in required_attrs)
        if attrs_ok:
            print(f"  ✓ AIVideoResult 包含所有必需属性 ({len(required_attrs)} 个)")
        else:
            print("  ✗ AIVideoResult 缺少必需属性")
        results.append(("result_dataclass", attrs_ok))
    except Exception as e:
        print(f"  ✗ AIVideoResult 错误: {e}")
        results.append(("result_dataclass", False))

    print("\n[测试 4/10] 检查 AIVideoGenerator 初始化...")
    try:
        gen = AIVideoGenerator(config=AIVideoConfig(mode="simulate"))
        print("  ✓ AIVideoGenerator 初始化成功")
        print(f"    - Mode: {gen.config.mode}")
        print(f"    - Runway available: {gen.is_available('runway')}")
        print(f"    - Pika available: {gen.is_available('pika')}")
        results.append(("generator_init", True))
    except Exception as e:
        print(f"  ✗ AIVideoGenerator 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("generator_init", False))

    print("\n[测试 5/10] 检查 get_provider_presets...")
    try:
        gen = AIVideoGenerator(config=AIVideoConfig(mode="simulate"))
        runway_presets = gen.get_provider_presets("runway")
        pika_presets = gen.get_provider_presets("pika")
        if len(runway_presets) == 8 and len(pika_presets) == 8:
            print(f"  ✓ Runway 预设: {len(runway_presets)} 个")
            print(f"  ✓ Pika 预设: {len(pika_presets)} 个")
            results.append(("provider_presets", True))
        else:
            print(f"  ✗ 预设数量不对 (runway: {len(runway_presets)}, pika: {len(pika_presets)})")
            results.append(("provider_presets", False))
    except Exception as e:
        print(f"  ✗ get_provider_presets 错误: {e}")
        results.append(("provider_presets", False))

    print("\n[测试 6/10] 检查 simulate 模式 text_to_video...")
    try:
        gen = AIVideoGenerator(config=AIVideoConfig(mode="simulate", output_dir=str(test_dir / "output")))

        progress_log = []
        def progress_cb(progress, msg):
            progress_log.append((progress, msg))

        result = gen.text_to_video(
            prompt="a beautiful sunset over the ocean",
            callback=progress_cb,
        )

        if result.success and Path(result.output_path).exists():
            print("  ✓ 文生视频模拟成功")
            print(f"    - Provider: {result.provider}")
            print(f"    - 分辨率: {result.width}x{result.height}")
            print(f"    - FPS: {result.fps}")
            print(f"    - 进度回调次数: {len(progress_log)}")
            results.append(("simulate_text_to_video", True))
        else:
            print(f"  ✗ 文生视频模拟失败: {result.error}")
            results.append(("simulate_text_to_video", False))
    except Exception as e:
        print(f"  ✗ text_to_video 错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("simulate_text_to_video", False))

    print("\n[测试 7/10] 检查 simulate 模式 image_to_video...")
    try:
        gen = AIVideoGenerator(config=AIVideoConfig(mode="simulate", output_dir=str(test_dir / "output")))

        progress_log = []
        def progress_cb(progress, msg):
            progress_log.append((progress, msg))

        result = gen.image_to_video(
            image_path=str(test_image),
            prompt="make it move with wind",
            callback=progress_cb,
        )

        if result.success and Path(result.output_path).exists():
            print("  ✓ 图生视频模拟成功")
            print(f"    - Provider: {result.provider}")
            print(f"    - 任务 ID: {result.task_id}")
            print(f"    - 进度回调次数: {len(progress_log)}")
            results.append(("simulate_image_to_video", True))
        else:
            print(f"  ✗ 图生视频模拟失败: {result.error}")
            results.append(("simulate_image_to_video", False))
    except Exception as e:
        print(f"  ✗ image_to_video 错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("simulate_image_to_video", False))

    print("\n[测试 8/10] 检查 simulate 模式 video_extend...")
    try:
        gen = AIVideoGenerator(config=AIVideoConfig(mode="simulate", output_dir=str(test_dir / "output")))

        result = gen.video_extend(
            video_path=str(test_video),
            prompt="continue the scene",
        )

        if result.success and Path(result.output_path).exists():
            print("  ✓ 视频延伸模拟成功")
            print(f"    - Provider: {result.provider}")
            print(f"    - 种子: {result.seed}")
            results.append(("simulate_video_extend", True))
        else:
            print(f"  ✗ 视频延伸模拟失败: {result.error}")
            results.append(("simulate_video_extend", False))
    except Exception as e:
        print(f"  ✗ video_extend 错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("simulate_video_extend", False))

    print("\n[测试 9/10] 检查 create_config_from_preset...")
    try:
        config = create_config_from_preset("cinematic", "runway")
        if config.provider == "runway" and config.motion_bucket == 120:
            print("  ✓ 预设创建成功 (cinematic @ runway)")
            print(f"    - motion_bucket: {config.motion_bucket}")
            print(f"    - 分辨率: {config.width}x{config.height}")
            print(f"    - duration: {config.duration}s")
            results.append(("preset_create", True))
        else:
            print("  ✗ 预设参数不匹配")
            results.append(("preset_create", False))
    except Exception as e:
        print(f"  ✗ create_config_from_preset 错误: {e}")
        results.append(("preset_create", False))

    print("\n[测试 10/10] 检查 batch_generate 批量生成...")
    try:
        gen = AIVideoGenerator(config=AIVideoConfig(mode="simulate", output_dir=str(test_dir / "batch_output")))

        configs = [
            AIVideoConfig(prompt="scene 1", generation_type="text_to_video"),
            AIVideoConfig(prompt="scene 2", generation_type="text_to_video"),
            AIVideoConfig(prompt="scene 3", generation_type="text_to_video"),
        ]

        batch_log = []
        def batch_cb(current, total, result):
            batch_log.append((current, total, result.success))

        results_list = gen.batch_generate(configs, callback=batch_cb)

        success_count = sum(1 for r in results_list if r.success)
        if success_count == len(configs) and len(batch_log) == len(configs):
            print(f"  ✓ 批量生成成功 ({success_count}/{len(configs)})")
            results.append(("batch_generate", True))
        else:
            print(f"  ✗ 批量生成失败 (成功 {success_count}/{len(configs)})")
            results.append(("batch_generate", False))
    except Exception as e:
        print(f"  ✗ batch_generate 错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("batch_generate", False))

    print("\n[预设配置清单]")
    for provider in ["runway", "pika"]:
        print(f"\n  [{provider.upper()}]")
        presets = AI_VIDEO_PRESETS.get(provider, {})
        for pname, pdata in presets.items():
            desc = pdata.get("description", "")
            print(f"    - {pname}: {desc}")

    try:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)
    except Exception:
        pass

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"自测结果: {passed}/{total} 通过")
    print("=" * 60)

    for name, ok in results:
        status = "✓ 通过" if ok else "✗ 失败"
        print(f"  {status}: {name}")

    return passed == total


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RunwayML / Pika AI Video Generator")
    parser.add_argument(
        "--mode",
        choices=["real", "simulate", "auto"],
        default="simulate",
        help="Execution mode",
    )
    parser.add_argument(
        "--provider",
        choices=["runway", "pika", "auto"],
        default="auto",
        help="AI provider",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run self-tests",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        help="Text prompt for video generation",
    )
    parser.add_argument(
        "--type",
        choices=["text_to_video", "image_to_video", "video_extend"],
        default="text_to_video",
        help="Generation type",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Input image or video path",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory",
    )
    parser.add_argument(
        "--preset",
        type=str,
        help="Style preset name",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List all available presets",
    )
    parser.add_argument(
        "--list-providers",
        action="store_true",
        help="List all available providers",
    )

    args = parser.parse_args()

    if args.test:
        success = _run_self_tests()
        sys.exit(0 if success else 1)
    elif args.list_presets:
        gen = AIVideoGenerator()
        provider = args.provider if args.provider != "auto" else "pika"
        presets = gen.get_provider_presets(provider)
        print(f"Available presets for {provider}:")
        for name, data in presets.items():
            desc = data.get("description", "")
            print(f"  {name}: {desc}")
    elif args.list_providers:
        print("Available providers:")
        for p in AVAILABLE_PROVIDERS:
            gen = AIVideoGenerator()
            avail = gen.is_available(p)
            print(f"  - {p}: {'available' if avail else 'not available'}")
    elif args.prompt:
        config = AIVideoConfig()
        config.mode = args.mode
        config.provider = args.provider
        config.generation_type = args.type
        config.prompt = args.prompt

        if args.output_dir:
            config.output_dir = args.output_dir

        if args.preset:
            provider = args.provider if args.provider != "auto" else "pika"
            config = create_config_from_preset(args.preset, provider)
            config.mode = args.mode
            config.prompt = args.prompt
            config.generation_type = args.type

        if args.type == "image_to_video" and args.input:
            config.input_image = args.input
        elif args.type == "video_extend" and args.input:
            config.input_video = args.input

        gen = AIVideoGenerator(config=config)

        print(f"Generating video with {args.provider} ({args.mode})")
        print(f"Type: {args.type}")
        print(f"Prompt: {args.prompt}")

        def progress(progress_val, msg):
            print(f"  [{int(progress_val * 100):3d}%] {msg}")

        result = gen.generate(callback=progress)

        if result.success:
            print(f"\n✓ Success! Output: {result.output_path}")
            print(f"  Duration: {result.duration:.2f}s")
            print(f"  Resolution: {result.width}x{result.height}")
            print(f"  FPS: {result.fps}")
            print(f"  Seed: {result.seed}")
            sys.exit(0)
        else:
            print(f"\n✗ Failed: {result.error}")
            sys.exit(1)
    else:
        parser.print_help()
