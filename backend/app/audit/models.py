"""
Audit Log Database Entity.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class AuditLog(Base):
    """System-wide audit trail model logging user actions and state modifications."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # Context references
    school_id = Column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Activity target details
    module = Column(String(50), nullable=False)
    entity_name = Column(String(100), nullable=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(String(50), nullable=False)

    # Tracing details
    client_ip = Column(String(45), nullable=True)
    request_id = Column(String(100), nullable=True)
    correlation_id = Column(String(100), nullable=True)

    # Dynamic context metadata
    metadata_json = Column(JSON, nullable=True)
