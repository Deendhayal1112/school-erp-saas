"""
app/middleware — Authorization & Security Middleware Package.

Exports:
  RequestContextMiddleware    Creates per-request context ContextVar.
  SecurityHeadersMiddleware   Injects OWASP security response headers.
  AuthorizationAuditMiddleware JWT enrichment + structured audit logging.
  RequestContext              Dataclass for per-request metadata.
  AuditEvent                  Enum of all audit event types.
"""

from app.middleware.audit import (
    AuditEvent,
    log_authentication_failure,
    log_authorization_success,
    log_login_failure,
    log_login_success,
    log_logout,
    log_permission_denied,
    log_request_completed,
    log_request_received,
    log_role_denied,
    log_token_expired,
    log_token_validation_failure,
)
from app.middleware.authorization import (
    AuthorizationAuditMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.middleware.request_context import (
    RequestContext,
    get_current_school_id,
    get_current_user_id,
    get_request_context,
    get_request_id,
    set_request_context,
)

__all__ = [
    # Middlewares
    "RequestContextMiddleware",
    "SecurityHeadersMiddleware",
    "AuthorizationAuditMiddleware",
    # Request context
    "RequestContext",
    "get_request_context",
    "set_request_context",
    "get_request_id",
    "get_current_user_id",
    "get_current_school_id",
    # Audit
    "AuditEvent",
    "log_login_success",
    "log_login_failure",
    "log_logout",
    "log_token_validation_failure",
    "log_token_expired",
    "log_authentication_failure",
    "log_authorization_success",
    "log_permission_denied",
    "log_role_denied",
    "log_request_received",
    "log_request_completed",
]
