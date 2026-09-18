#!/usr/bin/env python3
# ============================================================
# AE 自动化渲染编排器 - 全链路实战复刻 + 渲染输出
# ============================================================
# 功能：
#   1. 自动检测/打开 AE，加载指定项目文件
#   2. 按步骤操作图层/属性/关键帧完成复刻
#   3. 配置渲染设置与输出模块（本地路径 + 视频格式）
#   4. 执行渲染并监控进度，自动保存并关闭 AE
#   5. 完整异常处理 + 结构化报告输出
#
# 用法：
#   python scripts/ae_auto_render_orchestrator.py
#   python scripts/ae_auto_render_orchestrator.py --project ./my_project.aep --output ./renders
#   python scripts/ae_auto_render_orchestrator.py --format mp4 --step-file ./my_steps.json
#   python scripts/ae_auto_render_orchestrator.py --dry-run           # 预演模式
#   python scripts/ae_auto_render_orchestrator.py --skip-render       # 跳过渲染
# ============================================================

import argparse
import glob
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import textwrap
import threading
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ============================================================
# 数据类型定义
# ============================================================


class AEPhase(Enum):
    """AE 自动化执行阶段"""
    INIT = "初始化环境"
    DETECTING = "检测 AE 安装"
    LAUNCHING = "启动 AE"
    CONNECTING = "连接 Bridge"
    LOADING = "加载项目"
    EXECUTING = "执行复刻步骤"
    CONFIGURING_RENDER = "配置渲染"
    RENDERING = "执行渲染"
    MONITORING = "监控渲染进度"
    SAVING = "保存项目"
    CLOSING = "关闭 AE"
    COMPLETE = "流程完成"
    ABORTED = "流程中止"
    ERROR = "错误状态"


class StepStatus(Enum):
    """步骤执行状态"""
    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    SKIP = "⚪ SKIP"
    WARN = "⚠️ WARN"
    PENDING = "⏳ PENDING"


@dataclass
class StepResult:
    """单个复刻步骤的执行结果"""
    step_id: str
    module: str
    description: str
    status: StepStatus = StepStatus.PENDING
    message: str = ""
    error_type: str = ""
    error_traceback: str = ""
    elapsed_ms: float = 0.0
    retry_count: int = 0
    jsx_cmd: str = ""  # 执行的 JSX 命令摘要
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class RenderConfig:
    """渲染配置"""
    output_dir: str = ""
    output_filename: str = "ae_reproduction_output"
    output_format: str = "avi"  # avi / mov / jpeg_sequence / png_sequence / psd_sequence
    resolution_multiplier: float = 1.0  # 1.0=Full, 0.5=Half, 0.25=Quarter
    drop_frame_rate: int = 0  # 0=不丢帧, 1=丢半帧, 2=丢一帧
    skip_existing: bool = False
    timeout_minutes: int = 30
    use_work_area: bool = False
    custom_render_settings: dict[str, Any] | None = None
    custom_output_module: dict[str, Any] | None = None


@dataclass
class OrchestratorReport:
    """编排器最终报告"""
    session_id: str
    title: str
    phase: AEPhase = AEPhase.INIT
    start_time: str = ""
    end_time: str = ""
    total_elapsed_ms: float = 0.0

    # 项目信息
    project_file: str = ""
    project_loaded: bool = False
    composition_name: str = ""
    composition_duration: float = 0.0

    # 复刻步骤统计
    total_steps: int = 0
    steps_passed: int = 0
    steps_failed: int = 0
    steps_skipped: int = 0
    steps_warn: int = 0

    # 渲染统计
    render_success: bool = False
    render_output_path: str = ""
    render_duration_ms: float = 0.0
    render_format: str = ""
    render_resolution: str = ""
    output_file_size_mb: float = 0.0
    output_frame_count: int = 0
    render_method: str = ""  # "aerender_cli" / "bridge_extendscript" / "manual_fallback"

    # 错误与诊断
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    steps_details: list[dict] = field(default_factory=list)
    phase_timeline: list[dict] = field(default_factory=list)

    # 环境信息
    ae_version: str = ""
    ae_path: str = ""
    aerender_path: str = ""
    bridge_connected: bool = False
    plugin_missing: list[dict] = field(default_factory=list)
    system_info: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["phase"] = self.phase.value
        return d


# ============================================================
# 常量 / 默认配置
# ============================================================

# AE 检测路径（按版本倒序，优先最新）
AE_PATHS_WIN = [
    r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files",
    r"C:\Program Files\Adobe\Adobe After Effects 2024\Support Files",
    r"C:\Program Files\Adobe\Adobe After Effects 2023\Support Files",
    r"C:\Program Files\Adobe\Adobe After Effects 2022\Support Files",
    r"C:\Program Files\Adobe\Adobe After Effects 2021\Support Files",
    r"C:\Program Files\Adobe\Adobe After Effects 2020\Support Files",
    r"C:\Program Files\Adobe\Adobe After Effects CC 2019\Support Files",
]

AE_EXE = "AfterFX.exe"
AERENDER_EXE = "aerender.exe"

# Bridge 文件路径
BRIDGE_DIR = os.path.expanduser(r"~\.ae-mcp-bridge")
BRIDGE_CMD_FILE = os.path.join(BRIDGE_DIR, "executeAtomScript_cmd.json")
BRIDGE_RESULT_FILE = os.path.join(BRIDGE_DIR, "executeAtomScript_result.json")

# 默认渲染格式映射
FORMAT_EXTENSIONS = {
    "avi": ".avi",
    "mov": ".mov",
    "mp4": ".mp4",  # 需 Media Encoder 桥接
    "jpeg_sequence": "",  # 序列帧自动编号
    "png_sequence": "",
    "psd_sequence": "",
    "tiff_sequence": "",
    "tga_sequence": "",
}

FORMAT_OM_STRINGS = {
    "avi": "AVI",
    "mov": "QuickTime",
    "jpeg_sequence": "JPEG Sequence",
    "png_sequence": "PNG Sequence",
    "psd_sequence": "Photoshop Sequence",
    "tiff_sequence": "TIFF Sequence",
    "tga_sequence": "Targa Sequence",
}

# 输出编码预设 (Output Module Template)
OM_PRESETS = {
    "lossless": "Lossless",
    "lossless_alpha": "Lossless with Alpha",
    "draft_movie": "Draft Movie",
    "hdtv_1080": "HDTV 1080p 29.97",
    "h264": "H.264",
}

# 渲染设置预设
RS_PRESETS = {
    "best": "Best Settings",
    "draft": "Draft Settings",
    "dv": "DV Settings",
    "multi_machine": "Multi-Machine Settings",
}

# 重试参数
MAX_RETRIES = 2
RETRY_DELAY_SEC = 3


# ============================================================
# 工具函数
# ============================================================


def timestamp_iso() -> str:
    """ISO 8601 时间戳"""
    return datetime.now().isoformat(timespec="seconds")


def elapsed_since(start: float) -> float:
    """毫秒耗时"""
    return (time.time() - start) * 1000.0


def safe_path(path: str) -> str:
    """确保路径存在，返回绝对路径"""
    return os.path.abspath(os.path.expandvars(path))


def safe_mkdirs(dirpath: str) -> str:
    """递归创建目录，返回绝对路径"""
    p = safe_path(dirpath)
    os.makedirs(p, exist_ok=True)
    return p


