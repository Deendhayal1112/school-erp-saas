"""
Audit Logging service implementation.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.core.config import settings
from app.middleware.request_context import get_request_context

logger = logging.getLogger(__name__)


class AuditLogService:
    """Provides platform audit logging operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log_action(
        self,
        module: str,
        action: str,
        entity_name: str | None = None,
        entity_id: uuid.UUID | None = None,
        metadata_json: dict[str, Any] | None = None,
        user_id: uuid.UUID | None = None,
        school_id: uuid.UUID | None = None,
    ) -> None:
        """
        Creates and persists an audit log record.
        Automatically resolves correlation contexts from the active RequestContext.
        """
        if not settings.ENABLE_AUDIT_LOG:
            return

        ctx = get_request_context()

        # Fallback values from request context variables
        resolved_user = user_id or (ctx.user_id if ctx else None)
        resolved_school = school_id or (ctx.school_id if ctx else None)
        client_ip = ctx.client_ip if ctx else None
        request_id = ctx.request_id if ctx else None
        correlation_id = ctx.correlation_id if ctx else None

        try:
            log_entry = AuditLog(
                user_id=resolved_user,
                school_id=resolved_school,
                module=module,
                action=action,
                entity_name=entity_name,
                entity_id=entity_id,
                client_ip=client_ip,
                request_id=request_id,
                correlation_id=correlation_id,
                metadata_json=metadata_json,
            )
            self.session.add(log_entry)
            await (
                self.session.flush()
            )  # Write to DB without committing transaction prematurely
            logger.debug(
                "Audit log written: module=%s, action=%s, user_id=%s",
                module,
                action,
                resolved_user,
            )
        except Exception as exc:
            # Prevent audit logging failures from crashing parent business transactions
            logger.exception("Failed to write audit log entry: %s", exc)
