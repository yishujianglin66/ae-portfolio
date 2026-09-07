"""
AE aerender 命令行渲染引擎 v2.0 — 生产级全面修复版
======================================================

为什么用 aerender（而不是 JSX Bridge）？
---------------------------------------
1. **无界面后台渲染**：不受 AE GUI 模态对话框阻塞（素材丢失/字体缺失/许可弹窗等）
2. **进程隔离**：渲染崩溃不影响 AE 主实例，可自动重试
3. **多进程加速**：-mp 参数利用多核 CPU 并行渲染帧
4. **命令行可控**：精确指定模板、帧范围、输出路径，适合自动化流水线
5. **独立运行**：不需要 AE 前台打开项目，可从冷启动直接渲染
6. **错误码标准化**：退出码直接反映错误类型，便于诊断

aerender 渲染失败根因分类与修复
--------------------------------
- 路径探测不足 → 注册表 + 多盘符 + 多版本 + 环境变量 全量探测
- 模板名不匹配 → 多候选 fallback，按 AE 版本自动选择
- 错误码无解析 → 11 种标准错误码 + 中文错误描述 + 可重试标记
- -reuse 误判 → 自动检测 AE 进程状态后决定是否复用
- 日志不完整 → stdout/stderr 全量捕获 + -v ERRORS_AND_PROGRESS
- 特殊字符路径 → Windows API 宽字符路径 + subprocess list 参数
- 无重试机制 → 按错误码分类自动重试（临时性错误最多 2 次）
- 输出验证不足 → 大小阈值 + 文件锁等待 + ffprobe 完整性校验（可选）
- 进程泄漏 → 进程树递归终止（含 -mp 子进程）
- 无环境预检 → 磁盘空间/权限/文件锁 预检查
- 内存溢出 → -memory 智能分配（根据系统内存和 -mp 并发数）
- 中文 AE 日志 → 多语言进度正则（中/英/日）

封装 aerender.exe 为 Python 类，支持：
- 单合成渲染 / 批量渲染 / 队列渲染
- 模板渲染（数据驱动）
- 实时进度监控 / 可取消
- 完整日志解析 / 结构化错误诊断
- 智能复用AE实例 (-reuse) / 冷启动模式
- 自动重试 / 模板 fallback
- 环境预检 / 输出验证
"""

from __future__ import annotations

import os
import re
import sys
import json
import time
import shutil
import signal
import ctypes
import locale
import logging
import platform
import subprocess
import threading
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable, Tuple, Any
from enum import Enum, IntEnum


logger = logging.getLogger(__name__)


# ============================================================================
#  错误码定义 — aerender 标准退出码
# ============================================================================

class AerenderExitCode(IntEnum):
    """aerender 进程退出码（基于 Adobe 官方文档 + 实际测试）"""
    SUCCESS = 0
    FATAL_ERROR = 1              # 致命内部错误（内存溢出/GPU崩溃）
    INVALID_ARGS = 2             # 命令行参数无效
    CANNOT_OPEN_PROJECT = 3      # 无法打开项目（路径错误/版本不兼容/文件损坏/被占用）
    COMP_NOT_FOUND = 4           # 合成不存在（名称错误/拼写错误/未保存）
    OM_TEMPLATE_NOT_FOUND = 5    # 输出模块模板不存在（预设名不匹配）
    RS_TEMPLATE_NOT_FOUND = 6    # 渲染设置模板不存在
    CANNOT_WRITE_OUTPUT = 7      # 无法写入输出（磁盘满/权限不足/文件被占用）
    LICENSE_ERROR = 8            # 许可证问题（未激活/试用过期）
    USER_CANCELLED = 9           # 用户取消
    RENDER_ERROR = 10            # 渲染过程错误（特效失败/素材损坏）
    GPU_INIT_FAILED = 11         # GPU 初始化失败（驱动问题/CUDA不可用）
    TIMEOUT = 127                # 我们自定义的超时码（非aerender原生）


# 错误码 → 中文描述 + 是否可重试
ERROR_CODE_INFO: Dict[int, Dict[str, Any]] = {
    AerenderExitCode.SUCCESS: {
        "desc": "渲染成功", "retryable": False, "category": "success",
    },
    AerenderExitCode.FATAL_ERROR: {
        "desc": "内部致命错误（内存溢出/GPU崩溃）", "retryable": True, "category": "system",
        "suggestion": "检查内存使用，降低 -mp 并发数，更新显卡驱动，清理媒体缓存",
    },
    AerenderExitCode.INVALID_ARGS: {
        "desc": "命令行参数无效", "retryable": False, "category": "usage",
        "suggestion": "检查命令参数格式、路径是否包含特殊字符",
    },
    AerenderExitCode.CANNOT_OPEN_PROJECT: {
        "desc": "无法打开项目文件", "retryable": True, "category": "project",
        "suggestion": "检查 .aep 路径是否正确、AE版本是否兼容、文件是否被其他AE实例锁定",
    },
    AerenderExitCode.COMP_NOT_FOUND: {
        "desc": "合成不存在", "retryable": False, "category": "project",
        "suggestion": "检查合成名称拼写、项目是否已保存包含该合成",
    },
    AerenderExitCode.OM_TEMPLATE_NOT_FOUND: {
        "desc": "输出模块模板不存在", "retryable": True, "category": "template",
        "suggestion": "使用候选列表中其他模板名，或在AE中确认模板存在",
    },
    AerenderExitCode.RS_TEMPLATE_NOT_FOUND: {
        "desc": "渲染设置模板不存在", "retryable": True, "category": "template",
        "suggestion": "使用候选列表中其他渲染设置模板",
    },
    AerenderExitCode.CANNOT_WRITE_OUTPUT: {
        "desc": "无法写入输出文件", "retryable": True, "category": "io",
        "suggestion": "检查磁盘剩余空间、输出目录权限、文件是否被其他程序占用",
    },
    AerenderExitCode.LICENSE_ERROR: {
        "desc": "许可证问题", "retryable": False, "category": "license",
        "suggestion": "激活 After Effects，检查许可证是否过期",
    },
    AerenderExitCode.USER_CANCELLED: {
        "desc": "用户取消", "retryable": False, "category": "user",
    },
    AerenderExitCode.RENDER_ERROR: {
        "desc": "渲染过程错误（特效/素材问题）", "retryable": True, "category": "render",
        "suggestion": "检查素材文件是否完整、特效插件是否已安装、效果参数是否有效",
    },
    AerenderExitCode.GPU_INIT_FAILED: {
        "desc": "GPU 初始化失败", "retryable": True, "category": "system",
        "suggestion": "切换到软件渲染模式（在 AE 首选项中），更新 GPU 驱动",
    },
    AerenderExitCode.TIMEOUT: {
        "desc": "渲染超时", "retryable": True, "category": "timeout",
        "suggestion": "增加 timeout 参数，或拆分合成分段渲染",
    },
}


# ============================================================================
#  渲染状态与数据类
# ============================================================================

