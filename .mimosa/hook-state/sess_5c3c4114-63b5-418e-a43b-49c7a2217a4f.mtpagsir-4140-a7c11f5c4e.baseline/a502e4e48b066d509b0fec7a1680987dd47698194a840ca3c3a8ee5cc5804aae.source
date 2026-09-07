"""core/llm_chain.py — LLM 多模型自动切换链（额度耗尽自动降级，不断层）

用户指令（2026-09-01）: "当模型的免费额度用完自动切换其他模型可用的有额度的调用，
不导致任务的断层"。

链序（按交接文档 2.4 节）:
  1. dashscope  qwen-vl-max      (DASHSCOPE_API_KEY)     主视觉模型
  2. siliconflow Qwen3-VL-32B    (SILICONFLOW_API_KEY)   备 1
  3. siliconflow Qwen3-VL-8B     (SILICONFLOW_API_KEY)   备 2
  (ModelScope 待新 token 后再追加为第 4 节点)

错误分级:
  - 403 / 429 / 401  额度或鉴权错 → 节点拉黑 30 分钟（data/llm_chain_state.json）
  - 404              模型名不存在 → 拉黑 30 分钟（配置错，需人工改模型名）
  - 5xx              服务器瞬时错误 → 本次跳过，不拉黑
  - 网络异常          连接失败 → 本次跳过，不拉黑

拉黑过期自动重试 → 充值/换 key 后无需改代码自动回主链。

公开 API:
  vision_call(frames_b64, prompt) -> dict   多模态评分（帧 base64 列表）
  chat_call(prompt, system="") -> str       纯文本调用
  chain_status() -> dict                    各节点健康/黑名单状态
  reset_blacklist() -> None                 手动清空黑名单

与 visual_scorer 的关系:
  visual_scorer._call_qwen_vl 直连 DashScope 为主路径，捕获 403/429 后
  调用本模块 vision_call() 走降级链（见 visual_scorer 接线处）。

环境变量:
  DASHSCOPE_API_KEY      必填（主链）
  SILICONFLOW_API_KEY    备链 key（VISION_API_KEY 作为第二候选，兼容旧配置）
  LLM_CHAIN_SILICONFLOW_VL_32B  可选覆盖 SiliconFlow 32B 模型名
  LLM_CHAIN_SILICONFLOW_VL_8B   可选覆盖 SiliconFlow 8B 模型名
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── 状态与缓存路径 ────────────────────────────────────────────────
_PROJECT = Path(__file__).resolve().parent.parent
_STATE_FILE = _PROJECT / "data" / "llm_chain_state.json"
_CACHE_DIR = _PROJECT / "cache" / "llm_chain_vision"

_BLACKLIST_SECONDS = 30 * 60  # 额度错拉黑 30 分钟
_CACHE_READ_LIMIT = 3 * 1024 * 1024  # 缓存文件 >3MB 直接跳过（防写坏）

# ── 链定义 ────────────────────────────────────────────────────────
# base_url: OpenAI 兼容 /chat/completions；key_env: 依次尝试的环境变量名列表
_CHAIN: List[Dict[str, Any]] = [
    {
        "name": "dashscope-qwen-vl-max",
        "provider": "dashscope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-vl-max",
        "key_env": ["DASHSCOPE_API_KEY"],
        "roles": ["vision", "chat"],
    },
    {
        "name": "siliconflow-qwen3-vl-32b",
        "provider": "siliconflow",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen3-VL-32B-Instruct",
        "key_env": ["SILICONFLOW_API_KEY", "VISION_API_KEY"],
        "roles": ["vision"],
    },
    {
        "name": "siliconflow-qwen3-vl-8b",
        "provider": "siliconflow",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen3-VL-8B-Instruct",
        "key_env": ["SILICONFLOW_API_KEY", "VISION_API_KEY"],
        "roles": ["vision"],
    },
]


def _load_env() -> None:
    """读项目 .env（若存在）。无 python-dotenv 依赖，setdefault 不覆盖系统环境变量。"""
    env = _PROJECT / ".env"
    if not env.exists():
        return
    try:
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    except OSError:
        pass


def _model_name(node: Dict[str, Any]) -> str:
    """模型名支持 env 覆盖（LLM_CHAIN_SF_VL_32B / LLM_CHAIN_SF_VL_8B）。"""
    override = os.environ.get(f"LLM_CHAIN_{node['provider'].upper()}_VL_{'32B' if '32b' in node['model'].lower() else '8B'}")
    return override or node["model"]


def _node_key(node: Dict[str, Any]) -> Optional[str]:
    for env_name in node["key_env"]:
        v = os.environ.get(env_name, "").strip()
        if v:
            return v
    return None


# ── 状态持久化 ────────────────────────────────────────────────────

def _load_state() -> Dict[str, Any]:
    try:
        if _STATE_FILE.exists():
            d = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(d, dict) and "blacklist" in d:
                return d
    except (json.JSONDecodeError, OSError):
        pass
    return {"version": 1, "blacklist": {}, "history": []}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:  # 状态写失败不阻塞调用
        logger.warning("llm_chain 状态写入失败: %s", e)


def _is_blacklisted(name: str, state: Dict[str, Any]) -> bool:
    bl = state.get("blacklist", {}).get(name)
    if not bl:
        return False
    until = bl.get("until", 0)
    if time.time() >= until:
        # 过期自动摘除（充值后无需改代码自动回主链）
        state["blacklist"].pop(name, None)
        return False
    return True


def _blacklist(name: str, reason: str, seconds: int = _BLACKLIST_SECONDS) -> None:
    state = _load_state()
    state["blacklist"][name] = {
        "until": time.time() + seconds,
        "reason": reason,
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    state.setdefault("history", []).append({
        "node": name, "reason": reason,
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    state["history"] = state["history"][-200:]  # 只留最近 200 条
    _save_state(state)
    logger.warning("[llm_chain] 拉黑节点 %s (%s, %ds)", name, reason, seconds)


def reset_blacklist() -> None:
    """手动清空黑名单（充值/换 key 后）。"""
    state = _load_state()
    state["blacklist"] = {}
    _save_state(state)


def chain_status() -> Dict[str, Any]:
    """各节点可用性 + 黑名单状态（验证命令 / 交接文档调用）。"""
    _load_env()
    state = _load_state()
    nodes = []
    for node in _CHAIN:
        key = _node_key(node)
        bl = state.get("blacklist", {}).get(node["name"])
        nodes.append({
            "name": node["name"],
            "provider": node["provider"],
            "model": _model_name(node),
            "has_key": bool(key),
            "blacklisted": bool(bl),
            "blacklist_until": bl.get("until") if bl else None,
            "blacklist_reason": bl.get("reason") if bl else None,
        })
    return {
        "version": 1,
        "nodes": nodes,
        "blacklist_count": sum(1 for n in nodes if n["blacklisted"]),
    }


# ── 缓存（相同帧+prompt 命中直接返回，省 API 计费） ──────────────

def _cache_path(prompt: str, frames_b64: List[str]) -> Path:
    h = hashlib.md5((prompt + "|" + "|".join(frames_b64)).encode()).hexdigest()[:16]
    return _CACHE_DIR / f"{h}.json"


def _cache_read(p: Path) -> Optional[Dict[str, Any]]:
    try:
        if not p.exists() or p.stat().st_size > _CACHE_READ_LIMIT:
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _cache_write(p: Path, result: Dict[str, Any]) -> None:
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


# ── HTTP 调用 ─────────────────────────────────────────────────────

def _post_json(url: str, key: str, payload: Dict[str, Any], timeout: int = 120
               ) -> Tuple[int, Dict[str, Any]]:
    """POST OpenAI 兼容接口，返回 (status_code, body_dict)。

    死代理直连（继承 visual_scorer 教训）：Windows 注册表残留 Clash 代理配置时
    代理进程已死，urlopen 走系统代理必报 WinError 10061。国内服务无需代理。
    """
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
            return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            body = {}
        return e.code, body
    except Exception as e:  # 网络异常（ConnectionRefused / timeout 等）
        return 0, {"error": str(e)}


def _extract_json(text: str) -> Dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"scores": {}, "issues": [], "advice": "", "overall": 0}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"scores": {}, "issues": [], "advice": "", "overall": 0}


# ── 错误分级 ──────────────────────────────────────────────────────
# 返回 "blacklist"（拉黑 30min）/ "skip"（本次跳过，不拉黑）

def _classify(status: int, node: Dict[str, Any]) -> str:
    if status in (401, 403, 429):
        return "blacklist"          # 额度耗尽 / key 无效 / 限流
    if status == 404:
        return "blacklist"          # 模型名不存在（配置错，需人工改）
    if status >= 500:
        return "skip"               # 服务器瞬时错误
    if status == 0:
        return "skip"               # 网络异常
    return "skip"


def _extract_message(body: Dict[str, Any]) -> str:
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return body.get("error", {}).get("message", json.dumps(body)[:200]
                                          if body else "空响应")


def _reset_on_success(state: Dict[str, Any], name: str) -> None:
    """节点成功后摘除其黑名单（避免 404 改配置后仍需等拉黑到期）。"""
    if name in state.get("blacklist", {}):
        state["blacklist"].pop(name, None)
        _save_state(state)


# ── 主入口：vision_call / chat_call ───────────────────────────────

def _run_chain(prompt: str, frames_b64: Optional[List[str]],
               timeout: int = 120) -> Dict[str, Any]:
    """按链序尝试各节点。返回最终结果或错误摘要。"""
    _load_env()
    cache_key = None
    if frames_b64:
        cache_key = _cache_path(prompt, frames_b64)
        hit = _cache_read(cache_key)
        if hit is not None:
            return hit

    errors: List[str] = []
    state = _load_state()
    for node in _CHAIN:
        name = node["name"]
        if frames_b64 and "vision" not in node["roles"]:
            continue
        key = _node_key(node)
        if not key:
            errors.append(f"{name}: 无 key（{node['key_env']}）")
            continue
        if _is_blacklisted(name, state):
            errors.append(f"{name}: 黑名单中")
            continue

        model = _model_name(node)
        content: list = []
        if frames_b64:
            content = [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}}
                for b in frames_b64
            ]
        content.append({"type": "text", "text": prompt})
        payload = {"model": model,
                   "messages": [{"role": "user", "content": content}],
                   "max_tokens": 1500}

        status, body = _post_json(
            f"{node['base_url']}/chat/completions", key, payload, timeout=timeout)
        if status == 200:
            text = _extract_message(body)
            result = _extract_json(text) if frames_b64 else {"text": text}
            result["_chain"] = {"node": name, "model": model, "status": 200}
            if frames_b64 and cache_key is not None:
                _cache_write(cache_key, result)
            _reset_on_success(state, name)
            return result

        cls = _classify(status, node)
        reason = (body.get("error", {}).get("message", "")
                  if isinstance(body, dict) else str(body)[:200])
        if cls == "blacklist":
            _blacklist(name, f"HTTP {status} {reason}")
        errors.append(f"{name}: HTTP {status} ({reason or '无详情'}) → {cls}")
        if cls == "blacklist":
            # 额度/配置类错误在本轮不再试后续同 provider 节点意义不大，
            # 但仍继续尝试不同 provider（例如 SF 无 key 时 DashScope 403 已试过，
            # 直接交给下一个能跑的 provider）。保持链式尝试。
            continue

    return {"error": "所有节点均不可用 | " + "；".join(errors)}


def vision_call(frames_b64: List[str], prompt: str, timeout: int = 120) -> Dict[str, Any]:
    """多模态视觉评分。frames_b64 为 jpeg base64 列表，返回结构化 JSON 结果。

    供 visual_scorer._call_qwen_vl 的 403/429 分支接入。
    """
    return _run_chain(prompt, frames_b64, timeout=timeout)


def chat_call(prompt: str, system: str = "", timeout: int = 120) -> str:
    """纯文本调用（qwen-vl-max 不支持纯文本时由链内节点自行过滤——当前
    dashscope 节点 roles 含 chat，但 qwen-vl-max 是视觉模型，纯文本场景
    建议后续在链上追加 qwen-flash 文本节点）。"""
    full = f"{system}\n{prompt}" if system else prompt
    result = _run_chain(full, None, timeout=timeout)
    if "text" in result:
        return result["text"]
    return result.get("error", "空响应")


__all__ = ["vision_call", "chat_call", "chain_status", "reset_blacklist"]
