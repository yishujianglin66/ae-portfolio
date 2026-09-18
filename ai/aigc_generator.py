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

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output_director" / "materials"


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


# --- SSRF 防护 (Mimosa 修复): 只允许已知生成服务域, 拒绝内网/回环地址 ---
_API_HOSTS = {
    "api.openai.com", "generativelanguage.googleapis.com", "queue.fal.run",
    "api.klingai.com", "open.kuaishou.com", "api.pika.style", "api.stability.ai",
    "dashscope.aliyuncs.com",
}

# 本地服务显式白名单（2026-09-09 修复：ComfyUI 本地通道从未可达）。
# ComfyUIAdapter 的目标是本机 ComfyUI（127.0.0.1:8188），属显式配置的本地
# 服务而非外部输入；此前 _validate_url 把 loopback 一律拒绝，导致
# is_available() 恒为 False，"ComfyUI 一开自动升级"链路从未生效。
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _validate_url(url: str) -> str:
    """校验外呼 URL。

    - 外部域名：仅 https 白名单，解析后拒绝私网/回环/链路本地/保留地址；
    - 本地服务（127.0.0.1/localhost/::1）：仅允许 http，端口须为已知本地服务
      （ComfyUI 8188）。其余一律拒绝。
    """
    import ipaddress
    import socket
    import urllib.parse
    pu = urllib.parse.urlparse(str(url))
    if pu.scheme not in ("https", "http") or not pu.hostname:
        raise ValueError(f"拒绝非 http(s) URL: {url!r}")
    host = pu.hostname.lower()
    if host in _LOCAL_HOSTS:
        # 本地 ComfyUI 通道：仅 http + 已知端口
        if pu.scheme != "http" or pu.port not in (8188,):
            raise ValueError(f"拒绝非法本地服务地址: {url!r}")
        return str(url)
    if host not in _API_HOSTS:
        raise ValueError(f"拒绝非白名单域: {pu.hostname}")
    for info in socket.getaddrinfo(pu.hostname, pu.port or (443 if pu.scheme == "https" else 80)):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError(f"拒绝解析到内网地址: {pu.hostname} -> {ip}")
    return str(url)


def _safe_urlopen(req, timeout: float):
    # 2026-09-09 修复：原实现递归调用自身（重构事故），任何调用都会
    # RecursionError 且被上层 except 吞掉 → 全部适配器（含 ComfyUI 本地
    # 通道）从未真正发出过请求。改为经 opener 发起（URL 先过 _validate_url）。
    _validate_url(req.full_url)
    return urllib.request.build_opener().open(req, timeout=timeout)


