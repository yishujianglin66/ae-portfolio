#!/usr/bin/env python3
"""
统一配置管理器 (B07/B2 修复)

所有 Python 模块通过 ConfigManager 读取配置，不再各自解析 JSON。
支持：
- 环境变量覆盖（AE_WORK_DIR 等）
- 相对路径自动解析（基于项目根目录）
- 目录自动创建
- CLI 接口供 Node.js 侧调用：python config_manager.py --get key

用法：
    from config.config_manager import ConfigManager
    cfg = ConfigManager()
    video_dir = cfg.get_directory("video_library")
    cookie_path = cfg.get_platform_cookie_path("douyin")
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# 项目根目录（config/ 的父目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config" / "media-config.json"


class ConfigManager:
    """统一配置管理器，所有模块共享单一配置源。"""

    def __init__(self, config_path: Path | None = None):
        self._config_path = config_path or _DEFAULT_CONFIG_PATH
        self._config: dict[str, Any] = {}
        self._load()

    def _load(self):
        """加载配置文件并解析相对路径。"""
        if not self._config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self._config_path}")

        with open(self._config_path, "r", encoding="utf-8") as f:
            self._config = json.load(f)

        # 应用环境变量覆盖
        self._apply_env_overrides()
        # 解析相对路径
        self._resolve_relative_paths()

    def _apply_env_overrides(self):
        """环境变量优先级高于配置文件。"""
        env_mappings = {
            "AE_WORK_DIR": ("directories", None),  # 覆盖所有目录的基础路径
            "AEK_VIDEO_LIBRARY": ("directories", "video_library"),
            "AEK_BGM_LIBRARY": ("directories", "bgm_library"),
            "AEK_AUDIO_LIBRARY": ("directories", "audio_library"),
            "AEK_IMAGE_LIBRARY": ("directories", "image_library"),
            "AEK_OUTPUT": ("directories", "output"),
            "AEK_DOWNLOAD_TEMP": ("directories", "download_temp"),
            "AEK_COOKIES_DIR": ("directories", "cookies"),
            "AEK_FFMPEG": ("tools", "ffmpeg"),
            "AEK_FFPROBE": ("tools", "ffprobe"),
            "AEK_YT_DLP": ("tools", "yt_dlp"),
        }

        for env_key, (section, field) in env_mappings.items():
            value = os.environ.get(env_key)
            if value is None:
                continue
            if field is None:
                # AE_WORK_DIR: 覆盖所有目录路径的前缀
                if section in self._config:
                    for dir_key in self._config[section]:
                        old_val = self._config[section][dir_key]
                        if isinstance(old_val, str) and ("D:/AE-Work" in old_val or "D:\\AE-Work" in old_val):
                            # 替换 D:/AE-Work 前缀
                            self._config[section][dir_key] = old_val.replace(
                                "D:/AE-Work", value
                            ).replace("D:\\AE-Work", value)
            else:
                if section not in self._config:
                    self._config[section] = {}
                self._config[section][field] = value

    def _resolve_relative_paths(self):
        """将 ./ 开头的相对路径解析为基于项目根目录的绝对路径。"""
        directories = self._config.get("directories", {})
        for key, value in directories.items():
            if isinstance(value, str) and (value.startswith("./") or value.startswith(".\\")):
                directories[key] = str(_PROJECT_ROOT / value[2:])

        # 解析平台 cookie_path
        platforms = self._config.get("platforms", {})
        for platform_key, platform_cfg in platforms.items():
            if isinstance(platform_cfg, dict) and "cookie_path" in platform_cfg:
                cp = platform_cfg["cookie_path"]
                if isinstance(cp, str) and (cp.startswith("./") or cp.startswith(".\\")):
                    platform_cfg["cookie_path"] = str(_PROJECT_ROOT / cp[2:])

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    @property
    def project_root(self) -> Path:
        return _PROJECT_ROOT

    def get(self, key: str, default: Any = None) -> Any:
        """获取顶层配置项。"""
        return self._config.get(key, default)

    def get_directory(self, name: str) -> str:
        """获取目录路径，支持环境变量覆盖。"""
        directories = self._config.get("directories", {})
        return directories.get(name, "")

    def get_tool(self, name: str) -> str:
        """获取工具命令路径。"""
        tools = self._config.get("tools", {})
        return tools.get(name, name)

    def get_platform_cookie_path(self, platform: str) -> str | None:
        """获取指定平台的 Cookie 文件路径。"""
        platforms = self._config.get("platforms", {})
        platform_cfg = platforms.get(platform, {})
        return platform_cfg.get("cookie_path")

    def get_platform_config(self, platform: str) -> dict[str, Any]:
        """获取指定平台的完整配置。"""
        return self._config.get("platforms", {}).get(platform, {})

    def ensure_directories(self):
        """确保所有配置的目录存在。"""
        for dir_path in self._config.get("directories", {}).values():
            if isinstance(dir_path, str) and dir_path:
                os.makedirs(dir_path, exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        """返回完整配置字典的副本。"""
        return json.loads(json.dumps(self._config))

    # ------------------------------------------------------------------
    # 软件路径配置（software_sdk 集成）
    # ------------------------------------------------------------------

    # 常见软件安装路径（自动检测用）
    _SOFTWARE_PATHS: dict[str, list] = {
        "blender": [
            r"D:\Blender\Blender 5.1.0\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
        ],
        "silhouette": [
            r"C:\Program Files\BorisFX\Silhouette 2026.0\Silhouette.exe",
            r"C:\Program Files\BorisFX\Silhouette\Silhouette.exe",
        ],
        "topaz": [
            r"C:\Program Files\Topaz Labs LLC\Topaz Video AI\topazcli.exe",
            r"C:\Program Files\Topaz Labs\Topaz Video AI\topazcli.exe",
        ],
        "davinci": [
            r"D:\DaVinci Resolve\Resolve.exe",
            r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
        ],
        "photoshop": [
            r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
            r"C:\Program Files\Adobe\Adobe Photoshop 2025\Photoshop.exe",
        ],
        "premiere": [
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
        ],
        "media_encoder": [
            r"C:\Program Files\Adobe\Adobe Media Encoder 2024\Adobe Media Encoder.exe",
            r"C:\Program Files\Adobe\Adobe Media Encoder 2025\Adobe Media Encoder.exe",
        ],
    }

    def get_software_path(self, software: str) -> str | None:
        """获取软件可执行文件路径。

        优先级：配置文件 > 环境变量 > 自动检测

        Args:
            software: 软件名称 (blender/silhouette/topaz/davinci/photoshop/premiere/media_encoder)

        Returns:
            软件路径，未找到返回 None
        """
        # 1. 环境变量
        env_key = f"AEK_{software.upper()}_PATH"
        env_path = os.environ.get(env_key)
        if env_path and os.path.isfile(env_path):
            return env_path

        # 2. 配置文件 tools 段
        tool_path = self.get_tool(software)
        if tool_path and tool_path != software and os.path.isfile(tool_path):
            return tool_path

        # 3. 自动检测
        candidates = self._SOFTWARE_PATHS.get(software, [])
        for path in candidates:
            if os.path.isfile(path):
                return path

        return None

    def detect_installed_software(self) -> dict[str, str]:
        """自动检测已安装的软件。

        Returns:
            软件名称 -> 路径 字典
        """
        found: dict[str, str] = {}
        for software in self._SOFTWARE_PATHS:
            path = self.get_software_path(software)
            if path:
                found[software] = path
        return found

    # ------------------------------------------------------------------
    # CLI 接口（供 Node.js 侧调用）
    # ------------------------------------------------------------------

    @classmethod
    def cli_main(cls):
        """CLI 入口：python config_manager.py --get key"""
        import argparse
        parser = argparse.ArgumentParser(description="统一配置管理器")
        parser.add_argument("--get", type=str, help="获取配置项 (如 directories.video_library)")
        parser.add_argument("--list", action="store_true", help="列出所有配置")
        parser.add_argument("--ensure-dirs", action="store_true", help="创建所有目录")
        args = parser.parse_args()

        cfg = cls()

        if args.list:
            print(json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2))
        elif args.get:
            keys = args.get.split(".")
            value = cfg._config
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                else:
                    value = None
                    break
            if value is not None:
                print(value)
            else:
                print(f"配置项未找到: {args.get}", file=sys.stderr)
                sys.exit(1)
        elif args.ensure_dirs:
            cfg.ensure_directories()
            print("所有目录已确保存在")
        else:
            parser.print_help()


if __name__ == "__main__":
    ConfigManager.cli_main()

# ======================================================================
# 函数式配置 API（支持多环境配置、环境变量覆盖、凭证安全管理）
# ======================================================================

import copy

_CONFIG_DIR = _PROJECT_ROOT / "config"
_ENV_FILE = _PROJECT_ROOT / ".env"

_DEFAULT_CONFIG = {
    "version": "1.0.0",
    "environment": "development",
    "directories": {
        # 资源库主目录（统一指向 D:/AE-Work/resources/）
        "resources_root": "D:/AE-Work/resources",
        # 资源库子目录（与 puppet-automation/src/config/settings.py 同步）
        "video_library": "D:/AE-Work/resources/video",
        "audio_library": "D:/AE-Work/resources/audio",
        "image_library": "D:/AE-Work/resources/effects",
        "bgm_library": "D:/AE-Work/resources/audio/bgm",
        "sound_effects": "D:/AE-Work/resources/audio/sfx",
        "fonts_dir": "D:/AE-Work/resources/fonts",
        "luts_dir": "D:/AE-Work/resources/luts",
        "psd_dir": "D:/AE-Work/resources/psd",
        "effects_dir": "D:/AE-Work/resources/effects",
        "davinci_dir": "D:/AE-Work/resources/davinci",
        "models_dir": "D:/AE-Work/resources/models",
        "premiere_dir": "D:/AE-Work/resources/premiere",
        "tutorials_dir": "D:/AE-Work/resources/tutorials",
        "docs_dir": "D:/AE-Work/resources/docs",
        "references_dir": "D:/AE-Work/resources/references",
        "presets_dir": "D:/AE-Work/resources/presets",
        "software_dir": "D:/AE-Work/resources/software",
        "ae_projects_resource": "D:/AE-Work/resources/projects",
        # 工作流目录（非资源库，保留独立路径）
        "download_temp": "D:/AE-Work/临时下载",
        "output": "D:/AE-Work/成品库",
        "logs": "D:/AE-Work/日志与报告",
        "cookies": "D:/AE-Work/cookies",
        "vector_index": "D:/AE-Work/向量索引",
        "temp_frames": "D:/AE-Work/临时帧",
        "ae_projects": "D:/AE-Work/projects",
    },
    "tools": {
        "yt_dlp": "yt-dlp",
        # 修复 P0-3：ffmpeg 不在系统 PATH 中，原 "ffmpeg" 命令名无法解析，
        # 统一改为实际安装路径（与 settings.py / core/config.py 一致）
        "ffmpeg": "C:/ffmpeg/bin/ffmpeg.exe",
        "ffprobe": "C:/ffmpeg/bin/ffprobe.exe",
        "python": "python",
    },
    "download": {
        "max_concurrent": 3,
        "timeout": 300,
        "retries": 3,
        "audio_only_formats": ["m4a", "mp3", "wav"],
        "video_formats": ["mp4", "mov", "webm"],
    },
    "audio": {
        "default_sample_rate": 44100,
        "default_bitrate": "192k",
        "analysis": {
            "tempo_window": 10,
            "beat_threshold": 0.5,
        },
    },
    "mcp_bridge": {
        "command_dir": "~/Documents/ae-mcp-bridge",
        "command_file": "command.json",
        "result_file": "result.json",
        "log_file": "bridge.log",
        "poll_interval_ms": 1000,
        "command_timeout": 30,
        "signature_enabled": True,
        "signature_algorithm": "HMAC-SHA256",
    },
    "platforms": {
        "douyin": {
            "enabled": True,
            "cookie_env_key": "DOUYIN_COOKIE",
            "cookie_path_env_key": "DOUYIN_COOKIE_PATH",
            "download_mode": "watermark_free",
        },
        "bilibili": {
            "enabled": True,
            "prefer_high_quality": True,
            "cookie_env_key": "BILIBILI_COOKIE",
        },
        "youtube": {
            "enabled": True,
            "language": "zh-CN",
        },
        "tiktok": {
            "enabled": True,
        },
        "kuaishou": {
            "enabled": False,
        },
    },
    "security": {
        "command_signature": {
            "enabled": True,
            "secret_env_key": "MCP_BRIDGE_SECRET",
            "timestamp_tolerance": 300,
        },
    },
    "auto_import": {
        "enabled": True,
        "target_composition": "Main Comp",
        "after_import_action": "center_and_fit",
    },
}

_cached_config: dict[str, Any] | None = None
_cached_env: dict[str, str] | None = None


def _load_dotenv() -> dict[str, str]:
    """加载 .env 文件中的环境变量。"""
    global _cached_env
    if _cached_env is not None:
        return _cached_env

    env_vars: dict[str, str] = {}

    if _ENV_FILE.exists():
        with open(_ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        env_vars[key] = value
                        os.environ[key] = value

    _cached_env = env_vars
    return env_vars


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """深度合并两个字典，override 覆盖 base。"""
    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _find_config_path(config: dict[str, Any], target_key: str) -> list | None:
    """在配置字典中递归查找目标键的路径。

    Args:
        config: 配置字典
        target_key: 目标键名（小写）

    Returns:
        键路径列表，如果未找到返回 None
    """
    for key in config:
        if key.lower() == target_key:
            return [key]
        if isinstance(config[key], dict):
            sub_path = _find_config_path(config[key], target_key)
            if sub_path:
                return [key] + sub_path
    return None


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """使用环境变量覆盖配置值。

    支持的环境变量格式：
    - AEK_VIDEO_LIBRARY -> 递归查找 video_library 键
    - AEK_BGM_LIBRARY -> 递归查找 bgm_library 键
    - AEK_MCP_BRIDGE_COMMAND_DIR -> 递归查找 mcp_bridge 下的 command_dir
    - AEK_ENVIRONMENT -> 顶层 environment 键

    优先级：精确匹配（直接键名）> 递归查找
    """
    prefix = "AEK_"
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        path_key = env_key[len(prefix):].lower()

        found = False

        if path_key in config:
            _set_nested_value(config, [path_key], env_value)
            found = True
        else:
            parts = path_key.split("_")
            for i in range(1, len(parts)):
                first = "_".join(parts[:i])
                rest = "_".join(parts[i:])
                path = _find_config_path(config, first)
                if path:
                    sub_config = config
                    for p in path:
                        sub_config = sub_config[p]
                    if isinstance(sub_config, dict):
                        sub_path = _find_config_path(sub_config, rest)
                        if sub_path:
                            full_path = path + sub_path
                            _set_nested_value(config, full_path, env_value)
                            found = True
                            break

            if not found:
                path = _find_config_path(config, path_key)
                if path:
                    _set_nested_value(config, path, env_value)
                    found = True

    return config


def _set_nested_value(d: dict[str, Any], keys: list, value: str) -> None:
    """递归设置嵌套字典值。"""
    current = d
    for i, key in enumerate(keys[:-1]):
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    last_key = keys[-1]

    if isinstance(current.get(last_key), bool):
        current[last_key] = value.lower() in ("true", "1", "yes")
    elif isinstance(current.get(last_key), int):
        try:
            current[last_key] = int(value)
        except ValueError:
            current[last_key] = value
    elif isinstance(current.get(last_key), float):
        try:
            current[last_key] = float(value)
        except ValueError:
            current[last_key] = value
    elif isinstance(current.get(last_key), list):
        current[last_key] = [v.strip() for v in value.split(",")]
    else:
        current[last_key] = value


def _load_config_file(env: str) -> dict[str, Any]:
    """加载指定环境的配置文件。"""
    config_path = _CONFIG_DIR / f"config.{env}.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_config(environment: str | None = None) -> dict[str, Any]:
    """获取配置。

    优先级（从高到低）：
    1. 环境变量覆盖（AEK_ 前缀）
    2. 环境特定配置文件（config.{env}.json）
    3. 默认配置

    Args:
        environment: 环境名称（development/test/production），
                     默认为 AEK_ENVIRONMENT 或 "development"

    Returns:
        合并后的配置字典
    """
    global _cached_config
    if _cached_config is not None and environment is None:
        return copy.deepcopy(_cached_config)

    _load_dotenv()

    if environment is None:
        environment = os.environ.get("AEK_ENVIRONMENT", "development")

    config = copy.deepcopy(_DEFAULT_CONFIG)
    config["environment"] = environment

    env_config = _load_config_file(environment)
    if env_config:
        config = _deep_merge(config, env_config)

    config = _apply_env_overrides(config)

    if environment is None:
        _cached_config = copy.deepcopy(config)

    return config


def get_secret(key: str, default: str | None = None) -> str | None:
    """从环境变量获取敏感凭证。

    Args:
        key: 环境变量名
        default: 默认值

    Returns:
        凭证值或默认值
    """
    _load_dotenv()
    return os.environ.get(key, default)


def get_path(config_key: str) -> Path:
    """获取配置中的路径并转换为 Path 对象。

    Args:
        config_key: 配置键，格式为 "directories.video_library"

    Returns:
        Path 对象
    """
    config = get_config()
    parts = config_key.split(".")
    value = config
    for part in parts:
        value = value.get(part, {})
    return Path(str(value)).expanduser()


def reload_config() -> None:
    """重新加载配置（修改环境变量或配置文件后调用）。"""
    global _cached_config, _cached_env
    _cached_config = None
    _cached_env = None
