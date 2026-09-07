"""Async SQLAlchemy engine, session factory and declarative base.

Layered note: this module is the only place that knows *how* to talk to the DB.
Repositories depend on an injected `AsyncSession` and never create engines.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类（SQLAlchemy 2.0 风格）。"""


# future=True 启用 2.0 行为；echo 在 debug 时打印 SQL，便于排查。
engine = create_async_engine(settings.database_url, echo=settings.debug, future=True)

# expire_on_commit=False：提交后对象属性仍可读，避免懒加载意外触发新查询。
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """按已注册模型建表。

    仅用于演示/本地开发。生产环境请使用 Alembic 做迁移，
    而非 `create_all`（它无法处理列变更、数据迁移等）。
    """
    # 导入模型以确保它们注册到 Base.metadata
    from app.models import user  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：为每个请求提供一个会话，请求结束自动关闭。"""
    async with AsyncSessionLocal() as session:
        yield session
