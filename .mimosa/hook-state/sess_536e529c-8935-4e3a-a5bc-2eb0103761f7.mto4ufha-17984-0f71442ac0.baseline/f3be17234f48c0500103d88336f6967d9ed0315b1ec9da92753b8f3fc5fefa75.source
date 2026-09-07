"""Aggregate all v1 sub-routers into one.

新增资源时，只需在此 `include_router` 你的子路由即可，
main.py 统一用 `prefix=settings.api_v1_prefix`（/api/v1）挂载。
"""
from fastapi import APIRouter

from app.api.v1 import users

api_router = APIRouter()
api_router.include_router(users.router)