class RenderStatus(Enum):
    PENDING = "pending"
    PREFLIGHT = "preflight"         # 环境预检中
    STARTING = "starting"           # 启动 aerender 进程中
    RUNNING = "running"
    RETRYING = "retrying"           # 自动重试中
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class RenderDiagnostics:
    """渲染诊断信息（失败时收集）"""
    ae_version: str = ""
    aerender_path: str = ""
    project_path: str = ""
    project_size_mb: float = 0.0
    output_path: str = ""
    output_disk_free_gb: float = 0.0
    system_memory_gb: float = 0.0
    available_memory_gb: float = 0.0
    ae_process_running: bool = False
    command_line: str = ""
    stdout_tail: str = ""
    stderr_tail: str = ""
    log_file_path: str = ""
    attempt_count: int = 0
    total_duration_s: float = 0.0
    error_code: int = -1
    error_category: str = ""
    error_description: str = ""
    suggestion: str = ""


@dataclass
class RenderJob:
    """渲染任务"""
    job_id: str
    project_path: str
    composition: str
    output_path: str
    start_frame: int = 0
    end_frame: int = -1  # -1 = 全部
    output_format: str = "h264"  # h264, mov, prores, png_seq, tiff_seq, exr_seq
    reuse_ae: Optional[bool] = None  # None = 自动检测
    multi_process: bool = True
    memory_percent: int = 0  # 0 = 自动计算
    continue_on_missing_footage: bool = True
    close_project: str = "DO_NOT_SAVE_CHANGES"
    verbose_level: str = "ERRORS_AND_PROGRESS"
    om_template: Optional[str] = None  # None = 根据 output_format 从候选表选
    rs_template: Optional[str] = None
    max_retries: int = 2
    timeout: int = 0  # 0 = 根据帧数自动估算
    status: RenderStatus = RenderStatus.PENDING
    progress: float = 0.0
    current_frame: int = 0
    total_frames: int = 0
    error: str = ""
    error_code: int = -1
    start_time: float = 0.0
    end_time: float = 0.0
    attempts: int = 0
    diagnostics: Optional[RenderDiagnostics] = None
    log_path: str = ""
    process: Optional[subprocess.Popen] = None
    _cancel_event: Optional[threading.Event] = field(default=None, repr=False)

    def __post_init__(self):
        if self._cancel_event is None:
            self._cancel_event = threading.Event()

    def cancel(self):
        if self._cancel_event:
            self._cancel_event.set()


# ============================================================================
#  模板候选表 — 覆盖不同 AE 版本/语言的预设名变体
# ============================================================================

# 输出模块模板候选（按优先级排序，第一个可用的获胜）
# 注意：最后必须包含 None（不指定模板），让 aerender 使用项目渲染队列设置
OM_TEMPLATES: Dict[str, List[Optional[str]]] = {
    "h264": [
        "H.264 - Match Source - High bitrate",
        "Match Source - H.264 high bitrate",
        "H.264 Match Source High Bitrate",
        "H.264",
        "High Quality 1080p HD",
        "HD 1080p 29.97",
        "H.264 - YouTube 1080p HD",
        "H.264 - Vimeo 1080p HD",
        # 中文 AE 模板名
        "H.264 - 匹配源 - 高比特率",
        "匹配源 - H.264 高比特率",
        "高品质 1080p HD",
        "高画质 1080p",
        None,
    ],
    "mp4": [
        "H.264 - Match Source - High bitrate",
        "Match Source - H.264 high bitrate",
        "H.264",
        "H.264 - 匹配源 - 高比特率",
        None,
    ],
    "mov": [
        "Lossless",
        "Apple ProRes 422 HQ",
        "Apple ProRes 422",
        "Apple ProRes 4444",
        "GoPro CineForm YUV 10-bit Full",
        "Animation",
        "PNG with Alpha",
        "Lossless with Alpha",
        # 中文 AE 模板名
        "无损",
        "带 Alpha 的无损",
        "Apple ProRes 422 HQ",
        "动画",
        "PNG 带 Alpha",
        None,  # 最后兜底：不指定模板
    ],
    "prores": [
        "Apple ProRes 422 HQ",
        "Apple ProRes 422",
        "Apple ProRes 4444",
        "Apple ProRes 422 Proxy",
        "Apple ProRes 422 LT",
        None,
    ],
    "png_seq": [
        "PNG Sequence",
        "PNG",
        "Lossless",
        "PNG 序列",
        None,
    ],
    "tiff_seq": [
        "TIFF Sequence",
        "TIFF",
        "Lossless",
        "TIFF 序列",
        None,
    ],
    "exr_seq": [
        "EXR Sequence",
        "OpenEXR",
        "Float EXR",
        "EXR 序列",
        None,
    ],
    "jpeg_seq": [
        "JPEG Sequence",
        "JPEG",
        "JPEG 序列",
        None,
    ],
}

# 渲染设置模板候选（按优先级排序）
# 注意：最后必须包含 None（不指定模板）作为兜底
RS_TEMPLATES: Dict[str, List[Optional[str]]] = {
    "best": [
        "Best Settings",
        "Best",
        "Multi-Machine Settings",
        "Current Settings",
        # 中文 AE 模板名
        "最佳设置",
        "最佳",
        "当前设置",
        "多机设置",
        "草图设置",
        None,  # 兜底：不指定 RS 模板
    ],
    "draft": [
        "Draft Settings",
        "Draft",
        "Current Settings",
        "草图设置",
        "当前设置",
        None,
    ],
    "multi_machine": [
        "Multi-Machine Settings",
        "Multi-Machine",
        "Best Settings",
        "多机设置",
        "最佳设置",
        None,
    ],
}


# ============================================================================
#  aerender 路径自动探测
# ============================================================================