def _safe_download(url: str, output_path: str):
    """校验 URL + 约束落盘路径在项目素材目录内"""
    _validate_url(url)
    out = Path(output_path).resolve()
    if OUTPUT_DIR not in out.parents and out.parent != OUTPUT_DIR:
        raise ValueError(f"拒绝越界输出路径: {output_path}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, str(out))
    return str(out)


def _safe_output_path(output_path: str) -> str:
    """约束落盘路径在项目素材目录内 (Mimosa: 防路径穿越)"""
    out = Path(output_path).resolve()
    if OUTPUT_DIR not in out.parents and out.parent != OUTPUT_DIR:
        raise ValueError(f"拒绝越界输出路径: {output_path}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return str(out)


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
                       duration: int = 4, size: str = "720x1280") -> dict:
        raise NotImplementedError

    def generate_image(self, prompt: str, output_path: str,
                       size: str = "1024x1024") -> dict:
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
                       size: str = "1024x1024") -> dict:
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
            with _safe_urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            image_url = result["data"][0]["url"]

            # 下载图片
            _safe_download(image_url, output_path)

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
                       size: str = "1024x1024") -> dict:
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
            with _safe_urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            # Imagen 返回 base64
            import base64
            image_data = base64.b64decode(result["predictions"][0]["bytesBase64Encoded"])
            output_path = _safe_output_path(output_path)
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
#  Veo 视频生成 (Google via fal.ai)
# ================================================================
class VeoAdapter(BaseAIGCAdapter):
    """Google Veo 视频生成 — 通过 fal.ai 异步调用"""

    name = "Veo"
    supports_video = True
    supports_image = False
    priority = 90

    def is_available(self) -> bool:
        return bool(os.environ.get("FAL_KEY") or os.environ.get("GEMINI_API_KEY"))

    def generate_video(self, prompt: str, output_path: str,
                       duration: int = 4, size: str = "720x1280") -> dict:
        api_key = os.environ.get("FAL_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return {"success": False, "error": "No FAL_KEY or GEMINI_API_KEY"}

        try:
            import urllib.request

            # 解析尺寸
            w, h = size.split("x") if "x" in size else (720, 1280)

            if os.environ.get("FAL_KEY"):
                return self._via_fal(api_key, prompt, output_path, duration, w, h)
            else:
                return self._via_gemini(api_key, prompt, output_path, duration, w, h)

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _via_fal(self, api_key: str, prompt: str, output_path: str,
                 duration: int, w: int, h: int) -> dict:
        """通过 fal.ai 调用 Veo"""
        import urllib.request

        # Step 1: 提交生成任务
        url = "https://queue.fal.run/fal-ai/veo/v1/fast"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Key {api_key}",
        }
        payload = {
            "prompt": prompt,
            "num_frames": min(duration * 24, 120),
            "aspect_ratio": f"{w}:{h}" if w > h else f"{h}:{w}",
        }

        log(f"  fal.ai Veo 提交任务: {prompt[:50]}...")
        req = urllib.request.Request(url, headers=headers,
                                     data=json.dumps(payload).encode("utf-8"), method="POST")
        with _safe_urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # fal 可能直接返回或返回 request_id
        if "video" in result and result["video"].get("url"):
            video_url = result["video"]["url"]
            _safe_download(video_url, output_path)
            return {"success": True, "path": output_path, "source": "Veo(fal)", "prompt": prompt}

        request_id = result.get("request_id", "")
        if not request_id:
            return {"success": False, "error": f"fal.ai 返回异常: {result}"}

        # Step 2: 轮询等待
        return self._poll_fal(api_key, request_id, output_path, prompt)

    def _poll_fal(self, api_key: str, request_id: str, output_path: str,
                  prompt: str, max_wait: int = 300) -> dict:
        """轮询 fal.ai 任务状态"""
        import urllib.request

        url = f"https://queue.fal.run/fal-ai/veo/v1/fast/requests/{request_id}"
        headers = {"Authorization": f"Key {api_key}"}
        start = time.time()

        while time.time() - start < max_wait:
            try:
                req = urllib.request.Request(url, headers=headers)
                with _safe_urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode("utf-8"))

                status = result.get("status", "")
                if status == "COMPLETED":
                    video_url = result.get("video", {}).get("url", "")
                    if video_url:
                        _safe_download(video_url, output_path)
                        return {"success": True, "path": output_path, "source": "Veo(fal)", "prompt": prompt}
                    return {"success": False, "error": "Completed but no video URL"}
                elif status in ("FAILED", "CANCELLED"):
                    return {"success": False, "error": f"fal.ai 任务{status}: {result}"}

                log(f"  Veo 生成中... ({int(time.time() - start)}s)")
                time.sleep(15)
            except Exception as e:
                return {"success": False, "error": f"轮询失败: {e}"}

        return {"success": False, "error": f"Veo 生成超时 ({max_wait}s)"}

    def _via_gemini(self, api_key: str, prompt: str, output_path: str,
                    duration: int, w: int, h: int) -> dict:
        """通过 Google Gemini/Vertex API 调用 Veo"""
        import urllib.request

        url = f"https://generativelanguage.googleapis.com/v1beta/models/veo-2:predict?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "durationSeconds": duration,
                "aspectRatio": "16:9" if w > h else "9:16",
            },
        }

        log(f"  Gemini Veo 提交: {prompt[:50]}...")
        req = urllib.request.Request(url, headers=headers,
                                     data=json.dumps(payload).encode("utf-8"), method="POST")
        with _safe_urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # Veo via Gemini 返回 operation name
        op_name = result.get("name", "")
        if not op_name:
            return {"success": False, "error": f"Gemini Veo 返回异常: {result}"}

        # 轮询 operation
        return self._poll_gemini(api_key, op_name, output_path, prompt)

    def _poll_gemini(self, api_key: str, op_name: str, output_path: str,
                     prompt: str, max_wait: int = 300) -> dict:
        """轮询 Gemini Veo operation"""
        import base64
        import urllib.request

        url = f"https://generativelanguage.googleapis.com/v1beta/{op_name}?key={api_key}"
        start = time.time()

        while time.time() - start < max_wait:
            try:
                req = urllib.request.Request(url)
                with _safe_urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode("utf-8"))

                if result.get("done"):
                    videos = result.get("response", {}).get("generateVideoResponse", {}).get("generatedSamples", [])
                    if videos:
                        video_data = videos[0].get("video", {})
                        if video_data.get("uri"):
                            _safe_download(video_data["uri"], output_path)
                        elif video_data.get("bytesBase64Encoded"):
                            output_path = _safe_output_path(output_path)
                            with open(output_path, "wb") as f:
                                f.write(base64.b64decode(video_data["bytesBase64Encoded"]))
                        return {"success": True, "path": output_path, "source": "Veo(Gemini)", "prompt": prompt}
                    return {"success": False, "error": "Done but no video"}

                log(f"  Veo(Gemini) 生成中... ({int(time.time() - start)}s)")
                time.sleep(15)
            except Exception as e:
                return {"success": False, "error": f"轮询失败: {e}"}

        return {"success": False, "error": f"Veo(Gemini) 超时 ({max_wait}s)"}


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
                       duration: int = 4, size: str = "720x1280") -> dict:
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
            with _safe_urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            # 假设返回直接下载链接 (实际可能需要轮询)
            video_url = result.get("output", {}).get("url", "")
            if video_url:
                _safe_download(video_url, output_path)
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
#  可灵视频生成 (Kling) — 完整异步实现
# ================================================================
class KlingAdapter(BaseAIGCAdapter):
    """快手可灵视频生成 (国内首选) — 完整异步任务+轮询+下载"""

    name = "Kling"
    supports_video = True
    supports_image = True
    priority = 95  # 国内最高优先级

    KLING_BASE_URL = "https://api.klingai.com/v1"

    def is_available(self) -> bool:
        return bool(os.environ.get("KLING_API_KEY"))

    def _headers(self, api_key: str) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    def generate_video(self, prompt: str, output_path: str,
                       duration: int = 5, size: str = "720x1280") -> dict:
        api_key = os.environ.get("KLING_API_KEY")
        if not api_key:
            return {"success": False, "error": "No KLING_API_KEY"}

        try:
            import urllib.request

            # 解析尺寸
            w, h = size.split("x") if "x" in size else (720, 1280)

            # Step 1: 创建视频生成任务
            url = f"{self.KLING_BASE_URL}/videos/text2video"
            payload = {
                "model_name": "kling-v1",
                "prompt": prompt,
                "duration": str(min(duration, 10)),  # 可灵最长10s
                "aspect_ratio": "16:9" if w > h else "9:16",
                "mode": "std",  # standard mode for speed
            }

            log(f"  可灵 提交视频任务: {prompt[:50]}...")
            req = urllib.request.Request(url, headers=self._headers(api_key),
                                         data=json.dumps(payload).encode("utf-8"), method="POST")
            with _safe_urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            task_id = result.get("data", {}).get("task_id", "")
            if not task_id:
                return {"success": False, "error": f"可灵返回异常: {result}"}

            # Step 2: 轮询任务状态
            return self._poll_task(api_key, task_id, output_path, prompt)

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            return {"success": False, "error": f"可灵HTTP {e.code}: {body}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _poll_task(self, api_key: str, task_id: str, output_path: str,
                   prompt: str, max_wait: int = 600) -> dict:
        """轮询可灵任务状态"""
        import urllib.request

        url = f"{self.KLING_BASE_URL}/videos/text2video/{task_id}"
        start = time.time()

        while time.time() - start < max_wait:
            try:
                req = urllib.request.Request(url, headers=self._headers(api_key))
                with _safe_urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode("utf-8"))

                data = result.get("data", {})
                status = data.get("task_status", "")

                if status == "succeed":
                    # 获取视频URL
                    videos = data.get("task_result", {}).get("videos", [])
                    if videos:
                        video_url = videos[0].get("url", "")
                        if video_url:
                            _safe_download(video_url, output_path)
                            return {
                                "success": True,
                                "path": output_path,
                                "source": "Kling",
                                "prompt": prompt,
                                "duration": data.get("task_result", {}).get("videos", [{}])[0].get("duration", 0),
                            }
                    return {"success": False, "error": "可灵完成但无视频URL"}
                elif status == "failed":
                    return {"success": False, "error": f"可灵任务失败: {data.get('task_status_msg', '')}"}

                log(f"  可灵生成中... ({int(time.time() - start)}s, status={status})")
                time.sleep(10)

            except Exception as e:
                log(f"  可灵轮询异常: {e}", "WARN")
                time.sleep(10)

        return {"success": False, "error": f"可灵超时 ({max_wait}s)"}

    def generate_image(self, prompt: str, output_path: str,
                       size: str = "1024x1024") -> dict:
        """可灵图片生成 (用于图生视频首帧)"""
        api_key = os.environ.get("KLING_API_KEY")
        if not api_key:
            return {"success": False, "error": "No KLING_API_KEY"}

        try:
            import urllib.request

            w, h = size.split("x") if "x" in size else (1024, 1024)

            url = f"{self.KLING_BASE_URL}/images/generations"
            payload = {
                "model_name": "kling-v1",
                "prompt": prompt,
                "width": w,
                "height": h,
                "n": 1,
            }

            log(f"  可灵 生成图片: {prompt[:50]}...")
            req = urllib.request.Request(url, headers=self._headers(api_key),
                                         data=json.dumps(payload).encode("utf-8"), method="POST")
            with _safe_urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            images = result.get("data", {}).get("images", [])
            if images:
                img_url = images[0].get("url", "")
                if img_url:
                    _safe_download(img_url, output_path)
                    return {"success": True, "path": output_path, "source": "Kling", "prompt": prompt}

            return {"success": False, "error": f"可灵图片返回异常: {result}"}

        except Exception as e:
            return {"success": False, "error": str(e)}


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
                       size: str = "1024x1024") -> dict:
        """使用即梦 Seedream 生成图片

        注意：图像生成为临时直连 ARK API，统一网关尚未覆盖图像生成接口，待网关扩展后迁移。
        """
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
            
            with _safe_urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            if "data" in result and result["data"]:
                img_url = result["data"][0].get("url", "")
                if img_url:
                    # 下载图片
                    _safe_download(img_url, output_path)
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
                       duration: int = 5, size: str = "720x1280") -> dict:
        """使用即梦 Seedance 1.5 生成视频 (2.0不可用)

        注意：视频生成为临时直连 ARK API（含异步任务轮询），统一网关尚未覆盖，待网关扩展后迁移。
        """
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
            
            with _safe_urlopen(req, timeout=30) as resp:
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
                         max_wait: int = 300) -> dict:
        """轮询视频生成任务状态"""
        import urllib.request
        
        url = f"{self.base_url}/videos/{task_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                req = urllib.request.Request(url, headers=headers)
                with _safe_urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode("utf-8"))

                status = result.get("status", "")
                if status == "succeeded":
                    video_url = result.get("data", [{}])[0].get("url", "")
                    if video_url:
                        _safe_download(video_url, output_path)
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
#  ComfyUI 本地 GPU 生成 (开源模型: Wan 2.2 / HunyuanVideo / LTX)
# ================================================================
class ComfyUIAdapter(BaseAIGCAdapter):
    """ComfyUI 本地 GPU 生成 — 零成本、完全离线可用"""

    name = "ComfyUI"
    supports_video = True
    supports_image = True
    priority = 98  # 本地免费最高优先级

    # ComfyUI 本地 API 地址
    COMFYUI_URL = "http://127.0.0.1:8188"

    # 内置工作流模板
    WORKFLOW_TEMPLATES = {
        "video_wan": {
            "class_type": "WanVideoGenerator",
            "inputs": {"prompt": "", "width": 720, "height": 1280, "frames": 81, "model": "wan2.2"},
        },
        "video_hunyuan": {
            "class_type": "HunyuanVideoGenerator",
            "inputs": {"prompt": "", "width": 720, "height": 720, "frames": 61, "model": "hunyuan-video"},
        },
        "video_ltx": {
            "class_type": "LTXVideoGenerator",
            "inputs": {"prompt": "", "width": 720, "height": 1280, "frames": 121, "model": "ltx-video"},
        },
        "image_sdxl": {
            "class_type": "KSampler",
            "inputs": {"prompt": "", "width": 1024, "height": 1024, "steps": 20, "model": "sd_xl"},
        },
        "image_flux": {
            "class_type": "FluxGenerator",
            "inputs": {"prompt": "", "width": 1024, "height": 1024, "steps": 20, "model": "flux-dev"},
        },
    }

    def __init__(self):
        self.comfyui_url = os.environ.get("COMFYUI_URL", self.COMFYUI_URL)

    def is_available(self) -> bool:
        """检查 ComfyUI 是否在本地运行"""
        try:
            import urllib.request
            url = f"{self.comfyui_url}/system_stats"
            req = urllib.request.Request(url)
            with _safe_urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate_video(self, prompt: str, output_path: str,
                       duration: int = 5, size: str = "720x1280") -> dict:
        if not self.is_available():
            return {"success": False, "error": "ComfyUI not running on " + self.comfyui_url}

        try:
            import urllib.request

            w, h = size.split("x") if "x" in size else (720, 1280)
            frames = min(duration * 16 + 1, 121)  # 16fps

            # 选择最佳模型工作流
            workflow = self._build_video_workflow(prompt, w, h, frames)

            # 提交到 ComfyUI
            prompt_id = self._queue_prompt(workflow)
            if not prompt_id:
                return {"success": False, "error": "Failed to queue prompt"}

            # 等待完成
            result = self._wait_for_completion(prompt_id, max_wait=600)
            if not result:
                return {"success": False, "error": "ComfyUI generation timeout"}

            # 下载输出文件
            output_images = result.get("outputs", {})
            for node_id, node_output in output_images.items():
                if "videos" in node_output:
                    video_file = node_output["videos"][0]
                    return self._download_output(video_file, output_path, prompt)
                if "images" in node_output:
                    # 某些工作流输出为图片序列，需要拼接
                    return self._download_and_stitch(node_output["images"], output_path, prompt)

            return {"success": False, "error": "No video output from ComfyUI"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_image(self, prompt: str, output_path: str,
                       size: str = "1024x1024") -> dict:
        if not self.is_available():
            return {"success": False, "error": "ComfyUI not running"}

        try:
            w, h = size.split("x") if "x" in size else (1024, 1024)
            workflow = self._build_image_workflow(prompt, w, h)

            prompt_id = self._queue_prompt(workflow)
            if not prompt_id:
                return {"success": False, "error": "Failed to queue prompt"}

            result = self._wait_for_completion(prompt_id, max_wait=120)
            if not result:
                return {"success": False, "error": "ComfyUI image gen timeout"}

            output_images = result.get("outputs", {})
            for node_id, node_output in output_images.items():
                if "images" in node_output:
                    img_file = node_output["images"][0]
                    return self._download_output(img_file, output_path, prompt)

            return {"success": False, "error": "No image output"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _build_video_workflow(self, prompt: str, w: int, h: int, frames: int) -> dict:
        """构建视频生成工作流 (优先 Wan 2.2 > HunyuanVideo > LTX)"""
        # 使用 Wan 2.2 作为默认 (画质最好、开源第一梯队)
        return {
            "prompt": {
                "1": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
                "2": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "wan2.2_14b.gguf"}},
                "3": {"class_type": "EmptyLatentVideo", "inputs": {"width": w, "height": h, "length": frames, "batch_size": 1}},
                "4": {"class_type": "KSampler", "inputs": {
                    "model": ["2", 0], "positive": ["1", 0], "negative": ["5", 0],
                    "latent_image": ["3", 0], "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal",
                }},
                "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, distorted", "clip": ["2", 0]}},
                "6": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["2", 1]}},
                "7": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["6", 0], "frame_rate": 16, "format": "video/h264-mp4"}},
            }
        }

    def _build_image_workflow(self, prompt: str, w: int, h: int) -> dict:
        """构建图片生成工作流 (优先 Flux > SDXL)"""
        return {
            "prompt": {
                "1": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
                "2": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "flux-dev-fp8.safetensors"}},
                "3": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
                "4": {"class_type": "KSampler", "inputs": {
                    "model": ["2", 0], "positive": ["1", 0], "negative": ["5", 0],
                    "latent_image": ["3", 0], "steps": 20, "cfg": 3.5, "sampler_name": "euler", "scheduler": "simple",
                }},
                "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality", "clip": ["2", 0]}},
                "6": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["2", 1]}},
                "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "aigc"}},
            }
        }

    def _queue_prompt(self, workflow: dict) -> str:
        """提交工作流到 ComfyUI 队列"""
        import urllib.request
        data = json.dumps(workflow).encode("utf-8")
        req = urllib.request.Request(
            f"{self.comfyui_url}/prompt",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _safe_urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("prompt_id", "")

    def _wait_for_completion(self, prompt_id: str, max_wait: int = 300) -> dict | None:
        """等待 ComfyUI 任务完成"""
        import urllib.request
        start = time.time()
        while time.time() - start < max_wait:
            try:
                req = urllib.request.Request(f"{self.comfyui_url}/history/{prompt_id}")
                with _safe_urlopen(req, timeout=10) as resp:
                    history = json.loads(resp.read().decode("utf-8"))
                if prompt_id in history:
                    entry = history[prompt_id]
                    if entry.get("status", {}).get("completed", False) or entry.get("outputs"):
                        return entry
                time.sleep(5)
            except Exception:
                time.sleep(5)
        return None

    def _download_output(self, file_info: dict, output_path: str, prompt: str) -> dict:
        """下载 ComfyUI 输出文件"""
        import urllib.request
        filename = file_info.get("filename", "")
        subfolder = file_info.get("subfolder", "")
        file_type = file_info.get("type", "output")
        url = f"{self.comfyui_url}/view?filename={filename}&subfolder={subfolder}&type={file_type}"
        _safe_download(url, output_path)
        return {"success": True, "path": output_path, "source": "ComfyUI", "prompt": prompt}

    def _download_and_stitch(self, images: list[dict], output_path: str, prompt: str) -> dict:
        """下载图片序列并用 ffmpeg 拼接为视频"""
        import subprocess
        import tempfile

        tmpdir = tempfile.mkdtemp(prefix="comfy_stitch_")
        for i, img_info in enumerate(images):
            img_path = os.path.join(tmpdir, f"frame_{i:04d}.png")
            self._download_output(img_info, img_path, prompt)

        # ffmpeg 拼接
        cmd = [
            "ffmpeg", "-y", "-framerate", "16",
            "-i", os.path.join(tmpdir, "frame_%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and os.path.exists(output_path):
            return {"success": True, "path": output_path, "source": "ComfyUI(stitch)", "prompt": prompt}
        return {"success": False, "error": "ffmpeg stitch failed"}

    def get_available_models(self) -> list[str]:
        """获取 ComfyUI 已安装的模型列表"""
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.comfyui_url}/object_info/CheckpointLoaderSimple")
            with _safe_urlopen(req, timeout=10) as resp:
                info = json.loads(resp.read().decode("utf-8"))
            return info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
        except Exception:
            return []


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
                       duration: int = 4, size: str = "720x1280") -> dict:
        """生成一个测试视频 (纯色+文字)"""
        try:
            import subprocess

            # 使用 ffmpeg 生成一个测试视频
            w, h = size.split("x") if "x" in size else (1280, 720)
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"color=c=blue:s={w}x{h}:d={duration}",
                "-vf", "drawtext=text='AIGC Placeholder':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
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
                       size: str = "1024x1024") -> dict:
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

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.prompt_generator = PromptGenerator()

        # 注册适配器 (按优先级排序: 本地免费 > 云端国内 > 云端海外 > 图片 > 模拟)
        self.adapters: list[BaseAIGCAdapter] = [
            ComfyUIAdapter(),   # P0: ComfyUI 本地 GPU (零成本、离线可用)
            ARKJimengAdapter(), # P1: ARK即梦 (国内云端首选)
            KlingAdapter(),     # P2: 可灵 (国内云端备选)
            VeoAdapter(),       # P3: Google Veo (fal.ai/Gemini)
            SoraAdapter(),      # P4: OpenAI Sora
            DALLEAdapter(),     # P5: DALL-E 图片
            ImagenAdapter(),    # P6: Imagen 图片
            MockAIGCAdapter(),  # P-1: 模拟 (兆底)
        ]

    def generate_supplementary(self, user_prompt: str,
                               missing_count: int = 1,
                               style: str = "cinematic",
                               material_type: str = "video") -> list[dict]:
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
        print("\n--- AIGCGenerator: AI生成补充素材 ---")
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

    def list_available_services(self) -> list[dict]:
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
                       style: str = "cinematic", material_type: str = "video") -> list[dict]:
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
