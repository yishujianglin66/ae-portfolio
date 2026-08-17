"""User 业务逻辑层。

编排 repository 调用，并承载业务规则（邮箱唯一性、密码哈希）。
这一层是"可单测"的核心：不依赖 HTTP，直接拿 repository 测即可。
"""
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserUpdate
from app.utils.exceptions import ConflictError, NotFoundError
from app.utils.security import hash_password


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def create_user(self, data: UserCreate) -> User:
        # 业务规则：邮箱唯一，重复注册返回 409 而非 500
        if await self.repository.get_by_email(data.email) is not None:
            raise ConflictError(f"Email {data.email} already registered")
        user = User(
            email=data.email,
            name=data.name,
            hashed_password=hash_password(data.password),
        )
        return await self.repository.create(user)

    async def get_user(self, user_id: int) -> User:
        user = await self.repository.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user

    async def list_users(self, *, page: int, size: int) -> tuple[list[User], int]:
        return await self.repository.list(page=page, size=size)

    async def update_user(self, user_id: int, data: UserUpdate) -> User:
        user = await self.get_user(user_id)  # 不存在则抛 404
        # 仅覆盖客户端提供的字段（PATCH 语义）
        if data.name is not None:
            user.name = data.name
        if data.is_active is not None:
            user.is_active = data.is_active
        if data.password is not None:
            user.hashed_password = hash_password(data.password)
        return await self.repository.update(user)

    async def delete_user(self, user_id: int) -> None:
        user = await self.get_user(user_id)
        await self.repository.delete(user)
