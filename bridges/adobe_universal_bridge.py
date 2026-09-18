#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adobe_universal_bridge.py — Adobe 通用 MCP Bridge 基类
=====================================================

基于 AE Bridge 成功经验，抽象出通用 Adobe 软件 Bridge 框架。
所有 Adobe 软件（PS/PR/ME/ID/AI）共享相同的文件轮询通信机制。

架构:
    AdobeUniversalBridge (本文件 - 通用基类)
      ├── PhotoshopBridge     (PS 桥接)
      ├── PremiereBridge      (PR 桥接)
      ├── MediaEncoderBridge  (ME 桥接)
      └── AEBridge            (AE 桥接 - 兼容已有实现)

通信协议:
    Python → 写 {app}_command.json → Adobe JSX Listener 轮询
    Adobe JSX 执行命令 → 写 {app}_result.json → Python 轮询读取

用法:
    bridge = PhotoshopBridge()
    result = bridge.execute("getDocumentInfo")
    result = bridge.execute_script("app.activeDocument.name")
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def log(msg: str, level: str = "INFO") -> None:
    """统一日志输出"""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}][{level}] {msg}")


# ================================================================
#  Adobe 软件配置注册表
# ================================================================

ADOBE_APPS = {
    "photoshop": {
        "name": "Adobe Photoshop",
        "short": "PS",
        "process_names": ["Photoshop"],
        "install_paths": [
            r"C:\Program Files\Adobe\Adobe Photoshop {year}",
            r"C:\Program Files\Adobe\Adobe Photoshop 2025",
            r"C:\Program Files\Adobe\Adobe Photoshop 2024",
        ],
        "startup_subdir": r"Presets\Scripts\Startup",
        "jsx_engine": "photoshop",
        "default_port": 7778,
    },
    "premiere": {
        "name": "Adobe Premiere Pro",
        "short": "PR",
        "process_names": ["Premiere Pro", "Adobe Premiere Pro"],
        "install_paths": [
            r"C:\Program Files\Adobe\Adobe Premiere Pro {year}",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2025",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2024",
        ],
        "startup_subdir": r"Support Files\Scripts\Startup",  
        "jsx_engine": "premiere",
        "default_port": 7779,
    },
    "media_encoder": {
        "name": "Adobe Media Encoder",
        "short": "ME",
        "process_names": ["Adobe Media Encoder"],
        "install_paths": [
            r"C:\Program Files\Adobe\Adobe Media Encoder {year}",
            r"C:\Program Files\Adobe\Adobe Media Encoder 2025",
            r"C:\Program Files\Adobe\Adobe Media Encoder 2024",
        ],
        "startup_subdir": r"Support Files\Scripts\Startup",
        "jsx_engine": "media_encoder",
        "default_port": 7780,
    },
    "after_effects": {
        "name": "Adobe After Effects",
        "short": "AE",
        "process_names": ["AfterFX"],
        "install_paths": [
            r"C:\Program Files\Adobe\Adobe After Effects {year}",
            r"C:\Program Files\Adobe\Adobe After Effects 2025",
            r"C:\Program Files\Adobe\Adobe After Effects 2024",
        ],
        "startup_subdir": r"Support Files\Scripts\Startup",
        "jsx_engine": "after_effects",
        "default_port": 7777,
    },
}


# ================================================================
#  通用 Adobe Bridge 基类
# ================================================================

