"""ORM models subpackage.

Importing this package registers all models onto `Base.metadata`,
which is what `database.init_db()` relies on to create tables.
"""
from app.models.user import User

__all__ = ["User"]
