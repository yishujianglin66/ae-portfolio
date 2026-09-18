#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adobe_open_source_integration.py — 开源项目集成层
==================================================

将GitHub开源项目集成到现有Adobe Bridge架构:

1. adobe-mcp (VoidChecksum) — COM自动化 + ExtendScript, 45工具/8软件
   - 通过COM直接控制Adobe软件 (无需文件轮询)
   - PowerShell执行ExtendScript
   
2. premiere-pro-mcp (leancoderkavy) — 269工具PR专用
   - CEP插件 + 文件IPC
   - 最全面的Premiere Pro自动化

3. 自研Bridge (本项目) — 文件轮询通信
   - 跨平台兼容
   - 支持无COM环境

集成策略:
  优先使用 adobe-mcp COM → 回退到 premiere-pro-mcp → 回退到自研文件Bridge
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def log(msg: str, level: str = "INFO") -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}][{level}] {msg}")


# ================================================================
#  adobe-mcp COM 自动化封装
# ================================================================

class AdobeCOMAutomation:
    """通过 COM 自动化直接控制 Adobe 软件 (基于 adobe-mcp 项目)
    
    优势: 无需JSX Listener常驻，直接通过COM调用
    限制: 仅Windows，需要Adobe软件已运行
    """
    
    COM_IDS = {
        "photoshop": "Photoshop.Application",
        "illustrator": "Illustrator.Application",
        "premiere": "Premiere.Application",
        "after_effects": "AfterEffects.Application",
        "indesign": "InDesign.Application",
        "animate": "Animate.Application",
        "media_encoder": "MediaEncoder.Application",
    }
    
    def __init__(self):
        self._available = None
    
    def is_available(self) -> bool:
        """检查COM自动化是否可用"""
        if self._available is not None:
            return self._available
        try:
            # 测试PowerShell是否可用
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", "echo ok"],
                capture_output=True, text=True, timeout=5
            )
            self._available = result.returncode == 0
        except Exception:
            self._available = False
        return self._available
    
    def execute_jsx(self, app_key: str, jsx_code: str, timeout: int = 30) -> dict:
        """通过COM在Adobe软件中执行ExtendScript
        
        Args:
            app_key: 软件标识 (photoshop/premiere/after_effects等)
            jsx_code: ExtendScript代码
            timeout: 超时秒数
        
        Returns:
            {"success": True/False, "result": "...", "error": "..."}
        """
        com_id = self.COM_IDS.get(app_key)
        if not com_id:
            return {"success": False, "error": f"Unknown app: {app_key}"}
        
        # 转义JSX代码用于PowerShell嵌入
        escaped_jsx = jsx_code.replace("'", "''").replace('"', '`"')
        
        ps_script = f"""
$app = New-Object -ComObject '{com_id}'
$jsx = @'
{jsx_code}
'@
try {{
    $result = $app.DoJavaScript($jsx)
    Write-Output $result
}} catch {{
    Write-Error $_.Exception.Message
}}
"""
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace"
            )
            if result.returncode == 0:
                return {"success": True, "result": result.stdout.strip()}
            else:
                return {"success": False, "error": result.stderr.strip()}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Timeout after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def execute_powershell(self, ps_code: str, timeout: int = 30) -> dict:
        """直接执行PowerShell脚本 (用于COM操作)"""
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_code],
                capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace"
            )
            return {
                "success": result.returncode == 0,
                "result": result.stdout.strip(),
                "error": result.stderr.strip() if result.returncode != 0 else ""
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def check_app_running(self, app_key: str) -> bool:
        """通过COM检查软件是否运行 (先检查进程再尝试COM)"""
        # 先通过进程名快速判断
        process_map = {
            "photoshop": "Photoshop",
            "illustrator": "Illustrator",
            "premiere": "Premiere",
            "after_effects": "AfterFX",
            "indesign": "InDesign",
            "animate": "Animate",
            "media_encoder": "Media Encoder",
        }
        pname = process_map.get(app_key, "")
        if not pname:
            return False
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {pname}*"],
                capture_output=True, text=True, timeout=3,
                encoding="utf-8", errors="replace"
            )
            if pname.lower() not in result.stdout.lower():
                return False
        except Exception:
            pass
        # 进程存在，尝试验证COM
        com_id = self.COM_IDS.get(app_key)
        if not com_id:
            return False
        ps_script = f"""
try {{
    $app = New-Object -ComObject '{com_id}'
    Write-Output "running"
}} catch {{
    Write-Output "not_running"
}}
"""
        result = self.execute_powershell(ps_script, timeout=5)
        return "running" in result.get("result", "")
    
    def get_app_version(self, app_key: str) -> str:
        """获取软件版本号"""
        com_id = self.COM_IDS.get(app_key)
        if not com_id:
            return ""
        
        ps_script = f"""
$app = New-Object -ComObject '{com_id}'
Write-Output $app.Version
"""
        result = self.execute_powershell(ps_script, timeout=10)
        return result.get("result", "")


# ================================================================
#  Premiere Pro MCP 集成 (269工具)
# ================================================================

