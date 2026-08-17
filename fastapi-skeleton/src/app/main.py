"""FastAPI application entrypoint.

Demonstrates the standard layered wiring:
  config -> database -> dependencies -> repositories -> services -> api -> main
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.database import init_db
from app.utils.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表（演示用）。生产环境请使用 Alembic 迁移。
    await init_db()
    yield
    # 此处可释放连接池等资源（本骨架未持有需手动释放的资源）。


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

    # CORS：生产环境请收缩为具体前端域名，不要用 "*"。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


# uvicorn 通过 `app.main:app` 找到这个实例。
app = create_app()
