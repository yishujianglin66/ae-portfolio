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

# 路径类默认值收口到 core/paths.py（未设环境变量时返回值与历史硬编码相同，向后兼容）。
# 注意: core/paths.py 是零依赖模块, 此处 import 不会循环。
# 注意: media_library 各目录(如 D:/AE-Work/resources/video)与 core.paths.video_library()
#       (D:/AE-Work/视频素材库) 是历史上并存的两套目录约定, 值不同, 不做合并。
try:
    from core.paths import ae_exe as _paths_ae_exe, ffmpeg_bin as _paths_ffmpeg, resources_root as _paths_resources_root
    _DEFAULT_AE_INSTALL = _paths_ae_exe()
    _DEFAULT_FFMPEG_BIN = _paths_ffmpeg()
    _DEFAULT_RESOURCES_ROOT = _paths_resources_root()
except ImportError:  # core 模块被独立加载且项目根不在 sys.path 时兜底
    _DEFAULT_AE_INSTALL = r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"
    _DEFAULT_FFMPEG_BIN = r"C:\ffmpeg\bin\ffmpeg.exe"
    _DEFAULT_RESOURCES_ROOT = "D:/AE-Work/resources"


@dataclass
class ConfigSource:
    """配置来源"""
    name: str
    priority: int
    data: Dict[str, Any] = field(default_factory=dict)


class ConfigValidator:
    """配置验证器"""

    # 仅在生产环境视为 errors；非生产环境降级为 warnings 的项
    _NON_FATAL_KEYS = (
        "ae.install_path",
        "silhouette.install_path",
        "topaz.install_path",
        "blender.install_path",
        "ffmpeg.ffmpeg_path",
        "ffmpeg.ffprobe_path",
        "runway.install_path",
        "pika.install_path",
    )

    def __init__(self, strict: bool = True):
        self.strict = strict

    def validate(self, config: Dict[str, Any]):
        """验证配置并返回 (errors, warnings)"""
        errors: List[str] = []
        warnings: List[str] = []
        env = os.environ.get("AEK_ENVIRONMENT", "development").lower()
        is_production = env == "production" or self.strict

        def err_or_warn(msg: str, key: Optional[str] = None):
            """非致命项（key 在 _NON_FATAL_KEYS 中）在非生产环境降级为 warning。"""
            non_fatal = key in self._NON_FATAL_KEYS if key else False
            if is_production or not non_fatal:
                errors.append(msg)
            else:
                warnings.append(msg)

        # 验证输出目录
        output_dir = config.get("output", {}).get("default_dir")
        if output_dir:
            if not os.path.isabs(output_dir):
                config["output"]["default_dir"] = os.path.abspath(output_dir)

        # 新增：核心必填项非空校验
        output_dir = config.get("output", {}).get("default_dir")
        if not output_dir:
            errors.append("output.default_dir 不能为空，请配置输出根目录")
        else:
            output_dir = os.path.abspath(output_dir)
            config["output"]["default_dir"] = output_dir

        tmp_dir = config.get("output", {}).get("tmp_dir")
        if tmp_dir:
            config["output"]["tmp_dir"] = os.path.abspath(tmp_dir)

        media_video = config.get("media_library", {}).get("video_dir")
        if media_video:
            config["media_library"]["video_dir"] = os.path.abspath(media_video)
            if not os.path.isdir(config["media_library"]["video_dir"]):
                warnings.append(f"media_library.video_dir 目录不存在: {config['media_library']['video_dir']}")

        # 新增：当某 Provider 被配置了 base_url 但缺 api_key 时，warning
        for provider in config.get("model", {}).get("fallback_providers", []):
            provider_name = provider.get("name", "unknown")
            if provider.get("base_url") and not provider.get("api_key"):
                warnings.append(f"Provider[{provider_name}] 配置了 base_url 但 api_key 为空，该 Provider 实际不可用")

        # 验证 AE 路径
        ae_path = config.get("ae", {}).get("install_path")
        if ae_path and not os.path.exists(ae_path):
            err_or_warn(f"AE 安装路径不存在: {ae_path}", key="ae.install_path")

        # 验证 Silhouette 路径
        sil_path = config.get("silhouette", {}).get("install_path")
        if sil_path and not os.path.exists(sil_path):
            err_or_warn(f"Silhouette 安装路径不存在: {sil_path}", key="silhouette.install_path")

        # 验证端口范围
        port = config.get("server", {}).get("port", 8000)
        if not (1024 <= port <= 65535):
            errors.append("server.port 必须在 1024-65535 范围内")

        # 验证并发数
        concurrency = config.get("pipeline", {}).get("max_concurrent_tasks", 5)
        if concurrency < 1:
            errors.append("pipeline.max_concurrent_tasks 必须 >= 1")

        # 新增：H3 Provider 配置一致性校验
        h3 = config.get("minimax_h3", {})
        if h3:
            h3_url = h3.get("base_url", "")
            h3_key = h3.get("api_key", "")
            if h3_url and not h3_key:
                warnings.append("minimax_h3.base_url 已配置但 api_key 为空，H3 API 将无法调用")
            duration = h3.get("default_duration_sec", 10)
            if not (5 <= duration <= 15):
                errors.append(f"minimax_h3.default_duration_sec={duration} 超出官方支持范围 [5, 15]")
            resolution = h3.get("default_resolution", "768p").lower()
            if resolution not in ("768p", "2k", "1440p"):
                errors.append(f"minimax_h3.default_resolution={resolution!r} 非官方支持 (768p/2k/1440p)")
            fps = h3.get("default_fps", 24)
            if fps != 24:
                warnings.append(f"minimax_h3.default_fps={fps} 非官方固定 24FPS，H3 可能忽略此设置")
            poll = h3.get("max_poll_wait_sec", 600)
            if poll < 60:
                errors.append(f"minimax_h3.max_poll_wait_sec={poll} 过小，H3 15s 生成约需 3~8 分钟，建议 >= 600")
            download_dir = h3.get("download_dir")
            if download_dir:
                h3["download_dir"] = os.path.abspath(download_dir)
            cache_dir = h3.get("cache_dir")
            if cache_dir:
                h3["cache_dir"] = os.path.abspath(cache_dir)

        return errors, warnings


