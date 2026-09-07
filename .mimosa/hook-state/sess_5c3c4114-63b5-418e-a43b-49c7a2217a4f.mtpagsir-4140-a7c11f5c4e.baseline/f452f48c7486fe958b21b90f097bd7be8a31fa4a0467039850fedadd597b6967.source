"""
Premiere Pro MCP Bridge 客户端
==============================
与临时目录下的 ae_kv_pr_bridge 通信

协议格式（匹配 pr_bridge_core.jsx）：
  1. Python 写入 cmd_{id}.json 文件
  2. PR Bridge 轮询发现并执行
  3. PR 写入 result_{id}.json 结果文件
  4. Python 轮询读取结果

新架构特性：
- 支持动态加载 handler（无需重启 PR）
- 支持运行时重载 handlers
- 支持执行任意 JSX 脚本

使用方式：
    client = PremiereMCP()
    result = client.ping()
    result = client.execute_script("app.project.name")
"""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional


class PremiereMCP:
    """Premiere Pro MCP Bridge 客户端。"""

    def __init__(
        self,
        bridge_dir: str = None,
        timeout: float = 60.0,
        poll_interval: float = 0.3,
    ) -> None:
        if bridge_dir is None:
            self.bridge_dir = Path(tempfile.gettempdir()) / "ae_kv_pr_bridge"
        else:
            self.bridge_dir = Path(bridge_dir)

        self.timeout = timeout
        self.poll_interval = poll_interval
        self._cmd_id = 0

    def _next_id(self) -> str:
        self._cmd_id += 1
        return f"{int(time.time() * 1000)}_{self._cmd_id}"

    def _write_command(self, action: str, **params) -> str:
        cmd_id = self._next_id()
        cmd_file = self.bridge_dir / f"cmd_{cmd_id}.json"

        # 删除旧结果
        result_file = self.bridge_dir / f"result_{cmd_id}.json"
        if result_file.exists():
            try:
                result_file.unlink()
            except:
                pass

        cmd_data = {"action": action, **params}
        cmd_file.write_text(json.dumps(cmd_data, ensure_ascii=False), encoding="utf-8")
        return cmd_id

    def _read_result(self, cmd_id: str) -> Optional[Dict[str, Any]]:
        result_file = self.bridge_dir / f"result_{cmd_id}.json"
        if not result_file.exists():
            return None
        try:
            content = result_file.read_text(encoding="utf-8")
            if not content:
                return None
            return json.loads(content)
        except (json.JSONDecodeError, IOError):
            return None

    def _send_command(self, action: str, **params) -> Dict[str, Any]:
        cmd_id = self._write_command(action, **params)
        keepalive_file = self.bridge_dir / f".keepalive_{cmd_id}"
        try:
            keepalive_file.touch()
        except (IOError, OSError):
            pass

        try:
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                result = self._read_result(cmd_id)
                if result is not None:
                    try:
                        if keepalive_file.exists():
                            keepalive_file.unlink()
                    except (IOError, OSError):
                        pass
                    return result
                time.sleep(self.poll_interval)

            try:
                if keepalive_file.exists():
                    keepalive_file.unlink()
            except (IOError, OSError):
                pass
            return {
                "success": False,
                "status": "error",
                "error": f"Timeout after {self.timeout}s",
            }
        except Exception:
            try:
                if keepalive_file.exists():
                    keepalive_file.unlink()
            except (IOError, OSError):
                pass
            raise

    def ping(self) -> Dict[str, Any]:
        return self._send_command("ping")

    def get_info(self) -> Dict[str, Any]:
        return self._send_command("getInfo")

    def get_project_info(self) -> Dict[str, Any]:
        return self._send_command("getProjectInfo")

    def import_media(self, files: list) -> Dict[str, Any]:
        return self._send_command("importMedia", files=files)

    def create_sequence(self, name: str) -> Dict[str, Any]:
        return self._send_command("createSequence", name=name)

    def add_clip_to_track(self, clip_name: str, track: int = 0, start_time: float = 0) -> Dict[str, Any]:
        return self._send_command(
            "addClipToTrack",
            clipName=clip_name,
            track=track,
            startTime=start_time
        )

    def apply_transition(self, clip_index: int, track: int = 0, transition: str = "Cross Dissolve", duration: float = 0.5) -> Dict[str, Any]:
        return self._send_command(
            "applyTransition",
            clipIndex=clip_index,
            track=track,
            transition=transition,
            duration=duration
        )

    def add_effect(self, clip_index: int, effect: str = "Lumetri Color", track: int = 0) -> Dict[str, Any]:
        return self._send_command(
            "addEffect",
            clipIndex=clip_index,
            effect=effect,
            track=track
        )

    def save_project(self) -> Dict[str, Any]:
        return self._send_command("saveProject")

    def execute_script(self, script: str) -> Dict[str, Any]:
        """执行任意 JSX 脚本（无需重启 PR 即可使用）。"""
        return self._send_command("executeScript", script=script)

    def execute_script_file(self, script_path: str) -> Dict[str, Any]:
        """执行脚本文件（通过 executeScript 实现）。"""
        script_file = Path(script_path)
        if not script_file.exists():
            return {"success": False, "error": f"Script file not found: {script_path}"}
        script_content = script_file.read_text(encoding="utf-8")
        return self.execute_script(script_content)

    def reload_handlers(self) -> Dict[str, Any]:
        """重新加载所有 handler 文件（无需重启 PR）。"""
        return self._send_command("reloadHandlers")

    def register_handler(self, script_path: str) -> Dict[str, Any]:
        """通过执行外部脚本动态注册 handler（无需重启 PR）。"""
        return self._send_command("registerHandler", scriptPath=script_path)


if __name__ == "__main__":
    client = PremiereMCP()

    print("=== Premiere Pro MCP Bridge 测试 ===")
    print()

    print("1. Ping...")
    result = client.ping()
    print(f"   {json.dumps(result, ensure_ascii=False, indent=2)}")
    print()

    if result.get("status") == "success":
        print("2. Get Info...")
        result = client.get_info()
        print(f"   {json.dumps(result, ensure_ascii=False, indent=2)}")
    else:
        print("⚠️  无法连接到 Bridge")
        print("   请确保 PR 已启动并加载了 Startup 脚本")