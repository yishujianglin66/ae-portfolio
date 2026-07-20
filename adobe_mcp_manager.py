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

import os
import json
import time
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from adobe_universal_bridge import (
    AdobeUniversalBridge,
    PhotoshopBridge,
    PremiereBridge,
    MediaEncoderBridge,
    AfterEffectsBridge,
    ADOBE_APPS,
    create_bridge,
    detect_installed_adobe_apps,
    log,
)


class AdobeMCPManager:
    """Adobe MCP 统一管理器"""
    
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root) if project_root else Path(__file__).parent
        self.bridges: Dict[str, AdobeUniversalBridge] = {}
        self.installed_apps: Dict[str, Dict] = {}
        self.jsx_files: Dict[str, str] = {
            "photoshop": str(self.project_root / "photoshop_mcp_listener.jsx"),
            "premiere": str(self.project_root / "premiere_mcp_listener.jsx"),
            "media_encoder": str(self.project_root / "media_encoder_mcp_listener.jsx"),
            "after_effects": str(self.project_root / "ae_mcp_auto_listener.jsx"),
        }
    
    # ------------------------------------------------------------------
    # 检测
    # ------------------------------------------------------------------
    def detect_all(self) -> Dict[str, Dict]:
        """检测系统上所有已安装的 Adobe 软件"""
        self.installed_apps = detect_installed_adobe_apps()
        log(f"检测到 {len(self.installed_apps)} 个 Adobe 软件")
        for key, info in self.installed_apps.items():
            status = "运行中" if info["running"] else "未运行"
            log(f"  [{info['short']}] {info['name']} - {status}")
        return self.installed_apps
    
    def get_installed_apps(self) -> List[str]:
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
    
    def install_all(self) -> Dict[str, bool]:
        """安装所有已安装软件的 Bridge"""
        results = {}
        for app_key in self.installed_apps:
            results[app_key] = self.install_bridge(app_key)
        return results
    
    def uninstall_bridge(self, app_key: str) -> bool:
        """卸载指定软件的 Startup Listener"""
        startup_dir = self.installed_apps.get(app_key, {}).get("startup_dir")
        if not startup_dir:
            return False
        
        loader_name = f"mcp_{app_key}_listener.jsx"
        loader_path = Path(startup_dir) / loader_name
        
        if loader_path.exists():
            try:
                loader_path.unlink()
                log(f"[{app_key}] Startup listener removed")
                return True
            except Exception as e:
                log(f"[{app_key}] 卸载失败: {e}", "ERROR")
                return False
        return True
    
    # ------------------------------------------------------------------
    # 命令执行
    # ------------------------------------------------------------------
    def send_command(self, app_key: str, command: str, args: Optional[Dict] = None, 
                     timeout: Optional[int] = None) -> Dict:
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
    
    def execute_script(self, app_key: str, script: str, timeout: Optional[int] = None) -> Dict:
        """在指定软件中执行 ExtendScript"""
        bridge = self.get_bridge(app_key)
        return bridge.execute_script(script, timeout=timeout)
    
    def ping_all(self) -> Dict[str, bool]:
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
    def get_all_app_info(self) -> Dict[str, Dict]:
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
    
    def batch_execute(self, command: str, args: Optional[Dict] = None, 
                      target_apps: Optional[List[str]] = None) -> Dict[str, Dict]:
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
    def generate_mcp_config(self, output_path: Optional[str] = None) -> str:
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
                    lines.append(f"       日志: 有")
            else:
                lines.append(f"       Bridge: 未初始化")
            
            # Startup 检查
            startup = info.get("startup_dir", "")
            if startup and Path(startup).exists():
                loader = Path(startup) / f"mcp_{app_key}_listener.jsx"
                if loader.exists():
                    lines.append(f"       Startup: 已安装")
                else:
                    lines.append(f"       Startup: 未安装")
            
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
    
    def handle_request(self, method: str, params: Dict) -> Dict:
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
    
    def _list_tools(self) -> Dict:
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
    
    def _call_tool(self, tool_name: str, arguments: Dict) -> Dict:
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