def format_size_bytes(size: int) -> str:
    """人类可读文件大小"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


# ============================================================
# AE 安装检测器
# ============================================================


class AEInstallDetector:
    """自动检测 AE 和 aerender 的安装路径"""

    @staticmethod
    def find_ae_path() -> tuple[str | None, str | None, str | None]:
        """
        返回 (afterfx_path, support_dir, aerender_path)
        """
        # 1. 遍历已知路径
        for known in AE_PATHS_WIN:
            exe = os.path.join(known, AE_EXE)
            if os.path.isfile(exe):
                aerender = os.path.join(known, AERENDER_EXE)
                aer = aerender if os.path.isfile(aerender) else None
                return exe, known, aer

        # 2. 通过注册表搜索
        try:
            import winreg
            for base in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                for sub in [
                    r"SOFTWARE\Adobe\After Effects",
                    r"SOFTWARE\WOW6432Node\Adobe\After Effects",
                ]:
                    try:
                        key = winreg.OpenKey(base, sub)
                        idx = 0
                        while True:
                            try:
                                ver = winreg.EnumKey(key, idx)
                                with winreg.OpenKey(key, ver) as vk:
                                    install_path, _ = winreg.QueryValueEx(vk, "InstallPath")
                                    exe = os.path.join(install_path, AE_EXE)
                                    if os.path.isfile(exe):
                                        sup = install_path
                                        aer = os.path.join(install_path, AERENDER_EXE)
                                        aer = aer if os.path.isfile(aer) else None
                                        return exe, sup, aer
                            except OSError:
                                break
                            idx += 1
                    except OSError:
                        continue
        except ImportError:
            pass

        # 3. 搜索 Program Files（慢，但兜底）
        for candidate in glob.glob(r"C:\Program Files\Adobe\*"):
            exe = os.path.join(candidate, "Support Files", AE_EXE)
            if os.path.isfile(exe):
                sup = os.path.join(candidate, "Support Files")
                aer = os.path.join(sup, AERENDER_EXE)
                aer = aer if os.path.isfile(aer) else None
                return exe, sup, aer

        return None, None, None

    @staticmethod
    def detect_ae_version(ae_path: str) -> str:
        """通过 exe 属性获取 AE 版本"""
        try:
            info = subprocess.check_output(
                ['powershell', '-Command',
                 f"(Get-Item '{ae_path}').VersionInfo.FileVersion"],
                text=True, timeout=10
            ).strip()
            return info or "Unknown"
        except Exception:
            pass
        # 回退：从路径名提取版本
        match = re.search(r"After Effects (\d{4}|\w{2} \d{4})", ae_path)
        if match:
            return match.group(1)
        return "Unknown"


# ============================================================
# AE Bridge 通信客户端 (文件轮询协议)
# ============================================================


class AEBridgeClient:
    """
    AE Bridge 通信客户端

    协议：基于文件轮询 JSON
    - 写入 cmd JSON → 等待 result JSON 出现 → 读取并清理
    - 每个命令用唯一 session_id 标识
    - 支持超时和重试
    """

    POLL_INTERVAL_SEC = 0.3
    DEFAULT_TIMEOUT_SEC = 60.0
    CLEANUP_GRACE_SEC = 1.0

    def __init__(self, timeout_sec: float = 60.0, poll_interval: float = 0.3):
        self.timeout_sec = timeout_sec
        self.poll_interval = poll_interval
        self._connected = False
        self._session_prefix = uuid.uuid4().hex[:8]
        self._cmd_seq = 0
        self._response_cache: dict[str, Any] = {}

    # ---- 连接管理 ----

    @property
    def connected(self) -> bool:
        """检查 Bridge 是否就绪（命令文件可写入）"""
        try:
            os.makedirs(BRIDGE_DIR, exist_ok=True)
            test_file = os.path.join(BRIDGE_DIR, f"_ping_{self._session_prefix}.json")
            with open(test_file, "w", encoding="utf-8") as f:
                json.dump({"ping": timestamp_iso()}, f)
            time.sleep(0.5)
            if os.path.isfile(test_file):
                os.remove(test_file)
                self._connected = True
                return True
        except (IOError, OSError, PermissionError):
            pass
        self._connected = False
        return False

    def disconnect(self):
        self._connected = False

    # ---- 核心：executeAtomScript ----

    def execute_atom_script(
        self,
        jsx_code: str,
        timeout_sec: float | None = None,
        retry: int = 0,
    ) -> tuple[bool, dict[str, Any]]:
        """
        执行 AtomScript（JSX）并返回结果。

        协议：
        1. 写入 cmd JSON → { "cmd": "executeAtomScript", "script": "...", "id": "xxx" }
        2. 轮询 → 等待 result JSON 出现
        3. 读取 result JSON → 清理 → 返回

        返回：
            (success: bool, result: dict)
            success=True 时 result = {"data": ..., "status": "ok"}
            success=False 时 result = {"error": ..., "type": "timeout"/"protocol"/"parse"}
        """
        seq = self._cmd_seq
        self._cmd_seq += 1
        cmd_id = f"{self._session_prefix}_{seq:06d}"
        timeout = timeout_sec or self.timeout_sec

        # 清理可能残留的文件
        self._cleanup_stale(cmd_id)

        # 1) 写入命令
        cmd_payload = {
            "cmd": "executeAtomScript",
            "script": jsx_code,
            "id": cmd_id,
            "timestamp": timestamp_iso(),
        }
        if not self._write_cmd(cmd_payload, cmd_id):
            return False, {"error": "Failed to write command file", "type": "io"}

        # 2) 轮询结果
        start = time.time()
        while (time.time() - start) < timeout:
            result = self._read_result(cmd_id)
            if result is not None:
                self._cleanup_files(cmd_id)
                if result.get("status") == "ok":
                    return True, result
                else:
                    return False, {
                        "error": result.get("error", result.get("message", "Unknown AE error")),
                        "type": "ae_error",
                        "data": result.get("data"),
                        "output": result.get("output", ""),
                    }
            time.sleep(self.poll_interval)

        # 3) 超时
        self._cleanup_files(cmd_id)
        if retry < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SEC)
            return self.execute_atom_script(jsx_code, timeout_sec, retry + 1)

        return False, {
            "error": f"Command timed out after {timeout:.1f}s (id={cmd_id})",
            "type": "timeout",
            "timeout_sec": timeout,
        }

    def execute_atom_script_checked(
        self, jsx_code: str, description: str = "", timeout_sec: float = 60.0
    ) -> tuple[bool, dict[str, Any]]:
        """
        执行 AtomScript，自动添加 try/catch 包裹。
        返回 (success, result)
        """
        wrapped = textwrap.dedent(f"""\
        (function() {{
            var __result = {{ status: "ok", data: null, error: null, output: "" }};
            try {{
                var __fn = function() {{
                    {jsx_code}
                }};
                __result.data = __fn();
            }} catch(__e) {{
                __result.status = "error";
                __result.error = "" + __e;
                __result.output = __e.stack || "";
            }}
            return JSON.stringify(__result);
        }})();
        """)
        ok, res = self.execute_atom_script(wrapped, timeout_sec)
        if ok:
            raw = res.get("data", "{}")
            if isinstance(raw, str):
                try:
                    inner = json.loads(raw)
                    if inner.get("status") == "error":
                        return False, {"error": inner.get("error", "Unknown"), "type": "jsx_error"}
                    return True, inner
                except json.JSONDecodeError:
                    return True, {"data": raw, "status": "ok"}
            return True, res
        return False, res

    # ---- 文件 I/O 辅助 ----

    def _write_cmd(self, payload: dict, cmd_id: str) -> bool:
        """写入命令文件，重试 3 次"""
        for attempt in range(3):
            try:
                os.makedirs(BRIDGE_DIR, exist_ok=True)
                with open(BRIDGE_CMD_FILE, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
                # 确认写入成功（原子性检查）
                with open(BRIDGE_CMD_FILE, "r", encoding="utf-8") as f:
                    written = json.load(f)
                    if written.get("id") == cmd_id:
                        return True
            except (IOError, OSError, PermissionError, json.JSONDecodeError):
                pass
            time.sleep(0.3 * (attempt + 1))
        return False

    def _read_result(self, cmd_id: str) -> dict[str, Any] | None:
        """尝试读取结果文件"""
        if not os.path.isfile(BRIDGE_RESULT_FILE):
            return None
        try:
            with open(BRIDGE_RESULT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 检查是否是对应 cmd 的响应
            if data.get("id") == cmd_id:
                return data
            # 旧文件留存，返回并清理
            if self._is_stale(data):
                os.remove(BRIDGE_RESULT_FILE)
                return None
            return None
        except (IOError, json.JSONDecodeError):
            return None

    def _cleanup_stale(self, current_id: str):
        """清理路径下的孤儿文件"""
        for fname in [BRIDGE_CMD_FILE, BRIDGE_RESULT_FILE]:
            try:
                if os.path.isfile(fname):
                    with open(fname, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if self._is_stale(data):
                        os.remove(fname)
            except (IOError, json.JSONDecodeError, OSError):
                try:
                    os.remove(fname)
                except OSError:
                    pass

    def _cleanup_files(self, cmd_id: str):
        """移除本次会话的文件"""
        for fname in [BRIDGE_CMD_FILE, BRIDGE_RESULT_FILE]:
            try:
                if os.path.isfile(fname):
                    os.remove(fname)
            except OSError:
                pass

    @staticmethod
    def _is_stale(data: dict) -> bool:
        """判断结果是否超过 5 分钟（认为过期）"""
        try:
            ts = data.get("timestamp", "")
            if ts:
                dt = datetime.fromisoformat(ts)
                return (datetime.now() - dt) > timedelta(minutes=5)
        except ValueError:
            pass
        return True


# ============================================================
# AE 项目管理器
# ============================================================


class AEProjectManager:
    """AE 项目生命周期管理：打开 / 保存 / 关闭"""

    def __init__(self, bridge: AEBridgeClient):
        self.bridge = bridge
        self._loaded_project = ""

    def get_project_info(self) -> dict[str, Any]:
        """获取当前项目信息"""
        jsx = textwrap.dedent("""\
        var info = {
            fileName: "",
            filePath: "",
            dirty: false,
            numItems: 0,
            numSelectedItems: 0,
            compositions: [],
            compCount: 0
        };
        if (app.project) {
            info.fileName = app.project.file ? app.project.file.displayName : "(Unsaved)";
            info.filePath = app.project.file ? app.project.file.fsName : "";
            info.dirty = app.project.dirty;
            info.numItems = app.project.numItems;
            info.numSelectedItems = app.project.selection.length;
            info.compCount = app.project.numItems;
            for (var i = 1; i <= app.project.numItems; i++) {
                var item = app.project.item(i);
                if (item && item instanceof CompItem) {
                    info.compositions.push({
                        name: item.name,
                        width: item.width,
                        height: item.height,
                        duration: item.duration,
                        frameRate: item.frameRate,
                        frameDuration: item.frameDuration,
                        id: item.id,
                        layersCount: item.numLayers
                    });
                }
            }
        }
        return JSON.stringify(info);
        """)
        ok, res = self.bridge.execute_atom_script_checked(jsx, "get_project_info")
        if not ok:
            return {}
        try:
            data = res.get("data", "{}")
            if isinstance(data, str):
                return json.loads(data)
            return data or {}
        except json.JSONDecodeError:
            return {}

    def open_project(self, project_path: str) -> tuple[bool, dict[str, Any]]:
        """打开 AE 项目文件"""
        escaped = project_path.replace("\\", "\\\\").replace("'", "\\'")
        jsx = textwrap.dedent(f"""\
        var fp = new File('{escaped}');
        if (!fp.exists) {{
            return JSON.stringify({{ status: "error", error: "File not found: " + fp.fsName }});
        }}
        try {{
            var proj = app.open(fp);
            if (!proj) {{
                return JSON.stringify({{ status: "error", error: "app.open returned null (user may have cancelled)" }});
            }}
            return JSON.stringify({{
                status: "ok",
                fileName: proj.file.displayName,
                numItems: proj.numItems,
                filePath: proj.file.fsName
            }});
        }} catch(e) {{
            return JSON.stringify({{ status: "error", error: e.toString() }});
        }}
        """)
        ok, res = self.bridge.execute_atom_script_checked(jsx, f"open_project: {project_path}", 120.0)
        if ok:
            self._loaded_project = project_path
        return ok, res

    def save_project(self, save_path: str | None = None) -> tuple[bool, str]:
        """保存当前项目"""
        if save_path:
            escaped = save_path.replace("\\", "\\\\").replace("'", "\\'")
            jsx = f"app.project.save(new File('{escaped}')); return 'saved to ' + '{escaped}';"
        else:
            jsx = textwrap.dedent("""\
            if (app.project.file) {
                app.project.save();
                return "saved to " + app.project.file.fsName;
            } else {
                var defaultPath = Folder.desktop.fsName + "/_ae_auto_save.aep";
                app.project.save(new File(defaultPath));
                return "saved to " + defaultPath;
            }
            """)
        ok, res = self.bridge.execute_atom_script_checked(jsx, "save_project")
        msg = res.get("data", "") if ok else res.get("error", "save failed")
        return ok, str(msg)

    def close_project(self, save: bool = True) -> tuple[bool, str]:
        """关闭项目（含清理）"""
        jsx = textwrap.dedent(f"""\
        try {{
            if (app.project && {str(save).lower()}) {{
                if (app.project.file) {{
                    app.project.save();
                }}
            }}
            // 清理渲染队列
            try {{
                var rq = app.project.renderQueue;
                while (rq.numItems > 0) {{
                    rq.item(rq.numItems).remove();
                }}
            }} catch(eC) {{}}
            app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
            return "project closed";
        }} catch(e) {{
            return "close error: " + e.toString();
        }}
        """)
        ok, res = self.bridge.execute_atom_script_checked(jsx, "close_project", 30.0)
        msg = res.get("data", "") if ok else res.get("error", "close failed")
        return ok, str(msg)

    def find_composition(self, comp_name: str | None = None) -> dict[str, Any] | None:
        """查找指定名称的合成，未指定则返回第一个"""
        info = self.get_project_info()
        comps = info.get("compositions", [])
        if not comps:
            return None
        if comp_name:
            for c in comps:
                if c.get("name") == comp_name:
                    return c
            return None
        return comps[0]


# ============================================================
# AE 步骤执行器
# ============================================================


class AEStepExecutor:
    """
    复刻步骤执行器

    支持的操作类型：
    - new_composition  : 创建合成
    - new_solid        : 创建固态层
    - new_text_layer   : 创建文字层
    - new_shape_layer  : 创建形状图层
    - new_null_layer   : 创建空对象层
    - new_adjust_layer : 创建调整图层
    - set_property     : 设置属性值
    - add_keyframe     : 添加关键帧
    - add_effect       : 添加效果
    - set_expression   : 设置表达式
    - set_3d           : 设置 3D 图层
    - set_blending     : 设置混合模式
    - set_opacity      : 设置不透明度
    - add_animation    : 添加文字动画
    - duplicate_layer  : 复制图层
    - rename_layer     : 重命名图层
    - run_jsx          : 执行自定义 JSX
    """

    def __init__(self, bridge: AEBridgeClient):
        self.bridge = bridge
        self.created_comps: list[str] = []
        self.active_comp: str = ""

    def get_active_comp_name(self) -> str:
        """获取当前活动合成名称"""
        jsx = """return app.project.activeItem ? app.project.activeItem.name : "";"""
        ok, res = self.bridge.execute_atom_script_checked(jsx, "get_active_comp")
        if ok:
            name = res.get("data", "")
            if isinstance(name, str) and name:
                self.active_comp = name
                return name
        return self.active_comp

    def execute_step(self, step: dict[str, Any]) -> tuple[StepResult, dict | None]:
        """
        执行单个复刻步骤

        step 格式:
        {
            "id": "step_01",
            "module": "M1_Composition",
            "type": "new_composition",
            "description": "创建 1080p 主合成",
            "params": { ... }
        }
        """
        step_id = step.get("id", f"step_{uuid.uuid4().hex[:6]}")
        module = step.get("module", "unknown")
        step_type = step.get("type", "")
        desc = step.get("description", step_type)
        params = step.get("params", {})

        sr = StepResult(step_id=step_id, module=module, description=desc)
        t0 = time.time()

        # 调度到具体处理器
        handlers: dict[str, Callable[[dict], tuple[bool, Any]]] = {
            "new_composition": self._step_new_composition,
            "new_solid": self._step_new_solid,
            "new_text_layer": self._step_new_text_layer,
            "new_shape_layer": self._step_new_shape_layer,
            "new_null_layer": self._step_new_null_layer,
            "new_adjust_layer": self._step_new_adjust_layer,
            "set_property": self._step_set_property,
            "add_keyframe": self._step_add_keyframe,
            "add_effect": self._step_add_effect,
            "set_expression": self._step_set_expression,
            "set_3d": self._step_set_3d,
            "set_blending": self._step_set_blending,
            "set_opacity": self._step_set_opacity,
            "add_animation": self._step_add_text_animation,
            "duplicate_layer": self._step_duplicate_layer,
            "rename_layer": self._step_rename_layer,
            "set_layer_pos": self._step_set_layer_pos,
            "set_in_point": self._step_set_in_point,
            "set_out_point": self._step_set_out_point,
            "set_scale": self._step_set_scale,
            "set_rotation": self._step_set_rotation,
            "run_jsx": self._step_run_jsx,
        }

        handler = handlers.get(step_type)
        if handler is None:
            sr.status = StepStatus.SKIP
            sr.message = f"Unknown step type: {step_type}"
            sr.elapsed_ms = elapsed_since(t0)
            return sr, None

        try:
            ok, data = handler(params)
            if ok:
                sr.status = StepStatus.PASS
                sr.message = data if isinstance(data, str) else "OK"
            else:
                sr.status = StepStatus.FAIL
                sr.message = data.get("error", str(data)) if isinstance(data, dict) else str(data)
                sr.error_type = data.get("type", "execution_error") if isinstance(data, dict) else "execution_error"
        except Exception as e:
            sr.status = StepStatus.FAIL
            sr.message = f"Python-side error: {e}"
            sr.error_type = type(e).__name__
            sr.error_traceback = traceback.format_exc()

        sr.elapsed_ms = elapsed_since(t0)
        return sr, params

    # ============ 步骤处理器 ============

    def _step_new_composition(self, p: dict) -> tuple[bool, Any]:
        name = p.get("name", "Comp")
        w = p.get("width", 1920)
        h = p.get("height", 1080)
        fps = p.get("fps", 30)
        dur = p.get("duration", 10.0)
        bg = p.get("bg_color", [0, 0, 0])

        jsx = textwrap.dedent(f"""\
        var comp = app.project.items.addComp(
            '{name}', {w}, {h}, 1.0, {dur}, {fps}
        );
        comp.bgColor = [{bg[0]}, {bg[1]}, {bg[2]}];
        return JSON.stringify({{
            name: comp.name, id: comp.id, width: comp.width, height: comp.height,
            duration: comp.duration, frameRate: comp.frameRate
        }});
        """)
        ok, res = self.bridge.execute_atom_script_checked(jsx, f"new_comp: {name}")
        self.created_comps.append(name)
        self.active_comp = name
        return ok, res

    def _step_new_solid(self, p: dict) -> tuple[bool, Any]:
        name = p.get("name", "Solid")
        color = p.get("color", [0.5, 0.5, 0.5])
        w = p.get("width", 1920)
        h = p.get("height", 1080)
        comp_name = p.get("comp", self.active_comp)

        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found: {comp_name}" }});
        var solid = comp.layers.addSolid(
            [{color[0]}, {color[1]}, {color[2]}], '{name}', {w}, {h}, 1.0
        );
        return JSON.stringify({{ name: solid.name, index: solid.index, width: solid.width, height: solid.height }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"new_solid: {name}")

    def _step_new_text_layer(self, p: dict) -> tuple[bool, Any]:
        text = p.get("text", "Sample Text")
        comp_name = p.get("comp", self.active_comp)
        font = p.get("font", "Arial")
        font_size = p.get("font_size", 72)

        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        var layer = comp.layers.addText('{text}');
        var txt = layer.property("Source Text");
        if (txt) {{
            var doc = txt.value;
            doc.font = '{font}';
            doc.fontSize = {font_size};
            txt.setValue(doc);
        }}
        return JSON.stringify({{ name: layer.name, index: layer.index, text: '{text}' }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"new_text: {text[:30]}")

    def _step_new_shape_layer(self, p: dict) -> tuple[bool, Any]:
        comp_name = p.get("comp", self.active_comp)
        shape_type = p.get("shape", "rect")
        size = p.get("size", [200, 200])

        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        var layer = comp.layers.addShape();
        var contents = layer.property("ADBE Root Vectors Group");
        if (contents) {{
            var group = contents.addProperty("ADBE Vector Group");
            var shape = group.addProperty("ADBE Vector Shape - {shape_type.capitalize()}");
            if (shape) {{
                var shapePath = shape.property("ADBE Vector Shape");
                if (shapePath) {{
                    var rect = shapePath.value;
                    var sizeArr = rect.size;
                    if (sizeArr && sizeArr.length >= 2) {{
                        rect.size = [{size[0]}, {size[1]}];
                        shapePath.setValue(rect);
                    }}
                }}
            }}
        }}
        return JSON.stringify({{ name: layer.name, index: layer.index }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, "new_shape_layer")

    def _step_new_null_layer(self, p: dict) -> tuple[bool, Any]:
        name = p.get("name", "Null")
        comp_name = p.get("comp", self.active_comp)
        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        var layer = comp.layers.addNull();
        layer.name = '{name}';
        return JSON.stringify({{ name: layer.name, index: layer.index }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"new_null: {name}")

    def _step_new_adjust_layer(self, p: dict) -> tuple[bool, Any]:
        name = p.get("name", "Adjustment")
        comp_name = p.get("comp", self.active_comp)
        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        var layer = comp.layers.addSolid([1,1,1], '{name}',
            comp.width, comp.height, comp.pixelAspect);
        layer.adjustmentLayer = true;
        return JSON.stringify({{ name: layer.name, index: layer.index, adjustment: true }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"new_adjust: {name}")

    def _step_set_property(self, p: dict) -> tuple[bool, Any]:
        layer_name = p.get("layer", "")
        prop_path = p.get("property", "")
        value = json.dumps(p.get("value", 0))
        comp_name = p.get("comp", self.active_comp)
        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        for (var l = 1; l <= comp.numLayers; l++) {{
            var layer = comp.layer(l);
            if (layer.name.indexOf('{layer_name}') >= 0) {{
                var prop = layer.property('{prop_path}');
                if (prop) {{
                    prop.setValue({value});
                    return JSON.stringify({{ layer: layer.name, property: '{prop_path}', value: {value} }});
                }} else {{
                    return JSON.stringify({{ status: "error", error: "Property not found: {prop_path}" }});
                }}
            }}
        }}
        return JSON.stringify({{ status: "error", error: "Layer not found: {layer_name}" }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"set_prop: {prop_path}")

    def _step_add_keyframe(self, p: dict) -> tuple[bool, Any]:
        layer_name = p.get("layer", "")
        prop_path = p.get("property", "")
        value = json.dumps(p.get("value", 0))
        time_sec = p.get("time", 0.0)
        comp_name = p.get("comp", self.active_comp)
        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        for (var l = 1; l <= comp.numLayers; l++) {{
            var layer = comp.layer(l);
            if (layer.name.indexOf('{layer_name}') >= 0) {{
                var prop = layer.property('{prop_path}');
                if (prop) {{
                    prop.setValueAtTime({time_sec}, {value});
                    return JSON.stringify({{ layer: layer.name, time: {time_sec}, keyframes: prop.numKeys }});
                }}
            }}
        }}
        return JSON.stringify({{ status: "error", error: "Property not found: {prop_path}" }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"keyframe: {prop_path}@{time_sec}")

    def _step_add_effect(self, p: dict) -> tuple[bool, Any]:
        layer_name = p.get("layer", "")
        effect_match_name = p.get("effect", "")
        comp_name = p.get("comp", self.active_comp)
        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        for (var l = 1; l <= comp.numLayers; l++) {{
            var layer = comp.layer(l);
            if (layer.name.indexOf('{layer_name}') >= 0) {{
                try {{
                    var eff = layer.property("ADBE Effect Parade").addProperty('{effect_match_name}');
                    return JSON.stringify({{ name: eff.name, matchName: eff.matchName, index: eff.propertyIndex }});
                }} catch(e) {{
                    return JSON.stringify({{ status: "error", error: "Effect add failed: " + e.toString(), matchName: '{effect_match_name}' }});
                }}
            }}
        }}
        return JSON.stringify({{ status: "error", error: "Layer not found" }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"add_effect: {effect_match_name}")

    def _step_set_expression(self, p: dict) -> tuple[bool, Any]:
        layer_name = p.get("layer", "")
        prop_path = p.get("property", "")
        expression = p.get("expression", "").replace("\\", "\\\\").replace("'", "\\'")
        comp_name = p.get("comp", self.active_comp)
        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        for (var l = 1; l <= comp.numLayers; l++) {{
            var layer = comp.layer(l);
            if (layer.name.indexOf('{layer_name}') >= 0) {{
                var prop = layer.property('{prop_path}');
                if (prop && prop.canSetExpression) {{
                    prop.expression = '{expression}';
                    return JSON.stringify({{ layer: layer.name, prop: '{prop_path}', expression: '{expression[:50]}...' }});
                }}
            }}
        }}
        return JSON.stringify({{ status: "error", error: "Cannot set expression" }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"expression: {prop_path}")

    def _step_set_3d(self, p: dict) -> tuple[bool, Any]:
        layer_name = p.get("layer", "")
        comp_name = p.get("comp", self.active_comp)
        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        for (var l = 1; l <= comp.numLayers; l++) {{
            var layer = comp.layer(l);
            if (layer.name.indexOf('{layer_name}') >= 0) {{
                layer.threeDLayer = true;
                return JSON.stringify({{ layer: layer.name, threeDLayer: true }});
            }}
        }}
        return JSON.stringify({{ status: "error", error: "Layer not found" }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"set_3d: {layer_name}")

    def _step_set_blending(self, p: dict) -> tuple[bool, Any]:
        layer_name = p.get("layer", "")
        mode = p.get("mode", 3)  # 默认 Normal=3
        comp_name = p.get("comp", self.active_comp)
        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        for (var l = 1; l <= comp.numLayers; l++) {{
            var layer = comp.layer(l);
            if (layer.name.indexOf('{layer_name}') >= 0) {{
                layer.blendingMode = BlendingMode.NORMAL;
                try {{ layer.blendingMode = {mode}; }} catch(e) {{}}
                return JSON.stringify({{ layer: layer.name, blendingMode: layer.blendingMode }});
            }}
        }}
        return JSON.stringify({{ status: "error", error: "Layer not found" }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"blending: {layer_name}={mode}")

    def _step_set_opacity(self, p: dict) -> tuple[bool, Any]:
        return self._step_set_property({
            "layer": p.get("layer", ""),
            "property": "ADBE Transform Group/ADBE Opacity",
            "value": p.get("value", 100),
            "comp": p.get("comp", self.active_comp),
        })

    def _step_add_text_animation(self, p: dict) -> tuple[bool, Any]:
        layer_name = p.get("layer", "")
        animator_name = p.get("animator", "Animator 1")
        prop_name = p.get("add_property", "ADBE Text Opacity")
        value = json.dumps(p.get("value", 0))
        comp_name = p.get("comp", self.active_comp)
        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        for (var l = 1; l <= comp.numLayers; l++) {{
            var layer = comp.layer(l);
            if (layer.name.indexOf('{layer_name}') >= 0) {{
                try {{
                    var animators = layer.property("ADBE Text Properties").property("ADBE Text Animators");
                    if (!animators) return JSON.stringify({{ status: "error", error: "No animators available" }});
                    var anim = animators.addProperty("ADBE Text Animator");
                    if (!anim) return JSON.stringify({{ status: "error", error: "Failed to create animator" }});
                    anim.name = '{animator_name}';
                    var sel = anim.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
                    if (sel) {{
                        var rangeStart = sel.property("ADBE Text Percent Start");
                        var rangeEnd = sel.property("ADBE Text Percent End");
                        if (rangeEnd) rangeEnd.setValue(100);
                    }}
                    var prop = anim.property("ADBE Text Animator Properties").addProperty('{prop_name}');
                    if (prop) prop.setValue({value});
                    return JSON.stringify({{ animator: anim.name, property: '{prop_name}', value: {value} }});
                }} catch(e) {{
                    return JSON.stringify({{ status: "error", error: "Anim add failed: " + e.toString() }});
                }}
            }}
        }}
        return JSON.stringify({{ status: "error", error: "Layer not found" }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"text_anim: {animator_name}")

    def _step_duplicate_layer(self, p: dict) -> tuple[bool, Any]:
        layer_name = p.get("layer", "")
        comp_name = p.get("comp", self.active_comp)
        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        for (var l = 1; l <= comp.numLayers; l++) {{
            if (comp.layer(l).name.indexOf('{layer_name}') >= 0) {{
                var dup = comp.layer(l).duplicate();
                return JSON.stringify({{ original: comp.layer(l).name, duplicate: dup.name, index: dup.index }});
            }}
        }}
        return JSON.stringify({{ status: "error", error: "Layer not found" }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"duplicate: {layer_name}")

    def _step_rename_layer(self, p: dict) -> tuple[bool, Any]:
        layer_name = p.get("layer", "")
        new_name = p.get("new_name", "Renamed")
        comp_name = p.get("comp", self.active_comp)
        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        for (var l = 1; l <= comp.numLayers; l++) {{
            if (comp.layer(l).name.indexOf('{layer_name}') >= 0) {{
                comp.layer(l).name = '{new_name}';
                return JSON.stringify({{ old: '{layer_name}', new: comp.layer(l).name }});
            }}
        }}
        return JSON.stringify({{ status: "error", error: "Layer not found" }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"rename: {layer_name}->{new_name}")

    def _step_set_layer_pos(self, p: dict) -> tuple[bool, Any]:
        pos = p.get("position", [960, 540])
        return self._step_set_property({
            "layer": p.get("layer", ""),
            "property": "ADBE Transform Group/ADBE Position",
            "value": pos,
            "comp": p.get("comp", self.active_comp),
        })

    def _step_set_in_point(self, p: dict) -> tuple[bool, Any]:
        layer_name = p.get("layer", "")
        time_sec = p.get("time", 0.0)
        comp_name = p.get("comp", self.active_comp)
        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        for (var l = 1; l <= comp.numLayers; l++) {{
            if (comp.layer(l).name.indexOf('{layer_name}') >= 0) {{
                comp.layer(l).inPoint = {time_sec};
                return JSON.stringify({{ layer: comp.layer(l).name, inPoint: comp.layer(l).inPoint }});
            }}
        }}
        return JSON.stringify({{ status: "error", error: "Layer not found" }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"set_in: {layer_name}={time_sec}")

    def _step_set_out_point(self, p: dict) -> tuple[bool, Any]:
        layer_name = p.get("layer", "")
        time_sec = p.get("time", 5.0)
        comp_name = p.get("comp", self.active_comp)
        jsx = textwrap.dedent(f"""\
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) return JSON.stringify({{ status: "error", error: "Comp not found" }});
        for (var l = 1; l <= comp.numLayers; l++) {{
            if (comp.layer(l).name.indexOf('{layer_name}') >= 0) {{
                comp.layer(l).outPoint = {time_sec};
                return JSON.stringify({{ layer: comp.layer(l).name, outPoint: comp.layer(l).outPoint }});
            }}
        }}
        return JSON.stringify({{ status: "error", error: "Layer not found" }});
        """)
        return self.bridge.execute_atom_script_checked(jsx, f"set_out: {layer_name}={time_sec}")

    def _step_set_scale(self, p: dict) -> tuple[bool, Any]:
        scale = p.get("value", [100, 100])
        return self._step_set_property({
            "layer": p.get("layer", ""),
            "property": "ADBE Transform Group/ADBE Scale",
            "value": scale,
            "comp": p.get("comp", self.active_comp),
        })

    def _step_set_rotation(self, p: dict) -> tuple[bool, Any]:
        rot = p.get("value", 0)
        return self._step_set_property({
            "layer": p.get("layer", ""),
            "property": "ADBE Transform Group/ADBE Rotate Z",
            "value": rot,
            "comp": p.get("comp", self.active_comp),
        })

    def _step_run_jsx(self, p: dict) -> tuple[bool, Any]:
        jsx = p.get("code", "return 'empty jsx';")
        return self.bridge.execute_atom_script_checked(jsx, "custom_jsx")


# ============================================================
# AE 渲染管理器
# ============================================================


class AERenderManager:
    """
    AE 渲染管理器

    两种渲染方式：
    1. aerender CLI — 独立进程，可监控进度（推荐）
    2. Bridge ExtendScript — 配置 RQ，由用户手动渲染（回退）
    """

    def __init__(self, bridge: AEBridgeClient, aerender_path: str | None = None):
        self.bridge = bridge
        self.aerender_path = aerender_path
        self._render_process: subprocess.Popen | None = None
        self._render_start_time: float = 0.0

    @property
    def use_aerender(self) -> bool:
        return bool(self.aerender_path and os.path.isfile(self.aerender_path))

    def configure_render_queue_bridge(
        self, comp_name: str, config: RenderConfig
    ) -> tuple[bool, dict[str, Any]]:
        """
        通过 Bridge 配置渲染队列

        设置：
        - 将合成添加到渲染队列
        - 设置输出模块（文件路径 + 格式）
        - 设置渲染设置（分辨率、帧范围）
        """
        output_path = safe_path(config.output_dir)
        safe_mkdirs(output_path)

        # 根据格式确定文件扩展名
        ext = FORMAT_EXTENSIONS.get(config.output_format, ".avi")
        out_file = os.path.join(output_path, f"{config.output_filename}{ext}")
        out_file_normalized = out_file.replace("\\", "\\\\")

        # 获取 OM 字符串
        om_template = OM_PRESETS.get("lossless", "Lossless")
        rs_template = RS_PRESETS.get("best", "Best Settings")

        jsx = textwrap.dedent(f"""\
        // 查找合成
        var comp = null;
        for (var i = 1; i <= app.project.numItems; i++) {{
            var it = app.project.item(i);
            if (it && it instanceof CompItem && it.name === '{comp_name}') {{
                comp = it; break;
            }}
        }}
        if (!comp) {{
            return JSON.stringify({{ status: "error", error: "Comp not found: {comp_name}" }});
        }}

        var result = {{ status: "ok", queueItems: [], errors: [] }};

        try {{
            // 清空现有渲染队列
            var rq = app.project.renderQueue;
            while (rq.numItems > 0) {{
                rq.item(rq.numItems).remove();
            }}

            // 添加合成到渲染队列
            var rqItem = rq.items.add(comp);
            if (!rqItem) {{
                return JSON.stringify({{ status: "error", error: "Failed to add comp to render queue" }});
            }}

            // 配置输出模块
            var om = rqItem.outputModule(1);
            if (om) {{
                om.file = new File('{out_file_normalized}');
                // 尝试设置输出格式
                try {{
                    om.applyTemplate('{om_template}');
                }} catch(eOM) {{
                    result.errors.push("OM template failed: " + eOM.toString());
                }}

                var omInfo = {{
                    filePath: om.file.fsName,
                    template: '{om_template}',
                    includeSourceXMP: om.includeSourceXMP,
                    includeProjectLink: om.includeProjectLink
                }};
                result.outputModule = omInfo;
            }} else {{
                result.errors.push("outputModule(1) returned null");
            }}

            // 配置渲染设置
            try {{
                rqItem.applyTemplate('{rs_template}');
            }} catch(eRS) {{
                result.errors.push("RS template failed: " + eRS.toString());
            }}

            // 手动设置渲染分辨率
            try {{
                var rs = rqItem.getSettings(GetSettingsFormat.STRING_SETTABLE);
                rs.resolution = {int(config.resolution_multiplier * 100)};
                rqItem.setSettings(rs, GetSettingsFormat.STRING_SETTABLE);
            }} catch(eR) {{
                result.errors.push("Resolution setting failed: " + eR.toString());
            }}

            result.queueItems.push({{
                compName: comp.name,
                numOutputModules: rqItem.numOutputModules,
                status: "RQItemStatus." + rqItem.status,
                startTime: rqItem.startTime,
                duration: rqItem.duration
            }});

        }} catch(e) {{
            result.status = "error";
            result.error = e.toString();
            result.stack = e.stack || "";
        }}

        return JSON.stringify(result);
        """)
        return self.bridge.execute_atom_script_checked(
            jsx, f"configure_rq: {comp_name}", 60.0
        )

    def render_via_aerender(
        self, config: RenderConfig, comp_name: str, project_path: str | None = None,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """
        通过 aerender CLI 执行渲染

        参数：
            config: RenderConfig 配置
            comp_name: 合成名称
            project_path: 项目文件路径（如已加载可留空）
            progress_callback: 进度回调 (msg, percent)

        返回：
            (success, info_dict)
        """
        if not self.use_aerender:
            return False, {"error": "aerender not available", "type": "no_aerender"}

        output_dir = safe_mkdirs(safe_path(config.output_dir))
        ext = FORMAT_EXTENSIONS.get(config.output_format, ".avi")
        base_name = config.output_filename
        output_file = os.path.join(output_dir, base_name + ext)

        # 构建 aerender 命令
        cmd = [self.aerender_path]

        if project_path:
            cmd.extend(["-project", safe_path(project_path)])

        cmd.extend([
            "-comp", comp_name,
            "-output", output_file,
        ])

        # 分辨率
        res_map = {1.0: "full", 0.5: "half", 0.25: "quarter", 0.33: "third"}
        res_str = res_map.get(config.resolution_multiplier, "full")
        cmd.extend(["-RStemplate", RS_PRESETS.get("best", "Best Settings")])
        cmd.extend(["-resolution", res_str])

        # 输出模块
        om_str = FORMAT_OM_STRINGS.get(config.output_format, "Lossless")
        cmd.extend(["-OMtemplate", om_str])

        # 帧范围
        if config.start_frame > 0 or config.end_frame is not None:
            cmd.extend(["-s", str(config.start_frame)])
            if config.end_frame is not None:
                cmd.extend(["-e", str(config.end_frame)])

        # 丢帧设置
        if config.drop_frame_rate > 0:
            cmd.extend(["-i", str(config.drop_frame_rate)])

        # 跳过现有文件
        if config.skip_existing:
            cmd.append("-reuse")

        # 关闭 AE 渲染完成后（可选，建议保存项目后单独处理）
        # cmd.append("-close")

        self._render_start_time = time.time()
        start_time_str = timestamp_iso()

        # 执行渲染
        try:
            self._render_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except (FileNotFoundError, OSError, PermissionError) as e:
            return False, {"error": f"Failed to start aerender: {e}", "type": "launch_error"}

        # 监控渲染进度（解析 stdout）
        output_lines: list[str] = []
        last_progress = 0.0
        render_success = False

        try:
            for line in self._render_process.stdout:
                line = line.rstrip()
                output_lines.append(line)

                # 解析进度信息
                progress = self._parse_aerender_progress(line)
                if progress is not None and progress_callback:
                    last_progress = progress
                    progress_callback(comp_name, progress)

                # 检测完成或错误
                if "Finished composition" in line or "finished composition" in line:
                    render_success = True

            # 等待进程结束
            return_code = self._render_process.wait(timeout=config.timeout_minutes * 60)

        except subprocess.TimeoutExpired:
            self._render_process.kill()
            self._render_process.wait(timeout=10)
            return False, {
                "error": f"Render timed out after {config.timeout_minutes} min",
                "type": "timeout",
                "output": "\n".join(output_lines[-50:]),
            }
        except Exception as e:
            try:
                self._render_process.kill()
            except Exception:
                pass
            return False, {
                "error": f"Render error: {e}",
                "type": "exception",
                "output": "\n".join(output_lines[-50:]),
            }

        render_duration = elapsed_since(self._render_start_time)
        self._render_process = None

        # 检查输出文件
        output_file_size = 0.0
        if os.path.isfile(output_file):
            output_file_size = os.path.getsize(output_file) / (1024.0 * 1024.0)

        # 对于序列帧，检查目录是否存在帧文件
        frame_count = 0
        if config.output_format.endswith("_sequence") and os.path.isdir(output_dir):
            pattern = f"{base_name}_*.*"
            frames = glob.glob(os.path.join(output_dir, pattern))
            frame_count = len(frames)

        return render_success, {
            "success": render_success,
            "return_code": return_code if 'return_code' in dir() else -1,
            "output_file": output_file,
            "output_dir": output_dir,
            "file_size_mb": output_file_size,
            "frame_count": frame_count,
            "duration_ms": render_duration,
            "render_method": "aerender_cli",
            "last_progress": last_progress,
            "output_lines": output_lines[-30:],  # 最后 30 行日志
            "start_time": start_time_str,
            "command": " ".join(cmd),
        }

    def render_via_bridge(
        self, config: RenderConfig,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """
        通过 Bridge ExtendScript 直接调用 app.project.renderQueue.render()

        注意：render() 是同步阻塞的，会阻塞整个 AE 和 Bridge。
        这里采用超时 + 轮询方式等待，但对于长渲染不推荐。
        建议优先使用 aerender CLI。
        """
        jsx = textwrap.dedent("""\
        var rq = app.project.renderQueue;
        if (rq.numItems === 0) {
            return JSON.stringify({ status: "error", error: "Render queue is empty" });
        }
        try {
            rq.render();
            var results = [];
            for (var i = 1; i <= rq.numItems; i++) {
                var item = rq.item(i);
                results.push({
                    compName: item.comp ? item.comp.name : "unknown",
                    status: "RQItemStatus." + item.status,
                    elapsed: item.elapsedSeconds,
                    rendered: item.rendered,
                    outputFile: item.outputModule(1) ? item.outputModule(1).file.fsName : "none"
                });
            }
            return JSON.stringify({ status: "ok", items: results });
        } catch(e) {
            return JSON.stringify({ status: "error", error: e.toString(), stack: e.stack || "" });
        }
        """)

        self._render_start_time = time.time()
        timeout = config.timeout_minutes * 60

        ok, res = self.bridge.execute_atom_script(
            jsx, timeout_sec=timeout
        )

        render_duration = elapsed_since(self._render_start_time)

        if not ok:
            return False, {
                "error": res.get("error", "Render failed"),
                "type": res.get("type", "ae_error"),
                "duration_ms": render_duration,
                "render_method": "bridge_extendscript",
            }

        # 查找输出文件
        output_path = ""
        output_size = 0.0
        try:
            data = res.get("data", "{}")
            if isinstance(data, str):
                data = json.loads(data)
            items = data.get("items", [])
            if items:
                output_path = items[0].get("outputFile", "")
                if output_path and os.path.isfile(output_path):
                    output_size = os.path.getsize(output_path) / (1024.0 * 1024.0)
        except (json.JSONDecodeError, KeyError):
            pass

        return True, {
            "success": True,
            "output_file": output_path,
            "file_size_mb": output_size,
            "duration_ms": render_duration,
            "render_method": "bridge_extendscript",
            "raw_response": res,
        }

    def render(
        self, comp_name: str, config: RenderConfig, project_path: str | None = None,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """
        统一渲染入口：优先 aerender CLI，回退 Bridge
        """
        # 1) 先通过 Bridge 配置渲染队列
        ok, cfg_result = self.configure_render_queue_bridge(comp_name, config)
        if not ok:
            return False, {
                "error": "Failed to configure render queue: " + cfg_result.get("error", "unknown"),
                "type": "config_error",
                "detail": cfg_result,
            }

        # 2) 保存项目（aerender 需要项目文件已保存）
        if self.use_aerender:
            save_jsx = textwrap.dedent("""\
            if (!app.project.file) {
                var defaultSavePath = Folder.desktop.fsName + "/_ae_render_temp.aep";
                app.project.save(new File(defaultSavePath));
            } else {
                app.project.save();
            }
            return app.project.file.fsName;
            """)
            ok_save, save_res = self.bridge.execute_atom_script_checked(save_jsx, "save_for_render")
            if ok_save:
                proj_path = save_res.get("data", "") if isinstance(save_res, dict) else str(save_res)
                if isinstance(proj_path, str) and proj_path.strip():
                    project_path = project_path or proj_path.strip()

            # 3) 用 aerender 渲染
            result = self.render_via_aerender(config, comp_name, project_path, progress_callback)
            return result

        else:
            # 回退：用 Bridge 直接渲染
            return self.render_via_bridge(config, progress_callback)

    def cancel_render(self) -> bool:
        """取消正在进行的 aerender 渲染"""
        if self._render_process and self._render_process.poll() is None:
            try:
                self._render_process.terminate()
                time.sleep(2)
                if self._render_process.poll() is None:
                    self._render_process.kill()
                self._render_process = None
                return True
            except Exception:
                pass
        return False

    @staticmethod
    def _parse_aerender_progress(line: str) -> float | None:
        """解析 aerender 输出的进度信息"""
        # "PROGRESS:  0:00:00:05 (1): 10%"
        # "PROGRESS:  0:00:00:10 (10): 50%"
        for pattern in [
            r'PROGRESS:.*?(\d+)%',
            r'(\d+)%[/\s]',
        ]:
            m = re.search(pattern, line)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
        return None


# ============================================================
# 默认复刻步骤集
# ============================================================

DEFAULT_REPRODUCTION_STEPS = [
    # === 模块 1: 合成管理 ===
    {
        "id": "M1_new_comp_hd", "module": "M1_Composition",
        "type": "new_composition",
        "description": "创建 1080p 30fps 主合成（10秒）",
        "params": {"name": "Repro_Main_HD", "width": 1920, "height": 1080, "fps": 30, "duration": 10.0, "bg_color": [0.1, 0.1, 0.15]},
    },
    {
        "id": "M1_new_comp_vertical", "module": "M1_Composition",
        "type": "new_composition",
        "description": "创建竖屏 1080x1920 合成",
        "params": {"name": "Repro_Vertical", "width": 1080, "height": 1920, "fps": 30, "duration": 5.0, "bg_color": [0.05, 0.05, 0.08]},
    },
    {
        "id": "M1_new_comp_square", "module": "M1_Composition",
        "type": "new_composition",
        "description": "创建 1:1 方形合成",
        "params": {"name": "Repro_Square", "width": 1080, "height": 1080, "fps": 30, "duration": 5.0, "bg_color": [0, 0, 0]},
    },
    # === 模块 2: 图层系统 ===
    {
        "id": "M2_solid_bg", "module": "M2_Layers",
        "type": "new_solid",
        "description": "创建背景固态层",
        "params": {"name": "BG_Gradient", "color": [0.05, 0.08, 0.2], "comp": "Repro_Main_HD"},
    },
    {
        "id": "M2_text_title", "module": "M2_Layers",
        "type": "new_text_layer",
        "description": "创建标题文字层",
        "params": {"text": "AE 实战复刻验证", "font": "Arial", "font_size": 96, "comp": "Repro_Main_HD"},
    },
    {
        "id": "M2_shape_rect", "module": "M2_Layers",
        "type": "new_shape_layer",
        "description": "创建矩形形状图层",
        "params": {"shape": "rect", "size": [400, 200], "comp": "Repro_Main_HD"},
    },
    {
        "id": "M2_null_ctrl", "module": "M2_Layers",
        "type": "new_null_layer",
        "description": "创建控制器空对象",
        "params": {"name": "Control_Null", "comp": "Repro_Main_HD"},
    },
    {
        "id": "M2_adjust_glow", "module": "M2_Layers",
        "type": "new_adjust_layer",
        "description": "创建发光调整图层",
        "params": {"name": "Glow_Adjust", "comp": "Repro_Main_HD"},
    },
    # === 模块 3: 属性与关键帧 ===
    {
        "id": "M3_kf_opacity", "module": "M3_Keyframes",
        "type": "add_keyframe",
        "description": "文字层关键帧: opacity 0→100",
        "params": {"layer": "AE 实战复刻验证", "property": "ADBE Transform Group/ADBE Opacity", "value": 0, "time": 0.0, "comp": "Repro_Main_HD"},
    },
    {
        "id": "M3_kf_opacity_100", "module": "M3_Keyframes",
        "type": "add_keyframe",
        "description": "文字层关键帧: opacity 100 at 1s",
        "params": {"layer": "AE 实战复刻验证", "property": "ADBE Transform Group/ADBE Opacity", "value": 100, "time": 1.0, "comp": "Repro_Main_HD"},
    },
    {
        "id": "M3_kf_scale_in", "module": "M3_Keyframes",
        "type": "add_keyframe",
        "description": "矩形缩放关键帧: 0%→100%",
        "params": {"layer": "Shape", "property": "ADBE Transform Group/ADBE Scale", "value": [0, 0], "time": 0.0, "comp": "Repro_Main_HD"},
    },
    {
        "id": "M3_kf_scale_out", "module": "M3_Keyframes",
        "type": "add_keyframe",
        "description": "矩形缩放关键帧: 100% at 0.8s",
        "params": {"layer": "Shape", "property": "ADBE Transform Group/ADBE Scale", "value": [100, 100], "time": 0.8, "comp": "Repro_Main_HD"},
    },
    {
        "id": "M3_pos_title", "module": "M3_Keyframes",
        "type": "set_layer_pos",
        "description": "设置标题位置居中",
        "params": {"layer": "AE 实战复刻验证", "position": [960, 540], "comp": "Repro_Main_HD"},
    },
    {
        "id": "M3_pos_shape", "module": "M3_Keyframes",
        "type": "set_layer_pos",
        "description": "设置矩形居中",
        "params": {"layer": "Shape", "position": [960, 540], "comp": "Repro_Main_HD"},
    },
    # === 模块 4: 效果 ===
    {
        "id": "M4_effect_gaussian", "module": "M4_Effects",
        "type": "add_effect",
        "description": "添加高斯模糊效果",
        "params": {"layer": "AE 实战复刻验证", "effect": "ADBE Gaussian Blur 2", "comp": "Repro_Main_HD"},
    },
    {
        "id": "M4_effect_fill", "module": "M4_Effects",
        "type": "add_effect",
        "description": "添加填充效果",
        "params": {"layer": "Shape", "effect": "ADBE Fill", "comp": "Repro_Main_HD"},
    },
    {
        "id": "M4_effect_glow", "module": "M4_Effects",
        "type": "add_effect",
        "description": "添加发光效果到调整层",
        "params": {"layer": "Glow_Adjust", "effect": "ADBE Glow2", "comp": "Repro_Main_HD"},
    },
    # === 模块 5: 表达式 ===
    {
        "id": "M5_expr_wiggle", "module": "M5_Expressions",
        "type": "set_expression",
        "description": "设置 wiggle 表达式到文字位置",
        "params": {"layer": "AE 实战复刻验证", "property": "ADBE Transform Group/ADBE Position", "expression": "wiggle(2, 10)", "comp": "Repro_Main_HD"},
    },
    {
        "id": "M5_expr_loopout", "module": "M5_Expressions",
        "type": "set_expression",
        "description": "设置 loopOut 表达式到形状缩放",
        "params": {"layer": "Shape", "property": "ADBE Transform Group/ADBE Scale", "expression": "loopOut('cycle')", "comp": "Repro_Main_HD"},
    },
    # === 模块 6: 混合与 3D ===
    {
        "id": "M6_blending_add", "module": "M6_Blending",
        "type": "set_blending",
        "description": "设置发光调整层混合模式为 Add",
        "params": {"layer": "Glow_Adjust", "mode": 14, "comp": "Repro_Main_HD"},
    },
    {
        "id": "M6_3d_layer", "module": "M6_3D",
        "type": "set_3d",
        "description": "设置矩形为 3D 图层",
        "params": {"layer": "Shape", "comp": "Repro_Main_HD"},
    },
    # === 模块 7: 复制与重命名 ===
    {
        "id": "M7_dup", "module": "M7_Duplication",
        "type": "duplicate_layer",
        "description": "复制矩形图层",
        "params": {"layer": "Shape", "comp": "Repro_Main_HD"},
    },
    {
        "id": "M7_rename", "module": "M7_Duplication",
        "type": "rename_layer",
        "description": "重命名复制图层",
        "params": {"layer": "Shape", "new_name": "Shape_Original", "comp": "Repro_Main_HD"},
    },
]


# ============================================================
# AE 编排器（总控）
# ============================================================


class AEOrchestrator:
    """
    AE 自动化编排器 — 全链路实战复刻 + 渲染

    流程：
    INIT → DETECTING → LAUNCHING → CONNECTING → LOADING
    → EXECUTING → CONFIGURING_RENDER → RENDERING
    → MONITORING → SAVING → CLOSING → COMPLETE

    每个阶段都有异常处理和状态记录。
    """

    def __init__(
        self,
        output_dir: str = "test_outputs/render_outputs",
        render_format: str = "avi",
        bridge_timeout: float = 60.0,
        render_timeout_minutes: int = 30,
        dry_run: bool = False,
        skip_render: bool = False,
        skip_close: bool = False,
    ):
        self.output_dir = safe_mkdirs(safe_path(output_dir))
        self.report_dir = safe_mkdirs(os.path.join(self.output_dir, "..", "reports"))
        self.render_format = render_format
        self.bridge_timeout = bridge_timeout
        self.render_timeout_minutes = render_timeout_minutes
        self.dry_run = dry_run
        self.skip_render = skip_render
        self.skip_close = skip_close

        # 会话标识
        self.session_id = uuid.uuid4().hex[:12]
        self.report = OrchestratorReport(
            session_id=self.session_id,
            title=f"AE 自动化复刻渲染报告 - {timestamp_iso()}",
            start_time=timestamp_iso(),
        )
        self._phase_start: dict[str, float] = {}
        self._start_time = time.time()

        # 组件（延迟初始化）
        self.bridge: AEBridgeClient | None = None
        self.project_mgr: AEProjectManager | None = None
        self.step_executor: AEStepExecutor | None = None
        self.render_mgr: AERenderManager | None = None

        # AE 路径
        self.ae_path: str | None = None
        self.aerender_path: str | None = None
        self.ae_support_dir: str | None = None

        # 信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    # ========== 阶段管理 ==========

    def _enter_phase(self, phase: AEPhase):
        """进入新阶段，记录时间"""
        self._phase_start[phase.name] = time.time()
        self.report.phase = phase
        self.report.phase_timeline.append({
            "phase": phase.value,
            "time": timestamp_iso(),
            "status": "entered",
        })

    def _exit_phase(self, phase: AEPhase, success: bool, detail: str = ""):
        """退出阶段"""
        elapsed = elapsed_since(self._phase_start.get(phase.name, time.time()))
        self.report.phase_timeline[-1].update({
            "status": "completed" if success else "failed",
            "elapsed_ms": elapsed,
            "detail": detail,
        })

    # ========== 信号处理 ==========

    def _signal_handler(self, signum, frame):
        print(f"\n⚠️ 收到信号 {signum}，正在安全清理...")
        self._emergency_cleanup()
        sys.exit(1)

    def _emergency_cleanup(self):
        """紧急清理：取消渲染、保存项目"""
        try:
            if self.render_mgr:
                self.render_mgr.cancel_render()
        except Exception:
            pass
        try:
            if self.project_mgr:
                self.project_mgr.save_project()
        except Exception:
            pass

    # ========== 阶段 1: 环境检测 ==========

    def phase_detect_ae(self) -> bool:
        """检测 AE 安装"""
        self._enter_phase(AEPhase.DETECTING)
        detector = AEInstallDetector()
        self.ae_path, self.ae_support_dir, self.aerender_path = detector.find_ae_path()

        if not self.ae_path:
            self.report.errors.append("未找到 After Effects 安装")
            self._exit_phase(AEPhase.DETECTING, False, "AE not found")
            return False

        self.report.ae_path = self.ae_path
        self.report.aerender_path = self.aerender_path or ""
        self.report.ae_version = detector.detect_ae_version(self.ae_path)
        self.report.system_info = {
            "platform": sys.platform,
            "python_version": sys.version,
            "ae_path": self.ae_path,
            "aerender_available": str(self.aerender_path is not None),
        }

        ports = [f"\u2714 AE: {self.ae_path}"]
        if self.aerender_path:
            ports.append(f"\u2714 aerender: {self.aerender_path}")
        else:
            ports.append("\u26A0 aerender 未找到（将使用 Bridge 渲染）")
            self.report.warnings.append("aerender CLI 未安装，渲染将回退到 Bridge 模式")

        self._exit_phase(AEPhase.DETECTING, True, " | ".join(ports))
        return True

    # ========== 阶段 2: 连接 Bridge ==========

    def phase_connect_bridge(self) -> bool:
        """连接 AE Bridge"""
        self._enter_phase(AEPhase.CONNECTING)
        self.bridge = AEBridgeClient(timeout_sec=self.bridge_timeout)

        if self.bridge.connected:
            self.report.bridge_connected = True
            self._exit_phase(AEPhase.CONNECTING, True, "Bridge connected")
            return True

        # Bridge 未连接
        self.report.bridge_connected = False
        if self.dry_run:
            self.report.warnings.append("DRY-RUN: Bridge 未连接，将使用模拟模式")
            self._exit_phase(AEPhase.CONNECTING, True, "Dry-run mode (no bridge)")
            return True

        msg = (
            "AE Bridge 未连接。请检查：\n"
            "  1. After Effects 是否已启动\n"
            "  2. Bridge 面板是否已加载 (Ctrl+Shift+B)\n"
            "  3. Bridge 文件目录权限: {BRIDGE_DIR}"
        ).format(BRIDGE_DIR=BRIDGE_DIR)
        self.report.errors.append(msg)
        self._exit_phase(AEPhase.CONNECTING, False, "Bridge not connected")
        return False

    # ========== 阶段 3: 加载项目 ==========

    def phase_load_project(self, project_path: str) -> bool:
        """加载 AE 项目文件"""
        self._enter_phase(AEPhase.LOADING)
        self.report.project_file = safe_path(project_path)
        self.project_mgr = AEProjectManager(self.bridge)

        if self.dry_run:
            self.report.warnings.append(f"DRY-RUN: 模拟加载项目 {project_path}")
            self._exit_phase(AEPhase.LOADING, True, "Dry-run")
            return True

        # 检查文件存在
        project_path = safe_path(project_path)
        if not os.path.isfile(project_path):
            self.report.errors.append(f"项目文件不存在: {project_path}")
            self._exit_phase(AEPhase.LOADING, False, "File not found")
            return False

        # 打开项目
        ok, res = self.project_mgr.open_project(project_path)
        if not ok:
            err = res.get("error", "Unknown") if isinstance(res, dict) else str(res)
            self.report.errors.append(f"加载项目失败: {err}")
            self._exit_phase(AEPhase.LOADING, False, err)
            return False

        # 获取项目信息
        info = self.project_mgr.get_project_info()
        comps = info.get("compositions", [])
        if comps:
            self.report.composition_name = comps[0].get("name", "")
            self.report.composition_duration = comps[0].get("duration", 0.0)

        self.report.project_loaded = True
        self._exit_phase(AEPhase.LOADING, True, f"Loaded: {os.path.basename(project_path)}")
        return True

    # ========== 阶段 4: 执行复刻步骤 ==========

    def phase_execute_steps(
        self, steps: list[dict] | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> bool:
        """
        执行复刻步骤集

        参数：
            steps: 步骤列表，None 则使用 DEFAULT_REPRODUCTION_STEPS
            progress_callback: 进度回调 (current, total, description)
        """
        self._enter_phase(AEPhase.EXECUTING)
        self.step_executor = AEStepExecutor(self.bridge)
        all_steps = steps or DEFAULT_REPRODUCTION_STEPS
        total = len(all_steps)

        if self.dry_run:
            for step in all_steps:
                sr = StepResult(
                    step_id=step["id"], module=step["module"],
                    description=step["description"], status=StepStatus.PASS,
                    message="DRY-RUN simulated"
                )
                self._record_step(sr)
                if progress_callback:
                    progress_callback(self.report.total_steps, total, step["description"])
            self._exit_phase(AEPhase.EXECUTING, True, f"Dry-run: {total} steps simulated")
            return True

        for idx, step in enumerate(all_steps):
            if progress_callback:
                progress_callback(idx + 1, total, step["description"])

            sr, _ = self.step_executor.execute_step(step)
            self._record_step(sr)

            # 失败时尝试重试
            retry = 0
            while sr.status == StepStatus.FAIL and retry < MAX_RETRIES:
                retry += 1
                time.sleep(RETRY_DELAY_SEC)
                sr.retry_count = retry
                sr, _ = self.step_executor.execute_step(step)
                self.report.steps_passed = self.report.steps_passed  # 保留原有计数
                self._record_step(sr, merge=True)

        has_failures = self.report.steps_failed > 0
        detail = f"{self.report.steps_passed}/{total} passed"
        if has_failures:
            detail += f", {self.report.steps_failed} failed"
        if self.report.steps_skipped > 0:
            detail += f", {self.report.steps_skipped} skipped"

        self._exit_phase(AEPhase.EXECUTING, not (has_failures > total // 3), detail)
        return True

    def _record_step(self, sr: StepResult, merge: bool = False):
        """记录步骤结果到报告"""
        if merge:
            # 重试时更新已有记录
            for i, existing in enumerate(self.report.steps_details):
                if existing.get("step_id") == sr.step_id:
                    self.report.steps_details[i] = sr.to_dict()
                    # 更新计数
                    if sr.status == StepStatus.PASS:
                        self.report.steps_failed -= 1
                        self.report.steps_passed += 1
                    return

        self.report.total_steps += 1
        self.report.steps_details.append(sr.to_dict())

        if sr.status == StepStatus.PASS:
            self.report.steps_passed += 1
        elif sr.status == StepStatus.FAIL:
            self.report.steps_failed += 1
            self.report.errors.append(f"[{sr.step_id}] {sr.description}: {sr.message}")
        elif sr.status == StepStatus.SKIP:
            self.report.steps_skipped += 1
        elif sr.status == StepStatus.WARN:
            self.report.steps_warn += 1
            self.report.warnings.append(f"[{sr.step_id}] {sr.description}: {sr.message}")

    # ========== 阶段 5: 配置渲染 ==========

    def phase_configure_render(
        self, comp_name: str, config: RenderConfig | None = None
    ) -> bool:
        """配置渲染队列"""
        self._enter_phase(AEPhase.CONFIGURING_RENDER)
        self.render_mgr = AERenderManager(self.bridge, self.aerender_path)

        if config is None:
            config = RenderConfig(
                output_dir=self.output_dir,
                output_filename=f"ae_reproduce_{self.session_id}",
                output_format=self.render_format,
                resolution_multiplier=1.0,
                timeout_minutes=self.render_timeout_minutes,
            )

        self.report.render_format = config.output_format
        self.report.render_resolution = f"{int(config.resolution_multiplier * 100)}%"

        if self.dry_run:
            self.report.warnings.append(f"DRY-RUN: 模拟配置渲染队列 ({comp_name} → {config.output_filename}.{config.output_format})")
            self._exit_phase(AEPhase.CONFIGURING_RENDER, True, "Dry-run")
            return True

        ok, res = self.render_mgr.configure_render_queue_bridge(comp_name, config)
        if not ok:
            err = res.get("error", "Unknown") if isinstance(res, dict) else str(res)
            self.report.errors.append(f"渲染队列配置失败: {err}")
            self._exit_phase(AEPhase.CONFIGURING_RENDER, False, err)
            return False

        self._exit_phase(AEPhase.CONFIGURING_RENDER, True, f"{comp_name} → {config.output_format}")
        return True

    # ========== 阶段 6: 执行渲染 ==========

    def phase_render(
        self, comp_name: str, config: RenderConfig | None = None,
        project_path: str | None = None,
    ) -> bool:
        """执行渲染并监控进度"""
        self._enter_phase(AEPhase.RENDERING)

        if config is None:
            config = RenderConfig(
                output_dir=self.output_dir,
                output_filename=f"ae_reproduce_{self.session_id}",
                output_format=self.render_format,
                timeout_minutes=self.render_timeout_minutes,
            )

        if self.dry_run:
            self.report.warnings.append("DRY-RUN: 模拟渲染（跳过实际渲染）")
            self._exit_phase(AEPhase.RENDERING, True, "Dry-run")
            return True

        if self.skip_render:
            self.report.warnings.append("--skip-render 已启用，跳过渲染阶段")
            self._exit_phase(AEPhase.RENDERING, True, "Skipped by user")
            return True

        def on_progress(name: str, percent: float):
            print(f"  \r【渲染进度】{name}: {percent:.0f}%", end="", flush=True)

        success, info = self.render_mgr.render(
            comp_name, config, project_path, on_progress
        )
        print()  # 换行

        self.report.render_success = success
        self.report.render_duration_ms = info.get("duration_ms", 0.0)
        self.report.render_method = info.get("render_method", "unknown")
        self.report.render_output_path = info.get("output_file", "")
        self.report.output_file_size_mb = info.get("file_size_mb", 0.0)
        self.report.output_frame_count = info.get("frame_count", 0)

        if not success:
            err = info.get("error", "Unknown render error")
            self.report.errors.append(f"渲染失败: {err}")
            self._exit_phase(AEPhase.RENDERING, False, err)
            return False

        detail = f"{self.report.render_method}: {os.path.basename(self.report.render_output_path)} ({self.report.output_file_size_mb:.1f} MB)"
        self._exit_phase(AEPhase.RENDERING, True, detail)
        return True

    # ========== 阶段 7: 保存并关闭 ==========

    def phase_save_and_close(self) -> bool:
        """保存项目并关闭 AE"""
        self._enter_phase(AEPhase.SAVING)

        if self.dry_run or self.skip_close:
            self._exit_phase(AEPhase.SAVING, True, "Skipped")
            self._exit_phase(AEPhase.CLOSING, True, "Skipped")
            self._enter_phase(AEPhase.COMPLETE)
            return True

        # 保存
        if self.project_mgr:
            ok, msg = self.project_mgr.save_project()
            if not ok:
                self.report.warnings.append(f"保存项目时出现问题: {msg}")
        self._exit_phase(AEPhase.SAVING, True, "Saved")

        # 关闭
        self._enter_phase(AEPhase.CLOSING)
        if self.project_mgr:
            ok, msg = self.project_mgr.close_project(save=False)
            if not ok:
                self.report.warnings.append(f"关闭项目时出现问题: {msg}")
        self._exit_phase(AEPhase.CLOSING, True, "Closed")

        self._enter_phase(AEPhase.COMPLETE)
        return True

    # ========== 完整编排流程 ==========

    def run(
        self,
        project_path: str | None = None,
        comp_name: str | None = None,
        steps: list[dict] | None = None,
        render_config: RenderConfig | None = None,
    ) -> OrchestratorReport:
        """
        执行完整自动化流程

        参数：
            project_path: AE 项目文件路径（可选，不传则创建新项目复刻）
            comp_name: 目标合成名称（可选，自动从项目查找）
            steps: 复刻步骤列表（可选，默认使用内置步骤）
            render_config: 渲染配置（可选）
        """
        try:
            # --- 阶段 1: 检测环境 ---
            if not self.phase_detect_ae():
                self._enter_phase(AEPhase.ABORTED)
                self._finalize()
                return self.report

            # --- 阶段 2: 连接 Bridge ---
            if not self.phase_connect_bridge():
                self._enter_phase(AEPhase.ABORTED)
                self._finalize()
                return self.report

            # --- 阶段 3: 加载 / 创建项目 ---
            if project_path and os.path.isfile(safe_path(project_path)):
                if not self.phase_load_project(project_path):
                    self._enter_phase(AEPhase.ABORTED)
                    self._finalize()
                    return self.report
                # 从现有项目中查找合成
                if not comp_name and self.project_mgr:
                    comp = self.project_mgr.find_composition()
                    if comp:
                        comp_name = comp.get("name", "")
            else:
                if project_path:
                    self.report.warnings.append(f"项目文件不存在，将创建新项目: {project_path}")
                # 无项目文件，新建空项目（AE 默认就是空项目）
                self.report.project_file = "(new project)"
                self.report.project_loaded = True
                self._enter_phase(AEPhase.LOADING)
                self._exit_phase(AEPhase.LOADING, True, "New project")

            # --- 阶段 4: 执行复刻步骤 ---
            self.phase_execute_steps(steps)

            # --- 阶段 5: 查找/确定渲染目标合成 ---
            if not comp_name:
                # 尝试从步骤中找到创建的合成
                for sr in self.report.steps_details:
                    if sr.get("module") == "M1_Composition" and sr.get("status") == StepStatus.PASS.value:
                        comp_name = "Repro_Main_HD"
                        break
                if not comp_name and self.project_mgr:
                    comp = self.project_mgr.find_composition()
                    if comp:
                        comp_name = comp.get("name", "")

            if not comp_name:
                self.report.warnings.append("未找到可渲染的合成，跳过渲染阶段")
                self.skip_render = True

            # --- 阶段 6: 配置并执行渲染 ---
            if not self.skip_render and comp_name:
                if not self.phase_configure_render(comp_name, render_config):
                    pass  # 继续尝试渲染
                self.phase_render(comp_name, render_config, project_path)

            # --- 阶段 7: 保存并关闭 ---
            self.phase_save_and_close()

        except KeyboardInterrupt:
            self._enter_phase(AEPhase.ABORTED)
            self.report.errors.append("用户中断 (Ctrl+C)")
            self._emergency_cleanup()
        except Exception as e:
            self._enter_phase(AEPhase.ERROR)
            self.report.errors.append(f"未捕获异常: {e}\n{traceback.format_exc()}")
            self._emergency_cleanup()
        finally:
            self._finalize()

        return self.report

    def _finalize(self):
        """收尾：生成报告文件"""
        self.report.end_time = timestamp_iso()
        self.report.total_elapsed_ms = elapsed_since(self._start_time)

        # 写入报告文件
        report_json = os.path.join(self.report_dir, f"ae_orchestrator_{self.session_id}.json")
        report_md = os.path.join(self.report_dir, f"ae_orchestrator_{self.session_id}.md")

        try:
            with open(report_json, "w", encoding="utf-8") as f:
                json.dump(self.report.to_dict(), f, ensure_ascii=False, indent=2)
        except (IOError, OSError) as e:
            print(f"⚠️ 无法写入 JSON 报告: {e}")

        try:
            md_content = self._generate_markdown_report()
            with open(report_md, "w", encoding="utf-8") as f:
                f.write(md_content)
        except (IOError, OSError) as e:
            print(f"⚠️ 无法写入 Markdown 报告: {e}")

        print("\n📊 报告已保存:")
        print(f"   JSON: {report_json}")
        print(f"   MD:   {report_md}")

    def _generate_markdown_report(self) -> str:
        """生成 Markdown 结构化报告"""
        r = self.report
        pass_rate = (r.steps_passed / r.total_steps * 100) if r.total_steps > 0 else 0

        lines = [
            f"# {r.title}",
            "",
            f"**会话 ID**: `{r.session_id}`  ",
            f"**开始时间**: {r.start_time}  ",
            f"**结束时间**: {r.end_time}  ",
            f"**总耗时**: {r.total_elapsed_ms / 1000:.1f}s  ",
            f"**最终状态**: {r.phase.value}  ",
            "",
            "---",
            "",
            "## 环境信息",
            "",
            "| 项目 | 值 |",
            "|------|-----|",
            f"| AE 路径 | `{r.ae_path}` |",
            f"| AE 版本 | {r.ae_version} |",
            f"| aerender | {'✅ 可用' if r.aerender_path else '❌ 不可用'} |",
            f"| Bridge 连接 | {'✅ 已连接' if r.bridge_connected else '❌ 未连接'} |",
            f"| Python | {sys.version.split()[0]} |",
            f"| 平台 | {sys.platform} |",
            "",
            "---",
            "",
            "## 项目信息",
            "",
            "| 项目 | 值 |",
            "|------|-----|",
            f"| 项目文件 | `{r.project_file}` |",
            f"| 加载成功 | {'✅' if r.project_loaded else '❌'} |",
            f"| 目标合成 | `{r.composition_name}` |",
            f"| 合成时长 | {r.composition_duration:.1f}s |",
            "",
            "---",
            "",
            "## 复刻步骤统计",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 总步骤 | {r.total_steps} |",
            f"| ✅ 通过 | {r.steps_passed} |",
            f"| ❌ 失败 | {r.steps_failed} |",
            f"| ⚪ 跳过 | {r.steps_skipped} |",
            f"| ⚠️ 警告 | {r.steps_warn} |",
            f"| 通过率 | {pass_rate:.1f}% |",
            "",
            "### 步骤详情",
            "",
            "| ID | 模块 | 步骤 | 状态 | 耗时 | 备注 |",
            "|----|------|------|------|------|------|",
        ]

        for s in r.steps_details:
            status = s.get("status", "⏳")
            ms = s.get("elapsed_ms", 0)
            msg = str(s.get("message", ""))[:50]
            lines.append(
                f"| {s.get('step_id', '?')} | {s.get('module', '?')} | "
                f"{s.get('description', '?')} | {status} | {ms:.0f}ms | {msg} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 渲染信息",
            "",
            "| 项目 | 值 |",
            "|------|-----|",
            f"| 渲染成功 | {'✅ 成功' if r.render_success else '❌ 失败'} |",
            f"| 渲染方法 | `{r.render_method}` |",
            f"| 输出路径 | `{r.render_output_path}` |",
            f"| 输出格式 | {r.render_format} |",
            f"| 分辨率 | {r.render_resolution} |",
            f"| 文件大小 | {r.output_file_size_mb:.1f} MB |",
            f"| 帧数 | {r.output_frame_count} |",
            f"| 渲染耗时 | {r.render_duration_ms / 1000:.1f}s |",
            "",
        ])

        # 错误列表
        if r.errors:
            lines.extend(["---", "", "## ❌ 错误列表", ""])
            for i, err in enumerate(r.errors, 1):
                lines.append(f"{i}. {err}")
            lines.append("")

        # 警告列表
        if r.warnings:
            lines.extend(["---", "", "## ⚠️ 警告列表", ""])
            for i, warn in enumerate(r.warnings, 1):
                lines.append(f"{i}. {warn}")
            lines.append("")

        # 阶段时间线
        lines.extend(["---", "", "## 阶段时间线", ""])
        for entry in r.phase_timeline:
            status = "✅" if entry.get("status") == "completed" else "❌"
            lines.append(
                f"- {status} **{entry.get('phase', '?')}** "
                f"({entry.get('time', '?')}) "
                f"- {entry.get('detail', '')}"
            )

        # 插件缺失（如果有检测）
        if r.plugin_missing:
            lines.extend(["", "---", "", "## 🔌 缺失插件/效果", ""])
            lines.append("| 插件名 | MatchName | 安装 URL |")
            lines.append("|--------|-----------|----------|")
            for p in r.plugin_missing:
                lines.append(f"| {p.get('name', '?')} | `{p.get('matchName', '?')}` | {p.get('url', '-')} |")

        lines.extend([
            "",
            "---",
            "",
            f"*报告由 AE Orchestrator 自动生成，会话 ID: {self.session_id}*",
        ])

        return "\n".join(lines)


# ============================================================
# CLI 入口
# ============================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AE 自动化渲染编排器 — 全链路实战复刻 + 渲染输出",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        示例：
          # 标准复刻 + 渲染
          python ae_auto_render_orchestrator.py

          # 加载指定项目
          python ae_auto_render_orchestrator.py --project ./my_proj.aep

          # 指定输出路径和格式
          python ae_auto_render_orchestrator.py --output ./my_renders --format mov

          # 仅执行复刻步骤，跳过渲染
          python ae_auto_render_orchestrator.py --skip-render

          # 预演模式（不连接 AE）
          python ae_auto_render_orchestrator.py --dry-run

          # 自定义步骤文件
          python ae_auto_render_orchestrator.py --step-file ./my_steps.json

          # 渲染完成后保持 AE 打开
          python ae_auto_render_orchestrator.py --skip-close
        """),
    )
    parser.add_argument("--project", "-p", default="",
                        help="要加载的 AE 项目文件路径 (不指定则创建新项目)")
    parser.add_argument("--comp", "-c", default="",
                        help="目标合成名称 (不指定则自动查找)")
    parser.add_argument("--output", "-o", default="test_outputs/render_outputs",
                        help="渲染输出目录 (默认: test_outputs/render_outputs)")
    parser.add_argument("--format", "-f", default="avi",
                        choices=["avi", "mov", "jpeg_sequence", "png_sequence",
                                 "psd_sequence", "tiff_sequence", "tga_sequence"],
                        help="输出视频/序列格式 (默认: avi)")
    parser.add_argument("--resolution", "-r", type=float, default=1.0,
                        help="渲染分辨率倍率 (1.0=Full, 0.5=Half, 0.25=Quarter)")
    parser.add_argument("--timeout", "-t", type=int, default=30,
                        help="渲染超时时间（分钟）(默认: 30)")
    parser.add_argument("--bridge-timeout", type=float, default=60.0,
                        help="Bridge 通信超时（秒）(默认: 60)")
    parser.add_argument("--step-file", default="",
                        help="自定义复刻步骤 JSON 文件路径")
    parser.add_argument("--dry-run", action="store_true",
                        help="预演模式：模拟执行，不连接 AE")
    parser.add_argument("--skip-render", action="store_true",
                        help="跳过渲染阶段（仅执行复刻步骤）")
    parser.add_argument("--skip-close", action="store_true",
                        help="渲染完成后不关闭 AE")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="详细输出")
    return parser.parse_args()