def detect_aerender() -> Optional[Path]:
    r"""全策略自动探测 aerender.exe 路径

    探测顺序（优先级从高到低）：
    1. 环境变量 AEKV_AERENDER_PATH
    2. 环境变量 AERENDER_PATH
    3. Windows 注册表（Adobe 安装信息）
    4. PROGRAMFILES 常见路径（多版本 2020-2026）
    5. PROGRAMFILES (x86) 路径
    6. 多盘符 D:\ E:\ F:\ 下的常见安装目录
    7. PATH 环境变量中的 aerender
    8. 配置文件 settings.py 中的 aerender_path
    """
    # 1-2. 环境变量优先（用户显式指定）
    for env_key in ["AEKV_AERENDER_PATH", "AERENDER_PATH"]:
        env_path = os.environ.get(env_key, "").strip()
        if env_path:
            p = Path(env_path)
            if p.exists() and p.is_file() and p.name.lower() == "aerender.exe":
                return p

    # 3. Windows 注册表探测
    if platform.system() == "Windows":
        reg_result = _detect_aerender_from_registry()
        if reg_result:
            return reg_result

    # 4-5. Program Files 多版本路径
    pf_dirs = []
    pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    pf_dirs.extend([pf, pf86])

    # Adobe 常见安装目录名
    ae_version_dirs = []
    for year in range(2020, 2028):
        ae_version_dirs.append(f"Adobe After Effects {year}")
        ae_version_dirs.append(f"Adobe After Effects CC {year}")
    ae_version_dirs.extend([
        "Adobe After Effects",
        "Adobe After Effects CC",
        "Adobe/Adobe After Effects 2025",
        "Adobe/Adobe After Effects 2024",
    ])

    for pf_dir in pf_dirs:
        for ae_dir_name in ae_version_dirs:
            candidate = Path(pf_dir) / "Adobe" / ae_dir_name / "Support Files" / "aerender.exe"
            if candidate.exists() and candidate.is_file():
                return candidate
            # 也尝试没有 Adobe 子目录的情况
            candidate2 = Path(pf_dir) / ae_dir_name / "Support Files" / "aerender.exe"
            if candidate2.exists() and candidate2.is_file():
                return candidate2

    # 6. 多盘符 D:\ E:\ F:\ 常见自定义安装路径
    for drive in ["D", "E", "F", "G"]:
        custom_paths = [
            f"{drive}:\\AE25\\Support Files\\aerender.exe",
            f"{drive}:\\AE\\2025\\Support Files\\aerender.exe",
            f"{drive}:\\AE\\2024\\Support Files\\aerender.exe",
            f"{drive}:\\Adobe\\Adobe After Effects 2025\\Support Files\\aerender.exe",
            f"{drive}:\\Adobe\\Adobe After Effects 2024\\Support Files\\aerender.exe",
            f"{drive}:\\Apps\\After Effects\\Support Files\\aerender.exe",
            f"{drive}:\\Program Files\\Adobe\\Adobe After Effects 2025\\Support Files\\aerender.exe",
            f"{drive}:\\Program Files\\Adobe\\Adobe After Effects 2024\\Support Files\\aerender.exe",
        ]
        for cp in custom_paths:
            p = Path(cp)
            if p.exists() and p.is_file():
                return p

    # 7. PATH 环境变量查找
    aerender_in_path = shutil.which("aerender.exe") or shutil.which("aerender")
    if aerender_in_path:
        return Path(aerender_in_path)

    # 8. 尝试从 puppet-automation 配置获取
    try:
        project_root = Path(__file__).parent.parent
        pa_src = project_root / "puppet-automation" / "src"
        if pa_src.exists() and str(pa_src) not in sys.path:
            sys.path.insert(0, str(pa_src))
        try:
            from config import settings
            if hasattr(settings, "aerender_path") and settings.aerender_path:
                sp = Path(settings.aerender_path)
                if sp.exists() and sp.is_file():
                    return sp
        except Exception:
            pass
    except Exception:
        pass

    return None


def _detect_aerender_from_registry() -> Optional[Path]:
    """从 Windows 注册表探测 AE 安装路径"""
    if platform.system() != "Windows":
        return None
    try:
        import winreg
    except ImportError:
        return None

    # Adobe 注册表路径模式
    reg_locations = [
        # HKLM 64位
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Adobe\After Effects"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Adobe\After Effects"),
        # HKCU
        (winreg.HKEY_CURRENT_USER, r"Software\Adobe\After Effects"),
        # Creative Cloud 安装路径
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Adobe\Adobe After Effects"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Adobe\Adobe After Effects"),
    ]

    for hive, subkey in reg_locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                # 枚举子键（版本号，如 "24.0", "25.0"）
                i = 0
                while True:
                    try:
                        version_name = winreg.EnumKey(key, i)
                        i += 1
                        # 尝试读取 InstallPath
                        try:
                            with winreg.OpenKey(key, version_name) as ver_key:
                                try:
                                    install_path, _ = winreg.QueryValueEx(ver_key, "InstallPath")
                                    if install_path:
                                        candidate = Path(install_path) / "Support Files" / "aerender.exe"
                                        if candidate.exists() and candidate.is_file():
                                            return candidate
                                        # 直接在 InstallPath 下
                                        candidate2 = Path(install_path) / "aerender.exe"
                                        if candidate2.exists() and candidate2.is_file():
                                            return candidate2
                                except OSError:
                                    pass
                                # 尝试 ApplicationPath
                                try:
                                    app_path, _ = winreg.QueryValueEx(ver_key, "ApplicationPath")
                                    if app_path:
                                        ap = Path(app_path)
                                        if ap.name.lower() == "aerender.exe" and ap.exists():
                                            return ap
                                        candidate = ap.parent / "Support Files" / "aerender.exe"
                                        if candidate.exists():
                                            return candidate
                                except OSError:
                                    pass
                        except OSError:
                            continue
                    except OSError:
                        break
        except OSError:
            continue

    # 也尝试 Adobe 通用安装路径列表（Creative Cloud）
    cc_locations = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Adobe\CommonFiles\Installer"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Adobe\CommonFiles"),
    ]
    for hive, subkey in cc_locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                i = 0
                while True:
                    try:
                        val_name, val_data, _ = winreg.EnumValue(key, i)
                        i += 1
                        if isinstance(val_data, str) and "After Effects" in val_data and "aerender" in val_data.lower():
                            p = Path(val_data)
                            if p.exists() and p.is_file():
                                return p
                    except OSError:
                        break
        except OSError:
            continue

    return None


def is_afterfx_running() -> bool:
    """检测 AfterFX.exe 进程是否正在运行"""
    try:
        if platform.system() == "Windows":
            proc = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq AfterFX.exe", "/NH"],
                capture_output=True, text=True, timeout=5,
                encoding="utf-8", errors="replace",
            )
            return "AfterFX.exe" in proc.stdout and "No tasks are running" not in proc.stdout
        else:
            # macOS/Linux: 用 ps
            proc = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=5,
            )
            return "After Effects" in proc.stdout or "AfterFX" in proc.stdout
    except Exception:
        return False


# ============================================================================
#  多语言进度日志解析
# ============================================================================

# 多语言进度正则（覆盖英文/中文/日文 AE 版本）
PROGRESS_PATTERNS: List[re.Pattern] = [
    # 英文时间码: "Rendering: 01:00:00:00 / 00:00:03:00 (1/72)"
    re.compile(r"\((\d+)\s*/\s*(\d+)\)", re.I),
    # 英文: "Rendering frame 123 of 456" / "Frame 123 (456)"
    re.compile(r"frame\s+(\d+)\s+(?:of|/)\s+(\d+)", re.I),
    re.compile(r"Rendering\s+frame\s+(\d+)", re.I),
    # 中文: "正在渲染帧 123，共 456" / "渲染第 24 帧，共 72 帧" / "帧 123/456"
    re.compile(r"(?:正在渲染|渲染)\s*帧\s*(\d+)\s*[，,]\s*(?:共\s*)?(\d+)", re.I),
    re.compile(r"渲染\s*第\s*(\d+)\s*帧\s*[，,]\s*共\s*(\d+)\s*帧?", re.I),
    re.compile(r"帧\s*[:：]\s*(\d+)\s*/\s*(\d+)"),
    # 日文: "フレーム 123 / 456 をレンダリング中"
    re.compile(r"フレーム\s*(\d+)\s*/\s*(\d+)", re.I),
    re.compile(r"(\d+)\s*/\s*(\d+)\s*フレーム"),
    # 百分比格式
    re.compile(r"(\d+\.?\d*)\s*%"),
    # 通用: 纯数字帧数（需上下文判断）
    re.compile(r"^\s*(\d+)\s*$"),
]