class AdobeUniversalBridge(ABC):
    """Adobe 通用 Bridge 基类
    
    所有 Adobe 软件的 MCP Bridge 继承此类，实现:
    - 文件轮询通信 (command.json → result.json)
    - HMAC-SHA256 签名验证
    - 进程检测
    - JSX 脚本注入
    """

    # 子类必须设置
    APP_KEY: str = ""          # e.g. "photoshop"
    APP_CONFIG: dict = {}      # ADOBE_APPS 中的配置
    
    def __init__(
        self,
        bridge_dir: str | None = None,
        timeout: int = 15,
        poll_interval: float = 0.5,
        secret: str | None = None,
    ):
        if not self.APP_KEY:
            raise ValueError("子类必须设置 APP_KEY")
        
        self.app_config = ADOBE_APPS.get(self.APP_KEY, self.APP_CONFIG)
        self.short_name = self.app_config.get("short", self.APP_KEY.upper())
        self.timeout = timeout
        self.poll_interval = poll_interval
        
        # Bridge 目录
        project_root = Path(__file__).parent
        self.bridge_dir = Path(bridge_dir) if bridge_dir else project_root / f".{self.APP_KEY}-mcp-bridge"
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        
        # 通信文件
        self.command_file = self.bridge_dir / f"{self.APP_KEY}_command.json"
        self.result_file = self.bridge_dir / f"{self.APP_KEY}_result.json"
        self.log_file = self.bridge_dir / f"{self.APP_KEY}_bridge.log"
        
        # 密钥
        self.secret = secret or self._load_secret()
    
    def _load_secret(self) -> str:
        """加载签名密钥"""
        secret_file = Path(__file__).parent / ".ae-mcp-bridge" / ".mcp_secret"
        if secret_file.exists():
            try:
                return secret_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        # 尝试本app自己的secret
        my_secret = self.bridge_dir / ".mcp_secret"
        if my_secret.exists():
            try:
                return my_secret.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return ""
    
    # ------------------------------------------------------------------
    # 进程检测
    # ------------------------------------------------------------------
    def is_app_running(self) -> bool:
        """检测目标 Adobe 软件是否正在运行"""
        process_names = self.app_config.get("process_names", [])
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq *"],
                capture_output=True, text=True, timeout=5,
                encoding="utf-8", errors="replace"
            )
            running = subprocess.run(
                ["tasklist"],
                capture_output=True, text=True, timeout=5,
                encoding="utf-8", errors="replace"
            )
            for pname in process_names:
                if pname.lower() in running.stdout.lower():
                    return True
        except Exception:
            pass
        return False
    
    def find_install_path(self) -> str | None:
        """查找 Adobe 软件安装路径"""
        for path_template in self.app_config.get("install_paths", []):
            path = path_template.replace("{year}", str(time.localtime().tm_year))
            if Path(path).exists():
                return path
        return None
    
    def get_startup_dir(self) -> str | None:
        """获取 JSX Startup 脚本目录"""
        install_path = self.find_install_path()
        if not install_path:
            return None
        startup = Path(install_path) / self.app_config.get("startup_subdir", "")
        return str(startup) if startup.exists() else None
    
    # ------------------------------------------------------------------
    # 文件通信
    # ------------------------------------------------------------------
    def _generate_signature(self, data: dict) -> str:
        """HMAC-SHA256 签名"""
        if not self.secret:
            return ""
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hmac.new(
            self.secret.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    
    def _write_command(self, command: dict) -> None:
        """写入命令文件"""
        self.command_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.command_file, "w", encoding="utf-8") as f:
            json.dump(command, f, ensure_ascii=False, indent=2)
    
    def _read_result(self) -> dict | None:
        """读取结果文件"""
        if not self.result_file.exists():
            return None
        try:
            with open(self.result_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    
    def _wait_result(self) -> dict:
        """轮询等待结果"""
        start = time.time()
        while time.time() - start < self.timeout:
            result = self._read_result()
            if result and result.get("status") in ("success", "error", "timeout"):
                return result
            time.sleep(self.poll_interval)
        return {"status": "timeout", "error": f"Timeout after {self.timeout}s", "result": None}
    
    def _clear_result(self) -> None:
        """清除结果文件"""
        if self.result_file.exists():
            try:
                self.result_file.unlink()
            except OSError:
                pass
    
    # ------------------------------------------------------------------
    # 核心命令执行
    # ------------------------------------------------------------------
    def execute(self, command: str, args: dict | None = None, timeout: int | None = None) -> dict:
        """执行命令
        
        Args:
            command: 命令名称 (e.g. "getDocumentInfo", "executeScript")
            args: 命令参数
            timeout: 超时秒数 (覆盖默认)
        
        Returns:
            {"status": "success"|"error"|"timeout", "result": ..., "error": ...}
        """
        if timeout:
            self.timeout = timeout
        
        self._clear_result()
        
        cmd_data = {
            "command": command,
            "args": args or {},
            "status": "pending",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "app": self.APP_KEY,
            "signature": self._generate_signature({"command": command, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}),
            "processed": False,
        }
        
        self._write_command(cmd_data)
        result = self._wait_result()
        
        self._log(f"CMD {command} -> {result.get('status', 'unknown')}")
        return result
    
    def execute_script(self, script: str, timeout: int | None = None) -> dict:
        """执行 ExtendScript 脚本
        
        Args:
            script: ExtendScript 代码字符串
            timeout: 超时秒数
        
        Returns:
            {"status": "success", "result": "<script output>", ...}
        """
        return self.execute("executeScript", {"script": script}, timeout=timeout)
    
    def ping(self) -> bool:
        """测试 Bridge 连接"""
        result = self.execute("ping", timeout=5)
        return result.get("status") == "success"
    
    def get_app_info(self) -> dict:
        """获取 Adobe 软件信息"""
        result = self.execute("getAppInfo")
        return result.get("result", {}) if result.get("status") == "success" else {}
    
    # ------------------------------------------------------------------
    # JSX 安装
    # ------------------------------------------------------------------
    def install_startup_jsx(self, jsx_source_path: str) -> bool:
        """安装 JSX Listener 到 Adobe Startup 目录
        
        Args:
            jsx_source_path: 项目中的 JSX 源文件路径
        
        Returns:
            True=安装成功
        """
        startup_dir = self.get_startup_dir()
        if not startup_dir:
            log(f"{self.short_name}: 未找到安装路径，无法安装Startup脚本", "WARN")
            return False
        
        # 创建轻量加载器
        loader_name = f"mcp_{self.APP_KEY}_listener.jsx"
        loader_path = Path(startup_dir) / loader_name
        
        # 使用正斜杠避免JSX路径转义问题
        jsx_abs = Path(jsx_source_path).resolve()
        jsx_posix = str(jsx_abs).replace("\\", "/")
        
        loader_content = f"""// MCP Bridge Listener - {self.short_name} Auto Loader
// Auto-installed by adobe_universal_bridge.py
(function() {{
    try {{
        var listenerPath = "{jsx_posix}";
        if (new File(listenerPath).exists) {{
            $.evalFile(listenerPath);
            $.writeln("[MCP {self.short_name}] Listener loaded: " + listenerPath);
        }} else {{
            $.writeln("[MCP {self.short_name}] Not found: " + listenerPath);
        }}
    }} catch(e) {{
        $.writeln("[MCP {self.short_name}] Load error: " + e.message);
    }}
}})();
"""
        try:
            loader_path.write_text(loader_content, encoding="utf-8")
            log(f"{self.short_name}: Startup loader installed -> {loader_path}")
            return True
        except PermissionError:
            log(f"{self.short_name}: 需要管理员权限写入 {startup_dir}", "WARN")
            return False
        except Exception as e:
            log(f"{self.short_name}: 安装失败: {e}", "ERROR")
            return False
    
    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------
    def _log(self, msg: str) -> None:
        """写入日志文件"""
        try:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
        except Exception:
            pass
    
    def __repr__(self) -> str:
        running = self.is_app_running()
        return f"<{self.__class__.__name__} running={running} bridge={self.bridge_dir}>"


# ================================================================
#  具体软件 Bridge 实现
# ================================================================

class PhotoshopBridge(AdobeUniversalBridge):
    """Photoshop MCP Bridge"""
    APP_KEY = "photoshop"
    
    def execute_script(self, script: str, timeout: int | None = None) -> dict:
        """PS 脚本执行 (包装为 PS 兼容格式)"""
        return self.execute("executeScript", {"script": script}, timeout=timeout)
    
    def get_document_info(self) -> dict:
        """获取当前文档信息"""
        return self.execute("getDocumentInfo")
    
    def apply_filter(self, filter_name: str, params: dict | None = None) -> dict:
        """应用滤镜"""
        return self.execute("applyFilter", {"filter": filter_name, "params": params or {}})
    
    def export_document(self, output_path: str, format: str = "png") -> dict:
        """导出文档"""
        return self.execute("exportDocument", {"path": output_path, "format": format})
    
    def create_document(self, width: int, height: int, name: str = "Untitled") -> dict:
        """创建新文档"""
        return self.execute("createDocument", {"width": width, "height": height, "name": name})


class PremiereBridge(AdobeUniversalBridge):
    """Premiere Pro MCP Bridge"""
    APP_KEY = "premiere"
    
    def get_project_info(self) -> dict:
        """获取项目信息"""
        return self.execute("getProjectInfo")
    
    def import_media(self, file_paths: list[str]) -> dict:
        """导入媒体文件"""
        return self.execute("importMedia", {"files": file_paths})
    
    def add_to_sequence(self, clip_name: str, track: int = 1, position: float = 0) -> dict:
        """添加片段到序列"""
        return self.execute("addToSequence", {"clip": clip_name, "track": track, "position": position})
    
    def apply_transition(self, transition_name: str, duration: float = 1.0) -> dict:
        """应用转场"""
        return self.execute("applyTransition", {"name": transition_name, "duration": duration})
    
    def export_sequence(self, output_path: str, preset: str = "H.264") -> dict:
        """导出序列"""
        return self.execute("exportSequence", {"path": output_path, "preset": preset})
    
    def get_timeline_info(self) -> dict:
        """获取时间线信息"""
        return self.execute("getTimelineInfo")


class MediaEncoderBridge(AdobeUniversalBridge):
    """Media Encoder MCP Bridge"""
    APP_KEY = "media_encoder"
    
    def add_to_queue(self, source_path: str, preset: str = "H.264") -> dict:
        """添加到编码队列"""
        return self.execute("addToQueue", {"source": source_path, "preset": preset})
    
    def start_encoding(self) -> dict:
        """开始编码"""
        return self.execute("startEncoding")
    
    def get_queue_status(self) -> dict:
        """获取队列状态"""
        return self.execute("getQueueStatus")
    
    def get_presets(self) -> dict:
        """获取可用预设"""
        return self.execute("getPresets")


class AfterEffectsBridge(AdobeUniversalBridge):
    """After Effects MCP Bridge (兼容已有实现)"""
    APP_KEY = "after_effects"
    
    def __init__(self, **kwargs):
        # AE 使用已有的 .ae-mcp-bridge 目录
        project_root = Path(__file__).parent
        kwargs.setdefault("bridge_dir", str(project_root / ".ae-mcp-bridge"))
        super().__init__(**kwargs)


# ================================================================
#  Bridge 工厂
# ================================================================

def create_bridge(app_key: str, **kwargs) -> AdobeUniversalBridge:
    """创建指定软件的 Bridge 实例
    
    Args:
        app_key: "photoshop" | "premiere" | "media_encoder" | "after_effects"
    
    Returns:
        对应的 Bridge 实例
    """
    bridge_classes = {
        "photoshop": PhotoshopBridge,
        "premiere": PremiereBridge,
        "media_encoder": MediaEncoderBridge,
        "after_effects": AfterEffectsBridge,
    }
    cls = bridge_classes.get(app_key)
    if not cls:
        raise ValueError(f"Unknown app: {app_key}. Available: {list(bridge_classes.keys())}")
    return cls(**kwargs)


def detect_installed_adobe_apps() -> dict[str, dict]:
    """检测系统上已安装的 Adobe 软件
    
    Returns:
        {"photoshop": {"path": "...", "running": True/False}, ...}
    """
    detected = {}
    for app_key, config in ADOBE_APPS.items():
        install_path = None
        for path_tpl in config.get("install_paths", []):
            path = path_tpl.replace("{year}", str(time.localtime().tm_year))
            if Path(path).exists():
                install_path = path
                break
        
        if install_path:
            # 检查是否运行
            running = False
            try:
                result = subprocess.run(
                    ["tasklist"], capture_output=True, text=True, timeout=5,
                    encoding="utf-8", errors="replace"
                )
                for pname in config.get("process_names", []):
                    if pname.lower() in result.stdout.lower():
                        running = True
                        break
            except Exception:
                pass
            
            detected[app_key] = {
                "name": config["name"],
                "short": config["short"],
                "path": install_path,
                "running": running,
                "startup_dir": str(Path(install_path) / config.get("startup_subdir", "")),
            }
    
    return detected


# ================================================================
#  自测
# ================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Adobe Universal Bridge - 系统检测")
    print("=" * 60)
    
    # 检测已安装的 Adobe 软件
    installed = detect_installed_adobe_apps()
    print(f"\n已安装 {len(installed)} 个 Adobe 软件:")
    for key, info in installed.items():
        status = "运行中" if info["running"] else "未运行"
        print(f"  [{info['short']}] {info['name']}")
        print(f"       路径: {info['path']}")
        print(f"       状态: {status}")
    
    # 测试每个 Bridge
    print("\n--- Bridge 测试 ---")
    for key in installed:
        try:
            bridge = create_bridge(key)
            print(f"  {key}: {bridge}")
            if installed[key]["running"]:
                pong = bridge.ping()
                print(f"    ping: {'OK' if pong else 'FAIL'}")
        except Exception as e:
            print(f"  {key}: ERROR - {e}")
    
    print("\n完成!")
