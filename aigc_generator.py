"""
AIGCGenerator - AI生成补充素材
=========================

当真实素材搜索无法满足需求时，使用AI生成补充素材。

工作流:
1. 接收素材缺口信息 (需要多少个、什么类型、什么风格)
2. 生成英文提示词 (从用户中文描述翻译/转换)
3. 调用AI生成服务:
   - 图片: DALL-E / Imagen / Flux / 可灵图生视频首帧
   - 视频: Veo / Sora / 可灵 / Pika
4. 保存到素材目录
5. 返回生成结果

优先级:
- P1: 可灵 (国内可用，视频质量高)
- P2: Veo (Google，质量好但需代理)
- P3: Sora (OpenAI，质量好但贵)
- P4: DALL-E/Imagen (图片生成，用于静帧)
"""

import os
import sys
import json
import time
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output_director" / "materials"


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


# ================================================================
#  提示词生成器
# ================================================================
class PromptGenerator:
    """将用户中文描述转换为AI生成用的英文提示词"""

    # 中文→英文风格映射
    STYLE_MAP = {
        "高燃": "epic intense dramatic",
        "电影感": "cinematic film look",
        "古风": "ancient Chinese traditional style",
        "赛博朋克": "cyberpunk neon futuristic",
        "唯美": "beautiful aesthetic dreamy",
        "暗黑": "dark moody atmospheric",
        "治愈": "peaceful healing serene",
        "科幻": "sci-fi futuristic",
        "悬疑": "mysterious suspenseful",
        "浪漫": "romantic soft lighting",
        "热血": "passionate energetic",
        "清新": "fresh clean bright",
    }

    def generate_video_prompt(self, user_prompt: str, style: str = "cinematic") -> str:
        """生成视频生成提示词"""
        # 提取英文关键词
        en_keywords = self._extract_english(user_prompt)

        # 风格词
        style_words = self._get_style_words(style, user_prompt)

        # 视频质量后缀
        quality_suffix = (
            "high quality, 4K, smooth motion, "
            "professional cinematography, dynamic camera movement"
        )

        prompt = f"{en_keywords}, {style_words}, {quality_suffix}"
        return prompt.strip(", ")

    def generate_image_prompt(self, user_prompt: str, style: str = "cinematic") -> str:
        """生成图片生成提示词"""
        en_keywords = self._extract_english(user_prompt)
        style_words = self._get_style_words(style, user_prompt)

        quality_suffix = (
            "highly detailed, 4K, professional photography, "
            "sharp focus, cinematic composition"
        )

        prompt = f"{en_keywords}, {style_words}, {quality_suffix}"
        return prompt.strip(", ")

    def _extract_english(self, prompt: str) -> str:
        """从中文描述提取英文主体"""
        # 常用中文词汇映射
        mappings = {
            "利威尔": "Levi Ackerman from Attack on Titan",
            "冰海战记": "viking warriors in battle, Vinland Saga",
            "进击的巨人": "Attack on Titan, giant warriors",
            "战斗": "battle scene, warriors fighting",
            "风景": "beautiful landscape scenery",
            "人物": "character portrait",
            "城市夜景": "city nightscape, neon lights",
            "森林": "dense forest, nature",
            "海洋": "ocean waves, sea",
            "山峰": "mountain peaks, majestic",
            "日落": "sunset, golden hour",
            "星空": "starry night sky, galaxy",
        }

        results = []
        for cn, en in mappings.items():
            if cn in prompt:
                results.append(en)

        if results:
            return ", ".join(results)

        # 如果没有匹配到，返回一个通用的描述
        return "cinematic scene, high quality footage"

    def _get_style_words(self, style: str, user_prompt: str) -> str:
        """获取风格词"""
        words = []

        # 从 prompt 中检测风格词
        for cn, en in self.STYLE_MAP.items():
            if cn in user_prompt:
                words.append(en)

        # 从 style 参数添加
        if style == "cinematic":
            words.append("cinematic color grading, film grain")
        elif style == "cyberpunk":
            words.append("cyberpunk neon lights, futuristic")
        elif style == "dreamy":
            words.append("dreamy soft focus, ethereal")
        elif style == "dark":
            words.append("dark moody, low key lighting")

        return ", ".join(words) if words else "cinematic"


