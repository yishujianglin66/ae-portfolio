"""User 路由：把 HTTP 请求映射到 service 调用。

路由层的职责边界：
- 解析/校验请求（靠 Pydantic 的 request body + Query 参数）；
- 调用 service 拿到领域结果；
- 用 response_model 序列化返回。
业务规则一律不在路由里写，交给 service。
"""
from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_user_service
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    service: UserService = Depends(get_user_service),
) -> UserRead:
    user = await service.create_user(data)
    return UserRead.model_validate(user)


@router.get("", response_model=Page[UserRead])
async def list_users(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    size: int = Query(20, ge=1, le=100, description="每页条数，上限 100"),
    service: UserService = Depends(get_user_service),
) -> Page[UserRead]:
    items, total = await service.list_users(page=page, size=size)
    pages = (total + size - 1) // size if size else 0
    return Page[UserRead](
        items=[UserRead.model_validate(u) for u in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
) -> UserRead:
    user = await service.get_user(user_id)
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    data: UserUpdate,
    service: UserService = Depends(get_user_service),
) -> UserRead:
    user = await service.update_user(user_id, data)
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
) -> None:
    await service.delete_user(user_id)
    # 返回 204：FastAPI 会自动把 None 渲染为无 body 的 204 响应
