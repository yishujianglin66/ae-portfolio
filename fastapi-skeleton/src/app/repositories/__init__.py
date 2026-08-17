"""Data-access layer (repositories).

Repositories encapsulate *all* SQL/ORM knowledge. Services call repositories
and never touch the session's query API directly. This makes the data source
swappable (e.g. for tests) without touching business logic.
"""
from app.repositories.user import UserRepository

__all__ = ["UserRepository"]
