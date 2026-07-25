import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BaseEntity(Base):
    """
    Abstract Base Entity class that serves as the foundation for all
    database models in the enterprise School ERP SaaS application.

    Provides standardized primary keys, audit tracing, status controls,
    and soft-delete capabilities.
    """

    __abstract__ = (
        True  # Prevents SQLAlchemy from creating a physical table for this class
    )

    # UUID Primary Key (placed at the top of the columns list)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        sort_order=-10,  # Ensures primary key is rendered first in schemas
    )

    # ==========================================
    # Audit Fields (Timezone-Aware)
    # ==========================================
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),  # Automatically updates timestamp on row changes
        nullable=False,
    )

    # ==========================================
    # Status Fields
    # ==========================================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # ==========================================
    # Soft Delete Fields
    # ==========================================
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
    )
