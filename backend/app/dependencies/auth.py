from fastapi import HTTPException, Request, status

from app.core import jwt


# ==========================================
# FastAPI HTTP Dependency Exceptions
# ==========================================
class MissingTokenException(HTTPException):
    """Raised when the authorization header or credentials are missing."""

    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class InvalidBearerTokenException(HTTPException):
    """Raised when the authorization header format does not comply with bearer schemes."""

    def __init__(self, detail: str = "Invalid bearer format"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthenticationRequiredException(HTTPException):
    """Raised when authentication is required but missing."""

    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class UserNotFoundException(HTTPException):
    """Raised when the token subject user cannot be found in the system."""

    def __init__(self, detail: str = "User not found"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


class InactiveAccountException(HTTPException):
    """Raised when the user account status is set to inactive."""

    def __init__(self, detail: str = "Inactive user account"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class InactiveSchoolException(HTTPException):
    """Raised when the user's school tenant is deactivated."""

    def __init__(self, detail: str = "Inactive school tenant"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class TokenExpiredException(HTTPException):
    """Raised when a cryptographic signature token has expired."""

    def __init__(self, detail: str = "Signature has expired"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


# ==========================================
# Reusable Dependency Helpers
# ==========================================
def extract_bearer_token(request: Request) -> str:
    """Extracts raw Authorization header string value from request."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise MissingTokenException("Authorization header is missing")
    return auth_header


def validate_bearer_format(header_value: str) -> str:
    """Validates Authorization string complies with Bearer schema regulations."""
    parts = header_value.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise InvalidBearerTokenException("Authorization scheme must be Bearer")
    return parts[1]


def decode_authenticated_user(token: str) -> dict:
    """Decodes JWT, translating internal signature errors to HTTP exceptions."""
    try:
        return jwt.decode_token(token)
    except jwt.TokenExpiredError as e:
        raise TokenExpiredException("Signature has expired") from e
    except jwt.JWTError as e:
        raise InvalidBearerTokenException("Invalid token signature or formatting") from e
