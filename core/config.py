#!/usr/bin/env python3
"""
配置管理系统核心 - ConfigManager v1.0

设计原则（基于 12-Factor App 配置原则）：
1. 配置与代码分离：配置存储在环境变量或配置文件中，不嵌入代码
2. 分层覆盖：默认配置 < 文件配置 < 环境变量 < 命令行参数
3. 类型安全：配置值经过类型验证和转换
4. 热重载：支持运行时动态更新配置
5. 可验证：配置加载后自动进行完整性校验
6. 版本化：配置变更可追踪

配置来源优先级（从低到高）：
1. 默认配置（代码中定义）
2. config.json（项目根目录）
3. ~/.ae-knowledge-vault/config.json（用户目录）
4. 环境变量（AEKV_* 前缀）
5. 命令行参数

架构参考：
- 12-Factor App Configuration
- Spring Cloud Config
- HashiCorp Vault（安全配置）
"""
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class ConfigSource:
    """配置来源"""
    name: str
    priority: int
    data: Dict[str, Any] = field(default_factory=dict)


class ConfigValidator:
    """配置验证器"""
    def validate(self, config: Dict[str, Any]) -> List[str]:
        """验证配置并返回错误列表"""
        errors: List[str] = []

        # 验证输出目录
        output_dir = config.get("output", {}).get("default_dir")
        if output_dir:
            if not os.path.isabs(output_dir):
                config["output"]["default_dir"] = os.path.abspath(output_dir)

        # 验证 AE 路径
        ae_path = config.get("ae", {}).get("install_path")
        if ae_path and not os.path.exists(ae_path):
            errors.append(f"AE 安装路径不存在: {ae_path}")

        # 验证 Silhouette 路径
        sil_path = config.get("silhouette", {}).get("install_path")
        if sil_path and not os.path.exists(sil_path):
            errors.append(f"Silhouette 安装路径不存在: {sil_path}")

        # 验证端口范围
        port = config.get("server", {}).get("port", 8080)
        if not (1024 <= port <= 65535):
            errors.append("server.port 必须在 1024-65535 范围内")

        # 验证并发数
        concurrency = config.get("pipeline", {}).get("max_concurrent_tasks", 5)
        if concurrency < 1:
            errors.append("pipeline.max_concurrent_tasks 必须 >= 1")

        return errors