class PremiereMCPIntegration:
    """集成 premiere-pro-mcp 的269个Premiere Pro工具
    
    通过文件IPC与CEP插件通信
    """
    
    def __init__(self, temp_dir: str | None = None):
        self.temp_dir = Path(temp_dir) if temp_dir else Path(__file__).parent / ".premiere-mcp-bridge"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.npm_path = Path(r"C:\Users\Administrator\AppData\Roaming\npm\node_modules\premiere-pro-mcp")
    
    def is_available(self) -> bool:
        """检查premiere-pro-mcp是否已安装"""
        return self.npm_path.exists()
    
    def get_tool_count(self) -> int:
        """获取可用工具数量"""
        tools_dir = self.npm_path / "dist" / "tools"
        if tools_dir.exists():
            return len(list(tools_dir.glob("*.js")))
        return 0
    
    def list_tool_modules(self) -> list[str]:
        """列出所有工具模块"""
        tools_dir = self.npm_path / "dist" / "tools"
        if not tools_dir.exists():
            return []
        return [f.stem for f in tools_dir.glob("*.js") if not f.name.endswith(".d.ts")]


# ================================================================
#  统一集成管理器
# ================================================================

class AdobeOpenSourceIntegration:
    """开源项目统一集成管理器
    
    自动选择最佳通信方式:
    1. COM自动化 (adobe-mcp) — 最快速，无需Listener
    2. 文件轮询Bridge (自研) — 跨平台，需Listener常驻
    3. CEP插件 (premiere-pro-mcp) — PR专用，269工具
    """
    
    def __init__(self):
        self.com = AdobeCOMAutomation()
        self.pr_mcp = PremiereMCPIntegration()
        
        # 从 adobe_universal_bridge 导入
        try:
            from adobe_universal_bridge import create_bridge, detect_installed_adobe_apps
            self._create_bridge = create_bridge
            self._detect = detect_installed_adobe_apps
        except ImportError:
            self._create_bridge = None
            self._detect = None
    
    def get_best_method(self, app_key: str) -> str:
        """获取指定软件的最佳通信方式"""
        # 先检查进程是否存在 (快速)
        process_map = {
            "photoshop": "Photoshop", "premiere": "Premiere",
            "after_effects": "AfterFX", "media_encoder": "Media Encoder",
        }
        pname = process_map.get(app_key, "")
        app_running = False
        if pname:
            try:
                r = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {pname}*"],
                    capture_output=True, text=True, timeout=3,
                    encoding="utf-8", errors="replace"
                )
                app_running = pname.lower() in r.stdout.lower()
            except Exception:
                pass
        
        if not app_running:
            return "none"
        
        # 软件运行中，优先COM
        if self.com.is_available():
            return "com"
        
        # 回退到文件Bridge
        if self._create_bridge:
            return "file_bridge"
        
        return "none"
    
    def execute(self, app_key: str, command: str, **kwargs) -> dict:
        """统一执行入口 — 自动选择最佳方式"""
        method = self.get_best_method(app_key)
        
        if method == "com":
            jsx = kwargs.get("jsx", "")
            if jsx:
                return self.com.execute_jsx(app_key, jsx)
            return {"success": False, "error": "No JSX code provided for COM execution"}
        
        elif method == "file_bridge":
            if self._create_bridge:
                bridge = self._create_bridge(app_key)
                return bridge.execute(command, kwargs)
            return {"success": False, "error": "File bridge not available"}
        
        else:
            return {"success": False, "error": f"No communication method available for {app_key}"}
    
    def status_report(self) -> str:
        """生成集成状态报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("  Adobe 开源项目集成状态")
        lines.append("=" * 60)
        
        # adobe-mcp
        lines.append("\n[1] adobe-mcp (COM自动化)")
        lines.append(f"    状态: {'可用' if self.com.is_available() else '不可用'}")
        if self.com.is_available():
            # 只检查已安装且运行中的
            if self._detect:
                installed = self._detect()
                for app_key in installed:
                    running = installed[app_key]["running"]
                    lines.append(f"    {app_key}: {'运行中' if running else '未运行'}")
            else:
                lines.append("    (无法检测已安装软件)")
        
        # premiere-pro-mcp
        lines.append("\n[2] premiere-pro-mcp (269工具)")
        lines.append(f"    状态: {'已安装' if self.pr_mcp.is_available() else '未安装'}")
        if self.pr_mcp.is_available():
            lines.append(f"    工具模块: {self.pr_mcp.get_tool_count()}个")
            modules = self.pr_mcp.list_tool_modules()
            lines.append(f"    模块列表: {', '.join(modules[:10])}{'...' if len(modules) > 10 else ''}")
        
        # 自研Bridge
        lines.append("\n[3] 自研文件Bridge")
        if self._detect:
            installed = self._detect()
            lines.append(f"    已安装: {len(installed)}个Adobe软件")
            for key, info in installed.items():
                lines.append(f"    {key}: {'运行中' if info['running'] else '未运行'}")
        
        # 最佳方式
        lines.append("\n[4] 推荐通信方式")
        for app_key in ["photoshop", "premiere", "after_effects", "media_encoder"]:
            method = self.get_best_method(app_key)
            lines.append(f"    {app_key}: {method}")
        
        return "\n".join(lines)


# ================================================================
#  CLI
# ================================================================

if __name__ == "__main__":
    integration = AdobeOpenSourceIntegration()
    print(integration.status_report())
