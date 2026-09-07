"""FastAPI 依赖注入装配点。

把"细粒度"依赖（会话 -> 仓储 -> 服务）串成一条链。
路由只需要声明 `service: UserService = Depends(get_user_service)`，
完全不关心下层是如何构造的——这就是依赖倒置。
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.user import UserRepository
from app.services.user import UserService


def get_user_repository(session: AsyncSession = Depends(get_session)) -> UserRepository:
    return UserRepository(session)


def get_user_service(repo: UserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(repo)
