#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adobe_mcp_manager.py — Adobe MCP 统一管理器
============================================

统一管理所有 Adobe 软件的 MCP Bridge:
  - 自动检测已安装的 Adobe 软件
  - 安装/卸载 Startup JSX Listener
  - 提供统一的命令接口
  - 生成 MCP Server 配置

用法:
    manager = AdobeMCPManager()
    manager.detect_all()           # 检测已安装软件
    manager.install_all()          # 安装所有 Bridge
    manager.send_command("photoshop", "getDocumentInfo")
    
    # 或者通过统一接口
    ps = manager.get_bridge("photoshop")
    result = ps.execute_script("app.activeDocument.name")
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from adobe_universal_bridge import (
    ADOBE_APPS,
    AdobeUniversalBridge,
    AfterEffectsBridge,
    MediaEncoderBridge,
    PhotoshopBridge,
    PremiereBridge,
    create_bridge,
    detect_installed_adobe_apps,
    log,
)


class AdobeMCPManager:
    """Adobe MCP 统一管理器"""
    
    def __init__(self, project_root: str | None = None):
        self.project_root = Path(project_root) if project_root else Path(__file__).parent
        self.bridges: dict[str, AdobeUniversalBridge] = {}
        self.installed_apps: dict[str, dict] = {}
        self.jsx_files: dict[str, str] = {
            "photoshop": self._locate_listener("photoshop_mcp_listener.jsx"),
            "premiere": self._locate_listener("premiere_mcp_listener.jsx"),
            "media_encoder": self._locate_listener("media_encoder_mcp_listener.jsx"),
            "after_effects": self._locate_listener("ae_mcp_auto_listener.jsx"),
        }

    def _locate_listener(self, filename: str) -> str:
        """定位 JSX 监听器文件 (2026-09-19 修复)。

        监听器实际放在**仓库根**, 而本模块默认 project_root = bridges/,
        原实现按 project_root 解析 → 四个监听器全部指向 bridges/*.jsx
        (不存在), 于是 install_bridge 必然在"JSX文件不存在"分支返回 False,
        交互通道的 Bridge 安装一直是坏的。
        改为依次在 project_root 与其上一层查找, 命中即用。
        """
        for base in (self.project_root, self.project_root.parent):
            p = base / filename
            if p.exists():
                return str(p)
        return str(self.project_root / filename)   # 保底: 报缺失时路径可读
    
    # ------------------------------------------------------------------
    # 检测
    # ------------------------------------------------------------------
    def detect_all(self) -> dict[str, dict]:
        """检测系统上所有已安装的 Adobe 软件"""
        self.installed_apps = detect_installed_adobe_apps()
        log(f"检测到 {len(self.installed_apps)} 个 Adobe 软件")
        for key, info in self.installed_apps.items():
            status = "运行中" if info["running"] else "未运行"
            log(f"  [{info['short']}] {info['name']} - {status}")
        return self.installed_apps
    
    def get_installed_apps(self) -> list[str]:
        """获取已安装的 Adobe 软件列表"""
        if not self.installed_apps:
            self.detect_all()
        return list(self.installed_apps.keys())
    
    def is_app_installed(self, app_key: str) -> bool:
        """检查某个软件是否已安装"""
        if not self.installed_apps:
            self.detect_all()
        return app_key in self.installed_apps
    
    def is_app_running(self, app_key: str) -> bool:
        """检查某个软件是否正在运行"""
        if not self.installed_apps:
            self.detect_all()
        return self.installed_apps.get(app_key, {}).get("running", False)
    
    # ------------------------------------------------------------------
    # Bridge 管理
    # ------------------------------------------------------------------
    def get_bridge(self, app_key: str) -> AdobeUniversalBridge:
        """获取指定软件的 Bridge 实例"""
        if app_key not in self.bridges:
            self.bridges[app_key] = create_bridge(app_key)
        return self.bridges[app_key]
    
    def install_bridge(self, app_key: str) -> bool:
        """安装指定软件的 JSX Listener 到 Startup 目录"""
        if app_key not in self.installed_apps:
            log(f"[{app_key}] 未安装，无法安装Bridge", "WARN")
            return False
        
        jsx_path = self.jsx_files.get(app_key)
        if not jsx_path or not Path(jsx_path).exists():
            log(f"[{app_key}] JSX文件不存在: {jsx_path}", "WARN")
            return False
        
        bridge = self.get_bridge(app_key)
        return bridge.install_startup_jsx(jsx_path)
    
    def install_all(self) -> dict[str, bool]:
        """安装所有已安装软件的 Bridge"""
        results = {}
        for app_key in self.installed_apps:
            results[app_key] = self.install_bridge(app_key)
        return results
    
    def uninstall_bridge(self, app_key: str) -> bool:
        """卸载指定软件的 Startup Listener。

        2026-09-24 修复：原实现只认 `mcp_{app_key}_listener.jsx`（即
        `adobe_universal_bridge.install_startup_jsx` 写出的名字）。但现场实际存在的是
        **另一条手工安装路径**留下的 `z_mcp_bridge_startup.jsx`（AE 那份，靠
        app.scheduleTask 延迟 eval 监听器）——旧实现在这种情形下会"什么也没删却返回 True"，
        于是那个已经失效的加载器一直留在 AE 的 Startup 目录里（实测：它在 AE 25.3 上
        根本不执行，日志停在 2026-09-19）。
        现改为按**候选名单**逐个尝试，并把"一个都没找到"与"删失败"区分开。
        """
        startup_dir = self.installed_apps.get(app_key, {}).get("startup_dir")
        if not startup_dir:
            return False

        candidates = [
            f"mcp_{app_key}_listener.jsx",          # 官方安装器写法
            "z_mcp_bridge_startup.jsx",             # 手工路径（AE 现场就是这个）
            f"z_mcp_{app_key}_startup.jsx",
            f"mcp_{app_key}_bridge_startup.jsx",
        ]
        removed: list[str] = []
        failed: list[str] = []
        for name in candidates:
            p = Path(startup_dir) / name
            if not p.exists():
                continue
            try:
                # 先留档再删：出问题可人工恢复（Startup 目录里留 .bak 也不会被执行）
                backup = p.with_suffix(p.suffix + ".uninstalled.bak")
                if backup.exists():
                    backup.unlink()
                p.rename(backup)
                removed.append(name)
            except Exception as e:
                failed.append(f"{name}: {e}")

        if failed:
            log(f"[{app_key}] 卸载失败: {'; '.join(failed)}", "ERROR")
            return False
        if removed:
            log(f"[{app_key}] Startup listener 已移除（留档为 .uninstalled.bak）: "
                f"{', '.join(removed)}")
            return True
        log(f"[{app_key}] Startup 目录未见任何已知加载器（可能本就未安装）")
        return True
    
    # ------------------------------------------------------------------
    # 命令执行
    # ------------------------------------------------------------------
    def send_command(self, app_key: str, command: str, args: dict | None = None, 
                     timeout: int | None = None) -> dict:
        """向指定软件发送命令
        
        Args:
            app_key: "photoshop" | "premiere" | "media_encoder" | "after_effects"
            command: 命令名称
            args: 命令参数
            timeout: 超时秒数
        
        Returns:
            {"status": "success"|"error"|"timeout", "result": ..., "error": ...}
        """
        bridge = self.get_bridge(app_key)
        return bridge.execute(command, args, timeout=timeout)
    
    def execute_script(self, app_key: str, script: str, timeout: int | None = None) -> dict:
        """在指定软件中执行 ExtendScript"""
        bridge = self.get_bridge(app_key)
        return bridge.execute_script(script, timeout=timeout)
    
    def ping_all(self) -> dict[str, bool]:
        """测试所有 Bridge 连接"""
        results = {}
        for app_key in self.installed_apps:
            if self.installed_apps[app_key]["running"]:
                bridge = self.get_bridge(app_key)
                results[app_key] = bridge.ping()
            else:
                results[app_key] = False
        return results
    
    # ------------------------------------------------------------------
    # 高级功能
    # ------------------------------------------------------------------
    def get_all_app_info(self) -> dict[str, dict]:
        """获取所有运行中软件的详细信息"""
        info = {}
        for app_key in self.installed_apps:
            if self.installed_apps[app_key]["running"]:
                bridge = self.get_bridge(app_key)
                try:
                    app_info = bridge.get_app_info()
                    info[app_key] = app_info
                except Exception as e:
                    info[app_key] = {"error": str(e)}
        return info
    
    def batch_execute(self, command: str, args: dict | None = None, 
                      target_apps: list[str] | None = None) -> dict[str, dict]:
        """在多个软件中批量执行同一命令
        
        Args:
            command: 命令名称
            args: 命令参数
            target_apps: 目标软件列表 (None=所有运行中的)
        
        Returns:
            {"photoshop": {"status": "success", ...}, "premiere": {...}, ...}
        """
        if target_apps is None:
            target_apps = [k for k, v in self.installed_apps.items() if v["running"]]
        
        results = {}
        for app_key in target_apps:
            if app_key in self.installed_apps and self.installed_apps[app_key]["running"]:
                results[app_key] = self.send_command(app_key, command, args)
        return results
    
    # ------------------------------------------------------------------
    # MCP 配置生成
    # ------------------------------------------------------------------
    def generate_mcp_config(self, output_path: str | None = None) -> str:
        """生成 MCP Server 配置 (用于 Qoder/其他 MCP 客户端)
        
        Returns:
            JSON 配置字符串
        """
        config = {
            "mcpServers": {}
        }
        
        for app_key, info in self.installed_apps.items():
            server_name = f"Adobe{info['short']}MCP"
            jsx_path = self.jsx_files.get(app_key, "")
            
            config["mcpServers"][server_name] = {
                "command": "python",
                "args": [
                    str(self.project_root / "adobe_mcp_server.py"),
                    "--app", app_key,
                    "--jsx", jsx_path,
                ],
                "env": {
                    "ADOBE_APP": app_key,
                    "BRIDGE_DIR": str(self.project_root / f".{app_key}-mcp-bridge"),
                }
            }
        
        config_json = json.dumps(config, indent=2, ensure_ascii=False)
        
        if output_path:
            Path(output_path).write_text(config_json, encoding="utf-8")
            log(f"MCP config written to: {output_path}")
        
        return config_json
    
    # ------------------------------------------------------------------
    # 状态报告
    # ------------------------------------------------------------------
    def status_report(self) -> str:
        """生成系统状态报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("  Adobe MCP Bridge 系统状态报告")
        lines.append("=" * 60)
        
        if not self.installed_apps:
            self.detect_all()
        
        lines.append(f"\n已安装: {len(self.installed_apps)} 个 Adobe 软件")
        lines.append("")
        
        for app_key, info in self.installed_apps.items():
            status = "运行中" if info["running"] else "未运行"
            lines.append(f"  [{info['short']}] {info['name']}")
            lines.append(f"       路径: {info['path']}")
            lines.append(f"       状态: {status}")
            
            # Bridge 状态
            bridge_dir = self.project_root / f".{app_key}-mcp-bridge"
            if bridge_dir.exists():
                lines.append(f"       Bridge: {bridge_dir}")
                # 检查 listener log
                log_file = bridge_dir / f"{app_key}_bridge.log"
                if log_file.exists():
                    lines.append("       日志: 有")
            else:
                lines.append("       Bridge: 未初始化")
            
            # Startup 检查
            startup = info.get("startup_dir", "")
            if startup and Path(startup).exists():
                loader = Path(startup) / f"mcp_{app_key}_listener.jsx"
                if loader.exists():
                    lines.append("       Startup: 已安装")
                else:
                    lines.append("       Startup: 未安装")
            
            lines.append("")
        
        return "\n".join(lines)


# ================================================================
#  独立 MCP Server 入口 (供 Qoder MCP 调用)
# ================================================================

class AdobeMCPServer:
    """轻量 MCP Server 包装器 - 通过 stdin/stdout 与 MCP 客户端通信
    
    用法:
        python adobe_mcp_manager.py --app photoshop
    """
    
    def __init__(self, app_key: str):
        self.app_key = app_key
        self.manager = AdobeMCPManager()
        self.bridge = self.manager.get_bridge(app_key)
    
    def handle_request(self, method: str, params: dict) -> dict:
        """处理 MCP 请求"""
        if method == "tools/list":
            return self._list_tools()
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            return self._call_tool(tool_name, arguments)
        elif method == "initialize":
            return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}
        else:
            return {"error": f"Unknown method: {method}"}
    
    def _list_tools(self) -> dict:
        """列出可用工具"""
        app_info = self.manager.installed_apps.get(self.app_key, {})
        short = app_info.get("short", self.app_key.upper())
        
        tools = [
            {
                "name": "execute_script",
                "description": f"在 {short} 中执行 ExtendScript 代码",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script": {"type": "string", "description": "ExtendScript 代码"},
                        "timeout": {"type": "integer", "description": "超时秒数", "default": 15}
                    },
                    "required": ["script"]
                }
            },
            {
                "name": "ping",
                "description": f"测试 {short} Bridge 连接",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "get_app_info",
                "description": f"获取 {short} 应用信息",
                "inputSchema": {"type": "object", "properties": {}}
            },
        ]
        
        # App-specific tools
        if self.app_key == "photoshop":
            tools.extend([
                {"name": "get_document_info", "description": "获取当前文档信息",
                 "inputSchema": {"type": "object", "properties": {}}},
                {"name": "apply_filter", "description": "应用滤镜",
                 "inputSchema": {"type": "object", "properties": {
                     "filter": {"type": "string"}, "params": {"type": "object"}}}},
                {"name": "export_document", "description": "导出文档",
                 "inputSchema": {"type": "object", "properties": {
                     "path": {"type": "string"}, "format": {"type": "string", "default": "png"}}}},
                {"name": "create_document", "description": "创建新文档",
                 "inputSchema": {"type": "object", "properties": {
                     "width": {"type": "integer"}, "height": {"type": "integer"},
                     "name": {"type": "string"}}}},
            ])
        elif self.app_key == "premiere":
            tools.extend([
                {"name": "get_project_info", "description": "获取项目信息",
                 "inputSchema": {"type": "object", "properties": {}}},
                {"name": "import_media", "description": "导入媒体文件",
                 "inputSchema": {"type": "object", "properties": {
                     "files": {"type": "array", "items": {"type": "string"}}}}},
                {"name": "get_timeline_info", "description": "获取时间线信息",
                 "inputSchema": {"type": "object", "properties": {}}},
                {"name": "export_sequence", "description": "导出序列",
                 "inputSchema": {"type": "object", "properties": {
                     "path": {"type": "string"}, "preset": {"type": "string"}}}},
            ])
        elif self.app_key == "media_encoder":
            tools.extend([
                {"name": "add_to_queue", "description": "添加到编码队列",
                 "inputSchema": {"type": "object", "properties": {
                     "source": {"type": "string"}, "preset": {"type": "string"}}}},
                {"name": "start_encoding", "description": "开始编码",
                 "inputSchema": {"type": "object", "properties": {}}},
                {"name": "get_queue_status", "description": "获取队列状态",
                 "inputSchema": {"type": "object", "properties": {}}},
                {"name": "get_presets", "description": "获取可用预设",
                 "inputSchema": {"type": "object", "properties": {}}},
            ])
        
        return {"tools": tools}
    
    def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        """调用工具"""
        if tool_name == "execute_script":
            result = self.bridge.execute_script(
                arguments["script"], 
                timeout=arguments.get("timeout", 15)
            )
        elif tool_name == "ping":
            pong = self.bridge.ping()
            result = {"status": "success" if pong else "error", "result": "pong" if pong else "no response"}
        elif tool_name == "get_app_info":
            result = {"status": "success", "result": self.bridge.get_app_info()}
        elif tool_name == "get_document_info":
            result = self.bridge.execute("getDocumentInfo")
        elif tool_name == "apply_filter":
            result = self.bridge.execute("applyFilter", arguments)
        elif tool_name == "export_document":
            result = self.bridge.execute("exportDocument", arguments)
        elif tool_name == "create_document":
            result = self.bridge.execute("createDocument", arguments)
        elif tool_name == "get_project_info":
            result = self.bridge.execute("getProjectInfo")
        elif tool_name == "import_media":
            result = self.bridge.execute("importMedia", arguments)
        elif tool_name == "get_timeline_info":
            result = self.bridge.execute("getTimelineInfo")
        elif tool_name == "export_sequence":
            result = self.bridge.execute("exportSequence", arguments)
        elif tool_name == "add_to_queue":
            result = self.bridge.execute("addToQueue", arguments)
        elif tool_name == "start_encoding":
            result = self.bridge.execute("startEncoding")
        elif tool_name == "get_queue_status":
            result = self.bridge.execute("getQueueStatus")
        elif tool_name == "get_presets":
            result = self.bridge.execute("getPresets")
        else:
            result = {"status": "error", "error": f"Unknown tool: {tool_name}"}
        
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}
    
    def run_stdio(self):
        """运行 stdio 模式 MCP Server"""
        import sys
        
        log(f"MCP Server started for {self.app_key}")
        
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            try:
                request = json.loads(line)
                method = request.get("method", "")
                params = request.get("params", {})
                req_id = request.get("id", 0)
                
                response = self.handle_request(method, params)
                response["id"] = req_id
                
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                
            except json.JSONDecodeError:
                continue
            except Exception as e:
                error_resp = {"id": 0, "error": str(e)}
                sys.stdout.write(json.dumps(error_resp) + "\n")
                sys.stdout.flush()


# ================================================================
#  CLI 入口
# ================================================================

def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Adobe MCP Bridge Manager")
    parser.add_argument("--app", type=str, help="Target Adobe app key")
    parser.add_argument("--detect", action="store_true", help="Detect installed Adobe apps")
    parser.add_argument("--install", action="store_true", help="Install all bridges")
    parser.add_argument("--status", action="store_true", help="Show status report")
    parser.add_argument("--mcp-config", type=str, help="Generate MCP config to file")
    parser.add_argument("--server", action="store_true", help="Run as MCP stdio server")
    
    args = parser.parse_args()
    
    if args.server and args.app:
        # Run as MCP server
        server = AdobeMCPServer(args.app)
        server.run_stdio()
        return
    
    manager = AdobeMCPManager()
    
    if args.detect:
        manager.detect_all()
    elif args.install:
        manager.detect_all()
        results = manager.install_all()
        for app, ok in results.items():
            print(f"  {app}: {'OK' if ok else 'FAIL'}")
    elif args.status:
        manager.detect_all()
        print(manager.status_report())
    elif args.mcp_config:
        manager.detect_all()
        config = manager.generate_mcp_config(args.mcp_config)
        print(config)
    else:
        # Default: show status
        manager.detect_all()
        print(manager.status_report())


if __name__ == "__main__":
    main()
