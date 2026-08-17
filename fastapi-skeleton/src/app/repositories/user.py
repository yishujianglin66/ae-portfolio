"""User 数据访问层。

只负责"把对象存进/取出来"，不含业务规则（如邮箱唯一性校验放在 service 层）。
构造函数接收一个 `AsyncSession`，由依赖注入在请求级提供。
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int) -> User | None:
        # session.get 走主键缓存，比 select 更轻量
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, *, page: int, size: int) -> tuple[list[User], int]:
        """返回 (本页数据, 总数)。总数用于分页元信息，与偏移无关。"""
        total = await self.session.scalar(select(func.count()).select_from(User))
        stmt = select(User).order_by(User.id).offset((page - 1) * size).limit(size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total or 0

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.commit()
        # refresh 从 DB 取回自增 id / 默认值（如 created_at）
        await self.session.refresh(user)
        return user

    async def update(self, user: User) -> User:
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self.session.delete(user)
        await self.session.commit()
