"""Configuration loader for Puppet Automation Pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=(),
    )

    # Environment
    env: str = Field(default="development")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    # Paths
    project_root: Path = Path(__file__).resolve().parent.parent.parent.parent
    data_dir: Path = project_root / "data"
    input_dir: Path = data_dir / "input"
    output_dir: Path = data_dir / "output"
    # 二线实战反馈隔离目录：引擎实战任务(真实反馈)产物独立存放，
    # 与一线 learning 状态(digital_twin/self_evolution/versions 等)物理隔离，避免交叉污染
    feedback_dir: Path = data_dir / "engine_feedback"
    temp_dir: Path = data_dir / "temp"
    cache_dir: Path = data_dir / "cache"
    projects_dir: Path = data_dir / "projects"
    logs_dir: Path = project_root / "logs"

    # Resource directories (D盘资源库)
    resources_dir: Path = Path(
        os.environ.get("AEKV_RESOURCES_DIR", "D:/AE-Work/resources")
    )
    video_dir: Path = resources_dir / "video"
    audio_dir: Path = resources_dir / "audio"
    effects_dir: Path = resources_dir / "effects"
    fonts_dir: Path = resources_dir / "fonts"
    luts_dir: Path = resources_dir / "luts"
    davinci_dir: Path = resources_dir / "davinci"
    psd_dir: Path = resources_dir / "psd"
    # 扩展资源目录（百度网盘整理后新增）
    models_dir: Path = resources_dir / "models"          # 3D 模型（FBX/MAX/OBJ）
    tutorials_dir: Path = resources_dir / "tutorials"    # 教程视频
    docs_dir: Path = resources_dir / "docs"              # 教程文档
    references_dir: Path = resources_dir / "references"  # 素材网站与下载工具
    premiere_dir: Path = resources_dir / "premiere"      # PR 插件与 LUTS 调色预设
    presets_dir: Path = resources_dir / "presets"        # 预留：预设资源
    resource_projects_dir: Path = resources_dir / "projects"  # AE 工程文件（资源库内）
    software_dir: Path = resources_dir / "software"      # 软件安装包
    scripts_dir: Path = resources_dir / "scripts"        # AE 脚本（JSX/JSXBIN）
    plugins_dir: Path = resources_dir / "plugins"        # AE 插件安装包 (ZXP/AEX)
    templates_dir: Path = resources_dir / "templates"    # AE 工程模板
    images_dir: Path = resources_dir / "images"          # 图片素材（PNG/JPG/TIFF）

    # AE Projects directory
    ae_projects_dir: Path = Path(
        os.environ.get("AEKV_PROJECTS_DIR", "D:/AE-Work/projects")
    )

    # API Server
    api_host: str = "127.0.0.1"  # 安全：默认仅本机访问，需对外时显式配置 0.0.0.0
    api_port: int = 8000
    api_workers: int = 4

    # Redis / Celery
    redis_host: str = "localhost"
    redis_port: int = 6379
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Database
    database_url: str = f"sqlite:///{data_dir / 'puppet_automation.db'}"

    # Render Job Persistence (aerender 任务持久化)
    render_db_path: Path = data_dir / "render_jobs.db"
    render_stale_timeout_minutes: int = 30
    render_max_history_days: int = 90
    render_auto_cleanup: bool = True

    # Dashboard Storage (前端面板数据持久化)
    db_path: Path = data_dir / "dashboard.db"

    # Engine Paths
    # 注：项目规范要求使用 AE 2025 (25.3)，AE 2026 不兼容，已删除 ae_2026_path 字段
    # （原 ae_2026_path 值指向 2025 目录是 typo，且无其他代码引用 settings.ae_2026_path）
    ae_2025_path: Path = Path(
        os.environ.get("AEKV_AE_PATH", "C:/Program Files/Adobe/Adobe After Effects 2025")
    )
    aerender_path: Path = ae_2025_path / "Support Files" / "aerender.exe"
    silhouette_path: Path = Path("C:/Program Files/BorisFX/Silhouette 2026.0")
    davinci_path: Path = Path(
        os.environ.get("AEKV_DAVINCI_PATH", "D:/app")
    )
    topaz_path: Path = Path(
        os.environ.get("AEKV_TOPAZ_PATH", "D:/top/Topaz Video AI Pro/Topaz Video AI BETA.exe")
    )
    blender_path: Path = Path(
        os.environ.get("AEKV_BLENDER_PATH", "D:/Blender/Blender 5.1.0/blender.exe")
    )

    # Cinema 4D 2026（3D 场景生成 + MoGraph 运动图形）
    c4d_path: Path = Path("C:/Program Files/Maxon Cinema 4D 2026")
    c4d_executable: Path = c4d_path / "Cinema 4D.exe"
    c4dpy_executable: Path = c4d_path / "c4dpy.exe"

    # Adobe Media Encoder（与 AE 2025 同版本系列，保证队列直发兼容）
    # 已安装 AME 2025 (25.3.0.73)，路径已验证
    media_encoder_path: Path = Path(
        os.environ.get("AEKV_ME_PATH", "D:/Me/Adobe Media Encoder 2025/Adobe Media Encoder.exe")
    )

    # Adobe Premiere Pro（剪辑节奏 + 动态链接）— 实际安装在 D:\Pr25
    premiere_path: Path = Path(
        os.environ.get("AEKV_PR_PATH", "D:/Pr25/Adobe Premiere Pro 2025/Adobe Premiere Pro.exe")
    )

    # Adobe Photoshop（素材预处理 + PSD分层 + LUT生成）— 实际安装在 D:\ps
    photoshop_path: Path = Path(
        os.environ.get("AEKV_PS_PATH", "D:/ps/Adobe Photoshop 2025/Photoshop.exe")
    )

    # Adobe Audition（AI降噪 + 响度统一 + 音频修复）
    audition_path: Path = Path("C:/Program Files/Adobe/Adobe Audition 2025/Adobe Audition.exe")

    # FFmpeg: prefer system install, fallback to imageio-ffmpeg binary
    # 修复 P0-3：原 C:/tools/ffmpeg/bin/ 路径不存在，统一改为实际安装路径 C:/ffmpeg/bin/
    ffmpeg_path: Path = Path(
        os.environ.get("AEKV_FFMPEG_PATH", "C:/ffmpeg/bin/ffmpeg.exe")
    )
    ffprobe_path: Path = Path("C:/ffmpeg/bin/ffprobe.exe")

    # ComfyUI
    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_workflows_dir: Path = data_dir / "comfyui_workflows"
    comfyui_output_dir: Path = data_dir / "comfyui_output"
    comfyui_input_dir: Path = data_dir / "comfyui_input"
    comfyui_timeout: int = 600

    # Flux 3 (Black Forest Labs API - 音画一体生成)
    flux3_base_url: str = "https://api.bfl.ml/v1"
    flux3_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Flux3 API Key",
        validation_alias=AliasChoices("flux3_api_key", "BFL_API_KEY", "FLUX3_API_KEY"),
    )
    flux3_output_dir: Path = data_dir / "flux3_output"
    flux3_timeout: int = 1800
    flux3_poll_interval: float = 5.0

    # SadTalker（音频驱动数字人视频生成）
    sadtalker_root: Path = Path(
        os.environ.get("AEKV_SADTALKER_ROOT", "D:/AE-Work/sadtalker")
    )
    sadtalker_python: Path = sadtalker_root / "venv" / "Scripts" / "python.exe"
    sadtalker_inference: Path = sadtalker_root / "inference.py"
    sadtalker_output_dir: Path = data_dir / "sadtalker_output"
    sadtalker_timeout: int = 1800

    # SAM2（视频对象分割/遮罩）— 子进程隔离模式
    # venv-sam2 独立虚拟环境，避免 PyTorch/SAM2 依赖污染主环境
    sam2_venv_python: Path = Path(
        os.environ.get("AEKV_SAM2_PYTHON", "D:/AE-Work/venv-sam2/Scripts/python.exe")
    )
    sam2_model_dir: Path = Path(
        os.environ.get("AEKV_SAM2_MODEL_DIR", "D:/AE-Work/models/sam2")
    )
    sam2_default_model: str = "base"  # base/large/small/tiny (8GB显存推荐 base)
    sam2_output_dir: Path = data_dir / "sam2_output"
    sam2_timeout: int = 3600

    # Matting（抠像引擎）— PP-MattingV2 ONNX 推理
    # 依赖 onnxruntime/onnxruntime-gpu，CPU/GPU 均可运行
    matting_model_dir: Path = Path(
        os.environ.get("AEKV_MATTING_MODEL_DIR", "D:/AE-Work/models/matting")
    )
    matting_output_dir: Path = data_dir / "matting_output"
    matting_timeout: int = 3600

    # Ultralytics config dir (sandbox-safe)
    yolo_config_dir: Path = cache_dir / "ultralytics"

    def get_ffmpeg(self) -> Path:
        """Get ffmpeg path, fallback to imageio-ffmpeg bundled binary."""
        if self.ffmpeg_path.exists():
            return self.ffmpeg_path
        try:
            import imageio_ffmpeg
            return Path(imageio_ffmpeg.get_ffmpeg_exe())
        except ImportError:
            return self.ffmpeg_path

    # MCP Gateway
    mcp_gateway_host: str = "0.0.0.0"
    mcp_gateway_port: int = 3000
    mcp_auth_token: SecretStr = SecretStr("")

    # Premiere MCP Bridge（文件轮询通信）
    # 与 CEP 插件 MCPBridgeCEP 的 DEFAULT_TEMP_DIR 保持一致：<project_root>/.premiere-mcp-bridge/
    pr_bridge_dir: Path = project_root / ".premiere-mcp-bridge"
    pr_bridge_timeout: int = 15
    pr_bridge_poll_interval: float = 0.3
    pr_bridge_signature_enabled: bool = False

    # Photoshop MCP Bridge（文件轮询通信）
    ps_bridge_dir: Path = project_root / ".ps-mcp-bridge"
    ps_bridge_timeout: int = 15
    ps_bridge_poll_interval: float = 0.3
    ps_bridge_signature_enabled: bool = False

    # GPU
    cuda_visible_devices: str = "0"

    # AI Models
    model_cache_dir: Path = cache_dir / "models"
    huggingface_home: Path = cache_dir / "huggingface"

    # ---------- Webhook 告警通知 ----------
    # 敏感字段通过环境变量注入：AEKV_WEBHOOK_URL / AEKV_WEBHOOK_SECRET
    # 同时支持 WEBHOOK_URL / WEBHOOK_SECRET（pydantic 默认从字段名派生）
    webhook_enabled: bool = False
    webhook_platform: str = "wechat"  # wechat / dingtalk / feishu
    webhook_url: str = Field(
        default="",
        validation_alias=AliasChoices("webhook_url", "AEKV_WEBHOOK_URL"),
    )
    webhook_secret: SecretStr = Field(
        default=SecretStr(""),
        description="Webhook signing secret",
        validation_alias=AliasChoices("webhook_secret", "AEKV_WEBHOOK_SECRET"),
    )
    webhook_max_retries: int = 3
    webhook_retry_interval: float = 5.0
    webhook_timeout: float = 10.0
    webhook_quiet_minutes: int = 5  # 同一告警类型静默期（分钟）

    # 持续阈值告警配置（资源持续超过阈值指定秒数后触发 webhook）
    alert_cpu_threshold: float = 90.0
    alert_cpu_sustained_seconds: int = 30
    alert_memory_threshold: float = 90.0
    alert_memory_sustained_seconds: int = 30
    alert_disk_threshold: float = 95.0
    alert_disk_sustained_seconds: int = 60
    alert_hostname: str = ""  # 告警消息中显示的主机名，空则自动探测

    # LLM Gateway (统一网关 core/llm_gateway.py) — 业务代码必须通过网关调用 LLM
    # 优先级：AEKV_LLM_* 环境变量 > 下方字段默认值
    llm_base_url: str = ""           # AEKV_LLM_BASE_URL / OPENAI_BASE_URL
    llm_api_key: SecretStr = SecretStr("")  # AEKV_LLM_API_KEY / OPENAI_API_KEY
    llm_default_model: str = "auto"  # AEKV_LLM_MODEL
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 3
    llm_enable_compression: bool = True
    llm_enable_fallback: bool = True
    # 降级 Provider 列表 (JSON 字符串，解析为 list[dict])
    llm_fallback_providers_json: str = ""

    def get_llm_gateway_config(self):
        """构造 core.llm_gateway.LLMConfig 配置对象。

        Returns:
            core.llm_gateway.LLMConfig — 已合并 settings 与环境变量的配置
        """
        import json as _json

        from core.llm_gateway import LLMConfig, TaskType

        fallbacks = []
        if self.llm_fallback_providers_json:
            try:
                fallbacks = _json.loads(self.llm_fallback_providers_json)
            except (ValueError, TypeError):
                fallbacks = []

        return LLMConfig(
            base_url=self.llm_base_url,
            api_key=self.llm_api_key.get_secret_value() if isinstance(self.llm_api_key, SecretStr) else self.llm_api_key,
            default_model=self.llm_default_model,
            timeout_seconds=self.llm_timeout_seconds,
            max_retries=self.llm_max_retries,
            enable_compression=self.llm_enable_compression,
            enable_fallback=self.llm_enable_fallback,
            fallback_providers=fallbacks,
        )

    # 兼容字段（已废弃 — 仅用于老代码读取，新代码必须使用 llm_* 字段或网关）
    llm_provider: str = ""  # 保留以兼容老配置文件
    default_llm_model: str = "gpt-4o-mini"
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    @field_validator(
        "resources_dir", "ae_projects_dir", "ae_2025_path", "topaz_path",
        "blender_path", "media_encoder_path", "ffmpeg_path", "sadtalker_root",
        mode="after",
    )
    @classmethod
    def ensure_path_absolute(cls, v: Path, info) -> Path:
        """如果路径不存在，输出 WARNING（不抛异常，允许后续降级）"""
        env_map = {
            "resources_dir": "AEKV_RESOURCES_DIR",
            "ae_projects_dir": "AEKV_PROJECTS_DIR",
            "ae_2025_path": "AEKV_AE_PATH",
            "topaz_path": "AEKV_TOPAZ_PATH",
            "blender_path": "AEKV_BLENDER_PATH",
            "media_encoder_path": "AEKV_ME_PATH",
            "ffmpeg_path": "AEKV_FFMPEG_PATH",
            "sadtalker_root": "AEKV_SADTALKER_ROOT",
        }
        if not v.exists():
            import logging as _l
            env_name = env_map.get(info.field_name, "")
            _l.getLogger(__name__).warning(
                f"[Config] {info.field_name} 不存在: {v}. "
                f"可通过环境变量 {env_name} 指定。"
            )
        return v

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.env == "production":
            # 生产环境必须修改默认 token
            token_val = (
                self.mcp_auth_token.get_secret_value()
                if isinstance(self.mcp_auth_token, SecretStr)
                else self.mcp_auth_token
            )
            if not token_val:
                raise ValueError(
                    "PRODUCTION ERROR: mcp_auth_token 必须显式配置，不能为空或默认值"
                )
            # 生产环境必须关闭 debug
            if self.debug:
                import warnings
                warnings.warn("PRODUCTION: debug=True has been auto-forced to False")
                object.__setattr__(self, "debug", False)
        return self

    def ensure_dirs(self) -> None:
        """Ensure all required directories exist."""
        for d in [
            self.data_dir, self.input_dir, self.output_dir, self.feedback_dir,
            self.temp_dir, self.cache_dir, self.projects_dir,
            self.logs_dir, self.model_cache_dir, self.huggingface_home,
            self.yolo_config_dir, self.comfyui_workflows_dir,
            self.comfyui_output_dir, self.comfyui_input_dir,
            self.flux3_output_dir,
            self.sadtalker_output_dir,
            self.sam2_output_dir,
            self.matting_output_dir,
            self.render_db_path.parent,
            self.resources_dir, self.video_dir, self.audio_dir,
            self.effects_dir, self.fonts_dir, self.luts_dir,
            self.davinci_dir, self.psd_dir,
            self.models_dir, self.tutorials_dir, self.docs_dir,
            self.references_dir, self.premiere_dir, self.presets_dir,
            self.resource_projects_dir, self.software_dir,
            self.ae_projects_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)
        # Set YOLO_CONFIG_DIR env var so ultralytics uses sandbox-safe path
        import os
        os.environ.setdefault("YOLO_CONFIG_DIR", str(self.yolo_config_dir))


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance (for FastAPI dependency injection)."""
    return settings
