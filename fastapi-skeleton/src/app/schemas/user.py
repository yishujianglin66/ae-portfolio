"""User 请求/响应 Schema（Pydantic v2）。

分层纪律：Schema 与 ORM 模型严格分离——
- 请求体（Create/Update）定义"允许客户端传入什么"；
- 响应体（Read）定义"返回给客户端什么"，且绝不暴露密码字段。
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=120)


class UserCreate(UserBase):
    # 明文密码仅出现在请求体，不会进入响应体
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """全字段可选：PATCH 语义，只更新提供的字段。"""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserRead(UserBase):
    """响应体。from_attributes=True 让它能从 ORM 对象直接 model_validate。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # 注意：无 hashed_password / password 字段 => 密码永不出网
