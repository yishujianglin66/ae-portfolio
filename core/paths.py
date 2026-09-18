# -*- coding: utf-8 -*-
"""统一路径解析层 — 所有绝对路径的单一权威源 (2026-08-14)

背景（路径配置化第一坎）：
    项目历史上把本机绝对路径（D:/AE-Work、C:/ffmpeg、Documents/ae-mcp-bridge 等）
    散落硬编码在 100+ 个模块里，换机器 / 换盘符即失效。本模块把它们收口到
    一处：业务代码不再写死路径，而是 `from core.paths import ffmpeg_bin`。

设计原则：
    1. 一个主变量 AE_WORK_DIR 决定"工作根目录"，绝大多数工作路径从它推导，
       换机器只需设一个环境变量即可整体迁移。
    2. 每个具体路径可被独立的 AEK_* 环境变量覆盖（优先级高于 AE_WORK_DIR 推导）。
    3. 默认值集中在本文件，且与历史硬编码值完全一致 —— 未设置任何环境变量时，
       行为与旧代码 100% 相同（向后兼容，零迁移风险）。
    4. 纯标准库、零依赖、函数式惰性求值（每次调用读环境变量，避免 import 时序
       早于 .env 加载导致的缓存陷阱）。不 import 任何项目模块，杜绝循环依赖。

环境变量约定（前缀 AEK_，与 config/config_manager.py、下载器 _get_env_or_default 兼容）：
    AE_WORK_DIR          工作根目录（默认 D:/AE-Work）—— 主变量
    AEK_FFMPEG           ffmpeg 可执行文件
    AEK_FFPROBE          ffprobe 可执行文件
    AEK_AE_EXE           After Effects 主程序
    AEK_AERENDER         aerender 可执行文件
    AEK_VIDEO_LIBRARY    视频素材库目录
    AEK_AUDIO_LIBRARY    音频素材库目录
    AEK_BGM_LIBRARY      BGM 目录
    AEK_RESOURCES_ROOT   资源库根目录
    AEK_OUTPUT_DIR       成品输出目录
    AEK_WORK_OUTPUT      工作输出目录 (D:/AE-Work/output)
    AEK_COOKIES_DIR      Cookie 目录
    AEK_MODELS_DIR       模型目录
    AEK_AE_BRIDGE_DIR    AE MCP Bridge 目录
    AEK_INSTALLED_FONTS  已安装字体清单文件

用法:
    from core.paths import ffmpeg_bin, video_library, work_root
    subprocess.run([ffmpeg_bin(), "-version"])
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# 项目根目录（core/ 的父目录），供相对路径推导
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env(name: str) -> str | None:
    """读取环境变量，空串视为未设置。"""
    v = os.environ.get(name)
    return v.strip() if isinstance(v, str) and v.strip() else None


def _env_or(name: str, default: str) -> str:
    return _env(name) or default


# ---------------------------------------------------------------------------
# 工作根目录（主变量）
# ---------------------------------------------------------------------------

def work_root() -> str:
    """工作根目录。AE_WORK_DIR 一键覆盖，未设置回退 D:/AE-Work。"""
    return _env_or("AE_WORK_DIR", r"D:\AE-Work")


def _work(subpath: str) -> str:
    """work_root() 下的子路径（用 os.path.join 保证盘符分隔符正确）。"""
    return os.path.join(work_root(), subpath)


# ---------------------------------------------------------------------------
# 工具（ffmpeg 等）
# ---------------------------------------------------------------------------

def ffmpeg_bin() -> str:
    """ffmpeg 可执行文件。项目硬约束 C:/ffmpeg/bin/ffmpeg.exe。"""
    return _env_or("AEK_FFMPEG", r"C:\ffmpeg\bin\ffmpeg.exe")


def ffprobe_bin() -> str:
    """ffprobe 可执行文件。"""
    return _env_or("AEK_FFPROBE", r"C:\ffmpeg\bin\ffprobe.exe")


# ---------------------------------------------------------------------------
# Adobe 软件路径
# ---------------------------------------------------------------------------

def ae_exe() -> str:
    """After Effects 主程序（AE 2025 完整版；AE 2026 目录是空壳）。"""
    return _env_or(
        "AEK_AE_EXE",
        r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe",
    )


def aerender_exe() -> str:
    """aerender 命令行渲染器（与 ae_exe 同目录）。"""
    return _env_or(
        "AEK_AERENDER",
        r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe",
    )


# ---------------------------------------------------------------------------
# 素材库目录
# ---------------------------------------------------------------------------

def resources_root() -> str:
    """资源库根目录。"""
    return _env_or("AEK_RESOURCES_ROOT", _work(r"resources"))


def video_library() -> str:
    """视频素材库目录。"""
    return _env_or("AEK_VIDEO_LIBRARY", _work(r"视频素材库"))


def audio_library() -> str:
    """音频素材库目录。"""
    return _env_or("AEK_AUDIO_LIBRARY", _work(r"音频素材库"))


def bgm_library() -> str:
    """BGM 目录。"""
    return _env_or("AEK_BGM_LIBRARY", _work(r"音频素材库\BGM"))


# ---------------------------------------------------------------------------
# 输出 / 缓存 / 其它工作目录
# ---------------------------------------------------------------------------

def output_dir() -> str:
    """成品输出目录。"""
    return _env_or("AEK_OUTPUT_DIR", _work(r"成品库"))


def work_output_dir() -> str:
    """工作输出目录（渲染中间产物，历史约定 D:/AE-Work/output）。"""
    return _env_or("AEK_WORK_OUTPUT", _work(r"output"))


def cookies_dir() -> str:
    """平台 Cookie 目录。"""
    return _env_or("AEK_COOKIES_DIR", _work(r"cookies"))


def models_dir() -> str:
    """模型目录。"""
    return _env_or("AEK_MODELS_DIR", _work(r"models"))


def installed_fonts_file() -> str:
    """已安装字体清单文件。"""
    return _env_or("AEK_INSTALLED_FONTS", _work(r"installed_fonts.txt"))


def self_evolution_dir() -> str:
    """自进化运行时数据目录（执行历史/经验知识，属运行时产物，移出代码仓库）。

    默认 <AE_WORK_DIR>/self_evolution（AEK_SELF_EVOLUTION_DIR 可覆盖）。
    历史位置 data/self_evolution 由 core.self_evolution_engine 做启动搬迁。
    """
    return _env_or("AEK_SELF_EVOLUTION_DIR", _work(r"self_evolution"))


# ---------------------------------------------------------------------------
# 环境变量读取公共函数（收敛下载器等模块里 4 份重复的 _get_env_or_default）
# ---------------------------------------------------------------------------

_LOADED_ENV_FILES: set = set()


def env_or_default(
    env_key: str,
    default: str,
    *,
    env_file: str | None = None,
    skip_keys: set | None = None,
) -> str:
    """从环境变量取配置，未设置时回退默认值（含 AE_WORK_DIR 前缀替换）。

    与下载器历史上各自实现的 _get_env_or_default 行为一致：
    1. 若给了 env_file，加载其中尚未存在于 os.environ 的键（幂等，每个文件只加载一次）
    2. env_key 已显式设置 → 原样返回
    3. 未设置 → AE_WORK_DIR 主变量存在时，把默认值里的 D:/AE-Work 前缀整体替换

    Args:
        env_key: 环境变量名（如 "AEK_VIDEO_LIBRARY"）
        default: 回退默认值
        env_file: 可选 .env 文件路径（如项目根/.env）
        skip_keys: 加载 .env 时跳过的键集合（douyin 用于跳过代理变量）
    """
    if env_file and env_file not in _LOADED_ENV_FILES:
        _LOADED_ENV_FILES.add(env_file)
        try:
            if os.path.isfile(env_file):
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and key not in os.environ and key not in (skip_keys or set()):
                            os.environ[key] = value
        except Exception:
            pass

    value = os.environ.get(env_key)
    if value:
        return value
    work_dir = os.environ.get("AE_WORK_DIR")
    if work_dir:
        default = default.replace("D:/AE-Work", work_dir).replace(r"D:\AE-Work", work_dir)
    return default


# ---------------------------------------------------------------------------
# MCP Bridge 目录
# ---------------------------------------------------------------------------

def ae_bridge_dir() -> str:
    """AE MCP Bridge 目录（历史约定 Documents/ae-mcp-bridge）。"""
    return _env_or(
        "AEK_AE_BRIDGE_DIR",
        r"C:\Users\Administrator\Documents\ae-mcp-bridge",
    )


def ps_bridge_dir() -> str:
    """Photoshop MCP Bridge 目录。"""
    return _env_or(
        "AEK_PS_BRIDGE_DIR",
        r"C:\Users\Administrator\Documents\ps-mcp-bridge",
    )


def au_bridge_dir() -> str:
    """Audition MCP Bridge 目录。"""
    return _env_or(
        "AEK_AU_BRIDGE_DIR",
        r"C:\Users\Administrator\Documents\au-mcp-bridge",
    )


def pr_bridge_dir() -> str:
    """Premiere MCP Bridge 目录（历史约定项目根/.premiere-mcp-bridge）。"""
    return _env_or(
        "AEK_PR_BRIDGE_DIR",
        str(PROJECT_ROOT / ".premiere-mcp-bridge"),
    )


# ---------------------------------------------------------------------------
# FFmpeg / ffprobe 版本检测（惰性缓存，供 FFmpeg 8.0 兼容性判断）
# ---------------------------------------------------------------------------

_FFMPEG_VERSION_CACHE: tuple | None = None
_FFPROBE_VERSION_CACHE: tuple | None = None


def _parse_ffmpeg_version(output: str) -> tuple:
    """从 ffmpeg -version 首行提取 (major, minor, patch)。"""
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("ffmpeg version") or line.startswith("ffmpeg v"):
            parts = line.split()
            for p in parts:
                segs = p.split(".")
                if len(segs) >= 2 and segs[0].isdigit():
                    return tuple(int(s) for s in segs[:3]) if len(segs) >= 3 else (int(segs[0]), int(segs[1]), 0)
    return (0, 0, 0)


def ffmpeg_version() -> tuple:
    """返回已安装 ffmpeg 的 (major, minor, patch)；未找到时返回 (0, 0, 0)。

    结果惰性缓存——ffmpeg 版本在单次运行中不会变化。
    用法:
        if ffmpeg_version() >= (8, 0, 0):
            ...  # FFmpeg 8.0+ 专属路径
    """
    global _FFMPEG_VERSION_CACHE
    if _FFMPEG_VERSION_CACHE is not None:
        return _FFMPEG_VERSION_CACHE
    try:
        import subprocess
        result = subprocess.run(
            [ffmpeg_bin(), "-version"],
            capture_output=True, text=True, timeout=5,
        )
        _FFMPEG_VERSION_CACHE = _parse_ffmpeg_version(result.stdout)
    except Exception:
        _FFMPEG_VERSION_CACHE = (0, 0, 0)
    return _FFMPEG_VERSION_CACHE


def ffprobe_version() -> tuple:
    """返回已安装 ffprobe 的 (major, minor, patch)；未找到时返回 (0, 0, 0)。"""
    global _FFPROBE_VERSION_CACHE
    if _FFPROBE_VERSION_CACHE is not None:
        return _FFPROBE_VERSION_CACHE
    try:
        import subprocess
        result = subprocess.run(
            [ffprobe_bin(), "-version"],
            capture_output=True, text=True, timeout=5,
        )
        _FFPROBE_VERSION_CACHE = _parse_ffmpeg_version(result.stdout)
    except Exception:
        _FFPROBE_VERSION_CACHE = (0, 0, 0)
    return _FFPROBE_VERSION_CACHE


def ffmpeg_version_str() -> str:
    """人类可读的 ffmpeg 版本字符串，如 '7.1.0' 或 'unknown'。"""
    v = ffmpeg_version()
    return ".".join(str(x) for x in v) if v != (0, 0, 0) else "unknown"


def ffmpeg_has_hwaccel(codec: str = "h264") -> bool:
    """检测 ffmpeg 是否编译了指定编解码器的硬件加速支持。

    用于运行时自动选择 nvenc/cuda 加速路径（RTX 4060 → h264_nvenc）。
    """
    try:
        import subprocess
        result = subprocess.run(
            [ffmpeg_bin(), "-hwaccels"],
            capture_output=True, text=True, timeout=5,
        )
        return "cuda" in result.stdout.lower() or "nvenc" in result.stdout.lower()
    except Exception:
        return False
