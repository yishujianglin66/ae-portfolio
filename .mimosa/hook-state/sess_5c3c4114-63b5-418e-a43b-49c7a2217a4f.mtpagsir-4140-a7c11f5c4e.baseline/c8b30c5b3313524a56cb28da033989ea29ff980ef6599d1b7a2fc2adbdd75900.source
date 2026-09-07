# -*- coding: utf-8 -*-
"""
scripts/check_llm_keys.py — 自动检测并标记无效的 LLM API Key 配置

功能:
    1. 扫描 .env / .env.doubao 中所有已知的 LLM API Key
    2. 对每个 key 发最小请求在线验证（200 → 有效；401/403 → 无效；其他 → 未知）
    3. 把结果写入 data/llm_key_status.json（网关读取后自动熔断失效 Provider，避免误用）
    4. 可选: 在配置文件中把失效的 key 行注释掉并加 [INVALID] 标记（--comment）

用法:
    python scripts/check_llm_keys.py                     # 检测 + 写状态文件 + 注释失效行
    python scripts/check_llm_keys.py --no-comment        # 只检测 + 写状态文件，不改配置文件
    python scripts/check_llm_keys.py --no-mark           # 只检测，不写任何东西
    python scripts/check_llm_keys.py --timeout 15        # 自定义单请求超时

状态判定:
    - HTTP 200          → valid   (可用)
    - HTTP 401 / 403    → invalid (key 无效/过期/分组停用，网关将熔断该 Provider)
    - 其他 HTTP/网络异常 → unknown (端点或网络问题，不断言 key 失效，避免误伤)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Tuple

ROOT = Path(__file__).resolve().parents[1]
ENV_FILES = [ROOT / ".env", ROOT / ".env.doubao"]
STATUS_FILE = ROOT / "data" / "llm_key_status.json"

# env key → 探测配置（base_url/model 优先取配置文件中已有的值）
KEY_PROBES: Dict[str, Dict[str, str]] = {
    "DEEPSEEK_API_KEY": {
        "provider": "deepseek",
        "base_url_env": "DEEPSEEK_BASE_URL", "base_url": "https://api.deepseek.com/v1",
        "model_env": "DEEPSEEK_FLASH_MODEL", "model": "deepseek-v4-flash",
    },
    "MODELSCOPE_API_KEY": {
        "provider": "modelscope",
        "base_url_env": "MODELSCOPE_BASE_URL", "base_url": "https://api-inference.modelscope.cn/v1",
        "model_env": "MODELSCOPE_FLASH_MODEL", "model": "Qwen/Qwen3-8B",
    },
    "GPT_GATEWAY_API_KEY": {
        "provider": "gpt",
        "base_url_env": "GPT_GATEWAY_BASE_URL", "base_url": "https://duckmiss.site/v1",
        "model_env": "GPT_BACKUP_MODEL", "model": "gpt-5.6",
    },
    "DOUBAO_API_KEY": {
        "provider": "doubao",
        "base_url_env": "DOUBAO_BASE_URL", "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model_env": "ARK_DEFAULT_MODEL", "model": "deepseek-v4-flash-260425",
    },
    "DOUBAO_API_KEY_AGENT": {
        "provider": "agent_plan",
        "base_url_env": "DOUBAO_BASE_URL", "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model_env": "ARK_DEFAULT_MODEL", "model": "deepseek-v4-flash-260425",
    },
    "DUCK_MISS_API_KEY": {
        "provider": "claude",
        "base_url_env": "DUCK_MISS_BASE_URL", "base_url": "https://duckmiss.site/v1",
        "model_env": "DUCK_MISS_DEFAULT_MODEL", "model": "claude-sonnet-4-6",
    },
    "DUCK_MISS_API_KEY_BACKUP": {
        "provider": "claude_backup",
        "base_url_env": "DUCK_MISS_BASE_URL", "base_url": "https://duckmiss.site/v1",
        "model_env": "DUCK_MISS_DEFAULT_MODEL", "model": "claude-sonnet-4-6",
    },
    "SILICONFLOW_API_KEY": {
        "provider": "siliconflow",
        "base_url_env": "SILICONFLOW_BASE_URL", "base_url": "https://api.siliconflow.cn/v1",
        "model_env": "SILICONFLOW_MODEL", "model": "Qwen/Qwen2.5-7B-Instruct",
    },
}


def load_env_values(path: Path) -> Dict[str, str]:
    """读取 .env 风格文件的 key=value（跳过注释行）"""
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def probe_key(base_url: str, api_key: str, model: str, timeout: int) -> Tuple[str, str, float]:
    """最小请求验证 key，返回 (status, reason, latency_ms)"""
    url = f"{base_url.rstrip('/')}/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
            "temperature": 0,
        }).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        },
        method="POST",
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
            latency = (time.time() - start) * 1000
            return "valid", f"HTTP {resp.status}", latency
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:150]
        latency = (time.time() - start) * 1000
        if e.code in (401, 403):
            return "invalid", f"HTTP {e.code}: {body}", latency
        return "unknown", f"HTTP {e.code}: {body}", latency
    except Exception as e:
        latency = (time.time() - start) * 1000
        return "unknown", f"{type(e).__name__}: {str(e)[:120]}", latency


def comment_out_invalid(env_file: Path, invalid_reasons: Dict[str, str]) -> int:
    """把配置文件中失效的 key 行注释掉并加 [INVALID] 标记（幂等）。返回改动行数。"""
    if not env_file.exists() or not invalid_reasons:
        return 0
    lines = env_file.read_text(encoding="utf-8").splitlines(keepends=True)
    ts = time.strftime("%Y-%m-%d")
    changed = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key not in invalid_reasons:
            continue
        # 幂等：上一行已是 [INVALID] 标记则跳过
        prev = lines[i - 1].strip() if i > 0 else ""
        if prev.startswith("# [INVALID"):
            continue
        indent = line[: len(line) - len(line.lstrip())]
        body = line.lstrip()
        reason = invalid_reasons[key].replace("\n", " ")
        lines[i] = (
            f"# [INVALID {ts}] 检测失败: {reason}（更新 key 后删除本行并取消下一行注释）\n"
            f"{indent}# {body}"
        )
        changed += 1
    if changed:
        env_file.write_text("".join(lines), encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="检测并标记无效的 LLM API Key 配置")
    parser.add_argument("--timeout", type=int, default=20, help="单请求超时秒数（默认 20）")
    parser.add_argument("--no-mark", action="store_true", help="只检测，不写 data/llm_key_status.json")
    parser.add_argument("--no-comment", action="store_true", help="不在配置文件中注释失效行")
    args = parser.parse_args()

    envs: Dict[str, str] = {}
    for f in ENV_FILES:
        envs.update(load_env_values(f))

    results: Dict[str, Dict[str, str]] = {}
    order = ["invalid", "unknown", "valid", "missing"]
    buckets: Dict[str, list] = {k: [] for k in order}

    for env_key, cfg in KEY_PROBES.items():
        api_key = envs.get(env_key, "")
        if not api_key:
            results[env_key] = {"provider": cfg["provider"], "status": "missing",
                                "reason": "未配置", "checked_at": time.time()}
            buckets["missing"].append(env_key)
            continue
        base_url = envs.get(cfg.get("base_url_env", ""), cfg["base_url"])
        model = envs.get(cfg.get("model_env", ""), cfg["model"])
        status, reason, latency = probe_key(base_url, api_key, model, args.timeout)
        results[env_key] = {"provider": cfg["provider"], "status": status,
                            "reason": f"{reason} ({latency:.0f}ms)", "checked_at": time.time()}
        buckets[status].append(env_key)

    # 打印结果（无效项优先，便于一眼发现问题）
    print("=" * 78)
    label = {"valid": "OK", "invalid": "INVALID", "unknown": "UNKNOWN", "missing": "SKIP"}
    for status in order:
        for env_key in buckets[status]:
            r = results[env_key]
            print(f"[{label[status]:7s}] {env_key:26s} {r['provider']:14s} {r['reason']}")
    print("=" * 78)

    # 写状态文件（网关据此熔断）
    if not args.no_mark:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[标记] 状态文件已更新: {STATUS_FILE}")

    # 注释失效行
    invalid_reasons = {k: v["reason"] for k, v in results.items() if v["status"] == "invalid"}
    if not args.no_comment and invalid_reasons:
        total = 0
        for f in ENV_FILES:
            total += comment_out_invalid(f, invalid_reasons)
        print(f"[标记] 已在配置文件中注释 {total} 个失效 key 行")

    # 汇总
    n_invalid = len(buckets["invalid"])
    n_unknown = len(buckets["unknown"])
    n_valid = len(buckets["valid"])
    print(f"汇总: valid={n_valid}, invalid={n_invalid}, unknown={n_unknown}, missing={len(buckets['missing'])}")
    if n_invalid:
        print("提示: 失效 key 已被网关熔断并注释，更新 key 后删除 [INVALID] 标记行并取消注释即可恢复。")
    return 0 if n_invalid == 0 and n_unknown == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
