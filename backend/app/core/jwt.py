import jwt

from app.core.config import settings


# ==========================================
# Reusable JWT Exceptions
# ==========================================
class JWTError(Exception):
    """Base exception for all JWT operations."""
    pass


class TokenExpiredError(JWTError):
    """Raised when the token signature has expired."""
    pass


class InvalidSignatureError(JWTError):
    """Raised when the cryptographic signature verification fails."""
    pass


class MalformedTokenError(JWTError):
    """Raised when the token format is invalid or cannot be parsed."""
    pass


class MissingClaimsError(JWTError):
    """Raised when required claims (e.g., 'sub', 'exp') are missing."""
    pass


class InvalidTokenError(JWTError):
    """General error for invalid tokens that do not fit other categories."""
    pass


# ==========================================
# Core JWT Operations
# ==========================================
def encode_token(payload: dict, secret_key: str | None = None, algorithm: str | None = None) -> str:
    """
    Encodes a dict payload into a signed JWT string.
    Uses centralized Settings configurations by default.
    """
    key = secret_key or settings.SECRET_KEY
    alg = algorithm or settings.ALGORITHM
    try:
        return jwt.encode(payload, key, algorithm=alg)
    except Exception as e:
        raise MalformedTokenError(f"Failed to encode token: {e!s}")


def decode_token(token: str, secret_key: str | None = None, algorithm: str | None = None) -> dict:
    """
    Decodes a JWT string and validates its cryptographic signature and expiration.
    Also asserts the presence of required claims ('sub', 'exp', 'type').
    """
    key = secret_key or settings.SECRET_KEY
    alg = algorithm or settings.ALGORITHM
    try:
        payload = jwt.decode(token, key, algorithms=[alg])
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("Token has expired.") from e
    except jwt.InvalidSignatureError as e:
        raise InvalidSignatureError("Token signature verification failed.") from e
    except jwt.DecodeError as e:
        raise MalformedTokenError("Token is malformed or invalid.") from e
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError("Token validation failed.") from e

    # Enforce standard required claims for security compliance
    for claim in ("sub", "exp", "type"):
        if claim not in payload:
            raise MissingClaimsError(f"Required claim '{claim}' is missing from token payload.")

    return payload
