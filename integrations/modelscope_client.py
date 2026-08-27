"""ModelScope 统一推理客户端
========================
正确对接 api-inference.modelscope.cn/v1 的 OpenAI 兼容接口。
关键发现 (2026-07-29 实测):
  - 非流式模式返回 choices=null，必须使用 stream=True
  - 模型ID格式: "Qwen/Qwen3-235B-A22B" (带org前缀)
  - Embedding API 不支持 bge-m3，需本地部署或用 DashScope
"""
from __future__ import annotations

import json
import os
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------

def _load_env() -> Dict[str, str]:
    """从 .env 文件加载配置"""
    env_path = Path(__file__).parent.parent / ".env"
    config = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
    # 环境变量优先
    for key in ["MODELSCOPE_API_KEY", "MODELSCOPE_BASE_URL", "MODELSCOPE_MODEL",
                "MODELSCOPE_FLASH_MODEL", "MODELSCOPE_VISION_MODEL"]:
        if os.environ.get(key):
            config[key] = os.environ[key]
    return config


_ENV = _load_env()

DEFAULT_BASE_URL = _ENV.get("MODELSCOPE_BASE_URL", "https://api-inference.modelscope.cn/v1")
DEFAULT_API_KEY = _ENV.get("MODELSCOPE_API_KEY", "")
DEFAULT_MODEL = _ENV.get("MODELSCOPE_MODEL", "Qwen/Qwen3-235B-A22B")
FLASH_MODEL = _ENV.get("MODELSCOPE_FLASH_MODEL", "Qwen/Qwen3-8B")
VISION_MODEL = _ENV.get("MODELSCOPE_VISION_MODEL", "Qwen/Qwen3-VL-235B-A22B-Instruct")


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ChatResponse:
    content: str
    model: str
    reasoning_content: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    raw_chunks: int = 0


@dataclass
class VisionResponse:
    content: str
    model: str
    reasoning_content: str = ""
    usage: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 核心客户端
# ---------------------------------------------------------------------------