class ConfigManager:
    """配置管理器 - 支持分层覆盖和类型安全"""

    def __init__(self):
        self._logger = logging.getLogger(f"{__name__}.ConfigManager")
        self._sources: List[ConfigSource] = []
        self._config: Dict[str, Any] = {}
        self._validator = ConfigValidator()
        self._last_reload_time = 0.0
        self._config_files: List[str] = []

        # 默认配置
        self._register_default_config()

    # -------------------------------------------------------------------------
    # 默认配置
    # -------------------------------------------------------------------------

    def _register_default_config(self) -> None:
        """注册默认配置"""
        default = {
            # 输出配置
            "output": {
                "default_dir": "./output",
                "tmp_dir": "./temp",
                "max_file_size_mb": 1000,
                "keep_temporary_files": False,
            },
            # AE 配置
            "ae": {
                "install_path": r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe",
                "script_dir": "./scripts",
                "max_retries": 3,
                "retry_delay_ms": 2000,
                "timeout_ms": 60000,
            },
            # Silhouette 配置
            "silhouette": {
                "install_path": r"C:\Program Files\BorisFX\Silhouette 2026.0\Silhouette.exe",
                "python_path": r"C:\Program Files\BorisFX\Silhouette 2026.0\resources\python\python.exe",
                "output_dir": "./silhouette_output",
                "max_retries": 3,
                "retry_delay_ms": 3000,
                "timeout_ms": 120000,
            },
            # Topaz Video AI 配置
            "topaz": {
                "install_path": r"D:\top\Topaz Video AI Pro\Topaz Video AI BETA.exe",
                "model": "amqs",                # 增强模型：amqs / proteus / iris 等
                "output_dir": "./topaz_output",
                "max_retries": 2,
                "retry_delay_ms": 3000,
                "timeout_ms": 300000,
            },
            # RunwayML 配置
            "runway": {
                "api_key": "",                   # AEKV_RUNWAY_API_KEY
                "api_base": "https://api.runwayml.com/v1",
                "max_retries": 3,
                "retry_delay_ms": 5000,
                "timeout_ms": 180000,
            },
            # Pika 配置
            "pika": {
                "api_key": "",                   # AEKV_PIKA_API_KEY
                "api_base": "https://api.pika.art/v1",
                "max_retries": 3,
                "retry_delay_ms": 5000,
                "timeout_ms": 180000,
            },
            # Blender 配置
            "blender": {
                "install_path": r"D:\Blender\Blender 5.1.0\blender.exe",  # 修复 P0-2：原 Blender 4.2 路径不存在，改为实际安装路径（与 settings.py 的 blender_path 一致）
                "python_script_path": "./scripts/blender",
                "output_dir": "./blender_output",
                "max_retries": 2,
                "retry_delay_ms": 3000,
                "timeout_ms": 600000,
            },
            # FFmpeg 配置
            # 修复 P0-3：原 D:\ffmpeg\bin\ffmpeg.exe 不存在，统一改为 C:\ffmpeg\bin\ffmpeg.exe
            "ffmpeg": {
                "bin_path": r"C:\ffmpeg\bin\ffmpeg.exe",
                "max_retries": 2,
                "retry_delay_ms": 2000,
                "timeout_ms": 300000,
            },
            # DaVinci Resolve 配置（P0-4 补全，与 settings.py 的 davinci_path 一致）
            "davinci": {
                "install_path": r"D:\DaVinci Resolve",
                "scripting_modules_dir": r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
            },
            # Adobe Media Encoder 配置（P0-5 补全，与 settings.py 的 media_encoder_path 一致）
            "media_encoder": {
                "install_path": r"D:\Me\Adobe Media Encoder 2025\Adobe Media Encoder.exe",
            },
            # 服务器配置
            "server": {
                "host": "localhost",
                "port": 8080,
                "debug": False,
                "cors_enabled": True,
            },
            # 工作流配置
            "pipeline": {
                "max_concurrent_tasks": 5,
                "default_frame_rate": 30,
                "default_resolution": [1920, 1080],
                "auto_save_interval_minutes": 5,
                "enable_silhouette_fallback": True,
            },
            # 日志配置
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "file_path": "./logs/ae_knowledge_vault.log",
                "max_size_mb": 100,
                "backup_count": 5,
            },
            # 素材库配置
            "media_library": {
                "video_dir": "D:/AE-Work/resources/video",
                "audio_dir": "D:/AE-Work/resources/audio",
                "image_dir": "D:/AE-Work/resources/effects",
                "projects_dir": "D:/AE-Work/resources/projects",
                "psd_dir": "D:/AE-Work/resources/psd",
                "fonts_dir": "D:/AE-Work/resources/fonts",
                "luts_dir": "D:/AE-Work/resources/luts",
                "davinci_dir": "D:/AE-Work/resources/davinci",
                # 扩展资源目录（百度网盘整理后新增）
                "models_dir": "D:/AE-Work/resources/models",          # 3D 模型
                "tutorials_dir": "D:/AE-Work/resources/tutorials",    # 教程视频
                "docs_dir": "D:/AE-Work/resources/docs",              # 教程文档
                "references_dir": "D:/AE-Work/resources/references",  # 素材网站
                "premiere_dir": "D:/AE-Work/resources/premiere",      # PR 插件与 LUTS
                "presets_dir": "D:/AE-Work/resources/presets",        # 预设资源
                "software_dir": "D:/AE-Work/resources/software",      # 软件安装包
                "cache_enabled": True,
                "cache_size_gb": 10,
            },
            # MCP Bridge 配置
            "mcp_bridge": {
                "bridge_dir": "./ae-mcp-bridge",
                "timeout_seconds": 300,
                "poll_interval_seconds": 1.0,
                "signature_enabled": False,
                "secret": "",
            },
            # 模型配置 — 对接 LLM 网关 (core/llm_gateway.py)
            "model": {
                "nlu_model": "local",          # local=纯正则, llm=LLM增强, hybrid=混合
                "max_tokens": 4096,
                "temperature": 0.7,
                "api_key": "",                 # AEKV_LLM_API_KEY 或 OPENAI_API_KEY
                "base_url": "https://duckmiss.site/v1",  # 第三方中转站端点
                "default_model": "claude-sonnet-4-6",  # 中转站默认模型
                "timeout_seconds": 60,
                "max_retries": 3,
                "enable_compression": True,    # Caveman token 压缩
                "enable_fallback": True,       # Provider 降级
                "fallback_providers": [        # 降级 Provider 列表（火山方舟）
                    {
                        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                        "api_key": "",
                        "default_model": "deepseek-v4-pro-260425",
                    }
                ],
                # 任务→模型路由表
                "routing": {
                    "intent_classification": "claude-haiku-4-5-20251001",
                    "scene_description": "claude-sonnet-4-6",
                    "effect_planning": "claude-opus-4-8",
                    "quality_review": "claude-sonnet-4-6",
                    "feedback_analysis": "claude-haiku-4-5-20251001",
                    "general": "claude-sonnet-4-6",
                },
            },
            # 豆包模型配置 — 对接火山方舟(ARK)平台
            "doubao": {
                "enabled": False,              # 是否启用豆包模型
                "api_key": "",                 # DOUBAO_API_KEY 环境变量
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",  # 火山方舟端点
                "platform": "ark",             # open_platform 或 ark
                "endpoint_id": "",             # ARK接入点ID（平台为ark时必填）
                "default_model": "deepseek-v4-pro-260425",  # 默认模型
                "timeout_seconds": 60,
                "max_retries": 3,
                # 文本对话模型 - PRO级
                "text_pro_models": [
                    "deepseek-v4-pro-260425",
                    "doubao-seed-2-1-pro-260628",
                    "doubao-pro-256k-240428",
                    "deepseek-v3-2-260122",
                    "deepseek-r1-250722",
                    "qwen2-5-72b-250922",
                    "qwen3-32b-260328",
                    "glm-5-2-260617",
                    "kimi-k2-260328",
                ],
                # 文本对话模型 - FLASH级
                "text_flash_models": [
                    "deepseek-v4-flash-260425",
                    "doubao-seed-2-1-turbo-260628",
                    "doubao-seed-1-6-flash-250722",
                ],
                # 文本对话模型 - LITE级
                "text_lite_models": [
                    "doubao-lite-128k-240428",
                    "doubao-seed-2-0-lite-251228",
                    "doubao-seed-2-0-mini-251228",
                ],
                # 深度思考模型
                "thinking_models": [
                    "doubao-1-5-thinking-pro-241128",
                    "doubao-seed-1-6-thinking-250722",
                ],
                # 垂直领域模型
                "specialized_models": {
                    "code": "doubao-seed-code-251228",
                    "translation": "doubao-seed-translation-250722",
                    "character": "doubao-seed-character-251228",
                    "evolving": "doubao-seed-evolving-251228",
                },
            },
        
            # 视觉模型配置 — 火山方舟(ARK)视觉模型
            "vision": {
                "enabled": False,              # 是否启用视觉模型
                "api_key": "",                 # DOUBAO_API_KEY 环境变量（复用ARK API Key）
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                # 视觉理解模型
                "vl_model_pro": "doubao-vision-pro-32k-240428",
                "vl_model_lite": "doubao-vision-lite-32k-240428",
                "vl_model_seed": "doubao-seed-1-6-vision-250722",
                # 图像生成模型
                "image_model_pro": "doubao-seedream-5-0-pro-260628",
                "image_model_standard": "doubao-seedream-5-0-260128",
                "image_model_lite": "doubao-seedream-4-5-251128",
                # 视频生成模型
                "video_model_pro": "doubao-seedance-2-0-260128",
                "video_model_fast": "doubao-seedance-2-0-fast-260128",
                # 3D生成模型
                "3d_model": "doubao-seed3d-2-0-251228",
                # Embedding模型
                "embedding_model": "doubao-embedding-240428",
                "embedding_model_large": "doubao-embedding-large-240428",
                "embedding_model_vision": "doubao-embedding-vision-240428",
                "timeout_seconds": 120,
                "max_retries": 2,
            },
            # 记忆系统配置 — 对接 core/memory_store.py
            "memory": {
                "enabled": True,
                "db_path": "",                 # 空=默认 ~/.ae-knowledge-vault/memory.db
                "min_confidence": 0.3,         # 经验推荐最低置信度
            },
        }
        self._sources.append(ConfigSource("default", 1, default))

    # -------------------------------------------------------------------------
    # 加载配置
    # -------------------------------------------------------------------------

    def load_config(self, config_files: List[str] = None) -> None:
        """加载配置（文件 + 环境变量）"""
        self._config_files = config_files or []

        # 加载默认配置
        self._merge_source(self._sources[0])

        # 加载配置文件
        self._load_config_files()

        # 加载环境变量
        self._load_env_vars()

        # 验证配置
        errors = self._validator.validate(self._config)
        if errors:
            self._logger.warning(f"配置验证发现 {len(errors)} 个问题:")
            for error in errors:
                self._logger.warning(f"  - {error}")

        self._last_reload_time = time.time()
        self._logger.info("配置加载完成")

    def _load_config_files(self) -> None:
        """加载配置文件"""
        default_paths = [
            "./config.json",
            os.path.expanduser("~/.ae-knowledge-vault/config.json"),
        ]

        all_paths = default_paths + self._config_files

        for idx, path in enumerate(all_paths, start=2):
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._sources.append(ConfigSource(path, idx, data))
                    self._merge_source(self._sources[-1])
                    self._logger.info(f"加载配置文件: {path}")
                except Exception as e:
                    self._logger.error(f"加载配置文件失败 {path}: {e}")

    def _load_env_vars(self) -> None:
        """加载环境变量配置"""
        env_config: Dict[str, Any] = {}

        for key, value in os.environ.items():
            if key.startswith("AEKV_"):
                # 转换 AEKV_OUTPUT_DIR -> output.dir
                path = key[5:].lower().replace("_", ".")
                parts = path.split(".")

                # 逐层创建嵌套字典
                current = env_config
                for i, part in enumerate(parts):
                    if i == len(parts) - 1:
                        current[part] = self._convert_value(value)
                    else:
                        if part not in current:
                            current[part] = {}
                        current = current[part]

        if env_config:
            self._sources.append(ConfigSource("environment", 99, env_config))
            self._merge_source(self._sources[-1])
            self._logger.info(f"加载 {len(env_config)} 个环境变量配置")

    def _convert_value(self, value: str) -> Any:
        """将字符串值转换为正确类型"""
        # 布尔值
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False

        # 整数
        try:
            return int(value)
        except ValueError:
            pass

        # 浮点数
        try:
            return float(value)
        except ValueError:
            pass

        # 列表
        if value.startswith("[") and value.endswith("]"):
            try:
                return json.loads(value)
            except ValueError:
                pass

        # 字典
        if value.startswith("{") and value.endswith("}"):
            try:
                return json.loads(value)
            except ValueError:
                pass

        return value

    def _merge_source(self, source: ConfigSource) -> None:
        """合并配置来源到主配置"""
        self._config = self._deep_merge(self._config, source.data)

    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并两个字典"""
        result = base.copy()
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    # -------------------------------------------------------------------------
    # 配置访问 API
    # -------------------------------------------------------------------------

    def get(self, path: str, default: Any = None) -> Any:
        """通过点路径获取配置值"""
        parts = path.split(".")
        current = self._config

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default

        return current

    def get_str(self, path: str, default: str = "") -> str:
        """获取字符串配置"""
        value = self.get(path, default)
        return str(value)

    def get_int(self, path: str, default: int = 0) -> int:
        """获取整数配置"""
        value = self.get(path, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_float(self, path: str, default: float = 0.0) -> float:
        """获取浮点数配置"""
        value = self.get(path, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def get_bool(self, path: str, default: bool = False) -> bool:
        """获取布尔配置"""
        value = self.get(path, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)

    def get_list(self, path: str, default: List[Any] = None) -> List[Any]:
        """获取列表配置"""
        value = self.get(path, default or [])
        if isinstance(value, list):
            return value
        return default or []

    def get_dict(self, path: str, default: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取字典配置"""
        value = self.get(path, default or {})
        if isinstance(value, dict):
            return value
        return default or {}

    # -------------------------------------------------------------------------
    # 配置更新 API
    # -------------------------------------------------------------------------

    def set(self, path: str, value: Any) -> None:
        """设置配置值"""
        parts = path.split(".")
        current = self._config

        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current[part] = value
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]

        self._logger.debug(f"配置更新: {path} = {value}")

    def update(self, data: Dict[str, Any]) -> None:
        """批量更新配置"""
        self._config = self._deep_merge(self._config, data)
        self._logger.debug(f"配置批量更新: {len(data)} 项")

    # -------------------------------------------------------------------------
    # 配置管理
    # -------------------------------------------------------------------------

    def reload(self) -> None:
        """热重载配置"""
        self._logger.info("热重载配置...")
        self._config = {}
        self._sources = []
        self._register_default_config()
        self.load_config(self._config_files)

    def save(self, path: str = "./config.json") -> None:
        """保存当前配置到文件"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)
        self._logger.info(f"配置已保存到: {path}")

    def validate(self) -> List[str]:
        """验证当前配置"""
        return self._validator.validate(self._config)

    # -------------------------------------------------------------------------
    # 配置检查
    # -------------------------------------------------------------------------

    def check_dependencies(self) -> Dict[str, bool]:
        """检查依赖项是否可用"""
        dependencies = {
            "ae_installed": os.path.exists(self.get_str("ae.install_path")),
            "silhouette_installed": os.path.exists(self.get_str("silhouette.install_path")),
            "topaz_installed": os.path.exists(self.get_str("topaz.install_path")),
            "blender_installed": os.path.exists(self.get_str("blender.install_path")),
            "ffmpeg_available": os.path.exists(self.get_str("ffmpeg.bin_path")),
            "runway_configured": bool(self.get_str("runway.api_key")),
            "pika_configured": bool(self.get_str("pika.api_key")),
            "output_dir_writable": self._is_writable(self.get_str("output.default_dir")),
            "tmp_dir_writable": self._is_writable(self.get_str("output.tmp_dir")),
            "bridge_dir_writable": self._is_writable(self.get_str("mcp_bridge.bridge_dir")),
        }
        return dependencies

    def _is_writable(self, path: str) -> bool:
        """检查路径是否可写"""
        try:
            os.makedirs(path, exist_ok=True)
            test_file = os.path.join(path, ".test_writable")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # 配置信息
    # -------------------------------------------------------------------------

    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要（不含敏感信息）"""
        summary = {
            "sources": [s.name for s in self._sources],
            "last_reload_time": self._last_reload_time,
            "output": {
                "default_dir": self.get_str("output.default_dir"),
                "tmp_dir": self.get_str("output.tmp_dir"),
            },
            "ae": {
                "install_path": self.get_str("ae.install_path"),
                "max_retries": self.get_int("ae.max_retries"),
            },
            "silhouette": {
                "install_path": self.get_str("silhouette.install_path"),
                "enable_fallback": self.get_bool("pipeline.enable_silhouette_fallback"),
            },
            "server": {
                "host": self.get_str("server.host"),
                "port": self.get_int("server.port"),
                "debug": self.get_bool("server.debug"),
            },
            "pipeline": {
                "max_concurrent_tasks": self.get_int("pipeline.max_concurrent_tasks"),
                "default_frame_rate": self.get_int("pipeline.default_frame_rate"),
            },
            "model": {
                "nlu_model": self.get_str("model.nlu_model"),
                "base_url": self.get_str("model.base_url"),
                "default_model": self.get_str("model.default_model"),
                "enable_compression": self.get_bool("model.enable_compression"),
                "enable_fallback": self.get_bool("model.enable_fallback"),
                "available": bool(self.get_str("model.base_url") and self.get_str("model.api_key")),
            },
            "memory": {
                "enabled": self.get_bool("memory.enabled"),
                "db_path": self.get_str("memory.db_path"),
                "min_confidence": self.get_float("memory.min_confidence"),
            },
        }
        return summary

    def get_full_config(self) -> Dict[str, Any]:
        """获取完整配置（注意：包含敏感信息如 API Key）"""
        return self._config.copy()


# -----------------------------------------------------------------------------
# 全局配置管理器实例
# -----------------------------------------------------------------------------

config_manager = ConfigManager()


# -----------------------------------------------------------------------------
# 便捷函数
# -----------------------------------------------------------------------------

def load_config(config_files: List[str] = None) -> None:
    config_manager.load_config(config_files)


def get_config(path: str, default: Any = None) -> Any:
    return config_manager.get(path, default)


def get_str(path: str, default: str = "") -> str:
    return config_manager.get_str(path, default)


def get_int(path: str, default: int = 0) -> int:
    return config_manager.get_int(path, default)


def get_float(path: str, default: float = 0.0) -> float:
    return config_manager.get_float(path, default)


def get_bool(path: str, default: bool = False) -> bool:
    return config_manager.get_bool(path, default)


def get_list(path: str, default: List[Any] = None) -> List[Any]:
    return config_manager.get_list(path, default)


def get_dict(path: str, default: Dict[str, Any] = None) -> Dict[str, Any]:
    return config_manager.get_dict(path, default)


def set_config(path: str, value: Any) -> None:
    config_manager.set(path, value)


def check_dependencies() -> Dict[str, bool]:
    return config_manager.check_dependencies()
