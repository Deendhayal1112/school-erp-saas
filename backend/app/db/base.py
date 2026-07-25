from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Central Declarative Base class for all database models.
    All future domain-specific database models (e.g. Students, Teachers)
    will inherit from this Base class to share metadata and state.
    """
    pass