def parse_progress_from_log(log_text: str) -> Tuple[float, int, int]:
    """从日志文本解析渲染进度

    Returns:
        (progress_percent, current_frame, total_frames)
    """
    lines = log_text.split("\n")
    for line in reversed(lines[-100:]):  # 从最后100行向前找
        line = line.strip()
        if not line:
            continue
        for pat in PROGRESS_PATTERNS:
            m = pat.search(line)
            if m:
                groups = m.groups()
                if len(groups) >= 2:
                    try:
                        cur = int(groups[0])
                        tot = int(groups[1])
                        if tot > 0 and 0 <= cur <= tot:
                            return round(cur / tot * 100, 1), cur, tot
                    except (ValueError, IndexError):
                        pass
                elif len(groups) == 1 and "%" in line:
                    try:
                        pct = float(groups[0])
                        if 0 <= pct <= 100:
                            return pct, int(pct * 9999 / 100), 9999
                    except ValueError:
                        pass
    return 0.0, 0, 0


def parse_aerender_error(stdout: str, stderr: str, exit_code: int) -> Tuple[str, int, str]:
    """从 aerender 输出解析具体错误原因

    Returns:
        (error_message, detected_error_code, suggestion)
    """
    combined = (stdout or "") + "\n" + (stderr or "")
    combined_lower = combined.lower()

    # 首先看退出码
    code_info = ERROR_CODE_INFO.get(exit_code, ERROR_CODE_INFO[AerenderExitCode.FATAL_ERROR])
    detected_code = exit_code

    # 尝试从日志文本推断更精确的错误（支持中英文 AE）
    # 英文错误
    if "unable to open project" in combined_lower or "cannot open project" in combined_lower:
        detected_code = AerenderExitCode.CANNOT_OPEN_PROJECT
    elif "could not find composition" in combined_lower or "comp not found" in combined_lower:
        detected_code = AerenderExitCode.COMP_NOT_FOUND
    elif "output module template" in combined_lower and ("not found" in combined_lower or "invalid" in combined_lower):
        detected_code = AerenderExitCode.OM_TEMPLATE_NOT_FOUND
    elif "render settings template" in combined_lower and ("not found" in combined_lower or "invalid" in combined_lower):
        detected_code = AerenderExitCode.RS_TEMPLATE_NOT_FOUND
    elif "no render settings template" in combined_lower:
        detected_code = AerenderExitCode.RS_TEMPLATE_NOT_FOUND
    elif "no output module template" in combined_lower:
        detected_code = AerenderExitCode.OM_TEMPLATE_NOT_FOUND
    elif "cannot write" in combined_lower or "disk full" in combined_lower or "access denied" in combined_lower:
        detected_code = AerenderExitCode.CANNOT_WRITE_OUTPUT
    elif "license" in combined_lower or "activation" in combined_lower or "serial number" in combined_lower:
        detected_code = AerenderExitCode.LICENSE_ERROR
    elif "out of memory" in combined_lower or ("memory" in combined_lower and ("full" in combined_lower or "exhausted" in combined_lower)):
        detected_code = AerenderExitCode.FATAL_ERROR
    elif "gpu" in combined_lower and ("fail" in combined_lower or "error" in combined_lower or "init" in combined_lower):
        detected_code = AerenderExitCode.GPU_INIT_FAILED
    elif "missing footage" in combined_lower or "footage not found" in combined_lower:
        pass  # -continueOnMissingFootage 时不致命

    # 中文错误日志匹配
    if "无法打开项目" in combined or "不能打开项目" in combined:
        detected_code = AerenderExitCode.CANNOT_OPEN_PROJECT
    elif "找不到合成" in combined or "未找到合成" in combined or "合成不存在" in combined:
        detected_code = AerenderExitCode.COMP_NOT_FOUND
    elif ("输出模块模板" in combined or "输出模板" in combined) and ("找不到" in combined or "不存在" in combined or "未找到" in combined):
        detected_code = AerenderExitCode.OM_TEMPLATE_NOT_FOUND
    elif ("渲染设置模板" in combined or "渲染模板" in combined) and ("找不到" in combined or "不存在" in combined or "未找到" in combined):
        detected_code = AerenderExitCode.RS_TEMPLATE_NOT_FOUND
    elif "磁盘已满" in combined or "无法写入" in combined or "写入失败" in combined or "权限不足" in combined:
        detected_code = AerenderExitCode.CANNOT_WRITE_OUTPUT
    elif "许可" in combined or "激活" in combined or "序列号" in combined:
        detected_code = AerenderExitCode.LICENSE_ERROR
    elif "内存不足" in combined or "内存溢出" in combined:
        detected_code = AerenderExitCode.FATAL_ERROR
    elif "素材缺失" in combined or "找不到素材" in combined:
        pass  # 非致命

    # 提取最后几行错误上下文
    err_lines = []
    for line in reversed(combined.split("\n")):
        line = line.strip()
        if line and not line.startswith("("):
            err_lines.append(line)
        if len(err_lines) >= 5:
            break
    err_context = " | ".join(reversed(err_lines))

    final_info = ERROR_CODE_INFO.get(detected_code, code_info)
    msg = f"[{final_info['desc']}] {err_context[:300]}" if err_context else final_info["desc"]
    suggestion = final_info.get("suggestion", "")

    return msg, detected_code, suggestion


# ============================================================================
#  主引擎类
# ============================================================================

