# -*- coding: utf-8 -*-
"""
scripts/update_doubao_keys.py — 更新 .env.doubao 中的 Claude(DuckMiss) API Key

用途:
    将新的有效 DuckMiss(Claude) Key 写入 .env.doubao，验证通过后自动刷新
    LLM 网关，使 claude 恢复为 QUALITY_REVIEW / EFFECT_PLANNING 等任务的
    首选 Provider（TASK_PROVIDER_MAP 已默认 claude 优先，key 有效即生效）。

用法:
    python scripts/update_doubao_keys.py --key sk-新key
    python scripts/update_doubao_keys.py --key sk-新key --backup sk-备用key
    python scripts/update_doubao_keys.py --key sk-新key --base-url https://新端点/v1 --model claude-sonnet-4-6
    python scripts/update_doubao_keys.py --key sk-新key --no-verify   # 跳过在线验证（不推荐）

安全特性:
    1. 写文件前先备份为 .env.doubao.bak
    2. 在线验证新 key 有效后才落盘；验证失败自动回滚，不破坏原文件
    3. 落盘后强制刷新网关并实测一次 claude 调用，确认恢复优先
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Tuple

ENV_FILE = Path(__file__).resolve().parents[1] / ".env.doubao"
DEFAULT_BASE_URL = "https://duckmiss.site/v1"
DEFAULT_MODEL = "claude-sonnet-4-6"

# 允许更新的键（白名单，防止误改其他配置）
UPDATABLE_KEYS = (
    "DUCK_MISS_API_KEY",
    "DUCK_MISS_API_KEY_BACKUP",
    "DUCK_MISS_BASE_URL",
    "DUCK_MISS_DEFAULT_MODEL",
)


def load_env_values(path: Path) -> Dict[str, str]:
    """读取 .env 风格文件中所有 key=value（含被注释行的现值，用于默认回退）"""
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


def verify_claude_key(base_url: str, api_key: str, model: str, timeout: int = 25) -> Tuple[bool, str]:
    """用最小请求在线验证 Claude(DuckMiss) key 是否有效。

    Returns:
        (有效?, 说明)
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
        "temperature": 0,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
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
            body = resp.read().decode("utf-8", errors="replace")
            latency = (time.time() - start) * 1000
            print(f"[API] POST {url} → HTTP {resp.status}, {latency:.0f}ms")
            if resp.status == 200:
                return True, f"HTTP 200, {latency:.0f}ms"
            return False, f"HTTP {resp.status}, {body[:200]}"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        latency = (time.time() - start) * 1000
        print(f"[API] POST {url} → HTTP {e.code}, {latency:.0f}ms")
        if e.code == 401:
            return False, f"HTTP 401 (key 无效或已过期), {body[:200]}"
        return False, f"HTTP {e.code}, {body[:200]}"
    except Exception as e:
        latency = (time.time() - start) * 1000
        print(f"[API] POST {url} → 异常, {latency:.0f}ms ({type(e).__name__})")
        return False, f"{type(e).__name__}: {e}"


