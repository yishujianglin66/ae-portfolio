"""DaVinci Resolve 21.1 官方 MCP（ResolveMCP.exe）stdio 客户端。

Resolve 21.1 随安装目录携带 ResolveMCP.exe——官方 MCP 服务器（换行分隔
JSON-RPC 2.0 over stdio）。本模块把它的 run_script / get_resolve_status /
search_scripting_api 能力引入本项目，走 DaVinciResolveScript 官方 Python API。

关键前置（2026-09-24 实测）：
- Resolve 必须处于运行状态（GUI）；
- Resolve 安装在非默认目录时，必须设 RESOLVE_SCRIPT_LIB 指向该目录下的
  fusionscript.dll，否则内置 DaVinciResolveScript 按安装器记录的默认路径
  查找并抛 ImportError。
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import Any

# 单次调用默认超时（秒）：run_script 内可能含渲染轮询，留足余量
DEFAULT_TIMEOUT = 300


def _resolve_install_dir() -> Path | None:
    """定位 Resolve 安装目录（含 ResolveMCP.exe 才算数）。"""
    candidates: list[Path] = []
    env_dir = os.environ.get("RESOLVE_INSTALL_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    try:  # 复用项目配置（puppet-automation 内部）
        from ...config import settings

        if getattr(settings, "davinci_path", None):
            candidates.append(Path(settings.davinci_path))
    except Exception:  # noqa: BLE001
        pass
    candidates.append(Path(r"D:\app"))
    for d in candidates:
        if (d / "ResolveMCP.exe").exists():
            return d
    return None


def is_available() -> bool:
    """官方 MCP 可执行文件与 fusionscript.dll 均存在即可用。"""
    d = _resolve_install_dir()
    return bool(d) and (d / "fusionscript.dll").exists()


class ResolveMCPClient:
    """一次调用 = 起一个 ResolveMCP 子进程完成 JSON-RPC 会话（简单可靠）。"""

    def __init__(self, install_dir: Path | None = None):
        self.install_dir = install_dir or _resolve_install_dir()
        if not self.install_dir:
            raise FileNotFoundError(
                "ResolveMCP.exe 未找到（确认 Resolve 21.1+ 安装目录，或设 RESOLVE_INSTALL_DIR）"
            )
        self.exe = self.install_dir / "ResolveMCP.exe"

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        dll = self.install_dir / "fusionscript.dll"
        # 必须强制覆盖：实测系统里存在指向旧默认安装路径的 User 级
        # RESOLVE_SCRIPT_LIB（D:\DaVinci Resolve\…），setdefault 会被它劫持。
        env["RESOLVE_SCRIPT_LIB"] = str(dll)
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """调用一个 MCP 工具，返回 {output/…} 结果 dict。失败抛 RuntimeError。"""
        proc = subprocess.Popen(
            [str(self.exe)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._env(),
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # 后台读线程 → 队列，规避 Windows 管道无法 select 的问题
        lines: queue.Queue[str | None] = queue.Queue()
        err_lines: list[str] = []

        def _reader() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                lines.put(line)
            lines.put(None)

        def _err_reader() -> None:
            assert proc.stderr is not None
            for line in proc.stderr:
                if len(err_lines) < 80:
                    err_lines.append(line.rstrip())

        threading.Thread(target=_reader, daemon=True).start()
        threading.Thread(target=_err_reader, daemon=True).start()

        try:
            self._send(proc, {
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "ae-kv-gateway", "version": "1.0"},
                },
            })
            init = self._recv(lines, timeout)
            if not init or "result" not in init:
                raise RuntimeError(
                    "MCP initialize 失败: %s | stderr: %s" % (init, " | ".join(err_lines[-6:])[:600])
                )

            self._send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
            self._send(proc, {
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments or {}},
            })
            resp = self._recv(lines, timeout)
            if resp is None:
                raise RuntimeError(f"工具 {tool_name} 无响应（超时 {timeout}s）")
            if "error" in resp:
                raise RuntimeError(f"工具 {tool_name} 返回错误: {resp['error']}")
            result = resp.get("result", {})
            if result.get("isError"):
                texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
                raise RuntimeError(f"工具 {tool_name} 执行失败: {' | '.join(texts)[:500]}")
            return result
        finally:
            try:
                proc.stdin.close()  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                pass
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    @staticmethod
    def _send(proc: subprocess.Popen, obj: dict[str, Any]) -> None:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        proc.stdin.flush()

    @staticmethod
    def _recv(lines: queue.Queue[str | None], timeout: int) -> dict[str, Any] | None:
        """取下一条带 id 的响应（跳过通知/空行）。"""
        import time as _t

        deadline = _t.time() + timeout
        while _t.time() < deadline:
            try:
                line = lines.get(timeout=1.0)
            except queue.Empty:
                continue
            if line is None:  # stdout EOF
                return None
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(msg, dict) and "id" in msg:
                return msg
        return None


def extract_text(result: dict[str, Any]) -> str:
    """把 tools/call 结果里的 text content 拼成纯文本。"""
    parts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
    return "\n".join(parts)
