"""Application configuration via pydantic-settings.

Reads from environment variables and an optional `.env` file.
Using pydantic-settings keeps config strongly typed and validated at startup,
so a missing/wrong env var fails fast instead of failing deep in the code.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "FastAPI Skeleton"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    # 逗号分隔的允许来源，例如 "https://a.com,https://b.com"
    cors_origins: str = "*"

    # --- Database ---
    # 默认 SQLite 文件库 => 零配置本地即跑；换 Postgres 只改这一行。
    database_url: str = "sqlite+aiosqlite:///./app.db"


# 模块级单例：所有模块 import 同一个实例，避免重复解析 .env。
settings = Settings()