def update_env_file(path: Path, updates: Dict[str, str]) -> int:
    """将 updates 写入 .env.doubao：命中已有行则原位替换，未命中则追加。

    Returns:
        更新的行数
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = 0
    for key, value in updates.items():
        target = f"{key}="
        hit = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue  # 跳过注释行，只改实际配置行
            if stripped.startswith(target):
                # 保留原有缩进/换行风格，仅替换值
                indent = line[: len(line) - len(line.lstrip())]
                nl = "\n" if line.endswith("\n") else ""
                lines[i] = f"{indent}{key}={value}{nl}"
                hit = True
                changed += 1
                break
        if not hit:
            lines.append(f"{key}={value}\n")
            changed += 1
    path.write_text("".join(lines), encoding="utf-8")
    return changed


def refresh_gateway_and_verify(model: str) -> bool:
    """强制刷新网关并实测一次 claude provider 调用，确认恢复优先。

    Returns:
        claude 调用是否成功
    """
    try:
        import asyncio
        from core.llm_gateway import llm_gateway

        llm_gateway.ensure_configured(force=True)
        providers = list(llm_gateway._config.providers.keys())
        print(f"[网关] 已加载 Provider: {providers}")
        if "claude" not in providers:
            print("[网关] 警告: claude Provider 未装配，请检查 DUCK_MISS_* 配置")
            return False

        claude_cfg = llm_gateway._config.providers.get("claude", {})
        base_url = claude_cfg.get("base_url", "?")
        url = f"{base_url.rstrip('/')}/chat/completions"

        async def _probe():
            return await llm_gateway.chat_with_provider(
                prompt="ping",
                provider="claude",
                model_type="default",
                max_tokens=5,
                temperature=0,
            )

        resp = asyncio.run(_probe())
        latency = getattr(resp, "latency_ms", 0.0)
        if getattr(resp, "success", False):
            print(f"[API] POST {url} → HTTP 200, {latency:.0f}ms")
            print(
                f"[网关] claude 实测调用成功: model={getattr(resp, 'model', '?')}, "
                f"latency={latency:.0f}ms"
            )
            return True
        err = getattr(resp, "error", "") or ""
        m = re.search(r"HTTP (\d{3})", err)
        status = m.group(1) if m else "?"
        print(f"[API] POST {url} → HTTP {status}, {latency:.0f}ms")
        print(f"[网关] claude 实测调用失败: {err}")
        return False
    except Exception as e:
        print(f"[网关] 刷新/验证异常: {type(e).__name__}: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="更新 .env.doubao 中的 Claude(DuckMiss) Key")
    parser.add_argument("--key", required=True, help="新的 DUCK_MISS_API_KEY")
    parser.add_argument("--backup", default="", help="备用 DUCK_MISS_API_KEY_BACKUP（可选）")
    parser.add_argument("--base-url", default="", help="DUCK_MISS_BASE_URL（可选，默认保留现值）")
    parser.add_argument("--model", default="", help="DUCK_MISS_DEFAULT_MODEL（可选，默认保留现值）")
    parser.add_argument("--no-verify", action="store_true", help="跳过在线验证（不推荐）")
    args = parser.parse_args()

    if not ENV_FILE.exists():
        print(f"[错误] 找不到 {ENV_FILE}")
        return 1

    # 1. 读取现状（含 base_url / model 现值，验证用）
    current = load_env_values(ENV_FILE)
    base_url = args.base_url or current.get("DUCK_MISS_BASE_URL", DEFAULT_BASE_URL)
    model = args.model or current.get("DUCK_MISS_DEFAULT_MODEL", DEFAULT_MODEL)
    print(f"[目标] {ENV_FILE.name}")
    print(f"[验证] base_url={base_url}, model={model}")

    # 2. 在线验证新 key（默认开启；验证失败直接退出，不改文件）
    if not args.no_verify:
        print("[验证] 正在测试新 key ...")
        ok, detail = verify_claude_key(base_url, args.key, model)
        print(f"[验证] 新 key: {'有效' if ok else '无效'} — {detail}")
        if not ok:
            print("[结果] 验证未通过，文件未做任何修改。请确认 key 正确或使用 --no-verify 强制写入。")
            return 1
        if args.backup:
            ok2, detail2 = verify_claude_key(base_url, args.backup, model)
            print(f"[验证] 备用 key: {'有效' if ok2 else '无效（仍会写入，但不建议）'} — {detail2}")

    # 3. 备份 + 落盘
    backup_path = ENV_FILE.with_suffix(".env.doubao.bak")
    shutil.copy2(ENV_FILE, backup_path)
    updates = {"DUCK_MISS_API_KEY": args.key}
    if args.backup:
        updates["DUCK_MISS_API_KEY_BACKUP"] = args.backup
    if args.base_url:
        updates["DUCK_MISS_BASE_URL"] = args.base_url
    if args.model:
        updates["DUCK_MISS_DEFAULT_MODEL"] = args.model
    changed = update_env_file(ENV_FILE, updates)
    print(f"[写入] 已更新 {changed} 个字段（备份: {backup_path.name}）")

    # 4. 刷新网关并实测 claude，确认恢复优先
    print("[网关] 刷新配置并实测 claude ...")
    ok = refresh_gateway_and_verify(model)
    if not ok:
        # 网关实测失败 → 回滚文件，恢复原状
        shutil.copy2(backup_path, ENV_FILE)
        print("[结果] claude 实测失败，已自动回滚 .env.doubao 到原配置。")
        print("       提示: 若 key 在线验证通过但网关失败，可能是端点/模型名问题，可加 --base-url / --model 指定。")
        return 1

    print("[结果] 完成。claude 已重新成为 QUALITY_REVIEW / EFFECT_PLANNING 等任务的优先 Provider。")
    print("       提示: 运行中的服务需重启后生效（网关单例已在新进程中自动加载）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
