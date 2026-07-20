"""
aep_analyzer/analyzer.py - AEP 分析主逻辑

通过 MCP/JSX 桥接调用 deep_inspect.jsx，解析 JSON 输出。
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# JSX 脚本路径
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEEP_INSPECT_JSX = str(_PROJECT_ROOT / "aep_analyzer" / "jsx" / "deep_inspect.jsx")

# MCP Bridge 通信路径
_BRIDGE_DIR = os.path.expanduser("~/Documents/ae-mcp-bridge")
_COMMAND_FILE = os.path.join(_BRIDGE_DIR, "ae_command.json")
_RESULT_FILE = os.path.join(_BRIDGE_DIR, "ae_result.json")


class AEPAnalyzer:
    """AEP 工程分析器。

    支持两种模式：
    - 在线模式：通过 MCP Bridge 与运行中的 AE 通信
    - 离线模式：解析已有的 JSON 分析结果
    """

    def __init__(
        self,
        bridge_dir: str = "",
        jsx_path: str = "",
    ) -> None:
        self._bridge_dir = bridge_dir or _BRIDGE_DIR
        self._jsx_path = jsx_path or _DEEP_INSPECT_JSX
        self._last_report: Optional[Dict[str, Any]] = None

    def analyze_from_json(self, json_path: str) -> Dict[str, Any]:
        """从 JSON 文件加载分析结果（离线模式）。

        Args:
            json_path: JSON 文件路径

        Returns:
            分析报告字典
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)
        self._last_report = data
        return data

    def analyze_via_bridge(self, timeout: int = 30) -> Dict[str, Any]:
        """通过 MCP Bridge 分析当前 AE 中打开的项目（在线模式）。

        发送 deep_inspect.jsx 命令到 AE，等待结果。

        Args:
            timeout: 等待超时（秒）

        Returns:
            分析报告字典
        """
        # 读取 JSX 脚本内容
        jsx_content = self._read_jsx()

        # 写入命令文件
        command = {
            "command": "execute_script",
            "params": {"script": jsx_content},
            "timestamp": self._get_timestamp(),
        }
        self._write_command(command)

        # 等待结果
        result = self._wait_for_result(timeout)
        if result is None:
            return {"error": "TIMEOUT", "message": f"No result within {timeout}s"}

        # 解析结果
        try:
            if isinstance(result, str):
                data: Dict[str, Any] = json.loads(result)
            else:
                data = result
        except json.JSONDecodeError as e:
            return {"error": "PARSE_ERROR", "message": str(e)}

        if "error" in data:
            return dict(data)

        self._last_report = data
        return dict(data)

    def analyze_via_mcp(self) -> Dict[str, Any]:
        """通过 MCP Server 的 run-jsx-script 工具分析项目。

        Returns:
            分析报告字典
        """
        jsx_content = self._read_jsx()
        # 返回脚本内容，由调用方通过 MCP 执行
        return {
            "jsx_script": jsx_content,
            "instructions": "Execute via MCP run-jsx-script tool",
        }

    def get_last_report(self) -> Optional[Dict[str, Any]]:
        """获取上次分析报告。"""
        return self._last_report

    def get_summary(self, report: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取分析报告摘要。

        Args:
            report: 分析报告（默认使用上次结果）

        Returns:
            摘要字典
        """
        if report is None:
            report = self._last_report
        if report is None:
            return {"error": "No report available"}

        stats = report.get("stats", {})
        return {
            "project_name": report.get("project", {}).get("name", "Unknown"),
            "project_path": report.get("project", {}).get("path", ""),
            "total_comps": stats.get("totalComps", 0),
            "total_layers": stats.get("totalLayers", 0),
            "total_effects": stats.get("totalEffects", 0),
            "total_keyframes": stats.get("totalKeyframes", 0),
            "total_expressions": stats.get("totalExpressions", 0),
            "total_masks": stats.get("totalMasks", 0),
            "techniques": report.get("techniques", []),
            "unique_effects": len(report.get("effectsByType", {})),
            "precomp_count": len(report.get("precompGraph", {})),
        }

    def get_effect_chains(
        self, report: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """提取效果链（每个图层的效果组合）。

        Args:
            report: 分析报告

        Returns:
            效果链列表
        """
        if report is None:
            report = self._last_report
        if report is None:
            return []

        chains: List[Dict[str, Any]] = []
        for comp in report.get("compositions", []):
            for layer in comp.get("layers", []):
                effects = layer.get("effects", [])
                if len(effects) >= 2:
                    chain = {
                        "comp": comp.get("name", ""),
                        "layer": layer.get("name", ""),
                        "layer_type": layer.get("type", ""),
                        "effects": [
                            {
                                "name": e.get("name", ""),
                                "matchName": e.get("matchName", ""),
                                "category": e.get("category", ""),
                                "param_count": len(e.get("params", [])),
                            }
                            for e in effects
                        ],
                    }
                    chains.append(chain)
        return chains

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _read_jsx(self) -> str:
        """读取 JSX 脚本内容。"""
        if not os.path.isfile(self._jsx_path):
            raise FileNotFoundError(f"JSX script not found: {self._jsx_path}")
        with open(self._jsx_path, "r", encoding="utf-8") as f:
            return f.read()

    def _write_command(self, command: Dict[str, Any]) -> None:
        """写入命令文件。"""
        os.makedirs(self._bridge_dir, exist_ok=True)
        with open(_COMMAND_FILE, "w", encoding="utf-8") as f:
            json.dump(command, f, ensure_ascii=False)

    def _wait_for_result(self, timeout: int) -> Optional[Any]:
        """等待结果文件。"""
        import time
        start = time.time()
        while time.time() - start < timeout:
            if os.path.isfile(_RESULT_FILE):
                try:
                    with open(_RESULT_FILE, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception:
                    pass
            time.sleep(0.5)
        return None

    @staticmethod
    def _get_timestamp() -> int:
        """获取当前时间戳。"""
        import time
        return int(time.time())