def load_steps_from_file(step_file: str) -> list[dict] | None:
    """从 JSON 文件加载步骤"""
    try:
        with open(step_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "steps" in data:
            return data["steps"]
        if isinstance(data, list):
            return data
        return None
    except (IOError, json.JSONDecodeError, OSError) as e:
        print(f"⚠️ 无法加载步骤文件: {e}")
        return None


def progress_printer(current: int, total: int, description: str, verbose: bool = False):
    """终端进度输出"""
    bar_len = 30
    filled = int(bar_len * current / total)
    bar = "█" * filled + "░" * (bar_len - filled)
    status_line = f"  [{bar}] {current}/{total}"
    if verbose:
        status_line += f" - {description}"
    print(f"\r{status_line}", end="", flush=True)


def main():
    args = parse_args()

    print("=" * 60)
    print("  AE 自动化渲染编排器")
    print("  全链路实战复刻 + 渲染输出")
    print("=" * 60)
    print()

    # 步骤文件
    steps = None
    if args.step_file:
        steps = load_steps_from_file(args.step_file)
        if steps is None:
            print("⚠️ 步骤文件加载失败，将使用默认步骤集")
        else:
            print(f"✅ 加载自定义步骤: {len(steps)} 步")
    if steps is None:
        steps = DEFAULT_REPRODUCTION_STEPS
        print(f"📋 使用默认步骤集: {len(steps)} 步")

    # 渲染配置
    render_config = RenderConfig(
        output_dir=args.output,
        output_filename=f"ae_reproduce_{datetime.now():%Y%m%d_%H%M%S}",
        output_format=args.format,
        resolution_multiplier=args.resolution,
        timeout_minutes=args.timeout,
    )

    # 创建编排器
    orchestrator = AEOrchestrator(
        output_dir=args.output,
        render_format=args.format,
        bridge_timeout=args.bridge_timeout,
        render_timeout_minutes=args.timeout,
        dry_run=args.dry_run,
        skip_render=args.skip_render,
        skip_close=args.skip_close,
    )

    # 进度回调（非 dry-run 且详细模式下）
    progress_cb = None
    if not args.dry_run and args.verbose:

        def cb(current, total, desc):
            progress_printer(current, total, desc, verbose=True)

        progress_cb = cb

    # 执行
    print(f"\n{'【预演模式】' if args.dry_run else '🚀 开始自动化流程...'}")
    t0 = time.time()

    report = orchestrator.run(
        project_path=args.project if args.project else None,
        comp_name=args.comp if args.comp else None,
        steps=steps,
        render_config=render_config,
    )

    total_sec = (time.time() - t0)

    # 最终输出
    print(f"\n{'=' * 60}")
    print(f"  流程完成 (耗时 {total_sec:.1f}s)")
    print(f"  状态: {report.phase.value}")
    print(f"  步骤: {report.steps_passed}/{report.total_steps} 通过 "
          f"({report.steps_failed} 失败, {report.steps_skipped} 跳过)")
    print(f"  渲染: {'✅ 成功' if report.render_success else '❌ 失败' if not args.skip_render else '⏭️ 跳过'}")
    if report.render_output_path:
        print(f"  输出: {report.render_output_path} "
              f"({report.output_file_size_mb:.1f} MB)")
    print(f"{'=' * 60}")

    if report.errors:
        print(f"\n❌ 共 {len(report.errors)} 个错误:")
        for i, err in enumerate(report.errors[:10], 1):
            short = str(err)[:120].replace("\n", " ")
            print(f"  {i}. {short}")
        if len(report.errors) > 10:
            print(f"  ... 共 {len(report.errors)} 个错误，详见报告")

    # 返回码
    return 1 if report.phase in (AEPhase.ERROR, AEPhase.ABORTED) else 0


if __name__ == "__main__":
    sys.exit(main())
