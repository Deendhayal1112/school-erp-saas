"""
Request Context.

Stores per-request metadata in a contextvars.ContextVar so it is accessible
from anywhere in the call stack without passing it explicitly through function
arguments.  This is thread-safe and async-safe.

Stored fields:
  - request_id        Unique per-request UUID (set by SecurityHeadersMiddleware)
  - correlation_id    Caller-supplied X-Correlation-ID header (for distributed tracing)
  - user_id           UUID of the authenticated user (None for anonymous requests)
  - school_id         UUID of the user's school tenant (None for anonymous requests)
  - role              Role code string of the authenticated user
  - permissions       Frozenset of permission code strings
  - request_start     Monotonic clock timestamp at request receipt
  - client_ip         Originating client IP address
  - request_path      HTTP request path
  - http_method       HTTP method (GET, POST, …)
"""

from __future__ import annotations

import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class RequestContext:
    """Encapsulates all per-request security and tracing metadata."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None

    # Auth context — populated after JWT validation
    user_id: uuid.UUID | None = None
    school_id: uuid.UUID | None = None
    role: str | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)

    # Request metadata
    request_start: float = field(default_factory=time.monotonic)
    client_ip: str | None = None
    request_path: str | None = None
    http_method: str | None = None

    @property
    def elapsed_ms(self) -> float:
        """Milliseconds elapsed since the request was received."""
        return (time.monotonic() - self.request_start) * 1000

    @property
    def is_authenticated(self) -> bool:
        """True when a user_id has been resolved from the JWT."""
        return self.user_id is not None

    def to_log_dict(self) -> dict:
        """Serializes the context to a dict safe for structured logging."""
        return {
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "user_id": str(self.user_id) if self.user_id else None,
            "school_id": str(self.school_id) if self.school_id else None,
            "role": self.role,
            "client_ip": self.client_ip,
            "path": self.request_path,
            "method": self.http_method,
        }


# The single ContextVar that holds the RequestContext for the current task.
_request_context_var: ContextVar[RequestContext | None] = ContextVar(
    "_request_context", default=None
)


def set_request_context(ctx: RequestContext) -> None:
    """Stores the context for the currently executing async task."""
    _request_context_var.set(ctx)


def get_request_context() -> RequestContext | None:
    """
    Returns the RequestContext for the currently executing async task,
    or None if no context has been set (e.g., background tasks).
    """
    return _request_context_var.get()


def get_request_id() -> str | None:
    """Convenience accessor for the current request's unique ID."""
    ctx = get_request_context()
    return ctx.request_id if ctx else None


def get_current_user_id() -> uuid.UUID | None:
    """Convenience accessor for the currently authenticated user ID."""
    ctx = get_request_context()
    return ctx.user_id if ctx else None


def get_current_school_id() -> uuid.UUID | None:
    """Convenience accessor for the currently authenticated school tenant ID."""
    ctx = get_request_context()
    return ctx.school_id if ctx else None
