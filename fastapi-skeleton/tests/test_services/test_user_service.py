"""User service 单测：直接拿 repository 测业务逻辑，不依赖 HTTP。"""
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserUpdate
from app.services.user import UserService
from app.utils.exceptions import ConflictError, NotFoundError
from app.utils.security import verify_password


def _service(session):
    return UserService(UserRepository(session))


async def test_create_user_hashes_password(session):
    user = await _service(session).create_user(
        UserCreate(email="x@example.com", name="X", password="secret123")
    )
    assert user.id is not None
    assert user.hashed_password != "secret123"
    assert verify_password("secret123", user.hashed_password)


async def test_create_user_duplicate_email_raises(session):
    svc = _service(session)
    await svc.create_user(UserCreate(email="dup@example.com", name="A", password="secret123"))
    try:
        await svc.create_user(
            UserCreate(email="dup@example.com", name="B", password="secret123")
        )
        assert False, "expected ConflictError"
    except ConflictError:
        pass


async def test_update_user_partial(session):
    svc = _service(session)
    user = await svc.create_user(
        UserCreate(email="u@example.com", name="U", password="secret123")
    )
    updated = await svc.update_user(user.id, UserUpdate(name="Updated"))
    assert updated.name == "Updated"
    # 没改密码 => 原哈希保持不变
    assert updated.hashed_password == user.hashed_password


async def test_get_missing_user_raises(session):
    try:
        await _service(session).get_user(12345)
        assert False, "expected NotFoundError"
    except NotFoundError:
        pass


async def test_delete_user(session):
    svc = _service(session)
    user = await svc.create_user(
        UserCreate(email="d@example.com", name="D", password="secret123")
    )
    await svc.delete_user(user.id)
    assert await UserRepository(session).get(user.id) is None