class ModelScopeClient:
    """ModelScope 推理 API 统一客户端 (流式模式)"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: int = 120,
    ):
        self.api_key = api_key or DEFAULT_API_KEY
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.default_model = default_model or DEFAULT_MODEL
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        # 统计
        self.total_calls = 0
        self.total_tokens = 0
        self.total_errors = 0

    def _url(self, endpoint: str) -> str:
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    # ------------------------------------------------------------------
    # Chat Completions (流式)
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> ChatResponse:
        """发送聊天请求，自动使用流式模式并聚合结果"""
        model = model or self.default_model

        # 构建消息列表
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": model,
            "messages": full_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,  # 必须流式
        }

        self.total_calls += 1
        try:
            resp = self._session.post(
                self._url("chat/completions"),
                json=payload,
                stream=True,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return self._parse_stream(resp, model)
        except requests.exceptions.RequestException as e:
            self.total_errors += 1
            logger.error(f"ModelScope chat error: {e}")
            return ChatResponse(
                content=f"[ERROR] {e}",
                model=model,
                usage={"error": 1},
            )

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """流式生成器，逐token返回"""
        model = model or self.default_model
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": model,
            "messages": full_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        self.total_calls += 1
        try:
            resp = self._session.post(
                self._url("chat/completions"),
                json=payload,
                stream=True,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    choices = chunk.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                except json.JSONDecodeError:
                    continue
        except requests.exceptions.RequestException as e:
            self.total_errors += 1
            yield f"[ERROR] {e}"

    def _parse_stream(self, resp: requests.Response, model: str) -> ChatResponse:
        """解析流式响应，聚合为完整结果"""
        content_parts = []
        reasoning_parts = []
        usage = {}
        chunk_count = 0

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                chunk_count += 1
                choices = chunk.get("choices") or []
                if choices:
                    delta = choices[0].get("delta", {})
                    if delta.get("content"):
                        content_parts.append(delta["content"])
                    if delta.get("reasoning_content"):
                        reasoning_parts.append(delta["reasoning_content"])
                # 最后一个chunk通常有usage
                if chunk.get("usage") and chunk["usage"].get("total_tokens"):
                    usage = chunk["usage"]
            except json.JSONDecodeError:
                continue

        return ChatResponse(
            content="".join(content_parts),
            model=model,
            reasoning_content="".join(reasoning_parts),
            usage=usage,
            raw_chunks=chunk_count,
        )

    # ------------------------------------------------------------------
    # Vision (多模态)
    # ------------------------------------------------------------------

    def vision(
        self,
        image_url: str,
        prompt: str = "请描述这张图片的内容",
        model: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> VisionResponse:
        """视觉理解：分析图片内容"""
        model = model or VISION_MODEL
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": prompt},
            ]
        }]

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }

        self.total_calls += 1
        try:
            resp = self._session.post(
                self._url("chat/completions"),
                json=payload,
                stream=True,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            result = self._parse_stream(resp, model)
            return VisionResponse(
                content=result.content,
                model=model,
                reasoning_content=result.reasoning_content,
                usage=result.usage,
            )
        except requests.exceptions.RequestException as e:
            self.total_errors += 1
            return VisionResponse(content=f"[ERROR] {e}", model=model)

    # ------------------------------------------------------------------
    # 便捷方法
    # ------------------------------------------------------------------

    def quick(self, prompt: str, model: Optional[str] = None) -> str:
        """快速单轮对话"""
        resp = self.chat(
            [{"role": "user", "content": prompt}],
            model=model or FLASH_MODEL,
            max_tokens=1024,
        )
        return resp.content

    def analyze_video_frame(self, frame_path: str, prompt: str = "分析这个视频帧") -> str:
        """分析视频帧（本地文件转base64）"""
        import base64
        path = Path(frame_path)
        if not path.exists():
            return f"[ERROR] File not found: {frame_path}"

        suffix = path.suffix.lower().lstrip(".")
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(suffix, "jpeg")
        b64 = base64.b64encode(path.read_bytes()).decode()
        data_url = f"data:image/{mime};base64,{b64}"

        result = self.vision(data_url, prompt)
        return result.content

    def get_stats(self) -> Dict[str, Any]:
        """获取客户端统计"""
        return {
            "total_calls": self.total_calls,
            "total_tokens": self.total_tokens,
            "total_errors": self.total_errors,
            "error_rate": self.total_errors / max(self.total_calls, 1),
            "base_url": self.base_url,
            "default_model": self.default_model,
        }

    def health_check(self) -> Dict[str, Any]:
        """健康检查：验证API连通性"""
        start = time.time()
        try:
            resp = self._session.get(self._url("models"), timeout=10)
            latency = time.time() - start
            if resp.status_code == 200:
                data = resp.json()
                models = [m["id"] for m in data.get("data", [])]
                return {
                    "status": "healthy",
                    "latency_ms": round(latency * 1000),
                    "available_models": len(models),
                    "sample_models": models[:5],
                }
            return {"status": "error", "code": resp.status_code, "latency_ms": round(latency * 1000)}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_global_client: Optional[ModelScopeClient] = None


def get_client() -> ModelScopeClient:
    """获取全局客户端单例"""
    global _global_client
    if _global_client is None:
        _global_client = ModelScopeClient()
    return _global_client


def reset_client():
    """重置全局客户端（测试用）"""
    global _global_client
    _global_client = None


# ---------------------------------------------------------------------------
# CLI 验证
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = ModelScopeClient()

    print("=" * 60)
    print("ModelScope 统一客户端验证")
    print("=" * 60)

    # 1. 健康检查
    print("\n[1] 健康检查...")
    health = client.health_check()
    print(f"    状态: {health['status']}")
    if health["status"] == "healthy":
        print(f"    延迟: {health['latency_ms']}ms")
        print(f"    可用模型: {health['available_models']}个")

    # 2. 快速对话
    print("\n[2] 快速对话测试 (Qwen3-8B)...")
    answer = client.quick("用一句话介绍After Effects")
    print(f"    回答: {answer[:100]}...")

    # 3. 统计
    print("\n[3] 客户端统计:")
    stats = client.get_stats()
    for k, v in stats.items():
        print(f"    {k}: {v}")

    print("\n" + "=" * 60)
    print("验证完成")
