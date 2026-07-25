from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.jwt import encode_token


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """
    Generates a short-lived cryptographic access token representing user identity.
    Uses ACCESS_TOKEN_EXPIRE_MINUTES config value by default.
    """
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    return encode_token(payload)


def create_refresh_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """
    Generates a long-lived session refresh token used to rotate access tokens.
    Uses REFRESH_TOKEN_EXPIRE_DAYS config value by default.
    """
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "refresh",
    }
    return encode_token(payload)