class ConfigManager:
    """配置管理器 - 支持分层覆盖和类型安全"""

    def __init__(self, config_files: List[str] = None, auto_load: bool = True):
        self._logger = logging.getLogger(f"{__name__}.ConfigManager")
        self._sources: List[ConfigSource] = []
        self._config: Dict[str, Any] = {}
        self._validator = ConfigValidator()
        self._last_reload_time = 0.0
        self._config_files: List[str] = []

        # 默认配置
        self._register_default_config()

        # 自动加载：合并默认配置 + 配置文件 + 环境变量
        if auto_load:
            try:
                self.load_config(config_files)
            except Exception as _e:
                self._logger.warning(f"[ConfigManager] 初始化自动加载失败（非strict模式降级）: {_e}")
                # 至少合并默认配置层，避免 _config 全空
                if self._sources:
                    self._merge_source(self._sources[0])
                # memory.db_path 兜底（不依赖 load_config 的修正逻辑）
                mem_cfg = self._config.setdefault("memory", {})
                if not mem_cfg.get("db_path"):
                    import os as _os
                    default_db = _os.path.expanduser("~/.ae-knowledge-vault/memory.db")
                    _os.makedirs(_os.path.dirname(default_db), exist_ok=True)
                    mem_cfg["db_path"] = default_db

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
                "install_path": _DEFAULT_AE_INSTALL,
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
            # MiniMax H3 全模态视频生成/编辑模型配置（2026-08-03 开源权重）
            "minimax_h3": {
                # 云端 API 入口（异步任务模式：创建任务→轮询→下载URL）
                "base_url": "https://api.minimaxi.com/v1",    # AEKV_LLM_MINIMAX_H3_BASE_URL
                "api_key": "",                                   # AEKV_LLM_MINIMAX_H3_API_KEY
                # 成本系数（按秒计费，单位：元/秒）
                "cost_per_sec_2k": 0.8,      # 2K(1440P) 官方原价 0.8元/秒
                "cost_per_sec_768p": 0.3,    # 768P 档位约 0.3元/秒
                # 生成参数默认值
                "default_resolution": "768p",  # "768p" 或 "2k"(1440p)，大批量默认 768p 降成本
                "default_duration_sec": 10,    # 5~15s，默认 10s 平衡成本/内容量
                "default_fps": 24,             # H3 固定 24FPS（官方规格）
                "default_aspect_ratio": "16:9", # 9:16 / 16:9 / 1:1 / 4:3 / 21:9
                # 输入素材上限（官方规格：9图 + 3视频 + 3音频 = 12份参考）
                "max_reference_images": 9,
                "max_reference_videos": 3,
                "max_reference_audios": 3,
                "max_prompt_chars": 7000,
                # 异步任务轮询参数
                "poll_interval_sec": 3.0,      # 轮询间隔 3 秒
                "max_poll_wait_sec": 600,      # 最长等 10 分钟（15s 生成通常 3~8 分钟）
                # 下载目录（与 security.py 沙箱白名单保持一致）
                "download_dir": "./output/h3_downloads",
                "cache_dir": "./data/h3_cache",
                # 本地部署（权重开源后预留）
                "local_deployment": {
                    "enabled": False,
                    "model_path": "",           # AEKV_LLM_MINIMAX_H3_LOCAL_MODEL_PATH
                    "device": "auto",           # auto/cuda/cpu，8GB VRAM 默认 auto 检测不可用会 fallback
                    "vram_8gb_mode": True,      # 8GB 用户笔记本默认开启低显存模式（--num_persistent_param_in_dit 0）
                },
                # 超时/重试
                "timeout_sec": 600,
                "max_retries": 2,
                "retry_delay_ms": 5000,
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
                "install_path": r"D:\Blender\Blender 5.1.0\blender.exe",
                "python_script_path": "./scripts/blender",
                "output_dir": "./blender_output",
                "max_retries": 2,
                "retry_delay_ms": 3000,
                "timeout_ms": 600000,
            },
            # FFmpeg 配置
            # 与 settings.py 的 ffmpeg_path 保持一致（项目硬约束：C:\ffmpeg\bin\ffmpeg.exe）
            "ffmpeg": {
                "bin_path": _DEFAULT_FFMPEG_BIN,
                "max_retries": 2,
                "retry_delay_ms": 2000,
                "timeout_ms": 300000,
            },
            # 服务器配置
            "server": {
                "host": "localhost",
                "port": 8000,
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
            # 默认值由 resources_root() 推导并以正斜杠输出(与历史字符串字节级一致,
            # 避免反斜杠影响下游 JSON 序列化/字符串匹配); AE_WORK_DIR 主变量可整体迁移。
            "media_library": {
                "video_dir": os.path.join(_DEFAULT_RESOURCES_ROOT, "video").replace("\\", "/"),
                "audio_dir": os.path.join(_DEFAULT_RESOURCES_ROOT, "audio").replace("\\", "/"),
                "image_dir": os.path.join(_DEFAULT_RESOURCES_ROOT, "effects").replace("\\", "/"),
                "projects_dir": os.path.join(_DEFAULT_RESOURCES_ROOT, "projects").replace("\\", "/"),
                "psd_dir": os.path.join(_DEFAULT_RESOURCES_ROOT, "psd").replace("\\", "/"),
                "fonts_dir": os.path.join(_DEFAULT_RESOURCES_ROOT, "fonts").replace("\\", "/"),
                "luts_dir": os.path.join(_DEFAULT_RESOURCES_ROOT, "luts").replace("\\", "/"),
                "davinci_dir": os.path.join(_DEFAULT_RESOURCES_ROOT, "davinci").replace("\\", "/"),
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
                "enable_local_fallback": True,   # 全局开关：允许 local:// 协议 Provider 参与链路
                "fallback_providers": [        # 降级 Provider 列表（火山方舟）
                    {
                        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                        "api_key": "",
                        "default_model": "deepseek-v4-pro-260425",
                    },
                    {
                        "name": "local_openvino",
                        "base_url": "local://openvino/qwen2-1.5b",
                        "api_key": "none",
                        "default_model": "qwen2-1.5b",
                        "enabled": False,
                        "backend": "openvino",
                        "ov_device": "GPU.0",
                        "ov_precision": "int8",
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
                # 全量 Provider 注册表（含本地 OpenVINO）
                "providers": [
                    {
                        "name": "primary",
                        "base_url": "https://duckmiss.site/v1",
                        "api_key": "",
                        "default_model": "claude-sonnet-4-6",
                    },
                    {
                        "name": "ark",
                        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                        "api_key": "",
                        "default_model": "deepseek-v4-pro-260425",
                    },
                    {
                        "name": "local_openvino",
                        "base_url": "local://openvino/qwen2-1.5b",
                        "api_key": "none",
                        "model": "qwen2-1.5b",
                        "enabled": False,
                        "backend": "openvino",
                        "ov_device": "GPU.0",
                        "ov_precision": "int8",
                    },
                ],
                # Phase A: 深度推理升级配置
                # 注：max_cost_per_task_usd 采用修正后的成本估算口径（含输出 token 与
                # self-check 轮成本，见 llm_gateway.ThinkingUpgradePolicy._estimate_thinking_cost），
                # 3 轮旗舰推理估算约 $1.7，故预算取 $2.0；旧值 $0.5 会导致升级路径永远被
                # cost_exceeded 拦截（H1/H2 修复前预算字段为死代码，无人消费）。
                "thinking_upgrade": {
                    "enabled": True,
                    "auto_upgrade_task_types": ["complex_analysis", "code_generation"],
                    "max_rounds": 3,
                    "max_tokens_per_round": 8000,
                    "timeout_seconds": 300,
                    "max_cost_per_task_usd": 2.0,
                    "downgrade_on_failure": True,
                    "self_check_enabled": True,
                    "confidence_threshold": 0.85,
                    "debug_skip_invariants": False,
                },
            },
            # Kimi K3 模型配置 — 支持私有化部署的国产开源模型
            "kimi": {
                "enabled": False,              # 是否启用 Kimi K3 模型
                "api_key": "",                 # KIMI_API_KEY 环境变量
                "base_url": "https://api.moonshot.cn/v1",  # Moonshot Kimi API端点
                "platform": "moonshot",        # moonshot 或 ark(火山方舟)
                "default_model": "kimi-k3",    # 默认模型
                "timeout_seconds": 90,
                "max_retries": 3,
                # 文本对话模型
                "text_pro_models": [
                    "kimi-k3",
                    "kimi-k3-32k",
                    "kimi-k3-128k",
                    "kimi-k2",
                    "kimi-k2-32k",
                ],
                "text_flash_models": [
                    "kimi-flash",
                    "kimi-flash-32k",
                ],
                # 视觉理解模型
                "vision_models": [
                    "kimi-vision-pro",
                ],
                # 代码模型
                "code_models": [
                    "kimi-code",
                ],
                # Embedding模型
                "embedding_models": [
                    "kimi-embedding",
                ],
                # 私有化部署配置
                "privatized": {
                    "enabled": False,          # 是否启用私有化部署
                    "local_base_url": "http://localhost:8000/v1",  # 本地部署端点
                    "enable_data_isolation": True,  # 是否启用数据隔离（敏感素材处理）
                    "max_context_length": 128000,   # 最大上下文长度
                },
            },
            # DeepSeek V4 模型配置 — 对接 DeepSeek 官方 API
            # 官方 API 模型名不带日期后缀：deepseek-v4-flash / deepseek-v4-pro
            # 原生支持 Responses API 格式，适配 Codex Agent 工作流
            # 与 doubao 配置块的区别：doubao 走火山方舟中转（ARK 命名带日期后缀），deepseek 走官方直连
            "deepseek": {
                "enabled": False,              # 是否启用 DeepSeek 官方 API
                "api_key": "",                 # DEEPSEEK_API_KEY 环境变量
                "base_url": "https://api.deepseek.com/v1",  # DeepSeek 官方 API 端点
                "default_model": "deepseek-v4-flash",  # 默认模型（V4-Flash）
                "timeout_seconds": 60,
                "max_retries": 3,
                # 峰谷计价感知（DeepSeek 已实施动态收费）
                "peak_hours": [9, 10, 11, 14, 15, 16, 17],  # 高峰时段
                "prefer_valley": True,         # 是否低谷期优先调用
                # 文本对话模型 - FLASH 级（官方 API 正式版）
                "text_flash_models": [
                    "deepseek-v4-flash",           # 官方 API 正式版（推荐）
                    "deepseek-v4-flash-260425",    # ARK 端点预览版（向后兼容）
                ],
                # 文本对话模型 - PRO 级
                "text_pro_models": [
                    "deepseek-v4-pro",             # 官方 API
                    "deepseek-v4-pro-260425",      # ARK 端点预览版
                ],
                # 深度推理模型（R1 系列）
                "reasoning_models": [
                    "deepseek-r1-250722",
                ],
                # 代码模型（复用 Flash，最佳性价比）
                "code_models": [
                    "deepseek-v4-flash",
                ],
                # 历史模型（向后兼容）
                "legacy_models": [
                    "deepseek-v3-250722",
                    "deepseek-v3-1-250922",
                    "deepseek-v3-2-260122",
                ],
            },
            # 豆包模型配置 — 对接火山方舟(ARK)平台
            "doubao": {
                "enabled": False,              # 是否启用豆包模型
                "api_key": "",                 # DOUBAO_API_KEY 环境变量
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",  # 火山方舟端点
                "platform": "ark",             # open_platform 或 ark
                "endpoint_id": "",             # ARK接入点ID（平台为ark时必填）
                "default_model": "doubao-seed-2-1-turbo-260628",  # 默认模型 (Agent Plan)
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
                # 视频生成模型 (2.0系列不可用，使用1.5/1.0)
                "video_model_pro": "doubao-seedance-1-5-pro-251128",
                "video_model_fast": "doubao-seedance-1-0-pro-fast-250722",
                # 3D生成模型
                "3d_model": "doubao-seed3d-2-0-251228",
                # Embedding模型
                "embedding_model": "doubao-embedding-240428",
                "embedding_model_large": "doubao-embedding-large-240428",
                "embedding_model_vision": "doubao-embedding-vision-240428",
                "timeout_seconds": 120,
                "max_retries": 2,
            },
            # NVIDIA Agent Toolkit 配置 — DGX Station GB300 本地部署
            "nvidia": {
                "enabled": False,               # 是否启用NVIDIA本地推理
                "agent_toolkit_path": "/opt/nvidia/agent-toolkit",  # Linux路径
                "agent_toolkit_path_win": "C:\\Program Files\\NVIDIA\\Agent Toolkit",  # Windows路径
                "api_base": "http://localhost:8000/v1",  # Agent Toolkit API端点
                "api_key": "",                 # AEKV_NVIDIA_API_KEY
                "max_retries": 3,
                "timeout_seconds": 120,
                # GB300 Blackwell Ultra 配置
                "blackwell": {
                    "enabled": False,          # 是否启用GB300加速
                    "device_count": 1,         # GB300设备数量
                    "max_batch_size": 32,
                    "inference_precision": "fp16",  # fp16 / bf16 / fp32
                    "enable_tensorrt": True,   # 是否启用TensorRT优化
                    "enable_triton": True,     # 是否启用Triton推理服务器
                },
                # 本地模型配置
                "local_models": {
                    "text_pro": "nvidia-llama-3.3-70b",      # PRO级文本模型
                    "text_flash": "nvidia-llama-3.3-8b",     # FLASH级文本模型
                    "vision": "nvidia-megatron-vision",      # 视觉模型
                    "image_gen": "nvidia-sd-3",              # 图像生成模型
                    "video_gen": "nvidia-veo",               # 视频生成模型
                    "embedding": "nvidia-embedding",         # 向量化模型
                    "code": "nvidia-code-llama",             # 代码生成模型
                },
                # 自动降级策略
                "fallback_to_cloud": True,     # 本地模型不可用时是否降级到云端
                "fallback_to_local_llm": True,  # 当 NVIDIA Agent Toolkit 不可用时，回退到本地 transformers LLM
                "local_llm_model": "phi3-mini",  # 本地回退模型: phi3-mini / gemma2-2b / qwen2-7b
                "health_check_interval_seconds": 30,  # 健康检查间隔
            },
            # NVIDIA Omniverse 配置 — 3D渲染与物理仿真
            "omniverse": {
                "enabled": False,              # 是否启用Omniverse
                "server_url": "localhost:8211",  # Omniverse Nucleus服务器
                "cache_dir": "./omniverse_cache",
                "renderer": "rtx",             # rtx / path_tracer / iray
                "resolution": [1920, 1080],
                "frame_rate": 30,
                "enable_physics": True,        # 是否启用物理仿真
                "enable_particles": True,      # 是否启用粒子系统
                "max_particles": 1000000,
                "enable_lighting": True,       # 是否启用光照系统
                "timeout_seconds": 300,
                "max_retries": 2,
            },
            # 魔搭 ModelScope 配置 — 阿里云开源模型社区
            # 注意: 推理API必须使用 stream=True 模式
            "modelscope": {
                "enabled": True,               # 已启用 (2026-07-29 验证通过)
                "api_key": "",                 # MODELSCOPE_API_KEY 环境变量
                "base_url": "https://api-inference.modelscope.cn/v1",  # 正确推理端点
                "default_model": "Qwen/Qwen3-235B-A22B",  # 默认文本模型
                "stream_required": True,       # 必须流式调用
                "timeout_seconds": 120,
                "max_retries": 3,
                # 文本对话模型 (完整model_id格式)
                "text_pro_models": [
                    "Qwen/Qwen3-235B-A22B",
                    "deepseek-ai/DeepSeek-V4-Pro",
                    "ZhipuAI/GLM-5.2",
                ],
                "text_flash_models": [
                    "Qwen/Qwen3-8B",
                    "Qwen/Qwen3-14B",
                ],
                # 视觉理解模型
                "vision_models": [
                    "Qwen/Qwen3-VL-235B-A22B-Instruct",
                    "Qwen/Qwen3-VL-8B-Instruct",
                ],
                # 代码模型
                "code_models": [
                    "Qwen/Qwen3-Coder-30B-A3B-Instruct",
                ],
                # Embedding模型 (需本地部署或DashScope)
                "embedding_models": [
                    "bge-m3",
                ],
                # 文生图模型（创空间）
                "image_gen_models": [
                    "flux-1-dev",
                    "sd-xl-base",
                ],
                # 自动降级配置
                "fallback_enabled": True,       # 魔搭不可用时是否降级到其他Provider
                "health_check_interval_seconds": 30,
            },
            # 记忆系统配置 — 对接 core/memory_store.py
            "memory": {
                "enabled": True,
                "db_path": "",                 # 空=默认 ~/.ae-knowledge-vault/memory.db
                "min_confidence": 0.3,         # 经验推荐最低置信度
            },
            # 无水印素材获取 (Stock Footage) — Pexels + Pixabay 双源
            # 环境变量映射:
            #   AEKV_STOCK_PEXELS_API_KEY  -> stock.pexels.api_key
            #   AEKV_STOCK_PIXABAY_API_KEY -> stock.pixabay.api_key
            #   AEKV_STOCK_CACHE_DIR       -> stock.cache_dir
            # 也兼容无前缀版本: PEXELS_API_KEY / PIXABAY_API_KEY
            "stock": {
                "enabled": True,
                "cache_dir": "./data/stock_footage",
                "default_min_width": 1280,
                "default_min_height": 720,
                "default_min_duration": 5.0,
                "download_timeout_seconds": 180,
                "request_timeout_seconds": 30,
                "pexels": {
                    "api_key": "",               # AEKV_STOCK_PEXELS_API_KEY 或 PEXELS_API_KEY
                    "base_url": "https://api.pexels.com/videos/search",
                    "max_retries": 2,
                    "per_page": 15,
                    "enabled": True,
                },
                "pixabay": {
                    "api_key": "",               # AEKV_STOCK_PIXABAY_API_KEY 或 PIXABAY_API_KEY
                    "base_url": "https://pixabay.com/api/videos/",
                    "max_retries": 2,
                    "per_page": 20,
                    "enabled": True,
                },
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

        # 修正 memory.db_path 空值：注释说明空=默认~/.ae-knowledge-vault/memory.db，但代码没转
        mem_cfg = self._config.setdefault("memory", {})
        if not mem_cfg.get("db_path"):
            default_db = os.path.expanduser("~/.ae-knowledge-vault/memory.db")
            os.makedirs(os.path.dirname(default_db), exist_ok=True)
            mem_cfg["db_path"] = default_db

        # 验证配置（生产环境严格；非生产环境下软件路径不存在等非致命问题降级为警告）
        env_name = os.environ.get("AEK_ENVIRONMENT", "development").lower()
        strict = env_name == "production"
        validator = ConfigValidator(strict=strict)
        errors, warnings = validator.validate(self._config)
        if warnings:
            for w in warnings:
                self._logger.warning(f"  [WARN] {w}")
        if errors:
            self._logger.error(f"配置验证发现 {len(errors)} 个严重问题:")
            for err in errors:
                self._logger.error(f"  [ERROR] {err}")
            if strict:
                raise RuntimeError(
                    f"配置验证失败（{len(errors)} 个错误）:\n  - " + "\n  - ".join(errors)
                )
            else:
                self._logger.warning("非 production 环境，验证错误降级为警告（继续加载）")

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
        """加载环境变量配置。

        策略：
        1. 精确映射表优先（覆盖下划线命名的复合键）。
        2. Section 别名表（llm → model 等）。
        3. 通用回退：按第一个下划线切分 section/key，避免把所有下划线转成点号。
        """
        # 显式映射: env var (AEKV_ 之后的部分, 大写) → 配置点路径
        EXPLICIT_MAP: Dict[str, str] = {
            # LLM / Model
            "LLM_API_KEY": "model.api_key",
            "LLM_BASE_URL": "model.base_url",
            "LLM_MODEL": "model.model",
            "LLM_PRO_MODEL": "model.pro_model",
            "LLM_FLASH_MODEL": "model.flash_model",
            "LLM_VISION_MODEL": "model.vision_model",
            "LLM_CODE_MODEL": "model.code_model",
            "LLM_EMBEDDING_MODEL": "model.embedding_model",
            "MODEL_BASE_URL": "model.base_url",
            "MODEL_MAX_TOKENS": "model.max_tokens",
            "MODEL_TEMPERATURE": "model.temperature",
            # 各类 API Key 别名
            "OPENAI_API_KEY": "model.api_key",
            "DEEPSEEK_API_KEY": "deepseek.api_key",
            "DEEPSEEK_BASE_URL": "deepseek.base_url",
            "DEEPSEEK_MODEL": "deepseek.default_model",
            "DEEPSEEK_FLASH_MODEL": "deepseek.default_model",
            "DEEPSEEK_PRO_MODEL": "deepseek.default_model",
            "DEEPSEEK_CODE_MODEL": "deepseek.default_model",
            "DEEPSEEK_REASONING_MODEL": "deepseek.default_model",
            "DOUBAO_API_KEY": "doubao.api_key",
            "KIMI_API_KEY": "kimi.api_key",
            "MODELSCOPE_API_KEY": "modelscope.api_key",
            "MODELSCOPE_BASE_URL": "modelscope.base_url",
            # Stock footage
            "STOCK_PEXELS_API_KEY": "stock.pexels.api_key",
            "STOCK_PIXABAY_API_KEY": "stock.pixabay.api_key",
            "PEXELS_API_KEY": "stock.pexels.api_key",
            "PIXABAY_API_KEY": "stock.pixabay.api_key",
            # Pipeline
            "PIPELINE_MAX_CONCURRENT_TASKS": "pipeline.max_concurrent_tasks",
            "OUTPUT_DEFAULT_DIR": "output.default_dir",
            "OUTPUT_TMP_DIR": "output.tmp_dir",
            "OUTPUT_MAX_FILE_SIZE_MB": "output.max_file_size_mb",
            "OUTPUT_KEEP_TEMPORARY_FILES": "output.keep_temporary_files",
            # Server
            "SERVER_HOST": "server.host",
            "SERVER_PORT": "server.port",
            # AE
            "AE_INSTALL_PATH": "ae.install_path",
            "AE_SCRIPT_DIR": "ae.script_dir",
            "AE_MAX_RETRIES": "ae.max_retries",
            "AE_RETRY_DELAY_MS": "ae.retry_delay_ms",
            "AE_TIMEOUT_MS": "ae.timeout_ms",
            # Security
            "VAULT_SECRET_KEY": "security.secret_key",
        }

        # Section 别名（保留供未来扩展；当前通用回退直接按点路径写入）
        SECTION_ALIASES: Dict[str, str] = {
            "LLM": "model",
        }
        _ = SECTION_ALIASES  # 目前通用回退不使用别名，保留显式映射表即可

        env_config: Dict[str, Any] = {}
        loaded = 0

        for key, value in os.environ.items():
            if not key.startswith("AEKV_"):
                continue

            suffix = key[5:]  # 去掉 AEKV_ 前缀
            target_path: Optional[str] = EXPLICIT_MAP.get(suffix)

            if target_path is None:
                # 通用回退（已知复合键已由 EXPLICIT_MAP 覆盖）：
                # 从默认配置根开始，贪心匹配最长已知 dict 键，逐层下钻，
                # 无法再下钻时把剩余段整体作为叶子 key（保留 snake_case 下划线）。
                # 若第一个段就不是已知 section，全下划线转点号（兼容任意深度自定义）。
                parts_lower = suffix.lower().split("_")
                matched_parts: List[str] = []
                current_node: Any = self._config
                pos = 0
                n = len(parts_lower)
                if isinstance(current_node, dict) and parts_lower[0] not in current_node:
                    # 未知顶级 section：旧行为全拆分
                    target_path = ".".join(parts_lower)
                else:
                    while pos < n:
                        # 从 pos 开始找最长匹配键
                        best_end = -1
                        best_is_dict = False
                        for end in range(n, pos, -1):
                            candidate = "_".join(parts_lower[pos:end])
                            if isinstance(current_node, dict) and candidate in current_node:
                                best_end = end
                                best_is_dict = isinstance(current_node[candidate], dict)
                                break  # 最长优先
                        if best_end == -1:
                            # 无匹配键：剩余整段作为叶子 key（保留下划线）
                            matched_parts.append("_".join(parts_lower[pos:]))
                            break
                        matched_parts.append("_".join(parts_lower[pos:best_end]))
                        if not best_is_dict:
                            # 叶子节点，后续段并入 key（理论上不会到达）
                            if best_end < n:
                                extra = "_".join(parts_lower[best_end:])
                                matched_parts[-1] = matched_parts[-1] + "_" + extra
                            break
                        current_node = current_node[matched_parts[-1]]
                        pos = best_end
                    target_path = ".".join(matched_parts)

            parts = target_path.split(".")
            current = env_config
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    current[part] = self._convert_value(value)
                else:
                    if part not in current or not isinstance(current[part], dict):
                        current[part] = {}
                    current = current[part]
            loaded += 1

        if env_config:
            self._sources.append(ConfigSource("environment", 99, env_config))
            self._merge_source(self._sources[-1])
            self._logger.info(f"加载 {loaded} 个环境变量配置")

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

        # 日志脱敏
        SENSITIVE_PATH_KEYWORDS = ["key", "token", "secret", "password", "authorization", "credential"]
        display_value = value
        if any(kw in path.lower() for kw in SENSITIVE_PATH_KEYWORDS):
            if isinstance(value, str) and value:
                if len(value) <= 4:
                    display_value = "***"
                else:
                    display_value = value[:2] + "***" + value[-2:]
            else:
                display_value = "***"
        self._logger.debug(f"配置更新: {path} = {display_value}")

    def update(self, data: Dict[str, Any]) -> None:
        """批量更新配置"""
        self._config = self._deep_merge(self._config, data)
        self._logger.debug(f"配置批量更新: {len(data)} 项")

    # -------------------------------------------------------------------------
    # 配置管理
    # -------------------------------------------------------------------------

    @staticmethod
    def _mask_sensitive_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """递归掩码配置中的敏感字段，用于保存/导出时不泄漏 API Key。"""
        import copy
        SENSITIVE_KEYWORDS = [
            "token", "secret", "password",
            "authorization", "credential", "bearer",
            "apikey", "api_key", "private_key", "access_key", "access_token",
            "refresh_token", "id_token", "session_key", "signing_key",
        ]
        def _is_sk_like(val: Any) -> bool:
            if not isinstance(val, str) or len(val) < 4:
                return False
            return val.startswith(("sk-", "sk_live_", "sk_test_", "Bearer ", "eyJ", "xoxb-", "xoxp-", "ghp_"))

        def _mask(val: str) -> str:
            if len(val) <= 4:
                return "***"
            return val[:2] + "*" * max(4, len(val) - 4) + val[-2:]

        def _recurse(obj: Any) -> Any:
            if isinstance(obj, dict):
                out = {}
                for k, v in obj.items():
                    key_sensitive = any(kw in str(k).lower() for kw in SENSITIVE_KEYWORDS)
                    if isinstance(v, (dict, list)):
                        out[k] = _recurse(v)
                    elif key_sensitive or _is_sk_like(v):
                        out[k] = _mask(str(v)) if v else ""
                    else:
                        out[k] = v
                return out
            if isinstance(obj, list):
                return [_recurse(item) for item in obj]
            return obj

        return _recurse(copy.deepcopy(config_dict))

    def reload(self) -> None:
        """热重载配置"""
        self._logger.info("热重载配置...")
        self._config = {}
        self._sources = []
        self._register_default_config()
        self.load_config(self._config_files)

    def save(self, path: str = "./config.json") -> None:
        """保存当前配置到文件"""
        safe_config = self._mask_sensitive_config(self._config)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(safe_config, f, ensure_ascii=False, indent=2)
        self._logger.info(f"配置已保存到: {path}")

    def validate(self):
        """验证当前配置，返回错误字符串列表（warnings 仅记录日志）"""
        errors, warnings = self._validator.validate(self._config)
        for w in warnings:
            self._logger.warning(f"[配置警告] {w}")
        return errors

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

    def get_config(self) -> Dict[str, Any]:
        """获取完整配置字典的只读副本"""
        import copy
        return copy.deepcopy(self._config)

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
        """获取完整配置的深拷贝（不掩码；对外展示请用 get_config_summary）"""
        import copy
        return copy.deepcopy(self._config)


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
