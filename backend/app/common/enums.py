"""
Platform Enums.
"""

from enum import Enum


class NotificationChannel(str, Enum):
    """Channels supported by the notification delivery service."""

    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


class StorageProviderType(str, Enum):
    """Storage provider backends supported by File Storage Service."""

    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"


class AuditAction(str, Enum):
    """Audit action types recorded in audit logs."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    PERMISSION_DENIED = "permission_denied"
    PASSWORD_CHANGE = "password_change"
    EMAIL_VERIFICATION = "email_verification"
