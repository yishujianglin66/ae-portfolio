"""跨资源复用的通用 Schema，例如分页包装。"""
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """通用分页响应：items + 分页元信息。

    用泛型避免为每个资源重复写 page 结构。
    """

    items: list[T]
    total: int
    page: int
    size: int
    pages: int