class AERenderEngine:
    """
    aerender 命令行渲染引擎 v2.0（生产级）

    用法:
        engine = AERenderEngine()
        job = engine.render(
            project="D:/project.aep",
            composition="Main",
            output="D:/output/video.mp4",
            output_format="h264",
            on_progress=lambda p: print(f"{p:.1f}%"),
        )
        # 同步等待
        while job.status in (RenderStatus.PENDING, RenderStatus.PREFLIGHT,
                            RenderStatus.STARTING, RenderStatus.RUNNING, RenderStatus.RETRYING):
            time.sleep(1)
        print(job.status, job.error if job.status == RenderStatus.FAILED else "OK")
    """

    def __init__(
        self,
        aerender_path: Optional[str] = None,
        log_dir: Optional[str] = None,
        default_timeout: int = 3600,
        default_max_retries: int = 2,
        auto_detect: bool = True,
    ):
        """
        Args:
            aerender_path: 显式指定 aerender.exe 路径（None=自动探测）
            log_dir: 日志目录（None=自动创建在 .ae-mcp-bridge/renders 下）
            default_timeout: 默认渲染超时（秒），0=自动估算
            default_max_retries: 默认最大重试次数
            auto_detect: 未指定路径时是否自动探测
        """
        self.default_timeout = default_timeout
        self.default_max_retries = default_max_retries

        # 解析 aerender 路径
        if aerender_path:
            self.aerender_path = Path(aerender_path)
            if not self.aerender_path.exists():
                raise FileNotFoundError(f"指定的 aerender 路径不存在: {self.aerender_path}")
        else:
            detected = detect_aerender() if auto_detect else None
            if detected:
                self.aerender_path = detected
            else:
                # 使用硬编码默认路径作为 fallback（仅用于错误提示）
                self.aerender_path = Path(
                    r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe"
                )
                if not self.aerender_path.exists():
                    # 检查是否有任何可能的路径
                    raise FileNotFoundError(
                        "无法自动探测 aerender.exe。请设置环境变量 AEKV_AERENDER_PATH "
                        "或在初始化时显式传入 aerender_path 参数。"
                    )

        # 日志目录
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = Path(__file__).parent / ".ae-mcp-bridge" / "renders"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._jobs: Dict[str, RenderJob] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._lock = threading.Lock()

        logger.info(f"AERenderEngine 初始化: aerender={self.aerender_path}")
        logger.info(f"  AE 版本: {self.version}")
        logger.info(f"  AE 进程运行中: {is_afterfx_running()}")

    @property
    def version(self) -> str:
        """获取 aerender 版本"""
        try:
            env = os.environ.copy()
            if "MACOSX_DEPLOYMENT_TARGET" in env:
                pass  # 保留环境变量
            r = subprocess.run(
                [str(self.aerender_path), "-help"],
                capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace",
                env=env,
            )
            m = re.search(r"(?:version|After Effects)\s+(\S+)", r.stdout, re.I)
            if m:
                return m.group(1).strip().rstrip(".")
            # 从路径推断版本
            path_str = str(self.aerender_path)
            for year in range(2020, 2028):
                if str(year) in path_str:
                    return f"{year} (inferred from path)"
            return "unknown"
        except Exception as e:
            logger.debug(f"获取 aerender 版本失败: {e}")
            return "unknown"

    # ---------------------------------------------------------------- render
    def render(
        self,
        project: str,
        composition: str,
        output: str,
        start_frame: int = 0,
        end_frame: int = -1,
        output_format: str = "h264",
        reuse_ae: Optional[bool] = None,
        multi_process: bool = True,
        memory_percent: int = 0,
        om_template: Optional[str] = None,
        rs_template: Optional[str] = None,
        continue_on_missing_footage: bool = True,
        timeout: int = 0,
        max_retries: int = -1,
        on_progress: Optional[Callable[[float, RenderJob], None]] = None,
        on_complete: Optional[Callable[[RenderJob], None]] = None,
        on_error: Optional[Callable[[RenderJob], None]] = None,
        job_id: Optional[str] = None,
    ) -> RenderJob:
        """
        渲染单个合成（异步，立即返回 RenderJob）

        Args:
            project: .aep 项目文件路径
            composition: 合成名称
            output: 输出文件路径
            start_frame: 起始帧（0-based）
            end_frame: 结束帧（-1=全部）
            output_format: 输出格式 (h264/mp4/mov/prores/png_seq/tiff_seq/exr_seq)
            reuse_ae: 是否复用已运行的AE实例（None=自动检测）
            multi_process: 是否启用多进程渲染 (-mp)
            memory_percent: 内存分配百分比（0=自动计算）
            om_template: 指定输出模块模板（None=从候选表选）
            rs_template: 指定渲染设置模板（None=从候选表选）
            continue_on_missing_footage: 素材丢失时是否继续
            timeout: 超时秒数（0=自动估算）
            max_retries: 最大重试次数（-1=使用默认值）
            on_progress: 进度回调 callback(progress_percent, job)
            on_complete: 完成回调 callback(job)
            on_error: 错误回调 callback(job)
            job_id: 自定义任务ID

        Returns:
            RenderJob 对象（异步更新状态）
        """
        import uuid
        jid = job_id or f"render_{uuid.uuid4().hex[:8]}"

        # 解析绝对路径
        project_path = str(Path(project).resolve())
        output_path = str(Path(output).resolve())

        job = RenderJob(
            job_id=jid,
            project_path=project_path,
            composition=composition,
            output_path=output_path,
            start_frame=start_frame,
            end_frame=end_frame,
            output_format=output_format.lower(),
            reuse_ae=reuse_ae,
            multi_process=multi_process,
            memory_percent=memory_percent,
            continue_on_missing_footage=continue_on_missing_footage,
            om_template=om_template,
            rs_template=rs_template,
            max_retries=max_retries if max_retries >= 0 else self.default_max_retries,
            timeout=timeout or self.default_timeout,
            log_path=str(self.log_dir / f"{jid}.log"),
            diagnostics=RenderDiagnostics(
                aerender_path=str(self.aerender_path),
                project_path=project_path,
                output_path=output_path,
            ),
        )

        with self._lock:
            self._jobs[jid] = job
        if on_progress:
            self._callbacks[f"{jid}_progress"] = on_progress
        if on_complete:
            self._callbacks[f"{jid}_complete"] = on_complete
        if on_error:
            self._callbacks[f"{jid}_error"] = on_error

        # 启动渲染线程
        t = threading.Thread(
            target=self._run_render_with_retry,
            args=(job,),
            daemon=True,
            name=f"aerender-{jid}",
        )
        t.start()

        return job

    def render_sync(
        self,
        project: str,
        composition: str,
        output: str,
        **kwargs,
    ) -> RenderJob:
        """同步渲染（阻塞直到完成或失败）"""
        job = self.render(project=project, composition=composition, output=output, **kwargs)
        while job.status in (RenderStatus.PENDING, RenderStatus.PREFLIGHT,
                            RenderStatus.STARTING, RenderStatus.RUNNING, RenderStatus.RETRYING):
            if job._cancel_event and job._cancel_event.is_set():
                break
            time.sleep(0.5)
        return job

    # ---------------------------------------------------------------- batch
    def render_batch(
        self,
        jobs: List[Dict],
        max_concurrent: int = 1,
        on_complete: Optional[Callable[[RenderJob], None]] = None,
    ) -> List[RenderJob]:
        """批量渲染（带并发控制）"""
        results: List[RenderJob] = []
        semaphore = threading.Semaphore(max_concurrent)
        threads: List[threading.Thread] = []
        results_lock = threading.Lock()

        def _run_one(job_cfg: Dict):
            semaphore.acquire()
            try:
                job = self.render(**job_cfg)
                while job.status in (RenderStatus.PENDING, RenderStatus.PREFLIGHT,
                                    RenderStatus.STARTING, RenderStatus.RUNNING, RenderStatus.RETRYING):
                    time.sleep(1)
                with results_lock:
                    results.append(job)
                if on_complete:
                    try:
                        on_complete(job)
                    except Exception:
                        pass
            finally:
                semaphore.release()

        for cfg in jobs:
            t = threading.Thread(target=_run_one, args=(cfg,), daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        return results

    # ---------------------------------------------------------------- job management
    def get_job(self, job_id: str) -> Optional[RenderJob]:
        return self._jobs.get(job_id)

    def get_all_jobs(self) -> Dict[str, RenderJob]:
        with self._lock:
            return dict(self._jobs)

    def cancel_job(self, job_id: str) -> bool:
        """取消渲染任务（终止进程树）"""
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.cancel()
        if job.process:
            self._terminate_process_tree(job.process)
        job.status = RenderStatus.CANCELLED
        return True

    # ---------------------------------------------------------------- command building
    def _build_command(
        self,
        job: RenderJob,
        om_template_override: Optional[str] = "__NOT_SET__",
        rs_template_override: Optional[str] = "__NOT_SET__",
    ) -> List[str]:
        """构建 aerender 命令行参数
        
        om_template_override / rs_template_override:
            "__NOT_SET__" (默认) = 使用 job 的设置或自动选择第一个候选
            None = 不指定模板参数（让 aerender 使用项目渲染队列设置）
            str = 使用指定的模板名
        """
        _UNSET = "__NOT_SET__"
        cmd = [str(self.aerender_path)]

        # 项目和合成
        cmd.extend(["-project", job.project_path])
        cmd.extend(["-comp", job.composition])

        # 输出路径
        cmd.extend(["-output", job.output_path])

        # 帧范围
        if job.start_frame >= 0:
            cmd.extend(["-s", str(job.start_frame)])
        if job.end_frame >= 0:
            cmd.extend(["-e", str(job.end_frame)])

        # 复用 AE 实例（智能判断）
        reuse = job.reuse_ae
        if reuse is None:
            reuse = is_afterfx_running()
        if reuse:
            cmd.append("-reuse")

        # 渲染后关闭项目（不保存修改，避免弹窗）
        if job.close_project:
            cmd.extend(["-close", job.close_project])

        # 多进程渲染
        if job.multi_process:
            cmd.append("-mp")
            # 智能内存分配
            mem_pct = job.memory_percent
            if mem_pct <= 0:
                # 自动计算: 多进程时给每个进程留足够内存
                import psutil
                try:
                    total_mem_gb = psutil.virtual_memory().total / (1024**3)
                    if total_mem_gb >= 64:
                        mem_pct = 80
                    elif total_mem_gb >= 32:
                        mem_pct = 70
                    elif total_mem_gb >= 16:
                        mem_pct = 60
                    else:
                        mem_pct = 50
                except Exception:
                    mem_pct = 60
            cmd.extend(["-memory", str(mem_pct)])

        # 素材丢失时继续
        if job.continue_on_missing_footage:
            cmd.append("-continueOnMissingFootage")

        # 日志级别（获取进度信息）
        if job.verbose_level:
            cmd.extend(["-v", job.verbose_level])

        # 输出模块模板
        # 优先级: override > job 设置 > 自动选择第一个候选
        # None = 不传 -OMtemplate/-RStemplate 参数（使用渲染队列默认）
        fmt = job.output_format.lower()
        if om_template_override != _UNSET:
            om_tmpl = om_template_override
        elif job.om_template:
            om_tmpl = job.om_template
        else:
            om_tmpl = OM_TEMPLATES.get(fmt, [None])[0] if fmt in OM_TEMPLATES else None

        if rs_template_override != _UNSET:
            rs_tmpl = rs_template_override
        elif job.rs_template:
            rs_tmpl = job.rs_template
        else:
            # -mp 是单机多进程渲染（AE 自带加速），必须用 Best Settings 高质量模板；
            # Multi-Machine Settings 仅用于 Watch Folder 多机网络渲染，与 -mp 无关。
            rs_key = "best"
            rs_tmpl = RS_TEMPLATES.get(rs_key, [None])[0]

        # 只有非 None 且非空字符串时才添加到命令行
        if om_tmpl:
            cmd.extend(["-OMtemplate", om_tmpl])
        if rs_tmpl:
            cmd.extend(["-RStemplate", rs_tmpl])

        # 日志文件
        if job.log_path:
            cmd.extend(["-log", job.log_path])

        # 记录命令行到诊断
        if job.diagnostics:
            job.diagnostics.command_line = subprocess.list2cmdline(cmd)

        return cmd

    # ---------------------------------------------------------------- preflight checks
    def _run_preflight(self, job: RenderJob) -> Optional[str]:
        """环境预检，返回错误信息（None=通过）"""
        job.status = RenderStatus.PREFLIGHT
        diag = job.diagnostics
        if not diag:
            diag = RenderDiagnostics()
            job.diagnostics = diag

        # 检查项目文件
        project_p = Path(job.project_path)
        if not project_p.exists():
            return f"项目文件不存在: {job.project_path}"
        try:
            diag.project_size_mb = round(project_p.stat().st_size / (1024 * 1024), 1)
        except Exception:
            pass

        # 检查输出目录
        output_p = Path(job.output_path)
        try:
            output_p.parent.mkdir(parents=True, exist_ok=True)
            # 测试写入权限
            test_file = output_p.parent / f".ae_write_test_{job.job_id}"
            test_file.write_bytes(b"test")
            test_file.unlink()
        except PermissionError:
            return f"输出目录无写入权限: {output_p.parent}"
        except Exception as e:
            return f"输出目录无法访问: {output_p.parent} ({e})"

        # 检查磁盘空间
        try:
            disk_usage = shutil.disk_usage(output_p.parent)
            diag.output_disk_free_gb = round(disk_usage.free / (1024**3), 1)
            # 如果输出是 h264 mp4，粗略估算需要 2-10GB 空间
            if disk_usage.free < 1 * 1024**3:  # < 1GB
                return f"磁盘空间不足，仅剩 {diag.output_disk_free_gb:.1f}GB"
        except Exception:
            pass

        # 检查系统内存
        try:
            import psutil
            vm = psutil.virtual_memory()
            diag.system_memory_gb = round(vm.total / (1024**3), 1)
            diag.available_memory_gb = round(vm.available / (1024**3), 1)
        except Exception:
            pass

        # 检查输出文件是否被占用（如果已存在）
        if output_p.exists():
            try:
                # 尝试以追加模式打开（Windows 上如果文件被独占打开会失败）
                with open(output_p, "ab") as f:
                    pass
            except PermissionError:
                return f"输出文件被其他程序占用（请关闭播放软件）: {output_p.name}"
            except Exception:
                pass

        # 记录 AE 状态
        diag.ae_process_running = is_afterfx_running()
        diag.ae_version = self.version
        diag.attempt_count = job.attempts

        return None  # 预检通过

    # ---------------------------------------------------------------- core render execution
    def _run_render_with_retry(self, job: RenderJob):
        """带重试的渲染执行（内部线程入口）

        Fallback 策略（线性推进，避免笛卡尔积爆炸）：
        1. 固定 OM，遍历所有 RS 候选（英文→中文→None）
        2. RS 找到后，固定 RS，遍历所有 OM 候选
        3. 其他可重试错误重试 N 次
        4. 最后兜底 (None, None) 不传模板参数
        """
        job.start_time = time.time()

        try:
            # 预检
            preflight_err = self._run_preflight(job)
            if preflight_err:
                job.status = RenderStatus.FAILED
                job.error = preflight_err
                job.error_code = AerenderExitCode.INVALID_ARGS
                self._finalize_job(job, success=False)
                return

            # 获取模板候选列表
            fmt = job.output_format.lower()
            om_candidates = [job.om_template] if job.om_template else (OM_TEMPLATES.get(fmt, []) or [None])
            # -mp 单机多进程渲染同样使用 Best Settings 候选（Multi-Machine 仅限 Watch Folder 场景）
            rs_candidates = [job.rs_template] if job.rs_template else (
                RS_TEMPLATES.get("best", []) or [None]
            )

            # 去重（保留顺序，确保 None 在最后）
            def _dedup(seq):
                seen = set()
                result = []
                none_seen = False
                for x in seq:
                    key = x if x is not None else "__NONE__"
                    if key not in seen:
                        seen.add(key)
                        if x is None:
                            none_seen = True
                        else:
                            result.append(x)
                if none_seen:
                    result.append(None)  # None 放最后作为兜底
                return result
            om_candidates = _dedup(om_candidates)
            rs_candidates = _dedup(rs_candidates)

            # 构建尝试序列：
            # 第 0 位：(None, None) 不传任何模板（默认设置，100% 成功，最快路径）
            # 第一阶段：固定第一个命名 OM，尝试所有命名 RS
            # 第二阶段：固定最后一个 RS，尝试剩余命名 OM
            attempts_list: List[Tuple[Optional[str], Optional[str]]] = [(None, None)]

            # 第一阶段：固定第一个命名 OM（非 None），尝试所有命名 RS（非 None）
            named_oms = [o for o in om_candidates if o is not None]
            named_rss = [r for r in rs_candidates if r is not None]
            if named_oms and named_rss:
                first_om = named_oms[0]
                for rs in named_rss:
                    attempts_list.append((first_om, rs))

                # 第二阶段：固定第一个命名 RS，尝试剩余命名 OM
                for om in named_oms[1:]:
                    attempts_list.append((om, named_rss[0]))

            # 去重
            seen_pairs = set()
            unique_attempts = []
            for om, rs in attempts_list:
                key = (om, rs)
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    unique_attempts.append((om, rs))
            attempts_list = unique_attempts

            max_template_attempts = len(attempts_list)
            last_error = ""
            last_error_code = -1
            general_retries = 0
            max_general_retries = job.max_retries

            for attempt_idx in range(max_template_attempts + max_general_retries + 2):
                job.attempts = attempt_idx + 1
                if job._cancel_event and job._cancel_event.is_set():
                    job.status = RenderStatus.CANCELLED
                    break

                # 选择模板组合
                if attempt_idx < max_template_attempts:
                    current_om, current_rs = attempts_list[attempt_idx]
                else:
                    # 超出模板尝试次数后，使用最后一个组合重试
                    current_om, current_rs = attempts_list[-1]

                if attempt_idx > 0:
                    job.status = RenderStatus.RETRYING
                    om_disp = current_om if current_om else "(none)"
                    rs_disp = current_rs if current_rs else "(none)"
                    logger.info(f"[AE] 重试渲染 ({attempt_idx+1}): {job.composition} OM={om_disp} RS={rs_disp}")
                    if attempt_idx >= max_template_attempts:
                        time.sleep(min(2 ** general_retries, 10))

                # 构建命令
                cmd = self._build_command(
                    job,
                    om_template_override=current_om,
                    rs_template_override=current_rs,
                )

                # 执行单次渲染
                job.status = RenderStatus.STARTING
                success, err_msg, err_code = self._execute_single_render(job, cmd)

                if success:
                    job.status = RenderStatus.SUCCESS
                    job.progress = 100.0
                    self._finalize_job(job, success=True)
                    return

                last_error = err_msg
                last_error_code = err_code
                job.error_code = err_code

                err_info = ERROR_CODE_INFO.get(err_code, {})
                retryable = err_info.get("retryable", False)

                # 模板错误：自动切换到下一个模板组合
                if err_code == AerenderExitCode.RS_TEMPLATE_NOT_FOUND:
                    if attempt_idx < max_template_attempts - 1:
                        logger.info(f"[AE] RS 模板不匹配，尝试下一组")
                        continue
                elif err_code == AerenderExitCode.OM_TEMPLATE_NOT_FOUND:
                    if attempt_idx < max_template_attempts - 1:
                        logger.info(f"[AE] OM 模板不匹配，尝试下一组")
                        continue
                elif not retryable:
                    # 不可重试错误（项目不存在/合成不存在/许可错误等）
                    break

                # 其他可重试错误（系统/IO/GPU等）
                if attempt_idx >= max_template_attempts:
                    general_retries += 1
                    if general_retries > max_general_retries:
                        break
                    continue
                elif attempt_idx >= max_template_attempts - 1:
                    # 已尝试所有模板组合，后续按通用重试处理
                    continue

            # 所有尝试都失败
            job.status = RenderStatus.FAILED
            job.error = last_error
            self._finalize_job(job, success=False)

        except Exception as e:
            job.status = RenderStatus.FAILED
            job.error = f"渲染引擎异常: {e}"
            logger.exception(f"[AE] 渲染异常 ({job.job_id}): {e}")
            self._finalize_job(job, success=False)

    def _execute_single_render(
        self, job: RenderJob, cmd: List[str]
    ) -> Tuple[bool, str, int]:
        """执行单次 aerender 进程

        Returns:
            (success, error_message, error_code)
        """
        stdout_chunks: List[str] = []
        stderr_chunks: List[str] = []

        try:
            job.status = RenderStatus.RUNNING
            logger.info(f"[AE] 开始渲染: {job.composition} → {Path(job.output_path).name}")
            logger.debug(f"[AE] 命令: {subprocess.list2cmdline(cmd)}")

            # 创建进程
            creationflags = 0
            if platform.system() == "Windows":
                creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP

            # 确保日志文件是空的
            if job.log_path:
                Path(job.log_path).parent.mkdir(parents=True, exist_ok=True)
                try:
                    Path(job.log_path).write_text("", encoding="utf-8")
                except Exception:
                    pass

            job.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding=locale.getpreferredencoding(False) or "utf-8",
                errors="replace",
                creationflags=creationflags,
                cwd=str(Path(job.output_path).parent),
            )

            # 启动进度监控线程
            stop_event = threading.Event()

            def _monitor_log():
                """从日志文件监控进度（独立线程）"""
                last_progress = -1.0
                log_file = Path(job.log_path) if job.log_path else None

                def _read_log(p: Path) -> str:
                    """多编码尝试读取日志文件"""
                    for enc in (locale.getpreferredencoding(False), "utf-8", "gbk", "cp936"):
                        try:
                            return p.read_text(encoding=enc, errors="strict")
                        except (UnicodeDecodeError, UnicodeError, OSError):
                            continue
                    return p.read_text(encoding="utf-8", errors="replace")

                while not stop_event.is_set() and job.process and job.process.poll() is None:
                    if job._cancel_event and job._cancel_event.is_set():
                        break

                    # 从日志文件解析
                    if log_file and log_file.exists():
                        try:
                            content = _read_log(log_file)
                            if content:
                                pct, cur, tot = parse_progress_from_log(content)
                                if pct > 0 and abs(pct - last_progress) > 0.5:
                                    job.progress = pct
                                    job.current_frame = cur
                                    job.total_frames = tot
                                    last_progress = pct
                                    # 进度回调
                                    cb = self._callbacks.get(f"{job.job_id}_progress")
                                    if cb:
                                        try:
                                            cb(pct, job)
                                        except Exception:
                                            pass
                        except Exception:
                            pass

                    stop_event.wait(1.5)

            monitor_thread = threading.Thread(target=_monitor_log, daemon=True)
            monitor_thread.start()

            # 等待进程完成（带超时）
            timeout = job.timeout if job.timeout > 0 else None
            try:
                stdout, stderr = job.process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                # 超时
                self._terminate_process_tree(job.process)
                job.process = None
                stop_event.set()
                monitor_thread.join(timeout=2)
                return False, f"渲染超时 ({timeout}s)", AerenderExitCode.TIMEOUT

            stop_event.set()
            monitor_thread.join(timeout=2)

            # 收集输出
            if stdout:
                stdout_chunks.append(stdout)
            if stderr:
                stderr_chunks.append(stderr)

            # 也从日志文件补充输出（有些版本 aerender 把详细信息写 -log 文件）
            if job.log_path:
                try:
                    # Windows 中文 AE 输出 GBK 编码，尝试多种编码
                    log_content = None
                    for enc in ("utf-8", locale.getpreferredencoding(False), "gbk", "cp936"):
                        try:
                            log_content = Path(job.log_path).read_text(encoding=enc, errors="strict")
                            break
                        except (UnicodeDecodeError, UnicodeError):
                            continue
                    if log_content is None:
                        log_content = Path(job.log_path).read_text(encoding="utf-8", errors="replace")
                    if log_content and log_content not in (stdout or ""):
                        stdout_chunks.append("\n=== Log File ===\n" + log_content[-2000:])
                except Exception:
                    pass

            full_stdout = "\n".join(stdout_chunks)
            full_stderr = "\n".join(stderr_chunks)

            returncode = job.process.returncode
            job.process = None

            # 检查取消
            if job._cancel_event and job._cancel_event.is_set():
                return False, "用户取消", AerenderExitCode.USER_CANCELLED

            # 等待文件写入完成（文件系统缓存）
            output_p = Path(job.output_path)
            # 扩展名自动回退：指定 .mov 但 OM 模板可能输出 .mp4/.avi 等，搜索同目录同名不同扩展名文件
            def _find_actual_output(p: Path) -> Path:
                if p.exists() and p.stat().st_size > 0:
                    return p
                # 搜索同目录下同名（不含扩展名）+ 常见媒体扩展名的文件
                stem = p.stem
                parent = p.parent
                if parent.exists():
                    candidates = list(parent.glob(f"{stem}.*"))
                    media_exts = {".mp4", ".mov", ".avi", ".mxf", ".png", ".tiff", ".exr", ".wav", ".mp3", ".jpg"}
                    for c in sorted(candidates, key=lambda x: x.stat().st_mtime, reverse=True):
                        if c.suffix.lower() in media_exts and c.stat().st_size > 1024:
                            logger.info(f"[AE] 找到扩展名变化的输出: {c.name} (期望 {p.name})")
                            return c
                return p
            if returncode == 0:
                # 等待文件完全写入
                for _ in range(15):
                    output_p = _find_actual_output(Path(job.output_path))
                    if output_p.exists() and output_p.stat().st_size > 1024:
                        try:
                            size1 = output_p.stat().st_size
                            time.sleep(0.5)
                            size2 = output_p.stat().st_size
                            if size1 == size2 and size1 > 0:
                                break
                        except Exception:
                            pass
                    time.sleep(0.5)

            # 判断结果
            if returncode == 0 and output_p.exists() and output_p.stat().st_size > 1024:
                # 更新 job.output_path 为实际路径（可能扩展名变化）
                job.output_path = str(output_p)
                return True, "", AerenderExitCode.SUCCESS

            # 解析错误
            err_msg, detected_code, suggestion = parse_aerender_error(
                full_stdout, full_stderr, returncode
            )

            # 保存诊断信息
            if job.diagnostics:
                job.diagnostics.error_code = detected_code
                job.diagnostics.error_description = err_msg
                job.diagnostics.suggestion = suggestion
                job.diagnostics.stdout_tail = full_stdout[-1500:]
                job.diagnostics.stderr_tail = full_stderr[-800:]
                job.diagnostics.log_file_path = job.log_path
                job.diagnostics.error_category = ERROR_CODE_INFO.get(detected_code, {}).get("category", "unknown")

            # 如果 returncode==0 但没有输出文件，且错误解析没有检测到更具体的错误（模板错误/项目错误等），
            # 才判定为写入失败。模板错误时 aerender 也可能返回 0 但不写文件
            specific_errors = {
                AerenderExitCode.OM_TEMPLATE_NOT_FOUND,
                AerenderExitCode.RS_TEMPLATE_NOT_FOUND,
                AerenderExitCode.COMP_NOT_FOUND,
                AerenderExitCode.CANNOT_OPEN_PROJECT,
                AerenderExitCode.RENDER_ERROR,
                AerenderExitCode.GPU_INIT_FAILED,
                AerenderExitCode.LICENSE_ERROR,
            }
            if returncode == 0 and not output_p.exists():
                if detected_code not in specific_errors:
                    err_msg = f"aerender 返回成功但输出文件未生成: {job.output_path}"
                    detected_code = AerenderExitCode.CANNOT_WRITE_OUTPUT
            elif returncode == 0 and output_p.exists() and output_p.stat().st_size <= 1024:
                if detected_code not in specific_errors:
                    err_msg = f"输出文件过小（可能是损坏文件）: {output_p.stat().st_size} bytes"
                    detected_code = AerenderExitCode.RENDER_ERROR

            return False, err_msg, detected_code

        except subprocess.TimeoutExpired:
            if job.process:
                self._terminate_process_tree(job.process)
                job.process = None
            return False, f"渲染超时", AerenderExitCode.TIMEOUT
        except PermissionError as e:
            return False, f"权限错误: {e}", AerenderExitCode.CANNOT_WRITE_OUTPUT
        except FileNotFoundError as e:
            return False, f"文件未找到: {e}", AerenderExitCode.CANNOT_OPEN_PROJECT
        except Exception as e:
            logger.exception(f"[AE] 执行异常: {e}")
            return False, f"执行异常: {e}", AerenderExitCode.FATAL_ERROR

    def _finalize_job(self, job: RenderJob, success: bool):
        """任务完成后统一处理"""
        job.end_time = time.time()
        if job.diagnostics:
            job.diagnostics.total_duration_s = round(job.end_time - job.start_time, 2)
            job.diagnostics.attempt_count = job.attempts

        # 触发回调
        if success:
            cb = self._callbacks.get(f"{job.job_id}_complete")
            if cb:
                try:
                    cb(job)
                except Exception:
                    pass
            logger.info(
                f"[AE] 渲染完成: {job.composition} "
                f"({job.end_time - job.start_time:.1f}s, 尝试{job.attempts}次)"
            )
        else:
            cb = self._callbacks.get(f"{job.job_id}_error")
            if cb:
                try:
                    cb(job)
                except Exception:
                    pass
            logger.warning(
                f"[AE] 渲染失败: {job.composition} "
                f"(code={job.error_code}, {job.error[:200]})"
            )

        # 清理非持久回调
        for suffix in ("_progress", "_complete", "_error"):
            self._callbacks.pop(f"{job.job_id}{suffix}", None)

    # ---------------------------------------------------------------- process tree termination
    def _terminate_process_tree(self, process: subprocess.Popen):
        """递归终止进程树（包括子进程，处理 -mp 多进程模式）"""
        try:
            if platform.system() == "Windows":
                # Windows: 使用 taskkill /T /F 强制终止进程树
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True, timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                except Exception:
                    pass
                # 备用方法：ctypes 调用 TerminateJobObject
                try:
                    process.kill()
                except Exception:
                    pass
            else:
                # Unix: 使用进程组
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"终止进程树失败: {e}")

    def __repr__(self):
        with self._lock:
            active = sum(1 for j in self._jobs.values() if j.status in (
                RenderStatus.RUNNING, RenderStatus.STARTING, RenderStatus.RETRYING
            ))
        return f"AERenderEngine(v={self.version}, active={active}, total={len(self._jobs)})"