# ================================================================
#  AI 生成适配器基类
# ================================================================
class BaseAIGCAdapter:
    """AI生成适配器基类"""

    name: str = ""
    supports_video: bool = False
    supports_image: bool = False
    priority: int = 0

    def is_available(self) -> bool:
        return False

    def generate_video(self, prompt: str, output_path: str,
                       duration: int = 4, size: str = "720x1280") -> Dict:
        raise NotImplementedError

    def generate_image(self, prompt: str, output_path: str,
                       size: str = "1024x1024") -> Dict:
        raise NotImplementedError


# ================================================================
#  DALL-E 图片生成 (OpenAI)
# ================================================================
class DALLEAdapter(BaseAIGCAdapter):
    """OpenAI DALL-E 图片生成"""

    name = "DALL-E"
    supports_image = True
    supports_video = False
    priority = 70

    def is_available(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    def generate_image(self, prompt: str, output_path: str,
                       size: str = "1024x1024") -> Dict:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {"success": False, "error": "No OPENAI_API_KEY"}

        try:
            import urllib.request

            url = "https://api.openai.com/v1/images/generations"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            data = json.dumps({
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": size,
                "response_format": "url",
            }).encode("utf-8")

            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            image_url = result["data"][0]["url"]

            # 下载图片
            urllib.request.urlretrieve(image_url, output_path)

            return {
                "success": True,
                "path": output_path,
                "source": "DALL-E",
                "prompt": prompt,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


# ================================================================
#  Google Imagen 图片生成
# ================================================================
class ImagenAdapter(BaseAIGCAdapter):
    """Google Imagen 图片生成"""

    name = "Imagen"
    supports_image = True
    supports_video = False
    priority = 60

    def is_available(self) -> bool:
        return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))

    def generate_image(self, prompt: str, output_path: str,
                       size: str = "1024x1024") -> Dict:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return {"success": False, "error": "No GEMINI_API_KEY"}

        try:
            import urllib.request

            url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={api_key}"
            headers = {"Content-Type": "application/json"}
            data = json.dumps({
                "instances": [{"prompt": prompt}],
                "parameters": {
                    "sampleCount": 1,
                    "aspectRatio": "1:1" if size == "1024x1024" else "16:9",
                },
            }).encode("utf-8")

            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            # Imagen 返回 base64
            import base64
            image_data = base64.b64decode(result["predictions"][0]["bytesBase64Encoded"])
            with open(output_path, "wb") as f:
                f.write(image_data)

            return {
                "success": True,
                "path": output_path,
                "source": "Imagen",
                "prompt": prompt,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


# ================================================================
#  Veo 视频生成 (Google)
# ================================================================
class VeoAdapter(BaseAIGCAdapter):
    """Google Veo 视频生成"""

    name = "Veo"
    supports_video = True
    supports_image = False
    priority = 90

    def is_available(self) -> bool:
        return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("FAL_KEY"))

    def generate_video(self, prompt: str, output_path: str,
                       duration: int = 4, size: str = "720x1280") -> Dict:
        # Veo 需要通过 fal.ai 或直接 Google API
        # 这里简化实现，实际使用时需要更复杂的异步轮询
        log("  Veo 生成需要异步轮询，简化实现中...", "WARN")
        return {"success": False, "error": "Veo async not implemented in simplified version"}


