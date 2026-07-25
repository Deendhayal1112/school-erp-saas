from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Central Declarative Base class for all database models.
    All future domain-specific database models (e.g. Students, Teachers)
    will inherit from this Base class to share metadata and state.
    """
    pass


# Import all application models here to ensure they are registered
# on Base.metadata for Alembic autogeneration detection.
from app.models.base import BaseEntity
from app.models.school import School
from app.models.role import Role
