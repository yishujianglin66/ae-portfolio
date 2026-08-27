"""
生产配置管理 - 集中化环境配置
支持 development / test / production 三种环境
"""

import os
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings:
    """全局配置单例"""

    def __init__(self) -> None:
        self.environment: str = os.environ.get("AEK_ENVIRONMENT", "development")
        self.is_production: bool = self.environment == "production"
        self.is_development: bool = self.environment == "development"

        # --- API 服务 ---
        self.api_host: str = os.environ.get("API_HOST", "0.0.0.0")
        self.api_port: int = int(os.environ.get("API_PORT", "8000"))
        self.api_workers: int = int(os.environ.get("API_WORKERS", "1"))
        self.cors_origins: str = os.environ.get("CORS_ORIGINS", "*")

        # --- 认证 ---
        self.jwt_secret: str = os.environ.get("AE_VAULT_SECRET_KEY", "")
        self.jwt_alg: str = "HS256"
        self.access_token_ttl: int = int(os.environ.get("ACCESS_TOKEN_TTL", "3600"))
        self.refresh_token_ttl: int = int(os.environ.get("REFRESH_TOKEN_TTL", "604800"))
        if not self.jwt_secret:
            if self.is_production:
                raise RuntimeError(
                    "生产环境必须设置 AE_VAULT_SECRET_KEY 环境变量"
                )
            # VULN-004: 非生产环境随机化，避免使用公开硬编码字符串；
            # 每次实例化生成不同值，防止会话固定/伪造攻击。
            import secrets
            self.jwt_secret = secrets.token_urlsafe(32)

        # --- 数据库 ---
        self.db_path: str = os.environ.get(
            "DB_PATH", str(PROJECT_ROOT / "data" / "ae_vault.db")
        )

        # --- 监控 ---
        self.metrics_interval: float = float(os.environ.get("METRICS_INTERVAL", "15.0"))
        self.alert_check_interval: float = float(os.environ.get("ALERT_CHECK_INTERVAL", "10.0"))

        # --- 任务调度 ---
        self.scheduler_workers: int = int(os.environ.get("SCHEDULER_WORKERS", "3"))

        # --- 前端 ---
        self.frontend_dist: str = os.environ.get(
            "FRONTEND_DIST", str(PROJECT_ROOT / "ae-dashboard" / "dist")
        )

        # --- 路径 ---
        self.data_dir: Path = PROJECT_ROOT / "data"
        self.logs_dir: Path = PROJECT_ROOT / "logs"
        # 管线实战反馈隔离目录 (feedback_loop / KnowledgeInjector 回读写历史经验)
        self.feedback_dir: str = os.environ.get(
            "FEEDBACK_DIR", str(PROJECT_ROOT / "data" / "engine_feedback")
        )
        self._ensure_dirs()

        # --- 日志 ---
        self.log_level: str = os.environ.get("LOG_LEVEL", "INFO" if self.is_production else "DEBUG")
        self.log_file: Optional[str] = str(self.logs_dir / "api.log") if self.is_production else None

    def _ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        Path(self.feedback_dir).mkdir(parents=True, exist_ok=True)

    @property
    def cors_origin_list(self) -> list:
        if self.cors_origins == "*":
            # 缺口A：生产环境禁止 CORS 通配符，拒绝启动消费方继续运行
            if self.is_production:
                raise RuntimeError(
                    "生产环境禁止 CORS_ORIGINS=*，请设置显式域名白名单"
                )
            # 缺口B：开发环境允许通配符但必须警告（仅限本地调试）
            import warnings
            warnings.warn(
                "开发环境正在使用 CORS_ORIGINS=*，仅限本地调试；上线前必须设置显式域名",
                RuntimeWarning,
                stacklevel=2,
            )
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def summary(self) -> dict:
        return {
            "environment": self.environment,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "is_production": self.is_production,
            "db_path": self.db_path,
            "frontend_dist": self.frontend_dist,
            "log_level": self.log_level,
        }


settings = Settings()
