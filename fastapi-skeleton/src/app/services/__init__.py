"""Business-logic layer (services).

Services hold the rules: validation, uniqueness, hashing, orchestration.
They depend on repositories (injected), keeping them framework-agnostic and
easy to unit-test without HTTP/FastAPI.
"""
from app.services.user import UserService

__all__ = ["UserService"]
