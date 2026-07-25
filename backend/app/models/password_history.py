"""
PasswordHistory — stores hashed copies of previous passwords
to prevent password reuse.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseEntity

if TYPE_CHECKING:
    from app.models.user import User


class PasswordHistory(BaseEntity):
    """
    Stores the bcrypt hashes of a user's previous passwords.
    The service layer checks this list before accepting a new password,
    preventing reuse of the last N passwords (configurable via settings).
    """

    __tablename__ = "password_history"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Bcrypt hash of the historical password
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="password_history")