# ================================================================
#  Sora 视频生成 (OpenAI)
# ================================================================
class SoraAdapter(BaseAIGCAdapter):
    """OpenAI Sora 视频生成"""

    name = "Sora"
    supports_video = True
    supports_image = False
    priority = 85

    def is_available(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    def generate_video(self, prompt: str, output_path: str,
                       duration: int = 4, size: str = "720x1280") -> Dict:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {"success": False, "error": "No OPENAI_API_KEY"}

        try:
            import urllib.request

            # Sora API (简化版，实际可能需要更复杂的异步处理)
            url = "https://api.openai.com/v1/video/generations"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            data = json.dumps({
                "model": "sora-2",
                "prompt": prompt,
                "duration": duration,
                "resolution": size,
            }).encode("utf-8")

            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            # 假设返回直接下载链接 (实际可能需要轮询)
            video_url = result.get("output", {}).get("url", "")
            if video_url:
                urllib.request.urlretrieve(video_url, output_path)
                return {
                    "success": True,
                    "path": output_path,
                    "source": "Sora",
                    "prompt": prompt,
                }
            else:
                return {"success": False, "error": "No video URL in response"}

        except Exception as e:
            return {"success": False, "error": str(e)}


# ================================================================
#  可灵视频生成 (Kling)
# ================================================================
class KlingAdapter(BaseAIGCAdapter):
    """快手可灵视频生成 (国内友好)"""

    name = "Kling"
    supports_video = True
    supports_image = True
    priority = 95  # 国内最高优先级

    def is_available(self) -> bool:
        return bool(os.environ.get("KLING_API_KEY"))

    def generate_video(self, prompt: str, output_path: str,
                       duration: int = 5, size: str = "720x1280") -> Dict:
        api_key = os.environ.get("KLING_API_KEY")
        if not api_key:
            return {"success": False, "error": "No KLING_API_KEY"}

        try:
            # 可灵 API 简化调用 (实际需要更复杂的签名和轮询)
            log("  可灵 API 调用 (简化版)...")
            # 这里只是一个占位实现
            # 实际可灵 API 需要:
            # 1. 生成任务
            # 2. 轮询状态
            # 3. 下载结果
            return {"success": False, "error": "Kling adapter needs full implementation"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_image(self, prompt: str, output_path: str,
                       size: str = "1024x1024") -> Dict:
        # 可灵也支持图生视频的首帧生成
        return {"success": False, "error": "Kling image gen not implemented"}


# ================================================================
#  ARK 即梦生成器 (火山方舟 - 国内首选)
# ================================================================
class ARKJimengAdapter(BaseAIGCAdapter):
    """火山方舟即梦系列 - 图片(Seedream) + 视频(Seedance) 生成"""

    name = "ARK_Jimeng"
    supports_video = True
    supports_image = True
    priority = 100  # 国内最高优先级

    # 可用模型 (2.0系列不可用，使用1.5/1.0)
    IMAGE_MODEL = "doubao-seedream-5-0-pro-260628"  # 即梦图片Pro
    VIDEO_MODEL = "doubao-seedance-1-5-pro-251128"  # 即梦视频1.5 (2.0不可用)

    def __init__(self):
        self.api_key = os.environ.get("DOUBAO_API_KEY", "")
        self.base_url = "https://ark.cn-beijing.volces.com/api/v3"

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_image(self, prompt: str, output_path: str,
                       size: str = "1024x1024") -> Dict:
        """使用即梦 Seedream 生成图片"""
        if not self.api_key:
            return {"success": False, "error": "No DOUBAO_API_KEY"}

        try:
            import urllib.request

            url = f"{self.base_url}/images/generations"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            payload = {
                "model": self.IMAGE_MODEL,
                "prompt": prompt,
                "size": size,
            }

            log(f"  ARK Seedream 生成图片: {prompt[:50]}...")
            req = urllib.request.Request(url, headers=headers, 
                                        data=json.dumps(payload).encode("utf-8"))
            
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            if "data" in result and result["data"]:
                img_url = result["data"][0].get("url", "")
                if img_url:
                    # 下载图片
                    urllib.request.urlretrieve(img_url, output_path)
                    return {
                        "success": True,
                        "path": output_path,
                        "source": "ARK_Seedream",
                        "prompt": prompt,
                        "model": self.IMAGE_MODEL,
                    }
            return {"success": False, "error": f"API返回异常: {result}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_video(self, prompt: str, output_path: str,
                       duration: int = 5, size: str = "720x1280") -> Dict:
        """使用即梦 Seedance 1.5 生成视频 (2.0不可用)"""
        if not self.api_key:
            return {"success": False, "error": "No DOUBAO_API_KEY"}

        try:
            import urllib.request

            # Seedance 视频生成 API (异步任务)
            url = f"{self.base_url}/videos/generations"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            
            # 解析尺寸
            w, h = size.split("x") if "x" in size else (720, 1280)
            
            payload = {
                "model": self.VIDEO_MODEL,
                "prompt": prompt,
                "duration": str(duration),
                "size": f"{w}x{h}",
            }

            log(f"  ARK Seedance 1.5 生成视频: {prompt[:50]}...")
            req = urllib.request.Request(url, headers=headers,
                                        data=json.dumps(payload).encode("utf-8"))
            
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            # 视频生成是异步的，返回任务ID
            task_id = result.get("id") or result.get("task_id")
            if task_id:
                # 轮询等待结果
                return self._poll_video_task(task_id, output_path, prompt)
            
            return {"success": False, "error": f"API返回异常: {result}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _poll_video_task(self, task_id: str, output_path: str, prompt: str,
                         max_wait: int = 300) -> Dict:
        """轮询视频生成任务状态"""
        import urllib.request
        
        url = f"{self.base_url}/videos/{task_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode("utf-8"))

                status = result.get("status", "")
                if status == "succeeded":
                    video_url = result.get("data", [{}])[0].get("url", "")
                    if video_url:
                        urllib.request.urlretrieve(video_url, output_path)
                        return {
                            "success": True,
                            "path": output_path,
                            "source": "ARK_Seedance",
                            "prompt": prompt,
                            "model": self.VIDEO_MODEL,
                        }
                elif status == "failed":
                    return {"success": False, "error": f"视频生成失败: {result}"}
                
                # 等待中
                log(f"  视频生成中... ({int(time.time() - start_time)}s)")
                time.sleep(10)
                
            except Exception as e:
                return {"success": False, "error": f"轮询失败: {e}"}

        return {"success": False, "error": f"视频生成超时 ({max_wait}s)"}


# ================================================================
#  模拟生成器 (用于测试/无API时)
# ================================================================
class MockAIGCAdapter(BaseAIGCAdapter):
    """模拟生成器 - 用于测试或API不可用时"""

    name = "Mock"
    supports_video = True
    supports_image = True
    priority = 0

    def is_available(self) -> bool:
        return True  # 总是可用

    def generate_video(self, prompt: str, output_path: str,
                       duration: int = 4, size: str = "720x1280") -> Dict:
        """生成一个测试视频 (纯色+文字)"""
        try:
            import subprocess

            # 使用 ffmpeg 生成一个测试视频
            w, h = size.split("x") if "x" in size else (1280, 720)
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"color=c=blue:s={w}x{h}:d={duration}",
                "-vf", f"drawtext=text='AIGC Placeholder':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
                "-c:v", "libx264", "-preset", "fast", "-crf", "28",
                "-pix_fmt", "yuv420p",
                output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0 and os.path.exists(output_path):
                return {
                    "success": True,
                    "path": output_path,
                    "source": "Mock",
                    "prompt": prompt,
                    "note": "This is a placeholder video. Set up API keys for real generation.",
                }
            else:
                return {"success": False, "error": f"ffmpeg failed: {result.stderr[:200]}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_image(self, prompt: str, output_path: str,
                       size: str = "1024x1024") -> Dict:
        """生成一个测试图片 (纯色)"""
        try:
            from PIL import Image
            w, h = size.split("x") if "x" in size else (1024, 1024)
            img = Image.new("RGB", (int(w), int(h)), color=(100, 150, 200))
            img.save(output_path)
            return {
                "success": True,
                "path": output_path,
                "source": "Mock",
                "prompt": prompt,
                "note": "This is a placeholder image. Set up API keys for real generation.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# ================================================================
#  主生成器
# ================================================================
class AIGCGenerator:
    """
    AI生成补充素材。

    当真实素材不足时，使用AI生成补充。
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.prompt_generator = PromptGenerator()

        # 注册适配器 (按优先级排序)
        self.adapters: List[BaseAIGCAdapter] = [
            ARKJimengAdapter(),   # P0: ARK即梦 (国内首选, 已配置)
            KlingAdapter(),       # P1: 可灵 (国内备选)
            VeoAdapter(),         # P2: Google Veo
            SoraAdapter(),        # P3: OpenAI Sora
            DALLEAdapter(),       # P4: DALL-E 图片
            ImagenAdapter(),      # P5: Imagen 图片
            MockAIGCAdapter(),    # P-1: 模拟 (兜底)
        ]

    def generate_supplementary(self, user_prompt: str,
                               missing_count: int = 1,
                               style: str = "cinematic",
                               material_type: str = "video") -> List[Dict]:
        """
        生成补充素材。

        Args:
            user_prompt: 用户描述
            missing_count: 需要生成的数量
            style: 风格
            material_type: "video" 或 "image"

        Returns:
            生成结果列表
        """
        print(f"\n--- AIGCGenerator: AI生成补充素材 ---")
        log(f"需求: {missing_count} 个 {material_type}, 风格={style}")

        results = []

        # 生成提示词
        if material_type == "video":
            prompt = self.prompt_generator.generate_video_prompt(user_prompt, style)
        else:
            prompt = self.prompt_generator.generate_image_prompt(user_prompt, style)

        log(f"英文提示词: {prompt[:80]}...")

        # 找到可用的适配器
        available_adapters = [a for a in self.adapters if a.is_available()]
        if not available_adapters:
            log("无可用AI生成服务", "ERROR")
            return []

        # 选择最佳适配器
        best_adapter = available_adapters[0]
        log(f"使用: {best_adapter.name}")

        # 生成
        for i in range(missing_count):
            timestamp = int(time.time())
            if material_type == "video":
                output_path = str(self.output_dir / f"aigc_{best_adapter.name.lower()}_{timestamp}_{i}.mp4")
                if best_adapter.supports_video:
                    result = best_adapter.generate_video(prompt, output_path)
                else:
                    log(f"{best_adapter.name} 不支持视频，尝试图片", "WARN")
                    output_path = str(self.output_dir / f"aigc_{best_adapter.name.lower()}_{timestamp}_{i}.png")
                    result = best_adapter.generate_image(prompt, output_path)
            else:
                output_path = str(self.output_dir / f"aigc_{best_adapter.name.lower()}_{timestamp}_{i}.png")
                if best_adapter.supports_image:
                    result = best_adapter.generate_image(prompt, output_path)
                else:
                    result = {"success": False, "error": "Adapter does not support image"}

            if result.get("success"):
                log(f"  生成成功: {Path(result['path']).name}")
                results.append(result)
            else:
                log(f"  生成失败: {result.get('error', 'Unknown')}", "WARN")

        log(f"AI生成完成: {len(results)}/{missing_count}")
        return results

    def list_available_services(self) -> List[Dict]:
        """列出所有可用的AI生成服务"""
        services = []
        for adapter in self.adapters:
            services.append({
                "name": adapter.name,
                "available": adapter.is_available(),
                "supports_video": adapter.supports_video,
                "supports_image": adapter.supports_image,
                "priority": adapter.priority,
            })
        return services


# ================================================================
#  快捷函数
# ================================================================
def generate_materials(user_prompt: str, missing_count: int = 1,
                       style: str = "cinematic", material_type: str = "video") -> List[Dict]:
    """快捷函数：生成补充素材"""
    generator = AIGCGenerator()
    return generator.generate_supplementary(user_prompt, missing_count, style, material_type)


if __name__ == "__main__":
    print("=" * 60)
    print("  AIGCGenerator - AI生成测试")
    print("=" * 60)

    generator = AIGCGenerator()

    # 显示可用服务
    print("\n可用AI生成服务:")
    for svc in generator.list_available_services():
        avail = "✅" if svc["available"] else "❌"
        v = "V" if svc["supports_video"] else "-"
        i = "I" if svc["supports_image"] else "-"
        print(f"  {avail} {svc['name']:10} 视频={v} 图片={i} 优先级={svc['priority']}")

    # 测试提示词生成
    print("\n提示词生成测试:")
    test_prompts = [
        "利威尔高燃混剪",
        "冰海战记电影感",
        "古风唯美意境",
    ]
    for p in test_prompts:
        vp = generator.prompt_generator.generate_video_prompt(p)
        ip = generator.prompt_generator.generate_image_prompt(p)
        print(f"\n  '{p}'")
        print(f"    视频: {vp[:100]}...")
        print(f"    图片: {ip[:100]}...")

    # 测试生成 (如果有API Key则真实生成，否则用Mock)
    print("\n--- 生成测试 ---")
    results = generator.generate_supplementary(
        user_prompt="cinematic nature scene",
        missing_count=1,
        material_type="video",
    )
    print(f"\n生成结果: {len(results)} 个")
    for r in results:
        print(f"  - {r.get('source')}: {r.get('path')}")
        if "note" in r:
            print(f"    注意: {r['note']}")
